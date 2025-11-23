# Recursive Upsert Architecture

**Version:** 2.0
**Date:** November 22, 2025
**Status:** Foundational Pattern

> **Core Innovation:** A semantic matching system that intelligently merges or creates concepts based on vector similarity as documents are ingested. Each new document recursively matches against the accumulating knowledge graph, building a unified conceptual structure across multiple sources.

---

## Table of Contents

1. [The Problem: Linear Information, Multidimensional Reality](#the-problem)
2. [The Solution: Recursive Semantic Upsert](#the-solution)
3. [How It Works: Multi-Stage Matching](#how-it-works)
4. [Why It Works Well](#why-it-works)
5. [The O(N) Problem](#the-on-problem)
6. [Evolution: How Later ADRs Improve The Pattern](#evolution)
7. [Trade-offs and Design Decisions](#trade-offs)

---

## The Problem

As Alan Watts articulated, human intelligence is fundamentally limited by its linear, scanning nature:

> "Human intelligence has a very serious limitation. That limitation is that it is a scanning system, of conscious attention, which is linear. That is to say, it examines the world, in lines. Rather as you would pass the beam of a flashlight across a room or a spotlight."

When we ingest documents into a knowledge system, we face two challenges:

1. **Sequential Processing:** Documents arrive one at a time, paragraph by paragraph
2. **Conceptual Overlap:** The same idea appears in different documents with different wording

Traditional approaches either:
- **Treat everything as new** → Massive duplication, no knowledge synthesis
- **Force exact ID matching** → Misses semantic equivalence, fragments knowledge
- **Use rigid schemas** → Fails to capture emergent concepts

We needed a pattern that could **accumulate knowledge organically** while **recognizing semantic equivalence** across different expressions of the same idea.

---

## The Solution: Recursive Semantic Upsert

**Recursive upsert** is a pattern where each new concept extracted from a document is:

1. **Compared** against all existing concepts using semantic similarity
2. **Merged** with a matching concept (if similarity > threshold)
3. **Created** as new (if no match found)
4. **Evidence added** regardless (quote + source provenance)

The "recursive" aspect comes from processing multiple documents sequentially, where each document's concepts are matched against the **accumulating graph state** from previous documents.

```
Document 1: Extract concepts → Create all (graph is empty)
                              → Graph has 10 concepts

Document 2: Extract concepts → Match against 10 existing
                              → Merge 3, Create 5 new
                              → Graph has 15 concepts

Document 3: Extract concepts → Match against 15 existing
                              → Merge 7, Create 2 new
                              → Graph has 17 concepts
```

The graph **learns** as it grows. Concepts that appear frequently across documents accumulate more evidence, while rare concepts remain distinct.

---

## How It Works: Multi-Stage Matching

When a new concept is extracted, we run a **cascade of matching strategies**:

### Stage 1: Exact ID Match
```
IF extracted concept_id exists in graph:
    → Use existing concept (LLM predicted correct ID)
    → Confidence: 100%
```

This happens when the LLM has seen similar text before and predicts an existing `concept_id`. We trust the LLM's judgment here.

### Stage 2: Vector Similarity Search (Primary)
```
1. Embed new concept: label + search_terms → 1536-dim vector
2. Cosine similarity against ALL existing concept embeddings
3. IF max_similarity > 0.85:
    → Use existing concept (semantic match)
    → Confidence: similarity_score
```

This is the **core of the pattern**. Vector similarity captures semantic equivalence:
- "linear scanning system" matches "sequential attention mechanism"
- "human-directed evolution" matches "genetic self-modification"

The threshold (0.85) balances:
- **Higher threshold (>0.90):** Fewer merges, more duplicates, safer
- **Lower threshold (<0.80):** More merges, potential false positives, aggressive

### Stage 3: Create New Concept
```
IF no match found:
    → Generate new concept_id
    → Store with embedding
    → Add to graph
```

This concept is now **available for future matching** in subsequent documents.

### Stage 4: Evidence Accumulation (Always)
```
Regardless of match/create:
    → Store quote (exact text from source)
    → Link to source (document + paragraph)
    → Track provenance
```

**Key insight:** Even merged concepts retain **all evidence** from all sources. You can trace back to where each instance appeared.

---

## Why It Works

### 1. **Semantic Tolerance**
Unlike exact string matching, vector similarity handles:
- Paraphrasing: "linear thinking" ≈ "sequential reasoning"
- Synonyms: "contradicts" ≈ "opposes"
- Different granularity: "AI safety concerns" ≈ "risks of artificial intelligence"

### 2. **LLM Context Awareness**
The LLM sees existing concepts during extraction, so it can:
- Predict existing IDs when confident
- Create new search terms that match existing concepts
- Understand domain-specific terminology

### 3. **Gradual Knowledge Synthesis**
The graph **evolves** as documents are added:
- Early documents create foundational concepts
- Later documents either reinforce or extend them
- Cross-document patterns emerge naturally

### 4. **Complete Provenance**
Every concept tracks:
- Which documents mentioned it
- What exact quotes support it
- When it first appeared

This enables:
- Evidence-based reasoning
- Source verification
- Cross-document analysis

---

## The O(N) Problem

The recursive upsert pattern has a **significant performance limitation**:

### Full-Scan Vector Search

Every new concept requires:
```
1. Compute embedding (OpenAI API call, ~100ms)
2. Load ALL existing concept embeddings (N vectors)
3. Compute cosine similarity for each (N comparisons)
4. Find maximum similarity
5. Compare to threshold
```

**Time Complexity:** O(N) per concept
**Space Complexity:** O(N × D) where D = embedding dimensions (1536)

### Real-World Impact

With 1,000 concepts in the graph:
- Each new concept: ~1,000 similarity calculations
- Document with 50 concepts: ~50,000 calculations
- 10 documents per day: ~500,000 calculations

**Current implementation:** Python NumPy, full scan, no indexing
**Typical performance:** 10-50ms per concept (acceptable for current scale)

### Why We Accept This Trade-off

1. **Simplicity:** No complex indexing logic, easy to debug
2. **Accuracy:** No false negatives from approximate search
3. **Current scale:** <10,000 concepts, performance is acceptable
4. **Future migration:** Can add HNSW/IVF later if needed (see ADR-055)

---

## Evolution: How Later ADRs Improve The Pattern

The recursive upsert pattern is **foundational**, but later architectural decisions significantly enhance it:

### ADR-028: Grounding Strength as Epistemic Feedback

**Problem:** Upsert creates concepts, but how do we know if they're *valid*?

**Enhancement:** Add **grounding strength** (-1.0 to 1.0) calculated from:
- Evidence consistency across sources
- Relationship support from connected concepts
- Contradiction detection

**Impact on Upsert:**
- Concepts with high grounding (>0.8) are more likely to match
- Concepts with negative grounding may indicate extraction errors
- Guides threshold tuning: if low-grounding concepts proliferate, raise threshold

### ADR-048: GraphQueryFacade (Namespace Safety)

**Problem:** As vocabulary metadata moves to the graph, upsert queries must not collide with vocabulary nodes.

**Enhancement:** Explicit `:Concept` labels in all queries, preventing namespace pollution.

**Impact on Upsert:**
```cypher
// Before (unsafe)
MATCH (n) WHERE n.embedding <-> $vec < 0.85

// After (safe)
MATCH (c:Concept) WHERE c.embedding <-> $vec < 0.85
```

### ADR-055: HNSW Vector Indexing (Future)

**Problem:** O(N) full scan becomes prohibitive at large scale.

**Enhancement:** Hierarchical Navigable Small World (HNSW) indexing for approximate nearest neighbor search.

**Impact on Upsert:**
- O(log N) search instead of O(N)
- Trade-off: 95-99% recall (might miss some matches)
- Enables 100K+ concept graphs

### ADR-065: Epistemic Status Classification

**Problem:** Not all concept merges are equally reliable.

**Enhancement:** Classify relationships by epistemic status:
- **AFFIRMATIVE:** High grounding, reliable merges
- **CONTESTED:** Mixed evidence, review recommended
- **CONTRADICTORY:** Negative grounding, potential false positive

**Impact on Upsert:**
- Flag uncertain merges for review
- Adjust thresholds based on relationship type
- Provide confidence metrics to users

---

## Trade-offs and Design Decisions

### Threshold Selection (0.85)

**Higher (0.90+):**
- ✅ Fewer false positives (wrong merges)
- ❌ More duplicates (missed semantic matches)
- Use case: High-precision domains (legal, medical)

**Current (0.85):**
- ✅ Balanced precision/recall
- ✅ Good for philosophical/conceptual documents
- ❌ Occasional false positives

**Lower (0.75-0.80):**
- ✅ Aggressive merging, fewer duplicates
- ❌ Higher false positive rate
- Use case: Exploratory research, brainstorming

### LLM Context: Show Existing Concepts?

**Current approach:** YES, show top 50 existing concepts during extraction

**Advantages:**
- LLM can predict existing IDs (Stage 1 match)
- LLM generates search terms that match existing concepts
- Reduces semantic drift over time

**Disadvantages:**
- Token cost (50 concepts ≈ 500 tokens per extraction)
- Potential bias toward existing concepts
- Doesn't scale beyond ~100 concepts in context

**Alternative:** No context, rely purely on vector similarity
**Future:** Hybrid approach with semantic retrieval

### Merge vs Create Philosophy

**Conservative (current):**
- Default to creating new concepts unless strong match
- Preserves nuance and subtle distinctions
- Accepts some duplication

**Aggressive:**
- Default to merging similar concepts
- Prioritizes deduplication over precision
- Risks losing subtle distinctions

**We chose conservative** because:
1. Duplicates can be merged later (manual or automated)
2. False merges are harder to split
3. Evidence accumulation works either way

---

## Summary

**Recursive upsert** is a deceptively simple pattern with profound implications:

1. **It works** because vector similarity captures semantic equivalence
2. **It scales** reasonably well to thousands of concepts (O(N) is acceptable)
3. **It evolves** as later ADRs add grounding, epistemic status, and indexing
4. **It's foundational** to how the system builds knowledge across documents

The key insight: **Don't force exact matches, don't accept everything as new—find the semantic middle ground and let evidence accumulate.**

Later enhancements (grounding, namespace safety, HNSW indexing, epistemic classification) address the pattern's limitations while preserving its core strength: **organic knowledge synthesis through semantic similarity.**

---

## Related ADRs

- **ADR-016:** Apache AGE Migration (graph database foundation)
- **ADR-028:** Grounding Strength Calculation (epistemic feedback)
- **ADR-042:** Ollama Integration (affects extraction cost)
- **ADR-048:** GraphQueryFacade (namespace safety)
- **ADR-055:** HNSW Vector Indexing (scaling beyond O(N))
- **ADR-065:** Epistemic Status Classification (merge reliability)

For complete system architecture, see [ARCHITECTURE.md](ARCHITECTURE.md).
