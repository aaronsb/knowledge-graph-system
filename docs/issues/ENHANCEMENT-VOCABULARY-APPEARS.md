# Enhancement: Vocabulary-Based APPEARS Relationships

**Issue Type:** Enhancement
**Priority:** Medium
**Component:** Ingestion Pipeline, Query Layer, Vocabulary System
**Related:** ADR-065, ADR-058, Issue #134

---

## Summary

Implement vocabulary-based appearance relationships following ADR-065, treating APPEARS as a semantic prototype in embedding space rather than a hardcoded relationship type. This brings Concept→Source provenance relationships into alignment with the emergent vocabulary system used for Concept→Concept semantic relationships.

---

## Goals

1. **Architectural consistency** - Concept→Source uses same vocabulary pattern as Concept→Concept
2. **Semantic richness** - Capture nuance in how concepts appear (central, mentioned, prophesied, etc.)
3. **Transparent migration** - No breaking changes to APIs, queries, or interfaces
4. **Progressive enhancement** - Old data works, new data enriched, both coexist

---

## Non-Goals

- Changing LLM extraction prompts (appearance type inferred from structure)
- Breaking existing API endpoints or query patterns
- Requiring users to understand vocabulary clustering
- Modifying graph schema (same nodes/edges, richer types)

---

## Implementation Phases

### Phase 1: Appearance Type Inference (Transparent Ingestion)

**File:** `api/lib/serialization.py`

Add automatic appearance type inference during instance creation:

```python
def infer_appearance_type(instance: Dict, source: Dict, all_instances: List[Dict]) -> str:
    """
    Infer appearance type from structural signals.

    Transparent to LLM - no extraction prompt changes needed.

    Args:
        instance: Current instance being processed
        source: Source document metadata
        all_instances: All instances of this concept in this source

    Returns:
        Inferred appearance type (will be normalized against vocabulary)
    """
    # Calculate structural signals
    quote_len = len(instance.get('quote', ''))
    text_len = len(source.get('full_text', ''))
    centrality = quote_len / text_len if text_len > 0 else 0

    frequency = len(all_instances)
    para_pos = instance.get('paragraph', 0)
    total_paras = source.get('total_paragraphs', 1)
    position = para_pos / total_paras if total_paras > 0 else 0

    # Infer type from signals (heuristics)
    if centrality > 0.3:
        # Quote is >30% of text - this is a central discussion
        return "CENTRAL_TO"
    elif frequency > 5:
        # Mentioned many times - thoroughly discussed
        return "THOROUGHLY_DISCUSSED_IN"
    elif position < 0.1:
        # Early in document - introduction
        return "INTRODUCED_IN"
    elif centrality < 0.05 and frequency == 1:
        # Small quote, single mention - brief reference
        return "MENTIONED_IN"
    else:
        # Default fallback
        return "APPEARS"


def normalize_appearance_type(
    type_hint: str,
    threshold: float = 0.80,
    age_client: Optional[AGEClient] = None
) -> str:
    """
    Normalize appearance type against vocabulary cluster.

    Similar to relationship_mapper.normalize_relationship_type() but for appearance types.

    Args:
        type_hint: Inferred or extracted appearance type
        threshold: Similarity threshold for cluster membership (0.80 = ~1 sigma)
        age_client: Optional AGEClient for vocabulary lookup

    Returns:
        Canonical appearance type from vocabulary, or type_hint if no match
    """
    if not age_client:
        # No vocabulary available, use hint as-is
        return type_hint.upper().replace(' ', '_')

    # Get APPEARS cluster from vocabulary
    try:
        appears_cluster = age_client.get_vocabulary_cluster(
            prototype="APPEARS",
            threshold=threshold,
            category="provenance"
        )

        # Check if type_hint is already in cluster
        type_upper = type_hint.upper().replace(' ', '_')
        if type_upper in appears_cluster:
            return type_upper

        # Calculate similarity to prototype
        type_emb = age_client.get_vocabulary_embedding(type_upper, create_if_missing=True)
        appears_emb = age_client.get_vocabulary_embedding("APPEARS")

        similarity = cosine_similarity(type_emb, appears_emb)

        if similarity >= threshold:
            # Close enough to cluster, use as-is
            return type_upper
        else:
            # Outside cluster, fall back to APPEARS
            return "APPEARS"

    except Exception as e:
        logger.warning(f"Vocabulary normalization failed: {e}, using {type_hint}")
        return type_hint.upper().replace(' ', '_')


def calculate_appearance_confidence(instance: Dict, source: Dict) -> float:
    """
    Calculate confidence score for appearance relationship.

    Based on:
    - Quote quality (length, completeness)
    - Instance quality (extraction confidence)
    - Source quality (document metadata)

    Returns:
        Confidence score 0.0 to 1.0
    """
    # Base confidence from instance
    base_conf = instance.get('confidence', 0.8)

    # Adjust for quote quality
    quote_len = len(instance.get('quote', ''))
    if quote_len < 20:
        # Very short quote, reduce confidence
        base_conf *= 0.8
    elif quote_len > 200:
        # Substantial quote, increase confidence
        base_conf *= 1.1

    # Clamp to [0, 1]
    return max(0.0, min(1.0, base_conf))
```

