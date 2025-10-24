# Edge Vocabulary Consolidation Guide

## Overview

Edge vocabulary consolidation uses AI-in-the-loop (AITL) evaluation to intelligently merge synonymous relationship types in your knowledge graph. As your graph grows through document ingestion, the system automatically creates new relationship types (e.g., `IMPLEMENTS`, `ENABLES`, `RELATED_TO`). Over time, this can lead to vocabulary fragmentation where semantically equivalent types coexist.

This guide covers **version 1.0** of the vocabulary consolidation feature - an autonomous AITL workflow that fully trusts LLM decisions to distinguish true synonyms from directional inverses.

## Why Consolidation Matters

### The Vocabulary Growth Problem

During document ingestion, the LLM creates relationship types to describe connections between concepts. With diverse document sets (especially software development, technical documentation, or multi-domain ontologies), vocabulary can grow rapidly:

**Example vocabulary growth:**
```
Initial: 30 builtin types (DEFINES, CONTAINS, etc.)
After 50 documents: 120 total types (30 builtin + 90 custom)
After 100 documents: 200+ types (vocabulary explosion)
```

### Symptoms of Vocabulary Fragmentation

**Redundant types:**
- `RELATED_TO`, `LINKED_TO`, `ASSOCIATED_WITH` (generic connections)
- `REFERENCES`, `REFERS_TO`, `CITES` (citation relationships)
- `IMPLEMENTS`, `REALIZES`, `EXECUTES` (implementation semantics)

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
- Too many relationship choices slow down LLM reasoning
- Subtle distinctions without semantic value
- Inconsistent type usage across documents

### When Consolidation Helps

✅ **Good candidates for consolidation:**
- **Generic relationship types** with high semantic overlap
- **Low-usage types** (< 20 edges) that are variants of common types
- **Post-ingestion cleanup** after ingesting diverse document sets
- **Vocabulary in "MIXED" or "TOO_LARGE" zones** (> 90 types)

❌ **When NOT to consolidate:**
- **Domain-specific precision matters** - Keep `VERIFIED_BY` ≠ `TESTED_BY` ≠ `REVIEWED_BY` in software dev
- **Directional distinctions are meaningful** - `PART_OF` ≠ `HAS_PART` (inverse relationships)
- **Small, curated vocabularies** (< 50 types) that are already coherent
- **During active ingestion** - Let vocabulary stabilize first

## How AITL Consolidation Works

### Three Decision Categories

The AITL workflow uses an LLM to categorize relationship pairs:

1. **✓ Merge** - True synonyms with no semantic distinction
   - Example: `RELATED_TO` + `LINKED_TO` → `ASSOCIATED_WITH`
   - Action: Automatically execute merge, update all edges

