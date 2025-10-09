alter table provider_enrollments
  add column if not exists teller_user_id text,
  add column if not exists teller_enrollment_id text;

-- backfill teller_user_id from what you’ve been calling “enrollment_id”
update provider_enrollments
set teller_user_id = enrollment_id
where teller_user_id is null;
