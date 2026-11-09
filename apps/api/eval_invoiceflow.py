#!/usr/bin/env python3
"""Eval de InvoiceFlow: corre el extractor sobre el set dorado y mide aciertos reales.

Mide, por caso: campos correctos, estado (pass/review) y motivos detectados.
Agrega precisión/recall por motivo, latencia media y escribe el resultado en `eval_runs`
(si hay base de datos) para que el panel y el README muestren el número medido.

Uso:
  docker exec suite-api python /app/eval_invoiceflow.py --samples /samples/invoiceflow
  o en local:  python apps/api/eval_invoiceflow.py --samples samples/invoiceflow
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import invoiceflow as iflow  # noqa: E402

FIELDS = ("vendor", "invoice_no", "issue_date", "neto", "iva", "total", "currency")


def same(field: str, got, want) -> bool:
    if want is None:
        return got in (None, "")
    if field in ("neto", "iva", "total"):
        if got is None:
            return False
        return abs(Decimal(str(got)) - Decimal(str(want))) <= Decimal("1")
    if field == "issue_date":
        if hasattr(got, "isoformat"):
            got = got.isoformat()
        return str(got) == str(want)
    return str(got).strip() == str(want).strip()


def run(samples: str, tenant: str | None, write_db: bool) -> int:
    golden_path = os.path.join(samples, "golden.json")
    with open(golden_path, encoding="utf-8") as fh:
        golden = json.load(fh)
    today = date.fromisoformat(golden.get("today") or date.today().isoformat())
    config = {"max_invoice_total": golden.get("max_invoice_total", 8_000_000)}
    vendors = golden.get("vendors") or []

    existing: list[dict] = []
    field_hits = {f: [0, 0] for f in FIELDS}
    status_ok = 0
    reason_tp = reason_fp = reason_fn = 0
    per_case: list[dict] = []
    durations: list[float] = []

    for case in golden["cases"]:
        path = os.path.join(samples, case["file"])
        t0 = time.perf_counter()
        text = iflow.pdf_text(open(path, "rb").read())
        result = iflow.evaluate_text(text, vendors=vendors, existing=existing,
                                     config=config, today=today)
        durations.append((time.perf_counter() - t0) * 1000)
        got, exp = result["fields"], case["expected"]

        hits = {}
        for f in FIELDS:
            if f not in exp:
                continue
            ok = same(f, got.get(f), exp.get(f))
            field_hits[f][0] += int(ok)
            field_hits[f][1] += 1
            hits[f] = ok
        st_ok = result["status"] == exp["status"]
        status_ok += int(st_ok)

        got_codes = {r["code"] for r in result["reasons"]}
        exp_codes = set(exp.get("reasons") or [])
        tp = len(got_codes & exp_codes)
        fp = len(got_codes - exp_codes)
        fn = len(exp_codes - got_codes)
        reason_tp += tp
        reason_fp += fp
        reason_fn += fn
        per_case.append({"file": case["file"], "status": result["status"],
                         "expected_status": exp["status"], "status_ok": st_ok,
                         "codes": sorted(got_codes), "expected_codes": sorted(exp_codes),
                         "fields": hits, "confidence": result["confidence"]})
        if result["status"] in ("pass", "approved"):
            existing.append({"vendor_rut": got.get("vendor_rut"),
                             "invoice_no": got.get("invoice_no"), "file_name": case["file"]})

    n = len(golden["cases"])
    total_fields = sum(v[1] for v in field_hits.values())
    total_hits = sum(v[0] for v in field_hits.values())
    precision = reason_tp / (reason_tp + reason_fp) if reason_tp + reason_fp else 1.0
    recall = reason_tp / (reason_tp + reason_fn) if reason_tp + reason_fn else 1.0
    summary = {
        "cases": n,
        "field_accuracy": round(100 * total_hits / total_fields, 1) if total_fields else 0.0,
        "by_field": {f: round(100 * h / t, 1) for f, (h, t) in field_hits.items() if t},
        "status_accuracy": round(100 * status_ok / n, 1),
        "reason_precision": round(100 * precision, 1),
        "reason_recall": round(100 * recall, 1),
        "latency_ms_p50": round(statistics.median(durations), 1),
        "latency_ms_max": round(max(durations), 1),
        "score": round(100 * (total_hits + status_ok) / (total_fields + n), 1),
    }

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    for c in per_case:
        flag = "ok " if c["status_ok"] else "MAL"
        print(f"  {flag} {c['file']:<28} {c['status']:<7} (esperado {c['expected_status']:<6}) "
              f"motivos={','.join(c['codes']) or '-'} esperados={','.join(c['expected_codes']) or '-'}")

    if write_db and tenant:
        try:
            import db
            tid = db.one("SELECT id FROM tenants WHERE slug=%s", (tenant,))
            if tid:
                db.execute("""INSERT INTO eval_runs (tenant_id, piece, total, passed, detail)
                              VALUES (%s,'invoiceflow',%s,%s,%s)""",
                           (tid["id"], n, round(summary["status_accuracy"] * n / 100),
                            json.dumps({"summary": summary, "cases": per_case}, ensure_ascii=False)))
                print(f"eval_runs: escrito para tenant {tenant}")
        except Exception as exc:  # sin DB el eval sigue sirviendo en CI
            print(f"eval_runs: no se pudo escribir ({type(exc).__name__}: {exc})")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", default=os.path.join(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))), "samples", "invoiceflow"))
    ap.add_argument("--tenant", default="clinica-sonrisa-nunoa")
    ap.add_argument("--no-db", action="store_true")
    a = ap.parse_args()
    sys.exit(run(a.samples, a.tenant, not a.no_db))
