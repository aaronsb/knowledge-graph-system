#!/bin/bash
# ============================================================================
# Knowledge Graph Platform Installer
# ============================================================================
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/aaronsb/knowledge-graph-system/main/install.sh | bash
#
# Headless:
#   curl -fsSL ... | bash -s -- --hostname kg.example.com --ai-provider openai --ai-key "$KEY"
#
# Interactive:
#   curl -fsSL ... | bash
# ============================================================================

set -e

# Version and source configuration
KG_VERSION="${KG_VERSION:-main}"
KG_REPO_RAW="https://raw.githubusercontent.com/aaronsb/knowledge-graph-system/${KG_VERSION}"
KG_INSTALL_DIR="${KG_INSTALL_DIR:-$HOME/knowledge-graph}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ============================================================================
# Configuration (set via arguments or interactive prompts)
# ============================================================================
HOSTNAME=""
AI_PROVIDER=""
AI_MODEL=""
AI_KEY=""
ADMIN_PASSWORD=""
GPU_MODE="auto"
INSTALL_DIR=""
INTERACTIVE=true
VALIDATION_FAILED=false
VALIDATION_ERRORS=()

# SSL Configuration
SSL_MODE="offload"       # offload, selfsigned, letsencrypt, manual
SSL_EMAIL=""             # Required for Let's Encrypt
SSL_CERT_PATH=""         # For manual SSL
SSL_KEY_PATH=""          # For manual SSL
SSL_DNS_PROVIDER=""      # For DNS-01 challenge (e.g., dns_porkbun, dns_cloudflare)
SSL_DNS_KEY=""           # DNS API key
SSL_DNS_SECRET=""        # DNS API secret

# Macvlan Configuration (for dedicated LAN IP)
MACVLAN_ENABLED=false    # Whether macvlan is enabled
MACVLAN_MODE=""          # create, use, delete
MACVLAN_NETWORK="kg-macvlan"  # Network name (standard name for detection)
MACVLAN_PARENT=""        # Parent interface for creation (e.g., eth0, eno1)
MACVLAN_SUBNET=""        # Subnet for creation (e.g., 192.168.1.0/24)
MACVLAN_GATEWAY=""       # Gateway for creation (e.g., 192.168.1.1)
MACVLAN_IP=""            # Static IP (optional - omit for DHCP)
MACVLAN_MAC=""           # MAC address for DHCP persistence (auto-generated if omitted)

# ============================================================================
# Help
# ============================================================================
show_help() {
    cat << EOF
${BOLD}Knowledge Graph Platform Installer${NC}

Install the Knowledge Graph system on a fresh server.

${BOLD}Usage:${NC}
  curl -fsSL <url>/install.sh | bash                    # Interactive mode
  curl -fsSL <url>/install.sh | bash -s -- [OPTIONS]    # Headless mode

${BOLD}Options:${NC}
  --hostname HOSTNAME       Public hostname or IP for web access (required for headless)
                            Examples: kg.example.com, 192.168.1.100

  --ai-provider PROVIDER    AI extraction provider: openai, anthropic, ollama
                            (required for headless, unless --skip-ai)

  --ai-model MODEL          Model name (default: gpt-4o for openai, claude-sonnet-4 for anthropic)

  --ai-key KEY              API key for the AI provider
                            (required for openai/anthropic, unless --skip-ai)

  --admin-password PASS     Admin user password (default: auto-generated)

  --gpu MODE                GPU acceleration: auto, nvidia, amd, cpu (default: auto)

  --install-dir DIR         Installation directory (default: ~/knowledge-graph)

  --skip-ai                 Skip AI provider configuration (configure later)

  --help                    Show this help message

${BOLD}SSL/HTTPS Options:${NC}
  --ssl MODE                SSL mode: offload, selfsigned, letsencrypt, manual (default: offload)
                            • offload: HTTP only - for use behind SSL-terminating reverse proxy
                            • selfsigned: Generate self-signed certificate (testing/internal)
                            • letsencrypt: Auto-generate certs via Let's Encrypt
                            • manual: Use existing certificates

  --ssl-email EMAIL         Email for Let's Encrypt registration (required for letsencrypt)

  --ssl-cert PATH           Path to SSL certificate file (required for manual)

  --ssl-key PATH            Path to SSL private key file (required for manual)

  --ssl-dns PROVIDER        DNS provider for DNS-01 challenge (e.g., dns_porkbun, dns_cloudflare)
                            Uses acme.sh instead of certbot - works behind firewalls/NAT
                            See: https://github.com/acmesh-official/acme.sh/wiki/dnsapi

  --ssl-dns-key KEY         DNS API key (provider-specific, e.g., Porkbun API key)

  --ssl-dns-secret SECRET   DNS API secret (provider-specific, e.g., Porkbun secret key)

${BOLD}Macvlan Options (Dedicated LAN IP):${NC}
  --macvlan                 Enable macvlan networking (auto-detects existing kg-macvlan network)
                            Useful when ports 80/443 are already in use on the host

  --macvlan-create          Create new kg-macvlan network (requires parent/subnet/gateway)
  --macvlan-delete          Delete existing kg-macvlan network (for cleanup)

  --macvlan-parent IFACE    Parent network interface (e.g., eth0, eno1) - required for create
  --macvlan-subnet CIDR     Network subnet (e.g., 192.168.1.0/24) - required for create
  --macvlan-gateway IP      Gateway IP (e.g., 192.168.1.1) - required for create

  --macvlan-ip IP           Static IP on macvlan network (optional - omit for DHCP reservation)
  --macvlan-mac MAC         MAC address for container (optional - auto-generated for DHCP)
                            Use consistent MAC for DHCP reservation to get same IP

  See docs/deployment/macvlan-dedicated-ip.md for setup guide.

${BOLD}Examples:${NC}

  # Interactive installation (prompts for configuration)
  curl -fsSL https://raw.githubusercontent.com/.../install.sh | bash

  # Headless with OpenAI
  curl -fsSL .../install.sh | bash -s -- \\
    --hostname kg.example.com \\
    --ai-provider openai \\
    --ai-key "\$OPENAI_API_KEY"

  # Headless with Anthropic
  curl -fsSL .../install.sh | bash -s -- \\
    --hostname 192.168.1.50 \\
    --ai-provider anthropic \\
    --ai-model claude-sonnet-4 \\
    --ai-key "\$ANTHROPIC_API_KEY"

  # Minimal (configure AI later via web UI)
  curl -fsSL .../install.sh | bash -s -- \\
    --hostname kg.example.com \\
    --skip-ai

  # With HTTPS via Let's Encrypt
  curl -fsSL .../install.sh | bash -s -- \\
    --hostname kg.example.com \\
    --ssl letsencrypt \\
    --ssl-email admin@example.com \\
    --ai-provider openai \\
    --ai-key "\$OPENAI_API_KEY"

  # With existing SSL certificates
  curl -fsSL .../install.sh | bash -s -- \\
    --hostname kg.example.com \\
    --ssl manual \\
    --ssl-cert /path/to/fullchain.pem \\
    --ssl-key /path/to/privkey.pem \\
    --skip-ai

  # With Let's Encrypt DNS-01 challenge (works behind NAT/firewall)
  curl -fsSL .../install.sh | bash -s -- \\
    --hostname kg.internal.example.com \\
    --ssl letsencrypt \\
    --ssl-email admin@example.com \\
    --ssl-dns dns_porkbun \\
    --ssl-dns-key "\$PORKBUN_API_KEY" \\
    --ssl-dns-secret "\$PORKBUN_SECRET_KEY" \\
    --skip-ai

  # Create macvlan network with static IP
  curl -fsSL .../install.sh | bash -s -- \\
    --hostname kg.example.com \\
    --ssl letsencrypt --ssl-email admin@example.com \\
    --ssl-dns dns_porkbun --ssl-dns-key "\$PORKBUN_API_KEY" --ssl-dns-secret "\$PORKBUN_SECRET_KEY" \\
    --macvlan-create --macvlan-parent eno1 \\
    --macvlan-subnet 192.168.1.0/24 --macvlan-gateway 192.168.1.1 \\
    --macvlan-ip 192.168.1.20 \\
    --skip-ai

  # Create macvlan with DHCP (reserve the output MAC in your router)
  curl -fsSL .../install.sh | bash -s -- \\
    --hostname kg.example.com \\
    --macvlan-create --macvlan-parent eno1 \\
    --macvlan-subnet 192.168.1.0/24 --macvlan-gateway 192.168.1.1 \\
    --skip-ai

  # Reinstall using existing macvlan network (auto-detects kg-macvlan)
  curl -fsSL .../install.sh | bash -s -- \\
    --hostname kg.example.com \\
    --macvlan \\
    --skip-ai

${BOLD}Requirements:${NC}
  - Linux (Ubuntu 20.04+ or Debian 11+ recommended)
  - Docker (will be installed if missing)
  - 4GB RAM minimum, 8GB recommended
  - 20GB disk space

${BOLD}After Installation:${NC}
  - Web UI: https://HOSTNAME (or http://HOSTNAME:3000 for offload mode)
  - API: https://HOSTNAME/api (or http://HOSTNAME:8000)
  - Default admin user: admin

${BOLD}Ongoing Management:${NC}
  This installer sets up the platform. For day-to-day management, use:

    cd ~/knowledge-graph && ./operator.sh help

  Key commands:
    ./operator.sh status     # Check platform health
    ./operator.sh upgrade    # Pull updates and restart
    ./operator.sh logs       # View container logs
    ./operator.sh shell      # Access configuration tools

EOF
}

