# Operations

> **Verification status.** Everything under "Local" was run and checked. Every cloud step
> below (Cloud Run, Cloud Scheduler, a hosted Supabase project, a production domain) is a
> written plan only. None of it has been run. Treat it as a checklist, not a known-good
> procedure.

## Services

| Service | Image | `SERVICE` | Public? | Notes |
| --- | --- | --- | --- | --- |
| web | `frontend/Dockerfile` | n/a | yes | nginx serving the SPA. Proxies `/api` and `/auth/v1` |
| api | `backend/Dockerfile` | `api` | yes (through web or its own URL) | Owner API |
| resolver | `backend/Dockerfile` | `resolver` | yes | Short links. Must sit on its own origin |
| remover | `backend/Dockerfile` | `remover` | no | `POST /internal/cleanup`, bearer token |
| migrate | `backend/Dockerfile` | n/a | no | `python -m safelinks.db`, run once per release |
| auth | Supabase Auth | n/a | yes | Hosted Supabase in production |
| db | Postgres 16 | n/a | no | Supabase Postgres or any Postgres |

The backend container listens on `$PORT` (default 8080) and starts
`uvicorn safelinks.${SERVICE}:app`. Each service exposes `/healthz` and `/readyz`.

## Configuration

All backend settings and defaults are in `backend/safelinks/config.py`. In production set
`APP_ENV=production`. The service then refuses to start with the default
`RATE_LIMIT_SALT` or with wildcard CORS.

| Variable | api | resolver | remover | Notes |
| --- | --- | --- | --- | --- |
| `DATABASE_URL` | yes | yes | yes | Use the pooled connection string for Supabase |
| `SUPABASE_JWT_SECRET` or `SUPABASE_JWKS_URL` | yes | | | |
| `SUPABASE_JWT_ISSUER` | yes | | | `https://<ref>.supabase.co/auth/v1` |
| `SUPABASE_AUTH_URL`, `SUPABASE_SERVICE_ROLE_KEY` | yes | | | Needed for account deletion |
| `RESOLVER_BASE_URL` | yes | | | Short URLs are built from it |
| `FRONTEND_URL`, `CORS_ORIGINS` | yes | yes | | |
| `RATE_LIMIT_SALT` | yes | yes | | Same value on both |
| `TRUSTED_PROXY_HOPS` | yes | yes | | `1` behind one load balancer |
| `CLEANUP_TOKEN` | | | yes | Long random string |
| `RL_*` | yes | yes | | `count/seconds`, for example `RL_RESOLVE_IP=120/60` |
| `RETENTION_*_DAYS`, `CLEANUP_BATCH_SIZE`, `CLEANUP_MAX_BATCHES` | | | yes | Defaults 30/30/30/90 days, 500, 200 |

Keep secrets (`SUPABASE_JWT_SECRET`, `SUPABASE_SERVICE_ROLE_KEY`, `RATE_LIMIT_SALT`,
`CLEANUP_TOKEN`, the database password) in a secret manager. Never put them in the image or
the repository. CI runs gitleaks on every push.

## Local

```sh
docker compose up --build        # whole stack, see README for URLs
docker compose logs -f api resolver remover
docker compose run --rm migrate  # re-apply migrations (idempotent)
```

The `cleanup-schedule` service calls the remover every `CLEANUP_INTERVAL_SECONDS`.

## Deploy to Google Cloud (not verified)

Assumes a project with Artifact Registry, Cloud Run, Cloud Scheduler and Secret Manager
enabled, and a hosted Supabase project.

1. **Supabase.** Create a project. From its settings take the database connection string,
   the JWT secret (or use `https://<ref>.supabase.co/auth/v1/.well-known/jwks.json`), and
   the service-role key. In Auth settings set the Site URL to the web origin and add
   `<web origin>/reset-password` to the redirect allow list. Configure SMTP.
2. **Secrets.** Store each secret in Secret Manager.
3. **Build and push** both images with a tag per commit:
   ```sh
   docker build -t $REGION-docker.pkg.dev/$PROJECT/safelinks/backend:$SHA backend
   docker build --build-arg VITE_SUPABASE_URL=https://<ref>.supabase.co \
     --build-arg VITE_SUPABASE_ANON_KEY=<anon key> \
     -t $REGION-docker.pkg.dev/$PROJECT/safelinks/web:$SHA frontend
   docker push ...
   ```
   The web image's nginx proxies `/api` to `API_UPSTREAM`. Set it to the api service URL,
   or put both behind one load balancer.
4. **Migrate.** Run the backend image once as a Cloud Run job with command
   `python -m safelinks.db` and `DATABASE_URL` set. Migrations are idempotent.
5. **Deploy services.** One Cloud Run service per `SERVICE` value, same image:
   ```sh
   gcloud run deploy safelinks-resolver --image ...backend:$SHA \
     --set-env-vars SERVICE=resolver,APP_ENV=production,TRUSTED_PROXY_HOPS=1 \
     --set-secrets DATABASE_URL=db-url:latest,RATE_LIMIT_SALT=rl-salt:latest \
     --allow-unauthenticated --min-instances 1
   ```
   Deploy `api` the same way with its variables. Deploy `remover` with
   `--no-allow-unauthenticated`.
