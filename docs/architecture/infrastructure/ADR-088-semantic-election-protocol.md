---
status: Proposed
date: 2026-01-17
deciders:
  - Engineering Team
related:
  - ADR-044
  - ADR-044
  - ADR-055
  - ADR-055
  - ADR-058
  - ADR-058
---

# ADR-088: Semantic Election Protocol for Distributed Concept Placement

## Overview

When knowledge outgrows a single shard, you need a way to decide where concepts should live. Traditional distributed hash tables (DHTs) solve this with XOR distance metrics and complex routing tables—but they answer the wrong question. They ask "where is this stored?" when we need to ask "who understands this best?"

This ADR describes a **semantic election protocol** where shards compete for concepts based on epistemic fit. When a shard detects a misfit concept (low coherence with its existing knowledge), it announces an election. Other shards compute their own fit scores locally and bid if they can beat the current score. The highest bidder wins the concept. No central authority decides placement—concepts flow toward whoever can make best use of them.

The protocol is deliberately simple. Vectors don't broadcast across the network. Shards don't maintain complex routing tables. Instead, candidates fetch what they need, compute locally, and respond with a single number. It's a distributed "ooh ooh pick me" that self-organizes knowledge placement through competitive fitness.

---

## Context

### The Single-Shard Foundation

The Knowledge Graph System operates successfully on a single Apache AGE instance with:

- **Recursive concept upsert**: LLM-driven extraction with vector similarity matching
- **Coherence monitoring**: Mean pairwise similarity detects domain drift (ADR-044)
- **Grounding scores**: Polarity axis triangulation measures evidential support (ADR-058)
- **Natural ontology separation**: Disconnected subgraphs form organically

### When Single-Shard Isn't Enough

Scaling triggers include:

1. **Resource limits**: Single PostgreSQL instance has finite capacity
2. **Ontology count**: 50+ ontologies make discovery non-trivial
3. **Epistemic saturation**: Cosine similarity threshold (≥0.85) causes false merges at scale
4. **Geographic distribution**: Teams or regions need autonomous instances

### Why Traditional DHT Doesn't Fit

| DHT Approach | Problem for Knowledge Graphs |
|--------------|------------------------------|
| Hash-based placement | Destroys semantic locality |
| XOR distance routing | Meaningless for embeddings |
| Fixed replication factor | Knowledge isn't uniformly important |
| Node ID assignment | Shards have *identity* (their expertise) |

**Core insight**: We don't want content-addressable storage. We want *expertise-addressable* storage. The question isn't "which node has the bits" but "which agent has the conceptual context to make sense of this."

### Prior Art in This Project

Previous conversations established:

1. **Greedy singletons**: Each shard acts as a gravitational well for its domain
2. **TCP-style migration**: Copy-on-write with confirmation before deletion
3. **Router as directory**: Knows who has what, but doesn't command placement
4. **Coherence-based reorganization**: Low coherence (< 0.5) triggers migration consideration

What was missing: the actual protocol for **how shards discover and negotiate transfers**.

---

## Decision

We adopt a **semantic election protocol** for distributed concept placement.

