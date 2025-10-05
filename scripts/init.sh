#!/bin/bash

# Knowledge Graph System Initialization Script
# This script sets up the complete development environment

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored messages
print_info() {
    echo -e "${BLUE}ℹ ${NC}$1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_section() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Main script starts here
print_section "Knowledge Graph System Initialization"

# 1. Check Prerequisites
print_section "1/7 Checking Prerequisites"

if ! command_exists docker; then
    print_error "Docker is not installed. Please install Docker first:"
    echo "  https://docs.docker.com/get-docker/"
    exit 1
fi
print_success "Docker is installed"

if ! command_exists docker-compose; then
    print_error "Docker Compose is not installed. Please install Docker Compose first:"
    echo "  https://docs.docker.com/compose/install/"
    exit 1
fi
print_success "Docker Compose is installed"

if ! command_exists python3; then
    print_error "Python 3 is not installed. Please install Python 3.11+ first"
    exit 1
fi
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
print_success "Python $PYTHON_VERSION is installed"

if ! command_exists node; then
    print_error "Node.js is not installed. Please install Node.js 18+ first:"
    echo "  https://nodejs.org/"
    exit 1
fi
NODE_VERSION=$(node --version)
print_success "Node.js $NODE_VERSION is installed"

if ! command_exists npm; then
    print_error "npm is not installed. Please install npm first"
    exit 1
fi
NPM_VERSION=$(npm --version)
print_success "npm $NPM_VERSION is installed"

# 2. Environment Configuration
print_section "2/7 Setting Up Environment"

if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        print_success "Created .env from .env.example"
    else
        # Create basic .env if example doesn't exist
        cat > .env << 'EOF'
# Database Configuration
NEO4J_AUTH=neo4j/password
NEO4J_URI=bolt://localhost:7687

# API Keys
OPENAI_API_KEY=your-openai-api-key-here
ANTHROPIC_API_KEY=your-anthropic-api-key-here

# MCP Server
MCP_PORT=3000
LOG_LEVEL=INFO
EOF
        print_success "Created default .env file"
    fi

    print_warning "IMPORTANT: Edit .env file and add your API keys!"
    echo ""
    echo "  1. Add your OpenAI API key (OPENAI_API_KEY)"
    echo "  2. Add your Anthropic API key (ANTHROPIC_API_KEY)"
    echo "  3. Optionally change Neo4j password (NEO4J_AUTH)"
    echo ""
    read -p "Press Enter after editing .env to continue..."
else
    print_info ".env file already exists"
fi

# 3. Start Neo4j
print_section "3/7 Starting Neo4j Database"

print_info "Starting Neo4j with Docker Compose..."
docker-compose up -d neo4j

print_success "Neo4j container started"
print_info "Waiting for Neo4j to be ready..."

# Wait for Neo4j to be ready (max 60 seconds)
MAX_RETRIES=30
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if docker exec neo4j cypher-shell -u neo4j -p password "RETURN 1;" >/dev/null 2>&1; then
        print_success "Neo4j is ready!"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
        print_error "Neo4j failed to start within 60 seconds"
        print_info "Check logs with: docker-compose logs neo4j"
        exit 1
    fi
    sleep 2
    echo -n "."
done
echo ""

# 4. Initialize Neo4j Schema
print_section "4/7 Initializing Database Schema"

if [ -f schema/init.cypher ]; then
    print_info "Loading schema from schema/init.cypher..."
    docker exec -i neo4j cypher-shell -u neo4j -p password < schema/init.cypher
    print_success "Schema initialized successfully"
else
    print_warning "schema/init.cypher not found, creating basic schema..."
    mkdir -p schema
    cat > schema/init.cypher << 'EOF'
// Create constraints for unique IDs
CREATE CONSTRAINT concept_id_unique IF NOT EXISTS
FOR (c:Concept) REQUIRE c.concept_id IS UNIQUE;

CREATE CONSTRAINT source_id_unique IF NOT EXISTS
FOR (s:Source) REQUIRE s.source_id IS UNIQUE;

CREATE CONSTRAINT instance_id_unique IF NOT EXISTS
FOR (i:Instance) REQUIRE i.instance_id IS UNIQUE;

// Create indexes for performance
CREATE INDEX concept_label IF NOT EXISTS
FOR (c:Concept) ON (c.label);

CREATE INDEX source_document IF NOT EXISTS
FOR (s:Source) ON (s.document);

// Create vector index for embeddings (Neo4j 5.11+)
CREATE VECTOR INDEX concept_embeddings IF NOT EXISTS
FOR (c:Concept) ON (c.embedding)
OPTIONS {indexConfig: {
  `vector.dimensions`: 1536,
  `vector.similarity_function`: 'cosine'
}};
EOF
    docker exec -i neo4j cypher-shell -u neo4j -p password < schema/init.cypher
    print_success "Basic schema created and initialized"
fi

# 5. Python Virtual Environment
print_section "5/7 Setting Up Python Environment"

if [ ! -d "venv" ]; then
    print_info "Creating Python virtual environment..."
    python3 -m venv venv
    print_success "Virtual environment created"
else
    print_info "Virtual environment already exists"
fi

print_info "Installing Python dependencies..."
source venv/bin/activate

if [ -f requirements.txt ]; then
    pip install -q --upgrade pip
    pip install -q -r requirements.txt
    print_success "Python dependencies installed"
else
    print_warning "requirements.txt not found, skipping Python dependencies"
fi

# 6. MCP Server Setup
print_section "6/7 Setting Up MCP Server"

if [ -d "mcp-server" ]; then
    cd mcp-server
    print_info "Installing MCP server dependencies..."
    npm install --silent
    print_success "Dependencies installed"

    print_info "Building MCP server..."
    npm run build
    print_success "MCP server built successfully"
    cd ..
else
    print_warning "mcp-server directory not found, skipping MCP setup"
fi

# 7. Display Success Message and Next Steps
print_section "Setup Complete!"

echo ""
print_success "Knowledge Graph System is ready to use!"
echo ""

echo -e "${GREEN}Next Steps:${NC}"
echo ""
echo "1. Configure Claude Desktop:"
echo "   Add this to your Claude Desktop config:"
echo "   (Location: ~/Library/Application Support/Claude/claude_desktop_config.json on macOS)"
echo "   (Location: %APPDATA%/Claude/claude_desktop_config.json on Windows)"
echo ""
echo -e "${YELLOW}   {${NC}"
echo -e "${YELLOW}     \"mcpServers\": {${NC}"
echo -e "${YELLOW}       \"knowledge-graph\": {${NC}"
echo -e "${YELLOW}         \"command\": \"node\",${NC}"
echo -e "${YELLOW}         \"args\": [${NC}"
echo -e "${YELLOW}           \"$(pwd)/mcp-server/build/index.js\"${NC}"
echo -e "${YELLOW}         ],${NC}"
echo -e "${YELLOW}         \"env\": {${NC}"
echo -e "${YELLOW}           \"NEO4J_URI\": \"bolt://localhost:7687\",${NC}"
echo -e "${YELLOW}           \"NEO4J_USER\": \"neo4j\",${NC}"
echo -e "${YELLOW}           \"NEO4J_PASSWORD\": \"password\",${NC}"
echo -e "${YELLOW}           \"OPENAI_API_KEY\": \"your-openai-key-here\"${NC}"
echo -e "${YELLOW}         }${NC}"
echo -e "${YELLOW}       }${NC}"
echo -e "${YELLOW}     }${NC}"
echo -e "${YELLOW}   }${NC}"
echo ""

echo "2. Run document ingestion:"
echo "   source venv/bin/activate"
echo "   python ingest/ingest.py docs/watts_lecture_1.txt --document-name \"Watts Doc 1\""
echo ""

echo "3. Access Neo4j Browser:"
echo "   URL: http://localhost:7474"
echo "   Username: neo4j"
echo "   Password: password"
echo ""

echo -e "${GREEN}Useful Commands:${NC}"
echo "  - Start services:    docker-compose up -d"
echo "  - Stop services:     docker-compose down"
echo "  - View logs:         docker-compose logs -f"
echo "  - Neo4j shell:       docker exec -it neo4j cypher-shell -u neo4j -p password"
echo "  - Activate Python:   source venv/bin/activate"
echo ""

print_success "Happy knowledge graphing!"
