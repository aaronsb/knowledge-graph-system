# Backup and Restore Guide

## Overview

The Knowledge Graph System provides comprehensive backup and restore functionality with **integrity checking** to protect against **torn ontological fabric** - the phenomenon where partial backups/restores create dangling references and orphaned concepts.

Backups are created and restored via the `kg admin` CLI (which talks to the API, ADR-036). For pure SQL dumps of the underlying PostgreSQL, see `operator/database/backup-database.sh` and `operator/database/restore-database.sh`.

## Quick Start

```bash
# Interactive backup (choose full or per-ontology)
kg admin backup

# Full database backup, non-interactive
kg admin backup --type full

# Ontology-specific backup
kg admin backup --type ontology --ontology "My Ontology"

# List available backups (configured backup directory)
kg admin list-backups

# Restore from backup (requires admin auth; prompts for password)
kg admin restore --file <backup-file>
```

## The Problem: Torn Ontological Fabric

When backing up or restoring **partial ontologies**, you risk creating integrity issues:

### Scenario 1: Cross-Ontology Relationships

**Setup:**
- Ontology A has Concept X
- Ontology B has Concept Y
- Concept X has relationship `IMPLIES` to Concept Y

**Problem:**
```bash
# Backup only Ontology A
kg admin backup --type ontology --ontology "Ontology A"

# Delete entire database
kg admin reset

# Restore Ontology A
kg admin restore --file ontology_a.json
```

**Result:** Concept X now has a dangling `IMPLIES` relationship pointing to non-existent Concept Y.

### Scenario 2: Shared Concepts

**Setup:**
- Concept X appears in BOTH Ontology A and Ontology B
- Concept X has different instances/evidence in each ontology

**Problem:**
```bash
# Backup Ontology A
kg admin backup --type ontology --ontology "Ontology A"

# Delete Ontology A
kg ontology delete "Ontology A" --force

# Restore Ontology A
kg admin restore --file ontology_a.json
```

**Result:** Concept X loses all connections to Ontology B sources. The concept's evidence from Ontology B is severed.

### Scenario 3: Incomplete Dependency Chain

**Setup:**
- Concept A `IMPLIES` Concept B
- Concept B `IMPLIES` Concept C
- Concept A is in Ontology 1
- Concepts B and C are in Ontology 2

**Problem:**
```bash
# Backup Ontology 1 only
kg admin backup --type ontology --ontology "Ontology 1"

# Restore into clean database
# Concept A is restored, but its IMPLIES relationship to B is dangling
```

**Result:** Logical implication chain is broken. Queries traversing relationships will fail.

## Integrity Checking

### Before Backup: Assessment

When backing up an ontology, the system **analyzes cross-ontology dependencies**:

```bash
kg admin backup --type ontology --ontology "Ontology A"
```

**Output:**
```
Backup Assessment
═════════════════
Backup Type: ontology_backup
Ontology: Ontology A

Contents:
  Concepts: 22
  Sources: 4
  Instances: 25
  Relationships: 14

Relationship Integrity:
  Internal: 10/14
  External: 4/14
  External %: 28.6%

Warnings:
  • 4/14 (28.6%) relationships point to external concepts
  • Found relationships pointing to 3 external concepts not included in this backup

External Dependencies:
  • 3 external concepts referenced

⚠ Restoring this backup may create dangling references!
  Consider one of these strategies:
    1. Restore into database that already has these dependencies
    2. Use --prune-external to skip external relationships
    3. Backup dependent ontologies together
```

### After Restore: Validation

After restoring, the system **validates integrity**:

```bash
kg admin restore --file ontology_a.json
```

**Output:**
```
Restore Complete
═══════════════
✓ Data restored successfully
  Concepts: 22
  Sources: 4
  Instances: 25
  Relationships: 14

Validating database integrity...

Database Integrity Check
════════════════════════
Ontology: Ontology A

✗ Critical Issues:
  • 0 orphaned concepts (no APPEARS relationship)

⚠ Warnings:
  • 4 relationships to concepts in other ontologies

  Cross-ontology relationships by type:
    - IMPLIES
    - SUPPORTS

💡 Recommendations:
  • Cross-ontology relationships are normal, but be aware when deleting ontologies
  • Deleting ontologies may orphan concepts referenced by other ontologies

⚠ Integrity issues detected after restore
Attempt automatic repair? [Y/n]:
```

### Standalone Integrity Check

```bash
# Check entire database
# Integrity is validated automatically by `kg admin restore`.

# Check specific ontology
# Integrity is validated automatically by `kg admin restore`.

# Auto-repair orphaned concepts
# Integrity repair runs as part of `kg admin restore` (use `--deps stitch|prune|defer`).
```

## Restore Strategies

### Strategy 1: Full Database Backup/Restore

**Safest approach** - no torn fabric:

```bash
# Backup entire database
kg admin backup --type full

# Restore entire database
kg admin restore --file full_backup_20251006.json
```

**Pros:**
- No dangling references
- All relationships preserved
- Complete ontological fabric

**Cons:**
- Large backup files (includes all ontologies)
- All-or-nothing restore

### Strategy 2: Ontology Groups

Backup **related ontologies together**:

```bash
# Backup Ontology A
kg admin backup --type ontology --ontology "Ontology A"

# Backup Ontology B (which A references)
kg admin backup --type ontology --ontology "Ontology B"

# Restore both
kg admin restore --file ontology_a.json
kg admin restore --file ontology_b.json
```

**Pros:**
- Smaller backups than full database
- Preserves cross-ontology relationships
- Mix-and-match restore

**Cons:**
- Must manually track dependencies
- Order matters (restore dependencies first)

