# Módulo 4 — Agente de soporte interno

Un chat que responde las dudas del equipo con los datos del negocio, y **deriva a una
persona** exactamente cuando corresponde.

> **Correr:** `make up && make demo` · incluye LLM mock, corre sin API keys.

## El problema

El personal de la clínica pregunta lo mismo por interno todo el día (precios, obras
sociales, protocolos) y las respuestas se pierden en el chat. Un bot que contesta todo es
peor que nada: necesita saber cuándo pasar a una persona.

## Qué hace

1. Un **webhook sirve una página de chat** (`GET /webhook/support-agent`) — la página guarda
   el historial del lado del cliente, así el agente es **sin estado**.
2. Cada mensaje postea a `POST /webhook/support-agent/chat` con `{session_id, messages[]}`.
3. El **LLM responde solo con los datos del negocio** definidos en el prompt (servicios,
   precios, horarios, convenios, políticas) y devuelve JSON estricto:
   - `reply` — el mensaje
   - `intent` + `sentiment`
   - `handoff` + `handoff_reason`
4. Las **reglas de derivación** están explícitas en el prompt: reclamos, casos fuera del
   alcance, alguien frustrado o pedido explícito de una persona.
5. Cuando se dispara el handoff, la conversación se **registra en la Data Table `handoffs`**
   con el transcript completo, para que una persona la retome con contexto.
6. La página muestra además un **panel de traza** (intent, sentimiento, badge de handoff) —
   útil para demostrar y depurar.

## Arquitectura

```
 página de chat (navegador, guarda historial)
        │  {session_id, messages}
        ▼
 Webhook ──▶ Agent Prompt ──▶ LLM Agent ──▶ Parse Agent Reply ──▶ Respond reply
                                                    │
                                                    ▼
                                        Needs Handoff? ──▶ Create Handoffs Table ──▶ Log Handoff
```

> Es el **mismo patrón de agente** que usa el Módulo 1 (WhatsApp). Acá el canal es webchat;
> cambiar el canal es cambiar el nodo de entrada/salida, no la lógica.

## Correr

1. Importá `workflows/ai-support-agent.json` en n8n y activalo.
2. Abrí `http://<tu-n8n>/webhook/support-agent` y conversá.
3. O por consola:

```sh
curl -X POST http://localhost:5678/webhook/support-agent/chat \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"s-1","messages":[{"role":"user","content":"¿Atienden Fonasa?"}]}'

curl -X POST http://localhost:5678/webhook/support-agent/chat \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"s-1","messages":[{"role":"user","content":"Un paciente dice que le cobramos mal, quiero hablar con un supervisor"}]}'
```

La segunda llamada devuelve `handoff: true` y escribe el transcript en `handoffs`.

## Adapters de producción

| El demo usa | Cambiar por |
|---|---|
| Página de webchat | WhatsApp Cloud API / Telegram / Instagram DM (mismo nodo de agente) |
| Historial en el cliente | Store de sesión (Postgres/Redis) para memoria multi-canal |
| Data Table `handoffs` | Aviso por Slack/email al equipo |
| Datos del negocio en el prompt | RAG sobre la documentación interna |

El prompt del agente es un solo string en el nodo *Agent Prompt*: actualizás los datos del
negocio y las reglas de escalado sin tocar código.
