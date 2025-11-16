# Semantic Role Query Filtering

**Feature:** ADR-065 Phase 2
**Status:** Implemented (2025-11-16)
**API:** GraphQueryFacade.match_concept_relationships()

---

## Overview

Semantic role filtering allows you to query relationships based on their **semantic role** - a classification derived from grounding patterns that indicates whether a relationship type tends to be affirmative, contested, contradictory, or historical.

This enables powerful dialectical queries such as:
- "Show me only high-confidence relationships" (AFFIRMATIVE)
- "Show me points of tension and contradiction" (CONTESTED + CONTRADICTORY)
- "Exclude outdated relationships" (exclude HISTORICAL)
- "Find relationships that are actively debated" (CONTESTED only)

### Semantic Role Classifications

Roles are automatically detected by measuring grounding patterns across vocabulary types:

| Role | Avg Grounding | Meaning | Example Use Case |
|------|---------------|---------|------------------|
| **AFFIRMATIVE** | > 0.8 | High-confidence, well-supported relationships | Building consensus views, finding established connections |
| **CONTESTED** | 0.2 to 0.8 | Mixed grounding, actively debated | Exploring uncertainty, finding areas needing investigation |
| **CONTRADICTORY** | < -0.5 | Negative grounding, oppositional | Dialectical analysis, identifying conflicts |
| **HISTORICAL** | N/A | Temporal vocabulary (detected by name) | Time-based filtering, evolution tracking |
| **UNCLASSIFIED** | Other | Doesn't fit known patterns | Default fallback |
| **INSUFFICIENT_DATA** | N/A | < 3 measurements | Need more data |

### How It Works

1. **Measurement:** Run `calculate_vocab_semantic_roles.py --store` to analyze grounding patterns
2. **Storage:** Semantic roles stored as VocabType properties (`v.semantic_role`, `v.grounding_stats`)
3. **Querying:** Use `include_roles` or `exclude_roles` parameters in GraphQueryFacade
4. **Filtering:** Facade queries VocabType nodes, builds relationship type list dynamically
5. **Results:** Only relationships matching role criteria are returned

**Philosophy:** Semantic roles are **temporal measurements**, not permanent classifications. Re-running measurement as your graph evolves will yield different results. This embraces bounded locality + satisficing (ADR-065).

---

## Enabling Semantic Role Filtering

### Step 1: Measure Semantic Roles

Run the measurement script to analyze grounding patterns:

```bash
# Basic measurement (no storage - report only)
docker exec kg-operator python /workspace/operator/admin/calculate_vocab_semantic_roles.py

# Measure and store to enable query filtering
docker exec kg-operator python /workspace/operator/admin/calculate_vocab_semantic_roles.py --store

# Larger sample for more precision
docker exec kg-operator python /workspace/operator/admin/calculate_vocab_semantic_roles.py --sample-size 500 --store

# Detailed analysis with uncertainty metrics
docker exec kg-operator python /workspace/operator/admin/calculate_vocab_semantic_roles.py --verbose --store
```

**Output Example:**
```
Semantic Role Measurement Report
=================================

Summary:
  CONTESTED: 1
  UNCLASSIFIED: 6
  INSUFFICIENT_DATA: 28

CONTESTED (1)
  • ENABLES
    8 measurements from 8/8 edges | avg grounding: +0.232

📝 Storing semantic roles to VocabType nodes...
✓ Stored 35/35 semantic roles to VocabType nodes
  Phase 2 query filtering now available via GraphQueryFacade.match_concept_relationships()
```

### Step 2: Verify Storage

Check that semantic roles were stored:

```python
from api.api.lib.age_client import AGEClient

client = AGEClient()
facade = client.facade

# List vocabulary types with semantic roles
vocab_types = facade.match_vocab_types(
    where="v.semantic_role IS NOT NULL"
)

for vt in vocab_types:
    props = vt['v']['properties']
    print(f"{props['name']}: {props['semantic_role']} (avg: {props['grounding_stats']['avg_grounding']:.3f})")
```

