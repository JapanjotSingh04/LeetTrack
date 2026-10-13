import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main
import auth
import engine

class FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self.lastrowid = None
    def execute(self, query, params=()):
        if query.strip().upper().startswith("INSERT INTO USERS"):
            self.conn.next_id += 1
            self.lastrowid = self.conn.next_id
            self.conn.users.append({
                "user_id": self.lastrowid, "username": params[0], "email": params[1],
                "password_hash": params[2],
            })
    def close(self): pass

class FakeConnection:
    def __init__(self):
        self.users = []
        self.next_id = 0
    def cursor(self, **kwargs): return FakeCursor(self)
    def commit(self): pass
    def rollback(self): pass
    def close(self): pass

@pytest.fixture
def setup_api(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret-with-more-than-32-characters-123")
    monkeypatch.setenv("APP_ENV", "development")
    main.limiter.clear()
    conn = FakeConnection()
    def fake_db():
        yield conn
    main.app.dependency_overrides[main.get_db] = fake_db

    def run_query(_conn, query, params=None, fetch=False, many=False):
        query_lower = query.lower()
        params = params or ()
        if "from users where lower(username)" in query_lower:
            username, email = params
            return [{"user_id": u["user_id"]} for u in conn.users
                    if u["username"].lower() == username.lower() or u["email"].lower() == email.lower()][:1]
        if "from users where lower(email)" in query_lower:
            email = params[0]
            return [{**u} for u in conn.users if u["email"].lower() == email.lower()][:1]
        if "from users where user_id" in query_lower:
            uid = params[0]
            return [{k: u[k] for k in ("user_id", "username", "email")} for u in conn.users if u["user_id"] == uid]
        return []
    monkeypatch.setattr(engine, "run_query", run_query)
    with TestClient(main.app) as client:
        yield client, conn
    main.app.dependency_overrides.clear()

def test_registration_hashes_password_and_sets_secure_session(setup_api):
    client, conn = setup_api
    response = client.post("/api/auth/register", json={
        "username": "tester", "email": "tester@example.com", "password": "a-long-test-password"
    }, headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 200
    assert response.json()["user"]["username"] == "tester"
    assert conn.users[0]["password_hash"] != "a-long-test-password"
    assert auth.verify_password("a-long-test-password", conn.users[0]["password_hash"])
    assert "leettrack_session" in response.cookies
    assert "httponly" in response.headers.get("set-cookie", "").lower()

def test_duplicate_registration_rejected(setup_api):
    client, _ = setup_api
    payload = {"username": "tester", "email": "tester@example.com", "password": "a-long-test-password"}
    assert client.post("/api/auth/register", json=payload, headers={"Origin": "http://localhost:5173"}).status_code == 200
    duplicate = client.post("/api/auth/register", json=payload, headers={"Origin": "http://localhost:5173"})
    assert duplicate.status_code == 409

def test_invalid_registration_password_rejected(setup_api):
    client, _ = setup_api
    response = client.post("/api/auth/register", json={
        "username": "tester", "email": "tester@example.com", "password": "short"
    }, headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 422
    assert '"input"' not in response.text

def test_login_success_and_wrong_password(setup_api):
    client, _ = setup_api
    client.post("/api/auth/register", json={
        "username": "tester", "email": "tester@example.com", "password": "a-long-test-password"
    }, headers={"Origin": "http://localhost:5173"})
    client.post("/api/auth/logout", headers={"Origin": "http://localhost:5173", "X-CSRF-Token": client.cookies.get("leettrack_csrf", "")})
    wrong = client.post("/api/auth/login", json={"email": "tester@example.com", "password": "wrong"}, headers={"Origin": "http://localhost:5173"})
    assert wrong.status_code == 401
    good = client.post("/api/auth/login", json={"email": "tester@example.com", "password": "a-long-test-password"}, headers={"Origin": "http://localhost:5173"})
    assert good.status_code == 200

def test_protected_endpoint_rejects_anonymous_requests(setup_api):
    client, _ = setup_api
    response = client.get("/api/me")
    assert response.status_code == 401

def test_user_id_cannot_be_supplied_through_old_route(setup_api):
    client, _ = setup_api
    response = client.get("/api/users/1/progress")
    assert response.status_code == 404

def test_csrf_is_required_for_logout(setup_api):
    client, _ = setup_api
    client.post("/api/auth/register", json={
        "username": "tester", "email": "tester@example.com", "password": "a-long-test-password"
    }, headers={"Origin": "http://localhost:5173"})
    response = client.post("/api/auth/logout", headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 403


def test_authenticated_user_id_is_derived_from_session_identity(setup_api, monkeypatch):
    client, _ = setup_api
    seen = []
    monkeypatch.setattr(main.services, "get_progress", lambda conn, user_id: seen.append(user_id) or {"user_id": user_id})
    main.app.dependency_overrides[main.get_current_user] = lambda: {"user_id": 11, "username": "alice", "email": "alice@example.com"}
    response_a = client.get("/api/me/progress")
    assert response_a.status_code == 200
    assert response_a.json()["user_id"] == 11
    main.app.dependency_overrides[main.get_current_user] = lambda: {"user_id": 22, "username": "bob", "email": "bob@example.com"}
    response_b = client.get("/api/me/progress")
    assert response_b.status_code == 200
    assert response_b.json()["user_id"] == 22
    assert seen == [11, 22]
    main.app.dependency_overrides.pop(main.get_current_user, None)


def test_client_supplied_user_id_is_ignored_for_completion(setup_api, monkeypatch):
    client, _ = setup_api
    main.app.dependency_overrides[main.get_current_user] = lambda: {"user_id": 11, "username": "alice", "email": "alice@example.com"}
    monkeypatch.setattr(main.services, "complete_question",
                        lambda conn, user_id, question_id, platform, difficulty: {"user_id": user_id})
    client.cookies.set("leettrack_csrf", "test-csrf")
    response = client.post(
        "/api/questions/complete",
        json={"user_id": 22, "question_id": 101, "platform": "leetcode", "difficulty": "Easy"},
        headers={"Origin": "http://localhost:5173", "X-CSRF-Token": "test-csrf"},
    )
    assert response.status_code == 200
    assert response.json()["user_id"] == 11
    main.app.dependency_overrides.pop(main.get_current_user, None)


def test_invalid_session_cookie_is_rejected(setup_api):
    client, _ = setup_api
    client.cookies.set("leettrack_session", "not-a-valid-token")
    response = client.get("/api/me")
    assert response.status_code == 401

def test_health_endpoint_does_not_expose_database_details(setup_api, monkeypatch):
    client, _ = setup_api
    monkeypatch.setattr(main, "check_connection", lambda: False)
    response = client.get("/api/health")
    assert response.status_code == 503
    assert "password" not in response.text.lower()
    assert "host" not in response.text.lower()
    assert response.headers.get("cache-control") == "no-store"

def test_revision_intervals_and_capacity_math(setup_api):
    assert engine.get_revision_interval("Easy", 0) == 7
    assert engine.get_revision_interval("Medium", 2) == 20
    assert engine.get_revision_interval("Hard", 4) == 48
    mix, used = engine.find_best_new_question_mix(100)
    assert used <= 100
    assert used == 100
    assert engine.calculate_capacity_usage([{"difficulty": "Hard"}, {"difficulty": "Easy"}]) == 85

def test_cors_preflight_only_allows_configured_origin(setup_api):
    client, _ = setup_api
    allowed = client.options("/api/auth/login", headers={
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    assert allowed.status_code == 200
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_expired_session_is_rejected(setup_api, monkeypatch):
    import jwt
    from datetime import datetime, timedelta, timezone
    client, _ = setup_api
    token = jwt.encode({
        "sub": "1",
        "iat": datetime.now(timezone.utc) - timedelta(hours=3),
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
    }, os.environ["JWT_SECRET"], algorithm="HS256")
    client.cookies.set("leettrack_session", token)
    response = client.get("/api/me")
    assert response.status_code == 401


def test_revision_completion_uses_authenticated_user_id(setup_api, monkeypatch):
    client, _ = setup_api
    main.app.dependency_overrides[main.get_current_user] = lambda: {"user_id": 11, "username": "alice", "email": "alice@example.com"}
    monkeypatch.setattr(main.services, "complete_revision",
                        lambda conn, user_id, question_id, platform, difficulty, revision_counter: {"user_id": user_id})
    client.cookies.set("leettrack_csrf", "test-csrf")
    response = client.post(
        "/api/revisions/complete",
        json={"user_id": 22, "question_id": 101, "platform": "leetcode", "difficulty": "Easy", "revision_counter": 0},
        headers={"Origin": "http://localhost:5173", "X-CSRF-Token": "test-csrf"},
    )
    assert response.status_code == 200
    assert response.json()["user_id"] == 11
    main.app.dependency_overrides.pop(main.get_current_user, None)


def test_question_bank_solved_status_query_is_user_scoped(setup_api, monkeypatch):
    _, conn = setup_api
    captured = []
    def fake_query(_conn, query, params=None, fetch=False, many=False):
        captured.append((query, params))
        return [{"question_id": 101, "platform": "leetcode", "title": "Sample", "difficulty": "Easy", "solved": int(params[0] == 11)}]
    monkeypatch.setattr(engine, "run_query", fake_query)
    rows_a = main.services.get_questions(conn, user_id=11)
    rows_b = main.services.get_questions(conn, user_id=22)
    assert rows_a[0]["solved"] == 1 and rows_b[0]["solved"] == 0
    assert "sq.user_id = %s" in captured[0][0]
    assert captured[0][1][0] == 11
    assert captured[1][1][0] == 22


def test_daily_plan_service_preserves_capacity_contract(setup_api, monkeypatch):
    _, conn = setup_api
    from datetime import date
    monkeypatch.setattr(main.services, "_user_exists", lambda _conn, _uid: True)
    monkeypatch.setattr(engine, "create_daily_plan", lambda _conn, _uid, _date: {
        "revisions": [{"difficulty": "Hard"}],
        "new_questions": [{"difficulty": "Medium"}],
        "new_mix": {"Easy": 0, "Medium": 1, "Hard": 0},
        "revision_capacity": 55,
        "new_capacity": 40,
        "remaining_capacity": 45,
    })
    result = main.services.get_daily_plan(conn, 11, date(2026, 1, 1))
    assert result["used_capacity"] == 95
    assert result["daily_capacity"] == 100
    assert result["date"] == "2026-01-01"
    assert result["is_simulated"] is True
