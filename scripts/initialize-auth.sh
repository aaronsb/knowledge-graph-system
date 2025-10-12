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

echo -e "${BLUE}${BOLD}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║   Knowledge Graph System - Authentication Initialization   ║"
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

# Check if admin user already exists
echo -e "${BLUE}→${NC} Checking if admin user exists..."
ADMIN_EXISTS=$(docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -t -c \
    "SELECT COUNT(*) FROM kg_auth.users WHERE username = 'admin'" 2>/dev/null | xargs)

if [ "$ADMIN_EXISTS" -gt "0" ]; then
    echo -e "${YELLOW}⚠${NC}  Admin user already exists"
    read -p "Do you want to reset the admin password? [y/N]: " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Initialization cancelled${NC}"
        exit 0
    fi
    RESET_MODE=true
else
    echo -e "${GREEN}✓${NC} No admin user found (fresh installation)"
    RESET_MODE=false
fi

# Prompt for admin password
echo ""
echo -e "${BOLD}Admin Password Setup${NC}"
echo -e "${YELLOW}Password requirements:${NC}"
echo "  • Minimum 8 characters"
echo "  • At least one uppercase letter"
echo "  • At least one lowercase letter"
echo "  • At least one digit"
echo "  • At least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)"
echo ""

while true; do
    read -s -p "Enter admin password: " ADMIN_PASSWORD
    echo
    read -s -p "Confirm admin password: " ADMIN_PASSWORD_CONFIRM
    echo

    if [ "$ADMIN_PASSWORD" != "$ADMIN_PASSWORD_CONFIRM" ]; then
        echo -e "${RED}✗ Passwords do not match. Try again.${NC}"
        echo ""
        continue
    fi

    # Validate password strength using Python
    VALIDATION_RESULT=$(python3 << EOF
import sys
sys.path.insert(0, "$PROJECT_ROOT")
from src.api.lib.auth import validate_password_strength

is_valid, error = validate_password_strength("$ADMIN_PASSWORD")
if is_valid:
    print("VALID")
else:
    print(f"INVALID:{error}")
EOF
)

    if [[ $VALIDATION_RESULT == "VALID" ]]; then
        echo -e "${GREEN}✓${NC} Password meets requirements"
        break
    else
        ERROR_MSG=$(echo "$VALIDATION_RESULT" | cut -d':' -f2-)
        echo -e "${RED}✗ $ERROR_MSG${NC}"
        echo ""
    fi
done

# Generate or check JWT_SECRET_KEY
echo ""
echo -e "${BOLD}JWT Secret Key Setup${NC}"

if [ -f "$PROJECT_ROOT/.env" ] && grep -q "^JWT_SECRET_KEY=" "$PROJECT_ROOT/.env"; then
    EXISTING_SECRET=$(grep "^JWT_SECRET_KEY=" "$PROJECT_ROOT/.env" | cut -d'=' -f2)
    if [[ "$EXISTING_SECRET" == *"CHANGE_THIS"* ]]; then
        echo -e "${YELLOW}⚠${NC}  Insecure JWT secret found in .env"
        GENERATE_SECRET=true
    else
        echo -e "${GREEN}✓${NC} JWT secret already configured in .env"
        read -p "Generate new JWT secret? [y/N]: " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            GENERATE_SECRET=true
        else
            GENERATE_SECRET=false
        fi
    fi
else
    echo -e "${BLUE}→${NC} No JWT secret found in .env"
    GENERATE_SECRET=true
fi

