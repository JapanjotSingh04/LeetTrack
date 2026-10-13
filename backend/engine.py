"""
LeetTrack Engine
================
This module is a direct, unmodified extraction of the business logic from
`notebooks/LeetTrack_Engine.ipynb`. Every constant, formula, and query is
copied as-is from the notebook — nothing about the revision math, capacity
math, or question-selection logic has been changed.

The only difference from the notebook is *where* this code lives (a .py
module instead of notebook cells) and that `get_connection()` now reads its
credentials from environment variables instead of a hardcoded password (see
"IMPORTANT SECURITY REQUIREMENT" in the project brief) — that is the one
deliberate, necessary change, and it does not touch any business logic.
"""

import os
import tempfile
from datetime import date, timedelta

import mysql.connector

# --- Tunable constants (all pulled from the spec, unchanged from the original) ---

DAILY_CAPACITY = 100

# Workload "cost" of one question of each difficulty, against DAILY_CAPACITY.
QUESTION_CAPACITY = {
    "Easy": 30,
    "Medium": 40,
    "Hard": 55
}

# Days until the *first* revision, per difficulty. Each later revision doubles
# the previous interval (see get_revision_interval below).
REVISION_BASELINE_DAYS = {
    "Easy": 7,
    "Medium": 5,
    "Hard": 3
}

# How many times a question can be revised in total, per difficulty.
REVISION_LIMITS = {
    "Easy": 2,
    "Medium": 4,
    "Hard": 5
}


# --------------------------------------------------------------------------
# 2. Database connection
# --------------------------------------------------------------------------

class StaleRevisionError(Exception):
    """The row was changed by another request (e.g. a double click) first."""


