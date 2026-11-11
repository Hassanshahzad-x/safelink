"""Owner API: create, list, inspect and revoke links; account; abuse reports.

Run: uvicorn safelinks.api:app
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import logging
from datetime import datetime
from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from . import repository as repo
from .auth import Principal, current_user
from .config import settings
from .domain import (
    AppError,
    LinkStatus,
    bad_request,
    derive_status,
    hash_passcode,
    looks_like_link_id,
    new_link_id,
    validate_passcode,
    validate_policy,
    validate_url,
)
from .http import client_ip, create_app, enforce_limit, ip_hash
from .logs import event

log = logging.getLogger("safelinks.api")

app = create_app("api", require_auth=True, cors=True)


async def api_ip_limit(request: Request) -> None:
    async with request.app.state.pool.acquire() as conn:
        await enforce_limit(conn, f"api:ip:{ip_hash(client_ip(request))}", settings.rl_api_ip)


router = APIRouter(prefix="/api/v1", dependencies=[Depends(api_ip_limit)])
User = Annotated[Principal, Depends(current_user)]

_LINK_NOT_FOUND = AppError(404, "LINK_NOT_FOUND", "Link not found.")


def short_url(link_id: str) -> str:
    return f"{settings.resolver_base_url.rstrip('/')}/r/{link_id}"


def link_out(r) -> dict:
    status = derive_status(
        now=r["db_now"],
        expires_at=r["expires_at"],
        clicks=r["clicks"],
        max_clicks=r["max_clicks"],
        revoked_at=r["revoked_at"],
    )
    return {
        "id": r["id"],
        "short_url": short_url(r["id"]),
        "url": r["original_url"],
        "destination_host": r["destination_host"],
        "created_at": r["created_at"],
        "expires_at": r["expires_at"],
        "max_clicks": r["max_clicks"],
        "clicks": r["clicks"],
        "remaining_clicks": r["max_clicks"] - r["clicks"] if status == LinkStatus.ACTIVE else 0,
        "status": status,
        "revoked_at": r["revoked_at"],
        "passcode_protected": r["passcode_protected"],
    }


# ---------------------------------------------------------------------------
# Account


@router.get("/me")
async def me(user: User):
    return {
        "id": user.user_id,
        "email": user.email,
        "status": user.status,
        "limits": {
            "max_ttl_hours": settings.max_ttl_hours,
            "max_clicks": settings.max_clicks_limit,
        },
    }


@router.delete("/account", status_code=204)
async def delete_account(request: Request, user: User):
    async with request.app.state.pool.acquire() as conn:
        deleted = await repo.delete_account(conn, user.user_id)
    event("account_deleted", links_deleted=deleted)
    if settings.supabase_auth_url and settings.supabase_service_role_key:
        key = settings.supabase_service_role_key
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.delete(
                    f"{settings.supabase_auth_url.rstrip('/')}/admin/users/{user.user_id}",
                    headers={"apikey": key, "authorization": f"Bearer {key}"},
                )
            if resp.status_code not in (200, 204, 404):
                raise RuntimeError(f"auth admin returned {resp.status_code}")
        except Exception as exc:
            # Data is already gone; the sign-in identity remains. Retrying is safe.
            log.error("auth user deletion failed", extra={"fields": {"error": str(exc)}})
            raise AppError(
                502,
                "AUTH_DELETE_FAILED",
                "Your links were deleted, but your sign-in could not be removed. Try again.",
            ) from None
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Links


class CreateLinkIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(max_length=4096)
    ttl_hours: StrictInt
    max_clicks: StrictInt
    passcode: str | None = Field(default=None, max_length=1024)


@router.post("/links", status_code=201)
async def create_link(body: CreateLinkIn, request: Request, user: User):
    if user.status != "active":
        raise AppError(403, "ACCOUNT_SUSPENDED", "This account cannot create links.")
    async with request.app.state.pool.acquire() as conn:
        await enforce_limit(conn, f"create:ip:{ip_hash(client_ip(request))}", settings.rl_create_ip)
        await enforce_limit(conn, f"create:user:{user.user_id}", settings.rl_create_user)
        await enforce_limit(
            conn,
            f"create_daily:user:{user.user_id}",
            settings.rl_create_user_daily,
            "Daily link limit reached. Try again tomorrow.",
        )
    dest = validate_url(body.url, settings.max_url_length)
    validate_policy(
        body.ttl_hours,
        body.max_clicks,
        max_ttl=settings.max_ttl_hours,
        max_clicks_limit=settings.max_clicks_limit,
    )
    passcode = validate_passcode(body.passcode)
    # Argon2 is deliberately slow and CPU-bound; keep it off the event loop.
    passcode_hash = await asyncio.to_thread(hash_passcode, passcode) if passcode else None

    async with request.app.state.pool.acquire() as conn:
        for _ in range(5):
            row = await repo.insert_link(
                conn,
                link_id=new_link_id(),
                owner_id=user.user_id,
                url=dest.url,
                host=dest.host,
                ttl_hours=body.ttl_hours,
                max_clicks=body.max_clicks,
                passcode_hash=passcode_hash,
            )
            if row is not None:
                break
            event("link_id_collision", logging.WARNING)
        else:
            raise AppError(500, "INTERNAL_ERROR", "Could not create the link. Try again.")
    event(
        "link_created",
        max_clicks=body.max_clicks,
        ttl_hours=body.ttl_hours,
        passcode=passcode_hash is not None,
    )
    return link_out(row)


def _encode_cursor(value: datetime, link_id: str) -> str:
    raw = json.dumps([value.isoformat(), link_id]).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        value, link_id = json.loads(base64.urlsafe_b64decode(padded))
        return datetime.fromisoformat(value), str(link_id)
    except (ValueError, TypeError, binascii.Error):
        raise bad_request("INVALID_CURSOR", "The cursor is invalid.") from None


@router.get("/links")
async def list_links(
    request: Request,
    user: User,
    status: LinkStatus | None = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    sort: Literal["created_desc", "created_asc", "expires_asc", "expires_desc"] = "created_desc",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query(max_length=500)] = None,
):
    after = _decode_cursor(cursor) if cursor else None
    async with request.app.state.pool.acquire() as conn:
        rows = await repo.list_links(
            conn,
            owner_id=user.user_id,
            status=status,
            search=(search or "").strip() or None,
            sort=sort,
            limit=limit,
            after=after,
        )
    page = rows[:limit]
    column = repo.SORTS[sort][0]
    next_cursor = _encode_cursor(page[-1][column], page[-1]["id"]) if len(rows) > limit else None
    return {"items": [link_out(r) for r in page], "next_cursor": next_cursor}


@router.get("/links/{link_id}")
async def get_link(link_id: str, request: Request, user: User):
    if not looks_like_link_id(link_id):
        raise _LINK_NOT_FOUND
    async with request.app.state.pool.acquire() as conn:
        row = await repo.get_owned_link(conn, user.user_id, link_id)
        if row is None:
            raise _LINK_NOT_FOUND
        events = await repo.link_events(conn, link_id)
    return {
        **link_out(row),
        "events": [
            {"type": e["event_type"], "at": e["created_at"], "metadata": json.loads(e["metadata"])}
            for e in events
        ],
    }


@router.post("/links/{link_id}/revoke")
async def revoke(link_id: str, request: Request, user: User):
    if not looks_like_link_id(link_id):
        raise _LINK_NOT_FOUND
    async with request.app.state.pool.acquire() as conn:
        row, changed = await repo.revoke_link(conn, link_id, owner_id=user.user_id, actor="owner")
    if row is None:
        raise _LINK_NOT_FOUND
    if changed:
        event("link_revoked", by="owner")
    return link_out(row)


# ---------------------------------------------------------------------------
# Abuse reports (public)


class ReportIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    link: str = Field(min_length=1, max_length=2048)
    reason: Literal["phishing", "malware", "spam", "illegal", "other"]
    details: str | None = Field(default=None, max_length=2000)
    email: str | None = Field(default=None, max_length=320)


@router.post("/reports", status_code=202)
async def report_link(body: ReportIn, request: Request):
    # Accept a bare id or a full short URL.
    link_id = body.link.strip().rstrip("/").rsplit("/", 1)[-1]
    if not looks_like_link_id(link_id):
        raise bad_request("INVALID_LINK", "Enter a SafeLinks short URL or link ID.")
    async with request.app.state.pool.acquire() as conn:
        await enforce_limit(conn, f"report:ip:{ip_hash(client_ip(request))}", settings.rl_report_ip)
        await repo.insert_report(
            conn, link_id, body.reason, body.details or None, (body.email or "").strip() or None
        )
    event("abuse_report", reason=body.reason)
    # Same response whether or not the link exists.
    return {"status": "received"}


app.include_router(router)
