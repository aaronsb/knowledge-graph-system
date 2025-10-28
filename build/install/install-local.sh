#!/usr/bin/env bash
#
# install-local.sh - Install from local build
#
# Status: TODO - Not yet implemented
#
# What this should do:
# - Build all components (calls build/local/build-all.sh)
# - Deploy to system locations
# - Install CLI globally
# - Create systemd services (Linux) or launchd (macOS)
# - Configure initial setup
# - Verify installation
#

set -e

echo "⚠ Local installation not yet implemented"
echo ""
echo "For now, use development workflow:"
echo "  1. Build: ./build/local/build-all.sh"
echo "  2. Deploy: ./build/deploy/local/deploy-all.sh"
echo "  3. Install CLI: cd client && ./install.sh"

exit 1
