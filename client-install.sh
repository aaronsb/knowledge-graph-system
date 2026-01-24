#!/bin/bash
# ============================================================================
# Knowledge Graph Client Installer
# ============================================================================
CLIENT_INSTALLER_VERSION="0.1.0"
# ============================================================================
#
# Installs and configures Knowledge Graph client tools:
#   - kg CLI (npm package @aaronsb/kg-cli)
#   - kg-mcp-server (included with CLI, for AI assistants)
#   - kg-fuse (PyPI package, FUSE filesystem driver)
#
# ARCHITECTURE OVERVIEW:
# ----------------------
# This script follows a "configuration-first" pattern (same as install.sh):
#
#   1. CONFIGURATION    - All options defined as variables (single source of truth)
#   2. UTILITIES        - Logging, prompts, validation helpers
#   3. DETECTION        - Detect OS, package manager, existing installs
#   4. VERIFICATION     - Test API, check installs work
#   5. INSTALLATION     - Install packages, configure OAuth
#   6. MAIN             - Orchestrates the flow
#
# USAGE:
# ------
#   Interactive:  curl -fsSL https://raw.githubusercontent.com/aaronsb/knowledge-graph-system/main/client-install.sh | bash
#   Headless:     curl -fsSL https://raw.githubusercontent.com/aaronsb/knowledge-graph-system/main/client-install.sh | bash -s -- --api-url X ...
#   Upgrade:      ./client-install.sh --upgrade
#   Uninstall:    ./client-install.sh --uninstall
#   Status:       ./client-install.sh --status
#   Help:         ./client-install.sh --help
#
# ============================================================================

set -e  # Exit on error

# ============================================================================
# SECTION 1: CONFIGURATION VARIABLES
# ============================================================================
#
# All configurable options are defined here. This is the single source of truth.
# Both flag parsing and interactive prompts set these same variables.
#
# Naming convention:
#   - UPPERCASE for config that can be set by user
#   - lowercase for internal/derived values
#

# --- Platform Connection ---
API_URL=""                          # Platform API URL (e.g., https://kg.example.com/api)
USERNAME=""                         # Admin username for authentication
PASSWORD=""                         # Admin password (prompted, never saved to config)

# --- Component Selection ---
INSTALL_CLI=true                    # kg CLI (required, always true)
INSTALL_MCP=true                    # MCP server OAuth client
INSTALL_FUSE=false                  # FUSE driver (optional, needs fuse3)

# --- FUSE Options ---
FUSE_MOUNT_DIR=""                   # Mount directory (default: ~/Knowledge)
FUSE_AUTOSTART=false                # Configure autostart on login

# --- Mode ---
MODE="install"                      # install, upgrade, uninstall, status
INTERACTIVE=false                   # Running in interactive mode (vs headless)
SAVE_CONFIG=false                   # Save config after installation

# --- Config File (XDG-compliant) ---
# Linux: ~/.config/kg/client-install.conf
# macOS: ~/Library/Application Support/kg/client-install.conf
if [[ "$OSTYPE" == "darwin"* ]]; then
    CONFIG_DIR="$HOME/Library/Application Support/kg"
else
    CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/kg"
fi
CONFIG_FILE="$CONFIG_DIR/client-install.conf"
CONFIG_VERSION=""                   # Version from loaded config

# --- Detected Values (populated by detection functions) ---
DETECTED_OS=""                      # linux-arch, linux-ubuntu, linux-fedora, macos
DETECTED_PKG_MGR=""                 # pacman, apt, dnf, brew
DETECTED_NODE_VERSION=""            # Node.js version or empty
DETECTED_PYTHON_VERSION=""          # Python version or empty
DETECTED_PIPX=""                    # true/false
DETECTED_DESKTOP=""                 # kde, gnome, macos, unknown
DETECTED_KG_VERSION=""              # Existing kg CLI version or empty
DETECTED_FUSE_VERSION=""            # Existing kg-fuse version or empty

# --- Package Names ---
# These are the package identifiers used for installation.
# Change these if you fork the project or use a private registry.
NPM_PACKAGE="@aaronsb/kg-cli"           # npm package name for kg CLI
PYPI_PACKAGE="kg-fuse"                  # PyPI package name for FUSE driver

# --- External URLs ---
# URLs for downloading dependencies and documentation.
# Change these if you need to use mirrors or internal repositories.
KG_REPO_RAW="https://raw.githubusercontent.com/aaronsb/knowledge-graph-system/main"
NODESOURCE_SETUP_URL="https://deb.nodesource.com/setup_lts.x"
NODEJS_DOWNLOAD_URL="https://nodejs.org/"
MACFUSE_DOWNLOAD_URL="https://osxfuse.github.io"


# ============================================================================
# SECTION 2: UTILITY FUNCTIONS
# ============================================================================
#
# Helper functions used throughout the script:
#   - Logging (colored output)
#   - User prompts (for interactive mode)
#   - Config save/load
#

# --- Terminal Colors ---
# Disable colors if not running in a terminal (e.g., piped to file)
if [ -t 1 ]; then
    RED=$'\033[0;31m'
    GREEN=$'\033[0;32m'
    YELLOW=$'\033[1;33m'
    BLUE=$'\033[0;34m'
    CYAN=$'\033[0;36m'
    GRAY=$'\033[0;90m'
    BOLD=$'\033[1m'
    NC=$'\033[0m'  # No Color
else
    RED='' GREEN='' YELLOW='' BLUE='' CYAN='' GRAY='' BOLD='' NC=''
