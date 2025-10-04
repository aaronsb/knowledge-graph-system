#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🚀 Knowledge Graph System - Setup"
echo "=================================="

# Check prerequisites
echo -e "\n${YELLOW}Checking prerequisites...${NC}"

if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker installed${NC}"

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}✗ Docker Compose not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker Compose installed${NC}"

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python 3 installed${NC}"

if ! command -v node &> /dev/null; then
    echo -e "${RED}✗ Node.js not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Node.js installed${NC}"

# Environment setup
echo -e "\n${YELLOW}Setting up environment...${NC}"

if [ ! -f .env ]; then
    cp .env.example .env
    echo -e "${GREEN}✓ Created .env file${NC}"
    echo -e "${YELLOW}⚠ Please edit .env and add your API keys:${NC}"
    echo "   - ANTHROPIC_API_KEY"
    echo "   - OPENAI_API_KEY"
    read -p "Press enter when ready to continue..."
else
    echo -e "${GREEN}✓ .env file exists${NC}"
fi

# Start Docker services
echo -e "\n${YELLOW}Starting Neo4j database...${NC}"
docker-compose up -d

# Wait for Neo4j to be ready
echo -e "${YELLOW}Waiting for Neo4j to be ready...${NC}"
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if docker exec knowledge-graph-neo4j cypher-shell -u neo4j -p password "RETURN 1" &> /dev/null; then
        echo -e "\n${GREEN}✓ Neo4j is ready${NC}"
        break
    fi
    echo -n "."
    sleep 2
    ((attempt++))
done

if [ $attempt -eq $max_attempts ]; then
    echo -e "\n${RED}✗ Neo4j failed to start${NC}"
    exit 1
fi

# Initialize database schema
echo -e "\n${YELLOW}Initializing database schema...${NC}"
docker exec -i knowledge-graph-neo4j cypher-shell -u neo4j -p password < schema/init.cypher
echo -e "${GREEN}✓ Database schema initialized${NC}"

# Python environment setup
echo -e "\n${YELLOW}Setting up Python environment...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✓ Created Python virtual environment${NC}"
else
    echo -e "${GREEN}✓ Virtual environment exists${NC}"
fi

source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo -e "${GREEN}✓ Python dependencies installed${NC}"

# MCP Server setup
echo -e "\n${YELLOW}Building MCP server...${NC}"
cd mcp-server
npm install --silent
npm run build
cd ..
echo -e "${GREEN}✓ MCP server built${NC}"

# Print MCP configuration
echo -e "\n${GREEN}✅ Setup complete!${NC}"
echo -e "\n${YELLOW}=== Claude Desktop Configuration ===${NC}"
echo -e "Add this to: ${YELLOW}~/Library/Application Support/Claude/claude_desktop_config.json${NC}"
echo -e "(or equivalent location on your system)\n"

cat << EOF
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "node",
      "args": ["$(pwd)/mcp-server/build/index.js"],
      "env": {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "password",
        "OPENAI_API_KEY": "<your-openai-key>"
      }
    }
  }
}
EOF

echo -e "\n${YELLOW}=== Next Steps ===${NC}"
echo "1. Add the MCP config to Claude Desktop (shown above)"
echo "2. Restart Claude Desktop to load the MCP server"
echo "3. Ingest documents:"
echo "   source venv/bin/activate"
echo "   python ingest/ingest.py docs/watts_lecture_1.txt --document-name \"Watts Doc 1\""
echo ""
echo "4. Access Neo4j Browser at: ${YELLOW}http://localhost:7474${NC}"
echo "   Username: neo4j"
echo "   Password: password"
echo ""
echo -e "${GREEN}Happy knowledge graphing! 🎉${NC}"
