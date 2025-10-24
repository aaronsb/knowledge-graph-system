# 13 - Managing Relationship Vocabulary

**Part:** II - Configuration
**Reading Time:** ~20 minutes
**Prerequisites:** [Section 04 - Understanding Concepts and Relationships](04-understanding-concepts-and-relationships.md), [Section 06 - Querying Your Knowledge Graph](06-querying-your-knowledge-graph.md)

---

This section explains how to manage relationship vocabulary - the set of relationship types (like `IMPLIES`, `SUPPORTS`, `CONTRADICTS`) used to connect concepts in your knowledge graph. The system starts with 30 builtin types and automatically expands vocabulary during document ingestion. This guide shows you how to monitor, consolidate, and curate relationship types.

## What Is Relationship Vocabulary

Every edge connecting two concepts has a type:

```cypher
(:Concept {label: "Authentication"})-[:REQUIRES]->(:Concept {label: "Encryption"})
(:Concept {label: "Linear Thinking"})-[:CONTRADICTS]->(:Concept {label: "Parallel Processing"})
(:Concept {label: "Microservices"})-[:PART_OF]->(:Concept {label: "Distributed Architecture"})
```

The relationship types (`REQUIRES`, `CONTRADICTS`, `PART_OF`) form your vocabulary. A well-managed vocabulary:

- **Captures semantics** - Relationship types convey meaning (`IMPLEMENTS` vs `REFERENCES` vs `MENTIONS`)
- **Enables precise queries** - Find all concepts that `CAUSES` failures vs all that `SUPPORTS` reliability
- **Guides extraction** - The LLM chooses from available relationship types during ingestion
- **Maintains consistency** - Synonymous types merged (`AUTHORED_BY` → `CREATED_BY`)

## How Vocabulary Grows

### Initial Builtin Types

The system starts with 30 core relationship types organized into 8 semantic categories:

**Logical Truth:**
- `IMPLIES`, `CONTRADICTS`, `PRESUPPOSES`, `EQUIVALENT_TO`

**Causal:**
- `CAUSES`, `ENABLES`, `PREVENTS`, `INFLUENCES`, `RESULTS_FROM`

**Structural:**
- `PART_OF`, `CONTAINS`, `COMPOSED_OF`, `SUBSET_OF`, `INSTANCE_OF`

**Evidential:**
- `SUPPORTS`, `REFUTES`, `EXEMPLIFIES`, `MEASURED_BY`

**Similarity:**
- `SIMILAR_TO`, `ANALOGOUS_TO`, `CONTRASTS_WITH`, `OPPOSITE_OF`

**Temporal:**
- `PRECEDES`, `CONCURRENT_WITH`, `EVOLVES_INTO`

**Functional:**
- `USED_FOR`, `REQUIRES`, `PRODUCES`, `REGULATES`

**Meta:**
- `DEFINED_AS`, `CATEGORIZED_AS`

These 30 types are protected - never automatically deleted.

### Automatic Expansion

During document ingestion, the LLM may identify relationships that don't fit existing types. The system automatically adds new types:

**Example: Machine Learning Documents**

Ingesting ML research papers might create:
- `TRAINS_ON` - model trains on dataset
- `OPTIMIZES` - technique optimizes metric
- `OUTPERFORMS` - model A outperforms model B
- `PRETRAINED_ON` - transfer learning relationships

**Example: Software Development**

Ingesting code documentation might create:
- `IMPLEMENTS` - class implements interface
- `TESTED_BY` - feature tested by test suite
- `VERIFIED_BY` - security verified by audit
- `DEPLOYS_TO` - service deploys to environment

These domain-specific types emerge naturally from your documents.

### Vocabulary Size Zones

The system tracks vocabulary size and operates in different zones:

```
30        60        75        85  90                200
├─────────┼─────────┼─────────┼───┼─────────────────┤
│ OPTIMAL │  WATCH  │  MERGE  │MIX│   EMERGENCY     │
│  (30)   │         │         │   │                 │
```

**Zone meanings:**
- **OPTIMAL** (30-90 types) - Healthy vocabulary, no action needed
- **MIXED** (90-120 types) - Consider consolidation
- **TOO_LARGE** (120-200 types) - Consolidation recommended
- **CRITICAL** (200+ types) - Urgent consolidation needed

## Checking Vocabulary Status

View current vocabulary state:

```bash
kg vocab status
```

**Example output:**

