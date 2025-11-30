# ADR-046: Grounding-Aware Vocabulary Management

**Status:** Proposed
**Date:** 2025-10-25
**Authors:** System Architecture Team
**Related:** ADR-032 (Automatic Edge Vocabulary Expansion), ADR-044 (Probabilistic Truth Convergence), ADR-045 (Unified Embedding Generation)

## Overview

Not all relationship types are created equal—some point to well-supported truths while others connect speculative or contradictory concepts. Should "SUPPORTS" (used in 38 solid connections backed by evidence) be treated the same as "THEORETICALLY_ENABLES" (used once, connecting two weakly-grounded concepts)?

This ADR adds quality awareness to vocabulary management by tracking how well-grounded each relationship type tends to be. The system already calculates a grounding score for each concept based on supporting versus contradicting evidence (from ADR-044). Now, when managing vocabulary, the system can consider: "This relationship type consistently appears in high-grounding connections—keep it" versus "This type only shows up in low-grounding, speculative connections—candidate for pruning." This is particularly useful for detecting near-synonyms: if "SUPPORTS" and "VALIDATES" have similar semantic embeddings AND similar grounding profiles, they're probably redundant and can be consolidated. The system also uses this information when choosing which types to show the AI during extraction—prioritizing vocabulary that has proven useful for building well-grounded knowledge. Think of it as reputation-aware vocabulary: words that consistently contribute to solid, evidence-backed connections earn their place, while terms that only appear in speculative edges are scrutinized more carefully.

---

## Context

### The ADR-044/045/046 Trio

This ADR completes a three-part system for truth convergence in the knowledge graph:

| ADR | Focus | Purpose |
|-----|-------|---------|
| **ADR-044** | **Theory** | Probabilistic truth convergence through grounding strength |
| **ADR-045** | **Storage** | Unified embedding generation infrastructure |
| **ADR-046** | **Management** | Vocabulary lifecycle with grounding awareness |

### The Vocabulary Dilution Problem

As the system operates, vocabulary expands through LLM-generated edge types (ADR-032). While this enables semantic richness, unchecked growth creates **dilution risks**:

**Problem 1: LLM Prompt Cognitive Overload**

```python
# Manageable (30 types)
EXTRACTION_PROMPT = """
Relationships: IMPLIES, SUPPORTS, CONTRADICTS, ENABLES, ... (30 types)
"""

# Cognitive overload (200 types)
EXTRACTION_PROMPT = """
Relationships: IMPLIES, SUPPORTS, CONTRADICTS, ENABLES, ENHANCES, FACILITATES,
STRENGTHENS, REINFORCES, BOLSTERS, UPHOLDS, VALIDATES, CORROBORATES,
SUBSTANTIATES, CONFIRMS, VERIFIES, ATTESTS, ... (200 types)
"""
```

**Result:** LLM gets confused, picks random types, extraction quality degrades.

**Problem 2: Synonym Explosion**

```sql
-- Production data (2025-10-25):
SUPPORTS (38 edges) [B]           -- Builtin
SUPPORTED_BY (1 edge)             -- LLM-created inverse
ENHANCES (1 edge)                 -- LLM-created near-synonym
STRENGTHENS (0 edges)             -- Future LLM invention (likely)
REINFORCES (0 edges)              -- Future LLM invention (likely)
CORROBORATES (0 edges)            -- Future LLM invention (likely)
```

All semantically similar, but treated as distinct types. This dilutes:
- **Grounding calculations** - Support split across 6 types instead of 1
- **Similarity matching** - Concept matching confused by near-duplicates
- **Operator comprehension** - Which type should humans use?
- **Query results** - Relationships scattered across synonyms

**Problem 3: Grounding Strength Degradation**

```python
# Before synonym explosion
Concept "System uses Apache AGE":
  ← SUPPORTS (38 edges, avg confidence 0.85) = 32.3 weight
  grounding_strength = 32.3 / 32.3 = 1.00 (100%)

# After synonym explosion
Concept "System uses Apache AGE":
  ← SUPPORTS (12 edges, avg confidence 0.85) = 10.2 weight
  ← CORROBORATES (8 edges, avg confidence 0.80) = 6.4 weight
  ← VALIDATES (7 edges, avg confidence 0.82) = 5.74 weight
  ← CONFIRMS (6 edges, avg confidence 0.83) = 4.98 weight
  ← STRENGTHENS (5 edges, avg confidence 0.81) = 4.05 weight

  # Grounding calculation WITHOUT synonym awareness
  grounding_strength = 10.2 / 31.37 = 0.325 (32%)  ← INCORRECT!

  # Should be: All are "support-like", total = 31.37
  grounding_strength = 31.37 / 31.37 = 1.00 (100%)
```

