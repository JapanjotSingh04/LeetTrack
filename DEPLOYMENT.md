# LeetTrack beta deployment guide (₹0/month target)

Target: about **100 registered accounts**, a few people online at once. That is *not* 100 simultaneous users, and free tiers give **no uptime guarantee**. Nothing here is activated for you: you create each account yourself, and you must **never add a payment method or click an upgrade button**.

Provider facts below were checked against the providers' own documentation in October 2026. Free plans change, so re-read the linked pages before signing up.

## 0. How the pieces fit (read this once)

```
Browser ──► Vercel (React site) ──/api/* forwarded──► Render (FastAPI) ──TLS──► Aiven MySQL
```

* The browser only ever talks to **your Vercel address**. Vercel forwards `/api/...` to Render (this is the `rewrites` block in `frontend/vercel.json`).
* Because the browser sees one address, the login cookie is a normal first-party cookie and works in every browser (cross-site cookies are increasingly blocked).
* **So you do NOT set `VITE_API_URL` in production.** The frontend ignores it in production builds. The only place the Render address goes is `frontend/vercel.json`.

| Component | Service | Free-plan facts (verified) |
|---|---|---|
| Source | GitHub private repo | Free |
| Frontend | Vercel **Hobby** | Free, but **personal / non-commercial use only**. If you exceed limits you wait for the window to reset (no auto-charge on Hobby). |
| API | Render **Free web service** | Sleeps after 15 min without traffic; waking takes ~1 minute. 750 free instance-hours/month per workspace (a single always-on service uses ≤744). Without a payment method, hitting a limit **suspends** services instead of billing. Ephemeral disk, one instance. |
| Database | Aiven for MySQL **Free** | 1 CPU, 1 GB RAM, **1 GB disk**, a **small connection limit**, single node, no SLA, no credit card, no time limit. Aiven can power it off after inactivity (with an email first; you can power it back on), may change region/config, and allows **one free MySQL service per organization**. |

