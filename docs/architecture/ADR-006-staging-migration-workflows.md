# ADR-006: Staging and Migration Workflows

**Status:** Proposed
**Date:** 2025-10-08
**Deciders:** System Architecture
**Related:** ADR-001 (Multi-Tier Access)

## Context

Directly ingesting experimental content or untested agent contributions into a production knowledge graph creates risk of data corruption or quality degradation. Users need a safe environment to test ingestion strategies, experiment with new concepts, and validate quality before promoting knowledge to production.

## Decision

Use separate Neo4j databases for staging/production/archive with CLI tools for selective migration. This provides a safe experimental environment with controlled promotion workflow.

### Database Structure

```
Neo4j Instance:
├── graph_staging        # Experimental ingestion, agent testing
├── graph_production     # Curated, validated knowledge
└── graph_archive        # Historical versions, backups
```

### Migration Workflow

**1. Ingest to Staging:**
```bash
# Ingest with staging flag
./scripts/ingest.sh document.md --name "New Doc" --target staging

# Or via MCP (contributor role)
create_concept({...}, target_graph="staging")
```

**2. Review in Staging:**
```bash
# CLI queries against staging
python cli.py --graph staging search "topic"
python cli.py --graph staging stats

# Web UI shows staging vs production toggle
```

**3. Quality Check:**
```python
# Automated librarian review
def assess_staging_quality():
    # Check for orphans, duplicates, low confidence
    issues = find_quality_issues(graph="staging")

    if issues:
        flag_for_manual_review(issues)
    else:
        approve_for_promotion()
```

**4. Promote to Production:**
```bash
# CLI migration tool - selective promotion
python cli.py migrate \
  --from staging \
  --to production \
  --concepts concept_101,concept_102,concept_103 \
  --include-relationships \
  --include-instances

# Or full graph merge
python cli.py migrate \
  --from staging \
  --to production \
  --merge-all \
  --deduplicate
```

**5. Archive Old Versions:**
```bash
# Before major updates, snapshot production
python cli.py snapshot \
  --from production \
  --to archive \
  --tag "pre-migration-2025-10-04"
```

### Migration Operations

**Copy (Non-destructive):**
```cypher
// Copy concept cluster to production
CALL apoc.graph.fromCypher(
  "MATCH (c:Concept) WHERE c.concept_id IN $ids
   MATCH (c)-[r*0..2]-(related)
   RETURN c, r, related",
  {ids: $concept_ids},
  {target: 'graph_production'}
)
```

**Move (Destructive in source):**
```cypher
// Move approved concepts
MATCH (c:Concept) WHERE c.approved = true
CALL apoc.refactor.cloneSubgraphFromPaths([c], {target: 'graph_production'})
WITH c
DETACH DELETE c  // Remove from staging
```

**Merge (Deduplicate):**
```python
def merge_graphs(source: str, target: str):
    # Find duplicates across graphs
    duplicates = find_cross_graph_duplicates(source, target)

    for src_concept, tgt_concept in duplicates:
        # Merge relationships into target
        merge_concepts(
            from_graph=source,
            to_graph=target,
            from_id=src_concept,
            to_id=tgt_concept
        )
```

### Rollback Capability

```bash
# Restore from archive
python cli.py restore \
  --from archive \
  --snapshot "pre-migration-2025-10-04" \
  --to production \
  --confirm

# Partial rollback (remove recent additions)
python cli.py rollback \
  --concepts-created-after "2025-10-04T14:00:00Z" \
  --graph production \
  --dry-run  # Preview first
```

## Consequences

### Positive
- Safe experimentation without polluting production graph
- Gradual promotion of validated knowledge only
- Rollback capability for mistakes or quality issues
- Archive provides complete audit trail
- Supports A/B testing of different ingestion strategies
- Clear separation between experimental and trusted knowledge

### Negative
- Requires managing multiple Neo4j databases (storage overhead)
- Migration operations can be complex for heavily connected subgraphs
- Need clear policies on when to promote vs. discard staging content
- Cross-graph queries more complex than single-graph queries

### Neutral
- Staging database may accumulate experimental data over time (periodic cleanup needed)
- Archive strategy needed (how long to keep, what to snapshot)
- Migration tools need testing to ensure data integrity
