---
status: Draft
date: 2026-07-01
deciders:
  - aaronsb
  - claude
related:
  - ADR-804
  - ADR-715.1
---

# ADR-508: Configurable Search Similarity Threshold

## Context

Semantic search returns noisy results: nonsense queries match real concepts.
Empirically, `kg search query "asdfgh qwerty zxcvb"` (random characters) returns
concepts, and every query — relevant or not — tops out around the same score.

### Root cause (measured)

The active embedding profile is **`nomic-ai/nomic-embed-text-v1.5`** (768-dim,
local provider; `kg_api.embedding_profile`, ADR-804). Measuring cosine similarity
directly against the live model:

| Query kind | cosine (max) |
|---|---|
| Gibberish vs domain concepts | ~0.47–0.51 |
| Relevant query ("application security") vs domain concepts | ~0.60–0.65 |

The scoring path is correct — proper cosine over L2-normalized vectors
(`api/app/lib/age_client/query.py`), no rescaling. The high floor is **inherent to
this embedding model**: nomic v1.5 has a compressed cosine distribution where even
out-of-distribution text sits at ~0.5.

The defect is therefore **calibration, not computation**: the clients disagree on
the threshold and one of them sits *below the model's noise floor*.

| Client | default `min_similarity` | effect on nomic v1.5 |
|---|---|---|
| API model (`models/queries.py`) | 0.7 | too high — relevant queries return 0 |
| CLI (`kg search`) | 0.7 | same |
| FUSE (`kg-fuse`, ADR-715.1) | 0.5 | too low — **below the ~0.5 gibberish floor**, so noise passes |

The "right" threshold (~0.55–0.60 for this model) is **model- and corpus-dependent**.
Hardcoding it in three clients is what produced the split-brain behavior. It belongs
in configuration.

### Related finding (deferred, not this ADR's fix)

The nomic task prefixes (`search_query:` / `search_document:`) are configured in the
profile but **never applied**: `_embed_sentence_transformers`
(`api/app/lib/embedding_model_manager.py`) gates on the configured strings, then
applies them via sentence-transformers `prompt_name` — but the model's named prompts
are empty strings, so `prompt_name="query"` is a no-op (verified: prefixed and
unprefixed embeddings are identical). Applying the prefixes correctly requires
re-embedding the corpus (query and document spaces must match). Measured on
real-domain text, correct prefixes were **neutral-to-slightly-worse** for separation,
so fixing this does **not** address the noise problem and is out of scope here. See
Phase 2 / a future embedding-correctness ADR.

## Decision

Introduce a single server-side, runtime-configurable default similarity threshold,
stored in the existing `kg_api.platform_config` key-value table (migration `031`),
and have clients **inherit** it rather than hardcode their own.

1. **Storage.** Seed `search_default_similarity_threshold` (default **`0.6`**, chosen
   from the measurements above) via a new migration, using the existing
   `set_platform_config` / `get_platform_config` helpers. Plaintext (non-secret),
   consistent with other `platform_config` entries.

2. **API.** `SearchRequest.min_similarity` becomes `Optional[float]` (default `None`).
   When a request omits it, `/query/search` reads the configured default from
   `platform_config` (falling back to `0.6` if unset). An admin-gated endpoint
   (`require_permission(...)`, per the `admin.py` convention) exposes GET/PUT of the
   value.

3. **Clients inherit.** CLI (`kg search`) and FUSE both change their default from a
   hardcoded number to "unset", so an omitted flag inherits the server default. This
   supersedes the FUSE `0.5` constant (ADR-715.1) and the CLI/API `0.7`. Explicit
   `--min-similarity` / `.meta/threshold` still override per query.

4. **Surfaces.** The value is settable via `operator/configure.py platform-config`
   (already supports it), the new admin API, `kg config`, and a web settings surface.

Phased delivery: **Phase 1** = schema + API + CLI + FUSE + web (this ADR). **Phase 2**
= the prefix-application fix + corpus re-embed, gated on a real before/after
separation eval (separate ADR).

## Consequences

### Positive

- One place to tune search precision per deployment; ends the split-brain 0.5/0.7 defaults.
- Operators can raise/lower the floor to match their embedding model and corpus without a redeploy.
- FUSE `mkdir` auto-adjust (ADR-715.1) becomes meaningfully useful: with the default at 0.6, zero-result cases occur and queries auto-tune down to where real matches live.
- No new tables or mechanisms — reuses `platform_config`, `configure.py`, RBAC admin endpoints.

### Negative

- `min_similarity` becoming optional touches the API model and every client default; care needed so scripts passing explicit values are unaffected.
- A per-deployment default can be mis-set (too high → empty results; too low → noise). Mitigated by the FUSE auto-adjust hint and a sane seed.

### Neutral

- Does not change the embedding model or scoring math. The nomic floor remains; the threshold is calibrated around it.
- The prefix no-op bug remains until Phase 2.

## Alternatives Considered

- **Hardcode a higher default (~0.6) in each client.** Rejected: perpetuates split-brain defaults and can't be tuned per deployment/model.
- **Fix the nomic prefixes + re-embed as the primary fix.** Rejected as the primary lever: measured separation was neutral-to-worse; it's a correctness improvement, not the noise fix. Deferred to Phase 2, evidence-gated.
- **Switch to a wider-range embedding model** (e.g. the inactive `text-embedding-3-small` profile). Viable but orthogonal and heavier (external provider, re-embed); the config surface makes the threshold tunable regardless of model, and model choice stays a separate `embedding_profile` decision (ADR-804).
- **Per-ontology thresholds.** Deferred: start with one global default; the key-value store can grow scoped keys later if needed.
