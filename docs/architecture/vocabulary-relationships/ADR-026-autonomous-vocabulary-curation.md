---
status: Proposed
date: 2025-10-10
deciders:
  - System Architects
related:
  - ADR-025
  - ADR-024
---

# ADR-026: Autonomous Vocabulary Curation and Ontology Management

## Overview

When your knowledge graph can learn new relationship types automatically (as enabled in ADR-025), you quickly discover a practical challenge: who decides if "ENHANCES", "IMPROVES", and "STRENGTHENS" are really different concepts or just three ways to say the same thing? A human curator could review every new term, but with 50+ new types appearing from large document sets, this becomes a full-time job that slows down your knowledge building.

This ADR explores using AI to help with vocabulary curation—essentially having the system clean up after itself. Imagine the AI extracting concepts uses GPT-4, and when new relationship types pile up, a separate AI agent (using embeddings to measure semantic similarity) reviews them and suggests: "These five types all mean roughly the same thing—should we consolidate them?" The human curator approves or rejects these suggestions, creating a collaborative workflow. The system also tracks which relationship types are actually being used versus just cluttering the vocabulary, enabling smart pruning decisions. This is theoretical enhancement rather than immediate implementation—exploring how to scale vocabulary management without requiring constant human oversight, while keeping humans in the loop for final decisions about the knowledge structure.

---

## Context

ADR-025 establishes a curator-driven workflow for managing relationship vocabulary growth. While effective, the manual curation process has scalability limitations:

### Current Curation Workflow (ADR-025)

```bash
# Curator manually reviews skipped relationships
kg vocabulary review
# Output: 127 occurrences of "ENHANCES" across 15 documents

# Curator manually decides: new type or synonym?
kg vocabulary add ENHANCES --category augmentation --description "..."
# OR
kg vocabulary alias ENHANCES --maps-to SUPPORTS
```

### Scalability Challenges

1. **Manual Bottleneck:**
   - Large ingestion jobs can produce 50+ unique relationship types
   - Curator must review each one individually
   - Decision fatigue on semantic similarity judgments
   - Slows down knowledge graph growth

2. **Limited Semantic Analysis:**
   - Curator relies on intuition for synonym detection
   - No formal similarity metrics between relationship types
   - Risk of creating near-duplicate types (ENHANCES vs IMPROVES vs STRENGTHENS)
   - Inconsistent categorization across curators

3. **Reactive Ontology Evolution:**
   - Vocabulary changes discovered post-ingestion
   - No proactive trend analysis
   - Missing strategic insights about domain evolution
   - Ontology "drifts" rather than "evolves" purposefully

### Research Context

- **LLM-Assisted Schema Matching:** Recent research demonstrates LLMs can identify semantic equivalence between schema elements with >85% accuracy (GPT-4 on COMA++ benchmark)
- **Ontology Versioning Standards:** Semantic Web community uses OWL versioning (owl:versionInfo, owl:priorVersion) for formal schema evolution tracking
- **Knowledge Discovery in Databases:** Skipped relationships table represents a "schema change recommendation stream" amenable to data mining

## Decision

**Introduce three autonomous enhancements to vocabulary management, transforming the curator from operator to validator:**

### 1. LLM-Assisted Synonym and Category Suggestion

**Automated Analysis Pipeline:**

