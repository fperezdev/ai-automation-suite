#!/usr/bin/env python3
"""Capturas (PNG) de los módulos 2, 3 y 4 manejando las páginas reales con Playwright.

Requiere el stack levantado:  make up
Uso:  PLAYWRIGHT_BROWSERS_PATH=... python scripts/make_suite_captures.py
"""
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("N8N_URL", "http://localhost:5688")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "capturas"
OUT.mkdir(parents=True, exist_ok=True)


def shot(page, name):
    p = OUT / name
    page.screenshot(path=str(p), full_page=True)
    print("wrote", p)


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1100, "height": 900})

        # --- Módulo 2: facturas ------------------------------------------------
        page.goto(f"{BASE}/webhook/doc-automation", wait_until="networkidle")
        page.screenshot(path=str(OUT / "m2-1-upload.png"), full_page=True)
        print("wrote", OUT / "m2-1-upload.png")
        page.set_input_files("#file", str(ROOT / "samples" / "invoice_003.pdf"))
        page.wait_for_selector("#result", state="visible", timeout=60000)
        time.sleep(0.6)
        shot(page, "m2-2-report-review.png")

        # --- Módulo 3: captación ----------------------------------------------
        page.goto(f"{BASE}/webhook/lead-gen", wait_until="networkidle")
        page.fill("#name", "María Soto")
        page.fill("#email", "maria.soto@example.com")
        page.fill("#company", "Estudio Contable Soto")
        page.fill("#website", "https://example.com")
        page.fill("#message", "Busco ortodoncia para mi hija, quiero cotizar y agendar una evaluación.")
        page.click("#send")
        page.wait_for_selector("#result", state="visible", timeout=60000)
        time.sleep(0.6)
        shot(page, "m3-1-lead-report.png")

        # --- Módulo 4: soporte (webchat) --------------------------------------
        page.goto(f"{BASE}/webhook/support-agent", wait_until="networkidle")
        for msg in ["¿cuánto cuesta una limpieza dental?", "¿dónde quedan? voy en metro"]:
            page.fill("#input", msg)
            page.click("#send")
            page.wait_for_timeout(3500)
        shot(page, "m4-1-webchat.png")

        # segundo caso: derivación a humano
        page2 = browser.new_page(viewport={"width": 1100, "height": 900})
        page2.goto(f"{BASE}/webhook/support-agent", wait_until="networkidle")
        page2.fill("#input", "me cobraron mal y quiero hablar con una persona")
        page2.click("#send")
        page2.wait_for_timeout(3500)
        shot(page2, "m4-2-handoff.png")

        browser.close()


if __name__ == "__main__":
    sys.exit(main())