# ============================================================================
# Logging
# ============================================================================
log_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

log_step() {
    echo -e "\n${BOLD}${CYAN}==>${NC} ${BOLD}$1${NC}"
}

# ============================================================================
# Validation
# ============================================================================
add_validation_error() {
    VALIDATION_FAILED=true
    VALIDATION_ERRORS+=("$1")
}

validate_hostname() {
    local hostname="$1"
    # Allow: domain names, IP addresses, localhost
    # Note: dash must be at end of character class in bash regex
    if [[ ! "$hostname" =~ ^[a-zA-Z0-9][a-zA-Z0-9.\-]*[a-zA-Z0-9]$ ]] && \
       [[ ! "$hostname" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] && \
       [[ "$hostname" != "localhost" ]] && \
       [[ ! "$hostname" =~ ^[a-zA-Z0-9]$ ]]; then
        return 1
    fi
    return 0
}

validate_ai_provider() {
    local provider="$1"
    case "$provider" in
        openai|anthropic|ollama|openrouter) return 0 ;;
        *) return 1 ;;
    esac
}

validate_gpu_mode() {
    local mode="$1"
    case "$mode" in
        auto|nvidia|amd|amd-host|mac|cpu) return 0 ;;
        *) return 1 ;;
    esac
}

validate_ssl_mode() {
    local mode="$1"
    case "$mode" in
        offload|selfsigned|letsencrypt|manual) return 0 ;;
        *) return 1 ;;
    esac
}

# ============================================================================
# Argument Parsing (Strict Mode)
# ============================================================================
SKIP_AI=false
SHOW_HELP=false

# Arguments that trigger headless mode (configuration args, not utility args)
HEADLESS_TRIGGERS="--hostname|--ai-provider|--ai-key|--ai-model|--ssl|--ssl-email|--ssl-cert|--ssl-key|--ssl-dns|--ssl-dns-key|--ssl-dns-secret|--admin-password|--skip-ai"

parse_args() {
    # Check if any headless-triggering arguments are provided
    for arg in "$@"; do
        # Extract the flag name (before = if present)
        local flag="${arg%%=*}"
        if [[ "$flag" =~ ^($HEADLESS_TRIGGERS)$ ]]; then
            INTERACTIVE=false
            break
        fi
    done

    while [[ $# -gt 0 ]]; do
        case $1 in
            --help|-h)
                SHOW_HELP=true
                shift
                ;;
            --hostname=*)
                HOSTNAME="${1#*=}"
                if [[ -z "$HOSTNAME" ]]; then
                    add_validation_error "--hostname requires a value"
                elif ! validate_hostname "$HOSTNAME"; then
                    add_validation_error "Invalid hostname: $HOSTNAME"
                fi
                shift
                ;;
            --hostname)
                if [[ -z "$2" || "$2" == --* ]]; then
                    add_validation_error "--hostname requires a value"
                    shift
                else
                    HOSTNAME="$2"
                    if ! validate_hostname "$HOSTNAME"; then
                        add_validation_error "Invalid hostname: $HOSTNAME"
                    fi
                    shift 2
                fi
                ;;
            --ai-provider=*)
                AI_PROVIDER="${1#*=}"
                if [[ -z "$AI_PROVIDER" ]]; then
                    add_validation_error "--ai-provider requires a value"
                elif ! validate_ai_provider "$AI_PROVIDER"; then
                    add_validation_error "Invalid AI provider: $AI_PROVIDER (must be: openai, anthropic, ollama, openrouter)"
                fi
                shift
                ;;
            --ai-provider)
                if [[ -z "$2" || "$2" == --* ]]; then
                    add_validation_error "--ai-provider requires a value"
                    shift
                else
                    AI_PROVIDER="$2"
                    if ! validate_ai_provider "$AI_PROVIDER"; then
                        add_validation_error "Invalid AI provider: $AI_PROVIDER (must be: openai, anthropic, ollama, openrouter)"
                    fi
                    shift 2
                fi
                ;;
            --ai-model=*)
                AI_MODEL="${1#*=}"
                if [[ -z "$AI_MODEL" ]]; then
                    add_validation_error "--ai-model requires a value"
                fi
                shift
                ;;
            --ai-model)
                if [[ -z "$2" || "$2" == --* ]]; then
                    add_validation_error "--ai-model requires a value"
                    shift
                else
                    AI_MODEL="$2"
                    shift 2
                fi
                ;;
            --ai-key=*)
                AI_KEY="${1#*=}"
                if [[ -z "$AI_KEY" ]]; then
                    add_validation_error "--ai-key requires a value"
                fi
                shift
                ;;
            --ai-key)
                if [[ -z "$2" || "$2" == --* ]]; then
                    add_validation_error "--ai-key requires a value"
                    shift
                else
                    AI_KEY="$2"
                    shift 2
                fi
                ;;
            --admin-password=*)
                ADMIN_PASSWORD="${1#*=}"
                if [[ -z "$ADMIN_PASSWORD" ]]; then
                    add_validation_error "--admin-password requires a value"
                fi
                shift
                ;;
            --admin-password)
                if [[ -z "$2" || "$2" == --* ]]; then
                    add_validation_error "--admin-password requires a value"
                    shift
                else
                    ADMIN_PASSWORD="$2"
                    shift 2
                fi
                ;;
            --gpu=*)
                GPU_MODE="${1#*=}"
                if [[ -z "$GPU_MODE" ]]; then
                    add_validation_error "--gpu requires a value"
                elif ! validate_gpu_mode "$GPU_MODE"; then
                    add_validation_error "Invalid GPU mode: $GPU_MODE (must be: auto, nvidia, amd, amd-host, mac, cpu)"
                fi
                shift
                ;;
            --gpu)
                if [[ -z "$2" || "$2" == --* ]]; then
                    add_validation_error "--gpu requires a value"
                    shift
                else
                    GPU_MODE="$2"
                    if ! validate_gpu_mode "$GPU_MODE"; then
                        add_validation_error "Invalid GPU mode: $GPU_MODE (must be: auto, nvidia, amd, amd-host, mac, cpu)"
                    fi
                    shift 2
                fi
                ;;
            --install-dir=*)
                INSTALL_DIR="${1#*=}"
                if [[ -z "$INSTALL_DIR" ]]; then
                    add_validation_error "--install-dir requires a value"
                fi
                shift
                ;;
            --install-dir)
                if [[ -z "$2" || "$2" == --* ]]; then
                    add_validation_error "--install-dir requires a value"
                    shift
                else
                    INSTALL_DIR="$2"
                    shift 2
                fi
                ;;
            --skip-ai)
                SKIP_AI=true
                shift
                ;;
            --ssl=*)
                SSL_MODE="${1#*=}"
                if [[ -z "$SSL_MODE" ]]; then
                    add_validation_error "--ssl requires a value"
                elif ! validate_ssl_mode "$SSL_MODE"; then
                    add_validation_error "Invalid SSL mode: $SSL_MODE (must be: offload, selfsigned, letsencrypt, manual)"
                fi
                shift
                ;;
            --ssl)
                if [[ -z "$2" || "$2" == --* ]]; then
                    add_validation_error "--ssl requires a value"
                    shift
                else
                    SSL_MODE="$2"
                    if ! validate_ssl_mode "$SSL_MODE"; then
                        add_validation_error "Invalid SSL mode: $SSL_MODE (must be: offload, selfsigned, letsencrypt, manual)"
                    fi
                    shift 2
                fi
                ;;
            --ssl-email=*)
                SSL_EMAIL="${1#*=}"
                if [[ -z "$SSL_EMAIL" ]]; then
                    add_validation_error "--ssl-email requires a value"
                fi
                shift
                ;;
            --ssl-email)
                if [[ -z "$2" || "$2" == --* ]]; then
                    add_validation_error "--ssl-email requires a value"
                    shift
                else
                    SSL_EMAIL="$2"
                    shift 2
                fi
                ;;
            --ssl-cert=*)
                SSL_CERT_PATH="${1#*=}"
                if [[ -z "$SSL_CERT_PATH" ]]; then
                    add_validation_error "--ssl-cert requires a value"
                fi
                shift
                ;;
            --ssl-cert)
                if [[ -z "$2" || "$2" == --* ]]; then
                    add_validation_error "--ssl-cert requires a value"
                    shift
                else
                    SSL_CERT_PATH="$2"
                    shift 2
                fi
                ;;
            --ssl-key=*)
                SSL_KEY_PATH="${1#*=}"
                if [[ -z "$SSL_KEY_PATH" ]]; then
                    add_validation_error "--ssl-key requires a value"
                fi
                shift
                ;;
            --ssl-key)
                if [[ -z "$2" || "$2" == --* ]]; then
                    add_validation_error "--ssl-key requires a value"
                    shift
                else
                    SSL_KEY_PATH="$2"
                    shift 2
                fi
                ;;
            --ssl-dns|--ssl-dns-provider)
                if [[ -z "$2" || "$2" == --* ]]; then
                    add_validation_error "--ssl-dns requires a provider name"
                    shift
                else
                    SSL_DNS_PROVIDER="$2"
                    shift 2
                fi
                ;;
            --ssl-dns-key)
                if [[ -z "$2" || "$2" == --* ]]; then
                    add_validation_error "--ssl-dns-key requires a value"
                    shift
                else
                    SSL_DNS_KEY="$2"
                    shift 2
                fi
                ;;
            --ssl-dns-secret)
                if [[ -z "$2" || "$2" == --* ]]; then
                    add_validation_error "--ssl-dns-secret requires a value"
                    shift
                else
                    SSL_DNS_SECRET="$2"
                    shift 2
                fi
                ;;
            --macvlan)
                MACVLAN_ENABLED=true
                MACVLAN_MODE="use"
                shift
                ;;
            --macvlan-create)
                MACVLAN_ENABLED=true
                MACVLAN_MODE="create"
                shift
                ;;
            --macvlan-delete)
                MACVLAN_MODE="delete"
                shift
                ;;
            --macvlan-parent)
                if [[ -z "$2" || "$2" == --* ]]; then
                    add_validation_error "--macvlan-parent requires an interface name"
                    shift
                else
                    MACVLAN_PARENT="$2"
                    shift 2
                fi
                ;;
            --macvlan-subnet)
                if [[ -z "$2" || "$2" == --* ]]; then
                    add_validation_error "--macvlan-subnet requires a CIDR"
                    shift
                else
                    MACVLAN_SUBNET="$2"
                    shift 2
                fi
                ;;
            --macvlan-gateway)
                if [[ -z "$2" || "$2" == --* ]]; then
                    add_validation_error "--macvlan-gateway requires an IP"
                    shift
                else
                    MACVLAN_GATEWAY="$2"
                    shift 2
                fi
                ;;
            --macvlan-ip)
                if [[ -z "$2" || "$2" == --* ]]; then
                    add_validation_error "--macvlan-ip requires an IP address"
                    shift
                else
                    MACVLAN_IP="$2"
                    shift 2
                fi
                ;;
            --macvlan-mac)
                if [[ -z "$2" || "$2" == --* ]]; then
                    add_validation_error "--macvlan-mac requires a MAC address"
                    shift
                else
                    MACVLAN_MAC="$2"
                    shift 2
                fi
                ;;
            *)
                add_validation_error "Unknown option: $1"
                shift
                ;;
        esac
    done

    # Headless mode requires certain arguments
    if [[ "$INTERACTIVE" == "false" && "$SHOW_HELP" == "false" ]]; then
        # Hostname is always required in headless mode
        if [[ -z "$HOSTNAME" ]]; then
            add_validation_error "Headless mode requires --hostname"
        fi

        # AI config required unless skipped
        if [[ "$SKIP_AI" == "false" ]]; then
            if [[ -z "$AI_PROVIDER" ]]; then
                add_validation_error "Headless mode requires --ai-provider (or use --skip-ai)"
            fi
            if [[ -n "$AI_PROVIDER" && "$AI_PROVIDER" != "ollama" && -z "$AI_KEY" ]]; then
                add_validation_error "--ai-key is required for provider: $AI_PROVIDER"
            fi
        fi

        # SSL validation
        if [[ "$SSL_MODE" == "letsencrypt" ]]; then
            if [[ -z "$SSL_EMAIL" ]]; then
                add_validation_error "--ssl-email is required for Let's Encrypt"
            fi
            # Allow private IPs with DNS-01 challenge, but not HTTP-01
            if [[ -z "$SSL_DNS_PROVIDER" ]]; then
                if [[ "$HOSTNAME" == "localhost" || "$HOSTNAME" =~ ^192\. || "$HOSTNAME" =~ ^10\. || "$HOSTNAME" =~ ^172\. ]]; then
                    add_validation_error "Let's Encrypt HTTP-01 requires a public domain name. Use --ssl-dns for internal networks."
                fi
            else
                # Validate DNS credentials
                if [[ -z "$SSL_DNS_KEY" ]]; then
                    add_validation_error "--ssl-dns-key is required for DNS-01 challenge"
                fi
            fi
        fi
        if [[ "$SSL_MODE" == "manual" ]]; then
            if [[ -z "$SSL_CERT_PATH" ]]; then
                add_validation_error "--ssl-cert is required for manual SSL"
            elif [[ ! -f "$SSL_CERT_PATH" ]]; then
                add_validation_error "SSL certificate not found: $SSL_CERT_PATH"
            fi
            if [[ -z "$SSL_KEY_PATH" ]]; then
                add_validation_error "--ssl-key is required for manual SSL"
            elif [[ ! -f "$SSL_KEY_PATH" ]]; then
                add_validation_error "SSL key not found: $SSL_KEY_PATH"
            fi
        fi

        # Macvlan validation
        if [[ "$MACVLAN_MODE" == "create" ]]; then
            if [[ -z "$MACVLAN_PARENT" ]]; then
                add_validation_error "--macvlan-parent is required for --macvlan-create"
            fi
            if [[ -z "$MACVLAN_SUBNET" ]]; then
                add_validation_error "--macvlan-subnet is required for --macvlan-create"
            fi
            if [[ -z "$MACVLAN_GATEWAY" ]]; then
                add_validation_error "--macvlan-gateway is required for --macvlan-create"
            fi
        fi
    fi
}

