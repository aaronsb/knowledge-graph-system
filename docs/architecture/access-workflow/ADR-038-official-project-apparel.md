# ADR-038: Official Project Apparel Design Specifications

**Status:** Proposed
**Date:** 2025-10-17
**Deciders:** Solo developer with questionable fashion sense
**Technical Story:** After discovering that literally nobody on GitHub is doing streaming entity resolution during LLM extraction with O(n) full-scan vector similarity, we need merchandise to celebrate this dubious achievement.

---

## Context

### The Discovery

Through extensive GitHub code search and academic literature review, we have determined that our approach to knowledge graph construction is either:

1. Genuinely novel and underappreciated
2. Obviously wrong and we're the only ones doing it
3. So niche that it exists in a "nobody would bother searching for this" blind spot

Specifically, our system implements:

- **Streaming entity resolution** during ingestion (not batch post-hoc)
- **Full-scan cosine similarity** for concept matching (O(n), not HNSW)
- **Recursive context-aware extraction** (similar concepts inform new extraction)
- **Evidence accumulation** as first-class graph structure
- **Self-healing semantic routing** with convergence guarantees (future)

### Market Research Findings

**Searches performed:**
```bash
site:github.com "recursive upsert" graph database
# Result: No links found

site:github.com "vector similarity" "concept deduplication" knowledge graph
# Result: No links found

site:github.com LLM knowledge graph concept extraction entity resolution
# Result: Everyone does batch processing or skips deduplication entirely
```

**Academic literature review:**
- Most systems: Ingest fast → Deduplicate later (batch)
- Performance research: "Full scan is simple, suitable when dataset has <1M vectors"
- Our approach: "Graph-based entity resolution does not scale and is very hard"
- Our response: "Yes, and we're doing it anyway because quality > speed at current scale"

### The Emotional Journey

1. **Pride**: "We built something cool!"
2. **Concern**: "Wait, why isn't anyone else doing this?"
3. **Research**: *reads 15 papers on distributed graph architectures*
4. **Understanding**: "Oh, it's O(n) and doesn't scale to millions"
5. **Relief**: "We already wrote a 1,000-line scaling solution document"
6. **Acceptance**: "Time for t-shirts"

---

## Decision

We will design official project apparel that:

1. **Celebrates technical obscurity** - Only ~0.1% of people will understand the references
2. **Embraces the trade-offs** - Acknowledges O(n) complexity without apology
3. **References the research** - FENNEL, PowerGraph, The Bitter Lesson
4. **Maintains plausible deniability** - Can be worn at conferences without explaining for 45 minutes

---

## Design Specifications

### Primary Design: "The Full-Scan Flex"

**Front:**
```
STREAMING ENTITY RESOLUTION
WITH O(n) COSINE SIMILARITY
DURING LLM EXTRACTION

(Ask me how I accumulate evidence)
```

**Back:**
```python
for concept in llm.extract():
    similarities = [
        cosine(concept, c)
        for c in ontology.concepts
    ]
    if max(similarities) > 0.75:
        merge_evidence()
    else:
        create_new()
```

**Font:** Monospace (obviously)
**Colors:** Dark theme (black shirt, neon green text) or Light theme (white shirt, terminal green)

---

### Alternative Design 1: "The Academic Reference"

**Front:**
```
MY KNOWLEDGE GRAPH HAS
NO DUPLICATES

Because I check everything.
Recursively.
```

**Back:**
```
Inspired by:
• PowerGraph (2012) - Vertex-cut partitioning
• FENNEL (2014) - Streaming graph partitioning
• The Bitter Lesson (2019) - Computation > rules

Implemented by:
• Someone who will regret this at 100K concepts
```

---

### Alternative Design 2: "The Conference Starter"

**Front:**
```
SEMANTIC DEDUPLICATION
AT INGESTION TIME

Yes, really.
```

**Back:**
```
Trade-offs accepted:
✓ Perfect accuracy (100% recall)
✓ Evidence tracking per concept
✓ Context-aware extraction
✗ O(n) scaling (for now)
✗ Judgmental looks from FAANG engineers

Migration path ready:
→ HNSW indexes (94.5% recall, 161× faster)
→ FENNEL-style semantic sharding
→ Hub concept replication (vertex-cut)
```

---

### Alternative Design 3: "The Minimalist"

