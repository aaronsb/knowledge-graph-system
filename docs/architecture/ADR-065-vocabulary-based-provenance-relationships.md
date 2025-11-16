# ADR-065: Vocabulary-Based Provenance Relationships

**Status:** Accepted
**Date:** 2025-01-15
**Validated:** 2025-11-16 (see docs/VALIDATION-RESULTS.md)
**Deciders:** Engineering Team
**Related ADRs:**
- ADR-058 (Polarity Axis Triangulation) - Pattern we're replicating
- ADR-052 (Vocabulary Expansion-Consolidation Cycle) - Similarity-based clustering
- ADR-048 (Query Safety via GraphQueryFacade) - Abstraction layer
- ADR-044 (Probabilistic Truth Convergence) - Grounding calculation

**Mathematical Foundation:** Hybrid symbolic-tensor network (emergent, not prescribed)

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

## Architectural Realization: From Boolean to Probabilistic, From Graph to Tensor Network

### The Emergent Pattern

Through successive design decisions—vocabulary expansion-consolidation (ADR-052), polarity axis triangulation (ADR-058), and now vocabulary-based provenance—we've been **systematically eliminating boolean logic in favor of probabilistic values**.

**What we thought we were building:** A graph database with semantic enrichment

**What we're actually building:** A hybrid symbolic-tensor network represented in a graph

### The Shift from Boolean to Probabilistic

**Before (boolean):**
```python
# Binary membership
relationship = "APPEARS" or "SUPPORTS" or "CONTRADICTS"  # Discrete choice

# Binary queries
has_relationship = (c)-[:APPEARS]->(s)  # True or False

# Binary grounding
grounded = all_edges_support  # True or False
```

**After (probabilistic):**
```python
# Gradient membership
similarity_to_appears = 0.87  # Continuous [0, 1]
in_cluster = similarity >= threshold  # Threshold-based

# Gradient relationships
relationship_strength = dot(edge_embedding, polarity_axis)  # [-1, 1]
confidence = 0.92  # [0, 1]

# Gradient grounding
grounding = weighted_avg(projections, confidences)  # [-1, 1]
```

### If It Walks Like a Tensor...

**Tensor network properties we've inadvertently created:**

| Property | Our System | Tensor Network Equivalent |
|----------|------------|---------------------------|
| **Nodes** | Concepts with embeddings | Tensors (vectors in R^n) |
| **Edges** | Relationships with type embeddings | Tensor indices/contractions |
| **Operations** | Dot products, projections, weighted sums | Tensor contractions |
| **Clustering** | Similarity threshold filtering | Contraction-based membership |
| **Grounding** | Weighted projection aggregation | Multi-edge tensor contraction |
| **Vocabulary** | Type embeddings in semantic space | Tensor factorization/basis vectors |

**We're not forcing a tensor paradigm—we're recognizing that our design naturally creates one.**

### Why This Happened

Each decision eliminated discrete categories in favor of continuous values:

1. **ADR-052 (Vocabulary Expansion-Consolidation):** Instead of hardcoded relationship types, use similarity-based clustering
   - Boolean: "Is this SUPPORTS?" → Probabilistic: "87% similar to SUPPORTS"

2. **ADR-058 (Polarity Axis):** Instead of binary support/contradict, project onto axis
   - Boolean: "Supporting or contradicting?" → Probabilistic: "+0.73 projection (leaning support)"

3. **ADR-065 (Vocabulary-Based APPEARS):** Instead of binary presence, use appearance strength
   - Boolean: "Does concept appear?" → Probabilistic: "92% central, 0.15 tangential"

**Result: A probabilistic tensor network indexed by graph structure**

### What This Means Architecturally

We're building a **hybrid system:**

**Graph layer (symbolic):**
- Structural queries (Cypher patterns)
- Ontology organization (human-readable)
- Provenance chains (source → instance → concept)

**Tensor layer (continuous):**
- Embeddings (vectors in semantic space)
- Projections (dot products onto axes)
- Clustering (similarity thresholds)
- Grounding (weighted contractions)

**Integration:**
- Relationship types bridge both layers (symbolic labels + vector embeddings)
- Graph topology indexes tensor network structure
- Queries combine symbolic patterns + probabilistic operations

### Examples of Tensor Operations in the Graph

