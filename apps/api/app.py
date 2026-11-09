"""API + panel de operación de la suite (multi-tenant).

Superficies:
  /api/...            JSON para el panel y para n8n
  /panel              panel del negocio (Operate)
  /health             liveness + estado de la base
"""
from __future__ import annotations

import os
import pathlib
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import db
from webhooks import router as replydesk_router

APP_DIR = pathlib.Path(__file__).parent
STATIC = APP_DIR / "static"

app = FastAPI(title="AI Automation Suite — API", version="1.0.0")
# el caso/demo público vive en otro origen (GitHub Pages o un http.server local)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC), name="static")
app.include_router(replydesk_router)


# ---------------------------------------------------------------- arranque
@app.on_event("startup")
def _startup() -> None:
    applied = db.migrate()
    if applied:
        print("migraciones aplicadas:", applied)


@app.get("/health")
def health() -> dict:
    row = db.one("SELECT now() AS ts, current_database() AS db")
    return {"ok": True, "ts": row["ts"].isoformat(), "db": row["db"]}


def tenant_id(slug: str) -> str:
    row = db.one("SELECT id FROM tenants WHERE slug = %s", (slug,))
    if not row:
        raise HTTPException(404, f"tenant '{slug}' no existe")
    return str(row["id"])


# ---------------------------------------------------------------- tenants
class TenantIn(BaseModel):
    slug: str
    name: str
    industry: str | None = None
    config: dict = Field(default_factory=dict)


@app.get("/api/tenants")
def tenants() -> list[dict]:
    return db.query("""SELECT t.*, (SELECT count(*) FROM conversations c WHERE c.tenant_id=t.id) AS conversations,
                              (SELECT count(*) FROM invoices i WHERE i.tenant_id=t.id) AS invoices
                       FROM tenants t ORDER BY t.created_at""")


@app.post("/api/tenants", status_code=201)
def create_tenant(t: TenantIn) -> dict:
    import json
    return db.execute("""INSERT INTO tenants (slug, name, industry, config) VALUES (%s,%s,%s,%s)
                         ON CONFLICT (slug) DO UPDATE SET name=EXCLUDED.name, industry=EXCLUDED.industry,
                         config=EXCLUDED.config RETURNING *""",
                      (t.slug, t.name, t.industry, json.dumps(t.config)))


# ---------------------------------------------------------------- métricas
@app.get("/api/metrics")
def metrics(tenant: str, days: int = Query(7, ge=1, le=90)) -> dict:
    tid = tenant_id(tenant)
    since = datetime.now(timezone.utc) - timedelta(days=days)
    daily = db.query("""SELECT day, conversations, handoff_conversations, inbound, outbound, human_messages
                        FROM v_conversations_daily WHERE tenant_id=%s AND day >= %s ORDER BY day""",
                     (tid, since.date()))
    handoff = db.one("SELECT * FROM v_handoff WHERE tenant_id=%s", (tid,)) or {}
    latency = db.one("SELECT * FROM v_latency WHERE tenant_id=%s", (tid,)) or {}
    inv = db.one("SELECT * FROM v_invoices WHERE tenant_id=%s", (tid,)) or {}
    leads = db.one("""SELECT count(*) AS total,
                             count(*) FILTER (WHERE tier='HOT') AS hot,
                             count(*) FILTER (WHERE status='contacted') AS contacted
                      FROM leads WHERE tenant_id=%s""", (tid,)) or {}
    ev = db.one("""SELECT score, created_at, piece, total, passed FROM eval_runs WHERE tenant_id=%s
                   ORDER BY created_at DESC LIMIT 1""", (tid,)) or {}
    cost = db.one("SELECT * FROM v_cost WHERE tenant_id=%s", (tid,)) or {}
    totals = db.one("""SELECT count(DISTINCT c.id) AS conversations,
                              count(m.*) FILTER (WHERE m.direction='in') AS inbound
                       FROM conversations c LEFT JOIN messages m ON m.conversation_id=c.id
                       WHERE c.tenant_id=%s AND c.created_at >= %s""", (tid, since)) or {}
    return {"tenant": tenant, "days": days, "daily": daily, "totals": totals,
            "handoff": handoff, "latency": latency, "invoices": inv, "leads": leads,
            "cost": cost, "eval": ev}


