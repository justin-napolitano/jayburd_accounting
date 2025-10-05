-- Idempotent reader role + grants. No passwords here.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fin_reader') THEN
    CREATE ROLE fin_reader LOGIN;
  END IF;
END$$;

GRANT CONNECT ON DATABASE finance TO fin_reader;
GRANT USAGE ON SCHEMA public TO fin_reader;

-- Current objects
GRANT SELECT ON ALL TABLES    IN SCHEMA public TO fin_reader;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO fin_reader;

-- Future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES    TO fin_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON SEQUENCES TO fin_reader;
