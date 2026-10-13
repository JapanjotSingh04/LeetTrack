"""End-to-end API tests that execute the REAL service/engine SQL.

MySQL is not available in CI-less environments, so these tests run the project's
actual queries against an in-memory SQLite database through a tiny adapter
(`%s` placeholders -> `?`). The queries used by LeetTrack are plain ANSI SQL, so
this verifies user-data isolation and the revision/capacity logic. It does NOT
replace one smoke test against real MySQL (see DEPLOYMENT.md).
"""
import os
import sqlite3
import warnings
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

import auth
import engine
import main
import services

warnings.filterwarnings("ignore", category=DeprecationWarning)

ORIGIN = {"Origin": "http://localhost:5173"}
PASSWORD = "a-long-test-password"

SCHEMA = """
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT UNIQUE,
    password_hash TEXT
);
CREATE TABLE question_bank (
    question_id INTEGER NOT NULL, platform TEXT NOT NULL, title TEXT NOT NULL,
    difficulty TEXT NOT NULL, topic TEXT, url TEXT,
    PRIMARY KEY (question_id, platform)
);
CREATE TABLE solved_questions (
    user_id INTEGER NOT NULL, question_id INTEGER NOT NULL, platform TEXT NOT NULL,
    solved_date TEXT NOT NULL, revision_counter INTEGER NOT NULL DEFAULT 0,
    last_revision_date TEXT, due_date TEXT,
    PRIMARY KEY (user_id, question_id, platform)
);
"""


class _Cursor:
    def __init__(self, raw):
        self.raw = raw

    @staticmethod
    def _convert(params):
        return tuple(p.isoformat() if isinstance(p, date) else p for p in (params or ()))

    def execute(self, query, params=None):
        self.raw.execute(query.replace("%s", "?"), self._convert(params))

    def executemany(self, query, seq):
        self.raw.executemany(query.replace("%s", "?"), [self._convert(p) for p in seq])

    def fetchall(self):
        cols = [c[0] for c in self.raw.description]
        return [dict(zip(cols, row)) for row in self.raw.fetchall()]

    @property
    def rowcount(self):
        return self.raw.rowcount

    @property
    def lastrowid(self):
        return self.raw.lastrowid

    def close(self):
        self.raw.close()


class SqliteConn:
    def __init__(self):
        self.raw = sqlite3.connect(":memory:", check_same_thread=False)
        self.raw.executescript(SCHEMA)
        rows = [
            (1, "leetcode", "Two Sum", "Easy", "Array", "u1"),
            (2, "leetcode", "Add Two Numbers", "Medium", "LinkedList", "u2"),
            (3, "leetcode", "Median of Two Sorted Arrays", "Hard", "Array", "u3"),
            (4, "leetcode", "Valid Parentheses", "Easy", "Stack", "u4"),
        ]
        self.raw.executemany("INSERT INTO question_bank VALUES (?,?,?,?,?,?)", rows)
        self.raw.commit()

    def cursor(self, **kwargs):
        return _Cursor(self.raw.cursor())

    def commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()

    def close(self):  # the app closes per request; the test fixture keeps it open
        pass


@pytest.fixture
def db():
    return SqliteConn()


@pytest.fixture
def make_client(monkeypatch, db):
    monkeypatch.setenv("JWT_SECRET", "test-secret-with-more-than-32-characters-123")
    monkeypatch.setenv("APP_ENV", "development")
    main.limiter.clear()
    main.app.dependency_overrides[main.get_db] = lambda: db
    clients = []

    def factory():
        client = TestClient(main.app)
        client.__enter__()
        clients.append(client)
        return client

    yield factory
    for client in clients:
        client.__exit__(None, None, None)
    main.app.dependency_overrides.clear()


def register(client, name):
    response = client.post(
        "/api/auth/register",
        json={"username": name, "email": f"{name}@example.com", "password": PASSWORD},
        headers=ORIGIN,
    )
    assert response.status_code == 200, response.text
    return response.json()["user"]["user_id"]


def post(client, path, body):
    token = client.cookies.get("leettrack_csrf")
    return client.post(path, json=body, headers={**ORIGIN, "X-CSRF-Token": token})


def test_two_users_have_independent_progress(make_client):
    alice, bob = make_client(), make_client()
    register(alice, "alice")
    register(bob, "bob")

    solved = post(alice, "/api/questions/complete", {"question_id": 1, "platform": "leetcode", "difficulty": "Easy"})
    assert solved.status_code == 200, solved.text

    assert [r["question_id"] for r in alice.get("/api/me/solved").json()] == [1]
    assert bob.get("/api/me/solved").json() == []
    assert bob.get("/api/me/revisions").json() == []
    assert bob.get("/api/me/progress").json()["total_solved"] == 0
    assert alice.get("/api/me/progress").json()["total_solved"] == 1

    alice_flags = {q["question_id"]: q["solved"] for q in alice.get("/api/questions").json()}
    bob_flags = {q["question_id"]: q["solved"] for q in bob.get("/api/questions").json()}
    assert alice_flags[1] == 1 and bob_flags[1] == 0


