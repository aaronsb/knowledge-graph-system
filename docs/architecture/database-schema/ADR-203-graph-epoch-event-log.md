---
status: Draft
date: 2026-05-19
deciders:
  - aaronsb
  - claude
related:
  - ADR-079
  - ADR-200
  - ADR-202
---

# ADR-203: Graph Epoch Event Log

## Context

The graph already carries a notion of "epoch" — `graph_metrics.graph_change_counter`, introduced by ADR-079 (migration 033). On every ingestion, concepts are tagged with `created_at_epoch` and `last_seen_epoch` (see `api/app/lib/age_client/ingestion.py:168-169`), and the counter is refreshed via `refresh_graph_metrics()`.

That counter is **a composite checksum**, not an event sequence:

```sql
graph_change_counter = count(concepts) + count(edges) + count(sources) + ...
```

Two consequences fall out of that definition:

1. **Values are not unique over time.** Delete a concept and add one — the counter is unchanged. Two distinct graph states can produce the same counter value. So `counter_value → wall_clock_time` is not a function: it cannot be a join key.
2. **There is no wall-clock anywhere.** Concept and Instance nodes do not record when they were created in real time; the system only knows "counter value at write."

Issue #187 originally framed this as "no temporal ordering capability for concept evolution." The original proposal — `PRECEDED_BY` / `EVOLVED_INTO` relationship types inferred from ordering — conflates two things that should remain distinct:

- **Logical time**: monotonic ordering of mutations to the graph. Always meaningful, including for activity that has no useful wall-clock (agent reasoning, ontology breathing, manual restructuring).
- **Wall-clock time**: when an event physically happened. Always present in absolute terms, but **semantically meaningful only for some kinds of events** — primarily external-corpus ingestion. An agent creating 200 concepts during a reasoning loop at 15:03 UTC doesn't make those concepts "from 15:03" in any useful sense.

The system needs both, treated as orthogonal dimensions. It also needs the data structure that lets the per-concept *re-evidence stream* be walked honestly — without inventing causal edges the data cannot justify.

### The re-evidence stream is the actual payoff

A `:Concept` already accumulates `:Instance` nodes via `EVIDENCED_BY` — one Instance per chunk that re-evidenced it. That stream **is** the concept's lifetime: born at the first Instance, grown by every subsequent one, dormant when none arrive for a long stretch.

Today the stream cannot be ordered chronologically. Instances carry no epoch tag (constructor at `api/app/lib/age_client/ingestion.py:281`). Tagging them closes the loop: a single ordered walk over a Concept's Instances yields its re-evidence history — count, sequence, and time deltas where wall-clock is meaningful — without the LLM having to assert causal relationships.

## Decision

Introduce a dedicated **epoch event log** alongside the existing change counter, and tag `:Instance` nodes with a foreign key into it.

### 1. New table: `kg_api.graph_epochs`

```sql
CREATE TABLE kg_api.graph_epochs (
    event_id     BIGSERIAL PRIMARY KEY,
    occurred_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    kind         TEXT NOT NULL,         -- 'ingestion' | 'reasoning' | 'breathing' | 'edit'
    actor        TEXT,                  -- user_id, agent session id, system component
    counter_after BIGINT,               -- graph_change_counter snapshot post-event (cross-ref)
    metadata     JSONB DEFAULT '{}'::jsonb
);
CREATE INDEX idx_graph_epochs_occurred_at ON kg_api.graph_epochs(occurred_at);
CREATE INDEX idx_graph_epochs_kind        ON kg_api.graph_epochs(kind, occurred_at);
```

`event_id` is the logical-time axis (monotonic, unique). `occurred_at` is the wall-clock axis (always recorded, but interpret semantically per `kind`). `kind` is the discriminator that tells downstream queries whether wall-clock means anything for this row.

`TIMESTAMPTZ` aligns with the UTC invariant from ADR-202.

### 2. Event granularity: one epoch per job

A new `graph_epochs` row is recorded **once per logical unit of graph mutation**:

- `kind='ingestion'` — one row per ingestion job, recorded at job *start*, so the assigned `event_id` is available to tag every Instance created during that job.
- `kind='breathing'` — one row per ontology-breathing pass (cross-ref ADR-200).
- `kind='edit'` — one row per explicit manual mutation.
- `kind='reasoning'` — one row per agent reasoning session that mutates the graph.

Per-chunk is too granular and explodes the row count without semantic value. Per-session is too coarse and loses the ability to attribute Instances to a specific ingestion. Per-job is the natural transaction boundary the system already operates on.

### 3. Instance tagging

