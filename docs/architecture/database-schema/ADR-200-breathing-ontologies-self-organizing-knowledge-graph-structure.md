---
status: Accepted
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

### Formal Positioning: TBox/ABox Collapse

In traditional knowledge engineering (RDF/OWL), the **TBox** (terminological box) defines the schema — classes, properties, constraints — and the **ABox** (assertion box) contains the data — instances, relationships, facts. The two are kept strictly separate. An ontology (TBox) dictates rules; concepts (ABox) obey them.

This ADR deliberately collapses the TBox/ABox distinction. An ontology here is not a logical schema that validates or constrains its members. It is a **context cluster** — a dynamic viewport that organizes information retrieval, not a rule engine that enforces logical consistency. We are not doing OWL reasoning; we are doing dynamic graph partitioning.

In Semantic Web terminology, what this ADR proposes is a combination of:

- **Punning** — treating what would be a Class (ontology) as also an Instance (graph node). OWL 2 permits this; purists avoid it.
- **Schema induction** / **Ontology learning** — extracting organizational structure from data patterns rather than pre-defining it.
- **Concept reification** — elevating a data-level entity (concept) into a schema-level organizing frame (ontology) when it accumulates sufficient structure.

This is a valid approach for dynamic knowledge graphs where schema evolves with data. It sacrifices the formal guarantees of strict TBox/ABox separation (logical validation, consistency checking) in exchange for adaptivity, self-organization, and reduced maintenance burden. This system does not need OWL-style reasoning — it needs navigable, self-maintaining structure.

### Terminology Map

This ADR uses metaphorical language for mental models. The formal equivalents:

| ADR Term | Formal Equivalent | Notes |
|----------|-------------------|-------|
| Breathing ontologies | Dynamic graph partitioning / Evolutionary ontology maintenance | The expansion-contraction cycles are hysteresis loops |
| Concept → Ontology promotion | Schema induction / Concept reification | Elevating a data node to a schematic container |
| "Ontology is a heavy concept" | Metamodeling / Punning | Collapsing TBox/ABox — valid in OWL 2, heresy in strict OWL |
| Mass | Degree centrality / Node salience | Standard graph theory |
| Coherence | Modularity / Clustering coefficient | "Internal density vs external sparsity" |
| Ecological ratio | Resolution limit / Cluster granularity | Louvain's resolution parameter controls this |
| Primordial pool | Root partition / Unclustered graph | Starting state before differentiation |
| Attractor | Vector space centroid | Standard embedding space behavior |
| Nucleus vs crossroads | High-modularity hub vs bridging node | Community detection distinguishes these |

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
- **Abstract anchor**: A special case — high connectivity AND high diversity, but the concept represents a broad organizing term (e.g., "Management," "Security," "Infrastructure"). These are often exactly what users want as navigation ontologies, even though their neighborhoods are semantically diverse. The promotion function should not automatically penalize diversity for concepts above a high-mass threshold. Abstract terms that attract connections from many subdomains may warrant promotion as **umbrella ontologies** — their children would then be candidates for sub-ontology promotion in later breathing cycles, creating hierarchical depth rather than flat partitioning.

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

**Reassignment cost**: If a promoted concept has thousands of first-order neighbors, each with multiple Source chunks, the `:SCOPED_BY` edge creation and `s.document` updates become a large write operation. This must be an **eventually consistent background process** — batched writes executed by the breathing worker over multiple transactions, not a single atomic operation. During reassignment, sources may temporarily have stale `s.document` values; the `:SCOPED_BY` edge is the source of truth, and `s.document` catches up. This is the same eventual-consistency model used by the vocabulary consolidation worker when merging edge types across thousands of edges.

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

#### Hysteresis: Separate Promotion and Demotion Thresholds

A concept hovering near the promotion threshold must not flicker between concept and ontology status across breathing cycles. The promotion threshold must be significantly higher than the demotion threshold, creating a **hysteresis band**:

```
promotion_threshold = 0.8   (high bar to become an ontology)
demotion_threshold  = 0.5   (lower bar to remain one)
```

Once promoted, an ontology has a stability margin — it must deteriorate substantially before demotion is considered, not just dip below the level that triggered promotion. This is standard practice in control systems (Schmitt triggers) and community detection (resolution hysteresis in Louvain).

The hysteresis band width is itself configurable — wider bands favor stability (fewer transitions), narrower bands favor responsiveness (faster adaptation). The Bezier curve infrastructure can model both thresholds as separate curves if non-linear hysteresis is desired.

### 8. Demotion

When `protection_score` drops below the demotion threshold, the ontology's concepts are reassigned based on edge affinity:

