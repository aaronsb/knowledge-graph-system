#!/bin/bash
# =============================================================================
# Test Runner - Executes pytest inside the API container (dev mode)
# =============================================================================
# Usage:
#   ./tests/run.sh                    # Full suite
#   ./tests/run.sh tests/api/         # Specific directory
#   ./tests/run.sh -k "concept"       # Pattern match
#   ./tests/run.sh --cov              # With coverage
#   ./tests/run.sh -m "not slow"      # Skip slow tests
# =============================================================================

set -e

# Find the API container (may be kg-api-dev or kg-api)
CONTAINER=$(docker ps --format '{{.Names}}' | grep -E "^kg-api(-dev)?$" | head -1)

if [ -z "${CONTAINER}" ]; then
    echo "Error: API container is not running."
    echo "Start the platform first:"
    echo "  ./operator.sh start"
    exit 1
fi

# Check if tests are mounted (dev mode required)
if ! docker exec "${CONTAINER}" test -f /app/pytest.ini 2>/dev/null; then
    echo "Error: Tests not mounted. Start in dev mode:"
    echo "  ./operator.sh start  (uses dev overlay by default)"
    exit 1
fi

# Run pytest inside the container
# Use -it if TTY available, otherwise just -i
if [ -t 0 ]; then
    docker exec -it "${CONTAINER}" pytest "$@"
else
    docker exec -i "${CONTAINER}" pytest "$@"
fi
