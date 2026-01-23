#!/bin/bash
# ============================================================================
# garage-manager.sh - Garage Object Storage Management
# ============================================================================
#
# Provides status, initialization, and repair operations for Garage.
# Runs inside the operator container, called via: ./operator.sh garage <cmd>
#
# Commands:
#   status  - Check Garage health and configuration
#   init    - Initialize layout, bucket, and credentials
#   repair  - Diagnose and fix common issues
#
# ============================================================================

set -e

# Colors
RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
BLUE=$'\033[0;34m'
BOLD=$'\033[1m'
NC=$'\033[0m'

# Workspace detection (works for both dev and standalone)
if [ -d "/workspace" ]; then
    WORKSPACE="/workspace"
elif [ -d "/project" ]; then
    WORKSPACE="/project"
else
    WORKSPACE="$(pwd)"
fi

# Garage configuration
GARAGE_HOST="${GARAGE_HOST:-garage}"
GARAGE_ADMIN_PORT="${GARAGE_ADMIN_PORT:-3903}"
GARAGE_S3_PORT="${GARAGE_S3_PORT:-3900}"
GARAGE_BUCKET="${GARAGE_BUCKET:-kg-storage}"

# ============================================================================
# Utility Functions
# ============================================================================

log_info()    { echo -e "${BLUE}ℹ${NC} $*"; }
log_success() { echo -e "${GREEN}✓${NC} $*"; }
log_warning() { echo -e "${YELLOW}⚠${NC} $*"; }
log_error()   { echo -e "${RED}✗${NC} $*"; }
log_section() { echo -e "\n${BOLD}$*${NC}"; }

garage_admin() {
    # Execute garage admin command
    docker exec knowledge-graph-garage /garage "$@" 2>&1
}

garage_healthy() {
    # Check if Garage is responding
    curl -sf "http://${GARAGE_HOST}:${GARAGE_ADMIN_PORT}/health" >/dev/null 2>&1
}

# ============================================================================
# Status Command
# ============================================================================

cmd_status() {
    log_section "Garage Object Storage Status"

    # Container status
    echo -e "\n${BOLD}Container:${NC}"
    if docker ps --format '{{.Names}} {{.Status}}' | grep -q "knowledge-graph-garage"; then
        local status=$(docker ps --format '{{.Status}}' --filter 'name=knowledge-graph-garage')
        log_success "Container running: $status"
    else
        log_error "Container not running"
        echo "  Run: ./operator.sh start"
        return 1
    fi

    # Health check
    echo -e "\n${BOLD}Health:${NC}"
    if garage_healthy; then
        log_success "Garage responding on port $GARAGE_ADMIN_PORT"
    else
        log_error "Garage not responding"
        echo "  Check logs: ./operator.sh logs garage"
        return 1
    fi

    # Layout status
    echo -e "\n${BOLD}Layout:${NC}"
    local layout_output
    if layout_output=$(garage_admin layout show 2>&1); then
        if echo "$layout_output" | grep -q "NO NODES"; then
            log_warning "No nodes in layout"
            echo "  Run: ./operator.sh garage init"
        else
            log_success "Layout configured"
            echo "$layout_output" | head -10 | sed 's/^/  /'
        fi
    else
        log_error "Could not check layout"
    fi

    # Bucket status
    echo -e "\n${BOLD}Buckets:${NC}"
    local bucket_output
    if bucket_output=$(garage_admin bucket list 2>&1); then
        if echo "$bucket_output" | grep -q "$GARAGE_BUCKET"; then
            log_success "Bucket '$GARAGE_BUCKET' exists"
        else
            log_warning "Bucket '$GARAGE_BUCKET' not found"
            echo "  Run: ./operator.sh garage init"
        fi
    else
        log_error "Could not list buckets"
    fi

    # Key status
    echo -e "\n${BOLD}API Keys:${NC}"
    local key_output
    if key_output=$(garage_admin key list 2>&1); then
        local key_count=$(echo "$key_output" | grep -c "Key ID" || echo "0")
        if [ "$key_count" -gt 0 ]; then
            log_success "$key_count API key(s) configured"
        else
            log_warning "No API keys configured"
            echo "  Run: ./operator.sh garage init"
        fi
    else
        log_error "Could not list keys"
    fi

    # Check credentials in database
    echo -e "\n${BOLD}Stored Credentials:${NC}"
    if python /workspace/operator/configure.py api-key list 2>/dev/null | grep -q "garage"; then
        log_success "Garage credentials stored in database"
    else
        log_warning "Garage credentials not in database"
        echo "  Run: ./operator.sh garage init"
    fi
}

