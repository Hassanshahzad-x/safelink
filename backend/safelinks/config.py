"""Environment-driven configuration. Every value has a safe local default except secrets."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


def _list(name: str, default: str) -> list[str]:
    return [v.strip() for v in os.environ.get(name, default).split(",") if v.strip()]


@dataclass(frozen=True)
class Settings:
    env: str = field(default_factory=lambda: os.environ.get("APP_ENV", "development"))
    database_url: str = field(
        default_factory=lambda: os.environ.get(
            "DATABASE_URL", "postgresql://postgres:postgres@localhost:54329/safelinks"
        )
    )
    db_pool_max: int = field(default_factory=lambda: _int("DB_POOL_MAX", 10))
    db_timeout_seconds: float = field(
        default_factory=lambda: float(os.environ.get("DB_TIMEOUT_SECONDS", "5"))
    )

    # Public URLs. Short URLs are always built from RESOLVER_BASE_URL, never the Host header.
    resolver_base_url: str = field(
        default_factory=lambda: os.environ.get("RESOLVER_BASE_URL", "http://localhost:8001")
    )
    frontend_url: str = field(
        default_factory=lambda: os.environ.get("FRONTEND_URL", "http://localhost:5173")
    )
    cors_origins: list[str] = field(
        default_factory=lambda: _list("CORS_ORIGINS", "http://localhost:5173,http://localhost:8080")
    )

    # Supabase Auth. Either a shared HS256 secret (local GoTrue, legacy projects)
    # or the project's JWKS endpoint (asymmetric signing keys).
    supabase_jwt_secret: str = field(
        default_factory=lambda: os.environ.get("SUPABASE_JWT_SECRET", "")
    )
    supabase_jwks_url: str = field(default_factory=lambda: os.environ.get("SUPABASE_JWKS_URL", ""))
    supabase_jwt_audience: str = field(
        default_factory=lambda: os.environ.get("SUPABASE_JWT_AUDIENCE", "authenticated")
    )
    supabase_jwt_issuer: str = field(
        default_factory=lambda: os.environ.get("SUPABASE_JWT_ISSUER", "")
    )
    # Used only to delete the auth user on account deletion.
    supabase_auth_url: str = field(default_factory=lambda: os.environ.get("SUPABASE_AUTH_URL", ""))
    supabase_service_role_key: str = field(
        default_factory=lambda: os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    )

    # Link policy limits.
    max_ttl_hours: int = field(default_factory=lambda: _int("MAX_TTL_HOURS", 720))
    max_clicks_limit: int = field(default_factory=lambda: _int("MAX_CLICKS_LIMIT", 1000))
    max_url_length: int = 2048

    # Rate limits: "count/seconds".
    rl_resolve_ip: str = field(default_factory=lambda: os.environ.get("RL_RESOLVE_IP", "120/60"))
    rl_create_user: str = field(default_factory=lambda: os.environ.get("RL_CREATE_USER", "30/60"))
    rl_create_user_daily: str = field(
        default_factory=lambda: os.environ.get("RL_CREATE_USER_DAILY", "500/86400")
    )
    rl_create_ip: str = field(default_factory=lambda: os.environ.get("RL_CREATE_IP", "60/60"))
    rl_api_ip: str = field(default_factory=lambda: os.environ.get("RL_API_IP", "300/60"))
    rl_passcode_link: str = field(
        default_factory=lambda: os.environ.get("RL_PASSCODE_LINK", "10/900")
    )
    rl_passcode_ip: str = field(default_factory=lambda: os.environ.get("RL_PASSCODE_IP", "30/900"))
    rl_report_ip: str = field(default_factory=lambda: os.environ.get("RL_REPORT_IP", "10/3600"))
    # Salt for hashing client IPs in rate-limit keys, so raw IPs are never stored.
    rate_limit_salt: str = field(
        default_factory=lambda: os.environ.get("RATE_LIMIT_SALT", "dev-only-salt")
    )
    # Number of trusted proxies appending to X-Forwarded-For. 0 = use the socket peer.
    trusted_proxy_hops: int = field(default_factory=lambda: _int("TRUSTED_PROXY_HOPS", 0))

    # Retention (days after the link became inactive).
    retention_expired_days: int = field(default_factory=lambda: _int("RETENTION_EXPIRED_DAYS", 30))
    retention_exhausted_days: int = field(
        default_factory=lambda: _int("RETENTION_EXHAUSTED_DAYS", 30)
    )
    retention_revoked_days: int = field(default_factory=lambda: _int("RETENTION_REVOKED_DAYS", 30))
    retention_audit_days: int = field(default_factory=lambda: _int("RETENTION_AUDIT_DAYS", 90))
    cleanup_batch_size: int = field(default_factory=lambda: _int("CLEANUP_BATCH_SIZE", 500))
    cleanup_max_batches: int = field(default_factory=lambda: _int("CLEANUP_MAX_BATCHES", 200))
    cleanup_token: str = field(default_factory=lambda: os.environ.get("CLEANUP_TOKEN", ""))

    max_body_bytes: int = field(default_factory=lambda: _int("MAX_BODY_BYTES", 16 * 1024))

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    def validate(self, *, require_auth: bool = False) -> None:
        """Fail fast on configuration that would make the service unsafe."""
        if require_auth and not (self.supabase_jwt_secret or self.supabase_jwks_url):
            raise RuntimeError("Set SUPABASE_JWT_SECRET or SUPABASE_JWKS_URL")
        if self.is_production:
            if self.rate_limit_salt == "dev-only-salt":
                raise RuntimeError("RATE_LIMIT_SALT must be set in production")
            if "*" in self.cors_origins:
                raise RuntimeError("Wildcard CORS is not allowed in production")


def parse_limit(spec: str) -> tuple[int, int]:
    count, seconds = spec.split("/")
    return int(count), int(seconds)


settings = Settings()
