#!/bin/bash
# ============================================================================
# Knowledge Graph Platform Installer
# ============================================================================
#
# Version: 0.6.0-dev.14
# Commit:  (pending)
#
# A single-command installer for the Knowledge Graph platform. Supports both
# interactive (wizard) and headless (flag-based) installation modes.
#
# ARCHITECTURE OVERVIEW:
# ----------------------
# This script follows a "configuration-first" pattern:
#
#   1. CONFIGURATION    - All options defined as variables (single source of truth)
#   2. UTILITIES        - Logging, prompts, validation helpers
#   3. COLLECTORS       - Two paths to populate config: flags OR interactive
#   4. VALIDATORS       - Verify config is complete and valid
#   5. ACTIONS          - Download files, setup SSL, start containers, etc.
#   6. MAIN             - Orchestrates the flow
#
# This design ensures:
#   - Every headless flag has an interactive equivalent
#   - Config validation works regardless of input method
#   - Easy to read: want to know all options? Look at section 1
#   - Easy to modify: each section is self-contained
#
# USAGE:
# ------
#   Interactive:  curl -fsSL .../install.sh | bash
#   Headless:     curl -fsSL .../install.sh | bash -s -- --hostname x --ssl y ...
#   Help:         curl -fsSL .../install.sh | bash -s -- --help
#
# ============================================================================

set -e  # Exit on error

# ============================================================================
# SECTION 1: CONFIGURATION VARIABLES
# ============================================================================
#
# All configurable options are defined here. This is the single source of truth
# for what can be configured. Both flag parsing and interactive prompts set
# these same variables.
#
# Naming convention:
#   - UPPERCASE for config that can be set by user
#   - lowercase for internal/derived values
#

# --- Installation ---
INSTALL_DIR=""                      # Where to install (default: ~/knowledge-graph)
KG_INSTALL_DIR="$HOME/knowledge-graph"  # Default install location

# --- Basic ---
HOSTNAME=""                         # Public hostname or IP for web access

# --- AI Provider ---
AI_PROVIDER=""                      # openai, anthropic, ollama, or empty to skip
AI_MODEL=""                         # Model name (e.g., gpt-4o, claude-sonnet-4)
AI_KEY=""                           # API key for cloud providers
SKIP_AI=false                       # Skip AI configuration entirely

# --- GPU ---
GPU_MODE="auto"                     # auto, nvidia, amd, cpu

# --- SSL/HTTPS ---
SSL_MODE="offload"                  # offload, selfsigned, letsencrypt, manual
SSL_EMAIL=""                        # Email for Let's Encrypt registration
SSL_CERT_PATH=""                    # Path to existing certificate (manual mode)
SSL_KEY_PATH=""                     # Path to existing private key (manual mode)

# --- SSL DNS-01 Challenge (for Let's Encrypt behind NAT/firewall) ---
SSL_DNS_PROVIDER=""                 # acme.sh DNS provider (e.g., dns_porkbun, dns_cloudflare)
SSL_DNS_KEY=""                      # DNS provider API key
SSL_DNS_SECRET=""                   # DNS provider API secret (if required)

# --- Macvlan Networking (dedicated LAN IP) ---
MACVLAN_ENABLED=false               # Use macvlan networking
MACVLAN_CREATE=false                # Create new kg-macvlan network
MACVLAN_DELETE=false                # Delete existing kg-macvlan network
MACVLAN_NETWORK="kg-macvlan"        # Network name (standard for auto-detection)
MACVLAN_PARENT=""                   # Parent interface (e.g., eth0, eno1)
MACVLAN_SUBNET=""                   # Network subnet (e.g., 192.168.1.0/24)
MACVLAN_GATEWAY=""                  # Gateway IP (e.g., 192.168.1.1)
MACVLAN_IP=""                       # Static IP for container (recommended)
MACVLAN_MAC=""                      # MAC address (optional, for DHCP reservation)

# --- Admin ---
ADMIN_PASSWORD=""                   # Admin user password (auto-generated if empty)

# --- Internal State ---
INTERACTIVE=false                   # Running in interactive mode
VALIDATION_ERRORS=()                # Accumulated validation errors
SECRETS_GENERATED=false             # Whether secrets have been generated

# --- Repository URLs ---
KG_REPO_RAW="https://raw.githubusercontent.com/aaronsb/knowledge-graph-system/main"
KG_REPO="https://github.com/aaronsb/knowledge-graph-system"


# ============================================================================
# SECTION 2: UTILITY FUNCTIONS
# ============================================================================
#
# Helper functions used throughout the script:
#   - Logging (colored output)
#   - User prompts (for interactive mode)
#   - Validation helpers
#   - System detection
#

# --- Terminal Colors ---
# Disable colors if not running in a terminal (e.g., piped to file)
if [ -t 1 ]; then
    RED=$'\033[0;31m'
    GREEN=$'\033[0;32m'
    YELLOW=$'\033[1;33m'
    BLUE=$'\033[0;34m'
    CYAN=$'\033[0;36m'
    BOLD=$'\033[1m'
    NC=$'\033[0m'  # No Color
else
    RED='' GREEN='' YELLOW='' BLUE='' CYAN='' BOLD='' NC=''
fi

# --- Logging Functions ---
# These write to stderr so they display even when stdout is captured

log_info() {
    echo -e "${BLUE}ℹ${NC} $1" >&2
}

log_success() {
    echo -e "${GREEN}✓${NC} $1" >&2
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $1" >&2
}

log_error() {
    echo -e "${RED}✗${NC} $1" >&2
}

log_step() {
    # Major step header
    echo -e "\n${BOLD}${BLUE}==>${NC} ${BOLD}$1${NC}" >&2
}

# ============================================================================
# SUDO HELPER FUNCTIONS
# ============================================================================
# All privileged operations go through these functions, making it clear
# what requires elevated access. The sudo token is acquired once at startup.
#
# Usage:
#   sudo_ensure                         # Acquire/refresh sudo token
#   as_root mkdir -p /opt/something     # Run command as root
#   as_root_write "content" /opt/file   # Write string to file
#   as_root_write_stdin /opt/file <<EOF # Write heredoc to file
#   as_root_append "line" /opt/file     # Append string to file
#   as_root_append_stdin /opt/file <<EOF# Append heredoc to file
#   docker_cmd compose up -d            # Run docker as root
# ============================================================================

sudo_ensure() {
    # Acquire or refresh sudo token
    # Call at startup and before privileged ops after long-running processes
    # Usage: sudo_ensure
    if ! sudo -v; then
        log_error "Failed to acquire sudo privileges"
        return 1
    fi
}

as_root() {
    # Run a command as root
    # Usage: as_root mkdir -p /opt/dir
    sudo "$@"
}

as_root_write() {
    # Write content to a file as root (overwrites)
    # Usage: as_root_write "content" /path/to/file
    local content="$1"
    local file="$2"
    echo "$content" | as_root_write_stdin "$file"
}

as_root_write_stdin() {
    # Write stdin to a file as root (for heredocs)
    # Usage: as_root_write_stdin /path/to/file <<< "content"
    #    or: as_root_write_stdin /path/to/file < somefile
    local file="$1"
    sudo tee "$file" > /dev/null
}

as_root_append() {
    # Append content to a file as root
    # Usage: as_root_append "line" /path/to/file
    local content="$1"
    local file="$2"
    echo "$content" | sudo tee -a "$file" > /dev/null
}

as_root_append_stdin() {
    # Append stdin to a file as root (for heredocs)
    # Usage: as_root_append_stdin /path/to/file << 'EOF'
    local file="$1"
    sudo tee -a "$file" > /dev/null
}

docker_cmd() {
    # Run docker command (always needs sudo unless user is in docker group)
    # Usage: docker_cmd compose up -d
    sudo docker "$@"
}

# --- Prompt Functions ---
# These handle user input in interactive mode. All read from /dev/tty
# to work correctly when script is piped (curl | bash).

prompt_value() {
    # Prompt for a text value with optional default
    # Usage: result=$(prompt_value "Prompt text" "default")
    local prompt="$1"
    local default="$2"
    local value

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
    # Prompt for a password (hidden input)
    # Usage: result=$(prompt_password "Password")
    local prompt="$1"
    local value

    echo -ne "${CYAN}?${NC} ${prompt}: " >&2
    read -sr value </dev/tty
    echo >&2  # Newline after hidden input
    echo "$value"
}

prompt_password_confirm() {
    # Prompt for a password with confirmation
    # Usage: result=$(prompt_password_confirm "Password")
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
            log_warning "Passwords don't match, try again"
        fi
    done
}

