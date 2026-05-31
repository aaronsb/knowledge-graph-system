# Freshness Architecture

How the platform keeps its **derived data** consistent with the graph it is
derived from — the catalog index, the grounding/polarity caches, and saved
artifacts. This is the "what and how" explainer; the decision record and its
rationale live in **ADR-207** (`docs/architecture/database-schema/`).

> **TL;DR.** There is **one universal monotonic tick** that advances on every
> graph mutation. Anything the platform computes *from* the graph stamps itself
> with the tick value it was built at, and re-checks that stamp against the
> current tick before it is trusted. The tick is maintained in application code
> (Apache AGE bypasses database triggers), so it is **eventually consistent** —
> it always converges, it is not transactionally instantaneous.

## The problem: derived data drifts

Several read surfaces are not primary state — they are **caches of a graph
computation**:

| Derivation | What it is | Where it lives |
|---|---|---|
| Catalog index | the ontology → document → concept browse tree | `kg_api.catalog_node` / `catalog_edge` |
| Grounding cache (per-concept) | each concept's grounding strength | in-memory, per API process |
| Grounding cache (polarity axis) | the shared polarity axis | in-memory, per API process |
| Artifacts | saved analyses / projections / results | PostgreSQL inline + Garage S3 |

Each is correct only as long as the graph it was computed from hasn't changed.
When the graph mutates and a derivation doesn't notice, it silently serves stale
data. Historically each derivation answered "am I stale?" its own way, against
different signals — some of them unsound. ADR-207 unifies that.

## The universal tick

> **One monotonic counter for every possible graph action. Sub-counters may
> exist for narrower scopes, but there is exactly one universal tick above them.**

