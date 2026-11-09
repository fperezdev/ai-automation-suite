"""ReportBot — planilla de ventas -> números -> resumen escrito.

Todo lo que se afirma en el resumen sale de una cuenta hecha acá: los totales, la variación
contra el período anterior, el día y la categoría que explican el movimiento. El texto se arma
con plantillas deterministas; un LLM puede reescribirlo después, pero nunca inventa cifras.

Funciones puras: texto CSV -> dicts; dicts -> métricas; métricas -> texto. Sin red y sin base.

Códigos de insight (estables):
  total_up, total_down, total_flat      variación del período contra el anterior
  no_previous                            período anterior en cero: no hay con qué comparar
  top_category                           categoría que más aporta
  category_drop                          categoría que más cae (>= 20%)
  category_jump                          categoría que más sube (>= 20%)
  best_day, worst_day                    día que explica el total
  concentration                          una categoría pasa el 60% del total
  low_volume                             menos de 7 movimientos en el período
  refunds                                hay montos negativos (devoluciones)
  negative_total                         el período cierra en negativo

Métricas (dict):
  period_start, period_end, days, rows, total, prev_total, delta_pct, currency,
  avg_ticket, best_day {date, total}, worst_day {date, total},
  by_category [{category, total, prev_total, delta_pct, share}],
  daily [{date, total}], top_category, insights [{code, text, severity}]
"""

from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime, timedelta

CURRENCY = "CLP"
SPARK = "▁▂▃▄▅▆▇█"

DATE_KEYS = ("fecha", "date", "dia", "día", "fecha_venta", "fecha venta")
AMOUNT_KEYS = ("monto", "total", "amount", "venta", "ventas", "importe", "valor", "neto", "bruto")
CATEGORY_KEYS = ("categoria", "categoría", "category", "tipo", "servicio", "producto", "rubro")
LABEL_KEYS = ("detalle", "descripcion", "descripción", "description", "glosa", "cliente", "item")


# ---------------------------------------------------------------- números y fechas

