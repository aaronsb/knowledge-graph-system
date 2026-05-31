---
status: Proposed
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
the graph as it mutates. Three exist today, each built independently at a
different time, for a different subsystem:

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

This is the same *shape* of problem the provider work just resolved. Vision was
a **parallel provider hierarchy** that duplicated the extraction hierarchy
(#379); ADR-801 defined a uniform provider contract and ADR-802 collapsed vision
onto it. Here, each derivation is a **parallel freshness hierarchy** — its own
stamp, its own clock, its own ad-hoc reconcile. The remedy rhymes: one contract,
one trustworthy signal, existing implementations migrated onto it.

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

### D1 — The canonical clock is the ADR-203 epoch event-log sequence

`kg_api.graph_epochs.event_id` is `BIGSERIAL PRIMARY KEY` — **monotonic and
unique by construction**, therefore injective in both directions: a stored stamp
equal to the current value *proves* freshness, and an unequal stamp *proves*
staleness. This is the property cache coherence requires of a version signal and
the property `graph_change_counter` provably lacks.

The contract resolves freshness against a **commit-gated accessor** over this
sequence:

```sql
-- returns the highest event_id whose mutation actually committed
kg_api.get_committed_epoch() := MAX(event_id) WHERE status = 'completed'
```

This makes **#384 (epoch `status` column) a hard prerequisite** — without it the
sequence reflects *attempts*, not *commits*, and a derivation could stamp itself
against a mutation that rolled back.

**`graph_change_counter` is demoted, not deleted.** It remains a sound
*one-directional dirty hint* — `counter != stamp` reliably means "changed", so
it is a legal cheap fast-path to *prove staleness* — but it is **never trusted
to prove freshness** (its non-injectivity, per ADR-203, makes `counter == stamp`
meaningless). Existing `graph_epoch` columns that today store the counter are
migrated to store the committed event-log sequence.

**`graph_accel.generation`** is the in-memory acceleration layer's *own*
invalidation signal, internal to the `graph_accel` extension — itself a
materialized derivation. It is not a competing system clock; it is brought under
the same contract (Phase 4), resolving against `get_committed_epoch()` or proven
to co-advance with it.

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

### D3 — One uniform surface: a `MaterializedDerivation` contract + registry

Every derivation implements a single interface (Python ABC / Protocol), so the
four steps stop being re-implemented per surface:

```
MaterializedDerivation:
    version_stamp() -> int          # the clock value this derivation was built at
    current_version() -> int        # get_committed_epoch()
    is_fresh() -> bool              # deferred, on-read; honors the staleness budget
    reconcile(strategy) -> None     # rebuild | regenerate | invalidate
    staleness_budget -> Budget      # declared; default strict
```

Derivations **register** themselves, which buys two things:

1. A **conformance test** asserting every registered derivation implements the
   contract (the freshness analogue of `docstring_coverage` / `lint_queries`) —
   so a *new* derivation that forgets on-read detection fails CI, not production.
2. A **uniform reconcile surface** across CLI/MCP/operator: list derivations,
   show freshness, trigger reconcile. This subsumes #233's regenerate/cleanup
   exposure and storage-tier-hiding items as fallout of conformance rather than
   as bespoke artifact work.

## Execution plan

This is one body of work, best delivered as a single PR whose commits read in
order as a coherent narrative — not a multi-phase project. Only one ordering
constraint is load-bearing: **the clock must be made trustworthy before any
derivation migrates onto it**, or we re-stamp everything against sand. Beyond
that, the sequence below is the natural narrative, not a gate sequence.

1. **Make the clock trustworthy.** Land the epoch `status` column, add
   `kg_api.get_committed_epoch()`, and re-comment `graph_change_counter` as a
   one-directional dirty-hint (with a lint note so it is never reintroduced as a
   freshness signal). This closes **#384** and fixes the false-FRESH class on its
   own merit, independent of the rest.
2. **Establish the contract against the surface that already obeys it.** Define
   the `MaterializedDerivation` interface, registry, and conformance test, then
   migrate the **catalog facade** first — it already behaves correctly, so it is
   the lowest-risk way to prove the interface is right before reshaping anything
   that isn't.
3. **Bring the misbehaving derivations into conformance.** The grounding cache
   gains on-read re-reads and a declared staleness budget (**#422**); artifacts
   stamp against the committed sequence, expose `reconcile` via CLI/MCP, and hide
   the storage tier behind `--verbose` (**#233**).
4. **Follow-up, separable:** bring `graph_accel.generation` under the contract or
   prove co-advance, and revisit IVM where it is cheap. This can trail in its own
   PR without holding up the rest.

The commits stand on their own in review — the clock fix is a correctness fix,
the contract is an abstraction with a test, each migration closes a standing
issue — while together they tell the single story this ADR names.

## Consequences

- **Positive:** silent-staleness defects become **contract violations the
  conformance test catches**, not production incidents; the false-FRESH class is
  eliminated at the root (D1); new derivations inherit correct freshness behavior
  by implementing one interface; cross-surface snapshot skew becomes a declared,
  reasoned property (D2) rather than an accident of which clock a subsystem
  happened to read.
- **Cost:** touches three subsystems plus a schema-level clock change; **the
  clock-trustworthiness work (#384) must land first**; the `graph_epoch`-column
  data migration (counter → committed sequence) must be planned with the existing
  artifact and catalog-index rows.
- **Risk accepted:** IVM is deferred — derivations full-recompute on staleness,
  which is correct but not always cheapest. Acceptable: correctness first, the
  contract *permits* IVM later without re-litigation.
- **Risk if not done:** each new materialized derivation adds another parallel
  freshness hierarchy on an unsound signal — the drift this ADR names compounds.

## Alternatives considered

- **Repair `graph_change_counter` into a monotonic commit-bumped sequence
  (decision-space A.2).** Rejected: ADR-203 already established the checksum is
  the wrong primitive, and a *second* monotonic sequence alongside the epoch log
  would be a redundant clock. The epoch `event_id` is already the monotonic
  sequence we need.
- **Reconcile the two existing clocks and prove co-advance (A.3).** Rejected as
  the *primary* signal: it preserves two clocks and therefore the snapshot-skew
  hazard, and proves a property the system would have to keep re-proving on every
  schema change. Co-advance is retained only as the *follow-up fallback* for the
  in-memory accel layer, where the generation counter is extension-internal.
- **Per-surface freshness with no shared contract (status quo).** Rejected: it
  is precisely the parallel-hierarchy drift this ADR exists to stop — the same
  anti-pattern ADR-802 collapsed for providers.
- **Immediate (in-transaction) maintenance instead of deferred/on-read.**
  Rejected for the initial contract: it couples every graph mutation to the cost
  of refreshing all derivations and does not fit the artifact/Garage tier at all.
  Deferred on-read matches the catalog facade's proven model.

## Implementing / related issues

- **#384** — `graph_epochs.status` (committed vs failed): foundation for the
  trustworthy clock (D1).
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
