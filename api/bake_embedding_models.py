"""Pre-bake the default nomic-first embedding models into a Docker image layer.

Single source of truth for which models are baked, invoked at build time by
BOTH `api/Dockerfile` (CPU / x86 / arm64 / NVIDIA) and `api/Dockerfile.rocm-host`
(AMD ROCm). Keeping it in one script means the image variants cannot drift —
an earlier copy-paste bake lived only in api/Dockerfile and silently skipped the
ROCm image, so AMD builds re-downloaded at runtime. See ADR-103 (nomic-first
appliance) and ADR-804 (local embedding service).

The models are LOADED, not merely downloaded, so the `trust_remote_code`
dynamic-module cache (HF_HOME/modules) is populated too — offline loads need it.
Loading runs on CPU at build time (no GPU is mounted during `docker build`),
which is fine: this only warms the cache.

Set HF_HOME to the seed directory before running, e.g.:
    HF_HOME=/opt/hf-seed python api/bake_embedding_models.py

A first-boot entrypoint (api/docker-entrypoint.sh) then copies the seed into the
live HuggingFace cache, so the platform boots fully offline.
"""

# Default nomic-first models. Mirror of the seeds in schema/migrations/008
# (text) and the profile image slot in migration 055 (vision). If those change,
# change these together.
#
# NOTE: we bake the default (unpinned) HuggingFace revision. The runtime loader
# passes the profile's text_revision/image_revision. Today both are NULL/"main"
# so they agree and the baked cache is hit offline. If a pinned revision is ever
# introduced in the embedding profile, pin the SAME revision here too — otherwise
# the runtime requests a revision the baked cache lacks and tries to download,
# breaking offline boot.
TEXT_MODEL = "nomic-ai/nomic-embed-text-v1.5"
VISION_MODEL = "nomic-ai/nomic-embed-vision-v1.5"


def bake_text(model_name: str) -> None:
    """Warm the sentence-transformers cache for the default text model."""
    from sentence_transformers import SentenceTransformer

    print(f"[bake] text: {model_name}", flush=True)
    SentenceTransformer(model_name, trust_remote_code=True)


def bake_vision(model_name: str) -> None:
    """Warm the transformers AutoModel + AutoProcessor cache for the vision model."""
    from transformers import AutoModel, AutoProcessor

    print(f"[bake] vision: {model_name}", flush=True)
    AutoModel.from_pretrained(model_name, trust_remote_code=True)
    AutoProcessor.from_pretrained(model_name, trust_remote_code=True)


def main() -> None:
    """Bake every default embedding model into the current HF_HOME cache."""
    bake_text(TEXT_MODEL)
    bake_vision(VISION_MODEL)
    print("[bake] done — text + vision models cached", flush=True)


if __name__ == "__main__":
    main()
