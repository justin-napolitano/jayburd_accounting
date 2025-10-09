-- Patch teller_jobs to match what sync.py expects
alter table teller_jobs
  add column if not exists run_after timestamptz not null default now(),
  add column if not exists attempts int not null default 0,
  add column if not exists last_error text,
  add column if not exists created_at timestamptz not null default now();

create index if not exists idx_teller_jobs_run_after
  on teller_jobs(run_after, id);

-- Make sure teller_sync exists (your sync.py upserts here)
create table if not exists teller_sync (
  account_id bigint primary key references accounts(id) on delete cascade,
  last_polled_at timestamptz,
  last_window_start date,
  last_window_end date
);

-- Make sure external_tx_id exists and dedupe works as your code expects
alter table transactions add column if not exists external_tx_id text;

create unique index if not exists uq_tx_account_external
  on transactions(account_id, external_tx_id)
  where external_tx_id is not null;