**Example Output:**
```
ENABLES: CONTESTED (avg: +0.232)
SUPPORTS: UNCLASSIFIED (avg: +0.165)
INFLUENCES: UNCLASSIFIED (avg: -0.049)
```

---

## API Usage

### Basic Role Filtering

```python
from api.api.lib.age_client import AGEClient

client = AGEClient()
facade = client.facade

# Include only AFFIRMATIVE relationships (high confidence)
affirmative = facade.match_concept_relationships(
    include_roles=["AFFIRMATIVE"],
    limit=10
)

# Exclude HISTORICAL relationships (current state only)
current = facade.match_concept_relationships(
    exclude_roles=["HISTORICAL"],
    limit=10
)
```

### Dialectical Queries

```python
# Explore areas of tension and contradiction
dialectical = facade.match_concept_relationships(
    include_roles=["CONTESTED", "CONTRADICTORY"],
    limit=20
)

# Find well-established connections (thesis)
thesis = facade.match_concept_relationships(
    include_roles=["AFFIRMATIVE"]
)

# Find points of disagreement (antithesis)
antithesis = facade.match_concept_relationships(
    include_roles=["CONTESTED", "CONTRADICTORY"]
)
```

### Combined Filtering

```python
# Specific relationship type + semantic role
enables_contested = facade.match_concept_relationships(
    rel_types=["ENABLES"],
    include_roles=["CONTESTED"],
    limit=10
)

# Multiple types + role filter
causal_affirmative = facade.match_concept_relationships(
    rel_types=["ENABLES", "CAUSES", "REQUIRES"],
    include_roles=["AFFIRMATIVE"]
)

# Type filter + exclude historical
current_supports = facade.match_concept_relationships(
    rel_types=["SUPPORTS", "VALIDATES"],
    exclude_roles=["HISTORICAL"]
)
```

### Backward Compatibility

```python
# Traditional queries still work (no role filtering)
all_supports = facade.match_concept_relationships(
    rel_types=["SUPPORTS"]
)

# No parameters - returns all relationships
all_rels = facade.match_concept_relationships(limit=100)
```

---

## Use Cases

### 1. Consensus Building

**Goal:** Find well-established, high-confidence connections

```python
# Get only AFFIRMATIVE relationships
consensus = facade.match_concept_relationships(
    include_roles=["AFFIRMATIVE"]
)

# Build consensus graph
for rel in consensus:
    source = rel['c1']['properties']['label']
    target = rel['c2']['properties']['label']
    rel_type = rel['r']['label']
    confidence = rel['r']['properties'].get('confidence', 'N/A')

    print(f"{source} --[{rel_type} (conf: {confidence})]-> {target}")
```

**Use Cases:**
- Academic literature reviews (established facts)
- Documentation generation (proven patterns)
- Educational content (consensus knowledge)

### 2. Research Questions & Investigation

**Goal:** Identify areas needing further investigation

```python
# Find contested relationships (mixed evidence)
contested = facade.match_concept_relationships(
    include_roles=["CONTESTED"],
    where="r.confidence > 0.5"  # Still reasonably confident despite mixed grounding
)

# Analyze contested areas
for rel in contested:
    source = rel['c1']['properties']['label']
    target = rel['c2']['properties']['label']
    rel_type = rel['r']['label']

    print(f"Contested: {source} --[{rel_type}]-> {target}")
    # → Suggests areas for further research or validation
```

**Use Cases:**
- Identifying research gaps
- Finding areas of active debate
- Prioritizing validation efforts
- Generating research questions

### 3. Dialectical Analysis

**Goal:** Explore thesis, antithesis, and synthesis patterns

