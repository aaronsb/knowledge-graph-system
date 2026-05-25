---
status: Accepted
date: 2026-05-24
deciders:
  - aaronsb
  - claude
related:
  - ADR-039
  - ADR-086
  - ADR-100
---

# ADR-101: ROCm Image Variant and Install-Time Selection

## Context

Issue #405 reports that `./operator.sh init` advertises an "AMD ROCm" path
but the resulting platform fails to ingest. The startup log claims "Falling
back to API-based embeddings" while the active embedding profile is still
`local`, and every concept then fails with `Embedding model not loaded. Call
load_model() first.` — a silent-broken state that looks fixed but isn't.

The root cause is image packaging, not configuration code:

- The published `kg-api:latest` image is built from `api/Dockerfile` with
  `PYTORCH_VARIANT=cpu` (the default). That step runs
  `pip install -r requirements.txt`, which pulls torch from the default
  PyPI index. **The default PyPI torch wheel bundles a CUDA runtime
  (`+cuXXX`).** That works on hosts with NVIDIA drivers and on hosts with
  no GPU at all (`torch.cuda.is_available()` → False, CPU path is taken).
  It does **not** work on AMD ROCm — ROCm PyTorch is a separate wheel
  (`+rocmYY`) only available from
  `https://download.pytorch.org/whl/rocmYY`.
- The operator wizard sets `embedding_profile.device = 'cuda'` for both
  `amd` and `amd-host` modes (`operator/lib/guided-init.sh:359`). On a
  CUDA-built torch this raises `Found no NVIDIA driver on your system`;
  on a ROCm-built torch the same value works because ROCm PyTorch reuses
  the `torch.cuda` API.

The codebase already contains every piece needed to *build* an image that
works on ROCm — they have simply never been published.

| Asset | Purpose |
|---|---|
| `api/Dockerfile` with `ARG PYTORCH_VARIANT=cpu\|rocm60\|rocm61` | Builds an image that installs PyTorch from a ROCm wheel index. |
| `api/Dockerfile.rocm-host` | Layered on `rocm/pytorch:rocm7.1_ubuntu24.04_py3.13_pytorch_release_2.9.1` — ROCm comes from the base image. |
| `docker/docker-compose.gpu-amd.yml` | Sets `PYTORCH_VARIANT: ${ROCM_VERSION:-rocm60}` as a build arg, plus `/dev/kfd` + `/dev/dri` + `video` group. |
| `docker/docker-compose.gpu-amd-host.yml` | Builds `Dockerfile.rocm-host`, plus `privileged: true` and `ipc: host` for ROCm 7.x HSA init. |
| `operator/lib/common.sh:148-156` | Selects the right overlay based on `GPU_MODE`. |
| `operator/lib/guided-init.sh:218-225` | Wizard options 3 (`amd`) and 4 (`amd-host`). |

All of this works under `./operator.sh init` *when the user has a local
source checkout and we let `docker compose build` run* — but the standalone
install path (`docker-compose.ghcr.yml`, used by `install.sh`) pulls
`kg-api:latest` and never builds, so the ROCm Dockerfile paths never
execute.

Two AMD modes exist because they target different ROCm generations:

- **`amd`** — ROCm 6.0 / 6.1 wheels installed via pip from the PyTorch
  ROCm index. The image carries ROCm libraries pinned to whichever wheel
  was chosen at build time.
- **`amd-host`** — ROCm 7.1 via AMD's official `rocm/pytorch` base image.
  Used for distros (Arch, recent Ubuntu) where ROCm 7.x is the platform.
  Higher-overhead image but tracks AMD's official build.

These cannot be unified into one image — they pin different ROCm runtime
versions — so we publish multiple variant tags rather than try to autodetect
at startup.

## Decision

We publish ROCm variants of `kg-api` to GHCR alongside the existing default
tag, and the operator selects the right tag at install time based on the
user's hardware choice.

### Image tags

