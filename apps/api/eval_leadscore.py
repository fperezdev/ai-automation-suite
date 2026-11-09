#!/usr/bin/env python3
"""Eval de LeadScore: corre el scorer sobre el set de prueba y mide aciertos reales.

Mide, por caso: tier correcto, score dentro del rango esperado, códigos de motivo presentes y
ausentes. Agrega precisión/recall de motivos, recall de dedupe (pares que debía detectar) y
latencia. Escribe el resultado en `eval_runs` (si hay base de datos) para que el panel y la
página de caso muestren el número medido, no una promesa.

Uso:
  docker exec suite-api python /app/eval_leadscore.py --samples /samples/leadscore
  local:  python apps/api/eval_leadscore.py --samples samples/leadscore --no-db
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import leadscore as ls  # noqa: E402


def run(samples: str, tenant: str | None, write_db: bool) -> int:
    with open(os.path.join(samples, "leads.json"), encoding="utf-8") as fh:
        leads = {l["id"]: l for l in json.load(fh)}
    with open(os.path.join(samples, "golden.json"), encoding="utf-8") as fh:
        golden = json.load(fh)

    tier_ok = score_ok = 0
    tp = fp = fn = 0
    durations: list[float] = []
    per_case: list[dict] = []

    for case in golden:
        lid, exp = case["id"], case["expect"]
        lead = leads[lid]
        t0 = time.perf_counter()
        verdict = ls.evaluate_lead(lead) if not lead.get("duplicate_of") else ls.score(lead)
        durations.append((time.perf_counter() - t0) * 1000)
        codes = {r["code"] for r in verdict["reasons"]}

        t_ok = verdict["tier"] == exp["tier"]
        s_ok = exp["score_min"] <= verdict["score"] <= exp["score_max"]
        tier_ok += int(t_ok)
        score_ok += int(s_ok)

        must = set(exp.get("codes") or [])
        absent = set(exp.get("absent") or [])
        tp += len(codes & must)
        fn += len(must - codes)
        fp += len(codes - must) if absent else 0  # sólo cuentan como error los prohibidos explícitos
        fp += len(codes & absent)

        per_case.append({
            "id": lid, "score": verdict["score"], "tier": verdict["tier"],
            "expected_tier": exp["tier"], "tier_ok": t_ok, "score_ok": s_ok,
            "codes": sorted(codes), "missing": sorted(must - codes), "forbidden": sorted(codes & absent),
            "next_action": verdict["next_action"]["kind"],
            "duplicate_of": lead.get("duplicate_of"),
        })

    # Dedupe: cada caso con duplicate_of debe compartir dedupe_key con su original.
    keys: dict[str, str] = {}
    for lid, lead in leads.items():
        k = ls.dedupe_key(lead)
        if k:
            keys.setdefault(k, lid)
    dup_total = dup_hit = 0
    for lid, lead in leads.items():
        orig = lead.get("duplicate_of")
        if not orig:
            continue
        dup_total += 1
        k = ls.dedupe_key(lead)
        if k and keys.get(k) == orig:
            dup_hit += 1
        else:
            per_case[[c["id"] for c in per_case].index(lid)]["dedupe_miss"] = True

    n = len(golden)
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    summary = {
        "cases": n,
        "tier_accuracy": round(100 * tier_ok / n, 1),
        "score_in_range": round(100 * score_ok / n, 1),
        "reason_precision": round(100 * precision, 1),
        "reason_recall": round(100 * recall, 1),
        "dedupe_recall": round(100 * dup_hit / dup_total, 1) if dup_total else 100.0,
        "latency_ms_p50": round(statistics.median(durations), 2),
        "latency_ms_max": round(max(durations), 2),
        "score": round(100 * (tier_ok + score_ok) / (2 * n), 1),
    }

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    for c in per_case:
        flag = "ok " if (c["tier_ok"] and c["score_ok"]) else "MAL"
        extra = f" faltan={','.join(c['missing'])}" if c["missing"] else ""
        extra += f" prohibidos={','.join(c['forbidden'])}" if c["forbidden"] else ""
        extra += " DEDUPE" if c.get("dedupe_miss") else ""
        print(f"  {flag} {c['id']} {c['score']:>3} {c['tier']:<4} (esperado {c['expected_tier']:<4}){extra}")

    if write_db and tenant:
        try:
            import db
            tid = db.one("SELECT id FROM tenants WHERE slug=%s", (tenant,))
            if tid:
                db.execute("""INSERT INTO eval_runs (tenant_id, piece, total, passed, detail)
                              VALUES (%s,'leadscore',%s,%s,%s)""",
                           (tid["id"], n, tier_ok,
                            json.dumps({"summary": summary, "cases": per_case}, ensure_ascii=False)))
                print(f"eval_runs: escrito para tenant {tenant}")
        except Exception as exc:  # sin DB el eval sigue sirviendo en CI
            print(f"eval_runs: no se pudo escribir ({type(exc).__name__}: {exc})")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", default=os.path.join(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))), "samples", "leadscore"))
    ap.add_argument("--tenant", default="clinica-sonrisa-nunoa")
    ap.add_argument("--no-db", action="store_true")
    a = ap.parse_args()
    sys.exit(run(a.samples, a.tenant, not a.no_db))
