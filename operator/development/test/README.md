# Development Test Scripts

Simple test script tree for running tests across the entire stack (Python API, TypeScript CLI/MCP, React webapp).

## Quick Reference

```bash
# Run everything
./scripts/development/test/all.sh

# Run by component (focused testing)
./scripts/development/test/api.sh       # Python API server tests
./scripts/development/test/client.sh    # TypeScript CLI + MCP tests (future)
./scripts/development/test/webapp.sh    # React webapp tests (future)
./scripts/development/test/lint.sh      # All code quality linters
```

## The Test Tree

```
                          all.sh (run everything)
                             |
        ┌────────────────────┼────────────────────┬──────────┐
        |                    |                    |          |
     api.sh             client.sh            webapp.sh    lint.sh
   (Python)          (TypeScript)            (React)    (Linters)
```

**Vertical navigation** - Test one component:
- Focus on Python API while developing backend
- Focus on TypeScript client while developing CLI/MCP
- Focus on React webapp while developing visualizations

**Horizontal navigation** - Test entire stack:
- `all.sh` runs everything before commit/PR
- Validates cross-component integration

## Scripts

### `all.sh` - Complete Test Suite

Run all tests across entire stack (Python + TypeScript + React + linters).

```bash
./scripts/development/test/all.sh              # Run everything
./scripts/development/test/all.sh --quick      # Skip coverage
```

**What it does:**
- Runs `api.sh` (Python tests)
- Runs `client.sh` (TypeScript tests - future)
- Runs `webapp.sh` (React tests - future)
- Runs `lint.sh` (all linters)
- Shows pass/fail summary

**When to use:**
- Before committing changes
- Before creating pull requests
- When you want comprehensive validation

---

### `api.sh` - Python API Server Tests

Test the Python API server (`api/app/`).

```bash
./scripts/development/test/api.sh              # All API tests with coverage
./scripts/development/test/api.sh --quick      # Skip coverage (faster)
./scripts/development/test/api.sh -k datetime  # Run specific tests
./scripts/development/test/api.sh -v           # Verbose output
```

**What it tests:**
- Unit tests (fast, no database required)
- Integration tests (requires database - future)
- Infrastructure: datetime, auth, config, secrets
- Ingestion: LLM extraction, chunking, workers
- Queries: graph queries, search, connections
- Vocabulary: vocabulary management

**Current scope:**
- 205 unit tests
- Excludes integration tests (require database)
- Coverage report: `htmlcov/unit/index.html`

---

### `client.sh` - TypeScript CLI + MCP Tests

Test the TypeScript client (`client/`).

```bash
./scripts/development/test/client.sh           # All client tests
./scripts/development/test/client.sh --watch   # Watch mode
```

**What it will test** (future):
- CLI command tests
- MCP server tool tests
- API client integration

**Status:** Placeholder - tests not yet implemented

---

### `webapp.sh` - React Webapp Tests

Test the React webapp (`viz-app/`).

```bash
./scripts/development/test/webapp.sh           # All webapp tests
./scripts/development/test/webapp.sh --watch   # Watch mode
```

**What it will test** (future):
- Component tests
- Integration tests
- E2E tests

**Status:** Placeholder - tests not yet implemented

---

### `lint.sh` - Code Quality Linters

Run all code quality linters across the codebase.

```bash
./scripts/development/test/lint.sh              # All linters
./scripts/development/test/lint.sh --verbose    # Show violations
./scripts/development/test/lint.sh --strict     # Exit 1 on violations
```

**Current linters:**
- **Datetime linter (ADR-056)** - Detects unsafe datetime patterns
  - `datetime.utcnow()` (deprecated)
  - `datetime.now()` without timezone
  - `datetime.fromtimestamp()` without tz

**Future linters:**
- Query safety linter (ADR-048) - Namespace safety checks
- General code quality (pylint, flake8, etc.)

**Linter implementations:** `src/testing/linters/`

---

## Common Workflows

### During Active Development

Focus on the component you're working on:

