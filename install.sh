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
SSL_MODE="none"          # none, letsencrypt, acme-dns, manual
SSL_EMAIL=""             # Required for Let's Encrypt
SSL_CERT_PATH=""         # For manual SSL
SSL_KEY_PATH=""          # For manual SSL
SSL_DNS_PROVIDER=""      # For DNS-01 challenge (e.g., dns_porkbun, dns_cloudflare)
SSL_DNS_CREDENTIALS=""   # DNS API credentials

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
  --ssl MODE                SSL mode: none, letsencrypt, manual (default: none)
                            • none: HTTP only (port 3000)
                            • letsencrypt: Auto-generate certs via Let's Encrypt
                            • manual: Use existing certificates

  --ssl-email EMAIL         Email for Let's Encrypt registration (required for letsencrypt)

  --ssl-cert PATH           Path to SSL certificate file (required for manual)

  --ssl-key PATH            Path to SSL private key file (required for manual)

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

${BOLD}Requirements:${NC}
  - Linux (Ubuntu 20.04+ or Debian 11+ recommended)
  - Docker (will be installed if missing)
  - 4GB RAM minimum, 8GB recommended
  - 20GB disk space

${BOLD}After Installation:${NC}
  - Web UI: http://HOSTNAME:3000
  - API: http://HOSTNAME:8000
  - Default admin user: admin

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
        none|letsencrypt|manual) return 0 ;;
        *) return 1 ;;
    esac
}

# ============================================================================
# Argument Parsing (Strict Mode)
# ============================================================================
SKIP_AI=false
SHOW_HELP=false

