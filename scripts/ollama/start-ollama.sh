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
PROFILE=""
PULL_MODEL=""

for arg in "$@"; do
    case $arg in
        -y|--yes)
            AUTO_CONFIRM=true
            ;;
        --nvidia|--amd|--intel|--cpu)
            PROFILE="${arg#--}"
            ;;
        --pull=*)
            PULL_MODEL="${arg#--pull=}"
            ;;
    esac
done

# Function to detect hardware
detect_hardware() {
    # Check for NVIDIA GPU
    if command -v nvidia-smi &> /dev/null; then
        if nvidia-smi &> /dev/null; then
            echo "nvidia"
            return
        fi
    fi

    # Check for AMD GPU (ROCm)
    if command -v rocm-smi &> /dev/null; then
        if rocm-smi &> /dev/null; then
            echo "amd"
            return
        fi
    fi

    # Check for Intel GPU
    if [ -d "/dev/dri" ]; then
        if lspci | grep -i "vga.*intel" &> /dev/null; then
            echo "intel"
            return
        fi
    fi

    # Default to CPU
    echo "cpu"
}

# Auto-detect hardware if not specified
if [ -z "$PROFILE" ]; then
    DETECTED=$(detect_hardware)
    PROFILE="$DETECTED"
    echo -e "${BLUE}🔍 Auto-detected hardware: ${YELLOW}${PROFILE}${NC}"
fi

# Show usage and require confirmation
if [ "$AUTO_CONFIRM" = false ]; then
    echo -e "${BLUE}🚀 Start Ollama Local Inference Service${NC}"
    echo "==========================================="
    echo ""
    echo -e "${YELLOW}What this does:${NC}"
    echo "  • Starts Ollama with $PROFILE-optimized profile"
    echo "  • Listens on http://localhost:11434"
    echo "  • Models stored in Docker volume 'ollama-models'"
    echo "  • Integrates with Knowledge Graph API"
    echo ""
    echo -e "${GRAY}Hardware Profiles:${NC}"
    echo "  nvidia  - NVIDIA GPUs (RTX, Tesla, A100)"
    echo "  amd     - AMD GPUs (RX 7000, MI series via ROCm)"
    echo "  intel   - Intel GPUs (Arc, Iris Xe)"
    echo "  cpu     - CPU-only inference (no GPU)"
    echo ""
    echo -e "${GRAY}Usage:${NC}"
    echo "  $0 -y                                    # Auto-detect and start"
    echo "  $0 -y --nvidia                           # Force NVIDIA profile"
    echo "  $0 -y --amd                              # Force AMD profile"
    echo "  $0 -y --cpu                              # Force CPU-only"
    echo "  $0 -y --pull=mistral:7b-instruct         # Start and pull model"
    echo ""
    echo -e "${GRAY}After starting:${NC}"
    echo "  1. Pull a model: docker exec kg-ollama ollama pull mistral:7b-instruct"
    echo "  2. Configure KG:  kg admin extraction set --provider ollama --model mistral:7b-instruct"
    echo "  3. Test:          kg admin extraction test"
    echo ""
    read -p "$(echo -e ${YELLOW}Continue? [y/N]:${NC} )" -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}❌ Cancelled${NC}"
        exit 1
    fi
fi

# Start Ollama with selected profile
echo -e "${BLUE}🚀 Starting Ollama ($PROFILE profile)...${NC}"
docker-compose -f docker-compose.ollama.yml --profile "$PROFILE" up -d

# Wait for Ollama to be ready
echo -e "${BLUE}⏳ Waiting for Ollama to start...${NC}"
for i in {1..30}; do
    if curl -s http://localhost:11434/api/version > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Ollama is ready!${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}❌ Timeout waiting for Ollama${NC}"
        exit 1
    fi
    sleep 1
done

# Pull model if requested
if [ -n "$PULL_MODEL" ]; then
    echo -e "${BLUE}📥 Pulling model: ${YELLOW}$PULL_MODEL${NC}"
    docker exec kg-ollama ollama pull "$PULL_MODEL"
    echo -e "${GREEN}✅ Model pulled successfully${NC}"
fi

# Show status
echo ""
echo -e "${GREEN}✅ Ollama Started Successfully${NC}"
echo "================================"
echo ""
echo -e "${BLUE}Service Info:${NC}"
echo "  Container: kg-ollama"
echo "  Profile:   $PROFILE"
echo "  Endpoint:  http://localhost:11434"
echo ""
echo -e "${BLUE}Recommended Models:${NC}"
echo "  7-8B:  mistral:7b-instruct (recommended, balanced)"
echo "  7-8B:  llama3.1:8b-instruct (high quality)"
echo "  7-8B:  qwen2.5:7b-instruct (excellent reasoning)"
echo "  14B:   qwen2.5:14b-instruct (best for 16GB VRAM)"
echo "  70B:   llama3.1:70b-instruct (GPT-4 quality, needs 48GB+ VRAM)"
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo "  # Pull a model"
echo "  docker exec kg-ollama ollama pull mistral:7b-instruct"
echo ""
echo "  # Configure Knowledge Graph to use Ollama"
echo "  kg admin extraction set --provider ollama --model mistral:7b-instruct"
echo ""
echo "  # Test extraction"
echo "  kg admin extraction test"
echo ""
echo -e "${GRAY}To stop: ./scripts/ollama/stop-ollama.sh${NC}"
echo ""
