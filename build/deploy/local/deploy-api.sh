#!/usr/bin/env bash
#
# deploy-api.sh - Deploy API server locally
#
# Status: FUNCTIONAL - Uses existing scripts
#

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

echo "Starting API server..."

# Use existing start-api.sh
"$PROJECT_ROOT/scripts/start-api.sh" -y

echo "✓ API server deployed (background)"
echo "  Logs: $PROJECT_ROOT/logs/api_*.log"

exit 0