prompt_select() {
    # Prompt user to select from a list of options
    # Usage: result=$(prompt_select "Question" "opt1" "opt2" "opt3")
    # Returns the selected option text
    local prompt="$1"
    shift
    local options=("$@")

    echo -e "${CYAN}?${NC} ${prompt}" >&2
    local i=1
    for opt in "${options[@]}"; do
        echo "   ${i}) ${opt}" >&2
        ((i++))
    done

    local selection
    echo -ne "   Choice [1]: " >&2
    read -r selection </dev/tty
    selection=${selection:-1}

    if [[ "$selection" -ge 1 && "$selection" -le ${#options[@]} ]]; then
        echo "${options[$((selection-1))]}"
    else
        echo "${options[0]}"  # Default to first option
    fi
}

prompt_bool() {
    # Prompt for yes/no answer
    # Usage: if prompt_bool "Enable feature?"; then ...
    local prompt="$1"
    local default="${2:-n}"  # Default to 'n' if not specified
    local response

    if [[ "$default" == "y" ]]; then
        echo -ne "${CYAN}?${NC} ${prompt} [Y/n]: " >&2
    else
        echo -ne "${CYAN}?${NC} ${prompt} [y/N]: " >&2
    fi

    read -r response </dev/tty
    response="${response:-$default}"

    [[ "$response" =~ ^[Yy] ]]
}

# --- Validation Helpers ---

add_validation_error() {
    # Add an error to the validation error list
    VALIDATION_ERRORS+=("$1")
}

validate_ip() {
    # Check if string is a valid IPv4 address
    local ip="$1"
    [[ "$ip" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]
}

validate_cidr() {
    # Check if string is a valid CIDR notation
    local cidr="$1"
    [[ "$cidr" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+/[0-9]+$ ]]
}

validate_hostname_format() {
    # Check if string looks like a valid hostname or IP
    local host="$1"
    [[ -n "$host" ]] && [[ "$host" =~ ^[a-zA-Z0-9]([a-zA-Z0-9\.\-]*[a-zA-Z0-9])?$ || "$host" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]
}

validate_email() {
    # Basic email format validation
    local email="$1"
    [[ "$email" =~ ^[^@]+@[^@]+\.[^@]+$ ]]
}

# --- System Detection ---

detect_default_interface() {
    # Find the default network interface
    ip route | grep default | awk '{print $5}' | head -1
}

detect_default_ip() {
    # Get the first non-localhost IP
    hostname -I 2>/dev/null | awk '{print $1}'
}

is_private_ip() {
    # Check if hostname/IP is private (would need DNS-01 for Let's Encrypt)
    local host="$1"
    [[ "$host" == "localhost" ]] || \
    [[ "$host" =~ ^192\.168\. ]] || \
    [[ "$host" =~ ^10\. ]] || \
    [[ "$host" =~ ^172\.(1[6-9]|2[0-9]|3[01])\. ]] || \
    [[ "$host" =~ \.local$ ]] || \
    [[ "$host" =~ \.internal$ ]]
}


# ============================================================================
# SECTION 3A: FLAG PARSING (Headless Mode)
# ============================================================================
#
# Parse command-line flags to populate configuration variables.
# Every flag here should have a corresponding interactive prompt in Section 3B.
#

show_help() {
    cat << 'EOF'
Knowledge Graph Platform Installer

Install the Knowledge Graph system on a fresh server.

USAGE:
  curl -fsSL <url>/install.sh | bash                    # Interactive mode
  curl -fsSL <url>/install.sh | bash -s -- [OPTIONS]    # Headless mode

BASIC OPTIONS:
  --hostname HOSTNAME       Public hostname or IP for web access
  --install-dir DIR         Installation directory (default: ~/knowledge-graph)
  --help                    Show this help message

AI PROVIDER OPTIONS:
  --ai-provider PROVIDER    AI extraction provider: openai, anthropic, ollama
  --ai-model MODEL          Model name (default varies by provider)
  --ai-key KEY              API key for the AI provider
  --skip-ai                 Skip AI provider configuration (configure later)

GPU OPTIONS:
  --gpu MODE                GPU acceleration: auto, nvidia, amd, cpu (default: auto)

SSL/HTTPS OPTIONS:
  --ssl MODE                SSL mode: offload, selfsigned, letsencrypt, manual
                            • offload: HTTP only (behind reverse proxy)
                            • selfsigned: Generate self-signed cert
                            • letsencrypt: Auto-generate via Let's Encrypt
                            • manual: Use existing certificates

  --ssl-email EMAIL         Email for Let's Encrypt registration
  --ssl-cert PATH           Path to SSL certificate (manual mode)
  --ssl-key PATH            Path to SSL private key (manual mode)

  --ssl-dns PROVIDER        DNS provider for DNS-01 challenge (e.g., dns_porkbun)
                            Required for Let's Encrypt on private networks
  --ssl-dns-key KEY         DNS provider API key
  --ssl-dns-secret SECRET   DNS provider API secret

MACVLAN OPTIONS (Dedicated LAN IP):
  --macvlan                 Use existing kg-macvlan network
  --macvlan-ip IP           Static IP on macvlan (recommended)
  --macvlan-mac MAC         MAC address for DHCP reservation

  --macvlan-create          Create new kg-macvlan network
  --macvlan-parent IFACE    Parent interface (e.g., eth0, eno1)
  --macvlan-subnet CIDR     Network subnet (e.g., 192.168.1.0/24)
  --macvlan-gateway IP      Gateway IP (e.g., 192.168.1.1)

  --macvlan-delete          Delete existing kg-macvlan network

ADMIN OPTIONS:
  --admin-password PASS     Set admin password (default: auto-generated)

EXAMPLES:
  # Interactive installation
  curl -fsSL https://raw.githubusercontent.com/.../install.sh | bash

  # Basic headless with OpenAI
  curl -fsSL .../install.sh | bash -s -- \
    --hostname myserver.example.com \
    --ai-provider openai --ai-key "$OPENAI_API_KEY"

  # Let's Encrypt with DNS-01 (Porkbun) + macvlan
  curl -fsSL .../install.sh | bash -s -- \
    --hostname kg.example.com \
    --ssl letsencrypt --ssl-email admin@example.com \
    --ssl-dns dns_porkbun \
    --ssl-dns-key "$PORKBUN_API_KEY" \
    --ssl-dns-secret "$PORKBUN_SECRET_KEY" \
    --macvlan --macvlan-ip 192.168.1.82 \
    --skip-ai

EOF
    exit 0
}

parse_flags() {
    # Parse command-line arguments and set configuration variables
    #
    # If no flags are provided (or only unknown flags), we'll run in
    # interactive mode. If ANY known flag is provided, we're in headless mode.

    local has_known_flags=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            # --- Help ---
            --help|-h)
                show_help
                ;;

            # --- Installation ---
            --install-dir)
                INSTALL_DIR="$2"
                has_known_flags=true
                shift 2
                ;;

            # --- Basic ---
            --hostname)
                HOSTNAME="$2"
                has_known_flags=true
                shift 2
                ;;

            # --- AI Provider ---
            --ai-provider)
                AI_PROVIDER="$2"
                has_known_flags=true
                shift 2
                ;;
            --ai-model)
                AI_MODEL="$2"
                has_known_flags=true
                shift 2
                ;;
            --ai-key)
                AI_KEY="$2"
                has_known_flags=true
                shift 2
                ;;
            --skip-ai)
                SKIP_AI=true
                has_known_flags=true
                shift
                ;;

            # --- GPU ---
            --gpu)
                GPU_MODE="$2"
                has_known_flags=true
                shift 2
                ;;

            # --- SSL ---
            --ssl)
                SSL_MODE="$2"
                has_known_flags=true
                shift 2
                ;;
            --ssl-email)
                SSL_EMAIL="$2"
                has_known_flags=true
                shift 2
                ;;
            --ssl-cert)
                SSL_CERT_PATH="$2"
                has_known_flags=true
                shift 2
                ;;
            --ssl-key)
                SSL_KEY_PATH="$2"
                has_known_flags=true
                shift 2
                ;;
            --ssl-dns)
                SSL_DNS_PROVIDER="$2"
                has_known_flags=true
                shift 2
                ;;
            --ssl-dns-key)
                SSL_DNS_KEY="$2"
                has_known_flags=true
                shift 2
                ;;
            --ssl-dns-secret)
                SSL_DNS_SECRET="$2"
                has_known_flags=true
                shift 2
                ;;

            # --- Macvlan ---
            --macvlan)
                MACVLAN_ENABLED=true
                has_known_flags=true
                shift
                ;;
            --macvlan-create)
                MACVLAN_ENABLED=true
                MACVLAN_CREATE=true
                has_known_flags=true
                shift
                ;;
            --macvlan-delete)
                MACVLAN_DELETE=true
                has_known_flags=true
                shift
                ;;
            --macvlan-parent)
                MACVLAN_PARENT="$2"
                has_known_flags=true
                shift 2
                ;;
            --macvlan-subnet)
                MACVLAN_SUBNET="$2"
                has_known_flags=true
                shift 2
                ;;
            --macvlan-gateway)
                MACVLAN_GATEWAY="$2"
                has_known_flags=true
                shift 2
                ;;
            --macvlan-ip)
                MACVLAN_IP="$2"
                has_known_flags=true
                shift 2
                ;;
            --macvlan-mac)
                MACVLAN_MAC="$2"
                has_known_flags=true
                shift 2
                ;;

            # --- Admin ---
            --admin-password)
                ADMIN_PASSWORD="$2"
                has_known_flags=true
                shift 2
                ;;

            # --- Unknown ---
            *)
                log_error "Unknown option: $1"
                log_info "Run with --help for usage information"
                exit 1
                ;;
        esac
    done

    # If no known flags were provided, run in interactive mode
    if [[ "$has_known_flags" == "false" ]]; then
        INTERACTIVE=true
    fi
}