# ============================================================================
# Prerequisites
# ============================================================================
check_prerequisites() {
    log_step "Checking prerequisites"

    # Check OS
    if [[ "$(uname)" != "Linux" ]]; then
        log_error "This installer only supports Linux"
        log_info "For macOS, clone the repo and use: ./operator.sh init"
        exit 1
    fi

    # Check if running as root (not recommended but allow it)
    if [[ $EUID -eq 0 ]]; then
        log_warning "Running as root. Consider using a non-root user with docker group access."
    fi

    # Check for curl
    if ! command -v curl &> /dev/null; then
        log_error "curl is required but not installed"
        log_info "Install with: sudo apt install curl"
        exit 1
    fi

    log_success "Prerequisites OK"
}

# ============================================================================
# Docker Installation
# ============================================================================
install_docker() {
    log_step "Checking Docker"

    if command -v docker &> /dev/null; then
        log_success "Docker is installed: $(docker --version)"

        # Check if docker daemon is running
        if ! docker info &> /dev/null; then
            log_error "Docker is installed but not running"
            log_info "Start Docker with: sudo systemctl start docker"
            exit 1
        fi
        return 0
    fi

    log_info "Docker not found. Installing..."

    # Use official Docker install script
    curl -fsSL https://get.docker.com | sh

    # Add current user to docker group if not root
    if [[ $EUID -ne 0 ]]; then
        sudo usermod -aG docker "$USER"
        log_warning "Added $USER to docker group. You may need to log out and back in."
        log_info "Alternatively, run: newgrp docker"
    fi

    # Start docker
    sudo systemctl enable docker
    sudo systemctl start docker

    log_success "Docker installed successfully"
}

# ============================================================================
# Macvlan Setup
# ============================================================================

# Generate a deterministic MAC address based on hostname
# Format: 02:42:kg:XX:XX:XX where XX is derived from hostname hash
generate_macvlan_mac() {
    local hostname="$1"
    # Use 02:42 prefix (locally administered, unicast)
    # Then 'kg' encoded as hex (6b:67), then 2 bytes from hostname hash
    local hash=$(echo -n "$hostname" | md5sum | cut -c1-4)
    local b1="${hash:0:2}"
    local b2="${hash:2:2}"
    echo "02:42:6b:67:$b1:$b2"
}

# Check if kg-macvlan network exists
detect_macvlan_network() {
    docker network ls --filter "name=^${MACVLAN_NETWORK}$" --format '{{.Name}}' 2>/dev/null | head -1
}

# Get macvlan network details
get_macvlan_info() {
    docker network inspect "$MACVLAN_NETWORK" --format '{{range .IPAM.Config}}Subnet: {{.Subnet}}, Gateway: {{.Gateway}}{{end}}' 2>/dev/null
}

# Create macvlan network
create_macvlan_network() {
    log_info "Creating macvlan network '$MACVLAN_NETWORK'"
    log_info "  Parent interface: $MACVLAN_PARENT"
    log_info "  Subnet: $MACVLAN_SUBNET"
    log_info "  Gateway: $MACVLAN_GATEWAY"

    if docker network create -d macvlan \
        --subnet="$MACVLAN_SUBNET" \
        --gateway="$MACVLAN_GATEWAY" \
        -o parent="$MACVLAN_PARENT" \
        "$MACVLAN_NETWORK" >/dev/null 2>&1; then
        log_success "Created macvlan network '$MACVLAN_NETWORK'"
        return 0
    else
        log_error "Failed to create macvlan network"
        log_info "Check that interface '$MACVLAN_PARENT' exists: ip link show $MACVLAN_PARENT"
        return 1
    fi
}

# Delete macvlan network
delete_macvlan_network() {
    local existing=$(detect_macvlan_network)
    if [[ -n "$existing" ]]; then
        log_info "Deleting macvlan network '$MACVLAN_NETWORK'"
        if docker network rm "$MACVLAN_NETWORK" >/dev/null 2>&1; then
            log_success "Deleted macvlan network '$MACVLAN_NETWORK'"
            return 0
        else
            log_error "Failed to delete macvlan network (containers may still be using it)"
            return 1
        fi
    else
        log_info "Macvlan network '$MACVLAN_NETWORK' does not exist"
        return 0
    fi
}