### Protocol Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                   TIER-AWARE SEMANTIC ELECTION                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Coherence Audit                                                │
│       │                                                         │
│       ▼                                                         │
│  ┌─────────────────┐                                           │
│  │ Classify Misfits│                                           │
│  │ by ConceptRank  │                                           │
│  └────────┬────────┘                                           │
│           │                                                     │
│     ┌─────┼─────────────────┐                                  │
│     │     │                 │                                  │
│     ▼     ▼                 ▼                                  │
│   HIGH  MEDIUM            LOW                                  │
│   (Hub) (Core)          (Orphan)                               │
│     │     │                 │                                  │
│     │     │                 │                                  │
│     ▼     ▼                 ▼                                  │
│  SUBGRAPH PROTECTED    CONSOLIDATION                           │
│  ELECTION (no move)    ELECTION                                │
│     │                       │                                  │
│     └───────────┬───────────┘                                  │
│                 │                                               │
│                 ▼                                               │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                     ELECTION_OPEN                        │   │
│  │  (concept_ids[], aggregate_embedding, originator_score) │   │
│  └────────────────────────┬────────────────────────────────┘   │
│                           │                                     │
│            ┌──────────────┼──────────────┐                     │
│            │              │              │                     │
│            ▼              ▼              ▼                     │
│      ┌──────────┐  ┌──────────┐  ┌──────────┐                 │
│      │ Shard A  │  │ Shard B  │  │ Shard C  │                 │
│      │ fit:0.91 │  │ fit:0.84 │  │ fit:0.68 │                 │
│      │  → BID   │  │  → BID   │  │(silence) │                 │
│      └────┬─────┘  └────┬─────┘  └──────────┘                 │
│           │             │                                      │
│           └──────┬──────┘                                      │
│                  ▼                                              │
│           ┌───────────┐                                        │
│           │  WINNER   │                                        │
│           │  Shard A  │                                        │
│           └─────┬─────┘                                        │
│                 │                                               │
│                 ▼                                               │
│           ┌───────────┐                                        │
│           │ TRANSFER  │  (concepts + edges + evidence)         │
│           └─────┬─────┘                                        │
│                 │                                               │
│                 ▼                                               │
│           ┌───────────┐                                        │
│           │ CONFIRM   │  (coherence check passed)              │
│           └─────┬─────┘                                        │
│                 │                                               │
│                 ▼                                               │
│           ┌───────────┐                                        │
│           │ RELEASE   │  (originator drops claims)             │
│           └───────────┘                                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Message Types

#### 1. ELECTION_OPEN

Originator announces concept(s) available for migration.

```python
@dataclass
class ElectionOpen:
    election_id: str          # Unique election identifier
    election_type: Literal["SINGLE", "SUBGRAPH", "CONSOLIDATION"]
    
    # For SINGLE elections
    concept_id: str | None    # Single concept being offered
    
    # For SUBGRAPH and CONSOLIDATION elections
    concept_ids: list[str] | None  # Multiple concepts as unit
    aggregate_embedding: list[float] | None  # Centroid of group
    
    originator_shard: str     # Who's offering
    originator_score: float   # Current fit score (floor for bids)
    fetch_endpoint: str       # Where to fetch embedding(s) for comparison
    ttl_seconds: int          # Election duration (default: 5)
    
    # Metadata
    concept_count: int        # How many concepts in this election
    edge_count: int | None    # Internal edges (for subgraph coherence)
    consolidation_theme: str | None  # LLM-generated description of orphan batch
    
    metadata: dict            # Optional: labels, evidence counts, etc.
```

**Semantics by type**:

- **SINGLE**: "I have concept X. My local fit is 0.73. Can anyone beat that?"
- **SUBGRAPH**: "I have hub X + 15 connected concepts. Combined fit is 0.68. Can anyone take this cluster?"
- **CONSOLIDATION**: "I have 7 orphans about 'governance'. Combined fit is 0.41. Anyone want them?"

#### 2. BID

Candidate shard submits a competing fit score.

```python
@dataclass
class Bid:
    election_id: str
    bidder_shard: str
    bid_score: float          # Candidate's local fit score
    capacity_ok: bool         # Bidder confirms they have capacity
    coherence_projection: float  # Projected coherence if concept added
```

**Semantics**: "I score 0.91 with this concept. I have room. My coherence would be 0.78 after adding it."

**Rule**: Only bid if `bid_score > originator_score`. Silence means "I can't beat that."

#### 3. WINNER

Originator announces election result.

```python
@dataclass
class Winner:
    election_id: str
    winner_shard: str | None  # None if no bids beat originator
    winning_score: float
    runner_up: str | None     # For protocol debugging
```

**Semantics**: "Shard-7 wins with 0.91." Or: "No winner. Concept stays home."

#### 4. TRANSFER_REQUEST

Winner requests the full concept data.

```python
@dataclass
class TransferRequest:
    election_id: str
    requester_shard: str
    include_evidence: bool    # Whether to transfer evidence nodes
    include_edges: bool       # Whether to transfer relationship edges
```

#### 5. TRANSFER_DATA

Originator sends concept to winner.

```python
@dataclass
class TransferData:
    election_id: str
    concept: ConceptNode           # Full concept with embedding
    evidence: list[EvidenceNode]   # Source quotes and references
    edges: list[RelationshipEdge]  # Relationships (may become cross-shard)
    provenance: TransferProvenance # Origin shard, timestamp, election details
```

