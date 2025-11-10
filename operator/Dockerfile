# Knowledge Graph Operator - Docker Build
#
# Build requirements:
#   - Docker BuildKit enabled (for mount cache support)
#   - Set DOCKER_BUILDKIT=1 or use docker-compose (BuildKit enabled by default)

FROM python:3.11-slim

# Build metadata (git commit, build time)
ARG GIT_COMMIT=unknown
ARG BUILD_DATE=unknown
LABEL org.opencontainers.image.revision="${GIT_COMMIT}"
LABEL org.opencontainers.image.created="${BUILD_DATE}"
LABEL org.opencontainers.image.title="Knowledge Graph Operator"
LABEL org.opencontainers.image.description="Platform configuration and lifecycle management"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Docker CLI for container management via socket
    docker.io \
    # PostgreSQL client for database operations
    postgresql-client \
    # curl for health checks
    curl \
    # Build tools for Python packages
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create working directory
WORKDIR /workspace

# Copy Python requirements (operator needs subset of API dependencies)
COPY operator/requirements.txt /workspace/operator/requirements.txt
# Use BuildKit mount cache for faster rebuilds while keeping images small
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r operator/requirements.txt

# Copy operator scripts and tools
COPY operator/ /workspace/operator/

# Copy API library code (operator imports from api.api.lib.*)
# Only copy what's needed for configuration, not the full API server
COPY api/api/lib/ /workspace/api/api/lib/
COPY api/api/__init__.py /workspace/api/api/__init__.py

# Copy schema directory (for backup/restore operations)
COPY schema/ /workspace/schema/

# Copy development scripts (diagnostics, etc.)
COPY scripts/development/ /workspace/scripts/development/

# Set Python path so imports work (api.api.lib.*)
ENV PYTHONPATH=/workspace

# Make scripts executable
RUN chmod +x /workspace/operator/configure.py \
    && chmod +x /workspace/operator/lib/*.sh

# Set up operator shell environment
# Create symlink for operator-help command (accessible from anywhere)
RUN ln -s /workspace/operator/lib/operator-help.sh /usr/local/bin/operator-help

# Create .bashrc that shows help on interactive shell login
RUN echo '#!/bin/bash' > /root/.bashrc \
    && echo '# Show operator help on interactive shell login' >> /root/.bashrc \
    && echo 'if [ -t 0 ] && [ -z "$OPERATOR_HELP_SHOWN" ]; then' >> /root/.bashrc \
    && echo '    export OPERATOR_HELP_SHOWN=1' >> /root/.bashrc \
    && echo '    /usr/local/bin/operator-help' >> /root/.bashrc \
    && echo 'fi' >> /root/.bashrc \
    && echo '' >> /root/.bashrc \
    && echo '# Convenient aliases' >> /root/.bashrc \
    && echo 'alias configure="python /workspace/operator/configure.py"' >> /root/.bashrc \
    && echo 'alias help="operator-help"' >> /root/.bashrc \
    && chmod +x /root/.bashrc

# Default command: Keep container running for exec commands
# The kg-operator wrapper will exec into this container
CMD ["tail", "-f", "/dev/null"]
