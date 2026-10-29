# Caso 2494070 — configuración de WhatsApp Business bloqueada

## Qué pasó

Al completar el alta del número `+56 9 6435 8909` en WhatsApp Business Platform
(Cloud API), Meta respondió:

> No se puede completar la configuración de la cuenta: No puedes completar el proceso de
> configuración porque tu negocio no cumple los requisitos de la política de WhatsApp.
> (#2494070: devx_onboarding_...)

Meta no documenta este código. Es una decisión automática de elegibilidad del negocio, no un
error técnico del sitio, del número ni del webhook. Hay reportes abiertos sin respuesta oficial
en el foro de desarrolladores de Meta.

## Plan (en orden, sin reintentar en bucle)

1. **Parar de reintentar.** Varios intentos seguidos refuerzan el bloqueo automático.
2. **Completar la verificación del negocio** en Meta Business Suite (Configuración del negocio →
   Verificación). Con RUT/cédula y comprobante de domicilio a nombre de Francisco Pérez.
   Un portfolio verificado cambia la evaluación de elegibilidad.
3. **Esperar 24–72 h** y reintentar una sola vez, desde WhatsApp Manager
   (`business.facebook.com/wa/manage`) en vez del flujo de developers.
4. **Abrir caso en Meta Business Support** (Business Suite → Ayuda → Contactar al soporte).
   Texto listo más abajo.
5. **Mientras se resuelve:** usar el **número de prueba** que Meta entrega en la app
   (WhatsApp → API Setup). Permite enviar a 5 números verificados sin costo y sirve para
   terminar el desarrollo y grabar la demo del portfolio. El código no cambia: solo el
   `phone_number_id` y el token.

## Texto para el caso de soporte

```
Subject: Cannot complete WhatsApp Business Platform onboarding — error #2494070

Hello,

I am trying to set up WhatsApp Business Platform (Cloud API) for my business and the setup
process fails with the following error:

"No puedes completar el proceso de configuración porque tu negocio no cumple los requisitos
de la política de WhatsApp." (#2494070, devx_onboarding_Acg8Ckwrcq_OO9nTH8tLnxO)

Details:
- Business portfolio name: Automatizaciones Fperez
- Country: Chile
- Phone number to register: +56 9 6435 8909 (WOM, prepaid, newly activated SIM, not registered
  on WhatsApp Messenger or WhatsApp Business app)
- Website: https://fperezdev.github.io/ai-automation-suite/
- The number has never been used with WhatsApp; it is a dedicated line for the business.

The website is publicly reachable (HTTP 200 from multiple countries), HTTPS is valid, and the
number receives SMS normally. I believe the account meets the WhatsApp Business Messaging
Policy: the use case is customer support for a small business (answering questions about
services, prices and hours, with handoff to a human agent).

Could you please review the eligibility decision on this business portfolio, or tell me which
requirement is not being met so I can fix it?

Thank you.
```

## Alternativas si el bloqueo persiste

- **BSP (360dialog, Twilio, Gupshup)**: el alta la hace el proveedor con su propia relación con
  Meta. Se mantiene el modelo B (webhook propio, panel propio), pero se paga una mensualidad y
  se pierde parte del control.
- **Coexistence** con la app de WhatsApp Business: requiere Tech Provider y un número con
  actividad real en la app; no aplica para un número nuevo.
- **Número de prueba de Meta** como solución permanente de demo pública: sirve para el portfolio,
  no para un cliente real.
