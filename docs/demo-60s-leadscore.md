# Video 60 s — LeadScore (`leadscore-60s.mp4`)

- Archivo: `docs/video/leadscore-60s.mp4` (copia publicada en `case/assets/leadscore-60s.mp4`)
- Duración: **64,1 s** · 1600×900 · 30 fps · 2,0 MB · voz clonada (`francisco`, `--speed 1.1`)
- Narración literal: `docs/video/leadscore-60s.txt`
- Capturas: `docs/video/shots/ls1_cola.png`, `ls6_motivos.png`, `ls4_dedupe.png`, `ls7_borrador.png`

## Toma por toma

| Tiempo | Qué se ve | Qué se dice |
|---|---|---|
| 0:00–0:14 | Vista **Leads**: cola con HOT/WARM/COLD, KPIs de la cabecera (en la cola, vencidos, avance) | «Cada consulta que llega… entra a una misma cola» · «entra ordenada: arriba quedan los contactos con intención real» |
| 0:14–0:34 | Ficha del lead con **QUÉ SUMÓ CADA PUNTO** (+30 urgencia, +20 «urgente», +10 presupuesto, +10 contexto, +10 email, +10 teléfono) | «Cada punto del score tiene nombre y se ve en el panel» · «queda en Hot, Warm o Cold, con la próxima acción decidida» |
| 0:34–0:45 | Lead duplicado: aviso «es la misma persona que un lead anterior» | «si alguien escribe dos veces, el trabajo no se duplica» · «se detecta por email o teléfono normalizado» |
| 0:45–1:04 | **Borrador de respuesta** listo para copiar | «treinta consultas de prueba, los treinta niveles correctos» · «cinco centésimas de milisegundo y cuesta cero» · cierre |

## Cómo se armó

```bash
vc say --file leadscore-60s.txt --name francisco --model hd --speed 1.1 --sample-rate 32000 --out _ls_voz.mp3
# 4 tomas 1600×900, xfade 0,3 s en 14,2 / 33,9 / 45,1 s
```

Antes de capturar: se re-sembró la demo y se dejaron los leads en `new` con `next_action_at`
futura, para que la cabecera no mostrara «3 vencidos» y el panel se viera limpio.