**The core issue:** Binary pruning (keep/delete) doesn't preserve semantic meaning. We need **grounding-aware clustering** that understands synonyms contribute to the same semantic dimension.

### Current State: ADR-032 Sliding Window

**Existing system** (implemented):

```python
VOCAB_MIN = 30          # Protected builtins
VOCAB_MAX = 90          # Soft limit - start pruning
VOCAB_EMERGENCY = 200   # Hard limit - aggressive pruning

def calculate_aggressiveness(vocab_size: int) -> float:
    """
    Returns pruning aggressiveness (0.0-1.0).

    Zones:
    - Safe (30-90): 0.0 (no pruning)
    - Active (90-150): 0.0-0.5 (gentle)
    - Critical (150-200): 0.5-1.0 (aggressive)
    - Emergency (200+): 1.0 (maximum)
    """
```

**Pruning strategies:**
- **Naive:** Usage count only (low edges = prune)
- **HITL:** Human-in-the-loop approval
- **AITL:** AI-in-the-loop suggestions

**Gaps in ADR-032:**
1. ❌ No embedding-based synonym detection (uses string matching only)
2. ❌ No grounding contribution awareness
3. ❌ No protection for high-value types in truth convergence
4. ❌ No dynamic prompt curation (shows all types to LLM)

### How ADR-044/045 Enable Better Management

**ADR-044 provides:**
- Grounding strength calculation for all concepts
- Ability to measure edge type contribution to grounding
- Truth convergence metrics

**ADR-045 provides:**
- Embeddings for all vocabulary types (builtins + LLM-generated)
- Semantic similarity measurement (not just string matching)
- Consistent embedding model across vocabulary

**ADR-046 leverages both:**
- Embedding similarity → accurate synonym detection
- Grounding contribution → value-based pruning priorities
- Semantic clustering → preserve meaning while consolidating

## Decision

### Implement Grounding-Aware Vocabulary Management

Extend ADR-032 with **grounding contribution metrics** and **embedding-based synonym clustering** to:
1. Prevent dilution of grounding strength through synonym consolidation
2. Protect high-value types that contribute significantly to truth convergence
3. Dynamically curate vocabulary subsets for LLM prompts
4. Manage vocabulary lifecycle with semantic awareness

### Core Principles

**Principle 1: Semantic Clustering**
```
Vocabulary is not a flat list - it's clusters in embedding space.

Cluster 1 (Support dimension):
  SUPPORTS [canonical] ← 38 edges, builtin
  ├─ CORROBORATES ← 8 edges, similarity 0.91
  ├─ VALIDATES ← 7 edges, similarity 0.88
  ├─ CONFIRMS ← 6 edges, similarity 0.87
  └─ STRENGTHENS ← 5 edges, similarity 0.85

All contribute to the SAME semantic dimension in grounding.
```

**Principle 2: Grounding Contribution is Value**
```python
# Type A: High usage, low grounding impact
RELATED_TO: 45 edges, but grounding_contribution = 0.05
# → Low value (structural, doesn't affect truth)

# Type B: Low usage, high grounding impact
SUPPORTS: 38 edges, grounding_contribution = 0.92
# → High value (evidential, critical for truth)

# Type C: Low usage, low grounding impact
TAGGED_WITH: 2 edges, grounding_contribution = 0.01
# → Candidate for pruning
```

**Principle 3: Dynamic LLM Vocabulary**
```python
# Don't show all 200 types to LLM
# Show curated subset based on:
# 1. Document domain relevance
# 2. Global usage frequency
# 3. Grounding contribution
# 4. Semantic diversity (avoid near-duplicates)

get_extraction_vocabulary(document, max_types=50)
# → [SUPPORTS, ENABLES, REQUIRES, ...] (50 diverse, high-value types)
```

### Enhanced Vocabulary Scoring

**Extend `EdgeTypeScore` with grounding metrics:**

