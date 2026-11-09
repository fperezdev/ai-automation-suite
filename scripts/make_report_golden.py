"""Genera 30 planillas de ventas + golden.json para el eval de ReportBot.

Cada caso arma filas con fecha y monto conocidos, escribe el CSV con un formato distinto
(separador, moneda, cabeceras en español o inglés, fechas ISO o dd/mm/yyyy) y calcula el
resultado esperado con aritmética directa, sin usar reportbot: el eval compara contra eso.

Salida: samples/reportbot/rep-001-*.csv ... rep-030-*.csv + golden.json
"""

from __future__ import annotations

import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

OUT = Path("samples/reportbot")

CASES: list[dict] = []


def add(name: str, rows: list[dict], *, headers=("fecha", "monto", "categoria", "detalle"),
        delim=";", date_fmt="%d/%m/%Y", money_fmt="cl", must=(), absent=(), note=""):
    CASES.append({"name": name, "rows": rows, "headers": headers, "delim": delim,
                  "date_fmt": date_fmt, "money_fmt": money_fmt,
                  "must": list(must), "absent": list(absent), "note": note})


def money_cl(v: float) -> str:
    s = f"{abs(v):,.0f}".replace(",", ".")
    return ("-$" if v < 0 else "$") + s


def money_plain(v: float) -> str:
    return f"{v:.2f}".replace(".", ",")


def days(start: str, n: int) -> list[date]:
    d0 = date.fromisoformat(start)
    return [d0 + timedelta(days=i) for i in range(n)]


def spread(dates: list[date], amounts: list, cats: list, labels=None) -> list[dict]:
    from itertools import cycle
    cats = [c for _, c in zip(dates, cycle(cats))] if len(cats) < len(dates) else cats
    labels = [l for _, l in zip(dates, cycle(labels or [""]))] if len(labels or [""]) < len(dates) \
        else (labels or [""] * len(dates))
    return [{"date": d, "amount": a, "category": c, "label": l}
            for d, a, c, l in zip(dates, amounts, cats, labels)]


# ---------------------------------------------------------------- casos

base = days("2026-10-01", 28)

# 01 mes completo, cuatro categorías, crecimiento moderado
add("mes-dental-crecimiento",
    spread(base,
           [180000, 220000, 95000, 0, 310000, 120000, 60000,
            150000, 260000, 110000, 0, 340000, 130000, 70000,
            190000, 280000, 120000, 0, 360000, 150000, 80000,
            210000, 300000, 130000, 0, 400000, 170000, 90000],
           ["Ortodoncia", "Implantes", "Limpieza", "Limpieza",
            "Implantes", "Ortodoncia", "Limpieza"] * 4),
    must=["total_up", "top_category", "best_day"])

# 02 caída fuerte en una categoría
add("caida-implantes",
    spread(base,
           [300000, 0, 400000, 0, 250000, 0, 500000,
            120000, 0, 90000, 0, 80000, 0, 60000,
            90000, 0, 70000, 0, 65000, 0, 50000,
            80000, 0, 60000, 0, 55000, 0, 45000],
           ["Implantes", "Ortodoncia", "Implantes", "Ortodoncia",
            "Implantes", "Ortodoncia", "Implantes"]),
    must=["total_down", "category_drop"])

# 03 plano
add("plano",
    spread(base, [100000] * 28, ["Limpieza"] * 28),
    must=["total_flat", "top_category"])

# 04 un solo día de ventas (sin período anterior)
add("primera-semana",
    spread(days("2026-11-02", 1), [480000], ["Ortodoncia"]),
    must=["no_previous"])

# 05 concentración en una categoría (>60%)
add("concentrado",
    spread(base,
           [50000, 60000, 900000, 0, 40000, 50000, 0,
            55000, 65000, 950000, 0, 45000, 55000, 0,
            60000, 70000, 1000000, 0, 50000, 60000, 0,
            65000, 75000, 1100000, 0, 55000, 65000, 0],
           ["Limpieza", "Ortodoncia", "Implantes", "Limpieza",
            "Limpieza", "Ortodoncia", "Limpieza"]),
    must=["concentration", "top_category"])

# 06 devoluciones (montos negativos)
add("con-devoluciones",
    spread(base,
           [200000, -40000, 180000, 0, 220000, -30000, 90000,
            210000, -45000, 190000, 0, 230000, -25000, 95000,
            200000, -50000, 185000, 0, 225000, -20000, 100000,
            205000, -55000, 195000, 0, 235000, -35000, 105000],
           ["Ortodoncia", "Limpieza", "Ortodoncia", "Limpieza"] * 7),
    must=["refunds"])

# 07 período negativo (segunda mitad en rojo)
add("periodo-negativo",
    spread(base,
           [300000, 280000, 250000, 0, 320000, 290000, 260000,
            120000, 100000, 90000, 0, 80000, 70000, 60000,
            -150000, -120000, -90000, 0, -80000, -70000, -60000,
            -50000, -40000, -30000, 0, -20000, -10000, -5000],
           ["Ortodoncia"] * 28),
    must=["negative_total"])

