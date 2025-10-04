#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "📊 Knowledge Graph System - Status"
echo "=================================="

# Check Docker containers
echo -e "\n${BLUE}Docker Containers:${NC}"
if docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep -q knowledge-graph-neo4j; then
    docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep knowledge-graph-neo4j
    echo -e "${GREEN}✓ Neo4j is running${NC}"
else
    echo -e "${RED}✗ Neo4j is not running${NC}"
    echo -e "${YELLOW}  Run: ./scripts/setup.sh${NC}"
fi

# Check Neo4j connection
echo -e "\n${BLUE}Database Connection:${NC}"
if docker exec knowledge-graph-neo4j cypher-shell -u neo4j -p password "RETURN 1" &> /dev/null; then
    echo -e "${GREEN}✓ Can connect to Neo4j${NC}"

    # Get node counts
    echo -e "\n${BLUE}Database Statistics:${NC}"

    concept_count=$(docker exec knowledge-graph-neo4j cypher-shell -u neo4j -p password \
        "MATCH (c:Concept) RETURN count(c)" --format plain 2>/dev/null | tail -1)
    echo -e "  Concepts: ${GREEN}${concept_count:-0}${NC}"

    source_count=$(docker exec knowledge-graph-neo4j cypher-shell -u neo4j -p password \
        "MATCH (s:Source) RETURN count(s)" --format plain 2>/dev/null | tail -1)
    echo -e "  Sources: ${GREEN}${source_count:-0}${NC}"

    instance_count=$(docker exec knowledge-graph-neo4j cypher-shell -u neo4j -p password \
        "MATCH (i:Instance) RETURN count(i)" --format plain 2>/dev/null | tail -1)
    echo -e "  Instances: ${GREEN}${instance_count:-0}${NC}"

    rel_count=$(docker exec knowledge-graph-neo4j cypher-shell -u neo4j -p password \
        "MATCH ()-[r]->() RETURN count(r)" --format plain 2>/dev/null | tail -1)
    echo -e "  Relationships: ${GREEN}${rel_count:-0}${NC}"
else
    echo -e "${RED}✗ Cannot connect to Neo4j${NC}"
fi

# Check Python environment
echo -e "\n${BLUE}Python Environment:${NC}"
if [ -d "venv" ]; then
    echo -e "${GREEN}✓ Virtual environment exists${NC}"
    if [ -f "venv/bin/python" ]; then
        python_version=$(venv/bin/python --version 2>&1)
        echo -e "  Version: ${python_version}"
    fi
else
    echo -e "${RED}✗ Virtual environment not found${NC}"
    echo -e "${YELLOW}  Run: ./scripts/setup.sh${NC}"
fi

# Check MCP server
echo -e "\n${BLUE}MCP Server:${NC}"
if [ -d "mcp-server/build" ]; then
    echo -e "${GREEN}✓ MCP server is built${NC}"
    if [ -f "mcp-server/build/index.js" ]; then
        size=$(du -h mcp-server/build/index.js | cut -f1)
        echo -e "  Size: ${size}"
    fi
else
    echo -e "${RED}✗ MCP server not built${NC}"
    echo -e "${YELLOW}  Run: ./scripts/setup.sh${NC}"
fi

# Check environment file
echo -e "\n${BLUE}Configuration:${NC}"
if [ -f ".env" ]; then
    echo -e "${GREEN}✓ .env file exists${NC}"

    # Check for required keys (without showing values)
    if grep -q "ANTHROPIC_API_KEY=" .env && ! grep -q "ANTHROPIC_API_KEY=$" .env; then
        echo -e "  ANTHROPIC_API_KEY: ${GREEN}configured${NC}"
    else
        echo -e "  ANTHROPIC_API_KEY: ${RED}missing${NC}"
    fi

    if grep -q "OPENAI_API_KEY=" .env && ! grep -q "OPENAI_API_KEY=$" .env; then
        echo -e "  OPENAI_API_KEY: ${GREEN}configured${NC}"
    else
        echo -e "  OPENAI_API_KEY: ${RED}missing${NC}"
    fi
else
    echo -e "${RED}✗ .env file not found${NC}"
    echo -e "${YELLOW}  Run: ./scripts/setup.sh${NC}"
fi

# Check disk usage
echo -e "\n${BLUE}Disk Usage:${NC}"
if docker volume inspect knowledge-graph-system_neo4j_data &> /dev/null; then
    volume_size=$(docker system df -v | grep knowledge-graph-system_neo4j_data | awk '{print $3}')
    echo -e "  Neo4j data volume: ${volume_size:-unknown}"
fi

# URLs and access
echo -e "\n${BLUE}Access Points:${NC}"
if docker ps | grep -q knowledge-graph-neo4j; then
    echo -e "  Neo4j Browser: ${GREEN}http://localhost:7474${NC}"
    echo -e "  Bolt Protocol: ${GREEN}bolt://localhost:7687${NC}"
    echo -e "  Credentials: neo4j/password"
fi

echo ""