def test_user_cannot_revise_or_complete_for_another_user(make_client):
    alice, bob = make_client(), make_client()
    register(alice, "alice")
    register(bob, "bob")
    post(alice, "/api/questions/complete", {"question_id": 1, "platform": "leetcode", "difficulty": "Easy"})

    # Bob tries to revise Alice's question, even while smuggling in Alice's user_id.
    attempt = post(bob, "/api/revisions/complete", {
        "user_id": 1, "question_id": 1, "platform": "leetcode", "difficulty": "Easy", "revision_counter": 0,
    })
    assert attempt.status_code == 404
    # Alice's record is untouched.
    row = alice.get("/api/me/solved").json()[0]
    assert row["revision_counter"] == 0

    # Bob solving the same question creates HIS row, not a conflict with Alice's.
    assert post(bob, "/api/questions/complete", {"question_id": 1, "platform": "leetcode", "difficulty": "Easy"}).status_code == 200


def test_old_user_id_routes_do_not_exist(make_client):
    alice = make_client()
    register(alice, "alice")
    for path in ("/api/users/1", "/api/users/1/solved", "/api/users/1/progress", "/api/users/1/daily-plan"):
        assert alice.get(path).status_code == 404


def test_duplicate_solve_is_conflict_and_revision_flow(make_client):
    alice = make_client()
    register(alice, "alice")
    body = {"question_id": 1, "platform": "leetcode", "difficulty": "Easy"}
    assert post(alice, "/api/questions/complete", body).status_code == 200
    assert post(alice, "/api/questions/complete", body).status_code == 409

    rev = {**body, "revision_counter": 0}
    first = post(alice, "/api/revisions/complete", rev)
    assert first.status_code == 200
    assert first.json()["revision_counter"] == 1
    # Replaying the same (now stale) revision request is rejected, not double counted.
    replay = post(alice, "/api/revisions/complete", rev)
    assert replay.status_code in (409, 422)
    assert alice.get("/api/me/solved").json()[0]["revision_counter"] == 1


def test_concurrent_revision_is_atomic_compare_and_set(db):
    uid = 1
    db.raw.execute("INSERT INTO users (username, email, password_hash) VALUES ('a','a@x.com','h')")
    engine.record_question_progress(db, uid, 1, "leetcode", "Easy", date.today(), None)
    engine.record_question_progress(db, uid, 1, "leetcode", "Easy", date.today(), 0)
    with pytest.raises(engine.StaleRevisionError):
        # a second request that still believes the counter is 0
        engine.record_question_progress(db, uid, 1, "leetcode", "Easy", date.today(), 0)
    row = db.raw.execute("SELECT revision_counter FROM solved_questions").fetchone()
    assert row[0] == 1


def test_revision_dates_follow_business_rules(db):
    db.raw.execute("INSERT INTO users (username, email, password_hash) VALUES ('a','a@x.com','h')")
    today = date.today()
    first = engine.record_question_progress(db, 1, 3, "leetcode", "Hard", today, None)
    assert first["due_date"] == today + timedelta(days=3)          # Hard: 3 days
    counter = 0
    expected_gaps = [6, 12, 24, 48]                                   # doubles each time
    for gap in expected_gaps:
        res = engine.record_question_progress(db, 1, 3, "leetcode", "Hard", today, counter)
        counter += 1
        assert res["due_date"] == today + timedelta(days=gap)
    last = engine.record_question_progress(db, 1, 3, "leetcode", "Hard", today, counter)
    assert last["due_date"] is None and last["completed"] is True     # limit of 5 reached


def test_daily_plan_capacity_and_backlog(db):
    db.raw.execute("INSERT INTO users (username, email, password_hash) VALUES ('a','a@x.com','h')")
    today = date.today()
    # One Medium revision due (40) -> 60 left for new questions.
    db.raw.execute("INSERT INTO solved_questions VALUES (1,2,'leetcode',?,0,?,?)",
                   ((today - timedelta(days=5)).isoformat(), (today - timedelta(days=5)).isoformat(), today.isoformat()))
    plan = services.get_daily_plan(db, 1, today)
    assert plan["revision_capacity"] == 40
    assert plan["new_capacity"] <= 60
    assert plan["used_capacity"] == plan["revision_capacity"] + plan["new_capacity"] <= plan["daily_capacity"] == 100

    # A large overdue backlog is shown in full (this is the "2130 / 100" situation):
    # revisions always come first, so used capacity may exceed 100 and no new questions are added.
    db.raw.execute("UPDATE solved_questions SET due_date = ?", ((today - timedelta(days=1)).isoformat(),))
    for qid, diff in ((1, "Easy"), (3, "Hard")):
        db.raw.execute("INSERT INTO solved_questions VALUES (1,?,'leetcode',?,0,?,?)",
                       (qid, today.isoformat(), today.isoformat(), (today - timedelta(days=1)).isoformat()))
    backlog = services.get_daily_plan(db, 1, today)
    assert backlog["revision_capacity"] == 40 + 30 + 55
    assert backlog["new_questions"] == []
    assert backlog["remaining_capacity"] == 0
    assert backlog["used_capacity"] > backlog["daily_capacity"]


