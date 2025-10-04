-- writer (ETL)
do $$ begin
  if not exists (select from pg_roles where rolname = current_setting('POSTGRES_USER', true)) then
    create role fin_writer login password current_setting('POSTGRES_PASSWORD', true);
  end if;
end $$;

-- reader (API)
do $$ begin
  if not exists (select from pg_roles where rolname = current_setting('POSTGRES_READONLY_USER', true)) then
    create role fin_reader login password current_setting('POSTGRES_READONLY_PASSWORD', true);
  end if;
end $$;

grant connect on database finance to fin_reader;
