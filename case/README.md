# Clínica Dental Sonrisa Ñuñoa — sitio del caso

Pieza del proyecto **AI Automation Suite** (`/case` del repo): es el sitio del negocio que
usa el asistente del **Módulo 1** (asistente de WhatsApp con RAG).

Landing page de una sola página para una clínica dental ficticia (Ñuñoa, Santiago de Chile),
creada como pieza de portafolio "web de una página para un negocio sin presencia online".
Mismo negocio que la demo del asistente virtual por WhatsApp, para que el caso de estudio sea coherente.

- HTML/CSS/JS en un único `index.html`, sin dependencias en runtime.
- Secciones: servicios, precios, convenios y pagos, ubicación/horarios, urgencias, agendar.
- CTA de contacto por WhatsApp (fijo y en el encabezado) + mención del asistente virtual 24/7.
- Publicado con GitHub Pages.
- `demo.html`: chat estilo WhatsApp que conversa **por HTTP** con el asistente real
  (n8n + RAG) vía `POST https://wa.fperez.top/webhook/whatsapp-dental`. El número de
  teléfono que aparece en el sitio es ficticio: el chat de la demo **no** es WhatsApp.
- `calendario.html`: calendario de contenido de 2 semanas (módulo de redes sociales con IA),
  organizado **por canal** (Instagram reels · feed/carruseles · stories, y Facebook) con etapa del
  embudo, CTA, métrica y estado por pieza.
- `lead-magnet.html`: página de captación — checklist de blanqueamiento de 7 puntos que entra al
  asistente de WhatsApp. Brief, prompt usado y versiones en `lead-magnet-brief.md`.
- `voz-de-marca.md`: guía de voz de marca del caso, reutilizable como *skill*/instrucción de proyecto.
  Castellano neutro con tildes, tuteo, CTA canónico «Escríbenos y cotizamos», reglas de validación
  clínica y checklist previo a publicar.
