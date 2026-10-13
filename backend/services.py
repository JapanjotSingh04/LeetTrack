"""
Service layer sitting between the FastAPI routes and the engine/database.
Routes stay thin: they call a service function and turn any raised
NotFoundError / ConflictError / ValidationError into the right HTTP status
code. All actual SQL happens in engine.py — this file never writes raw SQL
of its own beyond the small existence-checks needed for good error messages.
"""

from datetime import date, datetime, timedelta

import mysql.connector

import engine


# --------------------------------------------------------------------------
# Errors (translated to HTTP status codes in main.py)
# --------------------------------------------------------------------------

class NotFoundError(Exception):
    pass


class ConflictError(Exception):
    pass


class ValidationError(Exception):
    pass


# --------------------------------------------------------------------------
# JSON-safety helpers
# --------------------------------------------------------------------------

def _serialize_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, timedelta):
        return value.days
    return value


def _serialize_row(row: dict) -> dict:
    return {k: _serialize_value(v) for k, v in row.items()}


def _serialize_rows(rows):
    return [_serialize_row(r) for r in rows]


# --------------------------------------------------------------------------
# Small existence checks (used for clear 404s instead of opaque SQL errors)
# --------------------------------------------------------------------------

def _user_exists(conn, user_id: int) -> bool:
    rows = engine.run_query(
        conn, "SELECT user_id FROM users WHERE user_id = %s", (user_id,), fetch=True
    )
    return len(rows) > 0


def _get_question(conn, question_id: int, platform: str):
    rows = engine.run_query(
        conn,
        "SELECT * FROM question_bank WHERE question_id = %s AND platform = %s",
        (question_id, platform),
        fetch=True,
    )
    return rows[0] if rows else None


def _get_solved_row(conn, user_id: int, question_id: int, platform: str):
    rows = engine.run_query(
        conn,
        """SELECT * FROM solved_questions
           WHERE user_id = %s AND question_id = %s AND platform = %s""",
        (user_id, question_id, platform),
        fetch=True,
    )
    return rows[0] if rows else None


# --------------------------------------------------------------------------
# Users
# --------------------------------------------------------------------------

def get_user(conn, user_id: int) -> dict:
    rows = engine.run_query(
        conn, "SELECT user_id, username, email FROM users WHERE user_id = %s", (user_id,), fetch=True
    )
    if not rows:
        raise NotFoundError("User not found.")
    return _serialize_row(rows[0])


# --------------------------------------------------------------------------
# Daily plan
# --------------------------------------------------------------------------

def get_daily_plan(conn, user_id: int, target_date: date = None) -> dict:
    """
    Build the dashboard's daily plan as of `target_date` (defaults to
    date.today()). This is what powers the "Simulated Date" feature: pass
    any date here to see what the plan (due revisions + new-question mix)
    would have looked like — or will look like — on that day. Only affects
    *reads*; completing a question/revision still always records against
    the real date.today(), regardless of what date is being simulated.
    """
    if not _user_exists(conn, user_id):
        raise NotFoundError("User not found.")

    plan_date = target_date or date.today()
    plan = engine.create_daily_plan(conn, user_id, plan_date)

    return {
        "date": plan_date.isoformat(),
        "is_simulated": plan_date != date.today(),
        "revisions": _serialize_rows(plan["revisions"]),
        "new_questions": _serialize_rows(plan["new_questions"]),
        "new_mix": plan["new_mix"],
        "revision_capacity": plan["revision_capacity"],
        "new_capacity": plan["new_capacity"],
        "remaining_capacity": plan["remaining_capacity"],
        "daily_capacity": engine.DAILY_CAPACITY,
        "used_capacity": plan["revision_capacity"] + plan["new_capacity"],
    }


# --------------------------------------------------------------------------
# Complete a brand-new question
# --------------------------------------------------------------------------

def complete_question(conn, user_id: int, question_id: int, platform: str, difficulty: str) -> dict:
    if not _user_exists(conn, user_id):
        raise NotFoundError("User not found.")

    question = _get_question(conn, question_id, platform)
    if question is None:
        raise NotFoundError(f"Question {question_id} ({platform}) not found.")

    if difficulty not in engine.REVISION_BASELINE_DAYS:
        raise ValidationError(f"Unknown difficulty '{difficulty}'.")
    if question["difficulty"] != difficulty:
        raise ValidationError(
            f"Difficulty mismatch: question {question_id} is {question['difficulty']}, "
            f"not {difficulty}."
        )

    if _get_solved_row(conn, user_id, question_id, platform) is not None:
        raise ConflictError(f"Question {question_id} is already solved.")

    try:
        result = engine.record_question_progress(
            conn, user_id, question_id, platform, difficulty,
            activity_date=date.today(), revision_counter=None
        )
    except mysql.connector.IntegrityError:
        # Two simultaneous requests: the primary key stopped the second one.
        conn.rollback()
        raise ConflictError(f"Question {question_id} is already solved.")
    return {
        "question_id": question_id,
        "platform": platform,
        "title": question["title"],
        **_serialize_row(result),
    }


# --------------------------------------------------------------------------
# Complete a revision
# --------------------------------------------------------------------------

