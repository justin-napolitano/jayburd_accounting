-- Institutions (idempotent)
insert into institutions(name, external_id)
select 'TELLER','teller'
where not exists (select 1 from institutions where external_id='teller');

-- Jobs queue used by your drain_jobs()
create table if not exists teller_jobs (
  id bigserial primary key,
  account_api_id text not null,
  run_after timestamptz not null default now(),
  attempts int not null default 0,
  last_error text,
  created_at timestamptz not null default now()
);

create index if not exists idx_teller_jobs_run_after on teller_jobs(run_after, id);

-- Sync ledger (your code upserts here)
create table if not exists teller_sync (
  account_id bigint primary key references accounts(id) on delete cascade,
  last_polled_at timestamptz,
  last_window_start date,
  last_window_end date
);

-- Transactions external id you’re using (NOTE: your API also expects external_tx_id, not external_txn_id)
alter table transactions add column if not exists external_tx_id text;

-- For your ON CONFLICT (account_id, external_tx_id) DO NOTHING to be valid:
create unique index if not exists uq_tx_account_external
  on transactions(account_id, external_tx_id)
  where external_tx_id is not null;

