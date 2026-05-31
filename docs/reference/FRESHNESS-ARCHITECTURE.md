# Freshness Architecture

How the platform keeps its **derived data** consistent with the graph it is
derived from — the catalog index, the grounding/polarity caches, and saved
artifacts. This is the "what and how" explainer; the decision record and its
rationale live in **ADR-207** (`docs/architecture/database-schema/`).

> **TL;DR.** There is **one universal monotonic tick** for all graph actions —
> the `graph_epochs.event_id` sequence. Anything the platform computes *from* the
> graph stamps itself with the tick value it was built at, and re-checks that
> stamp against the current tick before it is trusted. The tick advances when
> application code **records an epoch event** for a mutation (Apache AGE bypasses
> database triggers, so a trigger-driven counter is impossible). It is **eventually
> consistent**: freshness converges for every mutation *kind that records an
> event*. Today that is ingestion; extending it to edits and annealing is the work
> tracked as #386.

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

> **One monotonic counter for every possible graph action — the
> `kg_api.graph_epochs.event_id` sequence. Sub-counters may exist for narrower
> scopes, but there is exactly one universal tick above them.**

`event_id` is a `BIGSERIAL`: one row per graph mutation event, monotonically
increasing. That sequence *is* the universal tick — every action that records an
event advances it. Every derivation resolves freshness against it through
`kg_api.get_committed_epoch()` (in Python, the single helper
`api/app/lib/freshness.py:read_committed_epoch()`), which reads the sequence via a
[committed-prefix watermark](#reading-the-tick-safely-the-watermark) so an
in-flight or out-of-order job can't expose a half-applied state. A derivation is
**fresh** when the tick it was built at still equals the current tick (within its
declared [staleness budget](#staleness-budgets)).

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

So the tick is advanced where the platform *can* see every mutation: **application
code records an epoch event when it commits a graph mutation.** `event_id` is the
one signal that fires for the exact set of mutations the application chooses to
announce — which is why making that set *complete* is the whole game (see below).

### Eventual consistency — convergence per recorded event-kind

Because the event is recorded *out of band* from the AGE write (not inside one
trigger), there is a brief window where the tick can lag the true graph state. We
accept that and guarantee **convergence** — but be precise about its scope:

> **Freshness converges for every mutation *kind* that records an epoch event.
> It is blind to kinds that record none.**

Today only the **ingestion** path records events, so the clock is correct for
ingestion and blind to edits and annealing. There is **no `COUNT`-checksum
backstop** that rescues this: `refresh_graph_metrics()` recomputes object counts
for statistics, but it never writes an epoch event, so it cannot advance this
clock. The only thing that makes the tick universal is **#386 — record an event
for every mutation kind.**

The concrete gap #386 closes: the **annealing path today records nothing** — it
calls neither `record_epoch()` nor `graph_accel_invalidate()`, so after annealing
re-scopes the graph, *both* the freshness clock and the in-memory accelerator are
silently stale. The fix is a single mutation-completion helper that every
mutating path calls:

```text
on graph mutation commit:
    record_epoch(kind, ...)      # advances the universal tick (event_id)
    graph_accel.invalidate()     # advances the graph_accel sub-counter + pg_notify
```

Recording both from one place means `event_id` and `graph_accel.generation`
**co-advance by construction**. The practical contract for anyone writing
graph-mutating code:

> **If you mutate the graph, record an epoch event (via the mutation-completion
> helper) when you commit.** A path that forgets doesn't corrupt anything, but its
> mutations are *invisible to freshness* — derivations will serve stale data for
> that kind until someone wires it in. There is no background sweep that covers
> for you.

### Reading the tick safely (the watermark)

`get_committed_epoch()` does not return the raw `MAX(event_id)`. Epoch rows are
inserted at a job's **start** (so the `event_id` can tag the nodes it creates),
the job commits at its **end**, and jobs finish **out of order** — a long
ingestion at id 6 can still be running when a short one at id 7 commits. So the
clock returns the **contiguous committed prefix**:

```text
get_committed_epoch() := MIN(event_id WHERE status='in_progress') - 1
                         if any job is in flight, else MAX(event_id)
```

An in-flight job at id N holds the clock at N-1, so derivations correctly read
stale until it lands. Both `completed` and `failed` events count (only
`in_progress` blocks) because ingestion commits **per-chunk** — a failed job may
have committed partial changes, and ignoring it would read false-fresh. The
`status` column makes this work, and a job must resolve its event on **every**
exit (success/cancel/exception) or it would freeze the clock behind a phantom
in-flight event.

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
