-- Least-privilege account for the running API (NOT root / NOT the provider admin).
--
-- Run ONCE as the provider's admin user (Aiven: "avnadmin"), after schema_managed.sql.
-- Replace YOUR_DB_NAME and the password placeholder BEFORE running. Never commit a real password.
--   * The API can read the question bank, and read/write users and solved_questions.
--   * It cannot DROP/ALTER tables, delete rows, or touch other databases.
-- Migrations and the legacy-account script must still be run with the admin user.

CREATE USER IF NOT EXISTS 'leettrack_app'@'%' IDENTIFIED BY 'REPLACE_WITH_A_LONG_RANDOM_PASSWORD';

GRANT SELECT ON YOUR_DB_NAME.question_bank TO 'leettrack_app'@'%';
GRANT SELECT, INSERT, UPDATE ON YOUR_DB_NAME.users TO 'leettrack_app'@'%';
GRANT SELECT, INSERT, UPDATE ON YOUR_DB_NAME.solved_questions TO 'leettrack_app'@'%';

-- Check the result:
SHOW GRANTS FOR 'leettrack_app'@'%';
