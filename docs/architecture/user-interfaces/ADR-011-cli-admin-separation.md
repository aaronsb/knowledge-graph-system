---
status: Accepted
date: 2025-10-08
deciders:
  - Development Team
related:
  - ADR-012
  - ADR-016
---

# ADR-011: CLI and Admin Tooling Separation

## Overview

When software grows organically, everything tends to end up in one place. Our knowledge graph system started with a single `cli.py` file that did everything—searching concepts, backing up databases, restoring data, and managing configurations. While this worked initially, it created a tangled mess where adding new features meant navigating an increasingly complex monolith.

The real problem wasn't just messy code. We had shell scripts duplicating Python logic, no shared libraries for common operations, and backup processes that didn't properly save expensive vector embeddings. If you lost your database, you'd have to re-process all your documents through the AI models again—potentially costing $50-100 in API fees for large document collections.

This ADR establishes a clean separation: query tools for exploring data go in the CLI layer, administrative tools for managing the database go in the admin layer, and shared functionality lives in reusable libraries. The result is a codebase that's easier to extend, properly backs up all your data (including those expensive embeddings), and provides a foundation for future interfaces like web UIs.

---

## Context

The original implementation mixed query operations (search, concept details) and administrative operations (backup, restore, database setup) in a single `cli.py` file. Shell scripts duplicated logic from Python code. No shared library existed for common operations like console output, JSON formatting, or graph database queries. This made it difficult to add new interfaces (GUI, web) without duplicating functionality.

Additionally, backup/restore operations didn't handle vector embeddings properly, risking expensive re-ingestion costs ($50-100 for large documents) if data was lost.

## Decision

Restructure codebase into three layers with shared libraries:

1. **Shared Libraries (`src/lib/`)** - Reusable components
2. **CLI Tools (`src/cli/`)** - Data query and exploration
3. **Admin Tools (`src/admin/`)** - Database administration

### Proposed Directory Structure

```
knowledge-graph-system/
├── src/
│   ├── lib/                      # Shared libraries
│   │   ├── __init__.py
│   │   ├── console.py            # Color output, formatting, progress bars
│   │   ├── age_ops.py            # Common Apache AGE operations (was neo4j_ops.py)
│   │   ├── serialization.py      # Export/import with embeddings
│   │   └── config.py             # Configuration management
│   │
│   ├── cli/                      # Query & exploration tools (HTTP API client)
│   │   ├── __init__.py
│   │   ├── main.py               # CLI entry point
│   │   ├── search.py             # Search commands
│   │   ├── concept.py            # Concept operations
│   │   ├── ontology.py           # Ontology inspection
│   │   └── database.py           # Database info/health (read-only)
│   │
│   ├── admin/                    # Administration tools (direct database)
│   │   ├── __init__.py
│   │   ├── backup.py             # Backup operations
│   │   ├── restore.py            # Restore operations
│   │   ├── reset.py              # Database reset
│   │   ├── prune.py              # Prune orphaned nodes
│   │   └── stitch.py             # Semantic restitching
│   │
│   └── api/                      # API server (replaces ingest/)
│       ├── main.py               # FastAPI application
│       ├── lib/age_client.py     # AGE database client
│       └── ...
│
├── scripts/                      # Thin shell wrappers
│   ├── backup.sh                 # Calls src/admin/backup.py
│   ├── restore.sh                # Calls src/admin/restore.py
│   └── ...
│
├── cli.py -> src/cli/main.py     # Symlink for backward compat
└── ...
```

### Implementation Strategy

**Phase 1: Create shared libraries**
```python
# src/lib/console.py
class Console:
    @staticmethod
    def success(msg): print(f"\033[92m{msg}\033[0m")
    @staticmethod
    def error(msg): print(f"\033[91m{msg}\033[0m")
    # ... progress bars, tables, etc.

# src/lib/serialization.py
def export_ontology(ontology_name: str) -> Dict:
    """Export ontology with all data including embeddings"""
    return {
        "metadata": {...},
        "concepts": [...],  # Including embeddings as lists
        "sources": [...],
        "instances": [...],
        "relationships": [...]
    }
```

**Phase 2: Implement admin tools**
```python
# src/admin/backup.py
from src.lib.console import Console
from src.lib.serialization import export_ontology

def backup_ontology(name: str, output_file: str):
    Console.info(f"Backing up ontology: {name}")
    data = export_ontology(name)
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)
    Console.success(f"Backup saved: {output_file}")
```

**Phase 3: Refactor CLI**
- Move query operations to `src/cli/`
- Remove admin operations from current `cli.py`
- Use shared libraries for output

**Phase 4: Update shell scripts**
```bash
# scripts/backup.sh
source venv/bin/activate
python -m src.admin.backup "$@"
```

### Data Format for Backups

**JSON format with explicit types:**
```json
{
  "version": "1.0",
  "type": "ontology_backup",
  "timestamp": "2025-10-06T14:30:00Z",
  "ontology": "My Ontology",
  "metadata": {
    "file_count": 3,
    "concept_count": 109,
    "source_count": 24
  },
  "concepts": [
    {
      "concept_id": "concept_001",
      "label": "Linear Thinking",
      "search_terms": ["linear", "sequential", "step-by-step"],
      "embedding": [0.234, -0.123, 0.456, ...]  // Full array
    }
  ],
  "sources": [
    {
      "source_id": "doc1_chunk1",
      "document": "My Ontology",
      "file_path": "/path/to/file.md",
      "paragraph": 1,
      "full_text": "..."
    }
  ],
  "relationships": [
    {
      "from": "concept_001",
      "to": "concept_002",
      "type": "IMPLIES",
      "properties": {"confidence": 0.9}
    }
  ]
}
```

## Consequences

### Positive

1. **Separation of Concerns**
   - CLI focused on data access
   - Admin focused on database operations
   - Clear boundaries

2. **Reusability**
   - Shared libraries avoid duplication
   - Easy to add new interfaces (web UI, API)
   - Testable modules

3. **Portability**
   - Backups include all data (embeddings, full text, relationships)
   - JSON format is portable across systems
   - Mix-and-match restore (selective ontology restore)

4. **Cost Protection**
   - Save expensive ingestion results ($50-100 for large documents)
   - Restore into clean database without re-processing
   - Share ontologies between team members

5. **Future-Proof**
   - GUI can import same modules
   - API server can use same libraries
   - Unit tests for all components

### Negative

- More files/directories (but better organized)
- Need to update imports in existing code
- Slight learning curve for new contributors

### Neutral

- Need to maintain backward compatibility during transition
- Documentation updates required

## Alternatives Considered

1. **Keep everything in cli.py** - Rejected: becomes unmaintainable kitchen sink
2. **Separate repos for admin tools** - Rejected: overkill, makes shared code difficult
3. **Bash-only for admin** - Rejected: can't handle embeddings properly, lots of duplication

## Migration Path

1. **Backward Compatibility**
   - Keep `cli.py` as symlink to `src/cli/main.py`
   - Shell scripts continue to work
   - Gradual migration of calling code

2. **Incremental**
   - Can implement admin tools first
   - CLI refactor can follow
   - No "big bang" rewrite

3. **Testing**
   - Test each component independently
   - Integration tests for workflows
   - Backup/restore round-trip tests
