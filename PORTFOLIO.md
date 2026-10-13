# Portfolio — AI Automation Suite (Workana)

Texto listo para pegar en el perfil de Workana / propuestas. Acompañar con el link
al repo y 1-2 capturas.

---

## Título

**Suite de automatización con IA para PyMEs (n8n + LLM) — caso completo: una clínica dental**

## Descripción corta (para el perfil)

Automaticé **un negocio de punta a punta** con 4 módulos de IA sobre **n8n** y un **LLM**:
asistente de **WhatsApp con RAG** que responde y deriva a un humano, **automatización de
facturas** (PDF → datos validados → planilla), **captación y calificación de pacientes**, y
un **agente de soporte** por webchat. Todo corre en un comando y está documentado con
capturas y pruebas end-to-end.

## Descripción larga

### Qué es

Una **suite de automatización con IA** para pequeñas empresas. Tomé un caso concreto —una
clínica dental que atendía todo a mano— y construí **cuatro módulos** que trabajan juntos:

- **M1 · Asistente de WhatsApp (RAG):** bot 24/7 que responde sobre horarios, precios,
  ubicación, servicios y agenda **desde la información real del negocio** (recuperación por
  relevancia con TF-IDF + coseno), y **deriva a una persona** en urgencias o reclamos.
  Corre sobre la **WhatsApp Cloud API oficial de Meta** (envío por Graph API).
- **M2 · Automatización de facturas:** sube un PDF, el LLM extrae los campos, reglas de
  negocio validan los totales y el gasto se registra solo (con alerta `REVIEW` cuando algo
  no cuadra).
- **M3 · Captación y calificación:** un formulario web → enriquecimiento + scoring con IA
  (HOT/WARM/COLD) → borrador de seguimiento listo.
- **M4 · Agente de soporte (webchat):** responde con los datos del negocio y escala a un
  humano con el transcript completo.

### Cómo está hecho

**n8n** (webhooks, Code nodes, Data Tables, HTTP) + un **LLM** por endpoint compatible con
OpenAI (mock determinista incluido para que corra sin API keys, o DeepSeek/OpenAI/Groq).
RAG sin vector DB para bases chicas (se cambia por embeddings + pgvector al escalar).
Docker Compose + Makefile + **smoke test** reproducible (12 chequeos reales).

### Qué demuestra

- Automatización end-to-end, no scripts sueltos.
- **RAG** con respuestas ancladas a la fuente (sin inventar) y trazabilidad.
- Integración con la **API oficial de WhatsApp** (webhook, Graph API, handoff).
- Extracción de documentos, validación de reglas de negocio y scoring con IA.
- Cómo llevar un caso concreto a un producto **reutilizable para cualquier PyME**.

### Enlaces

- Código: https://github.com/fperezdev/ai-automation-suite
- Demo (GitHub Pages): https://fperezdev.github.io/ai-automation-suite/
- **Probar el asistente en vivo:** https://fperezdev.github.io/clinica-sonrisa-nunoa/demo.html
  (chat estilo WhatsApp que conversa por HTTP con el flujo real de n8n + RAG)
- Sitio del caso (Clínica Dental Sonrisa Ñuñoa): https://fperezdev.github.io/clinica-sonrisa-nunoa/
- Capturas: `assets/capturas/` y `modules/01-asistente-whatsapp/capturas/`

---

## Frase de cierre (para propuestas)

> No vendo "una automatización": monto la suite completa de un negocio —asistente,
> facturación, captación y soporte— y la dejo corriendo con pruebas y documentación.
