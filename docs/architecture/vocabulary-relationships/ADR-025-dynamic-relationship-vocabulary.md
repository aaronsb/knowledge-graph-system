# ADR-025: Dynamic Relationship Vocabulary Management

**Status:** Proposed
**Date:** 2025-10-10
**Deciders:** System Architects
**Related:** ADR-024 (Multi-Schema PostgreSQL Architecture), ADR-004 (Pure Graph Design)

## Context

During ingestion, the LLM extraction process produces relationship types that don't match our fixed vocabulary of 30 approved types. These relationships are currently skipped with warnings, resulting in lost semantic connections.

### Current Problem

**Fixed Vocabulary Limitation:**
```python
ALLOWED_RELATIONSHIP_TYPES = {
    'IMPLIES', 'SUPPORTS', 'CONTRADICTS', 'RESULTS_FROM', 'ENABLES',
    'REQUIRES', 'INFLUENCES', 'COMPLEMENTS', 'OVERLAPS', 'EXTENDS',
    # ... 20 more
}
```

**Lost Relationships (from actual ingestion):**
```
⚠ Skipping relationship: invalid type 'ENHANCES' (no match)
⚠ Skipping relationship: invalid type 'INTEGRATES' (no match)
⚠ Skipping relationship: invalid type 'CONNECTS_TO' (no match)
⚠ Skipping relationship: invalid type 'ALIGNS_WITH' (no match)
⚠ Skipping relationship: invalid type 'PROVIDES' (no match)
⚠ Skipping relationship: invalid type 'RECEIVES' (no match)
⚠ Skipping relationship: invalid type 'POWERS' (no match)
⚠ Skipping relationship: invalid type 'EMBEDDED_IN' (no match)
⚠ Skipping relationship: invalid type 'CONTRIBUTES_TO' (no match)
⚠ Skipping relationship: invalid type 'ENABLED_BY' (no match)
⚠ Skipping relationship: invalid type 'MAINTAINS' (no match)
⚠ Skipping relationship: invalid type 'SCALES_WITH' (no match)
⚠ Skipping relationship: invalid type 'FOCUSES_ON' (no match)
⚠ Skipping relationship: invalid type 'ENSURES' (no match)
⚠ Skipping relationship: invalid type 'FEEDS' (no match)
⚠ Skipping relationship: invalid type 'INFORMS' (no match)
⚠ Skipping relationship: invalid type 'VALIDATES' (no match)
```

Many of these are semantically valid and would enrich the knowledge graph (e.g., ENHANCES, INTEGRATES, CONTRIBUTES_TO).

### Why Fixed Vocabulary Exists

From ADR-004 (Pure Graph Design):
- Prevents vocabulary explosion (LLMs can produce hundreds of variants)
- Ensures semantic consistency across ingestions
- Enables reliable graph traversal and queries
- Maintains interpretability of relationship types

## Decision

Implement a **two-tier dynamic relationship vocabulary system**:

1. **Capture Layer** - Record all skipped relationships for analysis
2. **Vocabulary Management** - Curator-approved expansion of relationship types

### Architecture Components

#### 1. Skipped Relationships Table (PostgreSQL `kg_api` schema)

Track all relationships that didn't match the approved vocabulary:

```sql
CREATE TABLE kg_api.skipped_relationships (
    id SERIAL PRIMARY KEY,
    relationship_type VARCHAR(100) NOT NULL,
    from_concept_label VARCHAR(500),
    to_concept_label VARCHAR(500),
    job_id VARCHAR(50),
    ontology VARCHAR(200),
    first_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    occurrence_count INTEGER DEFAULT 1,
    sample_context JSONB,  -- Store example {"from": "...", "to": "...", "confidence": ...}
    UNIQUE(relationship_type, from_concept_label, to_concept_label)
);

CREATE INDEX idx_skipped_rels_type ON kg_api.skipped_relationships(relationship_type);
CREATE INDEX idx_skipped_rels_count ON kg_api.skipped_relationships(occurrence_count DESC);
CREATE INDEX idx_skipped_rels_first_seen ON kg_api.skipped_relationships(first_seen DESC);
```

#### 2. Relationship Vocabulary Table (PostgreSQL `kg_api` schema)

Centralized, version-controlled relationship vocabulary:

```sql
CREATE TABLE kg_api.relationship_vocabulary (
    relationship_type VARCHAR(100) PRIMARY KEY,
    description TEXT,
    category VARCHAR(50),  -- e.g., 'causation', 'composition', 'temporal', 'semantic'
    added_by VARCHAR(100),  -- User or system that approved it
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    usage_count INTEGER DEFAULT 0,  -- Count of edges using this type
    is_active BOOLEAN DEFAULT TRUE,
    is_builtin BOOLEAN DEFAULT FALSE,  -- Original 30 types
    synonyms VARCHAR(100)[]  -- Alternative terms that map to this type
);

-- Initialize with existing 30 types
INSERT INTO kg_api.relationship_vocabulary (relationship_type, is_builtin, category, description)
VALUES
    ('IMPLIES', TRUE, 'logical', 'One concept logically implies another'),
    ('SUPPORTS', TRUE, 'evidential', 'One concept provides evidence for another'),
    ('CONTRADICTS', TRUE, 'logical', 'One concept contradicts another'),
    -- ... etc
;
```

#### 3. Relationship Mapping (Synonym Support)

Allow mapping similar terms to canonical types:

```sql
-- Example: Map 'ENHANCES' and 'IMPROVES' to 'SUPPORTS'
UPDATE kg_api.relationship_vocabulary
SET synonyms = ARRAY['ENHANCES', 'IMPROVES', 'STRENGTHENS']
WHERE relationship_type = 'SUPPORTS';

-- Or add as new canonical type:
INSERT INTO kg_api.relationship_vocabulary (relationship_type, category, description)
VALUES ('ENHANCES', 'augmentation', 'One concept enhances or improves another');
```

### Workflow

#### During Ingestion

```python
def upsert_relationship(from_id, to_id, rel_type, confidence):
    # 1. Check if type is in approved vocabulary
    if rel_type in get_approved_vocabulary():
        create_graph_edge(from_id, to_id, rel_type, confidence)
    else:
        # 2. Check if it's a known synonym
        canonical_type = get_canonical_type(rel_type)
        if canonical_type:
            create_graph_edge(from_id, to_id, canonical_type, confidence)
        else:
            # 3. Log to skipped_relationships for review
            record_skipped_relationship(
                rel_type=rel_type,
                from_label=get_concept_label(from_id),
                to_label=get_concept_label(to_id),
                context={'confidence': confidence, 'job_id': current_job_id}
            )
```

#### Vocabulary Expansion (Curator Process)

```bash
# CLI command to review skipped relationships
kg vocabulary review

# Output:
# Top Skipped Relationship Types:
# 1. ENHANCES (127 occurrences across 15 documents)
#    Example: "Advanced Analytics" ENHANCES "Decision Making"
# 2. INTEGRATES (89 occurrences across 12 documents)
#    Example: "API Layer" INTEGRATES "Data Pipeline"
# ...

# Approve a new relationship type
kg vocabulary add ENHANCES --category augmentation --description "One concept enhances another"

# Or map to existing type
kg vocabulary alias ENHANCES --maps-to SUPPORTS
```

#### Backfill Process

When a new relationship type is approved, optionally backfill:

```python
def backfill_relationship_type(rel_type):
    """
    Find all skipped instances of this relationship type and create edges.
    """
    skipped = get_skipped_by_type(rel_type)

    for skip in skipped:
        # Find concepts by label (fuzzy match if needed)
        from_id = find_concept_by_label(skip.from_concept_label)
        to_id = find_concept_by_label(skip.to_concept_label)

        if from_id and to_id:
            create_graph_edge(from_id, to_id, rel_type, confidence=0.8)
```

### Integration with ADR-024

Add to `kg_api` schema in ADR-024:

```sql
-- Relationship vocabulary management
CREATE TABLE kg_api.skipped_relationships (...);
CREATE TABLE kg_api.relationship_vocabulary (...);
```

This fits the schema's purpose: "API state (jobs, sessions, rate limits - ephemeral, write-heavy)"

Skipped relationships are ephemeral metadata that informs vocabulary curation.

## Decision Rationale

### Why This Approach

1. **Data-Driven Vocabulary Growth**
   - Track actual usage patterns from LLM extraction
   - Identify frequently occurring relationship types
   - Prioritize vocabulary expansion based on real needs

2. **Maintain Quality Control**
   - Curator approval prevents vocabulary explosion
   - Synonym mapping reduces redundancy
   - Category organization maintains semantic structure

3. **No Data Loss**
   - All skipped relationships are recorded
   - Backfill capability when types are approved
   - Audit trail of vocabulary evolution

4. **Performance**
   - PostgreSQL tables (not graph) for fast aggregation
   - Indexed by type and occurrence count
   - Vocabulary lookup is O(1) hash table in memory

### Alternatives Considered

#### 1. Automatic Vocabulary Expansion
- **Rejected:** Would lead to uncontrolled vocabulary explosion
- LLMs can produce hundreds of similar types (ENHANCES, IMPROVES, AUGMENTS, BOOSTS, etc.)
- Breaks graph query consistency