# 08 pocos movimientos
add("pocos-movimientos",
    spread(days("2026-11-03", 4), [120000, 80000, 95000, 150000], ["Limpieza"] * 4),
    must=["low_volume"])

# 09 fechas ISO y montos con punto de miles
add("iso-miles",
    spread(base, [140000 + i * 5000 for i in range(28)], ["Ortodoncia"] * 28),
    date_fmt="%Y-%m-%d", money_fmt="cl", must=["total_up"])

# 10 coma como separador decimal, CSV con comas
add("decimales-coma",
    spread(days("2026-10-05", 14), [99990.5, 0, 120000.75, 0, 0, 45000.25, 0,
                                    100000.5, 0, 130000.25, 0, 0, 47000.75, 0],
           ["Limpieza"] * 14),
    delim=",", money_fmt="plain", must=["total_up"])

# 11 cabeceras en inglés
add("headers-ingles",
    spread(base, [90000 + (i % 7) * 15000 for i in range(28)],
           ["Cleaning", "Implants", "Ortho", "Cleaning"] * 7),
    headers=("date", "amount", "category", "description"), must=["top_category"])

# 12 tab como separador
add("tab",
    spread(base, [60000 + (i % 5) * 20000 for i in range(28)], ["Limpieza"] * 28),
    delim="\t", must=["top_category"])

# 13 sin columna de categoría
add("sin-categoria",
    spread(base, [70000 + (i % 4) * 25000 for i in range(28)], [None] * 28),
    headers=("fecha", "monto"), must=["top_category"])

# 14 ticket alto, pocas ventas grandes
add("ticket-alto",
    spread(days("2026-10-10", 12), [1200000, 0, 0, 2400000, 0, 0,
                                    1500000, 0, 0, 2600000, 0, 0],
           ["Implantes"] * 12),
    must=["top_category"])

# 15 muchos días en cero (sparkline con huecos)
add("dias-vacios",
    spread(days("2026-10-01", 21), [0, 0, 0, 0, 0, 250000, 0,
                                    0, 0, 0, 0, 0, 300000, 0,
                                    0, 0, 0, 0, 0, 350000, 0],
           ["Ortodoncia"] * 21),
    must=["total_up"])

# 16 fin de semana concentrado
add("fin-de-semana",
    spread(base, [0, 0, 0, 0, 0, 380000, 420000] * 4, ["Ortodoncia"] * 28),
    must=["best_day"])

# 17 filas inválidas mezcladas
add("filas-invalidas",
    spread(days("2026-10-01", 14), [150000, 0, "texto", 180000, 0, 0, 200000,
                                    160000, 0, 190000, 0, 0, 210000, 0],
           ["Limpieza"] * 14),
    must=["total_up"])

# 18 dos categorías que se cruzan
add("cruce-categorias",
    spread(base,
           [200000, 50000, 210000, 55000, 220000, 60000, 230000,
            240000, 65000, 250000, 70000, 260000, 75000, 270000,
            100000, 400000, 90000, 420000, 80000, 440000, 70000,
            460000, 60000, 480000, 50000, 500000, 40000, 520000],
           ["Ortodoncia", "Implantes"] * 14),
    must=["category_jump", "category_drop"])

# 19 montos sin símbolo ni separador
add("montos-planos",
    spread(base, [85000 + (i % 6) * 10000 for i in range(28)], ["Limpieza"] * 28),
    money_fmt="raw", must=["top_category"])

# 20 dos semanas exactas
add("dos-semanas",
    spread(days("2026-11-02", 14), [120000, 0, 90000, 130000, 0, 110000, 0,
                                    150000, 0, 140000, 160000, 0, 155000, 0],
           ["Ortodoncia"] * 14),
    must=["total_up"])

# 21 mismo monto todos los días, dos categorías iguales
add("empate-categorias",
    spread(base, [100000] * 28, ["Ortodoncia", "Limpieza"] * 14),
    must=["top_category"])

# 22 caída chica (no dispara category_drop)
add("caida-chica",
    spread(base,
           [200000, 0, 210000, 0, 205000, 0, 208000,
            198000, 0, 207000, 0, 202000, 0, 206000,
            197000, 0, 205000, 0, 200000, 0, 204000,
            196000, 0, 203000, 0, 199000, 0, 202000],
           ["Ortodoncia"] * 28),
    absent=["category_drop"], must=["total_flat"])

# 23 tres categorías, una desaparece
add("categoria-desaparece",
    spread(base,
           [150000, 90000, 60000, 0, 160000, 95000, 65000,
            155000, 92000, 62000, 0, 165000, 98000, 66000,
            158000, 0, 64000, 0, 168000, 0, 67000,
            152000, 0, 63000, 0, 162000, 0, 68000],
           ["Ortodoncia", "Implantes", "Limpieza"] * 9 + ["Ortodoncia"]),
    must=["category_drop"])

