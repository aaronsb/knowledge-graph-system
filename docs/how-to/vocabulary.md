# Consolidate Vocabulary

Edge vocabulary consolidation merges synonymous relationship types in your graph, reducing fragmentation and simplifying queries.

As documents are ingested, the LLM creates new relationship types on demand. Across diverse document sets this leads to vocabulary explosion: `RELATED_TO`, `LINKED_TO`, and `ASSOCIATED_WITH` coexist without meaningful distinction. Consolidation identifies pairs that are true synonyms — not directional inverses — and merges them, rewriting all affected edges.

## When to consolidate

Consolidation helps when:

- Vocabulary has grown past the soft limit and the zone is `merge`, `mixed`, or higher
- Queries require `WHERE type(r) IN [...]` with five or more variants
- LLM reasoning slows because too many near-identical types exist

Do not consolidate while active ingestion is running. Let the vocabulary stabilize first.

Do not consolidate when domain-specific precision matters. Keep `VERIFIED_BY`, `TESTED_BY`, and `REVIEWED_BY` distinct in software-development graphs. Keep directional pairs (`PART_OF` / `HAS_PART`) separate — they are inverses, not synonyms.

## Check vocabulary status

```bash
kg vocab status
```

Example output:

```
────────────────────────────────────────────────────────────────────────────────
Vocabulary Status
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

Zone guide:

Zones are derived from the aggressiveness level, which is computed from a Bezier curve over the vocabulary's position between `vocab_min` and `vocab_max` (both configurable). The thresholds below are defaults.

| Zone | Aggressiveness | Meaning |
|---|---|---|
| `comfort` | < 0.2 | Vocabulary is well within limits |
| `watch` | 0.2–0.5 | Growth is accelerating; monitor |
| `merge` | 0.5–0.7 | Consolidation is worth running |
| `mixed` | 0.7–0.9 | Consolidation recommended |
| `emergency` | 0.9–1.0, below hard limit | Consolidation needed soon |
| `block` | At or above `vocab_emergency` | Expansion is blocked |

## Preview candidates without making changes

```bash
kg vocab consolidate --dry-run --target 75
```

Dry-run evaluates the top 10 synonym candidates and shows what would be merged or rejected. No edges are written.

Example output:

```
Consolidation Results
────────────────────────────────────────────────────────────────────────────────

Summary
  Initial Size: 80
  Final Size: 80 (no changes in dry-run)
  Merged: 7 (would merge)
  Rejected: 3 (would reject)

Would Merge:

✓ RELATED_TO → ASSOCIATED_WITH
   Similarity: 88.7%
   Reasoning: Both types are semantically equivalent generic relationship indicators.

✓ LINKED_TO → ASSOCIATED_WITH
   Similarity: 85.9%
   Reasoning: High similarity with no directional distinction.

Rejected Merges:

✗ VERIFIED_BY + VERIFIES
   Reasoning: Directional inverses representing opposite verification relationships.

✗ PART_OF + HAS_PART
   Reasoning: Compositional inverses with opposite semantic directions.
```

Use dry-run to verify that the LLM correctly distinguishes directional inverses, and to understand which types will be targeted before committing.

## Run consolidation

```bash
kg vocab consolidate --target 75
```

Without `--dry-run`, consolidation executes immediately. The workflow iterates: find the highest-priority synonym candidate, ask the LLM whether to merge or reject, execute the merge if approved, re-query the updated vocabulary, and repeat until the vocabulary reaches `--target` or no candidates remain.

The re-query on each iteration prevents race conditions that batch processing would introduce: after `A → B` merges, the next candidate is evaluated against the current state of the vocabulary, not a stale snapshot.

Example output:

```
Vocabulary Consolidation
────────────────────────────────────────────────────────────────────────────────

Mode: EXECUTE (merge + prune)
Target Size: 75
Running LLM-based consolidation workflow...

Consolidation Results
────────────────────────────────────────────────────────────────────────────────

Summary
  Initial Size: 80
  Final Size: 75
  Reduction: -5
  Merged: 5
  Rejected: 3

Executed Merges
────────────────────────────────────────────────────────────────────────────────

