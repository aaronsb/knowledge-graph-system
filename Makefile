# Knowledge Graph System — Developer Targets
#
# Run `make` or `make help` to see available targets.

.DEFAULT_GOAL := help
.PHONY: help test test-unit test-api test-program test-verbose test-list lint lint-queries \
        coverage coverage-verbose coverage-staleness \
        todos todos-verbose todos-age slopscan \
        build-cli build-fuse install-cli install-fuse test-cli test-fuse \
        docs docs-cli docs-mcp docs-fuse docs-site \
        publish publish-status \
        diagnose status logs rebuild-api rebuild-web rebuild-all \
        build-operator push-operator \
        build-graph-accel build-postgres push-postgres \
        start stop restart

SCRIPTS := scripts/development

# Verify kg-api-dev container is running before test targets
_require-api:
	@docker inspect -f '{{.State.Running}}' kg-api-dev >/dev/null 2>&1 \
		|| { echo "Error: kg-api-dev container is not running. Start it with: make start"; exit 1; }

##@ Testing (runs inside kg-api-dev container)

test: _require-api ## Run full test suite in container
	@docker exec kg-api-dev pytest tests/ -x -q

test-unit: _require-api ## Run unit tests only
	@docker exec kg-api-dev pytest tests/unit/ -x -q

test-api: _require-api ## Run API route tests only
	@docker exec kg-api-dev pytest tests/api/ -x -q

test-program: _require-api ## Run GraphProgram validation spec
	@docker exec kg-api-dev pytest tests/unit/test_program_validation.py -v

test-verbose: _require-api ## Run full suite with verbose output
	@docker exec kg-api-dev pytest tests/ -x -v --tb=short

test-list: ## Show available test suites
	@echo "Available test suites:"
	@echo ""
	@echo "  make test           Full suite (unit + API)"
	@echo "  make test-unit      Unit tests only"
	@echo "  make test-api       API route tests only"
	@echo "  make test-program   GraphProgram validation spec (109 tests)"
	@echo "  make test-verbose   Full suite with verbose output"
	@echo ""
	@echo "Run inside kg-api-dev container. Start platform first: make start"

##@ Static Analysis

lint: lint-queries lint-dead-code coverage ## Run all static analysis

lint-queries: ## Lint Cypher queries for safety issues
	@python3 $(SCRIPTS)/lint/lint_queries.py

lint-dead-code: _require-api ## Detect unused code with vulture (high confidence only)
	@docker exec kg-api-dev vulture api/app/ --min-confidence 90 \
		--exclude api/app/models/,api/app/routes/ \
		|| true

coverage: ## Report docstring coverage (Python, TypeScript, Rust)
	@python3 $(SCRIPTS)/lint/docstring_coverage.py

coverage-verbose: ## Show each undocumented item with file:line
	@python3 $(SCRIPTS)/lint/docstring_coverage.py -v

coverage-staleness: ## Check docstring freshness via @verified tags
	@python3 $(SCRIPTS)/lint/docstring_coverage.py --staleness

todos: ## Scan for TODO/FIXME/HACK/XXX markers
	@python3 $(SCRIPTS)/lint/todo_inventory.py

todos-verbose: ## List every marker with file:line
	@python3 $(SCRIPTS)/lint/todo_inventory.py -v

todos-age: ## Include git blame age per marker
	@python3 $(SCRIPTS)/lint/todo_inventory.py -v --age

slopscan: ## SLOPSCAN 9000: detect agent antipatterns
	@python3 $(SCRIPTS)/lint/todo_inventory.py --slop -v

##@ User Tools — Build

build-cli: ## Build CLI + MCP (TypeScript)
	@cd cli && npm install && npm run build

build-fuse: ## Build FUSE driver (Python wheel)
	@cd fuse && python3 -m build

##@ User Tools — Install

install-cli: build-cli ## Install kg CLI + MCP server to ~/.local
	@cd cli && npm install -g --prefix "$(HOME)/.local"

install-fuse: ## Install kg-fuse via pipx
	@command -v pipx >/dev/null || { echo "Error: pipx not found. Install with: python3 -m pip install --user pipx"; exit 1; }
	@cd fuse && pipx install --force .

##@ User Tools — Test

test-cli: ## Run CLI test suite
	@cd cli && npm test

test-fuse: ## Run FUSE driver test suite
	@cd fuse && { [ -x .venv/bin/python ] && .venv/bin/python -m pytest tests/ -x -q || python3 -m pytest tests/ -x -q; }

##@ Documentation

docs: docs-cli docs-mcp docs-fuse ## Generate all reference docs

docs-cli: ## Generate CLI command reference
	@cd cli && npm run docs:cli

docs-mcp: ## Generate MCP server tool reference
	@cd cli && npm run docs:mcp

docs-fuse: ## Generate FUSE driver API reference (markdown)
	@python3 fuse/scripts/generate-fuse-docs.py

docs-site: ## Build documentation site (MkDocs)
	@./site/scripts/docs build

##@ Publishing

publish: ## Interactive publish wizard
	@scripts/publish-wizard.sh

publish-status: ## Show current versions and auth status
	@scripts/publish.sh status

##@ Platform

start: ## Start the platform
	@./operator.sh start

stop: ## Stop the platform
	@./operator.sh stop

restart: ## Restart the platform
	@./operator.sh stop && ./operator.sh start

status: ## Show platform health
	@./operator.sh status

logs: ## Follow API logs (Ctrl-C to stop)
	@./operator.sh logs api -f

diagnose: ## Run database and storage diagnostics
	@echo "=== Database Tables ===" && $(SCRIPTS)/diagnostics/list-tables.sh
	@echo ""
	@echo "=== Garage Storage ===" && $(SCRIPTS)/diagnostics/garage-status.sh

##@ Build

rebuild-api: ## Rebuild and restart the API container
	@$(SCRIPTS)/build/rebuild-api.sh

rebuild-web: ## Rebuild and restart the web container
	@$(SCRIPTS)/build/rebuild-web.sh

rebuild-all: ## Rebuild all containers
	@$(SCRIPTS)/build/rebuild-all.sh

GHCR := ghcr.io/aaronsb/knowledge-graph-system

build-operator: ## Build the operator container
	@docker build -t $(GHCR)/kg-operator:latest -f operator/Dockerfile .

push-operator: ## Build and push the operator container to GHCR
	@docker build -t $(GHCR)/kg-operator:latest -f operator/Dockerfile .
	@docker push $(GHCR)/kg-operator:latest

build-graph-accel: ## Compile graph_accel extension (current arch)
	@./graph-accel/build-in-container.sh

build-postgres: ## Build the postgres container (requires graph-accel dist/)
	@docker build -t $(GHCR)/kg-postgres:latest -f docker/Dockerfile.postgres .

push-postgres: build-graph-accel build-postgres ## Compile graph_accel, build and push postgres to GHCR
	@docker push $(GHCR)/kg-postgres:latest

##@ Help

help: ## Show this help
	@echo "Usage: make <target>"
	@echo ""
	@awk '/^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } \
		/^[a-zA-Z_-]+:.*## / { printf "  \033[36m%-22s\033[0m%s\n", $$1, substr($$0, index($$0, "## ") + 3) }' \
		$(MAKEFILE_LIST)
