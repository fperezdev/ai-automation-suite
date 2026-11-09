"""InvoiceFlow — extracción y validación de facturas chilenas (y en inglés).

Determinista, sin LLM en el camino crítico: texto del PDF → campos → reglas → PASS / REVIEW.
Cada motivo de revisión es un código estable (`total_mismatch`) con su texto para el panel,
así el eval puede medir aciertos por motivo y el humano sabe qué mirar.

Las funciones de este módulo son puras (texto/dicts → dicts) para poder medirlas en
`eval_invoiceflow.py` sin base de datos.
"""
from __future__ import annotations

import io
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

TOLERANCE_CLP = Decimal("1")        # redondeo de 1 peso en documentos chilenos
TOLERANCE_USD = Decimal("0.02")
IVA_CLP = Decimal("0.19")
DEFAULT_MAX_TOTAL = Decimal("8000000")

REASON_TEXT = {
    "missing_field": "Falta un campo obligatorio ({field})",
    "total_mismatch": "Neto + IVA no cuadra con el total ({neto} + {iva} ≠ {total})",
    "iva_mismatch": "El IVA no corresponde al 19% del neto (esperado {expected})",
    "lines_mismatch": "La suma de las líneas no cuadra con el neto ({sum} ≠ {neto})",
    "invalid_rut": "El RUT del proveedor no es válido ({rut})",
    "unknown_vendor": "Proveedor no registrado en el maestro ({rut})",
    "duplicate_folio": "Folio ya registrado para este proveedor (posible duplicado de {existing})",
    "date_out_of_range": "Fecha fuera de rango ({date})",
    "total_over_cap": "Total sobre el tope configurado ({total} > {cap})",
    "no_text": "El PDF no tiene texto extraíble (¿escaneado?)",
    "low_confidence": "Extracción de baja confianza ({confidence}%)",
}


# ------------------------------------------------------------------ utilidades
def _norm(s: str) -> str:
    """Minúsculas sin tildes, para comparar etiquetas."""
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def parse_number(raw: str | None) -> Decimal | None:
    """Monto en formato chileno o inglés. '297.500' -> 297500, '1.234,56' -> 1234.56."""
    if raw is None:
        return None
    s = str(raw).strip().replace("$", "").replace("CLP", "").replace("USD", "").replace(" ", "")
    s = s.replace("\u00a0", "")
    # quitar símbolos de moneda sueltos
    s = re.sub(r"[^0-9.,-]", "", s)
    if not s or s in {"-", ".", ","}:
        return None
    neg = s.startswith("-")
    s = s.lstrip("-")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):          # 1.234,56
            s = s.replace(".", "").replace(",", ".")
        else:                                     # 1,234.56
            s = s.replace(",", "")
    elif "," in s:
        head, _, tail = s.rpartition(",")
        s = (head.replace(".", "") + "." + tail) if len(tail) in (1, 2) else s.replace(",", "")
    elif "." in s:
        parts = s.split(".")
        if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3):
            s = "".join(parts)                    # 297.500 -> 297500
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None
    return -d if neg else d


def parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    s = str(raw).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def normalize_rut(raw: str | None) -> tuple[str | None, bool]:
    """Devuelve (rut formateado 76.543.210-K, válido según módulo 11)."""
    if not raw:
        return None, False
    s = re.sub(r"[^0-9kK]", "", str(raw)).upper()
    if len(s) < 8 or len(s) > 9:
        return None, False
    body, dv = s[:-1], s[-1]
    if not body.isdigit():
        return None, False
    factor, total = 2, 0
    for ch in reversed(body):
        total += int(ch) * factor
        factor = 2 if factor == 7 else factor + 1
    rest = 11 - (total % 11)
    expected = "0" if rest == 11 else "K" if rest == 10 else str(rest)
    formatted = f"{int(body):,}".replace(",", ".") + "-" + dv
    return formatted, expected == dv


def _search(patterns: list[str], text: str, flags=re.IGNORECASE) -> tuple[str | None, bool]:
    """Primer grupo capturado y si vino de una etiqueta explícita (confianza alta)."""
    for p in patterns:
        m = re.search(p, text, flags)
        if m:
            return m.group(1).strip(), True
    return None, False