```python
@dataclass
class EdgeTypeScore:
    """
    Extended scoring for vocabulary types with grounding awareness.

    ADR-032 metrics (existing):
    - usage_count: How many edges use this type
    - bridge_score: Connects disconnected subgraphs
    - trend_score: Usage trending up/down

    ADR-046 metrics (new):
    - grounding_contribution: Impact on grounding strength
    - synonym_cluster_size: Number of near-synonyms (redundancy indicator)
    - avg_confidence: Average edge confidence
    - semantic_diversity: Distance from nearest neighbor in embedding space
    """
    # Existing (ADR-032)
    relationship_type: str
    usage_count: int
    bridge_score: float        # 0.0-1.0
    trend_score: float         # -1.0 to +1.0

    # New (ADR-046)
    grounding_contribution: float     # 0.0-1.0
    synonym_cluster_size: int         # Number of types with similarity > 0.85
    avg_confidence: float             # Average confidence of edges
    semantic_diversity: float         # 0.0-1.0 (distance to nearest neighbor)

    # Computed
    value_score: float         # Composite score (see calculation below)

    def calculate_value_score(self) -> float:
        """
        Composite value score for pruning decisions.

        High value = protect from pruning
        Low value = candidate for consolidation/pruning
        """
        score = 0.0

        # Usage weight (20%)
        score += (self.usage_count / 100) * 0.20

        # Grounding contribution weight (40%)
        # This is the MOST important metric for truth convergence
        score += self.grounding_contribution * 0.40

        # Bridge score weight (15%)
        score += self.bridge_score * 0.15

        # Semantic diversity weight (15%)
        # High diversity = unique semantic niche (protect)
        # Low diversity = redundant with others (merge candidate)
        score += self.semantic_diversity * 0.15

        # Trend weight (10%)
        # Positive trend = gaining usage (protect)
        # Negative trend = declining (merge candidate)
        score += (self.trend_score + 1.0) / 2.0 * 0.10

        # Penalty for large synonym clusters (redundancy)
        if self.synonym_cluster_size > 1:
            redundancy_penalty = min(0.3, self.synonym_cluster_size * 0.05)
            score -= redundancy_penalty

        return max(0.0, min(1.0, score))  # Clamp to [0.0, 1.0]
```

**Example scoring:**

```python
# High-value type: SUPPORTS
EdgeTypeScore(
    type="SUPPORTS",
    usage_count=38,
    bridge_score=0.67,
    trend_score=0.15,
    grounding_contribution=0.92,      # Critical for truth convergence!
    synonym_cluster_size=1,           # Unique (no near-synonyms yet)
    avg_confidence=0.85,
    semantic_diversity=0.88,          # Far from other types
    value_score=0.89                  # HIGH VALUE - PROTECT
)

# Low-value type: CORROBORATES
EdgeTypeScore(
    type="CORROBORATES",
    usage_count=1,
    bridge_score=0.02,
    trend_score=-0.20,
    grounding_contribution=0.02,      # Minimal impact (only 1 edge)
    synonym_cluster_size=4,           # Redundant with SUPPORTS cluster
    avg_confidence=0.78,
    semantic_diversity=0.12,          # Very close to SUPPORTS (0.91 similarity)
    value_score=0.18                  # LOW VALUE - MERGE CANDIDATE
)
```

### Grounding Contribution Calculation

```python
def calculate_grounding_contribution(edge_type: str, age_client) -> float:
    """
    Measure how much this edge type contributes to grounding across all concepts.

    High contribution = valuable for truth convergence
    Low contribution = candidate for pruning

    Algorithm:
    1. Find all concepts with edges of this type
    2. For each concept, calculate grounding WITH and WITHOUT this type
    3. Sum the absolute deltas
    4. Normalize by number of concepts

    Returns:
        Float 0.0-1.0 indicating grounding contribution
    """
    # Find concepts with this edge type
    query = f"""
    MATCH (c:Concept)<-[r:{edge_type}]-()
    RETURN DISTINCT c.concept_id as concept_id
    """
    concepts = age_client._execute_cypher(query)

    if not concepts:
        return 0.0  # No edges = no contribution

    total_delta = 0.0

    for concept in concepts:
        concept_id = concept["concept_id"]

        # Calculate grounding WITH this edge type
        grounding_with = calculate_grounding_strength_semantic(
            concept_id,
            include_types=[edge_type]
        )["grounding_strength"]

        # Calculate grounding WITHOUT this edge type
        grounding_without = calculate_grounding_strength_semantic(
            concept_id,
            exclude_types=[edge_type]
        )["grounding_strength"]

        # How much does this edge type affect grounding?
        delta = abs(grounding_with - grounding_without)
        total_delta += delta

    # Average delta across all concepts
    avg_contribution = total_delta / len(concepts)

    # Normalize to [0.0, 1.0]
    # Delta of 0.5 or more = maximum contribution
    return min(1.0, avg_contribution * 2.0)
```

**Example:**