#### 2. LLM-Based Synonym Mapping
- **Rejected for now:** Adds latency and cost to ingestion
- Could be added later as a batch process
- Example: Ask LLM "Is ENHANCES semantically similar to SUPPORTS?"

#### 3. Keep Fixed Vocabulary Forever
- **Rejected:** Loses valuable semantic information
- Domain-specific knowledge graphs need domain-specific relationships
- System should adapt to actual usage patterns

## Implementation Plan

### Phase 1: Capture Infrastructure (Week 1)

1. Create PostgreSQL tables in `kg_api` schema
2. Update `upsert_relationship()` to log skipped relationships
3. Add aggregation queries for vocabulary analysis

### Phase 2: CLI Tools (Week 1-2)

1. `kg vocabulary review` - Show top skipped types
2. `kg vocabulary add` - Approve new relationship type
3. `kg vocabulary alias` - Map synonym to canonical type
4. `kg vocabulary stats` - Usage statistics

### Phase 3: Backfill & Migration (Week 2)

1. Backfill tool to create edges for approved types
2. Migration script to populate initial 30 types
3. Documentation and curator guidelines

### Phase 4: Performance Optimization - Edge Usage Cache (Future)

Track frequently traversed edges for performance optimization:

```sql
CREATE TABLE kg_api.edge_usage_stats (
    from_concept_id VARCHAR(100),
    to_concept_id VARCHAR(100),
    relationship_type VARCHAR(100),
    traversal_count INTEGER DEFAULT 0,
    last_traversed TIMESTAMPTZ,
    avg_query_time_ms NUMERIC(10,2),
    PRIMARY KEY (from_concept_id, to_concept_id, relationship_type)
);

CREATE INDEX idx_edge_usage_count ON kg_api.edge_usage_stats(traversal_count DESC);
CREATE INDEX idx_edge_usage_type ON kg_api.edge_usage_stats(relationship_type);

-- Hot paths cache (top 1000 most frequently traversed edges)
CREATE MATERIALIZED VIEW kg_api.hot_edges AS
SELECT from_concept_id, to_concept_id, relationship_type, traversal_count
FROM kg_api.edge_usage_stats
WHERE traversal_count > 100
ORDER BY traversal_count DESC
LIMIT 1000;

CREATE INDEX idx_hot_edges_lookup ON kg_api.hot_edges(from_concept_id, to_concept_id);
```

**Concept Access Tracking:**
```sql
-- Track node-level access patterns for pre-routing and caching
CREATE TABLE kg_api.concept_access_stats (
    concept_id VARCHAR(100) PRIMARY KEY,
    access_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMPTZ,
    avg_query_time_ms NUMERIC(10,2),
    queries_as_start INTEGER DEFAULT 0,  -- How often used as query starting point
    queries_as_result INTEGER DEFAULT 0  -- How often appears in query results
);

CREATE INDEX idx_concept_access_count ON kg_api.concept_access_stats(access_count DESC);

-- Hot concepts cache (top 100 most-accessed concepts)
CREATE MATERIALIZED VIEW kg_api.hot_concepts AS
SELECT concept_id, access_count, queries_as_start
FROM kg_api.concept_access_stats
WHERE access_count > 50
ORDER BY access_count DESC
LIMIT 100;
```

**Use Cases:**
- **Pre-load hot concepts** into application memory cache
- **Pre-route queries** starting from popular concepts (fast path)
- **Identify trending concepts** for async insight processing
- **Optimize query planning** by prioritizing frequently accessed nodes
- **Detect query patterns** for index optimization
- **Smart caching** based on actual usage, not time

**Low-Overhead Collection:**
```python
async def track_concept_access(concept_id: str, query_type: str):
    """
    Non-blocking access tracking - fire and forget.
    Every query collects stats without performance impact.
    """
    # Async upsert (doesn't block query execution)
    asyncio.create_task(
        db.execute(f"""
            INSERT INTO kg_api.concept_access_stats (concept_id, access_count, queries_as_{query_type})
            VALUES ('{concept_id}', 1, 1)
            ON CONFLICT (concept_id) DO UPDATE SET
                access_count = concept_access_stats.access_count + 1,
                last_accessed = NOW(),
                queries_as_{query_type} = concept_access_stats.queries_as_{query_type} + 1
        """)
    )

# Usage in queries:
async def search_concepts(query):
    results = await execute_search(query)
    for result in results:
        track_concept_access(result.concept_id, 'result')  # Fire and forget
    return results

async def find_related(concept_id):
    track_concept_access(concept_id, 'start')  # Track starting point
    return await execute_traversal(concept_id)
```