def get_connection():
    """Open a bounded-timeout MySQL connection using environment configuration."""
    options = {
        "host": os.getenv("DB_HOST", "localhost"),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "database": os.getenv("DB_NAME", "leetcode_tracker"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "connection_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "8")),
        "autocommit": False,
    }
    ssl_ca = os.getenv("DB_SSL_CA", "").strip()
    ssl_pem = os.getenv("DB_SSL_CA_PEM", "").strip()
    if ssl_pem:
        global _DB_SSL_CA_TEMP_PATH
        if not globals().get("_DB_SSL_CA_TEMP_PATH"):
            handle = tempfile.NamedTemporaryFile(mode="w", suffix=".pem", prefix="leettrack-ca-", delete=False)
            try:
                handle.write(ssl_pem + "\n")
                handle.flush()
                _DB_SSL_CA_TEMP_PATH = handle.name
            finally:
                handle.close()
            try:
                os.chmod(_DB_SSL_CA_TEMP_PATH, 0o600)
            except OSError:
                pass
        ssl_ca = _DB_SSL_CA_TEMP_PATH
    production = os.getenv("APP_ENV", "development").lower() == "production"
    if production and not ssl_ca:
        raise RuntimeError("Configure DB_SSL_CA or DB_SSL_CA_PEM for verified production database TLS.")
    if ssl_ca:
        # The certificate chain is ALWAYS verified. Hostname matching is on by default;
        # set DB_SSL_VERIFY_IDENTITY=false only if your provider's certificate does not
        # contain the host name (equivalent to the MySQL "VERIFY_CA" mode).
        verify_identity = os.getenv("DB_SSL_VERIFY_IDENTITY", "true").strip().lower() not in ("0", "false", "no")
        options.update({"ssl_ca": ssl_ca, "ssl_verify_cert": True, "ssl_verify_identity": verify_identity})
    elif production:
        raise RuntimeError("Verified database TLS is required in production.")
    return mysql.connector.connect(**options)


# --------------------------------------------------------------------------
# 3. Generic DB read/write helper
# --------------------------------------------------------------------------

def run_query(conn, query, params=None, fetch=False, many=False):
    """
    Execute one SQL statement against `conn`.

    fetch=True   -> SELECT: returns list[dict] (one dict per row).
    fetch=False  -> INSERT/UPDATE/DELETE: commits and returns affected row count.
    many=True    -> params is a list of tuples; uses executemany (bulk insert).

    Centralizing this means every read/write persists correctly (commit is
    never forgotten) and every SELECT comes back as friendly dicts instead of
    raw tuples indexed by position.
    """
    cursor = conn.cursor(dictionary=True)
    try:
        if many:
            cursor.executemany(query, params or [])
        else:
            cursor.execute(query, params or ())

        if fetch:
            return cursor.fetchall()

        conn.commit()
        return cursor.rowcount
    finally:
        cursor.close()


# --------------------------------------------------------------------------
# 4. Revision math (pure functions)
# --------------------------------------------------------------------------

def get_revision_interval(difficulty, revision_counter):
    """
    Days until the *next* revision, given how many revisions have already
    happened. The interval doubles every time:
        Easy:   7  -> 14 -> 28
        Medium: 5  -> 10 -> 20 -> 40
        Hard:   3  -> 6  -> 12 -> 24 -> 48
    """
    baseline = REVISION_BASELINE_DAYS[difficulty]
    return baseline * (2 ** revision_counter)


def can_be_revised(difficulty, revision_counter):
    """True if this question still has revisions left for its difficulty."""
    return revision_counter < REVISION_LIMITS[difficulty]


def get_next_revision_date(base_date, difficulty, revision_counter):
    """
    Due date for the next revision at this revision_counter, counted from
    base_date. Returns None once the difficulty's revision limit is reached
    (i.e. there is no "next" revision left).
    """
    if not can_be_revised(difficulty, revision_counter):
        return None
    return base_date + timedelta(days=get_revision_interval(difficulty, revision_counter))


# --------------------------------------------------------------------------
# 5. Revision scheduling (DB query)
# --------------------------------------------------------------------------

def get_due_revisions(conn, user_id, target_date=None):
    """
    This user's solved questions whose next revision is due
    (due_date <= target_date). target_date defaults to date.today() — pass
    a different date to see the queue as of a simulated date (past or
    future) instead of the real system date.

    Relies on due_date being NULL once a question's revision limit is used
    up (see get_next_revision_date), so exhausted questions are naturally
    excluded -- no need to repeat REVISION_LIMITS again inside the SQL.
    """
    target_date = target_date or date.today()
    return run_query(conn, """
        SELECT
            sq.question_id, sq.platform, qb.title, qb.difficulty, qb.topic, qb.url,
            sq.solved_date, sq.revision_counter, sq.last_revision_date, sq.due_date
        FROM solved_questions AS sq
        JOIN question_bank AS qb
            ON sq.question_id = qb.question_id AND sq.platform = qb.platform
        WHERE sq.user_id = %s
            AND sq.due_date IS NOT NULL
            AND sq.due_date <= %s
        ORDER BY sq.due_date ASC
    """, (user_id, target_date), fetch=True)


# --------------------------------------------------------------------------
# 6. New-question selection (DB query)
# --------------------------------------------------------------------------

def get_new_questions(conn, user_id, new_mix):
    """
    Pick up to `count` questions per difficulty that this user has not solved
    yet (no row in solved_questions). new_mix looks like
    {"Easy": 2, "Medium": 1, "Hard": 0}, as produced by find_best_new_question_mix.
    """
    questions = []
    for difficulty, count in new_mix.items():
        if count == 0:
            continue

        rows = run_query(conn, """
            SELECT qb.question_id, qb.platform, qb.title, qb.difficulty, qb.topic, qb.url
            FROM question_bank AS qb
            LEFT JOIN solved_questions AS sq
                ON qb.question_id = sq.question_id
                AND qb.platform = sq.platform
                AND sq.user_id = %s
            WHERE sq.question_id IS NULL
                AND qb.difficulty = %s
            ORDER BY qb.question_id
            LIMIT %s
        """, (user_id, difficulty, count), fetch=True)

        questions.extend(rows)

    return questions


# --------------------------------------------------------------------------
# 7. Capacity & daily plan generation
# --------------------------------------------------------------------------

def calculate_capacity_usage(questions):
    """Total capacity consumed by a list of question dicts (each has 'difficulty')."""
    return sum(QUESTION_CAPACITY[q["difficulty"]] for q in questions)


def find_best_new_question_mix(remaining_capacity):
    """
    Brute-force search over (Easy, Medium, Hard) counts for the combination that
    uses as much of remaining_capacity as possible without exceeding it.
    The search space is tiny (at most remaining_capacity // 30 per difficulty),
    so brute force is fine at this scale -- same approach as the original.
    """
    best_mix = {"Easy": 0, "Medium": 0, "Hard": 0}
    best_used = 0

    max_hard = remaining_capacity // QUESTION_CAPACITY["Hard"]
    max_medium = remaining_capacity // QUESTION_CAPACITY["Medium"]
    max_easy = remaining_capacity // QUESTION_CAPACITY["Easy"]

    for hard in range(max_hard + 1):
        for medium in range(max_medium + 1):
            for easy in range(max_easy + 1):
                used = (hard * QUESTION_CAPACITY["Hard"]
                        + medium * QUESTION_CAPACITY["Medium"]
                        + easy * QUESTION_CAPACITY["Easy"])
                if used <= remaining_capacity and used > best_used:
                    best_used = used
                    best_mix = {"Easy": easy, "Medium": medium, "Hard": hard}

    return best_mix, best_used


def create_daily_plan(conn, user_id, target_date=None):
    """
    Build the plan for a user as of target_date (defaults to date.today()):
    due revisions always go in first (and consume capacity), then whatever
    capacity remains is filled with new questions. Passing a target_date
    other than today simulates what the plan looked like / will look like
    on that date, without changing any stored data.
    """
    target_date = target_date or date.today()
    revisions = get_due_revisions(conn, user_id, target_date)
    revision_capacity = calculate_capacity_usage(revisions)
    remaining_capacity = max(0, DAILY_CAPACITY - revision_capacity)

    new_mix, new_capacity = find_best_new_question_mix(remaining_capacity)
    new_questions = get_new_questions(conn, user_id, new_mix)

    return {
        "revisions": revisions,
        "new_questions": new_questions,
        "new_mix": new_mix,
        "revision_capacity": revision_capacity,
        "new_capacity": new_capacity,
        "remaining_capacity": remaining_capacity
    }


# --------------------------------------------------------------------------
# 8. Persisting progress (solve / revision) to MySQL
# --------------------------------------------------------------------------

def record_question_progress(conn, user_id, question_id, platform, difficulty,
                               activity_date, revision_counter=None):
    """
    Persist a solve/revision event and return the resulting state.

    - revision_counter=None -> brand-new solve: INSERT a row with
      revision_counter=0 and the first due_date.
    - revision_counter=<int> -> a revision was just completed: UPDATE the row,
      incrementing the counter and recomputing due_date (None once the
      difficulty's revision limit is reached).
    """
    if revision_counter is None:
        next_counter = 0
        due_date = get_next_revision_date(activity_date, difficulty, next_counter)

        run_query(conn, """
            INSERT INTO solved_questions
                (user_id, question_id, platform, solved_date,
                 revision_counter, last_revision_date, due_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (user_id, question_id, platform, activity_date,
              next_counter, activity_date, due_date))

        return {
            "type": "new_question",
            "revision_counter": next_counter,
            "last_revision_date": activity_date,
            "due_date": due_date
        }

    next_counter = revision_counter + 1
    due_date = get_next_revision_date(activity_date, difficulty, next_counter)

    # "AND revision_counter = %s" makes this an atomic compare-and-set: if two
    # requests race (double click), only the first one changes the row.
    updated = run_query(conn, """
        UPDATE solved_questions
        SET revision_counter = %s, last_revision_date = %s, due_date = %s
        WHERE user_id = %s AND question_id = %s AND platform = %s
            AND revision_counter = %s
    """, (next_counter, activity_date, due_date, user_id, question_id, platform,
          revision_counter))
    if updated != 1:
        raise StaleRevisionError("This revision was already recorded.")

    return {
        "type": "revision",
        "revision_counter": next_counter,
        "last_revision_date": activity_date,
        "due_date": due_date,
        "completed": due_date is None
    }