| Signal | Reassignment |
|--------|--------------|
| Concept edges primarily into Ontology A | Reassign to A |
| Concept bridges A and B roughly equally | Assign to whichever has higher grounding confidence |
| Concept is orphaned (weak edges everywhere) | Return to "everything else" |

**No deletion, only movement.** Concepts never disappear; they relocate. The demoted ontology node is removed, but its anchor concept survives — it was a concept before the ontology existed and remains one after.

### 9. Resolution Limit (Ecological Ratio)

The system maintains a target cluster granularity — the ratio of ontologies to concepts — analogous to how `vocab_min`/`vocab_max` govern vocabulary size and how Louvain's resolution parameter controls cluster count:

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

6. **Edge-agnostic lifecycle.** Breathing controls depend only on the `:SCOPED_BY` infrastructure edge for ontology membership — never on vocabulary edge names or ingestion plumbing like `:APPEARS`. Queries traverse `(c:Concept)-->(s:Source)-[:SCOPED_BY]->(o:Ontology)` where `-->` means "any outbound edge." This decouples lifecycle management from the ingestion pipeline's structural choices.

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

### Phase 1: Ontology Nodes (Foundation) — Complete

PR #237, merged 2026-01-30.

- `:Ontology` node type in Apache AGE schema (migration 044)
- `:SCOPED_BY` edges from all Source nodes to their corresponding Ontology node
- AGE client methods: create, get, list, delete, rename, ensure_ontology_exists
- Name-based embeddings at creation time (centroid recomputation deferred to Phase 3)
- `s.document` string retained as denormalized cache
- API: existing responses unchanged — internal box only

### Phase 1b: Client Exposure — Complete

PR #238, merged 2026-01-30.

- Graph nodes as source of truth for `GET /ontology/` (empty ontologies now visible)
- `POST /ontology/` for directed growth (create before ingest)
- `GET /ontology/{name}/node` for graph node properties
- CLI: `kg ontology create`, info shows graph node section, list shows State column
- MCP: `create` and `rename` actions on ontology tool
- Web/FUSE: type updates, no functional changes needed

### Phase 2: Lifecycle States, Frozen Enforcement & Owner Provenance — Complete

PR #239, merged 2026-01-30.

- `PUT /ontology/{name}/lifecycle` with `ontologies:write` RBAC (migration 045)
- `lifecycle_state`: `active | pinned | frozen` — frozen rejects ingest and rename
- Two-layer frozen enforcement: route-level 403 (fail fast) + worker-level (defense in depth)
- Frozen = source boundary protection. Concepts are global; freezing blocks new Sources scoped to the ontology, not cross-ontology edges pointing at its concepts
- `created_by` provenance on Ontology nodes (route passes username, worker passes job username)
- CLI: `kg ontology lifecycle <name> <state>`, MCP: `lifecycle` action
- 58 tests (35 existing + 23 new)

### Operational Foundation (Phases 1-2 Retrospective)

With Phases 1-2 complete, the system has all the **plumbing and controls** needed for active management:

| Capability | Available Since | Used By |
|------------|----------------|---------|
| `:Ontology` nodes with embeddings | Phase 1 | Scoring (mass, coherence) |
| `:SCOPED_BY` edges | Phase 1 | Boundary computation |
| `creation_epoch` on Ontology | Phase 1 | Exposure calculation |
| `ensure_ontology_exists()` | Phase 1 | Promotion execution |
| `lifecycle_state` enforcement | Phase 2 | Protection (pin/freeze) |
| `created_by` provenance | Phase 2 | Audit trail for automated actions |
| `ontologies:write` RBAC | Phase 2 | Worker needs permission to mutate |

What's missing is the **driver** — the intelligence that observes the graph, scores what it sees, and proposes structural changes. This is conceptually identical to `kg vocab consolidate`: a series of graph traversals, scoring, ranking, then feeding to an LLM to make determinations that impact graph structure. In that case, vocabulary type merging/splitting. In this case, concept→ontology promotion (mitosis) and ontology→concept collapse (demotion).

**Manual viability.** Everything the worker will do can be done manually today. A human (or Claude via MCP) could:
1. Query each ontology's concept count, edge density, and cross-ontology bridges
2. Compute mass and coherence scores from the results
3. Identify promotion candidates (high-mass, high-coherence concepts)
4. Use `POST /ontology/` to create the new ontology
5. Reassign sources by updating `:SCOPED_BY` edges
6. Identify demotion candidates (low-mass ontologies with high exposure)
7. Compute affinity to decide where demoted sources go
8. Execute reassignment

The worker automates this loop on a heartbeat, interacting with the epoch counter to decide *when* to evaluate, and delegating the *judgment* calls to an LLM.

### Phase 3: Breathing Worker (Scoring & Proposals)