# ============================================================================
# SECTION 3B: INTERACTIVE PROMPTS (Wizard Mode)
# ============================================================================
#
# Step-based interactive setup. Each step handles one category of config
# and mirrors the flags available in headless mode.
#
# Steps are run in order by run_interactive_setup(). Each step:
#   1. Displays a header
#   2. Prompts for relevant options
#   3. Sets the corresponding config variables
#

step_welcome() {
    # Display welcome message and explain what will happen
    echo
    echo -e "${BOLD}${BLUE}Knowledge Graph Platform Installer${NC}"
    echo
    echo "This wizard will guide you through the installation."
    echo "You can also run with --help to see headless options."
    echo
}

step_install_dir() {
    # Step: Choose installation directory
    echo
    echo -e "${BOLD}=== Installation Location ===${NC}"
    echo

    INSTALL_DIR=$(prompt_value "Installation directory" "$KG_INSTALL_DIR")
}

step_hostname() {
    # Step: Configure hostname/IP for web access
    echo
    echo -e "${BOLD}=== Basic Configuration ===${NC}"
    echo

    local default_host
    default_host=$(detect_default_ip)
    [[ -z "$default_host" ]] && default_host="localhost"

    HOSTNAME=$(prompt_value "Hostname or IP for web access" "$default_host")
}

step_network() {
    # Step: Configure macvlan networking (optional)
    #
    # Macvlan gives the platform its own LAN IP, useful when:
    #   - Ports 80/443 are already in use on the host
    #   - You want the platform to appear as a separate device
    #   - Running behind a firewall where port forwarding isn't possible
    echo
    echo -e "${BOLD}=== Network Configuration ===${NC}"
    echo
    echo "Macvlan networking gives the platform its own LAN IP address."
    echo "This is useful when ports 80/443 are already in use."
    echo

    if prompt_bool "Use macvlan networking (dedicated LAN IP)?" "n"; then
        MACVLAN_ENABLED=true

        # Check if kg-macvlan network already exists
        if docker_cmd network inspect "$MACVLAN_NETWORK" &>/dev/null; then
            log_success "Found existing '$MACVLAN_NETWORK' network"

            # Show current network config
            local subnet gateway parent
            subnet=$(docker_cmd network inspect "$MACVLAN_NETWORK" --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}')
            gateway=$(docker_cmd network inspect "$MACVLAN_NETWORK" --format '{{range .IPAM.Config}}{{.Gateway}}{{end}}')
            parent=$(docker_cmd network inspect "$MACVLAN_NETWORK" --format '{{index .Options "parent"}}')
            echo "   Subnet: $subnet, Gateway: $gateway, Parent: $parent"
            echo

            if prompt_bool "Use this existing network?" "y"; then
                MACVLAN_CREATE=false
            else
                if prompt_bool "Delete and recreate it?" "n"; then
                    MACVLAN_DELETE=true
                    MACVLAN_CREATE=true
                else
                    log_info "Keeping existing network"
                fi
            fi
        else
            log_info "No existing '$MACVLAN_NETWORK' network found"
            MACVLAN_CREATE=true
        fi

        # If creating new network, get parameters
        if [[ "$MACVLAN_CREATE" == "true" ]]; then
            echo
            echo "Configure the macvlan network:"
            local default_iface
            default_iface=$(detect_default_interface)

            MACVLAN_PARENT=$(prompt_value "Parent network interface" "$default_iface")
            MACVLAN_SUBNET=$(prompt_value "Network subnet (CIDR)" "192.168.1.0/24")
            MACVLAN_GATEWAY=$(prompt_value "Gateway IP" "192.168.1.1")
        fi

        # Static IP (recommended) or DHCP
        echo
        echo "A static IP is recommended. DHCP reservations don't work reliably"
        echo "because Docker generates random MAC addresses for secondary networks."
        echo
        MACVLAN_IP=$(prompt_value "Static IP for container (or leave empty for DHCP)" "")

        if [[ -z "$MACVLAN_IP" ]]; then
            log_warning "Using DHCP - container IP may change on restart"
            MACVLAN_MAC=$(prompt_value "MAC address for DHCP reservation (or leave empty)" "")
        fi
    fi
}

step_ssl() {
    # Step: Configure SSL/HTTPS
    #
    # Options:
    #   - offload: No SSL in containers, use reverse proxy (Traefik, nginx, etc.)
    #   - selfsigned: Generate self-signed cert (browser warnings)
    #   - letsencrypt: Auto-generate via Let's Encrypt (requires domain)
    #   - manual: Use existing certificate files
    echo
    echo -e "${BOLD}=== SSL/HTTPS Configuration ===${NC}"
    echo

    local ssl_choice
    ssl_choice=$(prompt_select "SSL/HTTPS mode" \
        "offload (behind reverse proxy)" \
        "selfsigned (quick setup, browser warnings)" \
        "letsencrypt (auto-generate certificate)" \
        "manual (use existing certificates)")

    # Extract first word (the actual mode)
    SSL_MODE="${ssl_choice%% *}"

    case "$SSL_MODE" in
        letsencrypt)
            echo
            SSL_EMAIL=$(prompt_value "Email for Let's Encrypt registration" "")

            if [[ -z "$SSL_EMAIL" ]]; then
                log_warning "Email required for Let's Encrypt"
                SSL_MODE="offload"
                return
            fi

            # Determine if we need DNS-01 challenge
            # DNS-01 is required for:
            #   - Private IPs (192.168.x.x, 10.x.x.x, etc.)
            #   - Internal domains (.local, .internal)
            #   - Servers behind NAT without port 80 forwarding
            echo
            local need_dns=false

            if is_private_ip "$HOSTNAME"; then
                log_info "Private hostname detected - DNS-01 challenge required"
                need_dns=true
            else
                # Public hostname - offer choice
                local challenge_choice
                challenge_choice=$(prompt_select "Certificate challenge method" \
                    "http (port 80 must be accessible from internet)" \
                    "dns (works behind NAT/firewall)")

                if [[ "$challenge_choice" == dns* ]]; then
                    need_dns=true
                fi
            fi

            if [[ "$need_dns" == "true" ]]; then
                echo
                echo "DNS-01 challenge requires API access to your DNS provider."
                echo "Supported providers: https://github.com/acmesh-official/acme.sh/wiki/dnsapi"
                echo

                local dns_choice
                dns_choice=$(prompt_select "DNS provider" \
                    "dns_porkbun" \
                    "dns_cloudflare" \
                    "dns_digitalocean" \
                    "dns_gandi" \
                    "dns_namecheap" \
                    "other (enter manually)")

                if [[ "$dns_choice" == "other"* ]]; then
                    SSL_DNS_PROVIDER=$(prompt_value "DNS provider name (e.g., dns_route53)" "")
                else
                    SSL_DNS_PROVIDER="$dns_choice"
                fi

                if [[ -n "$SSL_DNS_PROVIDER" ]]; then
                    echo
                    SSL_DNS_KEY=$(prompt_value "DNS API key" "")
                    SSL_DNS_SECRET=$(prompt_value "DNS API secret (if required, or Enter to skip)" "")
                fi

                if [[ -z "$SSL_DNS_PROVIDER" || -z "$SSL_DNS_KEY" ]]; then
                    log_warning "DNS credentials required for DNS-01 challenge"
                    log_info "Falling back to HTTP-only mode"
                    SSL_MODE="offload"
                    SSL_DNS_PROVIDER=""
                fi
            fi
            ;;

        manual)
            echo
            SSL_CERT_PATH=$(prompt_value "Path to SSL certificate (fullchain.pem)" "")
            SSL_KEY_PATH=$(prompt_value "Path to SSL private key (privkey.pem)" "")

            if [[ ! -f "$SSL_CERT_PATH" ]] || [[ ! -f "$SSL_KEY_PATH" ]]; then
                log_warning "Certificate files not found"
                log_info "Falling back to HTTP-only mode"
                SSL_MODE="offload"
            fi
            ;;

        selfsigned)
            log_info "Self-signed certificate will be generated"
            log_warning "Browsers will show security warnings"
            ;;

        offload)
            log_info "No SSL - configure your reverse proxy to handle HTTPS"
            ;;
    esac
}