| Tag | Built from | Torch source | Target |
|---|---|---|---|
| `kg-api:latest` (unchanged) | `api/Dockerfile`, `PYTORCH_VARIANT=cpu` | Default PyPI torch (bundles CUDA runtime) | CPU and NVIDIA hosts |
| `kg-api:rocm60` | `api/Dockerfile`, `PYTORCH_VARIANT=rocm60` | `https://download.pytorch.org/whl/rocm6.0` | ROCm 6.0 hosts |
| `kg-api:rocm61` | `api/Dockerfile`, `PYTORCH_VARIANT=rocm61` | `https://download.pytorch.org/whl/rocm6.1` | ROCm 6.1 hosts |
| `kg-api:rocm72-host` | `api/Dockerfile.rocm-host` | `rocm/pytorch:rocm7.2.3_ubuntu24.04_py3.12_pytorch_release_2.9.1` | ROCm 7.x hosts (Arch, modern Ubuntu) |

**NVIDIA support is preserved.** `kg-api:latest` is built from `PYTORCH_VARIANT=cpu`,
which in this Dockerfile means "install torch from the default PyPI index" —
and that wheel ships with the CUDA runtime bundled (the `+cuXXX` build seen
in issue #405's repro). On a host with NVIDIA drivers,
`torch.cuda.is_available()` returns True and the model loads on the GPU.
On a CPU-only host, the same image works (CUDA libs idle). NVIDIA users
get no operator changes, no new flags, no new image tags — they continue
on `latest` exactly as today.

Versioned aliases follow the same pattern: `kg-api:0.13.1`,
`kg-api:0.13.1-rocm60`, `kg-api:0.13.1-rocm61`, `kg-api:0.13.1-rocm72-host`.

**Naming convention**: the suffix is the **base image's** ROCm version. For
wheel-index variants (`rocm60`, `rocm61`) it's the wheel's ROCm version.
For host-mounted variants (`rocm72-host`) it's the base image's ROCm
version — which should match the operator's host ROCm major.minor as
closely as possible. When AMD ships an updated base image (e.g.
`rocm7.3.x`), a new variant tag (`rocm73-host`) is added rather than
overloading the existing tag — keeps tags immutable in meaning.

ROCm variants are **single-arch (`linux/amd64`) only**. AMD ROCm has no
production-quality `arm64` build path. arm64 users get the CPU image, which
works because the default PyPI wheel ships an arm64 variant with no CUDA
runtime.

### Operator selection

`docker/docker-compose.ghcr.yml` becomes parametric:

```yaml
api:
  image: ghcr.io/aaronsb/knowledge-graph-system/kg-api:${KG_API_IMAGE_TAG:-latest}
```

`operator/lib/common.sh` exports `KG_API_IMAGE_TAG` based on `GPU_MODE`:

| `GPU_MODE` | `KG_API_IMAGE_TAG` |
|---|---|
| `amd` | `rocm60` (default) or `rocm61` if `ROCM_VERSION=rocm61` |
| `amd-host` | `rocm72-host` |
| `nvidia` / `mac` / `cpu` / unset | `latest` |

The `.operator.conf` file gains an optional `KG_API_IMAGE_TAG=` line for
explicit overrides; if absent, the mapping above applies. This keeps a
single GHCR compose file and avoids a fan-out of `docker-compose.ghcr-*.yml`
overlays.

### Publish flow

`publish.sh images` continues to publish `kg-api:latest` (unchanged
default). A new target group, `api-rocm`, publishes the three ROCm variants
in one invocation:

```bash
./publish.sh images-rocm                      # default-variants only (rocm72-host)
./publish.sh images-rocm rocm60 --force       # opt into a deferred wheel variant
./publish.sh images-rocm rocm72-host rocm60 --force  # explicit subset
```

ROCm variants build locally only (consistent with the CLAUDE.md
"build strategy: local builds are faster than GHA runners" stance). The
publish flow runs `docker build` with the `PYTORCH_VARIANT` build arg, then
pushes the tag. No CI changes required.

### Embedding device mapping stays `cuda` for AMD

The mapping at `operator/lib/guided-init.sh:359` is **correct in spirit**
— ROCm PyTorch presents through the `torch.cuda` API, so `device='cuda'`
on a ROCm-built image will pick the ROCm device. It only failed before
because the wrong torch wheel was in the image. With this ADR's image
selection wired up, that mapping does the right thing end-to-end and no
operator-side change is needed.

### Honest CPU fallback at startup (separate but related)

A separate change — landed in the same PR as this ADR draft — makes the
API attempt an in-process CPU fallback when `load_model()` fails because
the requested device is unavailable. That removes the "Falling back to
API-based embeddings" lie at `api/app/main.py:199` and ensures that users
who pick the wrong ROCm variant get a degraded-but-working install instead
of a silent-broken one. The ROCm image work and the fallback work are
independent: the fallback is correct behavior even with no ROCm images
published.

## Consequences

### Positive

- AMD ROCm users can run the standalone installer (`install.sh` →
  `./operator.sh init` → choose AMD) and get a working platform without
  cloning the repo to build locally.
- The "silent broken" state from issue #405 disappears for the canonical
  paths.
- Tag scheme generalizes: if a future ROCm 7.0 wheel-based variant
  appears, it slots in as `kg-api:rocm70` with no operator-side changes.

### Negative

- Three additional `kg-api` images (~3–5 GB each on disk, smaller as
  registry blobs but still substantial) increase release time and GHCR
  storage. Acceptable given ROCm is opt-in — most releases will skip
  `api-rocm` and publish only on AMD-relevant changes.
- ROCm 7.x via host mode (`amd-host`) requires `privileged: true` and
  `ipc: host` (from `gpu-amd-host.yml`). This is a docker compose
  privilege escalation that some hardened deployments will reject. ROCm 6
  via `amd` mode does not need either; that's the lower-privilege
  fallback.
- AMD users with the *wrong* ROCm runtime version (host has 6.1, picked
  `rocm60` image — or vice versa) will still hit a device-load failure.
  The CPU fallback (separate change) absorbs this failure cleanly, but
  the user does not get GPU acceleration until they re-init with the
  matching variant. Wizard hint added.
- The visual embedding generator (`api/app/lib/visual_embeddings.py`,
  initialized at `main.py:202-211`) has the same "user picks
  unavailable accelerator" surface but is **not** addressed in this
  ADR's first PR. Its failure mode is less severe (no global-pollution
  bug; visual embeddings are opt-in via the profile's image config)
  and #405 only names the text path. Follow-up: extend the CPU fallback
  in `init_visual_embedding_generator` once the text-path approach is
  shipped and verified on the ROCm 7900 XTX target.

### Neutral

- The release flow gains a maintainer judgment call: "does this release
  touch anything ROCm-relevant?" If no, skip `api-rocm`. If yes, run it.
  Documented in `publish.sh` help text.
- Versioned ROCm tags `kg-api:0.13.1-rocm60` mean we never overwrite a
  ROCm variant for a released version — same immutability story as the
  default tag.
- arm64 hosts get no ROCm option. This is a ROCm-side limitation, not a
  decision we're making; documenting it explicitly so it's not a surprise.

## Alternatives Considered

### One fat image with every PyTorch variant

Reject: image would be ~15 GB+, defeats the registry-pull install model,
and PyTorch builds are mutually exclusive in a single Python env (only
one `torch` install at a time).

### Run-time wheel download — image stays small, fetches the right torch on first boot

Reject: introduces a network dependency at startup, fails for airgapped
installs, and turns a fast container start into a multi-minute wheel
download. Also moves a build-time concern (which torch?) into the runtime
codepath where it's harder to debug.

### Detect ROCm at startup and refuse to start if image variant is wrong

Reject: helpful for diagnostics, but doesn't make AMD installs work — the
fallback to CPU does. Worth adding as a *log line* alongside the CPU
fallback, but not as a hard gate.

### Build ROCm variants in CI (GitHub Actions) rather than locally

Reject (for now): ROCm wheel installs are heavy and slow even on local
hardware; GHA runners are slower still and have no ROCm hardware to test
against anyway. Re-evaluate if a maintainer without ROCm hardware needs to
ship variants.

### Drop ROCm support and document "CPU only on AMD"

Reject: the platform already has working `amd-host` and `amd` paths from
a local build; users with AMD hardware reasonably expect the published
images to support them too. The marginal cost of publishing variants is
worth the marginal user.