def complete_revision(conn, user_id: int, question_id: int, platform: str,
                       difficulty: str, revision_counter: int) -> dict:
    if not _user_exists(conn, user_id):
        raise NotFoundError("User not found.")

    question = _get_question(conn, question_id, platform)
    if question is None:
        raise NotFoundError(f"Question {question_id} ({platform}) not found.")

    solved_row = _get_solved_row(conn, user_id, question_id, platform)
    if solved_row is None:
        raise NotFoundError(
            f"Question {question_id} has not been solved yet; "
            f"cannot complete a revision for it."
        )

    if solved_row["revision_counter"] != revision_counter:
        raise ValidationError(
            f"Stale revision_counter: question {question_id} is currently at "
            f"revision_counter={solved_row['revision_counter']}, not {revision_counter}."
        )

    if difficulty not in engine.REVISION_BASELINE_DAYS:
        raise ValidationError(f"Unknown difficulty '{difficulty}'.")

    if not engine.can_be_revised(difficulty, revision_counter):
        raise ConflictError(
            f"Question {question_id} has already used all of its "
            f"{engine.REVISION_LIMITS[difficulty]} revisions for {difficulty}."
        )

    try:
        result = engine.record_question_progress(
            conn, user_id, question_id, platform, difficulty,
            activity_date=date.today(), revision_counter=revision_counter
        )
    except engine.StaleRevisionError:
        raise ConflictError("This revision was already recorded. Refresh and try again.")
    return {
        "question_id": question_id,
        "platform": platform,
        "title": question["title"],
        **_serialize_row(result),
    }


# --------------------------------------------------------------------------
# Solved questions / upcoming revisions / question bank / progress
# --------------------------------------------------------------------------

def get_solved_questions(conn, user_id: int) -> list:
    if not _user_exists(conn, user_id):
        raise NotFoundError("User not found.")

    rows = engine.run_query(conn, """
        SELECT sq.question_id, sq.platform, qb.title, qb.difficulty, qb.topic, qb.url,
               sq.solved_date, sq.revision_counter, sq.last_revision_date, sq.due_date
        FROM solved_questions AS sq
        JOIN question_bank AS qb
            ON sq.question_id = qb.question_id AND sq.platform = qb.platform
        WHERE sq.user_id = %s
        ORDER BY sq.solved_date DESC
    """, (user_id,), fetch=True)
    return _serialize_rows(rows)


def get_upcoming_revisions(conn, user_id: int) -> list:
    """All future (not-yet-due) revisions, soonest first — a superset view of
    get_due_revisions() for a 'what's coming up' page rather than 'due today'."""
    if not _user_exists(conn, user_id):
        raise NotFoundError("User not found.")

    rows = engine.run_query(conn, """
        SELECT sq.question_id, sq.platform, qb.title, qb.difficulty, qb.topic, qb.url,
               sq.solved_date, sq.revision_counter, sq.last_revision_date, sq.due_date
        FROM solved_questions AS sq
        JOIN question_bank AS qb
            ON sq.question_id = qb.question_id AND sq.platform = qb.platform
        WHERE sq.user_id = %s
            AND sq.due_date IS NOT NULL
        ORDER BY sq.due_date ASC
    """, (user_id,), fetch=True)
    return _serialize_rows(rows)


def get_questions(conn, difficulty: str = None, topic: str = None,
                   platform: str = None, user_id: int = None) -> list:
    query = """
        SELECT qb.question_id, qb.platform, qb.title, qb.difficulty, qb.topic, qb.url,
               CASE WHEN sq.question_id IS NOT NULL THEN 1 ELSE 0 END AS solved
        FROM question_bank AS qb
        LEFT JOIN solved_questions AS sq
            ON qb.question_id = sq.question_id
            AND qb.platform = sq.platform
            AND sq.user_id = %s
        WHERE 1 = 1
    """
    params = [user_id]

    if difficulty:
        query += " AND qb.difficulty = %s"
        params.append(difficulty)
    if topic:
        query += " AND qb.topic = %s"
        params.append(topic)
    if platform:
        query += " AND qb.platform = %s"
        params.append(platform)

    query += " ORDER BY qb.question_id"

    rows = engine.run_query(conn, query, tuple(params), fetch=True)
    return _serialize_rows(rows)


def get_progress(conn, user_id: int) -> dict:
    if not _user_exists(conn, user_id):
        raise NotFoundError("User not found.")

    totals = engine.run_query(conn, """
        SELECT qb.difficulty, COUNT(*) AS count
        FROM solved_questions AS sq
        JOIN question_bank AS qb
            ON sq.question_id = qb.question_id AND sq.platform = qb.platform
        WHERE sq.user_id = %s
        GROUP BY qb.difficulty
    """, (user_id,), fetch=True)

    by_difficulty = {"Easy": 0, "Medium": 0, "Hard": 0}
    for row in totals:
        by_difficulty[row["difficulty"]] = row["count"]
    total_solved = sum(by_difficulty.values())

    revisions_completed_row = engine.run_query(conn, """
        SELECT COALESCE(SUM(revision_counter), 0) AS total
        FROM solved_questions
        WHERE user_id = %s
    """, (user_id,), fetch=True)
    revisions_completed = revisions_completed_row[0]["total"]

    over_time = engine.run_query(conn, """
        SELECT solved_date, COUNT(*) AS count
        FROM solved_questions
        WHERE user_id = %s
        GROUP BY solved_date
        ORDER BY solved_date ASC
    """, (user_id,), fetch=True)

    return {
        "total_solved": total_solved,
        "easy_solved": by_difficulty["Easy"],
        "medium_solved": by_difficulty["Medium"],
        "hard_solved": by_difficulty["Hard"],
        "revisions_completed": revisions_completed,
        "solved_over_time": _serialize_rows(over_time),
    }
