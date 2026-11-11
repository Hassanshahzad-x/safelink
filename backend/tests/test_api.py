import asyncio
import uuid

import pytest
from conftest import User, create_link, make_token

pytestmark = pytest.mark.asyncio(loop_scope="session")


# ---------------------------------------------------------------------------
# Auth


async def test_requires_auth(api_client):
    for method, path in [
        ("GET", "/api/v1/links"),
        ("POST", "/api/v1/links"),
        ("GET", "/api/v1/me"),
        ("DELETE", "/api/v1/account"),
    ]:
        r = await api_client.request(method, path)
        assert r.status_code == 401, path
        assert r.json() == {"error": {"code": "UNAUTHORIZED", "message": "Sign in to continue."}}


@pytest.mark.parametrize(
    "token",
    [
        make_token(secret="wrong-secret-wrong-secret-wrong-secret!"),
        make_token(exp=1),
        make_token(aud="anon"),
        make_token(sub="not-a-uuid"),
        make_token(sub=None),
        make_token(exp=None),
        "garbage",
    ],
)
async def test_rejects_bad_tokens(api_client, token):
    r = await api_client.get("/api/v1/me", headers={"authorization": f"Bearer {token}"})
    assert r.status_code == 401


async def test_alg_none_rejected(api_client):
    import jwt

    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "aud": "authenticated", "exp": 9999999999},
        None,
        algorithm="none",
    )
    r = await api_client.get("/api/v1/me", headers={"authorization": f"Bearer {token}"})
    assert r.status_code == 401


async def test_me_creates_account(api_client, alice, pool):
    r = await api_client.get("/api/v1/me", headers=alice.headers)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == alice.id and body["status"] == "active"
    assert body["limits"] == {"max_ttl_hours": 720, "max_clicks": 1000}
    assert await pool.fetchval("select count(*) from accounts where id = $1", uuid.UUID(alice.id))


# ---------------------------------------------------------------------------
# Create


async def test_create_link(api_client, alice, pool):
    link = await create_link(
        api_client, alice, url="https://Example.com/a", ttl_hours=24, max_clicks=3
    )
    assert link["short_url"] == f"https://sl.test/r/{link['id']}"
    assert link["url"] == "https://Example.com/a"
    assert link["destination_host"] == "example.com"
    assert link["status"] == "active"
    assert link["clicks"] == 0 and link["remaining_clicks"] == 3
    assert link["passcode_protected"] is False
    assert "passcode_hash" not in link
    events = await pool.fetch("select event_type from audit_events where link_id = $1", link["id"])
    assert [e["event_type"] for e in events] == ["created"]


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"url": "javascript:alert(1)", "ttl_hours": 1, "max_clicks": 1}, "INVALID_URL"),
        ({"url": "https://x.com", "ttl_hours": 0, "max_clicks": 1}, "INVALID_TTL"),
        ({"url": "https://x.com", "ttl_hours": 721, "max_clicks": 1}, "INVALID_TTL"),
        ({"url": "https://x.com", "ttl_hours": 1, "max_clicks": 0}, "INVALID_MAX_CLICKS"),
        ({"url": "https://x.com", "ttl_hours": 1, "max_clicks": 1001}, "INVALID_MAX_CLICKS"),
        (
            {"url": "https://x.com", "ttl_hours": 1, "max_clicks": 1, "passcode": "abc"},
            "INVALID_PASSCODE",
        ),
        ({"url": "https://x.com", "ttl_hours": "1", "max_clicks": 1}, "INVALID_REQUEST"),
        ({"url": "https://x.com", "ttl_hours": 1.5, "max_clicks": 1}, "INVALID_REQUEST"),
        ({"url": "https://x.com", "ttl_hours": 1}, "INVALID_REQUEST"),
        (
            {"url": "https://x.com", "ttl_hours": 1, "max_clicks": 1, "owner_id": "x"},
            "INVALID_REQUEST",
        ),
    ],
)
async def test_create_validation(api_client, alice, body, code):
    r = await api_client.post("/api/v1/links", json=body, headers=alice.headers)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == code


