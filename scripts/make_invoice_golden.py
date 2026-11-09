#!/usr/bin/env python3
"""Genera el set dorado de InvoiceFlow: 30 facturas en PDF + `golden.json`.

Cada caso declara lo que el extractor debería devolver (campos y estado), para que
`apps/api/eval_invoiceflow.py` mida aciertos de verdad en vez de "parece que anda".

Variantes que cubre el set: formato chileno clásico, formato tabla con columnas,
factura en inglés (USD), exenta sin IVA, multi-página, descuento por línea,
RUT sin formato, folio alfanumérico, fecha futura y fecha en el borde, total justo
en el tope, y los 10 motivos de revisión.

Uso:  /home/fperez/homelab/.venv/bin/python scripts/make_invoice_golden.py
Salida: samples/invoiceflow/*.pdf  ·  samples/invoiceflow/golden.json
"""
from __future__ import annotations

import json
import os
import sys
from decimal import Decimal

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


def money(n, currency: str = "CLP") -> str:
    """CLP sin decimales con punto de miles; USD con dos decimales y coma de miles."""
    if currency == "CLP":
        return f"{int(round(float(n))):,}".replace(",", ".")
    return f"{Decimal(str(n)):,.2f}"


def build_pdf(path: str, *, vendor: str, vendor_rut: str | None, folio: str | None, fecha: str,
              lines: list[tuple], neto, iva, total, currency: str = "CLP",
              layout: str = "cl", total_label: str = "TOTAL A PAGAR",
              iva_label: str = "IVA 19%", neto_label: str = "NETO",
              empty: bool = False, notes: str = "") -> None:
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

    def header(page: int) -> None:
        y = h - 2.5 * cm
        c.setFont("Helvetica-Bold", 16)
        c.drawString(2.5 * cm, y, "FACTURA ELECTRONICA" if currency == "CLP" else "INVOICE")
        c.setFont("Helvetica", 9)
        c.drawRightString(w - 2.5 * cm, y, ("R.U.T.: " + vendor_rut) if vendor_rut else "S.I.I.")
        y -= 0.7 * cm
        c.setFont("Helvetica-Bold", 11)
        c.drawString(2.5 * cm, y, ("Proveedor: " if currency == "CLP" else "Vendor: ") + vendor)
        c.setFont("Helvetica", 9)
        c.drawRightString(w - 2.5 * cm, y, "S.I.I. - SANTIAGO" if currency == "CLP" else "SANTIAGO, CHILE")
        y -= 0.6 * cm
        if folio:
            c.drawString(2.5 * cm, y, ("FOLIO N° " if currency == "CLP" else "Invoice No: ") + folio)
        if page > 1:
            c.drawRightString(w - 2.5 * cm, y, f"pag. {page}")
        y -= 0.5 * cm
        c.drawString(2.5 * cm, y, ("Fecha Emision: " if currency == "CLP" else "Date: ") + fecha)
        c.drawRightString(w - 2.5 * cm, y, "MONEDA: " + currency)
        y -= 1.0 * cm
        c.setFont("Courier-Bold" if layout == "table" else "Helvetica-Bold", 9)
        if layout == "table":
            c.drawString(2.5 * cm, y, f"{'Descripcion':<40}{'Cant.':>7}{'P.Unit.':>16}{'Monto':>17}")
        else:
            c.drawString(2.5 * cm, y, "Descripcion")
            c.drawRightString(w - 2.5 * cm, y, "Monto")
        y -= 0.45 * cm
        c.line(2.5 * cm, y, w - 2.5 * cm, y)
        return y - 0.55 * cm

    line_font = "Courier" if layout == "table" else "Helvetica"
    y = header(1)
    page = 1
    for item in lines:
        desc, qty, price = item[0], item[1], item[2]
        amount = item[3] if len(item) > 3 else Decimal(str(qty)) * Decimal(str(price))
        if y < 3.2 * cm:
            c.showPage()
            page += 1
            y = header(page)
        c.setFont(line_font, 9)
        if layout == "table":
            c.drawString(2.5 * cm, y, f"{desc[:38]:<40}{qty:>7}{money(price, currency):>16}{money(amount, currency):>17}")
        else:
            c.drawString(2.5 * cm, y, f"{desc}")
            c.drawRightString(w - 2.5 * cm, y, f"{qty}    {money(price, currency)}    {money(amount, currency)}")
        y -= 0.5 * cm

    if y < 4.2 * cm:
        c.showPage()
        page += 1
        y = header(page)
    y -= 0.4 * cm
    c.setFont("Helvetica", 9)
    rows = []
    if neto is not None:
        rows.append((neto_label, neto))
    if iva is not None:
        rows.append((iva_label, iva))
    if total is not None:
        rows.append((total_label, total))
    for label, value in rows:
        c.drawRightString(w - 4.6 * cm, y, label)
        c.drawRightString(w - 2.5 * cm, y, ("$ " if currency == "CLP" else "US$ ") + money(value, currency))
        y -= 0.5 * cm

    if notes:
        c.setFont("Helvetica-Oblique", 8)
        c.drawString(2.5 * cm, 2 * cm, notes)
    c.showPage()
    c.save()


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    v = {name: r for name, r in VENDORS}
    unknown_rut = rut("78111222")
    cases: list[dict] = []

    def add(*args, **kwargs) -> None:
        *rest, expect = args
        if len(rest) == 2:                     # add(*cl(...), expect(...))
            file, pdf = rest[0], {**rest[1], **kwargs}
        else:                                  # add("archivo.pdf", expect, **kwargs)
            file, pdf = rest[0], kwargs
        build_pdf(os.path.join(OUT, file), **pdf)
        cases.append({"file": file, "expected": expect, "notes": pdf.get("notes", "")})

    def cl(num: str, vendor: str, vendor_rut: str | None, folio: str | None, fecha: str,
           lines: list[tuple], neto, iva, total, **kw) -> tuple[str, dict, dict]:
        """Caso chileno en el layout clásico."""
        return (f"if-{num}.pdf", dict(vendor=vendor, vendor_rut=vendor_rut, folio=folio, fecha=fecha,
                                      lines=lines, neto=neto, iva=iva, total=total, **kw))

    def expect(status, reasons, **fields):
        return {"status": status, "reasons": reasons, **fields}

    def fields_of(vendor, folio, iso, neto, iva, total, currency="CLP"):
        return dict(vendor=vendor, invoice_no=folio, issue_date=iso, neto=neto,
                    iva=iva, total=total, currency=currency)

    # ---------------------------------------------------------------- 1-12: base
    add(*cl("001-limpia", "Insumos Dentales SpA", v["Insumos Dentales SpA"], "004512", "15/10/2026",
            [("Guantes nitrilo caja 100", 12, 8500), ("Anestesia lidocaina 2%", 20, 3200)],
            166000, 31540, 197540),
        expect("pass", [], **fields_of("Insumos Dentales SpA", "004512", "2026-10-15", 166000, 31540, 197540)))

    add(*cl("002-tres-lineas", "Implantes CL SpA", v["Implantes CL SpA"], "007788", "02/10/2026",
            [("Implante titanio premium", 8, 145000), ("Kit cirugia basico", 2, 39000),
             ("Flete region metropolitana", 1, 12000)],
            1250000, 237500, 1487500),
        expect("pass", [], **fields_of("Implantes CL SpA", "007788", "2026-10-02", 1250000, 237500, 1487500)))

    add(*cl("003-total-malo", "Dental Supply SpA", v["Dental Supply SpA"], "091201", "10/10/2026",
            [("Resina compuesta jeringa", 15, 27500)], 412500, 78375, 500000),
        expect("review", ["total_mismatch"],
               **fields_of("Dental Supply SpA", "091201", "2026-10-10", 412500, 78375, 500000)))

    add(*cl("004-iva-malo", "Ortodoncia Insumos Ltda", v["Ortodoncia Insumos Ltda"], "012107", "08/10/2026",
            [("Brackets metalicos set", 10, 24500)], 245000, 24500, 269500),
        expect("review", ["iva_mismatch"],
               **fields_of("Ortodoncia Insumos Ltda", "012107", "2026-10-08", 245000, 24500, 269500)))

    add(*cl("005-sin-folio", "Rayos X Digital SpA", v["Rayos X Digital SpA"], None, "12/10/2026",
            [("Revelado peliculas panoramicas", 30, 4200)], 126000, 23940, 149940),
        expect("review", ["missing_field"],
               **fields_of("Rayos X Digital SpA", None, "2026-10-12", 126000, 23940, 149940)))

    add(*cl("006-rut-malo", "Limpieza Pro SpA", "77.678.901-9", "023101", "09/10/2026",
            [("Aseo profundo sala clinica", 1, 189000)], 189000, 35910, 224910),
        expect("review", ["invalid_rut"],
               **fields_of("Limpieza Pro SpA", "023101", "2026-10-09", 189000, 35910, 224910)))

    add(*cl("007-proveedor-nuevo", "Distribuidora Nova SpA", unknown_rut, "055001", "14/10/2026",
            [("Insumos varios", 5, 12000)], 60000, 11400, 71400),
        expect("review", ["unknown_vendor"],
               **fields_of("Distribuidora Nova SpA", "055001", "2026-10-14", 60000, 11400, 71400)))

    add(*cl("008-duplicada", "Insumos Dentales SpA", v["Insumos Dentales SpA"], "004512", "16/10/2026",
            [("Guantes nitrilo caja 100", 12, 8500), ("Anestesia lidocaina 2%", 20, 3200)],
            166000, 31540, 197540),
        expect("review", ["duplicate_folio"],
               **fields_of("Insumos Dentales SpA", "004512", "2026-10-16", 166000, 31540, 197540)))

    add(*cl("009-fecha-vieja", "Dental Supply SpA", v["Dental Supply SpA"], "091305", "03/03/2024",
            [("Fresas diamantadas", 40, 3900)], 156000, 29640, 185640),
        expect("review", ["date_out_of_range"],
               **fields_of("Dental Supply SpA", "091305", "2024-03-03", 156000, 29640, 185640)))

    add(*cl("010-sobre-tope", "Implantes CL SpA", v["Implantes CL SpA"], "007999", "11/10/2026",
            [("Equipo radiografia intraoral", 1, 7983193)], 7983193, 1516807, 9500000),
        expect("review", ["total_over_cap"],
               **fields_of("Implantes CL SpA", "007999", "2026-10-11", 7983193, 1516807, 9500000)))

    add(*cl("011-lineas-mal", "Ortodoncia Insumos Ltda", v["Ortodoncia Insumos Ltda"], "012233", "07/10/2026",
            [("Tubos ortodonticos", 20, 12000), ("Arcos niquel titanio", 10, 24000)],
            500000, 95000, 595000),
        expect("review", ["lines_mismatch"],
               **fields_of("Ortodoncia Insumos Ltda", "012233", "2026-10-07", 500000, 95000, 595000)))

    add("if-012-escaneada.pdf", {"status": "review", "reason_codes": ["no_text"], "reasons": ["no_text"]},
        vendor="", vendor_rut=None, folio=None, fecha="", lines=[], neto=None, iva=None, total=None, empty=True)

    # ------------------------------------------------------- 13-30: variantes reales
    # 13. factura en inglés, USD, todo cuadra
    add("if-013-usd-limpia.pdf",
        expect("pass", [], **fields_of("Dental Imaging LLC", "INV-2041", "2026-10-05",
                                      2580.00, 490.20, 3070.20, "USD")),
        vendor="Dental Imaging LLC", vendor_rut=None, folio="INV-2041", fecha="05/10/2026",
        lines=[("Intraoral scanner", 1, 2400.00), ("Software license 1y", 1, 180.00)],
        neto=2580.00, iva=490.20, total=3070.20, currency="USD", layout="en",
        total_label="TOTAL DUE", iva_label="Tax (19%)", neto_label="Subtotal")

    # 14. USD con el total inflado 30 dólares
    add("if-014-usd-total-malo.pdf",
        expect("review", ["total_mismatch"], **fields_of("Dental Imaging LLC", "INV-2042", "2026-10-06",
                                                        2580.00, 490.20, 3100.00, "USD")),
        vendor="Dental Imaging LLC", vendor_rut=None, folio="INV-2042", fecha="06/10/2026",
        lines=[("Intraoral scanner", 1, 2400.00), ("Software license 1y", 1, 180.00)],
        neto=2580.00, iva=490.20, total=3100.00, currency="USD", layout="en",
        total_label="TOTAL DUE", iva_label="Tax (19%)", neto_label="Subtotal")

    # 15. exenta: sin IVA, neto = total
    add(*cl("015-exenta", "Limpieza Pro SpA", v["Limpieza Pro SpA"], "023140", "13/10/2026",
            [("Aseo semanal octubre", 4, 78000)], 312000, None, 312000, iva_label="IVA (exento)"),
        expect("pass", [], **fields_of("Limpieza Pro SpA", "023140", "2026-10-13", 312000, None, 312000)))

    # 16. layout tabla con columnas
    add("if-016-tabla.pdf",
        expect("pass", [], **fields_of("Insumos Dentales SpA", "004530", "2026-10-17", 227260, 43179, 270439)),
        vendor="Insumos Dentales SpA", vendor_rut=v["Insumos Dentales SpA"], folio="004530", fecha="17/10/2026",
        lines=[("Guantes latex caja 100", 10, 7800), ("Mascarillas quirurgicas", 20, 3200),
               ("Baberos desechables", 60, 1421)],
        neto=227260, iva=43179, total=270439, layout="table", total_label="TOTAL")

    # 17. multi-página: 14 líneas, totales en la segunda hoja
    many = [(f"Insumo clinico linea {i:02d}", 2, 3500 + i * 250) for i in range(1, 15)]
    many_neto = sum(q * p for _, q, p in many)
    add("if-017-multipagina.pdf",
        expect("pass", [], **fields_of("Dental Supply SpA", "091420", "2026-10-18",
                                      many_neto, int(many_neto * 0.19), many_neto + int(many_neto * 0.19))),
        vendor="Dental Supply SpA", vendor_rut=v["Dental Supply SpA"], folio="091420", fecha="18/10/2026",
        lines=many, neto=many_neto, iva=int(many_neto * 0.19), total=many_neto + int(many_neto * 0.19))

    # 18. fecha futura
    add(*cl("018-fecha-futura", "Rayos X Digital SpA", v["Rayos X Digital SpA"], "055210", "20/12/2026",
            [("Scanner de placas", 1, 450000)], 450000, 85500, 535500),
        expect("review", ["date_out_of_range"],
               **fields_of("Rayos X Digital SpA", "055210", "2026-12-20", 450000, 85500, 535500)))

    # 19. justo en el tope: 8.000.000 no debe marcar nada
    add(*cl("019-en-el-tope", "Implantes CL SpA", v["Implantes CL SpA"], "008010", "19/10/2026",
            [("Equipo de esterilizacion", 1, 6722689)], 6722689, 1277311, 8000000),
        expect("pass", [], **fields_of("Implantes CL SpA", "008010", "2026-10-19", 6722689, 1277311, 8000000)))

    # 20. descuento por línea: la suma de líneas incluye el negativo
    add(*cl("020-descuento", "Ortodoncia Insumos Ltda", v["Ortodoncia Insumos Ltda"], "012300", "21/10/2026",
            [("Tratamiento ortodontico mensual", 1, 500000),
             ("Descuento convenio clinico", 1, -50000)],
            450000, 85500, 535500),
        expect("pass", [], **fields_of("Ortodoncia Insumos Ltda", "012300", "2026-10-21", 450000, 85500, 535500)))

    # 21. etiquetas SUBTOTAL / IVA / TOTAL
    add("if-021-solo-subtotal.pdf",
        expect("pass", [], **fields_of("Rayos X Digital SpA", "055240", "2026-10-22", 96000, 18240, 114240)),
        vendor="Rayos X Digital SpA", vendor_rut=v["Rayos X Digital SpA"], folio="055240", fecha="22/10/2026",
        lines=[("Revelado bite wings", 24, 4000)], neto=96000, iva=18240, total=114240,
        neto_label="SUBTOTAL", total_label="TOTAL")

    # 22. sin total en el documento
    add(*cl("022-sin-total", "Dental Supply SpA", v["Dental Supply SpA"], "091455", "23/10/2026",
            [("Sellantes dentales", 30, 5200)], 156000, 29640, None),
        expect("review", ["missing_field"],
               **fields_of("Dental Supply SpA", "091455", "2026-10-23", 156000, 29640, None)))

    # 23. IVA con decimales que redondea (neto 123.456 → IVA 23.456,64 → 23.457)
    add(*cl("023-iva-decimales", "Insumos Dentales SpA", v["Insumos Dentales SpA"], "004545", "24/10/2026",
            [("Compositos jeringa", 7, 17636.57)], 123456, 23457, 146913),
        expect("pass", [], **fields_of("Insumos Dentales SpA", "004545", "2026-10-24", 123456, 23457, 146913)))

    # 24. RUT sin puntos ni guión
    add(*cl("024-rut-sin-formato", "Limpieza Pro SpA", v["Limpieza Pro SpA"].replace(".", "").replace("-", ""), "023155", "25/10/2026",
            [("Aseo profundo", 1, 189000)], 189000, 35910, 224910),
        expect("pass", [], **fields_of("Limpieza Pro SpA", "023155", "2026-10-25", 189000, 35910, 224910)))

    # 25. nombre largo con S.A. y proveedor no registrado
    add(*cl("025-nombre-largo", "Distribuidora Odontologica del Pacifico S.A.", unknown_rut, "066002", "26/10/2026",
            [("Kit de fresas", 12, 9500)], 114000, 21660, 135660),
        expect("review", ["unknown_vendor"],
               **fields_of("Distribuidora Odontologica del Pacifico S.A.", "066002", "2026-10-26",
                           114000, 21660, 135660)))

    # 26. etiqueta IMPUESTO en vez de IVA
    add(*cl("026-impuesto", "Ortodoncia Insumos Ltda", v["Ortodoncia Insumos Ltda"], "012315", "27/10/2026",
            [("Retenedores", 5, 32000)], 160000, 30400, 190400, iva_label="IMPUESTO 19%"),
        expect("pass", [], **fields_of("Ortodoncia Insumos Ltda", "012315", "2026-10-27", 160000, 30400, 190400)))

    # 27. tabla + multi-página
    many2 = [(f"Consumible tabla {i:02d}", 3, 2100 + i * 130) for i in range(1, 17)]
    neto2 = sum(q * p for _, q, p in many2)
    add("if-027-tabla-multipagina.pdf",
        expect("pass", [], **fields_of("Insumos Dentales SpA", "004560", "2026-10-28",
                                      neto2, int(neto2 * 0.19), neto2 + int(neto2 * 0.19))),
        vendor="Insumos Dentales SpA", vendor_rut=v["Insumos Dentales SpA"], folio="004560", fecha="28/10/2026",
        lines=many2, neto=neto2, iva=int(neto2 * 0.19), total=neto2 + int(neto2 * 0.19), layout="table",
        total_label="TOTAL A PAGAR")

    # 28. USD con tres líneas y centavos
    add("if-028-usd-lineas.pdf",
        expect("pass", [], **fields_of("Dental Imaging LLC", "INV-2043", "2026-10-07",
                                      1862.90, 353.95, 2216.85, "USD")),
        vendor="Dental Imaging LLC", vendor_rut=None, folio="INV-2043", fecha="07/10/2026",
        lines=[("Sensor cable", 2, 145.20), ("Mounting kit", 1, 372.00), ("Calibration service", 350, 3.43)],
        neto=1862.90, iva=353.95, total=2216.85, currency="USD", layout="en",
        total_label="TOTAL DUE", iva_label="Tax (19%)", neto_label="Subtotal")

    # 29. fecha exactamente en el borde (365 días antes del 2026-11-09)
    add(*cl("029-fecha-borde", "Dental Supply SpA", v["Dental Supply SpA"], "091500", "09/11/2025",
            [("Repuestos unidad", 3, 48000)], 144000, 27360, 171360),
        expect("pass", [], **fields_of("Dental Supply SpA", "091500", "2025-11-09", 144000, 27360, 171360)))

    # 30. folio alfanumérico
    add(*cl("030-folio-alfa", "Rayos X Digital SpA", v["Rayos X Digital SpA"], "RX-2026/0455", "29/10/2026",
            [("Informe radiologico", 8, 15500)], 124000, 23560, 147560),
        expect("pass", [], **fields_of("Rayos X Digital SpA", "RX-2026/0455", "2026-10-29",
                                      124000, 23560, 147560)))

    with open(os.path.join(OUT, "golden.json"), "w", encoding="utf-8") as fh:
        json.dump({"today": "2026-11-09", "max_invoice_total": MAX_TOTAL,
                   "vendors": [{"name": n, "rut": r} for n, r in VENDORS],
                   "cases": cases}, fh, ensure_ascii=False, indent=2)
    print(f"{len(cases)} PDFs + golden.json en {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