fi

# --- Logging Functions ---
# These write to stderr so they display even when stdout is captured

log_info() {
    # Informational message
    echo -e "${BLUE}ℹ${NC} $1" >&2
}

log_success() {
    # Success message (checkmark)
    echo -e "${GREEN}✓${NC} $1" >&2
}

log_warning() {
    # Warning message
    echo -e "${YELLOW}⚠${NC} $1" >&2
}

log_error() {
    # Error message
    echo -e "${RED}✗${NC} $1" >&2
}

log_step() {
    # Major step header - used to mark beginning of a phase
    echo -e "\n${BOLD}${BLUE}==>${NC} ${BOLD}$1${NC}" >&2
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

prompt_bool() {
    # Prompt for yes/no answer
    # Usage: if prompt_bool "Enable feature?" "n"; then ...
    # Second arg is default: "y" or "n" (defaults to "n")
    local prompt="$1"
    local default="${2:-n}"
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

prompt_with_fallback() {
    # Three-tier prompt: previous config → auto-detect → custom entry
    # Usage: result=$(prompt_with_fallback "Prompt text" "$PREVIOUS_VAR" "$auto_detected")
    #
    # Behavior:
    #   - If previous exists: shows "(previous)" hint and uses it as default
    #   - If no previous: uses auto-detected as default with "(detected)" hint
    #   - User presses Enter to accept shown default, or types to override
    local prompt="$1"
    local previous="$2"
    local detected="$3"

    local default=""
    local hint=""

    if [[ -n "$previous" ]]; then
        default="$previous"
        hint="${GRAY}(previous)${NC}"
    elif [[ -n "$detected" ]]; then
        default="$detected"
        hint="${GRAY}(detected)${NC}"
    fi

    if [[ -n "$default" ]]; then
        echo -ne "${CYAN}?${NC} ${prompt} ${hint}\n   [${default}]: " >&2
    else
        echo -ne "${CYAN}?${NC} ${prompt}: " >&2
    fi

    local value
    read -r value </dev/tty
    echo "${value:-$default}"
}

# --- Config Save/Load ---
# Saves user choices to XDG-compliant config file for future upgrades

get_installer_version() {
    # Return the installer version
    echo "$CLIENT_INSTALLER_VERSION"
}

save_config() {
    # Save current configuration to config file
    # Note: PASSWORD is intentionally NOT saved for security
    local version
    version=$(get_installer_version)

    mkdir -p "$CONFIG_DIR"
    chmod 700 "$CONFIG_DIR"

    cat > "$CONFIG_FILE" << EOF
# Knowledge Graph Client Installer Configuration
# Generated by client-install.sh $version on $(date -Iseconds)
# This file can be used with: client-install.sh --config "$CONFIG_FILE"

CLIENT_INSTALLER_VERSION="$version"

# --- Platform Connection ---
API_URL="$API_URL"
USERNAME="$USERNAME"
# Note: PASSWORD is NOT saved for security - enter during install

# --- Component Selection ---
INSTALL_MCP="$INSTALL_MCP"
INSTALL_FUSE="$INSTALL_FUSE"

# --- FUSE Options ---
FUSE_MOUNT_DIR="$FUSE_MOUNT_DIR"
FUSE_AUTOSTART="$FUSE_AUTOSTART"
EOF

    chmod 600 "$CONFIG_FILE"
    log_info "Configuration saved to $CONFIG_FILE"
}

load_config() {
    # Load configuration from config file
    # Returns 0 if loaded, 1 if file not found
    local config_path="${1:-$CONFIG_FILE}"

    if [[ ! -f "$config_path" ]]; then
        return 1
    fi

    # Source the config file (it's shell variables)
    # shellcheck disable=SC1090
    source "$config_path"

    # Store the version from config for compatibility check
    CONFIG_VERSION="${CLIENT_INSTALLER_VERSION:-unknown}"

    return 0
}

show_config_summary() {
    # Display loaded config for user confirmation
    echo -e "${BOLD}Previous configuration found:${NC}"
    echo -e "  ${BOLD}Version:${NC}    $CONFIG_VERSION"
    echo -e "  ${BOLD}API URL:${NC}    ${API_URL:-not set}"
    echo -e "  ${BOLD}Username:${NC}   ${USERNAME:-not set}"
    echo -e "  ${BOLD}MCP:${NC}        ${INSTALL_MCP:-true}"
    echo -e "  ${BOLD}FUSE:${NC}       ${INSTALL_FUSE:-false}"
    [[ "$INSTALL_FUSE" == "true" ]] && echo -e "  ${BOLD}Mount Dir:${NC}  ${FUSE_MOUNT_DIR:-~/Knowledge}"
    echo
}


# ============================================================================
# SECTION 3: DETECTION FUNCTIONS
# ============================================================================
#
# Functions to detect the current environment:
#   - Operating system and package manager
#   - Installed prerequisites (Node.js, Python, pipx)
#   - Existing kg CLI and kg-fuse installations
#   - Desktop environment (for autostart configuration)
#

detect_os() {
    # Detect operating system
    # Sets: DETECTED_OS (linux-arch, linux-ubuntu, linux-fedora, macos)

    if [[ "$OSTYPE" == "darwin"* ]]; then
        DETECTED_OS="macos"
    elif [[ -f /etc/arch-release ]]; then
        DETECTED_OS="linux-arch"
    elif [[ -f /etc/debian_version ]]; then
        DETECTED_OS="linux-ubuntu"
    elif [[ -f /etc/fedora-release ]]; then
        DETECTED_OS="linux-fedora"
    elif [[ -f /etc/redhat-release ]]; then
        DETECTED_OS="linux-fedora"  # RHEL-compatible
    else
        DETECTED_OS="linux-unknown"
    fi
}

detect_package_manager() {
    # Detect package manager based on OS
    # Sets: DETECTED_PKG_MGR (pacman, apt, dnf, brew)

    case "$DETECTED_OS" in
        macos)
            if command -v brew &>/dev/null; then
                DETECTED_PKG_MGR="brew"
            else
                DETECTED_PKG_MGR=""
            fi
            ;;
        linux-arch)
            DETECTED_PKG_MGR="pacman"
            ;;
        linux-ubuntu)
            DETECTED_PKG_MGR="apt"
            ;;
        linux-fedora)
            DETECTED_PKG_MGR="dnf"
            ;;
        *)
            DETECTED_PKG_MGR=""
            ;;
    esac
}