**Example 1: Grounding calculation**
```python
# This is a tensor contraction
grounding = Σ(confidence_i * dot(edge_embedding_i, polarity_axis)) / Σ(confidence_i)
            └──────────────────────┬──────────────────────┘
                          Weighted tensor contraction
```

**Example 2: Appearance clustering**
```python
# This is tensor filtering via contraction
cluster = {r | dot(embed(r), embed("APPEARS")) >= 0.75}
               └──────────────┬─────────────┘
                    Tensor similarity (normalized contraction)
```

**Example 3: Vocabulary consolidation**
```python
# This is tensor proximity detection
should_merge = cosine_sim(embed(type1), embed(type2)) >= threshold
               └─────────────────┬────────────────┘
                    Normalized tensor contraction
```

### Implications

**If we acknowledge this is a tensor network:**

**Benefits we gain:**
- Leverage tensor network optimization theory
- GPU acceleration for batch operations (dot products, projections)
- Tensor decomposition methods (reduce dimensionality, find patterns)
- Anomaly detection (outliers in tensor space)

**Clarity we gain:**
- Honest about mathematical foundation
- Probabilistic semantics (not boolean approximations)
- Gradient-based reasoning (smooth transitions, not hard boundaries)

**Risks we avoid:**
- Pretending discrete when actually continuous
- Binary queries on probabilistic data (threshold confusion)
- Losing semantic richness through forced categorization

**Architecture we maintain:**
- Graph remains primary interface (Cypher, ontologies)
- Tensors are implementation detail (users see probabilities)
- Hybrid symbolic-continuous reasoning

### Decision: Embrace the Pattern

**Treat APPEARS as a semantic prototype in embedding space**, identical to how SUPPORTS/CONTRADICTS function as polarity prototypes in ADR-058.

**But acknowledge:** This creates tensor network structure, and that's okay. We're not forcing tensors—they're emerging from our design principles.

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

## Open Question: LLM Interface Design

### Problem Statement

The vocabulary cluster is backend infrastructure for semantic richness and query flexibility. But how do we determine appearance types without burdening the LLM with vocabulary cluster complexity?

**Core tension:**
- **Backend needs:** Rich appearance types (CENTRAL_TO, MENTIONED_IN, PROPHESIED_IN, etc.)
- **LLM should see:** Simple, straightforward extraction task

**Critical constraint:** Avoid domain-specific overfitting. Solution must work across:
- Technical documentation (introduced, deprecated, explained, referenced)
- Research papers (foundational, cited, critiqued, extended)
- Narrative text (central, peripheral, foreshadowed, recalled)
- Code documentation (defined, used, imported, exported)
- Legal documents (enacted, amended, superseded, referenced)

### Interface Options

#### Option 1: Zero LLM Involvement (Pure Structural Inference)

**LLM sees:** Current extraction prompt (no changes)

```
Extract concepts from this text. For each concept:
- Label
- Description
- Relationships to other concepts
- Quote (evidence)
```

**LLM does:** Extracts concepts with quotes (exactly as today)

**Backend does:** Infers appearance type from structural signals

```python
def infer_appearance_type(instance, source, all_instances):
    """Pure structural inference - no LLM involvement"""

    # Structural signals
    centrality = len(instance['quote']) / len(source['full_text'])
    frequency = len(all_instances)  # How many times in source
    position = instance['paragraph'] / source['total_paragraphs']

    # Domain-agnostic heuristics
    if centrality > 0.3:
        return "CENTRAL_TO"
    elif frequency > 5:
        return "FREQUENTLY_MENTIONED_IN"
    elif position < 0.1:
        return "INTRODUCED_IN"
    else:
        return "APPEARS"
```

**Pros:**
- Zero LLM cognitive load (truly transparent)
- No prompt engineering required
- No extraction cost increase
- Works across all domains identically

**Cons:**
- Misses semantic nuances structure can't capture
- Example failures:
  - Short prophetic statement → "MENTIONED_IN" (should be "PROPHESIED_IN")
  - Lengthy critique → "CENTRAL_TO" (should be "CRITIQUED_IN")
  - Referenced theorem → "MENTIONED_IN" (should be "APPLIED")

**Domain-agnostic effectiveness:** Medium - structure approximates semantics but misses intent

---

#### Option 2: Simple Categorical Hint (Recommended Balance)

**LLM sees:** One additional simple question (no vocabulary exposure)

