"""Pure domain rules: validation, lifecycle derivation, ids and passcode hashing.

Nothing here touches the network or the database, so it is unit-testable in isolation.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from urllib.parse import urlsplit

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

# ---------------------------------------------------------------------------
# Errors


class AppError(Exception):
    """An expected failure with a stable machine-readable code."""

    def __init__(self, status: int, code: str, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.retry_after = retry_after


def bad_request(code: str, message: str) -> AppError:
    return AppError(400, code, message)


# ---------------------------------------------------------------------------
# Lifecycle


class LinkStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    EXHAUSTED = "exhausted"
    REVOKED = "revoked"


def derive_status(
    *,
    now: datetime,
    expires_at: datetime,
    clicks: int,
    max_clicks: int,
    revoked_at: datetime | None,
) -> LinkStatus:
    """Precedence: revoked > exhausted > expired > active.

    Exhausted outranks expired because a link can only be exhausted while it was still
    active, so it is the more specific explanation. Must match status_sql() below.
    """
    if revoked_at is not None:
        return LinkStatus.REVOKED
    if clicks >= max_clicks:
        return LinkStatus.EXHAUSTED
    if now >= expires_at:
        return LinkStatus.EXPIRED
    return LinkStatus.ACTIVE


# SQL predicates mirroring derive_status, used for filtering in the database.
STATUS_SQL: dict[LinkStatus, str] = {
    LinkStatus.REVOKED: "l.revoked_at is not null",
    LinkStatus.EXHAUSTED: "l.revoked_at is null and l.clicks >= l.max_clicks",
    LinkStatus.EXPIRED: (
        "l.revoked_at is null and l.clicks < l.max_clicks and l.expires_at <= now()"
    ),
    LinkStatus.ACTIVE: "l.revoked_at is null and l.clicks < l.max_clicks and l.expires_at > now()",
}

# ---------------------------------------------------------------------------
# Input validation

_ALLOWED_SCHEMES = {"http", "https"}


@dataclass(frozen=True)
class Destination:
    url: str
    host: str


def validate_url(raw: object, max_length: int = 2048) -> Destination:
    """Accept only absolute http(s) URLs with a host. The URL is stored as submitted
    (minus surrounding whitespace) so the destination is never silently changed."""
    if not isinstance(raw, str) or not raw.strip():
        raise bad_request("INVALID_URL", "Enter a URL.")
    url = raw.strip()
    if len(url) > max_length:
        raise bad_request("INVALID_URL", f"URLs can be at most {max_length} characters.")
    if any(ord(c) < 0x21 or ord(c) == 0x7F for c in url):
        raise bad_request("INVALID_URL", "URLs cannot contain spaces or control characters.")
    try:
        parts = urlsplit(url)
        port = parts.port  # raises ValueError for non-numeric or out-of-range ports
    except ValueError:
        raise bad_request("INVALID_URL", "That URL is malformed.") from None
    if parts.scheme.lower() not in _ALLOWED_SCHEMES:
        raise bad_request("INVALID_URL", "Only http and https URLs are supported.")
    if not parts.netloc or not parts.hostname:
        raise bad_request("INVALID_URL", "The URL must include a host name.")
    if parts.username is not None or parts.password is not None:
        # "https://bank.com@evil.example" style URLs disguise the real host.
        raise bad_request("INVALID_URL", "URLs with embedded credentials are not allowed.")
    if port == 0:
        raise bad_request("INVALID_URL", "The URL has an invalid port.")
    return Destination(url=url, host=normalize_host(parts.hostname))


def normalize_host(hostname: str) -> str:
    """Lowercase, strip the trailing dot and convert IDNs to punycode so look-alike
    characters are visible when the host is displayed."""
    host = hostname.rstrip(".").lower()
    if not host:
        raise bad_request("INVALID_URL", "The URL must include a host name.")
    try:
        return host.encode("idna").decode("ascii")
    except UnicodeError:
        if host.isascii():
            return host
        raise bad_request("INVALID_URL", "The host name is not valid.") from None


def validate_policy(ttl_hours: int, max_clicks: int, *, max_ttl: int, max_clicks_limit: int):
    if ttl_hours < 1 or ttl_hours > max_ttl:
        raise bad_request("INVALID_TTL", f"Expiry must be between 1 and {max_ttl} hours.")
    if max_clicks < 1 or max_clicks > max_clicks_limit:
        raise bad_request("INVALID_MAX_CLICKS", f"Visits must be between 1 and {max_clicks_limit}.")


PASSCODE_MIN, PASSCODE_MAX = 4, 128


def validate_passcode(passcode: str | None) -> str | None:
    if passcode is None or passcode == "":
        return None
    if not (PASSCODE_MIN <= len(passcode) <= PASSCODE_MAX):
        raise bad_request(
            "INVALID_PASSCODE",
            f"Passcodes must be {PASSCODE_MIN}-{PASSCODE_MAX} characters.",
        )
    return passcode


# ---------------------------------------------------------------------------
# Identifiers

ID_ALPHABET = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")


def new_link_id() -> str:
    """128 bits from the OS CSPRNG, base64url (22 chars)."""
    return secrets.token_urlsafe(16)


def looks_like_link_id(value: str) -> bool:
    return 16 <= len(value) <= 64 and set(value) <= ID_ALPHABET


# ---------------------------------------------------------------------------
# Passcodes (Argon2id; argon2-cffi defaults: t=3, m=64 MiB, p=4)

_hasher = PasswordHasher()
# Verified against when a link has no usable hash, so the work done is the same.
_DUMMY_HASH = _hasher.hash("safelinks-dummy-passcode")


def hash_passcode(passcode: str) -> str:
    return _hasher.hash(passcode)


def verify_passcode(stored_hash: str | None, candidate: str) -> bool:
    try:
        return _hasher.verify(stored_hash or _DUMMY_HASH, candidate) and stored_hash is not None
    except (VerificationError, InvalidHashError):
        return False
