PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -p 5434 -U $POSTGRES_USER -d $POSTGRES_DB -v ON_ERROR_STOP=1 -P pager=off -c "
\\set start_date '2025-01-01'
\\set end_date   current_date
with months as (
  select date_trunc('month', gs)::date as start_date
  from generate_series(:'start_date'::date, :'end_date'::date, interval '1 month') gs
)
insert into teller_jobs(provider_account_id, account_api_id, start_date, end_date, run_after)
select pa.id,
       pa.teller_account_id,
       m.start_date,
       least((m.start_date + interval '1 month')::date, current_date),
       now()
from months m
join provider_accounts pa on true
on conflict on constraint uq_teller_jobs_window_queued do nothing;
"
