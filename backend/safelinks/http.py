"""Shared ASGI plumbing: app factory, middleware, error mapping, health checks, client IP."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.datastructures import MutableHeaders
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import repository as repo
from .config import parse_limit, settings
from .db import create_pool
from .domain import AppError
from .logs import configure_logging, event, request_id_var

log = logging.getLogger("safelinks.http")

# Errors that mean "the database is unreachable or overloaded", as opposed to a bug.
# These fail closed with 503 so callers can retry; nothing is ever redirected.
DB_UNAVAILABLE = (
    OSError,
    TimeoutError,
    asyncpg.InterfaceError,
    asyncpg.exceptions.PostgresConnectionError,
    asyncpg.exceptions.CannotConnectNowError,
    asyncpg.exceptions.InsufficientResourcesError,
    asyncpg.exceptions.QueryCanceledError,
)

ErrorRenderer = Callable[[int, str, str], Response]

BASE_SECURITY_HEADERS = {
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "x-frame-options": "DENY",
    "cache-control": "no-store",
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
    "cross-origin-opener-policy": "same-origin",
    "permissions-policy": "camera=(), microphone=(), geolocation=()",
}

_RID_OK = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


def json_error(status: int, code: str, message: str) -> Response:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


def client_ip(request: Request) -> str:
    """The socket peer, or the Nth-from-last X-Forwarded-For entry when N trusted proxies
    sit in front (entries further left are client-controlled and spoofable)."""
    hops = settings.trusted_proxy_hops
    if hops > 0:
        parts = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",")]
        parts = [p for p in parts if p]
        if len(parts) >= hops:
            return parts[-hops]
    return request.client.host if request.client else "unknown"


def ip_hash(ip: str) -> str:
    return hashlib.sha256(f"{settings.rate_limit_salt}:{ip}".encode()).hexdigest()[:32]


async def enforce_limit(conn, key: str, spec: str, message: str | None = None) -> None:
    """Fixed-window counter shared by every instance through Postgres."""
    limit, window = parse_limit(spec)
    count = await repo.hit_rate_limit(conn, key, window)
    if count > limit:
        event("rate_limited", logging.WARNING, scope=key.split(":", 1)[0])
        retry = max(1, window - int(time.time()) % window)
        raise AppError(429, "RATE_LIMITED", message or "Too many requests. Try again later.", retry)


class Middleware:
    """Pure ASGI (no BaseHTTPMiddleware) so streaming and contextvars behave.

    Request ids, one access log line per request, security headers, body size limit, and a
    last-resort 500 that never leaks internals.
    """

    def __init__(self, app, render_error: ErrorRenderer):
        self.app = app
        self.render_error = render_error

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope["headers"])
        incoming = headers.get(b"x-request-id", b"").decode("latin-1")
        rid = incoming if _RID_OK.match(incoming) else uuid.uuid4().hex
        token = request_id_var.set(rid)
        start = time.perf_counter()
        state = {"status": 500, "started": False}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                state["status"] = message["status"]
                state["started"] = True
                h = MutableHeaders(scope=message)
                for k, v in BASE_SECURITY_HEADERS.items():
                    if k not in h:
                        h[k] = v
                if settings.is_production:
                    h["strict-transport-security"] = "max-age=63072000; includeSubDomains"
                h["x-request-id"] = rid
            await send(message)

        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > settings.max_body_bytes:
                    raise StarletteHTTPException(413)
            return message

        try:
            length = headers.get(b"content-length")
            if length is not None and (
                not length.isdigit() or int(length) > settings.max_body_bytes
            ):
                resp = self.render_error(413, "PAYLOAD_TOO_LARGE", "Request body too large.")
                await resp(scope, receive, send_wrapper)
            else:
                await self.app(scope, limited_receive, send_wrapper)
        except Exception:
            log.exception("unhandled error")
            if not state["started"]:
                resp = self.render_error(500, "INTERNAL_ERROR", "Something went wrong.")
                await resp(scope, receive, send_wrapper)
        finally:
            route = scope.get("route")
            # Log the route template, never the raw path: link ids are bearer capabilities.
            log.info(
                "request",
                extra={
                    "fields": {
                        "event": "http_request",
                        "method": scope["method"],
                        "route": getattr(route, "path", "unmatched"),
                        "status": state["status"],
                        "latency_ms": round((time.perf_counter() - start) * 1000, 1),
                    }
                },
            )
            request_id_var.reset(token)


def create_app(
    service: str,
    *,
    require_auth: bool = False,
    cors: bool = False,
    render_error: ErrorRenderer = json_error,
) -> FastAPI:
    configure_logging(service)
    settings.validate(require_auth=require_auth)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.pool = await create_pool()
        try:
            yield
        finally:
            await app.state.pool.close()

    app = FastAPI(
        title=f"SafeLinks {service}",
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )

    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        resp = render_error(exc.status, exc.code, exc.message)
        if exc.retry_after:
            resp.headers["retry-after"] = str(exc.retry_after)
        return resp

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(p) for p in first.get("loc", ())[1:]) or "request"
        return render_error(400, "INVALID_REQUEST", f"{field}: {first.get('msg', 'invalid')}")

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        codes = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 413: "PAYLOAD_TOO_LARGE"}
        messages = {404: "Not found.", 405: "Method not allowed.", 413: "Request body too large."}
        return render_error(
            exc.status_code,
            codes.get(exc.status_code, "HTTP_ERROR"),
            messages.get(exc.status_code, "Request failed."),
        )

    for exc_type in DB_UNAVAILABLE:

        @app.exception_handler(exc_type)
        async def _db_down(request: Request, exc: Exception):
            event("db_unavailable", logging.ERROR, error=type(exc).__name__)
            return render_error(
                503, "SERVICE_UNAVAILABLE", "Service temporarily unavailable. Try again shortly."
            )

    @app.get("/healthz", include_in_schema=False)
    async def healthz():
        return {"status": "ok"}

    @app.get("/readyz", include_in_schema=False)
    async def readyz(request: Request):
        try:
            async with asyncio.timeout(2):
                await request.app.state.pool.fetchval("select 1")
        except Exception:
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return {"status": "ok"}

    if cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["authorization", "content-type", "x-request-id"],
            expose_headers=["x-request-id", "retry-after"],
            max_age=600,
        )
    app.add_middleware(Middleware, render_error=render_error)
    return app
