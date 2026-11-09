"""ReplyDesk — agente de WhatsApp para pymes con política de derivación a recepción.

Decisiones que toma el módulo, en este orden:
  1. reglas deterministas (urgencia, reclamo, pide persona, fuera de alcance) -> deriva,
     sin gastar tokens ni depender del modelo;
  2. si la conversación ya está en manos de una persona -> no responde;
  3. LLM con la base de conocimiento del tenant y respuesta en JSON
     {"reply": "...", "handoff": bool, "reason": "..."}.

Todo lo que se mide (latencia, tokens, costo, derivación) se guarda en `messages`
y `conversations`, así el panel muestra números medidos y no estimados.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

import db

LLM_ROUTER_URL = os.getenv("LLM_ROUTER_URL", "http://127.0.0.1:8770/chat")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "25"))
# precio de referencia del modelo (USD por 1M tokens). Sirve para el costo medido.
PRICE_IN = float(os.getenv("LLM_PRICE_IN", "0.10"))
PRICE_OUT = float(os.getenv("LLM_PRICE_OUT", "0.40"))
MAX_BOT_TURNS = int(os.getenv("MAX_BOT_TURNS", "8"))

# (patrón, motivo que ve recepción). Castellano neutro; se evalúan en minúscula.
HANDOFF_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(urgencia|urgente|dolor (fuerte|agudo)|sangra|se me rompi|emergencia|me duele mucho)\b"),
     "Urgencia: dolor o emergencia"),
    (re.compile(r"\b(hablar con (una )?(persona|humano|secretaria|alguien)|que me llame|que me llamen|deriv(a|ar) a)\b"),
     "Pide hablar con una persona"),
    (re.compile(r"\b(reclamo|reclamaci[oó]n|estoy molesto|p[eé]simo|denuncia|devoluci[oó]n del dinero)\b"),
     "Reclamo"),
    # convenios e isapres SÍ están en la base de conocimiento: los responde el LLM.
    (re.compile(r"\b(fonasa|reembolso|boleta|factura|presupuesto por escrito|cheque|pago en cuotas)\b"),
     "Tema administrativo o de convenios"),
    (re.compile(r"\b(implante|ortodoncia|endodoncia|extracci[oó]n|cirug[ií]a|corona)\b"),
     "Tratamiento que requiere evaluación clínica"),
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


# respuesta corta al cliente cuando se deriva (para no dejarlo sin contestación)
HANDOFF_ACK = {
    "Urgencia: dolor o emergencia": "Entiendo, eso necesita atención hoy. Ya aviso a recepción para que te contacte a la brevedad.",
    "Pide hablar con una persona": "Claro, ya aviso a recepción para que te escriba.",
    "Reclamo": "Lamento la molestia. Estoy pasando el caso a recepción para que lo revise y te responda.",
    "Tema administrativo o de convenios": "Eso lo maneja recepción; ya les paso tu mensaje para que te confirmen.",
    "Tratamiento que requiere evaluación clínica": "Para indicarte bien necesitamos una evaluación. Ya aviso a recepción para coordinar una hora.",
}
DEFAULT_ACK = "Ya aviso a recepción para que te responda."


def handoff_reason(text: str) -> str | None:
    """Motivo de derivación si el mensaje cae en una regla, si no None."""
    low = (text or "").lower()
    for pattern, reason in HANDOFF_RULES:
        if pattern.search(low):
            return reason
    return None


def kb_block(tenant_id: str) -> tuple[str, int]:
    rows = db.query(
        "SELECT topic, answer, price FROM kb_entries WHERE tenant_id = %s AND active ORDER BY topic",
        (tenant_id,),
    )
    lines = []
    for r in rows:
        price = f" (precio: {r['price']})" if r["price"] else ""
        lines.append(f"- {r['topic']}: {r['answer']}{price}")
    return "\n".join(lines), len(rows)


def history_block(conversation_id: str, limit: int = 8) -> list[dict]:
    rows = db.query(
        """SELECT direction, body FROM messages WHERE conversation_id = %s
           ORDER BY created_at DESC LIMIT %s""",
        (conversation_id, limit),
    )
    out = []
    for r in reversed(rows):
        out.append({"role": "user" if r["direction"] == "in" else "assistant", "content": r["body"]})
    return out


def system_prompt(tenant: dict, kb: str) -> str:
    name = tenant.get("name") or "el negocio"
    return (
        f"Eres el asistente de atención por WhatsApp de {name}.\n"
        "Reglas obligatorias:\n"
        "1. Responde en español neutro (nada de vosco ni modismos), breve: 1 a 3 frases.\n"
        "2. Usa SOLO la información de la base de conocimiento. Si el dato no está, no lo inventes.\n"
        "3. Si no tienes el dato, si el paciente pide hablar con una persona, o si el caso "
        "necesita evaluación clínica, deriva.\n"
        "4. Nunca des diagnósticos ni recomendaciones médicas.\n"
        "5. No prometas horarios concretos: ofrece coordinar con recepción.\n"
        "Responde SIEMPRE con un JSON de una sola línea, sin markdown:\n"
        '{"reply": "texto para el paciente", "handoff": true|false, "reason": "motivo si derivas"}\n\n'
        "Base de conocimiento:\n" + (kb or "(vacía)")
    )


def call_llm(messages: list[dict]) -> tuple[str, int, int, int]:
    """Devuelve (contenido, tokens_in, tokens_out, latencia_ms)."""
    payload = json.dumps({"messages": messages, "max_tokens": 4000}).encode()
    req = urllib.request.Request(
        LLM_ROUTER_URL, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    started = time.time()
    with urllib.request.urlopen(req, timeout=LLM_TIMEOUT) as resp:
        data = json.loads(resp.read().decode())
    latency = int((time.time() - started) * 1000)
    content = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
    usage = data.get("usage") or {}
    tokens_in = int(usage.get("prompt_tokens") or (len(json.dumps(messages)) // 4))
    tokens_out = int(usage.get("completion_tokens") or (len(content) // 4))
    return content.strip(), tokens_in, tokens_out, latency


def parse_decision(content: str) -> dict:
    """JSON tolerante: acepta bloque ```json, texto alrededor o respuesta plana."""
    raw = content.strip()
    if "```" in raw:
        raw = raw.split("```")[1].removeprefix("json").strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start >= 0 and end > start:
        try:
            obj = json.loads(raw[start : end + 1])
            reply = str(obj.get("reply") or "").strip()
            if reply:
                return {
                    "reply": reply,
                    "handoff": bool(obj.get("handoff")),
                    "reason": (str(obj.get("reason") or "").strip() or None),
                }
        except json.JSONDecodeError:
            pass
    # fallback: el modelo contestó texto plano
    return {"reply": raw[:600], "handoff": False, "reason": None}


