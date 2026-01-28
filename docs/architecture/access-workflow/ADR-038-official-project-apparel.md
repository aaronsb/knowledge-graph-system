---
status: Proposed
date: 2025-10-17
deciders:
  - Solo developer with questionable fashion sense
---

# ADR-038: Official Project Apparel Design Specifications

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

---

## Appendix C: Competitive Landscape Analysis (The "Why Is No One Else Doing This" Sequel)

*Added 2026-01-28 after external review by Gemini 2.5 Pro, who was asked "why are we weird" and delivered a thesis*

### The Emotional Journey, Part 2

Following the discovery documented in this ADR (nobody else does streaming entity resolution), we asked an AI to explain *why* we're alone in this space. The answer was simultaneously validating and concerning.

### The "Agent Memory" Market

Apparently we exist in the same conceptual space as several "Agent Brain" projects. Here's why they're all wrong and we're right (copium levels: maximum):

#### Zep: "A Very Efficient Secretary"

Zep is built for scale and speed—designed for companies building chatbots that remember users across millions of sessions.

```
Zep's approach:
if user.preference_changed:
    old_fact.invalidate()
    new_fact.store()
    # Done in <200ms
    # Whether it's TRUE is someone else's problem
```

**Their pitch:** "Fast retrieval for conversational AI!"
**Our response:** "But is the retrieval *correct*?"
**Their response:** "94.5% of the time!"
**Our response:** *gestures at t-shirt*

#### Mem0: "A Post-it Note Archive"

Formerly known as EmbedChain. Focuses on "long-term memory for AI."

**Architecture:** Essentially a fancy wrapper around a vector database that updates a user profile. Very flat. No epistemic depth.

**Their approach:** Facts exist or they don't.
**Our approach:** Facts exist with a grounding score of -1.0 to +1.0, semantic diversity metrics, evidence provenance, and a FUSE filesystem to browse them.

**Who's overengineering?** *(points at mirror)*

#### Microsoft GraphRAG: "A Corporate Wiki"

The current titan of the space. Backed by Microsoft Research. Probably has more PhDs than we have commits.

**Their approach:** Build massive global summaries, identify "communities" of ideas, then ask an LLM at query time "Hey, there's a conflict here, what do you think?"

**Our approach:** Mathematically encode conflict into the graph structure itself. No post-hoc LLM arbitration required.

**GraphRAG:** "We'll let the AI figure it out."
**Us:** "We'll do math so the AI doesn't have to figure it out."

*(One of these approaches scales to millions of users. The other one is correct.)*

### The Comparison Matrix (Now With Vibes)

| Feature | Our System | Zep | Mem0 | GraphRAG |
|---------|------------|-----|------|----------|
| **Primary Goal** | Epistemic Truth | Agent Latency | User Personalization | Global Comprehension |
| **Conflict Handling** | Mathematical (-1 to +1) | Temporal Invalidation | Overwriting | "Ask LLM Later" |
| **Filesystem Access** | Yes (FUSE) | No | No | No |
| **Search Method** | Exact O(n) | ANN (HNSW) | ANN (Vector) | Graph + ANN |
| **Recall** | 100% | 94.5% | ~95% | Variable |
| **Speed** | 2 seconds | 200ms | 150ms | 500ms |
| **ADRs Written** | 88+ | Unknown | Unknown | Probably reasonable |
| **T-Shirt ADR** | You're reading it | No | No | Definitely not |
| **Vibe (Aspiration)** | "Library of Alexandria" | "Efficient Secretary" | "Post-it Archive" | "Corporate Wiki" |
| **Vibe (Reality)** | "Pepe Silvia Board" | Same | Same | Same |

### The Uncomfortable Truth

> "If a doctor is using a graph to find contradictions in medical papers, they don't want 'approximate' results (94.5% recall). They want 100% recall, even if it takes 2 seconds instead of 200ms."

This is our justification. We're clinging to it.

### Alternative T-Shirt Design 6: "The Competitive Analysis"

**Front:**
```
OUR COMPETITORS:
✓ Faster than us
✓ More scalable than us
✓ Better funded than us
✓ More users than us

US:
✓ Correct
```

**Back:**
```
Recall comparison:
• Zep (HNSW):     94.5%
• Mem0 (Vector):  ~95%
• GraphRAG:       ¯\_(ツ)_/¯
• Us (O(n)):      100%

The 5.5% we catch?
That's the contradiction that matters.
```

### The "Solo Dev" Observation

> "The fact that you have 88 ADRs and a FUSE filesystem makes your project more of a 'Semantic Operating System' than just a 'memory layer.' Zep is a tool you plug into an app; your system is an environment you live in to do research."

**Accurate.** We didn't build a library; we built a research environment. Whether anyone else wants to live in it remains to be seen.

---

## Appendix D: The Wes Anderson Interpretation

*Also from Gemini 2.5 Pro, who may understand this project better than we do*

> "You've built the Wes Anderson version of graph memory."

This is the most structurally accurate description of a software project ever written.

