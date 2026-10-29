# Alta de WhatsApp Cloud API — datos y checklist

## Número

- **Número:** `+56 9 6435 8909` (E.164: `56964358909`, 11 dígitos, móvil chileno válido)
- **Operador:** WOM, prepago (SIM recién activada: 1 GB + 50 min + WhatsApp ilimitado por 15 días)
- **Modelo:** dedicado a Cloud API (modelo B del plan) — el número queda solo para el asistente

## Antes de empezar (bloqueantes)

1. **El número no debe estar registrado en la app WhatsApp ni WhatsApp Business.**
   Si al poner el chip se verificó en WhatsApp, hay que desregistrarlo desde la app
   (Ajustes → Cuenta → Eliminar cuenta) antes del alta. Un número en Cloud API no
   puede estar en la app al mismo tiempo (eso requiere Coexistence, que no aplica acá).
2. **Saldo/prepago activo** para recibir el SMS o la llamada de verificación de Meta.
3. **Business Portfolio de Meta** (business.facebook.com) con los datos de la clínica.
4. **Método de pago** cargado en Meta: los mensajes de servicio dentro de la ventana de
   24 h son gratis, pero las plantillas iniciadas por el negocio (recordatorios) se cobran.
5. **Nombre visible del número:** `Automatizaciones Fperez` — **no** el de la clínica.
   Meta rechaza display names sin relación con el negocio verificado, y presentar el
   asistente como si fuéramos la clínica sería deshonesto en el portfolio. El nombre de la
   clínica va en el saludo y en la KB del asistente (es la demo del sector dental).

## Datos del portfolio de negocio (modal "información comercial")

- **Nombre:** `Automatizaciones Fperez` (debe coincidir con el documento si más adelante
  Meta pide verificación; como persona natural, el nombre del SII)
- **Categoría:** Tecnología de la información / Servicios de TI
- **País:** Chile
- **Zona horaria:** (GMT-03:00) America/Santiago

## Pasos de alta

1. Crear la app en `developers.facebook.com` → tipo Business → producto WhatsApp.
2. Agregar el número `56964358909`, recibir código por SMS o llamada, verificar.
3. Confirmar el nombre visible y el portfolio de negocio.
4. Generar **token permanente de sistema** (System User) y el **App Secret**.
   Guardarlos fuera del repo (vault / `.env` no versionado).
5. Configurar el webhook:
   - URL de callback (dominio propio, HTTPS)
   - `verify_token` propio
   - Suscribir el campo `messages`
   - Validar `X-Hub-Signature-256` con el App Secret en cada request
6. Registrar el `phone_number_id` en la configuración del proyecto.
7. Crear y aprobar las plantillas:
   - `recordatorio_cita_24h` (utility, es CL)
   - `confirmacion_cita` (utility, es CL)
8. Prueba end-to-end: mensaje desde otro teléfono → respuesta del asistente en < 5 s.

## Riesgos anotados

- Si el chip se queda sin saldo o la línea se suspende, el número se pierde para Meta.
- El número no se puede recuperar para uso personal después del alta sin desregistrarlo de la API.
- Costo de plantillas: verificar tarifa vigente para Chile antes de prometer precios al cliente.

## URL del sitio (campo "URL del sitio" en Meta)

`https://ai.fperez.top` — sitio del negocio publicado en el homelab
(systemd user `ai-site.service` en 127.0.0.1:8790, Caddy hace el TLS).
Sirve contenido estático desde `ai-automation-suite/site/`.
