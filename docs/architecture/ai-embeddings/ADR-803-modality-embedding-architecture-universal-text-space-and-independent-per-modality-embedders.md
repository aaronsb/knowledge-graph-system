---
status: Proposed
date: 2026-05-31
deciders:
  - aaronsb
  - claude
related:
  - ADR-802
  - ADR-800
  - ADR-801
  - ADR-057
  - ADR-039
  - ADR-045
---

# ADR-803: Modality Embedding Architecture — Universal Text Space and Independent Per-Modality Embedders

## Context

ADR-802 established vision as a first-class *reasoning* capability (image→prose)
resolved independently like embedding. Implementing the embedding side surfaced
a modality-general question about **embedding spaces** that ADR-057 and its
schema (migration 055, `kg_api.embedding_profile`) answered implicitly — and
incorrectly.

Migration 055 models an embedding profile as **two co-spatial slots**: a text
model and an image model sharing one `vector_space`, with
`chk_image_dimensions_match` forcing `text_dimensions = image_dimensions` and a
`multimodal` flag for "one model serves both." The implicit premise is that
image and text embeddings must be **comparable** — an image vector and a concept
vector in the same space, matched cross-modally.

Inspection of the running system contradicts that premise:

- The image embedding (`visual_embedding`, 768-dim) is **stored on Source nodes
  and exposed only as a `has_visual_embedding` presence flag**
  (`routes/sources.py`). There is **no `vector_search` over it**, and **nothing
  compares an image embedding to a Concept/text embedding.**
- The concept graph is built **entirely from prose**: image ingestion is a
  hairpin — `image → describe_image() → prose → text pipeline → concepts`
  (`workers/ingestion_worker.py`, ADR-057). Every semantic operation
  (extraction, vector-match/merge, edges) runs on **text** embeddings.

So the cross-modal co-spatiality the schema enforces is never exercised. It does
no work except to **forbid otherwise-valid configurations** (e.g. a 768-dim text
embedder with a 1024-dim image embedder). The coupling was a category error.

This is not a push to build new modalities. It is about keeping the architecture
**sane and non-locking** — so that it does not bake in the assumption that all
content must be reduced to one comparable vector space, and does not preclude
modality-native embedders (or reasoners) if they ever become useful.

**Why prose is privileged (grounding, not arbitrary).** Modality-native
symbolic relationships are real: one can mark two lines on wood and *see*,
wordlessly, that one is longer. But to make that relation **communicable and
relational** — to enter a *shared* knowledge graph — it must be rendered in
symbolic representation ("line", "mark", "longer"/"shorter", "wood"). A knowledge
graph arises precisely from the **unification of symbolic representation with the
sensory/format modalities** (visual, spatial, motion, auditory). Prose is not
privileged by fiat; it is the symbolic medium through which any modality's
content becomes relational knowledge. That is why every modality joins the graph
through prose, while its raw perceptual embedding stays an independent index.

## Decision

**The knowledge graph has exactly one semantic embedding space — the text/prose
space. Content joins it through prose; a modality's native embedding, if any, is
an independent same-modality search index that is never compared to the graph.**

### 1. One universal text/prose space

All graph semantics live in a single embedding space produced by the **text/prose
embedder**: concepts, edges, documents/sources, **and the prose description of
any non-text artifact**. It is the only space the graph reasons or matches in.
Exactly **one** embedder is semantically global.

### 2. Prose is the bridge into the graph (the hairpin)

A non-text artifact joins the graph by being **described into prose**, which is
embedded in the universal text space and extracted like any other text:

```
artifact → describe → prose → text space → concepts
```

The describe step is a *reasoning* capability (ADR-802); the embedding step is
the universal text embedder. The artifact needs no representation comparable to
concepts, because its **prose** is what reaches the graph.

### 3. A modality's native embedding is an independent index

Where a native embedding exists (the image vector today), it lives in its **own**
space, sized by its own model, used **only** for same-modality similarity search.
It is **not** co-spatial with the text space and is **never** compared to it.
Modalities are decoupled from text and from each other by construction.

A single multimodal model that *can* embed text and image into one space does
**not** change this: we treat its image output as an independent index and let
prose do the graph work. Co-spatiality is an optional property of a model, never
an architectural requirement.

### 4. The real invariant is text-space consistency

The risk worth guarding is **not** "text and image embedders differ" — that is
the design. It is **changing the active text/prose embedder**, which changes the
universal space and invalidates *every* existing text embedding (concepts, edges,
docs, image-prose), requiring a re-embed. That change must warn and prompt
re-embedding. Choosing a different (or absent) modality embedder carries no such
consequence.

### 5. Schema correction (incremental, non-committal)

Migration 055's co-spatiality constraints are relaxed: `chk_image_dimensions_match`
is dropped and the image slot may hold its **own** `vector_space` and dimensions,
independent of the text slot. This removes the over-constraint without committing
to any particular future shape — the architecture *permits* additional
independent per-modality embedders but this ADR does **not** design or schedule
them. We are not building the future here; we are not locking it out.

## Consequences

### Positive

- The cross-modal embedding-space problem **dissolves**: nothing must be
  co-spatial because nothing is compared across modalities. Prose is the only
  bridge, and it is already in the universal space.
- Configurations the old constraint forbade (independent image dims/space) become
  valid; the operator is no longer asked to match image and text embedders for a
  comparison that never happens.
- The warning surface points at the **real** risk (text-embedder change ⇒
  re-embed) instead of a non-issue (text≠image embedders).
- The architecture is not locked into "all content reduces to one vector space,"
  so future modality-native embedders are neither required nor precluded.

### Negative

- ADR-057 / migration 055 carried the co-spatiality assumption; relaxing it is a
  correction future readers must understand (hence this ADR supersedes that
  aspect). Code/docstrings asserting "image embeddings share the text vector
  space" (e.g. `routes/ingest_image.py`) must be corrected so the wrong premise
  is not re-propagated.

### Neutral

- Image-by-vector search is not yet wired (the native index is currently
  write-only/presence-flagged); this ADR defines the space it will search in when
  built, without requiring it now.
- **Forward note, not a decision:** prose is today the unification substrate for
  *reasoning* as well as embedding — all reasoning currently routes through text.
  Nothing here precludes modality-native reasoners (visual, auditory, motion)
  later, with prose remaining the common logical-reasoning substrate that ties
  them together. We are not building that; we are only keeping the door open.
- A multimodal embedder remains usable — it fills the text role and, optionally,
  an independent modality role; its cross-modal capability is simply not relied
  upon.

## Alternatives Considered

- **Keep co-spatiality (migration 055 as-is).** Rejected: it enforces a property
  the system never uses, forbids valid configurations, and points operator
  attention at a non-problem. The code shows no cross-modal comparison exists.
- **Require a single multimodal model for both text and image.** Rejected:
  couples the universal text space to image-model availability for no benefit —
  prose already bridges the modality, and forcing one model restricts provider
  choice (counter to ADR-801).
- **Re-architect now into a general text-embedder + N-modality registry.**
  Rejected for this ADR as over-building: the principle does not require a
  speculative registry, and the goal is a non-locking architecture, not a
  forward roadmap. The minimal constraint relaxation is sufficient; a richer
  shape can be designed if and when a real second modality arrives.
- **Compare image embeddings to concepts directly (a real cross-modal graph).**
  Rejected (analysed in the ADR-802 session): a raw image vector is a noisier
  query than its prose, and the prose is produced anyway — cross-modal adds cost
  and noise for no gain over the hairpin.
