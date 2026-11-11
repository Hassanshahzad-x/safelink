# API reference

Base path for the owner API: `/api/v1`. In the browser it is reached through the web
app's origin (`/api/v1/...`). The resolver and the cleanup service are separate origins.

## Conventions

- Requests and responses are JSON. Request bodies are capped at 16 KiB.
- Unknown request fields are rejected.
- Errors always use this shape:

  ```json
  { "error": { "code": "INVALID_URL", "message": "Only http and https URLs are supported." } }
  ```

- `429` responses include `Retry-After` in seconds.
- Every response carries `X-Request-Id`. Send your own (8 to 64 characters from
  `[A-Za-z0-9._-]`) to correlate logs.
- Times are ISO 8601 in UTC.

## Authentication

Owner endpoints need `Authorization: Bearer <Supabase access token>`. Get the token from
Supabase Auth (`/auth/v1/token?grant_type=password`, or the `@supabase/auth-js` client).
The API checks the signature, `exp`, the `authenticated` audience and, when configured,
the issuer. A missing or invalid token returns `401 UNAUTHORIZED`.

The first authenticated request creates the user's `accounts` row.

## Link object

```json
{
  "id": "AbCdEfGhIjKlMnOpQrStUv",
  "short_url": "https://sl.example/r/AbCdEfGhIjKlMnOpQrStUv",
  "url": "https://example.com/report.pdf",
  "destination_host": "example.com",
  "created_at": "2026-11-11T10:00:00Z",
  "expires_at": "2026-11-12T10:00:00Z",
  "max_clicks": 3,
  "clicks": 1,
  "remaining_clicks": 2,
  "status": "active",
  "revoked_at": null,
  "passcode_protected": false
}
```

- `id`: 22 characters, 128 bits from a CSPRNG, URL-safe base62.
- `status` is derived on read, in this order: `revoked`, then `expired`
  (`now >= expires_at`), then `exhausted` (`clicks >= max_clicks`), otherwise `active`.
- `remaining_clicks` is `0` when the link is not active.
- The passcode and its hash are never returned.

## Endpoints

### `GET /api/v1/me`

Returns the signed-in account and the server's limits.

```json
{ "id": "<uuid>", "email": "a@example.com", "status": "active",
  "limits": { "max_ttl_hours": 720, "max_clicks": 1000 } }
```

### `POST /api/v1/links` → `201`

```json
{ "url": "https://example.com/doc", "ttl_hours": 24, "max_clicks": 1, "passcode": null }
```

| Field | Rule |
| --- | --- |
| `url` | `http` or `https`, has a host, at most 2048 characters, no spaces or control characters, no embedded credentials. The host is lowercased and IDNA-encoded. |
| `ttl_hours` | Integer, 1 to `MAX_TTL_HOURS` (default 720). |
| `max_clicks` | Integer, 1 to `MAX_CLICKS_LIMIT` (default 1000). |
| `passcode` | Optional. 4 to 128 characters. Stored as an Argon2id hash. |

Errors: `400 INVALID_URL | INVALID_TTL | INVALID_MAX_CLICKS | INVALID_PASSCODE | INVALID_REQUEST`,
`403 ACCOUNT_SUSPENDED`, `429 RATE_LIMITED` (per IP, per user per minute and per user per day).

### `GET /api/v1/links`

Query parameters:

| Name | Values |
| --- | --- |
| `status` | `active`, `expired`, `exhausted`, `revoked` |
| `search` | Matches the destination host (substring, case-insensitive) or an exact link ID |
| `sort` | `created_desc` (default), `created_asc`, `expires_asc`, `expires_desc` |
| `limit` | 1 to 100, default 20 |
| `cursor` | `next_cursor` from the previous page |

```json
{ "items": [ { "...link" : "..." } ], "next_cursor": "WyIyMDI2LTEx..." }
```

`next_cursor` is `null` on the last page. Pagination is keyset-based, so it is stable while
links are created.

### `GET /api/v1/links/{id}`

The link object plus its activity:

```json
{ "...": "...", "events": [ { "type": "created", "at": "...", "metadata": {} },
                            { "type": "visit", "at": "...", "metadata": {} } ] }
```

Event types: `created`, `visit`, `revoked`. Activity older than 90 days is deleted.
A link owned by someone else returns `404 LINK_NOT_FOUND`, the same as a missing link.

### `POST /api/v1/links/{id}/revoke`

Revokes the link and returns it. Idempotent: revoking twice returns `200` and keeps the
first `revoked_at`. `404 LINK_NOT_FOUND` for missing or foreign links.

### `DELETE /api/v1/account` → `204`

Deletes the account, all of its links and their activity, then deletes the Supabase Auth
user. Links stop resolving immediately. If the auth deletion fails, the response is
`502 AUTH_DELETE_FAILED`. The data is already gone in that case, and retrying is safe.

### `POST /api/v1/reports` → `202` (no auth)

```json
{ "link": "https://sl.example/r/AbCd...", "reason": "phishing", "details": null, "email": null }
```

`link` accepts a short URL or a bare ID. `reason` is one of `phishing`, `malware`, `spam`,
`illegal`, `other`. The response is `{"status": "received"}` whether or not the link
exists. Rate limited per IP (default 10 per hour).

## Resolver

Origin: `RESOLVER_BASE_URL`. Responses are HTML with a strict CSP, `no-store` caching,
`noindex` and `Referrer-Policy: no-referrer`.

| Request | Result |
| --- | --- |
| `GET /r/{id}`, active, no passcode | `302` to the destination. The visit is counted in the same statement that checks the policy. |
| `GET /r/{id}`, active, passcode | `200` passcode form. No visit is counted. |
| `POST /r/{id}/verify` (form field `passcode`), correct | `303` to the destination, visit counted |
| `POST /r/{id}/verify`, wrong | `403` form with "Incorrect passcode." No visit is counted. |
| Expired | `410` "This link has expired." |
| Visit limit reached | `410` "This link has reached its visit limit." |
| Revoked, or owner suspended | `410` "This link is no longer available." |
| Unknown or malformed ID | `404` |
| Too many requests | `429` with `Retry-After` |
| Database unavailable | `503`. Never a redirect. |

Passcode attempts are rate limited per link (default 10 per 15 minutes) and per IP
(default 30 per 15 minutes). Only `GET` and `POST` are routed, so link previews that send
`HEAD` get `405` and never count a visit.

## Cleanup service

`POST /internal/cleanup` with `Authorization: Bearer <CLEANUP_TOKEN>`, or with
`X-Cleanup-Token: <CLEANUP_TOKEN>` when `Authorization` carries a Cloud Scheduler OIDC token.
Without a valid token it returns `401`.

```json
{ "deleted": { "revoked": 0, "exhausted": 2, "expired": 5, "audit_events": 40, "rate_limits": 12 },
  "batches": 4, "failed": 0, "duration_ms": 31 }
```

Returns `500 CLEANUP_PARTIAL_FAILURE` when any batch failed. The counts are then only in the
`cleanup_run` log entry. Completed batches stay deleted. Runs are idempotent and safe to
overlap.

## Health

Every service exposes `GET /healthz` (process is up) and `GET /readyz` (database
reachable, otherwise `503`). The web container exposes `GET /healthz`.