```python
async def suggest_vocabulary_actions(relationship_type: str):
    """
    LLM-powered analysis of skipped relationship types.

    Returns:
        - Synonym confidence scores for existing types
        - Suggested category if creating new type
        - Semantic description proposal
        - Decision recommendation (add vs alias)
    """
    # Retrieve context
    skipped_instances = get_skipped_instances(relationship_type)
    existing_vocab = get_relationship_vocabulary()

    # Build LLM prompt
    prompt = f"""
    You are a knowledge graph ontology curator. Analyze whether the relationship type
    '{relationship_type}' should be:
    1. Aliased to an existing type (synonym), OR
    2. Added as a new distinct semantic relationship

    EXISTING VOCABULARY:
    {format_vocabulary_with_descriptions(existing_vocab)}

    SKIPPED RELATIONSHIP EXAMPLES:
    {format_skipped_examples(skipped_instances[:10])}

    For each existing type, provide:
    - Semantic similarity score (0.0-1.0)
    - Reasoning

    If similarity > 0.85: RECOMMEND aliasing to most similar type
    If similarity < 0.85: RECOMMEND new type with suggested category and description

    Output JSON:
    {{
      "recommendation": "alias" | "new_type",
      "similar_types": [
        {{"type": "SUPPORTS", "similarity": 0.78, "reasoning": "..."}},
        ...
      ],
      "if_alias": {{"canonical_type": "SUPPORTS", "confidence": 0.92}},
      "if_new": {{
        "suggested_category": "augmentation",
        "suggested_description": "One concept improves another...",
        "confidence": 0.88
      }}
    }}
    """

    response = await llm_client.complete(
        prompt=prompt,
        model="gpt-4o",
        response_format={"type": "json_object"}
    )

    return parse_suggestion(response)
```

**Enhanced Curator Workflow:**

```bash
# LLM pre-analyzes and suggests actions
kg vocabulary review --with-suggestions

# Output:
# ┌─────────────┬────────────┬──────────────┬─────────────────────────────┐
# │ Type        │ Count      │ Suggestion   │ Reasoning                   │
# ├─────────────┼────────────┼──────────────┼─────────────────────────────┤
# │ ENHANCES    │ 127        │ NEW TYPE     │ Distinct from SUPPORTS      │
# │             │            │              │ (similarity: 0.72)          │
# │             │            │              │ Category: augmentation      │
# ├─────────────┼────────────┼──────────────┼─────────────────────────────┤
# │ IMPROVES    │ 89         │ ALIAS        │ Synonym of ENHANCES         │
# │             │            │ → ENHANCES   │ (similarity: 0.94)          │
# ├─────────────┼────────────┼──────────────┼─────────────────────────────┤
# │ VALIDATES   │ 56         │ ALIAS        │ Evidential relationship     │
# │             │            │ → SUPPORTS   │ (similarity: 0.88)          │
# └─────────────┴────────────┴──────────────┴─────────────────────────────┘
#
# Curator validation:
# Press [A]pprove all | [R]eview individually | [C]ancel

# One-click approval for high-confidence suggestions
kg vocabulary approve-batch --confidence-threshold 0.9
```

**Token Efficiency:**

- LLM analysis runs once per batch (not per concept)
- Embedding-based pre-filtering reduces LLM calls
- Results cached in `vocabulary_suggestions` table
- Cost: ~$0.05 per 100 relationship types analyzed

### 2. Formal Ontology Versioning

**Immutable Version History:**

```sql
-- Ontology Version Registry
CREATE TABLE kg_api.ontology_versions (
    version_id SERIAL PRIMARY KEY,
    version_number VARCHAR(20) NOT NULL,  -- Semantic versioning: 1.2.3
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100),
    change_summary TEXT,
    is_active BOOLEAN DEFAULT TRUE,

    -- Snapshot of vocabulary at this version
    vocabulary_snapshot JSONB NOT NULL,

    -- Change metadata
    types_added TEXT[],
    types_aliased JSONB,  -- [{"IMPROVES": "ENHANCES"}, ...]
    types_deprecated TEXT[],

    -- Compatibility
    backward_compatible BOOLEAN,
    migration_required BOOLEAN,

    UNIQUE(version_number)
);

-- Concept Provenance (track which version created each concept)
CREATE TABLE kg_api.concept_version_metadata (
    concept_id VARCHAR(100) PRIMARY KEY,
    created_in_version INTEGER REFERENCES kg_api.ontology_versions(version_id),
    last_modified_version INTEGER REFERENCES kg_api.ontology_versions(version_id)
);

-- Historical Vocabulary View (time-travel queries)
CREATE VIEW kg_api.vocabulary_at_version AS
SELECT
    ov.version_number,
    ov.created_at,
    jsonb_array_elements(ov.vocabulary_snapshot) as vocabulary_entry
FROM kg_api.ontology_versions ov;
```

**Semantic Versioning Rules:**

