# Knowledge Graph API Server - Multi-stage Docker Build
#
# This Dockerfile builds a clean FastAPI server image with NO secrets baked in.
# All configuration comes from environment variables at runtime (12-Factor App).
#
# Build requirements:
#   - Docker BuildKit enabled (for mount cache support)
#   - Set DOCKER_BUILDKIT=1 or use docker-compose (BuildKit enabled by default)
#
# Runtime environment variables (no rebuild required):
#   Infrastructure secrets (from .env or Docker secrets):
#     - ENCRYPTION_KEY          # Master key for encrypting API keys (ADR-031)
#     - OAUTH_SIGNING_KEY       # JWT token signing secret (ADR-054)
#     - POSTGRES_PASSWORD       # Database admin password
#
#   Database connection:
#     - POSTGRES_HOST           # Database hostname (postgres for Docker, localhost for host)
#     - POSTGRES_PORT           # Database port (5432)
#     - POSTGRES_DB             # Database name (knowledge_graph)
#     - POSTGRES_USER           # Database user (admin)
#
#   Application config (from database, not environment):
#     - AI provider settings    # Configured via kg-operator config ai-provider
#     - Embedding settings      # Configured via kg-operator config embedding
#     - API keys (encrypted)    # Configured via kg-operator config api-key
#
# The API server reads infrastructure secrets from environment, then loads all
# application configuration from the database (configured by operator).

# Stage 1: Build stage with development dependencies
FROM python:3.13-slim AS builder

# AMD ROCm: use the dedicated Dockerfile.rocm-host with the
# rocm/pytorch official base image (selected by GPU_MODE=amd-host).
# The previous wheel-based variants (PYTORCH_VARIANT=rocm60/rocm61)
# were never published — ADR-101 update 2026-05-28 removed that path
# in favor of the single host-ROCm image.

WORKDIR /build

# Install system dependencies for building Python packages
# Use BuildKit cache for apt to speed up rebuilds
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y \
    gcc \
    libpq-dev

# Copy requirements
COPY requirements.txt .

# Install Python dependencies into a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Use BuildKit mount cache for faster rebuilds while keeping images small.
# CPU and NVIDIA hosts both use the default PyPI torch wheel (CUDA runtime
# bundled, ignored when no NVIDIA driver is present). AMD hosts should use
# Dockerfile.rocm-host instead.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    pip install -r requirements.txt

# Stage 2: Production runtime
FROM python:3.13-slim

# Build metadata (git commit, build time)
ARG GIT_COMMIT=unknown
ARG BUILD_DATE=unknown
LABEL org.opencontainers.image.revision="${GIT_COMMIT}"
LABEL org.opencontainers.image.created="${BUILD_DATE}"
LABEL org.opencontainers.image.title="Knowledge Graph API"
LABEL org.opencontainers.image.description="FastAPI server for knowledge graph system"

WORKDIR /app

# Install runtime system dependencies
# Use BuildKit cache for apt to speed up rebuilds
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y \
    libpq5 \
    curl

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY api/ /app/api/
COPY schema/ /app/schema/
# Offline backup-object oracle: the single source of truth for kg-backup/2 validation.
# Shipped so the API can load it by path for POST /admin/backup/verify. Stdlib-only /
# standalone — no api-package coupling. Copy just the one file (not the dir) to avoid
# pulling in __pycache__ and unrelated lint scripts.
COPY scripts/development/lint/lint_backup.py /app/scripts/development/lint/lint_backup.py

# Set Python path for imports (api.app.lib.*)
ENV PYTHONPATH=/app

# Pre-bake the default nomic-first embedding models (text + vision) into the
# image at /opt/hf-seed — a path OUTSIDE the runtime cache volume. The platform
# is nomic-first: local on-device embeddings (text nomic-embed-text-v1.5 768d +
# vision nomic-embed-vision-v1.5), with only reasoning/extraction calling a
# remote LLM. docker-entrypoint.sh seeds these into the mounted hf_cache volume
# on first boot, so the system runs fully OFFLINE (no HuggingFace download) —
# the precondition for an air-gapped / Raspberry-Pi appliance.
#
# We bake by LOADING (not just downloading) so the trust_remote_code dynamic
# module cache (modules/) is populated too — offline loads need it. HF_HOME is
# scoped to this RUN only; the runtime must NOT inherit it (it would bypass the
# volume). See ADR-103 (nomic-first appliance) and ADR-039.
RUN HF_HOME=/opt/hf-seed python /app/api/bake_embedding_models.py

# First-boot cache seeder (copies /opt/hf-seed into the mounted hf_cache volume)
COPY api/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Create non-root user for running the API
# Pre-create cache directory with proper ownership for volume mount
RUN useradd -m -u 1000 api && \
    chown -R api:api /app && \
    mkdir -p /home/api/.cache && \
    chown -R api:api /home/api/.cache

USER api

# Expose FastAPI port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Seed the baked model cache on first boot, then start the API. The entrypoint
# execs the CMD, so compose `command:` overrides (e.g. dev --reload) still work.
ENTRYPOINT ["docker-entrypoint.sh"]

# Start FastAPI server with uvicorn.
# Single worker: each uvicorn worker is a separate Python process and would
# load its own copy of any local embedding model (and ROCm/CUDA runtime
# context on GPU variants) — 2 workers ≈ 2× memory for no async-throughput
# gain on this workload. Ingestion runs in the queue, not the request path.
CMD ["uvicorn", "api.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