def parse_amount(raw) -> float | None:
    """'$1.234.567' / '1234,50' / '1,234.50' / '-45.000' -> float. None si no hay número."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip()
    if not s:
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = re.sub(r"[^\d,.\-]", "", s)
    if not s or s in {"-", ".", ","}:
        return None
    if "," in s and "." in s:
        # el último separador manda: 1.234,56 -> coma decimal | 1,234.56 -> punto decimal
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        head, _, tail = s.rpartition(",")
        s = f"{head.replace(',', '')}.{tail}" if len(tail) in (1, 2) else s.replace(",", "")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    elif "." in s:
        head, _, tail = s.rpartition(".")
        if len(tail) == 3:  # 1.234 es mil doscientos treinta y cuatro
            s = s.replace(".", "")
    try:
        v = float(s)
    except ValueError:
        return None
    return -abs(v) if neg else v


def parse_date(raw):
    """dd/mm/yyyy, dd-mm-yyyy, yyyy-mm-dd, yyyy/mm/dd -> date. None si no se entiende."""
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    s = str(raw).strip()[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%Y/%m/%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def money(v: float) -> str:
    """1234567.5 -> '1.234.568' (CLP, sin decimales si son cero)."""
    txt = f"{abs(float(v)):,.2f}"
    txt = txt.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    if txt.endswith(",00"):
        txt = txt[:-3]
    return ("-" if v < 0 else "") + txt


def pct(v: float) -> str:
    return f"{v:+.1f}%".replace(".", ",")


def pct_abs(v: float) -> str:
    return f"{abs(v):.1f}%".replace(".", ",")


# ---------------------------------------------------------------- planilla

def _pick(header: list[str], keys) -> str | None:
    low = {h.strip().lower(): h for h in header}
    for k in keys:
        if k in low:
            return low[k]
    for h in low:
        if any(h.startswith(k) for k in keys):
            return low[h]
    return None


def parse_csv(text: str) -> list[dict]:
    """CSV con cabecera -> [{date, amount, category, label}]. Tolera ; o , y precios con $."""
    text = text.lstrip("\ufeff")
    sample = text[:4096]
    delim = ";" if sample.count(";") > sample.count(",") else ","
    if sample.count("\t") > max(sample.count(";"), sample.count(",")):
        delim = "\t"
    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    if not reader.fieldnames:
        return []
    header = [h for h in reader.fieldnames if h]
    dk, ak = _pick(header, DATE_KEYS), _pick(header, AMOUNT_KEYS)
    ck, lk = _pick(header, CATEGORY_KEYS), _pick(header, LABEL_KEYS)
    if not dk or not ak:
        return []
    out = []
    for row in reader:
        d = parse_date(row.get(dk))
        a = parse_amount(row.get(ak))
        if d is None or a is None:
            continue
        out.append({
            "date": d,
            "amount": a,
            "category": (row.get(ck) or "").strip() or None if ck else None,
            "label": (row.get(lk) or "").strip() or None if lk else None,
        })
    out.sort(key=lambda r: r["date"])
    return out


def normalize_rows(raw_rows: list[dict]) -> list[dict]:
    out = []
    for r in raw_rows or []:
        d = parse_date(r.get("date") or r.get("fecha"))
        a = parse_amount(r.get("amount", r.get("monto")))
        if d is None or a is None:
            continue
        out.append({"date": d, "amount": a,
                    "category": (r.get("category") or r.get("categoria") or None),
                    "label": (r.get("label") or r.get("detalle") or None)})
    out.sort(key=lambda r: r["date"])
    return out


# ---------------------------------------------------------------- métricas

def _sum(rows) -> float:
    return round(sum(r["amount"] for r in rows), 2)


def _by_day(rows) -> dict:
    acc: dict = {}
    for r in rows:
        acc[r["date"]] = round(acc.get(r["date"], 0.0) + r["amount"], 2)
    return acc


def _by_cat(rows) -> dict:
    acc: dict = {}
    for r in rows:
        key = r["category"] or "sin categoría"
        acc[key] = round(acc.get(key, 0.0) + r["amount"], 2)
    return acc


def aggregate(rows: list[dict], label_window: str = "período") -> dict:
    """Divide el rango cubierto en dos mitades iguales y compara la segunda contra la primera."""
    rows = [r for r in rows if r["date"] and r["amount"] is not None]
    if not rows:
        return {"rows": 0, "total": 0.0, "prev_total": 0.0, "delta_pct": 0.0,
                "period_start": None, "period_end": None, "days": 0, "currency": CURRENCY,
                "avg_ticket": 0.0, "best_day": None, "worst_day": None, "by_category": [],
                "daily": [], "top_category": None,
                "insights": [{"code": "low_volume", "severity": "warn",
                              "text": "La planilla no trae filas con fecha y monto reconocibles."}]}

    rows.sort(key=lambda r: r["date"])
    start, end = rows[0]["date"], rows[-1]["date"]
    days = (end - start).days + 1
    mid = start + timedelta(days=days // 2)
    prev_rows = [r for r in rows if r["date"] < mid]
    cur_rows = [r for r in rows if r["date"] >= mid]

    total, prev_total = _sum(cur_rows), _sum(prev_rows)
    delta_pct = ((total - prev_total) / abs(prev_total) * 100) if prev_total else 0.0

    daily_acc = _by_day(cur_rows)
    daily = []
    for i in range((end - mid).days + 1):
        d = mid + timedelta(days=i)
        daily.append({"date": d.isoformat(), "total": round(daily_acc.get(d, 0.0), 2)})

    cats_cur, cats_prev = _by_cat(cur_rows), _by_cat(prev_rows)
    by_category = []
    for name in set(cats_cur) | set(cats_prev):
        c, p = cats_cur.get(name, 0.0), cats_prev.get(name, 0.0)
        by_category.append({
            "category": name, "total": round(c, 2), "prev_total": round(p, 2),
            "delta_pct": round(((c - p) / abs(p) * 100) if p else 0.0, 1),
            "share": round((c / total * 100) if total else 0.0, 1),
        })
    by_category.sort(key=lambda x: (-x["total"], x["category"]))

    best = max(daily, key=lambda d: d["total"]) if daily else None
    worst = min(daily, key=lambda d: d["total"]) if daily else None
    top = by_category[0]["category"] if by_category and by_category[0]["total"] > 0 else None

    metrics = {
        "period_start": mid.isoformat(), "period_end": end.isoformat(),
        "prev_start": start.isoformat(), "prev_end": (mid - timedelta(days=1)).isoformat(),
        "days": (end - mid).days + 1, "rows": len(cur_rows), "rows_prev": len(prev_rows),
        "total": total, "prev_total": prev_total, "delta_pct": round(delta_pct, 1),
        "currency": CURRENCY,
        "avg_ticket": round(total / len(cur_rows), 2) if cur_rows else 0.0,
        "negatives": sum(1 for r in cur_rows if r["amount"] < 0),
        "best_day": best, "worst_day": worst, "by_category": by_category,
        "daily": daily, "top_category": top, "insights": [],
        "window": label_window,
    }
    metrics["insights"] = summarize(metrics)
    return metrics


def summarize(m: dict) -> list[dict]:
    """Códigos con el texto que ve la persona. Cada uno se apoya en un número ya calculado."""
    out: list[dict] = []
    total, prev = m["total"], m["prev_total"]

    if prev == 0 and total != 0:
        out.append({"code": "no_previous", "severity": "info",
                    "text": f"Sin período anterior con ventas para comparar: el total es {money(total)}."})
    elif prev != 0:
        d = m["delta_pct"]
        if abs(d) < 2:
            out.append({"code": "total_flat", "severity": "info",
                        "text": f"Total estable: {money(total)} contra {money(prev)} ({pct(d)})."})
        elif d > 0:
            out.append({"code": "total_up", "severity": "good",
                        "text": f"Sube {pct_abs(d)}: {money(total)} contra {money(prev)} del período anterior."})
        else:
            out.append({"code": "total_down", "severity": "warn",
                        "text": f"Baja {pct_abs(d)}: {money(total)} contra {money(prev)} del período anterior."})

    if m["top_category"]:
        top = next(c for c in m["by_category"] if c["category"] == m["top_category"])
        out.append({"code": "top_category", "severity": "info",
                    "text": f"«{top['category']}» explica {money(top['total'])} "
                            f"({str(top['share']).replace('.', ',')}% del total, {pct(top['delta_pct'])})."})
        if top["share"] >= 60:
            out.append({"code": "concentration", "severity": "warn",
                        "text": f"Dependencia de una sola categoría: {top['share']:.0f}% del período. "
                                f"Una caída ahí mueve todo el resultado."})

    moves = [c for c in m["by_category"] if c["prev_total"] > 0 and abs(c["delta_pct"]) >= 20]
    if moves:
        down = min(moves, key=lambda c: c["delta_pct"])
        if down["delta_pct"] < 0:
            out.append({"code": "category_drop", "severity": "warn",
                        "text": f"«{down['category']}» cae {pct_abs(down['delta_pct'])}: "
                                f"{money(down['total'])} contra {money(down['prev_total'])}."})
        up = max(moves, key=lambda c: c["delta_pct"])
        if up["delta_pct"] > 0 and up["category"] != down["category"]:
            out.append({"code": "category_jump", "severity": "good",
                        "text": f"«{up['category']}» sube {pct(up['delta_pct'])}: "
                                f"{money(up['total'])} contra {money(up['prev_total'])}."})

    if m["best_day"] and m["best_day"]["total"] > 0:
        out.append({"code": "best_day", "severity": "info",
                    "text": f"Mejor día: {day_label(m['best_day']['date'])}, con {money(m['best_day']['total'])}."})
    if m["worst_day"] is not None and m["days"] > 2:
        out.append({"code": "worst_day", "severity": "info",
                    "text": f"Día más bajo: {day_label(m['worst_day']['date'])}, con {money(m['worst_day']['total'])}."})

    if m["rows"] < 7:
        out.append({"code": "low_volume", "severity": "warn",
                    "text": f"Pocos movimientos en el período ({m['rows']}): la variación puede ser ruido."})
    if m.get("negatives"):
        out.append({"code": "refunds", "severity": "info",
                    "text": "Hay montos negativos: el total ya está neto de devoluciones o ajustes."})
    if total < 0:
        out.append({"code": "negative_total", "severity": "warn",
                    "text": f"El período cierra en negativo ({money(total)}): revisar devoluciones antes de sacar conclusiones."})
    return out


def day_label(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{['lunes','martes','miércoles','jueves','viernes','sábado','domingo'][d.weekday()]} {d.day}"


def sparkline(values: list[float]) -> str:
    if not values:
        return ""
    lo, hi = min(values), max(values)
    if hi == lo:
        return SPARK[3] * len(values)
    return "".join(SPARK[min(len(SPARK) - 1, int((v - lo) / (hi - lo) * (len(SPARK) - 1)))] for v in values)


# ---------------------------------------------------------------- texto

def compose(metrics: dict, business: str = "el negocio") -> str:
    """Resumen listo para mandar por mail o Telegram. Sin LLM: mismas cifras, mismas palabras."""
    if not metrics.get("rows") and not metrics.get("total"):
        return ("No pude leer la planilla: necesito una columna de fecha y una de monto "
                "(por ejemplo `fecha,monto,categoria`).")

    lines = [f"**Resumen de {business}** — {span_label(metrics)}", ""]
    lines.append(f"Total: **{money(metrics['total'])}** "
                 f"(período anterior {money(metrics['prev_total'])}, {pct(metrics['delta_pct'])})")
    if metrics.get("rows"):
        lines.append(f"Movimientos: {metrics['rows']} · ticket promedio {money(metrics['avg_ticket'])}")
    daily = metrics.get("daily") or []
    if daily:
        lines.append(f"Por día: {sparkline([d['total'] for d in daily])}")
    lines.append("")
    if metrics.get("by_category"):
        lines.append("Por categoría:")
        for c in metrics["by_category"][:5]:
            share = str(c["share"]).replace(".", ",")
            lines.append(f"· {c['category']}: {money(c['total'])} ({share}%, {pct(c['delta_pct'])})")
        lines.append("")
    if metrics.get("insights"):
        lines.append("Qué dicen los números:")
        for i in metrics["insights"]:
            lines.append(f"· {i['text']}")
    return "\n".join(lines).strip()


def span_label(m: dict) -> str:
    if not m.get("period_start"):
        return "sin período"
    a = date.fromisoformat(m["period_start"])
    b = date.fromisoformat(m["period_end"])
    if a == b:
        return day_label(m["period_start"])
    return f"{a.day}/{a.month:02d} a {b.day}/{b.month:02d}"


def build_prompt(metrics: dict, business: str = "el negocio") -> str:
    """Para el LLM opcional: le pasa sólo cifras ya calculadas y le prohíbe inventar."""
    bullets = "\n".join(f"- {i['text']}" for i in metrics.get("insights") or [])
    cats = "\n".join(f"- {c['category']}: {money(c['total'])} ({pct(c['delta_pct'])})"
                     for c in (metrics.get("by_category") or [])[:6])
    return (
        f"Eres analista de {business}. Escribe un resumen de 5 a 7 líneas en español neutro, "
        f"tono directo, para el dueño del negocio. Usa SOLO estas cifras; no estimes ni inventes datos "
        f"que no aparezcan. No uses tablas.\n\n"
        f"Período: {span_label(metrics)}\n"
        f"Total: {money(metrics['total'])} vs {money(metrics['prev_total'])} ({pct(metrics['delta_pct'])})\n"
        f"Movimientos: {metrics['rows']} · ticket promedio {money(metrics['avg_ticket'])}\n\n"
        f"Categorías:\n{cats}\n\nHallazgos:\n{bullets}\n"
    )


def report(m: dict, business: str = "el negocio") -> dict:
    return {"metrics": m, "text": compose(m, business), "prompt": build_prompt(m, business)}