parse_args() {
    # If any arguments provided, we're in headless mode
    if [[ $# -gt 0 ]]; then
        INTERACTIVE=false
    fi

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
                    add_validation_error "Invalid SSL mode: $SSL_MODE (must be: none, letsencrypt, manual)"
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
                        add_validation_error "Invalid SSL mode: $SSL_MODE (must be: none, letsencrypt, manual)"
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
            if [[ "$HOSTNAME" == "localhost" || "$HOSTNAME" =~ ^192\. || "$HOSTNAME" =~ ^10\. || "$HOSTNAME" =~ ^172\. ]]; then
                add_validation_error "Let's Encrypt requires a public domain name (not localhost or private IP)"
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
# SSL Setup
# ============================================================================
setup_ssl() {
    if [[ "$SSL_MODE" == "none" ]]; then
        log_info "SSL disabled - using HTTP only"
        return 0
    fi

    log_step "Setting up SSL"

    local install_dir="${INSTALL_DIR:-$KG_INSTALL_DIR}"
    local certs_dir="$install_dir/certs"
    mkdir -p "$certs_dir"

    if [[ "$SSL_MODE" == "letsencrypt" ]]; then
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

    # Install certbot if needed
    if ! command -v certbot &> /dev/null; then
        log_info "Installing certbot..."
        if command -v apt &> /dev/null; then
            sudo apt update && sudo apt install -y certbot
        elif command -v dnf &> /dev/null; then
            sudo dnf install -y certbot
        elif command -v snap &> /dev/null; then
            sudo snap install certbot --classic
        else
            log_error "Could not install certbot. Please install manually."
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

    log_info "Certificate auto-renewal configured"
}

generate_ssl_compose_overlay() {
    local install_dir="$1"

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
EOF

    log_info "Generated SSL compose overlay"
}

generate_nginx_ssl_config() {
    local install_dir="$1"

    cat > "$install_dir/nginx.ssl.conf" << EOF
# Nginx configuration for Knowledge Graph with SSL
# Auto-generated by install.sh

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name ${HOSTNAME};
    return 301 https://\$host\$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2;
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

    if [[ -n "$default" ]]; then
        read -rp "$(echo -e "${CYAN}?${NC} ${prompt} [${default}]: ")" value
        echo "${value:-$default}"
    else
        read -rp "$(echo -e "${CYAN}?${NC} ${prompt}: ")" value
        echo "$value"
    fi
}

prompt_password() {
    local prompt="$1"
    local value

    read -srp "$(echo -e "${CYAN}?${NC} ${prompt}: ")" value
    echo
    echo "$value"
}

prompt_select() {
    local prompt="$1"
    shift
    local options=("$@")
    local i=1

    echo -e "${CYAN}?${NC} ${prompt}"
    for opt in "${options[@]}"; do
        echo "  $i) $opt"
        ((i++))
    done

    local selection
    read -rp "  Select [1]: " selection
    selection=${selection:-1}

    if [[ "$selection" -ge 1 && "$selection" -le ${#options[@]} ]]; then
        echo "${options[$((selection-1))]}"
    else
        echo "${options[0]}"
    fi
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
                AI_KEY=$(prompt_password "OpenAI API key")
                ;;
            anthropic)
                AI_MODEL=$(prompt_value "Model name" "claude-sonnet-4")
                AI_KEY=$(prompt_password "Anthropic API key")
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
        "none (HTTP only)" "letsencrypt (auto-generate)" "manual (existing certs)")
    SSL_MODE="${SSL_MODE%% *}"  # Extract first word

    if [[ "$SSL_MODE" == "letsencrypt" ]]; then
        # Validate hostname for Let's Encrypt
        if [[ "$HOSTNAME" == "localhost" || "$HOSTNAME" =~ ^192\. || "$HOSTNAME" =~ ^10\. || "$HOSTNAME" =~ ^172\. ]]; then
            log_warning "Let's Encrypt requires a public domain name"
            log_info "Falling back to HTTP only"
            SSL_MODE="none"
        else
            SSL_EMAIL=$(prompt_value "Email for Let's Encrypt" "")
            if [[ -z "$SSL_EMAIL" ]]; then
                log_warning "Email required for Let's Encrypt. Falling back to HTTP only."
                SSL_MODE="none"
            fi
        fi
    elif [[ "$SSL_MODE" == "manual" ]]; then
        SSL_CERT_PATH=$(prompt_value "Path to SSL certificate (fullchain.pem)" "")
        SSL_KEY_PATH=$(prompt_value "Path to SSL private key (privkey.pem)" "")
        if [[ ! -f "$SSL_CERT_PATH" || ! -f "$SSL_KEY_PATH" ]]; then
            log_warning "Certificate files not found. Falling back to HTTP only."
            SSL_MODE="none"
        fi
    fi

    # Admin password
    echo
    echo -e "${YELLOW}Note:${NC} You can set admin password now or use the auto-generated one."
    local set_password
    read -rp "$(echo -e "${CYAN}?${NC} Set custom admin password? [y/N]: ")" set_password
    if [[ "$set_password" =~ ^[Yy] ]]; then
        ADMIN_PASSWORD=$(prompt_password "Admin password")
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

    # Files to download
    local files=(
        "docker/docker-compose.yml"
        "docker/docker-compose.prod.yml"
        "docker/docker-compose.ghcr.yml"
        "docker/docker-compose.gpu-nvidia.yml"
        "docker/docker-compose.gpu-amd.yml"
        ".env.example"
        "schema/00_baseline.sql"
    )

    # Download each file
    for file in "${files[@]}"; do
        local target_dir
        target_dir=$(dirname "$file")
        mkdir -p "$target_dir"

        log_info "Downloading $file..."
        if ! curl -fsSL "${KG_REPO_RAW}/${file}" -o "$file"; then
            log_error "Failed to download: $file"
            exit 1
        fi
    done

    # Download operator scripts
    mkdir -p operator/lib operator/database
    local operator_files=(
        "operator/configure.py"
        "operator/lib/common.sh"
        "operator/database/migrate-db.sh"
    )

    for file in "${operator_files[@]}"; do
        log_info "Downloading $file..."
        if ! curl -fsSL "${KG_REPO_RAW}/${file}" -o "$file"; then
            log_warning "Optional file not found: $file"
        fi
    done

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
    if [[ "$SSL_MODE" != "none" ]]; then
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
    if [[ "$SSL_MODE" != "none" && -f "docker-compose.ssl.yml" ]]; then
        cmd="$cmd -f docker-compose.ssl.yml"
    fi

    echo "$cmd"
}

start_containers() {
    log_step "Starting containers"

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

    local compose_cmd
    compose_cmd=$(build_compose_command)

    # Create admin user
    log_info "Creating admin user..."
    $compose_cmd exec -T operator python /workspace/operator/configure.py admin --password "$ADMIN_PASSWORD" || true

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
    if [[ "$SSL_MODE" != "none" ]]; then
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
    if [[ "$SSL_MODE" != "none" ]]; then
        echo -e "  ${BOLD}SSL:${NC}         ${SSL_MODE}"
    fi
    echo
    echo -e "${YELLOW}Save these credentials - they won't be shown again!${NC}"
    echo
    echo -e "${BOLD}Next Steps:${NC}"
    echo "  1. Open ${web_url} in your browser"
    echo "  2. Log in with admin credentials above"
    if [[ "$SKIP_AI" == "true" ]]; then
        echo "  3. Configure AI provider in Settings > AI Configuration"
    fi
    echo
    echo -e "${BOLD}Useful Commands:${NC}"
    echo "  cd ${install_dir}"
    echo "  docker compose logs -f          # View logs"
    echo "  docker compose ps               # Container status"
    echo "  docker compose down             # Stop platform"
    echo "  docker compose up -d            # Start platform"
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
    fi

    # Set default install directory
    INSTALL_DIR="${INSTALL_DIR:-$KG_INSTALL_DIR}"

    # Execute installation
    check_prerequisites
    install_docker
    download_files
    generate_secrets
    setup_ssl
    start_containers
    configure_platform
    show_completion
}

main "$@"