async def test_create_malformed_json(api_client, alice):
    r = await api_client.post(
        "/api/v1/links",
        content=b"{not json",
        headers={**alice.headers, "content-type": "application/json"},
    )
    assert r.status_code == 400


async def test_passcode_never_returned_or_stored_plain(api_client, alice, pool):
    link = await create_link(api_client, alice, passcode="hunter22")
    assert link["passcode_protected"] is True
    stored = await pool.fetchval("select passcode_hash from links where id = $1", link["id"])
    assert stored.startswith("$argon2id$") and "hunter22" not in stored
    detail = (await api_client.get(f"/api/v1/links/{link['id']}", headers=alice.headers)).text
    assert "hunter22" not in detail and "argon2" not in detail


async def test_suspended_account_cannot_create(api_client, alice, pool):
    await api_client.get("/api/v1/me", headers=alice.headers)
    await pool.execute("update accounts set status='suspended' where id=$1", uuid.UUID(alice.id))
    r = await api_client.post(
        "/api/v1/links",
        headers=alice.headers,
        json={"url": "https://x.com", "ttl_hours": 1, "max_clicks": 1},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "ACCOUNT_SUSPENDED"


async def test_create_rate_limit(api_client, alice, override):
    override(rl_create_user="2/60")
    await create_link(api_client, alice)
    await create_link(api_client, alice)
    r = await api_client.post(
        "/api/v1/links",
        headers=alice.headers,
        json={"url": "https://x.com", "ttl_hours": 1, "max_clicks": 1},
    )
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "RATE_LIMITED"
    assert int(r.headers["retry-after"]) >= 1
    # Another user is unaffected by alice's per-user limit.
    await create_link(api_client, User())


# ---------------------------------------------------------------------------
# Read, list, ownership


async def test_ownership_isolation(api_client, alice, bob):
    link = await create_link(api_client, alice)
    for method, path in [
        ("GET", f"/api/v1/links/{link['id']}"),
        ("POST", f"/api/v1/links/{link['id']}/revoke"),
    ]:
        r = await api_client.request(method, path, headers=bob.headers)
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "LINK_NOT_FOUND"
    r = await api_client.get("/api/v1/links", headers=bob.headers)
    assert r.json()["items"] == []
    # Still active for alice: bob's revoke attempt did nothing.
    r = await api_client.get(f"/api/v1/links/{link['id']}", headers=alice.headers)
    assert r.json()["status"] == "active"


async def test_unknown_and_malformed_ids_are_404(api_client, alice):
    for lid in ("A" * 22, "bad", "x" * 70):
        r = await api_client.get(f"/api/v1/links/{lid}", headers=alice.headers)
        assert r.status_code == 404


async def test_list_status_filter_search_sort_paginate(api_client, alice, pool):
    a = await create_link(api_client, alice, url="https://alpha.example/1", ttl_hours=5)
    b = await create_link(api_client, alice, url="https://beta.example/2", ttl_hours=1)
    c = await create_link(api_client, alice, url="https://gamma.example/3", ttl_hours=10)
    d = await create_link(api_client, alice, url="https://delta.example/4", ttl_hours=3)
    await pool.execute(
        "update links set expires_at = now() - interval '1 minute' where id=$1", b["id"]
    )
    await pool.execute(
        "update links set clicks = max_clicks, exhausted_at = now() where id=$1", c["id"]
    )
    await api_client.post(f"/api/v1/links/{d['id']}/revoke", headers=alice.headers)

    async def ids(**params):
        r = await api_client.get("/api/v1/links", params=params, headers=alice.headers)
        assert r.status_code == 200, r.text
        return [i["id"] for i in r.json()["items"]]

    assert await ids() == [d["id"], c["id"], b["id"], a["id"]]
    assert await ids(sort="created_asc") == [a["id"], b["id"], c["id"], d["id"]]
    assert await ids(sort="expires_asc") == [b["id"], d["id"], a["id"], c["id"]]
    assert await ids(status="active") == [a["id"]]
    assert await ids(status="expired") == [b["id"]]
    assert await ids(status="exhausted") == [c["id"]]
    assert await ids(status="revoked") == [d["id"]]
    assert await ids(search="GAMMA") == [c["id"]]
    assert await ids(search=a["id"]) == [a["id"]]
    assert await ids(search="%") == []  # LIKE wildcards are escaped
    assert await ids(search="_") == []

    seen, cursor = [], None
    while True:
        params = {"limit": 3, "sort": "expires_desc"}
        if cursor:
            params["cursor"] = cursor
        r = (await api_client.get("/api/v1/links", params=params, headers=alice.headers)).json()
        seen += [i["id"] for i in r["items"]]
        cursor = r["next_cursor"]
        if not cursor:
            break
    assert seen == [c["id"], a["id"], d["id"], b["id"]]


async def test_list_pagination_with_identical_timestamps(api_client, alice, pool):
    for _ in range(7):
        await create_link(api_client, alice)
    await pool.execute("update links set created_at = '2026-01-01T00:00:00Z'")
    seen, cursor = [], None
    for _ in range(10):
        params = {"limit": 2, **({"cursor": cursor} if cursor else {})}
        r = (await api_client.get("/api/v1/links", params=params, headers=alice.headers)).json()
        seen += [i["id"] for i in r["items"]]
        cursor = r["next_cursor"]
        if not cursor:
            break
    assert len(seen) == 7 and len(set(seen)) == 7


@pytest.mark.parametrize(
    "params",
    [
        {"cursor": "!!!"},
        {"cursor": "bm90IGpzb24"},
        {"limit": 0},
        {"limit": 101},
        {"status": "deleted"},
        {"sort": "random"},
    ],
)
async def test_list_bad_params(api_client, alice, params):
    r = await api_client.get("/api/v1/links", params=params, headers=alice.headers)
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Revoke


async def test_revoke_idempotent(api_client, alice, pool):
    link = await create_link(api_client, alice)
    r1 = await api_client.post(f"/api/v1/links/{link['id']}/revoke", headers=alice.headers)
    r2 = await api_client.post(f"/api/v1/links/{link['id']}/revoke", headers=alice.headers)
    assert r1.status_code == r2.status_code == 200
    assert r1.json()["status"] == "revoked" and r1.json()["revoked_at"]
    assert r1.json()["revoked_at"] == r2.json()["revoked_at"]
    assert r1.json()["remaining_clicks"] == 0
    n = await pool.fetchval(
        "select count(*) from audit_events where link_id=$1 and event_type='revoked'", link["id"]
    )
    assert n == 1
    detail = (await api_client.get(f"/api/v1/links/{link['id']}", headers=alice.headers)).json()
    assert [e["type"] for e in detail["events"]] == ["revoked", "created"]
    assert detail["events"][0]["metadata"] == {"by": "owner"}


async def test_concurrent_revokes_write_one_event(api_client, alice, pool):
    link = await create_link(api_client, alice)
    rs = await asyncio.gather(
        *[
            api_client.post(f"/api/v1/links/{link['id']}/revoke", headers=alice.headers)
            for _ in range(10)
        ]
    )
    assert {r.status_code for r in rs} == {200}
    n = await pool.fetchval(
        "select count(*) from audit_events where link_id=$1 and event_type='revoked'", link["id"]
    )
    assert n == 1


# ---------------------------------------------------------------------------
# Account deletion


async def test_delete_account(api_client, alice, bob, pool):
    mine = await create_link(api_client, alice)
    theirs = await create_link(api_client, bob)
    r = await api_client.delete("/api/v1/account", headers=alice.headers)
    assert r.status_code == 204
    assert await pool.fetchval("select count(*) from links where id=$1", mine["id"]) == 0
    assert (
        await pool.fetchval(
            "select count(*) from audit_events where owner_id=$1", uuid.UUID(alice.id)
        )
        == 0
    )
    assert await pool.fetchval("select count(*) from links where id=$1", theirs["id"]) == 1


async def test_delete_account_calls_auth_admin(api_client, alice, override, monkeypatch):
    import httpx

    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        return httpx.Response(500)

    real = httpx.AsyncClient
    monkeypatch.setattr(
        "safelinks.api.httpx.AsyncClient",
        lambda **kw: real(transport=httpx.MockTransport(handler), **kw),
    )
    override(supabase_auth_url="http://auth.test", supabase_service_role_key="svc-key")
    r = await api_client.delete("/api/v1/account", headers=alice.headers)
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "AUTH_DELETE_FAILED"
    assert calls[0].method == "DELETE"
    assert str(calls[0].url) == f"http://auth.test/admin/users/{alice.id}"
    assert calls[0].headers["authorization"] == "Bearer svc-key"


# ---------------------------------------------------------------------------
# Reports


async def test_report_accepts_short_url_and_id(api_client, alice, pool):
    link = await create_link(api_client, alice)
    for value in (link["short_url"], link["id"], "A" * 22):
        r = await api_client.post(
            "/api/v1/reports", json={"link": value, "reason": "phishing", "details": "bad"}
        )
        assert r.status_code == 202
        assert r.json() == {"status": "received"}
    assert await pool.fetchval("select count(*) from abuse_reports") == 3


async def test_report_validation_and_limit(api_client, override):
    r = await api_client.post("/api/v1/reports", json={"link": "nope", "reason": "spam"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "INVALID_LINK"
    r = await api_client.post("/api/v1/reports", json={"link": "A" * 22, "reason": "boring"})
    assert r.status_code == 400
    override(rl_report_ip="1/3600")
    assert (
        await api_client.post("/api/v1/reports", json={"link": "A" * 22, "reason": "spam"})
    ).status_code == 202
    assert (
        await api_client.post("/api/v1/reports", json={"link": "A" * 22, "reason": "spam"})
    ).status_code == 429


# ---------------------------------------------------------------------------
# Platform behaviour


async def test_health(api_client, pool):
    assert (await api_client.get("/healthz")).json() == {"status": "ok"}
    assert (await api_client.get("/readyz")).json() == {"status": "ok"}


async def test_security_headers_and_request_id(api_client):
    r = await api_client.get("/healthz", headers={"x-request-id": "abc12345"})
    assert r.headers["x-request-id"] == "abc12345"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["cache-control"] == "no-store"
    r = await api_client.get("/healthz", headers={"x-request-id": "bad id\n"})
    assert r.headers["x-request-id"] != "bad id\n" and len(r.headers["x-request-id"]) == 32


async def test_body_limit(api_client, alice):
    big = '{"url":"https://x.com/' + "a" * 20000 + '","ttl_hours":1,"max_clicks":1}'
    r = await api_client.post(
        "/api/v1/links", content=big, headers={**alice.headers, "content-type": "application/json"}
    )
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


async def test_cors(api_client):
    r = await api_client.options(
        "/api/v1/links",
        headers={
            "origin": "https://app.sl.test",
            "access-control-request-method": "POST",
            "access-control-request-headers": "authorization,content-type",
        },
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "https://app.sl.test"
    r = await api_client.options(
        "/api/v1/links",
        headers={"origin": "https://evil.test", "access-control-request-method": "POST"},
    )
    assert "access-control-allow-origin" not in r.headers


async def test_unknown_route_and_method(api_client):
    assert (await api_client.get("/nope")).json()["error"]["code"] == "NOT_FOUND"
    r = await api_client.put("/api/v1/links")
    assert r.status_code == 405 and r.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


async def test_db_down_returns_503(api_client, alice, monkeypatch):
    from safelinks import api

    class Down:
        def acquire(self):
            raise ConnectionRefusedError("db down")

        async def fetchval(self, *a, **k):
            raise ConnectionRefusedError("db down")

    real = api.app.state.pool
    api.app.state.pool = Down()
    try:
        r = await api_client.get("/api/v1/links", headers=alice.headers)
        assert r.status_code == 503
        assert r.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
        assert (await api_client.get("/readyz")).status_code == 503
    finally:
        api.app.state.pool = real
