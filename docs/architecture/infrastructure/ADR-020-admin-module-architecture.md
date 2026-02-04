---
status: Accepted
date: 2025-10-09
deciders:
  - Development Team
related:
  - ADR-015
  - ADR-016
---

# ADR-020: Admin Module Architecture Pattern

## Overview

Every system needs administrative operations - resetting databases, creating backups, checking system health. Early on, developers often reach for shell scripts because they're quick to write: `reset.sh`, `backup.sh`, `configure.sh`. But these scripts become a maintenance nightmare. They're hard to test, impossible to reuse in other contexts, and when something goes wrong, debugging is a mess of exit codes and stderr output.

We hit this wall when migrating from Neo4j to PostgreSQL. Our `reset.sh` script was still trying to restart Neo4j containers that didn't exist anymore. The error messages were confusing, the script sometimes succeeded but returned failure codes, and we couldn't easily call this logic from our API or CLI. It was like having important business logic written in bash instead of your main programming language - it works, but it's isolated and brittle.

The solution moves all admin operations into proper Python modules. Each major operation (reset, backup, restore) gets its own focused module that can be called from anywhere - CLI, API, tests, or even directly via Python REPL. The service layer becomes a thin wrapper that just delegates to these modules. This is like refactoring a messy script into a well-organized library: same functionality, but now it's testable, reusable, and maintainable.

---

## Context

As the knowledge graph system evolved, administrative operations grew in complexity:

1. **Shell Script Proliferation**: Initial implementation used shell scripts (`scripts/reset.sh`, `scripts/configure-ai.sh`) that were hard to maintain and test
2. **Service Layer Bloat**: `admin_service.py` was accumulating complex logic for backup, restore, reset, and status operations
3. **Code Duplication**: Same operations needed from CLI, API, and potentially future interfaces
4. **Testing Challenges**: Shell scripts mixed with Python made testing difficult
5. **Database Migration**: Migration from Neo4j to Apache AGE (ADR-016) broke `reset.sh` which still referenced Neo4j containers

### The Breaking Point

The `kg admin reset` command was failing with 500 errors despite actually working:
- Old `reset.sh` referenced Neo4j containers (`knowledge-graph-neo4j`) instead of PostgreSQL (`knowledge-graph-postgres`)
- Script exit codes were unreliable (non-zero even on success)
- Docker-compose output to stderr triggered error detection
- 60+ second execution with no progress feedback
- Service layer was trying to manage subprocess execution inline

## Decision

We adopt a **modular admin architecture** where each major admin operation gets its own Python module in `src/admin/`:

### Architecture Pattern

```
src/admin/
├── __init__.py
├── backup.py          # Database backup operations
├── restore.py         # Database restore operations
├── reset.py           # Database reset operations (NEW)
├── check_integrity.py # Backup validation
├── prune.py           # Cleanup operations
└── stitch.py          # Cross-ontology reconnection

api/app/services/
└── admin_service.py   # Thin delegation layer
```

### Module Responsibilities

Each admin module:
1. **Implements Core Logic**: Complete operation logic in Python (no shell scripts)
2. **Dual Interface**: Supports both CLI and programmatic use
3. **Interactive + Non-Interactive**: Menu-driven for CLI, auto-confirm for API/automation
4. **Self-Contained**: Uses `subprocess` for Docker/system commands, not dependent on shell scripts
5. **Structured Results**: Returns typed dictionaries with success/error/validation data

### Service Layer Delegation

`admin_service.py` becomes a thin async wrapper:
```python
async def reset_database(self, ...) -> ResetResponse:
    """Reset database - Delegates to reset module"""
    from ...admin.reset import ResetManager

    manager = ResetManager(project_root=self.project_root)
    result = await loop.run_in_executor(None, manager.reset, ...)

    if not result["success"]:
        raise RuntimeError(result["error"])

    return ResetResponse(...)
```

**Benefits:**
- Service layer: ~30 lines (was ~120 lines)
- Async execution via thread pool (modules use sync subprocess)
- Clear error propagation
- Easy to test and mock

### CLI Direct Access

Users can run modules directly:
```bash
# Via API (through kg CLI)
kg admin reset

# Via direct module execution
python -m src.admin.reset
python -m src.admin.backup --auto-full
python -m src.admin.restore --file backup.json
```

## Consequences

### Positive

1. **Eliminated Shell Scripts**: `scripts/reset.sh` removed; pure Python implementation
2. **Code Reuse**: Same logic serves CLI, API, and future interfaces
3. **Better Testing**: Python modules easier to unit test than shell scripts
4. **Consistent Patterns**: All admin operations follow same structure
5. **Improved Error Handling**: Structured error results instead of shell exit codes
6. **Progress Feedback**: Modules can provide verbose output for interactive use
7. **Type Safety**: Return types are documented and validated
8. **Service Layer Simplicity**: Each service method ~20-30 lines of delegation