Every derivation resolves freshness against this one signal — exposed as
`kg_api.get_committed_epoch()` and, in Python, the single helper
`api/app/lib/freshness.py:read_committed_epoch()`. A derivation is **fresh** when
the tick it was built at still equals the current tick (within its declared
[staleness budget](#staleness-budgets)).

### Why it lives in application code, not a trigger

The natural implementation would be a PostgreSQL trigger that bumps a sequence on
every write. **That does not work here, and it is the central constraint of this
whole design:** Apache AGE's Cypher operations manipulate the underlying label
tables through internal C functions that **bypass PostgreSQL's row-level trigger
mechanism entirely** (documented in migration 033). A trigger never fires for an
AGE mutation.

That is also why the legacy `graph_change_counter` is a recomputed `COUNT(*)`
checksum rather than a trigger counter — and why it is unsound as a freshness
signal: deleting one object and adding another leaves the sum unchanged, so two
different graph states can share a counter value (a derivation can read
*false-fresh*).

So the universal tick is advanced where the platform *can* see every mutation:
the application choke point `AGEClient.refresh_epoch()` →
`refresh_graph_metrics()`, which every mutation path is required to call,
"regardless of whether the caller is FUSE, CLI, curl, or the web UI."

### Eventual consistency — guaranteed convergence, not instant accuracy

Because the tick is advanced *out of band* from the AGE write (not inside the
same transaction), there is a brief window where it can lag the true graph state.
We accept that and guarantee **convergence** instead:

- **Periodic backstop.** The background `refresh_graph_metrics()` sync recomputes
  the snapshot and advances the tick on any detected change. So a count-changing
  mutation advances the tick within one interval *even if a mutation path forgot
  to signal it*. No mutation stays invisible forever.
- **Explicit signals for count-preserving mutations.** Some AGE mutations don't
  change object counts — annealing re-scopes an edge, a delete-plus-add nets to
  zero. A checksum can't see these (and neither could a trigger). Those paths
  **record an epoch event for their mutation kind**, which bumps the tick
  directly. (This is why recording epoch events for *all* mutation kinds — not
  just ingestion — is a prerequisite, tracked as #386.)

The practical contract for anyone writing graph-mutating code:

> **If you mutate the graph, call `refresh_epoch()` (or record an epoch event)
> when you're done.** Forgetting it doesn't corrupt anything — the periodic
> backstop will catch any count change — but it delays freshness until the next
> sync, and count-preserving changes won't be seen at all until you signal them.

### Sub-counters

Specialized invalidation scopes keep their own counters, **subordinate** to the
universal tick:

- `graph_accel.generation` — the `graph_accel` pgrx extension's own generation,
  advanced the same out-of-band way (`graph_accel_invalidate`). Same
  eventual-consistency nature; a sub-counter, not a competing clock.
- `vocabulary_change_counter` — vocabulary membership changes.
- `vocabulary_embedding_generation_counter` — vocabulary *embedding* regeneration
  (the polarity-axis cache keys on this; it changes far more rarely than the
  graph, so scoping it separately avoids needless axis recompute).

## The freshness contract

`api/app/lib/freshness.py` is where the four freshness questions — *built at what
version? / current version? / am I stale? / what do I do about it?* — are
answered once instead of per surface. Derivations come in two shapes (they are
genuinely different, so one interface would be a leaky fit):

```text
FreshnessContract                      shared: current_version() + staleness budget
├── CollectionDerivation               one stamp for the whole derivation
│     version_stamp() / is_fresh() / reconcile()     rebuild or invalidate the lot
│     e.g. catalog index, each grounding cache tier
└── InstanceDerivation                 per-row: each item has its own stamp
      version_stamp(id) / is_fresh(id) / reconcile(id)   regenerate one item
      e.g. artifacts
```

- **`current_version()`** always delegates to `read_committed_epoch()` — the one
  place the canonical-clock SQL lives, so no derivation can drift onto a
  different signal.
- **`is_fresh()`** is deferred and **on-read**: it re-reads the current tick every
  call. It must never short-circuit on a cached value without re-checking — that
  was the unbounded-staleness bug (#422).
- **`reconcile()`** brings the derivation back to current (rebuild / invalidate /
  regenerate), and is a no-op when already fresh.

Derivations **register** themselves (`@register_derivation`). Registration backs
two things: a **conformance test** (a new derivation that forgets the contract
fails CI, not production) and a uniform operator surface to list derivations,
show freshness, and trigger reconcile.

### Staleness budgets

A derivation declares how stale it may serve. The default is **strict** — it must
reflect the current tick. A derivation opts into tolerance explicitly (e.g. "may
be up to N versions behind"), making "fresh enough" a declared property rather
than emergent behavior.

## Adding a new materialized derivation

1. Subclass `CollectionDerivation` (whole-thing stamp) or `InstanceDerivation`
   (per-row stamp).
2. Implement `current_version()` via `read_committed_epoch()`, `version_stamp()`,
   and `reconcile()`. Inherit `is_fresh()`.
3. Declare a `name` and a `budget` (default strict).
4. Decorate with `@register_derivation`.
5. The conformance test (`tests/unit/lib/test_freshness_contract.py`) will hold
   you to the contract.

The catalog facade (`api/app/lib/catalog_facade.py`) is the **reference
implementation** — its deferred / on-read / serve-stale-under-lock rebuild is the
shape to copy.

## Reference implementation: the catalog index

The catalog index is the clearest worked example:

- **Stamp:** each `catalog_node` row stores the tick value (`graph_epoch`) the
  index was built at.
- **Compare/detect:** `ensure_fresh()` reads the current tick and the index's
  stamp on every browse.
- **Reconcile:** if the index lags, it rebuilds under a transaction-scoped
  advisory lock — one worker rebuilds, others serve the slightly-stale snapshot
  rather than blocking, and the single commit both publishes the new index and
  releases the lock.

## See also

- **ADR-207** — the decision record and rationale (canonical clock, contract
  shapes, alternatives considered).
- **ADR-203** — the graph epoch event log (logical-time / lifetime analytics; the
  "keep both" companion to the freshness tick).
- **ADR-079 / migration 033** — `graph_change_counter` and the AGE-bypasses-
  triggers constraint that shapes everything here.
- [STORAGE-ARCHITECTURE.md](STORAGE-ARCHITECTURE.md) — the PostgreSQL + Garage +
  AGE tiers the derivations live in.
