---
status: Accepted
date: 2026-06-01
deciders:
  - aaronsb
  - claude
related:
  - ADR-015
  - ADR-079
  - ADR-083
  - ADR-203
  - ADR-205
  - ADR-207
---

# ADR-102: Portable Backup and Restore with Clone/Merge Semantics

## Context

We want to fully export the graph (nodes, edges, properties) **and its source media**
(documents, images, any ingested media) out of a running system and round-trip them
back into a system — the same one, or a different one — under explicit, user-chosen
reconciliation rules. Derived products (projections, scores) are deliberately *not*
part of this payload; they recompute from the restored graph. The existing machinery
does not deliver this.

### What exists today

- **Logical JSON path** — `DataExporter`/`DataImporter` (`api/lib/serialization.py`)
  export concepts/sources/instances/relationships/vocabulary with their
  app-assigned string IDs preserved, and an `overwrite_existing` flag. This is the
  spine we build on.
- **Archive path** — `api/app/lib/backup_archive.py` packages the JSON manifest plus
  Garage document bytes into a `.tar.gz`.
- **Restore worker** — `api/app/workers/restore_worker.py` adds checkpoint + rollback
  safety and calls `record_mutation` to advance the freshness clock after a restore.
- **Semantic re-stitch** — `api/lib/restitching.py` `ConceptMatcher` already performs
  an O(n) cosine-similarity scan to attach incoming concepts to existing ones, no LLM.
  It is the engine for integration mode. (The legacy matcher uses a single 0.85
  threshold; integration mode adopts the canonical two-tier ingestion policy —
  0.85 strict / 0.75 label-boosted, `ingestion.py:432-461` — when the engine is ported.)
- **Physical path** — `operator/database/{backup,restore}-database.sh` wrap
  `pg_dump`/`pg_restore`.

### Why it is not viable as a faithful round-trip

1. **Epochs are dropped.** Export emits none of `created_at_epoch` / `last_seen_epoch`
   (Concepts) or `created_at_event_id` (Instances, FK to `kg_api.graph_epochs`,
   ADR-203). On restore, instances land with NULL event IDs, collapsing the
   re-evidence/lifetime ordering; a restore that records an epoch event but fails to
   complete it can stall the `get_committed_epoch()` watermark (ADR-207).
2. **No mode machinery.** `overwrite_existing` is a single boolean. There is no way to
   create a non-colliding parallel namespace, and no way to merge by similarity.
3. **`pg_dump` cannot do any of this.** It is all-or-nothing table replacement — no
   merge, no remap — and AGE graph identity is OID-coupled, so logical
   dump/restore does **not** survive cross-cluster (ADR-205). This is an Apache AGE
   limitation we do not own.
