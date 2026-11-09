-- 006_reportbot.sql — ReportBot: planilla de ventas -> resumen con cifras y texto

CREATE TABLE IF NOT EXISTS sales_reports (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  file_name     text,
  source_sha256 text,
  period_start  date,
  period_end    date,
  rows_count    integer NOT NULL DEFAULT 0,
  total         numeric(14,2) NOT NULL DEFAULT 0,
  prev_total    numeric(14,2) NOT NULL DEFAULT 0,
  delta_pct     numeric(6,1) NOT NULL DEFAULT 0,
  currency      text NOT NULL DEFAULT 'CLP',
  metrics       jsonb NOT NULL DEFAULT '{}'::jsonb,
  text          text,
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, source_sha256)
);

CREATE INDEX IF NOT EXISTS idx_sales_reports_tenant ON sales_reports (tenant_id, created_at DESC);
