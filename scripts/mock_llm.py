#!/usr/bin/env python3
"""Deterministic, OpenAI-compatible stand-in for the LLM used by these demos.

Why this exists
---------------
The three workflows are built to talk to *any* OpenAI-compatible chat endpoint:
a local model, OpenAI, Groq, Ollama, together with an in-house router... To let
anyone run the demos end to end with **zero API keys and zero cost**, this script
answers the exact same `POST /chat` contract the workflows expect, with rule-based
logic instead of a model:

| Workflow            | What the mock does                                                    |
|---------------------|-----------------------------------------------------------------------|
| doc-automation      | regex parser over the text the PDF extractor produced (real values!)   |
| lead-gen            | deterministic scoring on keywords found in the lead payload            |
| ai-support-agent    | canned policy answers + handoff detection                              |

It is deliberately simple and deterministic (same input -> same output), so the
demo doubles as a smoke test: no randomness, no network, no cost, no keys.

Swap it for a real model by pointing the `LLM` node (or `LLM_URL` in
docker-compose.yml) at any OpenAI-compatible endpoint.

Endpoints
---------
POST /chat  (also /v1/chat/completions) -> {"choices":[{"message":{"content": ...}}]}
GET  /health                           -> {"status":"ok"}

Usage: python scripts/mock_llm.py [--port 8770] [--host 0.0.0.0]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CLINIC_SERVICES = "consulta $15.000, limpieza $35.000, blanqueamiento $120.000, resina $45.000"
HOURS = "lunes a viernes de 9:00 a 19:00 y sábados de 10:00 a 14:00"
LOCATION = "Av. Irarrázaval 3421, a 3 minutos del Metro Chile España (Línea 3)"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _num(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = value.replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _last_user_message(messages: list[dict]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return str(msg.get("content") or "")
    return ""


def _system_prompt(messages: list[dict]) -> str:
    return "\n".join(str(m.get("content") or "") for m in messages if m.get("role") == "system")


# --------------------------------------------------------------------------- #
# 01 - invoice extraction
# --------------------------------------------------------------------------- #
def extract_invoice(text: str) -> dict:
    """Parse the text layer of an invoice PDF the same way a model would.

    Works on `samples/*.pdf` and on any invoice that keeps a similar layout.
    """
    # The workflow prefixes the prompt with "Invoice text:"; drop it so the
    # first line of the document is the vendor line.
    body = re.sub(r"^\s*Invoice text:\s*", "", text.replace("\r", ""), flags=re.IGNORECASE)
    lines = [ln.strip() for ln in body.split("\n")]

    def find(pattern: str) -> str | None:
        match = re.search(pattern, body, re.IGNORECASE)
        return match.group(1).strip() if match else None

    invoice_number = find(r"Invoice number:\s*([^\s]+)")
    date = find(r"Date:\s*(\d{4}-\d{2}-\d{2})")
    currency = find(r"Currency:\s*([A-Z]{3})")

    vendor = None
    for line in lines:
        if re.search(r"invoice number:", line, re.IGNORECASE):
            break
        candidate = re.sub(r"^\s*INVOICE\b", "", line, flags=re.IGNORECASE).strip()
        if candidate and candidate.upper() != "INVOICE":
            vendor = candidate
            break

    items: list[dict] = []
    in_items = False
    for line in lines:
        if re.search(r"Description", line, re.IGNORECASE) and re.search(r"Qty", line, re.IGNORECASE):
            in_items = True
            continue
        if re.match(r"^Subtotal", line, re.IGNORECASE):
            break
        if not in_items:
            continue
        row = re.match(
            r"^(?P<desc>.+?)\s+(?P<qty>\d+)\s+(?P<unit>[\d.,]+)\s+(?P<amount>[\d.,]+)$",
            line,
        )
        if row:
            qty = _num(row.group("qty"))
            unit = _num(row.group("unit"))
            amount = _num(row.group("amount"))
            if amount is None and qty is not None and unit is not None:
                amount = round(qty * unit, 2)
            items.append(
                {
                    "description": row.group("desc").strip(),
                    "quantity": qty,
                    "unit_price": unit,
                    "amount": amount,
                }
            )

    subtotal = _num(find(r"(?m)^\s*Subtotal[:\s]+([\d.,]+)"))
    tax = _num(find(r"(?m)^\s*Tax\s*\([^)]*\)[:\s]+([\d.,]+)")) or _num(find(r"(?m)^\s*Tax[:\s]+([\d.,]+)"))
    # anchored: plain `TOTAL` also matches inside the word "Subtotal"
    total = _num(find(r"(?m)^\s*TOTAL[:\s]+([\d.,]+)"))

    return {
        "invoice_number": invoice_number,
        "date": date,
        "vendor": vendor,
        "currency": currency,
        "line_items": items,
        "subtotal": subtotal,
        "tax": tax,
        "total": total,
    }


# --------------------------------------------------------------------------- #
# 02 - B2B lead scoring
# --------------------------------------------------------------------------- #
URGENCY_WORDS = ("asap", "urgent", "urgently", "immediately", "this week", "right away", "deadline",
                 "dolor", "duele", "urgencia", "urgente", "cuanto antes", "esta semana", "hoy mismo")
BUDGET_WORDS = ("budget", "usd", "$", "price", "pricing", "quote", "per month", "retainer", "pay",
                "precio", "cuánto", "cuanto", "presupuesto", "cotizar", "cotización", "pago", "cuotas")
SCOPE_WORDS = ("automate", "automation", "integrate", "integration", "workflow", "api", "agent", "chatbot", "invoice",
               "limpieza", "ortodoncia", "blanqueamiento", "implante", "endodoncia", "resina",
               "evaluación", "evaluacion", "tratamiento", "consulta", "dental")


def score_lead(payload: dict) -> dict:
    message = str(payload.get("message") or payload.get("notes") or "")
    lower = message.lower()
    score = 40
    reasons: list[str] = []

    if any(word in lower for word in URGENCY_WORDS):
        score += 20
        reasons.append("menciona urgencia o dolor: paciente con necesidad inmediata")
    if any(word in lower for word in BUDGET_WORDS):
        score += 15
        reasons.append("menciona precios o presupuesto: intención clara de cotizar")
    if any(word in lower for word in SCOPE_WORDS):
        score += 15
        reasons.append("nombra un tratamiento o servicio concreto de la clínica")
    if payload.get("website"):
        score += 5
        reasons.append("dejó datos de contacto completos, fácil de verificar")
    if len(message) > 160:
        score += 5
        reasons.append("consulta detallada en vez de una sola línea")
    if not reasons:
        reasons.append("consulta genérica: sin señales de urgencia, presupuesto ni tratamiento")

    score = max(0, min(100, score))
    tier = "HOT" if score >= 75 else "WARM" if score >= 45 else "COLD"
    name = str(payload.get("name") or "hola").split()[0]

    return {
        "score": score,
        "tier": tier,
        "reasons": reasons,
        "suggested_angle": (
            "Responder ofreciendo una evaluación y proponer 2 horarios concretos; "
            "pedir nombre completo, RUT y previsión (Fonasa/Isapre)."
        ),
        "followup_email": (
            f"Hola {name}, gracias por escribir a la Clínica Sonrisa Ñuñoa.\n"
            "Podemos ayudarte: para ese tratamiento coordinamos una evaluación, donde el odontólogo "
            "entrega el presupuesto definitivo.\n"
            "¿Te queda cómodo algún horario? Cuéntame tu nombre completo, RUT y la hora que prefieres, "
            "y confirmamos la cita por este medio.\n"
            "Saludos,\nRecepción — Clínica Sonrisa Ñuñoa"
        ),
    }


# --------------------------------------------------------------------------- #
# 03 - support agent
# --------------------------------------------------------------------------- #
def support_reply(messages: list[dict]) -> dict:
    question = _last_user_message(messages).lower()

    def reply(text: str, intent: str, handoff: bool = False, reason: str = "", sentiment: str = "neutral") -> dict:
        return {
            "reply": text,
            "intent": intent,
            "sentiment": sentiment,
            "handoff": handoff,
            "handoff_reason": reason,
        }

    if any(word in question for word in ("refund", "money back", "charge", "wrong charge", "complaint", "complain",
                                          "reembolso", "devolu", "cobro", "cobrar", "reclamo", "queja", "mal cobr")):
        return reply(
            "Lamento el problema — le avisé al equipo y una persona te va a contactar directamente "
            "para resolver el reembolso.",
            "reembolso_o_reclamo",
            handoff=True,
            reason="Reembolsos y reclamos los maneja una persona",
            sentiment="negative",
        )
    if any(word in question for word in ("human", "person", "agent", "manager", "call me", "phone", "call back",
                                          "hablar con", "persona real", "ejecutiv", "llamen", "teléfono", "telefono")):
        return reply(
            "Claro — dejé tu solicitud con el equipo y una persona te contacta directamente.",
            "hablar_con_persona",
            handoff=True,
            reason="El paciente pidió hablar con una persona",
        )
    if any(word in question for word in ("angry", "terrible", "awful", "useless", "frustrat", "unacceptable",
                                          "enojad", "pésim", "pesim", "inaceptable", "molest")):
        return reply(
            "Lo siento mucho — no quiero empeorarlo, así que le pedí a una persona del equipo que siga desde acá.",
            "frustracion",
            handoff=True,
            reason="El paciente está molesto",
            sentiment="negative",
        )
    if any(word in question for word in ("hour", "open", "close", "closed", "horario", "atienden", "abren", "cierran")):
        return reply(f"Atendemos {HOURS}. ¿Quieres que te anote una hora?", "horarios")
    if any(word in question for word in ("price", "cost", "how much", "precio", "cuánto", "cuanto", "vale", "cuesta")):
        return reply(f"Estos son los valores: {CLINIC_SERVICES}. El presupuesto definitivo se entrega tras la evaluación. ¿Quieres agendar?", "precios")
    if any(word in question for word in ("where", "address", "location", "dirección", "direccion", "dónde", "donde", "ubicad", "llegar", "metro")):
        return reply(f"Estamos en {LOCATION}. ¿Quieres que te anote una hora?", "ubicacion")
    if any(word in question for word in ("insur", "fonasa", "isapre", "convenio", "previsión", "prevision", "empresa")):
        return reply(
            "Atendemos Fonasa e Isapre (con modalidad de reembolso). Con la credencial de tu empresa tienes 15% de descuento.",
            "convenios",
        )
    if any(word in question for word in ("book", "appointment", "reserve", "agendar", "agenda", "hora", "reservar", "cita")):
        return reply(
            "Con gusto — cuéntame tu nombre, RUT y el horario que prefieres, y confirmamos la cita.",
            "agendar",
        )
    if any(word in question for word in ("thank", "great", "perfect", "gracias", "genial", "perfecto")):
        return reply("¡Con gusto! ¿Hay algo más que quieras consultar?", "agradecimiento", sentiment="positive")
    return reply(
        "Sobre eso no tengo la información a mano, así que lo derivé al equipo — una persona te contacta en breve.",
        "fuera_de_alcance",
        handoff=True,
        reason="Consulta fuera de las respuestas documentadas",
    )


# --------------------------------------------------------------------------- #
# router: system prompt decides which task is being asked for
# --------------------------------------------------------------------------- #
def generate(messages: list[dict]) -> dict:
    system = _system_prompt(messages).lower()
    user_text = _last_user_message(messages)

    if os.environ.get("MOCK_LLM_DEBUG"):
        print(f"[mock-llm][debug] user text:\n{user_text[:2000]}\n[mock-llm][debug] ---", flush=True)

    if "invoice data extraction engine" in system:
        return extract_invoice(user_text)
    if "b2b lead qualification analyst" in system:
        joined = "\n".join(str(m.get("content") or "") for m in messages if m.get("role") == "user")
        marker = joined.find("Lead data (JSON):")
        chunk = joined[marker + len("Lead data (JSON):"):].lstrip() if marker != -1 else joined
        try:
            payload, _ = json.JSONDecoder().raw_decode(chunk)
        except json.JSONDecodeError:
            payload = {"message": chunk}
        return score_lead(payload)
    if "support assistant" in system or "asistente de recepción" in system:
        return support_reply(messages)
    return {"reply": "mock-llm: no rule matched this prompt", "intent": "fallback"}


# --------------------------------------------------------------------------- #
# HTTP layer (stdlib only)
# --------------------------------------------------------------------------- #
class Handler(BaseHTTPRequestHandler):
    server_version = "mock-llm/1.0"

    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") in ("/health", "/healthz"):
            self._send(200, {"status": "ok", "service": "mock-llm"})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path.rstrip("/") not in ("/chat", "/v1/chat/completions"):
            self._send(404, {"error": "not found", "hint": "POST /chat"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            request = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self._send(400, {"error": "invalid JSON body"})
            return

        messages = request.get("messages") or []
        content = json.dumps(generate(messages), ensure_ascii=False)
        self._send(
            200,
            {
                "id": f"chatcmpl-mock-{int(time.time() * 1000)}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": "mock-llm",
                "choices": [
                    {"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
                ],
                "usage": {
                    "prompt_tokens": sum(len(str(m.get("content") or "").split()) for m in messages),
                    "completion_tokens": len(content.split()),
                    "total_tokens": 0,
                },
            },
        )

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - stdlib signature
        print(f"[mock-llm] {self.address_string()} {format % args}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenAI-compatible deterministic mock LLM")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8770)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"[mock-llm] listening on http://{args.host}:{args.port} (POST /chat, GET /health)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
