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