**Example Query Optimization:**
```python
def find_related_concepts(concept_id, max_depth=2):
    # 1. Check hot edges cache first (in-memory Redis/dict)
    cached_neighbors = get_hot_edges_from_cache(concept_id)
    if cached_neighbors and max_depth == 1:
        return cached_neighbors  # Fast path!

    # 2. Fall back to full graph traversal
    return execute_graph_query(concept_id, max_depth)
```

### Phase 5: Advanced Vocabulary Features (Future)

1. LLM-assisted synonym detection (batch process)
2. Relationship type embeddings for similarity search
3. Auto-suggest synonyms during approval
4. Relationship type analytics dashboard
5. Edge materialized views for common query patterns

## Monitoring & Metrics

### Key Metrics

1. **Vocabulary Growth Rate**
   - New types approved per month
   - Ratio of builtin vs. custom types

2. **Coverage Rate**
   - % of extracted relationships that match vocabulary
   - % of relationships skipped

3. **Backfill Impact**
   - Edges created through backfill
   - Concept connectivity improvements

4. **Type Usage Distribution**
   - Most/least used relationship types
   - Identify candidates for deprecation

### Alerts

- Alert if skipped relationship rate > 30%
- Alert if new unique types > 100/day (possible extraction issue)
- Alert if vocabulary size > 200 types (over-expansion)

## Vocabulary Pruning & Lifecycle Management

### Problem: Vocabulary Bloat

**Performance Impact:**
- Larger vocabulary → slower synonym lookups during ingestion
- More types to check → increased decision tree complexity
- Noisy graph with rarely-used relationship types

**Solution: Automatic Deprecation Process**

### Natural Freshness via Upsert Mechanism

**Critical Insight: Every ingestion refreshes activation naturally!**

Unlike neural networks where weights decay without explicit training:
- **New document ingestion** → Concept matching via embeddings
- **Concept reuse** → Creates new edges to existing concept
- **Edge creation** → Increments `usage_count` and `traversal_count`
- **Automatic refresh** → Semantically relevant concepts stay active

```python
async def upsert_concept(label, embedding):
    """
    Every concept match refreshes activation - no time-based decay needed!
    """
    # Find existing concept via semantic similarity
    existing = vector_search(embedding, threshold=0.8)

    if existing:
        # REUSE triggers activation refresh
        await track_concept_access(existing.concept_id, 'upsert')
        return existing.concept_id
    else:
        # Create new concept
        return create_concept(label, embedding)

async def create_relationship(from_id, to_id, rel_type):
    """
    Edge creation refreshes both nodes AND relationship type.
    """
    # Create graph edge
    cypher_create_edge(from_id, to_id, rel_type)

    # Refresh activation for BOTH concepts
    await track_concept_access(from_id, 'relationship_source')
    await track_concept_access(to_id, 'relationship_target')

    # Increment relationship type usage
    await increment_vocabulary_usage(rel_type)
```

**Self-Regulating System:**

1. **Foundational concepts stay active**
   - Core ideas appear across many documents
   - Constant matching → constant refresh
   - Example: "machine learning" → always relevant

2. **Obsolete concepts naturally fade**
   - Old/outdated ideas stop appearing in new documents
   - No matches → no refreshes → activation decays organically
   - Example: "floppy disk drivers" → rarely mentioned

3. **Bridge concepts get refreshed**
   - Low-activation bridge to high-activation concept
   - High-activation concept gets new edges
   - Bridge traversal → bridge concept refreshed too

4. **Seasonal concepts cycle naturally**
   - Domain-specific ideas wax and wane with document flow
   - "tax optimization" → high in Q1, low rest of year
   - No artificial time windows needed!

**No Time-Based Decay Required:**
- ❌ Don't prune based on "last_used" timestamp
- ✅ Prune based on structural value (edges × traversals × bridges)
- ✅ Let ingestion patterns determine relevance
- ✅ Trust the graph to self-regulate

### Natural Activation Refresh Loop

```
New Document Ingestion
         ↓
    Extract Concepts
         ↓
Vector Similarity Match ←─────┐
         ↓                     │
    Existing Match?            │
         ↓                     │
    YES → Reuse Concept        │
         ↓                     │
    Create New Edges           │
         ↓                     │
    Increment usage_count ─────┘  [REFRESH LOOP]
         ↓
Both Endpoints Activated
         ↓
    Relationship Type +1
         ↓
Bridge Detection Updated
```

### Key Architectural Properties

**1. Semantic-Based Freshness**
- Relevance = "Does new content reference this concept?"
- Not "When was it last accessed?"
- The corpus drives activation naturally

**2. Zero Configuration**
- No decay parameters to tune
- No time windows to configure
- No manual pruning schedules
- Graph self-regulates through ingestion patterns

