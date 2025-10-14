#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Check for and activate virtual environment
if [ -d "$PROJECT_ROOT/venv" ]; then
    source "$PROJECT_ROOT/venv/bin/activate"
elif [ -d "$PROJECT_ROOT/.venv" ]; then
    source "$PROJECT_ROOT/.venv/bin/activate"
fi

echo -e "${BLUE}${BOLD}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║        Knowledge Graph System - Password Reset            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check if PostgreSQL is running
echo -e "${BLUE}→${NC} Checking PostgreSQL connection..."
if ! docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c "SELECT 1" > /dev/null 2>&1; then
    echo -e "${RED}✗ PostgreSQL is not running${NC}"
    echo -e "${YELLOW}  Run: docker-compose up -d${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} PostgreSQL is running"

# List available users
echo ""
echo -e "${BOLD}Available Users:${NC}"
USERS=$(docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -t -c \
    "SELECT username FROM kg_auth.users ORDER BY username" 2>/dev/null)

if [ -z "$USERS" ]; then
    echo -e "${RED}✗ No users found in database${NC}"
    echo -e "${YELLOW}  Run: ./scripts/initialize-auth.sh to create admin user${NC}"
    exit 1
fi

echo "$USERS" | while read -r username; do
    if [ ! -z "$username" ]; then
        echo -e "  • $username"
    fi
done

# Prompt for username
echo ""
read -p "Enter username to reset: " USERNAME

if [ -z "$USERNAME" ]; then
    echo -e "${RED}✗ Username cannot be empty${NC}"
    exit 1
fi

# Check if user exists
USER_EXISTS=$(docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -t -c \
    "SELECT COUNT(*) FROM kg_auth.users WHERE username = '$USERNAME'" 2>/dev/null | xargs)

if [ "$USER_EXISTS" -eq "0" ]; then
    echo -e "${RED}✗ User '$USERNAME' not found${NC}"
    exit 1
fi

# Prompt for new password
echo ""
echo -e "${BOLD}Password Requirements:${NC}"
echo "  • Minimum 8 characters"
echo "  • At least one uppercase letter"
echo "  • At least one lowercase letter"
echo "  • At least one digit"
echo "  • At least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)"
echo ""

while true; do
    read -s -p "Enter new password: " NEW_PASSWORD
    echo
    read -s -p "Confirm new password: " NEW_PASSWORD_CONFIRM
    echo

    if [ "$NEW_PASSWORD" != "$NEW_PASSWORD_CONFIRM" ]; then
        echo -e "${RED}✗ Passwords do not match. Try again.${NC}"
        echo ""
        continue
    fi

    # Validate password strength using Python
    VALIDATION_RESULT=$(python3 << EOF 2>&1
import sys
sys.path.insert(0, "$PROJECT_ROOT")
from src.api.lib.auth import validate_password_strength

is_valid, error = validate_password_strength("$NEW_PASSWORD")
if is_valid:
    print("VALID")
else:
    print(f"INVALID:{error}")
EOF
)

    if echo "$VALIDATION_RESULT" | grep -q "ModuleNotFoundError"; then
        echo -e "${RED}✗ Python dependencies not installed${NC}"
        echo -e "${YELLOW}  Run: source venv/bin/activate && pip install -r requirements.txt${NC}"
        exit 1
    elif [[ $VALIDATION_RESULT == "VALID" ]]; then
        echo -e "${GREEN}✓${NC} Password meets requirements"
        break
    else
        ERROR_MSG=$(echo "$VALIDATION_RESULT" | cut -d':' -f2-)
        echo -e "${RED}✗ $ERROR_MSG${NC}"
        echo ""
    fi
done

# Hash the new password
echo ""
echo -e "${BLUE}→${NC} Hashing password..."

HASH_OUTPUT=$(python3 << EOF 2>&1
import sys
sys.path.insert(0, "$PROJECT_ROOT")
from src.api.lib.auth import get_password_hash
print(get_password_hash("$NEW_PASSWORD"))
EOF
)

if echo "$HASH_OUTPUT" | grep -q "ModuleNotFoundError"; then
    echo -e "${RED}✗ Python dependencies not installed${NC}"
    echo -e "${YELLOW}  Run: source venv/bin/activate && pip install -r requirements.txt${NC}"
    exit 1
elif echo "$HASH_OUTPUT" | grep -q "Traceback.*Error"; then
    echo -e "${RED}✗ Failed to hash password${NC}"
    echo "$HASH_OUTPUT"
    exit 1
fi

PASSWORD_HASH=$(echo "$HASH_OUTPUT" | tail -n 1)
echo -e "${GREEN}✓${NC} Password hashed"

# Update password in database
echo -e "${BLUE}→${NC} Updating password in database..."
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c \
    "UPDATE kg_auth.users SET password_hash = '$PASSWORD_HASH' WHERE username = '$USERNAME'" > /dev/null

echo -e "${GREEN}✓${NC} Password updated successfully"

# Success message
echo ""
echo -e "${GREEN}${BOLD}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║                Password Reset Complete!                    ║${NC}"
echo -e "${GREEN}${BOLD}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BOLD}Updated Credentials:${NC}"
echo -e "  Username: ${GREEN}$USERNAME${NC}"
echo -e "  Password: ${GREEN}(the password you just set)${NC}"
echo ""
echo -e "${BOLD}Test Login:${NC}"
echo -e "  ${BLUE}curl -X POST http://localhost:8000/auth/login \\${NC}"
echo -e "    ${BLUE}-d 'username=$USERNAME&password=YOUR_PASSWORD'${NC}"
echo ""
