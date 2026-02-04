# Knowledge Graph System — Developer Targets
#
# Run `make` or `make help` to see available targets.

.DEFAULT_GOAL := help
.PHONY: help test test-unit test-api test-verbose lint lint-queries \
        coverage coverage-verbose coverage-staleness \
        docs docs-cli docs-mcp docs-site \
        publish publish-status \
        diagnose status logs rebuild-api rebuild-web rebuild-all \
        start stop restart

SCRIPTS := scripts/development

##@ Testing (runs inside kg-api-dev container)

test: ## Run full test suite in container
	@docker exec kg-api-dev pytest tests/ -x -q

test-unit: ## Run unit tests only
	@docker exec kg-api-dev pytest tests/unit/ -x -q

test-api: ## Run API route tests only
	@docker exec kg-api-dev pytest tests/api/ -x -q

test-verbose: ## Run full suite with verbose output
	@docker exec kg-api-dev pytest tests/ -x -v --tb=short

##@ Static Analysis

lint: lint-queries coverage ## Run all static analysis

lint-queries: ## Lint Cypher queries for safety issues
	@python3 $(SCRIPTS)/lint/lint_queries.py

coverage: ## Report docstring coverage (Python, TypeScript, Rust)
	@python3 $(SCRIPTS)/lint/docstring_coverage.py

coverage-verbose: ## Show each undocumented item with file:line
	@python3 $(SCRIPTS)/lint/docstring_coverage.py -v

coverage-staleness: ## Check docstring freshness via @verified tags
	@python3 $(SCRIPTS)/lint/docstring_coverage.py --staleness

##@ Documentation

docs: docs-cli docs-mcp ## Generate all reference docs (CLI + MCP)

docs-cli: ## Generate CLI command reference
	@cd cli && npm run docs:cli

docs-mcp: ## Generate MCP server tool reference
	@cd cli && npm run docs:mcp

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

##@ Help

help: ## Show this help
	@echo "Usage: make <target>"
	@echo ""
	@awk '/^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } \
		/^[a-zA-Z_-]+:.*## / { printf "  \033[36m%-22s\033[0m%s\n", $$1, substr($$0, index($$0, "## ") + 3) }' \
		$(MAKEFILE_LIST)
