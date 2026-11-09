"""LeadScore — calificación determinista de consultas entrantes.

Funciones puras: el lead (dict) entra, el veredicto (dict) sale. Sin base de datos, sin LLM,
sin red. Cada punto del score viene de una regla con nombre y se puede mostrar en el panel,
de modo que la persona sabe *por qué* un lead es caliente y no sólo cuánto puntuó.

Códigos de motivo estables (el orden importa poco; el consumidor usa `code`):

    service_match     consultó por un servicio concreto
    urgency           pide atención urgente
    budget            menciona presupuesto, convenio o forma de pago
    price_question    pregunta por precios o valores
    phone_ok          teléfono con formato utilizable
    email_ok          email con formato válido y dominio real
    message_detail    mensaje con contexto suficiente para responder
    time_given        dice cuándo se le puede contactar
    returning         ya fue paciente del negocio
    invalid_email     email mal escrito o desechable
    no_contact        ni email ni teléfono
    out_of_scope      el mensaje no es una consulta de servicio
    spam              mensaje comercial o automático

Tiers: HOT >= 70 · WARM >= 40 · COLD < 40.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta, timezone

TIER_HOT = 70
TIER_WARM = 40

# Servicios: se comparan sin tildes ni mayúsculas. Cada grupo suma una sola vez aunque
# el mensaje lo mencione varias veces.
SERVICES: dict[str, tuple[str, ...]] = {
    "limpieza": ("limpieza", "destartraje", "sarro", "pulido"),
    "blanqueamiento": ("blanqueamiento", "blanquear", "blanquea"),
    "ortodoncia": ("ortodoncia", "brackets", "alineador", "invisalign", "alineadores"),
    "implantes": ("implante", "implantes", "corona", "coronas"),
    "urgencia dental": ("dolor", "duele", "muela", "fractur", "diente", "dientes", "golpe", "absceso", "sangra"),
    "resinas": ("resina", "caries", "empaste", "restauracion"),
    "endodoncia": ("endodoncia", "conducto", "nervio"),
    "periodoncia": ("encias", "periodoncia", "piorrea"),
    "infantil": ("hijo", "hija", "nino", "nina", "guagua", "infantil"),
    "presupuesto": ("presupuesto", "cotizacion", "cotizar", "cuanto sale", "precio", "valores"),
}

URGENCY = ("urgente", "urgencia", "hoy", "ahora", "cuanto antes", "lo antes posible",
           "dolor fuerte", "no aguanto", "emergencia", "manana mismo")

PRICE = ("cuanto sale", "cuanto cuesta", "cuanto vale", "precio", "precios", "valores",
         "cotizar", "cotizacion", "tarifa")

BUDGET = ("presupuesto", "cuotas", "financiamiento", "convenio", "isapre", "fonasa",
          "seguro", "descuento", "pago en cuotas", "tarjeta")

TIME_HINTS = ("en la manana", "en la tarde", "despues de las", "antes de las", "lunes",
              "martes", "miercoles", "jueves", "viernes", "sabado", "fin de semana",
              "cualquier hora", "a las")

SPAM = ("seo", "posicionamiento web", "marketing digital", "paginas web", "crypto",
        "inversion", "premio", "ganaste", "sorteo", "publicidad", "socio comercial",
        "vendo base de datos", "trabajo desde casa")

OUT_OF_SCOPE = ("curriculum", "cv", "postulacion", "practica profesional", "proveedor",
                "facturacion electronica", "software contable")

RETURNING = ("ya fui paciente", "ya me atendieron", "soy paciente", "volver", "mi ultima visita",
             "me atendio", "mi tratamiento anterior")

DISPOSABLE = ("mailinator.com", "tempmail.com", "10minutemail.com", "guerrillamail.com",
              "yopmail.com", "trashmail.com", "example.com", "test.com")

REASON_TEXT = {
    "service_match": "Consult\u00f3 por {service}",
    "urgency": "Pide atenci\u00f3n urgente (\u00ab{word}\u00bb)",
    "budget": "Menciona presupuesto, convenio o forma de pago",
    "price_question": "Pregunta por precios o valores",
    "phone_ok": "Deja un tel\u00e9fono utilizable",
    "email_ok": "Email con formato v\u00e1lido",
    "message_detail": "Mensaje con contexto ({words} palabras)",
    "time_given": "Indica cu\u00e1ndo contactarlo",
    "returning": "Ya fue paciente del negocio",
    "invalid_email": "Email inv\u00e1lido o desechable",
    "no_contact": "Sin email ni tel\u00e9fono de contacto",
    "out_of_scope": "No es una consulta de servicio",
    "spam": "Parece un mensaje comercial o autom\u00e1tico",
}

POINTS = {
    "service_match": 30,
    "urgency": 20,
    "budget": 10,
    "price_question": 10,
    "phone_ok": 10,
    "email_ok": 10,
    "message_detail": 10,
    "time_given": 5,
    "returning": 5,
    "invalid_email": -15,
    "no_contact": -25,
    "out_of_scope": -30,
    "spam": -40,
}


# ------------------------------------------------------------------ normalización
def fold(text: str | None) -> str:
    """Minúsculas, sin tildes y con los espacios colapsados."""
    if not text:
        return ""
    s = unicodedata.normalize("NFD", str(text))
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", s.lower()).strip()


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")


def norm_email(email: str | None) -> str | None:
    """Email normalizado (minúsculas, sin espacios). None si no hay."""
    if not email:
        return None
    e = str(email).strip().lower()
    return e or None


def email_valid(email: str | None) -> bool:
    e = norm_email(email)
    if not e or not _EMAIL_RE.match(e):
        return False
    if ".." in e or e.startswith("@") or e.endswith("."):
        return False
    domain = e.split("@", 1)[1]
    return domain not in DISPOSABLE


_PHONE_RE = re.compile(r"^\+?\d{8,15}$")


def norm_phone(phone: str | None) -> str | None:
    """Teléfono a dígitos; si es chileno, con el 56 adelante."""
    if not phone:
        return None
    digits = re.sub(r"\D", "", str(phone))
    if not digits:
        return None
    if len(digits) == 9 and digits[0] == "9":
        digits = "56" + digits
    elif len(digits) == 8:
        digits = "562" + digits  # fijo de Santiago sin código de área
    return digits


def phone_valid(phone: str | None) -> bool:
    p = norm_phone(phone)
    return bool(p and _PHONE_RE.match(p) and 8 <= len(p) <= 15)


def dedupe_key(lead: dict) -> str | None:
    """Clave para no cargar dos veces la misma persona.

    Email primero (es el identificador más limpio); si no hay, el teléfono.
    """
    e = norm_email(lead.get("email"))
    if e and email_valid(e):
        return f"email:{e}"
    p = norm_phone(lead.get("phone"))
    if p and phone_valid(p):
        return f"phone:{p}"
    return None


# ------------------------------------------------------------------ scoring
def _find(text: str, words: tuple[str, ...]) -> str | None:
    for w in words:
        if w in text:
            return w
    return None


def _services(text: str) -> list[str]:
    hits = []
    for name, words in SERVICES.items():
        if any(w in text for w in words):
            hits.append(name)
    return hits


def score(lead: dict, *, config: dict | None = None) -> dict:
    """Devuelve score, tier, motivos y la próxima acción sugerida.

    `lead` acepta las claves name, email, phone, source, message, service,
    returning (bool). `config` permite mover los cortes de tier (`tier_hot`,
    `tier_warm`) sin tocar el código.
    """
    config = config or {}
    hot = int(config.get("tier_hot", TIER_HOT))
    warm = int(config.get("tier_warm", TIER_WARM))

    text = fold(lead.get("message") or "") + " " + fold(lead.get("service") or "")
    reasons: list[dict] = []

    def add(code: str, **kw):
        reasons.append({"code": code, "points": POINTS[code],
                        "text": REASON_TEXT[code].format(**kw) if kw else REASON_TEXT[code]})

    # --- señales de intención
    services = _services(text)
    if services:
        add("service_match", service=", ".join(services[:2]))

    urgency = _find(text, URGENCY)
    if urgency:
        add("urgency", word=urgency)

    if _find(text, BUDGET):
        add("budget")

    if _find(text, PRICE):
        add("price_question")

    if _find(text, RETURNING) or lead.get("returning"):
        add("returning")

    if _find(text, TIME_HINTS):
        add("time_given")

    # --- calidad del mensaje
    words = len(text.split())
    if words >= 12:
        add("message_detail", words=words)

    # --- contacto
    if email_valid(lead.get("email")):
        add("email_ok")
    elif norm_email(lead.get("email")):
        add("invalid_email")

    if phone_valid(lead.get("phone")):
        add("phone_ok")

    if not norm_email(lead.get("email")) and not norm_phone(lead.get("phone")):
        add("no_contact")

    # --- descartes
    if _find(text, SPAM):
        add("spam")
    elif _find(text, OUT_OF_SCOPE):
        add("out_of_scope")

    raw = sum(r["points"] for r in reasons)
    total = max(0, min(100, raw))
    tier = "HOT" if total >= hot else ("WARM" if total >= warm else "COLD")

    return {
        "score": total,
        "tier": tier,
        "reasons": reasons,
        "services": services,
        "dedupe_key": dedupe_key(lead),
        "next_action": next_action(tier, reasons),
    }


def next_action(tier: str, reasons: list[dict]) -> dict:
    """Qué hacer con el lead, en texto, y en cuántas horas vence."""
    codes = {r["code"] for r in reasons}
    if "spam" in codes or "out_of_scope" in codes:
        return {"kind": "discard", "due_hours": None,
                "text": "No es una consulta real: archivar sin responder."}
    if tier == "HOT":
        return {"kind": "contact", "due_hours": 2,
                "text": "Contactar por WhatsApp dentro de las próximas 2 horas."}
    if tier == "WARM":
        return {"kind": "contact", "due_hours": 24,
                "text": "Responder hoy: confirmar servicio y ofrecer una hora concreta."}
    return {"kind": "nurture", "due_hours": 72,
            "text": "Sumar a la secuencia de email con la información del servicio."}


def due_at(hours: int | None, *, now: datetime | None = None) -> datetime | None:
    if not hours:
        return None
    now = now or datetime.now(timezone.utc)
    return now + timedelta(hours=hours)


def draft_reply(lead: dict, verdict: dict, *, business: str = "el negocio") -> str:
    """Borrador corto para responder, armado con lo que el lead dijo."""
    name = (lead.get("name") or "").split(" ")[0] or "hola"
    services = verdict.get("services") or []
    if "spam" in {r["code"] for r in verdict["reasons"]}:
        return ""
    if services:
        first = services[0]
        cuerpo = (f"Hola {name}, gracias por escribir a {business}. "
                  f"Por lo que cuentas sobre {first}, te puedo dar una hora esta semana. ")
    else:
        cuerpo = (f"Hola {name}, gracias por escribir a {business}. "
                  f"Cuéntame un poco m\u00e1s y te digo c\u00f3mo seguimos. ")
    if verdict["tier"] == "HOT":
        cuerpo += "Si me confirmas un horario, te reservo el cupo ahora."
    elif verdict["tier"] == "WARM":
        cuerpo += "Te dejo los valores y la disponibilidad; dime cu\u00e1l te acomoda."
    else:
        cuerpo += "Cuando quieras te env\u00edo los detalles del servicio."
    return cuerpo


def evaluate_lead(lead: dict, *, config: dict | None = None) -> dict:
    """Score + borrador en una sola llamada (lo que usa la API al ingerir)."""
    verdict = score(lead, config=config)
    verdict["draft"] = draft_reply(lead, verdict)
    return verdict