```python
# SUPPORTS: High contribution
calculate_grounding_contribution("SUPPORTS")
# 38 concepts affected
# Average delta: 0.47 (removing SUPPORTS drops grounding by 47% on average)
# → 0.94 contribution (critical!)

# RELATED_TO: Low contribution
calculate_grounding_contribution("RELATED_TO")
# 23 concepts affected
# Average delta: 0.02 (removing RELATED_TO barely affects grounding)
# → 0.04 contribution (not important for truth)
```

### Embedding-Based Synonym Detection

**Replace string similarity with embedding similarity:**

```python
def find_synonym_clusters(
    age_client,
    similarity_threshold: float = 0.85,
    min_cluster_size: int = 2
) -> List[SynonymCluster]:
    """
    Cluster vocabulary types by embedding similarity.

    Uses semantic embeddings (ADR-045) instead of string matching.
    Detects synonyms even with different words.

    Args:
        age_client: Database client with embedding access
        similarity_threshold: Cosine similarity threshold (default 0.85)
        min_cluster_size: Minimum cluster size to return (default 2)

    Returns:
        List of synonym clusters, each with canonical type and variants
    """
    # Get all active vocabulary types
    types = age_client.get_all_edge_types(include_inactive=False)

    # Build similarity matrix using embeddings
    similarity_matrix = {}

    for type_a in types:
        emb_a = age_client.get_vocabulary_embedding(type_a)["embedding"]

        for type_b in types:
            if type_a == type_b:
                continue

            emb_b = age_client.get_vocabulary_embedding(type_b)["embedding"]

            # Calculate cosine similarity
            similarity = cosine_similarity(emb_a, emb_b)

            if similarity >= similarity_threshold:
                if type_a not in similarity_matrix:
                    similarity_matrix[type_a] = []
                similarity_matrix[type_a].append((type_b, similarity))

    # Cluster types by mutual similarity
    clusters = []
    processed = set()

    for type_a, neighbors in similarity_matrix.items():
        if type_a in processed:
            continue

        # Build cluster
        cluster_members = {type_a}
        for type_b, sim in neighbors:
            cluster_members.add(type_b)
            processed.add(type_b)

        if len(cluster_members) >= min_cluster_size:
            clusters.append(SynonymCluster(
                members=list(cluster_members),
                canonical=select_canonical_type(cluster_members, age_client)
            ))

        processed.add(type_a)

    return clusters

def select_canonical_type(cluster: Set[str], age_client) -> str:
    """
    Select the canonical (preferred) type from a synonym cluster.

    Scoring criteria (in order of priority):
    1. Builtin types win (protected)
    2. Highest grounding contribution
    3. Highest usage count
    4. Alphabetically first (tiebreaker)
    """
    scores = []

    for edge_type in cluster:
        info = age_client.get_edge_type_info(edge_type)

        score = {
            "type": edge_type,
            "is_builtin": info["is_builtin"],
            "usage": info["edge_count"],
            "grounding": calculate_grounding_contribution(edge_type, age_client),
            "total": 0
        }

        # Builtin types massively weighted (ensure they win)
        if score["is_builtin"]:
            score["total"] += 10000

        # Grounding contribution (most important for non-builtins)
        score["total"] += score["grounding"] * 1000

        # Usage count
        score["total"] += score["usage"] * 10

        # Alphabetical tiebreaker (negative score for earlier letters)
        score["total"] -= ord(edge_type[0])

        scores.append(score)

    # Return highest-scoring type
    return max(scores, key=lambda x: x["total"])["type"]
```

**Example clustering:**

```python
clusters = find_synonym_clusters(age_client, similarity_threshold=0.85)

# Result:
[
    SynonymCluster(
        canonical="SUPPORTS",  # Builtin, highest grounding (0.92)
        members=["SUPPORTS", "CORROBORATES", "VALIDATES", "CONFIRMS", "SUBSTANTIATES"],
        avg_similarity=0.88
    ),
    SynonymCluster(
        canonical="ENABLES",   # Builtin, high usage (21 edges)
        members=["ENABLES", "FACILITATES", "ALLOWS", "PERMITS"],
        avg_similarity=0.87
    ),
    SynonymCluster(
        canonical="CONTRADICTS",  # Builtin
        members=["CONTRADICTS", "REFUTES", "OPPOSES", "CONFLICTS_WITH"],
        avg_similarity=0.86
    )
]
```

### Dynamic LLM Vocabulary Curation

**Problem:** Showing all 200 types to LLM causes cognitive overload.

**Solution:** Curate a relevant subset (40-50 types) for each extraction.