step_ai() {
    # Step: Configure AI provider for document extraction
    #
    # The AI provider is used to extract concepts and relationships from
    # documents. Options:
    #   - openai: GPT-4o, GPT-4o-mini (cloud, requires API key)
    #   - anthropic: Claude Sonnet 4, Claude 3.5 (cloud, requires API key)
    #   - ollama: Local inference (requires separate Ollama installation)
    #   - skip: Configure later via operator.sh
    echo
    echo -e "${BOLD}=== AI Provider Configuration ===${NC}"
    echo
    echo "An AI provider is needed for document concept extraction."
    echo "You can skip this and configure later with: ./operator.sh shell"
    echo

    local ai_choice
    ai_choice=$(prompt_select "AI provider for document extraction" \
        "openai (GPT-4o)" \
        "anthropic (Claude)" \
        "ollama (local)" \
        "skip (configure later)")

    # Extract first word
    AI_PROVIDER="${ai_choice%% *}"

    if [[ "$AI_PROVIDER" == "skip" ]]; then
        SKIP_AI=true
        AI_PROVIDER=""
        return
    fi

    case "$AI_PROVIDER" in
        openai)
            AI_MODEL=$(prompt_value "Model name" "gpt-4o")
            echo
            AI_KEY=$(prompt_value "OpenAI API key" "")

            if [[ -z "$AI_KEY" ]]; then
                log_warning "API key required for OpenAI"
                SKIP_AI=true
                AI_PROVIDER=""
            fi
            ;;

        anthropic)
            AI_MODEL=$(prompt_value "Model name" "claude-sonnet-4")
            echo
            AI_KEY=$(prompt_value "Anthropic API key" "")

            if [[ -z "$AI_KEY" ]]; then
                log_warning "API key required for Anthropic"
                SKIP_AI=true
                AI_PROVIDER=""
            fi
            ;;

        ollama)
            AI_MODEL=$(prompt_value "Model name" "llama3.1")
            log_info "Ollama runs locally - no API key needed"
            log_info "Make sure Ollama is installed and running"
            ;;
    esac
}

step_gpu() {
    # Step: Configure GPU acceleration
    #
    # GPU acceleration speeds up local embedding generation.
    # Options:
    #   - auto: Detect available GPU
    #   - nvidia: Force NVIDIA GPU (requires nvidia-container-toolkit)
    #   - amd: Force AMD GPU (requires ROCm)
    #   - cpu: No GPU acceleration
    echo
    echo -e "${BOLD}=== GPU Configuration ===${NC}"
    echo
    echo "GPU acceleration speeds up local embedding generation."
    echo

    local gpu_choice
    gpu_choice=$(prompt_select "GPU acceleration" \
        "auto (detect)" \
        "nvidia (NVIDIA GPU)" \
        "amd (AMD GPU)" \
        "cpu (no GPU)")

    GPU_MODE="${gpu_choice%% *}"
}

step_admin() {
    # Step: Configure admin password
    echo
    echo -e "${BOLD}=== Admin Configuration ===${NC}"
    echo
    echo "The admin account is used to manage the platform."
    echo "A secure password will be auto-generated if you skip this."
    echo

    if prompt_bool "Set a custom admin password?" "n"; then
        ADMIN_PASSWORD=$(prompt_password_confirm "Admin password")
    else
        log_info "Admin password will be auto-generated"
    fi
}

step_confirm() {
    # Step: Review configuration and confirm
    echo
    echo -e "${BOLD}=== Configuration Summary ===${NC}"
    echo
    echo "  Install directory: ${INSTALL_DIR:-$KG_INSTALL_DIR}"
    echo "  Hostname:          $HOSTNAME"
    echo "  SSL mode:          $SSL_MODE"
    [[ -n "$SSL_DNS_PROVIDER" ]] && echo "  DNS provider:      $SSL_DNS_PROVIDER"
    [[ "$MACVLAN_ENABLED" == "true" ]] && echo "  Macvlan IP:        ${MACVLAN_IP:-DHCP}"
    echo "  GPU mode:          $GPU_MODE"
    if [[ "$SKIP_AI" == "true" ]]; then
        echo "  AI provider:       (configure later)"
    else
        echo "  AI provider:       ${AI_PROVIDER:-none}"
        [[ -n "$AI_MODEL" ]] && echo "  AI model:          $AI_MODEL"
    fi
    echo

    if ! prompt_bool "Proceed with installation?" "y"; then
        log_info "Installation cancelled"
        exit 0
    fi
}

run_interactive_setup() {
    # Run all interactive steps in order
    step_welcome
    step_install_dir
    step_hostname
    step_network
    step_ssl
    step_ai
    step_gpu
    step_admin
    step_confirm
}


# ============================================================================
# SECTION 4: CONFIGURATION VALIDATION
# ============================================================================
#
# Validate configuration regardless of how it was collected (flags or interactive).
# This ensures consistent error handling and clear error messages.
#

