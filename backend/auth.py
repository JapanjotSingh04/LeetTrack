"""Authentication helpers for LeetTrack."""
import hmac
import os
import secrets
import threading
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

def _int_env(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except ValueError:
        return default


# Argon2id tuned for a small free host (512 MB RAM, 0.1 CPU). These are the
# OWASP minimum-recommended settings (19 MiB, 2 passes, 1 lane) instead of the
# library default of about 64 MiB per hash, so a burst of simultaneous logins
# cannot exhaust memory. Hashes made with other settings still verify, because
# the parameters are stored inside each hash.
_password_hasher = PasswordHasher(
    time_cost=_int_env("ARGON2_TIME_COST", 2),
    memory_cost=_int_env("ARGON2_MEMORY_KIB", 19456, minimum=8192),
    parallelism=_int_env("ARGON2_PARALLELISM", 1),
)
# Only a few password hashes may run at once; the rest wait their turn.
_hash_slots = threading.BoundedSemaphore(_int_env("ARGON2_MAX_CONCURRENT", 3))
ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "120"))


def _secret() -> str:
    secret = os.getenv("JWT_SECRET")
    if not secret or len(secret) < 32:
        raise RuntimeError("JWT_SECRET must be configured with at least 32 characters.")
    return secret


def hash_password(password: str) -> str:
    with _hash_slots:
        return _password_hasher.hash(password)


_DUMMY_HASH = None


def dummy_hash() -> str:
    """A valid hash of a throwaway value, used to equalise login timing."""
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        with _hash_slots:
            _DUMMY_HASH = _password_hasher.hash(secrets.token_urlsafe(16))
    return _DUMMY_HASH


def verify_password(password: str, password_hash: str) -> bool:
    try:
        with _hash_slots:
            return _password_hasher.verify(password_hash, password)
    except (VerificationError, VerifyMismatchError, ValueError):
        return False


def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=ACCESS_TOKEN_MINUTES)},
        _secret(),
        algorithm=ALGORITHM,
    )


def read_access_token(token: str) -> int:
    payload = jwt.decode(token, _secret(), algorithms=[ALGORITHM], options={"require": ["sub", "exp", "iat"]})
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.isdigit():
        raise jwt.InvalidTokenError("Invalid subject")
    return int(subject)


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def verify_csrf(cookie_token: str | None, header_token: str | None) -> bool:
    if not cookie_token or not header_token:
        return False
    return hmac.compare_digest(cookie_token, header_token)


def cookie_options() -> dict:
    production = os.getenv("APP_ENV", "development").lower() == "production"
    return {
        "httponly": True,
        "secure": production,
        "samesite": "lax",
        "path": "/",
    }


def csrf_cookie_options() -> dict:
    options = cookie_options()
    options["httponly"] = False
    return options