detect_node() {
    # Detect Node.js installation
    # Sets: DETECTED_NODE_VERSION (version string or empty)

    if command -v node &>/dev/null; then
        DETECTED_NODE_VERSION=$(node --version 2>/dev/null | sed 's/^v//')
    else
        DETECTED_NODE_VERSION=""
    fi
}

detect_python() {
    # Detect Python installation (3.11+ required for kg-fuse)
    # Sets: DETECTED_PYTHON_VERSION (version string or empty)

    if command -v python3 &>/dev/null; then
        DETECTED_PYTHON_VERSION=$(python3 --version 2>/dev/null | sed 's/Python //')
    else
        DETECTED_PYTHON_VERSION=""
    fi
}

detect_pipx() {
    # Detect pipx installation
    # Sets: DETECTED_PIPX (true/false)

    if command -v pipx &>/dev/null; then
        DETECTED_PIPX="true"
    else
        DETECTED_PIPX="false"
    fi
}

detect_existing_install() {
    # Detect existing kg CLI and kg-fuse installations
    # Sets: DETECTED_KG_VERSION, DETECTED_FUSE_VERSION

    # Check kg CLI
    if command -v kg &>/dev/null; then
        # kg --version returns something like "0.6.5" or "v0.6.5"
        DETECTED_KG_VERSION=$(kg --version 2>/dev/null | sed 's/^v//' | head -1)
    else
        DETECTED_KG_VERSION=""
    fi

    # Check kg-fuse
    if command -v kg-fuse &>/dev/null; then
        # Try to get version from pipx or just mark as installed
        DETECTED_FUSE_VERSION=$(pipx list 2>/dev/null | grep -oP "${PYPI_PACKAGE} \\K[0-9.]+" || echo "installed")
    else
        DETECTED_FUSE_VERSION=""
    fi
}

detect_desktop_environment() {
    # Detect desktop environment for autostart configuration
    # Sets: DETECTED_DESKTOP (kde, gnome, macos, unknown)

    if [[ "$DETECTED_OS" == "macos" ]]; then
        DETECTED_DESKTOP="macos"
    elif [[ "$XDG_CURRENT_DESKTOP" == *"KDE"* ]]; then
        DETECTED_DESKTOP="kde"
    elif [[ "$XDG_CURRENT_DESKTOP" == *"GNOME"* ]]; then
        DETECTED_DESKTOP="gnome"
    elif [[ "$XDG_CURRENT_DESKTOP" == *"XFCE"* ]]; then
        DETECTED_DESKTOP="xfce"
    else
        DETECTED_DESKTOP="unknown"
    fi
}

run_all_detection() {
    # Run all detection functions and display results
    log_step "Detecting environment"

    detect_os
    detect_package_manager
    detect_node
    detect_python
    detect_pipx
    detect_existing_install
    detect_desktop_environment

    # Display results
    echo -e "  OS: ${BOLD}${DETECTED_OS}${NC} (${DETECTED_PKG_MGR:-no package manager})" >&2

    if [[ -n "$DETECTED_NODE_VERSION" ]]; then
        echo -e "  Node.js: ${GREEN}v${DETECTED_NODE_VERSION}${NC} ✓" >&2
    else
        echo -e "  Node.js: ${YELLOW}not found${NC}" >&2
    fi

    if [[ -n "$DETECTED_PYTHON_VERSION" ]]; then
        echo -e "  Python: ${GREEN}${DETECTED_PYTHON_VERSION}${NC} ✓" >&2
    else
        echo -e "  Python: ${YELLOW}not found${NC}" >&2
    fi

    if [[ "$DETECTED_PIPX" == "true" ]]; then
        echo -e "  pipx: ${GREEN}installed${NC} ✓" >&2
    else
        echo -e "  pipx: ${YELLOW}not found${NC}" >&2
    fi

    echo -e "  Desktop: ${BOLD}${DETECTED_DESKTOP}${NC}" >&2

    # Show existing installations
    if [[ -n "$DETECTED_KG_VERSION" || -n "$DETECTED_FUSE_VERSION" ]]; then
        echo "" >&2
        echo -e "  ${BOLD}Existing installation:${NC}" >&2
        [[ -n "$DETECTED_KG_VERSION" ]] && echo -e "    kg CLI: v${DETECTED_KG_VERSION}" >&2
        [[ -n "$DETECTED_FUSE_VERSION" ]] && echo -e "    kg-fuse: v${DETECTED_FUSE_VERSION}" >&2
    fi
}


