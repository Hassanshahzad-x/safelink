import asyncio
import uuid

import pytest
from conftest import client_for, create_link

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_redirect_then_exhausted(api_client, resolver_client, alice, pool):
    link = await create_link(api_client, alice, url="https://example.com/doc?x=1", max_clicks=2)
    for _ in range(2):
        r = await resolver_client.get(f"/r/{link['id']}")
        assert r.status_code == 302
        assert r.headers["location"] == "https://example.com/doc?x=1"
        assert r.headers["cache-control"] == "no-store"
        assert r.headers["referrer-policy"] == "no-referrer"
    r = await resolver_client.get(f"/r/{link['id']}")
    assert r.status_code == 410
    assert "This link has reached its visit limit." in r.text
    assert "example.com" not in r.text  # never leak the destination
    row = await pool.fetchrow("select clicks, exhausted_at from links where id=$1", link["id"])
    assert row["clicks"] == 2 and row["exhausted_at"] is not None
    visits = await pool.fetchval(
        "select count(*) from audit_events where link_id=$1 and event_type='visit'", link["id"]
    )
    assert visits == 2
    detail = (await api_client.get(f"/api/v1/links/{link['id']}", headers=alice.headers)).json()
    assert detail["status"] == "exhausted" and detail["remaining_clicks"] == 0


async def test_expired(api_client, resolver_client, alice, pool):
    link = await create_link(api_client, alice, max_clicks=5)
    await pool.execute(
        "update links set expires_at = now() - interval '1 second' where id=$1", link["id"]
    )
    r = await resolver_client.get(f"/r/{link['id']}")
    assert r.status_code == 410 and "This link has expired." in r.text
    assert await pool.fetchval("select clicks from links where id=$1", link["id"]) == 0


async def test_revoked(api_client, resolver_client, alice):
    link = await create_link(api_client, alice, max_clicks=5)
    await api_client.post(f"/api/v1/links/{link['id']}/revoke", headers=alice.headers)
    r = await resolver_client.get(f"/r/{link['id']}")
    assert r.status_code == 410 and "This link is no longer available." in r.text


async def test_unknown_and_malformed(resolver_client):
    for lid in ("A" * 22, "nope", "%3Cscript%3E"):
        r = await resolver_client.get(f"/r/{lid}")
        assert r.status_code == 404
        assert "<script>" not in r.text


async def test_suspended_owner(api_client, resolver_client, alice, pool):
    link = await create_link(api_client, alice, max_clicks=5)
    await pool.execute("update accounts set status='suspended' where id=$1", uuid.UUID(alice.id))
    r = await resolver_client.get(f"/r/{link['id']}")
    assert r.status_code == 410 and "This link is no longer available." in r.text
    assert await pool.fetchval("select clicks from links where id=$1", link["id"]) == 0


async def test_head_and_prefetch_do_not_consume(api_client, resolver_client, alice, pool):
    link = await create_link(api_client, alice)
    r = await resolver_client.head(f"/r/{link['id']}")
    assert r.status_code == 405
    assert await pool.fetchval("select clicks from links where id=$1", link["id"]) == 0


async def test_page_headers(resolver_client):
    r = await resolver_client.get("/r/" + "A" * 22)
    csp = r.headers["content-security-policy"]
    assert "default-src 'none'" in csp and "script-src" not in csp
    assert "frame-ancestors 'none'" in csp
    assert r.headers["x-robots-tag"] == "noindex"
    assert r.headers["content-type"].startswith("text/html")
    assert "<script" not in r.text


async def test_resolve_rate_limit(api_client, resolver_client, alice, override):
    override(rl_resolve_ip="3/60")
    link = await create_link(api_client, alice, max_clicks=10)
    codes = [(await resolver_client.get(f"/r/{link['id']}")).status_code for _ in range(4)]
    assert codes == [302, 302, 302, 429]
    r = await resolver_client.get(f"/r/{link['id']}")
    assert "Too many attempts" in r.text and r.headers["retry-after"]


# ---------------------------------------------------------------------------
# Concurrency: the core guarantee


