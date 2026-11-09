-- 001_init.sql — núcleo multi-tenant de la suite
-- Regla: todo cuelga de un tenant. Un mismo stack sirve a varios negocios.
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS tenants (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug        text UNIQUE NOT NULL,
  name        text NOT NULL,
  industry    text,
  config      jsonb NOT NULL DEFAULT '{}'::jsonb,   -- precios, horarios, faq, tono
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS contacts (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id   uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  wa_id       text,                                  -- teléfono / id de canal
  name        text,
  email       text,
  phone       text,
  meta        jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, wa_id)
);

CREATE TABLE IF NOT EXISTS conversations (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id      uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  contact_id     uuid REFERENCES contacts(id) ON DELETE SET NULL,
  channel        text NOT NULL DEFAULT 'whatsapp',   -- whatsapp | webchat | instagram
  status         text NOT NULL DEFAULT 'bot'
                 CHECK (status IN ('bot','human','closed')),
  handoff_reason text,
  handoff_at     timestamptz,
  assigned_to    text,
  last_message_at timestamptz,
  created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_conv_tenant_status ON conversations (tenant_id, status, last_message_at DESC);

CREATE TABLE IF NOT EXISTS messages (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  direction      text NOT NULL CHECK (direction IN ('in','out')),
  source         text NOT NULL DEFAULT 'bot' CHECK (source IN ('bot','human','system')),
  body           text NOT NULL,
  wa_message_id  text,
  latency_ms     int,
  tokens         int,
  cost_usd       numeric(10,6),
  created_at     timestamptz NOT NULL DEFAULT now()
);
-- idempotencia: Meta reintenta el mismo message.id
CREATE UNIQUE INDEX IF NOT EXISTS uq_messages_wa_id ON messages (wa_message_id) WHERE wa_message_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages (conversation_id, created_at);

CREATE TABLE IF NOT EXISTS kb_entries (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id  uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  topic      text NOT NULL,
  question   text,
  answer     text NOT NULL,
  price      text,
  active     boolean NOT NULL DEFAULT true,
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS invoices (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id   uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  file_name   text,
  vendor      text,
  invoice_no  text,
  total       numeric(14,2),
  currency    text DEFAULT 'CLP',
  status      text NOT NULL DEFAULT 'pending'
              CHECK (status IN ('pending','pass','review','approved','rejected')),
  reason      text,
  extracted   jsonb NOT NULL DEFAULT '{}'::jsonb,
  reviewed_by text,
  reviewed_at timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_inv_tenant_status ON invoices (tenant_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS leads (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id  uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name       text,
  email      text,
  phone      text,
  source     text,
  score      int,
  tier       text CHECK (tier IN ('HOT','WARM','COLD')),
  reasons    jsonb NOT NULL DEFAULT '[]'::jsonb,
  draft      text,
  status     text NOT NULL DEFAULT 'new' CHECK (status IN ('new','contacted','qualified','discarded')),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_leads_tenant ON leads (tenant_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS reports (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id  uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  period     text NOT NULL,
  payload    jsonb NOT NULL DEFAULT '{}'::jsonb,
  channel    text DEFAULT 'email',
  status     text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','sent','failed')),
  sent_at    timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS events (
  id         bigserial PRIMARY KEY,
  tenant_id  uuid REFERENCES tenants(id) ON DELETE CASCADE,
  entity     text NOT NULL,
  entity_id  uuid,
  action     text NOT NULL,
  meta       jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_events_tenant ON events (tenant_id, created_at DESC);

CREATE TABLE IF NOT EXISTS eval_runs (
  id         bigserial PRIMARY KEY,
  tenant_id  uuid REFERENCES tenants(id) ON DELETE CASCADE,
  piece      text NOT NULL,          -- replydesk | invoiceflow | leadscore | reportbot
  total      int NOT NULL,
  passed     int NOT NULL,
  score      numeric(5,2) GENERATED ALWAYS AS (CASE WHEN total > 0 THEN round(passed::numeric * 100 / total, 2) ELSE 0 END) STORED,
  detail     jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