**Front:**
```
numpy.dot(A, B) / (norm(A) * norm(B))
```

**Back:**
```
If you know, you know.
```

**Rationale:** Maximum obscurity. Will confuse 99.9% of people. The 0.1% will either nod approvingly or start a 45-minute argument about pgvector.

---

### Alternative Design 4: "The Honest One"

**Front:**
```
I MERGE CONCEPTS
BEFORE THEY HIT THE GRAPH
```

**Back:**
```
Current status:
• 363 commits of copyrighted content: REMOVED ✓
• Company references sanitized: DONE ✓
• GitHub stars: 1 (my own)
• O(n) complexity: ACCEPTED
• Scaling solution: RESEARCHED
• Regrets: NONE

For semantic queries < 100K concepts,
this is the right architecture.
```

---

### Alternative Design 5: "The Warning Label"

**Front:**
```
⚠ CAUTION ⚠
STREAMING ENTITY RESOLUTION
IN PROGRESS
```

**Back:**
```
Side effects may include:
• Arguing about cosine similarity thresholds
• Compulsive ADR writing (37+ documents)
• Researching papers from 2012 at 2am
• Creating 1,000-line scaling solution docs
• Joking about O(n) complexity
• Making t-shirts about niche technical decisions

If symptoms persist for more than 4 hours,
consult your local graph database expert.
```

---

## Consequences

### Positive