@pytest.mark.parametrize(("max_clicks", "requests"), [(1, 50), (5, 60)])
async def test_concurrent_visits_never_exceed_limit(
    api_client, alice, pool, override, max_clicks, requests
):
    override(rl_resolve_ip="100000/60")
    link = await create_link(api_client, alice, max_clicks=max_clicks)
    # Independent clients so requests genuinely race on separate pool connections.
    from safelinks import resolver

    async def hit():
        async with client_for(resolver.app) as c:
            return (await c.get(f"/r/{link['id']}")).status_code

    codes = await asyncio.gather(*[hit() for _ in range(requests)])
    assert codes.count(302) == max_clicks
    assert codes.count(410) == requests - max_clicks
    assert await pool.fetchval("select clicks from links where id=$1", link["id"]) == max_clicks
    visits = await pool.fetchval(
        "select count(*) from audit_events where link_id=$1 and event_type='visit'", link["id"]
    )
    assert visits == max_clicks


async def test_db_check_constraint_backstop(api_client, alice, pool):
    import asyncpg

    link = await create_link(api_client, alice, max_clicks=1)
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute("update links set clicks = 2 where id=$1", link["id"])


# ---------------------------------------------------------------------------
# Passcode flow


async def test_passcode_flow(api_client, resolver_client, alice, pool):
    link = await create_link(
        api_client, alice, url="https://secret.example/", passcode="letmein", max_clicks=1
    )
    lid = link["id"]
    r = await resolver_client.get(f"/r/{lid}")
    assert r.status_code == 200
    assert 'name="passcode"' in r.text and f'action="/r/{lid}/verify"' in r.text
    assert "secret.example" not in r.text
    assert await pool.fetchval("select clicks from links where id=$1", lid) == 0

    form = {"content-type": "application/x-www-form-urlencoded"}
    r = await resolver_client.post(f"/r/{lid}/verify", content="passcode=wrong", headers=form)
    assert r.status_code == 403 and "Incorrect passcode." in r.text
    assert await pool.fetchval("select clicks from links where id=$1", lid) == 0

    r = await resolver_client.post(f"/r/{lid}/verify", content="passcode=letmein", headers=form)
    assert r.status_code == 303 and r.headers["location"] == "https://secret.example/"
    assert await pool.fetchval("select clicks from links where id=$1", lid) == 1

    # Correct passcode cannot exceed the limit.
    r = await resolver_client.post(f"/r/{lid}/verify", content="passcode=letmein", headers=form)
    assert r.status_code == 410 and "visit limit" in r.text


async def test_passcode_unknown_link_looks_like_wrong_passcode(resolver_client):
    form = {"content-type": "application/x-www-form-urlencoded"}
    r = await resolver_client.post("/r/" + "A" * 22 + "/verify", content="passcode=x", headers=form)
    assert r.status_code == 403 and "Incorrect passcode." in r.text


async def test_passcode_on_unprotected_link_rejected(api_client, resolver_client, alice, pool):
    link = await create_link(api_client, alice)
    form = {"content-type": "application/x-www-form-urlencoded"}
    r = await resolver_client.post(f"/r/{link['id']}/verify", content="passcode=", headers=form)
    assert r.status_code == 403
    assert await pool.fetchval("select clicks from links where id=$1", link["id"]) == 0


async def test_passcode_throttle(api_client, resolver_client, alice, override):
    override(rl_passcode_link="3/900")
    link = await create_link(api_client, alice, passcode="letmein")
    form = {"content-type": "application/x-www-form-urlencoded"}
    codes = [
        (
            await resolver_client.post(
                f"/r/{link['id']}/verify", content="passcode=nope", headers=form
            )
        ).status_code
        for _ in range(4)
    ]
    assert codes == [403, 403, 403, 429]
    # Even the right passcode is refused while throttled.
    r = await resolver_client.post(
        f"/r/{link['id']}/verify", content="passcode=letmein", headers=form
    )
    assert r.status_code == 429


async def test_passcode_page_escapes(resolver_client):
    lid = "A" * 20 + "<>"
    r = await resolver_client.post(
        f"/r/{lid}/verify",
        content="passcode=x",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert "&lt;&gt;" in r.text
    assert lid not in r.text


async def test_head_does_not_count_a_visit(api_client, resolver_client, alice, pool):
    # Link previewers often send HEAD; it must never burn a visit.
    link = await create_link(api_client, alice, max_clicks=1)
    r = await resolver_client.head(f"/r/{link['id']}")
    assert r.status_code == 405
    assert await pool.fetchval("select clicks from links where id=$1", link["id"]) == 0
