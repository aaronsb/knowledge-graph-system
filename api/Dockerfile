# Knowledge Graph API Server - Multi-stage Docker Build
#
# This Dockerfile builds a clean FastAPI server image with NO secrets baked in.
# All configuration comes from environment variables at runtime (12-Factor App).
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
FROM python:3.11-slim AS builder

WORKDIR /build

# Install system dependencies for building Python packages
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies into a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Production runtime
FROM python:3.11-slim

WORKDIR /app

# Install runtime system dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY api/ /app/api/
COPY schema/ /app/schema/

# Set Python path for imports (api.api.lib.*)
ENV PYTHONPATH=/app

# Create non-root user for running the API
RUN useradd -m -u 1000 api && \
    chown -R api:api /app

USER api

# Expose FastAPI port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Start FastAPI server with uvicorn
# Note: Uses --reload for development hot reload (disable in production)
CMD ["uvicorn", "api.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
