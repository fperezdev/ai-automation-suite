# ReplyDesk — demo de 60 s

Video: [`replydesk-60s.mp4`](video/replydesk-60s.mp4) (55 s, 1600×900, voz en off).
Narración: `docs/video/replydesk-60s.txt`.

## Guion y tomas

| # | Tiempo | Qué se ve | Qué se dice |
|---|---|---|---|
| 1 | 0:00–0:10 | Panel `/panel`, vista Resumen: conversaciones/día, % resuelto sin humano, latencia, costo, calidad del agente | «Este es ReplyDesk: el agente de WhatsApp que atiende a los clientes de una PyME y deriva a recepción cuando hace falta.» |
| 2 | 0:10–0:22 | Página de caso, chat: «¿cuánto sale la limpieza?» → CLP 35.000 + métrica de la burbuja (1307 ms · 419 tokens · US$ 0,00005) | «Llega un mensaje preguntando cuánto sale la limpieza dental. Responde con el valor real del negocio, en un segundo y medio, y ofrece coordinar la hora.» |
| 3 | 0:22–0:34 | Mismo chat: «me duele mucho una muela» → respuesta de contención + etiqueta «derivado a recepción — Urgencia: dolor o emergencia» (regla · 0 ms · sin tokens) | «Si el mensaje es una urgencia, no consulta al modelo: una regla determinista le avisa al cliente que recepción lo va a contactar… Cuesta cero tokens.» |
| 4 | 0:34–0:45 | Panel, bandeja filtrada por «con persona»: estados, última respuesta, y el hilo con el composer activo | «Recepción ve todo en el panel: estado de cada conversación, latencia, tokens y costo. Puede tomar el chat, y el bot se calla.» |
| 5 | 0:45–0:55 | Página de caso, «Resultados medidos»: 40/40, 1,6 s, US$ 0,00004, 15/40 derivadas sin tokens, 0 duplicados | «La calidad está medida: cuarenta preguntas del negocio, cuarenta respuestas correctas, y el número queda guardado en la base.» |

## Cómo se regenera

```bash
# 1. voz (piper, voz es_MX-claude-high)
/home/fperez/homelab/.venv/bin/piper -m ~/.local/share/piper/es_MX-claude-high.onnx \
  -f voz.wav --length-scale 0.95 < docs/video/replydesk-60s.txt

# 2. capturas 1600×900: panel resumen, chat precio, chat urgencia, bandeja, resultados
# 3. diapositivas estáticas con fundido de 0,33 s, 30 fps, audio AAC
```

Regla del video: **diapositivas estáticas, sin zoom**, sólo voz en off. Los números que aparecen
son los que devolvió la API en ese momento (`/api/simulate` guarda latencia, tokens y costo por mensaje).
