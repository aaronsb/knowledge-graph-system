FROM python:3.11-slim

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
RUN pip install --no-cache-dir -r operator/requirements.txt

# Copy operator scripts and tools
COPY operator/ /workspace/operator/

# Copy API library code (operator imports from api.api.lib.*)
# Only copy what's needed for configuration, not the full API server
COPY api/api/lib/ /workspace/api/api/lib/
COPY api/api/__init__.py /workspace/api/api/__init__.py

# Copy schema directory (for backup/restore operations)
COPY schema/ /workspace/schema/

# Set Python path so imports work (api.api.lib.*)
ENV PYTHONPATH=/workspace

# Make scripts executable
RUN chmod +x /workspace/operator/configure.py \
    && chmod +x /workspace/operator/lib/*.sh

# Default command: Keep container running for exec commands
# The kg-operator wrapper will exec into this container
CMD ["tail", "-f", "/dev/null"]
