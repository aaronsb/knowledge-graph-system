#!/usr/bin/env bash
#
# deploy-database.sh - Deploy database locally
#
# Status: FUNCTIONAL - Uses existing scripts
#

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

echo "Starting database..."

# Use existing start-database.sh
"$PROJECT_ROOT/scripts/start-database.sh"

echo "✓ Database deployed"

exit 0
