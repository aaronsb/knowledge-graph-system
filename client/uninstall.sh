#!/bin/bash
#
# Uninstall kg CLI from user-local bin directory
#

set -e

INSTALL_DIR="${HOME}/.local"
BIN_DIR="${INSTALL_DIR}/bin"

echo "🗑️  Uninstalling Knowledge Graph CLI (kg)..."
echo ""

# Uninstall using npm
npm uninstall -g --prefix "$INSTALL_DIR" @kg/client

echo ""
echo "✅ Uninstall complete!"
echo ""
echo "Note: ${BIN_DIR}/kg should now be removed"
echo ""