```python
def get_extraction_vocabulary(
    document_context: Optional[str] = None,
    max_types: int = 50,
    min_grounding: float = 0.3,
    age_client = None
) -> List[str]:
    """
    Return a curated vocabulary subset for LLM extraction prompts.

    Selection criteria:
    1. High grounding contribution (truth-critical types)
    2. High usage frequency (proven utility)
    3. Semantic diversity (avoid near-duplicates)
    4. Document relevance (if context provided)

    Args:
        document_context: Optional document text for relevance scoring
        max_types: Maximum types to return (default 50)
        min_grounding: Minimum grounding contribution to consider (default 0.3)
        age_client: Database client

    Returns:
        List of edge type names, curated for LLM prompt
    """
    # Get all active types with scores
    all_types = age_client.get_all_edge_types(include_inactive=False)

    scored_types = []

    for edge_type in all_types:
        info = age_client.get_edge_type_info(edge_type)

        # Calculate composite score
        score = 0.0

        # Grounding contribution (50% weight)
        grounding = calculate_grounding_contribution(edge_type, age_client)
        if grounding < min_grounding and not info["is_builtin"]:
            continue  # Skip low-grounding non-builtins
        score += grounding * 0.50

        # Usage frequency (30% weight)
        usage_normalized = min(1.0, info["edge_count"] / 50)
        score += usage_normalized * 0.30

        # Semantic diversity (20% weight)
        diversity = calculate_semantic_diversity(edge_type, all_types, age_client)
        score += diversity * 0.20

        # Document relevance (if context provided)
        if document_context:
            relevance = calculate_document_relevance(edge_type, document_context)
            score *= (1.0 + relevance)  # Boost score by relevance

        scored_types.append({
            "type": edge_type,
            "score": score,
            "is_builtin": info["is_builtin"]
        })

    # Sort by score descending
    scored_types.sort(key=lambda x: (x["is_builtin"], x["score"]), reverse=True)

    # Apply diversity filter to avoid near-duplicates
    curated = diversity_filter(scored_types, max_types, age_client)

    return [t["type"] for t in curated]

def diversity_filter(
    scored_types: List[Dict],
    max_types: int,
    age_client,
    min_similarity_distance: float = 0.15
) -> List[Dict]:
    """
    Filter to ensure semantic diversity (avoid showing synonyms together).

    If SUPPORTS is included, don't also include CORROBORATES, VALIDATES, etc.
    """
    selected = []

    for candidate in scored_types:
        if len(selected) >= max_types:
            break

        # Check if too similar to already-selected types
        too_similar = False
        candidate_emb = age_client.get_vocabulary_embedding(candidate["type"])["embedding"]

        for selected_type in selected:
            selected_emb = age_client.get_vocabulary_embedding(selected_type["type"])["embedding"]
            similarity = cosine_similarity(candidate_emb, selected_emb)

            # If very similar (>0.85), skip this candidate
            if similarity > (1.0 - min_similarity_distance):
                too_similar = True
                break

        if not too_similar:
            selected.append(candidate)

    return selected
```

**Example output:**

```python
# All 64 types in vocabulary (with synonyms)
all_types = ["SUPPORTS", "CORROBORATES", "VALIDATES", "CONFIRMS", ...]

# Curated subset for LLM (semantic diversity, high value)
curated = get_extraction_vocabulary(max_types=40)
# → ["SUPPORTS", "CONTRADICTS", "ENABLES", "REQUIRES", "IMPLIES",
#     "PART_OF", "RESULTS_FROM", "INFLUENCES", ...] (40 types)
#
# Notable: CORROBORATES, VALIDATES, CONFIRMS excluded (synonyms of SUPPORTS)
```

### Grounding-Aware Merge Recommendations

**Enhanced merge recommendation algorithm:**

