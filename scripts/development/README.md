# Development Scripts

Development utilities for code quality, testing, and auditing.

## Directory Structure

```
scripts/development/
├── README.md                 # This file
├── audit-api-auth.py        # API authentication audit tool
└── test/                     # Test runner scripts
    ├── all.sh               # Run all tests
    ├── api.sh               # Python API tests
    └── ...
```

## Authentication Audit

### audit-api-auth.py

**Purpose:** Continuously monitor API endpoint authentication coverage.

**When to Run:**
- Before committing API changes
- When adding new endpoints
- During security reviews
- As part of CI/CD pipeline

**Usage:**

```bash
# Quick summary (default - prints table to terminal)
./scripts/development/audit-api-auth.py

# Detailed breakdown with all endpoints
./scripts/development/audit-api-auth.py --verbose

# Also export to JSON (still prints table)
./scripts/development/audit-api-auth.py --format=json

# Also export to Markdown (still prints table)
./scripts/development/audit-api-auth.py --format=markdown

# Custom output path
./scripts/development/audit-api-auth.py --format=markdown --output=docs/testing/AUTH_AUDIT.md
```

**Note:** The tool always prints the summary table to the terminal. The `--format` option adds file export on top of that.

**What It Checks:**
- ✅ Which endpoints require authentication
- ✅ Which endpoints are public
- ✅ Which endpoints have role/permission requirements
- ⚠️  Which endpoints lack auth but probably should

**Output Categories:**
1. **Public** - No auth required (documented as public)
2. **Authenticated** - Requires valid user session
3. **Role-Based** - Requires specific role (e.g., admin)
4. **Permission-Based** - Requires specific permission
5. **⚠️ Unclear/Missing** - Needs review (likely missing auth)

**Example Output:**

```
================================================================================
API ENDPOINT AUTHENTICATION AUDIT
================================================================================

Total endpoints: 112

+--------------------------+---------+
| Category                 |   Count |
+==========================+=========+
| Public (no auth)         |      54 |
+--------------------------+---------+
| Authenticated (user)     |       6 |
+--------------------------+---------+
| Role-based               |       0 |
+--------------------------+---------+
| Permission-based         |       0 |
+--------------------------+---------+
| ⚠️  Unclear/Missing Auth |      52 |
+--------------------------+---------+
```

**Integration with CI/CD:**

Add to `.github/workflows/security-audit.yml`:

```yaml
name: Security Audit

on:
  pull_request:
    paths:
      - 'src/api/routes/**'
  schedule:
    - cron: '0 0 * * 0'  # Weekly on Sunday

jobs:
  audit-auth:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install tabulate

      - name: Run auth audit
        run: |
          ./scripts/development/audit-api-auth.py --format=markdown --output=auth_audit.md

      - name: Check for regression
        run: |
          # Fail if number of unclear/missing auth endpoints increased
          python scripts/development/check_auth_regression.py

      - name: Upload audit report
        uses: actions/upload-artifact@v3
        with:
          name: auth-audit-report
          path: auth_audit.md
```

**Pre-Commit Hook:**

Add to `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Run auth audit if API routes changed

if git diff --cached --name-only | grep -q "src/api/routes"; then
    echo "API routes changed, running auth audit..."
    ./scripts/development/audit-api-auth.py

    # Ask for confirmation if unclear endpoints exist
    unclear_count=$(./scripts/development/audit-api-auth.py --format=json --output=/tmp/audit.json && \
                    jq '.unclear | length' /tmp/audit.json)

    if [ "$unclear_count" -gt 0 ]; then
        echo "⚠️  Warning: $unclear_count endpoints with unclear authentication"
        read -p "Continue with commit? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
fi
```

## Testing

See `test/README.md` for the complete testing framework documentation.

## Contributing

When adding new development scripts:

1. **Make it executable:** `chmod +x your-script.sh`
2. **Add usage docs:** Update this README
3. **Follow naming:** Use kebab-case (e.g., `check-something.py`)
4. **Add help:** Support `--help` flag
5. **Test it:** Run on real codebase before committing

## Related Documentation

- [API Auth Testing Research](../../docs/testing/API_AUTH_TESTING_RESEARCH.md)
- [API Auth Audit Summary](../../docs/testing/API_AUTH_AUDIT_SUMMARY.md)
- [Testing Framework](./test/README.md)
- [ADR-054: OAuth 2.0 Authentication](../../docs/architecture/ADR-054-oauth-authentication.md)
- [ADR-028: Dynamic RBAC](../../docs/architecture/ADR-028-dynamic-rbac.md)