**Critical**: Originator **keeps** the data until TRANSFER_CONFIRM received.

#### 6. TRANSFER_CONFIRM

Winner confirms successful receipt and integration.

```python
@dataclass
class TransferConfirm:
    election_id: str
    winner_shard: str
    coherence_after: float    # Actual coherence after adding concept
    status: Literal["SUCCESS", "ROLLBACK"]
    rollback_reason: str | None
```

**Semantics**: "Received. Coherence is 0.79. Committed." Or: "Rollback. Coherence dropped to 0.41."

#### 7. RELEASE

Originator drops its claim on the concept.

```python
@dataclass
class Release:
    election_id: str
    originator_shard: str
    concept_id: str
    new_home: str             # Where concept now lives
    cross_shard_stub: bool    # Whether to keep a routing stub
```

### Fit Score Calculation

Each shard computes fit as similarity between concept embedding and its hub concepts:

```python
def calculate_fit(self, concept_embedding: np.ndarray) -> float:
    """
    How well does this concept fit with my existing knowledge?
    
    Uses hub concepts as domain signature (top-k by PageRank/betweenness).
    """
    if not self.hub_concepts:
        return 0.0
    
    hub_embeddings = np.array([h.embedding for h in self.hub_concepts])
    
    # Similarity to each hub concept
    similarities = cosine_similarity(
        concept_embedding.reshape(1, -1),
        hub_embeddings
    )[0]
    
    # Weighted by hub importance (PageRank score)
    weights = np.array([h.pagerank for h in self.hub_concepts])
    weights = weights / weights.sum()
    
    fit_score = np.dot(similarities, weights)
    
    return float(fit_score)
```

### Connectivity Tiers

Not all concepts should be treated equally in elections. We use ConceptRank (PageRank over the concept graph) to classify concepts into tiers:

```
┌─────────────────────────────────────────────────────────────────┐
│                   CONNECTIVITY DISTRIBUTION                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  HIGH (Hubs)        │ Top 10% by ConceptRank                   │
│  ████████           │ "Most obvious thing"                      │
│                     │ Moving one = moving a topic cluster       │
│                     │                                           │
│  MEDIUM (Core)      │ Middle 60% by ConceptRank                │
│  ████████████████   │ "Most average thing"                      │
│  ████████████████   │ Stable anchors, generally don't move      │
│                     │                                           │
│  LOW (Orphans)      │ Bottom 30% by ConceptRank                │
│  ██████████         │ "Most obscure thing"                      │
│                     │ Consolidate or grow                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

```python
@dataclass
class ConceptTier:
    HIGH = "hub"      # Top 10% connectivity
    MEDIUM = "core"   # Middle 60% connectivity  
    LOW = "orphan"    # Bottom 30% connectivity

def classify_concept(concept: Concept, ontology: Ontology) -> ConceptTier:
    """
    Classify concept by its ConceptRank percentile within ontology.
    """
    percentile = ontology.get_conceptrank_percentile(concept)
    
    if percentile >= 0.90:
        return ConceptTier.HIGH
    elif percentile >= 0.30:
        return ConceptTier.MEDIUM
    else:
        return ConceptTier.LOW
```

### Tier-Aware Election Strategies

Different tiers require different election strategies:

#### HIGH Tier (Hubs): Subgraph Election

When a hub concept is a misfit, its connected neighborhood is likely also misfit. Elect the subgraph, not just the node.

```python
def elect_hub_subgraph(hub_concept: Concept, max_hops: int = 2):
    """
    Elect a hub + its neighborhood as a unit.
    
    Rationale: Moving a hub alone orphans its connections.
    Moving the subgraph keeps the cluster coherent.
    """
    # Gather neighborhood
    subgraph = traverse_neighborhood(
        start=hub_concept,
        max_hops=max_hops,
        filter=lambda c: c.coherence_score < COHERENCE_THRESHOLD
    )
    
    # Compute aggregate embedding (centroid of subgraph)
    aggregate_embedding = np.mean(
        [c.embedding for c in subgraph],
        axis=0
    )
    
    # Open election for the subgraph as a unit
    return ElectionOpen(
        election_id=generate_id(),
        election_type="SUBGRAPH",
        concept_ids=[c.id for c in subgraph],
        aggregate_embedding=aggregate_embedding,
        originator_score=calculate_fit(aggregate_embedding),
        concept_count=len(subgraph),
        edge_count=count_internal_edges(subgraph)
    )
