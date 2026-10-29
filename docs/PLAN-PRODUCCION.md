# Plan — un solo proyecto, en producción

**Producto:** sistema de atención con IA para la Clínica Dental Sonrisa Ñuñoa.
**Repo:** `ai-automation-suite` (se renombra cuando la web nueva esté publicada).
**Regla de diseño:** toda superficie UI/UX se trabaja con la skill `impeccable`
(`~/.hermes/profiles/freelance/skills/design/impeccable`), no es opcional.

## 0. Alcance

Un solo proyecto, un solo repo, una sola web, un solo workflow en producción.
La clínica deja de ser "un demo del módulo 1" y pasa a ser el producto completo.
Todo lo demás se elimina, no se archiva "por si acaso".

## 1. Fase 0 — Consolidación y borrado

### Qué se elimina

| Dónde | Qué | Acción |
|---|---|---|
| GitHub | repo `fperezdev/ai-automation-demos` (ya archivado, 3 workflows) | `gh repo delete` |
| n8n | `demoDocAutomat01` (invoice) | desactivar → backup JSON → borrar |
| n8n | `demoLeadGen00001` (lead gen) | desactivar → backup JSON → borrar |
| n8n | `demoSupportAgent1` (soporte webchat) | desactivar → backup JSON → borrar |
| n8n | `demoWhatsAppDental1` (duplicado del asistente) | borrar; el bueno es el de producción |
| n8n | `Asistente Whatsapp - Veterinaria Huellitas` | backup → borrar |
| repo | `modules/02-facturacion/`, `03-captacion/`, `04-soporte/` | borrar |
| repo | `workflows/doc-automation.json`, `lead-gen.json`, `ai-support-agent.json` | borrar |
| repo | menciones a los 4 módulos en `README.md`, `PORTFOLIO.md`, `site/index.html` | reescribir |
| Upwork | portfolio con 3 items | dejar 1 (lo hace Francisco en la web) |
| docs | `PLAN.md` del negocio y `profiles/freelance.md` | actualizar a "un caso completo" |

### Criterio de aceptación
- `grep -ri` en el repo: cero referencias a invoice / lead gen / support agent como demos.
- n8n: un solo workflow activo (el de la clínica).
- `gh repo list` sin repos de demos.
- Capturas viejas (`case/portfolio/03-conversaciones.png`, `04-urgencia-handoff.png`) borradas o reemplazadas por capturas reales del producto final.

## 2. Arquitectura objetivo

```
apps/web        sitio público + chat + panel del negocio (Next.js/TS)
apps/api        webhook de WhatsApp, agenda, métricas (TS)
packages/db     Postgres + migraciones (contactos, conversaciones, mensajes,
                citas, handoffs, kb, eventos, métricas)
orchestration   workflows n8n exportados en JSON + entrypoint reproducible
evals           golden set de preguntas + script de exactitud/alucinaciones
docs            caso de estudio, arquitectura, runbook, costos
```

- **n8n** orquesta: recibe el webhook, llama al LLM, decide handoff, dispara recordatorios.
- **Postgres** es la fuente de verdad (no Data Tables).
- **Caddy + dominio propio** delante de todo, HTTPS real.
- Un `docker compose up` levanta el stack completo.

## 3. Fases

### F1 — Reparar el asistente (bloqueante)
Hoy `POST /webhook/whatsapp-dental` devuelve `{"reply": null, "ack": true}`: la demo
pública está muda.

- Diagnosticar el nodo LLM y el fallback.
- Firma `X-Hub-Signature-256` del webhook de Meta (rechazar payloads sin firma).
- Idempotencia por `message.id` (Meta reintenta; hoy respondería dos veces).
- Timeouts, reintentos y respuesta de fallback con mensaje humano.
- Token permanente de sistema + app secret fuera del repo.
- **Aceptación:** mensaje real de WhatsApp recibe respuesta correcta en < 5 s; payload duplicado no genera doble respuesta; firma inválida devuelve 403.