```
────────────────────────────────────────────────────────────────────────────────
📚 Vocabulary Status
────────────────────────────────────────────────────────────────────────────────

Current State
  Vocabulary Size: 80
  Zone: OPTIMAL
  Aggressiveness: 77.5%
  Profile: aggressive

Thresholds
  Minimum: 30
  Maximum: 90
  Emergency: 200

Edge Types
  Builtin: 28
  Custom: 52
  Categories: 11
```

This shows:
- **80 active types** (within optimal range)
- **28 builtin types** used
- **52 custom types** added automatically
- **11 categories** (8 builtin + 3 custom)

## The Vocabulary Growth Problem

As you ingest diverse documents, vocabulary can fragment:

**Redundant types:**
```
RELATED_TO, LINKED_TO, ASSOCIATED_WITH, CONNECTED_TO
REFERENCES, REFERS_TO, CITES, MENTIONS
IMPLEMENTS, REALIZES, EXECUTES
```

These are semantically similar but treated as distinct types.

**Query complexity:**

```cypher
// Without consolidation - must check all variants
MATCH (c1:Concept)-[r]->(c2:Concept)
WHERE type(r) IN ['RELATED_TO', 'LINKED_TO', 'ASSOCIATED_WITH', 'CONNECTED_TO']
RETURN c1, c2

// After consolidation - single unified type
MATCH (c1:Concept)-[:ASSOCIATED_WITH]->(c2:Concept)
RETURN c1, c2
```

**Agent confusion:**

Too many relationship choices slow down LLM reasoning during extraction. The LLM sees 150+ types and struggles to pick the most appropriate one.

## Vocabulary Consolidation

Consolidation uses AI-in-the-loop (AITL) evaluation to intelligently merge synonymous relationship types.

### How AITL Consolidation Works

The system uses an LLM to categorize relationship pairs:

**1. Merge** - True synonyms with no semantic distinction
- Example: `RELATED_TO` + `LINKED_TO` → `ASSOCIATED_WITH`
- Action: Automatically execute merge, update all edges

