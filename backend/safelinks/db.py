"""Connection pool and SQL migration runner."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import asyncpg

from .config import settings

log = logging.getLogger("safelinks.db")

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
_MIGRATION_LOCK_ID = 7_441_001


async def create_pool(dsn: str | None = None) -> asyncpg.Pool:
    # command_timeout bounds every query so a stuck database fails closed instead of hanging.
    return await asyncpg.create_pool(
        dsn or settings.database_url,
        min_size=1,
        max_size=settings.db_pool_max,
        command_timeout=settings.db_timeout_seconds,
        timeout=settings.db_timeout_seconds,
    )


async def migrate(dsn: str | None = None) -> list[str]:
    """Apply pending migrations in order. Safe to run concurrently (advisory lock)."""
    conn = await asyncpg.connect(dsn or settings.database_url)
    applied: list[str] = []
    try:
        await conn.execute("select pg_advisory_lock($1)", _MIGRATION_LOCK_ID)
        await conn.execute(
            "create table if not exists schema_migrations ("
            " version text primary key, applied_at timestamptz not null default now())"
        )
        await conn.execute("alter table schema_migrations enable row level security")
        done = {r["version"] for r in await conn.fetch("select version from schema_migrations")}
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.stem in done:
                continue
            async with conn.transaction():
                await conn.execute(path.read_text())
                await conn.execute("insert into schema_migrations (version) values ($1)", path.stem)
            applied.append(path.stem)
            log.info("migration applied", extra={"fields": {"version": path.stem}})
    finally:
        await conn.execute("select pg_advisory_unlock($1)", _MIGRATION_LOCK_ID)
        await conn.close()
    return applied


if __name__ == "__main__":
    from .logs import configure_logging

    configure_logging("migrate")
    print(asyncio.run(migrate()) or "up to date")