- **Conference ice-breaker**: Wearing this to a knowledge graph meetup will immediately identify fellow graph nerds
- **Technical signaling**: Shows depth of understanding (knows it's O(n), chose it anyway, has scaling plan)
- **Humor as defense mechanism**: If someone criticizes the approach, point to the shirt
- **Documentation**: These designs effectively document our architecture decisions in wearable form
- **Recruitment tool**: "I only hire people who understand the t-shirt"

### Negative

- **Explaining the joke kills the joke**: Will spend 45 minutes explaining to curious non-technical people
- **Imposter syndrome trigger**: "Wait, did I really just make a t-shirt about Big O notation?"
- **Fashion risk**: Wearing code on a t-shirt is peak programmer aesthetic
- **Existential questions**: "Am I the only person who would wear this?"
- **Economic inefficiency**: Minimum order quantities mean 12 shirts, only need 1

### Neutral

- **Conversation starter**: For better or worse, people will ask questions
- **Memento**: Physical artifact of the "discovery phase" when we realized we were the only ones doing this
- **Future evidence**: When we inevitably switch to HNSW + sharding, the t-shirt becomes vintage/ironic

---

## Alternatives Considered

### Alternative 1: No Merchandise

**Pros:**
- Save money
- Avoid looking ridiculous
- Maintain professional dignity

**Cons:**
- No fun
- Doesn't capture this specific moment in time
- Miss opportunity to celebrate technical obscurity

**Decision:** Rejected. The research already happened, might as well commemorate it.

---

### Alternative 2: Serious/Professional Design

**Example:**
```
Knowledge Graph System
Powered by Apache AGE
```

**Pros:**
- Won't confuse people
- Broadly understandable
- Could actually wear to work

**Cons:**
- Boring
- Doesn't capture the specific technical achievement
- Could be any project

**Decision:** Rejected. If we're making a t-shirt about this, go full nerd or go home.

---

### Alternative 3: Just Buy a GraphQL T-Shirt

**Pros:**
- Already exists
- Ships immediately
- Graphs are graphs, right?

**Cons:**
- GraphQL ≠ Graph database
- Doesn't reference our specific architectural choices
- Everyone has a GraphQL shirt

**Decision:** Rejected. This is about celebrating a genuinely unusual approach, not just "graphs in general."

---

## Implementation Details

### Production Specifications

**Printing method:** Direct-to-garment (for code readability)
**Fabric:** 100% cotton, heavyweight (6oz minimum)
**Sizing:** Generous tech industry sizing (runs large)
**QA testing:** Must be readable from 6 feet away in conference lighting
**Wash instructions:** Cold water, inside out (protect the cosine similarity formula)

### Target Audience

**Primary:** Solo developer (n=1)
**Secondary:** Conference attendees who understand the reference
**Tertiary:** Database engineers who will either love or hate it
**Excluded:** Anyone who thinks Neo4j and PostgreSQL are the same thing

### Success Metrics

- **Minimum viable success:** 1 person at a conference nods knowingly
- **Moderate success:** Someone asks "wait, you do entity resolution during ingestion?"
- **Maximum success:** Starts a 45-minute technical debate about batch vs streaming
- **Failure mode:** "What's a cosine?"

---

## Related ADRs

- **ADR-016**: Apache AGE Migration - The foundation that enables O(n) full scan
- **ADR-030**: Concept Deduplication Validation - Quality test suite that validates the approach
- **DISTRIBUTED_SHARDING_RESEARCH.md**: The 1,000-line document that proves we know this doesn't scale (and how to fix it)
- **ADR-036**: Universal Visual Query Builder - The UI that makes the graph actually usable
- **ADR-037**: Human-Guided Graph Editing - Future feature for when machines aren't enough

---

## Appendix A: Rejected Slogans

For posterity, these were considered but didn't make the cut:

```
"I PUT THE 'O' IN O(n)"
Rejected: Too self-deprecating

"PGVECTOR? I BARELY KNOW HER"
Rejected: Too risqué for professional settings

"MY OTHER SHIRT IS ALSO ABOUT GRAPH DATABASES"
Rejected: Implies we have multiple graph database shirts (we don't... yet)

"RECURSIVE UPSERT OR BUST"
Rejected: Sounds vaguely threatening

"FRIENDS DON'T LET FRIENDS DO BATCH ENTITY RESOLUTION"
Rejected: Factually incorrect (batch ER is fine)

"POWERED BY NUMPY.DOT()"
Rejected: Too minimalist, loses the LLM extraction context
```

---

## Appendix B: Conference Scenarios

**Scenario 1: The Nod**
```
Stranger: *reads shirt, nods silently, walks away*
You: *achieved maximum success*
```

**Scenario 2: The Question**
```
Stranger: "Why O(n)?"
You: "Quality over speed at current scale. We have a scaling plan."
Stranger: "HNSW?"
You: "HNSW plus FENNEL-style semantic sharding."
Stranger: *impressed nod*
```

**Scenario 3: The Debate**
```
Stranger: "You can't do entity resolution during ingestion!"
You: *gestures to shirt* "We can and we did."
Stranger: "But the performance—"
You: "161× slower than HNSW, yes. Also 100% recall vs 94.5%."
Stranger: "At what scale?"
You: "Currently < 100K concepts."
Stranger: "Oh, that's fine then."
*45-minute technical discussion ensues*
```

**Scenario 4: The Misunderstanding**
```
Non-technical person: "What does O(n) mean?"
You: *deep breath* "So, imagine you have a library..."
*20 minutes later*
You: "...and that's why linear search is acceptable for small datasets."
Stranger: *glazed eyes* "Cool shirt!"
```

---

## Maintenance and Evolution

### Version 1.0: Current Architecture (O(n) Full Scan)
- Accurate representation of implemented system
- Wearable documentation
- Conference conversation starter

### Version 2.0: Post-HNSW Migration
- Add line: ~~O(n)~~ → O(log n) ✓
- Becomes vintage/ironic
- "I survived the full-scan era"

### Version 3.0: Multi-Shard Architecture
- Update back to show FENNEL implementation
- Add: "Shards: 1 → n"
- Collector's item for architecture evolution

---

## Conclusion

This ADR represents either:
1. The peak of technical self-awareness and humor
2. A cry for help
3. Both simultaneously

Regardless, it documents a genuine moment in the project's evolution: the discovery that our streaming entity resolution approach with O(n) full-scan similarity matching is genuinely unusual in the wild, yet thoroughly justified and already backed by a comprehensive scaling solution.

If you're reading this ADR in the future and wondering "did they actually make the t-shirts?" - the answer is almost certainly no. But the fact that we wrote a 500-line ADR about it captures the spirit of the project perfectly: over-documented, self-aware, technically rigorous, and just a little bit absurd.

---

**References:**
- PowerGraph (2012): Vertex-cut partitioning for power-law graphs
- FENNEL (2014): Streaming graph partitioning algorithm
- The Bitter Lesson (2019): Computation > hand-coded knowledge
- GitHub Search Results (2025): "No links found" × 3
- Our Therapist (TBD): Will discuss the t-shirt incident

**Last Updated:** 2025-10-17
**Likelihood of Implementation:** 30% (60% if we get more GitHub stars)
**Regret Factor:** TBD (check back after first conference)