**3. Emergent Patterns**
- Foundational concepts → persistent high activation
- Obsolete concepts → gradual natural decay
- Seasonal concepts → organic cyclical patterns
- Bridge concepts → transitive activation via neighbors

**4. Catastrophic Forgetting Prevention**
- Bridge bonus preserves low-activation connectors
- Structural value (topology) > activation alone
- Graph topology "remembers" important paths

**5. Living Knowledge Representation**
- Ideas stay "active" when they appear in new contexts
- Naturally fade when they stop being relevant
- Mirrors how human collective consciousness works
- Self-organizing semantic relevance

### Pruning Strategy

```sql
-- Pruning is value-based, not time-based
-- Find low-value relationship types (bottom of value score ranking)
WITH value_scores AS (
    SELECT
        v.relationship_type,
        v.usage_count as edge_count,
        COALESCE(e.avg_traversal, 0) as avg_traversal,
        -- Value = edges × traversal frequency
        v.usage_count * (1.0 + COALESCE(e.avg_traversal, 0) / 100.0) as value_score
    FROM kg_api.relationship_vocabulary v
    LEFT JOIN (
        SELECT relationship_type, AVG(traversal_count) as avg_traversal
        FROM kg_api.edge_usage_stats
        GROUP BY relationship_type
    ) e ON v.relationship_type = e.relationship_type
    WHERE v.is_builtin = FALSE AND v.is_active = TRUE
)
SELECT * FROM value_scores
ORDER BY value_score ASC  -- Lowest value first (pruning candidates)
LIMIT 10;
```

### Automated Pruning Process

**Triggered when vocabulary exceeds max limit:**
```python
def prune_to_maintain_window():
    """
    Prune lowest-value relationship types when vocabulary exceeds max.
    """
    active_count = count_active_custom_types()

    if active_count > VOCABULARY_WINDOW['max']:
        prune_count = active_count - VOCABULARY_WINDOW['max']

        # Get lowest-value types (structural value, not time-based)
        candidates = get_custom_types_ordered_by_value()  # Ordered by value ASC

        for candidate in candidates[:prune_count]:  # Take bottom N
            # Check if edges exist in graph
            edge_count = count_graph_edges(candidate.relationship_type)

            if edge_count == 0:
                # Zero edges - safe to completely remove
                delete_relationship_type(
                    candidate.relationship_type,
                    reason=f"No structural value (0 edges, 0 traversals)"
                )
            else:
                # Has edges - deactivate but preserve graph integrity
                mark_inactive(
                    candidate.relationship_type,
                    reason=f"Low structural value (score={candidate.value_score:.2f})"
                )
```

**Pruning Levels:**

1. **Deactivation** (is_active = FALSE)
   - Stop accepting new relationships of this type
   - Existing graph edges remain intact
   - Can still query existing data
   - Curator can reactivate if structural importance increases

2. **Removal** (delete from vocabulary)
   - Only if ZERO graph edges exist
   - Only for non-builtin types
   - Automatic when value score = 0

### Reactivation

```bash
# Curator can reactivate if usage pattern changes
kg vocabulary reactivate ENHANCES --reason "New domain requires this type"
```

### Vocabulary Size Limits - Sliding Window Strategy

**Maintain a functional vocabulary window with min/max boundaries:**

```python
VOCABULARY_WINDOW = {
    'min': 30,   # Core builtin types (never prune)
    'max': 100,  # Soft limit for active custom types
    'total_hard_limit': 500  # Including deprecated
}
```

**Sliding Window Pruning:**
When vocabulary reaches max limit, automatically prune least valuable types to maintain window:

