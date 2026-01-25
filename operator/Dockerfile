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
# Use BuildKit cache for apt to speed up rebuilds
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y \
    # Docker CLI for container management via socket
    docker.io \
    # PostgreSQL client for database operations
    postgresql-client \
    # curl for health checks
    curl \
    # Build tools for Python packages
    gcc \
    libpq-dev

# Install docker compose v2 plugin (not included in docker.io package)
# v2.35.1 fixes network override issues with mixed list/map syntax
RUN mkdir -p /usr/local/lib/docker/cli-plugins \
    && curl -fsSL "https://github.com/docker/compose/releases/download/v2.35.1/docker-compose-linux-$(uname -m)" \
       -o /usr/local/lib/docker/cli-plugins/docker-compose \
    && chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# Create working directory
WORKDIR /workspace

# Copy Python requirements (operator needs subset of API dependencies)
COPY operator/requirements.txt /workspace/operator/requirements.txt
# Use BuildKit mount cache for faster rebuilds while keeping images small
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r operator/requirements.txt

# Copy operator scripts and tools
COPY operator/ /workspace/operator/

# Copy API library code (operator imports from api.app.lib.*)
# Only copy what's needed for configuration, not the full API server
COPY api/__init__.py /workspace/api/__init__.py
COPY api/app/lib/ /workspace/api/app/lib/
COPY api/app/__init__.py /workspace/api/app/__init__.py

# Copy schema directory (for backup/restore operations)
COPY schema/ /workspace/schema/

# Copy operator.sh for self-update capability
# Users can extract this trusted copy: docker cp kg-operator:/etc/kg/operator.sh ./
COPY operator.sh /etc/kg/operator.sh

# Copy development scripts (diagnostics, etc.)
COPY scripts/development/ /workspace/scripts/development/

# Set Python path so imports work (api.app.lib.*)
# Note: The directory structure is api/app/ but Python imports use api.app
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
    && echo '# PostgreSQL convenience - use existing POSTGRES_PASSWORD for psql' >> /root/.bashrc \
    && echo 'export PGPASSWORD="${POSTGRES_PASSWORD}"' >> /root/.bashrc \
    && echo 'export PGHOST="${POSTGRES_HOST:-knowledge-graph-postgres}"' >> /root/.bashrc \
    && echo 'export PGUSER="${POSTGRES_USER:-admin}"' >> /root/.bashrc \
    && echo 'export PGDATABASE="${POSTGRES_DB:-knowledge_graph}"' >> /root/.bashrc \
    && echo '' >> /root/.bashrc \
    && echo '# Convenient aliases' >> /root/.bashrc \
    && echo 'alias configure="python /workspace/operator/configure.py"' >> /root/.bashrc \
    && echo 'alias help="operator-help"' >> /root/.bashrc \
    && echo 'alias pg="psql"' >> /root/.bashrc \
    && echo 'alias status="configure status"' >> /root/.bashrc \
    && chmod +x /root/.bashrc

# Create startup script that logs a message then keeps container running
RUN echo '#!/bin/bash' > /usr/local/bin/operator-start.sh \
    && echo 'echo "════════════════════════════════════════════════════════════"' >> /usr/local/bin/operator-start.sh \
    && echo 'echo "  Knowledge Graph Operator Container"' >> /usr/local/bin/operator-start.sh \
    && echo 'echo "  Started: $(date -Iseconds)"' >> /usr/local/bin/operator-start.sh \
    && echo 'echo "════════════════════════════════════════════════════════════"' >> /usr/local/bin/operator-start.sh \
    && echo 'echo ""' >> /usr/local/bin/operator-start.sh \
    && echo 'echo "Configuration plane ready."' >> /usr/local/bin/operator-start.sh \
    && echo 'echo "Enter shell: docker exec -it kg-operator /bin/bash"' >> /usr/local/bin/operator-start.sh \
    && echo 'echo "Quick status: docker exec kg-operator configure.py status"' >> /usr/local/bin/operator-start.sh \
    && echo 'echo ""' >> /usr/local/bin/operator-start.sh \
    && echo 'exec tail -f /dev/null' >> /usr/local/bin/operator-start.sh \
    && chmod +x /usr/local/bin/operator-start.sh

# Default command: Show startup message then keep container running
CMD ["/usr/local/bin/operator-start.sh"]
