#!/bin/bash
# Wrapper script to run the TypeScript CLI without npm link

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CLI_PATH="$PROJECT_ROOT/client/dist/index.js"

# Check if built
if [ ! -f "$CLI_PATH" ]; then
    echo "Error: CLI not built. Run: cd client && npm run build"
    exit 1
fi

# Run CLI with all arguments
node "$CLI_PATH" "$@"
