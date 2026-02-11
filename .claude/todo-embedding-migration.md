# Embedding System Migration Plan

**Issue:** #313 (image ingestion fails with NomicVisionModel AttributeError)
**Branch:** `fix/313-nomic-vision-attributeerror`
**Date:** 2026-02-10

## Root Cause

Nomic Vision v1.5 uses `trust_remote_code=True` to load custom model classes from
HuggingFace Hub. These classes are not maintained for transformers 5.x:

1. `all_tied_weights_keys` AttributeError — model loading crashes
2. Non-persistent buffers (rotary position embeddings) silently corrupted to NaN
3. No native transformers integration planned (HF issue #30995 still open)

This is not a pinnable bug — it's a structural incompatibility between Nomic's
custom code and transformers 5.x's `from_pretrained` initialization changes.

## Decision: Multi-backend embedding system

Support multiple embedding backends with priority fallback:

| Priority | Backend | Text | Vision | Native transformers | License |
|----------|---------|------|--------|--------------------|---------|
| 1 | **SigLIP 2** (Google) | Yes | Yes | Yes (no trust_remote_code) | Apache 2.0 |
| 2 | **Nomic v1.5** (pinned) | Yes | Yes | No (trust_remote_code) | Apache 2.0 |
| 3 | **API-based** (OpenAI, etc) | Yes | Varies | N/A | Commercial |

SigLIP 2 variants:
- `siglip2-base-patch16-224` — 86M params, 768-dim embeddings (closest to Nomic's 92M/768)
- `siglip2-so400m-patch14-384` — 400M params, 1152-dim embeddings (higher quality)

## Implementation phases

### Phase 1: Immediate fix — pin transformers for Nomic compat
- [ ] Pin `transformers>=4.41.0,<5.0` in requirements.txt
- [ ] Verify Nomic text + vision both work on transformers 4.57.x
- [ ] Rebuild and publish API container
- [ ] Close #313

### Phase 2: Embedding backend abstraction
- [ ] Create `api/app/lib/embedding_backends/` package
  - `base.py` — abstract interface: `embed_text()`, `embed_image()`, `embed_dimension()`
  - `siglip.py` — SigLIP 2 backend (text + vision, native transformers)
  - `nomic.py` — Nomic v1.5 backend (text + vision, pinned transformers)
  - `api_openai.py` — OpenAI API backend (text only)
- [ ] Config in operator: `embedding_backend: siglip2 | nomic | openai`
- [ ] Backend auto-detection: try SigLIP first, fall back to Nomic, then API
- [ ] Migrate `visual_embeddings.py` and `embedding_model_manager.py` to use backends

### Phase 3: SigLIP 2 integration
- [ ] Add SigLIP 2 model loading (no trust_remote_code needed)
- [ ] Validate embedding quality vs Nomic benchmarks (reproduce ADR-057 tests)
- [ ] Validate cross-modal search: text query "green parrot" finds parrot images
- [ ] Validate clustering quality matches Nomic's 0.847 avg top-3 similarity
- [ ] Update device_selector.py for SigLIP model variants
- [ ] HuggingFace model cache management (persistent volume)

### Phase 4: Re-encoding migration
- [ ] Use existing re-encoding worker to migrate all embeddings
- [ ] Store embedding backend name + version on each concept/source node
- [ ] Migration path: Nomic 768-dim → SigLIP 768-dim (base) or 1152-dim (so400m)
- [ ] If dimension changes, update pgvector index configuration
- [ ] Operator command: `./operator.sh shell` → `configure.py embedding-backend`

### Phase 5: Remove transformers pin
- [ ] Once SigLIP is default and validated, remove `<5.0` pin
- [ ] Keep Nomic backend available but document it requires transformers 4.x
- [ ] Or: vendor Nomic model code locally if we want both on transformers 5.x

## Non-implementation items

### Attribution / licensing dialog
- [ ] Design a "system status" page in web UI with technology attributions
- [ ] Scrollable credits list (like game credits or About dialog)
- [ ] Include all open-source dependencies with license types:
  - Apache AGE (Apache 2.0)
  - SigLIP 2 / Google (Apache 2.0)
  - Nomic Embed (Apache 2.0)
  - PyTorch (BSD)
  - HuggingFace Transformers (Apache 2.0)
  - FastAPI (MIT)
  - React / Next.js (MIT)
  - Garage S3 (AGPL-3.0)
  - pgrx (MIT)
  - And others from requirements.txt, package.json, Cargo.toml
- [ ] Auto-generate from dependency manifests where possible
- [ ] Include model cards / research paper citations for AI models
- [ ] Accessible from web UI footer and `kg health --verbose`

### ADR
- [ ] Write ADR documenting embedding backend decision
- [ ] Reference ADR-057 (original Nomic vision research)
- [ ] Document quality validation methodology
- [ ] Document migration path and rollback strategy

## Research notes

**SigLIP 2 key facts:**
- Google DeepMind, Apache 2.0, fully open weights
- Native transformers support (no trust_remote_code)
- `get_text_features()` and `get_image_features()` in shared vector space
- Base model (86M) produces 768-dim — same as Nomic, drop-in dimension match
- Uses sigmoid loss (not softmax like CLIP) — better for retrieval
- Multilingual text encoder (Gemma tokenizer)
- Available via `AutoModel.from_pretrained("google/siglip2-base-patch16-224")`

**Nomic v1.5 key facts:**
- 92M vision + 137M text, Apache 2.0
- 768-dim shared text/vision space
- Requires `trust_remote_code=True` — broken on transformers 5.x
- No native transformers integration planned
- 0.847 avg top-3 similarity in our ADR-057 research

**Why not Jina v4:**
- 3.8B params — too large for local inference on most hardware
- Also requires `trust_remote_code=True`
