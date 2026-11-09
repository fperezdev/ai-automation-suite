# Portfolio — AI Automation Suite

Texto listo para pegar en Workana, Upwork y propuestas. Números medidos, no estimados:
cada módulo tiene su set de prueba y su eval reproducible.

- Sitio: **https://ai.fperez.top/** · Casos: `https://ai.fperez.top/case/`
- Código: https://github.com/fperezdev/ai-automation-suite

---

## Título

**Automatización con IA para PyMEs (n8n + LLM) — cinco módulos medidos sobre un caso real: una clínica dental**

## Descripción corta (perfil)

Cinco piezas de automatización para un negocio real, cada una con su set de prueba y su
medición publicada: **facturas PDF → datos validados**, **WhatsApp con respuestas ancladas al
negocio**, **leads calificados con score explicable**, **planillas de ventas → resumen
escrito** y **soporte por texto**. Determinista donde importa: las cifras salen de una cuenta,
no de un modelo. Todo corre con Docker Compose en un comando y se mide con eval propio.

## Descripción larga

### Qué es

Una **suite de automatización con IA** armada sobre un caso concreto —una clínica dental en
Ñuñoa que atendía todo a mano— con cinco módulos que comparten base de datos y panel:

- **01 · InvoiceFlow — facturas.** Se suelta el PDF y sale el gasto registrado: proveedor,
  RUT con dígito verificador, neto, IVA 19%, total. Reglas de negocio marcan lo que no cuadra
  (tolerancia 1 CLP / 0,02 USD) y el ítem queda en `OK` o `REVIEW` con el motivo escrito.
  **30/30 facturas del set dorado, campos 100%, p50 2,9 ms, US$ 0.**
- **02 · ReplyDesk — soporte y WhatsApp.** Responde con la información real del negocio
  (recuperación TF-IDF + coseno, sin vector DB), cita la fuente y deriva a una persona cuando
  hay urgencia o reclamo. **40/40 preguntas del set, p50 1,6 s.**
- **03 · LeadScore — captación.** Cada consulta entra a una cola única y sale con score
  explicable punto por punto (HOT ≥ 70 / WARM ≥ 40 / COLD), próxima acción y borrador de
  respuesta. Dedupe por email y teléfono normalizado. **30/30 niveles, motivos 100/100,
  p50 0,05 ms, US$ 0.**
- **04 · ReportBot — ventas.** Se sube la planilla del mes y sale el resumen escrito: total,
  comparación con el período anterior, variación, ticket promedio, reparto por categoría,
  mejor y peor día, y observaciones con severidad. **30/30 planillas, cifras 100%,
  p50 0,6 ms, US$ 0.**
- **05 · Agente n8n + LLM a medida.** Los mismos bloques conectados a webhooks, Data Tables y
  HTTP para procesos propios del negocio.

### Cómo está hecho

**n8n** (webhooks, Code nodes, Data Tables, HTTP) + **LLM** por endpoint compatible con
OpenAI (mock determinista incluido: corre sin API keys; DeepSeek/OpenAI/Groq en producción).
FastAPI + PostgreSQL + panel en un solo docker-compose, migraciones versionadas, Makefile y
smoke test. Cada módulo determinista separa **calcular** de **redactar**: las cifras salen de
funciones puras con tolerancias declaradas; el LLM, si entra, solo reescribe el texto.

### Qué demuestra

- Automatización end-to-end con base de datos, panel y pruebas, no scripts sueltos.
- **Medición**: cada pieza tiene set de 30 casos y eval reproducible; los números están
  publicados en su página de caso.
- **Cero alucinación de cifras**: montos, porcentajes y scores se calculan; el texto se limita
  a lo que la cuenta dice.
- Integración con la **API oficial de WhatsApp** (webhook, Graph API, handoff a humano).
- Entrega en **texto**: demo grabada de 60 s, documentación por módulo, sin llamadas.

### Enlaces

- Sitio: https://ai.fperez.top/
- Casos: [InvoiceFlow](https://ai.fperez.top/case/invoiceflow.html) ·
  [ReplyDesk](https://ai.fperez.top/case/replydesk.html) ·
  [LeadScore](https://ai.fperez.top/case/leadscore.html) ·
  [ReportBot](https://ai.fperez.top/case/reportbot.html)
- Código: https://github.com/fperezdev/ai-automation-suite
- Demos n8n: https://n8n.fperez.top

---

## Ítems de portfolio (Upwork — se suben desde la web)

Un ítem por módulo. Título corto, descripción de 3-4 líneas, skills y el enlace al caso.

**1. InvoiceFlow — PDF de facturas a gastos validados**
> Extrae proveedor, RUT, neto, IVA 19% y total de facturas PDF y registra el gasto solo.
> Reglas de negocio marcan lo que no cuadra con el motivo escrito. Sobre 30 facturas de
> prueba: campos 100%, estado 100%, mediana 2,9 ms, sin costo por documento.
> `https://ai.fperez.top/case/invoiceflow.html`
> Skills: Python · FastAPI · PostgreSQL · OCR/PDF · business rules

**2. ReplyDesk — respuestas de WhatsApp ancladas al negocio**
> Responde horarios, precios, ubicación y servicios con la información real del negocio, cita
> la fuente y deriva a una persona en urgencias. 40 de 40 preguntas correctas, mediana 1,6 s.
> `https://ai.fperez.top/case/replydesk.html`
> Skills: n8n · WhatsApp Cloud API · RAG · LLM

**3. LeadScore — calificación de consultas con score explicable**
> Cada consulta entra a una cola y sale con score punto por punto, nivel HOT/WARM/COLD,
> próxima acción y borrador de respuesta. Detecta duplicados por email y teléfono.
> 30 de 30 niveles correctos, mediana 0,05 ms.
> `https://ai.fperez.top/case/leadscore.html`
> Skills: Python · scoring · CRM automation

**4. ReportBot — planilla de ventas a resumen escrito**
> Sube la planilla del mes y devuelve el resumen: total, variación contra el período
> anterior, ticket promedio, reparto por categoría, mejor y peor día y observaciones.
> 30 de 30 planillas exactas, mediana 0,6 ms, sin costo.
> `https://ai.fperez.top/case/reportbot.html`
> Skills: Python · pandas/CSV · reporting automation

---

## Frase de cierre (para propuestas)

> No vendo "una automatización": monto las piezas de un negocio —facturación, atención,
> captación y reportes—, dejo cada una medida con su set de prueba y documento lo que entra
> y lo que sale. Sin llamadas: demo grabada, texto y números.
