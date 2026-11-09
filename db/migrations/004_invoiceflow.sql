-- 004_invoiceflow.sql — InvoiceFlow a nivel producto:
-- maestro de proveedores, campos fiscales, motivos de revisión, correcciones humanas,
-- idempotencia por archivo (sha256) y métricas medidas de la cola.

CREATE TABLE IF NOT EXISTS vendors (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id  uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  rut        text NOT NULL,
  name       text NOT NULL,
  active     boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, rut)
);

ALTER TABLE invoices ADD COLUMN IF NOT EXISTS vendor_rut   text;
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS issue_date   date;
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS neto         numeric(14,2);
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS iva          numeric(14,2);
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS lines        jsonb NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS reasons      jsonb NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS corrections  jsonb NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS raw_text     text;
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS source_sha256 text;
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS extractor    text NOT NULL DEFAULT 'rules';
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS confidence   numeric(5,2);
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS duplicate_of uuid REFERENCES invoices(id) ON DELETE SET NULL;

-- un mismo archivo no se procesa dos veces (re-subida = idempotente)
CREATE UNIQUE INDEX IF NOT EXISTS uq_invoices_file ON invoices (tenant_id, source_sha256)
  WHERE source_sha256 IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_invoices_folio ON invoices (tenant_id, vendor_rut, invoice_no);
CREATE INDEX IF NOT EXISTS idx_invoices_review ON invoices (tenant_id, status, created_at DESC);

DROP VIEW IF EXISTS v_invoices;

CREATE VIEW v_invoices AS
SELECT tenant_id,
       count(*)                                                             AS total,
       count(*) FILTER (WHERE status = 'pending')                           AS pending,
       count(*) FILTER (WHERE status = 'pass')                              AS auto_pass,
       count(*) FILTER (WHERE status = 'review')                            AS need_review,
       count(*) FILTER (WHERE status = 'approved')                          AS approved,
       count(*) FILTER (WHERE status = 'rejected')                          AS rejected,
       round(100.0 * count(*) FILTER (WHERE status = 'pass') / GREATEST(count(*), 1), 1)           AS auto_pct,
       round(100.0 * count(*) FILTER (WHERE status IN ('pass', 'approved')) / GREATEST(count(*), 1), 1) AS approved_pct,
       round(avg(extract(epoch FROM (reviewed_at - created_at)) / 60.0)::numeric, 1)               AS review_minutes,
       round(avg(CASE WHEN jsonb_typeof(corrections) = 'array' THEN jsonb_array_length(corrections) END)::numeric, 2)
                                                                            AS corrections_per_review,
       coalesce(sum(total) FILTER (WHERE status IN ('pass', 'approved')), 0) AS booked_total,
       round(avg(confidence)::numeric, 1)                                   AS confidence
FROM invoices
GROUP BY 1;

CREATE OR REPLACE VIEW v_invoices_daily AS
SELECT tenant_id,
       created_at::date                                        AS day,
       count(*)                                                AS received,
       count(*) FILTER (WHERE status = 'pass')                  AS auto_pass,
       count(*) FILTER (WHERE status = 'review')                AS need_review,
       coalesce(sum(total) FILTER (WHERE status IN ('pass','approved')), 0) AS booked_total
FROM invoices
GROUP BY 1, 2;