### Strategy 3: Accept Torn Fabric + Repair

Restore ontology, accept warnings, and repair:

```bash
# Restore (may have dangling refs)
kg admin restore --file ontology_a.json

# System offers repair:
# "Attempt automatic repair? [Y/n]: y"

# Or manually repair later:
# Re-run `kg admin restore --file ontology_a.json` to revalidate integrity.
```

**What gets repaired:**
- Orphaned concepts → APPEARS relationships recreated
- Missing concept-source links → Derived from instances

**What doesn't get repaired:**
- External relationship targets (concepts in other ontologies)
- Cross-ontology dependencies

**Pros:**
- Flexible partial restore
- Automatic repair of common issues

**Cons:**
- External relationships remain dangling
- Manual verification needed

## Backup File Format

```json
{
  "version": "1.0",
  "type": "ontology_backup",
  "timestamp": "2025-10-06T14:30:00Z",
  "ontology": "My Ontology",
  "statistics": {
    "concepts": 22,
    "sources": 4,
    "instances": 25,
    "relationships": 14
  },
  "data": {
    "concepts": [
      {
        "concept_id": "concept_001",
        "label": "Agile Adoption",
        "search_terms": ["agile", "adoption", "transformation"],
        "embedding": [0.013, 0.048, ...] // Full 1536-dim array
      }
    ],
    "sources": [...],
    "instances": [...],
    "relationships": [
      {
        "from": "concept_001",
        "to": "concept_002",  // May be external!
        "type": "IMPLIES",
        "properties": {"confidence": 0.9}
      }
    ]
  }
}
```

**Key Points:**
- Embeddings are preserved as full arrays (1536 dimensions)
- Relationships may reference external concepts
- Full text preserved in sources
- Portable JSON format

## Cost Protection

Ingesting large documents can cost **$50-100 in LLM tokens**. Backups protect this investment:

1. **Ingest once, restore many times**
   ```bash
   # Expensive: Process 400KB document
   kg ingest file large_document.txt -o "Expensive Ontology"
   # Cost: $75 in tokens

   # Cheap: Backup immediately
   kg admin backup --type ontology --ontology "Expensive Ontology"
   # Cost: $0

   # Cheap: Restore anytime
   kg admin restore --file expensive_ontology.json
   # Cost: $0
   ```

2. **Share ontologies between team members**
   ```bash
   # Team member A ingests
   kg ingest file document.txt -o "Shared Knowledge"
   kg admin backup --type ontology --ontology "Shared Knowledge"

   # Send backup file to team member B
   scp backups/ontology_shared_knowledge.json teammate@remote:/path/

   # Team member B restores (no re-ingestion needed)
   kg admin restore --file ontology_shared_knowledge.json
   ```

3. **Experiment safely**
   ```bash
   # Backup before experiments
   kg admin backup --type ontology --ontology "Production Data"

   # Run risky experiments
   kg ontology delete "Production Data" --force
   # Try different ingestion parameters

   # Restore if experiment fails
   kg admin restore --file production_data.json
   ```

## Best Practices

### 1. Backup Before Major Changes

```bash
# Before deleting ontologies
kg admin backup --type full

# Before schema migrations
kg admin backup --type full

# Before experiments
kg admin backup --type ontology --ontology "Ontology Name"
```

### 2. Check Integrity After Restore

**Always** validate after partial restore:

```bash
# Integrity is validated automatically by `kg admin restore`.
```

### 3. Document Dependencies

Create a dependency map for your ontologies:

```
ontologies.txt:
  - "Ontology A" (standalone)
  - "Ontology B" → depends on "Ontology A"
  - "Ontology C" → depends on "Ontology A", "Ontology B"
```

When backing up "Ontology C", also backup A and B.

### 4. Test Restore in Staging

Before restoring to production:

```bash
# Restore to test database first
# Use a separate API instance (e.g. via KG_API_URL=...) to restore to staging:
KG_API_URL=http://staging:8000 kg admin restore --file production.json

# (Integrity is validated automatically by `kg admin restore`.)

# If ok, restore to production
kg admin restore --file production.json
```

### 5. Version Control Backup Files

```bash
# Add to git (if small enough)
git add backups/critical_ontology_*.json

# Or use git-lfs for large files
git lfs track "backups/*.json"
git add .gitattributes backups/
```

## Troubleshooting

### Issue: "X relationships to external concepts"

**Cause:** Ontology has relationships pointing to concepts in other ontologies.

**Solutions:**
1. Restore the other ontologies too
2. Accept dangling refs (queries will skip them)
3. Remove external relationships before backup

### Issue: "Orphaned concepts after restore"

**Cause:** APPEARS relationships weren't created during restore.

**Solution:**
```bash
# Integrity is validated automatically during `kg admin restore`. There is
# no standalone check-integrity command; rerun the restore to revalidate.
```

### Issue: "Concepts missing embeddings"

**Cause:** Backup file corrupted or created before embeddings were added.

**Solution:**
- Re-ingest from source documents
- Or regenerate embeddings using OpenAI API

### Issue: "Backup file too large"

**Cause:** Embeddings are 1536 floats per concept.

**Solutions:**
1. Compress backup files: `gzip backups/*.json`
2. Split into ontology-specific backups
3. Use PostgreSQL-level backups (e.g. `operator/database/backup-database.sh`)

## See Also

- [ADR-011: Separation of CLI and Admin Tooling](../../architecture/INDEX.md#adr-011)
- [Architecture Overview](../../reference/ARCHITECTURE_OVERVIEW.md)
- [Quickstart Guide](../01-getting-started/02-CLI_USAGE.md)