```python
def maintain_vocabulary_window():
    """
    Keep vocabulary between min and max by pruning least useful types.
    """
    active_count = count_active_vocabulary()

    if active_count > VOCABULARY_WINDOW['max']:
        # Calculate how many to prune
        prune_count = active_count - VOCABULARY_WINDOW['max']

        # Get pruning candidates (excluding builtins)
        candidates = get_custom_types_ordered_by_value()

        # Prune bottom N types
        for candidate in candidates[-prune_count:]:
            if candidate.edge_count == 0:
                delete_type(candidate)  # Safe to remove
            else:
                deprecate_type(candidate)  # Has edges, just deactivate

def get_custom_types_ordered_by_value():
    """
    Order custom types by value score for pruning decisions.

    Value Score = (edge_count * traversal_weight * bridge_bonus)
    - edge_count: How many edges exist in the graph with this type
    - traversal_weight: How frequently these edges are traversed in queries
    - bridge_bonus: Prevents catastrophic forgetting of critical bridge nodes

    Time/age is IRRELEVANT - a graph's value is structural, not temporal.

    CRITICAL INSIGHT: Low-activation nodes can have high structural value!
    A rarely-accessed node might be a BRIDGE to high-activation subgraphs.
    We must remember these bridges even if they're not popular endpoints.
    """
    return db.execute("""
        WITH bridge_scores AS (
            -- Calculate bridge value: low-activation nodes connecting to high-activation nodes
            SELECT
                e.relationship_type,
                COUNT(*) as bridge_count,
                AVG(c_to.access_count) as avg_destination_activation
            FROM kg_api.edge_usage_stats e
            JOIN kg_api.concept_access_stats c_from ON e.from_concept_id = c_from.concept_id
            JOIN kg_api.concept_access_stats c_to ON e.to_concept_id = c_to.concept_id
            WHERE c_from.access_count < 10  -- Low activation source
              AND c_to.access_count > 100    -- High activation destination
            GROUP BY e.relationship_type
        )
        SELECT
            v.relationship_type,
            v.usage_count as edge_count,
            COALESCE(e.avg_traversal, 0) as avg_traversal,
            COALESCE(b.bridge_count, 0) as bridge_count,
            COALESCE(b.avg_destination_activation, 0) as bridge_value,
            -- Value score: edge count × traversal × (1 + bridge bonus)
            v.usage_count *
            (1.0 + COALESCE(e.avg_traversal, 0) / 100.0) *
            (1.0 + COALESCE(b.bridge_count, 0) / 10.0) as value_score
        FROM kg_api.relationship_vocabulary v
        LEFT JOIN (
            SELECT relationship_type, AVG(traversal_count) as avg_traversal
            FROM kg_api.edge_usage_stats
            GROUP BY relationship_type
        ) e ON v.relationship_type = e.relationship_type
        LEFT JOIN bridge_scores b ON v.relationship_type = b.relationship_type
        WHERE v.is_builtin = FALSE AND v.is_active = TRUE
        ORDER BY value_score DESC
    """)

def calculate_bridge_importance(concept_id):
    """
    Prevents catastrophic forgetting by identifying bridge nodes.

    A concept might have LOW activation (rarely accessed) but HIGH value
    because it bridges to important subgraphs.

    Example:
    - Concept "distributed consensus" has 5 accesses (LOW)
    - But it connects to "raft algorithm" (500 accesses, HIGH)
    - And "paxos protocol" (300 accesses, HIGH)
    - → Don't prune! It's a critical bridge.
    """
    return db.execute(f"""
        SELECT
            c.concept_id,
            c.access_count as own_activation,
            COUNT(neighbor.concept_id) as high_value_neighbors,
            AVG(neighbor.access_count) as avg_neighbor_activation
        FROM kg_api.concept_access_stats c
        JOIN kg_api.edge_usage_stats e ON c.concept_id = e.from_concept_id
        JOIN kg_api.concept_access_stats neighbor ON e.to_concept_id = neighbor.concept_id
        WHERE c.concept_id = '{concept_id}'
          AND neighbor.access_count > 100  -- High activation threshold
        GROUP BY c.concept_id, c.access_count
    """)
```

**Pruning Strategy:**
1. **Below min (30):** Never prune (builtin types protected)
2. **Between min-max (30-100):** Stable, no pruning
3. **Above max (100+):** Auto-prune lowest value types to return to max
4. **Hard limit (500 total):** Block new types, force curator review

**Example Scenario:**
```
Current state:
- Builtin: 30 (protected)
- Custom active: 95 (within window)
- Deprecated: 50 (historical)

New type requested: "ENHANCES"
Action: Approve (still below max of 100)

After 10 more approvals:
- Builtin: 30
- Custom active: 105 (exceeds max!)

Auto-pruning triggers:
1. Calculate value scores for all 75 custom types
2. Prune bottom 5 types to return to max (100)
3. Types with zero edges: deleted
4. Types with edges: deprecated (is_active = FALSE)
```

**Benefits:**
- ✅ Prevents vocabulary bloat automatically
- ✅ Keeps most valuable types (frequently used, recently accessed)
- ✅ No manual intervention needed for steady-state operations
- ✅ Curator only needed for exceptions or hard limit reached

## Security & Governance

### Access Control

- **Read vocabulary:** All users (needed for ingestion)
- **Approve new types:** Curators only (role: `kg_curator`)
- **Modify builtins:** System admins only

### Audit Trail

```sql
CREATE TABLE kg_api.vocabulary_audit (
    id SERIAL PRIMARY KEY,
    relationship_type VARCHAR(100),
    action VARCHAR(50),  -- 'added', 'aliased', 'deprecated', 'backfilled'
    performed_by VARCHAR(100),
    performed_at TIMESTAMPTZ DEFAULT NOW(),
    details JSONB
);
```

