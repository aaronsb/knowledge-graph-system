#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
GRAY='\033[0;90m'
NC='\033[0m'

# Parse arguments
AUTO_CONFIRM=false
REMOVE_MODELS=false

for arg in "$@"; do
    case $arg in
        -y|--yes)
            AUTO_CONFIRM=true
            ;;
        --remove-models)
            REMOVE_MODELS=true
            ;;
    esac
done

# Show usage and require confirmation
if [ "$AUTO_CONFIRM" = false ]; then
    echo -e "${BLUE}🛑 Stop Ollama Local Inference Service${NC}"
    echo "==========================================="
    echo ""
    echo -e "${YELLOW}What this does:${NC}"
    echo "  • Stops and removes Ollama container"
    if [ "$REMOVE_MODELS" = true ]; then
        echo -e "  • ${RED}Removes all downloaded models (ollama-models volume)${NC}"
    else
        echo "  • Preserves downloaded models (ollama-models volume)"
    fi
    echo ""
    echo -e "${GRAY}Usage:${NC}"
    echo "  $0 -y                   # Stop Ollama (keep models)"
    echo "  $0 -y --remove-models   # Stop and delete all models"
    echo ""
    if [ "$REMOVE_MODELS" = false ]; then
        echo -e "${GREEN}💡 Tip: Models will be preserved for next startup${NC}"
    else
        echo -e "${RED}⚠️  WARNING: This will delete all downloaded models!${NC}"
    fi
    echo ""
    read -p "$(echo -e ${YELLOW}Continue? [y/N]:${NC} )" -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}❌ Cancelled${NC}"
        exit 1
    fi
fi

# Check if Ollama container is running
if ! docker ps -a --format '{{.Names}}' | grep -q "^kg-ollama$"; then
    echo -e "${YELLOW}ℹ️  Ollama container not found${NC}"
    exit 0
fi

# Stop and remove container
echo -e "${BLUE}🛑 Stopping Ollama container...${NC}"
docker-compose -f docker-compose.ollama.yml down

# Remove models if requested
if [ "$REMOVE_MODELS" = true ]; then
    echo -e "${RED}🗑️  Removing models volume...${NC}"
    docker volume rm ollama-models 2>/dev/null || true
    echo -e "${GREEN}✅ Models removed${NC}"
else
    echo -e "${GREEN}✅ Models preserved in volume 'ollama-models'${NC}"
fi

echo ""
echo -e "${GREEN}✅ Ollama Stopped Successfully${NC}"
echo ""
echo -e "${GRAY}To restart: ./scripts/ollama/start-ollama.sh -y${NC}"
echo ""
