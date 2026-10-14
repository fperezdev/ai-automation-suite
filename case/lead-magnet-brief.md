# Brief — Lead magnet: checklist de blanqueamiento

Recurso de captación para el caso **Clínica Dental Sonrisa Ñuñoa** (negocio ficticio).
Entregable: **`lead-magnet.html`** → https://fperezdev.github.io/ai-automation-suite/case/lead-magnet.html

## 1. Brief

| Campo | Definición |
|---|---|
| **Objetivo** | Captar contactos de gente que está evaluando blanquearse y llevarla a una evaluación ($15.000) sin que nadie atienda el teléfono. |
| **Buyer persona** | Adulto de Ñuñoa y alrededores, 25–45, mira precios antes de decidir, llega desde Instagram o Facebook. Le frena la duda «¿me va a servir a mí?», no el precio. |
| **Etapa del embudo** | Consideración (medio): ya piensa en el tratamiento, todavía no se decidió. |
| **Formato** | Checklist de 7 puntos (más largo se lee poco; una checklist se usa y se marca). |
| **Promesa** | «7 puntos que revisamos antes de blanquear, para que no gastes de más.» Clara, útil y alcanzable. |
| **Problema chico y concreto que resuelve** | «¿Conviene blanquearme ahora o primero tengo que hacer otra cosa?» |
| **Dato que se pide** | Nombre + WhatsApp + qué le interesa + consentimiento para el contacto. |
| **Recompensa extra** | Precio de referencia ($120.000), qué incluye la sesión y el cupo de urgencia del mismo día. |
| **Canal de entrega** | El asistente de WhatsApp de la clínica (n8n + LLM), 24/7, en menos de un minuto. |
| **Métrica principal** | % de leads que pasan a hora agendada. |
| **Costo por lead** | $0 (difusión orgánica en las redes de la clínica). |

## 2. Prompt usado

```text
Actúa como el/la community manager de Clínica Dental Sonrisa Ñuñoa (clínica dental familiar en Ñuñoa,
Santiago; limpieza $35.000 · blanqueamiento $120.000 · resina $45.000 · consulta de evaluación $15.000;
Fonasa e Isapre; hasta 3 cuotas; urgencias con cupo el mismo día; asistente virtual 24/7 por WhatsApp).

Necesito un LEAD MAGNET en formato checklist para gente que está evaluando blanquearse los dientes.
Requisitos:
- No explique todo el blanqueamiento: resuelve un problema chico y concreto (¿me conviene ahora?).
- Exactamente 7 puntos, cada uno con una acción o un dato concreto, en lenguaje de paciente (sin jerga
  sin traducir).
- Cada punto que sea información de salud va marcado como [validar por odontólogo].
- Cierra con el precio de referencia, qué incluye la sesión y el CTA "Escríbenos y cotizamos".
- Voz: castellano neutro con tildes, tuteo ("tú"), frases cortas, sin superlativos ni promesas absolutas.
- Nada de voseo ni modismos rioplatenses.
- Además: el texto del primer mensaje de WhatsApp que envía la checklist (máximo 5 líneas) y 2 preguntas
  de calificación para saber si conviene limpieza, evaluación o urgencia.
Entrega: copy de la página, copy del mensaje de WhatsApp y la lista de datos que faltan validar.
```

## 3. Versiones

| Versión | Cambio | Motivo |
|---|---|---|
| v1 | Checklist de 10 puntos, tono folleto | Demasiado larga y genérica: «más pasta no es mejor» ya está en el reel. Se bajó a 7. |
| v2 | 7 puntos orientados a la decisión + precio + circuito del asistente | Cada punto responde a una razón por la que la gente **no** se blanquea. |
| **v3 (actual)** | Retoque de tono: las afirmaciones taxativas pasan a «en general» / «lo confirmamos en la evaluación» | Evita que la página suene a promesa clínica propia; el número de tonos queda sujeto a la evaluación. |
| v4 (pendiente) | Revisión del odontólogo del equipo | Los 5 puntos clínicos marcados `validar` no se publican sin esa revisión. |

## 4. Copy del primer mensaje de WhatsApp

```text
¡Hola, {nombre}! 👋 Soy el asistente de Sonrisa Ñuñoa. Te paso la checklist de blanqueamiento:
los 7 puntos que revisamos antes de empezar.

¿Te la envío ahora o prefieres que te cuente primero cómo es la sesión y cuánto sale?

— Si quieres, también puedes responder CHECKLIST y te la mando al tiro.
```

Preguntas de calificación:
1. ¿Hace cuánto te hiciste la última limpieza?
2. ¿Sientes sensibilidad al frío, al calor o al dulce?

Derivación según respuesta: limpieza primero (más de 6 meses) · evaluación normal · derivar a una persona si hay dolor agudo o un tema sensible.

## 5. Reglas de cumplimiento del recurso

- Los 5 puntos clínicos van marcados y pendientes de revisión de un odontólogo antes de publicar.
- El formulario de la página es **una simulación estática**: no envía ni guarda datos (el negocio y el número son ficticios). Está declarado en la propia página.
- Para producción faltaría: plantilla de primer mensaje aprobada por la plataforma de WhatsApp, aviso de privacidad de datos personales y registro del consentimiento del contacto.
- Voz según `case/voz-de-marca.md` (aplicación del skill de voz de marca).

## 6. Métricas a observar

- Leads por semana (formulario completado + gente que escribe CHECKLIST al chat).
- Tiempo de primera respuesta (objetivo: menos de 1 minuto).
- % de leads que responden la pregunta de calificación.
- % de leads que agendan hora y qué tratamiento piden.
- Si baja la respuesta de calificación → testear otro primer mensaje (más corto, una sola pregunta).
- Si agendan poco → el problema está en la oferta de hora, no en la checklist.
