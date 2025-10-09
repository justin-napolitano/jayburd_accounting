create unique index if not exists uq_teller_jobs_window_queued
  on teller_jobs(provider_account_id, account_api_id, start_date, end_date);
