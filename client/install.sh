#!/bin/bash
#
# Install kg CLI to user-local bin directory (~/.local/bin/)
# No sudo required - user-scope installation
#

set -e

INSTALL_DIR="${HOME}/.local"
BIN_DIR="${INSTALL_DIR}/bin"

echo "📦 Installing Knowledge Graph CLI (kg) to user-local directory..."
echo ""

# Check if ~/.local/bin exists, create if not
if [ ! -d "$BIN_DIR" ]; then
    echo "Creating ${BIN_DIR}..."
    mkdir -p "$BIN_DIR"
fi

# Check if ~/.local/bin is in PATH
if [[ ":$PATH:" != *":${BIN_DIR}:"* ]]; then
    echo "⚠️  Warning: ${BIN_DIR} is not in your PATH"
    echo ""
    echo "Add this to your shell profile (~/.bashrc, ~/.zshrc, etc.):"
    echo "  export PATH=\"\${HOME}/.local/bin:\${PATH}\""
    echo ""
fi

# Build TypeScript
echo "🔨 Building TypeScript client..."
npm run build

# Install to user-local prefix
echo "📦 Installing to ${INSTALL_DIR}..."
npm install -g --prefix "$INSTALL_DIR"

echo ""
echo "✅ Installation complete!"
echo ""
echo "The 'kg' command is now available at: ${BIN_DIR}/kg"
echo ""
echo "Test with:"
echo "  kg --version"
echo "  kg health"
echo ""
