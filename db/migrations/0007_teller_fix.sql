-- 0004_teller_api_sync.sql
-- Make Teller tables and core schema line up with the API and views.

BEGIN;

-- 1) transactions: add API-compatible columns + backfill + proper unique
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS external_tx_id text;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS external_source text;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS status text;

-- If you previously added external_txn_id, map it into external_tx_id.
-- Prefix with external_source to keep it globally unique across providers.
UPDATE transactions
SET external_tx_id = CASE
  WHEN external_tx_id IS NOT NULL THEN external_tx_id
  WHEN external_source IS NOT NULL AND EXISTS (
       SELECT 1 FROM information_schema.columns
       WHERE table_name='transactions' AND column_name='external_txn_id'
     ) THEN external_source || ':' || external_txn_id
  WHEN EXISTS (
       SELECT 1 FROM information_schema.columns
       WHERE table_name='transactions' AND column_name='external_txn_id'
     ) THEN external_txn_id
  ELSE external_tx_id
END
WHERE external_tx_id IS NULL;

-- Unique index to satisfy ON CONFLICT (external_tx_id) used by the ingestors.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_indexes
    WHERE schemaname='public' AND indexname='uq_transactions_external_tx_id'
  ) THEN
    EXECUTE 'CREATE UNIQUE INDEX uq_transactions_external_tx_id
             ON public.transactions(external_tx_id)
             WHERE external_tx_id IS NOT NULL';
  END IF;
END $$;

-- 2) Provider accounts: link to core accounts and institutions so /accounts works

-- Ensure the link column exists
ALTER TABLE provider_accounts ADD COLUMN IF NOT EXISTS account_id bigint;

-- FK to core accounts
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='fk_provider_accounts_core_account'
  ) THEN
    ALTER TABLE provider_accounts
      ADD CONSTRAINT fk_provider_accounts_core_account
      FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE SET NULL;
  END IF;
END $$;

-- Upsert institutions using institution *name* as the stable key.
-- Your schema already has uq_institutions_name, so we respect it.
-- We fill external_id if it's blank; we don't stomp an existing one.
INSERT INTO institutions(name, external_id)
SELECT DISTINCT
  COALESCE(pe.institution_name, 'Unknown'),
  'teller:' || COALESCE(pa.institution_id, 'unknown')
FROM provider_accounts pa
JOIN provider_enrollments pe ON pe.enrollment_id = pa.enrollment_id
ON CONFLICT ON CONSTRAINT uq_institutions_name DO UPDATE
  SET external_id = COALESCE(institutions.external_id, EXCLUDED.external_id);

-- 3) Upsert core accounts from provider_accounts and wire them back
WITH upserted AS (
  INSERT INTO accounts (institution_id, name, type, currency, mask, external_id, is_active)
  SELECT
    i.id,
    -- Label like "Chase ••••1234" or just the institution if no last_four
    COALESCE(pe.institution_name,'Teller') ||
      CASE WHEN COALESCE(pa.last_four,'') <> '' THEN ' ••••' || pa.last_four ELSE '' END,
    -- Keep within your accounts_type_check
    CASE
      WHEN COALESCE(pa.subtype,'') <> '' THEN pa.subtype            -- checking/savings
      ELSE pa.type                                                  -- credit/loan/investment
    END,
    COALESCE(pa.currency, 'USD'),
    pa.last_four,
    'teller:' || pa.teller_account_id,
    TRUE
  FROM provider_accounts pa
  JOIN provider_enrollments pe ON pe.enrollment_id = pa.enrollment_id
  JOIN institutions i
    ON i.name = COALESCE(pe.institution_name, 'Unknown')            -- relies on uq_institutions_name
  ON CONFLICT (external_id) DO UPDATE
     SET institution_id = EXCLUDED.institution_id,
         name          = EXCLUDED.name,
         type          = EXCLUDED.type,
         mask          = EXCLUDED.mask,
         is_active     = TRUE
  RETURNING external_id, id
)
UPDATE provider_accounts p
SET account_id = u.id
FROM upserted u
WHERE ('teller:' || p.teller_account_id) = u.external_id;

CREATE INDEX IF NOT EXISTS idx_provider_accounts_account_id
  ON provider_accounts(account_id);

COMMIT;
