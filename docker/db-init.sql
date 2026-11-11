-- Local only: Supabase Auth (GoTrue) keeps its tables in the "auth" schema.
-- On hosted Supabase this schema already exists.
create schema if not exists auth;
