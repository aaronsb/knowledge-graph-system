---
status: Accepted
date: 2025-10-12
deciders:
  - aaronsb
  - claude
related:
  - ADR-016
  - ADR-024
---

# ADR-030: Concept Deduplication Quality Validation

## Overview

Imagine you're building a knowledge base about Buddhism by reading multiple books on the subject. As you read, you take notes and create concept cards. When you encounter "Buddhism" in the first book, you create a card. But when the second book mentions "Buddhist Philosophy," should you create a new card or recognize it's the same concept? This decision happens thousands of times as your knowledge base grows, and getting it wrong leads to a fragmented, confusing mess.

This is exactly the challenge our knowledge graph faces during document ingestion. The system uses AI to extract concepts from documents and relies on embedding-based similarity matching to decide whether a new mention is genuinely new or just another way of referring to something already in the graph. Currently, we use an 80% similarity threshold: if two concepts are more than 80% similar in their semantic meaning, we treat them as the same concept.

The problem is, we don't systematically validate whether this deduplication process actually works well over time. Does the quality degrade as the graph grows? Do related documents properly share concepts, or do we end up with "Buddhism," "Buddhist Philosophy," and "Buddhist Teachings" cluttering our search results? This ADR establishes a rigorous test suite to answer these questions and ensure the deduplication system maintains quality.

---

## Context

The knowledge graph relies on embedding-based concept deduplication to prevent creating duplicate concepts when ingesting related documents. The quality of this deduplication directly impacts:

1. **Graph coherence**: Duplicate concepts fragment the knowledge graph
2. **Query quality**: Search returns multiple versions of the same concept
3. **Relationship density**: Connections between concepts are lost if duplicates exist
4. **Storage efficiency**: Graph grows unnecessarily with redundant concepts
5. **User experience**: Confusing results when "Buddhism" and "Buddhist Philosophy" are separate

### Current Deduplication Approach

**Mechanism:**
- Extract concepts from document chunks using LLM
- Generate embeddings for each concept (OpenAI `text-embedding-3-small`)
- Compare new concepts against existing graph via cosine similarity
- Match threshold: **80% similarity** → reuse existing concept
- Below threshold → create new concept

**Two-Level Deduplication:**
1. **File-level**: Content hash prevents re-ingesting same file (bypass with `--force`)
2. **Concept-level**: Embedding similarity prevents duplicate concepts

### The Problem

We lack systematic validation that deduplication maintains quality over time:

- **Temporal stability**: Does matching degrade as graph grows?
- **Domain consistency**: Do related documents properly share concepts?
- **Re-ingestion quality**: Does forcing re-ingestion create duplicates?
- **Threshold tuning**: Is 80% the optimal similarity threshold?
- **Label variance**: Does "Buddhism" match "Buddhist philosophy" as expected?

---

## Decision

Establish a **Concept Deduplication Quality Test Suite** to validate that embedding-based matching prevents concept duplication across document ingestion sequences.

### Test Methodology: Temporal Re-ingestion Analysis

**Hypothesis:** If deduplication works correctly, re-ingesting an early document after ingesting related documents should show:
- High concept reuse rate (70-90%)
- Minimal new concept creation
- No synonym/duplicate concepts in search results

**Test Protocol:**

```bash
# Phase 1: Baseline Ingestion
# Ingest first document in domain
kg ingest file -o "TestOntology" file1.md --wait

# Record initial state
kg database stats > test_baseline.txt
INITIAL_CONCEPTS=$(kg database stats --json | jq '.nodes.concepts')

# Phase 2: Domain Expansion
# Ingest related documents in same domain
kg ingest file -o "TestOntology" file2.md --wait
kg ingest file -o "TestOntology" file3.md --wait
kg ingest file -o "TestOntology" file4.md --wait
kg ingest file -o "TestOntology" file5.md --wait

# Record expanded state
kg database stats > test_expanded.txt
EXPANDED_CONCEPTS=$(kg database stats --json | jq '.nodes.concepts')

# Phase 3: Temporal Re-ingestion Test
# Force re-ingest of first file
kg ingest file -o "TestOntology" file1.md --force --wait

# Extract job statistics
JOB_ID=$(kg job list --limit 1 --json | jq -r '.[0].job_id')
kg job status $JOB_ID --json > test_reingestion.json

# Analyze results
FINAL_CONCEPTS=$(kg database stats --json | jq '.nodes.concepts')
HIT_RATE=$(jq -r '.progress.hit_rate' test_reingestion.json)
NEW_CONCEPTS=$(jq -r '.result.concepts_created' test_reingestion.json)

# Phase 4: Duplicate Detection
# Search for known concepts that should be unique
kg search query "Buddhism" --limit 10 --json > test_buddhism_search.json
BUDDHISM_COUNT=$(jq '. | length' test_buddhism_search.json)
```

