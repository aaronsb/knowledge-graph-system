---
status: Accepted
date: 2026-05-31
deciders:
  - aaronsb
  - claude
related:
  - ADR-079
  - ADR-201
  - ADR-203
  - ADR-083
  - ADR-079
  - ADR-080
  - ADR-801
  - ADR-802
---

# ADR-207: A Uniform Freshness Contract for Materialized Graph Derivations

## Status note

This ADR both **names** the problem (grounding it in the materialized-view /
bounded-staleness literature) and **decides** the architecture to resolve it.
The [Context](#context) and [Problem statement](#problem-statement) establish
the class of problem; the [Decision](#decision) commits to a uniform freshness
contract over a single trustworthy clock; the [Execution plan](#execution-plan)
sequences it as a coherent series of changes. It is executable as written — the
[Alternatives considered](#alternatives-considered) record why the rejected
clocks were rejected on the merits, not deferred.

## Context

### The system quietly grew three materialized derivations of the graph

Several read-heavy surfaces in the platform are not primary state — they are
**caches of a graph computation**, persisted in some tier and expected to track
the graph as it mutates. At least four exist today (the grounding row below is
itself two cache tiers — see [Scope / inventory](#scope--inventory)), each built
independently at a different time, for a different subsystem:

| Derivation | Storage tier | Version signal it reads | Tracking issue |
|---|---|---|---|
| Grounding / polarity scores | in-memory cache | `graph_accel.generation` (ADR-201) | #422 |
| Artifacts (analyses, projections, saved results) | PostgreSQL inline / Garage S3 | `graph_change_counter` via `get_graph_epoch()` (ADR-079) | #233 |
| Catalog index (`kg_api.catalog_node`) | materialized table | `graph_change_counter` via `get_graph_epoch()` (ADR-079) | — |

Each independently re-implements the same four-part lifecycle:

1. **Stamp** — record which graph version the derivation was computed from.
2. **Compare** — read the current graph version and diff it against the stamp.
3. **Detect** — decide, *on the read path*, whether the derivation is stale.
4. **Reconcile** — act on staleness: rebuild, regenerate, invalidate, or
   serve-stale-with-a-signal.

They do not agree on how — or whether — they perform each step:

- **Catalog index** does all four correctly. It stamps `graph_epoch` per row,
  `CatalogFacade.ensure_fresh()` re-reads the current epoch on every read,
  rebuilds under a lock, and serves the older snapshot gracefully when another
  worker holds the rebuild lock (migration 073). *It is the de-facto reference
  implementation of the pattern.*
- **Artifacts** stamp (`artifacts.graph_epoch`) and compare (`is_fresh`), but
  **step 4 is not exposed to users** — `POST /artifacts/{id}/regenerate` exists
  in the API yet has no CLI/MCP surface, and cleanup runs only as an automatic
  worker. The storage tier (inline vs Garage) also leaks into the user view.
  (#233)
- **Grounding cache** stamps and compares, but **skips the compare on the warm
  path** — the Phase-0 short-circuit returns without re-reading
  `graph_accel.generation`, so staleness is unbounded in wall-clock time. (#422)

### Three version signals, none of them a shared clock

The comparisons above are not even measured against the same clock:

| Signal | Defined | Nature |
|---|---|---|
| `graph_change_counter` (`get_graph_epoch()`) | ADR-079, migration 033 | composite **count checksum** of graph objects |
| `graph_accel.generation` | ADR-201, migration 051 | separate invalidation counter for the in-memory layer |
| `kg_api.graph_epochs` event log | ADR-203, migration 063 | monotonic mutation event log, *explicitly "distinct from `graph_change_counter`"* |

Two soundness gaps fall out of this, both already documented in our own ADRs:

1. **The counter is non-injective over time.** ADR-203 proves it: "Delete a
   concept and add one — the counter is unchanged... `counter_value →
   wall_clock_time` is not a function." Any derivation whose freshness test is
   `stamp == get_graph_epoch()` can therefore read **false-FRESH** — a stale
   derivation passing as current because the count happened to return to a prior
   value. In-place edits and compensating mutations (delete+add) are invisible
   to it.
2. **Independently-maintained derivations produce inconsistent snapshots.** This
   is a named hazard in the materialized-view literature: multiple views
   refreshed against different signals, read concurrently, reflect *different
   points in time*. With three derivations on (up to) three clocks, a single
   request can compose grounding scores, an artifact, and a catalog listing that
   each describe a different graph state.

And the clock that *is* monotonic and honest — the epoch event log (ADR-203) —
**cannot yet distinguish a committed mutation from a failed attempt** (#384): a
job that aborts mid-extraction still leaves an epoch row, polluting the very
signal a freshness contract would want to trust.

### We are not the first to hit this

This is a well-trodden class of problem. Naming it in the field's terms lets us
borrow solutions instead of inventing them:

- **Materialized view maintenance.** Our three derivations *are* materialized
  views of the graph. The literature's staleness states (FRESH / STALE), its
  **immediate vs deferred maintenance** distinction (update in the writing
  transaction, vs. on-read / on-command / periodic), and its **incremental view
  maintenance (IVM) vs full recompute** trade-off map directly onto our
  reconcile step. The catalog index does *deferred, on-read, full-recompute*
  maintenance; the grounding cache attempts deferred maintenance but skips the
  detect step.
- **Bounded staleness** (a consistency model). #422 is precisely an
  *unbounded-staleness* defect: the warm path bounds staleness by neither
  versions nor wall-clock. Probabilistically Bounded Staleness (PBS) formalizes
  bounds along both axes — the vocabulary for what "fresh enough" should mean
  per surface.
- **Cache invalidation / coherence.** The single-writer + monotonic-versioning
  framing from coherence protocols is the lens on our three-clocks problem: a
  derivation is coherent only against a version signal that monotonically and
  injectively reflects committed writes — which `graph_change_counter` does not.

### Structural precedent inside this repo

This shares its *motivation* with the provider work — not its difficulty. Vision
was a **parallel provider hierarchy** that duplicated the extraction hierarchy
(#379); ADR-801 defined a uniform provider contract and ADR-802 collapsed vision
onto it. Each derivation here is likewise a **parallel freshness hierarchy** —
its own stamp, its own clock, its own ad-hoc reconcile — and the remedy rhymes:
one contract, one trustworthy signal, existing implementations brought onto it.
But the provider collapse unified objects that were *already the same kind of
thing* behind one call signature, whereas these derivations are genuinely
**heterogeneous in tier and cardinality** (per-process in-memory dict vs.
per-row persisted blob vs. materialized relational table). The shared *motive*
holds; do not expect the same clean collapse — which is exactly why D3 is a small
hierarchy, not one interface.

### Scope / inventory

The contract governs **graph-topology-derived, server-maintained read surfaces**.
By that rule the inventory is:

- **Catalog index** (`catalog_node`) — collection-level. *Reference implementation.*
- **Grounding cache, per-concept tier** — collection-level; keyed on the graph
  generation. (#422)
- **Grounding cache, polarity-axis tier** — collection-level but keyed on the
  **vocabulary-embedding generation**, not the graph epoch; it changes only on
  embedding regeneration, so it is registered and invalidated separately.
- **Artifacts** — instance-level (per-row, user-parameterized). (#233)
- **`graph_accel` in-memory generation layer** — in scope *in principle* (it is a
  materialized derivation) but its version signal is internal to the Rust
  extension; brought under the contract or proven to co-advance as a separable
  follow-up, not in the first pass.

Deliberately **excluded**: caches not derived from graph topology — e.g. the
model catalog (provider/model metadata) — which have their own invalidation
lifecycles and no graph-epoch relationship.

## Problem statement

> The platform maintains multiple materialized derivations of the graph
> (grounding cache, artifacts, catalog index), but has **no uniform contract for
> derived-state freshness**. Each derivation answers "am I current, and what
> happens when I'm not?" ad-hoc — against version signals that are not the same
> clock, at least one of which (`graph_change_counter`) is non-injective and can
> report false-FRESH, on top of an epoch log that cannot yet tell a committed
> mutation from a failed attempt. The result is silent staleness (#422),
> unexposed reconciliation (#233), and the latent risk of composing a single
> response from derivations that each describe a different graph state.

## Decision

Adopt a **single uniform freshness contract** for every materialized graph
derivation, resolved against **one canonical logical clock**, with the catalog
facade's deferred / on-read / serve-stale-under-lock behavior as the reference
shape. Three concrete decisions:

### D1 — The canonical clock is the epoch event sequence: one monotonic tick for all graph actions

The freshness clock is **`kg_api.graph_epochs.event_id`** — a `BIGSERIAL`,
monotonic, one row per graph mutation event. This *is* the "one universal tick
for all graph actions": every action that records an epoch event advances it.
Derivations resolve freshness against it via `kg_api.get_committed_epoch()`,
which reads it through a **committed-prefix watermark** so in-flight and
out-of-order jobs cannot expose a half-applied state (see D1a). Sub-counters
exist for narrower scopes, but this one sequence is above them all.

**Why an event-recorded sequence, not a trigger counter.** A PostgreSQL trigger
that bumps a sequence on every write would be the obvious choice, but it does not
work here, and migration 033 documents why: *Apache AGE's Cypher operations
bypass PostgreSQL's trigger mechanism entirely* (AGE manipulates label tables via
internal C functions that fire no row-level triggers). That is also why the
legacy `graph_change_counter` is a recomputed `COUNT(*)` checksum — and why it is
non-injective (ADR-203: delete one + add one leaves the sum unchanged), hence
unusable as a freshness signal. Since neither a trigger nor a checksum works, the
tick is advanced where the platform *can* see every mutation: **application code
records an epoch event when it commits a graph mutation.**

**This makes #386 a hard prerequisite, and it is the entire convergence story.**
Today `record_epoch()` is called only by the ingestion worker, so the tick
advances on ingestion alone — edits and annealing record nothing and are
invisible to the clock. There is no `COUNT`-checksum backstop that rescues this:
`refresh_graph_metrics()` recomputes counts but never writes an epoch event, so
it cannot advance this clock. The *only* mechanism that makes the tick universal
is **#386 — record an epoch event for every mutation kind**. Until #386 lands, a
derivation on this clock is correct for ingestion and blind to everything else.
The honest guarantee is therefore: **freshness converges for every mutation kind
that records an event; #386 is what extends that set to all of them.**

**Annealing is the concrete gap (and the co-advance fix).** The annealing path
today calls *neither* `record_epoch()` *nor* `graph_accel_invalidate()` — so it
is invisible to both this clock and the in-memory accelerator. The fix is a
single application-side mutation-completion helper that does both on every
mutating path:

```text
on graph mutation commit:
    record_epoch(kind, ...)      # advances the universal tick (event_id)
    graph_accel.invalidate()     # advances the graph_accel sub-counter + pg_notify
```

Calling both from one place means `event_id` and `graph_accel.generation`
**co-advance by construction** — no separate "prove co-advance" obligation. This
is application wiring (the substance of #386); the `graph_accel` extension needs
**no change** — its `DESIGN.md` deliberately limits it to writing only its own
`generation` table, and recording our epoch events there would violate that
boundary.

**Sub-counters stay subordinate.** `graph_accel.generation`,
`vocabulary_change_counter`, and `vocabulary_embedding_generation_counter` remain
for their narrower invalidation scopes (e.g. the polarity-axis tier keys on the
vocab-embedding counter, which changes far more rarely than the graph). The one
`event_id` tick is above them; they do not substitute for it.

**`graph_change_counter` is demoted, not deleted.** The `COUNT` checksum keeps
its statistics role and is a legitimate cheap *dirty-hint* (`counter != last`
reliably means "something changed"), but it is **never** the freshness stamp —
`counter == stamp` is meaningless (non-injective). Freshness reads the tick.

**Keep both: the same sequence serves freshness and analytics.** `graph_epochs`
is read two ways. Freshness reads the committed-prefix watermark over `event_id`
(D1a). Analytics/lifetime (ADR-203) reads the richer event rows — `kind`,
`actor`, `occurred_at`, and the `#384` `status`. These are not two clocks that
can skew; they are two read patterns over one table.

**`graph_epoch` stamp columns are typed `BIGINT`** to match `event_id` — the
existing `INTEGER` columns (`artifacts.graph_epoch`, `catalog_node.graph_epoch`)
and the relevant accessor return types are widened as part of this work.

### D1a — The watermark: reading the tick safely

Epoch rows are inserted at job **start** (ADR-203, so the `event_id` can tag
nodes created during the run), while a job *commits* at its end, and jobs
complete **out of order**. So the raw `MAX(event_id)` — or `MAX(event_id WHERE
status='completed')` — is not a safe cursor: it could expose a later job's id
while an earlier job is still committing. `get_committed_epoch()` returns the
**contiguous committed prefix** instead:

```text
get_committed_epoch() := MIN(event_id WHERE status='in_progress') - 1
                         if any job is in flight, else MAX(event_id)
```

Both `completed` and `failed` count toward it; only `in_progress` blocks it —
because ingestion commits **per-chunk**, so a failed/cancelled job may have
already committed partial changes, and excluding it would read false-FRESH. The
`status` column (#384) is what makes this possible; resolving the epoch on every
exit path (success/cancel/exception) is what keeps a crashed job from freezing
the watermark behind a phantom in-flight event. (Built and verified in step 1.)

**Staleness bound (review S3).** Because the watermark holds at
`MIN(in_flight) - 1`, a mutation committed *while a longer job is in flight* is
not reflected until that job resolves. So the bound on detection latency is **the
duration of the longest concurrent in-flight job**, not wall-clock. This is the
deliberate price of the contiguous-prefix guarantee (no half-applied state ever
shows as fresh), and it is acceptable because the dominant in-flight job is
ingestion, after which a rebuild was going to happen anyway. An atomic edit's own
`record_mutation` records a *completed* event, so in the common case (no long job
running) it advances the tick immediately. The brief two-phase window inside
`record_mutation` itself (record → complete) only *holds* the watermark at its
prior value, never regresses it (S2), so it cannot surface stale-as-fresh — at
worst a derivation rebuilt inside that window re-checks once the event completes.

### D2 — Mandatory maintenance discipline: deferred, on-read, bounded

- **Deferred / on-read detection is the floor.** Every derivation re-reads the
  canonical clock on the read path before serving. **No warm-path short-circuit
  may skip the compare** — this is the contract clause that #422 violates.
- **Each derivation declares an explicit staleness budget.** Default is
  **strict** (0 versions / 0 ms — never serve stale). A derivation opts into
  tolerance explicitly (`stale_ok_versions: N` / `stale_ok_ms: T`), making
  "fresh enough" a declared property rather than emergent behavior. (Vocabulary:
  bounded staleness / PBS.)
- **Reconcile strategy is per-derivation, full-recompute by default.**
  Incremental view maintenance (IVM) is permitted where a derivation supports it
  but is explicitly **out of scope** for the initial contract — the catalog
  index's full rebuild is the baseline all three adopt first.

### D3 — A small contract hierarchy: collection- vs instance-level derivations

A *single* interface does not honestly fit the surfaces (architectural review,
PR #462): a materialized table or in-memory cache is **collection-level** (one
stamp for the whole derivation, reconcile = rebuild/invalidate the lot), whereas
an artifact is **instance-level** (each row carries its own stamp and reconciles
— regenerate — independently, against its own stored parameters). Forcing both
behind one `version_stamp() -> int` is an ISP/LSP leak. So the contract is a
shared base specialized into two shapes:

```text
FreshnessContract (shared):
    current_version() -> int        # get_committed_epoch()
    staleness_budget -> Budget      # declared; default strict (0 versions / 0 ms)

CollectionDerivation(FreshnessContract):   # catalog index, each grounding cache tier
    version_stamp() -> int          # the clock value the whole derivation was built at
    is_fresh() -> bool              # deferred, on-read; honors the budget
    reconcile() -> None             # rebuild | invalidate (whole derivation)

InstanceDerivation(FreshnessContract):     # artifacts
    version_stamp(id) -> int        # per-row stamp
    is_fresh(id) -> bool            # deferred, on-read, per row
    reconcile(id) -> None           # regenerate one instance from its stored parameters
```

The grounding cache is **not one derivation** — it is (at least) two registered
`CollectionDerivation`s on two different signals: the per-concept grounding tier
and the polarity-axis tier, the latter keyed on the vocabulary-embedding
generation rather than the graph epoch (see [inventory](#scope--inventory)).
Registering them separately keeps each one's invalidation honest rather than
over-invalidating the rarely-changing axis on every graph mutation.

Derivations **register** themselves, which buys two things:

1. A **conformance test** asserting every registered derivation implements its
   contract and pins the comparison semantics (strict `==` on the monotonic
   clock — *not* the catalog's legacy `>=`, which only existed to tolerate the
   regressing counter). This is the freshness analogue of `docstring_coverage` /
   `lint_queries`: a *new* derivation that forgets on-read detection fails CI,
   not production.
2. A **uniform reconcile surface** across CLI/MCP/operator: list derivations,
   show freshness, trigger reconcile. This subsumes #233's regenerate/cleanup
   exposure and storage-tier-hiding items as fallout of conformance rather than
   as bespoke artifact work.

## Execution plan

**Clean-rebuild assumption.** The platform carries no production data that must
be preserved: it is wiped and re-initialized as part of landing this. That
removes the riskiest piece a freshness-clock change would normally carry — there
is **no back-fill and no migration machinery** to map old stamps (a different
number space) onto the new clock, and **no rollback-of-data hazard**. Columns are
simply defined `BIGINT` from the reset forward; every derivation builds fresh
against the tick on first read. (If the platform ever holds data worth
preserving, this execution section must be revisited.)

Given that, this is one body of work, best delivered as a single PR whose commits
read in order as a coherent narrative. Only one ordering constraint is
load-bearing: **the tick must advance on every mutation kind before any
derivation reads it** — otherwise a derivation goes blind to the kinds that don't
yet record an event.

1. **Make the clock trustworthy (built, step 1) and universal (#386).** The
   `status` column, the committed-prefix `get_committed_epoch()` watermark over
   `event_id`, `complete_epoch()` wiring, and the `BIGINT` widening are done and
   verified (**#384**). The remaining, load-bearing piece is **#386 — record an
   epoch event for every mutation kind, not just ingestion**, via one
   mutation-completion helper that records the event *and* calls
   `graph_accel.invalidate()` (so the tick and the `graph_accel` sub-counter
   co-advance). Its concrete first target is the **annealing path, which today
   records nothing**. Until #386 lands, derivations on the clock see ingestion
   only — so it gates step 2's catalog migration in practice even though step 1's
   plumbing is already in place.
2. **Establish the contract against the surface that already obeys it.** Define
   the `FreshnessContract` base + the two specializations + registry +
   conformance test, then bring the **catalog facade** on first — it already
   behaves correctly, so it is the lowest-risk way to prove the interface is
   right before reshaping anything that isn't.
3. **Bring the misbehaving derivations into conformance.** The two grounding
   cache tiers gain on-read re-reads and declared staleness budgets, registered
   separately (**#422**); artifacts implement `InstanceDerivation`, expose
   `reconcile` via CLI/MCP, and hide the storage tier behind `--verbose`
   (**#233**).
4. **Follow-up, separable:** formalize `graph_accel.generation` as a declared
   sub-counter under the tick (prove co-advance), and revisit IVM where it is
   cheap. This can trail in its own PR without holding up the rest.

The commits stand on their own in review — the clock fix is a correctness fix,
the contract is an abstraction with a test, each conformance step closes a
standing issue — while together they tell the single story this ADR names.

## Consequences

- **Positive:** silent-staleness defects become **contract violations the
  conformance test catches**, not production incidents; the false-FRESH class is
  eliminated at the root (D1's watermark); new derivations inherit correct
  freshness behavior by implementing the contract for their cardinality;
  cross-surface snapshot skew becomes a declared, reasoned property (D2) rather
  than an accident of which clock a subsystem happened to read.
- **Cost:** touches the grounding, artifact, and catalog subsystems plus a
  schema-level clock change; **the clock-trustworthiness work (#384) must land
  first**. The data-migration cost is avoided only by the clean-rebuild
  assumption above — it is a real, unsolved cost the moment the platform holds
  data worth preserving.
- **Risk accepted:** IVM is deferred — derivations full-recompute on staleness,
  which is correct but not always cheapest. Acceptable: correctness first, the
  contract *permits* IVM later without re-litigation.
- **Risk if not done:** each new materialized derivation adds another parallel
  freshness hierarchy on an unsound signal — the drift this ADR names compounds.

## Alternatives considered

- **A PostgreSQL trigger bumping a monotonic sequence on every write.** Infeasible
  here: AGE Cypher bypasses row-level triggers (migration 033), which is the whole
  reason `graph_change_counter` is a recomputed checksum. The clock instead
  advances by application code recording an epoch event on each mutation — the
  only layer that reliably sees AGE mutations.
- **A standalone monotonic counter advanced in `refresh_graph_metrics()`** (a
  draft of this ADR proposed exactly this). Rejected because it does not actually
  work: `refresh_graph_metrics()` recomputes a `COUNT(*)` checksum, which is
  non-injective (misses count-preserving annealing) and so cannot be a sound
  monotonic tick; and it would be a *second* clock alongside `event_id`. The
  `graph_epochs.event_id` sequence already *is* the monotonic tick we need — once
  #386 records an event for every mutation kind. No separate counter buys
  anything.
- **Use `graph_accel.generation` as the canonical clock.** It is monotonic and
  already advances on some mutations, so it is a genuine contender. Rejected as
  *primary* because: it is internal to the pgrx extension (whose `DESIGN.md`
  scopes it to in-memory acceleration), it falls back to a vocab-only counter when
  the extension isn't loaded on a connection, and — like `event_id` today — it is
  not advanced by the annealing path either. It earns its place as a **sub-counter
  that co-advances with `event_id`** (both bumped by the one mutation-completion
  helper), not as the system clock.
- **Two co-equal, fully-synchronous clocks.** Rejected: synchronous accuracy is
  unattainable against AGE's trigger-bypass, and two co-equal clocks reintroduce
  snapshot skew.
- **Per-surface freshness with no shared contract (status quo).** Rejected: it
  is precisely the parallel-hierarchy drift this ADR exists to stop — the same
  anti-pattern ADR-802 collapsed for providers.
- **Immediate (in-transaction) maintenance instead of deferred/on-read.**
  Rejected for the initial contract: it couples every graph mutation to the cost
  of refreshing all derivations and does not fit the artifact/Garage tier at all.
  Deferred on-read matches the catalog facade's proven model.

## Implementing / related issues

- **#384** — `graph_epochs.status` (committed vs failed): analytics signal +
  part of the clock foundation (D1).
- **#386** — record epoch events for annealing/reasoning/edit kinds, **and bump
  the universal tick for them**: a *prerequisite* (D1). Without it the tick only
  advances on ingestion and derivations go blind to count-preserving mutations.
- **#422** — grounding-cache unbounded warm-path staleness: the on-read
  detection defect the contract forbids (D2).
- **#233** — artifact lifecycle exposure + storage-tier transparency: the
  reconcile-surface gap the uniform interface subsumes (D3).
- Catalog facade (migration 073) — prior art / reference implementation.

## References

External grounding (problem-naming, not prescriptions):

- Incremental View Maintenance — PostgreSQL wiki:
  https://wiki.postgresql.org/wiki/Incremental_View_Maintenance
- "Everything You Need to Know About Incremental View Maintenance":
  https://materializedview.io/p/everything-to-know-incremental-view-maintenance
- "Probabilistically Bounded Staleness for Practical Partial Quorums" (PBS):
  https://arxiv.org/pdf/1204.6082
- Cache coherence (overview): https://en.wikipedia.org/wiki/Cache_coherence
