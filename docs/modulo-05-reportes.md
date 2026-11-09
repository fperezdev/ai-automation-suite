# Módulo 5 — Reportes: de la planilla de ventas al resumen escrito

Pieza **ReportBot**. Entra el CSV de ventas del negocio, sale un resumen escrito donde cada cifra
proviene de una cuenta sobre el archivo. Sin LLM en el camino crítico: el texto se arma con
plantillas y códigos de observación estables, así que el mismo archivo da siempre el mismo reporte
y el costo por reporte es cero.

## Qué entra y qué sale

- **Entra**: un CSV (separador `;`, `,` o tab), cabeceras en español o inglés
  (`fecha/date`, `monto/amount`, `categoría/category`), fechas ISO o `dd/mm/aaaa`, montos en
  formato chileno (`$1.240.000`), con decimales (`1.234,56`) o planos.
- **Sale**: total del período, total del período anterior y variación %, ticket promedio, ventas por
  día, reparto y variación por categoría, mejor y peor día, y una lista de observaciones.
- **Formatos de salida**: panel operable (lista + detalle), texto para copiar y `.md` descargable
  (`GET /api/reports/{id}.md`).

## Cómo se calculan las cifras

1. `parse_csv(texto)` → filas `{date, amount, category, label}`. Las filas sin fecha o monto válido
   se descartan (se cuentan, no rompen el reporte).
2. `aggregate(rows)` parte el rango en **dos mitades iguales**: la segunda mitad es el período del
   reporte, la primera es la base de comparación. Si la primera mitad no tiene ventas, no se inventa
   una variación: se emite `no_previous`.
3. `compose(metrics, nombre_negocio)` → texto. Cada número sale de `metrics`; el nombre del negocio
   viene de `tenant.config.negocio` (fallback `config.name` → slug).
4. `report(texto_csv, nombre)` encadena las tres y devuelve el registro completo.

`money()` formatea en chileno (`. ` de miles, `,` decimal), `pct()` con signo, `pct_abs()` para que
una baja se lea “Baja 34,3%” y no “+”.

## Observaciones (códigos estables)

Cada observación tiene código y umbral escrito, para poder discutir la regla y ajustarla:

| Código | Cuándo aparece |
|---|---|
| `total_up` / `total_down` / `total_flat` | variación del total contra el período anterior (±5%) |
| `no_previous` | no hay período anterior con ventas |
| `top_category` | categoría de mayor venta y su peso |
| `category_drop` / `category_jump` | variación fuerte de una categoría con peso suficiente |
| `best_day` / `worst_day` | día de mayor y menor venta del período |
| `concentration` | una categoría supera el 60% del total |
| `low_volume` | pocos movimientos en el período |
| `refunds` | hay montos negativos (se cuentan con `metrics.negatives`) |
| `negative_total` | el período cierra en negativo |

La severidad (`good`, `warn`, `down`) solo define el color en el panel; el texto no cambia.

## Persistencia e idempotencia

Tabla **`sales_reports`** (migración `006_reportbot.sql`). Se llama así porque `reports` ya existía
con el esquema de ReplyDesk; la colisión se detectó al aplicar la migración.

```sql
sales_reports(
  id uuid PK, tenant_id uuid → tenants, file_name, source_sha256,
  period_start date, period_end date, rows_count int,
  total numeric(14,2), prev_total numeric(14,2), delta_pct numeric(6,1),
  currency text default 'CLP', metrics jsonb, text, created_at
)
UNIQUE (tenant_id, source_sha256)          -- re-subir el mismo archivo no duplica
```

`POST /api/reports/upload` responde `duplicate_file: true` cuando el `sha256` ya está registrado
para ese tenant y devuelve el reporte existente.

## Endpoints

- `POST /api/reports/upload` — multipart `tenant`, `file`, `business` (opcional).
- `GET /api/reports?tenant=&limit=`
- `GET /api/reports/{id}?tenant=`
- `GET /api/reports/{id}.md`

## Set de prueba y eval

- `scripts/make_report_golden.py` genera **30 planillas** (`samples/reportbot/rep-001..030-*.csv`) y
  su `golden.json`: meses completos, caídas y crecimientos fuertes, períodos planos, primera
  planilla sin historial, una sola categoría, devoluciones en negativo, meses en rojo, pocos
  movimientos, días vacíos, fin de semana concentrado, filas inválidas mezcladas, tres separadores
  y dos formatos de fecha.
- `apps/api/eval_reportbot.py` mide, por planilla: total, período anterior y variación (tolerancia
  0,01), categoría principal, códigos `must`/`absent` y presencia del total con formato chileno en el
  texto; además latencia p50 y máximo. Cada corrida queda en `eval_runs`.

Correr:

```bash
docker cp samples/reportbot suite-api:/samples/
docker exec suite-api python eval_reportbot.py --samples /samples/reportbot
# sin base, solo CPU:
python3 apps/api/eval_reportbot.py --no-db
```

**Resultado (2026-11-09):** 30/30 planillas, cifras 100%, categoría principal 100%, observaciones
100%, texto 100%, p50 **0,6 ms**, máximo **2,8 ms**, costo **US$ 0** por reporte.

## Qué no hace

- No pronostica ni detecta estacionalidad.
- No calcula IVA ni cruza con facturas: usa el monto tal como viene en el archivo.
- La comparación es contra la primera mitad del rango de la planilla, no contra el mes anterior del
  calendario: para comparar octubre completo contra septiembre completo hay que subir ambos meses.

Un LLM puede reescribir el resumen después, pero las cifras quedan fijas por `metrics`: el modelo
redacta, no calcula.

## Página de caso

`case/reportbot.html` — captura del panel (`case/assets/reportbot-panel.png`), tabla de métricas
medidas, ejemplo del texto real de la demo y la sección de límites.