### F2 — Datos y memoria
- Postgres + migraciones.
- Historial por contacto: el bot deja de responder cada mensaje aislado.
- RAG sobre la base de conocimiento real (precios, horarios, servicios, convenios), con cita de la fuente.
- **Aceptación:** conversación de 5 turnos mantiene contexto; toda respuesta factual traza a una fila de la KB.

### F3 — Agenda
- Disponibilidad real, propuesta de horas, confirmación, reagendar y cancelar.
- Recordatorio 24 h antes con plantilla aprobada por Meta.
- **Aceptación:** cita creada por WhatsApp aparece en la agenda del panel y dispara recordatorio.

### F4 — Panel del negocio (superficie `Operate`)
- Bandeja de conversaciones con take-over (pausa el bot al intervenir un humano).
- Leads, citas del día, métricas básicas.
- Editor de precios, horarios y FAQ sin tocar n8n.
- **Aceptación:** recepción puede tomar una conversación y el bot se calla; cambio de precio se refleja en la siguiente respuesta.

### F5 — Calidad y operación
- Golden set de 30–50 preguntas con respuesta esperada; script que mide exactitud y detecta alucinaciones.
- CI: tests + eval en cada push.
- Logs estructurados, métricas (conversaciones/día, % resuelto sin humano, latencia, costo por conversación), alerta si el webhook cae.
- Backups diarios de Postgres.
- **Aceptación:** eval corre en CI y publica el porcentaje; alerta probada con el webhook apagado.

### F6 — Producción real (requiere a Francisco)
- Chip → número verificado en WhatsApp Cloud API (Meta Business, nombre visible, método de pago).
- Dominio propio + HTTPS.
- Aviso de asistente virtual, política de privacidad, retención de datos, opt-out (datos de salud: Ley 21.719).
- **Aceptación:** un número público real contesta, con aviso de IA y privacidad publicados.

### F7 — Portfolio
- Caso de estudio: problema → arquitectura → decisiones → números medidos → costo mensual → qué haría distinto.
- Un solo item en el portfolio de Upwork con link a la demo en vivo.
- Video one-way de 90 s (cero llamadas).
- **Aceptación:** un cliente puede tocar el producto desde el portfolio en dos clics.

## 4. Diseño

Toda pantalla (sitio, chat, panel, emails de plantilla) pasa por `impeccable`:
`PRODUCT.md` + `DESIGN.md` primero, después `context`, `critique`, `polish`.
Nada de plantillas genéricas ni "que se vea moderno": dirección visual con criterio,
modo `Persuade` para el sitio público y `Operate` para el panel.

## 5. Lo que necesito de Francisco

1. **Chip:** operador, prepago o contrato, si el número ya se usó en WhatsApp, y si existe Meta Business verificado.
2. **Dominio:** ¿usamos uno nuevo para el caso (ej. `sonrisanunoa.cl`) o un subdominio del portafolio?
3. **Upwork:** bajar el portfolio a 1 item (yo dejo el texto, la web la tocás tú).
4. **Borrados irreversibles:** confirmar `gh repo delete` y el borrado de workflows en n8n.

## 6. Riesgos

- **Número en Cloud API:** el número queda inutilizable en la app normal de WhatsApp.
- **Datos de salud:** son categoría sensible; sin política y consentimiento el producto no es vendible.
- **Costo de plantillas:** los recordatorios iniciados por el negocio se cobran por conversación; verificar tarifa vigente para Chile antes de prometer precios.
- **Alcance:** cada módulo extra que aparezca (facturas, etc.) vuelve a fragmentar el proyecto. Lo que no sea la clínica, no entra.

## 7. Orden de ejecución

F0 (borrado) → F1 (reparar) → F2 (datos) → F3 (agenda) → F4 (panel) → F5 (calidad) → F6 (producción) → F7 (portfolio).

Primera tarea concreta: F0 + F1 en la misma sesión, porque la demo rota no puede seguir publicada.