```python
# Thesis: Established connections
thesis_rels = facade.match_concept_relationships(
    include_roles=["AFFIRMATIVE"]
)

# Antithesis: Points of contradiction
antithesis_rels = facade.match_concept_relationships(
    include_roles=["CONTESTED", "CONTRADICTORY"]
)

# Analyze dialectical tension
print(f"Thesis statements: {len(thesis_rels)}")
print(f"Antithesis statements: {len(antithesis_rels)}")
print(f"Dialectical ratio: {len(antithesis_rels) / len(thesis_rels):.2f}")
```

**Use Cases:**
- Philosophical analysis
- Argumentative writing
- Critical thinking exercises
- Identifying intellectual tensions

### 4. Temporal Analysis

**Goal:** Compare current state vs. historical evolution

```python
# Current state (exclude historical)
current_state = facade.match_concept_relationships(
    exclude_roles=["HISTORICAL"]
)

# Historical context (only historical)
historical_context = facade.match_concept_relationships(
    include_roles=["HISTORICAL"]
)

# Evolution analysis
print(f"Current relationships: {len(current_state)}")
print(f"Historical relationships: {len(historical_context)}")
```

**Use Cases:**
- Tracking knowledge evolution
- Understanding paradigm shifts
- Documenting deprecated patterns
- Historical research

### 5. Confidence-Based Filtering

**Goal:** Filter by reliability level

```python
# High confidence + high grounding
reliable = facade.match_concept_relationships(
    include_roles=["AFFIRMATIVE"],
    where="r.confidence > 0.8"
)

# Mixed evidence but still valuable
uncertain = facade.match_concept_relationships(
    include_roles=["CONTESTED"],
    where="r.confidence > 0.5"
)

# Low confidence relationships (may need review)
low_confidence = facade.match_concept_relationships(
    include_roles=["UNCLASSIFIED"],
    where="r.confidence < 0.5"
)
```

**Use Cases:**
- Risk assessment
- Data quality analysis
- Prioritizing verification
- Building trust layers

---

## Advanced Patterns

### Pattern 1: Concept-Specific Role Analysis

```python
def analyze_concept_roles(concept_id: str):
    """Analyze semantic role distribution for a specific concept."""

    roles = ["AFFIRMATIVE", "CONTESTED", "CONTRADICTORY", "HISTORICAL"]
    role_counts = {}

    for role in roles:
        rels = facade.match_concept_relationships(
            include_roles=[role],
            where=f"c1.concept_id = '{concept_id}' OR c2.concept_id = '{concept_id}'"
        )
        role_counts[role] = len(rels)

    return role_counts

# Example
counts = analyze_concept_roles("sha256:abc123...")
print(f"AFFIRMATIVE: {counts['AFFIRMATIVE']}")
print(f"CONTESTED: {counts['CONTESTED']}")
print(f"CONTRADICTORY: {counts['CONTRADICTORY']}")
```

### Pattern 2: Dialectical Subgraph Extraction

```python
def extract_dialectical_subgraph(topic_concept_id: str):
    """Extract thesis-antithesis relationships for a topic."""

    # Thesis (well-supported)
    thesis = facade.match_concept_relationships(
        include_roles=["AFFIRMATIVE"],
        where=f"c1.concept_id = '{topic_concept_id}'"
    )

    # Antithesis (contested/contradictory)
    antithesis = facade.match_concept_relationships(
        include_roles=["CONTESTED", "CONTRADICTORY"],
        where=f"c1.concept_id = '{topic_concept_id}'"
    )

    return {
        "thesis": thesis,
        "antithesis": antithesis,
        "synthesis_needed": len(antithesis) > 0
    }
```

### Pattern 3: Role Evolution Tracking