`:Instance` nodes gain a `created_at_event_id` property at creation time (`age_client/ingestion.py:281`). The ingestion flow obtains the event_id at job start (Decision §2) and threads it through to Instance creation. Existing Instances carry no event_id — see Migration below.

### 4. Coexistence with `graph_change_counter`

The existing `graph_change_counter` (ADR-079) is **retained, unchanged**. Its purpose is composite cache-invalidation; it remains a count checksum. `graph_epochs.event_id` is the new monotonic event sequence with different semantics. The two coexist:

- ADR-079 counter → "has any part of the graph changed since I cached?"
- ADR-203 event_id → "what discrete mutation event introduced this data?"

They are not unified, because their semantics are different. The ADR records this explicitly so future readers do not attempt to reconcile them.

### 5. Concept-level epoch fields

`:Concept.created_at_epoch` and `last_seen_epoch` (count-snapshot values, written by current ingestion code) are **left in place as legacy**. They retain their ADR-079 cache-invalidation semantics. They are *not* renamed or migrated. If a future ADR wants to add `created_at_event_id` / `last_evidenced_event_id` to Concepts directly, that is a separate scope; the present ADR derives concept lifetime from the Instance chain.

### 6. Scope of this ADR

In scope:
- The `graph_epochs` table and its insertion contract.
- Instance-level `created_at_event_id` tagging.
- Recording an `ingestion` epoch at job start.
- Test coverage proving re-evidenced Concepts have Instances spanning distinct event_ids.

Out of scope (deferred to follow-up issues):
- API endpoints for re-evidence timeline queries.
- Web UI for time-travel / epoch picker.
- Analytics queries (anchor / hot / stale / acceleration signals).
- Concept-level event_id columns.
- Backfilling event_ids onto historical Instances.
- Wiring up `kind='breathing'` / `'reasoning'` / `'edit'` events. These will land as those subsystems independently grow event awareness.

## Consequences

### Positive

- **Honest logical/wall-clock separation.** Two dimensions, queryable independently, no false-causality edges.
- **Re-evidence stream becomes walkable.** `MATCH (c:Concept)-[:EVIDENCED_BY]->(i:Instance) ORDER BY i.created_at_event_id` is the concept-lifetime query.
- **Foundation for drift / freshness signals** — Freshness Way explicitly notes its blindness to content-level drift; epoch-tagged Instances close part of that gap (concepts not re-touched in N events become a derivable signal).
- **Forensic floor.** Every mutation now has a recorded actor and wall-clock, which is independently useful even when wall-clock isn't semantically primary.

### Negative

- **Insertion-timing contract change.** Ingestion must record its epoch *before* creating Instances, not as a post-hoc effect of `refresh_graph_metrics()`. Code paths need to be audited.
- **Slight write overhead** — one extra row per ingestion job. Negligible relative to the work the job does.
- **Two epoch concepts coexist.** Cognitive load on contributors until the distinction is internalized. Mitigated by explicit naming (`graph_change_counter` vs `graph_epochs.event_id`) and this ADR.

### Neutral

- Existing Instances will carry `NULL` for `created_at_event_id`. Queries that require event ordering must either exclude them or treat them as a single "pre-epoch" cohort. Backfill is possible (from each Instance's Source's ingestion job timestamp) but explicitly deferred.

## Alternatives Considered

### A. Promote `created_at_epoch` to TIMESTAMPTZ on every node

Stamp the wall-clock directly onto Concept and Instance properties — no event table.

**Rejected.** Forces wall-clock onto every node, including ones created during agent reasoning or breathing where wall-clock is semantically noise. Conflates the two dimensions the design is trying to separate. Also makes it impossible to attribute multiple Instances to "the same ingestion job" without inventing a separate grouping mechanism.

### B. Reuse `graph_change_counter` as the event_id

Tie a timestamp table to existing counter values.

**Rejected.** The counter is a count checksum, not monotonic — values can recur (delete+add). The mapping `counter_value → wall_clock` is not a function, so it cannot serve as a join key.

### C. PRECEDED_BY / EVOLVED_INTO relationship vocabulary (original #187)

Infer causal relationships between concepts from ordering and re-evidence patterns.

**Rejected.** Requires either ordering-based shallow inference (which is misleading — order ≠ causation, and re-ingesting older content inverts the apparent order) or LLM judgment about evolution (which is expensive, brittle, and asserts facts into the graph the data can't honestly support). The Instance-stream design supersedes this: evolution narratives are *derived* from honest accumulation, not asserted.

### D. Per-chunk event granularity

Record a `graph_epochs` row for every chunk processed.

**Rejected.** Explodes row count without semantic value. The job is the natural transaction boundary; finer granularity is recoverable from `Instance.created_at_event_id` joined to source/chunk metadata if anyone ever needs it.