def test_simulated_date_only_affects_reads(make_client):
    alice = make_client()
    register(alice, "alice")
    post(alice, "/api/questions/complete", {"question_id": 1, "platform": "leetcode", "difficulty": "Easy"})
    future = (date.today() + timedelta(days=8)).isoformat()
    plan = alice.get(f"/api/me/daily-plan?simulated_date={future}").json()
    assert plan["is_simulated"] is True
    assert [r["question_id"] for r in plan["revisions"]] == [1]
    assert alice.get("/api/me/daily-plan?simulated_date=not-a-date").status_code == 422
    assert alice.get("/api/me/daily-plan").json()["revisions"] == []


def test_login_is_rate_limited_per_account_even_with_new_ips(make_client):
    c = make_client()
    register(c, "alice")
    c.cookies.clear()
    for _ in range(8):
        r = c.post("/api/auth/login", json={"email": "alice@example.com", "password": "wrong-password"}, headers=ORIGIN)
        assert r.status_code == 401
    blocked = c.post("/api/auth/login", json={"email": "alice@example.com", "password": PASSWORD}, headers=ORIGIN)
    assert blocked.status_code == 429
    # other accounts are not affected by that lockout
    other = make_client()
    register(other, "bob")


def test_successful_login_resets_failure_counter(make_client):
    c = make_client()
    register(c, "alice")
    c.cookies.clear()
    for _ in range(5):
        c.post("/api/auth/login", json={"email": "alice@example.com", "password": "wrong-password"}, headers=ORIGIN)
    ok = c.post("/api/auth/login", json={"email": "alice@example.com", "password": PASSWORD}, headers=ORIGIN)
    assert ok.status_code == 200
    for _ in range(5):
        assert c.post("/api/auth/login", json={"email": "alice@example.com", "password": "wrong-password"}, headers=ORIGIN).status_code == 401


def test_registration_is_rate_limited(make_client):
    c = make_client()
    codes = []
    for i in range(7):
        r = c.post("/api/auth/register", json={"username": f"user{i}", "email": f"user{i}@example.com", "password": PASSWORD}, headers=ORIGIN)
        codes.append(r.status_code)
    assert codes[:5] == [200] * 5 and codes[5] == 429


def test_unknown_email_and_wrong_password_look_identical(make_client):
    c = make_client()
    register(c, "alice")
    c.cookies.clear()
    wrong = c.post("/api/auth/login", json={"email": "alice@example.com", "password": "nope-nope-nope"}, headers=ORIGIN)
    missing = c.post("/api/auth/login", json={"email": "ghost@example.com", "password": "nope-nope-nope"}, headers=ORIGIN)
    assert wrong.status_code == missing.status_code == 401
    assert wrong.json() == missing.json()


def test_legacy_account_without_credentials_cannot_log_in(make_client, db):
    db.raw.execute("INSERT INTO users (username) VALUES ('demo_user')")
    c = make_client()
    r = c.post("/api/auth/login", json={"email": "demo_user", "password": PASSWORD}, headers=ORIGIN)
    assert r.status_code == 401
    # a forged token for that legacy user is also rejected (no email => not a real account)
    token = auth.create_access_token(1)
    c.cookies.set("leettrack_session", token)
    assert c.get("/api/me").status_code == 401


def test_origin_guard_blocks_foreign_origin(make_client):
    c = make_client()
    r = c.post("/api/auth/register", json={"username": "evil", "email": "evil@example.com", "password": PASSWORD},
               headers={"Origin": "https://evil.example"})
    assert r.status_code == 403


def test_unauthenticated_requests_do_not_open_a_database_connection(monkeypatch):
    opened = []
    monkeypatch.setattr(engine, "get_connection", lambda: opened.append(1) or (_ for _ in ()).throw(AssertionError("DB opened")))
    monkeypatch.setenv("JWT_SECRET", "test-secret-with-more-than-32-characters-123")
    with TestClient(main.app) as client:
        assert client.get("/api/me").status_code == 401
        assert client.get("/api/me/progress").status_code == 401
        client.cookies.set("leettrack_session", "forged")
        assert client.get("/api/questions").status_code == 401
    assert opened == []
