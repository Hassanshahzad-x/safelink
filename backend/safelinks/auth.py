"""Supabase Auth access-token verification.

Tokens arrive as `Authorization: Bearer <jwt>` (never cookies, so CSRF does not apply).
HS256 with SUPABASE_JWT_SECRET (local GoTrue / legacy projects) or asymmetric keys from
SUPABASE_JWKS_URL (current Supabase projects).
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

import jwt
from fastapi import Request

from . import repository as repo
from .config import settings
from .domain import AppError

_jwks: jwt.PyJWKClient | None = None


def _unauthorized() -> AppError:
    return AppError(401, "UNAUTHORIZED", "Sign in to continue.")


@dataclass(frozen=True)
class Principal:
    user_id: str
    email: str | None
    status: str


def _signing_key(token: str):
    global _jwks
    if settings.supabase_jwt_secret:
        return settings.supabase_jwt_secret, ["HS256"]
    if _jwks is None:
        _jwks = jwt.PyJWKClient(settings.supabase_jwks_url, cache_keys=True, lifespan=600)
    return _jwks.get_signing_key_from_jwt(token).key, ["RS256", "ES256"]


async def verify_token(token: str) -> dict:
    try:
        # JWKS fetch is blocking network I/O (cached); keep it off the event loop.
        key, algorithms = await asyncio.to_thread(_signing_key, token)
        claims = jwt.decode(
            token,
            key,
            algorithms=algorithms,
            audience=settings.supabase_jwt_audience,
            issuer=settings.supabase_jwt_issuer or None,
            options={"require": ["exp", "sub", "aud"]},
            leeway=30,
        )
        uuid.UUID(claims["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise _unauthorized() from None
    return claims


async def current_user(request: Request) -> Principal:
    """FastAPI dependency: a signed-in user whose account has not been deleted."""
    user = await current_user_any_status(request)
    if user.status == "deleted":
        raise _unauthorized()
    return user


async def current_user_any_status(request: Request) -> Principal:
    """Verify the bearer token and make sure an account row exists. Only account
    deletion uses this directly, so a failed deletion can be retried."""
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _unauthorized()
    claims = await verify_token(token.strip())
    async with request.app.state.pool.acquire() as conn:
        account = await repo.ensure_account(conn, claims["sub"])
    return Principal(user_id=claims["sub"], email=claims.get("email"), status=account["status"])
