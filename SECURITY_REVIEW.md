# LeetTrack security review

Status: **suitable for a small, free-tier beta; not claimed production-ready.** Items marked *not run* could not be executed in the build environment (no MySQL server, no npm/PyPI registry access).

## What is implemented

| Area | Implementation |
|---|---|
| Passwords | Argon2id (`argon2-cffi`), never stored in plaintext; 12–128 character passwords. |
| Sessions | HS256 signed JWT in an **HttpOnly** cookie, 2 h lifetime, `Secure` in production, `SameSite=Lax`. Secret comes from `JWT_SECRET` (≥32 chars, server-only). |
| CSRF | Double-submit token (`leettrack_csrf` cookie + `X-CSRF-Token` header) on every state-changing authenticated request, plus an `Origin` allowlist check on login/register/logout/actions. |
| Authorization | The user id is **only** taken from the verified cookie. No route or body accepts a user id; the old `/api/users/{id}` routes were removed (404). Every user-data SQL query filters `user_id = <session user>`. |
| Account enumeration | Same message and an Argon2 verification on every login attempt, so unknown email and wrong password look and time alike. Duplicate sign-up says "username or email already registered". |
| Rate limiting | Login: 8 failures / 15 min **per account** (not bypassable by changing IP) and 30 tries / 15 min per IP. Register: 5 / h per IP and 40 / h overall. In memory (per process). |
| Legacy data | `demo_user` has no email/password so it cannot log in; no default credentials exist. A forged token for it is rejected. |
| Input validation | Pydantic models; difficulty is an enum pattern; dates parsed strictly; validation errors never echo submitted values (passwords). |
| SQL injection | All queries parameterised (`%s`); no user text is concatenated into SQL. |
| Database | Per-request connection closed in `finally`; connect timeout; production **requires** a CA and verifies certificate chain and host name (`DB_SSL_VERIFY_IDENTITY` can relax host-name matching only). Raw driver errors are never returned (generic 503). Unauthenticated/forged requests are rejected **before** a DB connection is opened. |
| Least privilege | `database/create_app_user.sql`: runtime user can only SELECT question_bank and SELECT/INSERT/UPDATE users and solved_questions. |
| Concurrency | Unique indexes on username/email; duplicate sign-up race → 409. Duplicate solve race → 409 (primary key). Double-clicked revision is an atomic compare-and-set (`AND revision_counter = old`), so it cannot double-count. |
| CORS / config | Exact-origin allowlist from `CORS_ORIGINS`; production refuses to start with `*`, localhost, empty origins, short secret or missing DB TLS settings. |
| Exposure | `/docs`, `/redoc` **and** `/openapi.json` are disabled in production; health returns only `{"status":"ok"}`; API responses are `no-store`; security headers set by API and Vercel. |
| Secrets in Git | `.env*`, `.venv`, `node_modules`, `dist`, logs, dumps, `*.pem/*.key` ignored; `.env.example` placeholders only; notebook scanned (no secrets/outputs with credentials). |
| Dangerous seed | `database/seed.sql` deletes every user's rows for ids 101–300 — now marked **local demo only**; a non-destructive `seed_question_bank.sql` is used for the hosted DB. |

## The "2130 / 100" dashboard figure

Traced, not a calculation bug. `engine.create_daily_plan` puts **all due revisions first** (by design); with a large overdue backlog `revision_capacity` (e.g. 53 items) legitimately exceeds the 100-unit daily capacity, leaving 0 for new questions. The earlier UI just printed the large number without context. The bar is now bounded and shows an "over capacity by N units" warning. The scheduling and capacity formulas are unchanged (covered by tests, including a backlog case).

## Tests actually run (this environment)

`cd backend && python -m pytest tests -q` → **37 passed, 1 skipped**. `python -m compileall` on backend and database scripts → OK. A mutation check (removing the `user_id` filter, removing the compare-and-set guard) made the isolation tests fail, so they do detect those defects.

Covered: registration (success, duplicate, invalid, password never echoed), login (success, wrong password, unknown email identical, per-account and per-IP limiting, counter reset), expired/forged/missing session, anonymous access opens no DB connection, user A vs user B isolation for profile, solved list, revisions, progress, question-bank solved flags, completing/revising another user's question (client-sent `user_id` ignored), old routes 404, CSRF, foreign Origin 403, legacy account cannot log in, revision intervals/limits for Easy/Medium/Hard, daily plan capacity incl. the overdue-backlog case, simulated date is read-only, health endpoint, and production mode (docs hidden, CORS allow/deny, startup refusal on bad CORS/secret/TLS, secure cookies).

**Caveats:** the SQL tests run on SQLite standing in for MySQL, with fastapi 0.115.0 / starlette 0.38.6 / argon2-cffi 23.1.0 as pinned but newer PyJWT/pydantic than `requirements.txt` (no registry access). `mysql-connector-python` was not installed, so a stub provided its exception classes.

## Not run / still to do by you

* **Real MySQL**: `tests/test_migration_mysql.py` (migration on a pre-auth schema, idempotency, data preserved) is written but **not run**; run it against a disposable `leettrack_test_*` database, and do one live smoke test (register, solve, revise) on the real DB.
* **Frontend production build** (`npm ci && npm run build`): not run here (no npm registry). All source bundled/parsed successfully with esbuild; run the build on your PC before pushing.
* **Dependency audit** (`pip-audit`, `npm audit`): not run. Run them; do not use `npm audit fix --force`.
* Live deployment, Aiven certificate host-name behaviour, and Vercel→Render cold-start behaviour: unverified until you deploy.

## Remaining risks

* JWTs cannot be revoked server-side before expiry (2 h); logout only clears the cookie.
* Rate limits reset when the free instance restarts; an attacker can lock a *specific* account for 15 minutes by guessing wrongly 8 times.
* No email verification, password reset, MFA or account deletion; sign-up accepts any email.
* The IP used for per-IP limits comes from forwarded headers and can be spoofed (the per-account and global limits are the real protection).
* Free tiers: cold starts, possible suspension/power-off, single DB node, no SLA, no tested automatic restore.
* Vercel Hobby is non-commercial only.
