#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "📥 Knowledge Graph - Document Ingestion"
echo "========================================"

# Check if Neo4j is running
if ! docker ps --format '{{.Names}}' | grep -q knowledge-graph-neo4j; then
    echo -e "${RED}✗ Neo4j is not running${NC}"
    echo -e "${YELLOW}  Start it with: docker-compose up -d${NC}"
    exit 1
fi

# Check if venv exists
if [ ! -d "venv" ]; then
    echo -e "${RED}✗ Python virtual environment not found${NC}"
    echo -e "${YELLOW}  Run: ./scripts/setup.sh${NC}"
    exit 1
fi

# Parse arguments
DOCUMENT_PATH=""
ONTOLOGY_NAME=""
RESUME=false
YES=false
TARGET_WORDS=1000
MIN_WORDS=800
MAX_WORDS=1500
OVERLAP_WORDS=200
CHECKPOINT_INTERVAL=5

show_help() {
    cat << EOF
Usage: $0 [OPTIONS] <document-path>

Arguments:
  document-path         Path to document to ingest (required)

Options:
  -n, --name NAME           Ontology name for grouping documents (required)
  -r, --resume              Resume from checkpoint if available
  -y, --yes                 Skip confirmation prompt
  --target-words N          Target words per chunk (default: 1000)
  --min-words N             Minimum words per chunk (default: 800)
  --max-words N             Maximum words per chunk (default: 1500)
  --overlap-words N         Overlap between chunks (default: 200)
  --checkpoint-interval N   Save checkpoint every N chunks (default: 5)
  -h, --help                Show this help message

Examples:
  # Basic usage - single document into ontology
  $0 ingest_source/file1.txt --name "My Ontology"

  # Add another document to same ontology
  $0 ingest_source/file2.txt --name "My Ontology"

  # Resume interrupted ingestion
  $0 ingest_source/large_file.txt --name "My Ontology" --resume

  # Custom chunk sizes
  $0 document.txt --name "My Ontology" --target-words 1500 --max-words 2000

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--name)
            ONTOLOGY_NAME="$2"
            shift 2
            ;;
        -r|--resume)
            RESUME=true
            shift
            ;;
        -y|--yes)
            YES=true
            shift
            ;;
        --target-words)
            TARGET_WORDS="$2"
            shift 2
            ;;
        --min-words)
            MIN_WORDS="$2"
            shift 2
            ;;
        --max-words)
            MAX_WORDS="$2"
            shift 2
            ;;
        --overlap-words)
            OVERLAP_WORDS="$2"
            shift 2
            ;;
        --checkpoint-interval)
            CHECKPOINT_INTERVAL="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        -*)
            echo -e "${RED}Unknown option: $1${NC}"
            show_help
            exit 1
            ;;
        *)
            DOCUMENT_PATH="$1"
            shift
            ;;
    esac
done

# Validate document path
if [ -z "$DOCUMENT_PATH" ]; then
    echo -e "${RED}✗ Document path is required${NC}"
    show_help
    exit 1
fi

if [ ! -f "$DOCUMENT_PATH" ]; then
    echo -e "${RED}✗ Document not found: $DOCUMENT_PATH${NC}"
    exit 1
fi

# Validate ontology name is provided
if [ -z "$ONTOLOGY_NAME" ]; then
    echo -e "${RED}✗ Ontology name is required (use --name)${NC}"
    show_help
    exit 1
fi

# Show configuration
FILENAME=$(basename "$DOCUMENT_PATH" | sed 's/\.[^.]*$//')

echo -e "\n${BLUE}Configuration:${NC}"
echo -e "  File: ${GREEN}$DOCUMENT_PATH${NC}"
echo -e "  Ontology: ${GREEN}$ONTOLOGY_NAME${NC}"
echo -e "  Resume: ${GREEN}$RESUME${NC}"
echo -e "  Target words/chunk: ${GREEN}$TARGET_WORDS${NC}"
echo -e "  Min words/chunk: ${GREEN}$MIN_WORDS${NC}"
echo -e "  Max words/chunk: ${GREEN}$MAX_WORDS${NC}"
echo -e "  Overlap words: ${GREEN}$OVERLAP_WORDS${NC}"
echo -e "  Checkpoint interval: ${GREEN}every $CHECKPOINT_INTERVAL chunks${NC}"