# Setup macvlan based on mode
setup_macvlan() {
    # Handle delete mode (standalone operation)
    if [[ "$MACVLAN_MODE" == "delete" ]]; then
        delete_macvlan_network
        if [[ "$MACVLAN_ENABLED" != "true" ]]; then
            # Delete-only mode, exit after cleanup
            log_success "Macvlan cleanup complete"
            exit 0
        fi
        return 0
    fi

    # Skip if macvlan not enabled
    if [[ "$MACVLAN_ENABLED" != "true" ]]; then
        return 0
    fi

    log_step "Configuring macvlan networking"

    local existing=$(detect_macvlan_network)

    if [[ "$MACVLAN_MODE" == "create" ]]; then
        if [[ -n "$existing" ]]; then
            log_warning "Macvlan network '$MACVLAN_NETWORK' already exists"
            log_info "$(get_macvlan_info)"
            log_info "Using existing network (use --macvlan-delete first to recreate)"
        else
            create_macvlan_network || exit 1
        fi
    elif [[ "$MACVLAN_MODE" == "use" ]]; then
        if [[ -z "$existing" ]]; then
            log_error "Macvlan network '$MACVLAN_NETWORK' not found"
            log_info "Create it with: --macvlan-create --macvlan-parent <iface> --macvlan-subnet <cidr> --macvlan-gateway <ip>"
            log_info "Or create manually: docker network create -d macvlan --subnet=... --gateway=... -o parent=... $MACVLAN_NETWORK"
            exit 1
        fi
        log_info "Using existing macvlan network '$MACVLAN_NETWORK'"
        log_info "$(get_macvlan_info)"
    fi

    # Generate MAC if not specified and no static IP (DHCP mode)
    if [[ -z "$MACVLAN_MAC" && -z "$MACVLAN_IP" ]]; then
        MACVLAN_MAC=$(generate_macvlan_mac "$HOSTNAME")
        log_info "Generated MAC address for DHCP: $MACVLAN_MAC"
    fi

    log_success "Macvlan networking configured"
}

# ============================================================================
# SSL Setup
# ============================================================================
setup_ssl() {
    local install_dir="${INSTALL_DIR:-$KG_INSTALL_DIR}"

    if [[ "$SSL_MODE" == "offload" ]]; then
        log_info "SSL disabled - using HTTP only"
        generate_nginx_http_config "$install_dir"
        return 0
    fi

    log_step "Setting up SSL"

    local certs_dir="$install_dir/certs"
    mkdir -p "$certs_dir"

    if [[ "$SSL_MODE" == "selfsigned" ]]; then
        setup_selfsigned_ssl "$certs_dir"
    elif [[ "$SSL_MODE" == "letsencrypt" ]]; then
        setup_letsencrypt "$certs_dir"
    elif [[ "$SSL_MODE" == "manual" ]]; then
        setup_manual_ssl "$certs_dir"
    fi

    # Generate nginx SSL config and compose overlay
    generate_nginx_ssl_config "$install_dir"
    generate_ssl_compose_overlay "$install_dir"

    log_success "SSL configured"
}

setup_letsencrypt() {
    local certs_dir="$1"

    log_info "Setting up Let's Encrypt certificates"

    # Use DNS-01 challenge with acme.sh if DNS provider specified
    if [[ -n "$SSL_DNS_PROVIDER" ]]; then
        setup_letsencrypt_dns "$certs_dir"
        return
    fi

    # Otherwise use HTTP-01 challenge with certbot (requires port 80)
    setup_letsencrypt_http "$certs_dir"
}

setup_letsencrypt_dns() {
    local certs_dir="$1"

    log_info "Using DNS-01 challenge with $SSL_DNS_PROVIDER"

    # Install acme.sh if needed
    local acme_home="$HOME/.acme.sh"
    if [[ ! -f "$acme_home/acme.sh" ]]; then
        log_info "Installing acme.sh..."
        curl -fsSL https://get.acme.sh | sh -s email="$SSL_EMAIL"
    fi

    # Set DNS API credentials based on provider
    case "$SSL_DNS_PROVIDER" in
        dns_porkbun)
            export PORKBUN_API_KEY="$SSL_DNS_KEY"
            export PORKBUN_SECRET_API_KEY="$SSL_DNS_SECRET"
            ;;
        dns_cloudflare)
            export CF_Key="$SSL_DNS_KEY"
            export CF_Email="$SSL_EMAIL"
            ;;
        dns_digitalocean)
            export DO_API_KEY="$SSL_DNS_KEY"
            ;;
        dns_namecheap)
            export NAMECHEAP_API_KEY="$SSL_DNS_KEY"
            export NAMECHEAP_USERNAME="$SSL_DNS_SECRET"
            ;;
        dns_gandi)
            export GANDI_LIVEDNS_KEY="$SSL_DNS_KEY"
            ;;
        *)
            # Generic - set both as env vars, acme.sh will use what it needs
            log_warning "Unknown DNS provider $SSL_DNS_PROVIDER - setting generic credentials"
            export DNS_API_KEY="$SSL_DNS_KEY"
            export DNS_API_SECRET="$SSL_DNS_SECRET"
            ;;
    esac

    log_info "Requesting certificate for $HOSTNAME via DNS-01..."

    # Check if certificate already exists
    local cert_exists=false
    if [[ -d "$acme_home/${HOSTNAME}_ecc" ]] || [[ -d "$acme_home/$HOSTNAME" ]]; then
        cert_exists=true
        log_info "Existing certificate found, will reuse"
    fi

    # Issue certificate using DNS challenge (or renew if exists)
    local issue_result=0
    "$acme_home/acme.sh" --issue \
        --dns "$SSL_DNS_PROVIDER" \
        -d "$HOSTNAME" \
        --server letsencrypt || issue_result=$?

    # Exit code 2 means cert is up to date (no renewal needed)
    if [[ $issue_result -ne 0 && $issue_result -ne 2 ]]; then
        log_error "Failed to obtain Let's Encrypt certificate via DNS-01"
        log_info "Check your DNS API credentials and provider name"
        log_info "See: https://github.com/acmesh-official/acme.sh/wiki/dnsapi"
        exit 1
    fi

    if [[ $issue_result -eq 2 ]]; then
        log_info "Certificate is up to date, using existing cert"
    fi

    # Install certificate to our directory
    "$acme_home/acme.sh" --install-cert -d "$HOSTNAME" \
        --key-file "$certs_dir/${HOSTNAME}.key" \
        --fullchain-file "$certs_dir/${HOSTNAME}.fullchain.cer" \
        --reloadcmd "docker restart kg-web 2>/dev/null || true"

    chmod 600 "$certs_dir/${HOSTNAME}.key"

    log_success "Let's Encrypt certificate obtained via DNS-01"
    log_info "Auto-renewal configured via acme.sh cron job"
    log_info "To manually renew: ./operator.sh recert"
}