### Negative

1. **More Files**: Each operation gets its own module (acceptable trade-off)
2. **Import Overhead**: Dynamic imports in service layer (minimal performance impact)
3. **Subprocess Complexity**: Still uses subprocess for Docker commands (no pure-Python alternative)

### Migration Path

**Candidates for Modularization:**
- `scripts/configure-ai.sh` → `src/admin/config_ai.py`
- `scripts/setup.sh` → `src/admin/setup.py`
- System shutdown logic → `src/admin/shutdown.py`

**Keep as Scripts:**
- `scripts/start-api.sh` (simple process launcher)
- `docker-compose.yml` (infrastructure definition)

## Implementation Details

### Reset Module Structure

`src/admin/reset.py` (~360 lines):

```python
class ResetManager:
    """Database reset manager"""

    def run_interactive(self):
        """Interactive menu with confirmations"""
        # Show warnings
        # Confirm destructive action
        # Execute reset with verbose output

    def reset(self, clear_logs, clear_checkpoints, verbose) -> Dict:
        """Execute reset operation"""
        # 1. Stop PostgreSQL container (docker-compose down -v)
        # 2. Remove volumes explicitly
        # 3. Start fresh container (docker-compose up -d)
        # 4. Wait for PostgreSQL ready (30 attempts @ 2s)
        # 5. Initialize schema (init_age.sql)
        # 6. Clear log files (optional)
        # 7. Clear checkpoints (optional)
        # 8. Verify schema
        # Return: {success, validation, error}

    def _verify_schema(self) -> Dict:
        """Verify schema correctness"""
        # Check graph exists
        # Check tables created
        # Check node count (should be 0)
        # Test create/delete concept
        # Return: {graph_exists, table_count, node_count, schema_test_passed}
```

### Service Integration

```python
# Before (120 lines of subprocess management)
async def reset_database(self, ...):
    proc = await asyncio.create_subprocess_exec(...)
    stdout, stderr = await proc.communicate(...)
    if proc.returncode != 0:
        raise RuntimeError(...)
    # ... 100+ more lines of inline logic

# After (30 lines of delegation)
async def reset_database(self, ...):
    from ...admin.reset import ResetManager
    manager = ResetManager(project_root=self.project_root)
    result = await loop.run_in_executor(None, manager.reset, ...)
    if not result["success"]:
        raise RuntimeError(result["error"])
    return ResetResponse(...)
```

## Validation

### Before Fix
```
→ POST /admin/reset
← POST /admin/reset - 500 (61.111s)
Error: Reset failed: [docker-compose output]
Database: Actually reset (data gone, schema initialized)
```

### After Fix
```
→ POST /admin/reset
← POST /admin/reset - 200 (13.048s)
Database: Reset successfully
Schema validation: ✓ graph_exists, ✓ schema_test_passed
```

**Improvements:**
- ✅ Returns 200 (not 500)
- ✅ 13s execution (was 61s)
- ✅ Proper error handling
- ✅ Schema validation included
- ✅ No shell script dependency

## Future Considerations

### Planned Modules

1. **config_ai.py**: Replace `scripts/configure-ai.sh`
   - Test API keys
   - Configure providers (OpenAI, Anthropic)
   - Model selection
   - Cost estimation

2. **setup.py**: Replace `scripts/setup.sh`
   - Create venv
   - Install dependencies
   - Verify PostgreSQL
   - Initialize database

3. **shutdown.py**: Graceful system shutdown
   - Stop API server
   - Stop PostgreSQL
   - Save state
   - Cleanup resources

### API Evolution

As modules are added, `admin_service.py` remains thin:
```python
async def configure_ai(self, provider, model):
    from ...admin.config_ai import AIConfigurator
    configurator = AIConfigurator()
    return await loop.run_in_executor(None, configurator.configure, ...)
```

## References

- **ADR-015**: Backup/Restore Streaming - Established pattern for admin modules
- **ADR-016**: Apache AGE Migration - Required reset.sh replacement
- Code: `src/admin/reset.py` (new)
- Code: `src/admin/backup.py` (existing pattern)
- Code: `src/admin/restore.py` (existing pattern)
- Code: `api/app/services/admin_service.py` (simplified)

## Decision Outcome

**Accepted** - The modular admin architecture successfully:
- Eliminated brittle shell script dependency
- Fixed the `kg admin reset` 500 error bug
- Reduced service layer complexity
- Enabled code reuse across interfaces
- Improved testability and maintainability

This pattern will be applied to future admin operations as shell scripts are phased out in favor of pure Python implementations.
