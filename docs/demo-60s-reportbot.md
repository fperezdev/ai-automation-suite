# Video 60 s — ReportBot (`reportbot-60s.mp4`)

- Archivo: `docs/video/reportbot-60s.mp4` (copia publicada en `case/assets/reportbot-60s.mp4`)
- Duración: **62,9 s** · 1600×900 · 30 fps · 1,9 MB · voz clonada (`francisco`, `--speed 1.1`)
- Narración literal: `docs/video/reportbot-60s.txt`
- Capturas: `docs/video/shots/rb1_lista.png`, `rb2_total.png`, `rb3_categorias.png`, `rb4_texto.png`

## Toma por toma

| Tiempo | Qué se ve | Qué se dice |
|---|---|---|
| 0:00–0:12 | Vista **Reportes**: zona de carga, lista de planillas procesadas | «todos los meses, el mismo trabajo… a mano» · «se sube el archivo y el reporte queda armado» |
| 0:12–0:29 | Reporte de octubre: **$6.821.000** contra **$5.663.000** (+20,4%), KPIs, ventas por día | «no adivina nada: lee la planilla, suma» · «acepta el archivo como venga» · «total, comparación y variación» |
| 0:29–0:46 | Reparto por categoría, mejor y peor día, observaciones con severidad | «ticket promedio, reparto por categoría» · «qué categoría explica el crecimiento, concentración, devoluciones» |
| 0:46–1:02 | Resumen escrito completo con **Copiar resumen** / **Descargar .md** | «cada observación tiene su regla escrita» · «treinta planillas exactas, medio milisegundo, sin costo» |

## Cómo se armó

```bash
vc say --file reportbot-60s.txt --name francisco --model hd --speed 1.1 --sample-rate 32000 --out _rb_voz.mp3
# 4 tomas 1600×900, xfade 0,3 s en 12,7 / 29,4 / 46,1 s
```

Los números en pantalla son los del reporte sembrado en la demo (`ventas-octubre-2026.csv`), los
mismos que devuelve `GET /api/reports`.