# ============================================================================
# Init Command
# ============================================================================

cmd_init() {
    log_section "Initializing Garage Object Storage"

    local force=false
    [[ "$1" == "--force" ]] && force=true

    # Check container
    if ! docker ps --format '{{.Names}}' | grep -q "knowledge-graph-garage"; then
        log_error "Garage container not running"
        echo "  Start infrastructure first: ./operator.sh start"
        return 1
    fi

    # Wait for Garage to be ready
    log_info "Waiting for Garage to be ready..."
    local retries=30
    while ! garage_healthy && [ $retries -gt 0 ]; do
        sleep 1
        retries=$((retries - 1))
    done

    if ! garage_healthy; then
        log_error "Garage failed to become healthy"
        echo "  Check logs: ./operator.sh logs garage"
        return 1
    fi
    log_success "Garage is ready"

    # Get node ID
    log_info "Getting node ID..."
    local node_id
    node_id=$(garage_admin node id 2>&1 | grep -oE '[a-f0-9]{64}' | head -1)

    if [ -z "$node_id" ]; then
        log_error "Could not get node ID"
        return 1
    fi
    log_success "Node ID: ${node_id:0:16}..."

    # Configure layout
    log_info "Configuring storage layout..."
    if ! garage_admin layout show 2>&1 | grep -q "$node_id"; then
        garage_admin layout assign "$node_id" -z dc1 -c 1G 2>&1 || true
        garage_admin layout apply --version 1 2>&1 || \
            garage_admin layout apply --version 2 2>&1 || \
            garage_admin layout apply --version 3 2>&1 || true
        log_success "Layout configured"
    else
        log_info "Layout already configured"
    fi

    # Create bucket
    log_info "Creating bucket '$GARAGE_BUCKET'..."
    if ! garage_admin bucket list 2>&1 | grep -q "$GARAGE_BUCKET"; then
        garage_admin bucket create "$GARAGE_BUCKET" 2>&1 || true
        log_success "Bucket created"
    else
        log_info "Bucket already exists"
    fi

    # Create API key
    log_info "Creating API key..."
    local key_output

    # Check if key already exists
    if garage_admin key info kg-api 2>&1 | grep -q "Key ID"; then
        log_info "API key 'kg-api' already exists"
        if [ "$force" = true ]; then
            log_info "Recreating key (--force specified)..."
            garage_admin key delete kg-api 2>&1 || true
            key_output=$(garage_admin key create kg-api 2>&1)
        else
            # Get existing key info
            key_output=$(garage_admin key info kg-api 2>&1)
        fi
    else
        key_output=$(garage_admin key create kg-api 2>&1)
        log_success "API key created"
    fi

    # Parse key credentials
    local key_id secret_key
    key_id=$(echo "$key_output" | grep -E "Key ID|GK" | head -1 | awk '{print $NF}')
    secret_key=$(echo "$key_output" | grep "Secret key" | awk '{print $NF}')

    if [ -z "$key_id" ]; then
        log_error "Could not parse key ID from output"
        echo "$key_output"
        return 1
    fi

    # Grant bucket permissions
    log_info "Granting bucket permissions..."
    garage_admin bucket allow "$GARAGE_BUCKET" --read --write --owner --key kg-api 2>&1 || true
    log_success "Permissions granted"

    # Store credentials in database (only if we have the secret)
    if [ -n "$secret_key" ]; then
        log_info "Storing credentials in database..."
        python /workspace/operator/configure.py api-key garage --key "${key_id}:${secret_key}" 2>&1 || {
            log_error "Failed to store credentials"
            echo "  Manual command: ./operator.sh api-key garage --key '${key_id}:${secret_key}'"
        }
        log_success "Credentials stored"
    else
        log_warning "Could not get secret key (key already existed)"
        echo "  If credentials not in database, recreate: ./operator.sh garage init --force"
    fi

    log_section "Garage Initialization Complete"
    echo "  Bucket: $GARAGE_BUCKET"
    echo "  Key ID: $key_id"
    [ -n "$secret_key" ] && echo "  Status: Credentials stored in database"
}