```python
def generate_merge_recommendations(
    vocab_size: int,
    age_client
) -> List[MergeRecommendation]:
    """
    Generate merge recommendations with grounding awareness.

    Priority formula:
    - High similarity (>0.85) + low grounding contribution = high priority
    - High similarity + high grounding contribution = manual review
    - Low similarity = no merge (preserve semantic diversity)
    """
    aggressiveness = calculate_aggressiveness(vocab_size)

    if aggressiveness == 0.0:
        return []  # Safe zone - no merging

    # Find synonym clusters
    clusters = find_synonym_clusters(age_client, similarity_threshold=0.85)

    recommendations = []

    for cluster in clusters:
        canonical = cluster.canonical

        for member in cluster.members:
            if member == canonical:
                continue  # Don't merge canonical into itself

            # Get grounding contribution for deprecated type
            deprecated_grounding = calculate_grounding_contribution(member, age_client)
            canonical_grounding = calculate_grounding_contribution(canonical, age_client)

            # Calculate merge priority
            priority = calculate_merge_priority(
                deprecated=member,
                canonical=canonical,
                deprecated_grounding=deprecated_grounding,
                canonical_grounding=canonical_grounding,
                aggressiveness=aggressiveness
            )

            # Determine review level
            if priority > 0.9:
                review = "auto"  # Very high confidence - auto-approve
            elif deprecated_grounding > 0.5:
                review = "hitl"  # High grounding impact - human review
            else:
                review = "aitl"  # Medium confidence - AI review

            recommendations.append(MergeRecommendation(
                action="merge",
                deprecated_type=member,
                canonical_type=canonical,
                similarity=cluster.avg_similarity,
                deprecated_grounding=deprecated_grounding,
                canonical_grounding=canonical_grounding,
                priority=priority,
                review_level=review,
                reason=generate_merge_reason(member, canonical, cluster)
            ))

    return sorted(recommendations, key=lambda x: x.priority, reverse=True)

def calculate_merge_priority(
    deprecated: str,
    canonical: str,
    deprecated_grounding: float,
    canonical_grounding: float,
    aggressiveness: float
) -> float:
    """
    Calculate merge priority (0.0-1.0).

    High priority = should merge immediately
    Low priority = preserve diversity
    """
    priority = 0.0

    # Base priority from aggressiveness
    priority += aggressiveness * 0.3

    # Low usage of deprecated type (high priority to merge)
    deprecated_info = age_client.get_edge_type_info(deprecated)
    if deprecated_info["edge_count"] < 5:
        priority += 0.3

    # Grounding contribution delta
    # If canonical has much higher grounding, merge is safer
    grounding_delta = canonical_grounding - deprecated_grounding
    if grounding_delta > 0.3:
        priority += 0.2
    elif deprecated_grounding > 0.5:
        # Deprecated has high grounding - be cautious
        priority -= 0.2

    # Inverse relationship (SUPPORTED_BY → SUPPORTS)
    if is_inverse_relationship(deprecated, canonical):
        priority += 0.2  # High priority - clear redundancy

    return max(0.0, min(1.0, priority))
```

**Example recommendations:**

```python
# At vocab_size=64 (safe zone, aggressiveness=0.0)
recommendations = generate_merge_recommendations(64, age_client)
# → []  (no recommendations in safe zone)

# At vocab_size=120 (active zone, aggressiveness=0.4)
recommendations = generate_merge_recommendations(120, age_client)
# → [
#     MergeRecommendation(
#         deprecated="SUPPORTED_BY",
#         canonical="SUPPORTS",
#         similarity=0.94,
#         deprecated_grounding=0.02,
#         canonical_grounding=0.92,
#         priority=0.87,
#         review_level="auto",
#         reason="Inverse relationship with high similarity"
#     ),
#     MergeRecommendation(
#         deprecated="ENABLED_BY",
#         canonical="ENABLES",
#         similarity=0.92,
#         deprecated_grounding=0.04,
#         canonical_grounding=0.71,
#         priority=0.83,
#         review_level="auto",
#         reason="Inverse relationship with high similarity"
#     )
# ]

# At vocab_size=190 (critical zone, aggressiveness=0.9)
recommendations = generate_merge_recommendations(190, age_client)
# → Many more recommendations, including:
#     - CORROBORATES → SUPPORTS (similarity 0.91)
#     - VALIDATES → SUPPORTS (similarity 0.88)
#     - CONFIRMS → SUPPORTS (similarity 0.87)
#     - FACILITATES → ENABLES (similarity 0.89)
```

## Implementation

### Phase 1: Enhanced Scoring (Week 1)

**1. Extend `EdgeTypeScore` dataclass**

File: `src/api/lib/vocabulary_scoring.py`

Add new fields:
- `grounding_contribution: float`
- `synonym_cluster_size: int`
- `avg_confidence: float`
- `semantic_diversity: float`

**2. Implement grounding contribution calculation**

File: `src/api/lib/vocabulary_scoring.py`

```python
def calculate_grounding_contribution(
    edge_type: str,
    age_client
) -> float:
    """Calculate grounding contribution for edge type."""
    # Implementation from Decision section above
```

**3. Update `VocabularyScorer.score_edge_types()`**

Calculate all new metrics for each edge type.

### Phase 2: Embedding-Based Synonym Detection (Week 2)

**1. Implement synonym clustering**

