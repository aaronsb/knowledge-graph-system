#!/bin/bash
# ============================================================================
# operator-help.sh
# Topic-based help system for the operator container shell
#
# Usage:
#   operator-help              Show overview
#   operator-help admin        Admin user management
#   operator-help embedding    Embedding configuration
#   operator-help extraction   AI extraction provider setup
#   operator-help api-keys     API key management
#   operator-help diagnostics  Diagnostic tools
#   operator-help database     Database operations
#   operator-help all          Show all topics
# ============================================================================

# Colors
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

show_header() {
    echo -e "${BLUE}${BOLD}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║       Knowledge Graph Operator Shell                       ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

show_overview() {
    show_header
    echo -e "${BOLD}Platform Configuration & Management${NC}"
    echo ""
    echo "You're inside the operator container - the configuration plane"
    echo "for setting up and managing the knowledge graph platform."
    echo ""
    echo -e "${CYAN}Quick Start:${NC}"
    echo "  configure.py status    View current platform configuration"
    echo ""
    echo -e "${CYAN}Help Topics:${NC}"
    echo "  operator-help admin        Admin user management"
    echo "  operator-help embedding    Embedding configuration"
    echo "  operator-help extraction   AI extraction provider"
    echo "  operator-help api-keys     API key management"
    echo "  operator-help diagnostics  Diagnostic tools"
    echo "  operator-help database     Database operations"
    echo "  operator-help all          Show all help topics"
    echo ""
    echo -e "${YELLOW}Exit this shell:${NC} ${BOLD}exit${NC} or ${BOLD}Ctrl+D${NC}"
    echo ""
}

show_admin_help() {
    echo -e "${BOLD}Admin User Management${NC}"
    echo ""
    echo "Create or update admin users for platform authentication."
    echo ""
    echo -e "${CYAN}Commands:${NC}"
    echo ""
    echo -e "${GREEN}# Create/update admin (interactive password prompt)${NC}"
    echo "  configure.py admin"
    echo ""
    echo -e "${GREEN}# Create/update with specific password${NC}"
    echo "  configure.py admin --password \"your-password\""
    echo ""
    echo -e "${GREEN}# Create admin with custom username${NC}"
    echo "  configure.py admin --username \"ops\" --password \"secret\""
    echo ""
    echo -e "${CYAN}Related Scripts:${NC}"
    echo "  /workspace/operator/admin/set-admin-password.sh"
    echo "  /workspace/operator/admin/reset-password.sh"
    echo ""
}

show_embedding_help() {
    echo -e "${BOLD}Embedding Configuration${NC}"
    echo ""
    echo "Configure which embedding model generates concept vectors."
    echo "Embeddings must match across your entire knowledge graph."
    echo ""
    echo -e "${CYAN}Commands:${NC}"
    echo ""
    echo -e "${GREEN}# List available embedding profiles${NC}"
    echo "  configure.py embedding"
    echo ""
    echo -e "${GREEN}# Activate a specific profile by ID${NC}"
    echo "  configure.py embedding 2"
    echo ""
    echo -e "${CYAN}Available Profiles:${NC}"
    echo "  [1] openai / text-embedding-3-small (1536 dims) - Cloud API"
    echo "  [2] local / nomic-embed-text-v1.5 (768 dims) - Local GPU/CPU"
    echo ""
    echo -e "${YELLOW}Important:${NC}"
    echo "  - Changing embedding model invalidates existing embeddings"
    echo "  - Local embeddings require sufficient VRAM for GPU acceleration"
    echo "  - OpenAI embeddings require valid API key"
    echo ""
}

show_extraction_help() {
    echo -e "${BOLD}AI Extraction Provider${NC}"
    echo ""
    echo "Configure which LLM extracts concepts from documents."
    echo ""
    echo -e "${CYAN}Commands:${NC}"
    echo ""
    echo -e "${GREEN}# Set OpenAI as extraction provider${NC}"
    echo "  configure.py ai-provider openai --model gpt-4o"
    echo "  configure.py ai-provider openai --model gpt-4o-mini"
    echo ""
    echo -e "${GREEN}# Set Anthropic as extraction provider${NC}"
    echo "  configure.py ai-provider anthropic --model claude-sonnet-4-20250514"
    echo "  configure.py ai-provider anthropic --model claude-3-5-sonnet-20241022"
    echo ""
    echo -e "${GREEN}# Set Ollama for local extraction${NC}"
    echo "  configure.py ai-provider ollama --model mistral:7b-instruct"
    echo "  configure.py ai-provider ollama --model qwen2.5:14b"
    echo ""
    echo -e "${CYAN}Testing:${NC}"
    echo "  /workspace/operator/admin/extraction_test.py"
    echo ""
    echo -e "${YELLOW}Note:${NC} Requires corresponding API key for cloud providers."
    echo ""
}

show_api_keys_help() {
    echo -e "${BOLD}API Key Management${NC}"
    echo ""
    echo "Store encrypted API keys for AI providers."
    echo "Keys are encrypted at rest using the master encryption key."
    echo ""
    echo -e "${CYAN}Commands:${NC}"
    echo ""
    echo -e "${GREEN}# Store OpenAI API key (interactive)${NC}"
    echo "  configure.py api-key openai"
    echo ""
    echo -e "${GREEN}# Store with key directly (non-interactive)${NC}"
    echo "  configure.py api-key openai --key \"sk-...\""
    echo ""
    echo -e "${GREEN}# Store Anthropic API key${NC}"
    echo "  configure.py api-key anthropic"
    echo ""
    echo -e "${GREEN}# Store Garage S3 credentials${NC}"
    echo "  configure.py api-key garage --key \"ACCESS_KEY:SECRET_KEY\""
    echo ""
    echo -e "${CYAN}Key Management Scripts:${NC}"
    echo "  /workspace/operator/admin/manage_api_keys.py list"
    echo "  /workspace/operator/admin/manage_api_keys.py delete openai"
    echo ""
    echo -e "${YELLOW}Security:${NC}"
    echo "  - Keys validated before storage"
    echo "  - Encrypted using ENCRYPTION_KEY from .env"
    echo "  - Never logged or displayed after storage"
    echo ""
}

show_diagnostics_help() {
    echo -e "${BOLD}Diagnostic Tools${NC}"
    echo ""
    echo "Tools for monitoring and debugging the platform."
    echo ""
    echo -e "${CYAN}Database Diagnostics:${NC}"
    echo "  /workspace/scripts/development/diagnostics/monitor-db.sh"
    echo "    - Live database statistics and connections"
    echo ""
    echo "  /workspace/scripts/development/diagnostics/list-tables.sh"
    echo "    - List all tables with row counts"
    echo ""
    echo "  /workspace/scripts/development/diagnostics/explain-query.sh"
    echo "    - Explain query execution plans"
    echo ""
    echo -e "${CYAN}Garage S3 Storage:${NC}"
    echo "  /workspace/scripts/development/diagnostics/garage-status.sh"
    echo "    - Garage cluster status"
    echo ""
    echo "  /workspace/scripts/development/diagnostics/garage-keys.sh"
    echo "    - List API keys and permissions"
    echo ""
    echo "  /workspace/scripts/development/diagnostics/garage-list-images.sh"
    echo "    - List stored images in bucket"
    echo ""
    echo -e "${CYAN}Code Quality:${NC}"
    echo "  python /workspace/scripts/development/diagnostics/lint_queries.py"
    echo "    - Check for unsafe graph queries"
    echo ""
    echo -e "${CYAN}Container Logs (via Docker socket):${NC}"
    echo "  docker logs kg-api-dev              # API logs"
    echo "  docker logs knowledge-graph-postgres # Database logs"
    echo "  docker logs knowledge-graph-garage   # Storage logs"
    echo ""
}

show_database_help() {
    echo -e "${BOLD}Database Operations${NC}"
    echo ""
    echo "Database management and maintenance tools."
    echo ""
    echo -e "${CYAN}Migrations:${NC}"
    echo "  /workspace/operator/database/migrate-db.sh"
    echo "    - Apply pending database migrations"
    echo "    - Run automatically on startup"
    echo ""
    echo -e "${CYAN}Backup & Restore:${NC}"
    echo "  /workspace/operator/database/backup-database.sh"
    echo "    - Create database backup"
    echo ""
    echo "  /workspace/operator/database/restore-database.sh"
    echo "    - Restore from backup"
    echo ""
    echo -e "${CYAN}Direct Database Access:${NC}"
    echo "  psql -h knowledge-graph-postgres -U admin -d knowledge_graph"
    echo ""
    echo -e "${CYAN}Graph Operations:${NC}"
    echo "  /workspace/operator/admin/calculate_concept_grounding.py"
    echo "    - Recalculate concept grounding scores"
    echo ""
    echo -e "${YELLOW}Note:${NC} Always backup before major operations."
    echo ""
}

show_all_help() {
    show_header
    echo ""
    show_admin_help
    echo "────────────────────────────────────────────────────────────────"
    echo ""
    show_embedding_help
    echo "────────────────────────────────────────────────────────────────"
    echo ""
    show_extraction_help
    echo "────────────────────────────────────────────────────────────────"
    echo ""
    show_api_keys_help
    echo "────────────────────────────────────────────────────────────────"
    echo ""
    show_diagnostics_help
    echo "────────────────────────────────────────────────────────────────"
    echo ""
    show_database_help
}

# Main dispatch
case "${1:-}" in
    admin)
        show_admin_help
        ;;
    embedding|embeddings)
        show_embedding_help
        ;;
    extraction|ai-provider|provider)
        show_extraction_help
        ;;
    api-key|api-keys|keys)
        show_api_keys_help
        ;;
    diagnostics|diag)
        show_diagnostics_help
        ;;
    database|db)
        show_database_help
        ;;
    all)
        show_all_help
        ;;
    *)
        show_overview
        ;;
esac
