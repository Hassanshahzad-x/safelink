"""Retention cleanup: bounded, batched, idempotent, safe to run concurrently.

HTTP:  uvicorn safelinks.remover:app   ->  POST /internal/cleanup (Bearer CLEANUP_TOKEN)
CLI:   python -m safelinks.remover
"""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import time

import asyncpg
from fastapi import Request

from . import repository as repo
from .config import settings
from .db import create_pool
from .domain import AppError
from .http import create_app
from .logs import configure_logging, event

log = logging.getLogger("safelinks.remover")


async def run_cleanup(pool: asyncpg.Pool) -> dict:
    """Delete links past their retention window, old audit events and stale rate-limit
    windows. Each batch is its own short transaction, so a failure keeps prior progress
    and a rerun simply continues."""
    start = time.perf_counter()
    plan = {
        "revoked": settings.retention_revoked_days,
        "exhausted": settings.retention_exhausted_days,
        "expired": settings.retention_expired_days,
        "audit_events": settings.retention_audit_days,
    }
    deleted = dict.fromkeys(plan, 0)
    batches = failed = 0
    for kind, days in plan.items():
        for _ in range(settings.cleanup_max_batches):
            try:
                async with pool.acquire() as conn:
                    n = await repo.delete_batch(conn, kind, days, settings.cleanup_batch_size)
            except Exception:
                failed += 1
                log.exception("cleanup batch failed", extra={"fields": {"kind": kind}})
                break
            batches += 1
            deleted[kind] += n
            if n < settings.cleanup_batch_size:
                break
    try:
        async with pool.acquire() as conn:
            deleted["rate_limits"] = await repo.purge_rate_limits(conn)
    except Exception:
        failed += 1
        log.exception("rate-limit purge failed")
    result = {
        "deleted": deleted,
        "batches": batches,
        "failed": failed,
        "duration_ms": round((time.perf_counter() - start) * 1000),
    }
    event("cleanup_run", logging.ERROR if failed else logging.INFO, **result)
    return result


app = create_app("remover")


@app.post("/internal/cleanup")
async def cleanup(request: Request):
    expected = settings.cleanup_token
    # Cloud Scheduler with OIDC puts its Google ID token in Authorization, so the app
    # token can also come in X-Cleanup-Token. Cloud Run IAM checks the OIDC token.
    token = request.headers.get("x-cleanup-token")
    if token is None:
        scheme, _, token = request.headers.get("authorization", "").partition(" ")
        token = token if scheme.lower() == "bearer" else ""
    if not expected or not hmac.compare_digest(token.strip().encode(), expected.encode()):
        raise AppError(401, "UNAUTHORIZED", "Unauthorized.")
    result = await run_cleanup(request.app.state.pool)
    if result["failed"]:
        raise AppError(500, "CLEANUP_PARTIAL_FAILURE", "Cleanup finished with failures.")
    return result


async def _main() -> int:
    configure_logging("remover-cli")
    pool = await create_pool()
    try:
        result = await run_cleanup(pool)
    finally:
        await pool.close()
    print(json.dumps(result))
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
