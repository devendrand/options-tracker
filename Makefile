# Options Tracker — Lifecycle Makefile
# Manages DEV / QA / PROD local environments
#
# One-time setup:
#   make setup
#
# Deploy to DEV (latest main, hot-reload):
#   make deploy-dev
#
# Promote a git tag to QA or PROD:
#   make promote-qa VERSION=v0.1-rc1
#   make promote-prod VERSION=v0.1

.DEFAULT_GOAL := help

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Fail-fast check: ensure an env file exists before running docker compose
_check_env = @if [ ! -f "$(1)" ]; then \
	echo "ERROR: $(1) not found. Run: cp $(1).example $(1)"; \
	exit 1; \
fi

# Determine if a string is a branch name (exists in refs/heads)
_is_branch = $(shell git show-ref --verify --quiet refs/heads/$(1) 2>/dev/null && echo yes || echo no)

# ---------------------------------------------------------------------------
# setup
# ---------------------------------------------------------------------------

.PHONY: setup
setup: ## Create .env.dev / .env.qa / .env.prod from examples (idempotent)
	@created=""; \
	for env in dev qa prod; do \
		if [ ! -f ".env.$$env" ]; then \
			cp ".env.$$env.example" ".env.$$env"; \
			created="$$created .env.$$env"; \
		fi; \
	done; \
	if [ -n "$$created" ]; then \
		echo "Created:$$created"; \
		echo "Edit credentials before deploying."; \
	else \
		echo "All env files already exist — nothing to do."; \
	fi

# ---------------------------------------------------------------------------
# deploy-dev
# ---------------------------------------------------------------------------

.PHONY: deploy-dev
deploy-dev: ## Build and deploy latest main to DEV (port 4200/8000/5432, hot-reload)
	$(call _check_env,.env.dev)
	@if [ -n "$$(git status --porcelain 2>/dev/null)" ]; then \
		echo "WARNING: Working tree has uncommitted changes. Deploying current state."; \
	fi
	docker compose -f docker-compose.dev.yml --env-file .env.dev up -d --build
	@git rev-parse --short HEAD > .version-dev 2>/dev/null || echo "main" > .version-dev
	@echo ""
	@echo "DEV deployed → http://localhost:4200  (API: http://localhost:8000)"
	@echo "Run smoke tests: make smoke-dev"

# ---------------------------------------------------------------------------
# promote-qa
# ---------------------------------------------------------------------------

.PHONY: promote-qa
promote-qa: ## Deploy a git tag to QA  (make promote-qa VERSION=v0.1-rc1)
	$(call _check_env,.env.qa)
	@if [ -z "$(VERSION)" ]; then \
		echo "ERROR: VERSION is required. Usage: make promote-qa VERSION=v0.1-rc1"; \
		exit 1; \
	fi
	@if [ -z "$$(git tag -l '$(VERSION)')" ]; then \
		echo "ERROR: Tag '$(VERSION)' not found locally. Run: git tag $(VERSION)"; \
		exit 1; \
	fi
	@if [ "$$(git show-ref --verify --quiet refs/heads/$(VERSION) 2>/dev/null && echo yes || echo no)" = "yes" ]; then \
		echo "WARNING: '$(VERSION)' looks like a branch name, not a tag."; \
		printf "Continue anyway? [y/N] "; \
		read ans; [ "$$ans" = "y" ] || exit 1; \
	fi
	@WORKTREE=/tmp/options-tracker-qa; \
	echo "Checking out $(VERSION) into $$WORKTREE ..."; \
	git worktree remove --force "$$WORKTREE" 2>/dev/null || true; \
	git worktree add "$$WORKTREE" "$(VERSION)"; \
	docker compose \
		-f "$$WORKTREE/docker-compose.qa.yml" \
		--env-file .env.qa \
		--project-directory . \
		up -d --build; \
	git worktree remove --force "$$WORKTREE"; \
	echo "$(VERSION)" > .version-qa
	@echo ""
	@echo "QA deployed → http://localhost:4300  (API: http://localhost:8100)  version: $(VERSION)"
	@echo "Run smoke tests: make smoke-qa"

# ---------------------------------------------------------------------------
# promote-prod
# ---------------------------------------------------------------------------

.PHONY: promote-prod
promote-prod: ## Deploy a git tag to PROD  (make promote-prod VERSION=v0.1)
	$(call _check_env,.env.prod)
	@if [ -z "$(VERSION)" ]; then \
		echo "ERROR: VERSION is required. Usage: make promote-prod VERSION=v0.1"; \
		exit 1; \
	fi
	@if [ -z "$$(git tag -l '$(VERSION)')" ]; then \
		echo "ERROR: Tag '$(VERSION)' not found locally. Run: git tag $(VERSION)"; \
		exit 1; \
	fi
	@if [ "$$(git show-ref --verify --quiet refs/heads/$(VERSION) 2>/dev/null && echo yes || echo no)" = "yes" ]; then \
		echo "WARNING: '$(VERSION)' looks like a branch name, not a tag."; \
		printf "Continue anyway? [y/N] "; \
		read ans; [ "$$ans" = "y" ] || exit 1; \
	fi
	@WORKTREE=/tmp/options-tracker-prod; \
	echo "Checking out $(VERSION) into $$WORKTREE ..."; \
	git worktree remove --force "$$WORKTREE" 2>/dev/null || true; \
	git worktree add "$$WORKTREE" "$(VERSION)"; \
	docker compose \
		-f "$$WORKTREE/docker-compose.prod.yml" \
		--env-file .env.prod \
		--project-directory . \
		up -d --build; \
	git worktree remove --force "$$WORKTREE"; \
	echo "$(VERSION)" > .version-prod
	@echo ""
	@echo "PROD deployed → http://localhost:4400  (API: http://localhost:8200)  version: $(VERSION)"

# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

.PHONY: status
status: ## Show version and health of all three environments
	@printf "\n%-12s %-16s %-26s %-26s %-14s %s\n" \
		"Environment" "Version" "Frontend" "Backend" "DB" "Status"
	@printf "%-12s %-16s %-26s %-26s %-14s %s\n" \
		"───────────" "───────────────" "─────────────────────────" \
		"─────────────────────────" "─────────────" "──────"
	@for env in dev qa prod; do \
		fe_port=$$(case $$env in dev) echo 4200;; qa) echo 4300;; prod) echo 4400;; esac); \
		be_port=$$(case $$env in dev) echo 8000;; qa) echo 8100;; prod) echo 8200;; esac); \
		db_port=$$(case $$env in dev) echo 5432;; qa) echo 5433;; prod) echo 5434;; esac); \
		version="(not running)"; \
		[ -f ".version-$$env" ] && version=$$(cat ".version-$$env"); \
		container="ot-backend-$$env"; \
		health=$$(docker inspect --format='{{.State.Health.Status}}' "$$container" 2>/dev/null || echo "stopped"); \
		status=$$(case $$health in healthy) echo HEALTHY;; unhealthy) echo UNHEALTHY;; starting) echo STARTING;; *) echo STOPPED;; esac); \
		printf "%-12s %-16s %-26s %-26s %-14s %s\n" \
			"$$env" "$$version" \
			"http://localhost:$$fe_port" \
			"http://localhost:$$be_port" \
			"localhost:$$db_port" \
			"$$status"; \
	done
	@echo ""

# ---------------------------------------------------------------------------
# teardown
# ---------------------------------------------------------------------------

.PHONY: teardown-dev
teardown-dev: ## Stop DEV containers (data volume postgres_data_dev preserved)
	$(call _check_env,.env.dev)
	docker compose -f docker-compose.dev.yml --env-file .env.dev down
	@echo "DEV environment stopped. Data volume postgres_data_dev preserved."

.PHONY: teardown-qa
teardown-qa: ## Stop QA containers (data volume postgres_data_qa preserved)
	$(call _check_env,.env.qa)
	docker compose -f docker-compose.qa.yml --env-file .env.qa down
	@echo "QA environment stopped. Data volume postgres_data_qa preserved."

.PHONY: teardown-prod
teardown-prod: ## Stop PROD containers (data volume postgres_data_prod preserved)
	$(call _check_env,.env.prod)
	docker compose -f docker-compose.prod.yml --env-file .env.prod down
	@echo "PROD environment stopped. Data volume postgres_data_prod preserved."

.PHONY: teardown-all
teardown-all: teardown-dev teardown-qa teardown-prod ## Stop all environments

# ---------------------------------------------------------------------------
# logs
# ---------------------------------------------------------------------------

.PHONY: logs-dev
logs-dev: ## Tail all DEV container logs (Ctrl+C to exit)
	$(call _check_env,.env.dev)
	docker compose -f docker-compose.dev.yml --env-file .env.dev logs -f

.PHONY: logs-qa
logs-qa: ## Tail all QA container logs (Ctrl+C to exit)
	$(call _check_env,.env.qa)
	docker compose -f docker-compose.qa.yml --env-file .env.qa logs -f

.PHONY: logs-prod
logs-prod: ## Tail all PROD container logs (Ctrl+C to exit)
	$(call _check_env,.env.prod)
	docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f

# ---------------------------------------------------------------------------
# smoke tests (F-19)
# ---------------------------------------------------------------------------

.PHONY: smoke-dev
smoke-dev: ## Run F-19 smoke suite against DEV (http://localhost:8000)
	$(call _check_env,.env.dev)
	SMOKE_BASE_URL=http://localhost:8000 \
	DATABASE_URL=$$(grep '^DATABASE_URL=' .env.dev | cut -d= -f2-) \
	python smoke-tests/run_smoke_tests.py http://localhost:8000

.PHONY: smoke-qa
smoke-qa: ## Run F-19 smoke suite against QA (http://localhost:8100)
	$(call _check_env,.env.qa)
	SMOKE_BASE_URL=http://localhost:8100 \
	DATABASE_URL=$$(grep '^DATABASE_URL=' .env.qa | cut -d= -f2-) \
	python smoke-tests/run_smoke_tests.py http://localhost:8100

.PHONY: smoke-prod
smoke-prod: ## Run F-19 smoke suite against PROD (http://localhost:8200)
	$(call _check_env,.env.prod)
	SMOKE_BASE_URL=http://localhost:8200 \
	DATABASE_URL=$$(grep '^DATABASE_URL=' .env.prod | cut -d= -f2-) \
	python smoke-tests/run_smoke_tests.py http://localhost:8200

# ---------------------------------------------------------------------------
# help
# ---------------------------------------------------------------------------

.PHONY: help
help: ## Show this help
	@echo "Options Tracker — Makefile"
	@echo ""
	@echo "Usage: make <target> [VERSION=vX.Y]"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'
	@echo ""