validate_config() {
    # Validate all configuration and accumulate errors
    # Returns 0 if valid, 1 if errors found

    VALIDATION_ERRORS=()

    # --- Required fields ---
    if [[ -z "$HOSTNAME" ]]; then
        add_validation_error "Hostname is required (--hostname or interactive)"
    elif ! validate_hostname_format "$HOSTNAME"; then
        add_validation_error "Invalid hostname format: $HOSTNAME"
    fi

    # --- SSL validation ---
    case "$SSL_MODE" in
        offload|selfsigned)
            # No additional validation needed
            ;;
        letsencrypt)
            if [[ -z "$SSL_EMAIL" ]]; then
                add_validation_error "Email required for Let's Encrypt (--ssl-email)"
            elif ! validate_email "$SSL_EMAIL"; then
                add_validation_error "Invalid email format: $SSL_EMAIL"
            fi

            # If using DNS-01, validate DNS credentials
            if [[ -n "$SSL_DNS_PROVIDER" ]]; then
                if [[ -z "$SSL_DNS_KEY" ]]; then
                    add_validation_error "DNS API key required for DNS-01 challenge (--ssl-dns-key)"
                fi
            fi
            ;;
        manual)
            if [[ -z "$SSL_CERT_PATH" ]]; then
                add_validation_error "Certificate path required for manual SSL (--ssl-cert)"
            elif [[ ! -f "$SSL_CERT_PATH" ]]; then
                add_validation_error "Certificate file not found: $SSL_CERT_PATH"
            fi

            if [[ -z "$SSL_KEY_PATH" ]]; then
                add_validation_error "Key path required for manual SSL (--ssl-key)"
            elif [[ ! -f "$SSL_KEY_PATH" ]]; then
                add_validation_error "Key file not found: $SSL_KEY_PATH"
            fi
            ;;
        *)
            add_validation_error "Invalid SSL mode: $SSL_MODE (must be: offload, selfsigned, letsencrypt, manual)"
            ;;
    esac

    # --- Macvlan validation ---
    if [[ "$MACVLAN_CREATE" == "true" ]]; then
        if [[ -z "$MACVLAN_PARENT" ]]; then
            add_validation_error "Parent interface required for macvlan (--macvlan-parent)"
        fi
        if [[ -z "$MACVLAN_SUBNET" ]]; then
            add_validation_error "Subnet required for macvlan (--macvlan-subnet)"
        elif ! validate_cidr "$MACVLAN_SUBNET"; then
            add_validation_error "Invalid subnet format: $MACVLAN_SUBNET (expected CIDR, e.g., 192.168.1.0/24)"
        fi
        if [[ -z "$MACVLAN_GATEWAY" ]]; then
            add_validation_error "Gateway required for macvlan (--macvlan-gateway)"
        elif ! validate_ip "$MACVLAN_GATEWAY"; then
            add_validation_error "Invalid gateway IP: $MACVLAN_GATEWAY"
        fi
    fi

    if [[ -n "$MACVLAN_IP" ]] && ! validate_ip "$MACVLAN_IP"; then
        add_validation_error "Invalid macvlan IP: $MACVLAN_IP"
    fi

    # --- AI provider validation ---
    if [[ "$SKIP_AI" == "false" && -n "$AI_PROVIDER" ]]; then
        case "$AI_PROVIDER" in
            openai|anthropic)
                if [[ -z "$AI_KEY" ]]; then
                    add_validation_error "API key required for $AI_PROVIDER (--ai-key)"
                fi
                ;;
            ollama)
                # No key required
                ;;
            *)
                add_validation_error "Invalid AI provider: $AI_PROVIDER (must be: openai, anthropic, ollama)"
                ;;
        esac
    fi

    # --- GPU validation ---
    case "$GPU_MODE" in
        auto|nvidia|amd|cpu)
            # Valid
            ;;
        *)
            add_validation_error "Invalid GPU mode: $GPU_MODE (must be: auto, nvidia, amd, cpu)"
            ;;
    esac

    # --- Report errors ---
    if [[ ${#VALIDATION_ERRORS[@]} -gt 0 ]]; then
        echo
        echo -e "${BOLD}${RED}Configuration Error${NC}"
        echo
        for error in "${VALIDATION_ERRORS[@]}"; do
            log_error "$error"
        done
        echo
        log_info "Run with --help for usage information"
        return 1
    fi

    return 0
}


# ============================================================================
# SECTION 5: PREREQUISITES AND DOCKER CHECK
# ============================================================================
#
# Check that the system meets requirements before proceeding.
#

check_prerequisites() {
    log_step "Checking prerequisites"

    # Check for required commands
    local missing=()

    if ! command -v curl &>/dev/null; then
        missing+=("curl")
    fi

    if ! command -v openssl &>/dev/null; then
        missing+=("openssl")
    fi

    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Missing required commands: ${missing[*]}"
        log_info "Install with: sudo apt install ${missing[*]}"
        exit 1
    fi

    log_success "Prerequisites OK"
}

check_docker() {
    log_step "Checking Docker"

    if ! command -v docker &>/dev/null; then
        log_warning "Docker not found"

        if [[ "$INTERACTIVE" == "true" ]]; then
            if prompt_bool "Install Docker now?" "y"; then
                install_docker
            else
                log_error "Docker is required. Install manually and retry."
                exit 1
            fi
        else
            log_error "Docker is required. Install with: curl -fsSL https://get.docker.com | sh"
            exit 1
        fi
    fi

    # Verify Docker is running (use sudo since user may not be in docker group)
    if ! docker_cmd info &>/dev/null; then
        log_error "Docker daemon is not running"
        log_info "Start with: sudo systemctl start docker"
        exit 1
    fi

    # Check for compose plugin
    if ! docker_cmd compose version &>/dev/null; then
        log_error "Docker Compose plugin not found"
        log_info "Install with: sudo apt install docker-compose-plugin"
        exit 1
    fi

    log_success "Docker is installed: $(docker --version | head -1)"
}

install_docker() {
    # Install Docker using the official convenience script
    log_info "Installing Docker..."

    if curl -fsSL https://get.docker.com | as_root sh; then
        log_success "Docker installed"

        # Add current user to docker group
        as_root usermod -aG docker "$USER"
        log_info "Added $USER to docker group"
        log_warning "You may need to log out and back in for group changes to take effect"
    else
        log_error "Docker installation failed"
        exit 1
    fi
}


# ============================================================================
# SECTION 6: MACVLAN NETWORK SETUP
# ============================================================================
#
# Handle macvlan network creation/deletion if needed.
#

generate_macvlan_mac() {
    # Generate a random locally-administered MAC address
    # Format: x2:xx:xx:xx:xx:xx (where x2 indicates locally administered)
    printf '02:%02x:%02x:%02x:%02x:%02x' \
        $((RANDOM % 256)) $((RANDOM % 256)) \
        $((RANDOM % 256)) $((RANDOM % 256)) \
        $((RANDOM % 256))
}

setup_macvlan() {
    # Create or delete macvlan network as configured

    if [[ "$MACVLAN_DELETE" == "true" ]]; then
        log_step "Deleting macvlan network"

        if docker_cmd network inspect "$MACVLAN_NETWORK" &>/dev/null; then
            # Check for connected containers
            local connected
            connected=$(docker_cmd network inspect "$MACVLAN_NETWORK" --format '{{range .Containers}}{{.Name}} {{end}}')
            if [[ -n "$connected" ]]; then
                log_error "Cannot delete network - containers connected: $connected"
                log_info "Stop containers first: sudo docker stop $connected"
                exit 1
            fi

            docker_cmd network rm "$MACVLAN_NETWORK"
            log_success "Deleted network: $MACVLAN_NETWORK"
        else
            log_info "Network '$MACVLAN_NETWORK' does not exist"
        fi
    fi

    if [[ "$MACVLAN_CREATE" == "true" ]]; then
        log_step "Creating macvlan network"

        # Delete existing if requested
        if docker_cmd network inspect "$MACVLAN_NETWORK" &>/dev/null; then
            log_info "Removing existing network '$MACVLAN_NETWORK'"
            docker_cmd network rm "$MACVLAN_NETWORK" || true
        fi

        log_info "Creating network: $MACVLAN_NETWORK"
        log_info "  Parent: $MACVLAN_PARENT"
        log_info "  Subnet: $MACVLAN_SUBNET"
        log_info "  Gateway: $MACVLAN_GATEWAY"

        docker_cmd network create -d macvlan \
            --subnet="$MACVLAN_SUBNET" \
            --gateway="$MACVLAN_GATEWAY" \
            -o parent="$MACVLAN_PARENT" \
            "$MACVLAN_NETWORK"

        log_success "Created network: $MACVLAN_NETWORK"
    fi

    # Verify network exists if macvlan is enabled
    if [[ "$MACVLAN_ENABLED" == "true" ]]; then
        if ! docker_cmd network inspect "$MACVLAN_NETWORK" &>/dev/null; then
            log_error "Macvlan network '$MACVLAN_NETWORK' not found"
            log_info "Create with: --macvlan-create --macvlan-parent <iface> --macvlan-subnet <cidr> --macvlan-gateway <ip>"
            exit 1
        fi
        log_success "Macvlan networking configured"
    fi
}


# ============================================================================
# SECTION 7: FILE DOWNLOAD
# ============================================================================
#
# Download compose files, schema, and operator script from the repository.
#

download_files() {
    log_step "Downloading platform files"

    local install_dir="${INSTALL_DIR:-$KG_INSTALL_DIR}"

    # Create install directory (needs sudo for /opt)
    as_root mkdir -p "$install_dir"
    cd "$install_dir"

    log_info "Installing to: $install_dir"

    # --- Docker Compose files ---
    local compose_files=(
        "docker-compose.yml"
        "docker-compose.ghcr.yml"
        "docker-compose.standalone.yml"
        "docker-compose.gpu-nvidia.yml"
        "docker-compose.gpu-amd.yml"
    )

    for file in "${compose_files[@]}"; do
        log_info "Downloading $file..."
        if ! curl -fsSL "${KG_REPO_RAW}/docker/${file}" | as_root_write_stdin "$file"; then
            log_error "Failed to download: $file"
            exit 1
        fi
    done

    # Adapt compose files for standalone installation
    # (compose files assume docker/ subdirectory in repo)
    log_info "Adapting compose files for standalone installation..."
    for file in docker-compose*.yml; do
        if [[ -f "$file" ]]; then
            # Fix relative paths
            as_root sed -i 's|\.\./schema/|./schema/|g' "$file"
            as_root sed -i 's|\.\./config/|./config/|g' "$file"
        fi
    done

    log_success "Compose files downloaded"

    # --- Schema files ---
    as_root mkdir -p schema
    log_info "Downloading schema/00_baseline.sql..."
    curl -fsSL "${KG_REPO_RAW}/schema/00_baseline.sql" | as_root_write_stdin "schema/00_baseline.sql"

    # --- Garage config ---
    as_root mkdir -p config
    log_info "Downloading config/garage.toml..."
    curl -fsSL "${KG_REPO_RAW}/config/garage.toml" | as_root_write_stdin "config/garage.toml"

    # --- Operator script ---
    log_info "Downloading operator.sh..."
    curl -fsSL "${KG_REPO_RAW}/operator.sh" | as_root_write_stdin "operator.sh"
    as_root chmod +x operator.sh
    log_success "operator.sh installed - use ./operator.sh to manage the platform"

    # --- Operator config ---
    as_root_write_stdin ".operator.conf" << EOF
# Operator configuration
# Generated by install.sh on $(date -Iseconds)
OPERATOR_MODE=standalone
COMPOSE_PROJECT_NAME=knowledge-graph
EOF
    log_success ".operator.conf created"

    log_success "Files downloaded"
}


# ============================================================================
# SECTION 8: SECRETS GENERATION
# ============================================================================
#
# Generate secure random secrets for the platform.
#

generate_secrets() {
    log_step "Generating secrets"

    local install_dir="${INSTALL_DIR:-$KG_INSTALL_DIR}"
    cd "$install_dir"

    # Generate admin password if not provided
    if [[ -z "$ADMIN_PASSWORD" ]]; then
        ADMIN_PASSWORD=$(openssl rand -base64 16 | tr -d '/+=' | head -c 22)
        log_info "Generated admin password (save this!): $ADMIN_PASSWORD"
    fi

    # Generate infrastructure secrets
    local postgres_password encryption_key oauth_key internal_key garage_rpc_secret

    postgres_password=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
    encryption_key=$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())' 2>/dev/null || openssl rand -base64 32)
    oauth_key=$(openssl rand -base64 48 | tr -d '/+=' | head -c 64)
    internal_key=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
    garage_rpc_secret=$(openssl rand -hex 32)

    # Generate .env file (root-owned for security)
    as_root_write_stdin ".env" << EOF
# Knowledge Graph Platform Configuration
# Generated by install.sh on $(date -Iseconds)
#
# WARNING: This file contains secrets. Do not commit to version control.
#

# --- Database ---
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_USER=admin
POSTGRES_PASSWORD=${postgres_password}
POSTGRES_DB=knowledge_graph

# --- Security ---
# Fernet key for encrypting API keys in database
ENCRYPTION_KEY=${encryption_key}

# JWT signing key for OAuth tokens
OAUTH_SIGNING_KEY=${oauth_key}

# Internal service authentication
INTERNAL_KEY_SERVICE_SECRET=${internal_key}

# --- Garage Object Storage ---
GARAGE_HOST=garage
GARAGE_PORT=3900
GARAGE_BUCKET=kg-storage
GARAGE_RPC_SECRET=${garage_rpc_secret}
# Note: Garage S3 credentials are stored encrypted in the database after initialization
EOF

    # Secure the .env file (root-only, readable by docker/podman)
    as_root chown root:root .env
    as_root chmod 600 .env

    SECRETS_GENERATED=true
    log_success "Secrets generated (.env secured: root:root 600)"
}


# ============================================================================
# SECTION 9: SSL SETUP
# ============================================================================
#
# Configure SSL/HTTPS based on the selected mode.
#

setup_ssl() {
    log_step "Setting up SSL"

    local install_dir="${INSTALL_DIR:-$KG_INSTALL_DIR}"
    cd "$install_dir"

    case "$SSL_MODE" in
        offload)
            log_info "SSL offload mode - no certificates needed"
            log_info "Configure your reverse proxy to handle HTTPS"
            generate_nginx_http_config
            ;;

        selfsigned)
            setup_selfsigned_ssl
            ;;

        letsencrypt)
            if [[ -n "$SSL_DNS_PROVIDER" ]]; then
                setup_letsencrypt_dns
            else
                setup_letsencrypt_http
            fi
            ;;

        manual)
            setup_manual_ssl
            ;;
    esac

    log_success "SSL configured"
}

