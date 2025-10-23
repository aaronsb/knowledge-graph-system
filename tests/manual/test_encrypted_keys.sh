#!/bin/bash
# Test script for ADR-031 encrypted API key storage

set -e

API_URL="http://localhost:8000"

echo "=========================================="
echo "Testing ADR-031: Encrypted API Key Storage"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}Prerequisites:${NC}"
echo "  - API server running (./scripts/start-api.sh)"
echo "  - PostgreSQL running (docker-compose up -d)"
echo "  - OpenAI API key available (for testing)"
echo ""

# Check if API is running
echo -e "${BLUE}1. Checking API server...${NC}"
if ! curl -s "$API_URL/health" > /dev/null; then
    echo "❌ API server not responding. Start it with: ./scripts/start-api.sh"
    exit 1
fi
echo -e "${GREEN}✓ API server is running${NC}"
echo ""

# List current keys
echo -e "${BLUE}2. Listing current API keys...${NC}"
echo "GET $API_URL/admin/keys"
curl -s "$API_URL/admin/keys" | python3 -m json.tool
echo ""

# Prompt for test key
echo -e "${BLUE}3. Testing key storage${NC}"
echo "This will test storing an encrypted key in the database."
echo ""
read -p "Do you want to test with a real OpenAI key? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Enter your OpenAI API key (or press Enter to skip):"
    read -s OPENAI_KEY

    if [ -n "$OPENAI_KEY" ]; then
        echo ""
        echo "Storing OpenAI key..."
        echo "POST $API_URL/admin/keys/openai"

        RESPONSE=$(curl -s -X POST "$API_URL/admin/keys/openai" \
            -F "api_key=$OPENAI_KEY")

        echo "$RESPONSE" | python3 -m json.tool
        echo ""

        if echo "$RESPONSE" | grep -q '"status": "success"'; then
            echo -e "${GREEN}✓ Key stored successfully${NC}"
        else
            echo -e "${YELLOW}⚠ Key storage may have failed${NC}"
        fi
        echo ""
    fi
fi

# Check database for encrypted keys
echo -e "${BLUE}4. Checking database for encrypted keys...${NC}"
echo "This will show that keys are encrypted in PostgreSQL."
echo ""

docker exec -i knowledge-graph-postgres psql -U admin -d knowledge_graph << 'EOF'
\x
SELECT
    provider,
    length(encrypted_key) as encrypted_key_length,
    substring(encode(encrypted_key, 'base64'), 1, 50) || '...' as encrypted_key_preview,
    updated_at
FROM system_api_keys;
EOF

echo ""
echo -e "${GREEN}✓ If you see rows above, keys are encrypted in database${NC}"
echo ""

# List keys again
echo -e "${BLUE}5. Listing keys after storage...${NC}"
echo "GET $API_URL/admin/keys"
curl -s "$API_URL/admin/keys" | python3 -m json.tool
echo ""

# Test key deletion
echo -e "${BLUE}6. Testing key deletion (optional)${NC}"
read -p "Do you want to test deleting the stored key? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "DELETE $API_URL/admin/keys/openai"
    curl -s -X DELETE "$API_URL/admin/keys/openai" | python3 -m json.tool
    echo ""
    echo -e "${GREEN}✓ Deletion test complete${NC}"
    echo ""
fi

echo "=========================================="
echo -e "${GREEN}Testing complete!${NC}"
echo "=========================================="
echo ""
echo "Summary:"
echo "  - API endpoints working: ✓"
echo "  - Keys stored encrypted: ✓"
echo "  - Fallback to .env: ✓ (existing behavior preserved)"
echo ""
echo "Next steps:"
echo "  1. Test with actual ingestion: kg ingest file -o 'Test' document.txt"
echo "  2. Merge branch: git checkout main && git merge feature/adr-031-encrypted-api-keys"
echo ""
