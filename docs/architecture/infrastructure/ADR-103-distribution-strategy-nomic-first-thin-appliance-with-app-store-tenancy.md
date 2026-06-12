---
status: Proposed
date: 2026-06-11
deciders:
  - aaronsb
  - claude
related:
  - ADR-039
---

# ADR-103: Distribution strategy: nomic-first thin appliance with app-store tenancy

## Context

The system is fully containerized and managed by `operator.sh` (an apt-style
lifecycle tool) with a standalone `install.sh` for production deployment.
Despite this, the single biggest constraint on broader adoption is **distribution**:
standing the platform up requires the operator to understand Docker, Compose,
`operator.sh`, provider configuration, and secret generation. That is a steep
funnel for a system that is otherwise self-contained.

"Distribution" is not one problem but four, and they have different solutions:

| Axis | What it means | Solved by an appliance? |
|------|---------------|-------------------------|
| **Install friction** | Docker/Compose/operator literacy required | Yes — flash, boot, paste a key |
| **Discovery** | People finding the project at all | No — needs to live where self-hosters browse |
| **Update lifecycle** | Keeping deployed instances current | Partly — `operator.sh upgrade` is already proto-OTA |
| **Support surface** | Variance across host environments | Mixed — known-good env helps; tenant management adds surface |

A naive "ship it all as one VM" framing hides a fork. A **fat appliance** bakes
images + data into a frozen VM image (truly offline, but fights the existing
pull-based `operator.sh upgrade` lifecycle and ships multi-GB images per
release). A **thin appliance** ships a minimal host with Docker + `operator.sh`
preinstalled and pulls images on first boot (keeps the incremental update story,
needs network on first boot). For a system whose deployment philosophy is
already "pull images, migrate, restart," the thin model is the natural fit.

Two technical facts shape the strategy:

