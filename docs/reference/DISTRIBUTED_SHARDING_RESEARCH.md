# Distributed Graph Database Sharding: Research and Architectural Patterns

*Research findings on distributed graph database architectures, semantic routing, and workload-aware partitioning strategies - compiled October 15, 2025*

---

## Table of Contents

- [Context and Motivation](#context-and-motivation)
- [Current System Architecture](#current-system-architecture)
- [Parallel Architectures in Distributed Systems](#parallel-architectures-in-distributed-systems)
- [Key Research Findings](#key-research-findings)
- [Conceptual Design Patterns](#conceptual-design-patterns)
- [Technical Implementation Considerations](#technical-implementation-considerations)
- [The Bitter Lesson Perspective](#the-bitter-lesson-perspective)
- [References](#references)

---

## Context and Motivation

### The Single-Shard Reality

The current Knowledge Graph System operates successfully on a single Apache AGE (PostgreSQL graph extension) instance with:

- **Recursive concept upsert**: LLM-driven extraction with vector similarity matching (≥0.75 threshold)
- **Natural domain separation**: Disconnected subgraphs form organically within AGE
- **Full-scan vector search**: NumPy-based cosine similarity (works well, will hit scaling limits)
- **Hub concept emergence**: High-connectivity nodes naturally identify domain expertise

**Key observation**: Apache AGE already handles multiple disconnected ontologies on a single shard without performance degradation - they simply exist as separate subgraphs with sparse or no inter-connections.

### The Scaling Question

What problems does multi-shard architecture actually solve?

1. **Resource limits**: Single PostgreSQL instance has finite RAM/disk/CPU capacity
2. **Query performance**: Graph traversal degrades with total graph size (even if disconnected)
3. **Write throughput**: Concurrent upserts compete for locks
4. **Ontology discovery**: With 50+ ontologies, knowing "which to query" becomes non-trivial
5. **Geographic/organizational distribution**: Teams or regions need autonomous instances

**Not solving**: Domain pollution (AGE already separates), or complex "reasoning" (computation > hand-crafted knowledge)

### Research Goals

Investigate distributed graph database architectures to:

1. Identify proven patterns for semantic-based sharding
2. Understand routing mechanisms for content-based partitioning
3. Evaluate workload-aware adaptation strategies
4. Assess Apache AGE horizontal scaling options
5. Avoid anthropomorphizing design (focus on computational patterns)

---

## Current System Architecture

### Single-Shard Components

```
Document → REST API → LLM Extraction → Apache AGE Graph
              ↓
       Vector Similarity Search
              ↓
       Recursive Concept Upsert
```

**Tech Stack**:
- Python 3.11+ FastAPI (REST API + ingestion pipeline)
- Apache AGE 1.5.0 / PostgreSQL 16 (graph database using openCypher)
- TypeScript/Node.js (unified `kg` CLI + MCP client)
- OpenAI/Anthropic APIs (LLM providers for extraction + embeddings)

### Recursive Upsert Process

1. **Chunk document** into semantic boundaries (~1000 words, configurable)
2. **Vectorize chunk** using OpenAI embeddings (1536-dim)
3. **Query local ontology** for similar concepts (≥0.75 cosine similarity)
4. **Extract relationships** - LLM receives high-similarity concepts + their relationship clusters as context
5. **Upsert to graph** - merge similar concepts or create new ones
6. **Update hub concepts** - track high-connectivity nodes (PageRank/betweenness centrality)

**Critical insight**: Existing knowledge shapes how new knowledge integrates - recursive, context-aware extraction.

### Natural Ontology Separation

```cypher
// Two unrelated ontologies on same shard
MATCH path = (:Concept {ontology: "CRISPR Techniques"})-[*]->(:Concept {ontology: "1980s Cartoons"})
RETURN path
// Result: No paths found (semantic distance too high, no edges created)
```

**What this means**: Multi-shard architecture isn't solving "domain pollution" - it's solving resource scaling and ontology discovery.

---

## Parallel Architectures in Distributed Systems

### 1. PowerGraph: Vertex-Cut Partitioning (2012)

**Source**: PowerGraph: Distributed Graph-Parallel Computation on Natural Graphs (OSDI 2012)

**Problem**: Natural graphs (social networks, web graphs, knowledge graphs) follow **power-law distributions**:
- A small number of high-degree vertices connect to most edges
- Example: 1% of vertices in Twitter graph connect to 50% of edges

**Traditional edge-cut approach fails**:
- Partitions vertices, cuts edges between partitions
- High-degree vertices and ALL their edges land on one partition → hotspot
- Massive imbalance in work distribution

**PowerGraph's vertex-cut approach**:
- Partitions edges, allows vertices to be replicated across machines
- High-degree vertices distributed across partitions
- Work balances automatically
- **Percolation theory**: Power-law graphs have good natural vertex-cuts

**Parallel to our design**:
- **Hub concepts** (high-connectivity nodes in our graph) ≈ PowerGraph's high-degree vertices
- Distributing hub concepts across shards ≈ vertex-cut strategy
- Our emergent hub concepts = data-driven identification of natural cut points

**Key insight**: "By cutting a small fraction of very high degree vertices, you can quickly shatter a graph" - natural partitioning emerges from graph structure, not prescribed boundaries.

---

### 2. FENNEL: Streaming Graph Partitioning (2014)

**Source**: FENNEL: Streaming Graph Partitioning for Massive Scale Graphs (WSDM 2014)

**Problem**: How to assign vertices/edges to partitions as they arrive in stream, without knowing full graph upfront?

**FENNEL's objective function**:
```
assign vertex v to partition that maximizes:
  score = (# neighbors already in partition) - α * (partition_size)^γ

where:
  first term  = locality benefit (keep related things together)
  second term = balance penalty (prevent overload)
  α, γ        = tuning parameters (typically γ = 1.5)
```

**Performance**:
- One-pass streaming algorithm
- Comparable to offline METIS but **6-8x faster**
- Twitter graph (1.4B edges): FENNEL 40 minutes (6.8% edge cuts) vs METIS 8.5 hours (11.98% edge cuts)

**Direct parallel to our routing design**:
```python
def route_document(doc_vector, shard_stats):
    scores = []
    for shard in shards:
        # Locality term (FENNEL's neighbor count)
        similarity = cosine_similarity(doc_vector, shard.hub_vector_summary)

        # Balance penalty (FENNEL's partition size penalty)
        α = 1.5  # tuning parameter
        γ = 1.5  # FENNEL recommendation
        penalty = α * (shard.concept_count / target_size) ** γ

        score = similarity - penalty
        scores.append((shard, score))

    return max(scores, key=lambda x: x[1])[0]
```

**Key insight**: Our "router decides where documents upsert" based on similarity + capacity = FENNEL's proven streaming partitioning approach.

---

### 3. Workload-Aware Adaptive Partitioning

#### AWAPart (2022)

**Source**: AWAPart: Adaptive Workload-Aware Partitioning of Knowledge Graphs (arXiv 2203.14884)

**Problem**: Static partitioning optimizes for initial data distribution, but query workloads change over time.

**Approach**:
- Monitor query patterns to identify frequently co-accessed concepts
- **Dynamically repartition** to cluster query-relevant triples together
- Minimize cross-partition joins by adapting to actual usage

**Metrics**:
- Query processing time improved after dynamic adaptation
- Reduces communication overhead for common query patterns

#### WASP (2021)

**Source**: A Workload-Adaptive Streaming Partitioner for Distributed Graph Stores

**Problem**: Existing methods don't adapt to dynamic workloads that keep emerging

**Approach**:
- **Runtime adaptation**: Incrementally adjusts partitions based on active edges in query workload
- Tracks "hot paths" through the graph (frequently traversed relationships)
- Rebalances to colocate frequently co-traversed subgraphs

**Parallel to our "active management agent"**:
- Coherence monitoring → detects ontology drift
- Misfit detection → identifies poorly-matched concepts
- Reorganization → splits + re-routes to better shard
- Convergent process → once concepts find "right home" (high similarity), stops triggering reorganization

**Key insight**: Our self-healing architecture with coherence scoring = workload-aware adaptive partitioning applied to semantic knowledge graphs.

---

### 4. Semantic Overlay Networks & DHT-Based Routing

**Sources**:
- DHT-based Semantic Overlay Network for Service Discovery
- Content Addressable Networks (CAN)

**Traditional DHT problem**:
```python
shard = hash(key) % N  # Destroys semantic locality
```
- Documents about "quantum physics" scatter randomly across shards
- No locality benefit for related queries

**Semantic overlay approach**:
```python
shard = argmax(similarity(query, shard_semantic_profile))  # Preserves locality
```
- Nodes advertise **semantic descriptions** of their content
- Routing based on semantic similarity, not hash distribution
- TTL prevents infinite routing loops (like our router hop limits)

**Content-Addressable Networks (CAN)**:
- Treats nodes as points in d-dimensional coordinate space
- Routes to nearest node in semantic space
- **Our vector embeddings = CAN's coordinate space**

**Parallel to our router shard**:
- Router maintains **ontology fingerprints** (hub concepts + vector summaries)
- Routes queries/upserts based on vector similarity to shard profiles
- Each router knows peer routers + reachable ontology clusters
- Message passing with hop limits prevents loops

**Key insight**: Our "router tracks hub concepts for semantic routing" = DHT-based semantic overlay networks, proven pattern in P2P systems.

---

### 5. Federated SPARQL Query Optimization

**Sources**:
- Lothbrok: Optimizing SPARQL Queries over Decentralized Knowledge Graphs
- FedX Federation Engine

#### Lothbrok Strategy

**Problem**: How to efficiently query knowledge graphs distributed across multiple endpoints?

**Approach**:
1. **Cardinality estimation**: Predict result sizes to plan query execution
2. **Locality awareness**: Minimize network transfers by smart join ordering
3. **Fragmentation strategy**: Based on **characteristic sets** (natural clusters) vs predicate-based

**Characteristic sets** ≈ our concept clusters (domain-driven grouping)

#### FedX Engine

**Capabilities**:
- Transparent federation of multiple SPARQL endpoints
- **Source selection**: Determine which endpoints have relevant data (like our router)
- Join processing that minimizes remote requests
- Automatically selects relevant sources based on query patterns

**Index structures**:
- **PPBF (Prefix-Partitioned Bloom Filters)**: Compact summary of endpoint contents
  - Analogous to our router's hub concept index
- Query planning uses index to prune unnecessary endpoints

**Parallel to our cross-shard queries**:
- Router knows which shards contain which ontologies (source selection)
- Can dispatch to multiple shards in parallel if query spans domains
- Aggregates results from distributed endpoints

**Key insight**: Federated SPARQL systems solve exactly the problem we're designing for - semantic routing to distributed knowledge without centralized data.

---

### 6. Hybrid Vector + Graph Systems

**Source**: High-Throughput Vector Similarity Search in Knowledge Graphs (Apple ML Research, 2023)

**System**: HQI (High-Throughput Query Index)

**Problem**: Queries combine **vector similarity search** + **graph traversal predicates**

**Example query**: "Find songs similar to past queries, matching artist='X' AND genre='Y' AND release_date>2020"
- Vector part: Similarity to past query embeddings
- Graph part: Traverse artist→genre relationships, filter by attributes

**Approach**:
- **Workload-aware vector partitioning**: Organize vectors based on common query patterns
- **Multi-query optimization**: Batch similar searches to reduce overhead
- Co-optimize vector search + graph operations

**Performance**: 31× throughput improvement for hybrid queries

**Parallel to our recursive concept upsert**:
```
Query: "Find similar concepts (≥0.75 threshold) with their relationship clusters"
  ↓
Vector part: Embedding similarity to existing concepts
  ↓
Graph part: Pull relationship subgraph for context
  ↓
LLM extraction: Use context to guide new concept creation
```

**Key insight**: Our system is already a hybrid vector-graph architecture - the research validates co-optimizing both aspects.

---

### 7. Apache AGE with Citus Sharding

**Source**: Scaling Apache AGE for Large Datasets (Dev.to, 2024)

**Citus extension for PostgreSQL**:
```sql
CREATE EXTENSION citus;
SELECT create_distributed_table('vertex_label', 'id');
SELECT create_distributed_table('edge_label', 'id');
```

**Capabilities**:
- Horizontal scaling of PostgreSQL tables across worker nodes
- Distributed query execution with pushdown
- Colocated joins if partitioning keys match

**Challenge for semantic routing**:
- Citus uses **hash-based sharding** by default: `shard = hash(id) % workers`
- **Destroys semantic locality** - related concepts scatter randomly
- Performance benefit from parallelism, but loses domain coherence

**Solution options**:
1. **Custom distribution column**: Use semantic key (e.g., ontology name) instead of hash
2. **Application-level routing**: Our router layer directs to specific Citus workers
3. **Hybrid approach**: Citus for storage distribution, semantic router for query/upsert routing

**Key insight**: Citus provides infrastructure for multi-shard AGE, but semantic routing must be application-layer (exactly what we're designing).

---

## Key Research Findings

### 1. Graph Partitioning Fundamentals

**Edge-Cut vs Vertex-Cut**:

| Approach | How It Works | Best For | Weakness |
|----------|--------------|----------|----------|
| **Edge-Cut** | Partition vertices, cut edges between partitions | Regular graphs, balanced degree | Power-law graphs create hotspots |
| **Vertex-Cut** | Partition edges, replicate high-degree vertices | Natural graphs (social, web, knowledge) | Requires vertex replication |

**METIS**: Classical offline partitioning (multilevel coarsening)
- High quality partitions
- Slow on massive graphs
- Requires full graph knowledge upfront

**Streaming Partitioning** (FENNEL, etc.):
- One-pass, online assignment
- Near-METIS quality, much faster
- Works with unknown graph structure
- **Perfect for our upsert-as-you-go model**

---

### 2. Semantic Routing Patterns

**Content-based routing** consistently outperforms hash-based for knowledge graphs:

```
Hash-based:     semantic locality = 0   (random distribution)
Semantic-based: semantic locality → 1   (related concepts colocated)
```

**Objective function design** (from FENNEL, AWAPart, others):
```
routing_score = locality_benefit - balance_penalty

where:
  locality   = how well content matches shard domain
  balance    = prevent any shard from becoming overloaded
```

**Trade-off**: Perfect locality vs perfect balance
- All related content on one shard → hotspot
- Perfectly balanced load → poor locality
- **Solution**: Tunable penalty function (α, γ parameters)

---

### 3. Workload-Aware Adaptation

**Key findings from AWAPart, WASP, Q-Graph**:

1. **Static partitioning is suboptimal**: Initial data distribution ≠ query patterns
2. **Runtime monitoring essential**: Track frequently co-accessed concepts
3. **Incremental adaptation works**: No need for full repartitioning
4. **Locality trumps balance for queries**: Better to have slight imbalance if it reduces cross-shard communication

**Adaptation triggers**:
- Query latency exceeds threshold
- Cross-shard join rate too high
- Shard coherence score drops (concepts don't "fit" together)

**Our coherence monitoring** fits this pattern:
```python
def detect_misfit(ontology):
    # Measure intra-ontology similarity
    concept_vectors = [c.embedding for c in ontology.concepts]
    avg_similarity = mean(pairwise_cosine_similarity(concept_vectors))

    if avg_similarity < 0.5:  # Low coherence
        # Trigger reorganization
        split_into_new_ontology()
        find_better_shard()
        re_upsert()
```

---

### 4. Natural Graph Properties

**Power-law degree distribution** is universal in knowledge graphs:
- Few hub concepts with many connections
- Many peripheral concepts with few connections
- **Proven by our own data**: Some concepts appear in hundreds of relationships, most in <5

**Implications**:
- Vertex-cut naturally balances work (replicate hubs)
- Hub concepts = natural partitioning boundaries
- Emergent specialization (hubs attract related concepts)

**Percolation theory result**: By cutting small fraction of high-degree vertices, graph shatters into manageable components
- **Our application**: Replicating hub concepts across shards enables efficient cross-shard queries

---

### 5. Vector Similarity in Distributed Systems

**Workload-aware partitioning** (Apple HQI, others):
- Organize vectors based on common query patterns
- **Hot vectors**: Frequently queried, should be cached/replicated
- **Cold vectors**: Rarely accessed, can be on slower storage

**Our current full-scan approach**:
```python
# O(n) where n = all concepts in ontology
similarity_scores = cosine_similarity(query_vector, all_concept_vectors)
```

**Scaling options**:
1. **HNSW index** (Hierarchical Navigable Small World): O(log n) approximate search
2. **Shard-level parallelism**: Query each shard independently, merge results
3. **Hybrid**: HNSW within shards + semantic routing across shards

---

## Conceptual Design Patterns

### Pattern 1: Graceful Degradation (Single → Multi)

**Design principle**: Single-shard mode IS the core implementation, multi-shard is orchestration

```
Configuration determines mode:

SINGLE_SHARD (n=1):
  ├─ Apache AGE instance
  ├─ Recursive upsert (existing code)
  ├─ Local vector search (NumPy full scan)
  └─ No router needed

MULTI_SHARD (n>1):
  ├─ Multiple AGE instances (identical to single-shard code)
  ├─ Router layer (lightweight, optional)
  │   ├─ Tracks: which ontologies exist where
  │   ├─ Stores: hub concept vectors per ontology
  │   └─ Routes: based on semantic similarity
  └─ Each shard operates autonomously
```

**Key insight**: The shard implementation doesn't change. Multi-shard adds orchestration, not re-architecture.

---

### Pattern 2: Router as Metadata Layer

**Design**: Router is NOT on critical path for shard operations

```
Router Shard {
  ontology_index: [
    {
      id: "biology_001",
      shard: "shard_3",
      hub_concepts: ["CRISPR", "gene_editing", "DNA"],
      vector_summary: [0.23, 0.45, ...],  // centroid of hub concept vectors
      concept_count: 15420,
      capacity_metrics: { load: 0.6, latency_ms: 45 }
    },
    ...
  ]
}
```

**Query flow**:
1. User query → Vectorize
2. Router: Similarity search against ontology summaries
3. Router: "biology_001 on shard_3 matches 0.92"
4. Direct query to shard_3, ontology biology_001
5. Shard executes query (no router involved)

**Upsert flow**:
1. Document arrives → Vectorize
2. Router: "biology_001 matches 0.88, software_dev_001 matches 0.15"
3. Route to shard_3, ontology biology_001
4. Recursive upsert runs locally on shard
5. If new hub concepts emerge → push update to router

**Router failure mode**: Shards continue operating, router can be rebuilt from shard metadata

---

### Pattern 3: Self-Healing with Convergence Guarantee

**Problem**: Initial routing decisions may be suboptimal (user error, novel domain, etc.)

**Solution**: Active management agent with convergent reorganization

```
Periodic audit cycle:
  ├─ Query router for high-activity shards
  ├─ Analyze ontology coherence:
  │   └─ coherence = mean(pairwise_similarity(concepts in ontology))
  ├─ Detect misfits:
  │   └─ IF coherence < 0.5 THEN misfit detected
  ├─ Local reorganization:
  │   ├─ Split misfit concepts → new local ontology
  │   ├─ Query router for better shard location
  │   └─ Re-upsert to higher-match shard
  └─ Convergence property:
      └─ Once concepts reach high-similarity shard, coherence > 0.5
      └─ No longer triggers reorganization
      └─ Process terminates (no infinite loops)
```

**Example**:
```
User uploads "Smurfs 1980s cartoons" to CRISPR ontology (mistake)
  ↓
Coherence score drops (CRISPR concepts + Smurfs = low similarity)
  ↓
Agent detects: avg_similarity = 0.35 < 0.5 threshold
  ↓
Splits "Smurfs" concepts → new ontology on same shard
  ↓
Queries router: "which shard has '1980s cartoons' knowledge?"
  ↓
Router: "pop_culture_shard has 'Saturday morning cartoons' (similarity 0.87)"
  ↓
Re-upserts "Smurfs" ontology to pop_culture_shard
  ↓
New coherence: 0.91 > 0.5 → stable, no further reorganization
```

**Parallel to research**: AWAPart's dynamic adaptation + WASP's workload-aware rebalancing

---

### Pattern 4: Hub Concept Replication (Vertex-Cut)

**Insight from PowerGraph**: Replicate high-degree vertices to balance work

**Our application**:
```
Hub concept: "gene_editing" appears in:
  ├─ biology_shard (primary)
  ├─ ethics_shard (replica - bioethics discussions)
  └─ policy_shard (replica - regulation documents)

Query: "What are ethical concerns about gene editing?"
  ↓
Router: Ethics context → route to ethics_shard
  ↓
ethics_shard has local replica of "gene_editing" hub concept
  ↓
No cross-shard traversal needed for initial query
  ↓
Can optionally follow reference to biology_shard for deeper technical details
```

**Trade-off**: Storage overhead (replicas) vs query performance (local access)

**When to replicate**:
- Concept appears in 3+ ontologies across different shards
- High query frequency
- Cross-shard traversal is common

---

### Pattern 5: FENNEL-Style Streaming Assignment

**Implementation**:
```python
class ShardRouter:
    def route_document(self, document_text: str) -> tuple[Shard, Ontology]:
        # Vectorize document
        doc_vector = embed(document_text)

        # Score all shards
        scores = []
        for shard in self.shards:
            for ontology in shard.ontologies:
                # Locality benefit (semantic similarity)
                locality = cosine_similarity(doc_vector, ontology.vector_summary)

                # Balance penalty (prevent overload)
                load_ratio = shard.concept_count / self.target_shard_size
                penalty = self.alpha * (load_ratio ** self.gamma)

                score = locality - penalty
                scores.append((shard, ontology, score))

        # Threshold check
        best_shard, best_ontology, best_score = max(scores, key=lambda x: x[2])

        if best_score < 0.4:  # Novel domain
            # Create new ontology on least-loaded shard
            target_shard = min(self.shards, key=lambda s: s.concept_count)
            new_ontology = target_shard.create_ontology()
            return target_shard, new_ontology

        return best_shard, best_ontology
```

**Parameters** (from FENNEL research):
- `alpha`: Balance weight (typically 1.5)
- `gamma`: Penalty exponent (typically 1.5)
- `threshold`: Novel domain cutoff (typically 0.4-0.5)

---

## Technical Implementation Considerations

### Phase 1: Single-Shard Foundation

**Current state**: Already works well

**Additions**:
1. **Hub concept extraction**:
   ```python
   # Use PageRank or betweenness centrality
   hub_concepts = compute_pagerank(ontology.graph, top_k=20)
   ```

2. **Ontology metadata API**:
   ```python
   GET /api/ontology/{name}/profile
   Returns: {
       hub_concepts: [...],
       vector_summary: [...],  # centroid of hub vectors
       concept_count: 1523,
       capacity_metrics: {...}
   }
   ```

3. **Monitor for scaling triggers**:
   - Concept count > 100K (vector search slows)
   - Query latency > 500ms
   - Write contention detected

---

### Phase 2: Router + Multi-Shard

**Router service** (lightweight Python/FastAPI):
```python
class OntologyRouter:
    def __init__(self, shards: List[ShardConnection]):
        self.index = {}  # ontology_id -> shard profile
        self.shards = shards

    def sync_from_shards(self):
        """Pull metadata from all shards"""
        for shard in self.shards:
            profiles = shard.get_ontology_profiles()
            self.index.update(profiles)

    def route_query(self, query_vector: np.ndarray) -> List[ShardOntology]:
        """Find top-k matching ontologies"""
        scores = [
            (ont_id, cosine_similarity(query_vector, profile.vector_summary))
            for ont_id, profile in self.index.items()
        ]
        return sorted(scores, key=lambda x: x[1], reverse=True)[:5]

    def route_upsert(self, doc_vector: np.ndarray) -> ShardOntology:
        """FENNEL-style assignment"""
        return self._fennel_assignment(doc_vector)
```

**Shard modification** (minimal):
```python
# Add: Push updates to router when hub concepts change
if hub_concepts_changed_significantly():
    router.update_ontology_profile(ontology_id, new_profile)
```

---

### Phase 3: Workload-Aware Adaptation (Optional)

**Monitor query patterns**:
```python
class WorkloadMonitor:
    def track_query(self, query_id: str, ontologies_accessed: List[str]):
        # Record which ontologies are frequently co-queried
        self.coquery_matrix[ontologies_accessed] += 1

    def identify_hotspots(self) -> List[tuple[str, str]]:
        # Find ontology pairs queried together often
        # Suggests they should be on same shard
        return high_cooccurrence_pairs(self.coquery_matrix)
```

**Periodic rebalancing**:
```python
class AdaptiveRebalancer:
    def rebalance_cycle(self):
        for ontology in self.ontologies:
            coherence = compute_coherence(ontology)

            if coherence < 0.5:  # Misfit detected
                # Split + find better home
                better_shard = self.router.find_best_shard(
                    ontology.hub_concepts
                )
                if better_shard != ontology.current_shard:
                    self.move_ontology(ontology, better_shard)
```

---

### Phase 4: Hub Concept Replication (Advanced)

**Identify replication candidates**:
```python
def should_replicate(concept: Concept) -> bool:
    # Appears in 3+ ontologies across different shards
    cross_shard_refs = count_cross_shard_references(concept)

    # High query frequency
    query_freq = concept.query_count / total_queries

    return cross_shard_refs >= 3 and query_freq > 0.01
```

**Replication strategy**:
```python
class ConceptReplicator:
    def replicate(self, concept: Concept, target_shards: List[Shard]):
        for shard in target_shards:
            shard.create_replica(
                concept_id=concept.id,
                primary_shard=concept.home_shard,
                vector=concept.embedding,
                metadata={...}
            )

    def sync_updates(self):
        # Eventual consistency: periodically sync replicas
        for replica in self.replicas:
            if replica.is_stale():
                replica.sync_from_primary()
```

---

### Apache AGE + Citus Integration

**Option A: Custom distribution key**
```sql
-- Instead of hash(id), use ontology name for locality
SELECT create_distributed_table('vertex_label', 'ontology');
SELECT create_distributed_table('edge_label', 'ontology');
```
- ✅ Simple, uses Citus built-in
- ❌ Less flexible than application-layer routing

**Option B: Application-layer routing**
```python
# Router maintains mapping: ontology -> Citus worker
ontology_to_worker = {
    "biology_001": "worker_1:5432",
    "software_dev_001": "worker_2:5432",
    ...
}

# Direct connections to specific workers
def get_shard_connection(ontology_id: str) -> psycopg2.Connection:
    worker_url = ontology_to_worker[ontology_id]
    return psycopg2.connect(worker_url)
```
- ✅ Full control over routing logic
- ❌ More complex to manage

**Recommendation**: Start with Option A (Citus with semantic key), migrate to Option B if needed

---

## The Bitter Lesson Perspective

**Sutton's Bitter Lesson** (2019): Methods that leverage computation are ultimately more effective than those that leverage human knowledge.

### Applying the Lesson

**❌ Don't**:
- Hard-code domain taxonomies ("biology goes here, software goes there")
- Prescribe ontology structures
- Build complex "reasoning rules" for routing
- Anthropomorphize the system (avoid "expert" metaphors in implementation)

**✅ Do**:
- Let patterns emerge from data (hub concepts via graph metrics)
- Use computation (vector similarity, graph traversal)
- Scale with compute (more shards, parallel processing)
- Learn routing patterns from query workload

### Our Design Alignment

**Computational approaches in our architecture**:

1. **Vector embeddings** determine similarity, not hand-crafted similarity functions
2. **LLM extraction** discovers relationships, not pre-defined schema
3. **Graph metrics** identify hub concepts, not manual classification
4. **Streaming partitioning** (FENNEL) uses objective function, not rules
5. **Workload-aware adaptation** learns from queries, not prescribed optimization

**Minimal human knowledge encoded**:
- Relationship type vocabulary (30 canonical types) - but even this is fuzzy-matched and expandable
- Coherence threshold (0.5) - but this is tunable, not fundamental
- FENNEL parameters (α, γ) - researched defaults, adjustable

**Where computation wins**:
```
Question: "Should concept X be on shard A or shard B?"

Hard-coded approach:
  IF concept.domain == "biology" THEN shard_A
  ELSE IF concept.domain == "software" THEN shard_B
  (Brittle, requires maintaining taxonomy)

Computational approach:
  similarity_A = cosine(concept.vector, shard_A.profile)
  similarity_B = cosine(concept.vector, shard_B.profile)
  RETURN argmax(similarity - balance_penalty)
  (Generalizes, learns from data)
```

### Not Anthropomorphizing

**Original metaphor**: "Shards as enterprise architects with expertise"
- Useful for human understanding
- Misleading for implementation

**Computational reality**: "Shards as partitions optimizing objective function"
- Hub concepts = high PageRank/betweenness nodes
- Routing = maximize FENNEL score
- Reorganization = minimize coherence loss + balance constraint

The architecture **rhymes with** human expert collaboration, but that's emergent, not designed in. We're applying percolation theory and streaming partitioning algorithms, not modeling organizational behavior.

---

## References

### Academic Papers

**PowerGraph (2012)**
- Gonzalez, J.E., et al. "PowerGraph: Distributed Graph-Parallel Computation on Natural Graphs"
- USENIX OSDI 2012
- Key contribution: Vertex-cut partitioning for power-law graphs

**FENNEL (2014)**
- Tsourakakis, C., et al. "FENNEL: Streaming Graph Partitioning for Massive Scale Graphs"
- ACM WSDM 2014
- Key contribution: One-pass streaming partitioning with locality-balance objective

**AWAPart (2022)**
- "AWAPart: Adaptive Workload-Aware Partitioning of Knowledge Graphs"
- arXiv:2203.14884
- Key contribution: Dynamic repartitioning based on query workload

**WASP (2021)**
- "A Workload-Adaptive Streaming Partitioner for Distributed Graph Stores"
- Data Science and Engineering, 2021
- Key contribution: Runtime adaptation to emerging query patterns

**Apple HQI (2023)**
- "High-Throughput Vector Similarity Search in Knowledge Graphs"
- ACM SIGMOD 2023
- Key contribution: Workload-aware vector partitioning + multi-query optimization

**Lothbrok**
- "Optimizing SPARQL Queries over Decentralized Knowledge Graphs"
- Semantic Web Journal, 2023
- Key contribution: Locality-aware federated query planning

### Technical Documentation

**Apache AGE**
- Apache AGE Manual: https://age.apache.org/age-manual/master/intro/overview.html
- openCypher Reference: https://s3.amazonaws.com/artifacts.opencypher.org/openCypher9.pdf

**Citus for PostgreSQL**
- Citus Documentation: https://docs.citusdata.com/
- Scaling PostgreSQL: https://www.citusdata.com/blog/

**Graph Partitioning**
- METIS: http://glaros.dtc.umn.edu/gkhome/metis/metis/overview
- Graph Partition (Wikipedia): https://en.wikipedia.org/wiki/Graph_partition

**Distributed Hash Tables**
- Chord DHT: https://pdos.csail.mit.edu/papers/chord:sigcomm01/
- Content Addressable Networks: https://dl.acm.org/doi/10.1145/964723.383072

### Relevant Blog Posts & Guides

**Scaling Apache AGE**
- "Scaling Apache AGE for Large Datasets" (Dev.to, 2024)
- URL: https://dev.to/humzakt/scaling-apache-age-for-large-datasets-3nfi

**PuppyGraph on Distributed Graphs**
- "Distributed Graph Database: The Ultimate Guide"
- URL: https://www.puppygraph.com/blog/distributed-graph-database

**Neo4j Infinigraph (2025)**
- Property sharding architecture
- Keeps topology intact while distributing properties

---

## Summary and Next Steps

### What We Learned

1. **Our architectural intuitions align with proven patterns**:
   - Hub concept routing ↔ PowerGraph vertex-cut
   - Streaming document assignment ↔ FENNEL
   - Coherence monitoring ↔ AWAPart/WASP
   - Router metadata layer ↔ Semantic overlay networks

2. **Single-shard mode is the foundation**, multi-shard is orchestration
   - Don't redesign the shard, enable it to participate in topology

3. **Semantic routing preserves locality** where hash-based routing destroys it
   - Critical for knowledge graphs (unlike key-value stores)

4. **Workload-aware adaptation is proven** to improve query performance
   - Our coherence-based reorganization fits this pattern

5. **Apache AGE can scale horizontally** with Citus, but semantic routing must be application-layer
   - Citus provides infrastructure, we provide intelligence

### Recommended Path Forward

**Phase 1: Enhance Single-Shard** *(no architecture changes)*
- Extract hub concepts (PageRank/betweenness)
- Expose ontology metadata API
- Monitor for scaling triggers

**Phase 2: Add Router Layer** *(additive, not breaking)*
- Lightweight router service (Python/FastAPI)
- FENNEL-style streaming assignment
- Sync from shards, stateless design

**Phase 3: Deploy Multi-Shard** *(configuration-driven)*
- Multiple AGE instances (same codebase)
- Router routes queries/upserts
- Each shard operates autonomously

**Phase 4: Workload Adaptation** *(optional, based on real usage)*
- Monitor query patterns
- Coherence-based reorganization
- Hub concept replication if needed

### Open Questions for Future Research

1. **Optimal FENNEL parameters** (α, γ) for our specific workload?
2. **Hub concept replication threshold** - when does it pay off?
3. **Cross-shard query optimization** - when to federate vs consolidate?
4. **Coherence metrics** - is average pairwise similarity best, or graph modularity?
5. **Router failure modes** - how long can shards operate without router?

---

*This research demonstrates that distributed knowledge graph architectures are well-studied, with proven patterns from PowerGraph (2012) to AWAPart (2022). Our design leverages computational approaches (vector similarity, streaming partitioning, graph metrics) rather than hand-coded knowledge, aligning with Sutton's Bitter Lesson. The path from single-shard to multi-shard is incremental, additive, and grounded in established distributed systems research.*