# ============================================================================
# SECTION 4: VERIFICATION FUNCTIONS
# ============================================================================
#
# Functions to verify each step succeeded:
#   - API is reachable
#   - CLI is installed and working
#   - Authentication succeeded
#   - FUSE is installed and working
#

verify_api_reachable() {
    # Test if the API URL is reachable
    # Args: $1 = API URL
    # Returns: 0 if reachable, 1 if not
    local url="$1"

    # Try the health endpoint
    if curl -sf "${url}/health" --max-time 10 &>/dev/null; then
        return 0
    fi

    # Try the base URL (might redirect or return API info)
    if curl -sf "${url}" --max-time 10 &>/dev/null; then
        return 0
    fi

    return 1
}

verify_cli_installed() {
    # Verify kg CLI is installed and working
    # Returns: 0 if working, 1 if not

    if ! command -v kg &>/dev/null; then
        return 1
    fi

    # Try running a simple command
    if kg --version &>/dev/null; then
        return 0
    fi

    return 1
}

verify_logged_in() {
    # Verify we're logged in and can reach the platform
    # Returns: 0 if healthy, 1 if not

    if kg health &>/dev/null; then
        return 0
    fi

    return 1
}

verify_fuse_installed() {
    # Verify kg-fuse is installed and working
    # Returns: 0 if working, 1 if not

    if ! command -v kg-fuse &>/dev/null; then
        return 1
    fi

    # Try running help
    if kg-fuse --help &>/dev/null; then
        return 0
    fi

    return 1
}


# ============================================================================
# SECTION 5: INSTALLATION FUNCTIONS
# ============================================================================
#
# Functions to install components:
#   - Prerequisites (Node.js, Python, pipx, fuse3)
#   - kg CLI (via npm)
#   - kg-fuse (via pipx)
#   - OAuth clients (via kg CLI)
#   - Autostart configuration
#

# --- Prerequisite Installation ---
# These functions install system packages needed by the clients.
# Each handles package manager differences across platforms.

install_node() {
    # Install Node.js via package manager
    # Node.js 18+ required for kg CLI
    log_info "Installing Node.js..."

    case "$DETECTED_PKG_MGR" in
        pacman)
            # Arch Linux: nodejs package includes npm
            sudo pacman -S --noconfirm nodejs npm
            ;;
        apt)
            # Ubuntu/Debian: Use NodeSource for recent versions
            # nodejs package from default repos is often outdated
            log_info "Setting up NodeSource repository for recent Node.js..."
            curl -fsSL "$NODESOURCE_SETUP_URL" | sudo -E bash -
            sudo apt-get install -y nodejs
            ;;
        dnf)
            # Fedora: nodejs package is reasonably recent
            sudo dnf install -y nodejs npm
            ;;
        brew)
            # macOS: Homebrew
            brew install node
            ;;
        *)
            log_error "No supported package manager found"
            log_info "Please install Node.js 18+ manually: $NODEJS_DOWNLOAD_URL"
            return 1
            ;;
    esac

    # Verify installation
    if command -v node &>/dev/null; then
        local version
        version=$(node --version)
        log_success "Node.js $version installed"
        return 0
    else
        log_error "Node.js installation failed"
        return 1
    fi
}

install_pipx() {
    # Install pipx via package manager
    # pipx is used for isolated Python package installation
    log_info "Installing pipx..."

    case "$DETECTED_PKG_MGR" in
        pacman)
            sudo pacman -S --noconfirm python-pipx
            ;;
        apt)
            sudo apt-get install -y pipx
            ;;
        dnf)
            sudo dnf install -y pipx
            ;;
        brew)
            brew install pipx
            ;;
        *)
            # Fallback: install via pip
            log_info "Installing pipx via pip..."
            python3 -m pip install --user pipx
            python3 -m pipx ensurepath
            ;;
    esac

    # Ensure pipx paths are configured
    pipx ensurepath 2>/dev/null || true

    # Verify installation
    if command -v pipx &>/dev/null; then
        log_success "pipx installed"
        return 0
    else
        log_error "pipx installation failed"
        return 1
    fi
}

install_fuse_system_package() {
    # Install FUSE system libraries
    # Linux needs fuse3, macOS needs macFUSE
    log_info "Installing FUSE system package..."

    case "$DETECTED_OS" in
        linux-arch)
            sudo pacman -S --noconfirm fuse3
            ;;
        linux-ubuntu)
            sudo apt-get install -y fuse3
            ;;
        linux-fedora)
            sudo dnf install -y fuse3
            ;;
        macos)
            # macFUSE requires manual installation or Homebrew Cask
            if command -v brew &>/dev/null; then
                brew install --cask macfuse
            else
                log_error "macFUSE requires Homebrew or manual installation"
                log_info "Install Homebrew: https://brew.sh"
                log_info "Or install macFUSE: $MACFUSE_DOWNLOAD_URL"
                return 1
            fi
            ;;
        *)
            log_error "Cannot install FUSE on unknown platform"
            return 1
            ;;
    esac

    log_success "FUSE system package installed"
    return 0
}

# --- Client Installation ---
# These functions install the kg CLI and kg-fuse packages.

