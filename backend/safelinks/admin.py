"""Operator CLI. Uses DATABASE_URL directly; never exposed over HTTP.

python -m safelinks.admin suspend <user-uuid>
python -m safelinks.admin unsuspend <user-uuid>
python -m safelinks.admin revoke <link-id>
python -m safelinks.admin reports [--status open|actioned|dismissed]
python -m safelinks.admin resolve-report <report-id> actioned|dismissed
"""

from __future__ import annotations

import argparse
import asyncio
import json

import asyncpg

from . import repository as repo
from .config import settings
from .logs import configure_logging, event


async def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="safelinks.admin")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("suspend", "unsuspend"):
        sub.add_parser(name).add_argument("user_id")
    sub.add_parser("revoke").add_argument("link_id")
    rp = sub.add_parser("reports")
    rp.add_argument("--status", default="open", choices=["open", "actioned", "dismissed"])
    rr = sub.add_parser("resolve-report")
    rr.add_argument("report_id", type=int)
    rr.add_argument("status", choices=["actioned", "dismissed"])
    args = p.parse_args(argv)

    configure_logging("admin")
    conn = await asyncpg.connect(settings.database_url)
    try:
        if args.cmd in ("suspend", "unsuspend"):
            status = "suspended" if args.cmd == "suspend" else "active"
            ok = await repo.set_account_status(conn, args.user_id, status)
            event("account_status_changed", status=status, found=ok)
            print("ok" if ok else "account not found")
            return 0 if ok else 1
        if args.cmd == "revoke":
            row, changed = await repo.revoke_link(
                conn, args.link_id, owner_id=None, actor="operator"
            )
            if row is None:
                print("link not found")
                return 1
            event("link_revoked", by="operator", changed=changed)
            print("revoked" if changed else "already revoked")
            return 0
        if args.cmd == "reports":
            for r in await repo.list_reports(conn, args.status):
                print(json.dumps(dict(r), default=str))
            return 0
        ok = await repo.resolve_report(conn, args.report_id, args.status)
        print("ok" if ok else "report not found")
        return 0 if ok else 1
    finally:
        await conn.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
