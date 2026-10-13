"""LeetTrack API with authenticated, per-user data access."""
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import jwt
import mysql.connector
from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import auth
import engine
import services
from ratelimit import limiter
from database import get_db, check_connection
from models import LoginRequest, QuestionCompleteRequest, RegisterRequest, RevisionCompleteRequest

def _origins():
    return [item.strip().rstrip("/") for item in os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",") if item.strip()]

@asynccontextmanager
async def lifespan(_app):
    if os.getenv("APP_ENV", "development").lower() == "production":
        auth._secret()
        if not (os.getenv("DB_SSL_CA", "").strip() or os.getenv("DB_SSL_CA_PEM", "").strip()):
            raise RuntimeError("Production requires DB_SSL_CA or DB_SSL_CA_PEM for verified database TLS.")
        configured_origins = os.getenv("CORS_ORIGINS", "").strip()
        origins = _origins()
        if not configured_origins or not origins or "*" in origins or any(
            origin.startswith(("http://localhost", "http://127.0.0.1")) for origin in origins
        ):
            raise RuntimeError("Production CORS_ORIGINS must contain exact deployed frontend origins and cannot be wildcard or localhost.")
    yield


app = FastAPI(
    title="LeetTrack API",
    version="2.0.0",
    docs_url=None if os.getenv("APP_ENV", "").lower() == "production" else "/docs",
    redoc_url=None if os.getenv("APP_ENV", "").lower() == "production" else "/redoc",
    openapi_url=None if os.getenv("APP_ENV", "").lower() == "production" else "/openapi.json",
    lifespan=lifespan,
)

LOGIN_WINDOW = 900          # 15 minutes
REGISTER_WINDOW = 3600      # 1 hour


def _limit(name: str, default: int) -> int:
    """Rate limits can be raised through environment variables (read per request)."""
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _max_users() -> int:
    """MAX_USERS caps registered accounts. 0 / unset means no cap."""
    try:
        return max(0, int(os.getenv("MAX_USERS", "0")))
    except ValueError:
        return 0


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)


@app.middleware("http")
async def secure_api_responses(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response





def _origin_guard(request: Request):
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") not in _origins():
        raise HTTPException(status_code=403, detail="Request origin is not allowed.")

def _handle(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except services.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except services.ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except services.ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except mysql.connector.Error:
        raise HTTPException(status_code=503, detail="Database temporarily unavailable.")

@app.exception_handler(mysql.connector.Error)
async def mysql_error_handler(request: Request, exc):
    return JSONResponse(status_code=503, content={"detail": "Database temporarily unavailable."})


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError):
    # Exclude Pydantic's `input` field so passwords and other submitted values
    # are never echoed back in validation responses.
    errors = [
        {"loc": error.get("loc", ()), "msg": error.get("msg", "Invalid input"), "type": error.get("type", "value_error")}
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": errors})


def get_session_user_id(
    access_token: Optional[str] = Cookie(default=None, alias="leettrack_session"),
) -> int:
    """Verify the signed session cookie. Needs no database, so anonymous or
    forged requests are rejected without using a (scarce) DB connection."""
    if not access_token:
        raise HTTPException(status_code=401, detail="Please log in to continue.")
    try:
        return auth.read_access_token(access_token)
    except (jwt.InvalidTokenError, RuntimeError):
        raise HTTPException(status_code=401, detail="Your session has expired. Please log in again.")


def get_current_user(user_id: int = Depends(get_session_user_id), conn=Depends(get_db)):
    rows = engine.run_query(
        conn, "SELECT user_id, username, email FROM users WHERE user_id = %s",
        (user_id,), fetch=True,
    )
    if not rows or not rows[0].get("email"):
        raise HTTPException(status_code=401, detail="This account is not available. Please log in again.")
    return rows[0]

def require_csrf(
    request: Request,
    csrf_cookie: Optional[str] = Cookie(default=None, alias="leettrack_csrf"),
    csrf_header: Optional[str] = Header(default=None, alias="X-CSRF-Token"),
):
    _origin_guard(request)
    if not auth.verify_csrf(csrf_cookie, csrf_header):
        raise HTTPException(status_code=403, detail="Security token missing or invalid. Refresh the page and try again.")

def _set_session(response: Response, user_id: int):
    session = auth.create_access_token(user_id)
    csrf_token = auth.new_csrf_token()
    response.set_cookie("leettrack_session", session, max_age=auth.ACCESS_TOKEN_MINUTES * 60, **auth.cookie_options())
    response.set_cookie("leettrack_csrf", csrf_token, max_age=auth.ACCESS_TOKEN_MINUTES * 60, **auth.csrf_cookie_options())
    return csrf_token

def _public_user(row):
    return {"user_id": row["user_id"], "username": row["username"], "email": row["email"]}

@app.get("/api/health")
def health():
    if not check_connection():
        raise HTTPException(status_code=503, detail="Service temporarily unavailable.")
    return {"status": "ok"}

@app.post("/api/auth/register")
def register(payload: RegisterRequest, request: Request, response: Response, conn=Depends(get_db)):
    _origin_guard(request)
    ip_key = ("register-ip", _client_ip(request))
    limiter.check(ip_key, _limit("RATE_REGISTER_PER_IP", 5), REGISTER_WINDOW)
    limiter.check(("register-all",), _limit("RATE_REGISTER_TOTAL", 40), REGISTER_WINDOW)  # backstop if the IP header is spoofed
    limiter.hit(ip_key, REGISTER_WINDOW)
    limiter.hit(("register-all",), REGISTER_WINDOW)
    existing = engine.run_query(
        conn, "SELECT user_id FROM users WHERE LOWER(username) = LOWER(%s) OR LOWER(email) = LOWER(%s) LIMIT 1",
        (payload.username, payload.email), fetch=True,
    )
    if existing:
        raise HTTPException(status_code=409, detail="That username or email is already registered.")
    cap = _max_users()
    if cap:
        count = engine.run_query(
            conn, "SELECT COUNT(*) AS total FROM users WHERE email IS NOT NULL", fetch=True
        )[0]["total"]
        if int(count) >= cap:
            raise HTTPException(status_code=403, detail="Registrations are full for this demo.")
    try:
        password_hash = auth.hash_password(payload.password)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
                (payload.username, payload.email, password_hash),
            )
            conn.commit()
            user_id = cursor.lastrowid
        finally:
            cursor.close()
    except mysql.connector.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=409, detail="That username or email is already registered.")
    except mysql.connector.Error:
        conn.rollback()
        raise HTTPException(status_code=503, detail="Could not create your account right now.")
    csrf_token = _set_session(response, int(user_id))
    return {"user": {"user_id": int(user_id), "username": payload.username, "email": payload.email}, "csrf_token": csrf_token}

