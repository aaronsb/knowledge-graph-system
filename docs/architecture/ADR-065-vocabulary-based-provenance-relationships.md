# ADR-065: Vocabulary-Based Provenance Relationships

**Status:** Accepted
**Date:** 2025-01-15
**Deciders:** Engineering Team
**Related ADRs:** ADR-058 (Polarity Axis Triangulation), ADR-048 (Query Safety via GraphQueryFacade)

---

## Context

### Current Architecture: Hardcoded Structural Relationships

The system currently treats Concept→Source provenance relationships differently from Concept→Concept semantic relationships:

**Concept→Concept (vocabulary-based):**
```python
# Dynamic relationship types from emergent vocabulary
MERGE (c1)-[r:SUPPORTS]->(c2)
MERGE (c1)-[r:CONTRADICTS]->(c2)
MERGE (c1)-[r:IMPLIES]->(c2)

# Stored in relationship_vocabulary table
# - Embeddings for semantic matching
# - LLM-discovered types normalized via relationship_mapper
# - Polarity axis triangulation (ADR-058) for grounding
# - Consolidation reduces similar types
```

**Concept→Source (hardcoded):**
```python
# Fixed structural relationship types
MERGE (c)-[:APPEARS]->(s)          # Hardcoded
MERGE (c)-[:EVIDENCED_BY]->(i)     # Hardcoded
MERGE (i)-[:FROM_SOURCE]->(s)      # Hardcoded

# NOT in relationship_vocabulary table
# No embeddings, no semantic matching
# No variation, no discovery
# Fixed in code (api/lib/serialization.py:799)
```

### The Inconsistency

This creates an architectural asymmetry:

| Feature | Concept→Concept | Concept→Source |
|---------|----------------|----------------|
| **Relationship types** | Emergent from LLM | Hardcoded in code |
| **Vocabulary table** | ✅ Yes | ❌ No |
| **Embeddings** | ✅ Yes | ❌ No |
| **Semantic matching** | ✅ Threshold-based | ❌ Binary match |
| **Discovery** | ✅ LLM generates | ❌ Fixed types |
| **Consolidation** | ✅ Reduce similar | ❌ N/A |
| **Polarity axis** | ✅ ADR-058 | ❌ N/A |
| **Nuance** | ✅ Gradient scores | ❌ Binary present/absent |

### The Problem

**Lack of semantic richness:**

Current system can only express that a concept "appears" in a source. No way to distinguish:
- Central vs tangential mentions
- Predictive vs retrospective references (prophesy vs fulfillment)
- Direct statements vs implied references
- Foundational themes vs peripheral topics

**Example: Biblical covenant tracing**

```cypher
-- Current (all the same):
(covenant_name)-[:APPEARS]->(Genesis_Chapter_15)
(covenant_name)-[:APPEARS]->(Genesis_Chapter_17)
(covenant_name)-[:APPEARS]->(Exodus_Chapter_2)

-- Desired (semantic variation):
(covenant_name)-[:CENTRAL_TO]->(Genesis_Chapter_15)       # Foundational
(covenant_name)-[:PROPHESIED_IN]->(Genesis_Chapter_17)    # Predictive
(covenant_name)-[:MENTIONED_IN]->(Exodus_Chapter_2)       # Reference
```

**Query complexity:**

Users must manually filter by structural signals (quote length, instance count) rather than semantic characterization:

```cypher
-- Current: Infer centrality from instance count
MATCH (c:Concept)-[:APPEARS]->(s:Source)
WITH c, s, count(*) as mentions
WHERE mentions > 5
RETURN s  // Probably central?

-- Desired: Query semantic cluster
MATCH (c:Concept)-[r]->(s:Source)
WHERE type(r) IN $appearance_types  // Similarity to APPEARS > 0.75
  AND r.appearance_strength > 0.5   // Projection on centrality axis
RETURN s
```

---

## Decision

**Treat APPEARS as a semantic prototype in embedding space**, identical to how SUPPORTS/CONTRADICTS function as polarity prototypes in ADR-058.

### Core Principle

**No hardcoded relationship types.** All relationships—both Concept→Concept and Concept→Source—use the emergent vocabulary system with threshold-based semantic clustering.

### Pattern: APPEARS as Vocabulary Cluster