**Modify instance creation** (api/lib/serialization.py:~799):

```python
def process_instance(instance):
    """Process single instance with vocabulary-based appearance type"""

    # Infer appearance type from structural signals
    type_hint = infer_appearance_type(instance, source, all_instances)

    # Normalize against vocabulary cluster
    canonical_type = normalize_appearance_type(type_hint, threshold=0.80, age_client=client)

    # Calculate confidence
    confidence = calculate_appearance_confidence(instance, source)

    query = f"""
        MATCH (c:Concept {{concept_id: $concept_id}})
        MATCH (s:Source {{source_id: $source_id}})
        MERGE (i:Instance {{instance_id: $instance_id}})
        SET i.quote = $quote
        MERGE (c)-[:EVIDENCED_BY]->(i)
        MERGE (i)-[:FROM_SOURCE]->(s)
        MERGE (c)-[r:{canonical_type}]->(s)
        SET r.confidence = $confidence
    """

    params = {
        **instance,
        'confidence': confidence
    }

    client._execute_cypher(query, params=params)
```

**Testing:**
```bash
# Ingest test document
kg ingest file -o "Test" test-doc.txt

# Check relationship types created
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c "
SELECT DISTINCT label FROM ag_catalog.ag_label WHERE graph = 'knowledge_graph'::regnamespace
"

# Should see: CENTRAL_TO, MENTIONED_IN, etc. (not just APPEARS)
```

### Phase 2: Vocabulary Cluster Management (AGEClient Extension)

**File:** `api/api/lib/age_client.py`

Add methods for vocabulary cluster operations:

