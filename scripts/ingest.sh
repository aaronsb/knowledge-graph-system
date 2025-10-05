#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "📥 Knowledge Graph - Document Ingestion"
echo "======================================="

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
DOCUMENT_NAME=""
BATCH_SIZE=1

show_help() {
    cat << EOF
Usage: $0 [OPTIONS] <document-path>

Arguments:
  document-path         Path to document to ingest (required)

Options:
  -n, --name NAME      Document name/title (default: filename)
  -b, --batch-size N   Process N paragraphs at once (default: 1)
  -h, --help           Show this help message

Examples:
  $0 ingest_source/watts_lecture_1.txt
  $0 ingest_source/watts_lecture_1.txt --name "Watts Doc 1"
  $0 docs/paper.txt --name "Research Paper" --batch-size 5

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--name)
            DOCUMENT_NAME="$2"
            shift 2
            ;;
        -b|--batch-size)
            BATCH_SIZE="$2"
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

# Default document name to filename if not provided
if [ -z "$DOCUMENT_NAME" ]; then
    DOCUMENT_NAME=$(basename "$DOCUMENT_PATH" | sed 's/\.[^.]*$//')
    echo -e "${YELLOW}Using document name: $DOCUMENT_NAME${NC}"
fi

# Show configuration
echo -e "\n${BLUE}Configuration:${NC}"
echo -e "  Document: ${GREEN}$DOCUMENT_PATH${NC}"
echo -e "  Name: ${GREEN}$DOCUMENT_NAME${NC}"
echo -e "  Batch size: ${GREEN}$BATCH_SIZE${NC}"

# Check file size
FILE_SIZE=$(du -h "$DOCUMENT_PATH" | cut -f1)
echo -e "  Size: ${GREEN}$FILE_SIZE${NC}"

# Count paragraphs
PARA_COUNT=$(grep -c '^$' "$DOCUMENT_PATH" || true)
echo -e "  Approx paragraphs: ${GREEN}~$PARA_COUNT${NC}"

# Confirm
echo -e "\n${YELLOW}Press Enter to start ingestion (Ctrl+C to cancel)${NC}"
read

# Activate virtual environment and run ingestion
echo -e "\n${YELLOW}Starting ingestion...${NC}\n"

source venv/bin/activate

python -m ingest.ingest "$DOCUMENT_PATH" \
    --document-name "$DOCUMENT_NAME" \
    2>&1 | tee "logs/ingest_$(date +%Y%m%d_%H%M%S).log" || {
    echo -e "\n${RED}✗ Ingestion failed${NC}"
    echo -e "${YELLOW}Check the log file for details${NC}"
    exit 1
}

echo -e "\n${GREEN}✅ Ingestion complete!${NC}"

# Show stats
echo -e "\n${BLUE}Database Statistics:${NC}"
if command -v python &> /dev/null; then
    python cli.py stats
fi

echo -e "\n${YELLOW}Next steps:${NC}"
echo -e "  - View in Neo4j Browser: ${BLUE}http://localhost:7474${NC}"
echo -e "  - Query via CLI: ${BLUE}python cli.py search \"your query\"${NC}"
echo "  - Use with Claude Desktop (if MCP configured)"