Links: [Vercel Hobby](https://vercel.com/docs/plans/hobby) · [Render free](https://render.com/docs/free) · [Aiven MySQL free tier](https://aiven.io/docs/products/mysql/concepts/mysql-free-tier)

Render's free *Postgres* expires after 30 days and Render has no free MySQL, which is why Aiven is used.

**Feasibility:** 100 registered users who open the app daily for a few minutes is realistic: each request is short, the question bank is 200 rows, and the API opens a database connection per request and closes it (well within the free limit). Not realistic: dozens of people hitting it *at the same moment*, instant responses after idle periods, or any uptime promise.

## 1. Accounts you need

1. GitHub (private repo).
2. Aiven (choose the **Free** MySQL plan; no card).
3. Render (sign in with GitHub; **do not add a card**).
4. Vercel (sign in with GitHub; Hobby plan; personal use).

## 2. Back up before you touch your local database

`>` in Windows PowerShell 5 writes UTF-16 and corrupts SQL dumps, so always use `--result-file`. The tool asks for your MySQL password; never type it into the command.

```powershell
cd C:\Users\DELL\OneDrive\Desktop\LeetTrack\LeetTrack
mkdir ..\leettrack_backups -ErrorAction SilentlyContinue
mysqldump --single-transaction --routines --triggers --no-tablespaces -u root -p --result-file="..\leettrack_backups\leetcode_tracker_before_auth.sql" leetcode_tracker
Get-Item ..\leettrack_backups\leetcode_tracker_before_auth.sql | Select-Object Name, Length
```

The backup sits **outside** the project folder so it can never be committed. If `Length` is `0`, stop and fix that first.

The ZIP you originally uploaded contained a `backend/.env` and a `.env.example` with a password-like value. If that was ever a real password, change that MySQL password.

## 3. Run it locally first (existing local database)

1. Create your local settings file (it is git-ignored):
   ```powershell
   Copy-Item backend\.env.example backend\.env
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```
   Edit `backend\.env`: paste that value as `JWT_SECRET`, keep your existing local `DB_USER`/`DB_PASSWORD`/`DB_NAME=leetcode_tracker` (your `root` login is fine **locally**).
2. Install and migrate (the migration only *adds* two nullable columns and two unique indexes; it never drops or edits rows):
   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements-dev.txt
   cd ..
   python database\migrate_auth.py
   ```
3. Claim your old `demo_user` history for **your** login (interactive; asks for username/email/password and requires typing `CLAIM`):
   ```powershell
   python database\link_legacy_account.py
   ```
   Skip this if you would rather start clean. Until claimed, `demo_user` has no email/password and **cannot log in**, so no demo credentials exist anywhere.
4. Start backend and frontend in two terminals:
   ```powershell
   cd backend; .\.venv\Scripts\Activate.ps1; python -m uvicorn main:app --reload
   ```
   ```powershell
   cd frontend; npm ci; npm run dev
   ```
   Open **http://localhost:5173** (use `localhost`, not `127.0.0.1`, so the cookie is same-site with the API on `localhost:8000`).
5. Run the tests:
   ```powershell
   cd backend; python -m pytest tests -q
   cd ..\frontend; npm run build
   ```

## 4. Private GitHub repository

Your project already has a local Git repo; do not touch the unrelated one at `C:\Users\DELL\.git`.

```powershell
cd C:\Users\DELL\OneDrive\Desktop\LeetTrack\LeetTrack
git status --short
git add -A
git status --short
git diff --cached --name-only
```

Read that list. It must **not** contain `.env`, `.venv`, `node_modules`, `dist`, `.pem`, or any `.sql` other than `schema.sql`, `schema_managed.sql`, `seed.sql`, `seed_question_bank.sql`, `create_app_user.sql`. If something is wrong, `git restore --staged <file>` and fix `.gitignore`; never `git add -f`.

Create an **empty private** repo on github.com (no README), then:

```powershell
git commit -m "Secure LeetTrack beta with authentication"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_PRIVATE_REPO.git
git push -u origin main
```

(Only push when you have read the file list. A private repo is not a safe place for passwords.)

## 5. Create the Aiven MySQL database

1. Aiven console → **Create service → MySQL → Free plan**. Check it says $0. Pick any region offered.
2. When it is *Running*, open **Overview** and note **Host, Port, User (avnadmin), Password, Database name (usually `defaultdb`)**. Download the **CA certificate** to e.g. `C:\leettrack\aiven-ca.pem` (outside the project).
3. In PowerShell, set the connection for this session (nothing is written to disk):
   ```powershell
   $env:DB_HOST="YOUR_AIVEN_HOST"; $env:DB_PORT="YOUR_AIVEN_PORT"
   $env:DB_USER="avnadmin"; $env:DB_NAME="defaultdb"
   $env:DB_PASSWORD = Read-Host "Aiven admin password"
   $env:DB_SSL_CA="C:\leettrack\aiven-ca.pem"
   ```
   > `Read-Host` shows the password as you type; it is only held in this window. Close the window afterwards.
4. Create tables, load the 200-question bank (this seed **never deletes**), using the MySQL client. PowerShell cannot use `<`, so use `source`:
   ```powershell
   mysql --host=$env:DB_HOST --port=$env:DB_PORT --user=$env:DB_USER --password --ssl-mode=VERIFY_CA --ssl-ca="$env:DB_SSL_CA" $env:DB_NAME -e "source database/schema_managed.sql"
   mysql --host=$env:DB_HOST --port=$env:DB_PORT --user=$env:DB_USER --password --ssl-mode=VERIFY_CA --ssl-ca="$env:DB_SSL_CA" $env:DB_NAME -e "source database/seed_question_bank.sql"
   ```
5. Create the **least-privilege runtime user**. Open `database/create_app_user.sql` in an editor, replace `YOUR_DB_NAME` and the password placeholder (use a long random password), save **without committing it**, then:
   ```powershell
   mysql --host=$env:DB_HOST --port=$env:DB_PORT --user=$env:DB_USER --password --ssl-mode=VERIFY_CA --ssl-ca="$env:DB_SSL_CA" $env:DB_NAME -e "source database/create_app_user.sql"
   git checkout -- database/create_app_user.sql
   ```
   (The last line restores the placeholder version so you don't leave a password in the repo.) Aiven shows the new user's password settings under **Users**; if `CREATE USER` is refused there, create `leettrack_app` from the Aiven console instead and run only the `GRANT` lines.
6. Verify tables: `mysql ... -e "SHOW TABLES; SELECT COUNT(*) FROM question_bank;"` should show 3 tables and 200 rows.

### Optional: bring over your own history
Only if you want your existing local progress online. Do **not** also run `seed.sql` (it is a local-demo file that deletes rows).
```powershell
mysqldump --no-create-info --complete-insert --skip-add-locks --single-transaction --no-tablespaces --set-gtid-purged=OFF -u root -p --result-file="..\leettrack_backups\leettrack_data_only.sql" leetcode_tracker users question_bank solved_questions
```
Import into an **empty** schema (so skip step 4's seed), with the Aiven variables from step 3 set:
```powershell
mysql --host=$env:DB_HOST --port=$env:DB_PORT --user=$env:DB_USER --password --ssl-mode=VERIFY_CA --ssl-ca="$env:DB_SSL_CA" $env:DB_NAME -e "source ../leettrack_backups/leettrack_data_only.sql"
python database\link_legacy_account.py
```
The second command attaches your history to *your* login on the Aiven database (same env variables).

## 6. Backend on Render

1. Render → **New → Web Service** → pick the private repo. **Instance type: Free.**
2. Settings:
   * Root directory: `backend`
   * Build command: `pip install -r requirements.txt`
   * Start command: `python -m uvicorn main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips="*"`
   * Health check path: `/api/health`
3. **Environment** (set in Render only — these are secrets and never go in Vercel or Git):

| Variable | Value |
|---|---|
| `PYTHON_VERSION` | `3.12.10` (the version you test with) |
| `APP_ENV` | `production` |
| `DB_HOST`, `DB_PORT`, `DB_NAME` | from Aiven |
| `DB_USER` | `leettrack_app` (**not** `avnadmin`) |
| `DB_PASSWORD` | password you chose for `leettrack_app` |
| `DB_SSL_CA_PEM` | full text of the CA file, including the `BEGIN/END CERTIFICATE` lines |
| `DB_SSL_VERIFY_IDENTITY` | leave unset (`true`). Only set `false` if logs show a host-name mismatch (chain is still verified). |
| `JWT_SECRET` | `python -c "import secrets; print(secrets.token_urlsafe(48))"` (new, not your local one) |
| `CORS_ORIGINS` | your Vercel address, e.g. `https://leettrack-xyz.vercel.app` (no trailing slash). Add it after step 7, then redeploy. |
| `ACCESS_TOKEN_MINUTES` | `120` |
| `MAX_USERS` | `100` (registrations stop after 100 accounts) |
| `RATE_REGISTER_PER_IP` / `RATE_REGISTER_TOTAL` | `30` / `150` for a demo where a class signs up from one shared campus IP (code defaults are 5 / 40 per hour) |
| `RATE_LOGIN_PER_IP` | `200` for the same reason (default 30 per 15 min) |
| `ARGON2_MEMORY_KIB` / `ARGON2_MAX_CONCURRENT` | optional; defaults `19456` / `3` keep password hashing within the free 512 MB instance |

The API **refuses to start** in production if the secret is short, TLS settings are missing, or `CORS_ORIGINS` is empty/`*`/localhost. That is intentional; read the Render log if deploy fails.

4. After deploy, copy the address (`https://YOUR-API.onrender.com`) and check:
   ```powershell
   Invoke-RestMethod https://YOUR-API.onrender.com/api/health
   ```
   Expected: `status : ok`. (The first call after idle takes about a minute.) `503` = database unreachable: re-check host/port/user/password/CA in Render's environment.

## 7. Frontend on Vercel

1. Edit `frontend/vercel.json`: replace `https://YOUR-RENDER-SERVICE.onrender.com` with your real Render address (keep `/api/:path*` on the end). Commit and push:
   ```powershell
   git add frontend/vercel.json; git commit -m "Point API rewrite at Render"; git push
   ```
2. Vercel → **Add New → Project** → import the repo.
   * Root directory: `frontend` · Framework: Vite · Build: `npm run build` · Output: `dist`
   * **Do not add any environment variables.**
3. Deploy. Copy the production address (e.g. `https://leettrack-xyz.vercel.app`) into Render's `CORS_ORIGINS` and redeploy the API.
4. If Vercel shows a *Vercel login* page to visitors, turn off **Deployment Protection → Vercel Authentication** for Production in the project settings.

Preview deployments get different addresses and are intentionally **not** trusted by CORS.

## 8. Test the live site

1. Open the Vercel address → you are sent to **/login**.
2. **Create account** (12+ character password). You land on an empty dashboard with new-question suggestions.
3. Refresh: you stay logged in. **Log out**: you return to login, and opening `https://YOUR-SITE/api/me/progress` shows `Please log in to continue`.
4. **Two-user isolation:** in a private window register a second account. Mark a question solved as A → it shows as solved for A only; B's Profile/Progress stay at zero; complete a revision as A and confirm B's numbers do not change.
5. Old routes must not work: `https://YOUR-SITE/api/users/1/progress` → 404.
6. Scan the build for leaks (before pushing, from `frontend`):
   ```powershell
   npm run build
   Get-ChildItem .\dist -Recurse -File | Select-String -Pattern "JWT_SECRET","DB_PASSWORD","localhost:8000" -SimpleMatch
   ```
   No output = good.

## 9. Cold starts and limits

* After 15 idle minutes Render sleeps. The next request needs ~1 minute; the site may show *"The server is waking up"* — wait and retry once. (A free external pinger hitting `/api/health` every ~10 minutes keeps it awake and costs about 744 of the 750 monthly hours, but it leaves no room for a second service and Render may change its policy, so it is optional.)
* Aiven may power the database off after inactivity (you get an email first). Power it on from the Aiven console.
* Login/registration limits are kept in memory (reset on restart). Defaults: 8 failed logins / 15 min per account, 30 login tries / 15 min per IP, 5 sign-ups / hour per IP and 40 / hour overall; raise them with the `RATE_*` variables in section 6 if a class shares one IP. This is basic abuse protection, not a firewall.
* Free tiers can be suspended at their monthly limits — there is no card on file to be charged.

## 10. Common errors

| Symptom | Likely cause / fix |
|---|---|
| Deploy log: `Production CORS_ORIGINS must contain…` | `CORS_ORIGINS` missing, `*`, or localhost. Set the exact Vercel address. |
| Deploy log: `JWT_SECRET must be configured…` | Secret missing or under 32 characters. |
| Deploy log: `Production requires DB_SSL_CA…` | Add `DB_SSL_CA_PEM` with the full certificate text. |
| `/api/health` → 503 | DB powered off, wrong host/port/user/password, or CA/host-name check failed (see `DB_SSL_VERIFY_IDENTITY`). |
| Login works then you are logged out immediately | You set `VITE_API_URL`, or `vercel.json` still has the placeholder. Remove the variable, fix `vercel.json`, redeploy. |
| "Request origin is not allowed" (403) | `CORS_ORIGINS` doesn't exactly match the site address (scheme + host, no slash). |
| "Security token missing or invalid" (403) | Stale tab after log-out/in. Refresh and retry. |
| "Too many attempts" (429) | Rate limit; wait 15 min or (as owner) restart the Render service. |
| `mysql: ... '<' operator is reserved` | PowerShell can't use `<`; use the `-e "source file.sql"` form shown above. |
| Imported dump fails with weird characters | It was created with `>` in PowerShell 5. Recreate with `--result-file`. |
| Local: `JWT_SECRET must be configured` | Put a 32+ character `JWT_SECRET` in `backend\.env`. |

## 11. Backups and recovery

Aiven's docs list backups for the free tier, but treat them as a convenience; keep your own copy.
```powershell
# with the $env:DB_* variables from section 5 (admin user) set:
mysqldump --host=$env:DB_HOST --port=$env:DB_PORT --user=$env:DB_USER --password --ssl-mode=VERIFY_CA --ssl-ca="$env:DB_SSL_CA" --single-transaction --no-tablespaces --set-gtid-purged=OFF --result-file="..\leettrack_backups\aiven_$(Get-Date -Format yyyyMMdd).sql" $env:DB_NAME
```
Keep dumps outside the project, ideally encrypted, and never in Git (they contain email addresses and password hashes). To recover, create a fresh free service (or empty the schema), run `schema_managed.sql`, `create_app_user.sql`, then `source` the dump. Practise a restore once into a throwaway database before you need it.

## 12. Updating the live app

```powershell
cd backend; python -m pytest tests -q; cd ..\frontend; npm run build; cd ..
git add -A; git status --short; git commit -m "Describe change"; git push
```
Vercel and Render redeploy from `main` automatically. Schema changes are **not** automatic: back up, then run a reviewed SQL/migration script with the admin user.

## 13. Shutting everything down (no surprise charges)

1. Take a final backup (section 11).
2. Render: service → **Settings → Delete Web Service**.
3. Vercel: project → **Settings → Delete Project**.
4. Aiven: service → **Delete** (or power off to keep it).
5. Confirm none of the three dashboards shows a payment method or paid plan. GitHub repo: delete or keep private.

## 14. Remaining limitations

* Free hosting is a beta, not production: cold starts, possible suspension, one DB node.
* Not implemented: email verification, password reset, MFA, account deletion. Don't store sensitive personal data.
* Logout clears the browser cookie; a copied session token stays valid until it expires (default 2 h).
* Rate-limit counters are per process and reset on restart.
* If the app ever becomes commercial, Vercel Hobby no longer applies.
