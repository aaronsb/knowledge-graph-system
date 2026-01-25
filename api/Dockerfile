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

# GPU variant: cpu (default), rocm60, rocm61
# For AMD GPUs, set PYTORCH_VARIANT=rocm60 or rocm61
ARG PYTORCH_VARIANT=cpu

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

# Use BuildKit mount cache for faster rebuilds while keeping images small
# For ROCm variants, install PyTorch from ROCm wheel index first
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    if [ "$PYTORCH_VARIANT" = "rocm60" ]; then \
        echo "Installing PyTorch with ROCm 6.0 support..." && \
        pip install torch torchvision --index-url https://download.pytorch.org/whl/rocm6.0; \
    elif [ "$PYTORCH_VARIANT" = "rocm61" ]; then \
        echo "Installing PyTorch with ROCm 6.1 support..." && \
        pip install torch torchvision --index-url https://download.pytorch.org/whl/rocm6.1; \
    fi && \
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

# Set Python path for imports (api.app.lib.*)
ENV PYTHONPATH=/app

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

# Start FastAPI server with uvicorn
# Note: Uses --reload for development hot reload (disable in production)
CMD ["uvicorn", "api.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