```

**Example**: Hub "regulatory frameworks" (misfit in Biology shard)
```
Subgraph includes:
  - "regulatory frameworks" (hub, 47 connections)
  - "policy compliance" (2 hops, 12 connections)
  - "governance structures" (1 hop, 8 connections)
  - "oversight mechanisms" (2 hops, 5 connections)

Elected as unit → Policy shard bids 0.91 → Entire cluster transfers
```

#### MEDIUM Tier (Core): Protected, No Election

Core concepts anchor the ontology's identity. They define what the shard "knows about." Don't elect them unless the entire ontology is being dissolved.

```python
def should_elect(concept: Concept) -> bool:
    tier = classify_concept(concept)
    
    if tier == ConceptTier.MEDIUM:
        # Core concepts are protected
        # They ARE the ontology's identity
        return False
    
    if tier == ConceptTier.HIGH:
        # Hubs only elect if coherence is very low
        return concept.coherence_score < HUB_COHERENCE_THRESHOLD  # 0.4
    
    if tier == ConceptTier.LOW:
        # Orphans are candidates for consolidation
        return True
```

#### LOW Tier (Orphans): Batch Consolidation Election

Individual orphan elections create noise. Instead, batch similar orphans and elect them as a consolidation group.

```python
def elect_orphan_batch(ontology: Ontology):
    """
    Find orphan concepts, cluster them by similarity,
    and elect each cluster as a consolidation group.
    """
    orphans = [c for c in ontology.concepts 
               if classify_concept(c) == ConceptTier.LOW
               and c.coherence_score < COHERENCE_THRESHOLD]
    
    if len(orphans) < MIN_BATCH_SIZE:  # Default: 5
        return  # Not enough orphans to batch
    
    # Cluster orphans by embedding similarity
    clusters = cluster_by_similarity(
        concepts=orphans,
        method="agglomerative",
        threshold=0.7  # Orphans in same cluster are 70%+ similar
    )
    
    # Elect each cluster as a group
    for cluster in clusters:
        if len(cluster) < 2:
            continue  # Single orphans wait for more company
        
        aggregate_embedding = np.mean(
            [c.embedding for c in cluster],
            axis=0
        )
        
        yield ElectionOpen(
            election_id=generate_id(),
            election_type="CONSOLIDATION",
            concept_ids=[c.id for c in cluster],
            aggregate_embedding=aggregate_embedding,
            originator_score=calculate_fit(aggregate_embedding),
            concept_count=len(cluster),
            consolidation_theme=describe_cluster(cluster)  # LLM summary
        )
```

**Example**: 23 orphan concepts in Biology shard
```
Clustering finds:
  Cluster A (7 concepts): regulatory, policy, legal → "Governance orphans"
  Cluster B (5 concepts): software, API, deployment → "Tech orphans"  
  Cluster C (11 concepts): scattered, no clear theme → Wait for more data

