-- dimensions
create table if not exists institutions (
  id bigserial primary key,
  name text not null,
  external_id text unique
);

create table if not exists accounts (
  id bigserial primary key,
  institution_id bigint references institutions(id),
  name text not null,
  type text check (type in ('checking','savings','credit','loan','investment','cash')),
  currency char(3) not null default 'USD',
  mask text,
  external_id text unique,
  is_active boolean not null default true
);

create table if not exists merchants (
  id bigserial primary key,
  display_name text,
  canonical_name text,
  website text
);

create table if not exists categories (
  id bigserial primary key,
  code text unique,
  parent_id bigint references categories(id),
  is_budgetable boolean default true
);

create table if not exists tags (
  id bigserial primary key,
  name text unique not null
);

create table if not exists tx_tags (
  transaction_id bigint,
  tag_id bigint,
  primary key (transaction_id, tag_id)
);

-- ingestion audit
create table if not exists ingest_files (
  id bigserial primary key,
  source text not null,                    -- 'email','manual','headless'
  bank text,
  filename text not null,
  content_sha256 text not null,
  size_bytes bigint not null,
  mime_type text,
  received_at timestamptz not null default now(),
  processed_at timestamptz,
  status text not null default 'received', -- received | processed | error
  error text
);
create unique index if not exists ix_ingest_files_sha on ingest_files(content_sha256);

create table if not exists tx_staging_raw (
  id bigserial primary key,
  ingest_file_id bigint references ingest_files(id) on delete cascade,
  source text not null,                    -- 'csv','qfx','ofx'
  payload jsonb not null,
  ingested_at timestamptz not null default now()
);

-- facts
create table if not exists transactions (
  id bigserial primary key,
  account_id bigint references accounts(id) not null,
  posted_at date not null,
  amount numeric(14,2) not null,          -- outflow negative, inflow positive
  currency char(3) not null,
  description text not null,
  normalized_desc text,
  merchant_id bigint references merchants(id),
  external_tx_id text,                     -- stable id if present
  hash bytea,                              -- sha256(acct|date|amount|desc) as bytea
  balance_after numeric(14,2),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (account_id, external_tx_id)
);
create unique index if not exists ux_tx_hash on transactions(account_id, hash);
create index if not exists ix_tx_account_date on transactions(account_id, posted_at);

create table if not exists tx_splits (
  id bigserial primary key,
  transaction_id bigint references transactions(id) on delete cascade,
  category_id bigint references categories(id),
  amount numeric(14,2) not null,
  note text
);

-- rules
create table if not exists rules (
  id bigserial primary key,
  name text not null,
  priority int not null default 100,
  includes text[],
  excludes text[],
  merchant_hint text,
  category_id bigint references categories(id),
  set_tag_ids bigint[],
  amount_min numeric(14,2),
  amount_max numeric(14,2),
  active boolean default true
);

-- ML predictions (later)
create table if not exists category_predictions (
  transaction_id bigint references transactions(id) on delete cascade,
  predicted_category_id bigint references categories(id),
  model_version text not null,
  confidence numeric,
  created_at timestamptz default now(),
  primary key (transaction_id, model_version)
);

-- budgets
create table if not exists budgets (
  id bigserial primary key,
  category_id bigint references categories(id),
  period_start date not null,
  period_end date not null,
  amount numeric(14,2) not null,
  unique (category_id, period_start, period_end)
);

-- trigram index for fuzzy desc matching
create index if not exists ix_tx_normdesc_trgm on transactions using gin (normalized_desc gin_trgm_ops);

-- default tag fk once transactions exist
alter table if exists tx_tags
  add constraint fk_txtags_tx foreign key (transaction_id) references transactions(id) on delete cascade,
  add constraint fk_txtags_tag foreign key (tag_id) references tags(id) on delete cascade;