setup_selfsigned_ssl() {
    # Generate a self-signed certificate
    log_info "Generating self-signed SSL certificate for $HOSTNAME"
    log_warning "Self-signed certificates will show browser warnings - click through to continue"

    local install_dir="${INSTALL_DIR:-$KG_INSTALL_DIR}"
    as_root mkdir -p "$install_dir/certs"

    # Generate certificate with SAN (Subject Alternative Name)
    # Generate to temp location, then copy with sudo
    local cert_tmp=$(mktemp -d)
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$cert_tmp/server.key" -out "$cert_tmp/server.crt" \
        -subj "/CN=$HOSTNAME" \
        -addext "subjectAltName=DNS:$HOSTNAME,IP:${MACVLAN_IP:-127.0.0.1}" \
        2>/dev/null

    as_root cp "$cert_tmp/server.key" "$install_dir/certs/"
    as_root cp "$cert_tmp/server.crt" "$install_dir/certs/"
    as_root chmod 600 "$install_dir/certs/server.key"
    rm -rf "$cert_tmp"

    log_success "Self-signed certificate generated (valid for 365 days)"

    generate_nginx_ssl_config
    generate_ssl_compose_overlay
}

setup_letsencrypt_dns() {
    # Set up Let's Encrypt using DNS-01 challenge via acme.sh
    log_info "Setting up Let's Encrypt with DNS-01 challenge"
    log_info "DNS provider: $SSL_DNS_PROVIDER"

    local install_dir="${INSTALL_DIR:-$KG_INSTALL_DIR}"

    # Use acme.sh standard location - don't fight its design
    # When running as root (via sudo), this is /root/.acme.sh
    local acme_home="$HOME/.acme.sh"

    if [[ ! -f "$acme_home/acme.sh" ]]; then
        log_info "Installing acme.sh..."
        # Use official installer - handles everything correctly
        curl -fsSL https://get.acme.sh | sh -s email="$SSL_EMAIL"
    fi

    as_root mkdir -p "$install_dir/certs"

    # Set DNS API credentials based on provider
    case "$SSL_DNS_PROVIDER" in
        dns_porkbun)
            export PORKBUN_API_KEY="$SSL_DNS_KEY"
            export PORKBUN_SECRET_API_KEY="$SSL_DNS_SECRET"
            ;;
        dns_cloudflare)
            export CF_Key="$SSL_DNS_KEY"
            export CF_Email="$SSL_DNS_SECRET"
            ;;
        dns_digitalocean)
            export DO_API_KEY="$SSL_DNS_KEY"
            ;;
        dns_gandi)
            export GANDI_LIVEDNS_KEY="$SSL_DNS_KEY"
            ;;
        *)
            # Generic - assume key and secret are env vars
            log_warning "Using generic DNS provider setup"
            ;;
    esac

    # Issue certificate (running as normal user - no sudo issues with acme.sh)
    log_info "Requesting certificate for $HOSTNAME..."
    log_info "This may take 1-2 minutes for DNS propagation"

    # Request cert to temp location (user-writable), then copy to install dir
    local cert_tmp="$HOME/.acme.sh/certs-tmp"
    mkdir -p "$cert_tmp"

    local cert_success=false
    local acme_output
    acme_output=$("$acme_home/acme.sh" --issue --dns "$SSL_DNS_PROVIDER" -d "$HOSTNAME" \
        --keylength 2048 \
        --cert-file "$cert_tmp/server.crt" \
        --key-file "$cert_tmp/server.key" \
        --fullchain-file "$cert_tmp/fullchain.crt" 2>&1) && cert_success=true

    # Check if skipped because cert already valid (not due for renewal)
    if echo "$acme_output" | grep -q "Skipping.*Next renewal time"; then
        log_info "Certificate already valid, using existing cert"
        local existing_cert_dir="$acme_home/$HOSTNAME"
        if [[ -f "$existing_cert_dir/$HOSTNAME.cer" && -f "$existing_cert_dir/$HOSTNAME.key" ]]; then
            cert_success=true
            sudo_ensure
            as_root cp "$existing_cert_dir/$HOSTNAME.cer" "$install_dir/certs/server.crt"
            as_root cp "$existing_cert_dir/$HOSTNAME.key" "$install_dir/certs/server.key"
            as_root cp "$existing_cert_dir/fullchain.cer" "$install_dir/certs/fullchain.crt"
            as_root chmod 600 "$install_dir/certs/server.key"
        fi
    elif [ "$cert_success" = true ]; then
        # New cert issued - copy from temp location
        sudo_ensure
        as_root cp "$cert_tmp/server.crt" "$install_dir/certs/"
        as_root cp "$cert_tmp/server.key" "$install_dir/certs/"
        as_root cp "$cert_tmp/fullchain.crt" "$install_dir/certs/"
        as_root chmod 600 "$install_dir/certs/server.key"
        rm -rf "$cert_tmp"
    fi

    if [ "$cert_success" = true ]; then
        log_success "Certificate obtained successfully"
    else
        log_error "Failed to obtain certificate"
        log_info "Check $acme_home/acme.sh.log for details"
        echo

        # Interactive mode: give user a choice
        if [[ "$INTERACTIVE" == "true" ]]; then
            echo -e "${YELLOW}Certificate generation failed. Options:${NC}"
            echo "  1) Use self-signed certificate (browser warnings)"
            echo "  2) Abort installation and fix the issue"
            echo
            local choice
            read -p "Choice [1]: " choice </dev/tty
            choice="${choice:-1}"

            if [[ "$choice" == "2" ]]; then
                log_error "Installation aborted"
                log_info "Fix the issue and re-run: ./install.sh"
                log_info "Common issues:"
                log_info "  - DNS API credentials incorrect"
                log_info "  - DNS provider not supported"
                log_info "  - Rate limited (try again later)"
                exit 1
            fi
        fi

        log_info "Falling back to self-signed certificate"
        setup_selfsigned_ssl
        return
    fi

    generate_nginx_ssl_config
    generate_ssl_compose_overlay

    # Set up auto-renewal
    setup_cert_renewal
}

setup_letsencrypt_http() {
    # Set up Let's Encrypt using HTTP-01 challenge
    # Requires port 80 to be accessible from the internet
    log_info "Setting up Let's Encrypt with HTTP-01 challenge"
    log_warning "Port 80 must be accessible from the internet"

    # Install certbot if not present
    if ! command -v certbot &>/dev/null; then
        log_info "Installing certbot..."
        if command -v apt &>/dev/null; then
            as_root apt update && as_root apt install -y certbot
        elif command -v dnf &>/dev/null; then
            as_root dnf install -y certbot
        else
            log_error "Cannot install certbot - install manually"
            exit 1
        fi
    fi

    local install_dir="${INSTALL_DIR:-$KG_INSTALL_DIR}"
    as_root mkdir -p "$install_dir/certs"

    # Request certificate (standalone mode - binds to port 80 temporarily)
    log_info "Requesting certificate for $HOSTNAME..."

    if as_root certbot certonly --standalone \
        -d "$HOSTNAME" \
        --email "$SSL_EMAIL" \
        --agree-tos \
        --non-interactive; then

        # Copy certificates to our directory
        local certbot_dir="/etc/letsencrypt/live/$HOSTNAME"
        as_root cp "$certbot_dir/fullchain.pem" "$install_dir/certs/server.crt"
        as_root cp "$certbot_dir/privkey.pem" "$install_dir/certs/server.key"
        as_root chmod 600 "$install_dir/certs/server.key"

        log_success "Certificate obtained successfully"
    else
        log_error "Failed to obtain certificate"
        log_info "Ensure port 80 is accessible and DNS points to this server"
        log_info "Falling back to self-signed certificate"
        setup_selfsigned_ssl
        return
    fi

    generate_nginx_ssl_config
    generate_ssl_compose_overlay
}

