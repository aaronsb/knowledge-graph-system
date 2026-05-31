---
status: Accepted
date: 2026-05-30
deciders:
  - aaronsb
  - claude
related:
  - ADR-800
  - ADR-801
  - ADR-039
  - ADR-045
  - ADR-041
---

# ADR-802: Unify Vision Providers Under the Uniform Provider Contract

## Context

ADR-800 made *which models exist* catalog-driven; ADR-801 made *how a
reasoning provider is configured and selected* a uniform four-surface
contract (validate / enumerate / reasoning controls / persisted per-provider
config, with a per-provider config row decoupled from a single `active`
pointer). The catalog-driven vision work (task #13,
`feat/adr-801-catalog-driven-vision-selection`) made vision selection of
*which model* catalog-driven via the per-row `supports_vision` flag, but
deliberately stopped there. Two gaps remain, filed as #378 and #379:

- **#378 — vision provider default is a bare hardcoded policy.**
  `ingestion_worker.py` resolves the vision provider as
  `job_data.get("vision_provider", "openai")`. The default is `"openai"`
  independent of what is configured or active. A deployment running only
  Anthropic or only a local model still sends image→prose to OpenAI unless
  every job explicitly overrides it.

- **#379 — vision is a parallel hierarchy, not a unified one.**
  `api/app/lib/vision_providers.py` duplicates the reasoning hierarchy in
  `api/app/lib/ai_providers.py`: separate `VisionProvider` ABC, separate
  per-provider classes (OpenAI / Anthropic / Ollama), separate
  `describe_image()` interface, separate `get_vision_provider` factory,
  separate validation and enumeration. Task #13 made the two share the
  **model catalog** only; they do **not** share the ADR-801 four-surface
  contract, and there is no vision equivalent of the
  per-provider-config-plus-active-pointer resolution that extraction has.

The system already runs **two** decoupled provider capabilities, not one:

- **Reasoning/extraction** resolves its active provider from
  `kg_api.ai_extraction_config` via `load_active_extraction_config()` — a
  per-provider row plus a single `active` flag (ADR-801 §2).
- **Embedding** resolves *independently* via `get_embedding_provider()`
  (ADR-039/045). A local multimodal model can serve embeddings regardless of
  which cloud provider does extraction. As the code states: "the embedder
  stays separate (delegated), as with every reasoning provider."

Vision is the third capability, but it was never given this treatment — it
was left as a hardcoded default over a parallel hierarchy.

## Decision

**Vision is a first-class provider capability, resolved independently like
embedding, under the ADR-801 uniform contract.** Concretely:

### 1. Three capability slots, one contract

A deployment selects an active provider per **capability** — reasoning,
embedding, vision — independently. All three speak the ADR-801 four-surface
contract (validate / enumerate / reasoning controls / persisted per-provider
config) and draw their model lists from the ADR-800 catalog. A provider's
*capabilities* are catalog-described: a model row's `supports_vision` flag
declares it can serve the vision slot, exactly as it already gates vision
model selection.

This mirrors the established reasoning-vs-embedding split rather than
inventing a new abstraction. Vision is decoupled from extraction the same
way embedding is: choosing OpenAI for extraction does not force OpenAI for
vision, and a locally hosted multimodal model can serve the vision slot
while a cloud provider does extraction.

**Independent does not mean different.** The slots are configured
independently but may freely **coincide on one model**. Reasoning is the
higher-capability operation and is realistically cloud here
(OpenAI / Anthropic / OpenRouter) — local hardware on this machine is not
expected to host a reasoning-grade model. Within that, three shapes are all
first-class and expressible by the same mechanism:

- **One model, both slots** — a multimodal cloud model whose catalog row has
  `supports_vision` true serves *both* the reasoning and vision slots. No
  second configuration is needed; the single model's capability flags decide
  it.
- **Two models, one provider** — vision→prose handled by a vision-capable
  model and reasoning by a stronger text model, both from the same provider.
- **Two providers** — e.g. a local multimodal model for vision→prose, a
  cloud provider for reasoning.

The per-model `supports_vision` catalog flag is precisely what lets a single
model satisfy both slots without special-casing: the vision slot resolves to
"a model that can do vision," which may be the very model the reasoning slot
already points at.

### 2. Vision resolves an active provider — never a hardcoded literal

`get_vision_provider()` resolves the provider the way extraction does:

