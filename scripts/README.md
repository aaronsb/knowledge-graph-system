# Knowledge Graph Scripts

Organized collection of scripts for managing the Knowledge Graph System.

## Directory Structure

```
scripts/
├── setup/           # Initial setup and configuration
├── database/        # Database lifecycle and operations
├── services/        # Application service management
├── ollama/          # Local AI infrastructure (Docker)
├── diagnostics/     # Monitoring and debugging tools
├── admin/           # User and security administration
├── tools/           # Utility scripts
└── teardown/        # System cleanup and removal
```

## Quick Reference

### Initial Setup

```bash
# 1. Start database
#    - Starts PostgreSQL + Apache AGE container
#    - Automatically runs migrate-db.sh to apply all schema migrations
./scripts/services/start-database.sh

# 2. Start API server
./scripts/services/start-api.sh -y

# 3. Initialize authentication and secrets
./scripts/setup/initialize-auth.sh

# Optional: Configure database performance profile
./scripts/setup/configure-db-profile.sh <small|medium|large>

# Optional: Configure AI providers (legacy - now via kg CLI)
./scripts/setup/configure-ai.sh
```

### Daily Operations

```bash
# Database operations
./scripts/services/start-database.sh    # Start PostgreSQL + Apache AGE (auto-runs migrations)
./scripts/services/stop-database.sh     # Stop database
./scripts/database/migrate-db.sh        # Apply schema migrations (manual - auto-runs during start)
./scripts/database/backup-database.sh   # Create binary backup
./scripts/database/restore-database.sh  # Restore from backup

# Service management
./scripts/services/start-api.sh         # Start FastAPI server
./scripts/services/start-viz.sh         # Start visualization server
./scripts/services/stop-api.sh          # [Placeholder] Stop API (not containerized yet)
./scripts/services/stop-viz.sh          # [Placeholder] Stop viz (not containerized yet)

# Local AI (Ollama)
./scripts/ollama/start-ollama.sh        # Start Ollama container
./scripts/ollama/stop-ollama.sh         # Stop Ollama container

# Diagnostics
./scripts/diagnostics/monitor-db.sh     # Real-time database monitoring
./scripts/diagnostics/list-tables.sh    # List database tables/schemas
./scripts/diagnostics/explain-query.sh  # Query performance analysis
./scripts/diagnostics/lint_queries.py   # Query safety linter (CI)

# Administration
./scripts/admin/set-admin-password.sh   # Set/update admin password
./scripts/admin/reset-password.sh       # Reset any user password

# Utilities
./scripts/tools/graph_to_mermaid.py     # Export graph to Mermaid diagrams

# System teardown
./scripts/teardown/teardown.sh          # Complete system teardown
```

## Automation Flags

Most scripts support automation flags for CI/CD:

```bash
./scripts/services/start-database.sh -y         # Skip confirmation
./scripts/database/backup-database.sh -y        # Auto-confirm backup
./scripts/setup/initialize-auth.sh --dev        # Development mode (Password1!)
```

## Script Organization Principles

### setup/
**Purpose:** One-time or infrequent configuration tasks
- Initial authentication setup
- Database performance tuning
- AI provider configuration (legacy)

**When to use:** First-time setup or major configuration changes

### database/
**Purpose:** PostgreSQL + Apache AGE database lifecycle
- Start/stop database container
- Schema migrations (migrate-db.sh runs automatically during start-database.sh)
- Backup/restore operations

**All database operations** (except diagnostics) go here

**Migration workflow:**
- Initial setup: `start-database.sh` automatically applies all pending migrations
- After adding new migrations: Run `migrate-db.sh` manually or restart database

### services/
**Purpose:** Application-level services
- API server (FastAPI)
- Visualization server
- Future: containerized services

**Note:** stop-api.sh and stop-viz.sh are placeholders until services are containerized

### ollama/
**Purpose:** Local AI inference with Ollama (Docker)
- Start/stop Ollama container
- Separate from services/ because it's infrastructure, not application

### diagnostics/
**Purpose:** Monitoring, debugging, and analysis tools
- Real-time monitoring
- Schema inspection
- Query performance analysis
- CI linters

**Read-only operations** that help understand system state

### admin/
**Purpose:** User and security management
- Password management
- User administration

**Security-sensitive operations** separate from general setup

### tools/
**Purpose:** Utility scripts for data export, conversion, etc.
- Graph visualization exports
- Data transformation utilities

**One-off utilities** that don't fit other categories

### teardown/
**Purpose:** System cleanup and removal
- Complete system teardown
- Destructive operations

**Dangerous operations** isolated for safety

## Migration from Flat Structure

**Old paths** → **New paths:**

```bash
./scripts/start-database.sh     → ./scripts/services/start-database.sh
./scripts/stop-database.sh      → ./scripts/services/stop-database.sh
./scripts/start-api.sh          → ./scripts/services/start-api.sh
./scripts/migrate-db.sh         → ./scripts/database/migrate-db.sh
./scripts/backup-database.sh    → ./scripts/database/backup-database.sh
./scripts/restore-database.sh   → ./scripts/database/restore-database.sh
./scripts/initialize-auth.sh    → ./scripts/setup/initialize-auth.sh
./scripts/configure-ai.sh       → ./scripts/setup/configure-ai.sh
./scripts/start-ollama.sh       → ./scripts/ollama/start-ollama.sh
./scripts/stop-ollama.sh        → ./scripts/ollama/stop-ollama.sh
./scripts/monitor-db.sh         → ./scripts/diagnostics/monitor-db.sh
./scripts/list-tables.sh        → ./scripts/diagnostics/list-tables.sh
```

## Adding New Scripts

When creating a new script, place it in the appropriate directory:

1. **Setup** - One-time configuration tasks
2. **Database** - PostgreSQL/AGE lifecycle operations
3. **Services** - Application service management
4. **Ollama** - Local AI infrastructure
5. **Diagnostics** - Monitoring and debugging (read-only)
6. **Admin** - User and security management
7. **Tools** - Data utilities and exports
8. **Teardown** - Destructive cleanup operations

**Template for new scripts:**

```bash
#!/bin/bash
# ============================================================================
# Script Name
# ============================================================================
# Brief description of what this script does
# ============================================================================

set -e

# Colors for output
BOLD="\033[1m"
GREEN="\033[0;32m"
BLUE="\033[0;34m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
NC="\033[0m" # No Color

# Project root (adjust based on depth in scripts/)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Your script logic here
```

## Cross-References

Scripts may reference other scripts using relative paths from project root:

```bash
# From scripts/services/start-database.sh
"$PROJECT_ROOT/scripts/database/migrate-db.sh" -y

# From scripts/setup/initialize-auth.sh
echo "Next: ./scripts/services/start-api.sh"
```

## Documentation

After modifying scripts, update:
- `docs/guides/COLD-START.md` - Getting started guide
- `docs/guides/DEPLOYMENT.md` - Production deployment
- `docs/manual/` - User manual references
- `CLAUDE.md` - Development guide
- `README.md` - Main project documentation

---

**Last Updated:** 2025-11-02