```python
def increment_ontology_version(changes: dict):
    """
    Semantic versioning for ontology changes.

    MAJOR.MINOR.PATCH:
    - MAJOR: Breaking changes (type removed, semantics fundamentally changed)
    - MINOR: New relationship types added (backward compatible)
    - PATCH: Aliases added, descriptions improved (no schema change)
    """
    current_version = get_current_ontology_version()  # e.g., "1.2.3"
    major, minor, patch = parse_version(current_version)

    if changes['types_removed'] or changes['semantics_changed']:
        # Breaking change
        return f"{major + 1}.0.0"

    elif changes['types_added']:
        # New types (backward compatible)
        return f"{major}.{minor + 1}.0"

    else:
        # Aliases or description updates only
        return f"{major}.{minor}.{patch + 1}"
```

**Automatic Version Creation:**

```python
async def approve_vocabulary_change(action: str, details: dict):
    """
    Every vocabulary change triggers version increment.
    """
    # Calculate version increment
    new_version = increment_ontology_version(action, details)

    # Create immutable snapshot
    current_vocab = get_full_vocabulary()

    version_record = {
        'version_number': new_version,
        'created_by': current_user.username,
        'change_summary': generate_change_summary(action, details),
        'vocabulary_snapshot': current_vocab,
        'backward_compatible': is_backward_compatible(action),
        'types_added': details.get('new_types', []),
        'types_aliased': details.get('aliases', {}),
        'types_deprecated': details.get('deprecated', [])
    }

    await db.execute(
        "INSERT INTO kg_api.ontology_versions (...) VALUES (...)",
        version_record
    )

    # Audit trail
    await log_version_change(new_version, action, details)
```

**Time-Travel Queries:**

```cypher
-- Find concepts created with vocabulary from v1.2.x
MATCH (c:Concept)
WHERE c.created_in_version STARTS WITH '1.2'
RETURN c

-- Query graph as it existed at version 1.1.0
-- (using vocabulary snapshot to reinterpret relationship types)
SELECT * FROM kg_api.vocabulary_at_version
WHERE version_number = '1.1.0'
```

**Migration Support:**

```bash
# When breaking change occurs (v1.x.x → v2.0.0)
kg ontology migrate --from-version 1.5.2 --to-version 2.0.0

# Shows:
# BREAKING CHANGES:
# - Type REMOVED: "VALIDATES" (use "SUPPORTS" instead)
# - Type SEMANTICS CHANGED: "ENHANCES" now requires confidence > 0.8
#
# Migration will:
# 1. Remap all VALIDATES edges → SUPPORTS
# 2. Flag low-confidence ENHANCES edges for review
#
# Affected: 1,247 edges across 3 ontologies
# Estimated time: 5 minutes
#
# Proceed? [Y/n]
```

### 3. Advanced Vocabulary Analytics Dashboard

**Strategic Knowledge Discovery Interface:**

