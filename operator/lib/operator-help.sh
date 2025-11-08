#!/bin/bash
# ============================================================================
# operator-help.sh
# Display help information for the operator container shell
# ============================================================================

# Colors
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${BLUE}${BOLD}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║       Knowledge Graph Operator Shell                      ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""
echo -e "${BOLD}Platform Configuration & Management${NC}"
echo ""
echo "You're inside the operator container - the control plane for"
echo "configuring and managing the knowledge graph platform."
echo ""
echo -e "${CYAN}Quick Start:${NC}"
echo "  operator-help          Show this help message"
echo "  configure.py status    View current platform configuration"
echo ""
echo -e "${CYAN}Configuration Commands:${NC}"
echo ""
echo -e "${GREEN}# Admin User Management${NC}"
echo "  configure.py admin"
echo "  configure.py admin --password \"secret\""
echo ""
echo -e "${GREEN}# AI Provider Setup${NC}"
echo "  configure.py ai-provider openai --model gpt-4o"
echo "  configure.py ai-provider anthropic --model claude-sonnet-4-20250514"
echo ""
echo -e "${GREEN}# Embedding Configuration${NC}"
echo "  configure.py embedding              # List available profiles"
echo "  configure.py embedding 2            # Activate profile ID 2"
echo ""
echo -e "${GREEN}# API Key Management (Encrypted)${NC}"
echo "  configure.py api-key openai"
echo "  configure.py api-key openai --key \"sk-...\"    # Non-interactive"
echo "  configure.py api-key anthropic"
echo ""
echo -e "${GREEN}# Platform Status${NC}"
echo "  configure.py status                 # View all configuration"
echo ""
echo -e "${CYAN}Diagnostic Tools:${NC}"
echo "  /workspace/scripts/development/diagnostics/monitor-db.sh"
echo "  /workspace/scripts/development/diagnostics/list-tables.sh"
echo "  /workspace/scripts/development/diagnostics/garage-status.sh"
echo "  /workspace/scripts/development/diagnostics/lint_queries.py"
echo ""
echo -e "${CYAN}Database Operations:${NC}"
echo "  /workspace/operator/database/migrate-db.sh    # Apply migrations"
echo ""
echo -e "${CYAN}Container Management (via Docker socket):${NC}"
echo "  docker ps                           # List running containers"
echo "  docker logs kg-api-dev              # View API logs"
echo "  docker logs knowledge-graph-postgres # View database logs"
echo ""
echo -e "${YELLOW}Documentation:${NC}"
echo "  Quickstart: /workspace/docs/guides/QUICKSTART.md"
echo "  ADR-061:    /workspace/docs/architecture/ADR-061-operator-pattern-lifecycle.md"
echo ""
echo -e "${YELLOW}Exit this shell:${NC} ${BOLD}exit${NC} or ${BOLD}Ctrl+D${NC}"
echo ""
