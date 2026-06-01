# Backup Object Specification

**Status:** Draft
**Format version:** `kg-backup/2`
**Authority:** This document is the authoritative byte-level reference for the
portable backup object. It is the living artifact required by
[ADR-102](../architecture/infrastructure/ADR-102-portable-backup-and-restore-with-clone-merge-semantics.md)
§5 ("The backup is a self-describing, versioned object with a declarative
header"). ADR-102 fixes the *principles*; this spec fixes the *bytes*.

---

## 1. Purpose and scope

A backup object is a **portable, self-describing serialization** of a knowledge
graph's *primary inputs* — the irreplaceable data that cannot be recomputed. It
is designed to round-trip into a destination that shares **none** of the
source's internal indices: a different PostgreSQL cluster, a different platform
version, even a different embedding configuration.

The governing anti-coupling principle (ADR-102 Context, §5): **nothing in the
payload may reference a source-local index whose meaning the destination cannot
reconstruct.** AGE's internal `id()`/`graphid` is OID-coupled and never appears;
neither does any source-platform row id (e.g. "embedding profile = row 7" — that
is the OID mistake one layer down). All identity is carried as either an
app-assigned string id (`concept_id`, `source_id`, …) or a portable,
human-meaningful descriptor declared in the header.

This spec defines the **logical object**: the header, the dictionaries, and the
bulk record shapes. It is transport- and container-agnostic — the same logical
object is what the JSON manifest carries and what the `.tar.gz` archive
(`backup_archive.py`) wraps alongside Garage media bytes.

---

## 2. Top-level structure

A backup object is a single document with two regions in order:

```
┌──────────────────────────────────────────────────────────────┐
│ HEADER  — declarative dictionary of portable descriptors,     │
│           declared ONCE (format version, source, profiles,    │
│           vocabulary, epoch_kinds, actors, ontologies, schema) │
├──────────────────────────────────────────────────────────────┤
│ BULK    — record streams that reference HEADER entries by      │
│           compact integer index, NEVER by repeating strings    │
│           (concepts, sources, instances, relationships,        │
│            vocabulary, graph_epochs)                           │
└──────────────────────────────────────────────────────────────┘
```

```json
{
  "header": { ... },
  "bulk":   { ... }
}
```

The HEADER is read in full *before* any bulk record, so every dictionary a bulk
record might reference is already resolved. A consumer that cannot interpret the
HEADER (see §7) MUST refuse the object rather than partially apply the bulk.

---

## 3. HEADER

The HEADER is a dictionary of portable descriptors, each declared exactly once.
Repeated values that would otherwise appear across tens of thousands of bulk
records live here as **dictionaries**; bulk records cite them by integer index
(§4).

```json
{
  "header": {
    "format_version": "kg-backup/2",

    "source": {
      "platform": "knowledge-graph-system",
      "version":  "1.7.3"
    },

    "exported_at": "2026-06-01T17:42:08Z",

    "schema_version": 76,

    "embedding_profiles": [
      {
        "identity":           "openai:text-embedding-3-small@1536",
        "vector_space":       "openai-3-small",
        "image_vector_space": null,
        "name":               "default-openai",
        "multimodal":         false
      },
      {
        "identity":           "nomic:nomic-embed-text-v1.5@768",
        "vector_space":       "nomic-v1.5",
        "image_vector_space": "siglip2-base@1024",
        "name":               "local-multimodal-rig",
        "multimodal":         false
      }
    ],

    "default_embedding_profile": 0,

    "relationship_vocabulary": [
      {
        "relationship_type":  "IMPLIES",
        "description":        "...",
        "category":           "logical",
        "added_by":           "system",
        "added_at":           "2026-01-04T00:00:00Z",
        "usage_count":        4210,
        "is_active":          true,
        "is_builtin":         true,
        "synonyms":           null,
        "deprecation_reason": null,
        "direction_semantics":"directional",
        "embedding_model":    "openai:text-embedding-3-small@1536",
        "embedding_generated_at": "2026-01-04T00:00:00Z",
        "embedding":          [ 0.013, -0.041, ... ]
      }
    ],

    "epoch_kinds": [
      { "kind": "ingestion", "semantic_wallclock": true,  "description": "..." },
      { "kind": "edit",      "semantic_wallclock": true,  "description": "..." },
      { "kind": "reasoning", "semantic_wallclock": false, "description": "..." },
      { "kind": "annealing", "semantic_wallclock": false, "description": "..." }
    ],

    "actors": [
      "system",
      "user:aaronsb",
      "agent:session-9f3c"
    ],

    "content_types": [
      "text/plain",
      "application/pdf",
      "image/png"
    ],

    "ontologies": [
      {
        "name":                      "Philosophy Corpus",
        "default_embedding_profile": 0
      },
      {
        "name":                      "Vision Notes",
        "default_embedding_profile": 1
      }
    ]
  }
}
```

### 3.1 Field reference

| Field | Type | Meaning |
|---|---|---|
| `format_version` | string | Always `kg-backup/2` for this spec. The single negotiation token (§7). |
| `source.platform` | string | Producing platform identifier. |
| `source.version` | string | Producing platform version (informational; not used for gating). |
| `exported_at` | string | Export instant, ISO-8601 with explicit `Z` (UTC). |
| `schema_version` | integer | Highest applied DB migration at export (the value `BackupFormat.get_schema_version` reads from `kg_api.schema_migrations`). Informational compatibility hint. |
| `embedding_profiles[]` | array | Portable embedding-profile descriptors (§3.2). The dictionary that concept/vocabulary embeddings reference by index. |
| `default_embedding_profile` | integer | Backup-level default profile index — top of the cascade (§4.1). |
| `relationship_vocabulary[]` | array | Vocabulary dictionary; also the bulk `vocabulary` rows (§5.5). Edge `type` refs index into this array. |
| `epoch_kinds[]` | array | The `kg_api.graph_epoch_kinds` lookup rows (migration 064). |
| `actors[]` | array of strings | Distinct actor identifiers referenced by epoch rows, interned. |
| `content_types[]` | array of strings | Distinct MIME types referenced by sources, interned. |
| `ontologies[]` | array | Ontology descriptors, each with its own default embedding-profile index (§4.1). |

### 3.2 Embedding-profile identity string

Each `embedding_profiles[]` entry is a **portable identity**, never a
source-local row id. The canonical identity string is:

```
{provider}:{model}@{dims}
```

e.g. `openai:text-embedding-3-small@1536`, `nomic:nomic-embed-text-v1.5@768`.
This is the value ADR-102 §6 reads to decide *keep-vs-recompute* on restore: if
the target's active profile resolves to the same identity, carried vectors are
kept; if not, they are in the wrong space and MUST be regenerated.

The descriptor is derived from `export_embedding_profile()`
(`api/app/lib/embedding_config.py`) and the `kg_api.embedding_profile` schema
(migrations 055 and 075):

| Profile field | Source |
|---|---|
| `identity` | `{text_provider}:{text_model_name}@{text_dimensions}` (the universal text/prose space — ADR-803, migration 075). |
| `vector_space` | `embedding_profile.vector_space` — compatibility key for the universal **text** space. Two profiles with the same `vector_space` produce comparable text embeddings. |
| `image_vector_space` | `embedding_profile.image_vector_space` (migration 075). The **independent** same-modality image-index space, formatted `{image_provider}:{image_model_name}@{image_dimensions}` (or its `vector_space` tag). `null` for text-only / multimodal profiles. **Never** compared to the text `vector_space`. |
| `name` | `embedding_profile.name` (informational, not an identity). |
| `multimodal` | `embedding_profile.multimodal` — when true the text model also serves the image role and `image_vector_space` is `null`. |

> **Why two spaces.** ADR-803 / migration 075: the graph has ONE universal
> text/prose embedding space (concepts, edges, docs, image-prose). A modality's
> native embedding (the image vector on a Source) is an **independent**
> same-modality search index with its own space and dimensions. The header
> carries both so a destination can decide keep-vs-recompute *per space*.

---

## 4. Dictionary / interning rule

**The HEADER holds the dictionaries; bulk records reference entries by compact
integer index, never by repeating a string.** A concept's embedding-profile
reference is an integer index into `header.embedding_profiles[]`; an edge's
`type` is an integer index into `header.relationship_vocabulary[]`; an epoch
row's `kind`/`actor` are indices into `header.epoch_kinds[]` / `header.actors[]`;
a source's `content_type` is an index into `header.content_types[]`.

This is dictionary/interning encoding: the model string `openai:…@1536` is
written **once** in the header, not restated across every concept.

### 4.1 Cascading-default resolution order

The embedding-profile reference for any record **cascades**. A record states
only its *override*; absent an override it inherits from its parent scope. The
resolution order, most-specific-wins:

```
1. record-level override     (concept.embedding_profile)        — if present
2. ontology-level default    (ontologies[i].default_embedding_profile) — else
3. backup-level default      (header.default_embedding_profile)  — else
```

- A backup with **one uniform** embedding profile declares it once as
  `header.default_embedding_profile` and emits **no** per-record refs.
- A **mixed** backup declares per-ontology defaults; only records that deviate
  from their ontology default carry an explicit `embedding_profile`.
- The same cascade pattern is the model for any future header dictionary whose
  values are scope-defaultable; today only the embedding profile cascades.

A consumer resolves a record's effective profile by walking 1 → 2 → 3 and taking
the first index present. The resolved index then keys
`header.embedding_profiles[]` for the keep-vs-recompute decision (ADR-102 §6).

---

## 5. BULK records

The `bulk` region holds the primary-input record streams. Field lists below are
grounded in the current exporter (`api/lib/serialization.py`,
`DataExporter.export_*`) plus the ADR-102 §3 epoch additions.

```json
{
  "bulk": {
    "concepts":      [ ... ],
    "sources":       [ ... ],
    "instances":     [ ... ],
    "relationships": [ ... ],
    "vocabulary":    [ ... ],
    "graph_epochs":  [ ... ]
  }
}
```

### 5.1 concepts

| Field | Type | Notes |
|---|---|---|
| `concept_id` | string | App-assigned, preserved 1:1 (CLONE) or remapped (adjacent MERGE). |
| `label` | string | |
| `search_terms` | array of strings | |
| `embedding` | array of floats | The text/prose vector. Interpreted in the space named by the resolved embedding-profile ref (§4.1). May be recomputed on restore if the target profile differs (ADR-102 §6). |
| `created_at_epoch` | integer | Epoch `event_id` of first appearance (ADR-203). New in `kg-backup/2`; absent in the legacy `1.0` exporter. |
| `last_seen_epoch` | integer | Epoch `event_id` of most recent re-evidence. New in `kg-backup/2`. |
| `embedding_profile` | integer (optional) | **Override only.** Index into `header.embedding_profiles[]`. Omitted when the ontology/backup default applies (§4.1). |

### 5.2 sources

| Field | Type | Notes |
|---|---|---|
| `source_id` | string | App-assigned. Media keys are *re-derived* from this on restore (ADR-102 §7), not carried. |
| `document` | string | Ontology/document name. |
| `file_path` | string | Original ingest path. |
| `paragraph` | integer | Ordinal within document. |
| `full_text` | string | The source prose — a **primary input** (always carried). |
| `garage_key` | string (optional) | Present only when set (sources predating ADR-081 omit it). Informational; restore reconstructs the key from IDs rather than trusting it. |
| `content_type` | integer (optional) | Index into `header.content_types[]` (interned, replacing the raw MIME string the legacy exporter emitted inline). |
| `storage_key` | string (optional) | Image/media storage key, present only when set. Like `garage_key`, reconstructed on restore. |

### 5.3 instances

| Field | Type | Notes |
|---|---|---|
| `instance_id` | string | App-assigned. |
| `quote` | string | Evidence quote. |
| `concept_id` | string | The evidenced concept (`(c)-[:EVIDENCED_BY]->(i)`). Participates in ID remapping. |
| `source_id` | string | The originating source (`(i)-[:FROM_SOURCE]->(s)`). Participates in ID remapping. |
| `created_at_event_id` | integer | FK into `graph_epochs.event_id` (ADR-203). New in `kg-backup/2`. In **faithful** epoch mode it is remapped through the event-ID map; in **simple** mode all instances are restamped with the single restore event (ADR-102 §3). The legacy exporter dropped this entirely. |

### 5.4 relationships

| Field | Type | Notes |
|---|---|---|
| `from` | string | Source `concept_id`. Participates in ID remapping. |
| `to` | string | Target `concept_id`. Participates in ID remapping. |
| `type` | integer | Index into `header.relationship_vocabulary[]` (interned; the legacy exporter wrote the raw type string per edge). Resolves to the dynamic edge label on restore. |
| `properties` | object | Free-form edge properties. **See §5.4.1.** |

#### 5.4.1 The `learned_id` edge property participates in ID remapping

Edge `properties` is generally free-form, but one key is **load-bearing for
referential integrity**: `learned_id`. Edges minted from agent-learned knowledge
carry `{ learned_id: <source_id> }` (see
`api/app/lib/age_client/query.py` — `CREATE (c1)-[r:{type} {learned_id: $source_id}]->(c2)`).

**`learned_id` is a `source_id` by another name.** It therefore **participates in
ID remapping** exactly like `instances[].source_id`: in adjacent MERGE mode,
when a source's `source_id` is remapped to a new UID, every edge property
`learned_id` referencing the old value MUST be rewritten through the same
old→new ID map. A consumer that treats `properties` as opaque will silently
orphan the learned-knowledge linkage (and break `delete_learned_relationships`,
which matches `()-[r {learned_id: $learned_id}]-()`). Implementations MUST
enumerate `learned_id` in the reference-remap pass (ADR-102 Consequences:
"a missed class silently orphans relationships").

### 5.5 vocabulary

The vocabulary rows mirror `DataExporter.export_vocabulary`
(`kg_api.relationship_vocabulary`). The **same** rows are surfaced in
`header.relationship_vocabulary[]` so edge `type` refs can resolve; the bulk
`vocabulary` stream is the import payload (it reconciles against the target's
vocabulary during rehydration, ADR-102 §6).

| Field | Type |
|---|---|
| `relationship_type` | string |
| `description` | string |
| `category` | string |
| `added_by` | string |
| `added_at` | ISO-8601Z string |
| `usage_count` | integer |
| `is_active` | boolean |
| `is_builtin` | boolean |
| `synonyms` | array of strings or null |
| `deprecation_reason` | string or null |
| `direction_semantics` | string or null |
| `embedding_model` | string (identity form `{provider}:{model}@{dims}`) |
| `embedding_generated_at` | ISO-8601Z string or null |
| `embedding` | array of floats or null |

### 5.6 graph_epochs — **faithful epoch mode ONLY**

Present **only** when the backup is produced for faithful epoch replay
(ADR-102 §3, CLONE-only). Omitted entirely in simple mode. These are the
`kg_api.graph_epochs` log rows (migration 063).

| Field | Type | Notes |
|---|---|---|
| `event_id` | integer | Source-local logical-time id. On restore (faithful) it is recreated as a **new** id in the target range and the old→new mapping is applied to every `instances[].created_at_event_id`. |
| `occurred_at` | ISO-8601Z string | Wall-clock axis; preserved. |
| `kind` | integer | Index into `header.epoch_kinds[]`. |
| `actor` | integer or null | Index into `header.actors[]`. |
| `counter_after` | integer or null | `graph_change_counter` snapshot (ADR-079 cross-ref); informational. |
| `metadata` | object | Free-form event metadata. |

> **Why CLONE-only.** Faithful replay is coherent only when identity is
> preserved 1:1 (empty target). In MERGE the epoch collapses to one restore
> event (simple mode), so the source's `graph_epochs` rows are not carried.

---

## 6. Exclusions: derived products are NOT in the backup

Per **ADR-102 §4** (primary-in / derived-out), the backup carries **primary
inputs only**. The following are **explicitly excluded** and are **regenerated
post-restore** against the true post-restore graph state — never serialized:

- **Projections** (ADR-079, `projections/...`) — derived embedding-landscape
  snapshots.
- **Artifacts / scores** (ADR-083, `artifacts/...`) — polarity analyses,
  grounding results, epistemic scores, and other computed derivations.
- **Grounding caches** and the **catalog index**.

The discriminator is *input vs. derivation*. A derived product is a function of
**global** graph state; introducing any foreign node invalidates it wholesale,
so a carried copy would be stale-yet-fresh-looking (silent corruption). Carrying
none of them also designs out the fragile per-type concept-ID payload rewriter
entirely (ADR-102 §4). The freshness machinery marks derivations stale on
restore (`record_mutation` advances the epoch), so rehydration recomputes them
in dependency order **embeddings → vocabulary → scores** (ADR-102 §6).

Note this is what `image`/source **media bytes** are *not*: media is a **primary
input** the model consumed, so it is always backed up (carried in the archive
alongside this object, keyed by re-derivable `source_id`/content keys — ADR-102
§4, §7), whereas a projection is recomputable and excluded.

---

## 7. Versioning and compatibility negotiation

`header.format_version` is the **single negotiation token**. It is a
slash-delimited `{family}/{major}` string; this spec defines `kg-backup/2`.

**Producer.** Writes its native `format_version` and a HEADER that satisfies the
contract for that version. A producer never downgrades silently.

**Consumer.** On open, reads `header.format_version` *first* and:

1. **Exact major match** (`kg-backup/2`) — accept and apply.
2. **Known family, lower major** (`kg-backup/1` — the legacy `1.0` JSON shape:
   flat `version`/`type`/`data`, no header, no epoch fields, inline type/MIME
   strings) — a consumer MAY accept it through an explicit upcasting reader that
   synthesizes a minimal HEADER (one default embedding profile, interns the
   inline strings) and supplies the missing epoch fields as null/simple-mode
   defaults. Acceptance of older majors is a consumer capability, never assumed.
3. **Known family, higher major** — **refuse.** A `kg-backup/2` consumer MUST NOT
   attempt a `kg-backup/3` object; it may not understand new required HEADER
   dictionaries, and partially applying primary inputs is unsafe (ADR-102 §8:
   restore passes through transiently inconsistent states).
4. **Unknown family** — refuse.

`schema_version` and `source.version` are **informational** and never gate
acceptance — only `format_version` does. The major component bumps on any change
that an older consumer could not faithfully interpret (new required HEADER
dictionary, changed cascade semantics, changed bulk record shape). Additive,
back-compatible HEADER fields that a `2` consumer can ignore do **not** require a
major bump.

ADR-102 §5 recommends this `format_version` also be **discoverable via API**
(e.g. a format-version endpoint) so producer and consumer negotiate
compatibility before transfer. The concrete endpoint shape is an API-contract
concern out of scope for this spec.

---

## 8. References

- **ADR-102** — Portable Backup and Restore with Clone/Merge Semantics
  (§4 primary-in/derived-out; §5 self-describing versioned header; §3 epoch
  reconciliation; §6 rehydration; §7 storage keys).
- **ADR-203** — Graph epoch event log (`graph_epochs`, `created_at_event_id`).
- **ADR-803** — Independent image vector space (migration 075).
- **ADR-079 / ADR-083** — Projections / artifacts (excluded derived products).
- **ADR-015** — Prior backup/restore streaming architecture (schema versioning),
  partly superseded by ADR-102.
- Source: `api/lib/serialization.py` (`BackupFormat`, `DataExporter`),
  `api/app/lib/embedding_config.py` (`export_embedding_profile`),
  migrations `055_embedding_profile.sql`, `075_decouple_image_embedding_space.sql`,
  `063_graph_epoch_events.sql`, `064_graph_epoch_kinds_lookup.sql`.