```
Extract concepts from this text. For each concept:
- Label
- Description
- Quote (evidence)
- [OPTIONAL] Prominence: how prominent is this concept?
  - "central" (primary theme/subject)
  - "discussed" (explained in detail)
  - "mentioned" (brief reference)
  - "peripheral" (tangential or implied)
```

**LLM does:** Picks from 4 simple, semantic categories

**Backend does:** Maps category to vocabulary cluster

```python
# LLM output (simple):
{
    "concept": "microservices architecture",
    "prominence": "discussed",  # Simple semantic judgment
    "quote": "...",
}

# Backend mapping (complex, invisible):
PROMINENCE_MAPPING = {
    "central": "CENTRAL_TO",
    "discussed": "THOROUGHLY_DISCUSSED_IN",
    "mentioned": "MENTIONED_IN",
    "peripheral": "TANGENTIALLY_REFERENCED_IN"
}

hint = PROMINENCE_MAPPING[prominence]

# Normalize to cluster (vocabulary infrastructure)
canonical = normalize_to_cluster(hint, "APPEARS", threshold=0.80)
```

**Pros:**
- LLM provides semantic understanding (better than structure alone)
- Categories are domain-agnostic and intuitive
- LLM never sees vocabulary cluster complexity
- Minimal prompt addition (4 simple choices)
- Optional field (fallback to structural inference)

**Cons:**
- Slight increase in extraction prompt complexity
- Requires LLM to make prominence judgment
- Categories may not capture all nuances (prophesy, critique, definition)

**Domain-agnostic effectiveness:** High - prominence is universally meaningful

**Example across domains:**

| Domain | Concept | Prominence | Backend Mapping |
|--------|---------|------------|-----------------|
| Technical | "API versioning" | discussed | THOROUGHLY_DISCUSSED_IN |
| Research | "relativity" | central | CENTRAL_TO |
| Narrative | "betrayal theme" | peripheral | TANGENTIALLY_REFERENCED_IN |
| Code | "Logger class" | mentioned | MENTIONED_IN |
| Legal | "due process" | central | CENTRAL_TO |

---

#### Option 3: Domain-Specific Semantic Characterization

**LLM sees:** Domain-specific characterization prompt

```
# For technical documentation:
Indicate relationship to this concept:
- "introduces" (defines or explains for first time)
- "uses" (applies or implements)
- "deprecates" (marks as obsolete)
- "references" (cites or mentions)

# For research papers:
Indicate relationship to this concept:
- "proposes" (introduces new idea)
- "validates" (provides evidence for)
- "critiques" (challenges or questions)
- "extends" (builds upon)

# For narrative text:
Indicate relationship to this concept:
- "develops" (central theme)
- "foreshadows" (hints at future)
- "recalls" (references earlier)
- "mentions" (brief appearance)
```

**LLM does:** Picks from domain-specific semantic categories

**Backend does:** Maps domain category to vocabulary

**Pros:**
- Rich semantic characterization
- Domain-appropriate nuance
- LLM leverages domain understanding

**Cons:**
- **Requires domain detection** (how do we know which prompt to use?)
- Prompt engineering per domain
- Different vocabularies per domain (harder to consolidate)
- **Overfitting risk** - categories may not transfer

**Domain-agnostic effectiveness:** Low - explicitly domain-specific

**Rejected because:** Violates domain-agnostic constraint, adds complexity

---

#### Option 4: Natural Language Description + Parsing

**LLM sees:** Open-ended question

```
Extract concepts. For each, briefly describe how it appears in this text.

Examples:
- "discussed extensively as central argument"
- "referenced briefly in passing"
- "introduced early then developed throughout"
- "implied but not explicitly stated"
```

**LLM does:** Writes 1-2 sentence natural language description

**Backend does:** NLP extraction + vocabulary normalization

```python
# LLM output (natural):
{
    "concept": "observer pattern",
    "appearance_description": "introduced early in the document and used throughout as the primary design example",
    "quote": "..."
}

# Backend NLP (complex):
keywords = extract_keywords(appearance_description)
# → ["introduced", "primary", "design", "example", "throughout"]

if "primary" in keywords or "central" in keywords:
    hint = "CENTRAL_TO"
elif "introduced" in keywords:
    hint = "INTRODUCED_IN"
elif "throughout" in keywords:
    hint = "THOROUGHLY_DISCUSSED_IN"

canonical = normalize_to_cluster(hint, "APPEARS", threshold=0.80)
```

