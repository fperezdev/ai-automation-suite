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

---

## La misma pieza dentro de la suite (InvoiceFlow)

El demo de arriba usa un LLM para extraer. En el producto, la extracción es
**determinista**: el texto del PDF se parsea con reglas, sin modelo en el camino crítico.
Así el resultado es reproducible, medible y no cuesta tokens por factura.

- `apps/api/invoiceflow.py` — funciones puras `pdf_text()` → `evaluate_text()` → campos + estado.
  Se pueden correr sin base de datos, que es lo que usa la evaluación.
- `db/migrations/004_invoiceflow.sql` — maestro de proveedores por tenant (`vendors`), campos
  fiscales en `invoices` (RUT, emisión, neto, IVA, líneas, motivos, correcciones) e
  idempotencia por `sha256` del archivo (subir dos veces el mismo PDF no duplica).
- `POST /api/invoices/upload` → lee el PDF, extrae, valida contra el maestro y el historial
  (folio duplicado) y deja la factura en `pass` o `review` con los motivos.
- `PATCH /api/invoices/{id}` → aprobar, rechazar o devolver a revisión; guarda quién lo hizo
  y las correcciones de campos como `corrections`.
- Panel: cola con filtros, detalle de campos extraídos (el campo culpable en rojo), motivos
  con código y texto, líneas del documento, texto leído del PDF y exportación a CSV.

### Reglas

| Código | Qué detecta |
|---|---|
| `missing_field` | Falta un campo obligatorio (proveedor, folio, fecha, total) |
| `invalid_rut` | RUT con dígito verificador incorrecto |
| `unknown_vendor` | RUT válido pero fuera del maestro de proveedores |
| `total_mismatch` | Neto + IVA no cuadra con el total (tolerancia 1 CLP / 0,02 USD) |
| `iva_mismatch` | El IVA no es el 19% del neto |
| `lines_mismatch` | La suma de las líneas no cuadra con el neto |
| `duplicate_folio` | Ese folio ya existe para el mismo proveedor |
| `date_out_of_range` | Fecha fuera de la ventana aceptada |
| `total_over_cap` | Monto sobre el tope configurado del negocio (8.000.000 por defecto) |
| `no_text` | PDF escaneado o protegido: no hay texto que leer |

### Evaluación medida

Set dorado de 12 facturas chilenas (`scripts/make_invoice_golden.py` → `samples/invoiceflow/`,
con `golden.json`): 2 limpias y 10 con un defecto distinto cada una, de modo que cada motivo
tenga su caso.

```
docker cp apps/api/eval_invoiceflow.py suite-api:/app/
docker cp samples/invoiceflow suite-api:/samples/
docker exec suite-api python /app/eval_invoiceflow.py --samples /samples/invoiceflow
```

Resultado del último run (queda registrado en `eval_runs`):

| Métrica | Valor |
|---|---|
| Casos | 12 / 12 correctos |
| Precisión por campo (proveedor, folio, fecha, neto, IVA, total, moneda) | 100% |
| Estado (pass / review) | 100% |
| Precisión y recall de motivos | 100% |
| Latencia de extracción | p50 2,8 ms · máx 80 ms |

