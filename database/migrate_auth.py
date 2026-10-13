"""Idempotent, non-destructive migration adding account credentials to users.

Run from the project root after backing up the target database:
    python database/migrate_auth.py
This script never drops tables or changes solved-question data.
"""
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))
from dotenv import load_dotenv
load_dotenv(BACKEND / ".env")
import engine

def main():
    required = ("DB_HOST", "DB_USER", "DB_NAME")
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise SystemExit("Missing database settings: " + ", ".join(missing))
    conn = engine.get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SHOW COLUMNS FROM users")
        columns = {row["Field"] for row in cur.fetchall()}
        if "email" not in columns:
            cur.execute("ALTER TABLE users ADD COLUMN email VARCHAR(254) NULL")
            print("Added nullable users.email")
        if "password_hash" not in columns:
            cur.execute("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255) NULL")
            print("Added nullable users.password_hash")

        cur.execute("SHOW INDEX FROM users")
        indexes = {row["Key_name"] for row in cur.fetchall()}
        if "uq_users_email" not in indexes:
            cur.execute("SELECT email, COUNT(*) AS n FROM users WHERE email IS NOT NULL GROUP BY email HAVING n > 1 LIMIT 1")
            if cur.fetchone():
                raise SystemExit("Duplicate existing emails detected; resolve them before adding the unique email index.")
            cur.execute("ALTER TABLE users ADD UNIQUE KEY uq_users_email (email)")
            print("Added unique email index")
        if "uq_users_username" not in indexes:
            cur.execute("SELECT username, COUNT(*) AS n FROM users GROUP BY username HAVING n > 1 LIMIT 1")
            if cur.fetchone():
                raise SystemExit("Duplicate existing usernames detected; resolve them before adding the unique username index.")
            cur.execute("ALTER TABLE users ADD UNIQUE KEY uq_users_username (username)")
            print("Added unique username index")
        conn.commit()
        print("Migration completed. Existing users and solved-question history were preserved.")
        print("Legacy users without email/password_hash cannot log in until an owner explicitly links credentials to the intended account.")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
