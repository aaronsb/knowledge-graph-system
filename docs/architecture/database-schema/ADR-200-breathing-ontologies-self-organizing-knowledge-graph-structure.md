---
status: Draft
date: 2026-01-29
deciders:
  - aaronsb
  - claude
related: [22, 25, 44, 46, 63, 65, 68, 70, 700, 701]
---

# ADR-200: Breathing Ontologies — Self-Organizing Knowledge Graph Structure

## Context

### The Current Model

Ontologies in this system are a string property (`document`) on Source nodes. When a document is ingested into ontology "ITSM," each Source chunk carries `document = 'ITSM'`. Concepts extracted from those sources are global — they merge across ontologies via embedding similarity (ADR-068). The ontology is a label, not an entity.

This design is simple and makes cascade deletion straightforward: find all sources where `document = X`, delete them, clean up orphaned concepts. But it creates three escalating problems as the graph grows:

1. **Ontological flatness.** The organizational layer is static while the concept layer grows. Thousands of concepts organized by a flat list of string labels. What started as meaningful taxonomy becomes arbitrary buckets.

2. **Boundary rigidity.** Concepts form clusters that don't respect ontology boundaries. Cross-ontology edges accumulate, signaling that human-imposed structure doesn't match the emergent structure of the knowledge itself.

3. **Maintenance burden.** Reorganizing ontologies requires human intervention, but humans can't see the graph's structure clearly enough to make good decisions. The system knows more about its own organization than its operators do.

### The Core Insight

**A concept is just an extremely narrow ontology.** If you explore a concept deeply enough, it becomes an organizing frame. The semantics of "concept" versus "ontology" is about scope and current attention, not fundamental type.

This implies the inverse: **an ontology is just a concept that has accumulated enough structure to serve as an organizing frame.**

| Dimension | Concept | Ontology |
|-----------|---------|----------|
| Lifecycle | Emerges from ingest, may be transient | Deliberately created or promoted, longer-lived |
| Stewardship | Often unowned, machine-generated | Someone "owns" this as an organizing frame |
| Ingest behavior | Is *created by* document processing | Is *targeted by* document upload |
| Query expectation | "What is this thing?" | "What's in this bucket?" |
| Growth pattern | Accumulates edges | Accumulates concepts |
| UI affordance | Detail view | Navigation/scoping |

The distinction is operational, not ontological. This means:

- Ontologies should be **nodes in the same graph**, not a separate metadata layer
- Ontologies should be **connected to each other** via edges, forming their own graph
- Concepts should be **promotable** to ontologies when they accumulate sufficient structure
- Ontologies should be **demotable** when they fail to earn their status

### Research Support

**Community detection** (Girvan-Newman, Louvain modularity) identifies clusters through edge betweenness centrality, modularity (internal vs external edge density), and local clustering coefficient. These are precisely the signals that indicate ontology candidates and boundaries. Community structure can be detected algorithmically — we don't need humans to draw boundaries (Girvan & Newman, 2002; Blondel et al., 2008).

**Ontological emergence** proposes that ontologies should adapt to changes in the underlying system through registration, monitoring, analysis, and adaptation. Ontologies cannot be fully pre-defined for dynamic systems; new conceptualizations must emerge as the knowledge base evolves (Aguilar et al., 2020).

**Fractal knowledge structures** provide theoretical grounding for self-similarity across scales. A concept can be "zoomed into" and treated as an organizing frame; an ontology can be "zoomed out from" and treated as a node in a larger structure. The difference is the viewport, not the entity (Massel et al., 2016; FFOM, 2025).

### Prior Art in This Codebase

Several existing systems provide infrastructure that directly supports this model:

| System | ADR | What It Provides |
|--------|-----|------------------|
| Grounding strength | ADR-044 | Polarity axis projection measuring epistemic alignment of incoming edges. Range: -1.0 to +1.0 |
| Confidence scoring | ADR-044 | Composite of relationship count, source count, evidence count, type diversity. Michaelis-Menten saturation curve. Measures how much graph structure has accumulated around a concept |
| Diversity analysis | ADR-063 | Gini-Simpson index of pairwise embedding similarity in N-hop neighborhood. Distinguishes coherent clusters from scattered connections |
| Polarity projection | ADR-070 | Projects concepts onto semantic axes, measures directional distribution. Can evaluate whether a concept's neighborhood is semantically aligned or scattered |
| Epistemic status | ADR-065 | Classification of vocabulary types by grounding patterns. Extensible to per-ontology measurement |
| Degree centrality | ADR-071 | Used in graph_parallelizer for bidirectional path search optimization. Computed on-demand but not surfaced as ranking |
| Epoch counters | ADR-079 | graph_metrics table tracks ingestion events, vocabulary changes, concept creation. Infrastructure for exposure tracking already exists |
| Aggressiveness curves | ADR-046 | Bezier curve-based sigmoid functions governing vocabulary management thresholds. Reusable for promotion/demotion pressure curves |

