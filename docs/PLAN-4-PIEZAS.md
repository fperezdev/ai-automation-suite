# Plan — 4 piezas con nivel de producto

**Decisión (2026-11-09):** el portfolio no se arma con "4 módulos de una suite" sino con
**4 piezas con nombre propio**, cada una con página de caso y demo viva. Sigue siendo
**un solo repo** (`ai-automation-suite`), sin repos chicos.

> Esto **reemplaza** a `docs/PLAN-PRODUCCION.md` en la parte de "un solo proyecto, borrar los
> otros 3": ese plan apostaba a un único caso (clínica). La línea vigente es 4 piezas
> productizadas, con la clínica como *caso de referencia* de la pieza 1.

## Benchmark que manda (2026-11-09)

JOSE (Chile, USD 35/h, 32 reseñas) muestra 4 piezas con nombre propio: Bookify, MediAPI,
ShopMaster, landing pizzería. Martin B. (14 reseñas) gana con **caso + métrica**
("70% de reducción de tiempos"). Nadie del filtro IA muestra un agente real funcionando.

Conclusión: **nombre propio + caso con números + demo que se toca en 60 s**, en un repo.

## Las 4 piezas

| Pieza | Qué es | Estado hoy | Página |
|---|---|---|---|
| **InvoiceFlow** | factura PDF → extracción → validación → registro + cola de revisión | módulo 2 funcionando, sin persistencia | `/invoiceflow` |
| **ReplyDesk** | agente WhatsApp con KB del negocio, bandeja y derivación a humano | **productizada y medida**: reglas + LLM, webhook firmado e idempotente, take-over, eval 40/40, página de caso | `case/replydesk.html` |
| **LeadScore** | captación → scoring con motivos → borrador de seguimiento | módulo 3 funcionando | `/leadscore` |
| **ReportBot** | planilla → variaciones → resumen con LLM → mail/Telegram | **no existe** | `/reportbot` |

## Qué significa "nivel de producto" (checklist común)

Se aplica a las 4, sin excepción. Es lo que separa esto de un demo:

1. **Datos que persisten**: Postgres (ya en `docker-compose.yml`), migraciones en el repo,
   historial por contacto/factura/lead. Nada de Data Tables de n8n en el camino crítico.
2. **Tenant**: `tenant_id` en cada tabla y un registro de negocios. Un mismo stack sirve a
   varios clientes → es el argumento de venta (white-label) y evita "esto es para una clínica".
3. **Estados explícitos**: cada registro tiene ciclo (`nuevo → en_proceso → resuelto/revisión`),
   visible en el panel. El humano puede tomar el control y el bot se calla.
4. **Panel operable** (superficie `Operate` de la skill `impeccable`): bandeja/cola, detalle,
   acciones, y edición de configuración del negocio (precios, horarios, FAQ) sin tocar n8n.
5. **Métricas del producto** en el panel: volumen/día, % resuelto sin humano, latencia p50/p95,
   costo por conversación. Son las que después van al caso.
6. **Robustez de integración**: firma `X-Hub-Signature-256`, idempotencia por `message.id`,
   timeouts, reintentos con backoff, fallback con mensaje humano, logs estructurados.
7. **Calidad medida**: golden set de 30–50 preguntas por pieza, script de eval, % publicado en
   CI y en el badge del README.
8. **Se levanta solo**: `docker compose up` → todo arriba; `.env.example`; runbook de 1 página;
   tabla de costos mensuales reales.
9. **Caso escrito** (formato Martin): Contexto y Problema → qué se construyó → decisiones →
   **números medidos** → costo → qué haría distinto. Sin métricas inventadas: se mide la demo.
10. **Video de 60 s** por pieza + captura grande al inicio del README.

## Fases

## Estado (2026-11-09)

- **F1 — Base compartida: hecha.** Postgres 16 multi-tenant (puerto 5544), `tenant_id` en todas las
  tablas, migraciones al arrancar, panel `Operate` en `localhost:8090` con métricas medidas
  (vistas `v_conversations_daily` y `v_cost`), bandeja con take-over, facturas, leads y KB editable.
- **F2 — ReplyDesk: hecha y medida.** `replydesk.py` (reglas deterministas → LLM con la KB del
  tenant → JSON con `handoff`), `webhooks.py` (challenge de Meta, HMAC SHA-256, idempotencia por
  `wa_message_id`, `/api/simulate`), `eval_replydesk.py` con **40 preguntas → 40/40**, p50 1,6 s,
  US$ 0,00004 por pregunta. Página de caso con chat funcional en `case/replydesk.html`.
  Video de 60 s hecho: `docs/video/replydesk-60s.mp4` (voz clonada con fal.ai).
- Siguiente: **F3 — InvoiceFlow** (cola de revisión con estados, aprobación, export, métricas).

## Fases (plan original)
: migraciones Postgres, modelo `tenant`, panel shell con
  bandeja y métricas, `.env.example`, runbook. Sin esto las demás fases duplican trabajo.
- **F2 — ReplyDesk** (2–3 días): persistencia de conversaciones + historial, handoff con motivo,
  take-over, KB editable, eval de 30 preguntas. Es la pieza que más se vende (6/14 avisos).
- **F3 — InvoiceFlow** (1–2 días): cola de revisión con estados, aprobación humana, export,
  métricas de auto-aprobadas y tiempo medio.
- **F4 — LeadScore** (1 día): motivos del score visibles, dedupe, cola de seguimiento, export CRM.
- **F5 — ReportBot** (1 día): pieza nueva, la más simple y la que cierra el circuito de reseñas
  (tickets de USD 50–150, entrega en 2–4 días).
- **F6 — Publicación**: 4 páginas de caso en el sitio, capturas, videos 60 s, badge de eval,
  item en el portfolio de Workana y de Upwork.

## Lo que NO se va a fingir

- Nada de "ahorré 40 horas": las cifras salen de medir la demo (latencia, % auto-resuelto,
  tiempo por factura) y se declaran como medición de la demo, no de un cliente.
- La clínica es **caso de referencia declarado**, no un cliente con contrato.
- Si una pieza no llega a nivel de producto en el tiempo previsto, se publica igual con su
  estado real (beta) en la página del caso.