def respond(tenant: dict, conversation_id: str, text: str) -> dict:
    """Procesa un mensaje entrante y devuelve la traza completa de la decisión."""
    tid = str(tenant["id"])
    trace = {
        "conversation_id": conversation_id,
        "handoff": False,
        "reason": None,
        "source": "rules",
        "latency_ms": 0,
        "tokens": 0,
        "cost_usd": 0.0,
        "reply": None,
    }

    reason = handoff_reason(text)
    if reason:
        trace.update(handoff=True, reason=reason, source="rules", reply=HANDOFF_ACK.get(reason, DEFAULT_ACK))
        return trace

    turns = db.one(
        "SELECT count(*) AS n FROM messages WHERE conversation_id = %s AND direction = 'out'",
        (conversation_id,),
    )
    if turns and int(turns["n"]) >= MAX_BOT_TURNS:
        trace.update(reply=DEFAULT_ACK, handoff=True, reason=f"Conversación larga ({MAX_BOT_TURNS}+ respuestas del bot)", source="rules")
        return trace

    kb, n_kb = kb_block(tid)
    messages = [{"role": "system", "content": system_prompt(tenant, kb)}]
    messages += history_block(conversation_id)
    messages.append({"role": "user", "content": text})

    try:
        content, t_in, t_out, latency = call_llm(messages)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as err:
        # fallback: si el modelo no responde, deriva en vez de dejar al cliente sin respuesta
        trace.update(
            handoff=True,
            reason="Fallback: el modelo no respondió",
            source="fallback",
            reply="Para no dejarle esperando, ya aviso a recepción para que le responda a la brevedad.",
        )
        trace["error"] = str(err)[:200]
        return trace

    decision = parse_decision(content)
    cost = round(t_in / 1_000_000 * PRICE_IN + t_out / 1_000_000 * PRICE_OUT, 6)
    trace.update(
        reply=decision["reply"],
        handoff=decision["handoff"],
        reason=decision["reason"],
        source="llm",
        latency_ms=latency,
        tokens=t_in + t_out,
        cost_usd=cost,
        kb_entries=n_kb,
    )
    return trace
