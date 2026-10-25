# Disposable Render demo backend

Deploy `api.main:app` from `backend`. The legacy `main.py` is not the deployment
entrypoint. No business logic, schema changes, seeds, or local data copying are
part of deployment.

## Local development (PowerShell, from repository root)

For a fresh checkout, copy `backend/.env.example` to `backend/.env` and replace
the fake `DATABASE_URL` with your local connection. Do not overwrite an existing
`.env`. The current workstation's connection has been preserved there.

```powershell
cd backend
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m uvicorn api.main:app --reload
```

If no environment exists, first create one with `py -3.12 -m venv venv`.
Existing tracked Windows venv files are not used on Render; install dependencies
fresh there. Runtime dependencies are in `requirements.txt`, tests separately in
`requirements-test.txt`.

## Variables

| Variable | Local | Render |
|---|---|---|
| `DATABASE_URL` | Local PostgreSQL connection in ignored `.env` | Separate disposable database's Internal Database URL |
| `FRONTEND_ORIGIN` | `http://localhost:5173` (default) | Exact deployed frontend origin, e.g. `https://YOUR-FRONTEND.onrender.com` |
| `PORT` | Not needed by the local command | Supplied by Render and passed to Uvicorn |

Environment variables override `.env`; the file is resolved relative to backend,
independent of the shell directory. Missing `DATABASE_URL` fails startup clearly.
Both `postgresql://` and legacy `postgres://` URLs work. CORS origins may be
comma-separated; paths and wildcard origins are rejected.

**CORS is browser policy, not authentication.** This unauthenticated public demo
allows public API writes. Use fake, disposable data only.

## Render Web Service settings

Create a separate empty Render PostgreSQL database in the same region/workspace
as the backend. Copy its **Internal Database URL** into the service's
`DATABASE_URL` secret environment variable. No individual DB_HOST/DB_PASSWORD
variables are needed. Do not point this service at the local Billing_db or
upload/restore its data. External URLs are for clients outside Render's network.

```text
Branch: UAT (after merging the backend branch)
Root Directory: backend
Runtime: Python 3
Build Command: pip install -r requirements.txt
Start Command: alembic upgrade head && uvicorn api.main:app --host 0.0.0.0 --port $PORT
Health Check Path: /health
```

The service root's `backend/.python-version` selects Python 3.12 (latest patch). Do not
override it with an unrelated Python version in Render settings.

The combined start command is for one disposable demo instance: migration failure
prevents API startup. Render's paid services can instead use Pre-Deploy Command
`alembic upgrade head` with Start Command
`uvicorn api.main:app --host 0.0.0.0 --port $PORT`. Do not run migrations in the
build command or add `create_all()` to application startup. Coordinate migrations
separately before scaling to multiple instances.

## Database initialization

From `backend`, with `DATABASE_URL` set to the **empty demo database**:

```sh
alembic upgrade head
```

Alembic imports the same effective `DATABASE_URL` as the API. The frozen baseline
is unchanged; no new migration is required. Do not run this against an existing
unstamped local database as a deployment preparation step. `/health` is a cheap
liveness check, not a database readiness check.

## Secrets and verification

`.env`, backups, and virtual environments are ignored. An ignore rule does not
remove files already tracked in Git. Local database credentials previously in
application config and `alembic.ini` remain in Git history: rotate the password
and update the ignored local `.env`. No history rewrite is included.

Configuration tests and the existing business regression run without a cloud
database. Offline Alembic SQL generation checks migration wiring; an actual
Render build, online migration, and HTTP smoke test remain deployment-time checks.

Official references: [FastAPI deployment](https://render.com/docs/deploy-fastapi),
[deploy stages](https://render.com/docs/deploys),
[Python version](https://render.com/docs/python-version),
[PostgreSQL connections](https://render.com/docs/postgresql-creating-connecting).