2. **✗ Reject** - Directional inverses or meaningful distinctions
   - Example: `VERIFIED_BY` + `VERIFIES` (opposite directions)
   - Example: `PART_OF` + `HAS_PART` (compositional inverses)
   - Action: Skip and remember (don't re-present)

3. **No "needs review" category** - AITL trusts LLM completely
   - Unlike future HITL (human-in-the-loop) mode
   - Either merge or reject - no middle ground

### Process Flow

**Dry-run mode** (validation, no execution):
```
1. Get top 10 synonym candidates (embedding similarity ≥ 80%)
2. Ask LLM: "Are these true synonyms or directional inverses?"
3. Categorize: Would merge / Would reject
4. Display results (no database changes)
```

**Live mode** (autonomous execution):
```
1. Get current vocabulary size
2. While vocabulary_size > target_size:
   a. Find top synonym candidate (fresh query each iteration)
   b. Skip if already processed this session (prevents duplicates)
   c. Ask LLM: "Should these merge?"
   d. If YES → Execute merge immediately, update edges
   e. If NO → Mark as rejected, skip
   f. Re-query vocabulary (landscape has changed)
3. Stop when target reached or no more candidates
```

### Why One-at-a-Time Processing?

**Problem with batch processing:**
```
Batch 1: LLM suggests merging A→B and C→B
Execute both merges
Result: Contradictory state if B should have been merged elsewhere
```

**Solution: Sequential with re-query:**
```
Iteration 1: Merge A→B (execute, vocabulary changes)
Iteration 2: Re-query finds C+B pair (fresh context)
Iteration 3: LLM now sees B in current state, makes informed decision
```

This prevents race conditions and contradictory recommendations.

### Session-Based Duplicate Prevention

**Tracks processed pairs during the session:**
```python
processed_pairs = {
    frozenset(['VERIFIED_BY', 'VERIFIES']),      # Rejected in iteration 2
    frozenset(['RELATED_TO', 'ASSOCIATED_WITH']), # Merged in iteration 3
}
```

**Prevents:**
- Re-presenting rejected pairs after re-query
- Infinite loops where same pair keeps appearing
- Wasted LLM calls evaluating the same decision

## Usage

### Check Vocabulary Status

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
  Zone: MIXED
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

**Zone interpretations:**
- `OPTIMAL` (30-90) - Vocabulary is well-managed
- `MIXED` (90-120) - Consider consolidation
- `TOO_LARGE` (120-200) - Consolidation recommended
- `CRITICAL` (200+) - Urgent consolidation needed

### Dry-Run Mode (Validation)

**Evaluate top candidates without executing:**
```bash
kg vocab consolidate --dry-run --target 75 --threshold 0.90
```

**Parameters:**
- `--dry-run` - Evaluate top 10 candidates, no execution
- `--target 75` - Target vocabulary size (used only in live mode)
- `--threshold 0.90` - **DEPRECATED** (AITL trusts LLM completely)

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

**Use dry-run to:**
- Preview what would be merged
- Verify LLM correctly identifies directional inverses
- Understand vocabulary redundancy patterns
- Validate before committing to live mode

### Live Mode (Autonomous Consolidation)

**Execute consolidation with target size:**
```bash
kg vocab consolidate --auto --target 75
```

**Parameters:**
- `--auto` - Enable live mode (required for execution)
- `--target 75` - Stop when vocabulary reaches this size (default: 90)
- `--threshold 0.90` - **DEPRECATED** (no longer used in AITL)

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

**What happened:**
- 8 iterations (5 merges + 3 rejects)
- 82 total edges updated across all merges
- LLM correctly distinguished synonyms from inverses
- Reached target size (75) and stopped

### Generate Embeddings

**If vocabulary types lack embeddings (older databases):**
```bash
kg vocab generate-embeddings
```

This is a one-time operation. The consolidation workflow requires embeddings for similarity detection.

## Parameters Explained

### `--target <size>`

**Controls when consolidation stops:**
```bash
kg vocab consolidate --auto --target 75
```

**Guidance:**
- **Conservative** (80-90): Keep most distinctions
- **Moderate** (70-80): Balance precision vs. simplicity
- **Aggressive** (50-70): Maximize consolidation
- **Minimal** (30-50): Only essential types remain

**Choose based on domain:**
- **Software development**: 70-90 (rich relationship semantics)
- **General knowledge**: 50-70 (fewer precise distinctions)
- **Single-domain ontologies**: 40-60 (coherent vocabulary)
- **Multi-domain graphs**: 80-100 (preserve cross-domain nuance)

### `--threshold <0.0-1.0>` ⚠️ DEPRECATED

**In version 1.0, this parameter is ignored.**

**Why deprecated:**
- Original design: auto-execute if similarity ≥ threshold, otherwise "needs review"
- AITL mode: Fully trust LLM decisions regardless of similarity score
- LLM evaluates semantic equivalence, not just embedding similarity
- Similarity used only for candidate prioritization, not execution decisions

**Future versions may reintroduce this for HITL mode** (human-in-the-loop) where threshold determines when to ask for human approval.

### `--dry-run`

**Validation mode - no execution:**
```bash
kg vocab consolidate --dry-run --target 75
```

**Behavior:**
- Evaluates top 10 candidates only (not iterative)
- Shows what would be merged/rejected
- No database changes
- No target size enforcement (since nothing executes)

**Use for:**
- Understanding vocabulary redundancy patterns
- Verifying LLM distinguishes inverses correctly
- Planning consolidation strategy
- Documenting vocabulary decisions

### `--auto`

**Enables live execution mode:**
```bash
kg vocab consolidate --auto --target 75
```

**Without `--auto`:**
- Defaults to dry-run validation mode
- No execution occurs

**With `--auto`:**
- Iterative consolidation until target reached
- Real database changes
- Edge updates committed immediately
- Cannot be undone (no rollback)

**Safety:**
- Always run `--dry-run` first to preview
- Backup database before aggressive consolidation
- Test with higher target sizes first (e.g., 85 before 75)

## Best Practices

### Pre-Consolidation Checklist

**Before running live consolidation:**

1. **Check current state:**
   ```bash
   kg vocab status
   ```

2. **Run dry-run validation:**
   ```bash
   kg vocab consolidate --dry-run --target 75
   ```

3. **Review LLM decisions:**
   - Are rejected pairs actually inverses? ✓
   - Are merged pairs truly synonymous? ✓
   - Any domain-specific distinctions being lost? ✗

4. **Backup database (optional but recommended):**
   ```bash
   # Export current graph state
   kg ontology export "MyOntology" > backup.json
   ```

5. **Start conservative:**
   ```bash
   # First run: modest target
   kg vocab consolidate --auto --target 85

   # If results look good, go further
   kg vocab consolidate --auto --target 75
   ```

### Domain-Specific Guidance

**Software Development / Technical Docs:**
```bash
# Rich relationship semantics - keep distinctions
kg vocab consolidate --auto --target 80

# KEEP distinct: IMPLEMENTS, REFERENCES, DEPENDS_ON, TESTED_BY, VERIFIED_BY
# MERGE generic: RELATED_TO → ASSOCIATED_WITH
```

**Why:** Code relationships have precise meanings. `IMPLEMENTS` ≠ `REFERENCES` ≠ `MENTIONS`.

**General Knowledge / Research:**
```bash
# Broader consolidation acceptable
kg vocab consolidate --auto --target 65

# MERGE: Many generic connection types
# KEEP: Domain-specific relationships
```

**Why:** Research documents use more generic relationship language with fewer technical distinctions.

**Multi-Domain Ontologies:**
```bash
# Preserve cross-domain nuance
kg vocab consolidate --auto --target 90

# Risk: Same term means different things in different domains
# Example: "SPRINT" in software (iteration) vs. athletics (race)
```

**Why:** Cross-domain vocabularies need flexibility to represent diverse semantic spaces.

### Iterative Consolidation Strategy

**Don't over-consolidate in one pass:**

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

**Stop if:**
- Queries return unexpected results
- Domain-specific relationships being lost
- Vocabulary zone reaches OPTIMAL (30-90)

### Monitoring Consolidation Impact

**After consolidation, verify graph coherence:**

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

## What the LLM Evaluates

### LLM Prompt Summary

**For each candidate pair, the LLM considers:**

1. **Semantic equivalence** - Do they mean the same thing in practice?
2. **Directional inverses** - Are they opposite directions (e.g., `PART_OF` vs `HAS_PART`)?
3. **Useful distinctions** - Would merging lose important nuance?
4. **Graph consistency** - Would a unified term improve clarity?

**LLM returns:**
```json
{
  "should_merge": true,
  "reasoning": "Both types represent generic association with no semantic distinction.",
  "blended_term": "ASSOCIATED_WITH",
  "blended_description": "A generic relationship indicating conceptual association."
}
```

**If `should_merge: false`:**
```json
{
  "should_merge": false,
  "reasoning": "VERIFIED_BY and VERIFIES are directional inverses representing opposite directions of verification."
}
```

### Confidence in LLM Decisions

**AITL mode assumes:**
- LLM can distinguish synonyms from inverses (generally accurate)
- Semantic similarity from embeddings + LLM reasoning = good decisions
- Human review not required for routine vocabulary cleanup

**Limitations (version 1.0):**
- No human approval workflow yet
- Cannot manually override LLM decisions mid-session
- No interactive mode to review before each merge

**Future enhancements (HITL mode):**
- Human approval for medium-confidence decisions
- Interactive CLI prompts: "Merge A → B? [y/n/skip]"
- Web UI for batch review of recommendations

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
- Lower your target if you want to force more consolidation (not recommended)

### High similarity pairs rejected

**Symptom:**
```
✗ CREATED_BY + CREATED_AT
   Similarity: 91.2%
   Reasoning: CREATED_BY indicates creator, CREATED_AT indicates timestamp.
```

**Explanation:** Embedding similarity detects lexical similarity, but LLM understands semantic differences.

**This is correct behavior** - trust the LLM's semantic reasoning over raw similarity scores.

### Same pair appearing multiple times (historical bug - fixed)

**In version 1.0, this should not occur.**

If you see duplicate evaluations:
```
✗ VERIFIED_BY + VERIFIES
✗ VERIFIED_BY + VERIFIES  (duplicate)
```

**Report this as a bug** - session-based tracking should prevent this.

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

2. **Manual split (not yet implemented):**
   - Future feature: `kg vocab split MERGED_TYPE --into TYPE1 TYPE2`
   - Current workaround: Manually update edge types in database

3. **Adjust target for future runs:**
   ```bash
   # Don't push target so low
   kg vocab consolidate --auto --target 90  # More conservative
   ```

4. **Domain-specific LLM tuning (future):**
   - Provide domain context in prompts
   - Use domain-specific evaluation criteria

### Cannot undo consolidation

**Current limitation:** No rollback mechanism in version 1.0.

**Workarounds:**

1. **Before consolidation:**
   ```bash
   # Export ontology
   kg ontology export "YourOntology" > backup.json
   ```

2. **Manual edge type updates:**
   ```cypher
   // Update edges back to original type (openCypher query)
   MATCH ()-[r:MERGED_TYPE]->()
   WHERE r.original_type = 'ORIGINAL_TYPE'
   // Note: Requires tracking original types (not implemented yet)
   ```

3. **Database restore:**
   ```bash
   # Full PostgreSQL backup/restore
   docker exec knowledge-graph-postgres pg_dump -U admin knowledge_graph > backup.sql
   ```

## Technical Details

### Candidate Prioritization

**How candidates are ranked:**

```python
priority = (similarity * 2) - (min_edge_count / 100)
```

**Favors:**
- High embedding similarity (80%+ cosine similarity)
- Low-usage types (< 20 edges) - safer to merge
- Balance between similarity confidence and impact

**Example:**
```
Candidate: RELATED_TO (2 edges) + LINKED_TO (5 edges)
Similarity: 0.887 (88.7%)
Priority: (0.887 * 2) - (2 / 100) = 1.774 - 0.02 = 1.754

Candidate: VERIFIED_BY (50 edges) + VERIFIES (48 edges)
Similarity: 0.923 (92.3%)
Priority: (0.923 * 2) - (48 / 100) = 1.846 - 0.48 = 1.366
```

First candidate is prioritized despite lower similarity (safer merge with fewer edges).

### Embedding Generation

**Vocabulary types need embeddings for similarity detection:**

```python
# Each relationship type gets an embedding
text = relationship_type  # e.g., "IMPLEMENTS"
embedding = openai.embeddings.create(
    model="text-embedding-3-small",
    input=text
).data[0].embedding  # 1536 dimensions
```

**Stored in:** `kg_api.relationship_vocabulary.embedding`

**Generated:**
- Automatically during vocabulary expansion (ADR-025)
- Manually via `kg vocab generate-embeddings`

### Merge Operation

**What happens during a merge:**

1. **Update all edges:**
   ```cypher
   MATCH (c1:Concept)-[r:DEPRECATED_TYPE]->(c2:Concept)
   CREATE (c1)-[new_r:TARGET_TYPE]->(c2)
   SET new_r = properties(r)
   DELETE r
   ```

2. **Mark deprecated type inactive:**
   ```sql
   UPDATE kg_api.relationship_vocabulary
   SET is_active = false,
       merged_into = 'TARGET_TYPE',
       performed_by = 'aitl_consolidation'
   WHERE relationship_type = 'DEPRECATED_TYPE'
   ```

3. **Return edge count:**
   ```python
   {
       'deprecated': 'RELATED_TO',
       'target': 'ASSOCIATED_WITH',
       'edges_updated': 42
   }
   ```

## Version 1.0 Limitations

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

## Related Documentation

- [ADR-032: Automatic Edge Vocabulary Expansion](../../architecture/ADR-032-automatic-edge-vocabulary-expansion.md) - Architecture decision for vocabulary management
- [ADR-025: Dynamic Relationship Vocabulary](../../architecture/ADR-025-dynamic-relationship-vocabulary.md) - Original vocabulary expansion design
- [CLI Usage Guide](../01-getting-started/02-CLI_USAGE.md) - Full CLI command reference
- [Schema Reference](../06-reference/01-SCHEMA_REFERENCE.md) - Database schema for relationship vocabulary

## Getting Help

**If consolidation produces unexpected results:**

1. Share your consolidation output (merged/rejected pairs)
2. Describe your domain (software dev, research, general knowledge)
3. Report specific incorrect merges
4. Suggest improvements to LLM evaluation criteria

**Known limitations in version 1.0:**
- Cannot manually override LLM decisions
- No rollback mechanism
- No interactive approval workflow

These will be addressed in future HITL mode implementations.