# ============================================================================
# Repair Command
# ============================================================================

cmd_repair() {
    log_section "Garage Diagnostics & Repair"

    # Run status first
    echo "Running diagnostics..."
    echo

    local issues=0

    # Check container
    if ! docker ps --format '{{.Names}}' | grep -q "knowledge-graph-garage"; then
        log_error "Container not running"
        echo "  Fix: ./operator.sh start"
        issues=$((issues + 1))
    fi

    # Check RPC secret
    if [ -z "$GARAGE_RPC_SECRET" ]; then
        log_error "GARAGE_RPC_SECRET not set in environment"
        echo "  Fix: Add GARAGE_RPC_SECRET to .env file:"
        echo "    GARAGE_RPC_SECRET=\$(openssl rand -hex 32)"
        echo "  Then restart: ./operator.sh restart garage"
        issues=$((issues + 1))
    fi

    # Check health
    if garage_healthy; then
        # Check layout
        if garage_admin layout show 2>&1 | grep -q "NO NODES"; then
            log_warning "Layout not configured"
            echo "  Fix: ./operator.sh garage init"
            issues=$((issues + 1))
        fi

        # Check bucket
        if ! garage_admin bucket list 2>&1 | grep -q "$GARAGE_BUCKET"; then
            log_warning "Bucket '$GARAGE_BUCKET' missing"
            echo "  Fix: ./operator.sh garage init"
            issues=$((issues + 1))
        fi

        # Check database credentials
        if ! python /workspace/operator/configure.py api-key list 2>/dev/null | grep -q "garage"; then
            log_warning "Credentials not in database"
            echo "  Fix: ./operator.sh garage init --force"
            issues=$((issues + 1))
        fi
    else
        log_error "Garage not responding - check logs"
        issues=$((issues + 1))
    fi

    echo
    if [ $issues -eq 0 ]; then
        log_success "No issues found"
    else
        log_warning "$issues issue(s) found"
        echo
        echo "Quick fix: ./operator.sh garage init"
    fi
}

# ============================================================================
# Help
# ============================================================================

show_help() {
    cat << EOF
${BOLD}Garage Object Storage Manager${NC}

Usage: ./operator.sh garage <command> [options]

${BOLD}Commands:${NC}
  status           Check Garage health and configuration
  init [--force]   Initialize layout, bucket, and credentials
  repair           Diagnose issues and suggest fixes

${BOLD}Examples:${NC}
  ./operator.sh garage status
  ./operator.sh garage init
  ./operator.sh garage init --force   # Recreate API key

${BOLD}Common Issues:${NC}
  "Invalid RPC secret" - GARAGE_RPC_SECRET missing from .env
  "Bucket not found"   - Run './operator.sh garage init'
  "No credentials"     - Run './operator.sh garage init --force'

EOF
}

# ============================================================================
# Main
# ============================================================================

case "${1:-help}" in
    status)  cmd_status ;;
    init)    shift; cmd_init "$@" ;;
    repair)  cmd_repair ;;
    help|--help|-h) show_help ;;
    *) echo -e "${RED}Unknown command: $1${NC}"; show_help; exit 1 ;;
esac