# Check file size
FILE_SIZE=$(du -h "$DOCUMENT_PATH" | cut -f1)
WORD_COUNT=$(wc -w < "$DOCUMENT_PATH")
EST_CHUNKS=$((WORD_COUNT / TARGET_WORDS))

echo -e "\n${BLUE}Document Stats:${NC}"
echo -e "  Size: ${GREEN}$FILE_SIZE${NC}"
echo -e "  Words: ${GREEN}$(printf "%'d" $WORD_COUNT)${NC}"
echo -e "  Estimated chunks: ${GREEN}~$EST_CHUNKS${NC}"

# Load .env for cost configuration
if [ -f ".env" ]; then
    source .env
fi

# Cost estimation
echo -e "\n${BLUE}Estimated API Costs:${NC}"

# Determine extraction model and cost
AI_PROVIDER=${AI_PROVIDER:-openai}
if [ "$AI_PROVIDER" = "anthropic" ]; then
    EXTRACTION_MODEL=${ANTHROPIC_EXTRACTION_MODEL:-claude-sonnet-4-20250514}
    EXTRACTION_COST_PER_M=${TOKEN_COST_CLAUDE_SONNET_4:-9.00}
else
    EXTRACTION_MODEL=${OPENAI_EXTRACTION_MODEL:-gpt-4o}
    case $EXTRACTION_MODEL in
        gpt-4o)
            EXTRACTION_COST_PER_M=${TOKEN_COST_GPT4O:-6.25}
            ;;
        gpt-4o-mini)
            EXTRACTION_COST_PER_M=${TOKEN_COST_GPT4O_MINI:-0.375}
            ;;
        o1-preview)
            EXTRACTION_COST_PER_M=${TOKEN_COST_O1_PREVIEW:-30.00}
            ;;
        o1-mini)
            EXTRACTION_COST_PER_M=${TOKEN_COST_O1_MINI:-5.50}
            ;;
        *)
            EXTRACTION_COST_PER_M=${TOKEN_COST_GPT4O:-6.25}
            ;;
    esac
fi

# Determine embedding model and cost
EMBEDDING_MODEL=${OPENAI_EMBEDDING_MODEL:-text-embedding-3-small}
case $EMBEDDING_MODEL in
    text-embedding-3-large)
        EMBEDDING_COST_PER_M=${TOKEN_COST_EMBEDDING_LARGE:-0.13}
        ;;
    *)
        EMBEDDING_COST_PER_M=${TOKEN_COST_EMBEDDING_SMALL:-0.02}
        ;;
esac

# Estimate extraction cost (chunks × avg 500-800 tokens per chunk)
EXTRACTION_TOKENS_LOW=$((EST_CHUNKS * 500))
EXTRACTION_TOKENS_HIGH=$((EST_CHUNKS * 800))

# Calculate costs (multiply by 100 to avoid floating point, then divide)
EXTRACTION_COST_LOW_CENTS=$(echo "($EXTRACTION_TOKENS_LOW * ${EXTRACTION_COST_PER_M%.*}00) / 1000000" | bc 2>/dev/null || echo "0")
EXTRACTION_COST_HIGH_CENTS=$(echo "($EXTRACTION_TOKENS_HIGH * ${EXTRACTION_COST_PER_M%.*}00) / 1000000" | bc 2>/dev/null || echo "0")

# Estimate embedding cost (5-8 concepts per chunk × 80-120 tokens per concept)
CONCEPTS_LOW=$((EST_CHUNKS * 5))
CONCEPTS_HIGH=$((EST_CHUNKS * 8))
EMBEDDING_TOKENS_LOW=$((CONCEPTS_LOW * 80))
EMBEDDING_TOKENS_HIGH=$((CONCEPTS_HIGH * 120))

EMBEDDING_COST_LOW_CENTS=$(echo "($EMBEDDING_TOKENS_LOW * ${EMBEDDING_COST_PER_M%.*}00) / 1000000" | bc 2>/dev/null || echo "0")
EMBEDDING_COST_HIGH_CENTS=$(echo "($EMBEDDING_TOKENS_HIGH * ${EMBEDDING_COST_PER_M%.*}00) / 1000000" | bc 2>/dev/null || echo "0")

