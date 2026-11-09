"""Webhook de WhatsApp (Meta Cloud API) + simulador para demo y evaluación.

Puntos clave de producción que esta pieza demuestra:
  - verificación del challenge de Meta (GET) por tenant;
  - firma HMAC SHA-256 del cuerpo crudo (X-Hub-Signature-256);
  - idempotencia por `wa_message_id` (Meta reintenta webhooks);
  - el bot NO responde si la conversación ya está en manos de recepción;
  - cada respuesta guarda latencia, tokens y costo reales.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

import db
import replydesk

router = APIRouter(tags=["replydesk"])

DEMO_MODE = os.getenv("WA_DEMO_MODE", "1") == "1"
DEFAULT_VERIFY = os.getenv("WA_VERIFY_TOKEN", "suite-demo-verify")


def _now():
    return datetime.now(timezone.utc)


def get_tenant(slug: str) -> dict:
    row = db.one("SELECT * FROM tenants WHERE slug = %s", (slug,))
    if not row:
        raise HTTPException(404, f"tenant '{slug}' no existe")
    return row


def cfg(tenant: dict, key: str, default=None):
    return (tenant.get("config") or {}).get(key, default)


def verify_signature(tenant: dict, raw: bytes, header: str | None) -> tuple[bool, str]:
    """(válida, modo). Sin app secret configurado y en modo demo: se acepta y se marca."""
    secret = cfg(tenant, "wa_app_secret")
    if not secret:
        return (DEMO_MODE, "demo-sin-firma" if DEMO_MODE else "sin-secreto")
    if not header or not header.startswith("sha256="):
        return (False, "firma-ausente")
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return (hmac.compare_digest(expected, header.split("=", 1)[1]), "firma-verificada")


def upsert_contact(tenant_id: str, wa_id: str, name: str | None, phone: str | None = None) -> str:
    row = db.execute(
        """INSERT INTO contacts (tenant_id, wa_id, name, phone, meta)
           VALUES (%s, %s, %s, %s, '{}'::jsonb)
           ON CONFLICT (tenant_id, wa_id) DO UPDATE
             SET name = COALESCE(EXCLUDED.name, contacts.name),
                 phone = COALESCE(EXCLUDED.phone, contacts.phone)
           RETURNING id""",
        (tenant_id, wa_id, name, phone or wa_id),
    )
    assert row is not None, "upsert de contacto sin fila"
    return str(row["id"])


def open_conversation(tenant_id: str, contact_id: str) -> dict:
    """Conversación abierta del contacto (crea una si no hay)."""
    row = db.one(
        """SELECT * FROM conversations
           WHERE tenant_id = %s AND contact_id = %s AND status <> 'closed'
           ORDER BY created_at DESC LIMIT 1""",
        (tenant_id, contact_id),
    )
    if row:
        return row
    created = db.execute(
        """INSERT INTO conversations (tenant_id, contact_id, channel, status, last_message_at)
           VALUES (%s, %s, 'whatsapp', 'bot', now()) RETURNING *""",
        (tenant_id, contact_id),
    )
    assert created is not None, "no se pudo crear la conversación"
    return created


def store_inbound(conversation_id: str, body: str, wa_message_id: str | None) -> bool:
    """Guarda el mensaje entrante. False si ya lo teníamos (reintento de Meta)."""
    row = db.execute(
        """INSERT INTO messages (conversation_id, direction, source, body, wa_message_id)
           VALUES (%s, 'in', 'system', %s, %s)
           ON CONFLICT DO NOTHING
           RETURNING id""",
        (conversation_id, body, wa_message_id or f"sim-{conversation_id}-{time.time_ns()}"),
    )
    if wa_message_id:
        # con wa_id repetido no hay RETURNING: es un duplicado
        return bool(row)
    return True


def store_outbound(conversation_id: str, trace: dict) -> None:
    if not trace.get("reply"):
        return
    db.execute(
        """INSERT INTO messages (conversation_id, direction, source, body, latency_ms, tokens, cost_usd)
           VALUES (%s, 'out', 'bot', %s, %s, %s, %s)""",
        (conversation_id, trace["reply"], trace.get("latency_ms") or None,
         trace.get("tokens") or None, trace.get("cost_usd") or None),
    )


def apply_trace(conversation_id: str, trace: dict) -> None:
    store_outbound(conversation_id, trace)
    if trace.get("handoff"):
        db.execute(
            """UPDATE conversations
               SET status='human', handoff_reason=%s, handoff_at=now(), last_message_at=now()
               WHERE id=%s""",
            (trace.get("reason") or "Derivado por el agente", conversation_id),
        )
    else:
        db.execute("UPDATE conversations SET last_message_at=now() WHERE id=%s", (conversation_id,))


def process_incoming(tenant: dict, wa_id: str, name: str | None, body: str, wa_message_id: str | None) -> dict:
    tid = str(tenant["id"])
    contact_id = upsert_contact(tid, wa_id, name)
    conv = open_conversation(tid, contact_id)

    if not store_inbound(str(conv["id"]), body, wa_message_id):
        return {"duplicate": True, "conversation_id": str(conv["id"])}

    if conv["status"] != "bot":
        # recepción tiene el chat: el bot no contesta ni gasta tokens
        db.execute("UPDATE conversations SET last_message_at=now() WHERE id=%s", (conv["id"],))
        return {"conversation_id": str(conv["id"]), "status": conv["status"], "bot_replied": False}

    trace = replydesk.respond(tenant, str(conv["id"]), body)
    apply_trace(str(conv["id"]), trace)
    return {"conversation_id": str(conv["id"]), "status": "human" if trace["handoff"] else "bot",
            "bot_replied": bool(trace.get("reply")), **trace}


# ---------------------------------------------------------------- Meta webhook
@router.get("/webhooks/whatsapp/{slug}")
def verify(slug: str, request: Request):
    tenant = get_tenant(slug)
    q = request.query_params
    token = cfg(tenant, "wa_verify_token", DEFAULT_VERIFY)
    if q.get("hub.mode") == "subscribe" and q.get("hub.verify_token") == token:
        return int(q.get("hub.challenge", "0"))
    raise HTTPException(403, "verify token inválido")


@router.post("/webhooks/whatsapp/{slug}")
async def incoming(slug: str, request: Request):
    tenant = get_tenant(slug)
    raw = await request.body()
    ok, modo = verify_signature(tenant, raw, request.headers.get("x-hub-signature-256"))
    if not ok:
        raise HTTPException(401, f"firma rechazada ({modo})")

    try:
        payload = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(400, "payload no es JSON")

    results = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            names = {c.get("wa_id"): (c.get("profile") or {}).get("name") for c in value.get("contacts", [])}
            for msg in value.get("messages", []):
                text = ((msg.get("text") or {}).get("body") or "").strip()
                if not text:
                    continue  # audio/imagen: en producción va a una cola de revisión
                results.append(process_incoming(
                    tenant,
                    wa_id=msg.get("from"),
                    name=names.get(msg.get("from")),
                    body=text,
                    wa_message_id=msg.get("id"),
                ))
    return {"received": len(results), "firma": modo, "results": results}


# ---------------------------------------------------------------- simulador
class SimIn(BaseModel):
    tenant: str
    text: str
    wa_id: str = "56900000001"
    name: str | None = None


@router.post("/api/simulate")
def simulate(body: SimIn):
    """Mismo camino que el webhook, sin Meta: lo usa la demo y la evaluación."""
    tenant = get_tenant(body.tenant)
    started = time.time()
    out = process_incoming(tenant, body.wa_id, body.name or "Cliente demo", body.text, None)
    out["elapsed_ms"] = int((time.time() - started) * 1000)
    return out