setup_manual_ssl() {
    # Use existing certificate files
    log_info "Using existing SSL certificates"

    mkdir -p certs
    cp "$SSL_CERT_PATH" certs/server.crt
    cp "$SSL_KEY_PATH" certs/server.key
    chmod 600 certs/server.key

    log_success "Certificates copied"

    generate_nginx_ssl_config
    generate_ssl_compose_overlay
}

setup_cert_renewal() {
    # Set up automatic certificate renewal
    local install_dir="${INSTALL_DIR:-$KG_INSTALL_DIR}"
    local acme_home="$install_dir/.acme.sh"

    # Create renewal script with explicit paths (no ~ expansion issues)
    as_root_write_stdin "$install_dir/renew-certs.sh" << EOF
#!/bin/bash
# Certificate renewal script for $HOSTNAME
# Generated by install.sh

INSTALL_DIR="$install_dir"
ACME_HOME="$acme_home"
DOMAIN="$HOSTNAME"

cd "\$INSTALL_DIR"

"\$ACME_HOME/acme.sh" --home "\$ACME_HOME" --renew -d "\$DOMAIN" \\
    --cert-file "\$INSTALL_DIR/certs/server.crt" \\
    --key-file "\$INSTALL_DIR/certs/server.key" \\
    --fullchain-file "\$INSTALL_DIR/certs/fullchain.crt" \\
    --reloadcmd "docker restart kg-web"
EOF
    as_root chmod +x "$install_dir/renew-certs.sh"

    # Add cron job for renewal (checks daily, only renews when needed)
    (crontab -l 2>/dev/null | grep -v 'renew-certs.sh'; echo "0 3 * * * $install_dir/renew-certs.sh >/dev/null 2>&1") | crontab -

    log_info "Certificate auto-renewal configured"
}