```python
# APPEARS becomes a semantic prototype (not hardcoded type)
appearance_prototype = "APPEARS"

# LLM generates emergent appearance vocabulary during extraction
emergent_types = [
    "discussed in",
    "mentioned in",
    "central to",
    "prophesied in",
    "tangentially referenced in",
    "foundational to",
    ...
]

# Vocabulary table stores ALL relationship types with embeddings
relationship_vocabulary:
  - DISCUSSED_IN: embedding=[...], similarity_to_appears=0.91
  - MENTIONED_IN: embedding=[...], similarity_to_appears=0.87
  - PROPHESIED_IN: embedding=[...], similarity_to_appears=0.82
  - CENTRAL_TO: embedding=[...], similarity_to_appears=0.88
  - SUPPORTS: embedding=[...], similarity_to_appears=0.23  # Far from cluster
  - CONTRADICTS: embedding=[...], similarity_to_appears=0.19  # Far from cluster

# Query by semantic similarity to APPEARS prototype (threshold-based)
def match_concept_sources(concept_id, appears_threshold=0.75):
    """Find sources via relationships semantically similar to APPEARS"""

    # Get APPEARS cluster from vocabulary (not hardcoded)
    appears_embedding = get_vocabulary_embedding("APPEARS")

    # Find all types within threshold
    appearance_types = []
    for vocab_type in get_all_vocabulary_types():
        similarity = cosine_similarity(vocab_type.embedding, appears_embedding)
        if similarity >= appears_threshold:
            appearance_types.append(vocab_type.name)

    # Query using emergent vocabulary
    return f"""
        MATCH (c:Concept {{concept_id: $concept_id}})-[r]->(s:Source)
        WHERE type(r) IN {appearance_types}
        RETURN s, type(r), r.confidence
    """
```

### Polarity Axis for Appearance Strength

Apply ADR-058's polarity axis triangulation to appearance relationships:

```python
# Define polarity pairs (emergent from vocabulary, not hardcoded)
appearance_polarity_pairs = [
    ("CENTRAL_TO", "TANGENTIAL_TO"),
    ("THOROUGHLY_DISCUSSED_IN", "BRIEFLY_MENTIONED_IN"),
    ("FOUNDATIONAL_TO", "PERIPHERAL_TO"),
]

# Calculate polarity axis (same algorithm as grounding)
difference_vectors = []
for (positive, negative) in appearance_polarity_pairs:
    delta = embedding(positive) - embedding(negative)
    difference_vectors.append(delta)

appearance_axis = normalize(average(difference_vectors))

# Project edge onto axis for strength score
def calculate_appearance_strength(edge_type):
    """
    Returns: -1.0 (tangential) to +1.0 (central)

    Same dot product projection as grounding calculation.
    """
    edge_emb = get_vocabulary_embedding(edge_type)
    return dot_product(edge_emb, appearance_axis)
```

### Storage: Emergent Types, Not Hardcoded

```cypher
// LLM extraction generates whatever types emerge from corpus
MERGE (c:Concept {concept_id: "covenant_name"})-[:PROPHESIED_IN]->(s:Source {...})
MERGE (c:Concept {concept_id: "abraham"})-[:CENTRAL_TO]->(s:Source {...})
MERGE (c:Concept {concept_id: "livestock"})-[:MENTIONED_IN]->(s:Source {...})

// Vocabulary table auto-populated by extraction
// No hardcoded type list - vocabulary emerges from usage
```

---

## Implementation

### Phase 1: Infrastructure (Transparent Migration)

**Automatic appearance type inference** during ingestion:

```python
# api/lib/serialization.py
def infer_appearance_type(instance, source, all_instances):
    """
    Infer how concept appears based on structural signals.

    Transparent to LLM - no prompt changes needed.
    """
    signals = {
        'centrality': len(instance['quote']) / len(source['full_text']),
        'frequency': len(all_instances),  # How many times in this source
        'position': instance['paragraph'] / source['total_paragraphs'],
    }

    # Simple heuristics → vocabulary type
    if signals['centrality'] > 0.3:
        return "CENTRAL_TO"
    elif signals['frequency'] > 5:
        return "THOROUGHLY_DISCUSSED_IN"
    elif signals['position'] < 0.1:
        return "INTRODUCED_IN"
    else:
        return "APPEARS"  # Default fallback

def create_appearance_relationship(concept, source, instance, all_instances):
    """Create appearance relationship with inferred type"""
    # Infer type from structural signals
    type_hint = infer_appearance_type(instance, source, all_instances)

    # Normalize against vocabulary cluster
    canonical = normalize_appearance_type(type_hint, threshold=0.80)
    confidence = calculate_confidence(instance, source)

    # Create relationship (same structure, enriched type)
    query = f"""
        MATCH (c:Concept {{concept_id: $concept_id}})
        MATCH (s:Source {{source_id: $source_id}})
        MERGE (c)-[r:{canonical}]->(s)
        SET r.confidence = $confidence,
            r.appearance_strength = $strength
    """
```

### Phase 2: GraphQueryFacade Enhancement

**Vocabulary-aware source matching** (ADR-048 pattern):

