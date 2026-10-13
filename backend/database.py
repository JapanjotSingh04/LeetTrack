"""
Loads environment variables and provides a FastAPI dependency that yields a
MySQL connection per-request (opened via the engine's get_connection(), and
always closed afterwards).
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load backend/.env (if present) before anything reads os.getenv(...).
load_dotenv(Path(__file__).resolve().parent / '.env')

import engine  # noqa: E402  (import after load_dotenv on purpose)


def get_db():
    """
    FastAPI dependency: yields a live MySQL connection for the duration of a
    single request, then always closes it — even if the request raised.
    """
    conn = engine.get_connection()
    try:
        yield conn
    finally:
        conn.close()


def check_connection() -> bool:
    """Used by the /api/health endpoint to report whether MySQL is reachable."""
    try:
        conn = engine.get_connection()
        conn.close()
        return True
    except Exception:
        return False