```python
import json
from datetime import datetime

def track_role_evolution(vocab_type: str):
    """Track how a vocabulary type's semantic role changes over time."""

    # Get current role and stats
    vt = facade.match_vocab_types(where=f"v.name = '{vocab_type}'")

    if vt:
        props = vt[0]['v']['properties']
        measurement = {
            "timestamp": datetime.now().isoformat(),
            "vocab_type": vocab_type,
            "semantic_role": props.get('semantic_role'),
            "avg_grounding": props.get('grounding_stats', {}).get('avg_grounding'),
            "measured_concepts": props.get('grounding_stats', {}).get('measured_concepts')
        }

        # Append to evolution log
        with open(f"role_evolution_{vocab_type}.jsonl", "a") as f:
            f.write(json.dumps(measurement) + "\n")

        return measurement

    return None
```

---

## Performance Considerations

### Query Overhead

Role filtering adds a VocabType lookup query before the main relationship query:

```python
# Two queries executed:
# 1. MATCH (v:VocabType) WHERE v.semantic_role IN ['AFFIRMATIVE'] RETURN v.name
# 2. MATCH (c1:Concept)-[r:TYPE1|TYPE2|...]->(c2:Concept) RETURN c1, r, c2
```

**Impact:**
- VocabType query: ~1-5ms (35 vocab types → fast)
- Relationship query: Depends on graph size
- **Total overhead: Negligible** (~1-5ms for vocab lookup)

**Optimization:**
- VocabType nodes are small (35 in test graph)
- Lookup query is simple (indexed on semantic_role if needed)
- Relationship query benefits from reduced type list

### Sample Size Tradeoffs

| Sample Size | Measurement Time | Precision | Use Case |
|-------------|------------------|-----------|----------|
| 20 | ~10 seconds | Low | Quick check |
| 100 (default) | ~30 seconds | Medium | Standard use |
| 500 | ~2 minutes | High | Important decisions |
| 1000 | ~5 minutes | Very High | Research validation |

**Recommendation:** Use default 100 for most cases. Increase to 500+ when:
- Making critical decisions based on roles
- Publishing research results
- Validating architectural changes

---

## Limitations & Considerations

### 1. Temporal Nature

**Semantic roles are temporal measurements, not permanent truths.**

```python
# Roles change as graph evolves
# Measurement 1 (Week 1): ENABLES is CONTESTED (+0.232)
# Measurement 2 (Week 4): ENABLES is AFFIRMATIVE (+0.856)  # More supporting evidence added
```

**Implication:** Re-run measurement periodically to keep roles current.

### 2. Sample-Based Estimation

**Roles are estimated from sampled edges, not exhaustive analysis.**

```python
# Sample size affects precision
# 100 edges → ±0.05 uncertainty
# 500 edges → ±0.02 uncertainty
```

**Implication:** Larger samples = more precision, but longer measurement time.

### 3. Bounded Locality

**Grounding calculation uses limited recursion depth (bounded locality).**

```python
# Grounding is calculated with finite recursion
# Not infinite traversal (satisficing, not optimizing)
```

**Implication:** Results are "good enough" estimates, not perfect calculations.

### 4. Insufficient Data

**New or rare vocabulary types may lack sufficient measurements.**

```python
# Only 2 edges → INSUFFICIENT_DATA
# Cannot reliably classify with < 3 measurements
```

**Implication:** Some types may be INSUFFICIENT_DATA or UNCLASSIFIED until more data exists.

### 5. No Automatic Updates

**Semantic roles are NOT automatically recalculated when graph changes.**

```python
# Roles persist until you re-run measurement script
# Adding 1000 new concepts doesn't update roles
```

**Implication:** Treat stored roles as "last known measurement" with timestamp.

---

## Best Practices

### ✅ Do

1. **Re-measure periodically** as your graph evolves (weekly, monthly, or after major ingestion)
2. **Check timestamps** to know when roles were last measured (`v.role_measured_at`)
3. **Use appropriate sample sizes** for your use case (default 100 is usually fine)
4. **Combine with confidence filtering** for robust queries (`include_roles + where="r.confidence > 0.8"`)
5. **Document role-based decisions** (e.g., "Used AFFIRMATIVE filter for consensus view on 2025-11-16")

### ❌ Don't

