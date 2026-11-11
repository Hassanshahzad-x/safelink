"""All SQL lives here. Policy-enforcing mutations are single atomic statements."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import asyncpg

from .domain import STATUS_SQL, LinkStatus

LINK_COLUMNS = """
    l.id, l.owner_id, l.original_url, l.destination_host, l.created_at, l.updated_at,
    l.expires_at, l.max_clicks, l.clicks, l.exhausted_at, l.revoked_at, l.revoked_by,
    (l.passcode_hash is not null) as passcode_protected, now() as db_now
"""

# ---------------------------------------------------------------------------
# Accounts


async def ensure_account(conn: asyncpg.Connection, user_id: str) -> asyncpg.Record:
    return await conn.fetchrow(
        """
        with ins as (
            insert into accounts (id) values ($1) on conflict (id) do nothing
            returning id, status, plan, created_at
        )
        select * from ins
        union all
        select id, status, plan, created_at from accounts where id = $1
        limit 1
        """,
        user_id,
    )


async def set_account_status(conn: asyncpg.Connection, user_id: str, status: str) -> bool:
    result = await conn.execute(
        """
        update accounts set status = $2,
            suspended_at = case when $2 = 'suspended' then now() else null end
        where id = $1 and status <> 'deleted'
        """,
        user_id,
        status,
    )
    return result.endswith(" 1")


async def delete_account(conn: asyncpg.Connection, user_id: str) -> int:
    """Delete all links and activity, and tombstone the account. Returns links deleted.

    The row stays with status 'deleted' so a still-valid token cannot recreate it.
    """
    async with conn.transaction():
        await conn.execute("delete from audit_events where owner_id = $1", user_id)
        n = await conn.fetchval(
            "with d as (delete from links where owner_id = $1 returning 1) select count(*) from d",
            user_id,
        )
        await conn.execute(
            "update accounts set status = 'deleted', deleted_at = now(), suspended_at = null"
            " where id = $1",
            user_id,
        )
    return n


# ---------------------------------------------------------------------------
# Links


async def insert_link(
    conn: asyncpg.Connection,
    *,
    link_id: str,
    owner_id: str,
    url: str,
    host: str,
    ttl_hours: int,
    max_clicks: int,
    passcode_hash: str | None,
) -> asyncpg.Record | None:
    """Insert and audit in one statement. Returns None on id collision."""
    return await conn.fetchrow(
        f"""
        with l as (
            insert into links (id, owner_id, original_url, destination_host, expires_at,
                               max_clicks, passcode_hash)
            values ($1, $2, $3, $4, now() + make_interval(hours => $5), $6, $7)
            on conflict (id) do nothing
            returning *
        ), ev as (
            insert into audit_events (link_id, owner_id, event_type, metadata)
            select id, owner_id, 'created',
                   jsonb_build_object('max_clicks', max_clicks, 'ttl_hours', $5::int,
                                      'passcode', passcode_hash is not null)
            from l
        )
        select {LINK_COLUMNS} from l
        """,
        link_id,
        owner_id,
        url,
        host,
        ttl_hours,
        max_clicks,
        passcode_hash,
    )


async def get_owned_link(
    conn: asyncpg.Connection, owner_id: str, link_id: str
) -> asyncpg.Record | None:
    # Ownership is part of the WHERE clause: another user's id is indistinguishable
    # from a missing one.
    return await conn.fetchrow(
        f"select {LINK_COLUMNS} from links l where l.id = $1 and l.owner_id = $2",
        link_id,
        owner_id,
    )


SORTS: dict[str, tuple[str, str]] = {
    # name: (column, direction)
    "created_desc": ("created_at", "desc"),
    "created_asc": ("created_at", "asc"),
    "expires_asc": ("expires_at", "asc"),
    "expires_desc": ("expires_at", "desc"),
}


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def list_links(
    conn: asyncpg.Connection,
    *,
    owner_id: str,
    status: LinkStatus | None,
    search: str | None,
    sort: str,
    limit: int,
    after: tuple[datetime, str] | None,
) -> list[asyncpg.Record]:
    """Keyset pagination on (sort column, id). Fetches limit + 1 to detect a next page."""
    column, direction = SORTS[sort]
    cmp = "<" if direction == "desc" else ">"
    where = ["l.owner_id = $1"]
    args: list[Any] = [owner_id]
    if status is not None:
        where.append(f"({STATUS_SQL[status]})")
    if search:
        args.append(f"%{_escape_like(search.lower())}%")
        args.append(search)
        where.append(f"(l.destination_host like ${len(args) - 1} or l.id = ${len(args)})")
    if after is not None:
        args.extend(after)
        where.append(f"(l.{column}, l.id) {cmp} (${len(args) - 1}, ${len(args)})")
    args.append(limit + 1)
    return await conn.fetch(
        f"""
        select {LINK_COLUMNS} from links l
        where {" and ".join(where)}
        order by l.{column} {direction}, l.id {direction}
        limit ${len(args)}
        """,
        *args,
    )


async def revoke_link(
    conn: asyncpg.Connection, link_id: str, *, owner_id: str | None, actor: str
) -> tuple[asyncpg.Record | None, bool]:
    """Idempotent revoke. Returns (link, changed). owner_id=None means operator action.

    Only the first revocation writes revoked_at and an audit event; repeats are no-ops.
    """
    row = await conn.fetchrow(
        """
        with target as (
            select id from links
            where id = $1 and ($2::uuid is null or owner_id = $2::uuid)
        ), upd as (
            update links l set revoked_at = now(), revoked_by = $3, updated_at = now()
            from target t
            where l.id = t.id and l.revoked_at is null
            returning l.id, l.owner_id
        ), ev as (
            insert into audit_events (link_id, owner_id, event_type, metadata)
            select id, owner_id, 'revoked', jsonb_build_object('by', $3::text) from upd
        )
        select (select count(*) from upd) as changed, (select count(*) from target) as found
        """,
        link_id,
        owner_id,
        actor,
    )
    if not row["found"]:
        return None, False
    # Re-read after the CTE committed so the response reflects the stored state.
    link = await conn.fetchrow(f"select {LINK_COLUMNS} from links l where l.id = $1", link_id)
    return link, bool(row["changed"])


async def link_events(conn: asyncpg.Connection, link_id: str, limit: int = 50):
    return await conn.fetch(
        """
        select event_type, created_at, metadata from audit_events
        where link_id = $1 order by created_at desc, id desc limit $2
        """,
        link_id,
        limit,
    )


# ---------------------------------------------------------------------------
# Resolver


async def reserve_visit(
    conn: asyncpg.Connection, link_id: str, *, allow_protected: bool
) -> str | None:
    """Atomically authorise one visit. Returns the destination, or None if refused.

    A single conditional UPDATE: Postgres row-locks the link, and concurrent updaters
    re-evaluate the WHERE clause against the committed row (READ COMMITTED
    EvalPlanQual), so `clicks < max_clicks` can never be passed by more requests than
    there are remaining visits. The visit audit row is written in the same statement.
    """
    return await conn.fetchval(
        """
        with r as (
            update links l
            set clicks = l.clicks + 1,
                updated_at = now(),
                exhausted_at = case when l.clicks + 1 >= l.max_clicks then now() end
            from accounts a
            where l.id = $1
              and a.id = l.owner_id and a.status = 'active'
              and l.revoked_at is null
              and l.expires_at > now()
              and l.clicks < l.max_clicks
              and ($2 or l.passcode_hash is null)
            returning l.id, l.owner_id, l.original_url
        ), ev as (
            insert into audit_events (link_id, owner_id, event_type)
            select id, owner_id, 'visit' from r
        )
        select original_url from r
        """,
        link_id,
        allow_protected,
    )


async def resolver_lookup(conn: asyncpg.Connection, link_id: str) -> asyncpg.Record | None:
    """Read-only state used to explain a refusal or to show the passcode form."""
    return await conn.fetchrow(
        """
        select l.expires_at, l.clicks, l.max_clicks, l.revoked_at, l.passcode_hash,
               a.status as owner_status, now() as db_now
        from links l join accounts a on a.id = l.owner_id
        where l.id = $1
        """,
        link_id,
    )


# ---------------------------------------------------------------------------
# Rate limiting


async def hit_rate_limit(conn: asyncpg.Connection, key: str, window_seconds: int) -> int:
    """Increment and return the counter for the current fixed window."""
    return await conn.fetchval(
        """
        insert into rate_limits (key, window_start, count)
        values ($1, to_timestamp(floor(extract(epoch from now()) / $2) * $2), 1)
        on conflict (key, window_start) do update set count = rate_limits.count + 1
        returning count
        """,
        key,
        window_seconds,
    )


# ---------------------------------------------------------------------------
# Abuse reports


async def insert_report(
    conn: asyncpg.Connection, link_id: str, reason: str, details: str | None, email: str | None
) -> int:
    return await conn.fetchval(
        """
        insert into abuse_reports (link_id, reason, details, reporter_email)
        values ($1, $2, $3, $4) returning id
        """,
        link_id,
        reason,
        details,
        email,
    )


async def list_reports(conn: asyncpg.Connection, status: str = "open", limit: int = 50):
    return await conn.fetch(
        """
        select r.id, r.link_id, r.reason, r.details, r.created_at, l.destination_host,
               l.owner_id
        from abuse_reports r left join links l on l.id = r.link_id
        where r.status = $1 order by r.created_at limit $2
        """,
        status,
        limit,
    )


async def resolve_report(conn: asyncpg.Connection, report_id: int, status: str) -> bool:
    result = await conn.execute(
        "update abuse_reports set status = $2, resolved_at = now() where id = $1",
        report_id,
        status,
    )
    return result.endswith(" 1")


# ---------------------------------------------------------------------------
# Cleanup


# Each statement deletes one bounded batch. SKIP LOCKED keeps concurrent cleanup runs
# (or a run racing a resolver) from blocking each other.
CLEANUP_STATEMENTS: dict[str, str] = {
    "revoked": """
        delete from links where id in (
            select id from links
            where revoked_at is not null and revoked_at < now() - make_interval(days => $1)
            limit $2 for update skip locked)
        """,
    "exhausted": """
        delete from links where id in (
            select id from links
            where revoked_at is null and exhausted_at is not null
              and exhausted_at < now() - make_interval(days => $1)
            limit $2 for update skip locked)
        """,
    "expired": """
        delete from links where id in (
            select id from links
            where revoked_at is null and clicks < max_clicks
              and expires_at < now() - make_interval(days => $1)
            limit $2 for update skip locked)
        """,
    "audit_events": """
        delete from audit_events where id in (
            select id from audit_events where created_at < now() - make_interval(days => $1)
            limit $2 for update skip locked)
        """,
}


async def delete_batch(conn: asyncpg.Connection, kind: str, days: int, batch: int) -> int:
    result = await conn.execute(CLEANUP_STATEMENTS[kind], days, batch)
    return int(result.split()[-1])


async def purge_rate_limits(conn: asyncpg.Connection) -> int:
    # The longest window is one day; anything older is dead weight (and hashed IPs).
    result = await conn.execute(
        "delete from rate_limits where window_start < now() - interval '2 days'"
    )
    return int(result.split()[-1])