1. **The embedding/reasoning split is already a code path, not a thing to
   build.** `LocalEmbeddingProvider` does on-device embeddings via
   sentence-transformers and explicitly cannot extract (ADR-039). Concept
   *extraction/reasoning* is a separate provider path that calls a remote LLM.
   This lets the appliance own the cheap, private, edge-friendly compute
   (embeddings, vector similarity, graph storage — the user's data) while
   farming out only document chunks to a cloud LLM for extraction.

2. **Multi-arch images are already produced.** `publish.sh` runs
   `docker buildx --platform linux/amd64,linux/arm64`, auto-enabled on
   `release`/`main`. An ARM64 target (Raspberry Pi 4GB+, Home Assistant OS
   style) is feasible because the CPU/RAM profile fits when reasoning is remote
   and embeddings use a small local model.

A target deployment is a Raspberry-Pi-class appliance (HAOS-like): a flashable
image that runs the containers, does embeddings on-device, and only reaches out
for reasoning. Local inference for *reasoning* (e.g. vLLM passthrough) is
explicitly out of scope — if a user wants it, that is their own add-on
container, not a core responsibility.

## Decision

Adopt a **staged, thin-appliance distribution strategy** with a **nomic-first
local-embedding invariant**, and **defer** building a bespoke supervisor OS.

**Invariant — nomic-first, reasoning-remote.** The out-of-the-box embedding
model is the local `nomic-ai/nomic-embed-text-v1.5` profile (768-dim,
on-device, no API key). Cloud OpenAI embeddings remain a one-command
alternative but are no longer the default. Reasoning/extraction continues to
require a remote LLM provider. This makes the appliance self-contained for the
private/edge half of the workload and means a fresh install needs a cloud key
*only* for extraction, never for embeddings. Both default models — text
(`nomic-embed-text-v1.5`) **and** vision (`nomic-embed-vision-v1.5`, loaded via
the profile's image slot) — are baked into the API image at build time so the
platform boots without a runtime HuggingFace download, the precondition for an
offline / air-gapped / Pi appliance.

**Cache-topology constraint (non-obvious).** The HF cache path
(`~/.cache/huggingface`) sits under a mounted volume (`hf_cache ->
/home/api/.cache`) in every compose variant. Weights baked *directly* into that
path are shadowed by the empty volume on first boot, re-triggering the download.
So the image bakes both models into a path *outside* the volume (`/opt/hf-seed`,
loaded — not merely downloaded — so the `trust_remote_code` dynamic-module cache
is populated too), and a first-boot entrypoint (`docker-entrypoint.sh`) copies
them into the live cache with `cp -n` (preserving any model a user later
switches to or adds). This keeps the deliberate persistent-cache design intact
while guaranteeing offline first boot.

The bake and seed live in **shared scripts** (`api/bake_embedding_models.py` +
`api/docker-entrypoint.sh`) invoked by *every* published image variant — the
standard CPU/x86/arm64/NVIDIA `api/Dockerfile` (runs as `api`, seeds the cache
volume) and the AMD `api/Dockerfile.rocm-host` (runs as root, seeds `$HOME`).
This was learned the hard way: an inline bake added only to `api/Dockerfile`
silently skipped the ROCm image, which kept re-downloading at runtime. One
source of truth for the model list is the only way the variants stay in lockstep.

**Staged distribution path:**

1. **Stage 1 — app-store tenancy.** Publish to existing self-host platforms
   (Portainer template, CasaOS, Umbrel, TrueNAS SCALE app, Proxmox helper
   script, Home Assistant add-on). These are *already* "an appliance OS that
   manages container tenants." Being a tenant solves discovery **and** install
   at a fraction of the cost of authoring an OS. Lowest effort, highest leverage.

2. **Stage 2 — thin appliance images.** Ship prebuilt OVA/qcow2 + an arm64 Pi
   image: a minimal host with Docker + `operator.sh` preinstalled, nomic
   weights baked, reasoning cloud-only. Still thin — updates flow through the
   existing `operator.sh upgrade` pull lifecycle, not whole-image replacement.

3. **Stage 3 — supervisor model (deferred).** Becoming our own appliance OS
   with a first-class add-on model (e.g. user-supplied vLLM-passthrough
   container) is explicitly out of scope for now. We only **preserve the seam**:
   keep `operator.sh` add-on-shaped so the door stays open if demand proves out.

This ADR records the strategy and the nomic-first invariant. The nomic-first
flip is implemented on branch `survey/nomic-first-defaults` (seed migrations
003/008, mig-012 fallback, Dockerfile bake, mock/test dimension alignment,
operator-help/API-doc defaults).

## Consequences

### Positive

- Collapses install friction to "flash, boot, paste a reasoning key" on the
  HAOS adoption curve.
- App-store tenancy (Stage 1) hits discovery + install together without the
  multi-year cost of building an OS.
- The nomic-first invariant makes the appliance self-contained for embeddings
  and keeps the private graph local; only document chunks leave the box.
- Keeps the existing pull-based `operator.sh upgrade` lifecycle intact (thin,
  not fat) — no multi-GB per-release image churn.
- Reuses code paths that already exist (LocalEmbeddingProvider, multi-arch
  buildx) rather than introducing new architecture.

### Negative

- Baking both default models (text ~275MB + vision) adds several hundred MB to
  the API image, including for cloud-only deployments that will not use local
  embeddings, and first boot pays a one-time seed-copy into the cache volume.
  A build ARG to opt out of baking is a possible later refinement.
- Local 768-dim and OpenAI 1536-dim embeddings are incompatible vector spaces;
  the appliance standardizes on 768 and switching costs a full re-embed.
- A thin appliance still needs network on first boot to pull images (only the
  embedding model is offline); true air-gap remains a separate, later effort.
- App-store tenancy adds per-platform packaging/maintenance surface (Portainer
  vs CasaOS vs HA add-on manifests).

### Neutral

- ARM64 viability depends on two upstream images having arm64 variants —
  see open gates below.
- Stage 3 deliberately leaves the supervisor/add-on model unbuilt; this is a
  recorded non-goal, not an oversight.
- No deployed environments exist yet, so the seed-default flip is a direct
  migration edit rather than a forward reconciliation migration.

## Open Questions / Verification Gates

- **AGE arm64**: the Postgres+AGE image is pinned to a SHA digest
  (`apache/age@sha256:e7de17…`). Confirm that build publishes an arm64 variant,
  or repin/rebuild.
- **Garage arm64**: `dxflrs/garage:v1.0.0` — Garage is an edge/self-host
  product so arm64 almost certainly exists; verify.
- **Pi RAM budget**: validate Postgres+AGE + Garage + API + nomic (~400MB
  loaded) fit comfortably in 4GB under real ingestion.
- **Offline boot** ✅ *verified 2026-06-11* (AMD ROCm image, `Dockerfile.rocm-host`):
  a freshly built image seeded `/opt/hf-seed` into the runtime cache and loaded
  both text + vision models with logs showing "Loaded from local cache" and zero
  download lines. The appliance offline precondition holds on real hardware.
- **QEMU bake**: confirm the bake step (which *loads* both models, populating the
  dynamic-module cache) completes when building the arm64 image under emulation.

## Alternatives Considered

- **Fat VM appliance** (bake images + data into a frozen VM). Rejected as the
  default: fights the pull-based upgrade lifecycle, ships multi-GB images per
  release, and only earns its weight for a hard air-gapped requirement that no
  user has yet.
- **Build our own supervisor OS now** (HAOS from scratch). Rejected for now:
  multi-year effort; existing self-host app stores already provide the
  container-tenant substrate. Deferred to Stage 3, seam preserved.
- **Keep OpenAI-embedding default, add appliance packaging only.** Rejected:
  would force every appliance to carry a cloud embedding key and send all
  content out for embeddings, defeating the private/edge value proposition.
- **Local reasoning in-appliance (bundled vLLM/Ollama).** Rejected as a core
  responsibility: GPU passthrough into a VM/Pi is host-specific and fragile;
  left to user-supplied add-on containers.