1. Explicit per-job override (`job_data["vision_provider"]`) — unchanged.
2. Otherwise the **configured active vision provider** (its own pointer,
   parallel to extraction's `active`).
3. The chosen provider must have a `supports_vision` catalog model; if it
   does not, resolution **fails loud** with a diagnosable error naming the
   provider and the admin action that populates the catalog — consistent
   with the existing `_resolve_vision_model` "no literal fallback" stance.

The hardcoded `"openai"` default at `ingestion_worker.py` is removed. This
closes #378: the default is no longer a bare provider literal independent of
configuration, behaviour is defined when the chosen provider has no
vision-capable model, and the resolution policy is testable.

### 3. Scope boundary — vision-reasoning is decoupled; visual *embedding* is not

This ADR governs the **vision-reasoning** capability (image→prose,
`describe_image()`), and *only* that. The image ingestion path is a hairpin:
`image → prose → concepts` (`routes/ingest_image.py`). The vision slot can be
any vision-capable provider precisely **because its output is prose** — a
model-agnostic text string that rides the existing text-embedding path. By
the time anything is embedded, it is text; no cross-modal vector comparison
occurs. This is why the vision slot may be chosen as freely as the embedding
slot is chosen relative to reasoning.

The system *also* generates a **direct visual embedding** (currently Nomic
Vision v1.5, 768-dim) stored alongside the prose-derived concepts and
explicitly placed in the **same vector space as the text embeddings**. That
co-spatiality is mandatory: an image vector is only comparable to a concept
vector if both embedders share one space. The text and image embedders are
therefore **a matched pair, not independently selectable** — either one
multimodal model serves both (a multimodal profile), or a co-trained pair
(e.g. Nomic text-v1.5 ↔ vision-v1.5) whose alignment *is* the guarantee.
Mixing unrelated embedders (e.g. OpenAI `text-embedding-3` text + Nomic
vision images) puts the vectors in different spaces and makes cross-modal
similarity meaningless.

This coupling is **out of scope here** — it belongs to the embedding
**profile** abstraction (`kg_api.embedding_profile`, migration 055) and its
pending decision record (issues #321, #325). The boundary is the point:

> Independence between capability slots is permitted exactly where their
> outputs later **converge** to a common representation (reasoning and vision
> both converge to prose/concepts). Coupling is mandatory where the outputs
> **are themselves the comparison surface** (text and visual embeddings are
> compared directly as vectors, with no later convergence step).

ADR-802 sits on the "converge to prose" side; the embedding-profile decision
owns the "vectors must be co-spatial" side. Conflating them — e.g. trying to
make the visual embedder independently selectable the way the vision slot is
— reintroduces the cross-modal mismatch this boundary exists to prevent.

### 4. Convergence of the parallel hierarchy is incremental, not a rewrite

Unification is a direction, not a big-bang merge. The vision and reasoning
hierarchies converge on the **shared surfaces** they can share now — the
catalog (already shared), validation, enumeration, and per-provider config
persistence — while `describe_image()` remains a distinct capability method
(image→prose has a genuinely different request shape from text extraction,
and that distinction is intentional, not accidental drift). The end state is
one provider abstraction whose methods are capability-gated by the catalog;
the migration path retires `get_vision_provider`'s parallel validation and
config-loading in favour of the ADR-801 surfaces, capability by capability,
behind the existing factory signature.

## Consequences

### Positive

- Closes #378 and answers #379 with a single coherent model: vision is the
  third capability slot, decoupled and catalog-described.
- A local multimodal model can serve vision independently of the cloud
  extraction provider — the same flexibility embedding already has.
- No deployment silently routes image→prose to OpenAI; mis-selection fails
  loud with a diagnosable error instead of an invisible default.
- Adding a vision-capable provider becomes a connector + catalog flag, not a
  new parallel branch — the ADR-801 "connector + metadata, not surgery"
  property extends to vision.

### Negative

- A new active-vision pointer (and its admin surface) is configuration that
  did not exist before; operators now have a third capability to set,
  although it can sensibly default to "the active extraction provider if it
  has a vision model" for zero-config single-provider deployments.
- Incremental convergence means the codebase carries *both* the unified
  surfaces and the soon-to-be-retired parallel ones during migration; the
  transitional state must be clearly flagged so it is not mistaken for the
  end state.

### Neutral

- `describe_image()` stays a distinct capability method; unification is at
  the configuration/contract layer, not a forced collapse of request shapes.
- The per-job `vision_provider` override is preserved unchanged — the
  decision only changes the *default* resolution, not explicit selection.
- The vision active pointer can reuse the `ai_extraction_config` decoupled
  pattern or a parallel table; the exact schema shape is an implementation
  detail settled during #378, not by this ADR.

## Alternatives Considered

- **Vision inherits the active extraction provider** (no independent
  pointer). Rejected as the *primary* model: it couples image→prose to the
  text provider and forbids the local-multimodal-for-vision +
  cloud-for-extraction split that embedding already enjoys. Retained only as
  a sensible *default* for the vision pointer when unset.
- **Keep the parallel hierarchy, just make the default catalog-aware**
  (pick the first provider with a `supports_vision` model). Rejected: it
  patches #378 without answering #379, leaves two drifting hierarchies, and
  makes provider selection implicit/order-dependent rather than configured.
- **Big-bang merge of `vision_providers.py` into `ai_providers.py`.**
  Rejected: high-risk rewrite of the working extraction path for no
  immediate user benefit; the four-surface contract can be adopted
  incrementally behind the existing factory.
- **Leave the hardcoded `"openai"` default and document it.** Rejected:
  silently wrong on Anthropic-only / local-only deployments, the exact bug
  class ADR-801 §2–3 exists to eliminate.
</content>
</invoke>