```python
class VocabularyAnalyticsDashboard:
    """
    Transform skipped_relationships from maintenance log into strategic insight tool.
    """

    def get_emerging_relationship_trends(self, days: int = 30):
        """
        Identify relationship types with accelerating occurrence.
        """
        return db.execute(f"""
            WITH daily_counts AS (
                SELECT
                    relationship_type,
                    DATE(first_seen) as date,
                    SUM(occurrence_count) as daily_count
                FROM kg_api.skipped_relationships
                WHERE first_seen > NOW() - INTERVAL '{days} days'
                GROUP BY relationship_type, DATE(first_seen)
            ),
            growth_rates AS (
                SELECT
                    relationship_type,
                    REGR_SLOPE(daily_count, EXTRACT(EPOCH FROM date)) as growth_rate,
                    AVG(daily_count) as avg_daily_count
                FROM daily_counts
                GROUP BY relationship_type
            )
            SELECT
                relationship_type,
                growth_rate,
                avg_daily_count,
                growth_rate * avg_daily_count as trend_score
            FROM growth_rates
            WHERE growth_rate > 0
            ORDER BY trend_score DESC
            LIMIT 10
        """)

    def get_relationship_cooccurrence_network(self):
        """
        Which relationship types appear together in the same documents?
        Reveals semantic clusters.
        """
        return db.execute("""
            SELECT
                a.relationship_type as type_a,
                b.relationship_type as type_b,
                COUNT(DISTINCT a.job_id) as cooccurrence_count,
                CORR(a.occurrence_count, b.occurrence_count) as correlation
            FROM kg_api.skipped_relationships a
            JOIN kg_api.skipped_relationships b
                ON a.job_id = b.job_id
                AND a.relationship_type < b.relationship_type
            GROUP BY a.relationship_type, b.relationship_type
            HAVING COUNT(DISTINCT a.job_id) > 3
            ORDER BY cooccurrence_count DESC
        """)

    def get_ontology_vocabulary_fingerprint(self, ontology: str):
        """
        What makes this ontology's vocabulary unique?
        """
        return db.execute(f"""
            -- TF-IDF style scoring for relationship types per ontology
            WITH type_freq AS (
                SELECT
                    ontology,
                    relationship_type,
                    SUM(occurrence_count) as freq
                FROM kg_api.skipped_relationships
                GROUP BY ontology, relationship_type
            ),
            inverse_doc_freq AS (
                SELECT
                    relationship_type,
                    LOG(COUNT(DISTINCT ontology)) as idf
                FROM kg_api.skipped_relationships
                GROUP BY relationship_type
            )
            SELECT
                tf.relationship_type,
                tf.freq,
                idf.idf,
                tf.freq * idf.idf as distinctiveness_score
            FROM type_freq tf
            JOIN inverse_doc_freq idf ON tf.relationship_type = idf.relationship_type
            WHERE tf.ontology = '{ontology}'
            ORDER BY distinctiveness_score DESC
            LIMIT 20
        """)

    def predict_vocabulary_growth(self, months: int = 6):
        """
        Forecast vocabulary size and recommend pruning thresholds.
        """
        historical_growth = self.get_vocabulary_growth_history()

        # Simple linear regression (upgrade to Prophet/ARIMA for production)
        slope = calculate_growth_rate(historical_growth)
        current_size = get_vocabulary_size()

        projected_size = current_size + (slope * months * 30)

        if projected_size > VOCABULARY_WINDOW['max']:
            pruning_needed = projected_size - VOCABULARY_WINDOW['max']
            return {
                'forecast': projected_size,
                'action_required': True,
                'pruning_recommendation': {
                    'types_to_prune': pruning_needed,
                    'suggested_candidates': get_low_value_types(limit=pruning_needed)
                }
            }

        return {'forecast': projected_size, 'action_required': False}
```

**Visualization Examples:**

```bash
# Emerging relationship types (trending up)
kg vocabulary analytics trends --days 30

# Output (with sparkline):
# ┌──────────────┬────────────┬─────────────────────────────────┐
# │ Type         │ Growth Rate│ Trend (30 days)                 │
# ├──────────────┼────────────┼─────────────────────────────────┤
# │ OPTIMIZES    │ +340%      │ ▁▂▃▅▇█ (accelerating)          │
# │ MONITORS     │ +180%      │ ▂▃▅▆▇█ (steady growth)         │
# │ DELEGATES    │ +90%       │ ▃▄▅▆▆█ (recent spike)          │
# └──────────────┴────────────┴─────────────────────────────────┘

# Relationship co-occurrence network
kg vocabulary analytics network --min-cooccurrence 5

# Output (ASCII graph):
#              ENHANCES ---- INTEGRATES
#                 |              |
#            OPTIMIZES ---- DELEGATES
#                 |              |
#              MONITORS ---- VALIDATES
#
# Cluster 1: Performance (OPTIMIZES, MONITORS)
# Cluster 2: Integration (INTEGRATES, DELEGATES)
# Cluster 3: Validation (VALIDATES, ENHANCES)

# Ontology-specific vocabulary signature
kg vocabulary analytics fingerprint "ML Systems"

# Output:
# Distinctive relationship types for "ML Systems":
# 1. TRAINS_ON (87% unique to this ontology)
# 2. PREDICTS (76% unique)
# 3. OPTIMIZES (68% unique)
#
# Suggests: ML domain needs specialized vocabulary beyond core types

# Vocabulary growth forecast
kg vocabulary analytics forecast --months 6

# Output:
# Current vocabulary: 87 active types
# Projected (6 months): 142 types
#
# ⚠ EXCEEDS MAX LIMIT (100 types)
# Recommended action: Prune 42 low-value types
# Candidates: [list of least-used types with value scores]
```