1. **Don't treat roles as permanent** - they're temporal measurements
2. **Don't over-optimize sample size** - default 100 is sufficient for most cases
3. **Don't rely solely on roles** - combine with other signals (confidence, edge_count, etc.)
4. **Don't expect 100% coverage** - some types will be INSUFFICIENT_DATA or UNCLASSIFIED
5. **Don't skip --verbose** when investigating anomalies - it shows uncertainty metrics

---

## Troubleshooting

### Problem: No results with include_roles

```python
# Query returns empty
results = facade.match_concept_relationships(
    include_roles=["AFFIRMATIVE"]
)
# → []
```

**Solution:**
1. Check if semantic roles are stored: `facade.match_vocab_types(where="v.semantic_role IS NOT NULL")`
2. Run measurement with --store: `calculate_vocab_semantic_roles.py --store`
3. Check if any types have that role: `facade.match_vocab_types(where="v.semantic_role = 'AFFIRMATIVE'")`

### Problem: All relationships are INSUFFICIENT_DATA

```bash
# Measurement output shows:
# INSUFFICIENT_DATA: 35
```

**Solution:**
- Graph is too small or too new
- Increase sample size: `--sample-size 500`
- Wait for more data to accumulate
- Check grounding calculation is working: Look for non-zero grounding values

### Problem: Semantic roles seem incorrect

```python
# ENABLES shows AFFIRMATIVE, but you expected CONTESTED
```

**Solution:**
1. Run with --verbose to see detailed stats
2. Check grounding distribution: `v.grounding_stats.grounding_distribution`
3. Verify sample size was adequate
4. Re-run measurement with larger sample: `--sample-size 500`
5. Check if new data shifted grounding patterns

---

## Testing

Test script: `operator/admin/test_semantic_role_queries.py`

```bash
# Run all tests
docker exec kg-operator python /workspace/operator/admin/test_semantic_role_queries.py

# Expected output:
# ✓ All tests completed
# Phase 2 semantic role filtering is working correctly
```

**Test Coverage:**
- ✅ include_roles with single role
- ✅ include_roles with multiple roles
- ✅ exclude_roles
- ✅ Combined rel_types + include_roles
- ✅ Backward compatibility (no role parameters)
- ✅ Dialectical queries (CONTESTED + CONTRADICTORY)

---

## Related Documentation

- **ADR-065:** Vocabulary-Based Provenance Relationships
- **ADR-044:** Probabilistic Truth Convergence (grounding calculation)
- **ADR-058:** Polarity Axis Triangulation (grounding methodology)
- **VALIDATION-RESULTS.md:** Phase 1 validation results
- **GraphQueryFacade:** `api/api/lib/query_facade.py`

---

## Future Enhancements (Phase 3)

Potential future work:

1. **Auto-remeasurement:** Background job to periodically recalculate roles
2. **Role-aware pruning:** Preserve dialectical tension when pruning edges
3. **Temporal queries:** Point-in-time semantic state reconstruction
4. **Role-weighted grounding:** Adjust grounding calculation based on relationship roles
5. **Visualization:** Graph coloring by semantic role
6. **API endpoints:** REST API support for role filtering
7. **CLI commands:** `kg search --role AFFIRMATIVE` syntax

These await further validation with real-world usage patterns.

---

## Summary

**Semantic role filtering enables powerful, nuanced queries** that go beyond traditional graph traversal:

- **Dialectical analysis** (thesis/antithesis)
- **Confidence-based filtering** (AFFIRMATIVE only)
- **Temporal analysis** (exclude HISTORICAL)
- **Research prioritization** (find CONTESTED areas)

The feature is **fully backward compatible**, **well-tested**, and **production-ready**. Roles are **temporal measurements** that embrace bounded locality and satisficing rather than claiming perfect knowledge.

For questions or issues, see `docs/architecture/ADR-065-vocabulary-based-provenance-relationships.md`.