install_cli() {
    # Install kg CLI via npm
    # Installs globally to ~/.local prefix for user-space installation
    log_info "Installing kg CLI..."

    local npm_prefix="$HOME/.local"

    # Ensure npm prefix directory exists
    mkdir -p "$npm_prefix/lib" "$npm_prefix/bin"

    # Install the package globally with user prefix
    if npm install --prefix "$npm_prefix" -g "$NPM_PACKAGE"; then
        log_success "kg CLI installed"

        # Ensure ~/.local/bin is in PATH (for current session)
        if [[ ":$PATH:" != *":$npm_prefix/bin:"* ]]; then
            export PATH="$npm_prefix/bin:$PATH"
            log_info "Added $npm_prefix/bin to PATH for this session"
            log_info "Add to your shell profile for persistence:"
            log_info "  export PATH=\"\$HOME/.local/bin:\$PATH\""
        fi
        return 0
    else
        log_error "Failed to install kg CLI"
        return 1
    fi
}

upgrade_cli() {
    # Upgrade kg CLI to latest version
    log_info "Upgrading kg CLI..."

    local npm_prefix="$HOME/.local"

    if npm install --prefix "$npm_prefix" -g "${NPM_PACKAGE}@latest"; then
        local version
        version=$(kg --version 2>/dev/null || echo "unknown")
        log_success "kg CLI upgraded to v$version"
        return 0
    else
        log_error "Failed to upgrade kg CLI"
        return 1
    fi
}

uninstall_cli() {
    # Uninstall kg CLI
    log_info "Uninstalling kg CLI..."

    local npm_prefix="$HOME/.local"

    if npm uninstall --prefix "$npm_prefix" -g "$NPM_PACKAGE"; then
        log_success "kg CLI uninstalled"
        return 0
    else
        log_error "Failed to uninstall kg CLI"
        return 1
    fi
}

install_fuse() {
    # Install kg-fuse via pipx
    # pipx creates an isolated environment for the package
    log_info "Installing kg-fuse..."

    if pipx install "$PYPI_PACKAGE"; then
        log_success "kg-fuse installed"
        return 0
    else
        log_error "Failed to install kg-fuse"
        return 1
    fi
}

upgrade_fuse() {
    # Upgrade kg-fuse to latest version
    log_info "Upgrading kg-fuse..."

    if pipx upgrade "$PYPI_PACKAGE"; then
        log_success "kg-fuse upgraded"
        return 0
    else
        log_error "Failed to upgrade kg-fuse"
        return 1
    fi
}

uninstall_fuse() {
    # Uninstall kg-fuse
    log_info "Uninstalling kg-fuse..."

    if pipx uninstall "$PYPI_PACKAGE"; then
        log_success "kg-fuse uninstalled"
        return 0
    else
        log_error "Failed to uninstall kg-fuse"
        return 1
    fi
}

# --- Configuration Functions ---
# These configure the clients after installation.

configure_api_url() {
    # Configure kg CLI with API URL
    # Sets the API URL in kg's config file
    local url="$1"

    if [[ -z "$url" ]]; then
        log_error "API URL is required"
        return 1
    fi

    log_info "Configuring API URL: $url"

    if kg config set api_url "$url"; then
        log_success "API URL configured"
        return 0
    else
        log_error "Failed to configure API URL"
        return 1
    fi
}

authenticate() {
    # Authenticate with kg login
    # Creates a personal OAuth client for the CLI
    local username="$1"
    local password="$2"

    if [[ -z "$username" || -z "$password" ]]; then
        log_error "Username and password are required"
        return 1
    fi

    log_info "Authenticating as $username..."

    # Use non-interactive mode with password flag
    if kg login --username "$username" --password "$password" --remember-username; then
        log_success "Authentication successful"
        return 0
    else
        log_error "Authentication failed"
        return 1
    fi
}

create_mcp_oauth() {
    # Create OAuth client for MCP server
    # Uses: kg oauth create-mcp
    log_info "Creating MCP server OAuth client..."

    if kg oauth create-mcp; then
        log_success "MCP OAuth client created"
        return 0
    else
        log_error "Failed to create MCP OAuth client"
        return 1
    fi
}

create_fuse_oauth() {
    # Create OAuth client for FUSE driver
    # Uses: kg oauth create --for fuse
    log_info "Creating FUSE OAuth client..."

    if kg oauth create --for fuse; then
        log_success "FUSE OAuth client created"
        return 0
    else
        log_error "Failed to create FUSE OAuth client"
        return 1
    fi
}

# --- Autostart Configuration ---
# Configures FUSE to start automatically on login.

configure_fuse_autostart() {
    # Configure FUSE to start on login
    # Linux: Creates .desktop file in ~/.config/autostart/
    # macOS: Creates launchd plist in ~/Library/LaunchAgents/

    local mount_dir="${FUSE_MOUNT_DIR:-$HOME/Knowledge}"
    local config_dir
    local kg_fuse_path

    # Find kg-fuse binary
    kg_fuse_path=$(command -v kg-fuse)
    if [[ -z "$kg_fuse_path" ]]; then
        log_error "kg-fuse not found in PATH"
        return 1
    fi

    # Ensure mount directory exists
    mkdir -p "$mount_dir"

    case "$DETECTED_OS" in
        macos)
            # macOS: Create launchd plist
            config_dir="$HOME/Library/LaunchAgents"
            mkdir -p "$config_dir"

            cat > "$config_dir/com.kg.fuse.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.kg.fuse</string>
    <key>ProgramArguments</key>
    <array>
        <string>$kg_fuse_path</string>
        <string>$mount_dir</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>$HOME/Library/Logs/kg-fuse.log</string>
    <key>StandardErrorPath</key>
    <string>$HOME/Library/Logs/kg-fuse.log</string>