4. **Open correctness bugs.** `restore-database.sh` reports success when `pg_restore`
   fails (#397, the `| grep` swallows the real exit code) and `pg_restore --clean`
   aborts on AGE label tables (#398). No restore is trustworthy until these are fixed.

### Two facts that shape the design

- **We control every storage key.** No Garage object key is auto-assigned. Keys are
  deterministic functions of app-assigned IDs: `artifacts/{type}/{id}.json` (Postgres
  `SERIAL`), `sources/{ontology}/{sha256[:32]}.{ext}` (content hash),
  `images/{ontology}/{source_id}.{ext}`, `projections/{ontology}/{source}/{ts}.json`.
  Therefore restore **reconstructs** keys from restored IDs rather than tracking them;
  transposition is a *mode we offer*, never a constraint the bucket forces.
- **Identities split into preservable and irrelevant.** App-assigned string properties
  (`concept_id`, `source_id`, `instance_id`, `ontology_id`) are fully preservable — a
  restore simply sets the property. AGE's internal `id()`/`graphid` is OID-coupled and
  **not** preservable, but the application never references it, so its loss is
  immaterial. (Artifact `id` is a Postgres `SERIAL`, but artifacts are derived products
  that are not restored — see §4 — so its preservation is moot.)

## Decision

Make the **logical/portable archive the product**, supporting a full faithful
round-trip with explicit reconciliation. Relegate `pg_dump`/`pg_restore` to
same-version, same-cluster, empty-target disaster recovery, and fix #397/#398 there.

### 1. The governing discriminator is target emptiness, not the restore mode

A restore inspects whether the target graph is empty and bifurcates:

```
CLONE  (empty target)         → high-fidelity reconstruction
  • app-assigned IDs preserved 1:1
  • epoch log replayed (faithful) — coherent only here
  • source media restored as-is; derived products regenerate

MERGE  (populated target)     → idempotent | adjacent | integration
  • IDs preserved / remapped / similarity-matched (per chosen mode)
  • epoch = simple (one restore event)
  • derived products regenerate (never carried in the backup)
```

The rationale is a single invariant: **a derived product is a function of global
graph state.** A polarity analysis, grounding score, or projection computed on the
source describes the source's *entire* graph. Introduce *any* foreign node into the
target and every such product's basis has changed — so all of them are invalid
wholesale, regardless of restore mode. Source media and the graph itself are *primary
inputs* — irreplaceable, and round-tripped in every mode. Derived products are
*recomputable* from those inputs, so they are not carried in the backup at all; they
regenerate after restore (see §4). The one faithful behaviour that survives only the
clone case is epoch-log replay, which is coherent only when identity is preserved
1:1. Emptiness is detected once and gates it.

### 2. Restore modes (apply to MERGE; govern UID-collision behaviour for graph objects)

- **Idempotent** — On UID collision, `MERGE` then `SET` (update in place, no append,
  no mutation of identity). Extends today's `overwrite_existing=True`.
- **Adjacent, no integration** — On collision, mint a new UID and record the old→new
  pair in a persisted mapping table covering concept/source/instance/ontology IDs. All
  internal references (relationship endpoints, instance↔concept↔source links) are
  rewritten through the map on import. Produces a non-colliding parallel namespace.
  (No artifact IDs participate — derived products are not restored; see §4.)
- **Adjacent, with integration** — Wire `ConceptMatcher` (`restitching.py`) to attach
  incoming concepts to existing target concepts by cosine similarity, no LLM. Concepts
  below threshold fall through to adjacent (new UID). Evidence (instances/sources) of a
  matched concept attaches to the existing target concept.

### 3. Epoch reconciliation

- **Export** adds `created_at_epoch` / `last_seen_epoch` (Concepts),
  `created_at_event_id` (Instances), and — for faithful mode — the `kg_api.graph_epochs`
  log rows.
- **Simple** (default; the only mode valid for MERGE): record one `graph_epochs` event
  for the whole restore, stamp every imported instance with that event ID, and
  `complete_epoch` it (never leave it `in_progress`).
- **Faithful** (CLONE only): recreate the source's `graph_epochs` rows as new event IDs
  in the target range, preserving `occurred_at`/`kind`/ordering, and remap each
  instance's `created_at_event_id` through an event-ID map. Gated to the empty-target
  case, where identity is preserved and the replay is coherent.

The flag interface (`--epoch-mode simple|faithful`) ships day one; `simple` is
implemented first (valid everywhere), `faithful` is a scoped fast-follow.

### 4. What travels: primary inputs in, derived products out

The backup carries **primary inputs only** — the irreplaceable data that cannot be
recomputed. Everything derived is regenerated after restore and is never serialized.

**In scope (backed up and restored in every mode):**

- Graph nodes, edges, and properties (including epoch stamps and embedding vectors —
  embeddings travel as node properties, but may be recomputed on restore if the target's
  embedding profile differs; see §6).
- The `kg_api.graph_epochs` log rows (faithful epoch mode only).
- Source documents (text) — content-addressed.
- **Images and any other source media** (the raw ingested bytes — irreplaceable
  primary input, stored under content/`source_id`-derived keys).
- Vocabulary (`kg_api.relationship_vocabulary` + the `:VocabType`/`:VocabCategory`
  nodes).

**Out of scope (NOT backed up — regenerated from the restored graph):**

- **Projections** (ADR-079, `projections/...`) — derived embedding-landscape snapshots.
- **Artifacts / scores** (ADR-083, `artifacts/...`) — polarity analyses, grounding
  results, and other computed derivations.
- Grounding caches and the catalog index.

The discriminator is *input vs. derivation*: source media is an input the LLM consumed,
so losing it loses information; a projection or score is a pure function of the graph,
so it is cheaper and *more correct* to recompute it against the restored graph than to
carry a stale copy. The existing freshness machinery makes regeneration automatic — a
restore advances the global epoch via `record_mutation`, so any derivation is recomputed
on next access against the true post-restore state.

**Explicitly eliminated** by excluding derived products from the backup: the
per-artifact-type concept-ID payload rewriter the naïve "remap artifacts with the graph"
design would have required. There are no derived payloads in the archive, so there is
nothing to rewrite — removing the single most fragile, highest-maintenance component.

> **Consistency note (decided).** An earlier round selected "include artifacts + remap
> with the graph." That is superseded: artifacts/scores fall under the derived-products
> invariant above and are treated exactly like projections — excluded and regenerated —
> so the rule is uniform across *all* derivations, with no special case for the clone
> path. Regenerating them after restore (§6) is both correct (recomputed against the
> true post-restore graph) and simpler (no payload rewriter). If retaining artifact
> *bytes* for the clone case ever proves worth the recompute cost, that is a narrow,
> additive follow-up; the default is regenerate.

### 5. The backup is a self-describing, versioned object with a declarative header

A backup must be interpretable by a destination that shares none of the source's
internal indices. The anti-coupling principle that rules out AGE OIDs (Context) applies
to the *serialization* too: nothing in the payload may reference a source-local index
whose meaning the destination cannot reconstruct. Storing "embedding config = row 7" is
the OID mistake one layer down — row 7 is meaningless, or means something different, on
the target. The format is therefore self-describing.

**A declarative metadata header precedes the bulk records.** The header is a dictionary
of portable, human-meaningful descriptors — declared once as actual strings, never as a
source-platform index:

- **embedding profile(s)** — the model identity string and dimensionality (e.g.
  `openai:text-embedding-3-small@1536`), not the source's internal embedding-config row
  id. This is the exact value §6's rehydration reads to decide recompute-vs-keep.
- **schema / format version**, source platform + version, export timestamp.
- **relationship vocabulary**, **epoch kinds**, **actors**, **ontology descriptors** —
  any value that would otherwise repeat across many records.

**Bulk records reference the header by compact local index, not by repeating the
string.** A concept's embedding carries a small reference to the header's embedding-
profile entry instead of restating the model string tens of thousands of times
(dictionary/interning encoding). References **cascade**: a default declared at a parent
scope (backup → ontology) is inherited, and a record states only its *override*. A
backup with one uniform embedding profile declares it once at the top; a mixed backup
declares per-ontology.

**The byte-level schema is NOT defined in this ADR.** It is its own living artifact — a
versioned **Backup Object Specification** authored and maintained during the build, kept
as the authoritative reference and ideally discoverable via API (e.g. a format-version
endpoint) so producer and consumer negotiate compatibility. This ADR fixes the
*principles* — self-describing; portable strings, never source indices; a normalized
header with cascading local references; an explicit version carried in the header — and
requires the spec to exist. The spec fixes the bytes.

### 6. Post-restore rehydration: regenerating derived state

Because derived products are excluded (§4), a restore is not finished when the primary
data lands — the graph must be *rehydrated*: its derivations recomputed against the
restored state. Restore therefore ends with a rehydration phase that re-triggers three
derivation passes. Each is a toggle whose default performs it, so a default restore
yields a fully usable graph:

- **Embeddings** — default *auto*. Embeddings travel in the backup (node properties), so
  a clone into a target with the same embedding profile keeps them. But if the target's
  embedding profile differs (model/dimensions — see ADR-803 and the embedding-profile
  system), the carried vectors are in the wrong space and MUST be regenerated; `auto`
  detects the mismatch and recomputes only then. **Hard dependency:** integration mode
  (§2) matches incoming concepts by cosine similarity and therefore requires target-space
  embeddings — on a detected profile mismatch, embeddings are recomputed *before*
  integration matching runs, otherwise integration mode is rejected.
- **Vocabulary management** — default on. Imported relationship vocabulary is reconciled
  against the target's: new types embedded, synonyms consolidated, the vocab refreshed
  (the existing vocab consolidate / embedding / refresh workers). Cheap and
  correctness-bearing, so on by default.
- **Scores** — default on (eager warm-up); may be set lazy. Polarity, grounding, and
  epistemic scores recompute over the settled graph. The freshness machinery already
  marks them stale post-restore (§4), so *lazy* simply lets them regenerate on first
  access; the eager default proactively warms them so the restored graph is query-ready.

**Ordering is a dependency chain, not a preference: embeddings → vocabulary → scores.**
Scores depend on embeddings and settled vocabulary; integration-mode matching depends on
embeddings. Rehydration runs after the structural import and is the controlled
counterpart to worker quiescence (§8): the lanes frozen for the critical section are
re-enabled and kicked in this order, scoped to the restored data.

**Out of scope here:** the concrete request/response **DTO shape** of the
backup/restore endpoints (which flags, their JSON names, response envelopes). That is an
API-contract/implementation concern to settle during the build — possibly its own small
follow-up — not an architectural decision. This ADR fixes only that these passes
*exist*, their *defaults*, and their *dependency ordering*.

### 7. Storage is engine-agnostic; key collisions are a projection of ID collisions

Garage is one S3-compatible target and may be swapped (MinIO, AWS S3, a filesystem
backend). Backup/restore must therefore never embed Garage specifics. Two rules:

- **All object I/O goes through the abstract object-store port** — the verbs already
  exposed by `GarageBaseClient` (`put_object` / `get_object` / `list_objects` /
  `head_object` / `delete_object` / `delete_by_prefix`). Restore calls these, never a
  storage SDK and never a hardcoded bucket assumption. The orphan/reference
  reconciliation this enables (cf. #202/#188) is likewise just `list_objects(prefix)`
  cross-checked against the graph — storage-engine-agnostic by construction.
- **Key construction stays owned by the storage-domain layer** (`_build_key` in each
  storage service) and is *reused* by restore, not re-implemented. Restore reconstructs
  a key from a (possibly remapped) ID by calling the same scheme function the writer
  uses.

The consequence is that **a storage-key collision is never an independent event — it
is the shadow of an ID collision**, and the chosen restore mode already resolves it:

Only **primary inputs** are restored, so only their keys can collide. Derived products
(`artifacts/...`, `projections/...`) are never written by restore — they regenerate —
so they cannot collide at all and are absent from this table.

| Restored object | Key derivation | idempotent (ID kept) | adjacent (ID remapped) |
|---|---|---|---|
| image / source media | `images/{ontology}/{source_id}` | same key → overwrite in place | new `source_id` → new key |
| source document | `sources/{ontology}/{sha256[:32]}` | content-addressed: same key ⇒ same content ⇒ benign dedup | content-addressed: dedups regardless of graph remap |

Therefore **no separate storage-key mapping table exists**: the graph-ID mapping
(Decision §2, adjacent mode) is the single source of truth, and media keys are
re-derived from the (possibly remapped) IDs. Note that content-addressed source/media
keys are *immune* to ID remapping — identical bytes always resolve to the same key, so
adjacent mode dedups them rather than duplicating. Overwrite-vs-mint is decided by an
existence check expressed in port primitives (`head_object`), not by inspecting Garage.

This ADR does not require swapping the backend, but it does require the restore code to
depend only on the port. A recommended (non-blocking) follow-up is to **formalize the
port as an explicit `ObjectStore` interface that `GarageBaseClient` implements** — the
seam exists de facto today (clean S3-shaped verbs) but is not named, so a future swap
relies on convention rather than a typed contract.

### 8. Backup is concurrent-safe; restore requires worker quiescence

The two operations are fundamentally asymmetric:

- **Backup is read-only and non-interfering.** It enumerates the IDs of every
  qualifying object and serializes the data behind them. Run inside a single
  repeatable-read transaction it gets an MVCC-consistent snapshot, so it needs **no
  freeze** — workers may continue mutating; the snapshot is unaffected.
- **Restore fundamentally breaks the graph during the pass.** It is a foreign bulk
  import that passes through transiently inconsistent states (a concept exists before
  its edges; a remapped ID is half-rewritten; instances precede their epoch stamp).
  Other lanes will actively interfere with — or react destructively to — these
  intermediate states:
  - **ingestion** — concurrent foreign writes race the import and can collide on UIDs
    or, in integration mode, change the candidate set mid-similarity-scan, making
    matching non-deterministic;
  - **annealing** — promotes/demotes/merges concepts based on graph state and would
    act on a half-imported graph;
  - **integrity/healing** (#241) — would "heal" deliberately-transient incomplete
    structures;
  - **artifact cleanup** (#202) — would reap objects mid-restore as "orphaned."

  A restore therefore runs as a **bounded critical section** that freezes the
  interfering lanes for its duration and thaws them afterward, using the lane control
  shipped in `lane_manager.py` (per-lane `enabled` flag, `PATCH
  /admin/workers/lanes/{name}`; "Frozen" pill in the web UI). Freezing also keeps the
  epoch watermark clean: with ingestion paused, the restore's `graph_epochs` event is
  the only in-flight one, so `get_committed_epoch()` cannot stall on an interleaved
  foreign event.

  The freeze set scales with how invasive the restore is. **Clone** into an empty
  target still freezes (intermediate states would trip annealing/integrity if those
  lanes are running), but the embedding lane is a *dependency*, not interference, for
  **integration** mode and is left thawed. The exact per-mode freeze set is an
  implementation detail to be pinned during build and verified by an adversarial
  "run a worker mid-restore" test; the invariant is that no lane observes or mutates
  the graph inside the critical section except the restore itself.

### 9. One supported path; superseded code is deleted, not parked

This ADR defines *the* portable backup/restore path. Implementing it means **removing
the implementations it supersedes in the same PR series** — the tree must never carry
two restore systems at once. The rationale is not tidiness but safety: parallel,
half-working restore code is precisely how an operator reaches for the wrong tool and
loses data — the failure shape of #397. A superseded path left "just in case" is a
loaded footgun, and the backup we now guarantee is the actual safety net.

Method (not a guessed file list — the authoritative kill-list comes from tracing
imports, as the workflow's first phase):

- **Retained, explicitly NOT purged:** the operator `pg_dump`/`pg_restore` DR scripts
  (`operator/database/{backup,restore}-database.sh`). They are *narrowed* to
  same-version/same-cluster/empty-target DR and *bug-fixed* (#397/#398), not removed.
  This carve-out is stated so a later cleanup does not delete them as "redundant."
- **Audit then delete:** the backup/restore surface is currently spread across three
  trees — `api/lib/` (`serialization.py`, `restitching.py`, `integrity.py`),
  `api/app/lib/` (`backup_archive.py`, `backup_integrity.py`, `backup_streaming.py`,
  `gexf_exporter.py`), and `api/admin/` (`backup.py`, `restore.py`, `stitch.py`), plus
  routes and the `kg` CLI. The `api/lib/` vs `api/app/lib/` split is a strong signal of
  old-path/new-path coexistence (e.g. `api/lib/integrity.py` vs
  `api/app/lib/backup_integrity.py`; `api/admin/stitch.py` vs `api/lib/restitching.py`).
  The first implementation phase produces an import-traced inventory marking each
  module **keep / fold-into-new / delete**, and deletions land alongside the code that
  replaces them.
- **Reconcile the prior ADR:** ADR-015 (Backup/Restore Streaming Architecture) is at
  least partly superseded by this decision. The audit determines whether its
  streaming-transport mechanism is retained under the new path or fully replaced, and
  ADR-015's status is updated accordingly (Superseded, or amended) when this lands —
  rather than blanket-flipping it now on assumption.

### 10. Bug fixes folded in

- **#397** — capture `pg_restore`'s real exit status (`set -o pipefail` / `PIPESTATUS`)
  and verify post-restore counts.
- **#398** — restore into a genuinely empty database (DROP/CREATE then restore without
  `--clean`) or `drop_graph()` before a `--clean` restore.

## Consequences

### Positive

- True round-trip of all primary inputs: graph + epochs + source documents + images and
  other source media, IDs preserved. Derived products regenerate against the restored
  graph — more correct than carrying stale copies.
- Three explicit, well-defined merge behaviours instead of one opaque boolean.
- Cross-cluster portability via the logical path, sidestepping AGE OID coupling.
- The self-describing, versioned format makes backups portable across platforms with
  different internal indices and even different embedding configs (the declared profile
  drives recompute), and the normalized header keeps repeated descriptors out of the
  bulk (one interned string, not tens of thousands).
- The fragile per-type artifact rewriter is designed out, not merely deferred.
- Reuses existing engines (`DataExporter/Importer`, `ConceptMatcher`, restore worker,
  epoch/freshness machinery); the genuinely new surface is the ID-remap/mapping layer
  and epoch reconciliation.
- Two long-standing restore bugs (#397/#398) get fixed as a precondition.
- The backup/restore surface collapses from three overlapping trees to one supported
  path; the wrong-tool data-loss footgun is removed rather than left loaded.

### Negative

- The ID-remap layer must rewrite *every* internal reference class; a missed class
  silently orphans relationships. Demands exhaustive reference enumeration + tests.
- Faithful epoch replay is real complexity (event-ID map + contiguous-watermark proof),
  even though it is scoped to clone-only and sequenced as a fast-follow.
- Adjacent mode's mapping table is new persisted state with its own lifecycle.
- Deleting superseded modules demands careful import-tracing; an over-eager deletion
  could remove a still-referenced path. The keep/fold/delete inventory is the guard.

### Neutral

- `pg_dump`/`pg_restore` remains, narrowed to same-cluster DR; it is no longer the
  cross-cluster story.
- Backups stay lean: only primary inputs travel (graph, epoch log, source media);
  derived products (projections, scores) are excluded and regenerate post-restore.
- Target-emptiness detection becomes a load-bearing precondition check at restore time.
- Restore becomes a maintenance-window operation: it freezes interfering lanes for the
  duration of the critical section. Backup carries no such cost and stays online.

## Future Direction: Shard Data Exchange (north star, not in scope)

This is explicitly *not* what we are building now, but the endpoints defined here are
intended to become the data-plane primitives for the distributed sharding research
(`docs/manual/06-reference/08-DISTRIBUTED_SHARDING_RESEARCH.md`). The alignment is
direct enough to record so we don't design against it:

- **The portable archive is the shard interchange wire format.** Shards are separate
  AGE clusters, so AGE's OID coupling (ADR-205) rules out physical transfer between
  them — the logical/portable path is the *only* viable shard-to-shard channel. A
  rebalance is literally "export ontology from shard A, import into shard B."
- **The three restore modes are the three cross-shard data operations:**
  - *adjacent + mapping table* = **move an ontology to a new shard**, minting fresh
    IDs in the destination namespace while preserving referential integrity — the
    research's "re-upsert to better shard" / `move_ontology` (Patterns 3 & 5);
  - *integration (cosine attach)* = **arrival-side dedup for hub-concept replication**
    — when a vertex-cut replica lands on a shard that already holds that hub concept
    (Pattern 4), integration mode is the attach-to-existing primitive;
  - *idempotent* = **replica sync** — push the authoritative copy, update-in-place on
    collision (`ConceptReplicator.sync_updates`).
- **The ID-remap/mapping table is the cross-shard identity layer.** The old→new map
  adjacent mode persists is the same structure that tracks primary-shard ↔ replica
  identity for the research's `cross_shard_references`.
- **Epoch reconciliation prefigures the distributed logical clock.** Each shard owns
  an independent monotonic `graph_epochs` counter; faithful mode's event-ID remapping
  into a target range is the seed of per-shard logical clocks / vector-clock freshness
  across a federation.
- **Worker quiescence is the shard-migration consistency window.** Freezing the source
  ontology's lanes, exporting, importing to the target, then thawing is exactly the
  primitive an online ontology move between shards requires.

In short: the sharding research's router is the *control plane* (FENNEL-style routing,
coherence monitoring); this ADR builds the *data plane* that control plane would
command. Building backup/restore well now is building shard exchange later.

## Alternatives Considered

- **Invest equally in `pg_dump` cross-cluster restore.** Rejected: AGE OID coupling
  (ADR-205) is not ours to fix, and `pg_dump` cannot express merge/remap semantics.
- **Single epoch strategy only (simple everywhere).** Rejected as the *sole* option: a
  true clone/DR target legitimately wants the source's temporal ordering preserved.
  Adopted as the default and the only MERGE option; faithful is the clone-only addition.
- **Remap-and-keep derived products in all modes** (per-type payload rewriter).
  Rejected: a derived score is invalid once the target graph differs at all, so a
  remapped score presents as fresh while describing a graph state that no longer exists
  — silent corruption. The rewriter is also the highest-maintenance component (one per
  payload schema). Excluding derived products and regenerating them is both correct and
  simpler.
- **Keep derived-product bytes for the clone case only.** Considered and not adopted as
  the default: it splits the rule (carry-on-clone vs regenerate-on-merge) and reintroduces
  format/versioning concerns for payloads that recompute cheaply against the restored
  graph. Uniform "exclude and regenerate" was chosen instead; retaining clone-only bytes
  remains an additive follow-up if a specific derivation proves expensive to recompute.
- **Back up source media as derived/optional.** Rejected: images and ingested media are
  *primary inputs* the model consumed, not recomputable — losing them loses information.
  They are always backed up and restored, in every mode.