def pdf_text(data: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


# ------------------------------------------------------------------ extracción
def extract_fields(text: str) -> dict:
    """Campos fiscales del texto del PDF. Devuelve valores + confianza por campo."""
    t = text.replace("\r", "")
    fields: dict = {}
    conf: dict[str, float] = {}

    # folio / número
    folio, labeled = _search(
        [r"folio\s*(?:n[º°o.]*)?\s*[:#]?\s*([A-Z0-9][A-Z0-9\-\./]{1,20})",
         r"n[º°]\s*(?:de\s*)?factura\s*[:#]?\s*([A-Z0-9][A-Z0-9\-\./]{1,20})",
         r"invoice\s*(?:number|no\.?|#)\s*[:#]?\s*([A-Z0-9][A-Z0-9\-\./]{1,20})"],
        t)
    fields["invoice_no"] = folio.rstrip(".-") if folio else None
    conf["invoice_no"] = 1.0 if labeled else 0.0

    # fecha de emisión
    fdate, labeled = _search(
        [r"fecha\s*(?:de\s*)?(?:emisi[oó]n|emision|factura)\s*[:#]?\s*([0-9]{1,4}[/\-\.][0-9]{1,2}[/\-\.][0-9]{1,4})",
         r"^\s*date\s*[:#]?\s*([0-9]{1,4}[/\-\.][0-9]{1,2}[/\-\.][0-9]{1,4})",
         r"fecha\s*[:#]?\s*([0-9]{1,4}[/\-\.][0-9]{1,2}[/\-\.][0-9]{1,4})"],
        t, re.IGNORECASE | re.MULTILINE)
    fields["issue_date"] = parse_date(fdate)
    conf["issue_date"] = 1.0 if (labeled and fields["issue_date"]) else 0.0

    # RUT del proveedor (el primero del documento suele ser el emisor)
    rut_raw, labeled = _search([r"r\.?\s*u\.?\s*t\.?\s*[:#]?\s*([0-9][0-9\.]{6,12}\s*-?\s*[0-9kK])"], t)
    fields["vendor_rut"], rut_ok = normalize_rut(rut_raw)
    conf["vendor_rut"] = (1.0 if rut_ok else 0.5) if rut_raw else 0.0
    fields["rut_valid"] = rut_ok

    # proveedor
    vendor, labeled = _search(
        [r"^\s*(?:proveedor|raz[oó]n social|emisor)\s*[:#]?\s*(.+)$",
         r"^\s*INVOICE\s+(\S.{2,60})$"],
        t, re.IGNORECASE | re.MULTILINE)
    if not vendor:
        # heurística: primera línea con forma de razón social
        m = re.search(r"^([A-Z][^\n]{3,60}(?:SpA|S\.A\.|Ltda|LTDA|E\.I\.R\.L|LLC|Inc\.?|Spa))$",
                      t, re.MULTILINE)
        vendor = m.group(1).strip() if m else None
        labeled = False
    fields["vendor"] = re.sub(r"\s{2,}", " ", vendor).strip(" -:") if vendor else None
    conf["vendor"] = 1.0 if labeled else (0.6 if vendor else 0.0)

    # moneda
    cur = None
    if re.search(r"\bUSD\b|US\$", t):
        cur = "USD"
    elif re.search(r"\bEUR\b|€", t):
        cur = "EUR"
    elif re.search(r"\bCLP\b", t) or re.search(r"r\.?\s*u\.?\s*t", _norm(t)):
        cur = "CLP"
    elif fields["vendor_rut"]:
        cur = "CLP"
    fields["currency"] = cur or "CLP"

    # montos
    neto, l1 = _search([r"\bneto\b[^\d\-]{0,12}([\-\d][\d.,]*)",
                        r"\bsub\s*-?\s*total\b[^\d\-]{0,12}([\-\d][\d.,]*)",
                        r"\bsubtotal\b[^\d\-]{0,12}([\-\d][\d.,]*)",
                        r"monto\s*neto[^\d\-]{0,12}([\-\d][\d.,]*)"], t)
    # excluir la fila "Subtotal" cuando es la suma de líneas: es la misma cifra, sirve igual
    iva, l2 = _search([r"\btax\s*\(?\s*\d{1,2}\s*%\s*\)?\s*[^\d\-]{0,8}([\-\d][\d.,]*)",
                       r"\biva\s*\(?\s*\d{1,2}\s*%\s*\)?\s*[^\d\-]{0,8}([\-\d][\d.,]*)",
                       r"\biva\b[^\d\-]{0,14}([\-\d][\d.,]*)",
                       r"i\.?\s*v\.?\s*a\.?[^\d\-]{0,14}([\-\d][\d.,]*)",
                       r"\btax\b[^\d\-]{0,14}([\-\d][\d.,]*)",
                       r"\bimpuesto\b[^\d\-]{0,14}([\-\d][\d.,]*)"], t)
    total, l3 = _search([r"\btotal\s*(?:a\s*pagar)?\b[^\d\-]{0,14}([\-\d][\d.,]*)",
                         r"\bimporte\s*total\b[^\d\-]{0,14}([\-\d][\d.,]*)"], t)

    lines = parse_lines(t)
    fields["neto"] = parse_number(neto)
    fields["iva"] = parse_number(iva)
    fields["total"] = parse_number(total)
    fields["lines"] = lines
    for k, lab in (("neto", l1), ("iva", l2), ("total", l3)):
        conf[k] = 1.0 if (lab and fields[k] is not None) else 0.0

    fields["confidence"] = round(100 * sum(conf.values()) / len(conf), 1) if conf else 0.0
    if fields["lines"]:
        fields["confidence"] = round((fields["confidence"] * 6 + 100) / 7, 1)
    fields["field_confidence"] = conf
    return fields


def parse_lines(text: str) -> list[dict]:
    """Filas 'descripción  cantidad  precio  monto' (en una línea o en celdas sueltas)."""
    out: list[dict] = []
    for raw in text.splitlines():
        line = raw.strip()
        if len(line) < 8:
            continue
        m = re.match(r"^(?P<desc>.{3,80}?)\s{2,}(?P<qty>\d{1,4})\s+(?P<price>[\d.,]+)\s+(?P<amount>[\d.,]+)$", line)
        if not m:
            m = re.match(r"^(?P<desc>.{3,80}?)\s+(?P<qty>\d{1,4})\s+(?P<price>\d[\d.,]*\d|\d)\s+(?P<amount>\d[\d.,]*\d|\d)$", line)
        if not m:
            continue
        desc = m.group("desc").strip(" -:")
        if _norm(desc).startswith(("subtotal", "total", "iva", "tax", "descripcion")):
            continue
        qty = int(m.group("qty"))
        price = parse_number(m.group("price"))
        amount = parse_number(m.group("amount"))
        if price is None or amount is None:
            continue
        out.append({"description": desc, "qty": qty,
                    "unit_price": float(price), "amount": float(amount)})
    if out:
        return out

    # descripción en una línea y "cantidad  precio  monto" en la siguiente
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    pattern = re.compile(r"^(?P<qty>\d{1,4})\s{2,}(?P<price>[\d.,]+)\s{2,}(?P<amount>[\d.,]+)$")
    for i in range(1, len(lines)):
        m = pattern.match(lines[i])
        desc = lines[i - 1]
        if not m or _norm(desc).startswith(("subtotal", "total", "iva", "tax", "descripcion", "descripción")):
            continue
        pr, am = parse_number(m.group("price")), parse_number(m.group("amount"))
        if pr is None or am is None:
            continue
        out.append({"description": desc, "qty": int(m.group("qty")),
                    "unit_price": float(pr), "amount": float(am)})
    if out:
        return out

    # PDFs que extraen cada celda en su propia línea: bloques desc / qty / precio / monto
    stop = {"subtotal", "total", "iva", "tax", "neto", "total a pagar"}
    for i, line in enumerate(lines):
        if _norm(line) not in ("descripcion", "descripción", "detalle", "description"):
            continue
        j = i + 1
        for k in range(i + 1, min(i + 4, len(lines))):
            if _norm(lines[k]).startswith("amount") or _norm(lines[k]) == "monto":
                j = k + 1
                break
        while j + 3 < len(lines):
            desc, qty, price, amount = lines[j], lines[j + 1], lines[j + 2], lines[j + 3]
            if _norm(qty) in stop or _norm(desc) in stop:
                break
            if not qty.isdigit() or len(qty) > 4:
                j += 1
                continue
            pr, am = parse_number(price), parse_number(amount)
            if pr is None or am is None:
                j += 1
                continue
            out.append({"description": desc, "qty": int(qty),
                        "unit_price": float(pr), "amount": float(am)})
            j += 4
        break
    return out


# ------------------------------------------------------------------ validación
def validate(fields: dict, *, vendors: list[dict] | None = None,
             existing: list[dict] | None = None,
             config: dict | None = None, today: date | None = None) -> list[dict]:
    """Reglas de negocio. Devuelve la lista de motivos (vacía = auto-aprobable)."""
    today = today or date.today()
    config = config or {}
    vendors = vendors or []
    existing = existing or []
    tol = TOLERANCE_USD if fields.get("currency") in {"USD", "EUR"} else TOLERANCE_CLP
    reasons: list[dict] = []

    def add(code: str, **kw):
        reasons.append({"code": code, "text": REASON_TEXT[code].format(**kw) if kw else REASON_TEXT[code], **kw})

    for key in ("vendor", "invoice_no", "issue_date", "total"):
        if fields.get(key) in (None, ""):
            add("missing_field", field=key)

    neto, iva, total = fields.get("neto"), fields.get("iva"), fields.get("total")
    if neto is not None and iva is not None and total is not None:
        if abs((neto + iva) - total) > tol:
            add("total_mismatch", neto=float(neto), iva=float(iva), total=float(total))
        elif iva > 0 and neto > 0:
            expected = (neto * IVA_CLP).quantize(Decimal("0.01")) if fields.get("currency") == "CLP" else None
            if expected is not None:
                slack = max(Decimal("2"), (neto * Decimal("0.002")))
                if abs(iva - expected) > slack:
                    add("iva_mismatch", expected=float(expected))

    lines = fields.get("lines") or []
    if lines and neto is not None:
        s = sum(Decimal(str(l["amount"])) for l in lines)
        if abs(s - neto) > tol:
            add("lines_mismatch", sum=float(s), neto=float(neto))

    if fields.get("vendor_rut") and not fields.get("rut_valid"):
        add("invalid_rut", rut=fields["vendor_rut"])

    if vendors and fields.get("vendor_rut") and fields.get("rut_valid"):
        known = {v["rut"] for v in vendors if v.get("active", True)}
        if fields["vendor_rut"] not in known:
            add("unknown_vendor", rut=fields["vendor_rut"])

    if fields.get("invoice_no"):
        dup = next((e for e in existing
                    if e.get("invoice_no") == fields["invoice_no"]
                    and (not fields.get("vendor_rut") or e.get("vendor_rut") == fields["vendor_rut"])), None)
        if dup:
            add("duplicate_folio", existing=dup.get("file_name") or "otra factura")

    if fields.get("issue_date"):
        d = fields["issue_date"]
        if isinstance(d, str):
            d = parse_date(d)
        if d and (d > today or (today - d).days > 365):
            add("date_out_of_range", date=d.isoformat())

    cap = Decimal(str(config.get("max_invoice_total", DEFAULT_MAX_TOTAL)))
    if total is not None and total > cap:
        add("total_over_cap", total=float(total), cap=float(cap))

    if (fields.get("confidence") or 0) < 70:
        add("low_confidence", confidence=fields.get("confidence"))

    return reasons


def evaluate_text(text: str, *, vendors=None, existing=None, config=None, today=None) -> dict:
    """Extrae y valida. `status` = pass (auto) o review (humano)."""
    if not text or not text.strip():
        return {"fields": {}, "reasons": [{"code": "no_text", "text": REASON_TEXT["no_text"]}],
                "status": "review", "confidence": 0.0}
    fields = extract_fields(text)
    reasons = validate(fields, vendors=vendors, existing=existing, config=config, today=today)
    return {"fields": fields, "reasons": reasons,
            "status": "pass" if not reasons else "review",
            "confidence": fields.get("confidence") or 0.0}


def wrong_fields(original: dict, corrected: dict) -> list[dict]:
    """Diff campo a campo entre lo extraído y lo que dejó el humano."""
    keys = ("vendor", "vendor_rut", "invoice_no", "issue_date", "neto", "iva", "total", "currency")
    out = []
    for k in keys:
        a, b = original.get(k), corrected.get(k)
        if b in (None, ""):
            continue
        if isinstance(a, Decimal):
            a = float(a)
        if isinstance(b, Decimal):
            b = float(b)
        same = (str(a) == str(b)) if k != "issue_date" else (
            (a.isoformat() if hasattr(a, "isoformat") else a) == (b.isoformat() if hasattr(b, "isoformat") else b))
        if not same:
            out.append({"field": k, "from": a if not hasattr(a, "isoformat") else a.isoformat(),
                        "to": b if not hasattr(b, "isoformat") else b.isoformat()})
    return out


def to_csv_row(inv: dict) -> list[str]:
    reasons = "; ".join(r.get("text", r.get("code", "")) for r in (inv.get("reasons") or []))
    d = inv.get("issue_date")
    return [
        inv.get("file_name") or "",
        (d.isoformat() if hasattr(d, "isoformat") else (d or "")),
        inv.get("vendor") or "",
        inv.get("vendor_rut") or "",
        inv.get("invoice_no") or "",
        str(inv.get("neto") if inv.get("neto") is not None else ""),
        str(inv.get("iva") if inv.get("iva") is not None else ""),
        str(inv.get("total") if inv.get("total") is not None else ""),
        inv.get("currency") or "",
        inv.get("status") or "",
        (inv.get("reviewed_by") or ""),
        reasons,
    ]