```python
class AGEClient:

    def get_vocabulary_cluster(
        self,
        prototype: str,
        threshold: float = 0.75,
        category: Optional[str] = None
    ) -> List[str]:
        """
        Get vocabulary types semantically similar to prototype.

        Examples:
            client.get_vocabulary_cluster("APPEARS", 0.75)
            → ["APPEARS", "DISCUSSED_IN", "MENTIONED_IN", "CENTRAL_TO"]

            client.get_vocabulary_cluster("SUPPORTS", 0.80)
            → ["SUPPORTS", "VALIDATES", "CONFIRMS", "REINFORCES"]

        Args:
            prototype: Vocabulary type to use as cluster center
            threshold: Min cosine similarity for cluster membership (0.75 = ~1 sigma)
            category: Optional category filter (e.g., "provenance", "evidential")

        Returns:
            List of vocabulary types in cluster
        """
        # Get prototype embedding
        prototype_emb = self.get_vocabulary_embedding(prototype)

        if prototype_emb is None:
            logger.warning(f"No embedding for prototype '{prototype}', returning empty cluster")
            return []

        # Query vocabulary table
        with self.pool.connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT relationship_type, embedding
                    FROM kg_api.relationship_vocabulary
                    WHERE embedding IS NOT NULL
                      AND is_active = TRUE
                """
                params = []

                if category:
                    query += " AND category = %s"
                    params.append(category)

                cur.execute(query, params)
                results = cur.fetchall()

        # Calculate similarities
        cluster = []
        for row in results:
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
        Calculate appearance strength via polarity axis projection (ADR-058 pattern).

        Args:
            edge_type: Appearance relationship type
            polarity_pairs: Optional polarity pairs (defaults to centrality axis)

        Returns:
            Strength score: -1.0 (tangential) to +1.0 (central)
        """
        if not polarity_pairs:
            # Default: centrality polarity axis
            polarity_pairs = [
                ("CENTRAL_TO", "TANGENTIAL_TO"),
                ("THOROUGHLY_DISCUSSED_IN", "BRIEFLY_MENTIONED_IN"),
                ("FOUNDATIONAL_TO", "PERIPHERAL_TO"),
            ]

        # Use existing polarity axis calculation (ADR-058)
        axis = self._compute_polarity_axis(polarity_pairs)
        if axis is None:
            return 0.0  # Neutral if axis can't be computed

        # Get edge embedding
        edge_emb = self.get_vocabulary_embedding(edge_type)
        if edge_emb is None:
            return 0.0

        # Project onto axis (dot product)
        strength = np.dot(edge_emb, axis)

        return float(strength)
```

**Testing:**
```python
# Test cluster retrieval
client = AGEClient()
cluster = client.get_vocabulary_cluster("APPEARS", threshold=0.75)
print(f"APPEARS cluster: {cluster}")

# Test strength calculation
strength = client.calculate_appearance_strength("CENTRAL_TO")
print(f"CENTRAL_TO strength: {strength}")  # Should be positive

strength = client.calculate_appearance_strength("MENTIONED_IN")
print(f"MENTIONED_IN strength: {strength}")  # Should be neutral/slightly negative
```

### Phase 3: Query Facade Enhancement (Transparent Query Layer)

**File:** `api/api/lib/query_facade.py`

Extend facade with appearance-aware methods:

```python
class GraphQueryFacade:

    def match_concept_sources(
        self,
        concept_id: str,
        appearance_threshold: float = 0.75,
        strength_threshold: Optional[float] = None,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Match sources where concept appears, using vocabulary cluster.

        Transparent to callers - handles vocabulary complexity internally.

        Args:
            concept_id: Concept to find sources for
            appearance_threshold: Min similarity to APPEARS prototype (0.75 = ~1 sigma)
            strength_threshold: Optional min appearance strength (centrality filter)
            limit: Optional result limit

        Returns:
            List of source dictionaries with appearance metadata

        Examples:
            # Simple: All appearances
            sources = facade.match_concept_sources("covenant_name")

            # Strict: Only very similar to APPEARS
            sources = facade.match_concept_sources("covenant_name", appearance_threshold=0.90)

            # Filtered: Only central appearances
            sources = facade.match_concept_sources(
                "covenant_name",
                appearance_threshold=0.75,
                strength_threshold=0.5
            )
        """
        # Get appearance cluster from vocabulary
        appearance_types = self.client.get_vocabulary_cluster(
            prototype="APPEARS",
            threshold=appearance_threshold,
            category="provenance"
        )

        if not appearance_types:
            # Vocabulary not available, fall back to generic APPEARS
            appearance_types = ["APPEARS"]

        # Build query
        type_pattern = "|".join(appearance_types)
        filters = [f"type(r) =~ '{type_pattern}'"]

        if strength_threshold is not None:
            filters.append(f"r.appearance_strength >= {strength_threshold}")

        where = " AND ".join(filters)
        limit_clause = f"LIMIT {limit}" if limit else ""

        query = f"""
            MATCH (c:Concept {{concept_id: $concept_id}})-[r]->(s:Source)
            WHERE {where}
            RETURN s,
                   type(r) as appearance_type,
                   r.confidence as confidence,
                   r.appearance_strength as strength
            ORDER BY coalesce(r.appearance_strength, 0) DESC, r.confidence DESC
            {limit_clause}
        """

        return self.client._execute_cypher(query, {"concept_id": concept_id})
```

