#!/bin/sh
# Docker entrypoint for Knowledge Graph Visualizer (Development Mode)
# Generates runtime config.js from environment variables before starting Vite

set -e

echo "Generating runtime configuration from environment variables..."

# Create config.js from environment variables in public directory (served by Vite)
cat > /app/public/config.js <<EOF
// Runtime Configuration - Generated from Docker environment variables
// DO NOT EDIT - This file is auto-generated at container startup

window.APP_CONFIG = {
  apiUrl: '${VITE_API_URL:-http://localhost:8000}',

  oauth: {
    clientId: '${VITE_OAUTH_CLIENT_ID:-kg-viz}',
    redirectUri: '${VITE_OAUTH_REDIRECT_URI:-http://localhost:3000/callback}',
  },

  app: {
    name: '${VITE_APP_NAME:-Knowledge Graph Visualizer}',
    version: '${VITE_APP_VERSION:-1.0.0}',
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
