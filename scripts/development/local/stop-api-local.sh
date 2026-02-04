#!/bin/bash
# ============================================================================
# Stop API Server (Placeholder)
# ============================================================================
# This script will be used to stop the API server container once the API
# is containerized. Currently, the API runs as a foreground/background
# process started by start-api.sh.
#
# To stop the current API server:
#   - If running in foreground: Ctrl+C
#   - If running in background: pkill -f "uvicorn api.app.main:app"
#   - Or find PID: ps aux | grep uvicorn
# ============================================================================

echo ""
echo "⚠️  API server is not yet containerized"
echo ""
echo "The API currently runs as a Python process (started by start-api.sh)"
echo ""
echo "To stop the API server:"
echo "  • If running in foreground: Press Ctrl+C"
echo "  • If running in background: pkill -f \"uvicorn api.app.main:app\""
echo "  • Or find process: ps aux | grep uvicorn"
echo ""
echo "This script will be implemented when the API is containerized."
echo ""
exit 1