**Testing:**
```python
# Test facade
facade = GraphQueryFacade(client)

# Simple query
sources = facade.match_concept_sources("test_concept")
print(f"Found {len(sources)} sources")

# Filtered query
central_sources = facade.match_concept_sources(
    "test_concept",
    appearance_threshold=0.75,
    strength_threshold=0.5
)
print(f"Found {len(central_sources)} central sources")
```

### Phase 4: API Endpoint Updates (Optional Enhancement)

**File:** `api/api/routes/queries.py`

Add optional appearance filtering to existing endpoints:

```python
@router.get("/concepts/{concept_id}/sources")
async def get_concept_sources(
    concept_id: str,
    appearance_threshold: float = Query(0.75, description="Min similarity to APPEARS (0.0-1.0)"),
    min_centrality: Optional[float] = Query(None, description="Min appearance strength (-1.0 to 1.0)"),
    current_user: CurrentUser = None
):
    """
    Get sources where concept appears.

    Optional filters for appearance quality (progressive enhancement).

    Args:
        concept_id: Concept identifier
        appearance_threshold: Min similarity to APPEARS prototype (default: 0.75)
        min_centrality: Optional min centrality score (filters to central appearances)

    Returns:
        List of sources with appearance metadata
    """
    client = get_age_client()

    try:
        sources = client.facade.match_concept_sources(
            concept_id=concept_id,
            appearance_threshold=appearance_threshold,
            strength_threshold=min_centrality
        )

        return ConceptSourcesResponse(
            concept_id=concept_id,
            count=len(sources),
            sources=sources
        )

    finally:
        client.close()
```

**Backward compatibility:**
- Existing endpoints continue to work (default thresholds)
- New parameters are optional
- Old clients ignore new response fields

### Phase 5: CLI Enhancement (User Visibility)

**File:** `cli/src/cli/search.ts` (or similar)

Add filtering options to search commands:

```typescript
// kg search sources <concept-id> [--central] [--threshold 0.8]
program
  .command('sources')
  .argument('<concept-id>', 'Concept identifier')
  .option('--central', 'Only show central appearances (strength > 0.5)')
  .option('--threshold <value>', 'Appearance similarity threshold', '0.75')
  .action(async (conceptId, options) => {
    const params = {
      appearance_threshold: parseFloat(options.threshold),
      ...(options.central && { min_centrality: 0.5 })
    };

    const response = await client.get(`/concepts/${conceptId}/sources`, { params });

    console.log(`\nSources for concept ${conceptId}:\n`);
    response.data.sources.forEach((src, i) => {
      const strength = src.strength ? ` [${Math.round(src.strength * 100)}% central]` : '';
      const type = src.appearance_type !== 'APPEARS' ? ` (${src.appearance_type})` : '';

      console.log(`${i + 1}. ${src.document} (para ${src.paragraph})${type}${strength}`);
    });
  });
```

**Example usage:**
```bash
# Simple: All appearances
kg search sources covenant_name

# Filtered: Only central
kg search sources covenant_name --central

# Custom threshold
kg search sources covenant_name --threshold 0.85
```

---

## Migration Strategy

### Backward Compatibility

**Existing data (generic APPEARS):**
```cypher
(concept)-[:APPEARS]->(source)  // Created before enhancement
```

**New data (vocabulary types):**
```cypher
(concept)-[:CENTRAL_TO]->(source)      // Created after enhancement
(concept)-[:MENTIONED_IN]->(source)     // Created after enhancement
```

