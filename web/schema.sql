-- D1 schema. Apply with:
--   npx wrangler d1 execute jyotish-prep --file=./schema.sql --remote
--
-- `body` holds the whole consultation (src/worker/flow.ts:Consultation) as
-- JSON. The columns beside it exist only to list, order, and guard rows.
CREATE TABLE IF NOT EXISTS consultations (
  id          TEXT    PRIMARY KEY,           -- crypto.randomUUID()
  client_name TEXT    NOT NULL,              -- duplicated from body for the list view
  stage       TEXT    NOT NULL,              -- duplicated from body for the list view
  created_at  INTEGER NOT NULL,              -- unix ms
  updated_at  INTEGER NOT NULL,              -- unix ms
  -- A lease taken *before* calling the model, so a double-clicked button or a
  -- second tab gets "already working" instead of paying for a second LLM run.
  -- Checking at write time would be too late: both runs would already be paid
  -- for. It expires on its own, so a request that dies mid-call cannot wedge
  -- the consultation.
  busy_until  INTEGER,                       -- unix ms, NULL when idle
  body        TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS consultations_updated ON consultations (updated_at DESC);