**Curator Dashboard UI (Future):**

```
╔═══════════════════════════════════════════════════════════════╗
║          VOCABULARY ANALYTICS DASHBOARD                       ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  📈 TRENDING TYPES (30 days)          🔗 CO-OCCURRENCE NET   ║
║  ┌─────────────────────────┐          ┌──────────────────┐   ║
║  │ OPTIMIZES    ▁▃▅▇█ +340%│          │    [Graph View]  │   ║
║  │ MONITORS     ▂▄▆▇█ +180%│          │                  │   ║
║  └─────────────────────────┘          └──────────────────┘   ║
║                                                               ║
║  🎯 ONTOLOGY FINGERPRINTS              📊 GROWTH FORECAST    ║
║  ┌─────────────────────────┐          ┌──────────────────┐   ║
║  │ ML Systems:             │          │ Current: 87      │   ║
║  │  - TRAINS_ON (87%)      │          │ +6mo: 142 ⚠     │   ║
║  │  - PREDICTS (76%)       │          │ Action: Prune 42 │   ║
║  └─────────────────────────┘          └──────────────────┘   ║
╚═══════════════════════════════════════════════════════════════╝
```

## Implementation Plan

### Phase 1: LLM-Assisted Suggestions (2-3 weeks)

1. Create `vocabulary_suggestions` table for caching LLM analysis
2. Implement `suggest_vocabulary_actions()` function
3. Add `--with-suggestions` flag to `kg vocabulary review`
4. Build `approve-batch` command for high-confidence suggestions
5. Test accuracy on historical skipped relationships

### Phase 2: Ontology Versioning (2-3 weeks)

1. Create `ontology_versions` and `concept_version_metadata` tables
2. Implement semantic versioning logic
3. Add version tracking to all vocabulary mutations
4. Build time-travel query support
5. Create migration tool for breaking changes

### Phase 3: Analytics Dashboard (3-4 weeks)

1. Implement analytics queries (trends, cooccurrence, fingerprints)
2. Build CLI visualization commands
3. Create forecast models (linear regression → time series)
4. Develop curator dashboard UI (web-based)
5. Integrate with monitoring/alerting system

## Benefits

### 1. Curator Efficiency

- **10x faster curation:** LLM suggests actions, curator validates (not discovers)
- **Reduced cognitive load:** Clear recommendations with confidence scores
- **Batch operations:** Approve 50+ types in one command vs 50 individual decisions

### 2. Ontology Quality

- **Consistent categorization:** LLM applies uniform semantic analysis
- **Fewer synonyms:** Automated similarity detection prevents duplicates
- **Formal versioning:** Clear evolution history, no "drift"

### 3. Strategic Insights

- **Proactive vocabulary planning:** Forecasts prevent reactive scrambling
- **Domain discovery:** Trending types reveal emerging concepts in corpus
- **Ontology profiling:** Understand what makes each domain unique

### 4. System Intelligence

- **Self-improving:** Analytics feed back into curation recommendations
- **Transparent evolution:** Version history provides full audit trail
- **Migration safety:** Breaking changes handled with formal process

## Metrics

**Curation Speed:**
- Manual review time: 5 min/type (current) → 30 sec/type (with suggestions)
- Batch approval: <1 minute for 50 high-confidence suggestions

**Accuracy:**
- LLM synonym detection: Target >90% precision
- Category suggestions: Target >85% accuracy (vs curator ground truth)

**Knowledge Discovery:**
- Trending types identified: 5-10 per month
- Ontology fingerprints: 10-20 distinctive types per ontology
- Growth forecast: ±15% accuracy over 6 months

## Risks and Mitigations

### Risk 1: LLM Hallucination in Suggestions

**Risk:** LLM suggests incorrect synonym mapping or category

**Mitigation:**
- Curator ALWAYS validates (LLM is advisor, not decision-maker)
- Confidence thresholds (only show suggestions >0.8)
- Audit trail tracks LLM suggestions vs curator decisions
- Periodic accuracy review to retrain prompts

