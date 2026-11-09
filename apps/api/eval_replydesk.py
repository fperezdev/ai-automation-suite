"""Evaluación reproducible de ReplyDesk.

Corre el set de preguntas contra el agente real (con la KB real del tenant),
mide aciertos y escribe el resultado en `eval_runs`. El panel muestra ese número,
así que lo que se publica es una medición, no una promesa.

Uso (dentro del contenedor api):
    docker compose exec -T api python eval_replydesk.py
    docker compose exec -T api python eval_replydesk.py --tenant clinica-sonrisa-nunoa
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import db
import replydesk

HERE = pathlib.Path(__file__).parent
PIECE = "ReplyDesk"
EVAL_WA_ID = "eval-replydesk"


def reset_eval_conversation(tenant_id: str) -> str:
    """Un contacto/conversación de evaluación siempre limpio."""
    contact = db.execute(
        """INSERT INTO contacts (tenant_id, wa_id, name, meta)
           VALUES (%s, %s, 'Evaluación automática', '{}'::jsonb)
           ON CONFLICT (tenant_id, wa_id) DO UPDATE SET name = EXCLUDED.name
           RETURNING id""",
        (tenant_id, EVAL_WA_ID),
    )
    assert contact is not None
    db.execute("DELETE FROM conversations WHERE tenant_id = %s AND contact_id = %s", (tenant_id, contact["id"]))
    conv = db.execute(
        """INSERT INTO conversations (tenant_id, contact_id, channel, status, last_message_at)
           VALUES (%s, %s, 'whatsapp', 'bot', now()) RETURNING *""",
        (tenant_id, contact["id"]),
    )
    assert conv is not None
    return str(conv["id"])


def clean(tenant_id: str, conversation_id: str) -> None:
    db.execute("DELETE FROM messages WHERE conversation_id = %s", (conversation_id,))
    db.execute("DELETE FROM conversations WHERE id = %s", (conversation_id,))
    db.execute("DELETE FROM contacts WHERE tenant_id = %s AND wa_id = %s", (tenant_id, EVAL_WA_ID))


def check(case: dict, trace: dict) -> tuple[bool, str]:
    reply = (trace.get("reply") or "").lower()
    expect = case["expect"]
    if expect == "answer" and trace.get("handoff"):
        return False, "derivó cuando debía responder"
    if expect == "handoff" and not trace.get("handoff"):
        return False, "respondió cuando debía derivar"
    if expect == "handoff" and not reply:
        return False, "derivó sin contestar al cliente"
    if expect == "any" and not reply and not trace.get("handoff"):
        return False, "no respondió ni derivó"
    # "must" = alternativas aceptadas (basta una); "must_all" = todas obligatorias
    alts = case.get("must", [])
    if alts and not any(n.lower() in reply for n in alts):
        return False, f"faltó cualquiera de {alts} en la respuesta"
    for needle in case.get("must_all", []):
        if needle.lower() not in reply:
            return False, f"faltó '{needle}' en la respuesta"
    return True, "ok"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant", default="clinica-sonrisa-nunoa")
    ap.add_argument("--only", help="corre sólo los casos cuyo texto contenga esto")
    args = ap.parse_args()

    tenant = db.one("SELECT * FROM tenants WHERE slug = %s", (args.tenant,))
    if not tenant:
        print(f"tenant '{args.tenant}' no existe")
        return 1
    tid = str(tenant["id"])

    cases = json.loads((HERE / "eval_set_replydesk.json").read_text())
    if args.only:
        cases = [c for c in cases if args.only.lower() in c["text"].lower()]

    conv_id = reset_eval_conversation(tid)
    passed, failures, latencies, costs = 0, [], [], []
    for case in cases:
        trace = replydesk.respond(tenant, conv_id, case["text"])
        ok, why = check(case, trace)
        passed += ok
        latencies.append(trace.get("latency_ms") or 0)
        costs.append(trace.get("cost_usd") or 0)
        mark = "OK  " if ok else "FALLA"
        print(f"{mark} {case['text'][:58]:<58} -> {why}")
        if not ok:
            failures.append({"text": case["text"], "why": why, "reply": trace.get("reply"), "reason": trace.get("reason")})
        # cada caso arranca sin historial: el turno anterior no debe influir
        db.execute("DELETE FROM messages WHERE conversation_id = %s", (conv_id,))

    total = len(cases)
    score = round(100 * passed / total, 1) if total else 0
    with_latency = [x for x in latencies if x]
    summary = {
        "score": score,
        "total": total,
        "passed": passed,
        "latency_p50_ms": sorted(with_latency)[len(with_latency) // 2] if with_latency else 0,
        "cost_usd_per_question": round(sum(costs) / total, 6) if total else 0,
        "failures": failures,
    }
    db.execute(
        """INSERT INTO eval_runs (tenant_id, piece, total, passed, detail)
           VALUES (%s, %s, %s, %s, %s)""",
        (tid, PIECE, total, passed, json.dumps(summary)),
    )
    clean(tid, conv_id)
    print(f"\n{PIECE}: {passed}/{total} ({score}%) · p50 {summary['latency_p50_ms']} ms · "
          f"US$ {summary['cost_usd_per_question']:.5f}/pregunta")
    return 0 if score >= 80 else 2


if __name__ == "__main__":
    sys.exit(main())
