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
if [ "$RESUME" = false ]; then
    echo -e "\n${YELLOW}Press Enter to start ingestion (Ctrl+C to cancel)${NC}"
    read
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
