-- de-dupe active windows only
CREATE UNIQUE INDEX IF NOT EXISTS uq_teller_jobs_window_active
ON teller_jobs (provider_account_id, account_api_id, start_date, end_date)
WHERE status IN ('queued','running');
