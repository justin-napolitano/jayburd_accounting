-- enrollments, accounts, sync state, webhook audit
create table if not exists provider_enrollments (
  id bigserial primary key,
  provider text not null default 'teller',
  enrollment_id text not null unique,
  user_ref text,
  institution_name text,
  environment text not null,
  access_token_enc bytea not null,
  status text not null default 'active',
  created_at timestamptz not null default now()
);

create table if not exists provider_accounts (
  id bigserial primary key,
  enrollment_id text not null references provider_enrollments(enrollment_id) on delete cascade,
  teller_account_id text not null,
  institution_id text,
  last_four text,
  type text,
  subtype text,
  currency text,
  unique(enrollment_id, teller_account_id)
);

create table if not exists provider_sync_state (
  provider_account_id bigint primary key references provider_accounts(id) on delete cascade,
  last_start_date date,
  last_end_date date,
  last_synced_at timestamptz
);

create table if not exists webhook_events (
  id bigserial primary key,
  source text not null default 'teller',
  event_id text,
  type text,
  received_at timestamptz not null default now(),
  raw jsonb
);

alter table transactions add column if not exists external_source text;
alter table transactions add column if not exists external_txn_id text;
alter table transactions add column if not exists status text;

create unique index if not exists uq_transactions_external
  on transactions(external_source, external_txn_id)
  where external_txn_id is not null;

create index if not exists idx_transactions_posted_at on transactions(posted_at desc);