The breathing worker is a background job — similar in architecture to the ingestion worker and vocabulary consolidation worker. It runs on a heartbeat tied to the epoch counter: after N ingestion events (not wall-clock time), it evaluates the graph and generates proposals.

#### Worker Architecture

```
epoch counter (graph_metrics) → threshold check → breathing cycle
    ↓
per-ontology scoring (mass, coherence, exposure)
    ↓
promotion candidate identification (high-mass concepts)
    ↓
demotion candidate identification (low-protection ontologies)
    ↓
LLM judgment on borderline cases
    ↓
proposals stored as recommendations (not auto-executed)
```

The worker does NOT execute proposals in Phase 3. It produces scored recommendations for human review (HITL). This mirrors the vocabulary consolidation progression: observe first, automate later.

#### Scoring Algorithms

**Mass** — degree centrality aggregated per ontology:

```cypher
-- Per-ontology mass: count of concepts, sources, evidence, relationships
MATCH (o:Ontology {name: $name})
OPTIONAL MATCH (s:Source)-[:SCOPED_BY]->(o)
OPTIONAL MATCH (c:Concept)-->(s)
OPTIONAL MATCH (c)-[r]->()
RETURN count(DISTINCT s) AS sources,
       count(DISTINCT c) AS concepts,
       count(r) AS relationships
```

Mass is a composite score, not a single count. The existing confidence scoring infrastructure (ADR-044) uses a Michaelis-Menten saturation curve for concept-level confidence — the same curve shape applies here: mass saturates as an ontology grows, so raw counts are transformed to a 0-1 scale.

**Coherence** — internal semantic density vs external scatter:

The diversity analyzer (ADR-063) computes Gini-Simpson index of pairwise embedding similarity in an N-hop neighborhood. For ontology coherence, the "neighborhood" is all concepts scoped to the ontology. High coherence (low diversity) means concepts are semantically clustered. Low coherence (high diversity) means the ontology is a grab-bag.

```
coherence = 1 - diversity_score(concepts_in_ontology)
```