### Risk 2: Version Explosion

**Risk:** Every minor change creates new version (table bloat)

**Mitigation:**
- Batch changes into logical releases (weekly/monthly)
- Compress patch versions (only major/minor versions get snapshots)
- Archive old versions (>1 year) to cold storage

### Risk 3: Analytics Complexity

**Risk:** Too many metrics overwhelm curators

**Mitigation:**
- Start with 3 key dashboards (trends, network, forecast)
- Progressive disclosure (simple view by default, details on demand)
- Contextual recommendations ("Try expanding vocabulary in emerging areas")

## Alternatives Considered

### Alternative 1: Fully Automated Vocabulary (No Curator)

**Rejected:**
- Removes human oversight of semantic quality
- Risk of vocabulary explosion (LLM may over-create types)
- Cannot handle domain-specific nuance
- Violates "curator as validator" principle

**Decision:** Keep human in loop, use LLM as assistant

### Alternative 2: Manual Analytics (SQL Queries)

**Rejected:**
- Requires curator to write complex SQL
- No predictive capabilities
- Insights hidden in raw data

**Decision:** Pre-built analytics with visualization

### Alternative 3: Snapshot-Based Versioning (Not Immutable)

**Rejected:**
- Cannot do time-travel queries reliably
- Version history can be accidentally modified
- Breaks audit compliance

**Decision:** Immutable version records with JSONB snapshots

## Success Criteria

**Phase 1 (LLM Suggestions):**
- [ ] 80% of suggestions accepted by curator (high trust)
- [ ] <30 seconds per relationship type review (vs 5 min manual)
- [ ] Zero false positives in high-confidence (>0.9) suggestions

**Phase 2 (Versioning):**
- [ ] Every vocabulary change tracked in version history
- [ ] Breaking changes flagged with migration path
- [ ] Time-travel queries return correct historical vocabulary

**Phase 3 (Analytics):**
- [ ] Trending types dashboard identifies 5+ actionable insights/month
- [ ] Vocabulary growth forecast within ±15% accuracy
- [ ] Curator uses dashboard weekly (tracked via usage logs)

## References

- **LLM Schema Matching:**
  - Gu et al. (2024): "GPT-4 for Schema Matching" - 87% accuracy on COMA++ benchmark
  - Li et al. (2023): "Large Language Models as Ontology Aligners"

- **Ontology Versioning:**
  - W3C OWL 2 Web Ontology Language: Versioning semantics
  - Klein & Fensel (2001): "Ontology Versioning and Change Detection on the Web"
  - Semantic Web Best Practices: owl:versionInfo, owl:priorVersion

- **Knowledge Discovery:**
  - Fayyad et al. (1996): "From Data Mining to Knowledge Discovery in Databases"
  - Codd (1993): "Providing OLAP to User-Analysts" - Dimensional analytics

- **Related ADRs:**
  - ADR-025: Dynamic Relationship Vocabulary Management
  - ADR-024: Multi-Schema PostgreSQL Architecture
  - ADR-014: Job Approval Workflow (human-in-loop pattern)

## Future Enhancements

### Phase 4: Active Learning Loop

- Track curator overrides of LLM suggestions
- Retrain suggestion model on curator feedback
- Personalized suggestions per curator (learn their preferences)

### Phase 5: Cross-Ontology Alignment

- Detect when different ontologies use different types for same concept
- Suggest canonical mappings across ontologies
- Enable federated graph queries

### Phase 6: Natural Language Curation

```bash
# Natural language interface for curators
kg vocabulary curate "Make OPTIMIZES a synonym of IMPROVES"
# → System translates to: kg vocabulary alias OPTIMIZES --maps-to IMPROVES

kg vocabulary curate "Show me types related to performance"
# → System searches by semantic category and embeddings
```

---

**Status:** Proposed for discussion
**Next Steps:**
1. Review with knowledge graph team
2. Pilot LLM suggestions on historical skipped_relationships
3. Measure curator time savings
4. Build versioning infrastructure
5. Prototype analytics dashboard
