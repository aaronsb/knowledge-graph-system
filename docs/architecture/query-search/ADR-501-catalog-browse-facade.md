---
status: Proposed
date: 2026-05-30
deciders:
  - aaronsb
  - claude
related: [500, 700, 084, 085, 069, 200, 201, 233]
---

# ADR-501: Catalog Browse Facade

## Context

The knowledge graph has no first-class way to answer the simplest question a user
or reasoning agent can ask: **"what is actually in here?"**

Today, discovery is concept-first and search-first. You find concepts by semantic
similarity (`/query/search`), traverse relationships (`/query/related`), or run a
GraphProgram (ADR-500). All of these assume you already know roughly what you're
looking for. None of them let you *browse* the corpus the way you'd browse a
filesystem — start at the top, see what domains exist, drill into one, see its
documents, drill into a document, see its concepts.

This gap matters more now than it used to, for three reasons:

1. **The hierarchy became a living structure.** ADR-200's annealing worker is
   autonomously functional (`api/app/workers/annealing_worker.py`). Every cycle it
   scores ontologies, recomputes centroids, derives `OVERLAPS`/`SPECIALIZES`/
   `GENERALIZES` edges, and — in autonomous mode (migration 053, the default) —
   reorganizes the graph by merging, cleaving, dissolving, and renaming ontologies
   (ADR-206 verb vocabulary). The organizational structure of the graph now
   *changes on its own*. A user who hasn't looked in a week has no way to see what
   it looks like today.

2. **The hierarchy already exists as canonical graph edges.** ADR-200 promoted
   ontologies from a denormalized `Source.document` string to first-class
   `:Ontology` nodes with `:SCOPED_BY` edges (migration 044). The edges are
   canonical; `Source.document` is now a lagging cache. The browse hierarchy is
   therefore not new data — it is a **projection of edges the graph already
   maintains**:

   ```cypher
   (:Ontology)<-[:SCOPED_BY]-(:Source)           // ontology → its source chunks
   (:DocumentMeta)-[:HAS_SOURCE]->(:Source)       // document → its chunks (ADR-304)
   (:Concept)-[:APPEARS]->(:Source)               // concept ↔ where it appears
   ```

3. **Four client surfaces each reinvent listing.** CLI, MCP, web, and the FUSE
   driver (ADR-715) all need "list the children of X." Today each constructs its
   own queries: the CLI has `kg ontology list/files`, the web has bespoke
   `getSubgraph` composition, FUSE hand-builds `/query/*` calls in its readdir
   handlers. There is no shared catalog contract, so the four drift.