setup_letsencrypt_http() {
    local certs_dir="$1"

    log_info "Using HTTP-01 challenge (requires port 80 accessible)"

    # Install certbot if needed
    if ! command -v certbot &> /dev/null; then
        log_info "Installing certbot..."
        if command -v apt &> /dev/null; then
            sudo apt update && sudo apt install -y certbot
        elif command -v dnf &> /dev/null; then
            sudo dnf install -y certbot
        elif command -v yum &> /dev/null; then
            sudo yum install -y certbot
        elif command -v pacman &> /dev/null; then
            sudo pacman -S --noconfirm certbot
        elif command -v snap &> /dev/null; then
            sudo snap install certbot --classic
        elif command -v brew &> /dev/null; then
            brew install certbot
        else
            log_error "Could not install certbot. Please install manually:"
            log_info "  Arch: sudo pacman -S certbot"
            log_info "  Ubuntu/Debian: sudo apt install certbot"
            log_info "  Fedora: sudo dnf install certbot"
            exit 1
        fi
    fi

    # Stop any service using port 80
    log_info "Requesting certificate for $HOSTNAME..."

    # Use standalone mode (temporarily binds to port 80)
    if ! sudo certbot certonly --standalone \
        --non-interactive \
        --agree-tos \
        --email "$SSL_EMAIL" \
        -d "$HOSTNAME"; then
        log_error "Failed to obtain Let's Encrypt certificate"
        log_info "Make sure port 80 is accessible and DNS points to this server"
        log_info "For internal networks, use --ssl-dns with a DNS provider instead"
        exit 1
    fi

    # Copy certs to our directory
    local le_dir="/etc/letsencrypt/live/$HOSTNAME"
    sudo cp "$le_dir/fullchain.pem" "$certs_dir/${HOSTNAME}.fullchain.cer"
    sudo cp "$le_dir/privkey.pem" "$certs_dir/${HOSTNAME}.key"
    sudo chown "$USER:$USER" "$certs_dir"/*
    chmod 600 "$certs_dir/${HOSTNAME}.key"

    # Set up auto-renewal hook
    setup_cert_renewal "$certs_dir"

    log_success "Let's Encrypt certificate obtained"
}

setup_manual_ssl() {
    local certs_dir="$1"

    log_info "Copying SSL certificates"

    cp "$SSL_CERT_PATH" "$certs_dir/${HOSTNAME}.fullchain.cer"
    cp "$SSL_KEY_PATH" "$certs_dir/${HOSTNAME}.key"
    chmod 600 "$certs_dir/${HOSTNAME}.key"

    log_success "SSL certificates copied"
}

setup_selfsigned_ssl() {
    local certs_dir="$1"

    log_info "Generating self-signed SSL certificate for ${HOSTNAME}"
    log_warning "Self-signed certificates will show browser warnings - click through to continue"

    # Generate self-signed certificate valid for 365 days
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$certs_dir/${HOSTNAME}.key" \
        -out "$certs_dir/${HOSTNAME}.fullchain.cer" \
        -subj "/CN=${HOSTNAME}" \
        -addext "subjectAltName=DNS:${HOSTNAME},DNS:localhost,IP:127.0.0.1" \
        2>/dev/null

    if [[ $? -ne 0 ]]; then
        log_error "Failed to generate self-signed certificate"
        log_info "Make sure openssl is installed: apt install openssl"
        exit 1
    fi

    chmod 600 "$certs_dir/${HOSTNAME}.key"

    log_success "Self-signed certificate generated (valid for 365 days)"
}

setup_cert_renewal() {
    local certs_dir="$1"

    # Create renewal hook script
    local hook_script="$certs_dir/renewal-hook.sh"
    cat > "$hook_script" << EOF
#!/bin/bash
# Let's Encrypt renewal hook for Knowledge Graph
CERTS_DIR="$certs_dir"
HOSTNAME="$HOSTNAME"

cp /etc/letsencrypt/live/\$HOSTNAME/fullchain.pem "\$CERTS_DIR/\${HOSTNAME}.fullchain.cer"
cp /etc/letsencrypt/live/\$HOSTNAME/privkey.pem "\$CERTS_DIR/\${HOSTNAME}.key"
chmod 600 "\$CERTS_DIR/\${HOSTNAME}.key"

# Reload nginx in container
docker exec kg-web nginx -s reload 2>/dev/null || true
EOF
    chmod +x "$hook_script"

    # Register hook with certbot
    sudo mkdir -p /etc/letsencrypt/renewal-hooks/deploy
    sudo ln -sf "$hook_script" "/etc/letsencrypt/renewal-hooks/deploy/knowledge-graph.sh"

    log_info "Certificate auto-renewal configured via certbot cron/timer"
    log_info "To manually renew: ./operator.sh recert"
}

generate_ssl_compose_overlay() {
    local install_dir="$1"

    if [[ "$MACVLAN_ENABLED" == "true" ]]; then
        # Macvlan mode: dedicated IP on external network, no port mappings
        local ip_config=""
        local mac_config=""
        local mode_comment=""

        if [[ -n "$MACVLAN_IP" ]]; then
            # Static IP mode
            ip_config="        ipv4_address: ${MACVLAN_IP}"
            mode_comment="# Container gets static IP $MACVLAN_IP on network $MACVLAN_NETWORK"
        else
            # DHCP mode - use MAC address for consistent DHCP reservation
            mode_comment="# Container uses MAC $MACVLAN_MAC for DHCP on network $MACVLAN_NETWORK"
        fi

        if [[ -n "$MACVLAN_MAC" ]]; then
            mac_config="    mac_address: \"${MACVLAN_MAC}\""
        fi

        cat > "$install_dir/docker-compose.ssl.yml" << EOF
# SSL overlay with macvlan - auto-generated by install.sh
${mode_comment}
services:
  web:
    networks:
      default:        # Keep internal network for API communication
      ${MACVLAN_NETWORK}:
${ip_config}
${mac_config}
    ports: []         # Clear port mappings - not needed with dedicated IP
    volumes:
      - ./nginx.ssl.conf:/etc/nginx/conf.d/default.conf:ro
      - ./certs:/etc/nginx/certs:ro
    healthcheck:
      test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://127.0.0.1/health"]
      interval: 30s
      timeout: 3s
      retries: 3
      start_period: 5s

networks:
  ${MACVLAN_NETWORK}:
    external: true
EOF
        if [[ -n "$MACVLAN_IP" ]]; then
            log_info "Generated SSL compose overlay with macvlan (static IP: $MACVLAN_IP)"
        else
            log_info "Generated SSL compose overlay with macvlan (DHCP, MAC: $MACVLAN_MAC)"
        fi
    else
        # Standard mode: port mappings on host
        cat > "$install_dir/docker-compose.ssl.yml" << EOF
# SSL overlay - auto-generated by install.sh
services:
  web:
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.ssl.conf:/etc/nginx/conf.d/default.conf:ro
      - ./certs:/etc/nginx/certs:ro
    healthcheck:
      test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://127.0.0.1/health"]
      interval: 30s
      timeout: 3s
      retries: 3
      start_period: 5s
EOF
        log_info "Generated SSL compose overlay"
    fi
}

generate_nginx_http_config() {
    local install_dir="$1"

    cat > "$install_dir/nginx.prod.conf" << 'NGINXEOF'
# Nginx configuration for Knowledge Graph (HTTP only)
# Auto-generated by install.sh

server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss application/json;

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Proxy API requests to backend
    location /api/ {
        proxy_pass http://api:8000/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # SPA routing
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Health check
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
}
NGINXEOF

    log_info "Generated nginx HTTP configuration"
}

generate_nginx_ssl_config() {
    local install_dir="$1"

    cat > "$install_dir/nginx.ssl.conf" << EOF
# Nginx configuration for Knowledge Graph with SSL
# Auto-generated by install.sh

# Redirect HTTP to HTTPS (except healthcheck)
server {
    listen 80;
    server_name ${HOSTNAME};

    # Health check (allow HTTP for Docker healthcheck)
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }

    # Redirect all other HTTP to HTTPS
    location / {
        return 301 https://\$host\$request_uri;
    }
}

# HTTPS server
server {
    listen 443 ssl;
    http2 on;
    server_name ${HOSTNAME};
    root /usr/share/nginx/html;
    index index.html;

    # SSL certificates
    ssl_certificate /etc/nginx/certs/${HOSTNAME}.fullchain.cer;
    ssl_certificate_key /etc/nginx/certs/${HOSTNAME}.key;

    # Modern SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;

    # HSTS
    add_header Strict-Transport-Security "max-age=31536000" always;

    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss application/json;

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)\$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Proxy API requests to backend
    location /api/ {
        proxy_pass http://api:8000/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # SPA routing
    location / {
        try_files \$uri \$uri/ /index.html;
    }

    # Health check
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
}
EOF

    log_info "Generated nginx SSL configuration"
}

# ============================================================================
# Interactive Prompts
# ============================================================================
prompt_value() {
    local prompt="$1"
    local default="$2"
    local value

    # Output prompt to stderr so it displays (stdout is captured by $(...))
    if [[ -n "$default" ]]; then
        echo -ne "${CYAN}?${NC} ${prompt} [${default}]: " >&2
        read -r value </dev/tty
        echo "${value:-$default}"
    else
        echo -ne "${CYAN}?${NC} ${prompt}: " >&2
        read -r value </dev/tty
        echo "$value"
    fi
}

prompt_password() {
    local prompt="$1"
    local value

    # Output prompt to stderr, read silently from tty
    echo -ne "${CYAN}?${NC} ${prompt}: " >&2
    read -sr value </dev/tty
    echo >&2  # Newline after password
    echo "$value"
}

prompt_password_confirm() {
    local prompt="$1"
    local value1 value2

    while true; do
        echo -ne "${CYAN}?${NC} ${prompt}: " >&2
        read -sr value1 </dev/tty
        echo >&2

        echo -ne "${CYAN}?${NC} Confirm ${prompt,,}: " >&2
        read -sr value2 </dev/tty
        echo >&2

        if [[ "$value1" == "$value2" ]]; then
            echo "$value1"
            return 0
        else
            echo -e "${RED}✗${NC} Passwords do not match. Try again." >&2
        fi
    done
}

prompt_select() {
    local prompt="$1"
    shift
    local options=("$@")
    local i=1

    # Output to stderr so it displays (stdout is captured by $(...))
    echo -e "${CYAN}?${NC} ${prompt}" >&2
    for opt in "${options[@]}"; do
        echo "  $i) $opt" >&2
        ((i++))
    done

    local selection
    echo -n "  Select [1]: " >&2
    read -r selection </dev/tty
    selection=${selection:-1}

    if [[ "$selection" -ge 1 && "$selection" -le ${#options[@]} ]]; then
        echo "${options[$((selection-1))]}"
    else
        echo "${options[0]}"
    fi
}

# ============================================================================
# API Key Validation
# ============================================================================
validate_openai_key() {
    local key="$1"
    local response
    response=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer $key" \
        -H "Content-Type: application/json" \
        "https://api.openai.com/v1/models" 2>/dev/null)
    [[ "$response" == "200" ]]
}

validate_anthropic_key() {
    local key="$1"
    local response
    # Anthropic requires a minimal request to validate
    response=$(curl -s -w "\n%{http_code}" \
        -H "x-api-key: $key" \
        -H "Content-Type: application/json" \
        -H "anthropic-version: 2023-06-01" \
        -d '{"model":"claude-3-haiku-20240307","max_tokens":1,"messages":[{"role":"user","content":"hi"}]}' \
        "https://api.anthropic.com/v1/messages" 2>/dev/null | tail -1)
    # 200 = success, 400 = bad request (but key is valid)
    [[ "$response" == "200" || "$response" == "400" ]]
}

validate_api_key() {
    local provider="$1"
    local key="$2"

    echo -ne "  Validating API key... " >&2

    local valid=false
    case "$provider" in
        openai)
            if validate_openai_key "$key"; then
                valid=true
            fi
            ;;
        anthropic)
            if validate_anthropic_key "$key"; then
                valid=true
            fi
            ;;
        *)
            # Unknown provider, skip validation
            echo -e "${YELLOW}skipped${NC}" >&2
            return 0
            ;;
    esac

    if [[ "$valid" == "true" ]]; then
        echo -e "${GREEN}valid${NC}" >&2
        return 0
    else
        echo -e "${RED}invalid${NC}" >&2
        return 1
    fi
}

prompt_api_key_with_validation() {
    local provider="$1"
    local prompt="$2"
    local key
    local attempts=0
    local max_attempts=3

    while [[ $attempts -lt $max_attempts ]]; do
        key=$(prompt_password "$prompt")

        if [[ -z "$key" ]]; then
            log_warning "No API key provided"
            return 1
        fi

        if validate_api_key "$provider" "$key"; then
            echo "$key"
            return 0
        else
            ((attempts++))
            if [[ $attempts -lt $max_attempts ]]; then
                log_warning "API key validation failed. Please try again. (Attempt $attempts/$max_attempts)"
            else
                log_error "API key validation failed after $max_attempts attempts"
                echo -ne "  Continue without AI configuration? [y/N]: " >&2
                local skip
                read -r skip </dev/tty
                if [[ "$skip" =~ ^[Yy] ]]; then
                    return 1
                else
                    exit 1
                fi
            fi
        fi
    done
}

run_interactive_setup() {
    log_step "Interactive Setup"
    echo
    echo -e "${BOLD}Welcome to the Knowledge Graph Platform installer!${NC}"
    echo "This will guide you through the configuration."
    echo

    # Hostname
    local default_hostname
    default_hostname=$(hostname -I 2>/dev/null | awk '{print $1}')
    [[ -z "$default_hostname" ]] && default_hostname="localhost"
    HOSTNAME=$(prompt_value "Hostname or IP for web access" "$default_hostname")

    # AI Provider
    echo
    AI_PROVIDER=$(prompt_select "Select AI provider for document extraction" \
        "openai" "anthropic" "ollama" "skip (configure later)")

    if [[ "$AI_PROVIDER" == "skip (configure later)" ]]; then
        SKIP_AI=true
        AI_PROVIDER=""
    fi

    # AI Model and Key
    if [[ "$SKIP_AI" == "false" && -n "$AI_PROVIDER" ]]; then
        case "$AI_PROVIDER" in
            openai)
                AI_MODEL=$(prompt_value "Model name" "gpt-4o")
                AI_KEY=$(prompt_api_key_with_validation "openai" "OpenAI API key")
                if [[ -z "$AI_KEY" ]]; then
                    SKIP_AI=true
                    AI_PROVIDER=""
                    log_info "AI configuration skipped - you can configure it later"
                fi
                ;;
            anthropic)
                AI_MODEL=$(prompt_value "Model name" "claude-sonnet-4")
                AI_KEY=$(prompt_api_key_with_validation "anthropic" "Anthropic API key")
                if [[ -z "$AI_KEY" ]]; then
                    SKIP_AI=true
                    AI_PROVIDER=""
                    log_info "AI configuration skipped - you can configure it later"
                fi
                ;;
            ollama)
                AI_MODEL=$(prompt_value "Model name" "llama3.1")
                log_info "Ollama runs locally - no API key needed"
                ;;
        esac
    fi

    # GPU Mode
    echo
    GPU_MODE=$(prompt_select "GPU acceleration" \
        "auto (detect)" "nvidia" "amd" "cpu (none)")
    GPU_MODE="${GPU_MODE%% *}"  # Extract first word

    # SSL Configuration
    echo
    SSL_MODE=$(prompt_select "SSL/HTTPS configuration" \
        "selfsigned (quick setup)" "letsencrypt (auto-generate)" "manual (existing certs)" "offload (reverse proxy)")
    SSL_MODE="${SSL_MODE%% *}"  # Extract first word

    if [[ "$SSL_MODE" == "letsencrypt" ]]; then
        SSL_EMAIL=$(prompt_value "Email for Let's Encrypt" "")
        if [[ -z "$SSL_EMAIL" ]]; then
            log_warning "Email required for Let's Encrypt. Falling back to HTTP only."
            SSL_MODE="offload"
        else
            # Check if we need DNS-01 challenge (for private IPs or internal domains)
            if [[ "$HOSTNAME" == "localhost" || "$HOSTNAME" =~ ^192\. || "$HOSTNAME" =~ ^10\. || "$HOSTNAME" =~ ^172\. ]]; then
                log_warning "Private IP detected - HTTP-01 challenge won't work"
                log_info "Using DNS-01 challenge instead (requires DNS API credentials)"
                echo
                SSL_DNS_PROVIDER=$(prompt_select "DNS provider for DNS-01 challenge" \
                    "dns_porkbun" "dns_cloudflare" "dns_digitalocean" "dns_gandi" "dns_namecheap" "skip (use HTTP only)")
                if [[ "$SSL_DNS_PROVIDER" == "skip (use HTTP only)" ]]; then
                    SSL_MODE="offload"
                    SSL_DNS_PROVIDER=""
                fi
            else
                # Public domain - offer choice between HTTP-01 and DNS-01
                echo
                local challenge_type
                challenge_type=$(prompt_select "Certificate challenge type" \
                    "http (port 80 accessible)" "dns (works behind firewall)")
                if [[ "$challenge_type" == "dns (works behind firewall)" ]]; then
                    SSL_DNS_PROVIDER=$(prompt_select "DNS provider" \
                        "dns_porkbun" "dns_cloudflare" "dns_digitalocean" "dns_gandi" "dns_namecheap")
                fi
            fi

            # Get DNS credentials if using DNS-01
            if [[ -n "$SSL_DNS_PROVIDER" ]]; then
                echo
                log_info "Enter DNS API credentials for $SSL_DNS_PROVIDER"
                log_info "See: https://github.com/acmesh-official/acme.sh/wiki/dnsapi"
                SSL_DNS_KEY=$(prompt_value "API key" "")
                if [[ -z "$SSL_DNS_KEY" ]]; then
                    log_warning "DNS API key required. Falling back to HTTP only."
                    SSL_MODE="offload"
                    SSL_DNS_PROVIDER=""
                else
                    SSL_DNS_SECRET=$(prompt_value "API secret (if required, or press Enter)" "")
                fi
            fi
        fi
    elif [[ "$SSL_MODE" == "manual" ]]; then
        SSL_CERT_PATH=$(prompt_value "Path to SSL certificate (fullchain.pem)" "")
        SSL_KEY_PATH=$(prompt_value "Path to SSL private key (privkey.pem)" "")
        if [[ ! -f "$SSL_CERT_PATH" || ! -f "$SSL_KEY_PATH" ]]; then
            log_warning "Certificate files not found. Falling back to HTTP only."
            SSL_MODE="offload"
        fi
    fi

    # Admin password
    echo
    echo -e "${YELLOW}Note:${NC} You can set admin password now or use the auto-generated one." >&2
    local set_password
    echo -ne "${CYAN}?${NC} Set custom admin password? [y/N]: " >&2
    read -r set_password </dev/tty
    if [[ "$set_password" =~ ^[Yy] ]]; then
        ADMIN_PASSWORD=$(prompt_password_confirm "Admin password")
    fi

    echo
    log_success "Configuration complete"
}

# ============================================================================
# File Download
# ============================================================================
download_files() {
    log_step "Downloading platform files"

    local install_dir="${INSTALL_DIR:-$KG_INSTALL_DIR}"

    # Create install directory
    mkdir -p "$install_dir"
    cd "$install_dir"

    log_info "Installing to: $install_dir"

    # Docker compose files - download to root (not docker/ subdir)
    local compose_files=(
        "docker-compose.yml"
        "docker-compose.prod.yml"
        "docker-compose.ghcr.yml"
        "docker-compose.gpu-nvidia.yml"
        "docker-compose.gpu-amd.yml"
    )

    for file in "${compose_files[@]}"; do
        log_info "Downloading $file..."
        if ! curl -fsSL "${KG_REPO_RAW}/docker/${file}" -o "$file"; then
            log_error "Failed to download: $file"
            exit 1
        fi
    done

    # Verify essential files were downloaded
    if [[ ! -f "docker-compose.yml" ]]; then
        log_error "docker-compose.yml not found after download"
        log_info "Current directory: $(pwd)"
        log_info "Files in directory: $(ls -la)"
        exit 1
    fi

    # Fix compose files for standalone installation
    log_info "Adapting compose files for standalone installation..."
    for file in docker-compose*.yml; do
        if [[ -f "$file" ]]; then
            # Fix relative paths (they assume docker/ subdirectory)
            sed -i 's|\.\./schema/|./schema/|g' "$file"
            sed -i 's|\.\./config/|./config/|g' "$file"

            # Remove production-specific network settings (hardcoded IPs, MACs)
            sed -i '/mac_address:/d' "$file"
            sed -i '/ipv4_address:/d' "$file"

            # Remove lannet network references (production LAN)
            sed -i '/lannet:/d' "$file"
            sed -i '/external: true/d' "$file"

            # Remove hardcoded GPU deploy block (GPU config comes from overlay files)
            # This removes the entire deploy section for the api service
            sed -i '/^    deploy:$/,/^    [a-z]/{ /^    deploy:/d; /^      /d; }' "$file"

            # Remove development volume mounts (source code mounts for hot-reload)
            # These don't exist in standalone installs and would overwrite container contents
            sed -i '/\.\.\/api:\/app\/api/d' "$file"
            sed -i '/\.\.\/web/d' "$file"
            sed -i '/\.:\/workspace/d' "$file"

            # Remove build sections (we use pre-built GHCR images)
            sed -i '/^    build:$/,/^    [a-z]/{ /^    build:/d; /^      /d; }' "$file"

            # Remove production-specific data paths (use named volumes instead)
            sed -i '/\/srv\/docker\/data/d' "$file"

            # For non-SSL installs, replace https:// with http:// in VITE_ env vars
            if [[ "$SSL_MODE" == "offload" ]]; then
                sed -i 's|https://\${WEB_HOSTNAME|http://\${WEB_HOSTNAME|g' "$file"
            fi
        fi
    done
    log_success "Compose files downloaded"

    # Download baseline schema for postgres initialization
    # (The baseline SQL is mounted into postgres and runs on first start)
    # Incremental migrations are in the operator container and applied via migrate-db.sh
    mkdir -p schema
    log_info "Downloading schema/00_baseline.sql..."
    if ! curl -fsSL "${KG_REPO_RAW}/schema/00_baseline.sql" -o "schema/00_baseline.sql"; then
        log_error "Failed to download: schema/00_baseline.sql"
        exit 1
    fi

    # Config files
    mkdir -p config
    log_info "Downloading config/garage.toml..."
    curl -fsSL "${KG_REPO_RAW}/config/garage.toml" -o "config/garage.toml" 2>/dev/null || true

    # Download operator scripts
    mkdir -p operator/lib operator/database
    local operator_files=(
        "operator/configure.py"
        "operator/lib/common.sh"
        "operator/lib/upgrade.sh"
        "operator/lib/start-infra.sh"
        "operator/lib/start-app.sh"
        "operator/lib/stop.sh"
        "operator/lib/teardown.sh"
        "operator/database/migrate-db.sh"
        "operator/database/backup-database.sh"
    )

    for file in "${operator_files[@]}"; do
        log_info "Downloading $file..."
        if curl -fsSL "${KG_REPO_RAW}/${file}" -o "$file"; then
            # Make shell scripts executable
            if [[ "$file" == *.sh ]]; then
                chmod +x "$file"
            fi
        else
            log_warning "Optional file not found: $file"
        fi
    done

    # Download operator.sh management script
    log_info "Downloading operator.sh..."
    if curl -fsSL "${KG_REPO_RAW}/operator.sh" -o "operator.sh"; then
        chmod +x operator.sh
        log_success "operator.sh installed - use ./operator.sh to manage the platform"
    else
        log_warning "Could not download operator.sh"
    fi

    # Create operator configuration for standalone install
    cat > ".operator.conf" << EOF
# Operator configuration (standalone install)
# Container naming: kg-* (production style)
DEV_MODE=false
GPU_MODE=${GPU_MODE}
CONTAINER_PREFIX=kg
IMAGE_SOURCE=ghcr
INITIALIZED_AT=$(date -Iseconds)
EOF
    log_success ".operator.conf created"

    log_success "Files downloaded"
}

# ============================================================================
# Secret Generation
# ============================================================================
generate_secrets() {
    log_step "Generating secrets"

    # Generate cryptographic secrets
    local encryption_key
    local oauth_signing_key
    local postgres_password
    local garage_rpc_secret
    local internal_key_secret

    encryption_key=$(python3 -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())" 2>/dev/null || openssl rand -base64 32)
    oauth_signing_key=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || openssl rand -hex 32)
    postgres_password=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))" 2>/dev/null || openssl rand -base64 24)
    garage_rpc_secret=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || openssl rand -hex 32)
    internal_key_secret=$(python3 -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())" 2>/dev/null || openssl rand -base64 32)

    # Generate admin password if not set
    if [[ -z "$ADMIN_PASSWORD" ]]; then
        ADMIN_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))" 2>/dev/null || openssl rand -base64 16)
        log_info "Generated admin password (save this!): $ADMIN_PASSWORD"
    fi

    # Create .env file
    cat > .env << EOF
# Knowledge Graph Platform - Generated $(date -Iseconds)
# DO NOT COMMIT THIS FILE

# Infrastructure Secrets
ENCRYPTION_KEY=${encryption_key}
OAUTH_SIGNING_KEY=${oauth_signing_key}
POSTGRES_PASSWORD=${postgres_password}
GARAGE_RPC_SECRET=${garage_rpc_secret}
INTERNAL_KEY_SERVICE_SECRET=${internal_key_secret}

# Database
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=knowledge_graph
POSTGRES_USER=admin

# Garage S3 Storage
GARAGE_S3_ENDPOINT=http://garage:3900
GARAGE_ADMIN_ENDPOINT=http://garage:3903
GARAGE_REGION=garage
GARAGE_BUCKET=kg-storage

# Web Configuration
WEB_HOSTNAME=${HOSTNAME}
EOF

    # Add protocol-specific settings
    if [[ "$SSL_MODE" != "offload" ]]; then
        cat >> .env << EOF
VITE_API_URL=https://${HOSTNAME}/api
VITE_OAUTH_CLIENT_ID=kg-web
VITE_OAUTH_REDIRECT_URI=https://${HOSTNAME}/callback
SSL_ENABLED=true
EOF
    else
        cat >> .env << EOF
VITE_API_URL=http://${HOSTNAME}:8000
VITE_OAUTH_CLIENT_ID=kg-web
VITE_OAUTH_REDIRECT_URI=http://${HOSTNAME}:3000/callback
SSL_ENABLED=false
EOF
    fi

    cat >> .env << EOF

# Container Configuration
COMPOSE_PROJECT_NAME=kg
EOF

    log_success "Secrets generated"
}

# ============================================================================
# Container Startup
# ============================================================================
build_compose_command() {
    local cmd="docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.ghcr.yml"

    # Add GPU overlay if needed
    case "$GPU_MODE" in
        nvidia)
            if [[ -f "docker-compose.gpu-nvidia.yml" ]]; then
                cmd="$cmd -f docker-compose.gpu-nvidia.yml"
            fi
            ;;
        amd|amd-host)
            if [[ -f "docker-compose.gpu-amd.yml" ]]; then
                cmd="$cmd -f docker-compose.gpu-amd.yml"
            fi
            ;;
    esac

    # Add SSL overlay if enabled
    if [[ "$SSL_MODE" != "offload" && -f "docker-compose.ssl.yml" ]]; then
        cmd="$cmd -f docker-compose.ssl.yml"
    fi

    echo "$cmd"
}

start_containers() {
    log_step "Starting containers"

    local install_dir="${INSTALL_DIR:-$KG_INSTALL_DIR}"
    cd "$install_dir"

    local compose_cmd
    compose_cmd=$(build_compose_command)

    # Pull images
    log_info "Pulling images from GitHub Container Registry..."
    $compose_cmd pull

    # Start infrastructure first
    log_info "Starting infrastructure (postgres, garage)..."
    $compose_cmd up -d postgres garage

    # Wait for postgres
    log_info "Waiting for PostgreSQL..."
    local retries=30
    while ! docker compose exec -T postgres pg_isready -U admin &>/dev/null; do
        retries=$((retries - 1))
        if [[ $retries -le 0 ]]; then
            log_error "PostgreSQL failed to start"
            exit 1
        fi
        sleep 2
    done
    log_success "PostgreSQL ready"

    # Wait for garage
    log_info "Waiting for Garage..."
    retries=15
    while ! docker compose exec -T garage /garage status &>/dev/null; do
        retries=$((retries - 1))
        if [[ $retries -le 0 ]]; then
            log_error "Garage failed to start"
            exit 1
        fi
        sleep 2
    done
    log_success "Garage ready"

    # Start operator for configuration
    log_info "Starting operator..."
    $compose_cmd up -d operator
    sleep 3

    # Run database migrations via operator's migrate-db.sh (source of truth)
    log_info "Running database migrations..."
    if ! $compose_cmd exec -T operator /workspace/operator/database/migrate-db.sh -y 2>&1 | while read line; do
        # Filter to show progress without overwhelming output
        if [[ "$line" =~ (Applying|✓|✅|→|Migration) ]]; then
            echo "  $line"
        fi
    done; then
        log_error "Database migrations failed"
        log_info "Check operator logs: docker logs kg-operator"
        exit 1
    fi
    log_success "Migrations complete"

    # Configure OAuth redirect URIs for this deployment
    log_info "Configuring OAuth client redirect URIs..."
    local redirect_uri
    if [[ "$SSL_MODE" != "offload" ]]; then
        redirect_uri="https://${HOSTNAME}/callback"
    else
        redirect_uri="http://${HOSTNAME}:3000/callback"
    fi
    $compose_cmd exec -T operator bash -c "
        export PGPASSWORD=\"\$POSTGRES_PASSWORD\"
        psql -h postgres -U admin -d knowledge_graph -c \"
            UPDATE kg_auth.oauth_clients
            SET redirect_uris = ARRAY['http://localhost:3000/callback', '$redirect_uri']
            WHERE client_id = 'kg-web';
        \"
    " >/dev/null 2>&1 || log_warning "Could not update OAuth redirect URIs"
    log_success "OAuth configured for $redirect_uri"

    # Set admin password (before app startup so it's always available)
    log_info "Setting admin password..."
    ./operator.sh admin --password "$ADMIN_PASSWORD" >/dev/null 2>&1 || log_warning "Could not set admin password"
    log_success "Admin user configured"

    # Configure local embedding (nomic) as default
    log_info "Configuring local embedding model..."
    ./operator.sh embedding local >/dev/null 2>&1 || log_warning "Could not set local embedding"
    log_success "Local embedding configured (nomic-embed-text-v1.5)"

    # Start application
    log_info "Starting application (api, web)..."
    $compose_cmd up -d api web

    # Wait for API health
    log_info "Waiting for API..."
    retries=60
    while ! curl -sf "http://localhost:8000/health" &>/dev/null; do
        retries=$((retries - 1))
        if [[ $retries -le 0 ]]; then
            log_error "API failed to start"
            log_info "Check logs with: docker compose logs api"
            exit 1
        fi
        sleep 5
    done
    log_success "API ready"

    # Wait for web
    log_info "Waiting for Web UI..."
    retries=30
    while ! curl -sf "http://localhost:3000" &>/dev/null; do
        retries=$((retries - 1))
        if [[ $retries -le 0 ]]; then
            log_warning "Web UI may still be starting..."
            break
        fi
        sleep 2
    done
    log_success "Web UI ready"

    log_success "All containers started"
}

# ============================================================================
# Post-Install Configuration
# ============================================================================
configure_platform() {
    log_step "Configuring platform"

    local install_dir="${INSTALL_DIR:-$KG_INSTALL_DIR}"
    cd "$install_dir"

    local compose_cmd
    compose_cmd=$(build_compose_command)

    # Note: Admin password is set earlier in start_containers() before app startup

    # Configure AI provider if set
    if [[ "$SKIP_AI" == "false" && -n "$AI_PROVIDER" ]]; then
        log_info "Configuring AI provider: $AI_PROVIDER"

        local model="${AI_MODEL:-gpt-4o}"
        $compose_cmd exec -T operator python /workspace/operator/configure.py ai-provider "$AI_PROVIDER" --model "$model" || true

        if [[ -n "$AI_KEY" ]]; then
            $compose_cmd exec -T operator python /workspace/operator/configure.py api-key "$AI_PROVIDER" --key "$AI_KEY" || true
        fi
    fi

    # Configure embeddings (local by default)
    log_info "Configuring embeddings..."
    $compose_cmd exec -T operator python /workspace/operator/configure.py embedding 2 || true

    # Configure Garage storage
    log_info "Configuring storage..."
    # Create Garage API key
    local garage_key
    garage_key=$($compose_cmd exec -T garage /garage key create kg-api-key 2>/dev/null | grep -oP 'GK[a-zA-Z0-9]+' || echo "")
    if [[ -n "$garage_key" ]]; then
        $compose_cmd exec -T garage /garage bucket allow --read --write --key kg-api-key kg-storage || true
    fi

    log_success "Platform configured"
}

# ============================================================================
# Completion
# ============================================================================
show_completion() {
    local install_dir="${INSTALL_DIR:-$KG_INSTALL_DIR}"

    # Determine URLs based on SSL mode
    local web_url api_url docs_url
    if [[ "$SSL_MODE" != "offload" ]]; then
        web_url="https://${HOSTNAME}"
        api_url="https://${HOSTNAME}/api"
        docs_url="https://${HOSTNAME}/api/docs"
    else
        web_url="http://${HOSTNAME}:3000"
        api_url="http://${HOSTNAME}:8000"
        docs_url="http://${HOSTNAME}:8000/docs"
    fi

    echo
    echo -e "${GREEN}============================================================================${NC}"
    echo -e "${GREEN}${BOLD}  Knowledge Graph Platform Installed Successfully!${NC}"
    echo -e "${GREEN}============================================================================${NC}"
    echo
    echo -e "  ${BOLD}Web UI:${NC}      ${web_url}"
    echo -e "  ${BOLD}API:${NC}         ${api_url}"
    echo -e "  ${BOLD}API Docs:${NC}    ${docs_url}"
    echo
    echo -e "  ${BOLD}Admin User:${NC}  admin"
    echo -e "  ${BOLD}Password:${NC}    ${ADMIN_PASSWORD}"
    echo
    echo -e "  ${BOLD}Install Dir:${NC} ${install_dir}"
    if [[ "$SSL_MODE" != "offload" ]]; then
        echo -e "  ${BOLD}SSL:${NC}         ${SSL_MODE}"
    fi
    if [[ "$MACVLAN_ENABLED" == "true" ]]; then
        echo -e "  ${BOLD}Network:${NC}     macvlan ($MACVLAN_NETWORK)"
        if [[ -n "$MACVLAN_IP" ]]; then
            echo -e "  ${BOLD}IP:${NC}          ${MACVLAN_IP} (static)"
        else
            echo -e "  ${BOLD}MAC:${NC}         ${MACVLAN_MAC} (DHCP)"
        fi
    fi
    echo
    echo -e "${YELLOW}Save these credentials - they won't be shown again!${NC}"
    echo
    echo -e "${BOLD}Next Steps:${NC}"
    local step=1

    # Macvlan-specific steps come first
    if [[ "$MACVLAN_ENABLED" == "true" ]]; then
        if [[ -z "$MACVLAN_IP" ]]; then
            # DHCP mode
            echo "  ${step}. Reserve MAC ${MACVLAN_MAC} in your DHCP server/router"
            ((step++))
            echo "  ${step}. After container starts, find IP: docker inspect kg-web --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'"
            ((step++))
            echo "  ${step}. Point DNS ${HOSTNAME} to the assigned IP"
            ((step++))
        else
            # Static IP mode
            echo "  ${step}. Ensure ${MACVLAN_IP} is excluded from your DHCP pool (or reserved)"
            ((step++))
            echo "  ${step}. Point DNS ${HOSTNAME} to ${MACVLAN_IP}"
            ((step++))
        fi
    fi

    echo "  ${step}. Open ${web_url} in your browser"
    ((step++))
    echo "  ${step}. Log in with admin credentials above"
    ((step++))
    if [[ "$SKIP_AI" == "true" ]]; then
        echo "  ${step}. Configure AI provider in Settings > AI Configuration"
    fi
    echo
    echo -e "${BOLD}Platform Management:${NC}"
    echo "  cd ${install_dir}"
    echo
    echo "  ${BOLD}./operator.sh${NC} is your primary tool for managing the platform:"
    echo "    ./operator.sh status           # Platform and container status"
    echo "    ./operator.sh logs [service]   # View logs (api, web, postgres)"
    echo "    ./operator.sh logs api -f      # Follow logs in real-time"
    echo "    ./operator.sh stop             # Stop the platform"
    echo "    ./operator.sh start            # Start the platform"
    echo "    ./operator.sh upgrade          # Pull updates and restart"
    echo "    ./operator.sh shell            # Configuration shell"
    echo
    echo "  Inside the configuration shell (./operator.sh shell):"
    echo "    configure.py status            # Show current configuration"
    echo "    configure.py ai-provider       # Change AI extraction provider"
    echo "    configure.py api-key <name>    # Store API key"
    echo "    configure.py oauth --list      # Manage OAuth clients"
    echo
    echo "  Direct docker access (if needed):"
    echo "    docker compose ps              # Container status"
    echo "    docker compose down            # Stop all containers"
    echo "    docker compose up -d           # Start all containers"

    if [[ "$MACVLAN_ENABLED" == "true" && -z "$MACVLAN_IP" ]]; then
        echo
        echo -e "  ${BOLD}Macvlan (DHCP mode):${NC}"
        echo "    docker inspect kg-web --format '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}'"
        echo "                                   # Show container IP addresses"
        echo "    docker network inspect $MACVLAN_NETWORK"
        echo "                                   # Show macvlan network details"
    fi
    echo
}

# ============================================================================
# Main
# ============================================================================
main() {
    echo
    echo -e "${BOLD}${BLUE}Knowledge Graph Platform Installer${NC}"
    echo

    # Parse arguments
    parse_args "$@"

    # Show help if requested
    if [[ "$SHOW_HELP" == "true" ]]; then
        show_help
        exit 0
    fi

    # Check for validation errors (strict mode)
    if [[ "$VALIDATION_FAILED" == "true" ]]; then
        echo -e "${RED}${BOLD}Configuration Error${NC}"
        echo
        for error in "${VALIDATION_ERRORS[@]}"; do
            log_error "$error"
        done
        echo
        echo "Run with --help for usage information."
        exit 1
    fi

    # Run interactive setup if no arguments
    if [[ "$INTERACTIVE" == "true" ]]; then
        run_interactive_setup
    else
        # Headless mode - validate API key if provided
        if [[ -n "$AI_KEY" && -n "$AI_PROVIDER" && "$AI_PROVIDER" != "ollama" ]]; then
            if ! validate_api_key "$AI_PROVIDER" "$AI_KEY"; then
                log_error "API key validation failed"
                log_info "Check your API key and try again, or use --skip-ai to skip AI configuration"
                exit 1
            fi
        fi
    fi

    # Set default install directory
    INSTALL_DIR="${INSTALL_DIR:-$KG_INSTALL_DIR}"

    # Execute installation
    check_prerequisites
    install_docker
    setup_macvlan
    download_files
    generate_secrets
    setup_ssl
    start_containers
    configure_platform
    show_completion
}

main "$@"
