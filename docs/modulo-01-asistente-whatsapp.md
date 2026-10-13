# Módulo 1 — Asistente de WhatsApp con RAG

El asistente que responde el WhatsApp de la clínica 24/7: horarios, precios, ubicación,
cómo agendar, convenios — **desde la información real de la clínica** — y deriva a una
persona cuando corresponde.

> **Correr:** `make up && make demo` · incluye LLM mock, corre sin API keys.

## El problema

Una clínica chica contesta los mismos mensajes todo el día a mano y pierde los que
llegan de noche. Un chatbot genérico que improvisa precios o consejos clínicos es **peor
que nada**: el asistente debe responder **solo** con la información real de la clínica y
saber **cuándo** derivar a un humano.

## Qué hace

1. **Canal WhatsApp Cloud API.** Una sola URL — `https://<host>/webhook/whatsapp-dental` —
   atiende los dos métodos de Meta: `GET` hace la verificación (devuelve `hub.challenge`)
   y `POST` recibe los mensajes. El mismo `POST` acepta además un payload de prueba
   (`{from, text}` o `{from, messages[]}`), así el bot se puede ejercitar sin credenciales
   de Meta.
2. **RAG.** Un Code node (*Retrieve FAQ*) corre una recuperación **TF-IDF** (en español,
   normalizando acentos y stopwords) sobre la base de conocimiento de la clínica y se
   queda con los fragmentos más relevantes.
3. **Respuesta fundamentada.** Los fragmentos recuperados entran como **contexto** en el
   prompt; el LLM responde **solo** con eso y devuelve JSON estricto
   (`reply`, `intent`, `sentiment`, `handoff`, `handoff_reason`).
4. **Derivación a humano.** Urgencias fuera de horario, reclamos o pedido explícito de una
   persona → `handoff: true` y el transcript se registra en la Data Table `wa_handoffs`.
5. **Guarda de tono determinista.** Un normalizador elimina cualquier voseo
   (*tenés/tenís*) que el modelo cuele.

## Arquitectura

```
WhatsApp Cloud API ──▶ WhatsApp Webhook (GET verify + POST messages)
                              │
                              ▼
                       Parse Incoming ──▶ Retrieve FAQ (RAG, TF-IDF)
                              │                    │
                              │                    ▼
                              └──────────▶ Build Prompt (contexto + historial)
                                                   │
                                                   ▼
                                              LLM Agent ──▶ Parse Reply
                                                               │
                                        ┌──────────────────────┴───────────────┐
                                        ▼                                      ▼
                             Send via Graph API / Reply              Needs Handoff? ─▶ Log wa_handoffs
```

El RAG **no** usa vector DB ni embeddings: TF-IDF + coseno en un Code node. Para una base
chica es exacto y sin dependencias; con una base grande se cambia esa pieza por embeddings
+ pgvector/Chroma sin tocar el resto.

## Base de conocimiento

Siete fragmentos dentro del nodo *Retrieve FAQ (RAG)* (el workflow es autocontenido):
horarios · precios · ubicación · agendar/reagendar · convenios y pagos · urgencias · servicios.

## Correr

1. Importá `workflows/whatsapp-dental-agent.json` en n8n y activalo.
2. Una consulta desde la terminal:

```sh
curl -X POST http://localhost:5678/webhook/whatsapp-dental \
  -H 'Content-Type: application/json' \
  -d '{"from":"56911110001","text":"hola, cuánto cuesta una limpieza dental?"}'
```

3. Suite completa de 3 conversaciones + capturas estilo WhatsApp:

```sh
python scripts/run_whatsapp_tests.py
python scripts/make_whatsapp_captures.py
```

Capturas listas en [`../modules/01-asistente-whatsapp/capturas/`](../modules/01-asistente-whatsapp/capturas/).

## Conectar el canal real

Definí dos variables de entorno y activá el nodo *Send via Graph API*:

| Env var | Valor |
|---|---|
| `WHATSAPP_TOKEN` | token de acceso de Meta |
| `WHATSAPP_PHONE_NUMBER_ID` | ID del número de Cloud API |

En Meta, el webhook apunta a `https://<tu-host>/webhook/whatsapp-dental` (misma URL para
GET y POST). Para un demo alcanza el **número de prueba** gratuito de Cloud API — sin SIM.

## Adapters de producción

| El demo usa | Cambiar por |
|---|---|
| Manejo por mensaje sin estado | Un store de sesión (Postgres/Redis) para memoria multi-turno |
| Data Table `wa_handoffs` | Aviso por Slack/email a la recepción de la clínica |
| TF-IDF en un Code node | Vector store (pgvector, Qdrant) con embeddings |
| KB dentro del nodo | RAG sobre el sitio, la lista de precios y las FAQ de la clínica |
