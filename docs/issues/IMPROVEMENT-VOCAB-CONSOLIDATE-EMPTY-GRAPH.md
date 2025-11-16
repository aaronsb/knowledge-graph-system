# Improvement: Skip AI Consolidation When Graph is Empty

**Type:** Enhancement
**Component:** Vocabulary Management
**Command:** `kg vocab consolidate --auto`

---

## Problem

When running `kg vocab consolidate --auto` on an empty graph (0 ontologies), the command still performs expensive AI-based consolidation analysis before deleting unprotected vocabulary types.

This is wasteful because:
- AI consolidation requires LLM calls to analyze relationships and justify merges
- With 0 ontologies, there are no concepts/relationships to analyze
- The final cleanup phase already deletes unprotected vocab types
- The entire AI phase is unnecessary computational overhead

**Current Behavior:**
```bash
# Empty graph
kg ontology list
# → No ontologies found

# Run consolidation
kg vocab consolidate --auto
# → Performs AI analysis (slow, expensive, unnecessary)
# → Then deletes unprotected vocab types (the only needed step)
```

---

## Proposed Solution

**Detect empty graph and skip AI phase:**

```python
def consolidate_vocabulary(auto_approve: bool = False):
    """Consolidate vocabulary types."""

    # Check if graph has any ontologies
    ontology_count = get_ontology_count()

    if ontology_count == 0:
        console.info("Graph has no ontologies - skipping AI consolidation")
        console.info("Cleaning up unprotected vocabulary types...")

        # Skip AI phase, go straight to cleanup
        deleted = delete_unprotected_vocab_types()

        console.success(f"Deleted {deleted} unprotected vocabulary types")
        return

    # Normal consolidation flow with AI analysis
    ...
```

---

## Benefits

1. **Performance**: No wasted LLM calls on empty graphs
2. **Cost**: No API charges for unnecessary AI analysis
3. **User Experience**: Fast cleanup when resetting graph
4. **Correctness**: Same end result (unprotected types deleted)

---

## Use Cases

**Primary use case:**
- Testing architectural changes with clean slate
- Delete all ontologies → Consolidate vocab → Re-ingest with new architecture
- Currently wastes time on AI analysis before cleanup

**Workflow:**
```bash
# Delete all data
./scripts/delete_all_ontologies.sh

# Clean up vocabulary (currently slow due to AI phase)
kg vocab consolidate --auto  # ← Should be instant on empty graph

# Re-ingest with new architecture
kg ingest file -o "Genesis" genesis.txt
```

---

## Implementation Notes

**Detection:**
```python
def get_ontology_count() -> int:
    """Count ontologies in graph."""
    result = client._execute_cypher("""
        MATCH (s:Source)
        RETURN count(DISTINCT s.document) as count
    """)
    return result[0]['count'] if result else 0
```

**Protected Types:**
Already defined in consolidation logic (SUPPORTS, CONTRADICTS, structural types, etc.)

**Cleanup:**
Already implemented in post-consolidation phase - just call it directly.

---

## Edge Cases

**What if ontologies exist but have 0 concepts?**
- Still run AI consolidation (ontologies exist, may have been partially processed)
- Only skip when `ontology_count == 0`

**What if vocabulary types have embeddings but no edges?**
- Unprotected types get deleted regardless
- Protected types remain (as intended)
- Behavior unchanged from current implementation

---

## Testing

```bash
# Before fix (slow)
time kg vocab consolidate --auto  # ~30-60 seconds with AI

# After fix (fast)
time kg vocab consolidate --auto  # <1 second (no AI phase)

# Verify same result
kg vocab list  # Should only show protected types
```

---

## Related

- **Current implementation:** Vocabulary consolidation in consolidation worker
- **Protected types:** SUPPORTS, CONTRADICTS, APPEARS, structural types
- **Use case:** ADR-065 testing (vocabulary-based provenance)
- **Branch:** feature/vocabulary-based-appears