</dict>
</plist>
EOF
            log_success "Created launchd plist: $config_dir/com.kg.fuse.plist"
            log_info "To start now: launchctl load $config_dir/com.kg.fuse.plist"
            ;;

        linux-*)
            # Linux: Create .desktop file for XDG autostart
            config_dir="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
            mkdir -p "$config_dir"

            cat > "$config_dir/kg-fuse.desktop" << EOF
[Desktop Entry]
Type=Application
Name=Knowledge Graph FUSE
Comment=Mount knowledge graph as filesystem
Exec=$kg_fuse_path $mount_dir
Terminal=false
StartupNotify=false
X-GNOME-Autostart-enabled=true
EOF
            chmod 644 "$config_dir/kg-fuse.desktop"
            log_success "Created autostart entry: $config_dir/kg-fuse.desktop"
            ;;

        *)
            log_error "Autostart not supported on this platform"
            return 1
            ;;
    esac

    return 0
}

remove_fuse_autostart() {
    # Remove FUSE autostart configuration

    case "$DETECTED_OS" in
        macos)
            local plist="$HOME/Library/LaunchAgents/com.kg.fuse.plist"
            if [[ -f "$plist" ]]; then
                launchctl unload "$plist" 2>/dev/null || true
                rm -f "$plist"
                log_success "Removed launchd plist"
            fi
            ;;

        linux-*)
            local desktop="${XDG_CONFIG_HOME:-$HOME/.config}/autostart/kg-fuse.desktop"
            if [[ -f "$desktop" ]]; then
                rm -f "$desktop"
                log_success "Removed autostart entry"
            fi
            ;;
    esac

    return 0
}


# ============================================================================
# SECTION 6: MAIN FLOW
# ============================================================================
#
# Orchestrates the installation:
#   - Parse command-line flags
#   - Run detection
#   - Interactive prompts (if not headless)
#   - Execute installation steps
#   - Show summary
#

show_help() {
    cat << 'EOF'
Knowledge Graph Client Installer

USAGE:
    client-install.sh [OPTIONS]

MODES:
    (default)           Interactive installation
    --upgrade           Upgrade existing installation
    --uninstall         Uninstall clients
    --status            Show installation status
    --help              Show this help

OPTIONS:
    --api-url URL       Knowledge Graph API URL
    --username USER     Admin username
    --password PASS     Admin password

    --no-mcp            Skip MCP server configuration
    --install-fuse      Install FUSE driver
    --fuse-mount DIR    FUSE mount directory (default: ~/Knowledge)
    --fuse-autostart    Configure FUSE to start on login

    --config FILE       Load config from file
    --save-config       Save config after installation

EXAMPLES:
    # Interactive installation
    curl -fsSL https://raw.githubusercontent.com/aaronsb/knowledge-graph-system/main/client-install.sh | bash

    # Headless installation
    ./client-install.sh --api-url https://kg.example.com/api \
        --username admin --password secret

    # Install with FUSE
    ./client-install.sh --install-fuse --fuse-mount ~/Knowledge

    # Upgrade existing
    ./client-install.sh --upgrade
EOF
}

parse_flags() {
    # Parse command-line arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --help|-h)
                show_help
                exit 0
                ;;
            --upgrade)
                MODE="upgrade"
                shift
                ;;
            --uninstall)
                MODE="uninstall"
                shift
                ;;
            --status)
                MODE="status"
                shift
                ;;
            --api-url)
                API_URL="$2"
                shift 2
                ;;
            --username)
                USERNAME="$2"
                shift 2
                ;;
            --password)
                PASSWORD="$2"
                shift 2
                ;;
            --no-mcp)
                INSTALL_MCP=false
                shift
                ;;
            --install-fuse)
                INSTALL_FUSE=true
                shift
                ;;
            --fuse-mount)
                FUSE_MOUNT_DIR="$2"
                shift 2
                ;;
            --fuse-autostart)
                FUSE_AUTOSTART=true
                shift
                ;;
            --config)
                if ! load_config "$2"; then
                    log_error "Failed to load config: $2"
                    exit 1
                fi
                shift 2
                ;;
            --save-config)
                SAVE_CONFIG=true
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                echo "Run with --help for usage" >&2
                exit 1
                ;;
        esac
    done
}

show_banner() {
    # Display installer banner
    echo -e "${BOLD}"
    echo "┌─────────────────────────────────────────────────────────────┐"
    echo "│  Knowledge Graph Client Installer v${CLIENT_INSTALLER_VERSION}                      │"
    echo "└─────────────────────────────────────────────────────────────┘"
    echo -e "${NC}"
}

# --- Interactive Prompts ---
# Functions to collect installation options in interactive mode.