Election A → Policy shard wins → 7 concepts transfer as unit
Election B → Engineering shard wins → 5 concepts transfer as unit
Cluster C → No election yet (incoherent batch)
```

### Election Triggers

Elections occur when coherence monitoring detects misfits, with tier-aware batching:

```python
class CoherenceMonitor:
    def audit_cycle(self):
        for ontology in self.shard.ontologies:
            coherence = self.calculate_coherence(ontology)
            
            if coherence < COHERENCE_THRESHOLD:  # Default: 0.5
                # Identify and classify misfits
                misfits = self.identify_misfits(ontology)
                
                # Separate by tier
                hub_misfits = [c for c in misfits 
                               if classify_concept(c) == ConceptTier.HIGH]
                orphan_misfits = [c for c in misfits 
                                  if classify_concept(c) == ConceptTier.LOW]
                # (MEDIUM tier misfits are protected, not elected)
                
                # Strategy 1: Elect hub subgraphs
                for hub in hub_misfits:
                    if not self.in_cooldown(hub):
                        self.open_election(
                            elect_hub_subgraph(hub)
                        )
                
                # Strategy 2: Batch orphans and elect consolidation groups
                for batch_election in elect_orphan_batch(ontology):
                    self.open_election(batch_election)
    
    def identify_misfits(self, ontology) -> list[Concept]:
        """
        Find concepts whose similarity to ontology centroid 
        is > 2 standard deviations below mean.
        """
        centroid = ontology.get_centroid_embedding()
        
        similarities = [
            cosine_similarity(c.embedding, centroid)
            for c in ontology.concepts
        ]
        
        mean_sim = np.mean(similarities)
        std_sim = np.std(similarities)
        
        threshold = mean_sim - (2 * std_sim)
        
        return [
            c for c, sim in zip(ontology.concepts, similarities)
            if sim < threshold
        ]
```

### Election Types Summary

| Type | Trigger | What Moves | Benefit |
|------|---------|------------|---------|
| **SUBGRAPH** | Hub misfit | Hub + N-hop neighborhood | Keeps cluster coherent |
| **CONSOLIDATION** | Orphan batch | Similar orphans grouped | Reduces noise, efficient |
| **SINGLE** | (Rare) Individual high-value misfit | One concept | Simple case |

### Why This Matters

**Without tiers**: 100 misfit concepts = 100 elections = network noise + fragmented transfers

**With tiers**:
- 3 hub misfits → 3 subgraph elections (each moves ~20 concepts)
- 50 orphan misfits → 4 consolidation elections (batched by similarity)
- 47 core misfits → 0 elections (protected, they define the ontology)

Total: **7 elections** instead of 100, moving coherent groups instead of isolated nodes.

### Network Topology

Elections propagate through a lightweight gossip layer:

```
┌─────────┐     ┌─────────┐     ┌─────────┐
│ Shard A │◄───►│ Router  │◄───►│ Shard B │
└─────────┘     └────┬────┘     └─────────┘
                     │
                     ▼
                ┌─────────┐
                │ Router  │◄───► (more shards)
                └─────────┘
```

**Router responsibilities**:
- Maintain shard registry (who exists, their hub concept summaries)
- Broadcast ELECTION_OPEN to relevant shards (based on hub similarity)
- Do NOT decide winners (shards do that directly)

**Shard responsibilities**:
- Compute own fit scores
- Bid in elections
- Transfer data peer-to-peer (not through router)
- Maintain coherence through periodic audits

### System Values (Constraints)

Elections respect invariants:

| Value | Enforcement |
|-------|-------------|
| **Coherence floor** | Reject transfer if projected coherence < 0.5 |
| **Capacity limit** | Don't bid if at storage/load limit |
| **Improvement threshold** | Only bid if score > originator + 0.05 (5% better) |
| **Convergence** | Cooldown period prevents oscillation (default: 1 hour) |
| **Evidence preservation** | Transfers include full provenance chain |
| **Consistency** | TCP-style confirm before release |

### Failure Modes

#### Election Timeout (No Bids)

```python
if no_bids_received(election_id, ttl):
    # No one wants it more than originator
    # Concept stays home
    # Maybe schedule for pruning review if grounding is also low
    pass
```

#### Transfer Failure

```python
if transfer_confirm.status == "ROLLBACK":
    # Winner couldn't integrate concept
    # Originator still has data (never deleted)
    # Log failure reason
    # Maybe exclude this bidder from next election
    pass
```

#### Bidder Disappears After Winning

```python
if no_transfer_request_received(winner, timeout=30):
    # Winner went offline
    # Award to runner-up if available
    # Otherwise concept stays home
    pass
```

#### Originator Disappears Mid-Transfer

```python
if transfer_data_never_arrives(timeout=60):
    # Originator went offline
    # Winner cleans up partial state
    # Next coherence audit will detect orphaned election
    pass
