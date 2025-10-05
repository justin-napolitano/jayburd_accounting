-- sane default categories; extend later
insert into categories(code, parent_id, is_budgetable) values
  ('INCOME',          null, false),
  ('RENT',            null, true),
  ('GROCERIES',       null, true),
  ('SUBSCRIPTIONS',   null, true),
  ('DINING',          null, true),
  ('TRANSPORT',       null, true),
  ('UTILITIES',       null, true),
  ('HEALTH_INSURANCE',null, true),
  ('CASH',            null, false),
  ('TRANSFERS',       null, false),
  ('SHOPPING',        null, true),
  ('ENTERTAINMENT',   null, true),
  ('FEES',            null, true),
  ('OTHER',           null, true)
on conflict (code) do nothing;
