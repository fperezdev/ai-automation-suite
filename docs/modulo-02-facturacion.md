# Módulo 2 — Automatización de facturas

Convertí una carpeta de facturas PDF en un libro de gastos validado, sin tipear nada.

> **Correr:** `make up && make demo` · incluye LLM mock, corre sin API keys.

## El problema

La clínica recibe facturas de insumos (guantes, anestesia, material de restauración…) como
PDF. Alguien tiene que abrir cada una, copiar número, fecha, proveedor, montos e impuestos
a una planilla, y rezar que ningún total esté mal. Lento, aburrido y propenso a errores.

## Qué hace

1. Un **webhook sirve una página de carga** (`GET /webhook/doc-automation`).
2. El PDF se postea a `POST /webhook/doc-automation/process`.
3. **Extract from File** saca el texto crudo del PDF.
4. El **LLM extrae los campos estructurados** (número, fecha, proveedor, moneda, líneas,
   subtotal, impuesto, total) y devuelve JSON estricto.
5. Un **Code node corre reglas de validación**:
   - campos requeridos presentes
   - formato de fecha `YYYY-MM-DD`
   - la suma de líneas coincide con el subtotal
   - subtotal + impuesto coincide con el total
6. Cada documento se **agrega al libro `invoices`** (Data Table de n8n; cambiar por Google
   Sheets, Airtable o el sistema de la clínica).
7. El navegador recibe un reporte con badge **`PASS` / `REVIEW`** y los chequeos fallidos
   resaltados.

`REVIEW` = "acá conviene que mire un humano" — justo las facturas que querés que salten:
totales que no cuadran, campos faltantes, fechas mal.

## Arquitectura

```
 página de carga (navegador)
        │  PDF multipart
        ▼
 Webhook ──▶ Extract from File ──▶ Build LLM Request ──▶ LLM (HTTP)
                                                          │ JSON
                                                          ▼
                        Create Data Table ◀── Parse & Validate ──▶ Respond report
                                │
                                ▼
                          Log to Ledger (Data Table: invoices)
```

## Correr

1. Importá `workflows/doc-automation.json` en n8n y activalo.
2. Abrí `http://<tu-n8n>/webhook/doc-automation` y subí una de las facturas de ejemplo.
3. O por consola:

```sh
curl -F "data=@samples/invoice_001.pdf;type=application/pdf" \
     http://localhost:5678/webhook/doc-automation/process
```

Los PDF de ejemplo: `invoice_001/002` → limpias (`PASS`); `invoice_003` → **con un total
descuadrado a propósito** (`REVIEW`) para mostrar la validación.

## Adapters de producción

| El demo usa | Cambiar por |
|---|---|
| Data Table `invoices` | Google Sheets / Airtable / Postgres / el ERP de la clínica |
| Página de carga | Trigger IMAP (bandeja de entrada) o watcher de carpeta en Drive |
| Endpoint LLM local | OpenAI / Anthropic / cualquier endpoint compatible OpenAI |

Las reglas son JavaScript plano en el nodo *Parse & Validate*: se extienden con chequeos
propios (proveedor duplicado, orden de compra, topes de gasto).
