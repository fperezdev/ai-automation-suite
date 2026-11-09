-- 005_leadscore.sql — LeadScore: motivos con puntos, dedupe y cola de seguimiento

ALTER TABLE leads
  ADD COLUMN IF NOT EXISTS message           text,
  ADD COLUMN IF NOT EXISTS dedupe_key        text,
  ADD COLUMN IF NOT EXISTS score_breakdown   jsonb NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS services          jsonb NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS duplicate_of      uuid REFERENCES leads(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS next_action_kind  text,
  ADD COLUMN IF NOT EXISTS next_action_at    timestamptz,
  ADD COLUMN IF NOT EXISTS updated_at        timestamptz NOT NULL DEFAULT now();

-- La cola de seguimiento necesita el estado "contactado y con hora tomada" y "cerrado".
DO $$
BEGIN
  ALTER TABLE leads DROP CONSTRAINT IF EXISTS leads_status_check;
  ALTER TABLE leads ADD CONSTRAINT leads_status_check
    CHECK (status IN ('new','contacted','qualified','booked','discarded'));
END $$;

CREATE INDEX IF NOT EXISTS idx_leads_dedupe  ON leads (tenant_id, dedupe_key);
CREATE INDEX IF NOT EXISTS idx_leads_tier    ON leads (tenant_id, tier, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_leads_due     ON leads (tenant_id, next_action_at)
  WHERE status IN ('new','contacted');

-- Un lead no puede apuntar a sí mismo como duplicado.
DO $$
BEGIN
  ALTER TABLE leads ADD CONSTRAINT leads_dup_not_self CHECK (duplicate_of IS NULL OR duplicate_of <> id);
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;