generate_nginx_http_config() {
    # Generate nginx config for HTTP-only mode (SSL offloaded to reverse proxy)
    local install_dir="${INSTALL_DIR:-$KG_INSTALL_DIR}"

    as_root_write_stdin "$install_dir/nginx.conf" << 'EOF'
# Nginx configuration for HTTP mode (SSL offloaded to reverse proxy)
server {
    listen 80;
    server_name _;

    # API proxy
    location /api/ {
        proxy_pass http://api:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF
}

generate_nginx_ssl_config() {
    # Generate nginx config for HTTPS mode
    local install_dir="${INSTALL_DIR:-$KG_INSTALL_DIR}"

    as_root_write_stdin "$install_dir/nginx.ssl.conf" << 'EOF'
# Nginx configuration for HTTPS mode
server {
    listen 80;
    server_name _;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name _;

    ssl_certificate /etc/nginx/certs/server.crt;
    ssl_certificate_key /etc/nginx/certs/server.key;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    # API proxy
    location /api/ {
        proxy_pass http://api:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

    log_info "Generated nginx SSL configuration"
}

generate_ssl_compose_overlay() {
    # Generate docker-compose overlay for SSL mode
    local install_dir="${INSTALL_DIR:-$KG_INSTALL_DIR}"

    # Start building the compose file
    as_root_write_stdin "$install_dir/docker-compose.ssl.yml" << EOF
# SSL compose overlay - generated by install.sh
# Mounts certificates and nginx config for HTTPS

services:
  web:
    volumes:
      - ./nginx.ssl.conf:/etc/nginx/conf.d/default.conf:ro
      - ./certs:/etc/nginx/certs:ro
EOF

    # Add macvlan network configuration if enabled
    if [[ "$MACVLAN_ENABLED" == "true" ]]; then
        as_root_append_stdin "$install_dir/docker-compose.ssl.yml" << EOF
    networks:
      default:
      kg-macvlan:
EOF

        # Add static IP if configured
        if [[ -n "$MACVLAN_IP" ]]; then
            as_root_append_stdin "$install_dir/docker-compose.ssl.yml" << EOF
        ipv4_address: $MACVLAN_IP
EOF
        fi

        # Add MAC address if configured
        if [[ -n "$MACVLAN_MAC" ]]; then
            as_root_append_stdin "$install_dir/docker-compose.ssl.yml" << EOF
    mac_address: $MACVLAN_MAC
EOF
        fi

        # Remove default port bindings (macvlan uses its own IP)
        as_root_append_stdin "$install_dir/docker-compose.ssl.yml" << EOF
    ports: []

networks:
  kg-macvlan:
    external: true
EOF
    fi

    log_info "Generated SSL compose overlay"

    # Update operator.conf with SSL mode
    as_root_append "SSL_MODE=$SSL_MODE" "$install_dir/.operator.conf"
    if [[ "$MACVLAN_ENABLED" == "true" ]]; then
        as_root_append "MACVLAN_ENABLED=true" "$install_dir/.operator.conf"
        [[ -n "$MACVLAN_IP" ]] && as_root_append "MACVLAN_IP=$MACVLAN_IP" "$install_dir/.operator.conf"
    fi
}


# ============================================================================
# SECTION 10: CONTAINER STARTUP
# ============================================================================
#
# Build the compose command and start containers.
#

build_compose_command() {
    # Build the docker compose command with appropriate overlays
    local install_dir="${INSTALL_DIR:-$KG_INSTALL_DIR}"
    local cmd="docker_cmd compose"

    # Base files (always included)
    cmd+=" -f $install_dir/docker-compose.yml"
    cmd+=" -f $install_dir/docker-compose.ghcr.yml"
    cmd+=" -f $install_dir/docker-compose.standalone.yml"

    # GPU overlay
    case "$GPU_MODE" in
        nvidia)
            cmd+=" -f $install_dir/docker-compose.gpu-nvidia.yml"
            ;;
        amd)
            cmd+=" -f $install_dir/docker-compose.gpu-amd.yml"
            ;;
        auto)
            # Detect GPU
            if command -v nvidia-smi &>/dev/null && nvidia-smi &>/dev/null; then
                cmd+=" -f $install_dir/docker-compose.gpu-nvidia.yml"
                log_info "Detected NVIDIA GPU"
            elif [[ -d /dev/dri ]] && command -v rocm-smi &>/dev/null; then
                cmd+=" -f $install_dir/docker-compose.gpu-amd.yml"
                log_info "Detected AMD GPU"
            else
                log_info "No GPU detected, using CPU"
            fi
            ;;
    esac

    # SSL overlay (if not offload mode)
    if [[ "$SSL_MODE" != "offload" ]] && [[ -f "$install_dir/docker-compose.ssl.yml" ]]; then
        cmd+=" -f $install_dir/docker-compose.ssl.yml"
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

    # Start infrastructure first (postgres, garage)
    log_info "Starting infrastructure (postgres, garage)..."
    $compose_cmd up -d postgres garage

    # Wait for PostgreSQL
    log_info "Waiting for PostgreSQL..."
    local retries=30
    while ! $compose_cmd exec -T postgres pg_isready -U admin &>/dev/null; do
        ((retries--))
        if [[ $retries -le 0 ]]; then
            log_error "PostgreSQL failed to start"
            $compose_cmd logs postgres
            exit 1
        fi
        sleep 1
    done
    log_success "PostgreSQL ready"

    # Wait for Garage
    log_info "Waiting for Garage..."
    retries=30
    while ! $compose_cmd exec -T garage /garage status &>/dev/null; do
        ((retries--))
        if [[ $retries -le 0 ]]; then
            log_error "Garage failed to start"
            $compose_cmd logs garage
            exit 1
        fi
        sleep 1
    done
    log_success "Garage ready"

    # Start operator
    log_info "Starting operator..."
    $compose_cmd up -d operator

    # Run database migrations
    log_info "Running database migrations..."
    $compose_cmd exec -T operator /workspace/operator/database/migrate-db.sh
    log_success "Migrations complete"

    # Start application containers
    log_info "Starting application (api, web)..."
    $compose_cmd up -d api web

    # Wait for API
    log_info "Waiting for API..."
    retries=60
    while ! curl -sf http://localhost:8000/health &>/dev/null; do
        ((retries--))
        if [[ $retries -le 0 ]]; then
            log_warning "API may still be starting..."
            break
        fi
        sleep 1
    done

    if curl -sf http://localhost:8000/health &>/dev/null; then
        log_success "API ready"
    fi

    # Wait for Web
    log_info "Waiting for Web UI..."
    retries=30
    local web_port=3000
    [[ "$SSL_MODE" != "offload" ]] && web_port=443

    while ! curl -sfk "https://localhost:$web_port" &>/dev/null 2>&1 && \
          ! curl -sf "http://localhost:$web_port" &>/dev/null 2>&1; do
        ((retries--))
        if [[ $retries -le 0 ]]; then
            log_warning "Web UI may still be starting..."
            break
        fi
        sleep 1
    done
    log_success "Web UI ready"

    log_success "All containers started"
}


# ============================================================================
# SECTION 11: PLATFORM CONFIGURATION
# ============================================================================
#
# Configure the platform after containers are running:
#   - Admin password
#   - OAuth redirect URIs
#   - AI provider
#   - Embeddings
#   - Garage storage
#

configure_platform() {
    log_step "Configuring platform"

    local install_dir="${INSTALL_DIR:-$KG_INSTALL_DIR}"
    cd "$install_dir"

    local compose_cmd
    compose_cmd=$(build_compose_command)

    # Configure OAuth redirect URIs
    log_info "Configuring OAuth client redirect URIs..."
    local redirect_url
    if [[ "$SSL_MODE" == "offload" ]]; then
        redirect_url="http://${HOSTNAME}/callback"
    else
        redirect_url="https://${HOSTNAME}/callback"
    fi
    if $compose_cmd exec -T operator python /workspace/operator/configure.py oauth --redirect-uri "$redirect_url" 2>&1 | grep -qi "updated\|configured"; then
        log_success "OAuth configured for $redirect_url"
    else
        log_warning "Could not update OAuth redirect URIs"
    fi

    # Configure admin password
    log_info "Setting admin password..."
    if $compose_cmd exec -T operator python /workspace/operator/configure.py admin --password "$ADMIN_PASSWORD" 2>&1 | grep -qi "updated\|configured\|password"; then
        log_success "Admin user configured"
    else
        log_warning "Could not set admin password"
    fi

    # Configure AI provider (if not skipped)
    if [[ "$SKIP_AI" == "false" && -n "$AI_PROVIDER" ]]; then
        log_info "Configuring AI provider: $AI_PROVIDER"

        local model="${AI_MODEL:-gpt-4o}"
        $compose_cmd exec -T operator python /workspace/operator/configure.py ai-provider "$AI_PROVIDER" --model "$model" || true

        if [[ -n "$AI_KEY" ]]; then
            if $compose_cmd exec -T operator python /workspace/operator/configure.py api-key "$AI_PROVIDER" --key "$AI_KEY" 2>&1 | grep -qi "stored"; then
                log_success "AI provider configured: $AI_PROVIDER / $model"
            else
                log_warning "Could not store AI API key"
            fi
        fi
    fi

    # Configure embeddings (local by default)
    log_info "Configuring embeddings..."
    $compose_cmd exec -T operator python /workspace/operator/configure.py embedding 2 || true
    log_success "Local embedding configured (nomic-embed-text-v1.5)"

    # Configure Garage storage
    log_info "Configuring storage..."
    configure_garage "$compose_cmd"

    log_success "Platform configured"
}

configure_garage() {
    # Initialize Garage storage: assign node role, create bucket, store credentials
    local compose_cmd="$1"

    # Get Garage node ID
    local node_id
    node_id=$($compose_cmd exec -T garage /garage status 2>&1 | grep -oP '[a-f0-9]{16}' | head -1)

    if [[ -z "$node_id" ]]; then
        log_warning "Could not detect Garage node ID"
        return 1
    fi

    # Check if node already has a role
    local has_role
    has_role=$($compose_cmd exec -T garage /garage status 2>&1 | grep -c "NO ROLE ASSIGNED" || true)

    if [[ "$has_role" -gt 0 ]]; then
        # Assign role to node
        log_info "Assigning Garage node role..."
        $compose_cmd exec -T garage /garage layout assign -z dc1 -c 1G "$node_id" 2>/dev/null || true
        $compose_cmd exec -T garage /garage layout apply --version 1 2>/dev/null || true
    fi

    # Create bucket if it doesn't exist
    if ! $compose_cmd exec -T garage /garage bucket list 2>&1 | grep -q "kg-storage"; then
        log_info "Creating Garage bucket..."
        $compose_cmd exec -T garage /garage bucket create kg-storage 2>/dev/null || true
    fi

    # Delete existing key if present (to get fresh credentials)
    $compose_cmd exec -T garage /garage key delete kg-api-key --yes 2>/dev/null || true

    # Create API key and capture credentials
    log_info "Creating Garage API key..."
    local key_output garage_key_id garage_secret
    key_output=$($compose_cmd exec -T garage /garage key create kg-api-key 2>&1)
    garage_key_id=$(echo "$key_output" | grep "Key ID:" | awk '{print $3}')
    garage_secret=$(echo "$key_output" | grep "Secret key:" | awk '{print $3}')

    if [[ -n "$garage_key_id" && -n "$garage_secret" ]]; then
        # Grant bucket permissions
        $compose_cmd exec -T garage /garage bucket allow --read --write --owner kg-storage --key kg-api-key 2>/dev/null || true

        # Store credentials in encrypted database
        local garage_credentials="${garage_key_id}:${garage_secret}"
        if $compose_cmd exec -T operator python /workspace/operator/configure.py api-key garage --key "$garage_credentials" 2>&1 | grep -qi "stored"; then
            log_success "Garage credentials stored"
        else
            log_warning "Failed to store Garage credentials - may need manual configuration"
        fi
    else
        log_warning "Failed to create Garage API key"
    fi
}


# ============================================================================
# SECTION 12: COMPLETION
# ============================================================================
#
# Show installation summary and next steps.
#

show_completion() {
    local install_dir="${INSTALL_DIR:-$KG_INSTALL_DIR}"

    # Determine URLs
    local web_url api_url
    if [[ "$SSL_MODE" == "offload" ]]; then
        web_url="http://${HOSTNAME}:3000"
        api_url="http://${HOSTNAME}:8000"
    else
        if [[ "$MACVLAN_ENABLED" == "true" && -n "$MACVLAN_IP" ]]; then
            web_url="https://${HOSTNAME}"
            api_url="https://${HOSTNAME}/api"
        else
            web_url="https://${HOSTNAME}"
            api_url="https://${HOSTNAME}/api"
        fi
    fi

    echo
    echo -e "${GREEN}============================================================================${NC}"
    echo -e "${GREEN}${BOLD}  Knowledge Graph Platform Installed Successfully!${NC}"
    echo -e "${GREEN}============================================================================${NC}"
    echo
    echo -e "  ${BOLD}Web UI:${NC}      ${web_url}"
    echo -e "  ${BOLD}API:${NC}         ${api_url}"
    echo -e "  ${BOLD}API Docs:${NC}    ${api_url}/docs"
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
            echo -e "  ${BOLD}IP:${NC}          ${MACVLAN_IP}"
        fi
    fi

    echo
    echo -e "${YELLOW}Save these credentials - they won't be shown again!${NC}"
    echo
    echo -e "${BOLD}Next Steps:${NC}"
    echo "  1. Open ${web_url} in your browser"
    echo "  2. Log in with admin credentials above"

    if [[ "$SKIP_AI" == "true" ]]; then
        echo "  3. Configure AI provider: cd $install_dir && ./operator.sh shell"
    else
        echo "  3. Upload a document to start building your knowledge graph"
    fi

    echo
    echo -e "${BOLD}Management:${NC}"
    echo "  cd $install_dir"
    echo "  ./operator.sh status    # Check container status"
    echo "  ./operator.sh logs api  # View API logs"
    echo "  ./operator.sh shell     # Configuration shell"
    echo "  ./operator.sh --help    # All commands"
    echo
}


# ============================================================================
# SECTION 13: MAIN
# ============================================================================
#
# Main entry point - orchestrates the installation flow.
#

main() {
    # Display header with version
    echo
    echo -e "${BOLD}${BLUE}Knowledge Graph Platform Installer${NC}"
    echo -e "${GRAY}Version: 0.6.0-dev.14${NC}"
    echo

    # Don't run as root - we'll use sudo when needed
    if [[ $EUID -eq 0 ]]; then
        echo -e "${RED}ERROR: Do not run this script with sudo${NC}"
        echo
        echo "Run as your normal user:"
        echo "  ./install.sh"
        echo
        echo "The installer will prompt for sudo when needed."
        exit 1
    fi

    # Acquire sudo token early (keeps it alive during install)
    echo -e "${YELLOW}This installer requires sudo for some operations.${NC}"
    if ! sudo_ensure; then
        exit 1
    fi
    # Keep sudo alive in background (refresh every 30s, well within typical 5min timeout)
    (while true; do sudo -n true; sleep 30; kill -0 "$$" 2>/dev/null || exit; done) &
    SUDO_KEEPER_PID=$!
    trap "kill $SUDO_KEEPER_PID 2>/dev/null" EXIT

    # Parse command-line flags
    parse_flags "$@"

    # Run interactive setup if no flags provided
    if [[ "$INTERACTIVE" == "true" ]]; then
        run_interactive_setup
    fi

    # Validate configuration
    if ! validate_config; then
        exit 1
    fi

    # Check prerequisites
    check_prerequisites
    check_docker

    # Setup macvlan if enabled (before downloading files)
    if [[ "$MACVLAN_ENABLED" == "true" || "$MACVLAN_DELETE" == "true" ]]; then
        setup_macvlan
    fi

    # Exit if we were just deleting macvlan
    if [[ "$MACVLAN_DELETE" == "true" && "$MACVLAN_CREATE" == "false" ]]; then
        log_success "Macvlan network deleted"
        exit 0
    fi

    # Download files
    download_files

    # Generate secrets
    generate_secrets

    # Setup SSL
    setup_ssl

    # Start containers
    start_containers

    # Configure platform
    configure_platform

    # Show completion message
    show_completion

    # Drop sudo credentials (cleanup)
    sudo -k
}

# Run main with all arguments
main "$@"