**Pros:**
- Most natural for LLM (no categorization)
- Rich semantic information
- Domain-agnostic (LLM writes in own words)
- Captures nuances categories might miss

**Cons:**
- Requires NLP parsing (brittle, language-dependent)
- Inconsistent phrasing makes extraction harder
- Higher token cost (longer outputs)
- Validation difficult (free text)

**Domain-agnostic effectiveness:** High potential, high complexity

---

### Evaluation Criteria

| Criterion | Option 1:<br/>Structural | Option 2:<br/>Categorical | Option 3:<br/>Domain-Specific | Option 4:<br/>Natural Language |
|-----------|---------------------------|---------------------------|-------------------------------|--------------------------------|
| **LLM cognitive load** | None | Minimal | Medium | Low |
| **Prompt complexity** | Zero change | +4 categories | +domain detection | +open question |
| **Domain agnostic** | ✅ Yes | ✅ Yes | ❌ No | ✅ Yes |
| **Semantic accuracy** | Medium | High | Very High* | Very High |
| **Implementation complexity** | Low | Low | High | Medium |
| **Token cost** | No change | +~5 tokens | +~5 tokens | +~20 tokens |
| **Validation** | Easy (deterministic) | Easy (enum) | Medium (enum per domain) | Hard (free text) |
| **Extensibility** | Limited | Good | Domain-specific | Excellent |

*Per domain only

### Recommendation: Hybrid Approach (Option 1 + Optional Option 2)

**Default:** Structural inference (Option 1) - works transparently
**Enhancement:** Optional prominence hint (Option 2) - when extraction model supports it

```python
def determine_appearance_type(
    prominence_hint: Optional[str],  # From LLM if provided
    instance: Dict,
    source: Dict,
    all_instances: List
) -> str:
    """
    Determine appearance type using LLM hint OR structural fallback.

    LLM never sees vocabulary cluster - that's all backend.
    """

    # Priority 1: Use LLM's semantic hint if provided
    if prominence_hint:
        mapping = {
            "central": "CENTRAL_TO",
            "discussed": "THOROUGHLY_DISCUSSED_IN",
            "mentioned": "MENTIONED_IN",
            "peripheral": "TANGENTIALLY_REFERENCED_IN"
        }
        hint = mapping.get(prominence_hint.lower(), "APPEARS")

    # Priority 2: Infer from structure (always available)
    else:
        hint = infer_from_structure(instance, source, all_instances)

    # Normalize to vocabulary cluster (always backend)
    return normalize_to_cluster(hint, "APPEARS", threshold=0.80)
```

**Benefits of hybrid:**
- Works with current extraction (no changes required)
- Improves when extraction model enhanced (gradual upgrade)
- LLM never sees vocabulary cluster (maintains simplicity)
- Domain-agnostic (prominence is universal)
- Graceful degradation (structural fallback)

### Domain-Agnostic Examples

**Technical documentation:**
```
Concept: "dependency injection"
Structural signals: 15 mentions, 25% of text → "THOROUGHLY_DISCUSSED_IN"
LLM hint: "discussed" → "THOROUGHLY_DISCUSSED_IN"
Vocabulary cluster: Normalized, same result
```

**Research paper:**
```
Concept: "Nash equilibrium"
Structural signals: 2 mentions, 5% of text → "MENTIONED_IN"
LLM hint: "central" (it's the core theorem) → "CENTRAL_TO"
Vocabulary cluster: LLM hint more accurate than structure
```

**Code documentation:**
```
Concept: "Logger interface"
Structural signals: 1 mention, early in file → "INTRODUCED_IN"
LLM hint: "mentioned" (just referenced, not explained) → "MENTIONED_IN"
Vocabulary cluster: LLM provides nuance
```

**Legal document:**
```
Concept: "reasonable doubt"
Structural signals: 8 mentions, 18% of text → "FREQUENTLY_MENTIONED_IN"
LLM hint: "central" (foundational principle) → "CENTRAL_TO"
Vocabulary cluster: LLM understands legal importance
```

### Open Questions for Further Discussion

1. **Should prominence hint be required or optional?**
   - Optional: Graceful degradation, backward compatible
   - Required: Better quality, consistent across corpus

2. **Are 4 prominence categories sufficient?**
   - Could add "foundational" vs "derivative"
   - Could add "predictive" vs "retrospective"
   - Risk: More categories = harder for LLM to choose

