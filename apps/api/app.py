"""API + panel de operación de la suite (multi-tenant).

Superficies:
  /api/...            JSON para el panel y para n8n
  /panel              panel del negocio (Operate)
  /health             liveness + estado de la base
"""
from __future__ import annotations

import csv
import io
import json
import os
import pathlib
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import db
import invoiceflow as iflow
import leadscore as lscore
import reportbot as rbot
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
    inv_daily = db.query("""SELECT day, received, auto_pass, need_review, booked_total
                            FROM v_invoices_daily WHERE tenant_id=%s AND day >= %s ORDER BY day""",
                         (tid, since.date()))
    vendors = db.one("SELECT count(*) AS total FROM vendors WHERE tenant_id=%s", (tid,)) or {}
    leads = db.one("""SELECT count(*) FILTER (WHERE duplicate_of IS NULL) AS total,
                             count(*) FILTER (WHERE tier='HOT' AND duplicate_of IS NULL) AS hot,
                             count(*) FILTER (WHERE tier='WARM' AND duplicate_of IS NULL) AS warm,
                             count(*) FILTER (WHERE tier='COLD' AND duplicate_of IS NULL) AS cold,
                             count(*) FILTER (WHERE duplicate_of IS NOT NULL) AS duplicates,
                             count(*) FILTER (WHERE status IN ('new','contacted') AND duplicate_of IS NULL) AS open,
                             count(*) FILTER (WHERE status IN ('qualified','booked') AND duplicate_of IS NULL) AS won,
                             count(*) FILTER (WHERE status='contacted') AS contacted,
                             count(*) FILTER (WHERE next_action_at < now() AND status IN ('new','contacted')) AS overdue
                      FROM leads WHERE tenant_id=%s""", (tid,)) or {}
    ev = db.one("""SELECT score, created_at, piece, total, passed FROM eval_runs WHERE tenant_id=%s
                   ORDER BY created_at DESC LIMIT 1""", (tid,)) or {}
    cost = db.one("SELECT * FROM v_cost WHERE tenant_id=%s", (tid,)) or {}
    totals = db.one("""SELECT count(DISTINCT c.id) AS conversations,
                              count(m.*) FILTER (WHERE m.direction='in') AS inbound
                       FROM conversations c LEFT JOIN messages m ON m.conversation_id=c.id
                       WHERE c.tenant_id=%s AND c.created_at >= %s""", (tid, since)) or {}
    return {"tenant": tenant, "days": days, "daily": daily, "totals": totals,
            "handoff": handoff, "latency": latency, "invoices": inv, "invoices_daily": inv_daily,
            "vendors": vendors, "leads": leads,
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


# ---------------------------------------------------------------- facturas (InvoiceFlow)
class VendorIn(BaseModel):
    tenant: str
    rut: str
    name: str


@app.get("/api/vendors")
def vendors(tenant: str) -> list[dict]:
    return db.query("SELECT id, rut, name, active FROM vendors WHERE tenant_id=%s ORDER BY name",
                    (tenant_id(tenant),))


@app.post("/api/vendors", status_code=201)
def vendor_add(v: VendorIn) -> dict:
    rut, valid = iflow.normalize_rut(v.rut)
    if not valid:
        raise HTTPException(422, "RUT inválido")
    return db.execute("""INSERT INTO vendors (tenant_id, rut, name) VALUES (%s,%s,%s)
                         ON CONFLICT (tenant_id, rut) DO UPDATE SET name=EXCLUDED.name, active=true
                         RETURNING id, rut, name""", (tenant_id(v.tenant), rut, v.name))


@app.get("/api/invoices")
def invoices(tenant: str, status: str | None = None, limit: int = 100) -> list[dict]:
    tid = tenant_id(tenant)
    sql = """SELECT i.id, i.file_name, i.vendor, i.vendor_rut, i.invoice_no, i.issue_date,
                    i.neto, i.iva, i.total, i.currency, i.status, i.reason, i.reasons, i.confidence,
                    i.reviewed_by, i.reviewed_at, i.created_at,
                    i.duplicate_of, jsonb_typeof(i.corrections) AS corr_type,
                    coalesce(jsonb_array_length(i.corrections), 0) AS corrections,
                    round(extract(epoch FROM (coalesce(i.reviewed_at, now()) - i.created_at))/60.0::numeric, 1) AS age_minutes
             FROM invoices i WHERE i.tenant_id=%s"""
    params: list = [tid]
    if status:
        sql += " AND i.status=%s"
        params.append(status)
    sql += " ORDER BY (i.status='review') DESC, i.created_at DESC LIMIT %s"
    params.append(limit)
    return db.query(sql, tuple(params))


@app.post("/api/invoices/upload", status_code=201)
async def upload_invoice(tenant: str = Form(...), file: UploadFile = File(...)) -> dict:
    """PDF -> texto -> campos -> reglas -> PASS / REVIEW. Idempotente por sha256 del archivo."""
    import hashlib
    import json
    tid = tenant_id(tenant)
    data = await file.read()
    if not data:
        raise HTTPException(422, "archivo vacío")
    digest = hashlib.sha256(data).hexdigest()
    prev = db.one("SELECT id, status, total FROM invoices WHERE tenant_id=%s AND source_sha256=%s", (tid, digest))
    if prev:
        return {"id": str(prev["id"]), "status": prev["status"], "duplicate_file": True}

    try:
        text = iflow.pdf_text(data)
    except Exception as exc:  # PDF corrupto o protegido
        text = ""
        reason_text = f"No se pudo leer el PDF ({type(exc).__name__})"
    else:
        reason_text = None

    trow = db.one("SELECT config FROM tenants WHERE id=%s", (tid,)) or {}
    vendor_rows = db.query("SELECT rut, name, active FROM vendors WHERE tenant_id=%s", (tid,))
    existing = db.query("""SELECT vendor_rut, invoice_no, file_name FROM invoices
                           WHERE tenant_id=%s AND status IN ('pass','review','approved')""", (tid,))

    if reason_text:
        result = {"fields": {}, "status": "review", "confidence": 0.0,
                  "reasons": [{"code": "no_text", "text": reason_text}]}
    else:
        result = iflow.evaluate_text(text, vendors=vendor_rows, existing=existing,
                                     config=trow.get("config") or {})
    f = result["fields"]
    row = db.execute("""INSERT INTO invoices
        (tenant_id, file_name, vendor, vendor_rut, invoice_no, issue_date, neto, iva, total, currency,
         status, reason, reasons, lines, extracted, raw_text, source_sha256, confidence)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id, status""",
        (tid, file.filename, f.get("vendor"), f.get("vendor_rut"), f.get("invoice_no"),
         f.get("issue_date"), f.get("neto"), f.get("iva"), f.get("total"), f.get("currency") or "CLP",
         result["status"], "; ".join(r["text"] for r in result["reasons"]) or None,
         json.dumps(result["reasons"], ensure_ascii=False),
         json.dumps(f.get("lines") or [], ensure_ascii=False),
         json.dumps({k: (v.isoformat() if hasattr(v, "isoformat") else
                         (float(v) if hasattr(v, "quantize") else v)) for k, v in f.items()},
                    ensure_ascii=False, default=str),
         text[:60000], digest, result["confidence"]))
    db.execute("""INSERT INTO events (tenant_id, entity, entity_id, action, meta)
                  VALUES (%s,'invoice',%s,'extracted',%s)""",
               (tid, row["id"], json.dumps({"status": result["status"],
                                            "reasons": [r["code"] for r in result["reasons"]]})))
    return {"id": str(row["id"]), "status": row["status"], "reasons": result["reasons"],
            "confidence": result["confidence"], "fields": {k: (str(v) if v is not None else None)
                                                           for k, v in f.items() if k != "lines"},
            "lines": f.get("lines") or [], "duplicate_file": False}


@app.get("/api/invoices/export.csv")
def export_invoices(tenant: str, status: str | None = None):
    import csv
    import io as _io
    from fastapi.responses import Response
    tid = tenant_id(tenant)
    sql = """SELECT i.* FROM invoices i WHERE i.tenant_id=%s"""
    params: list = [tid]
    if status:
        sql += " AND i.status=%s"
        params.append(status)
    sql += " ORDER BY i.issue_date NULLS LAST, i.created_at"
    rows = db.query(sql, tuple(params))
    buf = _io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\n")
    w.writerow(["archivo", "fecha", "proveedor", "rut", "folio", "neto", "iva", "total",
                "moneda", "estado", "revisado_por", "motivos"])
    for r in rows:
        w.writerow(iflow.to_csv_row(r))
    return Response(buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="facturas-{tenant}.csv"'})


@app.get("/api/invoices/{iid}")
def invoice_detail(iid: str) -> dict:
    row = db.one("""SELECT i.*, round(extract(epoch FROM (i.reviewed_at - i.created_at))/60.0::numeric, 1) AS review_minutes
                    FROM invoices i WHERE i.id=%s""", (iid,))
    if not row:
        raise HTTPException(404, "factura no encontrada")
    return row


class InvoiceReview(BaseModel):
    status: str = "approved"                       # approved | rejected | review
    reviewed_by: str = "operador"
    reason: str | None = None
    fields: dict = Field(default_factory=dict)     # correcciones del humano


@app.patch("/api/invoices/{iid}")
def patch_invoice(iid: str, p: InvoiceReview) -> dict:
    import json
    if p.status not in ("approved", "rejected", "review", "pass"):
        raise HTTPException(422, "estado inválido")
    inv = db.one("SELECT * FROM invoices WHERE id=%s", (iid,))
    if not inv:
        raise HTTPException(404, "factura no encontrada")
    original = {k: inv.get(k) for k in ("vendor", "vendor_rut", "invoice_no", "issue_date",
                                        "neto", "iva", "total", "currency")}
    diffs = iflow.wrong_fields(original, p.fields or {})
    allowed = {"vendor", "vendor_rut", "invoice_no", "issue_date", "neto", "iva", "total", "currency"}
    fields = {k: v for k, v in (p.fields or {}).items() if k in allowed and v not in (None, "")}
    corrections = (inv.get("corrections") or []) + diffs
    sets, vals = [], []
    for k, v in fields.items():
        sets.append(f"{k}=%s")
        vals.append(v)
    sets += ["status=%s", "reviewed_by=%s", "reviewed_at=now()", "corrections=%s", "reason=%s"]
    vals += [p.status, p.reviewed_by, json.dumps(corrections, ensure_ascii=False, default=str),
             p.reason or ("; ".join(r["text"] for r in (inv.get("reasons") or [])) or None)]
    row = db.execute(f"UPDATE invoices SET {', '.join(sets)} WHERE id=%s "
                     f"RETURNING id, status, reviewed_by, reviewed_at", tuple(vals + [iid]))
    db.execute("""INSERT INTO events (tenant_id, entity, entity_id, action, meta)
                  VALUES (%s,'invoice',%s,%s,%s)""",
               (inv["tenant_id"], iid, p.status,
                json.dumps({"by": p.reviewed_by, "corrections": diffs}, ensure_ascii=False, default=str)))
    return {**row, "corrections": diffs}




# ---------------------------------------------------------------- leads (LeadScore)
LEAD_COLS = """id, name, email, phone, source, score, tier, reasons, score_breakdown, services,
                draft, status, message, dedupe_key, duplicate_of, next_action_kind, next_action_at,
                created_at, updated_at"""


class LeadIn(BaseModel):
    tenant: str
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    source: str | None = "formulario web"
    message: str | None = None
    service: str | None = None
    returning: bool = False


class LeadPatch(BaseModel):
    status: str | None = None
    next_action_at: datetime | None = None


@app.get("/api/leads")
def leads(tenant: str, status: str | None = None, tier: str | None = None,
          q: str | None = None, limit: int = 200) -> list[dict]:
    tid = tenant_id(tenant)
    sql = f"SELECT {LEAD_COLS} FROM leads WHERE tenant_id=%s"
    params: list = [tid]
    if status:
        sql += " AND status=%s"
        params.append(status)
    if tier:
        sql += " AND tier=%s"
        params.append(tier.upper())
    if q:
        sql += " AND (name ILIKE %s OR email ILIKE %s OR message ILIKE %s)"
        like = f"%{q}%"
        params += [like, like, like]
    sql += " ORDER BY duplicate_of IS NOT NULL, score DESC, created_at DESC LIMIT %s"
    params.append(limit)
    rows = db.query(sql, tuple(params))
    now = datetime.now(timezone.utc)
    for r in rows:
        due = r.get("next_action_at")
        r["overdue"] = bool(due and r["status"] in ("new", "contacted") and due < now)
    return rows


@app.post("/api/leads", status_code=201)
def lead_ingest(lead: LeadIn) -> dict:
    """Entra una consulta: se puntúa con reglas, se deduplica y se encola el seguimiento."""
    tid = tenant_id(lead.tenant)
    payload = lead.model_dump(exclude={"tenant"})
    verdict = lscore.evaluate_lead(payload)
    key = verdict["dedupe_key"]

    dup = None
    if key:
        dup = db.one("""SELECT id, name, score, tier FROM leads
                        WHERE tenant_id=%s AND dedupe_key=%s AND duplicate_of IS NULL
                        ORDER BY created_at LIMIT 1""", (tid, key))

    status = "discarded" if dup else "new"
    due = None if dup else lscore.due_at(verdict["next_action"]["due_hours"])
    row = db.execute(f"""INSERT INTO leads (tenant_id, name, email, phone, source, message, score, tier,
                                             reasons, score_breakdown, services, draft, status, dedupe_key,
                                             duplicate_of, next_action_kind, next_action_at)
                         VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,%s)
                         RETURNING {LEAD_COLS}""",
                      (tid, lead.name, lscore.norm_email(lead.email), lscore.norm_phone(lead.phone),
                       lead.source, lead.message, verdict["score"], verdict["tier"],
                       json.dumps([r["text"] for r in verdict["reasons"]], ensure_ascii=False),
                       json.dumps(verdict["reasons"], ensure_ascii=False),
                       json.dumps(verdict["services"], ensure_ascii=False),
                       verdict["draft"], status, key, dup["id"] if dup else None,
                       verdict["next_action"]["kind"], due))
    if not row:
        raise HTTPException(500, "no se pudo guardar el lead")
    row["duplicate"] = bool(dup)
    row["next_action_text"] = verdict["next_action"]["text"]
    return row


@app.patch("/api/leads/{lead_id}")
def lead_patch(lead_id: str, body: LeadPatch) -> dict:
    sets, params = [], []
    if body.status:
        if body.status not in ("new", "contacted", "qualified", "booked", "discarded"):
            raise HTTPException(400, "estado inválido")
        sets.append("status=%s")
        params.append(body.status)
        if body.status in ("qualified", "booked", "discarded"):
            sets.append("next_action_at=NULL")
    if body.next_action_at:
        sets.append("next_action_at=%s")
        params.append(body.next_action_at)
    if not sets:
        raise HTTPException(400, "nada que actualizar")
    sets.append("updated_at=now()")
    params.append(lead_id)
    row = db.execute(f"UPDATE leads SET {', '.join(sets)} WHERE id=%s RETURNING {LEAD_COLS}", tuple(params))
    if not row:
        raise HTTPException(404, "lead no encontrado")
    return row


@app.get("/api/leads/export.csv")
def leads_export(tenant: str) -> Response:
    """CSV plano con las columnas que pide cualquier CRM al importar contactos."""
    tid = tenant_id(tenant)
    rows = db.query(f"SELECT {LEAD_COLS} FROM leads WHERE tenant_id=%s ORDER BY score DESC", (tid,))
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["name", "email", "phone", "source", "score", "tier", "status", "next_action",
                "next_action_at", "reasons", "duplicate_of", "created_at", "message"])
    for r in rows:
        w.writerow([r["name"] or "", r["email"] or "", r["phone"] or "", r["source"] or "",
                    r["score"], r["tier"], r["status"], r["next_action_kind"] or "",
                    r["next_action_at"].isoformat() if r["next_action_at"] else "",
                    " | ".join(x.get("text", "") for x in (r["score_breakdown"] or [])),
                    r["duplicate_of"] or "",
                    r["created_at"].isoformat() if r["created_at"] else "", r["message"] or ""])
    return Response(content=out.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="leads.csv"'})


# ---------------------------------------------------------------- ReportBot
REPORT_COLS = ("id, file_name, period_start, period_end, rows_count, total, prev_total, "
               "delta_pct, currency, metrics, text, created_at")


@app.post("/api/reports/upload", status_code=201)
async def upload_report(tenant: str = Form(...), file: UploadFile = File(...),
                        business: str = Form("")) -> dict:
    """CSV de ventas -> números -> resumen escrito. Idempotente por sha256 del archivo."""
    import hashlib
    tid = tenant_id(tenant)
    data = await file.read()
    if not data:
        raise HTTPException(422, "archivo vacío")
    digest = hashlib.sha256(data).hexdigest()
    prev = db.one(f"SELECT {REPORT_COLS} FROM sales_reports WHERE tenant_id=%s AND source_sha256=%s",
                  (tid, digest))
    if prev:
        prev = dict(prev)
        prev["duplicate_file"] = True
        return prev

    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    rows = rbot.parse_csv(text)
    if not rows:
        raise HTTPException(422, "no encontré filas con fecha y monto: la planilla necesita "
                                 "una columna de fecha y una de monto")
    trow = db.one("SELECT config FROM tenants WHERE id=%s", (tid,)) or {}
    cfg = trow.get("config") or {}
    name = (business or cfg.get("negocio") or cfg.get("name") or tenant).strip()
    metrics = rbot.aggregate(rows)
    out = rbot.report(metrics, name)

    row = db.execute("""INSERT INTO sales_reports
        (tenant_id, file_name, source_sha256, period_start, period_end, rows_count, total,
         prev_total, delta_pct, currency, metrics, text)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING """ + REPORT_COLS,
        (tid, file.filename, digest, metrics["period_start"], metrics["period_end"],
         metrics["rows"], metrics["total"], metrics["prev_total"], metrics["delta_pct"],
         metrics["currency"], json.dumps(metrics, ensure_ascii=False, default=str),
         out["text"]))
    if not row:
        raise HTTPException(500, "no se pudo guardar el reporte")
    return dict(row)


@app.get("/api/reports")
def reports_list(tenant: str, limit: int = Query(50, ge=1, le=200)) -> list[dict]:
    cols = "id, file_name, period_start, period_end, rows_count, total, prev_total, delta_pct, created_at"
    return db.query(f"SELECT {cols} FROM sales_reports WHERE tenant_id=%s "
                    f"ORDER BY created_at DESC LIMIT %s", (tenant_id(tenant), limit))


@app.get("/api/reports/{report_id}")
def report_detail(report_id: str, tenant: str) -> dict:
    row = db.one(f"SELECT {REPORT_COLS} FROM sales_reports WHERE id=%s AND tenant_id=%s",
                 (report_id, tenant_id(tenant)))
    if not row:
        raise HTTPException(404, "reporte no encontrado")
    return dict(row)


@app.get("/api/reports/{report_id}.md")
def report_markdown(report_id: str, tenant: str) -> Response:
    row = report_detail(report_id, tenant)
    return Response(content=row["text"], media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition":
                             f'attachment; filename="reporte-{row["period_end"] or "sin-fecha"}.md"'})


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