File: `src/api/lib/synonym_detector.py`

Update to use embeddings instead of string similarity:

```python
def detect_synonyms_semantic(
    age_client,
    similarity_threshold: float = 0.85
) -> List[SynonymCandidate]:
    """
    Detect synonyms using embedding similarity (ADR-045).

    Replaces string-based detection with semantic similarity.
    """
    # Implementation from Decision section above
```

**2. Implement canonical type selection**

```python
def select_canonical_type(
    cluster: Set[str],
    age_client
) -> str:
    """Select canonical type from synonym cluster."""
    # Implementation from Decision section above
```

### Phase 3: Dynamic Vocabulary Curation (Week 3)

**1. Implement vocabulary subset selection**

File: `src/api/lib/vocabulary_curator.py` (new)

```python
def get_extraction_vocabulary(
    document_context: Optional[str] = None,
    max_types: int = 50,
    min_grounding: float = 0.3,
    age_client = None
) -> List[str]:
    """Curate vocabulary subset for LLM extraction."""
    # Implementation from Decision section above
```

**2. Update extraction prompt to use curated vocabulary**

File: `src/api/lib/llm_extractor.py`

```python
# Current (shows all types)
formatted_prompt = EXTRACTION_PROMPT_TEMPLATE.format(
    relationship_types=RELATIONSHIP_TYPES_LIST
)

# Updated (shows curated subset)
curated_types = get_extraction_vocabulary(
    document_context=text[:1000],  # First 1000 chars for context
    max_types=50,
    age_client=age_client
)
formatted_prompt = EXTRACTION_PROMPT_TEMPLATE.format(
    relationship_types=", ".join(curated_types)
)
```

### Phase 4: Grounding-Aware Merge Recommendations (Week 4)

**1. Update merge recommendation algorithm**

File: `src/api/lib/pruning_strategies.py`

```python
def generate_recommendations_grounding_aware(
    vocab_size: int,
    age_client
) -> List[ActionRecommendation]:
    """Generate merge recommendations with grounding awareness."""
    # Implementation from Decision section above
```

**2. Update merge execution to preserve embeddings**

File: `src/api/lib/age_client.py`

Update `merge_edge_types()` to handle embeddings (per ADR-045):

```python
def merge_edge_types(
    self,
    deprecated_type: str,
    target_type: str,
    performed_by: str = "system"
) -> Dict[str, int]:
    """Merge edge types with embedding management."""
    # Existing graph edge update logic...

    # NEW: Ensure target has embedding
    if not self.get_vocabulary_embedding(target_type):
        worker = EmbeddingWorker(get_provider(), self)
        worker.generate_vocabulary_embedding(target_type)

    # Preserve deprecated embedding for rollback
    # (mark as inactive, don't delete)

    # ... rest of existing logic
```

### Phase 5: Admin Endpoints (Week 5)

**1. Vocabulary analysis endpoint**

File: `src/api/routes/vocabulary.py`

```python
@router.get("/vocab/analysis")
async def analyze_vocabulary():
    """
    Analyze vocabulary with grounding metrics.

    Returns:
        - Synonym clusters
        - Grounding contribution scores
        - Merge recommendations
        - Vocabulary health metrics
    """
    age_client = get_age_client()

    # Find synonym clusters
    clusters = find_synonym_clusters(age_client)

    # Score all types
    scorer = VocabularyScorer(age_client)
    scores = scorer.score_all_types()

    # Generate recommendations
    recommendations = generate_merge_recommendations(
        vocab_size=len(scores),
        age_client=age_client
    )

    return {
        "vocab_size": len(scores),
        "synonym_clusters": clusters,
        "top_contributors": [s for s in scores if s.grounding_contribution > 0.5],
        "merge_recommendations": recommendations
    }
```

**2. CLI command**

File: `client/src/cli/vocab.ts`

```bash
kg vocab analyze
# Shows:
# - Current vocabulary size
# - Synonym clusters
# - Grounding contribution scores
# - Merge recommendations
```

## Consequences

### Positive

✅ **Prevents grounding dilution** - Synonym clustering preserves semantic meaning
✅ **Protects high-value types** - Truth-critical types protected from pruning
✅ **Scales with vocabulary growth** - Embedding-based approach handles any size
✅ **Reduces LLM confusion** - Dynamic curation shows relevant subset only
✅ **Automatic synonym detection** - No manual classification needed
✅ **Grounding-aware decisions** - Pruning/merging considers truth impact
✅ **Future-proof** - Works with any embedding model (ADR-045)

### Negative

