"""Interactively attach existing progress to the beta owner's login.

This script updates only one existing users row whose email/password_hash are NULL.
It never creates an account or changes solved_questions. Run only after a backup.
"""
import getpass
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))
from dotenv import load_dotenv
load_dotenv(BACKEND / ".env")
import auth
import engine

def main():
    legacy_username = input("Existing username to claim (for example demo_user): ").strip()
    new_username = input("Your desired username (3-40 letters/numbers/._-): ").strip()
    email = input("Your email: ").strip().lower()
    password = getpass.getpass("Choose a password (at least 12 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,40}", new_username):
        raise SystemExit("Invalid username format.")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise SystemExit("Invalid email format.")
    if len(password) < 12 or len(password) > 128:
        raise SystemExit("Password must be 12-128 characters.")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")

    conn = engine.get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute("SELECT user_id, username, email, password_hash FROM users WHERE username = %s", (legacy_username,))
            row = cur.fetchone()
            if not row:
                raise SystemExit("No existing user with that username was found.")
            if row["email"] or row["password_hash"]:
                raise SystemExit("That account already has login credentials; refusing to overwrite it.")
            cur.execute("SELECT user_id FROM users WHERE LOWER(username) = LOWER(%s) OR LOWER(email) = LOWER(%s)", (new_username, email))
            conflicts = [item for item in cur.fetchall() if item["user_id"] != row["user_id"]]
            if conflicts:
                raise SystemExit("Your chosen username or email is already in use.")
            print(f"Target account: user_id={row['user_id']}, current username={row['username']!r}")
            print("This will preserve all solved-question and revision rows for this account.")
            if input("Type CLAIM to confirm this exact change: ").strip() != "CLAIM":
                conn.rollback()
                raise SystemExit("Cancelled. No account changes were made.")
            password_hash = auth.hash_password(password)
            cur.execute(
                "UPDATE users SET username = %s, email = %s, password_hash = %s "
                "WHERE user_id = %s AND email IS NULL AND password_hash IS NULL",
                (new_username, email, password_hash, row["user_id"]),
            )
            if cur.rowcount != 1:
                conn.rollback()
                raise SystemExit("Account changed concurrently; no update was committed.")
            conn.commit()
            print("Owner account linked successfully. Existing progress was preserved.")
        finally:
            cur.close()
    finally:
        conn.close()

if __name__ == "__main__":
    main()