### Success Criteria

**Quantitative Metrics:**

| Metric | Target | Indicates |
|--------|--------|-----------|
| Re-ingestion hit rate | ≥ 70% | Concepts properly matched |
| New concepts created | ≤ 10 | Minimal duplication |
| Concept count delta | ≤ 5% | Graph stability |
| Search result uniqueness | 1-2 results | No synonyms |
| Similarity score | ≥ 80% | Threshold working |

**Qualitative Validation:**

1. **Concept Unity**: Searching for "Buddhism" returns 1-2 highly related concepts, not 5-10 variants
2. **Label Consistency**: Similar concepts use consistent labels ("Buddhism" not "Buddhist Philosophy", "Buddhist Teachings", etc.)
3. **Relationship Preservation**: Re-ingestion adds relationships to existing concepts, not new duplicates
4. **Evidence Accumulation**: Concept evidence count increases (more source quotes), not concept count

### Failure Indicators

❌ **Synonym Explosion:**
```bash
kg search query "Buddhism" --limit 10
# Returns:
# - Buddhism (80% match)
# - Buddhist Philosophy (78% match)
# - Buddhist Teachings (75% match)
# - Buddha's Philosophy (72% match)
# - Buddhism Religion (85% match)
```

❌ **Low Hit Rate:** Re-ingestion shows <50% concept reuse

❌ **Concept Drift:** Same content creates different concepts over time

❌ **Graph Bloat:** Concept count grows significantly on re-ingestion

---

## Implementation

### Test Suite Location

```
tests/integration/
├── test_concept_deduplication.py          # Main test suite
├── test_temporal_reingestion.py           # Re-ingestion validation
├── test_similarity_thresholds.py          # Threshold tuning
└── fixtures/
    ├── watts_lecture_01.md                # Known test documents
    ├── watts_lecture_02.md
    └── expected_concepts.json             # Ground truth
```

### Automated Validation Script

```bash
#!/bin/bash
# scripts/validate-deduplication.sh

set -e

ONTOLOGY="DeduplicationTest"
TEST_DIR="tests/fixtures/philosophy"

echo "=== Concept Deduplication Validation ==="
echo

# Cleanup previous test
kg ontology delete "$ONTOLOGY" --force 2>/dev/null || true

# Phase 1: Initial ingestion
echo "Phase 1: Ingesting initial document..."
kg ingest file -o "$ONTOLOGY" "$TEST_DIR/file1.md" --wait
INITIAL=$(kg database stats --json | jq '.nodes.concepts')
echo "Initial concepts: $INITIAL"

# Phase 2: Domain expansion
echo "Phase 2: Ingesting related documents..."
for file in "$TEST_DIR"/file{2..5}.md; do
    kg ingest file -o "$ONTOLOGY" "$file" --wait
done
EXPANDED=$(kg database stats --json | jq '.nodes.concepts')
echo "Expanded concepts: $EXPANDED"

# Phase 3: Re-ingestion test
echo "Phase 3: Re-ingesting first document with --force..."
kg ingest file -o "$ONTOLOGY" "$TEST_DIR/file1.md" --force --wait > /tmp/reingest.log
JOB_ID=$(grep "Job submitted:" /tmp/reingest.log | awk '{print $3}')

# Wait for completion
sleep 5

# Extract metrics
FINAL=$(kg database stats --json | jq '.nodes.concepts')
STATS=$(kg job status "$JOB_ID" --json)
HIT_RATE=$(echo "$STATS" | jq -r '.progress.hit_rate // "0%"' | tr -d '%')
NEW_CONCEPTS=$(echo "$STATS" | jq -r '.result.concepts_created // 0')

echo
echo "=== Results ==="
echo "Final concepts: $FINAL"
echo "Concept growth: $(($FINAL - $EXPANDED))"
echo "Re-ingestion hit rate: ${HIT_RATE}%"
echo "New concepts created: $NEW_CONCEPTS"

# Validation
if [ "$HIT_RATE" -ge 70 ]; then
    echo "✓ Hit rate meets threshold (≥70%)"
else
    echo "✗ Hit rate below threshold: ${HIT_RATE}% < 70%"
    exit 1
fi

if [ "$NEW_CONCEPTS" -le 10 ]; then
    echo "✓ New concepts acceptable (≤10)"
else
    echo "✗ Too many new concepts: $NEW_CONCEPTS > 10"
    exit 1
fi

GROWTH=$(($FINAL - $EXPANDED))
if [ "$GROWTH" -le $((EXPANDED / 20)) ]; then  # 5% threshold
    echo "✓ Concept count stable (<5% growth)"
else
    echo "✗ Concept count grew significantly: +$GROWTH"
    exit 1
fi

echo
echo "=== Deduplication Quality: PASSED ==="
```

