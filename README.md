# LeetTrack

LeetTrack is a React/Vite + FastAPI + MySQL app for tracking solved DSA questions, revision schedules, daily study plans, and progress.

## Features

- Per-account question and revision history
- Registration and login using Argon2 password hashes
- HttpOnly session cookie, short-lived signed session, CSRF token checks on state-changing requests
- Server-side user identity: the browser cannot select which account a request acts as
- Existing revision engine and simulated-date dashboard preserved
- Configurable CORS, database TLS verification, and health endpoint

## Technology

- Frontend: React 18, Vite, React Router
- Backend: Python, FastAPI, MySQL Connector/Python
- Database: MySQL 8-compatible managed MySQL
- Password hashing: Argon2id via `argon2-cffi`
- Session signing: HS256 JWT via PyJWT; signing secret is server-only

## Local setup (Windows PowerShell)

1. Make a backup before changing an existing database.
2. Create `backend/.env` from the safe template:

   ```powershell
   Copy-Item backend/.env.example backend/.env
   ```

3. Edit `backend/.env` locally. Do not commit it. For local MySQL, set `DB_HOST=localhost`, `DB_PORT=3306`, `DB_USER`/`DB_PASSWORD` to your existing local MySQL login (a least-privilege account is required for the hosted database, see `database/create_app_user.sql`), and `DB_NAME=leetcode_tracker`. Set `JWT_SECRET` to a random secret of at least 32 characters. Example generation:

   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

4. Install backend requirements and run the non-destructive auth migration only after taking a backup:

   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements-dev.txt
   cd ..
   python database/migrate_auth.py
   ```

   This migration only adds nullable email/password-hash fields and unique indexes. It does not delete progress. Existing accounts without credentials cannot log in until linked deliberately.

5. Start the backend in one terminal:

   ```powershell
   cd backend
   .\.venv\Scripts\Activate.ps1
   python -m uvicorn main:app --reload
   ```

6. Start the frontend in another terminal:

   ```powershell
   cd frontend
   npm ci
   npm run dev
   ```

   Open `http://localhost:5173`, register a new account, or link an existing legacy account with `python database/link_legacy_account.py` after reviewing the script and backing up first.

## Environment variables

See [`backend/.env.example`](backend/.env.example). Production secrets belong in the hosting provider's backend environment settings, never in Vite variables.

- `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`: database connection details
- `DB_SSL_CA`: path to the provider's CA certificate file, or `DB_SSL_CA_PEM`: its PEM contents for hosts that provide environment variables rather than secret files
- `JWT_SECRET`: random signing secret, minimum 32 characters
- `APP_ENV`: `development` locally; `production` on the hosted API
- `CORS_ORIGINS`: comma-separated exact frontend origins
- `ACCESS_TOKEN_MINUTES`: session lifetime (default 120)
- `DB_CONNECT_TIMEOUT`: database connection timeout (default 8 seconds)
- `DB_SSL_VERIFY_IDENTITY`: host-name check for the database certificate (default `true`; the certificate chain is always verified)

In production the browser calls the API through the frontend's own address (Vercel rewrite in `frontend/vercel.json`), so **no `VITE_` variables are needed**; `VITE_API_URL` only affects local development.

## Database files

- `database/schema.sql`: fresh local database schema (creates `leetcode_tracker`)
- `database/schema_managed.sql`: schema for a provider-created database
- `database/seed_question_bank.sql`: the 200-question bank only. Never deletes anything; use this for the hosted beta
- `database/seed.sql`: **local demo only** (question bank + sample history for `demo_user`). It deletes solved-question rows for ids 101-300 for every user, so never run it on a live database
- `database/create_app_user.sql`: least-privilege MySQL account for the running API
- `database/migrate_auth.py`: adds authentication columns to an existing database without dropping tables
- `database/link_legacy_account.py`: interactively attach credentials to one existing legacy account while preserving its progress

## API overview

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/logout`
- `GET /api/health`
- `GET /api/me`
- `GET /api/me/daily-plan?simulated_date=YYYY-MM-DD`
- `GET /api/me/solved`
- `GET /api/me/revisions`
- `GET /api/me/progress`
- `GET /api/questions` (authenticated; solved status is for the signed-in user)
- `POST /api/questions/complete`
- `POST /api/revisions/complete`

All user-specific routes derive the user ID from the verified session. The old `/api/users/{user_id}` routes have been removed.

## Testing

From the project root:

```powershell
cd backend
python -m pytest tests -q
python -m compileall -q .
cd ..\frontend
npm ci
npm run build
```

The suite (37 tests plus 1 optional) runs the real service SQL against an in-memory SQLite stand-in for MySQL, and tests production settings in separate processes. `tests/test_migration_mysql.py` runs the migration against a *disposable* MySQL database and is skipped unless `LEETTRACK_TEST_DB_*` variables are set (see the file header). Always do one smoke test on the real MySQL before going public.

## Deployment

Follow [`DEPLOYMENT.md`](DEPLOYMENT.md) for provider selection, backup/import instructions, exact hosting configuration, security checks, and shutdown steps. See [`SECURITY_REVIEW.md`](SECURITY_REVIEW.md) for test evidence and remaining risks.
