# Módulo 3 — Captación de pacientes (leads)

Convertí consultas crudas de la web en pacientes calificados, con el email de seguimiento
listo para enviar.

> **Correr:** `make up && make demo` · incluye LLM mock, corre sin API keys.

## El problema

Las consultas de nuevos pacientes llegan como mensajes sueltos desde la web. Alguien tiene
que averiguar, decidir si vale la pena, y escribir el seguimiento — normalmente horas
después. Para entonces el paciente ya reservó en otra clínica.

## Qué hace

1. Un **webhook sirve un formulario** (`GET /webhook/lead-gen`).
2. El formulario postea a `POST /webhook/lead-gen/process`.
3. Un **Code node enriquece el lead**: si viene un sitio web, lo busca y lo reduce a texto
   plano (sin APIs externas ni navegador).
4. El **LLM califica el lead** (0-100) usando el mensaje, los datos y el contenido del sitio,
   y devuelve JSON estricto:
   - `score` + `tier` (`HOT` / `WARM` / `COLD`)
   - `reasons[]` — por qué puntuó así
   - `suggested_angle` — cómo encararlo (ej.: "consultó por ortodoncia, mencionar cuotas")
   - `followup_email` — borrador listo para enviar
5. **Chequeos de validación** confirman formato de email, rango de score y tier.
6. Cada lead se **agrega a la Data Table `leads`** (cambiar por el CRM) y el navegador recibe
   el reporte completo.

## Arquitectura

```
 formulario (navegador)
        │  JSON
        ▼
 Webhook ──▶ Build Research Prompt ──▶ Enrich Lead (fetch + limpiar sitio) ──▶ LLM Score
                                                                              │ JSON
                          Create Leads Table ◀── Parse Lead ──▶ Respond report
                                  │
                                  ▼
                            Log Lead (Data Table: leads)
```

## Correr

1. Importá `workflows/lead-gen.json` en n8n y activalo.
2. Abrí `http://<tu-n8n>/webhook/lead-gen` y enviá el formulario.
3. O por consola:

```sh
curl -X POST http://localhost:5678/webhook/lead-gen/process \
  -H 'Content-Type: application/json' \
  -d '{"name":"María Soto","email":"maria@example.com","company":"Estudio Contable",
       "website":"https://example.com",
       "message":"Busco ortodoncia para mi hija, quiero cotizar."}'
```

## Adapters de producción

| El demo usa | Cambiar por |
|---|---|
| Data Table `leads` | HubSpot / Pipedrive / Airtable / el CRM de la clínica |
| Fetch del sitio en un Code node | Clearbit / Apollo para enriquecimiento más rico |
| `followup_email` mostrado en la UI | Nodo de Gmail/Outlook para enviarlo solo |
| Endpoint LLM local | OpenAI / Anthropic / cualquier endpoint compatible OpenAI |

El criterio de calificación es JavaScript plano en el nodo *Parse Lead*: ajustás la rúbrica,
los pesos o agregás tus propios criterios (ej. urgencia, obra social, presupuesto).