run_interactive_prompts() {
    # Collect installation options from user
    # Uses three-tier fallback: previous config → detected → manual entry

    echo "" >&2
    log_step "Configuration"

    # --- API URL ---
    # Try to auto-detect from existing kg config
    local detected_url=""
    if command -v kg &>/dev/null; then
        detected_url=$(kg config get api_url 2>/dev/null || true)
    fi

    API_URL=$(prompt_with_fallback "API URL (e.g., https://kg.example.com/api)" "$API_URL" "$detected_url")
    if [[ -z "$API_URL" ]]; then
        log_error "API URL is required"
        exit 1
    fi

    # Verify API is reachable
    echo -n "  Testing API connection... " >&2
    if verify_api_reachable "$API_URL"; then
        echo -e "${GREEN}OK${NC}" >&2
    else
        echo -e "${RED}FAILED${NC}" >&2
        log_warning "Could not reach API at $API_URL"
        if ! prompt_bool "Continue anyway?"; then
            exit 1
        fi
    fi

    # --- Username ---
    local detected_username=""
    if command -v kg &>/dev/null; then
        detected_username=$(kg config get username 2>/dev/null || true)
    fi

    USERNAME=$(prompt_with_fallback "Username" "$USERNAME" "$detected_username")
    if [[ -z "$USERNAME" ]]; then
        log_error "Username is required"
        exit 1
    fi

    # --- Password ---
    PASSWORD=$(prompt_password "Password")
    if [[ -z "$PASSWORD" ]]; then
        log_error "Password is required"
        exit 1
    fi

    # --- Component Selection ---
    echo "" >&2
    log_step "Components"

    # MCP server (default: yes)
    if prompt_bool "Configure MCP server for AI assistants?" "y"; then
        INSTALL_MCP=true
    else
        INSTALL_MCP=false
    fi

    # FUSE driver (default: no)
    if prompt_bool "Install FUSE driver to mount knowledge graph as filesystem?"; then
        INSTALL_FUSE=true

        # FUSE mount directory
        FUSE_MOUNT_DIR=$(prompt_with_fallback "FUSE mount directory" "$FUSE_MOUNT_DIR" "$HOME/Knowledge")

        # Autostart
        if prompt_bool "Start FUSE automatically on login?"; then
            FUSE_AUTOSTART=true
        fi
    fi

    # --- Save Config ---
    if prompt_bool "Save configuration for future upgrades?"; then
        SAVE_CONFIG=true
    fi
}

# --- Installation Flow ---
# Functions that perform the actual installation.

do_install_prerequisites() {
    # Install any missing prerequisites
    log_step "Prerequisites"

    # Node.js (required for kg CLI)
    if [[ -z "$DETECTED_NODE_VERSION" ]]; then
        log_info "Node.js not found"
        if [[ "$INTERACTIVE" == "true" ]]; then
            if prompt_bool "Install Node.js?"; then
                install_node || exit 1
            else
                log_error "Node.js is required for kg CLI"
                exit 1
            fi
        else
            install_node || exit 1
        fi
    else
        log_success "Node.js v$DETECTED_NODE_VERSION already installed"
    fi

    # pipx (required for kg-fuse if selected)
    if [[ "$INSTALL_FUSE" == "true" && "$DETECTED_PIPX" != "true" ]]; then
        log_info "pipx not found (required for kg-fuse)"
        if [[ "$INTERACTIVE" == "true" ]]; then
            if prompt_bool "Install pipx?"; then
                install_pipx || exit 1
            else
                log_error "pipx is required for kg-fuse"
                exit 1
            fi
        else
            install_pipx || exit 1
        fi
    elif [[ "$INSTALL_FUSE" == "true" ]]; then
        log_success "pipx already installed"
    fi

    # fuse3/macfuse (required for kg-fuse if selected)
    if [[ "$INSTALL_FUSE" == "true" ]]; then
        # Check if FUSE is available
        local fuse_available=false
        if [[ "$DETECTED_OS" == "macos" ]]; then
            # macOS: check for macFUSE
            if [[ -d "/Library/Filesystems/macfuse.fs" ]]; then
                fuse_available=true
            fi
        else
            # Linux: check for fuse3
            if command -v fusermount3 &>/dev/null || command -v fusermount &>/dev/null; then
                fuse_available=true
            fi
        fi

        if [[ "$fuse_available" == "false" ]]; then
            log_info "FUSE not found (required for kg-fuse)"
            if [[ "$INTERACTIVE" == "true" ]]; then
                if prompt_bool "Install FUSE?"; then
                    install_fuse_system_package || exit 1
                else
                    log_error "FUSE is required for kg-fuse"
                    exit 1
                fi
            else
                install_fuse_system_package || exit 1
            fi
        else
            log_success "FUSE already installed"
        fi
    fi
}

do_install_clients() {
    # Install the kg CLI and optionally kg-fuse
    log_step "Installing clients"

    # kg CLI
    if [[ -z "$DETECTED_KG_VERSION" ]]; then
        install_cli || exit 1
    else
        log_success "kg CLI v$DETECTED_KG_VERSION already installed"
    fi

    # kg-fuse
    if [[ "$INSTALL_FUSE" == "true" ]]; then
        if [[ -z "$DETECTED_FUSE_VERSION" ]]; then
            install_fuse || exit 1
        else
            log_success "kg-fuse v$DETECTED_FUSE_VERSION already installed"
        fi
    fi
}

do_configure() {
    # Configure clients and create OAuth credentials
    log_step "Configuration"

    # Set API URL
    configure_api_url "$API_URL" || exit 1

    # Authenticate
    authenticate "$USERNAME" "$PASSWORD" || exit 1

    # Create MCP OAuth client
    if [[ "$INSTALL_MCP" == "true" ]]; then
        create_mcp_oauth || log_warning "MCP OAuth creation failed (may already exist)"
    fi

    # Create FUSE OAuth client and configure autostart
    if [[ "$INSTALL_FUSE" == "true" ]]; then
        create_fuse_oauth || log_warning "FUSE OAuth creation failed (may already exist)"

        if [[ "$FUSE_AUTOSTART" == "true" ]]; then
            configure_fuse_autostart || log_warning "Autostart configuration failed"
        fi
    fi

    # Save config if requested
    if [[ "$SAVE_CONFIG" == "true" ]]; then
        save_config
    fi
}