⚠️ **Computational overhead** - Grounding contribution calculation is expensive
⚠️ **Merge complexity** - Need to handle embeddings, graph edges, and history
⚠️ **Requires ADR-044/045** - Cannot implement independently
⚠️ **Operator learning curve** - New metrics to understand (grounding contribution)

### Trade-offs

**Computation vs Accuracy**
- **More computation:** Grounding contribution requires re-calculating grounding for many concepts
- **Better accuracy:** Merging based on semantic meaning + truth impact
- **Mitigation:** Cache grounding contribution scores, recalculate periodically

**Automation vs Control**
- **More automation:** Embedding-based synonym detection finds clusters automatically
- **Less operator control:** May merge types operator wants separate
- **Mitigation:** HITL review level for high-grounding types

**Vocabulary Size vs Extraction Quality**
- **Smaller vocabulary:** Better LLM extraction (less confusion)
- **Less semantic granularity:** Nuanced relationships lost
- **Mitigation:** Dynamic curation preserves diversity while limiting size

## Related Decisions

**Dependency chain:**
```
ADR-045 (Embeddings)
    ↓
ADR-044 (Grounding)
    ↓
ADR-046 (Management) ← This ADR
```

**Extends:**
- **ADR-032:** Automatic Edge Vocabulary Expansion (adds grounding awareness)

**Enables:**
- **ADR-044:** Probabilistic Truth Convergence (protects grounding from dilution)

**Requires:**
- **ADR-045:** Unified Embedding Generation (for semantic similarity)

## Validation & Testing

### Test Scenarios

**1. Synonym Detection**
- Create types: SUPPORTS, CORROBORATES, VALIDATES
- Run synonym detection
- Verify: All clustered together (similarity >0.85)
- Verify: SUPPORTS selected as canonical (builtin, highest grounding)

**2. Grounding Contribution**
- Create concept with 10 SUPPORTS edges
- Calculate grounding contribution for SUPPORTS
- Remove SUPPORTS edges, recalculate
- Verify: Contribution score reflects grounding delta

**3. Dynamic Vocabulary Curation**
- Vocabulary size: 150 types
- Request curated subset (max 50)
- Verify: High-grounding types included
- Verify: Near-synonyms excluded (semantic diversity)

**4. Merge Recommendation Priorities**
- Vocab size: 120 (active zone, aggressiveness=0.4)
- Generate recommendations
- Verify: Inverse pairs (SUPPORTED_BY → SUPPORTS) have high priority
- Verify: High-grounding types require HITL review

**5. Grounding Preservation After Merge**
- Concept has 5 CORROBORATES edges (grounding=0.80)
- Merge CORROBORATES → SUPPORTS
- Recalculate grounding
- Verify: Grounding preserved (still ~0.80)

### Success Criteria

- [ ] Grounding contribution accurately reflects truth impact
- [ ] Synonym clustering finds semantically similar types
- [ ] Canonical selection prefers builtins and high-grounding types
- [ ] Dynamic curation limits LLM prompt to 40-50 diverse types
- [ ] Merge recommendations prioritize low-impact, high-similarity types
- [ ] Grounding strength preserved after synonym consolidation

## Implementation Status

**Prerequisites:**
- [ ] ADR-045 Phase 1: EmbeddingWorker (must complete first)
- [ ] ADR-044 Phase 1: Grounding calculation (must complete first)

**ADR-046 Implementation:**
- [ ] Phase 1: Enhanced scoring with grounding metrics
- [ ] Phase 2: Embedding-based synonym detection
- [ ] Phase 3: Dynamic vocabulary curation
- [ ] Phase 4: Grounding-aware merge recommendations
- [ ] Phase 5: Admin endpoints and CLI commands

**Next Steps:**
1. Complete ADR-045 (embeddings) and ADR-044 (grounding) first
2. Extend `EdgeTypeScore` with grounding metrics
3. Implement grounding contribution calculation
4. Update synonym detection to use embeddings
5. Integrate with ADR-047 category-based synonym detection
6. Test with production vocabulary (64 types)

## References

- **ADR-044:** Probabilistic Truth Convergence (grounding strength calculation)
- **ADR-045:** Unified Embedding Generation (embeddings for all vocabulary types)
- **ADR-032:** Automatic Edge Vocabulary Expansion (pruning weak types)
- **ADR-047:** Probabilistic Vocabulary Categorization (category-based synonym detection)
- **ADR-022:** Semantic Relationship Taxonomy (8 categories)

---

**Last Updated:** 2025-10-27
**Next Review:** After ADR-044/045/047 implementation
