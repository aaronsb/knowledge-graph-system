#!/bin/sh
# Docker entrypoint for Knowledge Graph Visualizer (Development Mode)
# Generates runtime config.js from environment variables before starting Vite

set -e

echo "Generating runtime configuration from environment variables..."

# Escape function: Escapes single quotes and backslashes for JavaScript strings
# Usage: escape_js "some'value"
escape_js() {
  printf '%s' "$1" | sed "s/\\\\/\\\\\\\\/g; s/'/\\\'/g"
}

# Set defaults and escape values
API_URL=$(escape_js "${VITE_API_URL:-http://localhost:8000}")
OAUTH_CLIENT_ID=$(escape_js "${VITE_OAUTH_CLIENT_ID:-kg-viz}")
OAUTH_REDIRECT_URI=$(escape_js "${VITE_OAUTH_REDIRECT_URI:-http://localhost:3000/callback}")
APP_NAME=$(escape_js "${VITE_APP_NAME:-Knowledge Graph Visualizer}")
APP_VERSION=$(escape_js "${VITE_APP_VERSION:-1.0.0}")

# Create config.js from environment variables in public directory (served by Vite)
# Using escaped values to prevent injection
cat > /app/public/config.js <<EOF
// Runtime Configuration - Generated from Docker environment variables
// DO NOT EDIT - This file is auto-generated at container startup

window.APP_CONFIG = {
  apiUrl: '${API_URL}',

  oauth: {
    clientId: '${OAUTH_CLIENT_ID}',
    redirectUri: '${OAUTH_REDIRECT_URI}',
  },

  app: {
    name: '${APP_NAME}',
    version: '${APP_VERSION}',
  },
};
EOF

echo "✓ Configuration generated:"
echo "  API URL: ${VITE_API_URL:-http://localhost:8000}"
echo "  OAuth Client ID: ${VITE_OAUTH_CLIENT_ID:-kg-viz}"
echo "  OAuth Redirect URI: ${VITE_OAUTH_REDIRECT_URI:-[auto-detect]}"

# Start Vite dev server
echo "Starting Vite dev server..."
exec "$@"