✓ RELATED_TO → ASSOCIATED_WITH
   Similarity: 88.7%
   Reasoning: Both types have no current usage and high embedding similarity.
   Edges Updated: 42

✓ LINKED_TO → ASSOCIATED_WITH
   Similarity: 85.9%
   Reasoning: High similarity with no useful distinction.
   Edges Updated: 29

Rejected Merges
────────────────────────────────────────────────────────────────────────────────

✗ VERIFIED_BY + VERIFIES
   Reasoning: Directional inverses representing opposite directions of verification.

✗ HAS_PART + PART_OF
   Reasoning: Compositional inverses with opposite semantic meaning.

✗ ENABLED_BY + ENABLES
   Reasoning: Directional inverses - ENABLED_BY indicates enabler, ENABLES indicates beneficiary.

────────────────────────────────────────────────────────────────────────────────
✓ Consolidation completed: 5 types reduced (80 → 75)
```

## Flags

| Flag | Default | Description |
|---|---|---|
| `--target <size>` | `90` | Stop when vocabulary reaches this size |
| `--threshold <0.0–1.0>` | `0.90` | Similarity threshold for candidate prioritization |
| `--dry-run` | off | Preview candidates; no merges, no pruning |
| `--no-prune-unused` | off | Skip pruning types with zero edge uses |

## Choose a target size

The right target depends on your domain.

| Domain | Suggested target | Rationale |
|---|---|---|
| Software development / technical docs | 70–90 | Rich relationship semantics; keep distinctions |
| General knowledge / research | 50–70 | More generic language; broader consolidation is safe |
| Multi-domain ontologies | 80–100 | Preserve cross-domain nuance |
| Single-domain ontologies | 40–60 | Coherent, curated vocabulary |

Start conservative. Run consolidation to a modest target first (e.g., 85), verify results, then run again to go further. Vocabulary that cannot reach a very aggressive target is often legitimately distinct — the LLM correctly rejected the remaining pairs.

## Inspect candidates before consolidating

Use `kg vocab similar` to find high-similarity pairs manually:

```bash
kg vocab similar RELATED_TO --limit 10
```

Use `kg vocab analyze` to see a type's category fit and whether it may be miscategorized:

```bash
kg vocab analyze PROCESSES
```

A type with a `Category Fit` of 0% that scores high similarity to another category is a candidate for reclassification, not consolidation.

## Generate embeddings (older databases)

Consolidation requires embeddings for similarity detection. If your database predates automatic embedding generation:

```bash
kg vocab generate-embeddings
```

This is a one-time operation.

## Recommended workflow

```bash
# 1. Check current state
kg vocab status

# 2. Pre-screen candidates
kg vocab similar RELATED_TO --limit 10

# 3. Analyze any suspicious types
kg vocab analyze RELATED_TO

# 4. Preview consolidation
kg vocab consolidate --dry-run --target 85

# 5. Execute if dry-run looks correct
kg vocab consolidate --target 85

# 6. Check results and run queries to verify coherence
kg vocab status
kg search query "your domain keywords"
```

## Back up before aggressive consolidation

Merges are immediate and there is no rollback mechanism. Before consolidating to a low target:

```bash
kg ontology export "YourOntology" > backup.json
```

For a full database backup:

```bash
docker exec knowledge-graph-postgres pg_dump -U admin knowledge_graph > backup.sql
```

## Troubleshooting

**"No more candidates available" but not at target.** All remaining candidate pairs were rejected by the LLM because they are directional inverses or meaningful distinctions. Your domain may legitimately require more types than your target. Raise the target rather than forcing further consolidation.

**High-similarity pair rejected.** Embedding similarity detects lexical overlap; the LLM evaluates semantic meaning. `CREATED_BY` and `CREATED_AT` score 91% similar because they share a root, but one identifies an actor and the other a timestamp. The rejection is correct.

**Consolidation merged types that should stay distinct.** Run `kg vocab status` to assess the current state. A split command is not yet implemented. Workaround: update edge types directly in the database, or restore from backup.

## Related

- `explanation/vocabulary-lifecycle.md` — how vocabulary expands during ingestion and the design rationale behind AITL consolidation
- ADR-032: Automatic Edge Vocabulary Expansion
- ADR-053: Vocabulary quality analysis and embedding similarity
