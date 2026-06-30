# ─────────────────────────────────────────────────────────────
# AI Recruitment Intelligence Platform — developer task runner
# ─────────────────────────────────────────────────────────────
.DEFAULT_GOAL := help

# ---- Docker Compose ---------------------------------------------------------
.PHONY: up down build logs ps restart
up: ## Start the full stack (db + backend)
	docker compose up --build

down: ## Stop and remove containers
	docker compose down

build: ## Build all images
	docker compose build

logs: ## Tail logs from all services
	docker compose logs -f

ps: ## Show running services
	docker compose ps

restart: down up ## Restart the stack

# ---- Backend ----------------------------------------------------------------
.PHONY: backend-install backend-run lint format typecheck test check
backend-install: ## Install backend deps into the active venv
	cd backend && pip install -r requirements.txt -r requirements-dev.txt

backend-run: ## Run the API locally (requires local Postgres)
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

lint: ## Run ruff linter
	cd backend && ruff check .

format: ## Apply black + isort + ruff --fix
	cd backend && isort . && black . && ruff check --fix .

typecheck: ## Run mypy
	cd backend && mypy app

test: ## Run pytest
	cd backend && pytest

check: lint typecheck test ## Run all backend quality gates

# ---- Database / migrations --------------------------------------------------
.PHONY: migrate revision
migrate: ## Apply latest Alembic migrations
	cd backend && alembic upgrade head

revision: ## Create a new migration: make revision m="message"
	cd backend && alembic revision --autogenerate -m "$(m)"

# ---- Help -------------------------------------------------------------------
.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