```python
# api/api/lib/query_facade.py
class GraphQueryFacade:

    def match_concept_sources(
        self,
        concept_id: str,
        appearance_threshold: float = 0.75,  # Similarity to APPEARS prototype
        strength_threshold: float = None      # Projection on centrality axis
    ):
        """
        Match sources using semantic similarity to APPEARS cluster.

        Args:
            appearance_threshold: Min similarity to APPEARS prototype (0.75 = ~1 sigma)
            strength_threshold: Min projection on appearance_axis (optional)

        Returns:
            Sources with appearance metadata
        """
        # Get appearance cluster from vocabulary (not hardcoded)
        appearance_types = self.client.get_vocabulary_cluster(
            prototype="APPEARS",
            threshold=appearance_threshold,
            category="provenance"  # Optional filter
        )

        # Build query with emergent types
        filters = [f"type(r) IN {appearance_types}"]

        if strength_threshold:
            # Filter by projection on appearance_axis (ADR-058 style)
            filters.append(f"r.appearance_strength >= {strength_threshold}")

        where = " AND ".join(filters)

        return self.client._execute_cypher(f"""
            MATCH (c:Concept {{concept_id: $concept_id}})-[r]->(s:Source)
            WHERE {where}
            RETURN s, type(r), r.appearance_strength
            ORDER BY r.appearance_strength DESC
        """, {"concept_id": concept_id})
```

### Phase 3: Vocabulary Cluster Management

**AGEClient methods** for cluster operations:

```python
# api/api/lib/age_client.py
class AGEClient:

    def get_vocabulary_cluster(
        self,
        prototype: str,
        threshold: float = 0.75,
        category: Optional[str] = None
    ) -> List[str]:
        """
        Get vocabulary types semantically similar to prototype.

        Uses embeddings, not hardcoded lists.

        Examples:
            get_vocabulary_cluster("APPEARS", 0.75)
            → ["APPEARS", "DISCUSSED_IN", "MENTIONED_IN", "CENTRAL_TO", ...]

            get_vocabulary_cluster("SUPPORTS", 0.80)
            → ["SUPPORTS", "VALIDATES", "CONFIRMS", "REINFORCES", ...]
        """
        prototype_emb = self.get_vocabulary_embedding(prototype)

        query = """
            SELECT relationship_type, embedding
            FROM kg_api.relationship_vocabulary
            WHERE embedding IS NOT NULL
              AND is_active = TRUE
        """
        if category:
            query += f" AND category = '{category}'"

        result = self._execute_sql(query)

        # Calculate similarities
        cluster = []
        for row in result:
            type_emb = np.array(json.loads(row['embedding']))
            similarity = cosine_similarity(prototype_emb, type_emb)

            if similarity >= threshold:
                cluster.append(row['relationship_type'])

        return cluster

    def calculate_appearance_strength(
        self,
        edge_type: str,
        polarity_pairs: Optional[List[Tuple[str, str]]] = None
    ) -> float:
        """
        Calculate edge position on appearance strength axis (ADR-058).

        Returns: -1.0 (tangential) to +1.0 (central)
        """
        if not polarity_pairs:
            # Default appearance polarity (emergent from vocabulary)
            polarity_pairs = [
                ("CENTRAL_TO", "TANGENTIAL_TO"),
                ("THOROUGHLY_DISCUSSED_IN", "BRIEFLY_MENTIONED_IN"),
            ]

        # Same algorithm as grounding calculation (ADR-058)
        axis = self._compute_polarity_axis(polarity_pairs)
        edge_emb = self.get_vocabulary_embedding(edge_type)

        return np.dot(edge_emb, axis)
```

---

## Consequences

### Benefits

**1. Architectural consistency**
- Concept→Concept and Concept→Source use identical patterns
- All relationships flow through vocabulary system
- Eliminates special-case hardcoded types

**2. Semantic richness**
- Capture nuance in how concepts appear in sources
- Domain-specific appearance types emerge naturally
- Biblical: prophesied_in, fulfilled_in, typified_in
- Technical docs: introduced_in, deprecated_in, explained_in

**3. Query flexibility**
```python
# Strict: Only very similar to APPEARS
sources = facade.match_concept_sources(concept_id, appearance_threshold=0.90)

# Relaxed: Broader appearance-like relationships
sources = facade.match_concept_sources(concept_id, appearance_threshold=0.70)

# Filtered: Only central appearances
sources = facade.match_concept_sources(
    concept_id,
    appearance_threshold=0.75,
    strength_threshold=0.5  # Positive projection on centrality axis
)
```

