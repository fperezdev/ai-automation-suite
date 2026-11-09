"""Eval de ReportBot: 30 planillas con resultado conocido -> número, texto y latencia.

Mide, por caso:
  - total, período anterior y variación exactos (tolerancia 0,01 CLP)
  - categoría top correcta
  - códigos de insight que debían estar (`must`) y los que no (`absent`)
  - que el texto generado incluya el total con formato chileno
Y al final: latencia p50/máx por planilla y costo (US$ 0: no hay modelo en el camino).

Uso:
  python eval_reportbot.py --samples /samples/reportbot
  python eval_reportbot.py --samples ./samples/reportbot --no-db
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import reportbot as rb  # noqa: E402


def run(samples: str, tenant: str, write_db: bool) -> int:
    golden = json.load(open(os.path.join(samples, "golden.json"), encoding="utf-8"))
    per_case = []
    lat = []

    for case in golden:
        path = os.path.join(samples, case["file"])
        text = open(path, encoding="utf-8", errors="replace").read()
        t0 = time.perf_counter()
        rows = rb.parse_csv(text)
        m = rb.aggregate(rows)
        out = rb.compose(m)
        lat.append((time.perf_counter() - t0) * 1000)

        num_ok = (abs(m["total"] - case["total"]) <= 0.01
                  and abs(m["prev_total"] - case["prev_total"]) <= 0.01
                  and abs(m["delta_pct"] - case["delta_pct"]) <= 0.15)
        top_ok = (m["top_category"] or None) == case["top_category"]
        codes = {i["code"] for i in m["insights"]}
        missing = [c for c in case["must"] if c not in codes]
        forbidden = [c for c in case["absent"] if c in codes]
        text_ok = rb.money(case["total"]) in out
        per_case.append({
            "file": case["file"], "total": m["total"], "expected": case["total"],
            "prev_total": m["prev_total"], "expected_prev": case["prev_total"],
            "delta_pct": m["delta_pct"], "expected_delta": case["delta_pct"],
            "num_ok": num_ok, "top_ok": top_ok, "text_ok": text_ok,
            "missing": missing, "forbidden": forbidden,
            "insights": sorted(codes),
        })

    n = len(per_case)
    ok = lambda k: sum(1 for c in per_case if c[k])  # noqa: E731
    summary = {
        "cases": n,
        "numbers_accuracy": round(100 * ok("num_ok") / n, 1),
        "top_category_accuracy": round(100 * ok("top_ok") / n, 1),
        "insights_ok": round(100 * sum(1 for c in per_case
                                       if not c["missing"] and not c["forbidden"]) / n, 1),
        "text_mentions_total": round(100 * ok("text_ok") / n, 1),
        "latency_ms_p50": round(statistics.median(lat), 2),
        "latency_ms_max": round(max(lat), 2),
        "score": round(100 * sum(1 for c in per_case
                                 if c["num_ok"] and c["top_ok"] and c["text_ok"]
                                 and not c["missing"] and not c["forbidden"]) / n, 1),
    }

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    for c in per_case:
        good = c["num_ok"] and c["top_ok"] and c["text_ok"] and not c["missing"] and not c["forbidden"]
        extra = f" faltan={','.join(c['missing'])}" if c["missing"] else ""
        extra += f" prohibidos={','.join(c['forbidden'])}" if c["forbidden"] else ""
        if not c["num_ok"]:
            extra += f" numeros({c['total']} vs {c['expected']})"
        if not c["top_ok"]:
            extra += " top"
        print(f"  {'ok ' if good else 'MAL'} {c['file']:<38} {str(c['total']):>12}{extra}")

    if write_db and tenant:
        try:
            import db
            tid = db.one("SELECT id FROM tenants WHERE slug=%s", (tenant,))
            if tid:
                db.execute("""INSERT INTO eval_runs (tenant_id, piece, total, passed, detail)
                              VALUES (%s,'reportbot',%s,%s,%s)""",
                           (tid["id"], n, sum(1 for c in per_case if c["num_ok"]),
                            json.dumps({"summary": summary, "cases": per_case}, ensure_ascii=False)))
                print(f"eval_runs: escrito para tenant {tenant}")
        except Exception as exc:
            print(f"eval_runs: no se pudo escribir ({type(exc).__name__}: {exc})")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "samples", "reportbot"))
    ap.add_argument("--tenant", default="clinica-sonrisa-nunoa")
    ap.add_argument("--no-db", action="store_true")
    a = ap.parse_args()
    sys.exit(run(a.samples, a.tenant, not a.no_db))
