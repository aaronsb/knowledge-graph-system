#!/bin/bash
# ============================================================================
# Stop Visualization Server (Placeholder)
# ============================================================================
# This script will be used to stop the visualization server container once
# the viz server is containerized. Currently, the viz server runs as a
# foreground/background process started by start-viz.sh.
#
# To stop the current viz server:
#   - If running in foreground: Ctrl+C
#   - If running in background: Find and kill the process
#   - Or find PID: ps aux | grep viz
# ============================================================================

echo ""
echo "⚠️  Visualization server is not yet containerized"
echo ""
echo "The viz server currently runs as a process (started by start-viz.sh)"
echo ""
echo "To stop the visualization server:"
echo "  • If running in foreground: Press Ctrl+C"
echo "  • If running in background: Find and kill the process"
echo "  • Or find process: ps aux | grep viz"
echo ""
echo "This script will be implemented when the viz server is containerized."
echo ""
exit 1