# ---------------------------------------------------------------- conversaciones
@app.get("/api/conversations")
def conversations(tenant: str, status: str | None = None, q: str | None = None, limit: int = 50) -> list[dict]:
    tid = tenant_id(tenant)
    sql = """SELECT c.id, c.channel, c.status, c.handoff_reason, c.handoff_at, c.last_message_at,
                    coalesce(ct.name, ct.wa_id, 'sin nombre') AS contact,
                    ct.wa_id, ct.phone,
                    (SELECT body FROM messages m WHERE m.conversation_id=c.id ORDER BY created_at DESC LIMIT 1) AS last_body,
                    (SELECT count(*) FROM messages m WHERE m.conversation_id=c.id) AS msgs
             FROM conversations c LEFT JOIN contacts ct ON ct.id=c.contact_id
             WHERE c.tenant_id=%s"""
    params: list = [tid]
    if status:
        sql += " AND c.status=%s"
        params.append(status)
    if q:
        sql += " AND (coalesce(ct.name,'') ILIKE %s OR coalesce(ct.wa_id,'') ILIKE %s)"
        params += [f"%{q}%", f"%{q}%"]
    sql += " ORDER BY c.last_message_at DESC NULLS LAST LIMIT %s"
    params.append(limit)
    return db.query(sql, tuple(params))


@app.get("/api/conversations/{cid}")
def conversation_detail(cid: str) -> dict:
    conv = db.one("""SELECT c.*, coalesce(ct.name, ct.wa_id) AS contact, ct.phone, ct.email
                     FROM conversations c LEFT JOIN contacts ct ON ct.id=c.contact_id WHERE c.id=%s""", (cid,))
    if not conv:
        raise HTTPException(404, "conversación no encontrada")
    conv["messages"] = db.query("""SELECT id, direction, source, body, latency_ms, cost_usd, created_at
                                   FROM messages WHERE conversation_id=%s ORDER BY created_at""", (cid,))
    return conv


class TakeoverIn(BaseModel):
    assignee: str = "operador"
    reason: str | None = None


@app.post("/api/conversations/{cid}/takeover")
def takeover(cid: str, body: TakeoverIn) -> dict:
    row = db.execute("""UPDATE conversations SET status='human', assigned_to=%s,
                          handoff_at=coalesce(handoff_at, now()), handoff_reason=coalesce(%s, handoff_reason)
                        WHERE id=%s RETURNING id, status, assigned_to""",
                     (body.assignee, body.reason, cid))
    if not row:
        raise HTTPException(404, "conversación no encontrada")
    db.execute("""INSERT INTO events (tenant_id, entity, entity_id, action, meta)
                  SELECT tenant_id, 'conversation', id, 'takeover', %s FROM conversations WHERE id=%s""",
               (f'{{"assignee": "{body.assignee}"}}', cid))
    return row


@app.post("/api/conversations/{cid}/close")
def close(cid: str) -> dict:
    row = db.execute("UPDATE conversations SET status='closed' WHERE id=%s RETURNING id, status", (cid,))
    if not row:
        raise HTTPException(404, "conversación no encontrada")
    return row


class MessageIn(BaseModel):
    tenant: str
    wa_id: str
    body: str
    direction: str = "in"
    source: str = "bot"
    wa_message_id: str | None = None
    latency_ms: int | None = None
    contact_name: str | None = None