**Queries work with both:**
```cypher
// Matches both old and new data
MATCH (c:Concept {concept_id: $id})-[r]->(s:Source)
WHERE type(r) IN $appearance_types  // Cluster includes "APPEARS"
RETURN s
```

### Gradual Rollout

**Week 1:** Infrastructure
- Add appearance inference functions (Phase 1)
- Add vocabulary cluster methods (Phase 2)
- Deploy to dev, test with sample documents

**Week 2:** Query layer
- Extend GraphQueryFacade (Phase 3)
- Update API endpoints (Phase 4)
- Deploy to staging, integration tests

**Week 3:** User interfaces
- CLI enhancements (Phase 5)
- MCP formatter updates
- Web visualization (node size = centrality)

**Week 4:** Production rollout
- Deploy to production
- Monitor appearance type distribution
- Tune inference heuristics based on usage

### Monitoring

**Track vocabulary emergence:**
```sql
-- Most common appearance types
SELECT relationship_type, usage_count
FROM kg_api.relationship_vocabulary
WHERE category = 'provenance'
  AND is_active = TRUE
ORDER BY usage_count DESC
LIMIT 10;
```

**Track appearance strength distribution:**
```cypher
MATCH (c:Concept)-[r]->(s:Source)
WHERE type(r) =~ '.*_TO|.*_IN|APPEARS'
RETURN type(r),
       avg(r.appearance_strength) as avg_strength,
       count(*) as count
ORDER BY count DESC
```

---

## Testing Plan

### Unit Tests

```python
# test_appearance_inference.py
def test_infer_central_appearance():
    instance = {"quote": "..." * 100, "paragraph": 1}  # Long quote
    source = {"full_text": "..." * 200, "total_paragraphs": 10}

    result = infer_appearance_type(instance, source, [instance])
    assert result == "CENTRAL_TO"

def test_infer_mentioned_appearance():
    instance = {"quote": "brief mention", "paragraph": 5}  # Short quote
    source = {"full_text": "..." * 1000, "total_paragraphs": 10}

    result = infer_appearance_type(instance, source, [instance])
    assert result == "MENTIONED_IN"

def test_vocabulary_cluster_retrieval():
    client = AGEClient()
    cluster = client.get_vocabulary_cluster("APPEARS", threshold=0.75)

    assert "APPEARS" in cluster
    assert len(cluster) > 0
    # Should include appearance-like types, exclude evidential types
    assert "SUPPORTS" not in cluster
```

### Integration Tests

```bash
# test_ingestion_with_vocabulary.sh

# 1. Ingest document with varied concept density
kg ingest file -o "TestOnt" test-documents/varied-density.txt

# 2. Verify multiple appearance types created
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph <<SQL
SELECT DISTINCT label
FROM ag_catalog.ag_label
WHERE graph = 'knowledge_graph'::regnamespace
  AND label LIKE '%_TO'
  OR label LIKE '%_IN'
  OR label = 'APPEARS';
SQL

# Should see: CENTRAL_TO, MENTIONED_IN, THOROUGHLY_DISCUSSED_IN, etc.

# 3. Test query filtering
kg search sources <concept-id> --central

# Should return subset of all sources
```

### End-to-End Tests

```bash
# Scenario: Biblical covenant tracing

# 1. Ingest Genesis chapters
kg ingest file -o "Genesis" genesis.txt

# 2. Search for covenant_name
kg search query "covenant name"

# 3. Get sources with centrality filter
kg search sources <covenant-concept-id> --central

# Expected: Genesis 15, 17 (covenant established)
# Not expected: Genesis 2, 3 (pre-covenant context)
```

---

## Success Criteria

### Functional
- ✅ Appearance types automatically inferred during ingestion
- ✅ Vocabulary cluster retrieval works (threshold-based)
- ✅ GraphQueryFacade provides appearance filtering
- ✅ API endpoints accept appearance parameters
- ✅ CLI supports centrality filtering