3. **Should we support corpus-specific category extensions?**
   - User defines custom categories for their domain
   - Maps to vocabulary cluster via similarity
   - Risk: Inconsistency across ontologies

4. **How to handle multi-document context?**
   - Concept "central" to one chapter but "mentioned" in another
   - Need document-scoped vs corpus-scoped prominence
   - Affects relationship granularity

5. **Should appearance strength affect grounding calculation?**
   - Central appearances have more grounding weight?
   - Peripheral mentions contribute less to truth convergence?
   - Needs testing with real corpora

### Decision Timeline

**Phase 1 (MVP):** Option 1 only (structural inference)
- Validate basic vocabulary clustering works
- Measure structural inference accuracy
- Gather real-world appearance type distribution

**Phase 2 (Enhancement):** Add Option 2 (optional prominence)
- Extend extraction prompt with optional field
- Compare LLM vs structural inference accuracy
- Measure impact on semantic query quality

**Phase 3 (Evaluation):** Consider Option 4 if needed
- If prominence categories insufficient
- If domain-specific nuance critical
- Only after Option 2 data collection

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

## Future Work: Epistemic Status Classification

**Status Update (2025-11-16):**
- **Phase 1 (measurement):** ✅ Complete. See `docs/VALIDATION-RESULTS.md`. First CONTESTED epistemic status detected (ENABLES: +0.232 avg grounding). Measurement script: `operator/admin/calculate_vocab_epistemic_statuss.py`.
- **Phase 2 (query enhancement):** ✅ Complete. GraphQueryFacade now supports optional role filtering via `include_roles` and `exclude_roles` parameters. Test script: `operator/admin/test_epistemic_status_queries.py`.

### Formal Connections to KG Research

External review (Gemini 2.5) identified that our emergent design maps directly to established KG research:

| Our System | Formal Research Area | Mapping |
|------------|---------------------|---------|
| **Grounding score** | Uncertain/Probabilistic KGs (UKG/PKG) | Confidence measure for fact veracity |
| **AFFIRMATIVE role** | Classification of Uncertainty | High confidence facts (> 0.8) |
| **CONTESTED role** | Classification of Uncertainty | Moderate/disputed confidence (0.2-0.8) |
| **HISTORICAL role** | Temporal Knowledge Graphs (TKG) | Vocabulary evolution tracking |
| **CONTRADICTORY role** | Dialectical Reasoning | Thesis/antithesis preservation |

**Key insight:** We didn't implement these paradigms—we **derived them from first principles** through successive design decisions.

### Phased Exploration (Non-Breaking)

**Phase 1: Calculate and Store (Read-Only)**

Add epistemic status metadata **without changing any core logic**:

```python
# NEW: scripts/calculate_vocab_epistemic_statuss.py
def calculate_epistemic_statuss(age_client):
    """
    Calculate epistemic status for each vocabulary type based on grounding impact.

    Purely additive - does not change ingestion, grounding, or queries.
    """
    vocab_types = age_client.get_all_vocabulary_types()

    for vocab_type in vocab_types:
        # Get all edges using this type
        edges = age_client.query(f"""
            MATCH (c1)-[r:{vocab_type}]->(c2)
            RETURN c1.grounding_strength as from_grounding,
                   c2.grounding_strength as to_grounding
        """)

        # Calculate grounding statistics
        stats = {
            'avg_grounding': mean([e['to_grounding'] for e in edges]),
            'max_grounding': max([e['to_grounding'] for e in edges]),
            'min_grounding': min([e['to_grounding'] for e in edges]),
            'count': len(edges)
        }

        # Classify epistemic status
        if stats['avg_grounding'] > 0.8:
            role = "AFFIRMATIVE"
        elif stats['avg_grounding'] < -0.5:
            role = "CONTRADICTORY"
        elif 0.2 <= stats['avg_grounding'] <= 0.8:
            role = "CONTESTED"
        elif vocab_type in ['REPLACED_BY', 'SUPERSEDED_BY', 'DEPRECATED']:
            role = "HISTORICAL"
        else:
            role = "NEUTRAL"

        # ADD new properties (non-destructive)
        age_client.execute("""
            MATCH (v:VocabType {name: $type})
            SET v.epistemic_status = $role,
                v.epistemic_stats = $stats
        """, {"type": vocab_type, "role": role, "stats": stats})
```

**Result:** Core system unchanged, new metadata available for exploration.

