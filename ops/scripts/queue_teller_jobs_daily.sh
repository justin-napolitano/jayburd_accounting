# ops/scripts/queue_teller_daily.sh
#!/usr/bin/env sh
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd -P)
[ -f "$REPO_ROOT/.env" ] && { set -a; . "$REPO_ROOT/.env"; set +a; }

# Host vs container DB details
IN_CONTAINER=0; [ -f "/.dockerenv" ] && IN_CONTAINER=1
grep -qE '(docker|kubepods)' /proc/1/cgroup 2>/dev/null && IN_CONTAINER=1
if [ "$IN_CONTAINER" -eq 1 ]; then
  : "${POSTGRES_HOST:=db}"; : "${POSTGRES_PORT_HOST:=5432}"
else
  [ "${POSTGRES_HOST:-db}" = "db" ] && POSTGRES_HOST=localhost
  : "${POSTGRES_PORT_HOST:=5434}"
fi
: "${POSTGRES_DB:=finance}"
: "${POSTGRES_USER:=fin_writer}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD missing}"

SQL="
\\set from_date (current_date - 1)
\\set to_date   current_date
insert into teller_jobs(provider_account_id, account_api_id, start_date, end_date, run_after)
select pa.id, pa.teller_account_id, :'from_date'::date, :'to_date'::date, now()
from provider_accounts pa
on conflict on constraint uq_teller_jobs_window_queued do nothing;

select 'queued' as label, count(*) as jobs
from teller_jobs
where start_date = :'from_date'::date and end_date = :'to_date'::date;
"

PGPASSWORD=\"$POSTGRES_PASSWORD\" psql \
  -h \"$POSTGRES_HOST\" -p \"$POSTGRES_PORT_HOST\" \
  -U \"$POSTGRES_USER\" -d \"$POSTGRES_DB\" \
  -v ON_ERROR_STOP=1 -P pager=off -c \"$SQL\"
