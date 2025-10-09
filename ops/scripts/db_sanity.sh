#!/usr/bin/env sh
# db_sanity.sh (POSIX sh)
# Sanity checks across Finance OS tables without bash-only features.

set -eu

# Load .env if present (export all vars while sourcing)
# Resolve repo root and load .env regardless of where you run this from
# Works with sh; tolerates symlinks; doesn't need bash.

# Directory of this script
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
# Assume repo root is the parent of ops/scripts (adjust if you move it)
REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd -P)

# If it's a git repo, prefer that (safer if you relocate scripts)
if command -v git >/dev/null 2>&1; then
  GIT_ROOT=$(git -C "$REPO_ROOT" rev-parse --show-toplevel 2>/dev/null || true)
  [ -n "$GIT_ROOT" ] && REPO_ROOT="$GIT_ROOT"
fi

ENV_FILE="$REPO_ROOT/.env"

# Load .env if present (export all vars while sourcing)
if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$ENV_FILE"
  set +a
else
  printf '%s\n' "[warn] .env not found at $ENV_FILE; using environment only."
fi

# --- Where am I running? host vs container ---
IN_CONTAINER=0
[ -f "/.dockerenv" ] && IN_CONTAINER=1
# crude but works: cgroup says 'docker' or 'kubepods'
grep -qE '(docker|kubepods)' /proc/1/cgroup 2>/dev/null && IN_CONTAINER=1

# Defaults that won't wreck your day
# On host: connect to mapped port 5434 @ localhost
# In container: connect to service name 'db' @ 5432
if [ "$IN_CONTAINER" -eq 1 ]; then
  : "${POSTGRES_HOST:=db}"
  : "${POSTGRES_PORT_HOST:=5432}"
else
  # if someone left service name in .env, fix it
  if [ "${POSTGRES_HOST:-db}" = "db" ] || [ "${POSTGRES_HOST:-postgres}" = "postgres" ]; then
    POSTGRES_HOST=localhost
  fi
  : "${POSTGRES_PORT_HOST:=5434}"
fi

# Still allow explicit overrides from environment
: "${POSTGRES_DB:=finance}"
: "${POSTGRES_USER:=fin_writer}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD missing}"

pg() {
  PGPASSWORD="$POSTGRES_PASSWORD" psql \
    -h "$POSTGRES_HOST" -p "$POSTGRES_PORT_HOST" \
    -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    -v "ON_ERROR_STOP=1" -q -t -A -F '	' \
    -c "$1"
}

pgf() {
  PGPASSWORD="$POSTGRES_PASSWORD" psql \
    -h "$POSTGRES_HOST" -p "$POSTGRES_PORT_HOST" \
    -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    -v "ON_ERROR_STOP=1" -P pager=off \
    -c "$1"
}

line() { printf '%s\n' "------------------------------------------------------------"; }
hdr()  { line; printf '### %s\n' "$1"; line; }

hdr "Connectivity"
pgf "select version();"
pgf "select current_database() db, current_user as user, inet_server_addr() as addr, inet_server_port() as port;"

hdr "Extensions"
pgf "\\dx"

hdr "Migrations"
pgf "select * from schema_migrations order by applied_at desc limit 20;"

hdr "Institutions"
pgf "select id, name, external_id from institutions order by id limit 20;"

hdr "Accounts (app-level)"
pgf "select count(*) as accounts_total from accounts;"
pgf "select id, institution_id, name, type, currency, mask, external_id, is_active
     from accounts order by id desc limit 15;"

hdr "Provider Enrollments (Teller)"
pgf "select id, provider, enrollment_id as usr_id, coalesce(teller_enrollment_id,'') as enr_id,
            environment, status, created_at
     from provider_enrollments
     order by id desc limit 10;"

hdr "Provider Accounts (Teller)"
pgf "select count(*) as provider_accounts_total from provider_accounts;"
pgf "select id, enrollment_id as usr_id, teller_account_id as acct_id, last_four, type, subtype, currency
     from provider_accounts order by id desc limit 15;"

hdr "Teller Jobs"
pgf "select count(*) as teller_jobs_total from teller_jobs;"
pgf "select provider_account_id, account_api_id, start_date, end_date, run_after
     from teller_jobs order by run_after desc limit 15;"

hdr "Raw Ingest Files"
pgf "select count(*) as ingest_files_total from ingest_files;"
pgf "select id, filename, status, received_at
     from ingest_files order by id desc limit 15;"

hdr "Transactions"
pgf "select count(*) as transactions_total from transactions;"
pgf "select id, posted_at, amount, description, account_id
     from transactions order by posted_at desc, id desc limit 20;"

hdr "Split Classifications"
pgf "select count(*) as tx_splits_total from tx_splits;"
pgf "select s.id, s.transaction_id, c.code as category_code, s.amount
     from tx_splits s
     join categories c on c.id = s.category_id
     order by s.id desc limit 20;"

hdr "Budgets"
pgf "select count(*) as budgets_total from budgets;"
pgf "select b.category_id, c.code as category_code, b.period_start, b.amount
     from budgets b join categories c on c.id = b.category_id
     order by b.period_start desc, c.code asc limit 30;"

hdr "Budget Status View (if present)"
# Not all envs have this view; don't die if missing
if ! pgf "select * from v_budget_status order by category limit 20;"; then
  printf '%s\n' "[note] v_budget_status not found. Skipping."
fi

hdr "Indexes & Health (quick glance)"
pgf "select schemaname, relname, indexrelname, idx_scan, idx_tup_read, idx_tup_fetch
     from pg_stat_user_indexes order by idx_scan desc nulls last limit 20;"
pgf "select relname, n_live_tup as est_rows, n_dead_tup as dead_rows, last_vacuum, last_autovacuum
     from pg_stat_user_tables order by n_dead_tup desc nulls last limit 20;"

hdr "Sizes"
pgf "select table_name, pg_size_pretty(pg_total_relation_size(quote_ident(table_name))) as size
     from information_schema.tables
     where table_schema='public'
     order by pg_total_relation_size(quote_ident(table_name)) desc
     limit 20;"

hdr "Done"
