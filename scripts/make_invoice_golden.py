#!/usr/bin/env python3
"""Genera el set dorado de InvoiceFlow: 12 facturas chilenas en PDF + `golden.json`.

Cada caso declara lo que el extractor debería devolver (campos y estado), para que
`apps/api/eval_invoiceflow.py` mida aciertos de verdad en vez de "parece que anda".

Uso:  /home/fperez/homelab/.venv/bin/python scripts/make_invoice_golden.py
Salida: samples/invoiceflow/*.pdf  ·  samples/invoiceflow/golden.json
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "samples", "invoiceflow")

MAX_TOTAL = 8_000_000  # tope configurado del tenant en el set dorado


def dv(body: str) -> str:
    factor, total = 2, 0
    for ch in reversed(body):
        total += int(ch) * factor
        factor = 2 if factor == 7 else factor + 1
    rest = 11 - (total % 11)
    return "0" if rest == 11 else "K" if rest == 10 else str(rest)


def rut(body: str) -> str:
    b = f"{int(body):,}".replace(",", ".")
    return f"{b}-{dv(body)}"


VENDORS = [
    ("Insumos Dentales SpA", rut("76123456")),
    ("Dental Supply SpA", rut("77234567")),
    ("Implantes CL SpA", rut("78345678")),
    ("Ortodoncia Insumos Ltda", rut("79456789")),
    ("Rayos X Digital SpA", rut("76567890")),
    ("Limpieza Pro SpA", rut("77678901")),
]


def clp(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def build_pdf(path: str, *, vendor: str, vendor_rut: str, folio: str | None, fecha: str,
              lines: list[tuple[str, int, int]], neto: int | None, iva: int | None,
              total: int | None, total_label: str = "TOTAL A PAGAR", empty: bool = False,
              notes: str = "") -> None:
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(path, pagesize=LETTER)
    w, h = LETTER
    if empty:
        c.rect(2 * cm, 2 * cm, w - 4 * cm, h - 4 * cm)
        c.showPage()
        c.save()
        return

    y = h - 2.5 * cm
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2.5 * cm, y, "FACTURA ELECTRONICA")
    c.setFont("Helvetica", 9)
    c.drawRightString(w - 2.5 * cm, y, "R.U.T.: " + vendor_rut)
    y -= 0.7 * cm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(2.5 * cm, y, "Proveedor: " + vendor)
    c.setFont("Helvetica", 9)
    c.drawRightString(w - 2.5 * cm, y, "S.I.I. - SANTIAGO")
    y -= 0.6 * cm
    if folio:
        c.drawString(2.5 * cm, y, "FOLIO N° " + folio)
    y -= 0.5 * cm
    c.drawString(2.5 * cm, y, "Fecha Emision: " + fecha)
    c.drawRightString(w - 2.5 * cm, y, "MONEDA: CLP")
    y -= 1.0 * cm

    c.setFont("Helvetica-Bold", 9)
    c.drawString(2.5 * cm, y, "Descripcion")
    c.drawRightString(w - 2.5 * cm, y, "Monto")
    y -= 0.45 * cm
    c.line(2.5 * cm, y, w - 2.5 * cm, y)
    y -= 0.55 * cm
    c.setFont("Helvetica", 9)
    for desc, qty, price in lines:
        c.drawString(2.5 * cm, y, f"{desc}")
        c.drawRightString(w - 2.5 * cm, y, f"{qty}    {clp(price)}    {clp(qty * price)}")
        y -= 0.5 * cm

    y -= 0.4 * cm
    for label, value in (("NETO", neto), ("IVA 19%", iva), (total_label, total)):
        if value is None:
            continue
        c.drawRightString(w - 4.0 * cm, y, label)
        c.drawRightString(w - 2.5 * cm, y, "$ " + clp(int(value)))
        y -= 0.5 * cm

    if notes:
        c.setFont("Helvetica-Oblique", 8)
        c.drawString(2.5 * cm, 2 * cm, notes)
    c.showPage()
    c.save()


def case(file: str, **kw) -> dict:
    return {"file": file, **kw}


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    v = {name: r for name, r in VENDORS}
    unknown_rut = rut("78111222")

    cases: list[dict] = []

    def add(kw: dict, expected: dict, *, pdf_kwargs: dict | None = None):
        spec = {**kw, **(pdf_kwargs or {})}
        build_pdf(os.path.join(OUT, spec["file"]), **{k: spec[k] for k in (
            "vendor", "vendor_rut", "folio", "fecha", "lines", "neto", "iva", "total")
            if k in spec}, **{k: spec[k] for k in ("empty", "notes", "total_label") if k in spec})
        cases.append({"file": spec["file"], "expected": expected, "notes": spec.get("notes", "")})

    # 1. limpia, 2 líneas, cuadra
    add({"file": "if-001-limpia.pdf", "vendor": "Insumos Dentales SpA", "vendor_rut": v["Insumos Dentales SpA"],
         "folio": "004512", "fecha": "15/10/2026",
         "lines": [("Guantes nitrilo caja 100", 12, 8500), ("Anestesia lidocaina 2%", 20, 3200)],
         "neto": 166000, "iva": 31540, "total": 197540},
        {"status": "pass", "vendor": "Insumos Dentales SpA", "invoice_no": "004512",
         "issue_date": "2026-10-15", "neto": 166000, "iva": 31540, "total": 197540,
         "currency": "CLP", "reasons": []})

    # 2. limpia, 3 líneas, montos grandes
    add({"file": "if-002-tres-lineas.pdf", "vendor": "Implantes CL SpA", "vendor_rut": v["Implantes CL SpA"],
         "folio": "007788", "fecha": "02/10/2026",
         "lines": [("Implante titanio premium", 8, 145000), ("Kit cirugia basico", 2, 39000),
                   ("Flete region metropolitana", 1, 12000)],
         "neto": 1250000, "iva": 237500, "total": 1487500},
        {"status": "pass", "vendor": "Implantes CL SpA", "invoice_no": "007788",
         "issue_date": "2026-10-02", "neto": 1250000, "iva": 237500, "total": 1487500,
         "currency": "CLP", "reasons": []})

    # 3. total descuadrado
    add({"file": "if-003-total-malo.pdf", "vendor": "Dental Supply SpA", "vendor_rut": v["Dental Supply SpA"],
         "folio": "091201", "fecha": "10/10/2026",
         "lines": [("Resina compuesta jeringa", 15, 27500)],
         "neto": 412500, "iva": 78375, "total": 500000},
        {"status": "review", "vendor": "Dental Supply SpA", "invoice_no": "091201",
         "issue_date": "2026-10-10", "neto": 412500, "iva": 78375, "total": 500000,
         "currency": "CLP", "reasons": ["total_mismatch"]})

    # 4. IVA mal calculado (10%)
    add({"file": "if-004-iva-malo.pdf", "vendor": "Ortodoncia Insumos Ltda",
         "vendor_rut": v["Ortodoncia Insumos Ltda"], "folio": "012107", "fecha": "08/10/2026",
         "lines": [("Brackets metalicos set", 10, 24500)],
         "neto": 245000, "iva": 24500, "total": 269500},
        {"status": "review", "vendor": "Ortodoncia Insumos Ltda", "invoice_no": "012107",
         "issue_date": "2026-10-08", "neto": 245000, "iva": 24500, "total": 269500,
         "currency": "CLP", "reasons": ["iva_mismatch"]})

    # 5. sin folio
    add({"file": "if-005-sin-folio.pdf", "vendor": "Rayos X Digital SpA", "vendor_rut": v["Rayos X Digital SpA"],
         "folio": None, "fecha": "12/10/2026",
         "lines": [("Revelado peliculas panoramicas", 30, 4200)],
         "neto": 126000, "iva": 23940, "total": 149940},
        {"status": "review", "vendor": "Rayos X Digital SpA", "invoice_no": None,
         "issue_date": "2026-10-12", "neto": 126000, "iva": 23940, "total": 149940,
         "currency": "CLP", "reasons": ["missing_field"]})

    # 6. RUT inválido
    add({"file": "if-006-rut-malo.pdf", "vendor": "Limpieza Pro SpA", "vendor_rut": "77.678.901-9",
         "folio": "023101", "fecha": "09/10/2026",
         "lines": [("Aseo profundo sala clinica", 1, 189000)],
         "neto": 189000, "iva": 35910, "total": 224910},
        {"status": "review", "vendor": "Limpieza Pro SpA", "invoice_no": "023101",
         "issue_date": "2026-10-09", "neto": 189000, "iva": 35910, "total": 224910,
         "currency": "CLP", "reasons": ["invalid_rut"]})

    # 7. proveedor no registrado
    add({"file": "if-007-proveedor-nuevo.pdf", "vendor": "Distribuidora Nova SpA", "vendor_rut": unknown_rut,
         "folio": "055001", "fecha": "14/10/2026",
         "lines": [("Insumos varios", 5, 12000)],
         "neto": 60000, "iva": 11400, "total": 71400},
        {"status": "review", "vendor": "Distribuidora Nova SpA", "invoice_no": "055001",
         "issue_date": "2026-10-14", "neto": 60000, "iva": 11400, "total": 71400,
         "currency": "CLP", "reasons": ["unknown_vendor"]})

    # 8. folio duplicado (mismo proveedor y folio que el caso 1)
    add({"file": "if-008-duplicada.pdf", "vendor": "Insumos Dentales SpA", "vendor_rut": v["Insumos Dentales SpA"],
         "folio": "004512", "fecha": "16/10/2026",
         "lines": [("Guantes nitrilo caja 100", 12, 8500), ("Anestesia lidocaina 2%", 20, 3200)],
         "neto": 166000, "iva": 31540, "total": 197540},
        {"status": "review", "vendor": "Insumos Dentales SpA", "invoice_no": "004512",
         "issue_date": "2026-10-16", "neto": 166000, "iva": 31540, "total": 197540,
         "currency": "CLP", "reasons": ["duplicate_folio"]})

    # 9. fecha vieja
    add({"file": "if-009-fecha-vieja.pdf", "vendor": "Dental Supply SpA", "vendor_rut": v["Dental Supply SpA"],
         "folio": "091305", "fecha": "03/03/2024",
         "lines": [("Fresas diamantadas", 40, 3900)],
         "neto": 156000, "iva": 29640, "total": 185640},
        {"status": "review", "vendor": "Dental Supply SpA", "invoice_no": "091305",
         "issue_date": "2024-03-03", "neto": 156000, "iva": 29640, "total": 185640,
         "currency": "CLP", "reasons": ["date_out_of_range"]})

    # 10. sobre el tope
    add({"file": "if-010-sobre-tope.pdf", "vendor": "Implantes CL SpA", "vendor_rut": v["Implantes CL SpA"],
         "folio": "007999", "fecha": "11/10/2026",
         "lines": [("Equipo radiografia intraoral", 1, 7983193)],
         "neto": 7983193, "iva": 1516807, "total": 9500000},
        {"status": "review", "vendor": "Implantes CL SpA", "invoice_no": "007999",
         "issue_date": "2026-10-11", "neto": 7983193, "iva": 1516807, "total": 9500000,
         "currency": "CLP", "reasons": ["total_over_cap"]})

    # 11. líneas no suman el neto
    add({"file": "if-011-lineas-mal.pdf", "vendor": "Ortodoncia Insumos Ltda",
         "vendor_rut": v["Ortodoncia Insumos Ltda"], "folio": "012233", "fecha": "07/10/2026",
         "lines": [("Tubos ortodonticos", 20, 12000), ("Arcos niquel titanio", 10, 24000)],
         "neto": 500000, "iva": 95000, "total": 595000},
        {"status": "review", "vendor": "Ortodoncia Insumos Ltda", "invoice_no": "012233",
         "issue_date": "2026-10-07", "neto": 500000, "iva": 95000, "total": 595000,
         "currency": "CLP", "reasons": ["lines_mismatch"]})

    # 12. PDF sin texto (escaneado)
    add({"file": "if-012-escaneada.pdf", "vendor": None, "vendor_rut": None, "folio": None,
         "fecha": "", "lines": [], "neto": None, "iva": None, "total": None, "empty": True},
        {"status": "review", "reason_codes": ["no_text"], "reasons": ["no_text"]})

    with open(os.path.join(OUT, "golden.json"), "w", encoding="utf-8") as fh:
        json.dump({"today": "2026-11-09", "max_invoice_total": MAX_TOTAL,
                   "vendors": [{"name": n, "rut": r} for n, r in VENDORS],
                   "cases": cases}, fh, ensure_ascii=False, indent=2)
    print(f"{len(cases)} PDFs + golden.json en {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
