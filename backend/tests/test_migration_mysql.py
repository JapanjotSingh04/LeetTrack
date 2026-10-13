"""Migration test against a REAL, DISPOSABLE MySQL database.

Skipped unless these variables are set (never point them at real data):
    LEETTRACK_TEST_DB_HOST, LEETTRACK_TEST_DB_USER, LEETTRACK_TEST_DB_PASSWORD,
    LEETTRACK_TEST_DB_NAME   (name must start with "leettrack_test_")
The test creates the ORIGINAL (pre-auth) schema, adds a legacy user with progress,
runs database/migrate_auth.py twice, and checks nothing was lost.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = ("LEETTRACK_TEST_DB_HOST", "LEETTRACK_TEST_DB_USER", "LEETTRACK_TEST_DB_PASSWORD", "LEETTRACK_TEST_DB_NAME")

pytestmark = pytest.mark.skipif(
    not all(os.getenv(k) for k in REQUIRED)
    or not os.getenv("LEETTRACK_TEST_DB_NAME", "").startswith("leettrack_test_"),
    reason="needs a disposable MySQL database named leettrack_test_* (see module docstring)",
)

LEGACY_SCHEMA = [
    "DROP TABLE IF EXISTS solved_questions", "DROP TABLE IF EXISTS question_bank", "DROP TABLE IF EXISTS users",
    "CREATE TABLE users (user_id INT PRIMARY KEY AUTO_INCREMENT, username VARCHAR(100) NOT NULL)",
    """CREATE TABLE question_bank (question_id INT NOT NULL, platform VARCHAR(50) NOT NULL, title VARCHAR(255) NOT NULL,
       difficulty ENUM('Easy','Medium','Hard') NOT NULL, topic VARCHAR(100), url VARCHAR(500),
       PRIMARY KEY (question_id, platform))""",
    """CREATE TABLE solved_questions (user_id INT NOT NULL, question_id INT NOT NULL, platform VARCHAR(50) NOT NULL,
       solved_date DATE NOT NULL, revision_counter INT NOT NULL DEFAULT 0, last_revision_date DATE, due_date DATE,
       PRIMARY KEY (user_id, question_id, platform),
       FOREIGN KEY (user_id) REFERENCES users(user_id),
       FOREIGN KEY (question_id, platform) REFERENCES question_bank(question_id, platform))""",
    "INSERT INTO users (username) VALUES ('demo_user')",
    "INSERT INTO question_bank VALUES (1,'leetcode','Two Sum','Easy','Array','u')",
    "INSERT INTO solved_questions VALUES (1,1,'leetcode','2026-01-01',1,'2026-01-08','2026-01-22')",
]


def _env():
    return {
        **os.environ,
        "DB_HOST": os.environ["LEETTRACK_TEST_DB_HOST"],
        "DB_PORT": os.environ.get("LEETTRACK_TEST_DB_PORT", "3306"),
        "DB_USER": os.environ["LEETTRACK_TEST_DB_USER"],
        "DB_PASSWORD": os.environ["LEETTRACK_TEST_DB_PASSWORD"],
        "DB_NAME": os.environ["LEETTRACK_TEST_DB_NAME"],
        "APP_ENV": "development",
    }


def test_migration_preserves_existing_rows_and_is_idempotent():
    import mysql.connector
    env = _env()
    conn = mysql.connector.connect(host=env["DB_HOST"], port=int(env["DB_PORT"]), user=env["DB_USER"],
                                   password=env["DB_PASSWORD"], database=env["DB_NAME"])
    cur = conn.cursor(dictionary=True)
    for stmt in LEGACY_SCHEMA:
        cur.execute(stmt)
    conn.commit()
    for _ in range(2):  # second run proves idempotency
        run = subprocess.run([sys.executable, str(ROOT / "database" / "migrate_auth.py")],
                             env=env, capture_output=True, text=True, timeout=120)
        assert run.returncode == 0, run.stderr + run.stdout
    cur.execute("SHOW COLUMNS FROM users")
    assert {"email", "password_hash"} <= {r["Field"] for r in cur.fetchall()}
    cur.execute("SELECT * FROM solved_questions")
    rows = cur.fetchall()
    assert len(rows) == 1 and rows[0]["revision_counter"] == 1
    cur.execute("SELECT username, email, password_hash FROM users")
    assert cur.fetchall() == [{"username": "demo_user", "email": None, "password_hash": None}]
    cur.execute("SHOW INDEX FROM users")
    assert {"uq_users_email", "uq_users_username"} <= {r["Key_name"] for r in cur.fetchall()}
    conn.close()
