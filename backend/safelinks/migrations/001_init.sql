-- SafeLinks initial schema.
-- Lifecycle state is derived from timestamps and counters; only revocation is persisted
-- as an explicit transition (revoked_at). See safelinks/domain.py:derive_status.

create table accounts (
    id uuid primary key,                       -- Supabase Auth user id (JWT "sub")
    created_at timestamptz not null default now(),
    status text not null default 'active' check (status in ('active', 'suspended')),
    plan text not null default 'free',
    suspended_at timestamptz
);

create table links (
    id text primary key,                       -- cryptographically random public id
    owner_id uuid not null references accounts (id) on delete cascade,
    original_url text not null,
    destination_host text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    expires_at timestamptz not null,
    max_clicks integer not null check (max_clicks > 0),
    -- The CHECK is a last line of defence: the counter can never exceed the limit,
    -- even if application logic regresses.
    clicks integer not null default 0 check (clicks >= 0 and clicks <= max_clicks),
    exhausted_at timestamptz,
    revoked_at timestamptz,
    revoked_by text check (revoked_by in ('owner', 'operator')),
    passcode_hash text
);

create index links_owner_created_idx on links (owner_id, created_at desc, id desc);
create index links_owner_expires_idx on links (owner_id, expires_at, id);
create index links_expires_idx on links (expires_at);
create index links_revoked_idx on links (revoked_at) where revoked_at is not null;
create index links_exhausted_idx on links (exhausted_at) where exhausted_at is not null;

-- Audit events outlive the link row on purpose (no FK) so revocations stay auditable
-- until the audit retention window passes.
create table audit_events (
    id bigint generated always as identity primary key,
    link_id text not null,
    owner_id uuid,
    event_type text not null,
    created_at timestamptz not null default now(),
    metadata jsonb not null default '{}'::jsonb
);

create index audit_events_link_idx on audit_events (link_id, created_at);
create index audit_events_created_idx on audit_events (created_at);

-- Shared fixed-window rate-limit counters. Keys contain salted hashes, never raw IPs.
-- Unlogged: losing counters on a crash only resets windows early.
create unlogged table rate_limits (
    key text not null,
    window_start timestamptz not null,
    count integer not null,
    primary key (key, window_start)
);

create index rate_limits_window_idx on rate_limits (window_start);

create table abuse_reports (
    id bigint generated always as identity primary key,
    link_id text not null,
    reason text not null check (reason in ('phishing', 'malware', 'spam', 'illegal', 'other')),
    details text check (char_length(details) <= 2000),
    reporter_email text check (char_length(reporter_email) <= 320),
    status text not null default 'open' check (status in ('open', 'actioned', 'dismissed')),
    created_at timestamptz not null default now(),
    resolved_at timestamptz
);

create index abuse_reports_status_idx on abuse_reports (status, created_at);

-- On Supabase, tables in "public" are reachable through the Data API with the anon key.
-- SafeLinks only accesses them from the backend (table owner, which bypasses RLS), so enable
-- RLS with no policies: the Data API sees nothing. Harmless on plain Postgres.
alter table accounts enable row level security;
alter table links enable row level security;
alter table audit_events enable row level security;
alter table rate_limits enable row level security;
alter table abuse_reports enable row level security;
