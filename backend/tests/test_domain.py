from datetime import UTC, datetime, timedelta

import pytest

from safelinks.domain import (
    AppError,
    LinkStatus,
    derive_status,
    hash_passcode,
    looks_like_link_id,
    new_link_id,
    validate_passcode,
    validate_policy,
    validate_url,
    verify_passcode,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.mark.parametrize(
    ("url", "host"),
    [
        ("https://example.com/a?b=c#d", "example.com"),
        ("  http://EXAMPLE.com.:8080/x  ", "example.com"),
        ("https://bücher.de/", "xn--bcher-kva.de"),
        ("https://[::1]:8443/", "::1"),
    ],
)
def test_valid_urls(url, host):
    d = validate_url(url)
    assert d.host == host
    assert d.url == url.strip()


@pytest.mark.parametrize(
    "url",
    [
        "",
        "   ",
        None,
        123,
        "example.com",
        "/relative",
        "javascript:alert(1)",
        "data:text/html,hi",
        "ftp://example.com/",
        "file:///etc/passwd",
        "https://",
        "https://user:pw@example.com/",
        "https://bank.com@evil.example/",
        "https://exa mple.com/",
        "https://example.com/\nx",
        "https://example.com:99999/",
        "https://example.com:0/",
        "https://example.com:abc/",
        "https://" + "a" * 2050 + ".com",
    ],
)
def test_invalid_urls(url):
    with pytest.raises(AppError) as e:
        validate_url(url)
    assert e.value.code == "INVALID_URL"
    assert e.value.status == 400


@pytest.mark.parametrize(
    ("ttl", "clicks", "code"),
    [
        (0, 1, "INVALID_TTL"),
        (721, 1, "INVALID_TTL"),
        (1, 0, "INVALID_MAX_CLICKS"),
        (1, 1001, "INVALID_MAX_CLICKS"),
        (-5, 1, "INVALID_TTL"),
    ],
)
def test_policy_bounds(ttl, clicks, code):
    with pytest.raises(AppError) as e:
        validate_policy(ttl, clicks, max_ttl=720, max_clicks_limit=1000)
    assert e.value.code == code


def test_policy_edges_ok():
    validate_policy(1, 1, max_ttl=720, max_clicks_limit=1000)
    validate_policy(720, 1000, max_ttl=720, max_clicks_limit=1000)


def test_passcode_validation():
    assert validate_passcode(None) is None
    assert validate_passcode("") is None
    assert validate_passcode("abcd") == "abcd"
    for bad in ("abc", "x" * 129):
        with pytest.raises(AppError):
            validate_passcode(bad)


def test_passcode_hashing():
    h = hash_passcode("open sesame")
    assert h.startswith("$argon2id$")
    assert "open sesame" not in h
    assert verify_passcode(h, "open sesame")
    assert not verify_passcode(h, "open sesam")
    # No stored hash never verifies, whatever the candidate (dummy hash path).
    assert not verify_passcode(None, "safelinks-dummy-passcode")
    assert not verify_passcode("not-a-hash", "x")


def test_ids():
    ids = {new_link_id() for _ in range(1000)}
    assert len(ids) == 1000
    assert all(len(i) == 22 and looks_like_link_id(i) for i in ids)
    for bad in ("short", "a" * 65, "abc/def/ghijklmnop", "abcdefghijklmnop.", "<script>xxxxxxxxx"):
        assert not looks_like_link_id(bad)


def _status(**kw):
    base = dict(
        now=NOW, expires_at=NOW + timedelta(hours=1), clicks=0, max_clicks=1, revoked_at=None
    )
    return derive_status(**{**base, **kw})


def test_status_precedence():
    past = NOW - timedelta(seconds=1)
    assert _status() == LinkStatus.ACTIVE
    assert _status(expires_at=NOW) == LinkStatus.EXPIRED  # boundary: expires_at is exclusive
    assert _status(clicks=1) == LinkStatus.EXHAUSTED
    assert _status(clicks=1, expires_at=past) == LinkStatus.EXHAUSTED
    assert _status(revoked_at=past, clicks=1, expires_at=past) == LinkStatus.REVOKED