@app.post("/api/auth/login")
def login(payload: LoginRequest, request: Request, response: Response, conn=Depends(get_db)):
    _origin_guard(request)
    ip_key = ("login-ip", _client_ip(request))
    email_key = ("login-email", payload.email)
    limiter.check(ip_key, _limit("RATE_LOGIN_PER_IP", 30), LOGIN_WINDOW)
    limiter.check(email_key, _limit("RATE_LOGIN_FAILS_PER_ACCOUNT", 8), LOGIN_WINDOW)  # per-account guard: cannot be dodged by changing IP
    limiter.hit(ip_key, LOGIN_WINDOW)
    rows = engine.run_query(
        conn, "SELECT user_id, username, email, password_hash FROM users WHERE LOWER(email) = %s LIMIT 1",
        (payload.email,), fetch=True,
    )
    stored_hash = rows[0].get("password_hash") if rows else None
    # Always run one Argon2 verification so response time does not reveal
    # whether the email is registered. Messages are identical as well.
    password_ok = auth.verify_password(payload.password, stored_hash or auth.dummy_hash())
    if not rows or not stored_hash or not password_ok:
        limiter.hit(email_key, LOGIN_WINDOW)
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    limiter.reset(email_key)
    row = rows[0]
    csrf_token = _set_session(response, int(row["user_id"]))
    return {"user": _public_user(row), "csrf_token": csrf_token}

@app.get("/api/auth/me")
def auth_me(user=Depends(get_current_user), csrf_cookie: Optional[str] = Cookie(default=None, alias="leettrack_csrf")):
    if not csrf_cookie:
        raise HTTPException(status_code=401, detail="Session security token is missing. Please log in again.")
    return {"user": _public_user(user), "csrf_token": csrf_cookie}

@app.post("/api/auth/logout")
def logout(request: Request, response: Response, _csrf=Depends(require_csrf), _user=Depends(get_current_user)):
    response.delete_cookie("leettrack_session", path="/", secure=auth.cookie_options()["secure"], httponly=True, samesite=auth.cookie_options()["samesite"])
    response.delete_cookie("leettrack_csrf", path="/", secure=auth.cookie_options()["secure"], httponly=False, samesite=auth.cookie_options()["samesite"])
    return {"ok": True}

@app.get("/api/me")
def get_user(user=Depends(get_current_user)):
    return _public_user(user)

@app.get("/api/me/daily-plan")
def get_daily_plan(
    simulated_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    plan_date: Optional[str] = Query(None, description="Deprecated alias"),
    user=Depends(get_current_user), conn=Depends(get_db),
):
    raw_date = simulated_date or plan_date
    parsed_date = None
    if raw_date:
        try:
            parsed_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=422, detail="simulated_date must be YYYY-MM-DD.")
    return _handle(services.get_daily_plan, conn, int(user["user_id"]), parsed_date)

@app.post("/api/questions/complete")
def complete_question(payload: QuestionCompleteRequest, _csrf=Depends(require_csrf),
                      user=Depends(get_current_user), conn=Depends(get_db)):
    return _handle(services.complete_question, conn, int(user["user_id"]),
                   payload.question_id, payload.platform, payload.difficulty)

@app.post("/api/revisions/complete")
def complete_revision(payload: RevisionCompleteRequest, _csrf=Depends(require_csrf),
                       user=Depends(get_current_user), conn=Depends(get_db)):
    return _handle(services.complete_revision, conn, int(user["user_id"]),
                   payload.question_id, payload.platform, payload.difficulty, payload.revision_counter)

@app.get("/api/me/solved")
def get_solved_questions(user=Depends(get_current_user), conn=Depends(get_db)):
    return _handle(services.get_solved_questions, conn, int(user["user_id"]))

@app.get("/api/me/revisions")
def get_upcoming_revisions(user=Depends(get_current_user), conn=Depends(get_db)):
    return _handle(services.get_upcoming_revisions, conn, int(user["user_id"]))

@app.get("/api/questions")
def get_questions(
    difficulty: Optional[str] = None, topic: Optional[str] = None, platform: Optional[str] = None,
    user=Depends(get_current_user), conn=Depends(get_db),
):
    return _handle(services.get_questions, conn, difficulty, topic, platform, int(user["user_id"]))

@app.get("/api/me/progress")
def get_progress(user=Depends(get_current_user), conn=Depends(get_db)):
    return _handle(services.get_progress, conn, int(user["user_id"]))
