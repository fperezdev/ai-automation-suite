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

## La misma pieza dentro de la suite (LeadScore)

El demo de arriba vive en n8n y usa un LLM para la rúbrica. Dentro de la suite, la captación
está escrita como **funciones puras** en `apps/api/leadscore.py`: mismo texto de entrada, mismo
puntaje, sin red y sin tokens. Cada motivo es un código estable con puntos, y el panel muestra
la suma completa.

### Qué mira cada regla

| Código | Puntos | Cuándo suma |
|---|---|---|
| `service_match` | +30 | La consulta nombra un servicio que el negocio vende (ortodoncia, limpieza, implantes…) |
| `urgency` | +20 | Pide atención urgente o describe un problema que no espera (`fractura`, `diente`, `dolor`, `hoy`, `urgente`) |
| `phone_ok` | +10 | Deja un teléfono chileno con largo plausible |
| `email_ok` | +10 | Deja un email de dominio real |
| `budget` | +10 | Menciona presupuesto, Isapre, Fonasa o pago en cuotas |
| `price_question` | +10 | Pregunta cuánto sale: es intención comercial, no charla |
| `message_detail` | +10 | Escribe más que un saludo: hay algo que responder |
| `time_given` | +5 | Dice cuándo puede atenderse |
| `returning` | +5 | Ya fue paciente del negocio |
| `invalid_email` | −10 | Email con formato imposible |
| `no_contact` | −15 | Sin email ni teléfono: no hay por dónde responder |
| `out_of_scope` | −30 | Pide algo que el negocio no hace |
| `spam` | −50 | Dominio desechable, links masivos o mensaje de bot |

Tiers: **HOT ≥ 70**, **WARM ≥ 40**, **COLD < 40**. Del tier sale `next_action_kind` y
`next_action_at`; la cola ordena por score y por vencimiento.

### Dedupe

`dedupe_key` = email normalizado (minúsculas) o, si no hay email, teléfono reducido a dígitos,
siempre por tenant. Si la clave ya existe, el lead nuevo se guarda con `duplicate_of` apuntando al
original: no se vuelve a contactar y las métricas lo cuentan aparte (`duplicates`).

### Endpoints

| Método | Ruta | Para qué |
|---|---|---|
| `GET` | `/api/leads?tenant=&status=&tier=&limit=` | cola con score, tier, motivos y próxima acción |
| `POST` | `/api/leads` | alta de consulta: puntúa, deduplica y guarda |
| `GET` | `/api/leads/export.csv?tenant=` | exportación para la planilla del negocio |
| `PATCH` | `/api/leads/{id}` | cambio de estado: `new`, `contacted`, `qualified`, `booked`, `discarded` |

### Cómo correr el eval

```sh
python scripts/make_lead_golden.py                      # 30 consultas + golden.json
docker cp samples/leadscore suite-api:/samples/
docker exec suite-api python eval_leadscore.py --samples /samples/leadscore
```

### Números medidos

| Métrica | Valor |
|---|---|
| Consultas con tier correcto | **30 / 30** |
| Score dentro del rango esperado | **30 / 30** |
| Motivos: precisión / cobertura | **100% / 100%** |
| Duplicados reconocidos | **100%** |
| Latencia | p50 **0,05 ms** · máx **0,23 ms** |
| Costo por consulta | **US$ 0** |