@app.post("/api/messages", status_code=201)
def ingest_message(m: MessageIn) -> dict:
    """Punto de entrada de n8n. Idempotente por wa_message_id."""
    tid = tenant_id(m.tenant)
    contact = db.execute("""INSERT INTO contacts (tenant_id, wa_id, name, phone) VALUES (%s,%s,%s,%s)
                            ON CONFLICT (tenant_id, wa_id) DO UPDATE SET name=coalesce(EXCLUDED.name, contacts.name)
                            RETURNING id""", (tid, m.wa_id, m.contact_name, m.wa_id))
    conv = db.one("""SELECT id FROM conversations WHERE tenant_id=%s AND contact_id=%s AND status<>'closed'
                     ORDER BY created_at DESC LIMIT 1""", (tid, contact["id"]))
    if not conv:
        conv = db.execute("""INSERT INTO conversations (tenant_id, contact_id, channel, last_message_at)
                             VALUES (%s,%s,'whatsapp',now()) RETURNING id""", (tid, contact["id"]))
    msg = db.execute("""INSERT INTO messages (conversation_id, direction, source, body, wa_message_id, latency_ms)
                        VALUES (%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (wa_message_id) DO NOTHING
                        RETURNING id""", (conv["id"], m.direction, m.source, m.body, m.wa_message_id, m.latency_ms))
    db.execute("UPDATE conversations SET last_message_at=now() WHERE id=%s", (conv["id"],))
    return {"conversation_id": str(conv["id"]), "message_id": (str(msg["id"]) if msg else None),
            "duplicate": msg is None}


# ---------------------------------------------------------------- facturas
@app.get("/api/invoices")
def invoices(tenant: str, status: str | None = None, limit: int = 100) -> list[dict]:
    tid = tenant_id(tenant)
    sql = """SELECT id, file_name, vendor, invoice_no, total, currency, status, reason, reviewed_by,
                    reviewed_at, created_at FROM invoices WHERE tenant_id=%s"""
    params: list = [tid]
    if status:
        sql += " AND status=%s"
        params.append(status)
    sql += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)
    return db.query(sql, tuple(params))


class InvoiceIn(BaseModel):
    tenant: str
    file_name: str | None = None
    vendor: str | None = None
    invoice_no: str | None = None
    total: float | None = None
    currency: str = "CLP"
    status: str = "pending"
    reason: str | None = None
    extracted: dict = Field(default_factory=dict)


@app.post("/api/invoices", status_code=201)
def create_invoice(i: InvoiceIn) -> dict:
    import json
    tid = tenant_id(i.tenant)
    return db.execute("""INSERT INTO invoices (tenant_id, file_name, vendor, invoice_no, total, currency, status, reason, extracted)
                         VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id, status, total""",
                      (tid, i.file_name, i.vendor, i.invoice_no, i.total, i.currency, i.status, i.reason,
                       json.dumps(i.extracted)))


class InvoicePatch(BaseModel):
    status: str
    reviewed_by: str = "operador"


@app.patch("/api/invoices/{iid}")
def patch_invoice(iid: str, p: InvoicePatch) -> dict:
    row = db.execute("""UPDATE invoices SET status=%s, reviewed_by=%s, reviewed_at=now()
                        WHERE id=%s RETURNING id, status, reviewed_by, reviewed_at""",
                     (p.status, p.reviewed_by, iid))
    if not row:
        raise HTTPException(404, "factura no encontrada")
    return row


# ---------------------------------------------------------------- leads
@app.get("/api/leads")
def leads(tenant: str, status: str | None = None, limit: int = 100) -> list[dict]:
    tid = tenant_id(tenant)
    sql = "SELECT * FROM leads WHERE tenant_id=%s"
    params: list = [tid]
    if status:
        sql += " AND status=%s"
        params.append(status)
    sql += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)
    return db.query(sql, tuple(params))


# ---------------------------------------------------------------- KB
@app.get("/api/kb")
def kb(tenant: str) -> list[dict]:
    return db.query("SELECT * FROM kb_entries WHERE tenant_id=%s ORDER BY topic", (tenant_id(tenant),))


class KbIn(BaseModel):
    tenant: str
    topic: str
    answer: str
    question: str | None = None
    price: str | None = None


@app.post("/api/kb", status_code=201)
def kb_add(k: KbIn) -> dict:
    return db.execute("""INSERT INTO kb_entries (tenant_id, topic, question, answer, price)
                         VALUES (%s,%s,%s,%s,%s) RETURNING id""",
                      (tenant_id(k.tenant), k.topic, k.question, k.answer, k.price))


@app.delete("/api/kb/{kid}")
def kb_del(kid: str) -> dict:
    db.execute("UPDATE kb_entries SET active=false, updated_at=now() WHERE id=%s", (kid,))
    return {"ok": True, "id": kid}


# ---------------------------------------------------------------- panel
@app.get("/")
def panel() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse({"error": type(exc).__name__, "detail": str(exc)}, status_code=500)