6. **Schedule cleanup.** Create a service account `cleanup-invoker` with
   `roles/run.invoker` on the remover. Then:
   ```sh
   gcloud scheduler jobs create http safelinks-cleanup --schedule "0 * * * *" \
     --uri https://<remover url>/internal/cleanup --http-method POST \
     --oidc-service-account-email cleanup-invoker@$PROJECT.iam.gserviceaccount.com \
     --headers "X-Cleanup-Token=<CLEANUP_TOKEN>"
   ```
   Scheduler puts its OIDC token in `Authorization`, and Cloud Run IAM checks it. The
   remover checks `X-Cleanup-Token` against `CLEANUP_TOKEN` as a second layer.
7. **Domain.** Map the web and resolver services to their domains (still TBD). The resolver
   must use a different origin from the web app. Update `RESOLVER_BASE_URL`,
   `FRONTEND_URL`, `CORS_ORIGINS` and the Supabase Site URL.

## Runbooks

### Deploy a change

1. CI must be green on the commit.
2. Build and push images tagged with the commit SHA.
3. Run the migrate job. Migrations must stay backward compatible with the running version.
4. Deploy resolver, then api, then remover, then web.
5. Check `/readyz` on each service and open one short link.

### Roll back

Redeploy the previous image tag (`gcloud run services update-traffic <svc>
--to-revisions <previous>=100`). Migrations are additive, so the older code keeps working.
Do not roll back the database.

### Check that scheduled cleanup runs

- Look for `event="cleanup_run"` log entries, one per schedule tick. Each carries
  `deleted`, `batches`, `failed` and `duration_ms`.
- `failed > 0` or a `500 CLEANUP_PARTIAL_FAILURE` response means some batches failed. The
  next run retries them. Investigate if it repeats.
- Manual run: `docker compose exec remover python -m safelinks.remover` locally, or
  trigger the Scheduler job with `gcloud scheduler jobs run safelinks-cleanup`.
- Confirm in SQL: `select count(*) from links where revoked_at < now() - interval '31 days';`
  should be `0`.

### Investigate resolver errors

1. Filter logs on `service="resolver"` and `event="http_request"` with `status>=500`. Each
   entry has a `request_id`, also returned to the client as `X-Request-Id`.
2. `event="db_unavailable"` means Postgres could not be reached. The resolver returns 503
   and never redirects in that case. Check `/readyz` and the database.
3. A spike of `event="resolve_outcome"` with `outcome="not_found"` from few IPs usually
   means link-ID scanning. `event="rate_limited"` should rise with it.
4. Check whether the cause was a deploy and roll back if so.

### Handle an abusive link or account

```sh
cd backend
uv run python -m safelinks.admin reports --status open
uv run python -m safelinks.admin revoke <link_id>
uv run python -m safelinks.admin suspend <user_id>     # all their links stop resolving
uv run python -m safelinks.admin resolve-report <report_id> actioned
uv run python -m safelinks.admin unsuspend <user_id>   # after a successful appeal
```

Point `DATABASE_URL` at production to run these against it. Every action writes a
structured log entry (`link_revoked`, `account_status_changed`).

### Rotate credentials

| Secret | How | Impact |
| --- | --- | --- |
| `CLEANUP_TOKEN` | Update the secret, redeploy remover, update the Scheduler job | One missed run at most |
| `RATE_LIMIT_SALT` | Update, redeploy api and resolver | Rate-limit counters reset |
| `SUPABASE_SERVICE_ROLE_KEY` | Roll in Supabase, update, redeploy api | Account deletion fails with 502 until redeployed |
| Supabase JWT secret | Roll in Supabase, update, redeploy api | All users must sign in again. Prefer JWKS to avoid this |
| Database password | Change in Supabase, update `DATABASE_URL`, redeploy all | Brief errors during rollout |

### Restore after a datastore outage

- While Postgres is down, the resolver returns 503 and never redirects. The api returns
  503. No visits are counted, so no limits are exceeded.
- After it returns, check `/readyz` on every service. Connections reconnect on their own.
- If the database was restored from a backup, links created after the backup are gone, and
  visits counted after it are lost. Visit limits can then allow extra visits for links that
  were active at the time. Tell affected owners if this matters.
- Run cleanup once by hand afterwards.

## Monitoring

Logs are JSON lines on stdout with `severity`, `service`, `event` and `request_id`. Cloud
Logging parses them as structured entries. Create log-based metrics on the `event` field:

| Metric | Filter | Suggested alert |
| --- | --- | --- |
| Request errors | `event="http_request" AND status>=500` | > 1% of requests for 5 minutes |
| Resolver latency | `event="http_request" AND service="resolver"`, distribution of `latency_ms` | p95 > 500 ms for 10 minutes |
| Database down | `event="db_unavailable"` | any, for 2 minutes |
| Cleanup missing | `event="cleanup_run"` count | 0 in 3 hours |
| Cleanup failing | `event="cleanup_run" AND failed>0` | 2 runs in a row |
| Rate limiting | `event="rate_limited"`, by `scope` | Sudden 10x jump |
| Passcode guessing | `event="passcode_attempt" AND outcome="rejected"` | Sudden 10x jump |
| Abuse reports | `event="abuse_report"` | any (notify, not page) |
| Link creation | `event="link_created"` | Sudden 10x jump |
| ID collisions | `event="link_id_collision"` | any (should never happen) |

Other events: `resolve_outcome` (`redirect`, `passcode_required`, `not_found`, `expired`,
`exhausted`, `revoked`, `owner_suspended`), `link_revoked`, `account_deleted`,
`account_status_changed`.

Logs never contain destination URLs, passcodes, tokens or raw IP addresses.
