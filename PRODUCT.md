# PRODUCT.md — AI Automation Suite

## Qué es
Suite de automatizaciones con IA que se vende e instala por negocio: un asistente de WhatsApp con
bandeja y derivación a humano, extracción de facturas PDF, scoring de leads con borrador de
respuesta y reportes periódicos. Un mismo backend multi-tenant (`tenant_id` en todas las tablas)
sirve a varios clientes; cada cliente ve sólo sus datos.

## Para quién
Pymes de servicios en Chile/LATAM (clínicas, talleres, estudios, distribuidores) que atienden por
WhatsApp y reciben documentos y consultas que hoy procesa una persona a mano. Quien opera el panel
es la persona de recepción o administración del negocio; quien lo instala es Francisco.

## Superficies
- `site/` — página de venta (Persuade).
- `case/` — caso escrito y demos públicas (Experience): `invoiceflow.html`, `replydesk.html`,
  `leadscore.html`, `reportbot.html`, cada una con su medición y su video de 60 s.
- `apps/api/static/index.html` — **panel de operación** (Operate): resumen de métricas, bandeja de
  conversaciones con take-over humano, cola de revisión de facturas, leads con score y borrador,
  base de conocimiento del agente.

## Verdad del producto que el panel debe mostrar
- Volumen y % de conversaciones resueltas sin humano, latencia p50/p95 y costo por conversación.
- Estado de cada conversación (bot / humano / cerrada) con el motivo de la derivación visible.
- Idempotencia y trazabilidad: cada mensaje guarda `wa_message_id`, latencia y costo.
- Facturas con estado automático (`pass`), a revisar (`review`, con el motivo) y aprobadas.
- Leads con score, tier y motivos; el borrador de respuesta ya escrito.
- Eval de cada pieza con su puntaje publicado (30 casos por módulo, mediana y máximo).
- Que el panel distinga lo calculado de lo redactado: toda cifra viene de una cuenta, no del modelo.

## Fuera de alcance del panel
Edición de flujos n8n, facturación del cliente, alta de tenants desde la UI (por API/seed).

## Identidad visual vigente
`site/` define el mundo: papel cálido `#f7f5f0`, tinta `#14181c`, verde `#1f6f5c`, Montserrat para
texto y JetBrains Mono para datos e identificadores. El panel extiende ese mundo con contención de
herramienta, no con un tema nuevo.
