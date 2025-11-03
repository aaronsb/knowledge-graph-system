#!/bin/bash
set -e

# set-admin-password.sh
# Simplified script to set admin password only
# Can be run standalone or called by other scripts

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

# Use venv Python if available, otherwise system python3
if [ -f "$PROJECT_ROOT/venv/bin/python" ]; then
    PYTHON="$PROJECT_ROOT/venv/bin/python"
elif [ -f "$PROJECT_ROOT/venv/bin/python3" ]; then
    PYTHON="$PROJECT_ROOT/venv/bin/python3"
else
    PYTHON="python3"
fi

# Parse arguments
NON_INTERACTIVE=false
CREATE_IF_MISSING=false
QUIET=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --non-interactive)
            NON_INTERACTIVE=true
            shift
            ;;
        --create)
            CREATE_IF_MISSING=true
            shift
            ;;
        --quiet)
            QUIET=true
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Show header (unless quiet)
if [ "$QUIET" = false ]; then
    echo -e "${BLUE}${BOLD}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║         Knowledge Graph System - Set Admin Password       ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
fi

# Check if PostgreSQL is running
if [ "$QUIET" = false ]; then
    echo -e "${BLUE}→${NC} Checking PostgreSQL connection..."
fi

if ! docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c "SELECT 1" > /dev/null 2>&1; then
    echo -e "${RED}✗ PostgreSQL is not running${NC}"
    echo -e "${YELLOW}  Run: ./scripts/database/start-database.sh${NC}"
    exit 1
fi

if [ "$QUIET" = false ]; then
    echo -e "${GREEN}✓${NC} PostgreSQL is running"
fi

# Check if admin user exists
ADMIN_EXISTS=$(docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -t -c \
    "SELECT COUNT(*) FROM kg_auth.users WHERE username = 'admin'" 2>/dev/null | xargs)

if [ "$ADMIN_EXISTS" -eq "0" ]; then
    if [ "$CREATE_IF_MISSING" = true ]; then
        if [ "$QUIET" = false ]; then
            echo -e "${BLUE}→${NC} Admin user does not exist, will create"
        fi
        RESET_MODE=false
    else
        echo -e "${RED}✗ Admin user not found${NC}"
        echo -e "${YELLOW}  Run with --create flag to create admin user${NC}"
        echo -e "${YELLOW}  Or run: ./scripts/setup/initialize-platform.sh${NC}"
        exit 1
    fi
else
    if [ "$QUIET" = false ]; then
        echo -e "${GREEN}✓${NC} Admin user exists"
    fi
    RESET_MODE=true
fi

# Prompt for admin password (unless non-interactive)
if [ "$NON_INTERACTIVE" = false ]; then
    if [ "$QUIET" = false ]; then
        echo ""
        echo -e "${BOLD}Admin Password Setup${NC}"
        echo -e "${YELLOW}Password requirements:${NC}"
        echo "  • Minimum 8 characters"
        echo "  • At least one uppercase letter"
        echo "  • At least one lowercase letter"
        echo "  • At least one digit"
        echo "  • At least one special character (!@#\$%^&*()_+-=[]{}|;:,.<>?)"
        echo ""
    fi

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
        VALIDATION_RESULT=$($PYTHON << EOF
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
else
    # Non-interactive mode requires ADMIN_PASSWORD env var
    if [ -z "$ADMIN_PASSWORD" ]; then
        echo -e "${RED}✗ ADMIN_PASSWORD environment variable not set${NC}"
        echo -e "${YELLOW}  In non-interactive mode, set: export ADMIN_PASSWORD='your-password'${NC}"
        exit 1
    fi
fi

# Hash the password
if [ "$QUIET" = false ]; then
    echo ""
    echo -e "${BLUE}→${NC} Hashing password..."
fi

HASH_OUTPUT=$($PYTHON << EOF 2>&1
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

# Check for errors
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
if [ "$QUIET" = false ]; then
    if echo "$HASH_OUTPUT" | grep -q "BCRYPT_COMPAT_INFO"; then
        COMPAT_INFO=$(echo "$HASH_OUTPUT" | grep "BCRYPT_COMPAT_INFO" | cut -d: -f2)
        PASSLIB_VER=$(echo "$COMPAT_INFO" | cut -d, -f1 | cut -d= -f2)
        BCRYPT_VER=$(echo "$COMPAT_INFO" | cut -d, -f2 | cut -d= -f2)

        echo -e "${YELLOW}ℹ${NC}  Crypto libraries: passlib ${PASSLIB_VER}, bcrypt ${BCRYPT_VER}"
        echo -e "${YELLOW}ℹ${NC}  Note: passlib 1.7.4 expects bcrypt <5.0 (caught compatibility notice, working correctly)"
    fi
fi

# Update or create admin user in database
if [ "$RESET_MODE" = true ]; then
    if [ "$QUIET" = false ]; then
        echo -e "${BLUE}→${NC} Updating admin password..."
    fi

    docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c \
        "UPDATE kg_auth.users SET password_hash = '$PASSWORD_HASH' WHERE username = 'admin'" > /dev/null

    if [ "$QUIET" = false ]; then
        echo -e "${GREEN}✓${NC} Admin password updated"
    fi
else
    if [ "$QUIET" = false ]; then
        echo -e "${BLUE}→${NC} Creating admin user..."
    fi

    docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c \
        "INSERT INTO kg_auth.users (username, password_hash, primary_role, created_at)
         VALUES ('admin', '$PASSWORD_HASH', 'admin', NOW())" > /dev/null

    if [ "$QUIET" = false ]; then
        echo -e "${GREEN}✓${NC} Admin user created"
    fi
fi

# Export password hash for use by calling scripts
export ADMIN_PASSWORD_HASH="$PASSWORD_HASH"

# Success message (unless quiet)
if [ "$QUIET" = false ]; then
    echo ""
    echo -e "${GREEN}${BOLD}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}${BOLD}║            Admin Password Set Successfully!               ║${NC}"
    echo -e "${GREEN}${BOLD}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BOLD}Test Login:${NC}"
    echo -e "  ${BLUE}kg login -u admin${NC}"
    echo ""
fi

# Exit successfully - hash is available in $ADMIN_PASSWORD_HASH for calling scripts
exit 0