**2. Reject** - Directional inverses or meaningful distinctions
- Example: `VERIFIED_BY` + `VERIFIES` (opposite directions)
- Example: `PART_OF` + `HAS_PART` (compositional inverses)
- Action: Skip and remember (don't re-present)

The AITL workflow trusts LLM decisions completely (no human approval required for individual merges).

### Dry-Run Mode (Validation)

Evaluate top candidates without executing:

```bash
kg vocab consolidate --dry-run --target 75
```

**Parameters:**
- `--dry-run` - Evaluate top 10 candidates, no execution
- `--target 75` - Target vocabulary size (for reference)

**Example output:**

```
📊 Consolidation Results
────────────────────────────────────────────────────────────────────────────────

Summary
  Initial Size: 80
  Final Size: 80 (no changes in dry-run)
  Merged: 7 (would merge)
  Rejected: 3 (would reject)

Would Merge:
────────────────────────────────────────────────────────────────────────────────

✓ RELATED_TO → ASSOCIATED_WITH
   Similarity: 88.7%
   Reasoning: Both types are semantically equivalent generic relationship indicators.

✓ LINKED_TO → ASSOCIATED_WITH
   Similarity: 85.9%
   Reasoning: High similarity with no directional distinction.

Rejected Merges:
────────────────────────────────────────────────────────────────────────────────

✗ VERIFIED_BY + VERIFIES
   Reasoning: Directional inverses representing opposite verification relationships.

✗ PART_OF + HAS_PART
   Reasoning: Compositional inverses with opposite semantic directions.
```

Use dry-run to:
- Preview what would be merged
- Verify LLM correctly identifies directional inverses
- Understand vocabulary redundancy patterns
- Validate before committing to live mode

### Live Mode (Autonomous Consolidation)

Execute consolidation with target size:

```bash
kg vocab consolidate --auto --target 75
```

**Parameters:**
- `--auto` - Enable live mode (required for execution)
- `--target 75` - Stop when vocabulary reaches this size (default: 90)

**Example output:**

```
🔄 Vocabulary Consolidation
────────────────────────────────────────────────────────────────────────────────

Mode: AUTO (AITL - auto-execute)
Target Size: 75
Running LLM-based consolidation workflow...

📊 Consolidation Results
────────────────────────────────────────────────────────────────────────────────

Summary
  Initial Size: 80
  Final Size: 75
  Reduction: -5
  Merged: 5
  Rejected: 3

Auto-Executed Merges
────────────────────────────────────────────────────────────────────────────────

✓ RELATED_TO → ASSOCIATED_WITH
   Similarity: 88.7%
   Reasoning: Both types have no current usage and high embedding similarity.
   Edges Updated: 42

✓ LINKED_TO → ASSOCIATED_WITH
   Similarity: 85.9%
   Reasoning: High similarity with no useful distinction.
   Edges Updated: 29

✓ REFERENCED_BY → MENTIONS_REFERENCED_BY
   Similarity: 83.7%
   Reasoning: Both represent the same practical meaning.
   Edges Updated: 8

✓ REFERS_TO → DEFINES_OR_REFERS_TO
   Similarity: 83.5%
   Reasoning: Semantically equivalent with no loss of nuance.
   Edges Updated: 3

✓ IMPLEMENTS → IMPLEMENTS
   Similarity: 87.2%
   Reasoning: Variant spellings of the same relationship type.
   Edges Updated: 0

Rejected Merges
────────────────────────────────────────────────────────────────────────────────

✗ VERIFIED_BY + VERIFIES
   Reasoning: Directional inverses representing opposite directions.

✗ HAS_PART + PART_OF
   Reasoning: Compositional inverses with opposite semantic meaning.

✗ ENABLED_BY + ENABLES
   Reasoning: Directional inverses - ENABLED_BY indicates enabler, ENABLES indicates beneficiary.

────────────────────────────────────────────────────────────────────────────────
✓ Consolidation completed: 5 types reduced (80 → 75)
```

What happened:
- 8 iterations (5 merges + 3 rejects)
- 82 total edges updated across all merges
- LLM correctly distinguished synonyms from inverses
- Reached target size (75) and stopped

## Choosing Target Size

### Conservative (80-90)

Keep most distinctions:

```bash
kg vocab consolidate --auto --target 85
```

**Good for:**
- Software development (rich relationship semantics)
- Technical documentation (precise distinctions matter)
- Multi-domain ontologies (preserve cross-domain nuance)

**Example:** Keep `IMPLEMENTS` ≠ `REFERENCES` ≠ `TESTED_BY` ≠ `VERIFIED_BY` distinct.

### Moderate (70-80)

Balance precision vs. simplicity:

```bash
kg vocab consolidate --auto --target 75
```

**Good for:**
- General knowledge graphs
- Research paper collections
- Mixed content domains

### Aggressive (50-70)

Maximize consolidation:

```bash
kg vocab consolidate --auto --target 65
```

**Good for:**
- Single-domain ontologies (coherent vocabulary)
- General research (fewer precise distinctions needed)
- Personal knowledge management (simplicity over nuance)

### Minimal (30-50)

Only essential types remain:

```bash
kg vocab consolidate --auto --target 40
```

**Use carefully:** May lose important domain-specific relationships.

## Workflow Examples

### Initial Cleanup After Bulk Ingestion

After ingesting 100+ documents from diverse sources:

```bash
# Step 1: Check status
kg vocab status

# Output shows 120 types (TOO_LARGE zone)

# Step 2: Run dry-run to preview
kg vocab consolidate --dry-run --target 85

# Step 3: Review output, verify LLM decisions look correct

# Step 4: Execute consolidation
kg vocab consolidate --auto --target 85

# Step 5: Verify results
kg vocab status
```

### Iterative Consolidation

Don't over-consolidate in one pass:

```bash
# Pass 1: Remove obvious redundancy
kg vocab consolidate --auto --target 85
kg vocab status  # Check results

# Pass 2: Moderate consolidation if Pass 1 looked good
kg vocab consolidate --auto --target 75
kg vocab status

# Pass 3: Query graph to verify relationship coherence
kg search query "software architecture"
# Do results still make sense?
```

Stop if:
- Queries return unexpected results
- Domain-specific relationships being lost
- Vocabulary zone reaches OPTIMAL (30-90)

### Domain-Specific Guidance

**Software Development / Technical Docs:**

```bash
# Rich relationship semantics - keep distinctions
kg vocab consolidate --auto --target 80

# KEEP distinct: IMPLEMENTS, REFERENCES, DEPENDS_ON, TESTED_BY, VERIFIED_BY
# MERGE generic: RELATED_TO → ASSOCIATED_WITH
```

Code relationships have precise meanings. `IMPLEMENTS` ≠ `REFERENCES` ≠ `MENTIONS`.

**General Knowledge / Research:**

```bash
# Broader consolidation acceptable
kg vocab consolidate --auto --target 65

# MERGE: Many generic connection types
# KEEP: Domain-specific relationships
```

Research documents use more generic relationship language with fewer technical distinctions.

**Multi-Domain Ontologies:**

```bash
# Preserve cross-domain nuance
kg vocab consolidate --auto --target 90

# Risk: Same term means different things in different domains
```

Cross-domain vocabularies need flexibility to represent diverse semantic spaces.

## Viewing Vocabulary

### List All Types

```bash
kg vocab list
```

Shows all active relationship types with usage statistics.

### View History

```bash
kg vocab history
```

**Example output:**

```
┌────────────────────────────────────────────────────────────┐
│ Vocabulary Change History                                  │
├────────────────────────────────────────────────────────────┤
│ 2025-10-15 14:32 CREATES                                  │
│   Action: Pruned (0 edges)                                │
│   Reason: Never used                                      │
│                                                            │
│ 2025-10-14 03:15 AUTHORED_BY → CREATED_BY                │
│   Action: Merged (27 edges updated)                       │
│   Reason: 94% semantic similarity                         │
│                                                            │
│ 2025-10-13 19:45 OPTIMIZES                                │
│   Action: Added (domain: ML)                              │
│   Source: Automatic expansion                             │
└────────────────────────────────────────────────────────────┘
```

This shows:
- Pruned types (deleted, 0 edges)
- Merged types (source → target, edge count)
- Added types (automatic expansion)

### View Categories

```bash
kg vocab categories list
```

**Example output:**

```
┌────────────────┬───────────────┬─────────────────┐
│ Category       │ Edge Types    │ Total Edges     │
├────────────────┼───────────────┼─────────────────┤
│ causal         │ 5 builtin     │ 1,247 edges     │
│                │ 3 custom      │                 │
├────────────────┼───────────────┼─────────────────┤
│ structural     │ 5 builtin     │ 892 edges       │
│                │ 1 custom      │                 │
├────────────────┼───────────────┼─────────────────┤
│ ml_specific    │ 0 builtin     │ 34 edges (NEW)  │
│                │ 3 custom      │                 │
└────────────────┴───────────────┴─────────────────┘
```

Categories organize relationship types into high-level semantic groups.

## Troubleshooting

### "No more candidates available" but not at target

**Symptom:**

```
📊 Consolidation Results
Summary
  Initial Size: 85
  Final Size: 82
  Reduction: -3

No more unprocessed candidates available
```

**Cause:** All remaining synonym candidates were rejected by LLM (e.g., all directional inverses).

**Solution:**
- This is expected behavior - not all vocabularies can reach aggressive targets
- Your domain may legitimately need 80+ types
- Accept current size or raise limit if vocabulary is functioning well

### High similarity pairs rejected

**Symptom:**

```
✗ CREATED_BY + CREATED_AT
   Similarity: 91.2%
   Reasoning: CREATED_BY indicates creator, CREATED_AT indicates timestamp.
```

**Explanation:** Embedding similarity detects lexical similarity, but LLM understands semantic differences.

**This is correct behavior** - trust the LLM's semantic reasoning over raw similarity scores.

### Consolidation too aggressive

**Symptom:** Domain-specific relationships being merged incorrectly.

**Examples:**
- `IMPLEMENTS` merged with `REFERENCES` (wrong - implementation ≠ reference)
- `TESTED_BY` merged with `VERIFIED_BY` (wrong in software contexts)

**Solutions:**

1. **Stop and assess:**
   ```bash
   kg vocab status  # Check current state
   ```

2. **Adjust target for future runs:**
   ```bash
   # Don't push target so low
   kg vocab consolidate --auto --target 90  # More conservative
   ```

3. **Accept limitations:**
   - Version 1.0 has no rollback mechanism
   - Future versions will support splitting merged types
   - Learn from this run and adjust targets

### Vector Search Returns Wrong Results After Consolidation

**Symptom:** Search results don't make sense after consolidation.

**Cause:** This is actually rare - consolidation only affects relationship types, not concept embeddings.

**Verify:**

```bash
# Test semantic search (should work normally)
kg search query "authentication security"

# Check if relationships still make sense
kg search details <concept-id>
```

If relationships look wrong, you may have over-consolidated domain-specific types.

## Best Practices

### Always Use Dry-Run First

Never run live consolidation without previewing:

```bash
# Step 1: Dry-run to preview
kg vocab consolidate --dry-run --target 75

# Step 2: Review output carefully

# Step 3: Execute if results look reasonable
kg vocab consolidate --auto --target 75
```

### Test with Conservative Targets First

```bash
# First run: modest target
kg vocab consolidate --auto --target 85

# If results look good, go further
kg vocab consolidate --auto --target 75
```

Don't jump straight to aggressive targets (40-50) without testing.

### Monitor After Consolidation

After consolidation, verify graph coherence:

```bash
# Check relationship diversity
kg vocab status

# Query concepts to see if relationships still make sense
kg search query "your domain keywords"

# Check specific merged types
kg vocab list | grep ASSOCIATED_WITH
```

**Red flags:**
- Too many edges collapsed into single generic type (e.g., 200+ edges → `ASSOCIATED_WITH`)
- Domain queries returning irrelevant connections
- Loss of semantic precision in critical relationships

### Document Your Decisions

Track consolidation runs and results:

```bash
# Before consolidation
kg vocab status > vocab_status_before.txt

# Run consolidation
kg vocab consolidate --auto --target 75 > consolidation_results.txt

# After consolidation
kg vocab status > vocab_status_after.txt

# View history
kg vocab history > vocab_history.txt
```

This helps you understand vocabulary evolution over time.

### Don't Delete Default Types

The default 30 builtin types are protected for good reason. Keep them for rollback purposes and semantic consistency.

### Consolidate Periodically, Not Continuously

**Good schedule:**
- After major ingestion batches (100+ documents)
- Monthly maintenance for active graphs
- When vocabulary reaches MIXED zone (90-120 types)

**Avoid:**
- Consolidating after every ingestion
- Consolidating in OPTIMAL zone (30-90)
- Multiple consolidation runs per day

## When to Consolidate

### Consolidate When:

✅ Vocabulary size > 90 types (MIXED or TOO_LARGE zone)
✅ After ingesting diverse document sets
✅ Generic types proliferating (`RELATED_TO`, `LINKED_TO`, `CONNECTED_TO`)
✅ Query complexity increasing (too many relationship variants)
✅ LLM extraction slowing down (too many type choices)

### Don't Consolidate When:

❌ Vocabulary < 60 types (comfort zone)
❌ Domain-specific precision matters (software dev, technical docs)
❌ During active ingestion (let vocabulary stabilize first)
❌ Right after consolidation (give it time to settle)
❌ If domain queries are working well (if not broken, don't fix)

## Configuration

### Embedding Generation

Consolidation requires embeddings for similarity detection.

If vocabulary types lack embeddings (older databases):

```bash
kg vocab generate-embeddings
```

This is a one-time operation. New types automatically get embeddings during expansion.

### Adjust Limits (Advanced)

The default limits (30 min, 90 max, 200 emergency) work well for most use cases.

If you need to adjust (rare):

```bash
# View current config
kg vocab config show

# Adjust limits (admin only)
kg vocab config set --min 30 --max 100 --emergency 250
```

**Only adjust if:**
- You have a very large multi-domain ontology (increase max to 100-120)
- You want stricter vocabulary control (decrease max to 70-80)

## What Consolidation Does

### Merge Operation

When merging `SOURCE_TYPE` into `TARGET_TYPE`:

**1. Update all edges:**
```cypher
MATCH ()-[r:SOURCE_TYPE]->()
CREATE ()-[new_r:TARGET_TYPE]->()
SET new_r = properties(r)
DELETE r
```

**2. Mark source type inactive:**
```sql
UPDATE kg_api.relationship_vocabulary
SET is_active = false,
    merged_into = 'TARGET_TYPE',
    performed_by = 'aitl_consolidation'
WHERE relationship_type = 'SOURCE_TYPE'
```

**3. Preserve history:**
```sql
INSERT INTO kg_api.vocabulary_history
  (relationship_type, action, merge_target, edges_updated, ...)
VALUES
  ('SOURCE_TYPE', 'merged', 'TARGET_TYPE', 42, ...)
```

### What Consolidation Preserves

✓ **All edges** - No data loss, just type changes
✓ **Edge properties** - Confidence scores, metadata preserved
✓ **Concept connections** - Graph structure unchanged
✓ **Evidence** - Source quotes and instances intact
✓ **History** - Complete audit trail of changes

### What Consolidation Changes

- **Relationship type names** - Deprecated type → target type
- **Query syntax** - Use merged type name in queries
- **Vocabulary size** - Reduced by number of merges
- **Type statistics** - Usage counts consolidated

## Real-World Example

### Scenario: Software Development Ontology

**Starting state:**

```bash
kg vocab status

Vocabulary Size: 120
Zone: TOO_LARGE
Custom Types: 92
```

**Consolidation run:**

```bash
# Step 1: Validate
kg vocab consolidate --dry-run --target 85

# Review output:
# - Would merge 15 pairs (generic types)
# - Would reject 8 pairs (directional inverses)
# - Looks reasonable

# Step 2: Execute
kg vocab consolidate --auto --target 85

# Results:
# Initial: 120
# Final: 102
# Merged: 18
# Rejected: 12
# Edges updated: 234
```

**Key merges:**

```
RELATED_TO → ASSOCIATED_WITH (42 edges)
LINKED_TO → ASSOCIATED_WITH (29 edges)
REFERENCES → MENTIONS (18 edges)
CITES → MENTIONS (12 edges)
APPLIES_TO → RELEVANT_TO (8 edges)
```

**Key rejects (preserved distinctions):**

```
IMPLEMENTS ≠ REFERENCES (implementation vs mention)
TESTED_BY ≠ VERIFIED_BY (testing vs verification)
DEPENDS_ON ≠ REQUIRES (dependency vs requirement)
PART_OF ≠ HAS_PART (directional inverse)
```

**Post-consolidation:**

```bash
kg vocab status

Vocabulary Size: 102
Zone: MIXED
Custom Types: 74

# Still above optimal, run again
kg vocab consolidate --auto --target 90

# Final state:
Vocabulary Size: 90
Zone: OPTIMAL
Custom Types: 62
```

**Impact on queries:**

```cypher
// Before: Must check 5 variants
MATCH (c1:Concept)-[r]->(c2:Concept)
WHERE type(r) IN ['RELATED_TO', 'LINKED_TO', 'ASSOCIATED_WITH', 'CONNECTED_TO', 'TIES_TO']
RETURN c1, c2

// After: Single unified type
MATCH (c1:Concept)-[:ASSOCIATED_WITH]->(c2:Concept)
RETURN c1, c2
```

Simpler queries, preserved domain-specific types (`IMPLEMENTS`, `TESTED_BY`, `VERIFIED_BY`).

## Limitations (Version 1.0)

**Current implementation:**
- ✅ Fully autonomous AITL workflow
- ✅ Distinguishes synonyms from directional inverses
- ✅ Session-based duplicate prevention
- ✅ One-at-a-time processing with re-query
- ❌ No human-in-the-loop (HITL) approval workflow
- ❌ No interactive CLI prompts
- ❌ No rollback/undo mechanism
- ❌ No manual override of LLM decisions
- ❌ No domain-specific evaluation tuning

**Future roadmap:**

**Version 2.0 (HITL mode):**
- Interactive approval: "Merge A → B? [y/n/skip]"
- Threshold-based human review (< 85% similarity)
- Batch review UI for pending decisions
- Session persistence across CLI sessions

**Version 3.0 (Advanced features):**
- Rollback mechanism: `kg vocab rollback <session-id>`
- Domain context injection in LLM prompts
- Split merged types: `kg vocab split MERGED --into A B`
- Dry-run with specific pair: `kg vocab evaluate TYPE1 TYPE2`

## What's Next

Now that you understand vocabulary management, you can:

- **[Section 14 - Advanced Query Patterns](14-advanced-query-patterns.md)**: Complex graph queries
- **[Section 15 - Integration with Claude Desktop (MCP)](15-integration-with-claude-desktop-mcp.md)**: Use the graph with Claude

For technical details:
- **Architecture:** [ADR-032 - Automatic Edge Vocabulary Expansion](architecture/ADR-032-automatic-edge-vocabulary-expansion.md)
- **Vocabulary Guide:** [guides/VOCABULARY_CONSOLIDATION.md](guides/VOCABULARY_CONSOLIDATION.md)

---

← [Previous: Local LLM Inference with Ollama](12-local-llm-inference-with-ollama.md) | [Documentation Index](README.md) | [Next: Advanced Query Patterns →](14-advanced-query-patterns.md)
