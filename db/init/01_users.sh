#!/usr/bin/env bash
set -euo pipefail

# This runs at init time with $POSTGRES_* env vars available.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
-- reader role if missing
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fin_reader') THEN
    CREATE ROLE fin_reader LOGIN;
  END IF;
END$$;

-- privileges: connect, read everything now and in the future
GRANT CONNECT ON DATABASE finance TO fin_reader;
GRANT USAGE ON SCHEMA public TO fin_reader;
GRANT SELECT ON ALL TABLES    IN SCHEMA public TO fin_reader;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO fin_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES    TO fin_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON SEQUENCES TO fin_reader;
SQL

# set password for fin_reader from env
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -c "ALTER ROLE fin_reader WITH PASSWORD '${POSTGRES_READONLY_PASSWORD}';"
