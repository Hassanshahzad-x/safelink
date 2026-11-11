-- Keep a tombstone row for deleted accounts (no personal data, only the auth user id).
-- Without it, a still-valid access token would recreate the account as active on the
-- next request, which also undid suspensions.
alter table accounts drop constraint accounts_status_check;
alter table accounts add constraint accounts_status_check
    check (status in ('active', 'suspended', 'deleted'));
alter table accounts add column deleted_at timestamptz;