if [ "$GENERATE_SECRET" = true ]; then
    # Try openssl first, fall back to Python
    if command -v openssl &> /dev/null; then
        JWT_SECRET=$(openssl rand -hex 32)
        echo -e "${GREEN}✓${NC} Generated JWT secret using openssl"
    else
        JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
        echo -e "${GREEN}✓${NC} Generated JWT secret using Python"
    fi

    # Update or create .env file
    if [ -f "$PROJECT_ROOT/.env" ]; then
        if grep -q "^JWT_SECRET_KEY=" "$PROJECT_ROOT/.env"; then
            # Update existing
            sed -i "s/^JWT_SECRET_KEY=.*/JWT_SECRET_KEY=$JWT_SECRET/" "$PROJECT_ROOT/.env"
        else
            # Append new
            echo "JWT_SECRET_KEY=$JWT_SECRET" >> "$PROJECT_ROOT/.env"
        fi
    else
        # Create new .env
        cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env" 2>/dev/null || true
        echo "JWT_SECRET_KEY=$JWT_SECRET" >> "$PROJECT_ROOT/.env"
    fi
    echo -e "${GREEN}✓${NC} JWT secret saved to .env"
fi

# Create or update admin user in database
echo ""
echo -e "${BOLD}Database Setup${NC}"

if [ "$RESET_MODE" = true ]; then
    echo -e "${BLUE}→${NC} Resetting admin password..."

    # Hash password using Python - capture both stdout and stderr
    HASH_OUTPUT=$(python3 << EOF 2>&1
import sys
sys.path.insert(0, "$PROJECT_ROOT")

# Get version info and check compatibility
try:
    import passlib
    import bcrypt
    passlib_version = passlib.__version__
    try:
        bcrypt_version = bcrypt.__version__
    except AttributeError:
        # bcrypt 5.x changed the version attribute location
        try:
            bcrypt_version = bcrypt.__about__.__version__
        except:
            bcrypt_version = "unknown (5.x+ detected)"

    # Check if we'll hit the compatibility issue
    has_compat_issue = not hasattr(bcrypt, '__about__')

    if has_compat_issue:
        print(f"BCRYPT_COMPAT_INFO:passlib={passlib_version},bcrypt={bcrypt_version}")
except Exception as e:
    print(f"VERSION_CHECK_ERROR:{e}")

from src.api.lib.auth import get_password_hash
print(get_password_hash("$ADMIN_PASSWORD"))
EOF
)

    # Check if there were any errors (anything other than just the hash)
    if echo "$HASH_OUTPUT" | grep -q "VERSION_CHECK_ERROR"; then
        echo -e "${RED}✗ Failed to check crypto library versions${NC}"
        echo "$HASH_OUTPUT" | grep "VERSION_CHECK_ERROR"
    fi

    if echo "$HASH_OUTPUT" | grep -q "Traceback.*Error" | grep -v "bcrypt.*version"; then
        echo -e "${RED}✗ Failed to hash password${NC}"
        echo "$HASH_OUTPUT"
        exit 1
    fi

    # Extract just the hash (last line of output)
    PASSWORD_HASH=$(echo "$HASH_OUTPUT" | tail -n 1)

    # Show informational message if bcrypt compatibility notice appeared
    if echo "$HASH_OUTPUT" | grep -q "BCRYPT_COMPAT_INFO"; then
        COMPAT_INFO=$(echo "$HASH_OUTPUT" | grep "BCRYPT_COMPAT_INFO" | cut -d: -f2)
        PASSLIB_VER=$(echo "$COMPAT_INFO" | cut -d, -f1 | cut -d= -f2)
        BCRYPT_VER=$(echo "$COMPAT_INFO" | cut -d, -f2 | cut -d= -f2)

        echo -e "${YELLOW}ℹ${NC}  Crypto libraries: passlib ${PASSLIB_VER}, bcrypt ${BCRYPT_VER}"
        echo -e "${YELLOW}ℹ${NC}  Note: passlib 1.7.4 expects bcrypt <5.0 (caught compatibility notice, working correctly)"
    fi

    # Update admin password
    docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c \
        "UPDATE kg_auth.users SET password_hash = '$PASSWORD_HASH' WHERE username = 'admin'" > /dev/null

    echo -e "${GREEN}✓${NC} Admin password updated"