**Phase 2: Enhance Querying (Additive Logic)**

Extend GraphQueryFacade with **optional** epistemic status filtering:

```python
# api/api/lib/query_facade.py
class GraphQueryFacade:

    def match_concept_relationships(
        self,
        concept_id: str,
        include_roles: Optional[List[str]] = None,  # NEW
        exclude_roles: Optional[List[str]] = None   # NEW
    ):
        """
        Match relationships with optional epistemic status filtering.

        Args:
            include_roles: Only include these roles (e.g., ["AFFIRMATIVE"])
            exclude_roles: Exclude these roles (e.g., ["HISTORICAL"])

        Backward compatible: If both None, behaves exactly as before.
        """
        # Get vocabulary types matching role filters
        if include_roles or exclude_roles:
            role_filter = []
            if include_roles:
                role_filter.append(f"v.epistemic_status IN {include_roles}")
            if exclude_roles:
                role_filter.append(f"v.epistemic_status NOT IN {exclude_roles}")

            vocab_query = f"""
                MATCH (v:VocabType)
                WHERE {' AND '.join(role_filter)}
                RETURN v.name as type_name
            """
            allowed_types = [r['type_name'] for r in self.client.execute(vocab_query)]
        else:
            allowed_types = None  # No filtering, use all types

        # Build main query (existing logic + optional type filter)
        type_pattern = f":{('|'.join(allowed_types))}" if allowed_types else ""

        query = f"""
            MATCH (c:Concept {{concept_id: $concept_id}})-[r{type_pattern}]->(c2)
            RETURN c2, type(r), r.confidence
        """

        return self.client.execute(query, {"concept_id": concept_id})
```

**New capabilities enabled:**

```python
# Explore only high-confidence relationships (thesis)
facade.match_concept_relationships(
    concept_id="covenant_name",
    include_roles=["AFFIRMATIVE"]
)

# Explore contradictions (antithesis)
facade.match_concept_relationships(
    concept_id="covenant_name",
    include_roles=["CONTRADICTORY", "CONTESTED"]
)

# Exclude historical relationships (current state only)
facade.match_concept_relationships(
    concept_id="covenant_name",
    exclude_roles=["HISTORICAL"]
)

# Default behavior unchanged (backward compatible)
facade.match_concept_relationships(concept_id="covenant_name")
```

**Phase 3: Integration (Only After Validation)**

Only if Phase 1-2 prove valuable:
- Add epistemic status to pruning logic (preserve dialectical tension)
- Add temporal queries (point-in-time semantic state)
- Integrate role-aware grounding (dialectical synthesis)

### Benefits of Phased Approach

**Safety:**
- Phase 1: Zero risk (read-only metadata)
- Phase 2: Backward compatible (optional parameters)
- Phase 3: Informed decision (validated with real data)

**Reversibility:**
- Git revert if exploration fails
- No breaking changes until Phase 3
- Can explore indefinitely in safe mode

**Learning:**
- Validate formal KG paradigms against our data
- Understand grounding distribution across roles
- Discover dialectical patterns in corpus

### Implementation Plan

**Week 1: Phase 1 (Calculation Script)**
- Create `scripts/calculate_vocab_epistemic_statuss.py`
- Run on existing vocabulary
- Analyze role distribution
- Document findings

**Week 2: Phase 2 (Query Enhancement)**
- Extend GraphQueryFacade
- Add CLI flags (e.g., `kg search --role AFFIRMATIVE`)
- Test dialectical queries
- Measure semantic value

**Week 3+: Evaluation**
- Use cases: Dialectical reasoning, temporal queries, uncertainty visualization
- Decision: Proceed to Phase 3 or keep as optional feature

---

## Related

- **ADR-058:** Polarity Axis Triangulation for Grounding Calculation (pattern we're replicating)
- **ADR-048:** Query Safety via GraphQueryFacade (abstraction layer for vocabulary complexity)
- **ADR-052:** Vocabulary Expansion-Consolidation Cycle (applies to appearance types)
- **Issue #134:** APPEARS_IN vs APPEARS naming bug (prerequisite fix)

---

## References

- Vocabulary consolidation: ADR-052
- Relationship mapper: `api/api/lib/relationship_mapper.py`
- Polarity axis: `api/api/lib/age_client.py:_compute_polarity_axis()`
- Query facade: `api/api/lib/query_facade.py`
