"""Datos de demostración: un tenant real-ish (clínica), conversaciones, facturas, leads, KB y eval.

Idempotente: borra el tenant y lo vuelve a crear. Reparte la actividad en 7 días para que el
panel muestre una semana con volumen real, no un solo punto.
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone

import db

TENANT = "clinica-sonrisa-nunoa"
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
     [{"code": "lines_mismatch", "text": "La suma de las líneas no cuadra con el neto (189030.0 ≠ 167252.10)"}],
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
    ("Josefa Contreras", "josefa.c@mail.com", "formulario web", 88, "HOT",
     ["Pidió hora en el formulario", "Presupuesto declarado CLP 500k", "Zona Ñuñoa"], 0),
    ("Rodrigo Peña", "rpena@mail.com", "instagram", 61, "WARM",
     ["Consultó por ortodoncia", "Sin presupuesto declarado"], 1),
    ("Ignacio Vera", "ivera@mail.com", "formulario web", 24, "COLD",
     ["Sólo pide lista de precios"], 2),
    ("Fernanda Lillo", "flillo@mail.com", "referido", 92, "HOT",
     ["Viene referida por una paciente", "Quiere iniciar tratamiento este mes"], 3),
    ("Tomás Aguilera", "taguilera@mail.com", "instagram", 47, "WARM",
     ["Pregunta por financiamiento"], 5),
]


def run() -> None:
    db.migrate()
    db.execute("DELETE FROM tenants WHERE slug=%s", (TENANT,))
    t = db.execute("""INSERT INTO tenants (slug, name, industry, config) VALUES (%s,%s,%s,%s) RETURNING id""",
                   (TENANT, "Clínica Dental Sonrisa Ñuñoa", "salud",
                    json.dumps({"ciudad": "Santiago", "horario": "L-V 09:00-19:00, S 09:00-14:00",
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

    for name, email, source, score, tier, reasons, days_ago in LEADS:
        db.execute("""INSERT INTO leads (tenant_id, name, email, source, score, tier, reasons, draft, status, created_at)
                      VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                   (tid, name, email, source, score, tier, json.dumps(reasons, ensure_ascii=False),
                    f"Hola {name.split()[0]}, gracias por escribirnos. Por lo que cuentas te conviene una "
                    f"evaluación inicial; tengo jueves 11:00 o viernes 17:30. ¿Cuál te sirve?",
                    "new" if tier != "COLD" else "discarded", now - timedelta(days=days_ago)))

    # La calidad NO se siembra: se mide corriendo `python eval_replydesk.py`.
    print("seed listo:", TENANT, "(para la tarjeta de calidad: docker compose exec -T api python eval_replydesk.py)")


if __name__ == "__main__":
    run()