### Semantic Drift and Ambiguity Prevention

**Risk:** As the vocabulary grows, there is a risk that the meaning of relationship types could become ambiguous or drift over time, especially if multiple curators are involved.

**Mitigation:** The `relationship_vocabulary` table defined in this ADR must be treated as a **formal semantic registry**. This is critical for maintaining semantic consistency without significant token overhead during ingestion.

**Requirements:**

1. **Clear, Unambiguous Descriptions**
   - Every relationship type MUST include a precise description of its meaning
   - Description should specify the semantic relationship between concepts
   - Include usage examples to prevent misinterpretation
   - Example:
     ```sql
     INSERT INTO kg_api.relationship_vocabulary
     (relationship_type, description, category)
     VALUES (
         'ENHANCES',
         'One concept improves or strengthens another concept. The source concept adds value, capability, or effectiveness to the target concept without fundamentally changing it.',
         'augmentation'
     );
     ```

2. **Single Source of Truth**
   - The `relationship_vocabulary` table is the authoritative definition
   - All curators, developers, and LLM extraction prompts reference this registry
   - No informal or undocumented relationship interpretations
   - Version control all changes via `vocabulary_audit` table

3. **Accessibility**
   - Vocabulary accessible via API: `GET /vocabulary/{relationship_type}`
   - CLI command: `kg vocabulary show ENHANCES`
   - Included in curator training and documentation
   - Displayed during approval workflow for context

4. **Curation Guidelines**
   - Before approving new type, check for semantic overlap with existing types
   - Consider synonym mapping if meaning is substantially similar
   - Document decision rationale in `vocabulary_audit.details`
   - Require curator to confirm they've read existing descriptions

**Token Efficiency:**
- Descriptions stored in database, NOT in prompts
- LLM extraction uses relationship type names only (minimal tokens)
- Full semantic context queried only during curation
- Result: Rich semantic registry without prompt bloat

**Example Curator Workflow:**
```bash
# Review candidate with semantic context
kg vocabulary review --show-similar ENHANCES

# Output shows existing types with similar semantics:
# SUPPORTS: "One concept provides evidence for another"
# STRENGTHENS: "One concept reinforces another" (SYNONYM of SUPPORTS)
#
# Curator decision: ENHANCES is semantically distinct
# - SUPPORTS = evidential relationship
# - ENHANCES = augmentation relationship
# → Approve as new type

kg vocabulary add ENHANCES \
  --category augmentation \
  --description "One concept improves or strengthens another without fundamentally changing it" \
  --example "Advanced Analytics ENHANCES Decision Making"
```

### Complexity of Backfilling

**Risk:** When a new relationship type is approved, the process of backfilling it—finding all previously skipped instances and creating the corresponding edges in the graph—can be a complex and computationally expensive operation, especially on a large graph.

**Mitigation:** Backfilling should be implemented as a dedicated, asynchronous background job that can be scheduled during off-peak hours. The system should also allow for selective backfilling, prioritizing the most frequent or important relationships first.

**Implementation Approach:**

```python
async def backfill_relationship_type(rel_type: str, options: dict):
    """
    Asynchronous background job for backfilling approved relationship types.

    Args:
        rel_type: The approved relationship type to backfill
        options: Configuration for backfill strategy
            - mode: 'full' | 'selective' | 'dry-run'
            - priority: 'frequency' | 'ontology' | 'manual'
            - batch_size: Number of edges to create per transaction
            - throttle_ms: Delay between batches to reduce load
    """
    # Get all skipped instances for this type
    skipped = await db.execute(f"""
        SELECT relationship_type, from_concept_label, to_concept_label,
               occurrence_count, job_id, ontology
        FROM kg_api.skipped_relationships
        WHERE relationship_type = '{rel_type}'
        ORDER BY occurrence_count DESC  -- High frequency first
    """)

    total = len(skipped)
    created = 0
    failed = 0

    # Process in batches to avoid transaction timeouts
    batch_size = options.get('batch_size', 100)
    throttle = options.get('throttle_ms', 50)

    for i in range(0, total, batch_size):
        batch = skipped[i:i+batch_size]

        for skip in batch:
            try:
                # Find concepts by label (fuzzy match with embedding similarity)
                from_id = await find_concept_by_label(skip.from_concept_label)
                to_id = await find_concept_by_label(skip.to_concept_label)

                if from_id and to_id:
                    if options.get('mode') == 'dry-run':
                        logger.info(f"[DRY-RUN] Would create: {from_id} -{rel_type}-> {to_id}")
                    else:
                        await create_graph_edge(from_id, to_id, rel_type, confidence=0.8)
                        created += 1
                else:
                    failed += 1
                    logger.warning(f"Could not resolve concepts for backfill: {skip}")

            except Exception as e:
                failed += 1
                logger.error(f"Backfill error: {e}")

        # Throttle between batches to reduce database load
        await asyncio.sleep(throttle / 1000.0)

        # Update progress
        progress = ((i + len(batch)) / total) * 100
        await update_job_progress(f"backfill_{rel_type}", progress)

    # Log completion
    await log_backfill_completion(rel_type, created, failed, total)
```

