import asyncio

import pytest
from conftest import create_link

from safelinks.remover import run_cleanup

pytestmark = pytest.mark.asyncio(loop_scope="session")

AUTH = {"authorization": "Bearer test-cleanup-token"}


async def _seed(api_client, alice, pool):
    ids = {}
    for name in (
        "active",
        "fresh_expired",
        "old_expired",
        "old_exhausted",
        "old_revoked",
        "recent_revoked",
    ):
        ids[name] = (await create_link(api_client, alice, max_clicks=2))["id"]
    await pool.execute(
        "update links set expires_at = now() - interval '1 day' where id=$1", ids["fresh_expired"]
    )
    await pool.execute(
        "update links set expires_at = now() - interval '31 days' where id=$1", ids["old_expired"]
    )
    await pool.execute(
        "update links set clicks = 2, exhausted_at = now() - interval '31 days' where id=$1",
        ids["old_exhausted"],
    )
    await pool.execute(
        "update links set revoked_at = now() - interval '31 days' where id=$1", ids["old_revoked"]
    )
    await pool.execute(
        "update links set revoked_at = now() - interval '1 day' where id=$1", ids["recent_revoked"]
    )
    await pool.execute(
        "update audit_events set created_at = now() - interval '91 days' where link_id=$1",
        ids["active"],
    )
    await pool.execute(
        "insert into rate_limits values ('x', now() - interval '3 days', 1), ('y', now(), 1)"
    )
    return ids


async def test_cleanup_retention(api_client, alice, pool):
    ids = await _seed(api_client, alice, pool)
    result = await run_cleanup(pool)
    assert result["failed"] == 0
    assert result["deleted"] == {
        "revoked": 1,
        "exhausted": 1,
        "expired": 1,
        "audit_events": 1,
        "rate_limits": 1,
    }
    left = {r["id"] for r in await pool.fetch("select id from links")}
    assert left == {ids["active"], ids["fresh_expired"], ids["recent_revoked"]}
    # Idempotent: a second run deletes nothing.
    again = await run_cleanup(pool)
    assert set(again["deleted"].values()) == {0}


async def test_cleanup_batches_and_concurrency(api_client, alice, pool, override):
    override(
        cleanup_batch_size=3, rl_create_user="1000/60", rl_create_ip="1000/60", rl_api_ip="10000/60"
    )
    for _ in range(10):
        await create_link(api_client, alice)
    await pool.execute("update links set expires_at = now() - interval '40 days'")
    results = await asyncio.gather(run_cleanup(pool), run_cleanup(pool))
    assert sum(r["deleted"]["expired"] for r in results) == 10
    assert all(r["failed"] == 0 for r in results)
    assert await pool.fetchval("select count(*) from links") == 0


async def test_cleanup_endpoint_auth(remover_client, override):
    assert (await remover_client.post("/internal/cleanup")).status_code == 401
    r = await remover_client.post("/internal/cleanup", headers={"authorization": "Bearer nope"})
    assert r.status_code == 401
    r = await remover_client.post("/internal/cleanup", headers=AUTH)
    assert r.status_code == 200 and r.json()["failed"] == 0
    # Cloud Scheduler OIDC: Google ID token in Authorization, app token in X-Cleanup-Token.
    oidc = {"authorization": "Bearer google-id-token", "x-cleanup-token": "test-cleanup-token"}
    assert (await remover_client.post("/internal/cleanup", headers=oidc)).status_code == 200
    oidc["x-cleanup-token"] = "nope"
    assert (await remover_client.post("/internal/cleanup", headers=oidc)).status_code == 401
    override(cleanup_token="")
    assert (await remover_client.post("/internal/cleanup", headers=AUTH)).status_code == 401


async def test_admin_cli(api_client, alice, pool, capsys):
    from safelinks import admin

    link = await create_link(api_client, alice)
    assert await admin.main(["suspend", alice.id]) == 0
    assert await pool.fetchval("select status from accounts") == "suspended"
    assert await admin.main(["unsuspend", alice.id]) == 0
    assert await admin.main(["revoke", link["id"]]) == 0
    assert await admin.main(["revoke", link["id"]]) == 0
    assert "already revoked" in capsys.readouterr().out
    assert await pool.fetchval("select revoked_by from links") == "operator"
    await api_client.post("/api/v1/reports", json={"link": link["id"], "reason": "spam"})
    assert await admin.main(["reports"]) == 0
    assert link["id"] in capsys.readouterr().out
    rid = await pool.fetchval("select id from abuse_reports")
    assert await admin.main(["resolve-report", str(rid), "actioned"]) == 0
    assert await pool.fetchval("select status from abuse_reports") == "actioned"