```

---

## Consequences

### Positive

**1. Self-Organizing Placement**

Concepts flow toward their highest-affinity shards without central coordination. Emergent specialization occurs as shards accumulate related knowledge.

**2. Minimal Network Traffic**

| What Travels | When |
|--------------|------|
| Election announcement | Broadcast (small) |
| Embedding fetch | Only interested candidates |
| Fit scores | Single float per bidder |
| Full concept data | Only to winner |

Compare to naive approach: broadcasting full embeddings to all shards.

**3. Graceful Degradation**

- Single shard = no elections, system works normally
- Router offline = shards continue operating, elections pause
- Shard offline = its concepts unavailable, but others unaffected

**4. Convergence Guarantee**

```
Concept in wrong place
  → Low coherence detected
  → Election opened
  → Better home bids higher
  → Transfer succeeds
  → Coherence improves at both shards
  → No more elections for this concept (cooldown + good fit)
  → System stabilizes
```

The improvement threshold + cooldown prevent infinite shuffling.

**5. Epistemic Integrity Preserved**

- Evidence travels with concepts (provenance maintained)
- Cross-shard edges created for relationships that span shards
- Grounding scores remain valid (edges are preserved)

### Negative

**1. Election Overhead**

Each misfit concept triggers network round-trip. Mitigation:
- Batch elections for multiple misfits
- Rate limit elections per shard
- Only elect concepts above minimum evidence threshold

**2. Temporary Inconsistency**

During transfer, concept exists on originator. After confirm, only on winner. Brief window where queries might miss it. Mitigation:
- Keep routing stub on originator
- Router caches recent transfers
- Queries can retry through router

**3. Hub Concept Dependency**

Fit score requires hub concepts. New/empty shards have no hubs → can't compute meaningful fit. Mitigation:
- Bootstrap shards with seed ontology
- New shards bid low, accumulate concepts, develop hubs organically
- "Frontier" shards accept anything (always bid 0.0)

**4. Oscillation Risk**

Concept could bounce between shards if fit scores are close. Mitigation:
- 5% improvement threshold
- Cooldown period after transfer
- Track transfer history, reject moves to previous homes within window

---

## Examples

### Example 1: Subgraph Election (Hub Tier)

```
Shard-3 (Biology) detects hub misfit: "regulatory frameworks"
  ConceptRank: 94th percentile (HUB tier)
  Local fit: 0.34
  Connected concepts (2-hop): 15 concepts, all low coherence

Elect as SUBGRAPH:
  - "regulatory frameworks" (hub)
  - "policy compliance" (12 connections)
  - "governance structures" (8 connections)
  - ... 12 more connected concepts
  
  Aggregate embedding: centroid of 15 concepts
  Combined fit: 0.38

ELECTION_OPEN broadcast (type=SUBGRAPH, concept_count=15)

Shard-7 (Policy): fetches aggregate embedding, computes fit = 0.89
  → BID: 0.89, capacity_ok=True

Shard-12 (Legal): computes fit = 0.71
  → BID: 0.71

WINNER: Shard-7 (0.89)

Transfer: 15 concepts + all internal edges + evidence

Shard-7 confirms: coherence 0.81, SUCCESS

Shard-3 releases claims, keeps cross-shard stubs to remaining Biology hubs
```

### Example 2: Consolidation Election (Orphan Tier)

```
Shard-3 (Biology) audit finds 23 orphans (bottom 30% ConceptRank)

Clustering orphans by similarity:
  Cluster A: ["regulatory", "policy", "compliance", "oversight", 
              "guidelines", "standards", "enforcement"] 
              → 7 concepts, theme: "Governance"
  
  Cluster B: ["API endpoint", "deployment", "container", 
              "kubernetes", "dockerfile"]
              → 5 concepts, theme: "DevOps"
  
  Cluster C: ["mitochondria", "chloroplast", "organelle", ...]
              → 11 concepts, but coherence WITH Biology is 0.72
              → Not misfits, just low-connectivity. Skip.

ELECTION_OPEN for Cluster A (type=CONSOLIDATION, concept_count=7)
  Aggregate embedding: centroid of 7 governance concepts
  Originator fit: 0.31
  Theme: "Governance and regulatory concepts"

Shard-7 (Policy): bids 0.88
Shard-12 (Legal): bids 0.79

WINNER: Shard-7

Transfer: 7 concepts as batch

---

