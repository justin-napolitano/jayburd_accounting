create table if not exists teller_nonces (
  nonce text primary key,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  used_at timestamptz,
  client_hint text
);
create index if not exists idx_teller_nonces_expires on teller_nonces(expires_at);
