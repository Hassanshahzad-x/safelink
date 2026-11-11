"""Integration tests run against a real Postgres (docker compose `db`, or CI service).

TEST_DATABASE_ADMIN_URL points at any database on that server; a fresh `safelinks_test`
database is created per session.
"""

from __future__ import annotations

import os
import time
import uuid

ADMIN_URL = os.environ.get(
    "TEST_DATABASE_ADMIN_URL", "postgresql://postgres:postgres@localhost:54329/postgres"
)
TEST_DB = "safelinks_test"
TEST_URL = ADMIN_URL.rsplit("/", 1)[0] + f"/{TEST_DB}"
JWT_SECRET = "test-jwt-secret-with-at-least-32-characters!!"

# Settings are read at import time, so configure the environment before importing the app.
os.environ.update(
    {
        "DATABASE_URL": TEST_URL,
        "SUPABASE_JWT_SECRET": JWT_SECRET,
        "RESOLVER_BASE_URL": "https://sl.test",
        "FRONTEND_URL": "https://app.sl.test",
        "CORS_ORIGINS": "https://app.sl.test",
        "CLEANUP_TOKEN": "test-cleanup-token",
        "DB_POOL_MAX": "20",
    }
)

import asyncpg  # noqa: E402
import httpx  # noqa: E402
import jwt  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402

from safelinks import api, remover, resolver  # noqa: E402
from safelinks.config import settings  # noqa: E402
from safelinks.db import create_pool, migrate  # noqa: E402


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def pool():
    admin = await asyncpg.connect(ADMIN_URL)
    try:
        await admin.execute(f"drop database if exists {TEST_DB} with (force)")
        await admin.execute(f"create database {TEST_DB}")
    finally:
        await admin.close()
    assert await migrate(TEST_URL) == ["001_init"]
    assert await migrate(TEST_URL) == []  # idempotent
    p = await create_pool(TEST_URL)
    for app in (api.app, resolver.app, remover.app):
        app.state.pool = p
    yield p
    await p.close()


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def clean(request):
    if "pool" not in request.fixturenames:
        yield
        return
    p = request.getfixturevalue("pool")
    await p.execute(
        "truncate accounts, links, audit_events, rate_limits, abuse_reports restart identity"
        " cascade"
    )
    yield


@pytest.fixture
def override():
    """Temporarily change frozen settings."""
    saved = {}

    def apply(**values):
        for k, v in values.items():
            saved.setdefault(k, getattr(settings, k))
            object.__setattr__(settings, k, v)

    yield apply
    for k, v in saved.items():
        object.__setattr__(settings, k, v)


def make_token(user_id: str | None = None, *, secret: str = JWT_SECRET, **claims) -> str:
    now = int(time.time())
    payload = {
        "sub": user_id or str(uuid.uuid4()),
        "aud": "authenticated",
        "role": "authenticated",
        "email": "user@example.com",
        "iat": now,
        "exp": now + 3600,
        **claims,
    }
    payload = {k: v for k, v in payload.items() if v is not None}  # claim=None drops it
    return jwt.encode(payload, secret, algorithm="HS256")


class User:
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.headers = {"authorization": f"Bearer {make_token(self.id)}"}


@pytest.fixture
def alice():
    return User()


@pytest.fixture
def bob():
    return User()


def client_for(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest_asyncio.fixture(loop_scope="session")
async def api_client(pool):
    async with client_for(api.app) as c:
        yield c


@pytest_asyncio.fixture(loop_scope="session")
async def resolver_client(pool):
    async with client_for(resolver.app) as c:
        yield c


@pytest_asyncio.fixture(loop_scope="session")
async def remover_client(pool):
    async with client_for(remover.app) as c:
        yield c


async def create_link(client, user, **body):
    payload = {"url": "https://example.com/report.pdf", "ttl_hours": 24, "max_clicks": 1}
    payload.update(body)
    r = await client.post("/api/v1/links", json=payload, headers=user.headers)
    assert r.status_code == 201, r.text
    return r.json()