```bash
# Working on Python API
./scripts/development/test/api.sh --quick      # Fast feedback loop

# Working on TypeScript client (future)
./scripts/development/test/client.sh --watch   # Auto-run on changes

# Working on React webapp (future)
./scripts/development/test/webapp.sh --watch   # Auto-run on changes
```

### Before Committing

Run complete validation:

```bash
# Run everything
./scripts/development/test/all.sh

# Or run separately for more control
./scripts/development/test/api.sh
./scripts/development/test/lint.sh
```

### Testing Specific Features

Use pytest directly from repo root (requires venv):

```bash
source venv/bin/activate

# Run specific test file
pytest tests/test_datetime_utils.py

# Run tests matching pattern
pytest tests/ -k datetime

# Run with verbose output
pytest tests/test_datetime_utils.py -v
```

---

## Future Expansion

As testing infrastructure grows, consider adding:

### Functional Domain Scripts

Cross-component test slices by feature (advanced pattern):

```bash
scripts/development/test/
├── queries.sh         # Query tests: API + CLI + MCP + webapp
├── ingestion.sh       # Ingestion tests: API + CLI
├── vocabulary.sh      # Vocabulary tests: API + CLI
├── infrastructure.sh  # Infrastructure tests: API + client + webapp
```

Each functional script orchestrates multiple components:

```bash
# Example: queries.sh
pytest tests/ -k query                    # Python API query tests
(cd client && npm test -- search)         # TypeScript CLI query tests
(cd viz-app && npm test -- QueryBuilder)  # React query visualization tests
```

**Benefits:**
- Test features end-to-end across entire stack
- Catch integration issues between components
- Map to user-facing functionality

**When to implement:**
- When you have tests in multiple components
- When you need cross-component validation
- When functional grouping adds value

---

## Architecture Decision Records (ADRs)

Tests are linked to ADRs that document architectural decisions:

| ADR | Related Tests | What it validates |
|-----|---------------|-------------------|
| ADR-056 | `api.sh -k datetime`<br>`lint.sh` (datetime linter) | Timezone-aware datetime utilities |
| ADR-048 | (future) Query safety tests | Query facade namespace safety |
| ADR-042 | (future) Ollama tests | Local LLM inference |

See `docs/architecture/ARCHITECTURE_DECISIONS.md` for complete ADR index.

---

## Prerequisites

**Python tests (api.sh):**
```bash
# One-time setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install test dependencies
pip install pytest pytest-cov pytest-asyncio
```

Scripts automatically activate venv if found.

**TypeScript tests (client.sh, webapp.sh):**
```bash
# Client
cd client
npm install
npm test

# Webapp
cd viz-app
npm install
npm test
```

---

## CI/CD Integration

These scripts work in both local development and CI pipelines:

```yaml
# .github/workflows/test.yml
- name: Run all tests
  run: ./scripts/development/test/all.sh

# Or run separately for parallel execution
- name: Python API tests
  run: ./scripts/development/test/api.sh --quick

- name: TypeScript client tests
  run: ./scripts/development/test/client.sh

- name: Linters
  run: ./scripts/development/test/lint.sh --strict
```

---

## Design Philosophy

**Start simple, grow as needed:**
- Begin with component-based scripts (api, client, webapp, lint, all)
- Add functional domain scripts when cross-component testing becomes valuable
- Keep scripts thin - they orchestrate existing test frameworks (pytest, jest, vitest)

**Why shell scripts?**
- Handle venv activation automatically
- Orchestrate across multiple languages/frameworks
- Provide consistent interface (no need to remember pytest vs npm test)
- Navigate the test tree at any level

**The test tree mental model:**
- Root: `all.sh` (everything)
- Branches: `api.sh`, `client.sh`, `webapp.sh` (components)
- Leaves: Direct test runner (pytest, npm test)
- Optional slices: Functional domain scripts (queries, ingestion, etc.)

---

**Pattern Established:** 2025-11-04
**Next Steps:** Add client/webapp tests when codebases mature, consider functional domain scripts when cross-component testing adds value