# Total cost in cents
TOTAL_COST_LOW_CENTS=$((EXTRACTION_COST_LOW_CENTS + EMBEDDING_COST_LOW_CENTS))
TOTAL_COST_HIGH_CENTS=$((EXTRACTION_COST_HIGH_CENTS + EMBEDDING_COST_HIGH_CENTS))

# Convert to dollars (divide by 100)
if command -v bc &> /dev/null; then
    TOTAL_LOW=$(echo "scale=2; $TOTAL_COST_LOW_CENTS / 100" | bc)
    TOTAL_HIGH=$(echo "scale=2; $TOTAL_COST_HIGH_CENTS / 100" | bc)

    # Show costs with model names
    echo -e "  Extraction (${EXTRACTION_MODEL}): ~${GREEN}\$${TOTAL_LOW}${NC}"
    if [ "$TOTAL_HIGH" != "$TOTAL_LOW" ]; then
        echo -e "  Embeddings (${EMBEDDING_MODEL}): included above"
        echo -e "  ${YELLOW}Estimated total: \$${TOTAL_LOW} - \$${TOTAL_HIGH}${NC}"
    else
        echo -e "  ${YELLOW}Estimated total: ~\$${TOTAL_LOW}${NC}"
    fi
else
    # Fallback if bc not available - rough estimate
    TOTAL_APPROX=$((TOTAL_COST_LOW_CENTS / 100))
    echo -e "  ${YELLOW}Estimated total: ~\$${TOTAL_APPROX}${NC}"
fi

echo -e "  ${BLUE}(Actual cost reported after ingestion)${NC}"

# Check for existing checkpoint (keyed by filename, not ontology)
if [ -f ".checkpoints/${FILENAME,,}.json" ]; then
    echo -e "\n${YELLOW}⚠ Checkpoint exists for this file${NC}"
    if [ "$RESUME" = false ]; then
        echo -e "${YELLOW}  Use --resume to continue from checkpoint${NC}"
        echo -e "${YELLOW}  Or the checkpoint will be ignored and ingestion starts fresh${NC}"
    else
        echo -e "${GREEN}  Will resume from checkpoint${NC}"
    fi
fi

# Confirm
if [ "$RESUME" = false ] && [ "$YES" = false ]; then
    echo -e "\n${YELLOW}Press Enter to start ingestion (Esc to cancel)${NC}"

    # Read single key press
    read -s -n1 key

    # Check if Escape key was pressed (ASCII 27 or \e)
    if [ "$key" = $'\e' ]; then
        echo -e "\n${RED}✗ Ingestion cancelled${NC}"
        exit 0
    fi
fi

# Build command (use -u for unbuffered output)
CMD="python -u -m ingest.ingest_chunked \"$DOCUMENT_PATH\" --ontology \"$ONTOLOGY_NAME\""
CMD="$CMD --target-words $TARGET_WORDS"
CMD="$CMD --min-words $MIN_WORDS"
CMD="$CMD --max-words $MAX_WORDS"
CMD="$CMD --overlap-words $OVERLAP_WORDS"
CMD="$CMD --checkpoint-interval $CHECKPOINT_INTERVAL"

if [ "$RESUME" = true ]; then
    CMD="$CMD --resume"
fi

# Activate virtual environment and run ingestion
echo -e "\n${YELLOW}Starting ingestion...${NC}\n"

source venv/bin/activate

# Create logs directory if it doesn't exist
mkdir -p logs

# Use stdbuf to disable buffering on tee as well
eval $CMD 2>&1 | stdbuf -oL tee "logs/ingest_$(date +%Y%m%d_%H%M%S).log" || {
    echo -e "\n${RED}✗ Ingestion failed or interrupted${NC}"
    echo -e "${YELLOW}Check the log file for details${NC}"
    echo -e "${YELLOW}Use --resume to continue from last checkpoint${NC}"
    exit 1
}

echo -e "\n${GREEN}✅ Ingestion complete!${NC}"

# Show stats
echo -e "\n${BLUE}Database Statistics:${NC}"
if command -v python &> /dev/null; then
    python cli.py database stats
fi

echo -e "\n${YELLOW}Next steps:${NC}"
echo -e "  - View in Neo4j Browser: ${BLUE}http://localhost:7474${NC}"
echo -e "  - Query via CLI: ${BLUE}python cli.py search \"your query\"${NC}"
echo "  - Use with Claude Desktop (if MCP configured)"