ELECTION_OPEN for Cluster B (type=CONSOLIDATION, concept_count=5)
  Aggregate embedding: centroid of 5 DevOps concepts
  Originator fit: 0.22
  Theme: "Software deployment infrastructure"

Shard-15 (Engineering): bids 0.91
Shard-8 (Cloud): bids 0.85

WINNER: Shard-15

Transfer: 5 concepts as batch

---

Result: 2 elections moved 12 concepts (instead of 12 separate elections)
Remaining 11 orphans stayed (they fit Biology, just low connectivity)
```

### Example 3: Protected Core (Medium Tier)

```
Shard-3 (Biology) coherence audit

Misfit candidates identified:
  - "CRISPR gene editing" (ConceptRank: 65th percentile) → CORE tier
  - "DNA replication" (ConceptRank: 78th percentile) → CORE tier
  - "cellular respiration" (ConceptRank: 55th percentile) → CORE tier

All three are MEDIUM tier (core concepts).

Even though coherence check flagged them, they are PROTECTED:
  → No election opened
  → These concepts ARE the Biology shard's identity
  → Moving them would hollow out the ontology

Instead: Flag for human review
  "3 core concepts have low coherence. Ontology may be fragmenting.
   Consider: Is this ontology too broad? Should it split?"
```

### Example 4: No Winner (Orphans Stay Home)

```
Shard-3 (Biology) has orphan batch: 
  ["obscure_bacteria_xyz", "rare_enzyme_abc", "novel_protein_123"]
  
  Theme: "Obscure biological entities"
  Aggregate fit at Shard-3: 0.45

ELECTION_OPEN (type=CONSOLIDATION, concept_count=3)

