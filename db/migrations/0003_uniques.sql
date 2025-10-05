-- institutions.name must be unique if you're upserting on it
alter table institutions
  add constraint uq_institutions_name unique (name);

-- optional but smart: don't duplicate accounts per bank/mask
-- mask can be null; make the unique only apply when it's present
create unique index if not exists uq_accounts_inst_mask
  on accounts (institution_id, mask)
  where mask is not null;