Coherence distinguishes nuclei (promotion candidates) from crossroads (bridging concepts that serve a structural role but shouldn't be ontologies).

**Exposure** — opportunity cost measured in graph activity:

```
raw_exposure = global_epoch - ontology.creation_epoch
weighted_exposure = Σ (ingest_events_into_adjacent_ontologies × adjacency_score)
```

Adjacency is computable from embedding similarity between ontology nodes. An ingest into a neighboring ontology counts more than an ingest into something unrelated. This prevents penalizing an ontology for irrelevant graph activity while holding it accountable when nearby content flows past without connecting.

#### Promotion Candidate Identification

The worker ranks all concepts within each ontology by degree centrality, then evaluates the top-N:

```
promotion_score = sigmoid(mass × coherence) - exposure_pressure(epoch_delta)
```

Concepts above the promotion threshold become proposals. The LLM evaluates borderline cases — "Is this concept a nucleus (should be an ontology) or a crossroads (valuable connector, should stay a concept)?"

#### Demotion Candidate Identification

The worker evaluates each non-pinned ontology's protection score:

```
protection_score = mass_curve(mass) - exposure_pressure(weighted_exposure)
```

Ontologies below the demotion threshold become demotion proposals. The hysteresis band (promotion_threshold=0.8, demotion_threshold=0.5) prevents flickering.

For each demotion candidate, the worker pre-computes **reassignment affinity** — where would the sources go?

```cypher
-- Cross-ontology affinity: which ontology shares the most concepts?
MATCH (s:Source)-[:SCOPED_BY]->(dying:Ontology {name: $name})
MATCH (c:Concept)-->(s)
MATCH (c)-->(other_s:Source)-[:SCOPED_BY]->(candidate:Ontology)
WHERE candidate <> dying
RETURN candidate.name, count(DISTINCT c) AS shared_concepts
ORDER BY shared_concepts DESC
```

This query works without materialized ontology-to-ontology edges — it computes affinity from the existing graph structure. Phase 5 materializes this as cached edges for performance.

#### Proposal Storage

Proposals are stored as structured recommendations (likely in the job queue or a dedicated table):

```json
{
  "type": "promotion",
  "concept_id": "c_abc123",
  "concept_label": "Incident Response",
  "source_ontology": "ITSM",
  "scores": { "mass": 0.87, "coherence": 0.92, "promotion_score": 0.85 },
  "suggested_name": "Incident Response",
  "suggested_description": "...",
  "reasoning": "LLM explanation of why this concept warrants promotion",
  "epoch": 5420
}
```

Proposals can be approved/rejected via CLI (`kg ontology promote <concept>`), MCP, or web UI (ADR-700).

### Phase 5: Ontology-to-Ontology Edges (Materialized Relationships)

**Resequenced: Phase 5 before Phase 4.** The scoring worker (Phase 3) traverses cross-ontology bridges as part of its evaluation. Phase 5 materializes what scoring discovers — the worker emits ontology-to-ontology edges as a side effect of its analysis. Phase 4 then uses these materialized edges for routing during automated execution.

Phase 5 is NOT a prerequisite for Phase 3 — the raw cross-ontology data is already traversable. But running Phase 5 between scoring and execution means Phase 4's demotion logic has a precomputed affinity map instead of recomputing it per-operation.

#### Derived Edges

As the breathing worker scores ontologies, it observes cross-ontology concept bridges. These are materialized as ontology-level edges:

- **OVERLAPS** — significant percentage of A's concepts also appear in B's sources
- **SPECIALIZES** — A's concepts are a coherent subset of B's concept space (A is more specific)
- **GENERALIZES** — inverse of SPECIALIZES

```cypher
-- Derive OVERLAPS from shared concept count
MATCH (a:Ontology), (b:Ontology)
WHERE a <> b
MATCH (s_a:Source)-[:SCOPED_BY]->(a)
MATCH (c:Concept)-->(s_a)
MATCH (c)-->(s_b:Source)-[:SCOPED_BY]->(b)
WITH a, b, count(DISTINCT c) AS shared,
     [(s:Source)-[:SCOPED_BY]->(a) | s] AS a_sources
WITH a, b, shared, size(a_sources) AS a_total
WHERE toFloat(shared) / a_total > 0.3  -- threshold for OVERLAPS
MERGE (a)-[:OVERLAPS {shared_concepts: shared, ratio: toFloat(shared)/a_total}]->(b)
```

#### Explicit Override Edges

Humans or AI can declare relationships that override or supplement derived edges:

```cypher
MERGE (a:Ontology {name: 'Security Engineering'})-[:SPECIALIZES {source: 'manual'}]->(b:Ontology {name: 'Infrastructure'})
```

Derived edges carry `source: 'breathing_worker'`; explicit edges carry `source: 'manual'` or `source: 'ai'`. Explicit edges take precedence when they conflict with derived edges.

#### Integration

- Ontology Explorer (ADR-700) bridge view consumes these edges for visualization
- Phase 4 uses OVERLAPS/SPECIALIZES for demotion routing
- Future: inter-ontology edges inform ontology search and navigation

### Phase 4: Automated Promotion & Demotion (Execution)

Phase 4 converts the worker from proposal-only (Phase 3) to proposal-and-execute. This follows the graduated automation pattern from vocabulary consolidation: HITL → AITL → autonomous.

#### Promotion Execution

On approved promotion:

1. `create_ontology_node()` with name derived from anchor concept, embedding from concept embedding
2. `(:Ontology)-[:ANCHORED_BY]->(:Concept)` edge links the new ontology to its founding concept
3. Reassign first-order concepts' sources: create `:SCOPED_BY` edges to new ontology, update `s.document`
4. This is an **eventually consistent background process** — batched writes over multiple transactions (same pattern as vocabulary consolidation merging edge types across thousands of edges)
5. `created_by: 'breathing_worker'` for provenance

#### Demotion Execution

On approved demotion:

1. Compute reassignment targets using Phase 5's materialized OVERLAPS edges (fast lookup) or fall back to the affinity query (slower, traversal-based)
2. For each source in the dying ontology, reassign `:SCOPED_BY` to the highest-affinity candidate
3. Sources with no clear affinity go to the primordial pool ("everything else")
4. Remove the `:Ontology` node — the anchor concept survives (it was a concept before, it remains one after)
5. **No deletion, only movement** — concepts and sources relocate, nothing disappears

#### Ecological Ratio Tracking

The system maintains a target cluster granularity — the ratio of ontologies to concepts:

```
target_ontology_count = f(total_concepts, desired_concepts_per_ontology)
```

When the primordial pool grows too large relative to named ontologies, promotion pressure increases. When ontologies get too small, absorption pressure increases. The Bezier curve infrastructure from vocabulary aggressiveness profiles (ADR-046) drives this — same mechanism, different domain.

#### Graduated Automation

| Level | Behavior | Trigger |
|-------|----------|---------|
| HITL | Worker proposes, human approves | Phase 3 (default) |
| AITL | Worker proposes, LLM evaluates, human reviews exceptions | Configurable |
| Autonomous | Worker proposes and executes within safety bounds | High-confidence proposals only |

Safety bounds for autonomous mode: only promote concepts above a high-confidence threshold, only demote ontologies that have been candidates for multiple consecutive cycles, never demote pinned or frozen ontologies.

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
