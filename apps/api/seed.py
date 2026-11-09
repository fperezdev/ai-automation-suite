"""Datos de demostración: un tenant real-ish (clínica), conversaciones, facturas, leads, KB y eval.

Idempotente: borra el tenant y lo vuelve a crear. Reparte la actividad en 7 días para que el
panel muestre una semana con volumen real, no un solo punto.
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone

import db
import leadscore
import reportbot

TENANT = "clinica-sonrisa-nunoa"

DEMO_VENTAS_OCT = """fecha;monto;categoria;detalle
01/10/2026;$180.000;Ortodoncia;control mensual
01/10/2026;$35.000;Limpieza;destartraje
02/10/2026;$184.000;Ortodoncia;control mensual
02/10/2026;$35.000;Limpieza;destartraje
03/10/2026;$188.000;Ortodoncia;control mensual
03/10/2026;$35.000;Limpieza;destartraje
05/10/2026;$196.000;Ortodoncia;control mensual
05/10/2026;$35.000;Limpieza;destartraje
05/10/2026;$1.250.000;Implantes;instalación
06/10/2026;$200.000;Ortodoncia;control mensual
06/10/2026;$35.000;Limpieza;destartraje
07/10/2026;$204.000;Ortodoncia;control mensual
07/10/2026;$35.000;Limpieza;destartraje
08/10/2026;$208.000;Ortodoncia;control mensual
08/10/2026;$35.000;Limpieza;destartraje
09/10/2026;$212.000;Ortodoncia;control mensual
09/10/2026;$35.000;Limpieza;destartraje
10/10/2026;$216.000;Ortodoncia;control mensual
10/10/2026;$35.000;Limpieza;destartraje
12/10/2026;$224.000;Ortodoncia;control mensual
12/10/2026;$35.000;Limpieza;destartraje
12/10/2026;$1.250.000;Implantes;instalación
13/10/2026;$228.000;Ortodoncia;control mensual
13/10/2026;$35.000;Limpieza;destartraje
14/10/2026;$232.000;Ortodoncia;control mensual
14/10/2026;$35.000;Limpieza;destartraje
15/10/2026;$236.000;Ortodoncia;control mensual
15/10/2026;$35.000;Limpieza;destartraje
16/10/2026;$240.000;Ortodoncia;control mensual
16/10/2026;$35.000;Limpieza;destartraje
17/10/2026;$244.000;Ortodoncia;control mensual
17/10/2026;$35.000;Limpieza;destartraje
19/10/2026;$252.000;Ortodoncia;control mensual
19/10/2026;$70.000;Limpieza;destartraje
19/10/2026;$1.250.000;Implantes;instalación
20/10/2026;$256.000;Ortodoncia;control mensual
20/10/2026;$35.000;Limpieza;destartraje
21/10/2026;$260.000;Ortodoncia;control mensual
21/10/2026;$35.000;Limpieza;destartraje
22/10/2026;$264.000;Ortodoncia;control mensual
22/10/2026;$35.000;Limpieza;destartraje
23/10/2026;$268.000;Ortodoncia;control mensual
23/10/2026;$35.000;Limpieza;destartraje
24/10/2026;$272.000;Ortodoncia;control mensual
24/10/2026;$35.000;Limpieza;destartraje
26/10/2026;$280.000;Ortodoncia;control mensual
26/10/2026;$35.000;Limpieza;destartraje
26/10/2026;$1.250.000;Implantes;instalación
27/10/2026;$284.000;Ortodoncia;control mensual
27/10/2026;$35.000;Limpieza;destartraje
28/10/2026;$288.000;Ortodoncia;control mensual
28/10/2026;$35.000;Limpieza;destartraje
29/10/2026;$292.000;Ortodoncia;control mensual
29/10/2026;$35.000;Limpieza;destartraje
30/10/2026;$296.000;Ortodoncia;control mensual
30/10/2026;$35.000;Limpieza;destartraje
31/10/2026;$300.000;Ortodoncia;control mensual
31/10/2026;$35.000;Limpieza;destartraje
"""

DEMO_VENTAS_NOV = """fecha;monto;categoria;detalle
02/11/2026;$215.000;Ortodoncia;control mensual
02/11/2026;$70.000;Limpieza;destartraje y pulido
03/11/2026;$220.000;Ortodoncia;control mensual
03/11/2026;$70.000;Limpieza;destartraje y pulido
04/11/2026;$225.000;Ortodoncia;control mensual
04/11/2026;$70.000;Limpieza;destartraje y pulido
05/11/2026;$230.000;Ortodoncia;control mensual
05/11/2026;$70.000;Limpieza;destartraje y pulido
05/11/2026;$1.250.000;Implantes;instalación de implante
06/11/2026;$235.000;Ortodoncia;control mensual
06/11/2026;$70.000;Limpieza;destartraje y pulido
07/11/2026;$240.000;Ortodoncia;control mensual
07/11/2026;$70.000;Limpieza;destartraje y pulido
09/11/2026;$250.000;Ortodoncia;control mensual
09/11/2026;$70.000;Limpieza;destartraje y pulido
10/11/2026;$255.000;Ortodoncia;control mensual
10/11/2026;$70.000;Limpieza;destartraje y pulido
11/11/2026;$260.000;Ortodoncia;control mensual
11/11/2026;$70.000;Limpieza;destartraje y pulido
12/11/2026;$265.000;Ortodoncia;control mensual
12/11/2026;$70.000;Limpieza;destartraje y pulido
13/11/2026;$270.000;Ortodoncia;control mensual
13/11/2026;$70.000;Limpieza;destartraje y pulido
14/11/2026;$275.000;Ortodoncia;control mensual
14/11/2026;$70.000;Limpieza;destartraje y pulido
"""

random.seed(7)

KB = [
    ("Limpieza dental", "La limpieza cuesta CLP 35.000 e incluye destartraje y pulido.", "CLP 35.000"),
    ("Blanqueamiento", "El blanqueamiento en consulta cuesta CLP 120.000 y dura cerca de 90 minutos.", "CLP 120.000"),
    ("Horario", "Atendemos de lunes a viernes de 09:00 a 19:00 y sábado de 09:00 a 14:00.", None),
    ("Urgencias", "Las urgencias se atienden el mismo día; si hay dolor agudo se deriva a un humano.", None),
    ("Convenios", "Tenemos convenio con Isapre Consalud y Colmena, con 20% de descuento en tratamientos.", None),
    ("Dirección", "Estamos en Av. Irarrázaval 3400, Ñuñoa, Santiago.", None),
]

# (wa_id, nombre, estado, motivo, días atrás, mensajes)
CONVERSATIONS = [
    ("+56911110001", "Camila Rojas", "human", "Dolor agudo: pide precio y hora para hoy", 0,
     [("in", "bot", "hola, me duele mucho una muela, atienden hoy?"),
      ("out", "bot", "Hola Camila, sí atendemos urgencias el mismo día. ¿Prefieres antes de las 12 o después de las 15?"),
      ("in", "bot", "antes de las 12 porfa"),
      ("out", "bot", "Tengo 10:30 con la Dra. Soto. ¿Te la reservo?"),
      ("in", "bot", "sí pero necesito saber el precio"),
      ("out", "human", "Camila, te escribe Javiera de recepción: la consulta de urgencia son CLP 25.000 y la reservé para las 10:30.")]),
    ("+56911110002", "Diego Fuentes", "bot", None, 0,
     [("in", "bot", "cuanto sale el blanqueamiento"),
      ("out", "bot", "El blanqueamiento en consulta cuesta CLP 120.000 y dura cerca de 90 minutos. ¿Quieres que te proponga horas?"),
      ("in", "bot", "y la limpieza?"),
      ("out", "bot", "La limpieza cuesta CLP 35.000 e incluye destartraje y pulido."),
      ("in", "bot", "ok, me avisas cuando tengan hora el viernes")]),
    ("+56911110003", "Valentina Paz", "human", "Convenio Isapre: hay que validar cobertura", 0,
     [("in", "bot", "trabajan con colmena?"),
      ("out", "bot", "Sí, tenemos convenio con Colmena con 20% de descuento en tratamientos. Para validar tu cobertura necesito que te hable una persona del equipo."),
      ("in", "bot", "ok"),
      ("out", "human", "Hola Valentina, soy Javiera. Mándame tu número de afiliación y lo reviso ahora.")]),
    ("+56911110004", "Matías Herrera", "closed", None, 1,
     [("in", "bot", "abren el sabado?"),
      ("out", "bot", "Sí, sábado de 09:00 a 14:00."),
      ("in", "bot", "perfecto, agendo la otra semana"),
      ("out", "bot", "Quedo atenta. Cualquier cosa me escribes por acá.")]),
    ("+56911110005", "Antonia Silva", "bot", None, 2,
     [("in", "bot", "necesito una limpieza, cuanto demora"),
      ("out", "bot", "La limpieza dura cerca de 45 minutos y cuesta CLP 35.000. ¿Te propongo horarios?"),
      ("in", "bot", "dale")]),
    ("+56911110006", "Pablo Cáceres", "bot", None, 3,
     [("in", "bot", "hacen ortodoncia?"),
      ("out", "bot", "Sí, trabajamos con brackets metálicos y alineadores. La evaluación inicial cuesta CLP 20.000 y se descuenta del tratamiento."),
      ("in", "bot", "y cuanto sale el tratamiento completo"),
      ("out", "bot", "Depende del caso: entre CLP 1.200.000 y CLP 2.400.000. La doctora te da el valor exacto en la evaluación.")]),
    ("+56911110007", "Rocío Mendoza", "human", "Paciente pide hablar con la doctora por una urgencia", 4,
     [("in", "bot", "mi hija se cayó y se quebró un diente, que hago"),
      ("out", "bot", "Voy a pasar la conversación a recepción ahora mismo para que la atiendan hoy."),
      ("out", "human", "Rocío, soy Javiera. Traela a las 16:00 y la ve la Dra. Soto; si hay sangrado, guarda el fragmento en leche.")]),
    ("+56911110008", "Cristián Soto", "bot", None, 5,
     [("in", "bot", "precio de una endodoncia"),
      ("out", "bot", "La endodoncia unirradicular cuesta CLP 180.000; la evaluación con radiografía son CLP 20.000."),
      ("in", "bot", "gracias")]),
    ("+56911110009", "Paulina Reyes", "closed", None, 5,
     [("in", "bot", "donde quedan?"),
      ("out", "bot", "Estamos en Av. Irarrázaval 3400, Ñuñoa, a dos cuadras del metro Chile España."),
      ("in", "bot", "gracias!")]),
    ("+56911110010", "Sebastián Núñez", "bot", None, 6,
     [("in", "bot", "atienden fonasa?"),
      ("out", "bot", "No trabajamos con Fonasa, pero tenemos convenio con Consalud y Colmena. ¿Tienes alguna de esas?"),
      ("in", "bot", "no, tengo fonasa"),
      ("out", "bot", "Entiendo. Igual puedes atenderte particular; la consulta de evaluación son CLP 20.000.")]),
    ("+56911110011", "Isidora Fuenzalida", "bot", None, 6,
     [("in", "bot", "quiero hora para limpieza esta semana"),
      ("out", "bot", "Tengo jueves 11:00 o viernes 17:30 con la Dra. Soto. ¿Cuál te sirve?"),
      ("in", "bot", "jueves 11"),
      ("out", "bot", "Listo, quedas agendada para el jueves a las 11:00. Te llega un recordatorio el día anterior.")]),
]

# (archivo, proveedor, número, total, estado, motivo, días atrás)
def _dv(body: str) -> str:
    factor, total = 2, 0
    for ch in reversed(body):
        total += int(ch) * factor
        factor = 2 if factor == 7 else factor + 1
    rest = 11 - (total % 11)
    return "0" if rest == 11 else "K" if rest == 10 else str(rest)


def _rut(body: str) -> str:
    return f"{int(body):,}".replace(",", ".") + "-" + _dv(body)


VENDORS = [
    ("Dental Supply SpA", _rut("77234567")),
    ("Insumos Norte Ltda", _rut("78345678")),
    ("Limpieza Pro SpA", _rut("77678901")),
    ("Implantes CL SpA", _rut("79456789")),
    ("Ortodoncia Insumos Ltda", _rut("76567890")),
]

# (archivo, proveedor, folio, total, estado, motivos, correcciones, días atrás)
INVOICES = [
    ("factura-dental-supply-0912.pdf", "Dental Supply SpA", "F-00912", 428900, "pass", [], [], 0),
    ("factura-insumos-norte-0455.pdf", "Insumos Norte Ltda", "F-00455", 199030, "review",
     [{"code": "lines_mismatch", "text": "La suma de las líneas no cuadra con el neto (189.030 ≠ 167.252)"}],
     [], 1),
    ("factura-limpieza-pro-0231.pdf", "Limpieza Pro SpA", "F-00231", 89000, "approved", [],
     [{"field": "total", "from": 84000.0, "to": 89000.0}], 2),
    ("factura-implantes-cl-0778.pdf", "Implantes CL SpA", "F-00778", 1250000, "pass", [], [], 3),
    ("factura-rayos-x-0344.pdf", "Rayos X Digital SpA", "F-00344", 156000, "review",
     [{"code": "unknown_vendor", "text": "Proveedor no registrado en el maestro (76.111.222-3)"}], [], 4),
    ("factura-ortodoncia-insumos-0121.pdf", "Ortodoncia Insumos Ltda", "F-00121", 312400, "pass", [], [], 5),
    ("factura-dental-supply-0901.pdf", "Dental Supply SpA", "F-00901", 275600, "approved", [],
     [{"field": "issue_date", "from": "2026-11-01", "to": "2026-10-31"}], 6),
]

LEADS = [
    dict(name="Josefa Contreras", email="josefa.contreras@gmail.com", phone="+56 9 8412 7733",
         source="formulario web", status="new", days_ago=0,
         message="Hola, quiero empezar ortodoncia con brackets. Tengo convenio con isapre y quisiera "
                 "saber los valores y si se puede pagar en cuotas. Puedo ir en la tarde."),
    dict(name="Rodrigo Pena", email="rpena@gmail.com", source="instagram", status="contacted", days_ago=1,
         message="hola, cuanto sale la limpieza dental?"),
    dict(name="Ignacio Vera", email="ivera@mail.com", source="formulario web", status="new", days_ago=2,
         message="Hola, buenas tardes. Necesito informacion."),
    dict(name="Fernanda Lillo", email="flillo@gmail.com", phone="+56 9 6677 8899",
         source="referido", status="qualified", days_ago=3,
         message="Me recomendó una paciente. Quiero hacerme un blanqueamiento antes de mi matrimonio, "
                 "cuanto sale? Puedo el sabado en la manana."),
    dict(name="Tomas Aguilera", email="taguilera@gmail.com", source="instagram", status="new", days_ago=5,
         message="Hola, tienen financiamiento para resinas? Tengo fonasa."),
    dict(name="Ana Maria Soto", email="ana.soto@gmail.com", phone="+56 9 5511 2244",
         source="whatsapp", status="contacted", days_ago=0,
         message="Hola, me duele mucho una muela y necesito atencion urgente hoy. Tengo isapre."),
    dict(name="Josefa Contreras", email="JOSEFA.CONTRERAS@gmail.com", phone="+56 9 8412 7733",
         source="whatsapp", status="discarded", days_ago=0,
         message="hola, escribi por el formulario, sigo interesada en los brackets"),
]


def run() -> None:
    db.migrate()
    db.execute("DELETE FROM tenants WHERE slug=%s", (TENANT,))
    t = db.execute("""INSERT INTO tenants (slug, name, industry, config) VALUES (%s,%s,%s,%s) RETURNING id""",
                   (TENANT, "Clínica Dental Sonrisa Ñuñoa", "salud",
                    json.dumps({"negocio": "Clínica Sonrisa Ñuñoa", "ciudad": "Santiago",
                                "horario": "L-V 09:00-19:00, S 09:00-14:00",
                                "max_invoice_total": 8000000})))
    tid = t["id"]

    for topic, answer, price in KB:
        db.execute("INSERT INTO kb_entries (tenant_id, topic, answer, price) VALUES (%s,%s,%s,%s)",
                   (tid, topic, answer, price))

    now = datetime.now(timezone.utc)
    for wa, name, status, reason, days_ago, msgs in CONVERSATIONS:
        start = now - timedelta(days=days_ago, hours=random.randint(1, 8), minutes=random.randint(0, 59))
        contact = db.execute("""INSERT INTO contacts (tenant_id, wa_id, name, phone) VALUES (%s,%s,%s,%s)
                                ON CONFLICT (tenant_id, wa_id) DO UPDATE SET name=EXCLUDED.name RETURNING id""",
                             (tid, wa, name, wa))
        conv = db.execute("""INSERT INTO conversations (tenant_id, contact_id, channel, status, handoff_reason,
                                                             handoff_at, assigned_to, last_message_at, created_at)
                             VALUES (%s,%s,'whatsapp',%s,%s,%s,%s,%s,%s) RETURNING id""",
                          (tid, contact["id"], status, reason,
                           start + timedelta(minutes=4) if status == "human" else None,
                           "Javiera" if status == "human" else None,
                           start + timedelta(minutes=3 * len(msgs)), start))
        for j, (direction, source, body) in enumerate(msgs):
            db.execute("""INSERT INTO messages (conversation_id, direction, source, body, latency_ms, cost_usd, created_at)
                          VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                       (conv["id"], direction, source, body,
                        random.randint(900, 2400) if direction == "out" else None,
                        round(random.uniform(0.0004, 0.0021), 6) if direction == "out" else None,
                        start + timedelta(minutes=3 * j)))

    for vendor_name, vendor_rut in VENDORS:
        db.execute("""INSERT INTO vendors (tenant_id, rut, name) VALUES (%s,%s,%s)
                      ON CONFLICT (tenant_id, rut) DO NOTHING""", (tid, vendor_rut, vendor_name))
    rut_by_name = dict(VENDORS)

    for fname, vendor, number, total, status, reasons, corrections, days_ago in INVOICES:
        created = now - timedelta(days=days_ago, hours=random.randint(1, 6))
        neto = round(total / 1.19)
        iva = total - neto
        reviewed = status == "approved"
        db.execute("""INSERT INTO invoices (tenant_id, file_name, vendor, vendor_rut, invoice_no, issue_date,
                                            neto, iva, total, currency, status, reason, reasons, corrections,
                                            extracted, confidence, reviewed_by, reviewed_at, created_at)
                      VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'CLP',%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                   (tid, fname, vendor, rut_by_name.get(vendor), number, created.date(),
                    neto, iva, total, status,
                    "; ".join(r["text"] for r in reasons) or None,
                    json.dumps(reasons, ensure_ascii=False),
                    json.dumps(corrections, ensure_ascii=False),
                    json.dumps({"neto": neto, "iva": iva, "total": total, "currency": "CLP"}),
                    88.5 if not reasons else 62.5,
                    "Javiera" if reviewed else None,
                    created + timedelta(minutes=random.randint(6, 40)) if reviewed else None,
                    created))

    seen: dict[str, str] = {}
    for lead in LEADS:
        payload = {k: lead.get(k) for k in ("name", "email", "phone", "source", "message")}
        verdict = leadscore.evaluate_lead(payload)
        key = verdict["dedupe_key"]
        dup = seen.get(key) if key else None
        created = now - timedelta(days=lead["days_ago"])
        due = None if dup else leadscore.due_at(verdict["next_action"]["due_hours"], now=created)
        row = db.execute("""INSERT INTO leads (tenant_id, name, email, phone, source, message, score, tier,
                                               reasons, score_breakdown, services, draft, status, dedupe_key,
                                               duplicate_of, next_action_kind, next_action_at, created_at)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,%s,%s)
                            RETURNING id""",
                         (tid, lead.get("name"), leadscore.norm_email(lead.get("email")),
                          leadscore.norm_phone(lead.get("phone")), lead.get("source"),
                          lead.get("message"),
                          verdict["score"], verdict["tier"],
                          json.dumps([r["text"] for r in verdict["reasons"]], ensure_ascii=False),
                          json.dumps(verdict["reasons"], ensure_ascii=False),
                          json.dumps(verdict["services"], ensure_ascii=False),
                          verdict["draft"], "discarded" if dup else lead["status"], key, dup,
                          verdict["next_action"]["kind"], due, created))
        if key and not dup and row:
            seen[key] = row["id"]

    # ReportBot: dos planillas de ventas ya procesadas (octubre y la primera quincena de noviembre).
    import hashlib
    for label, csv_text in (("ventas-octubre-2026.csv", DEMO_VENTAS_OCT),
                            ("ventas-noviembre-2026.csv", DEMO_VENTAS_NOV)):
        rows = reportbot.parse_csv(csv_text)
        m = reportbot.aggregate(rows)
        out = reportbot.report(m, "Clínica Sonrisa Ñuñoa")
        db.execute("""INSERT INTO sales_reports
            (tenant_id, file_name, source_sha256, period_start, period_end, rows_count, total,
             prev_total, delta_pct, currency, metrics, text, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)""",
            (tid, label, hashlib.sha256(csv_text.encode()).hexdigest(),
             m["period_start"], m["period_end"], m["rows"], m["total"], m["prev_total"],
             m["delta_pct"], m["currency"], json.dumps(m, ensure_ascii=False, default=str),
             out["text"], now - timedelta(days=3 if "nov" in label else 12)))

    # La calidad NO se siembra: se mide corriendo `python eval_replydesk.py`.
    print("seed listo:", TENANT, "(para la tarjeta de calidad: docker compose exec -T api python eval_replydesk.py)")


if __name__ == "__main__":
    run()