**4. Vocabulary consolidation applies**
```bash
# Same consolidation workflow
kg vocab consolidate --auto

# Might merge:
# - "discussed in" + "discussed thoroughly in" → "DISCUSSED_IN"
# - "mentioned" + "mentioned in" → "MENTIONED_IN"
# - "appears in" + "appears within" → "APPEARS"
```

**5. Transparent to interfaces**
- Raw Cypher queries unchanged (pattern `[r]` matches any type)
- API responses backward compatible
- MCP/CLI/Web progressively enhance with appearance metadata
- No breaking changes

### Costs

**1. Initial migration effort**
- Modify ingestion pipeline (serialization.py)
- Add appearance inference logic
- Extend GraphQueryFacade
- Update vocabulary table schema (add category="provenance")

**2. Complexity for simple cases**
- Binary "does concept appear?" becomes gradient with threshold
- Requires understanding of similarity scores
- More configuration options (thresholds, strength filters)

**3. Storage overhead**
- Each appearance type needs embedding in vocabulary table
- Polarity pairs for appearance axis calculation
- Additional relationship properties (confidence, strength)

### Mitigations

**Default fallback behavior:**
```python
# If inference fails or vocabulary unavailable, use generic APPEARS
canonical = normalize_appearance_type(type_hint, threshold=0.80)
if not canonical:
    canonical = "APPEARS"  # Safe fallback
```

**Progressive enhancement:**
- Old data: Generic APPEARS relationships (still works)
- New data: Rich appearance types (better quality)
- Queries: Work with both (type pattern matches any)

**Facade abstraction:**
- Complexity hidden in GraphQueryFacade
- API endpoints use simple interface
- Raw Cypher users can ignore vocabulary if desired

---

## Alternatives Considered

### Alternative 1: Keep APPEARS Hardcoded, Add Properties

**Approach:** Single APPEARS type, enrich with properties instead of using multiple types.

```cypher
MERGE (c)-[:APPEARS {
    variant: "CENTRAL_TO",
    confidence: 0.92,
    category: "thematic"
}]->(s)
```

**Pros:**
- Simpler queries (always match `:APPEARS`)
- No vocabulary cluster management
- Backward compatible

**Cons:**
- Still hardcoded relationship type
- Properties not indexed for similarity search
- Can't use vocabulary consolidation
- Doesn't leverage existing embedding infrastructure
- Asymmetry remains (Concept→Concept uses types, Concept→Source uses properties)

**Rejected because:** Doesn't solve architectural inconsistency, misses vocabulary system benefits.

### Alternative 2: LLM Explicit Characterization

**Approach:** Ask LLM to explicitly characterize appearance during extraction.

```
For each concept extracted, classify how it appears in this text:
- CENTRAL: Primary theme or subject
- DISCUSSED: Explicitly explained or analyzed
- MENTIONED: Brief reference or citation
- IMPLIED: Indirectly suggested
```

**Pros:**
- LLM understands semantic distinction
- No structural inference needed
- Rich characterization

**Cons:**
- Adds complexity to extraction prompt
- Increases LLM API costs (longer prompts)
- Harder to validate/debug
- Requires prompt engineering for each domain

**Rejected because:** Adds unnecessary complexity to extraction; structural inference is sufficient and transparent.

### Alternative 3: Post-Processing Enrichment

**Approach:** Create generic APPEARS during ingestion, enrich later via analysis job.

```python
# Ingestion: Simple APPEARS
MERGE (c)-[:APPEARS]->(s)

# Later: Enrichment job analyzes and upgrades
MATCH (c)-[r:APPEARS]->(s)
WITH c, s, r, analyze_appearance(c, s) as variant
DELETE r
CREATE (c)-[new:{variant}]->(s)
```

**Pros:**
- Doesn't slow down ingestion
- Can re-characterize as models improve
- Separation of concerns

**Cons:**
- Two-phase process adds complexity
- Must track enrichment status
- Relationship deletion/recreation risky
- Delayed availability of rich data

**Rejected because:** Complexity of two-phase approach outweighs benefits; prefer single-pass enrichment.

---

## Related

- **ADR-058:** Polarity Axis Triangulation for Grounding Calculation (pattern we're replicating)
- **ADR-048:** Query Safety via GraphQueryFacade (abstraction layer for vocabulary complexity)
- **ADR-050:** Vocabulary Consolidation via AITL Hysteresis (applies to appearance types)
- **Issue #134:** APPEARS_IN vs APPEARS naming bug (prerequisite fix)

---

## References

- Vocabulary consolidation: ADR-050
- Relationship mapper: `api/api/lib/relationship_mapper.py`
- Polarity axis: `api/api/lib/age_client.py:_compute_polarity_axis()`
- Query facade: `api/api/lib/query_facade.py`
