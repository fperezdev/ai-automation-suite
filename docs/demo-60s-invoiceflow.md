# Demo de 60 s — InvoiceFlow

Video: `docs/video/invoiceflow-60s.mp4` (61,4 s, 1600×900, 30 fps) · publicado en
`case/assets/invoiceflow-60s.mp4` y embebido en la página de caso.
Voz: clon `francisco` (fal.ai / MiniMax hd, `--speed 1.1`), ~$0,10.
Narración literal: `docs/video/invoiceflow-60s.txt`.

## Toma por toma

| Tiempo | Qué se ve | Qué se dice |
|---|---|---|
| 0:00–0:11 | Panel, vista **Facturas**: resumen (7 recibidas, 71% sin intervención, 2 por revisar), cola con las 7 facturas del seed | «Una pyme recibe facturas de insumos todos los meses, y alguien las tipea a mano. Invoice Flow las lee, las valida, y deja sólo las dudosas para revisar.» |
| 0:11–0:24 | Filtro **En revisión**: dos facturas, cada una con su motivo escrito | «El corazón no es un modelo de lenguaje. Son reglas. Del PDF se extraen proveedor, folio, fecha, neto, IVA y total.» |
| 0:24–0:37 | **Detalle** de la factura en revisión: campos extraídos, RUT, neto $167.252, IVA $31.778, total $199.030, y el motivo con los números | «Después se valida el RUT chileno con su dígito verificador, el IVA al diecinueve por ciento, la suma de las líneas y el cuadre del total.» |
| 0:37–0:47 | Filtro **Aprobadas**: las registradas por la persona, botón Exportar CSV a la vista | «Si todo cuadra, la factura queda automática y se registra sola. Si algo no cuadra, entra a la cola con el motivo escrito: acá la suma de las líneas no cuadra con el neto, y el panel muestra el número exacto.» |
| 0:47–1:01 | Página de caso, sección **Resultados medidos**: 30/30, campos 100%, 2,9 ms | «La persona revisa sólo esas, aprueba o devuelve, y exporta el mes a CSV para el contador. Se midió sobre un set de treinta facturas: treinta correctas, siete campos al cien por ciento, y menos de tres milisegundos por documento. Cero tokens, cero costo por factura, y el mismo resultado siempre. Eso se puede auditar, y por eso la cola se puede confiar.» |

## Capturas

`docs/video/shots/s1_panel.png` … `s5_resultados.png` (1600×900), tomadas del panel real con el
tenant `clinica-sonrisa-nunoa` re-sembrado antes de grabar. Para regrabar: re-sembrar
(`docker exec suite-api python seed.py`), capturar las 5 tomas y volver a montar con los mismos
tiempos; si cambia el largo de la voz, recalcular offsets (`offset_n = Σduraciones − 0,3·n`) y
dejar ≥1,5 s de cola al final.

## Montaje

`xfade` 0,3 s entre tomas, 1600×900, `-crf 20`, audio AAC 160k, `-shortest`. Duraciones usadas:
11,3 / 13,3 / 14,3 / 11,3 / 13,9 s (total 61,4 s = voz).

## Verificación hecha

- `ffprobe`: 61,400 s, 1600×900, 30 fps, audio 61,4 s (no se corta la última frase).
- OCR por toma (`tesseract -l spa`): aparecen `Insumos`, `revisión`, `motivo`, `199.030`, `167.252`,
  `Exportar` y en la última `30/30` y `2,9`.
- Hoja de contactos: 5 tomas distintas, sin frames negros.