If this project is the Wes Anderson version of graph memory, then ADR-038 isn't just a design document—it's a **costume department memo**. It explains why we have 88+ ADRs: Wes Anderson doesn't just "film a scene," he specifies the exact shade of saffron for the curtains and the kerning on the telegram.

### Why the Analogy is Technically Perfect

#### 1. The "Obsessive Planimetric" Detail

Wes Anderson is famous for perfectly centered, symmetrical shots. Our O(n) full-scan is the computational version of that.

| Approach | Camera Metaphor | Result |
|----------|-----------------|--------|
| HNSW (everyone else) | Hand-held, shaky but efficient | "Good enough" (94.5% recall) |
| O(n) full-scan (us) | Stationary tripod, prime lens | Perfect focus across entire frame |

We insist on setting up the shot correctly. It takes longer. The composition is perfect. No "stochastic" blur.

#### 2. The Color Palette (Epistemic Grounding)

While the rest of the AI world is a gritty, gray "vector space" of floating-point numbers, our system has a very specific chromatic logic:

```
GROUNDING SCORE COLOR PALETTE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
+1.0  ████████  Soft Pastel Pink      (Supporting evidence)
 0.0  ████████  Neutral Cream         (Ungrounded)
-1.0  ████████  Muted Mustard Yellow  (Contradictory evidence)

SEMANTIC DIVERSITY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
High  ████████  Deep Teal             (Fabrication detection)
```

We aren't just storing data; we're *color-grading the truth*.

#### 3. The "Cross-Section" Set (FUSE Filesystem)

The FUSE filesystem is the "Life Aquatic" / "Grand Budapest Hotel" cross-section shot. Instead of a black-box API, we've built a dollhouse where you can see every room (concept) by opening a "door" (directory) in the terminal.

```bash
$ ls /mnt/graph/concepts/the_bitter_lesson/evidence/
  source_001.txt
  source_002.txt
  contradicting_paper.txt

$ cat /mnt/graph/concepts/the_bitter_lesson/grounding_score
  0.73
```

It turns "traversing a graph" into "walking through a meticulously curated set."

**Normal database:** "Query the API to retrieve concept relationships."
**Us:** "Open the filing cabinet. It's the third drawer."

#### 4. The Meticulous Documentation

88+ ADRs are the narrator's voice-over. They explain the history of a decision with a dry, slightly detached wit, ensuring that even if the "solo developer" is the only one who ever sees it, the provenance of the madness is preserved.

*[Narrator voice]*: "The developer had written 88 Architecture Decision Records. Whether anyone would ever read them remained unclear. But they existed, and that was what mattered."

### Alternative T-Shirt Design 7: "The Wes Anderson"

**Front:**
```
┌─────────────────────────────────┐
│                                 │
│    THE KNOWLEDGE GRAPH SYSTEM   │
│                                 │
│    A Film by Solo Developer     │
│                                 │
│         Chapter 38:             │
│    "The Full-Scan Decision"     │
│                                 │
└─────────────────────────────────┘
```

**Back:**
```
CAST OF CHARACTERS

The Concept ............ Vector (1536-dimensional)
The Evidence ........... Source Document
The Grounding Score .... Float (-1.0 to +1.0)
The FUSE Mount ......... /mnt/graph
The ADRs ............... 88 and counting
The Developer .......... Questionable decision-maker

"Filmed on location in PostgreSQL"
```

**Design notes:**
- Centered perfectly (obviously)
- Futura font (the only acceptable choice)
- Accompanied by a small, unnecessary handbook explaining the font choice
- Heavyweight cotton (to represent the O(n) weight)

### The French Dispatch Move

The FUSE filesystem—mapping a complex graph topology into a flat, 2D filesystem hierarchy—is the ultimate "French Dispatch" production design choice for a database.

- **Unnecessary?** Probably.
- **Beautiful?** Definitely.
- **Makes perfect sense once you understand the aesthetic?** Absolutely.

```
┌──────────────────────────────────────────────────┐
│              THE KNOWLEDGE GRAPH                 │
│              (Cross-Section View)                │
├──────────┬──────────┬──────────┬────────────────┤
│ /concepts│ /sources │ /evidence│ /relationships │
├──────────┼──────────┼──────────┼────────────────┤
│  idea_1/ │  doc_1/  │ inst_1/  │   SUPPORTS/    │
│  idea_2/ │  doc_2/  │ inst_2/  │  CONTRADICTS/  │
│  idea_3/ │  doc_3/  │ inst_3/  │    IMPLIES/    │
└──────────┴──────────┴──────────┴────────────────┘
```

---

## Appendix E: Closing Thoughts

The addition of these appendices brings the total length of this ADR to approximately 800 lines. This is:

1. **Entirely on brand** for a Wes Anderson production
2. **Thoroughly documented** for future archaeologists
3. **Probably unnecessary** but here we are

---

*"If you're doing something and nobody else is doing it, you're either a genius or an idiot. The 88 ADRs suggest we've at least documented which one."*

*"The developer stared at the terminal. The FUSE mount was working. The concepts were browsable. The grounding scores were accurate to two decimal places. Nobody would ever use it. It was perfect."* — The Narrator, probably