## Decision

### 1. Ontologies as Graph Nodes

Introduce `:Ontology` nodes in the Apache AGE graph with the same core properties as concepts:

```cypher
(:Ontology {
  ontology_id,          -- unique identifier
  name,                 -- what s.document currently holds as a string
  description,          -- what this knowledge domain covers
  embedding,            -- 1536-dim vector in the SAME space as concepts
  search_terms,         -- alternative names for similarity matching

  -- Lifecycle metadata
  creation_epoch,       -- global epoch when this ontology was created
  lifecycle_state,      -- 'active' | 'pinned' | 'frozen'
  protection_score,     -- cached, recomputed by background job
  mass_score,           -- cached composite of internal metrics
  coherence_score,      -- cached neighborhood coherence (1 - diversity)
  last_evaluated_epoch  -- when the breathing job last assessed this
})
```

**Same embedding space** as concepts. Ontology-to-concept similarity is a cosine similarity query. Membership becomes a gradient, not a binary. New content naturally matches to ontologies by embedding proximity — ontologies act as **attractors** in the vector space.

**Same vocabulary** as concept-to-concept edges. Ontology-to-ontology and ontology-to-concept edges use the managed relationship vocabulary (ADR-022, ADR-025). The structural tier (CONTAINS, SPECIALIZES, GENERALIZES, OVERLAPS) is most natural at the ontology level, but no vocabulary restriction is enforced — the same dynamic vocabulary management applies.

### 2. Source-to-Ontology Edges

```cypher
(:Source)-[:SCOPED_BY]->(:Ontology)
```

The `s.document` string property **stays** as a denormalized cache. Existing queries that filter by `s.document` continue working. The `:SCOPED_BY` edge is the source of truth for new code paths. This is the same dual-storage pattern as VocabType nodes mirroring `relationship_vocabulary` rows.

### 3. The Primordial Pool

Every graph begins with a single ontology: **"everything else"** (or a user-chosen name). All undirected content ingestion targets this ontology. As concepts accumulate, internal structure emerges — concepts about the same domain connect densely to each other while remaining sparsely connected to concepts about other domains.

This creates natural modularity within "everything else" — the precondition for differentiation.

### 4. Three Growth Modes

**Undirected growth** — Feed "everything else." Let structure emerge through differentiation. The system proposes promotions based on connectivity and coherence. This is the novel contribution.

**Directed growth** — Feed a specific ontology deliberately. This is how the system works today. A human or AI ingests documents targeting "ITSM" because they know what they're building. Concepts attach to that ontology's sources, and cross-ontology links form naturally as concepts merge with existing graph nodes via embedding similarity (ADR-068). No behavioral change needed — `POST /ingest` with an ontology name already does this.

**Preservation** — Pin or freeze an ontology:
- **Pinned** (`lifecycle_state = 'pinned'`): Immune to demotion (`exposure_pressure = 0`), still accepts new concepts. Teaching mode — "I will keep feeding this until it stands on its own."
- **Frozen** (`lifecycle_state = 'frozen'`): Immune to demotion AND attachment. Read-only snapshot. Useful for regulatory baselines, published research, or "this represents our understanding as of epoch N."

### 5. The Promotion Function

Promotion evaluates whether a concept should become an ontology. The key insight: **high connectivity alone is insufficient**. A concept with many edges might be a nucleus (founding a domain) or a crossroads (bridging domains). These require different treatment.

#### Step 1: Identify Candidates by Mass

Periodic background job ranks concepts by degree centrality within each ontology. Candidates are concepts whose edge count exceeds a sigmoid threshold relative to their ontology's population.

The degree centrality computation already exists in `graph_parallelizer.py` for bidirectional path search optimization. The data is there — it needs to be aggregated and ranked rather than consumed per-query.

#### Step 2: Evaluate Coherence via Polarity

For each candidate, analyze the first-order neighborhood using the diversity analyzer (ADR-063) and polarity projection (ADR-070):

