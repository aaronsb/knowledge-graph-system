# Backup and Restore Guide

## Overview

The Knowledge Graph System provides comprehensive backup and restore functionality with **integrity checking** to protect against **torn ontological fabric** - the phenomenon where partial backups/restores create dangling references and orphaned concepts.

## Quick Start

```bash
# Full database backup
./scripts/backup.sh

# Ontology-specific backup
python -m src.admin.backup --ontology "My Ontology"

# Restore from backup
./scripts/restore.sh

# Check database integrity
python -m src.admin.check_integrity
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
python -m src.admin.backup --ontology "Ontology A"

# Delete entire database
./scripts/reset.sh

# Restore Ontology A
python -m src.admin.restore --file backups/ontology_a.json
```

**Result:** Concept X now has a dangling `IMPLIES` relationship pointing to non-existent Concept Y.

### Scenario 2: Shared Concepts

**Setup:**
- Concept X appears in BOTH Ontology A and Ontology B
- Concept X has different instances/evidence in each ontology

**Problem:**
```bash
# Backup Ontology A
python -m src.admin.backup --ontology "Ontology A"

# Delete Ontology A
python cli.py --yes ontology delete "Ontology A"

# Restore Ontology A
python -m src.admin.restore --file backups/ontology_a.json
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
python -m src.admin.backup --ontology "Ontology 1"

# Restore into clean database
# Concept A is restored, but its IMPLIES relationship to B is dangling
```

**Result:** Logical implication chain is broken. Queries traversing relationships will fail.

## Integrity Checking

### Before Backup: Assessment

When backing up an ontology, the system **analyzes cross-ontology dependencies**:

```bash
python -m src.admin.backup --ontology "Ontology A"
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
python -m src.admin.restore --file backups/ontology_a.json
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
  • 0 orphaned concepts (no APPEARS_IN relationship)

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
python -m src.admin.check_integrity

# Check specific ontology
python -m src.admin.check_integrity --ontology "My Ontology"

# Auto-repair orphaned concepts
python -m src.admin.check_integrity --repair
```

## Restore Strategies

### Strategy 1: Full Database Backup/Restore

**Safest approach** - no torn fabric:

```bash
# Backup entire database
python -m src.admin.backup --auto-full

# Restore entire database
python -m src.admin.restore --file backups/full_backup_20251006.json
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
python -m src.admin.backup --ontology "Ontology A"

# Backup Ontology B (which A references)
python -m src.admin.backup --ontology "Ontology B"

# Restore both
python -m src.admin.restore --file backups/ontology_a.json
python -m src.admin.restore --file backups/ontology_b.json
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
python -m src.admin.restore --file backups/ontology_a.json

# System offers repair:
# "Attempt automatic repair? [Y/n]: y"

# Or manually repair later:
python -m src.admin.check_integrity --ontology "Ontology A" --repair
```

**What gets repaired:**
- Orphaned concepts → APPEARS_IN relationships recreated
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
   ./scripts/ingest.sh large_document.txt --name "Expensive Ontology"
   # Cost: $75 in tokens

   # Cheap: Backup immediately
   python -m src.admin.backup --ontology "Expensive Ontology"
   # Cost: $0

   # Cheap: Restore anytime
   python -m src.admin.restore --file backups/expensive_ontology.json
   # Cost: $0
   ```

2. **Share ontologies between team members**
   ```bash
   # Team member A ingests
   ./scripts/ingest.sh document.txt --name "Shared Knowledge"
   python -m src.admin.backup --ontology "Shared Knowledge"

   # Send backup file to team member B
   scp backups/ontology_shared_knowledge.json teammate@remote:/path/

   # Team member B restores (no re-ingestion needed)
   python -m src.admin.restore --file ontology_shared_knowledge.json
   ```

3. **Experiment safely**
   ```bash
   # Backup before experiments
   python -m src.admin.backup --ontology "Production Data"

   # Run risky experiments
   python cli.py ontology delete "Production Data"
   # Try different ingestion parameters

   # Restore if experiment fails
   python -m src.admin.restore --file backups/production_data.json
   ```

## Best Practices

### 1. Backup Before Major Changes

```bash
# Before deleting ontologies
python -m src.admin.backup --auto-full

# Before schema migrations
python -m src.admin.backup --auto-full

# Before experiments
python -m src.admin.backup --ontology "Ontology Name"
```

### 2. Check Integrity After Restore

**Always** validate after partial restore:

```bash
python -m src.admin.check_integrity --ontology "Restored Ontology"
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
NEO4J_URI=bolt://localhost:7688 python -m src.admin.restore \
  --file backups/production.json

# Verify integrity
NEO4J_URI=bolt://localhost:7688 python -m src.admin.check_integrity

# If ok, restore to production
python -m src.admin.restore --file backups/production.json
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

**Cause:** APPEARS_IN relationships weren't created during restore.

**Solution:**
```bash
python -m src.admin.check_integrity --ontology "My Ontology" --repair
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
3. Use database-level backup (Neo4j native tools)

## See Also

- [ADR-011: Separation of CLI and Admin Tooling](ARCHITECTURE_DECISIONS.md#adr-011)
- [Architecture Overview](ARCHITECTURE.md)
- [Quickstart Guide](QUICKSTART.md)