All other shards compute fit:
  Shard-7 (Policy): 0.12 (no bid, can't beat 0.45)
  Shard-15 (Engineering): 0.08 (no bid)
  Shard-4 (Chemistry): 0.41 (no bid, below originator)

WINNER: None (no bids exceeded 0.45)

Concepts stay at Shard-3.
Flagged: "Orphan batch has no better home. Consider:
  - Are these concepts too niche? (pruning candidate)
  - Is there a missing ontology? (new shard needed)
  - Will future documents strengthen them? (wait and see)"
```

### Example 5: Hub Concept Replication (Not Election)

```
Hub concept "machine learning" exists on Shard-2 (AI/ML)
  ConceptRank: 99th percentile
  Connections: 234 edges

Shard-5 (Data Engineering) frequently references it:
  - 47 cross-shard edges point to "machine learning"
  - Queries often traverse Shard-2 → Shard-5

This is NOT an election case (hub is well-placed at Shard-2).
Instead: REPLICATION REQUEST

Shard-5: "Can I get a replica of 'machine learning'? 
          I have 47 edges pointing to it."

Shard-2: "machine learning" is hub (protected), but replication allowed.

Transfer as REPLICA (not migration):
  - Shard-5 gets read-only copy
  - Shard-2 keeps authoritative original
  - Changes sync periodically (eventual consistency)
  - Cross-shard edges become local on Shard-5

Now: Shard-5 queries resolve locally for common ML references
Hub stays at Shard-2 where it belongs
```

---

## Alternatives Considered

### Alternative 1: Central Coordinator

A master node decides all placements.

```python
class CentralCoordinator:
    def place_concept(self, concept):
        scores = [shard.calculate_fit(concept) for shard in self.shards]
        winner = argmax(scores)
        self.command_transfer(concept, winner)
```

**Rejected because**:
- Single point of failure
- Bottleneck for all placement decisions
- Doesn't scale with shard count
- Violates distributed systems principles we've established

### Alternative 2: Full DHT (Kademlia-style)

Use standard DHT with content hashing.

```python
shard = hash(concept.embedding) % num_shards
```

**Rejected because**:
- Destroys semantic locality
- "Similar" concepts scatter randomly
- No concept of epistemic fit
- Solves wrong problem (storage vs understanding)

### Alternative 3: Gossip-Only (No Elections)

Shards gossip about concepts, eventually converge.

```python
def gossip_cycle(self):
    neighbor = random.choice(self.neighbors)
    for concept in self.misfits:
        neighbor.consider(concept)  # Maybe they want it?
```

**Rejected because**:
- Slow convergence
- No guarantee of finding best home
- Concept might traverse many shards before settling
- Higher total network traffic

### Alternative 4: Periodic Global Rebalance

Central batch job analyzes all concepts, computes optimal placement, migrates everything.

**Rejected because**:
- Requires global knowledge (doesn't scale)
- Disruptive (mass migrations)
- Can't adapt to real-time changes
- Violates incremental, convergent design principle

---

## Implementation Roadmap

### Phase 1: Single-Shard Foundation (Current)

- ✅ Coherence monitoring
- ✅ Hub concept extraction
- ✅ Grounding score calculation
- 🔲 Misfit detection (> 2σ from centroid)

### Phase 2: Election Protocol

- 🔲 Message types (protobuf or JSON schema)
- 🔲 Election state machine
- 🔲 Fit score endpoint (for candidates to fetch)
- 🔲 Transfer data serialization (concept + evidence + edges)

### Phase 3: Multi-Shard Deployment

- 🔲 Router shard with registry
- 🔲 Election broadcast mechanism
- 🔲 Peer-to-peer transfer (not through router)
- 🔲 Cross-shard edge stubs

### Phase 4: Robustness

- 🔲 Failure handling (timeouts, rollbacks)
- 🔲 Cooldown and oscillation prevention
- 🔲 Hub concept replication
- 🔲 Monitoring and observability

---

## Open Questions

1. **Election scope**: Broadcast to all shards, or only those with similar hub concepts?
   - Full broadcast is simple but doesn't scale
   - Router could pre-filter based on hub similarity

2. **Batch elections**: How to handle multiple misfits from same ontology?
   - Separate elections? (parallel, more traffic)
   - Combined election? (complex winner determination)

3. **Cross-shard edges**: When concept moves, its relationships become cross-shard.
   - Keep stubs on originator?
   - Update all related concepts' edges?
   - Lazy resolution at query time?

4. **Hub concept protection**: Should hubs ever migrate?
   - Probably not (they define shard identity)
   - Replication instead of migration for hubs?

5. **Frontier shards**: How do new/empty shards bootstrap?
   - Special "frontier" role that accepts anything?
   - Seed with manually-assigned ontology?

---

## References

- **FENNEL (2014)**: Streaming graph partitioning with locality-balance objective
- **PowerGraph (2012)**: Vertex-cut for power-law graphs
- **Kademlia DHT**: XOR-based routing (contrast with our semantic approach)
- **Raft Consensus**: Not directly applicable, but informs failure handling
- **ADR-044**: Probabilistic Truth Convergence (grounding scores)
- **ADR-055**: CDN and Serverless Deployment (sharding context)
- **ADR-058**: Polarity Axis Triangulation (coherence calculation)

---

## Appendix: Protocol State Machine

```
                    ┌───────────────┐
                    │    IDLE       │
                    └───────┬───────┘
                            │ coherence < threshold
                            ▼
                    ┌───────────────┐
                    │ ELECTION_OPEN │
                    └───────┬───────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
              ▼             ▼             ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │ BID (A)  │  │ BID (B)  │  │ (timeout)│
        └────┬─────┘  └────┬─────┘  └────┬─────┘
              │             │             │
              └─────────────┼─────────────┘
                            │
                            ▼
                    ┌───────────────┐
                    │ WINNER_CHOSEN │──────────┐
                    └───────┬───────┘          │
                            │                  │ (no winner)
                            ▼                  │
                    ┌───────────────┐          │
                    │ TRANSFERRING  │          │
                    └───────┬───────┘          │
                            │                  │
              ┌─────────────┴─────────────┐    │
              │                           │    │
              ▼                           ▼    ▼
        ┌──────────┐                ┌──────────┐
        │ CONFIRMED│                │ ROLLBACK │
        └────┬─────┘                └────┬─────┘
              │                           │
              ▼                           ▼
        ┌──────────┐                ┌──────────┐
        │ RELEASED │                │   IDLE   │
        └────┬─────┘                └──────────┘
              │
              ▼
        ┌──────────┐
        │   IDLE   │
        └──────────┘
```

---

**Implementation Status:** Draft  
**Next Steps:** Review with team, refine message schemas, prototype Phase 1 misfit detection