# 24 una fila por día, montos crecientes
add("crecimiento-lineal",
    spread(days("2026-10-05", 20), [50000 + i * 5000 for i in range(20)], ["Limpieza"] * 20),
    must=["total_up", "best_day"])

# 25 montos con decimales y miles a la vez
add("miles-y-decimales",
    spread(days("2026-10-01", 12), [1234.56, 0, 2345.67, 0, 3456.78, 0,
                                    1345.67, 0, 2456.78, 0, 3567.89, 0],
           ["Insumos"] * 12),
    delim=",", money_fmt="mix", must=["top_category"])

# 26 planilla de servicios con muchas filas por día
rows = []
for d in days("2026-10-01", 14):
    for k in range(3):
        rows.append({"date": d, "amount": 30000 + k * 15000 + (d.day % 5) * 2000,
                     "category": ["Limpieza", "Ortodoncia", "Implantes"][k], "label": "servicio"})
add("muchas-filas", rows, must=["top_category"])

# 27 mes con un pico único
add("pico-unico",
    spread(base,
           [80000] * 10 + [900000] + [80000] * 6 + [85000] * 11,
           ["Ortodoncia"] * 28),
    must=["best_day"])

# 28 todo en un mismo día de la segunda mitad con categorías
add("una-jornada",
    spread(days("2026-11-07", 1), [150000, 95000, 220000],
           ["Ortodoncia", "Limpieza", "Implantes"]),
    must=["no_previous", "top_category"])

# 29 valores en cero salvo dos días
add("casi-vacio",
    spread(days("2026-10-01", 10), [0, 0, 0, 0, 0, 0, 0, 0, 120000, 130000],
           ["Limpieza"] * 10),
    must=["no_previous"])

# 30 planilla grande: 60 filas, cuatro categorías, caída suave
random.seed(7)
big = []
for d in days("2026-10-01", 30):
    for k, cat in enumerate(["Ortodoncia", "Implantes", "Limpieza", "Insumos"]):
        if (d.day + k) % 3:
            big.append({"date": d, "amount": round(random.uniform(20000, 180000), 0),
                        "category": cat, "label": ""})
add("planilla-grande", big, must=["top_category"])


# ---------------------------------------------------------------- escritura

def to_cell(v):
    if v is None:
        return ""
    if isinstance(v, (int, float)):
        return v
    return v


def fmt_amount(v, mode):
    if isinstance(v, str):
        return v
    if mode == "cl":
        return money_cl(v)
    if mode == "plain":
        return money_plain(v)
    if mode == "mix":
        return f"{v:,.2f}"
    return f"{v:.0f}"


def write_csv(path: Path, case: dict):
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=case["delim"])
        w.writerow(case["headers"])
        for r in case["rows"]:
            d = r["date"].strftime(case["date_fmt"])
            amt = fmt_amount(r["amount"], case["money_fmt"])
            if len(case["headers"]) == 2:
                w.writerow([d, amt])
            else:
                w.writerow([d, amt, r.get("category") or "", r.get("label") or ""])


def expected(case: dict) -> dict:
    """Aritmética directa sobre las filas válidas: la misma partición en dos mitades."""
    rows = [r for r in case["rows"] if isinstance(r["amount"], (int, float))]
    start = min(r["date"] for r in rows)
    end = max(r["date"] for r in rows)
    span = (end - start).days + 1
    mid = start + timedelta(days=span // 2)
    cur = [r for r in rows if r["date"] >= mid]
    prev = [r for r in rows if r["date"] < mid]
    total = round(sum(r["amount"] for r in cur), 2)
    prev_total = round(sum(r["amount"] for r in prev), 2)
    delta = round(((total - prev_total) / abs(prev_total) * 100) if prev_total else 0.0, 1)
    cats: dict = {}
    for r in cur:
        k = r.get("category") or "sin categoría"
        cats[k] = round(cats.get(k, 0.0) + r["amount"], 2)
    ranked = sorted(cats.items(), key=lambda kv: (-kv[1], kv[0]))
    top = ranked[0][0] if ranked and ranked[0][1] > 0 else None
    return {"total": total, "prev_total": prev_total, "delta_pct": delta,
            "top_category": top, "rows": len(cur), "period_start": mid.isoformat(),
            "period_end": end.isoformat()}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("rep-*.csv"):
        old.unlink()
    golden = []
    for i, case in enumerate(CASES, 1):
        slug = f"rep-{i:03d}-{case['name']}"
        path = OUT / f"{slug}.csv"
        write_csv(path, case)
        golden.append({"file": path.name, **expected(case),
                       "must": case["must"], "absent": case["absent"], "note": case["note"]})
    (OUT / "golden.json").write_text(json.dumps(golden, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    print(f"{len(CASES)} planillas en {OUT} · golden.json con {len(golden)} casos")


if __name__ == "__main__":
    main()
