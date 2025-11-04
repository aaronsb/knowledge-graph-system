# Development Test Scripts

Quick-access scripts for running tests during development. These scripts provide an easy way to run specific test suites without memorizing pytest commands.

## Quick Reference

```bash
# Unit tests (fast, no database required)
./scripts/development/test/unit.sh

# Datetime utilities tests
./scripts/development/test/datetime.sh

# Datetime linter
./scripts/development/test/lint-datetime.sh
```

## Available Scripts

### `unit.sh` - Unit Tests
Runs all unit tests (no external dependencies like database or API server).

**Examples:**
```bash
# Run all unit tests
./scripts/development/test/unit.sh

# Verbose output
./scripts/development/test/unit.sh -v

# Quick mode (skip coverage)
./scripts/development/test/unit.sh --quick

# Run specific test
./scripts/development/test/unit.sh -k datetime
```

**What it runs:**
- Pure Python unit tests
- No database required
- No API server required
- Fast feedback (<5 seconds)

**Excludes:**
- `tests/api/` (require database)
- `tests/test_synonym_detector.py` (requires database)
- `tests/test_vocabulary_manager_integration.py` (requires database)
- `tests/test_phase3_vocabulary_graph.py` (requires database)

---

### `datetime.sh` - Datetime Utilities Tests
Runs the ADR-056 datetime utilities test suite.

**Examples:**
```bash
# Run with coverage
./scripts/development/test/datetime.sh

# Quick mode (no coverage)
./scripts/development/test/datetime.sh --quick

# Verbose output
./scripts/development/test/datetime.sh -v
```

**What it tests:**
- `src/api/lib/datetime_utils.py` module
- 32 comprehensive tests
- 100% code coverage
- Timezone-aware datetime handling

---

### `lint-datetime.sh` - Datetime Usage Linter
Checks for unsafe datetime patterns in the codebase (ADR-056).

**Examples:**
```bash
# Lint entire src/api directory
./scripts/development/test/lint-datetime.sh

# Show violations with line numbers
./scripts/development/test/lint-datetime.sh --verbose

# Exit with code 1 if violations found (for CI)
./scripts/development/test/lint-datetime.sh --strict

# Lint specific file
./scripts/development/test/lint-datetime.sh --path src/api/lib/auth.py
```

**What it detects:**
- `datetime.utcnow()` (deprecated, use `datetime_utils.utcnow()`)
- `datetime.now()` without timezone (use `datetime_utils.utcnow()`)
- `datetime.fromtimestamp()` without tz (use `datetime_utils.utc_from_timestamp()`)

**Current status:**
- 13/34 violations fixed (38% complete)
- All critical security/job modules clean
- 21 violations remain in low-priority files

---

## Common Workflows

### During Active Development
```bash
# Fast iteration: run unit tests
./scripts/development/test/unit.sh --quick

# Or watch mode (requires pytest-watch):
# pip install pytest-watch
pytest-watch tests/ --ignore=tests/api/ --runner "pytest -v --tb=short"
```

### Before Committing
```bash
# Run unit tests + linting
./scripts/development/test/unit.sh
./scripts/development/test/lint-datetime.sh --verbose
```

### Testing Specific Changes
```bash
# If you modified datetime utilities:
./scripts/development/test/datetime.sh

# If you modified auth/OAuth code:
./scripts/development/test/lint-datetime.sh --path src/api/lib/auth.py
./scripts/development/test/lint-datetime.sh --path src/api/routes/oauth.py
```

---

## Future Expansion

As the test infrastructure grows, additional scripts will be added:

- **`integration.sh`** - Integration tests (auto-starts database)
- **`api.sh`** - API endpoint tests (auto-starts API server)
- **`all.sh`** - Full test suite (unit + integration)
- **`coverage.sh`** - Comprehensive coverage report
- **`lint.sh`** - All linters (datetime, queries, code quality)
- **`quick.sh`** - Pre-commit checks (fast)
- **`watch.sh`** - Continuous testing on file changes

---

## Prerequisites

**Virtual Environment:**
All scripts require an activated Python virtual environment:
```bash
# One-time setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Scripts will check for `venv/` and warn if not found.

**Test Dependencies:**
```bash
pip install pytest pytest-cov pytest-asyncio
```

---

## CI/CD Integration

These scripts are designed to work in both local development and CI pipelines:

```yaml
# .github/workflows/test.yml
- name: Run unit tests
  run: ./scripts/development/test/unit.sh --quick

- name: Lint datetime usage
  run: ./scripts/development/test/lint-datetime.sh --strict
```

---

## Related Documentation

- **ADR-056:** Timezone-Aware Datetime Utilities
  - `docs/architecture/ADR-056-timezone-aware-datetime-utilities.md`
  - Migration guide for datetime violations

- **Testing Guide:** (future)
  - `docs/guides/TESTING.md`
  - Comprehensive testing documentation

---

**Pattern Established:** 2025-11-04
**Next Steps:** Add integration test scripts when database testing infrastructure is mature