else
    echo -e "${BLUE}→${NC} Creating admin user..."

    # Hash password using Python - capture both stdout and stderr
    HASH_OUTPUT=$(python3 << EOF 2>&1
import sys
sys.path.insert(0, "$PROJECT_ROOT")

# Get version info and check compatibility
try:
    import passlib
    import bcrypt
    passlib_version = passlib.__version__
    try:
        bcrypt_version = bcrypt.__version__
    except AttributeError:
        # bcrypt 5.x changed the version attribute location
        try:
            bcrypt_version = bcrypt.__about__.__version__
        except:
            bcrypt_version = "unknown (5.x+ detected)"

    # Check if we'll hit the compatibility issue
    has_compat_issue = not hasattr(bcrypt, '__about__')

    if has_compat_issue:
        print(f"BCRYPT_COMPAT_INFO:passlib={passlib_version},bcrypt={bcrypt_version}")
except Exception as e:
    print(f"VERSION_CHECK_ERROR:{e}")

from src.api.lib.auth import get_password_hash
print(get_password_hash("$ADMIN_PASSWORD"))
EOF
)

    # Check if there were any errors (anything other than just the hash)
    if echo "$HASH_OUTPUT" | grep -q "VERSION_CHECK_ERROR"; then
        echo -e "${RED}✗ Failed to check crypto library versions${NC}"
        echo "$HASH_OUTPUT" | grep "VERSION_CHECK_ERROR"
    fi

    if echo "$HASH_OUTPUT" | grep -q "Traceback.*Error" | grep -v "bcrypt.*version"; then
        echo -e "${RED}✗ Failed to hash password${NC}"
        echo "$HASH_OUTPUT"
        exit 1
    fi

    # Extract just the hash (last line of output)
    PASSWORD_HASH=$(echo "$HASH_OUTPUT" | tail -n 1)

    # Show informational message if bcrypt compatibility notice appeared
    if echo "$HASH_OUTPUT" | grep -q "BCRYPT_COMPAT_INFO"; then
        COMPAT_INFO=$(echo "$HASH_OUTPUT" | grep "BCRYPT_COMPAT_INFO" | cut -d: -f2)
        PASSLIB_VER=$(echo "$COMPAT_INFO" | cut -d, -f1 | cut -d= -f2)
        BCRYPT_VER=$(echo "$COMPAT_INFO" | cut -d, -f2 | cut -d= -f2)

        echo -e "${YELLOW}ℹ${NC}  Crypto libraries: passlib ${PASSLIB_VER}, bcrypt ${BCRYPT_VER}"
        echo -e "${YELLOW}ℹ${NC}  Note: passlib 1.7.4 expects bcrypt <5.0 (caught compatibility notice, working correctly)"
    fi

    # Create admin user
    docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c \
        "INSERT INTO kg_auth.users (username, password_hash, role, created_at)
         VALUES ('admin', '$PASSWORD_HASH', 'admin', NOW())" > /dev/null

    echo -e "${GREEN}✓${NC} Admin user created"
fi

# Success message
echo ""
echo -e "${GREEN}${BOLD}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║              Authentication Initialized!                   ║${NC}"
echo -e "${GREEN}${BOLD}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BOLD}Admin Credentials:${NC}"
echo -e "  Username: ${GREEN}admin${NC}"
echo -e "  Password: ${GREEN}(the password you just set)${NC}"
echo ""
echo -e "${BOLD}Next Steps:${NC}"
echo -e "  1. ${BLUE}Start API server:${NC} ./scripts/start-api.sh"
echo -e "  2. ${BLUE}Login:${NC} curl -X POST http://localhost:8000/auth/login \\"
echo -e "           -d 'username=admin&password=YOUR_PASSWORD'"
echo -e "  3. ${BLUE}View docs:${NC} http://localhost:8000/docs"
echo ""
echo -e "${YELLOW}Security Notes:${NC}"
echo -e "  • JWT secret is stored in ${BOLD}.env${NC}"
echo -e "  • Never commit .env to git (it's in .gitignore)"
echo -e "  • Admin password is hashed with bcrypt (rounds=12)"
echo -e "  • JWT tokens expire after 60 minutes by default"
echo ""
