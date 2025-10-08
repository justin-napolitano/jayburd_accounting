-- 0005_teller_jobs.sql
-- Work queue for Teller sync. Matches what sync.py expects.

BEGIN;

CREATE TABLE IF NOT EXISTS teller_jobs (
  id                 bigserial PRIMARY KEY,
  provider_account_id bigint NOT NULL REFERENCES provider_accounts(id) ON DELETE CASCADE,
  account_api_id     text NOT NULL,                 -- Teller account id (e.g. acc_***)
  start_date         date NOT NULL,
  end_date           date NOT NULL,
  status             text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','done','failed')),
  attempts           int  NOT NULL DEFAULT 0,
  last_error         text,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now()
);

-- One queued job per account per window. Prevent duplicates.
CREATE UNIQUE INDEX IF NOT EXISTS uq_teller_jobs_window_queued
  ON teller_jobs(provider_account_id, start_date, end_date)
  WHERE status = 'queued';

-- Fast pulls of “what should I run next”
CREATE INDEX IF NOT EXISTS idx_teller_jobs_status_created
  ON teller_jobs(status, created_at);

-- Touch updated_at on updates
CREATE OR REPLACE FUNCTION touch_updated_at() RETURNS trigger AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_teller_jobs_touch ON teller_jobs;
CREATE TRIGGER trg_teller_jobs_touch
  BEFORE UPDATE ON teller_jobs
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

COMMIT;