- **Nucleus**: Neighbors are semantically aligned — low diversity score (neighbors are similar to each other), coherent directional cluster on polarity axes. This concept anchors a domain.
- **Crossroads**: Neighbors are semantically scattered — high diversity score, spread across polarity space. This concept bridges domains. Valuable as a concept, not a promotion candidate.

```
mass = degree_centrality(concept)
coherence = 1 - diversity_score(first_order_neighbors)
promotion_score = sigmoid(mass × coherence) - exposure_pressure(epoch_delta)
```

When `promotion_score` exceeds the promotion threshold, the system proposes promotion. The concept becomes the **anchor concept** of a new ontology — not replaced by it, but linked via `:ANCHORED_BY`.

#### Step 3: Cleave the Cluster

On promotion:
1. Create `:Ontology` node with name derived from anchor concept label, description from anchor concept description, embedding from anchor concept embedding.
2. Link: `(:Ontology)-[:ANCHORED_BY]->(:Concept)`.
3. Reassign first-order concepts: their sources get `:SCOPED_BY` edges to the new ontology. `s.document` updated for denormalization.
4. Second-order and beyond stay in their current ontology unless their own edge affinity pulls them (evaluated in subsequent breathing cycles).

### 6. Self-Correcting Attractor Model

A promoted ontology has an embedding in the shared vector space. New concepts ingested into the system compute cosine similarity against all ontologies. If the promotion was meaningful, the ontology's embedding occupies a region that attracts related content — it becomes a **seed crystal** that either:

- **Validates itself** by attracting mass (content matches, concepts link in, the ontology grows), or
- **Starves** because nothing matches (the embedding is in a dead region, no new content connects)

This is a self-correcting feedback loop. Premature differentiation doesn't create fragmentation — it creates attractors that are tested by the content stream. You would need to deliberately feed content that is statistically similar to noise to break this balance. In normal operation, the feedback loop governs itself.

### 7. The Protection Mechanism

New ontologies need protection from premature demotion, but protection should be earned through opportunity, not granted by calendar time.

#### Epoch-Based Exposure

Use the global epoch counter (ingestion events tracked in `graph_metrics`) rather than wall-clock time:

```
exposure = global_epoch - ontology.creation_epoch
```

An ontology that has existed through 5,000 ingests and still hasn't reached mass has failed to capture relevance despite ample opportunity. That's meaningful in a way that "90 days" isn't.

#### Weighted Exposure

Raw epoch delta treats every ingest equally. Ingests into *adjacent ontologies* should count more heavily — that content was "near" the ontology being evaluated:

```
weighted_exposure = Σ (ingest_events × ontology_adjacency_score)
```

Adjacency is computable from embedding similarity between ontology nodes. An ingest into a neighboring ontology is high-exposure; an ingest into something unrelated is low-exposure. This prevents an ontology from being penalized for irrelevant graph activity while holding it accountable when nearby content flows past without connecting.

#### The Protection Function

```
protection_score = mass_curve(mass) - exposure_pressure(weighted_exposure)
```

Where:
- `mass_curve(mass)`: sigmoid that asymptotes toward 1.0 (high mass = self-sustaining). Reuses the Bezier curve infrastructure from aggressiveness profiles (ADR-046).
- `exposure_pressure(exposure)`: grows as opportunity accumulates without mass gain.