show_summary() {
    # Display installation summary
    echo "" >&2
    log_step "Installation Complete"
    echo "" >&2

    echo -e "  ${BOLD}kg CLI${NC}" >&2
    echo -e "    Version: $(kg --version 2>/dev/null || echo 'unknown')" >&2
    echo -e "    API URL: $(kg config get api_url 2>/dev/null || echo 'unknown')" >&2
    echo "" >&2

    if [[ "$INSTALL_MCP" == "true" ]]; then
        echo -e "  ${BOLD}MCP Server${NC}" >&2
        echo -e "    Use kg mcp-config to configure AI assistants" >&2
        echo "" >&2
    fi

    if [[ "$INSTALL_FUSE" == "true" ]]; then
        echo -e "  ${BOLD}FUSE Driver${NC}" >&2
        echo -e "    Version: $(pipx list 2>/dev/null | grep -oP "${PYPI_PACKAGE} \\K[0-9.]+" || echo 'unknown')" >&2
        echo -e "    Mount: kg-fuse ${FUSE_MOUNT_DIR:-~/Knowledge}" >&2
        if [[ "$FUSE_AUTOSTART" == "true" ]]; then
            echo -e "    Autostart: enabled" >&2
        fi
        echo "" >&2
    fi

    echo -e "  ${BOLD}Next steps:${NC}" >&2
    echo -e "    • Run ${CYAN}kg health${NC} to verify connection" >&2
    echo -e "    • Run ${CYAN}kg search \"your query\"${NC} to search the knowledge graph" >&2
    if [[ "$INSTALL_MCP" == "true" ]]; then
        echo -e "    • Run ${CYAN}kg mcp-config${NC} to configure Claude or other AI assistants" >&2
    fi
    if [[ "$INSTALL_FUSE" == "true" ]]; then
        echo -e "    • Run ${CYAN}kg-fuse ${FUSE_MOUNT_DIR:-~/Knowledge}${NC} to mount the knowledge graph" >&2
    fi
    echo "" >&2
}

# --- Mode Handlers ---
# Functions that handle each mode (install, upgrade, uninstall, status).

do_install() {
    # Full installation flow

    # Interactive prompts if no API URL provided
    if [[ -z "$API_URL" ]]; then
        if [[ "$INTERACTIVE" == "true" ]]; then
            run_interactive_prompts
        else
            log_error "API URL is required in headless mode"
            log_info "Use: --api-url URL --username USER --password PASS"
            exit 1
        fi
    fi

    # Validate required options
    if [[ -z "$USERNAME" || -z "$PASSWORD" ]]; then
        if [[ "$INTERACTIVE" == "true" ]]; then
            run_interactive_prompts
        else
            log_error "Username and password are required"
            exit 1
        fi
    fi

    # Run installation steps
    do_install_prerequisites
    do_install_clients
    do_configure
    show_summary
}

do_upgrade() {
    # Upgrade existing installation
    log_step "Upgrading installation"

    # Check for existing installation
    if [[ -z "$DETECTED_KG_VERSION" && -z "$DETECTED_FUSE_VERSION" ]]; then
        log_error "No existing installation found"
        log_info "Run without --upgrade for fresh installation"
        exit 1
    fi

    # Upgrade kg CLI
    if [[ -n "$DETECTED_KG_VERSION" ]]; then
        upgrade_cli
    fi

    # Upgrade kg-fuse
    if [[ -n "$DETECTED_FUSE_VERSION" ]]; then
        upgrade_fuse
    fi

    log_success "Upgrade complete"
}

do_uninstall() {
    # Uninstall clients
    log_step "Uninstalling clients"

    # Confirm in interactive mode
    if [[ "$INTERACTIVE" == "true" ]]; then
        echo "" >&2
        echo -e "  ${BOLD}This will remove:${NC}" >&2
        [[ -n "$DETECTED_KG_VERSION" ]] && echo -e "    • kg CLI v$DETECTED_KG_VERSION" >&2
        [[ -n "$DETECTED_FUSE_VERSION" ]] && echo -e "    • kg-fuse v$DETECTED_FUSE_VERSION" >&2
        echo "" >&2

        if ! prompt_bool "Continue with uninstall?" "n"; then
            log_info "Uninstall cancelled"
            exit 0
        fi
    fi

    # Remove autostart configuration first
    remove_fuse_autostart

    # Uninstall kg-fuse
    if [[ -n "$DETECTED_FUSE_VERSION" ]]; then
        uninstall_fuse
    fi

    # Uninstall kg CLI
    if [[ -n "$DETECTED_KG_VERSION" ]]; then
        uninstall_cli
    fi

    log_success "Uninstall complete"
}

main() {
    # Main entry point
    parse_flags "$@"

    # Determine if running interactively
    # Check both stdin (tty) and if we have /dev/tty available
    if [ -t 0 ] || [ -e /dev/tty ]; then
        INTERACTIVE=true
    fi

    show_banner
    run_all_detection

    # Try to load existing config for upgrades
    if [[ -f "$CONFIG_FILE" ]]; then
        load_config
        if [[ "$MODE" == "install" && "$INTERACTIVE" == "true" ]]; then
            echo "" >&2
            show_config_summary
            if prompt_bool "Use previous configuration?"; then
                # Keep loaded values
                :
            else
                # Clear for fresh prompts
                API_URL=""
                USERNAME=""
            fi
        fi
    fi

    # Handle different modes
    case "$MODE" in
        status)
            # Just show detection results and exit
            exit 0
            ;;
        uninstall)
            do_uninstall
            ;;
        upgrade)
            do_upgrade
            ;;
        install)
            do_install
            ;;
    esac
}

# Run main with all arguments
main "$@"
