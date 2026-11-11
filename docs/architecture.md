# Architecture and decisions

## Shape

```
browser ──> web (nginx) ──/api/*────> api (FastAPI)
                        └─/auth/v1/*─> Supabase Auth
recipient ─> resolver (FastAPI, own origin) /r/{id}
scheduler ─> remover (FastAPI, private) POST /internal/cleanup
api, resolver, remover ──> Postgres (accounts, links, audit_events, rate_limits, abuse_reports)
```

- **One backend package, one image.** `backend/safelinks` holds the domain rules
  (`domain.py`), all SQL (`repository.py`), shared HTTP plumbing (`http.py`) and three thin
  ASGI apps (`api.py`, `resolver.py`, `remover.py`). `SERVICE` picks the app at start-up.
  Services share code but scale and fail separately.
- **Resolver on its own origin.** It serves server-rendered HTML with no JavaScript, so a
  bug in the web app cannot affect redirects, and the resolver never sees owner tokens.
- **Schema** is in `backend/safelinks/migrations/001_init.sql`. Status (`active`,
  `expired`, `exhausted`, `revoked`) is derived from columns on read and is never stored,
  so it cannot go stale.
- **Frontend** is a TypeScript React SPA. It talks only to its own origin. nginx (or the
  Vite dev server) proxies the API and Supabase Auth.

## Stack override

The repository started as Python services on Google Cloud Datastore with a JavaScript
frontend. As instructed, the stack is now TypeScript (frontend), FastAPI (backend),
Supabase (auth, and the hosted Postgres), and Docker Postgres for local development. The
Datastore code was removed.

## Decisions (PRD §23)

### 1. Authentication: Supabase Auth

Chosen as part of the required stack. Locally it runs as the `supabase/auth` container
against the same Postgres, with Mailpit catching emails. The browser uses
`@supabase/auth-js` for sign-up, sign-in, email confirmation and password reset. The API
verifies the access token itself (HS256 secret or JWKS, `exp`, `aud=authenticated`,
optional `iss`), so it does not call Supabase on each request. Evidence: `auth.py`, the
token tests in `tests/test_api.py`, and the browser QA run (sign-up, confirm, reset,
delete).

### 2. Transactions: one conditional UPDATE in Postgres

A visit is authorised by a single statement (`repository.reserve_visit`): it updates the
link only if the owner is active, the link is not revoked, not expired, under its limit,
and (for protected links) the passcode was checked. The visit audit row is inserted in the
same statement. Under READ COMMITTED, Postgres locks the row and re-checks the `WHERE`
clause for each waiting updater against the committed row, so the limit cannot be exceeded.
No retries or explicit transactions are needed.

Evidence: `tests/test_resolver.py::test_concurrent_visits_never_exceed_limit` fires
concurrent visits at a link with fewer visits left than requests and checks that exactly
`max_clicks` succeed and `clicks` and the audit rows agree.

### 3. Rate limiting: fixed-window counters in Postgres

`rate_limits(key, window_start, count)` with an `insert ... on conflict do update`
increment. It is shared across all instances with no extra infrastructure. Keys hash the
client IP with `RATE_LIMIT_SALT`, so raw IPs are never stored. Limits are configured with
`RL_*` variables. Cleanup deletes old windows.

Ceiling: every limited request is one write. If resolver traffic outgrows that, move the
counters to Redis (Memorystore) or put Cloud Armor rate limiting in front. The interface is
one function in `http.py`.

### 4. Retention: 30 days for inactive links, 90 days for activity

Revoked, exhausted and expired links are deleted 30 days after they stopped working.
Activity rows are deleted after 90 days. All four values are configurable
(`RETENTION_*_DAYS`). Cleanup works in batches, is idempotent and is safe to run twice at
once (`tests/test_cleanup.py`). The privacy page states these numbers.

### 5. Unavailable behaviour: 404 for unknown, specific 410 for inactive

Unknown or malformed IDs return a generic 404. Known but inactive links return 410 with the
reason (expired, visit limit reached, or "no longer available" for revoked and suspended).
IDs carry 128 random bits, so the 404/410 split does not help anyone find links. The
specific message helps a real recipient understand why a link they were sent stopped
working. Revoked and suspended share one message so a suspension is not disclosed. The page
never shows the destination.

### 6. Passcode delivery: immediate redirect, no session

The passcode form posts to `/r/{id}/verify`. On success the server counts the visit and
returns `303` to the destination at once. There is no session, cookie or token to steal or
replay. Wrong passcodes return `403`, count nothing, and are rate limited per link and per
IP. Passcodes are stored only as Argon2id hashes.

### 7. Domain: to be decided

Not chosen yet. The code needs only `RESOLVER_BASE_URL` and `FRONTEND_URL`. The resolver
must use a separate origin (for example `go.<domain>` and `app.<domain>`).

### 8. Deletion and retention commitments

What the code actually does, and what the privacy page promises:

- Account deletion removes all links and all activity in one transaction and marks the
  `accounts` row `deleted` (a tombstone holding only the auth user ID). It then deletes the
  Supabase Auth user, which holds the email and password. Links stop resolving at once. The
  tombstone stops a still-valid access token from recreating the account, which would
  otherwise also undo a suspension. If the auth call fails the API returns `502` and the
  user can retry.
- Inactive links and old activity are removed on the retention schedule above.
- Logs contain no destination URLs, passcodes, tokens or raw IPs.
- Abuse reports are kept until an operator resolves them.
- Database backups (on the hosted provider) are outside this code. Their retention must be
  stated once the provider plan is chosen.

## Security headers

| Surface | Headers |
| --- | --- |
| API and remover | `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `CSP: default-src 'none'; frame-ancestors 'none'`, COOP, Permissions-Policy |
| Resolver pages | As above, plus `CSP: default-src 'none'; style-src 'unsafe-inline'; img-src data:; frame-ancestors 'none'; base-uri 'none'` and `X-Robots-Tag: noindex` |
| Web (nginx) | Strict same-origin CSP (`script-src 'self'`, no inline script), `nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, Permissions-Policy. Hashed assets are cached for a year, `index.html` is `no-cache` |

Every response has an `X-Request-Id`. Request bodies over 16 KiB are rejected. Destination
URLs must be `http` or `https`, with no credentials and no control characters.
