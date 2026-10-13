-- Soft removal from the consultation list. Apply once to databases created
-- before removed_at was in schema.sql:
--   npx wrangler d1 execute jyotish-prep --file=./migrations/0001_removed_at.sql --remote
ALTER TABLE consultations ADD COLUMN removed_at INTEGER;