The `kg artifact` / `kg storage` usability work (issue #233) is a symptom of the
same root cause: without a browse surface, users can't tell what computed results
or source data the system holds, and the storage/artifact boundary reads as
confusing implementation detail.

### What this is NOT

This is **not** a new storage system, a new node type, or a new graph engine. It
is a read projection. It is also **not** the semantic-query path — it does not
replace ADR-500's set-algebra programs or vector search. Browse is deterministic,
cheap, and structural; search is probabilistic and expansion-oriented. Keeping the
two separate is a core decision here, not an accident.

### Adjacent work this composes with

- **ADR-700 (Ontology Explorer, Draft)** specifies the *web visualization* of this
  data — overview treemap, detail view with a searchable document list, bridge
  view. ADR-700's detail view is a **consumer** of this facade, not a competitor.
  This ADR provides the API substrate 700 currently lacks.
- **ADR-715 (FUSE, shipped)** already draws the deterministic path grammar
  `/ontology/<name>/documents/<file>`. Its stable half (ontology → documents) is
  exactly this catalog; its emergent half (query directories → concepts by
  similarity) stays as-is. The facade lets FUSE's readdir handlers become thin
  adapters over a shared contract.
- **ADR-201 (graph_accel)** is deliberately *not* the backing store here — see
  Alternatives.

## Decision

Introduce a **Catalog Browse Facade**: a single API-layer service that projects the
ontology → document → concept hierarchy as listable, paginated, sortable,
fragment-filterable nodes, consumed identically by CLI, MCP, web, and FUSE.

### 1. The `CatalogNode` DTO

A neutral, surface-agnostic shape — *not* the `WorkingGraph` of ADR-500. Browse
returns rows, not a graph.

```python
class CatalogNode(BaseModel):
    kind: Literal["ontology", "document", "concept"]
    id: str                       # stable identifier (ontology_id, document_id, concept_id)
    name: str                     # display label
    parent_id: Optional[str]      # for breadcrumb / tree assembly
    child_count: Optional[int]    # documents-in-ontology, concepts-in-document, etc.
    content_type: Optional[str]   # "document" | "image" | (future) "audio" | "video"
    properties: Dict[str, Any]    # kind-specific extras, opt-in via ?include=
    # storage/freshness extras surfaced only under verbose / explicit include:
    #   ontology: lifecycle_state, mass/coherence/protection scores (ADR-200)
    #   document: source_count, ingested_at, owner_id
    #   concept:  grounding strength, evidence count
```

Requirements imposed by FUSE (design for them up front): **stable `id`** (inode
mapping), **stat-able metadata** (size/content_type/mtime-or-epoch), and
**`child_count` without an N+1 query** (readdir must be one round-trip).

### 2. Browse endpoints

Two endpoints under a new `/catalog` router, both `read`-gated via
`get_current_active_user` and RBAC (ADR-400 baseline):

| Endpoint | Purpose |
|----------|---------|
| `GET /catalog/children` | List children of a node: `?parent=<id or ""root">&kind=<...>&q=<fragment>&sort=<field>&limit=&offset=` |
| `GET /catalog/node/{id}` | Single node with full properties (the `stat` / detail call) |

`parent=""` (root) returns the ontology level. The hierarchy is fixed-depth and
self-describing via `kind`, so a generic recursive client (FUSE, a tree widget)
needs no special-casing per level.

### 3. The terse selector grammar is sugar over the facade

A path selector — `ontology:foo / document:bar / concept:baz` — compiles to
`/catalog/children` calls, exactly as ADR-500 treats text DSL as compiling to its
JSON AST. The selector is a *navigation* convenience; it is not a graph program and
does not gain set-algebra operators. Where a user wants expansion, they hand the
catalog node's `id` to a GraphProgram as a seed. The seam stays explicit:

- **path selector → browse** (deterministic, structural, cheap)
- **graph program (ADR-500) → expansion** (set-algebra, semantic)

### 4. Canonical source: edges, never the string

The facade traverses `:Ontology` / `:SCOPED_BY` / `:HAS_SOURCE` / `:APPEARS`. It
**must not** read `Source.document` for membership — that string lags during
annealing reassignment (ADR-200). This is a permanent design constraint, not a
migration artifact.

### 5. Filtering: three named tiers, only the first in scope now

| Tier | Mechanism | Scope |
|------|-----------|-------|
| **Fragment** ("type a few chars") | Postgres `pg_trgm` / `ILIKE` on labels + names | **This ADR** — makes listings feel instant, no embeddings |
| **Semantic** | reuse existing cosine (concept embeddings in AGE; source embeddings in `kg_api.source_embeddings`) | reuse existing endpoints; wire as a filter mode later |
| **BM25 / full-text** | Postgres `tsvector` / `ts_rank` (net-new — no FTS index exists today) | **Deferred** to a follow-on ADR; flagged, not silently dropped |

### 6. Single insertion point: the Python API facade

The only layer all four clients share is the API. The facade lands as
`api/app/lib/catalog_facade.py` (composition over existing graph/query facades) +
`api/app/routes/catalog.py` (thin handler). Each client then gets a thin wrapper —
this per-endpoint "client tax" (~4 parallel changes: TS client method, CLI command,
MCP tool action, web client method, FUSE handler) is irreducible given the current
architecture (ADR-707 unified only CLI+MCP; web and FUSE remain separate), but a
thin facade minimizes it. A small Postgres-side property/count index (refreshed on
graph epoch bump, ADR-203) backs fast `child_count` and fragment filtering without
per-request graph aggregation.

## Consequences

### Positive

- **Answers "what's in here?"** for humans and reasoning agents — browse by
  document/ontology, not only by concept or similarity.
- **Makes the autonomous graph observable.** Annealing reshapes the hierarchy
  (ADR-200/206); the catalog is how a returning user sees the current shape.
- **Closes issue #233.** Storage location (inline/Garage) becomes an opt-in
  `properties` field; freshness/regenerate/cleanup become node-level concerns;
  `kg storage` (raw S3 admin) vs `kg artifact`/catalog (semantic) boundary becomes
  legible because the catalog shows *meaning*, not buckets.
- **Turns FUSE's stable half into a thin adapter** over a shared contract instead
  of bespoke readdir queries (ADR-715).
- **Gives ADR-700 its missing substrate** — the Ontology Explorer detail view
  consumes `/catalog/children` rather than inventing its own listing path.
- **One contract, four surfaces** — reduces the existing drift between CLI/MCP/web/
  FUSE listing logic.

### Negative

- **The four-client tax is real.** Even with a shared API facade, each surface
  needs a wrapper. This ADR minimizes but does not eliminate it.
- **A second read index to keep fresh.** The property/count index must invalidate
  on epoch bump; a missed invalidation shows stale counts (bounded, not
  corrupting — counts, not truth).
- **`child_count` at scale** needs the index; naive aggregation per readdir would
  be O(children) graph queries. The index is therefore not optional for FUSE.

### Neutral

- Browse and search remain deliberately separate code paths. Users wanting
  semantic results still use ADR-500 / vector search; the catalog seeds them.
- Media-type awareness (`content_type`) is carried through but the catalog does not
  itself render or transcode media; it only lists and describes.

## Alternatives Considered

### Back the catalog with graph_accel (ADR-201)

Rejected. `graph_accel` is verified to hold **Concept topology only** — node IDs +
edges + one app-id property, no ontology/document membership, no node properties, no
substring index, no counts (`graph-accel/core/src/graph.rs`). A catalog needs
exactly the opposite profile: property-rich, count-aware, fragment-searchable
listing. graph_accel stays for traversal-heavy expansion (neighborhood,
pathfinding); a catalog node action *may* hand off to it, but it cannot back the
listing.

### Extend the ADR-500 DSL with a tree/listing operator

Rejected. The DSL's value is a closed set-algebra (`+ − & ? !`) over concept sets
returning a `WorkingGraph`. A folder listing is a different shape (ordered,
paginated, parent/child rows) and coercing it into WorkingGraph would either
distort the DSL's invariants or produce an awkward hybrid. Browse rides as
`ApiOp`-style endpoints the DSL *can seed from*, not as a new operator.

### Fold this into ADR-700 (Ontology Explorer)

Rejected. ADR-700 is a web-explorer visualization spec. Merging a cross-cutting,
four-surface API contract into a single-surface viz ADR would couple the API's
lifecycle to the web UI's and hide the contract from CLI/MCP/FUSE readers. Keeping
the facade as its own ADR lets 700 (and 069, and the CLI) cite it as a dependency.

### Read `Source.document` for membership

Rejected. It is a denormalized cache that lags during annealing reassignment
(ADR-200). Canonical membership is the `:SCOPED_BY` edge.

### Ship all three filter tiers at once

Rejected for the first cut. Fragment match (pg_trgm) delivers the "instant
listing" feel with no new infrastructure. BM25 requires a net-new full-text index
(none exists today) and would balloon scope. It is explicitly deferred to a
follow-on ADR rather than silently omitted.