**Selective Backfilling Strategies:**

1. **By Frequency** (default)
   - Backfill most common relationships first
   - ORDER BY occurrence_count DESC
   - Creates high-value edges before low-value edges

2. **By Ontology**
   - Curator selects specific ontology/domain to backfill
   - WHERE ontology = 'Production ML Models'
   - Useful for focused graph enrichment

3. **By Job ID**
   - Backfill only specific ingestion jobs
   - WHERE job_id IN (...)
   - Allows targeted corrections

4. **Dry-Run Mode**
   - Preview backfill impact before execution
   - Shows: "Would create 1,247 edges of type ENHANCES"
   - Curator can approve after review

**CLI Commands:**

```bash
# Preview backfill impact
kg vocabulary backfill ENHANCES --dry-run

# Full backfill (scheduled as background job)
kg vocabulary backfill ENHANCES --schedule off-peak

# Selective backfill by ontology
kg vocabulary backfill ENHANCES --ontology "ML Concepts" --batch-size 50

# Prioritize by frequency
kg vocabulary backfill ENHANCES --mode frequency --top 1000
```

**Performance Considerations:**

- **Batch Processing:** Process in configurable batches (default 100 edges)
- **Throttling:** Delay between batches prevents database saturation
- **Off-Peak Scheduling:** Run during low-traffic periods (3-6 AM)
- **Transaction Management:** Commit per-batch to avoid long-running transactions
- **Progress Tracking:** Real-time progress updates via job status API
- **Rollback Support:** Can revert backfill if issues detected

**Resource Impact Mitigation:**

```python
# Check graph size before backfill
def estimate_backfill_cost(rel_type: str):
    """
    Estimate resource cost before running backfill.
    """
    stats = db.execute(f"""
        SELECT
            COUNT(*) as edge_count,
            COUNT(DISTINCT ontology) as ontology_count,
            SUM(occurrence_count) as total_occurrences
        FROM kg_api.skipped_relationships
        WHERE relationship_type = '{rel_type}'
    """)

    estimated_time = (stats.edge_count * 50) / 1000  # ~50ms per edge

    return {
        'edges_to_create': stats.edge_count,
        'estimated_duration_minutes': estimated_time,
        'ontologies_affected': stats.ontology_count,
        'recommendation': 'scheduled' if stats.edge_count > 1000 else 'immediate'
    }
```

## Documentation Impact

### New Documentation Needed

1. **Curator Guide:** How to review and approve relationship types
2. **Vocabulary Guidelines:** Naming conventions, categories
3. **API Documentation:** New endpoints for vocabulary management
4. **Migration Guide:** How to backfill approved types

### Updates Required

- ADR-024: Add vocabulary tables to `kg_api` schema
- CLAUDE.md: Add vocabulary management section
- API docs: Document `/vocabulary/*` endpoints

## Open Questions

1. **Backfill Strategy:** Automatic or manual trigger?
   - **Recommendation:** Manual trigger with dry-run preview

2. **Synonym Detection:** Use LLM or manual mapping only?
   - **Recommendation:** Start manual, add LLM batch process later

3. **Category Taxonomy:** Fixed categories or user-defined?
   - **Recommendation:** Start with fixed (causation, composition, temporal, semantic, augmentation, evidential, logical), allow custom later

4. **Deprecation Policy:** How to handle unused types?
   - **Recommendation:** Automatic deprecation process (see below)

## Success Criteria

1. **Zero Lost Relationships:** All extracted relationships either matched or logged
2. **Curator Workflow:** < 5 minutes to review and approve a batch of types
3. **Vocabulary Quality:** < 10% synonym overlap (e.g., ENHANCES and SUPPORTS both active)
4. **Performance:** Vocabulary lookup adds < 1ms to ingestion per relationship

## References

- ADR-004: Pure Graph Design (original vocabulary rationale)
- ADR-024: Multi-Schema PostgreSQL Architecture (database infrastructure)
- openCypher specification: Relationship type constraints
- Neo4j vocabulary management best practices