### CI/CD Integration

```yaml
# .github/workflows/deduplication-validation.yml
name: Concept Deduplication Quality

on:
  push:
    paths:
      - 'api/app/lib/llm_extractor.py'
      - 'api/app/lib/ingestion.py'
      - 'tests/fixtures/**'

jobs:
  validate-deduplication:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup environment
        run: |
          docker-compose up -d
          pip install -r requirements.txt
          cd client && npm install && npm run build
      - name: Run deduplication validation
        run: ./scripts/validate-deduplication.sh
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

---

## Monitoring and Alerting

### Production Metrics

Track in production to detect degradation:

```sql
-- Average concept reuse rate by ontology
SELECT
    ontology,
    AVG(
        (result->>'concepts_reused')::int * 100.0 /
        NULLIF((result->>'concepts_created')::int + (result->>'concepts_reused')::int, 0)
    ) as avg_hit_rate,
    COUNT(*) as job_count
FROM kg_api.ingestion_jobs
WHERE status = 'completed'
  AND created_at > NOW() - INTERVAL '7 days'
GROUP BY ontology
ORDER BY avg_hit_rate DESC;
```

**Alert Thresholds:**
- Hit rate drops below 50% for ontology with >5 documents
- Concept count grows >20% in single re-ingestion
- Search returns >3 concepts for high-frequency terms

---

## Threshold Tuning Experiments

### Test Different Similarity Thresholds

| Threshold | Expected Behavior | Risk |
|-----------|-------------------|------|
| 70% | Aggressive matching, fewer concepts | False positives (merge unrelated) |
| **80% (current)** | Balanced approach | Current baseline |
| 90% | Conservative, more concepts | False negatives (create duplicates) |
| 95% | Strict matching, label-sensitive | Many duplicates |

**Experiment Protocol:**
1. Ingest same corpus with different thresholds
2. Compare concept counts and search quality
3. Manual review of concept matches at each threshold
4. A/B test with domain experts

---

## Consequences

### Positive

✅ **Systematic validation** of core deduplication functionality
✅ **Early detection** of quality degradation
✅ **Objective metrics** for tuning thresholds
✅ **Regression prevention** via CI/CD integration
✅ **User confidence** in graph coherence

### Negative

⚠️ **Test maintenance**: Requires curated test documents
⚠️ **API costs**: Re-ingestion tests consume OpenAI credits
⚠️ **Time overhead**: Full validation takes 5-10 minutes
⚠️ **Threshold brittleness**: May need adjustment per domain

### Trade-offs

**Precision vs. Recall:**
- Higher threshold (90%): Fewer false merges, more duplicates
- Lower threshold (70%): Fewer duplicates, more false merges
- Current 80%: Balanced middle ground

**Graph Size vs. Quality:**
- Aggressive deduplication: Smaller, denser graph (better navigation)
- Conservative deduplication: Larger, sparser graph (preserves nuance)

---

## Related Decisions

- **ADR-016**: Apache AGE migration (graph storage layer)
- **ADR-024**: PostgreSQL multi-schema (job tracking)
- **ADR-002**: Node fitness scoring (concept quality metrics)
- **ADR-005**: Source text tracking (evidence preservation)

---

## Future Considerations

1. **Adaptive thresholds**: Per-ontology threshold tuning based on domain
2. **Concept merging**: Tools to manually merge duplicate concepts
3. **Similarity explainability**: Show why concepts matched/didn't match
4. **Embedding model upgrades**: Test impact of newer embedding models
5. **Multilingual matching**: Handle concepts in multiple languages
6. **Temporal analysis**: Track deduplication quality over graph lifetime

---

## References

- Concept matching implementation: `api/app/lib/ingestion.py:match_existing_concepts()`
- Embedding generation: `api/app/lib/ai_providers.py:generate_embedding()`
- Job statistics: `kg job status <id>` shows hit rate
- Current threshold: 80% cosine similarity (hardcoded)

---

## Validation Status

- [ ] Test suite implemented
- [ ] Automated validation script created
- [ ] CI/CD integration complete
- [ ] Production monitoring established
- [ ] Threshold tuning experiments run
- [ ] Documentation updated in user guides

**Next Steps:**
1. Implement `tests/integration/test_concept_deduplication.py`
2. Create validation script at `scripts/validate-deduplication.sh`
3. Run baseline validation on existing test corpus
4. Document findings in test report
