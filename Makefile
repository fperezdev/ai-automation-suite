SHELL := /bin/sh
COMPOSE := docker compose -f docker-compose.yml
N8N_URL ?= http://localhost:5688

.PHONY: help up down logs demo ui ps reset seed panel

help: ## show this help
	@grep -E '^[a-z]+:.*?##' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  %-8s %s\n", $$1, $$2}'

up: ## start n8n + the mock LLM (detached)
	$(COMPOSE) up -d --wait

down: ## stop and remove the containers (keeps the n8n volume)
	$(COMPOSE) down

reset: ## stop everything and wipe the n8n volume (fresh state)
	$(COMPOSE) down -v

logs: ## follow the n8n logs
	$(COMPOSE) logs -f n8n

ps: ## show container status
	$(COMPOSE) ps

ui: ## print the URLs to open
	@echo "n8n UI:           $(N8N_URL)   (first run: create the owner account, it stays local)"
	@echo "M1 asistente:     $(N8N_URL)/webhook/whatsapp-dental"
	@echo "M2 facturacion:   $(N8N_URL)/webhook/doc-automation"
	@echo "M3 captacion:     $(N8N_URL)/webhook/lead-gen"
	@echo "M4 soporte:       $(N8N_URL)/webhook/support-agent"
	@echo "mock LLM:         http://localhost:8780/health"
	@echo "panel:            http://localhost:8090/"
	@echo "API docs:         http://localhost:8090/docs"

seed: ## carga los datos de demostración (clínica) en Postgres
	$(COMPOSE) exec -T api python seed.py

panel: ## muestra la URL del panel de operación
	@echo "panel:   http://localhost:8090/   (datos demo: make seed)"

demo: ## run the end-to-end smoke test against the running stack
	N8N_URL=$(N8N_URL) ./scripts/smoke_test.sh