| State | Mass | Exposure | Protection | Outcome |
|-------|------|----------|------------|---------|
| Newborn | Low | Low | High | Safe (hasn't had a chance yet) |
| Struggling | Low | Medium | Medium | Borderline |
| Failed | Low | High | Low | Demotion candidate |
| Stable | High | High | High | Self-sustaining — not growing but coherent |
| Growing | High | Medium | High | Actively accumulating |

**Stable vs Failed**: Both have high exposure. The difference is mass AND coherence. A stable ontology has high internal edge density and sharp boundaries. A failed ontology has its concepts more connected to other ontologies than to each other. The mass component of the protection function must include coherence (boundary sharpness, internal grounding) not just concept count.

### 8. Demotion

When `protection_score` drops below the demotion threshold, the ontology's concepts are reassigned based on edge affinity:

| Signal | Reassignment |
|--------|--------------|
| Concept edges primarily into Ontology A | Reassign to A |
| Concept bridges A and B roughly equally | Assign to whichever has higher grounding confidence |
| Concept is orphaned (weak edges everywhere) | Return to "everything else" |

**No deletion, only movement.** Concepts never disappear; they relocate. The demoted ontology node is removed, but its anchor concept survives — it was a concept before the ontology existed and remains one after.

### 9. The Ecological Ratio

The system maintains a target ratio of ontologies to concepts, analogous to how `vocab_min`/`vocab_max` govern vocabulary size:

- Too few ontologies → hairball (no navigable structure)
- Too many ontologies → fragmentation (trivial groupings)

```
target_ontology_count = f(total_concepts, desired_concepts_per_ontology)
```

When "everything else" grows too large relative to peers, promotion pressure increases. When ontologies get too small, absorption pressure increases. The Bezier curve infrastructure from vocabulary aggressiveness profiles can drive this — same mechanism, different domain.

### 10. Ontology-to-Ontology Edges

With ontologies as graph nodes, inter-ontology relationships become explicit:

```cypher
(:Ontology {name: 'Security Engineering'})-[:SPECIALIZES]->(:Ontology {name: 'Infrastructure'})
(:Ontology {name: 'Customer Onboarding'})-[:OVERLAPS]->(:Ontology {name: 'Sales Enablement'})
```

These edges can be:
- **Derived** from aggregated concept-level data. "Ontology A OVERLAPS Ontology B" is observable when a significant percentage of A's concepts have well-grounded edges into B.
- **Explicit** when a human or AI declares the relationship.
- **Both** — derived edges form the baseline, explicit edges override or supplement.

### 11. Ontology Health Metrics

| Metric | Well-formed | Diffuse |
|--------|-------------|---------|
| Internal edge grounding | High average confidence | Mixed or low confidence |
| Edge type consistency | Coherent vocabulary subset | Scattered across categories |
| Boundary sharpness | Most edges stay internal | High ratio of cross-ontology edges |
| Concept-to-source ratio | Reasonable extraction density | Over/under-extraction |
| Cross-ontology affinity | Clear, intentional bridges | Spraying connections everywhere |

The epistemic status measurement (ADR-065) can be extended to run per-ontology, providing aggregate grounding scores, vocabulary distribution analysis, boundary coherence metrics, and merger/split recommendations.

### 12. Graph Lifecycle Interaction

The breathing process is not fully autonomous. Humans and AIs interact with the lifecycle deliberately:

| Action | Effect | Use Case |
|--------|--------|----------|
| Pin ontology | `exposure_pressure = 0` | Teaching mode — infinite runway to accumulate mass |
| Freeze ontology | No attachment, no demotion | Regulatory snapshot, published baseline |
| Direct ingest | Target specific ontology | Nurturing — deliberately feeding a domain |
| Override promotion | Accept or reject system proposal | Human judgment on borderline cases |
| Override demotion | Keep ontology despite low scores | AI or human knows something the graph doesn't |

These interventions are expected and deliberate. The graph provides proposals; operators provide judgment. Neither works alone.

## Consequences

### Positive

- Ontologies become first-class graph citizens with embeddings, edges, and scores — not metadata strings
- The same infrastructure (vocabulary, grounding, diversity, polarity) works at both concept and ontology scales — self-similarity across scale
- Emergent structure surfaces automatically — the system proposes ontology boundaries from observed connectivity patterns
- The embedding-space attractor model creates a self-correcting feedback loop — premature promotions either validate or starve without manual cleanup
- Directed growth (today's model) continues working unchanged — this is additive, not replacement
- Epoch-based protection is more meaningful than time-based protection — opportunity cost, not calendar duration
- The ecological ratio prevents both hairball (too few ontologies) and fragmentation (too many)
- The promotion function distinguishes nuclei from crossroads using existing diversity and polarity infrastructure
- `s.document` stays as a denormalized cache — no existing queries break

### Negative

- Adds a new node type (`:Ontology`) with lifecycle management — the breathing worker is a new background service that must run reliably
- Promotion and demotion are graph mutations — they change Source node edges and properties, which could affect concurrent queries. Transaction isolation needed.
- The promotion function involves computing degree centrality across all concepts in an ontology plus diversity analysis of candidates' neighborhoods — this is O(N) per ontology per evaluation cycle. Background job, not request-path.
- Sigmoid threshold calibration requires empirical tuning — the first promotion in a new graph has no baseline for "highly connected relative to peers"
- Users may resist automated demotion of "their" ontologies — the pin mechanism mitigates but doesn't eliminate this friction. Explainability features (why was this demoted? what did the scores look like?) are important.
- Weighted exposure requires computing ontology adjacency scores, which requires ontology embeddings to exist — chicken-and-egg during initial population

### Neutral

- The `:Ontology` node type is separate from `:Concept` for query clarity, but shares the same embedding space, vocabulary, and scoring infrastructure
- Community detection algorithms (Louvain, Girvan-Newman) are referenced as theoretical support but not required for MVP — the promotion function uses simpler signals (degree + diversity) that are already computable
- The "everything else" primordial pool is a starting posture, not a requirement — users can still create named ontologies upfront and direct content into them. Both modes coexist.
- This ADR does not address federation ("greedy agent" ontology trading across shards) — that is a future concern that builds on this foundation
- The Bezier curve infrastructure from vocabulary aggressiveness profiles (ADR-046, ADR-701) can be reused for promotion/demotion pressure curves — same mechanism, different domain

## Design Principles

1. **No deletion, only movement.** Concepts never disappear; they relocate. Deletion costs energy the system shouldn't spend.

2. **Mass over time.** Protection is based on accumulated structure, not calendar duration. Opportunity cost matters; wall-clock time doesn't.

3. **Emergent over imposed.** The system proposes structure based on observation. Humans confirm, reject, or override — but the default is "trust the graph."

4. **Self-similarity across scale.** Concepts and ontologies differ in scope, not kind. The same graph infrastructure, edge vocabulary, and measurement tools apply at both levels.

5. **Human-machine collaboration.** Humans assert hypotheses (create ontologies). The graph tests them. Weak hypotheses get absorbed. Strong patterns get elevated. Neither party works alone.

## Alternatives Considered

### A. Keep Ontologies as String Properties

Leave ontologies as `s.document` strings. Add API endpoints for statistics and visualization (ADR-700) without changing the data model.

**Rejected because:** This addresses the UI gap but not the structural problems. Ontologies remain flat, rigid, and manually maintained. The system can't propose reorganization because ontologies aren't entities it can reason about.

### B. Ontologies as Concepts with a Scope Property

Make all nodes `:Concept` with `scope: 'concept' | 'ontology'`. Promotion is a property flip. Purest expression of the "same type, different scope" thesis.

**Rejected because:** Every existing `MATCH (c:Concept)` query would return ontology-scoped nodes unless filtered. The noise-to-signal ratio degrades. More importantly, ontology-specific properties (creation_epoch, protection_score, lifecycle_state) would pollute the concept property space. Separate labels with shared infrastructure is cleaner than shared labels with conditional properties.

### C. External Community Detection Service

Run Louvain or Girvan-Newman on exported graph snapshots in a separate Python service, then import cluster assignments back.

**Not rejected, but deferred.** Full community detection is a valid enhancement for later phases. The MVP promotion function uses simpler signals (degree centrality + diversity) that are computable within the existing query infrastructure. Community detection becomes relevant at scale when the simpler signals produce too many false positives.

### D. Ontologies in a Separate PostgreSQL Table

Store ontology metadata (name, description, creation date) in a relational table, referencing them by ID from Source nodes.

**Rejected because:** This keeps ontologies outside the graph. They can't have edges to each other or to concepts. They can't be embedded in the same vector space. They can't participate in the managed vocabulary. The entire thesis of this ADR — self-similarity across scale — requires ontologies to be graph nodes.

## Implementation Notes

### Phase 1: Ontology Nodes (Foundation)

- Add `:Ontology` node type to Apache AGE schema
- Migration: create `:Ontology` nodes from distinct `s.document` values in existing graph
- Add `:SCOPED_BY` edges from all Source nodes to their corresponding Ontology node
- Generate embeddings for ontology nodes (from name + description, or centroid of member concept embeddings)
- Keep `s.document` string for backward compatibility
- API: extend `GET /ontology/` to return ontology node properties alongside existing statistics

### Phase 2: Lifecycle States and Directed Growth

- Add `lifecycle_state` property to `:Ontology` nodes (`active` | `pinned` | `frozen`)
- API: `PUT /ontology/{name}/lifecycle` to set state (pin, freeze, activate)
- Frozen ontologies reject new `:SCOPED_BY` edges during ingestion
- Pinned ontologies tracked for exposure calculation but exempt from demotion

### Phase 3: Breathing Worker

- New background worker: `ontology_breathing_worker`
- Per-ontology evaluation: compute mass (degree, edge density, grounding), coherence (diversity of internal concepts), exposure (weighted epoch delta)
- Rank concepts by degree within each ontology
- Evaluate promotion candidates: mass × coherence against sigmoid threshold
- Generate proposals (promote / demote / absorb) — stored as recommendations, not auto-executed initially
- Human-in-the-loop approval via web UI (ADR-700 Ontology Explorer) or CLI

### Phase 4: Automated Promotion and Demotion

- Execute approved promotions: create `:Ontology` node, link anchor concept, reassign first-order sources
- Execute approved demotions: reassign concepts by edge affinity, remove `:Ontology` node
- Track ecological ratio: ontology count vs concept count target
- Bezier curve profiles for promotion/demotion pressure (reuse vocabulary aggressiveness infrastructure)
- Graduated automation: HITL → AITL → autonomous (mirroring vocabulary consolidation progression)

### Phase 5: Ontology-to-Ontology Edges

- Derive inter-ontology edges from cross-ontology concept bridge analysis
- Compute: shared concept count, edge density between ontology pairs, vocabulary overlap
- Create derived edges: OVERLAPS, SPECIALIZES, GENERALIZES
- Allow explicit override edges from humans/AI
- Integrate with Ontology Explorer bridge view (ADR-700)

## Open Questions

- **Infinite regress.** If ontologies are nodes, can they group into meta-ontologies? The fractal self-similarity argument says yes; the stopping condition is utility, not structure. The UI viewport determines what level the user operates at. This is a zoom operation, not a schema change — but the ergonomics need design work.

- **Sigmoid calibration.** The first promotion in a new graph has no baseline. The protection function should handle this (low exposure = high protection), but the initial sigmoid parameters need empirical tuning across different corpus types.

- **Performance at scale.** Computing degree centrality across all concepts per ontology is O(N). Diversity analysis of candidate neighborhoods adds O(k²) where k is first-order neighbor count. Background job mitigates latency but compute cost grows with graph size. Incremental evaluation (only re-evaluate concepts whose edge count changed since last epoch) is the likely optimization.

- **User attachment.** How do we handle users who resist demotion of "their" ontologies? Pin mechanism provides the escape hatch. Explainability features (score history, comparison to thresholds, what triggered the proposal) support acceptance. ADR-082 grants system provides resource-level ownership.

## References

**Community Detection & Graph Algorithms:**
- Girvan, M., & Newman, M. E. J. (2002). Community structure in social and biological networks. *PNAS*.
- Blondel, V. D., et al. (2008). Fast unfolding of communities in large networks. *Journal of Statistical Mechanics*.
- Freeman, L. (1977). A set of measures of centrality based on betweenness. *Sociometry*.

**Knowledge Graph Lifecycles:**
- Pernisch, R., et al. (2024). When Ontologies Met Knowledge Graphs: Tale of a Methodology. *ESWC 2024*.
- Simsek, U., et al. (2021). Knowledge graph lifecycle: Building and maintaining knowledge graphs. *CEUR Workshop Proceedings*.
- Zablith, F., et al. (2015). Ontology evolution: a process-centric survey. *Knowledge Engineering Review*.

**Emergent & Self-Organizing Ontologies:**
- Aguilar, J., et al. (2020). Ontological emergence scheme in self-organized and emerging systems. *Expert Systems with Applications*.
- Moroz, O. V. (2020). Model of Self-organizing Knowledge Representation. *American Journal of Artificial Intelligence*.

**Fractal Knowledge Structures:**
- Massel, L. V., et al. (2016). Fractal Approach to Knowledge Structuring. *Ontological Engineering*.
- FFOM Framework (2025). Ontology Modeling Using Fractal and Fuzzy Concepts. *MDPI Applied Sciences*.

## Related ADRs

- **ADR-022** — Original 30-type taxonomy (vocabulary that ontology edges draw from)
- **ADR-025** — Dynamic relationship vocabulary (same vocabulary system applies at ontology scale)
- **ADR-044** — Probabilistic truth convergence (grounding strength and confidence scoring — reused for ontology mass)
- **ADR-046** — Grounding-aware vocabulary management (Bezier curve infrastructure reusable for promotion/demotion pressure)
- **ADR-063** — Semantic diversity (coherence scoring distinguishes nuclei from crossroads)
- **ADR-065** — Epistemic status (extensible to per-ontology measurement)
- **ADR-068** — Source text embeddings (cross-ontology concept merging — the mechanism that creates inter-ontology bridges)
- **ADR-070** — Polarity axis analysis (directional evaluation of candidate neighborhoods)
- **ADR-700** — Ontology Explorer (UI for visualizing and managing ontology structure — first consumer of this data model)
- **ADR-701** — Vocabulary Administration Interface (Bezier curve editor reusable for promotion/demotion profiles)
