# SafeLinks

SafeLinks creates short links that stop working after a set time, a set number of visits,
or when the owner revokes them. Owners can add an optional passcode. Recipients get a plain
server-rendered page or a redirect, and never need an account.

SafeLinks controls access to the short link, not to the destination. After a recipient
reaches the destination they can copy or share it. See [the terms page](frontend/src/pages/Static.tsx).

## Stack

| Part | Technology |
| --- | --- |
| Web app | TypeScript, React 19, React Router 7, Tailwind CSS 4, Vite, served by nginx |
| Owner API | Python 3.12, FastAPI (`safelinks.api`) |
| Resolver | FastAPI, server-rendered HTML with no JavaScript (`safelinks.resolver`) |
| Cleanup | FastAPI endpoint plus CLI (`safelinks.remover`), triggered on a schedule |
| Auth | Supabase Auth (GoTrue). Local: `supabase/auth` container. Hosted: a Supabase project |
| Database | PostgreSQL 16. Local: Docker. Hosted: Supabase Postgres or any Postgres |
| Local email | Mailpit (catches confirmation and password-reset emails) |

One backend image runs all three services. The `SERVICE` environment variable selects
`api`, `resolver` or `remover`.

```
browser ──> web (nginx :8080) ──/api/*──────> api (FastAPI)
                              └─/auth/v1/*──> auth (Supabase GoTrue)
recipient ─> resolver (FastAPI :8001) /r/{id}
schedule ──> remover (FastAPI :8002) POST /internal/cleanup
api, resolver, remover, auth ──> Postgres
```

More detail: [architecture and decisions](docs/architecture.md), [API reference](docs/api.md),
[operations and runbooks](docs/operations.md).

## Run everything locally

Requirements: Docker with Compose v2.

```sh
docker compose up --build
```

No `.env` file is needed. Copy `.env.example` to `.env` only to change a default.

| URL | What |
| --- | --- |
| http://localhost:8080 | Web app (also proxies `/api` and `/auth/v1`) |
| http://localhost:8001/r/{id} | Resolver (short links point here) |
| http://localhost:8025 | Mailpit inbox for sign-up and reset emails |
| http://localhost:8000 | Owner API, direct |
| http://localhost:8002 | Cleanup service, direct |
| http://localhost:9999 | Supabase Auth, direct |
| localhost:54329 | Postgres (`postgres` / `postgres`, database `safelinks`) |

All ports bind to 127.0.0.1 only.

First run:

1. Open http://localhost:8080 and sign up.
2. Open http://localhost:8025 and click the confirmation link.
3. Create a link and open the short URL in another browser.

Set `MAILER_AUTOCONFIRM=true` in `.env` to skip email confirmation.

The `migrate` service applies `backend/safelinks/migrations/*.sql` before the backend
services start. The `cleanup-schedule` service calls the remover every
`CLEANUP_INTERVAL_SECONDS` (default 3600). It stands in for Cloud Scheduler.

Stop with `docker compose down`. Add `-v` to delete the database volume.

## Develop

Run the database and auth in Docker, and the app processes on the host.

```sh
docker compose up -d db mailpit auth migrate

# Backend (needs uv: https://docs.astral.sh/uv/)
cd backend
uv sync
SUPABASE_JWT_SECRET=local-dev-jwt-secret-change-me-at-least-32-chars \
  uv run uvicorn safelinks.api:app --port 8000 --reload
uv run uvicorn safelinks.resolver:app --port 8001 --reload   # second terminal

# Frontend (Node 24, see frontend/.nvmrc)
cd frontend
npm ci
npm run dev        # http://localhost:5173, proxies /api and /auth/v1 like nginx does
```

Operator commands (suspend accounts, revoke links, review abuse reports):

```sh
cd backend && uv run python -m safelinks.admin --help
```

## Test

Backend tests need a Postgres server. They create and drop a `safelinks_test` database.

```sh
docker compose up -d db
cd backend
uv run ruff format --check . && uv run ruff check .
uv run pytest            # uses localhost:54329; override with TEST_DATABASE_ADMIN_URL
```

Frontend:

```sh
cd frontend
npm run typecheck && npm run lint && npm test && npm run build
```

CI (`.github/workflows/ci.yml`) runs all of the above on every pull request. It also builds
both Docker images, validates the compose file, audits dependencies (`pip-audit`,
`npm audit`) and scans for secrets (`gitleaks`, config in `.gitleaks.toml`).

## Configuration

Backend settings are environment variables, all listed with defaults in
[`backend/safelinks/config.py`](backend/safelinks/config.py). The ones you must set outside
local development:

| Variable | Purpose |
| --- | --- |
| `APP_ENV=production` | Turns on production checks (no default salt, no wildcard CORS) |
| `DATABASE_URL` | Postgres connection string |
| `SUPABASE_JWT_SECRET` or `SUPABASE_JWKS_URL` | Verifies Supabase access tokens |
| `SUPABASE_JWT_ISSUER` | Expected `iss`, for example `https://<ref>.supabase.co/auth/v1` |
| `SUPABASE_AUTH_URL`, `SUPABASE_SERVICE_ROLE_KEY` | Deletes the sign-in identity on account deletion |
| `RESOLVER_BASE_URL` | Public origin of the resolver; short URLs are built from it |
| `FRONTEND_URL`, `CORS_ORIGINS` | Public origin of the web app |
| `RATE_LIMIT_SALT` | Secret salt for hashed client IPs |
| `CLEANUP_TOKEN` | Bearer token for `POST /internal/cleanup` |
| `TRUSTED_PROXY_HOPS` | Proxies in front of the service that append to `X-Forwarded-For` |

The web app reads two optional build arguments: `VITE_SUPABASE_URL` and
`VITE_SUPABASE_ANON_KEY`. Leave them empty to use the same-origin `/auth/v1` proxy.

## Status

Verified locally: the full compose stack, the API and resolver end to end, the browser
flows (sign-up, email confirmation, create, passcode visit, revoke, password reset, account
deletion), and scheduled cleanup.

Not verified: any cloud deployment, Cloud Scheduler, a production domain, or a hosted
Supabase project. [docs/operations.md](docs/operations.md) describes those steps but they have
not been run.