### Quality
- ✅ No query failures (backward compatibility maintained)
- ✅ Appearance type distribution matches corpus (not all CENTRAL_TO)
- ✅ Centrality scores correlate with manual assessment
- ✅ Vocabulary consolidation reduces similar appearance types

### Performance
- ✅ Ingestion time increase < 10% (inference is fast)
- ✅ Query performance unchanged (indexed relationship types)
- ✅ Vocabulary cluster retrieval < 100ms

### Adoption
- ✅ Users use centrality filtering in queries
- ✅ Biblical tracing scenario works (prophesy vs fulfillment)
- ✅ Documentation updated with examples

---

## Risks & Mitigations

### Risk 1: Inference Heuristics Inaccurate

**Risk:** Structural signals don't reliably predict semantic appearance type.

**Mitigation:**
- Start with conservative heuristics (default to APPEARS)
- Monitor appearance type distribution
- Tune thresholds based on user feedback
- Allow manual override in future version

### Risk 2: Vocabulary Explosion

**Risk:** Too many appearance types, consolidation can't keep up.

**Mitigation:**
- Use high normalization threshold (0.80+) to reduce variants
- Run vocabulary consolidation regularly
- Category filter ("provenance") separates from evidential types
- Monitor vocabulary size, alert if > 50 appearance types

### Risk 3: Query Complexity Creeps Up

**Risk:** Users confused by threshold parameters and strength scores.

**Mitigation:**
- Good defaults (0.75 threshold, no strength filter)
- Simple CLI flags (--central instead of --strength 0.5)
- Documentation with examples
- Facade hides complexity from API consumers

### Risk 4: Migration Breaks Existing Data

**Risk:** Old APPEARS relationships don't work with new queries.

**Mitigation:**
- Cluster always includes "APPEARS" prototype
- Pattern matching `[r]` works with any type
- No data migration needed (old and new coexist)
- Integration tests verify backward compatibility

---

## Future Enhancements

### Enhancement 1: LLM Characterization (Optional)

Instead of structural inference, ask LLM to characterize appearance:

```
For each concept, describe how it appears in this text:
- Is it central to the discussion or tangential?
- Is it predictive (prophesied/foreshadowed) or retrospective (fulfilled/referenced)?
- Is it directly stated or implied?
```

**Pros:** More accurate semantic characterization
**Cons:** Increases extraction cost and complexity

### Enhancement 2: User Manual Override

Allow users to upgrade appearance relationships:

```bash
# Upgrade relationship type
kg relationship upgrade \
  --concept "covenant_name" \
  --source "Genesis:15" \
  --type "PROPHESIED_IN"
```

**Pros:** User control for important relationships
**Cons:** Manual effort, consistency issues

### Enhancement 3: Appearance Strength in Visualization

Web interface shows centrality visually:
- Node size proportional to avg appearance strength
- Edge thickness = confidence score
- Color gradient: central (warm) to tangential (cool)

**Pros:** Immediate visual insight
**Cons:** Requires web app changes

---

## Related Work

- **ADR-065:** Architectural decision (this enhancement implements it)
- **ADR-058:** Polarity axis pattern we're replicating
- **ADR-050:** Vocabulary consolidation applies to appearance types
- **Issue #134:** APPEARS_IN naming bug (prerequisite fix)
- **ENHANCEMENT-JOB-OUTPUT-CACHING:** Separate enhancement for job results

---

## Implementation Checklist

- [ ] Phase 1: Appearance inference (serialization.py)
- [ ] Phase 2: Vocabulary cluster methods (age_client.py)
- [ ] Phase 3: Query facade extension (query_facade.py)
- [ ] Phase 4: API endpoint updates (queries.py)
- [ ] Phase 5: CLI enhancements (search.ts)
- [ ] Unit tests (test_appearance_inference.py)
- [ ] Integration tests (test_ingestion_with_vocabulary.sh)
- [ ] Documentation updates (ARCHITECTURE.md, API docs)
- [ ] Monitoring dashboards (appearance type distribution)
- [ ] Production deployment
