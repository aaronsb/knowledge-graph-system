#!/bin/bash
# ============================================================================
# Knowledge Graph Client Manager
# ============================================================================
CLIENT_MANAGER_VERSION="0.6.6"
# ============================================================================
#
# Manages Knowledge Graph client tools across platforms:
#   - kg CLI (npm package @aaronsb/kg-cli)
#   - kg-mcp-server (included with CLI, for AI assistants)
#   - kg-fuse (PyPI package, FUSE filesystem driver)
#
# ARCHITECTURE OVERVIEW:
# ----------------------
# This script separates platform-specific logic into clean adapter modules:
#
#   ┌─────────────────────────────────────────────────────────────────┐
#   │                     CONFIGURATION                                │
#   │  (Variables, URLs, package names - single source of truth)      │
#   ├─────────────────────────────────────────────────────────────────┤
#   │                     UTILITIES                                    │
#   │  (Logging, prompts, config save/load)                           │
#   ├─────────────────────────────────────────────────────────────────┤
#   │                 PACKAGE MANAGER ADAPTERS                         │
#   │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
#   │  │  pacman  │ │   apt    │ │   dnf    │ │   brew   │           │
#   │  ├──────────┤ ├──────────┤ ├──────────┤ ├──────────┤           │
#   │  │ _node()  │ │ _node()  │ │ _node()  │ │ _node()  │           │
#   │  │ _pipx()  │ │ _pipx()  │ │ _pipx()  │ │ _pipx()  │           │
#   │  │ _fuse()  │ │ _fuse()  │ │ _fuse()  │ │ _fuse()  │           │
#   │  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
#   ├─────────────────────────────────────────────────────────────────┤
#   │                 PLATFORM FAMILY ADAPTERS                         │
#   │  ┌─────────────────────────┐ ┌─────────────────────────┐        │
#   │  │         linux           │ │         macos           │        │
#   │  ├─────────────────────────┤ ├─────────────────────────┤        │
#   │  │ _stop_fuse()            │ │ _stop_fuse()            │        │
#   │  │ _start_fuse()           │ │ _start_fuse()           │        │
#   │  │ _configure_autostart()  │ │ _configure_autostart()  │        │
#   │  │ _remove_autostart()     │ │ _remove_autostart()     │        │
#   │  │ _get_config_dir()       │ │ _get_config_dir()       │        │
#   │  └─────────────────────────┘ └─────────────────────────┘        │
#   ├─────────────────────────────────────────────────────────────────┤
#   │                     DISPATCH LAYER                               │
#   │  install_node()      → ${PKG_MGR}_install_node                  │
#   │  install_pipx()      → ${PKG_MGR}_install_pipx                  │
#   │  stop_fuse()         → ${PLATFORM}_stop_fuse                    │
#   │  start_fuse()        → ${PLATFORM}_start_fuse                   │
#   │  configure_autostart → ${PLATFORM}_configure_autostart          │
#   ├─────────────────────────────────────────────────────────────────┤
#   │                     DETECTION & VERIFICATION                     │
#   │  (OS detection, existing install detection, API verification)   │
#   ├─────────────────────────────────────────────────────────────────┤
#   │                     INSTALLATION LOGIC                           │
#   │  (Prerequisites, clients, OAuth - uses dispatch layer)          │
#   ├─────────────────────────────────────────────────────────────────┤
#   │                     MAIN FLOW                                    │
#   │  (Argument parsing, lifecycle menu, mode handlers)              │
#   └─────────────────────────────────────────────────────────────────┘
#
# KEY INSIGHT - TWO ORTHOGONAL DIMENSIONS:
# ----------------------------------------
# Platform differences break into two independent concerns:
#
#   | Dimension           | Values               | Governs                          |
#   |---------------------|----------------------|----------------------------------|
#   | Package Manager     | pacman, apt, dnf,    | Installing packages (node, pipx, |
#   |                     | brew                 | fuse3)                           |
#   | Platform Family     | linux, macos         | Service management, autostart,   |
#   |                     |                      | paths                            |
#
# Desktop environment (KDE/GNOME/XFCE) doesn't matter because:
#   - XDG autostart spec works on all Linux desktops
#   - FUSE operations (fusermount) are the same across Linux
#
# USAGE:
# ------
#   Interactive:  curl -fsSL https://raw.githubusercontent.com/aaronsb/knowledge-graph-system/main/client-manager.sh | bash
#   Headless:     curl -fsSL ... | bash -s -- --api-url X ...
#   Upgrade:      ./client-manager.sh --upgrade
#   Uninstall:    ./client-manager.sh --uninstall
#   Status:       ./client-manager.sh --status
#   Help:         ./client-manager.sh --help
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
# ============================================================================

# --- Platform Connection ---
# These configure how to connect to the KG platform
API_URL=""                          # Platform API URL (e.g., https://kg.example.com/api)
API_VERSION=""                      # Platform version (fetched from API, saved to config)
USERNAME=""                         # Admin username for authentication
PASSWORD=""                         # Admin password (prompted, never saved to config)

# --- Component Selection ---
# Choose which client tools to install
INSTALL_CLI=true                    # kg CLI (required, always true)
INSTALL_MCP=true                    # MCP server OAuth client
INSTALL_FUSE=false                  # FUSE driver (optional, needs fuse3)

# --- FUSE Options ---
# Configure FUSE filesystem behavior
FUSE_MOUNT_DIR=""                   # Mount directory (default: ~/Knowledge)
FUSE_AUTOSTART=false                # Configure autostart on login

# --- Mode ---
# Current operation mode
MODE="install"                      # install, upgrade, uninstall, status
INTERACTIVE=false                   # Running in interactive mode (vs headless)
SAVE_CONFIG=false                   # Save config after installation

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

# --- Detected Values ---
# These are populated by detection functions. Do not set manually.
DETECTED_OS=""                      # linux-arch, linux-ubuntu, linux-fedora, macos
DETECTED_PKG_MGR=""                 # pacman, apt, dnf, brew
DETECTED_NODE_VERSION=""            # Node.js version or empty
DETECTED_PYTHON_VERSION=""          # Python version or empty
DETECTED_PIPX=""                    # true/false
DETECTED_DESKTOP=""                 # kde, gnome, macos, unknown (informational only)
DETECTED_KG_VERSION=""              # Existing kg CLI version or empty
DETECTED_FUSE_VERSION=""            # Existing kg-fuse version or empty

# --- Derived Values ---
# These are computed from detected values during init
PLATFORM_FAMILY=""                  # linux, macos (for service management dispatch)

# --- Config File ---
# Location determined at runtime based on platform
CONFIG_DIR=""                       # Set in init based on platform
CONFIG_FILE=""                      # Set in init based on platform
CONFIG_VERSION=""                   # Version from loaded config


# ============================================================================
# SECTION 2: UTILITY FUNCTIONS
# ============================================================================
#
# Helper functions used throughout the script:
#   - Logging (colored output)
#   - User prompts (for interactive mode)
#   - Config save/load
#
# ============================================================================

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
    # Informational message (blue i icon)
    echo -e "${BLUE}ℹ${NC} $1" >&2
}

log_success() {
    # Success message (green checkmark)
    echo -e "${GREEN}✓${NC} $1" >&2
}

log_warning() {
    # Warning message (yellow warning icon)
    echo -e "${YELLOW}⚠${NC} $1" >&2
}

log_error() {
    # Error message (red x icon)
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

prompt_choice() {
    # Prompt for selection from numbered options
    # Usage: result=$(prompt_choice "Select option" "Option A" "Option B" "Option C")
    # Returns 0-indexed selection
    local prompt="$1"
    shift
    local options=("$@")
    local i=1
    local response

    echo -e "${CYAN}?${NC} ${prompt}:" >&2
    for opt in "${options[@]}"; do
        echo "  ${i}) ${opt}" >&2
        ((i++))
    done

    while true; do
        echo -ne "  Enter choice [1-${#options[@]}]: " >&2
        read -r response </dev/tty
        if [[ "$response" =~ ^[0-9]+$ ]] && [ "$response" -ge 1 ] && [ "$response" -le "${#options[@]}" ]; then
            echo $((response - 1))
            return
        fi
        echo "  Invalid choice. Please enter a number 1-${#options[@]}." >&2
    done
}

# --- Config Functions ---
# Save and load configuration to/from file

save_config() {
    # Save current configuration to config file
    # Creates config directory if needed
    mkdir -p "$CONFIG_DIR"

    cat > "$CONFIG_FILE" << EOF
# Knowledge Graph Client Manager Configuration
# Generated: $(date -Iseconds)
# Manager Version: $CLIENT_MANAGER_VERSION

API_URL="$API_URL"
API_VERSION="$API_VERSION"
USERNAME="$USERNAME"
INSTALL_CLI=$INSTALL_CLI
INSTALL_MCP=$INSTALL_MCP
INSTALL_FUSE=$INSTALL_FUSE
FUSE_MOUNT_DIR="$FUSE_MOUNT_DIR"
FUSE_AUTOSTART=$FUSE_AUTOSTART
EOF

    log_success "Configuration saved to $CONFIG_FILE"
}

load_config() {
    # Load configuration from config file if it exists
    # Returns 1 if no config file found
    if [[ -f "$CONFIG_FILE" ]]; then
        # shellcheck source=/dev/null
        source "$CONFIG_FILE"
        CONFIG_VERSION=$(grep -E "^# Manager Version:" "$CONFIG_FILE" 2>/dev/null | cut -d: -f2 | tr -d ' ' || true)
        return 0
    fi
    return 1
}


# ============================================================================
# SECTION 3: PACKAGE MANAGER ADAPTERS - PACMAN (Arch Linux)
# ============================================================================
#
# Functions for installing packages on Arch Linux using pacman.
# All functions follow the pattern: pacman_install_{package}
#
# ============================================================================

pacman_install_node() {
    # Install Node.js and npm on Arch Linux
    log_info "Installing Node.js via pacman..."
    sudo pacman -S --noconfirm nodejs npm
}

pacman_install_pipx() {
    # Install pipx on Arch Linux
    log_info "Installing pipx via pacman..."
    sudo pacman -S --noconfirm python-pipx
    # Ensure pipx bin directory is in PATH
    pipx ensurepath 2>/dev/null || true
}

pacman_install_fuse() {
    # Install FUSE3 libraries on Arch Linux
    log_info "Installing fuse3 via pacman..."
    sudo pacman -S --noconfirm fuse3
}


# ============================================================================
# SECTION 4: PACKAGE MANAGER ADAPTERS - APT (Ubuntu/Debian)
# ============================================================================
#
# Functions for installing packages on Ubuntu/Debian using apt.
# All functions follow the pattern: apt_install_{package}
#
# ============================================================================

apt_install_node() {
    # Install Node.js via NodeSource repository on Ubuntu/Debian
    # Uses LTS version for stability
    log_info "Installing Node.js via NodeSource..."
    curl -fsSL "$NODESOURCE_SETUP_URL" | sudo -E bash -
    sudo apt-get install -y nodejs
}

apt_install_pipx() {
    # Install pipx on Ubuntu/Debian
    log_info "Installing pipx via apt..."
    sudo apt-get install -y pipx
    # Ensure pipx bin directory is in PATH
    pipx ensurepath 2>/dev/null || true
}

apt_install_fuse() {
    # Install FUSE3 libraries on Ubuntu/Debian
    log_info "Installing fuse3 via apt..."
    sudo apt-get install -y fuse3
}


# ============================================================================
# SECTION 5: PACKAGE MANAGER ADAPTERS - DNF (Fedora/RHEL)
# ============================================================================
#
# Functions for installing packages on Fedora/RHEL using dnf.
# All functions follow the pattern: dnf_install_{package}
#
# ============================================================================

dnf_install_node() {
    # Install Node.js on Fedora/RHEL
    log_info "Installing Node.js via dnf..."
    sudo dnf install -y nodejs npm
}

dnf_install_pipx() {
    # Install pipx on Fedora/RHEL
    log_info "Installing pipx via dnf..."
    sudo dnf install -y pipx
    # Ensure pipx bin directory is in PATH
    pipx ensurepath 2>/dev/null || true
}

dnf_install_fuse() {
    # Install FUSE3 libraries on Fedora/RHEL
    log_info "Installing fuse3 via dnf..."
    sudo dnf install -y fuse3
}


# ============================================================================
# SECTION 6: PACKAGE MANAGER ADAPTERS - BREW (macOS)
# ============================================================================
#
# Functions for installing packages on macOS using Homebrew.
# All functions follow the pattern: brew_install_{package}
#
# Note: macFUSE requires special handling (cask install + reboot typically)
#
# ============================================================================

brew_install_node() {
    # Install Node.js on macOS via Homebrew
    log_info "Installing Node.js via Homebrew..."
    brew install node
}

brew_install_pipx() {
    # Install pipx on macOS via Homebrew
    log_info "Installing pipx via Homebrew..."
    brew install pipx
    # Ensure pipx bin directory is in PATH
    pipx ensurepath 2>/dev/null || true
}

brew_install_fuse() {
    # Install macFUSE on macOS
    # Note: macFUSE is a cask and may require system extension approval
    log_info "Installing macFUSE via Homebrew..."
    log_warning "macFUSE requires a system extension. You may need to approve it in System Preferences > Security & Privacy"
    brew install --cask macfuse
}


# ============================================================================
# SECTION 7: PLATFORM FAMILY ADAPTERS - LINUX
# ============================================================================
#
# Functions for Linux-specific operations:
#   - FUSE mount/unmount (uses fusermount)
#   - Autostart (uses XDG desktop entry spec, works on KDE/GNOME/XFCE/etc)
#   - Config directories (follows XDG Base Directory spec)
#
# ============================================================================

linux_get_config_dir() {
    # Return XDG-compliant config directory for Linux
    # Respects XDG_CONFIG_HOME if set, defaults to ~/.config
    echo "${XDG_CONFIG_HOME:-$HOME/.config}/kg"
}

linux_stop_fuse() {
    # Unmount FUSE filesystem on Linux
    # Args: $1 = mount directory
    local mount_dir="$1"

    if [[ -z "$mount_dir" ]]; then
        log_error "No mount directory specified for linux_stop_fuse"
        return 1
    fi

    # Check if mounted
    if mountpoint -q "$mount_dir" 2>/dev/null; then
        log_info "Unmounting FUSE at $mount_dir..."
        # Try fusermount3 first (newer), fall back to fusermount
        if command -v fusermount3 &>/dev/null; then
            fusermount3 -u "$mount_dir" 2>/dev/null || true
        elif command -v fusermount &>/dev/null; then
            fusermount -u "$mount_dir" 2>/dev/null || true
        else
            log_warning "No fusermount found, trying umount..."
            umount "$mount_dir" 2>/dev/null || true
        fi
        log_success "FUSE unmounted"
    else
        log_info "FUSE not mounted at $mount_dir"
    fi
}

linux_start_fuse() {
    # Start FUSE filesystem on Linux
    # Args: $1 = mount directory
    local mount_dir="$1"

    if [[ -z "$mount_dir" ]]; then
        log_error "No mount directory specified for linux_start_fuse"
        return 1
    fi

    # Check if kg-fuse is installed
    if ! command -v kg-fuse &>/dev/null; then
        log_warning "kg-fuse not found, cannot start FUSE"
        return 1
    fi

    # Ensure mount directory exists
    mkdir -p "$mount_dir"

    # Start in background
    log_info "Starting FUSE at $mount_dir..."
    nohup kg-fuse "$mount_dir" &>/dev/null &
    sleep 1  # Give it a moment to mount

    # Verify it mounted
    if mountpoint -q "$mount_dir" 2>/dev/null; then
        log_success "FUSE mounted at $mount_dir"
    else
        log_warning "FUSE may not have mounted correctly"
    fi
}

linux_configure_autostart() {
    # Configure FUSE to start on login using XDG autostart
    # Creates a .desktop file in ~/.config/autostart/
    # This works on KDE, GNOME, XFCE, and other freedesktop-compliant desktops
    # Args: $1 = mount directory
    local mount_dir="$1"
    local autostart_dir="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
    local desktop_file="$autostart_dir/kg-fuse.desktop"

    mkdir -p "$autostart_dir"

    cat > "$desktop_file" << EOF
[Desktop Entry]
Type=Application
Name=Knowledge Graph FUSE
Comment=Mount Knowledge Graph as filesystem
Exec=kg-fuse "$mount_dir"
Terminal=false
StartupNotify=false
X-GNOME-Autostart-enabled=true
EOF

    log_success "Autostart configured: $desktop_file"
}

linux_remove_autostart() {
    # Remove FUSE autostart configuration
    local autostart_dir="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
    local desktop_file="$autostart_dir/kg-fuse.desktop"

    if [[ -f "$desktop_file" ]]; then
        rm -f "$desktop_file"
        log_success "Autostart removed"
    else
        log_info "No autostart configuration found"
    fi
}


# ============================================================================
# SECTION 8: PLATFORM FAMILY ADAPTERS - MACOS
# ============================================================================
#
# Functions for macOS-specific operations:
#   - FUSE mount/unmount (uses diskutil/umount)
#   - Autostart (uses launchd with plist files)
#   - Config directories (uses ~/Library/Application Support)
#
# ============================================================================

macos_get_config_dir() {
    # Return macOS-standard config directory
    echo "$HOME/Library/Application Support/kg"
}

macos_stop_fuse() {
    # Unmount FUSE filesystem on macOS
    # Args: $1 = mount directory
    local mount_dir="$1"

    if [[ -z "$mount_dir" ]]; then
        log_error "No mount directory specified for macos_stop_fuse"
        return 1
    fi

    # Check if mounted (macOS doesn't have mountpoint command)
    if mount | grep -q " on $mount_dir "; then
        log_info "Unmounting FUSE at $mount_dir..."
        # Try diskutil first, fall back to umount
        if diskutil unmount "$mount_dir" 2>/dev/null; then
            log_success "FUSE unmounted"
        elif umount "$mount_dir" 2>/dev/null; then
            log_success "FUSE unmounted"
        else
            log_warning "Could not unmount FUSE"
        fi
    else
        log_info "FUSE not mounted at $mount_dir"
    fi
}

macos_start_fuse() {
    # Start FUSE filesystem on macOS
    # Args: $1 = mount directory
    local mount_dir="$1"

    if [[ -z "$mount_dir" ]]; then
        log_error "No mount directory specified for macos_start_fuse"
        return 1
    fi

    # Check if kg-fuse is installed
    if ! command -v kg-fuse &>/dev/null; then
        log_warning "kg-fuse not found, cannot start FUSE"
        return 1
    fi

    # Ensure mount directory exists
    mkdir -p "$mount_dir"

    # Start in background
    log_info "Starting FUSE at $mount_dir..."
    nohup kg-fuse "$mount_dir" &>/dev/null &
    sleep 1  # Give it a moment to mount

    # Verify it mounted
    if mount | grep -q " on $mount_dir "; then
        log_success "FUSE mounted at $mount_dir"
    else
        log_warning "FUSE may not have mounted correctly"
    fi
}

macos_configure_autostart() {
    # Configure FUSE to start on login using launchd
    # Creates a plist file in ~/Library/LaunchAgents/
    # Args: $1 = mount directory
    local mount_dir="$1"
    local plist_dir="$HOME/Library/LaunchAgents"
    local plist_file="$plist_dir/com.kg.fuse.plist"
    local kg_fuse_path

    # Find kg-fuse path
    kg_fuse_path=$(command -v kg-fuse 2>/dev/null || echo "/usr/local/bin/kg-fuse")

    mkdir -p "$plist_dir"

    cat > "$plist_file" << EOF
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
    <string>/tmp/kg-fuse.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/kg-fuse.err</string>
</dict>
</plist>
EOF

    # Load the agent
    launchctl load "$plist_file" 2>/dev/null || true

    log_success "Autostart configured: $plist_file"
}

macos_remove_autostart() {
    # Remove FUSE autostart configuration
    local plist_file="$HOME/Library/LaunchAgents/com.kg.fuse.plist"

    if [[ -f "$plist_file" ]]; then
        # Unload first
        launchctl unload "$plist_file" 2>/dev/null || true
        rm -f "$plist_file"
        log_success "Autostart removed"
    else
        log_info "No autostart configuration found"
    fi
}


# ============================================================================
# SECTION 9: DISPATCH LAYER
# ============================================================================
#
# These functions dispatch to the appropriate adapter based on detected
# package manager and platform family. They provide a uniform interface
# that the rest of the script uses.
#
# Pattern:
#   dispatch_function() calls ${DETECTED_PKG_MGR}_action or ${PLATFORM_FAMILY}_action
#
# ============================================================================

# --- Package Manager Dispatch ---
# These dispatch to the correct package manager adapter

install_node() {
    # Install Node.js using the detected package manager
    local fn="${DETECTED_PKG_MGR}_install_node"
    if declare -f "$fn" > /dev/null; then
        "$fn"
    else
        log_error "No Node.js install adapter for package manager: $DETECTED_PKG_MGR"
        return 1
    fi
}

install_pipx() {
    # Install pipx using the detected package manager
    local fn="${DETECTED_PKG_MGR}_install_pipx"
    if declare -f "$fn" > /dev/null; then
        "$fn"
    else
        log_error "No pipx install adapter for package manager: $DETECTED_PKG_MGR"
        return 1
    fi
}

install_fuse_libs() {
    # Install FUSE libraries using the detected package manager
    local fn="${DETECTED_PKG_MGR}_install_fuse"
    if declare -f "$fn" > /dev/null; then
        "$fn"
    else
        log_error "No FUSE install adapter for package manager: $DETECTED_PKG_MGR"
        return 1
    fi
}

# --- Platform Family Dispatch ---
# These dispatch to the correct platform family adapter

get_config_dir() {
    # Get config directory for current platform
    local fn="${PLATFORM_FAMILY}_get_config_dir"
    if declare -f "$fn" > /dev/null; then
        "$fn"
    else
        # Fallback to sensible default
        echo "${XDG_CONFIG_HOME:-$HOME/.config}/kg"
    fi
}

stop_fuse() {
    # Stop FUSE on current platform
    # Args: $1 = mount directory
    local fn="${PLATFORM_FAMILY}_stop_fuse"
    if declare -f "$fn" > /dev/null; then
        "$fn" "$@"
    else
        log_error "No stop_fuse adapter for platform: $PLATFORM_FAMILY"
        return 1
    fi
}

start_fuse() {
    # Start FUSE on current platform
    # Args: $1 = mount directory
    local fn="${PLATFORM_FAMILY}_start_fuse"
    if declare -f "$fn" > /dev/null; then
        "$fn" "$@"
    else
        log_error "No start_fuse adapter for platform: $PLATFORM_FAMILY"
        return 1
    fi
}

configure_autostart() {
    # Configure autostart on current platform
    # Args: $1 = mount directory
    local fn="${PLATFORM_FAMILY}_configure_autostart"
    if declare -f "$fn" > /dev/null; then
        "$fn" "$@"
    else
        log_error "No configure_autostart adapter for platform: $PLATFORM_FAMILY"
        return 1
    fi
}

remove_autostart() {
    # Remove autostart on current platform
    local fn="${PLATFORM_FAMILY}_remove_autostart"
    if declare -f "$fn" > /dev/null; then
        "$fn"
    else
        log_error "No remove_autostart adapter for platform: $PLATFORM_FAMILY"
        return 1
    fi
}


# ============================================================================
# SECTION 10: DETECTION & VERIFICATION
# ============================================================================
#
# Functions to detect the current environment:
#   - Operating system and distribution
#   - Package manager available
#   - Existing installations (Node, Python, kg CLI, kg-fuse)
#   - Desktop environment (informational)
#
# And to verify connections:
#   - API health check
#   - Credential verification
#
# ============================================================================

detect_os() {
    # Detect operating system and set DETECTED_OS, DETECTED_PKG_MGR, PLATFORM_FAMILY
    log_info "Detecting operating system..."

    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        DETECTED_OS="macos"
        DETECTED_PKG_MGR="brew"
        PLATFORM_FAMILY="macos"
        DETECTED_DESKTOP="macos"
        log_success "Detected macOS"
        return 0
    fi

    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        PLATFORM_FAMILY="linux"

        # Detect Linux distribution
        if [[ -f /etc/os-release ]]; then
            # shellcheck source=/dev/null
            source /etc/os-release

            case "$ID" in
                arch|manjaro|endeavouros)
                    DETECTED_OS="linux-arch"
                    DETECTED_PKG_MGR="pacman"
                    log_success "Detected Arch Linux (or derivative)"
                    ;;
                ubuntu|debian|linuxmint|pop)
                    DETECTED_OS="linux-ubuntu"
                    DETECTED_PKG_MGR="apt"
                    log_success "Detected Ubuntu/Debian (or derivative)"
                    ;;
                fedora|rhel|centos|rocky|alma)
                    DETECTED_OS="linux-fedora"
                    DETECTED_PKG_MGR="dnf"
                    log_success "Detected Fedora/RHEL (or derivative)"
                    ;;
                *)
                    log_warning "Unknown Linux distribution: $ID"
                    # Try to detect package manager anyway
                    if command -v pacman &>/dev/null; then
                        DETECTED_OS="linux-arch"
                        DETECTED_PKG_MGR="pacman"
                    elif command -v apt &>/dev/null; then
                        DETECTED_OS="linux-ubuntu"
                        DETECTED_PKG_MGR="apt"
                    elif command -v dnf &>/dev/null; then
                        DETECTED_OS="linux-fedora"
                        DETECTED_PKG_MGR="dnf"
                    else
                        log_error "Could not detect package manager"
                        return 1
                    fi
                    ;;
            esac
        else
            log_error "Could not detect Linux distribution (no /etc/os-release)"
            return 1
        fi

        # Detect desktop environment (informational only)
        detect_desktop

        return 0
    fi

    log_error "Unsupported operating system: $OSTYPE"
    return 1
}

detect_desktop() {
    # Detect desktop environment on Linux (informational only)
    # This doesn't affect behavior - XDG autostart works on all desktops
    if [[ "$XDG_CURRENT_DESKTOP" == *"KDE"* ]] || [[ "$DESKTOP_SESSION" == *"plasma"* ]]; then
        DETECTED_DESKTOP="kde"
    elif [[ "$XDG_CURRENT_DESKTOP" == *"GNOME"* ]] || [[ "$DESKTOP_SESSION" == *"gnome"* ]]; then
        DETECTED_DESKTOP="gnome"
    elif [[ "$XDG_CURRENT_DESKTOP" == *"XFCE"* ]] || [[ "$DESKTOP_SESSION" == *"xfce"* ]]; then
        DETECTED_DESKTOP="xfce"
    else
        DETECTED_DESKTOP="unknown"
    fi
    log_info "Desktop environment: $DETECTED_DESKTOP"
}

detect_prerequisites() {
    # Detect existing prerequisites (Node.js, Python, pipx)
    log_info "Checking prerequisites..."

    # Node.js
    if command -v node &>/dev/null; then
        DETECTED_NODE_VERSION=$(node --version 2>/dev/null | sed 's/^v//')
        log_success "Node.js: $DETECTED_NODE_VERSION"
    else
        DETECTED_NODE_VERSION=""
        log_info "Node.js: not installed"
    fi

    # Python
    if command -v python3 &>/dev/null; then
        DETECTED_PYTHON_VERSION=$(python3 --version 2>/dev/null | sed 's/Python //')
        log_success "Python: $DETECTED_PYTHON_VERSION"
    else
        DETECTED_PYTHON_VERSION=""
        log_info "Python: not installed"
    fi

    # pipx
    if command -v pipx &>/dev/null; then
        DETECTED_PIPX=true
        log_success "pipx: installed"
    else
        DETECTED_PIPX=false
        log_info "pipx: not installed"
    fi
}

detect_existing_installs() {
    # Detect existing kg CLI and kg-fuse installations
    log_info "Checking existing installations..."

    # kg CLI
    if command -v kg &>/dev/null; then
        # Get version from kg --version, being careful about output format
        DETECTED_KG_VERSION=$(kg --version 2>/dev/null | head -1 || true)
        log_success "kg CLI: $DETECTED_KG_VERSION"
    else
        DETECTED_KG_VERSION=""
        log_info "kg CLI: not installed"
    fi

    # kg-fuse
    if command -v kg-fuse &>/dev/null; then
        DETECTED_FUSE_VERSION=$(kg-fuse --version 2>/dev/null | head -1 || true)
        log_success "kg-fuse: $DETECTED_FUSE_VERSION"
    else
        DETECTED_FUSE_VERSION=""
        log_info "kg-fuse: not installed"
    fi
}

detect_existing_config() {
    # Try to detect existing configuration from kg CLI
    # Returns values via global variables
    local json_config=""
    local detected_url=""

    if command -v kg &>/dev/null; then
        # Use kg config json get for machine-readable output (no ANSI codes)
        json_config=$(kg config json get 2>/dev/null || true)

        if [[ -n "$json_config" ]]; then
            # Try jq first, fall back to grep/sed
            if command -v jq &>/dev/null; then
                detected_url=$(echo "$json_config" | jq -r '.api_url // empty' 2>/dev/null || true)
            else
                detected_url=$(echo "$json_config" | grep -o '"api_url"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*: *"\([^"]*\)"/\1/' || true)
            fi

            if [[ -n "$detected_url" ]]; then
                log_info "Detected existing API URL: $detected_url"
                API_URL="$detected_url"
            fi
        fi
    fi
}

verify_api_connection() {
    # Verify connection to the API and fetch platform version
    # Args: $1 = API URL (optional, uses $API_URL if not provided)
    local url="${1:-$API_URL}"

    if [[ -z "$url" ]]; then
        log_error "No API URL provided"
        return 1
    fi

    log_info "Checking API connection..."

    # Remove trailing /api if present for root endpoint
    local root_url="${url%/api}"

    local response
    response=$(curl -sf "$root_url" --max-time 10 2>/dev/null || true)

    if [[ -z "$response" ]]; then
        log_error "Could not connect to $root_url"
        return 1
    fi

    # Try to extract version
    if command -v jq &>/dev/null; then
        API_VERSION=$(echo "$response" | jq -r '.version // empty' 2>/dev/null || true)
    else
        API_VERSION=$(echo "$response" | grep -o '"version"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*: *"\([^"]*\)"/\1/' || true)
    fi

    if [[ -n "$API_VERSION" ]]; then
        log_success "API reachable, platform version: $API_VERSION"
    else
        log_success "API reachable"
    fi

    return 0
}


# ============================================================================
# SECTION 11: INSTALLATION LOGIC
# ============================================================================
#
# Functions for the actual installation steps:
#   - Prerequisites (Node.js, pipx, FUSE libs)
#   - kg CLI (via npm)
#   - kg-fuse (via pipx)
#   - OAuth client creation
#   - Configuration
#
# These use the dispatch layer to call platform-specific implementations.
#
# ============================================================================

ensure_prerequisites() {
    # Ensure required prerequisites are installed
    # Uses dispatch layer to call correct package manager adapter
    log_step "Checking prerequisites"

    # Node.js is required for kg CLI
    if [[ -z "$DETECTED_NODE_VERSION" ]]; then
        log_info "Node.js is required for the kg CLI"
        install_node

        # Re-detect after install
        if command -v node &>/dev/null; then
            DETECTED_NODE_VERSION=$(node --version 2>/dev/null | sed 's/^v//')
            log_success "Node.js installed: $DETECTED_NODE_VERSION"
        else
            log_error "Node.js installation failed"
            return 1
        fi
    fi

    # pipx is required for kg-fuse (only if installing FUSE)
    if [[ "$INSTALL_FUSE" == true ]] && [[ "$DETECTED_PIPX" != true ]]; then
        log_info "pipx is required for kg-fuse"
        install_pipx

        # Re-detect after install
        if command -v pipx &>/dev/null; then
            DETECTED_PIPX=true
            log_success "pipx installed"
        else
            log_error "pipx installation failed"
            return 1
        fi
    fi

    # FUSE libraries (only if installing FUSE)
    if [[ "$INSTALL_FUSE" == true ]]; then
        # Check if FUSE is available (platform-specific check)
        local fuse_available=false

        if [[ "$PLATFORM_FAMILY" == "linux" ]]; then
            # Check for fusermount or fusermount3
            if command -v fusermount3 &>/dev/null || command -v fusermount &>/dev/null; then
                fuse_available=true
            fi
        elif [[ "$PLATFORM_FAMILY" == "macos" ]]; then
            # Check for macFUSE
            if [[ -d "/Library/Frameworks/macFUSE.framework" ]]; then
                fuse_available=true
            fi
        fi

        if [[ "$fuse_available" != true ]]; then
            log_info "FUSE libraries required for kg-fuse"
            install_fuse_libs
        fi
    fi

    log_success "Prerequisites ready"
}

npm_user_install() {
    # Install npm package to user-local directory (~/.local)
    # This avoids needing sudo and doesn't touch system packages
    # Usage: npm_user_install <package-name>
    local package="$1"
    local npm_dir="$HOME/.local"

    # Ensure user npm directories exist
    mkdir -p "$npm_dir/lib/node_modules" "$npm_dir/bin"

    # Install to user directory using --prefix
    (cd /tmp && npm install -g --prefix "$npm_dir" "$package")

    # Ensure bin directory is in PATH for this session
    if [[ ":$PATH:" != *":$npm_dir/bin:"* ]]; then
        export PATH="$npm_dir/bin:$PATH"
    fi
}

npm_user_uninstall() {
    # Uninstall npm package from user-local directory
    # Usage: npm_user_uninstall <package-name>
    local package="$1"
    local npm_dir="$HOME/.local"

    npm uninstall -g --prefix "$npm_dir" "$package" 2>/dev/null || true
}

install_kg_cli() {
    # Install the kg CLI via npm to user-local directory
    log_step "Installing kg CLI"

    log_info "Installing $NPM_PACKAGE to ~/.local..."
    npm_user_install "$NPM_PACKAGE"

    # Verify installation
    if command -v kg &>/dev/null; then
        DETECTED_KG_VERSION=$(kg --version 2>/dev/null | head -1 || true)
        log_success "kg CLI installed: $DETECTED_KG_VERSION"
    else
        log_error "kg CLI installation failed"
        log_warning "Ensure ~/.local/bin is in your PATH"
        return 1
    fi
}

install_kg_fuse() {
    # Install kg-fuse via pipx
    log_step "Installing kg-fuse"

    log_info "Installing $PYPI_PACKAGE via pipx..."
    pipx install "$PYPI_PACKAGE"

    # Verify installation
    if command -v kg-fuse &>/dev/null; then
        DETECTED_FUSE_VERSION=$(kg-fuse --version 2>/dev/null | head -1 || true)
        log_success "kg-fuse installed: $DETECTED_FUSE_VERSION"
    else
        log_error "kg-fuse installation failed"
        return 1
    fi
}

configure_cli() {
    # Configure the kg CLI with API URL and credentials
    log_step "Configuring kg CLI"

    # Set API URL
    log_info "Setting API URL..."
    kg config set api_url "$API_URL"

    # Login
    if [[ -n "$USERNAME" ]] && [[ -n "$PASSWORD" ]]; then
        log_info "Authenticating..."
        # kg login with credentials
        kg login --username "$USERNAME" --password "$PASSWORD"
        log_success "Authenticated as $USERNAME"
    else
        log_info "Skipping authentication (no credentials provided)"
    fi
}

configure_fuse() {
    # Configure FUSE mount directory and autostart
    log_step "Configuring kg-fuse"

    # Set default mount directory if not specified
    if [[ -z "$FUSE_MOUNT_DIR" ]]; then
        FUSE_MOUNT_DIR="$HOME/Knowledge"
    fi

    # Create mount directory
    mkdir -p "$FUSE_MOUNT_DIR"
    log_success "Mount directory: $FUSE_MOUNT_DIR"

    # Configure autostart if requested
    if [[ "$FUSE_AUTOSTART" == true ]]; then
        configure_autostart "$FUSE_MOUNT_DIR"
    fi

    # Start FUSE
    start_fuse "$FUSE_MOUNT_DIR"
}

upgrade_kg_cli() {
    # Upgrade the kg CLI to latest version
    log_step "Upgrading kg CLI"

    log_info "Upgrading $NPM_PACKAGE..."
    npm_user_install "$NPM_PACKAGE"

    # Re-detect version
    if command -v kg &>/dev/null; then
        DETECTED_KG_VERSION=$(kg --version 2>/dev/null | head -1 || true)
        log_success "kg CLI upgraded: $DETECTED_KG_VERSION"
    fi
}

upgrade_kg_fuse() {
    # Upgrade kg-fuse to latest version
    log_step "Upgrading kg-fuse"

    # Stop FUSE first if running
    if [[ -n "$FUSE_MOUNT_DIR" ]]; then
        stop_fuse "$FUSE_MOUNT_DIR"
    fi

    log_info "Upgrading $PYPI_PACKAGE..."
    pipx upgrade "$PYPI_PACKAGE"

    # Re-detect version
    if command -v kg-fuse &>/dev/null; then
        DETECTED_FUSE_VERSION=$(kg-fuse --version 2>/dev/null | head -1 || true)
        log_success "kg-fuse upgraded: $DETECTED_FUSE_VERSION"
    fi

    # Restart FUSE if it was running
    if [[ -n "$FUSE_MOUNT_DIR" ]]; then
        start_fuse "$FUSE_MOUNT_DIR"
    fi
}

uninstall_kg_cli() {
    # Uninstall the kg CLI from user-local directory
    log_step "Uninstalling kg CLI"

    log_info "Uninstalling $NPM_PACKAGE..."
    npm_user_uninstall "$NPM_PACKAGE"

    # Verify uninstallation
    if ! command -v kg &>/dev/null; then
        log_success "kg CLI uninstalled"
    else
        log_warning "kg CLI may still be installed"
    fi
}

uninstall_kg_fuse() {
    # Uninstall kg-fuse
    log_step "Uninstalling kg-fuse"

    # Stop FUSE first
    if [[ -n "$FUSE_MOUNT_DIR" ]]; then
        stop_fuse "$FUSE_MOUNT_DIR"
    fi

    # Remove autostart
    remove_autostart

    log_info "Uninstalling $PYPI_PACKAGE..."
    pipx uninstall "$PYPI_PACKAGE" 2>/dev/null || true

    # Verify uninstallation
    if ! command -v kg-fuse &>/dev/null; then
        log_success "kg-fuse uninstalled"
    else
        log_warning "kg-fuse may still be installed"
    fi
}


# ============================================================================
# SECTION 12: MAIN FLOW
# ============================================================================
#
# Main script execution:
#   - Argument parsing
#   - Mode selection (interactive vs headless)
#   - Lifecycle menu
#   - Mode handlers (install, upgrade, uninstall, status)
#
# ============================================================================

show_help() {
    cat << EOF
Knowledge Graph Client Manager v$CLIENT_MANAGER_VERSION

Usage: $0 [OPTIONS]

Modes:
  --install         Install client tools (default)
  --upgrade         Upgrade existing installation
  --uninstall       Remove client tools
  --status          Show installation status

Options:
  --api-url URL     Platform API URL (e.g., https://kg.example.com/api)
  --username USER   Username for authentication
  --fuse            Install FUSE filesystem driver
  --no-fuse         Skip FUSE driver (default)
  --autostart       Configure FUSE to start on login
  --mount-dir DIR   FUSE mount directory (default: ~/Knowledge)
  --help            Show this help message

Interactive mode:
  Run without arguments for guided installation

Examples:
  # Interactive installation
  curl -fsSL .../client-manager.sh | bash

  # Headless installation
  curl -fsSL .../client-manager.sh | bash -s -- --api-url https://kg.example.com/api --username admin

  # Upgrade existing installation
  ./client-manager.sh --upgrade

  # Check status
  ./client-manager.sh --status
EOF
}

parse_args() {
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --install)
                MODE="install"
                shift
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
            --fuse)
                INSTALL_FUSE=true
                shift
                ;;
            --no-fuse)
                INSTALL_FUSE=false
                shift
                ;;
            --autostart)
                FUSE_AUTOSTART=true
                shift
                ;;
            --mount-dir)
                FUSE_MOUNT_DIR="$2"
                shift 2
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done

    # Enable interactive mode if:
    # - Running in a terminal directly (stdin is a tty), OR
    # - Piped from curl but /dev/tty is available for prompts
    # AND no API URL was provided (headless mode requires --api-url)
    if [[ -z "$API_URL" ]]; then
        if [ -t 0 ] || [ -e /dev/tty ]; then
            INTERACTIVE=true
        fi
    fi
}

show_lifecycle_menu() {
    # Show lifecycle options based on what's currently installed
    # Returns the selected mode

    if [[ -n "$DETECTED_KG_VERSION" ]] || [[ -n "$DETECTED_FUSE_VERSION" ]]; then
        # Tools are installed - offer lifecycle options
        echo ""
        echo -e "${BOLD}Current installation:${NC}"
        [[ -n "$DETECTED_KG_VERSION" ]] && echo "  kg CLI: $DETECTED_KG_VERSION"
        [[ -n "$DETECTED_FUSE_VERSION" ]] && echo "  kg-fuse: $DETECTED_FUSE_VERSION"
        echo ""

        local choice
        choice=$(prompt_choice "What would you like to do?" \
            "Upgrade to latest versions" \
            "Reconfigure (change settings)" \
            "Reinstall (fresh installation)" \
            "Uninstall")

        case "$choice" in
            0) MODE="upgrade" ;;
            1) MODE="configure" ;;
            2) MODE="install" ;;
            3) MODE="uninstall" ;;
        esac
    else
        # Nothing installed - proceed with install
        MODE="install"
    fi
}

show_status() {
    # Show current installation status
    log_step "Installation Status"

    detect_os
    detect_prerequisites
    detect_existing_installs
    detect_existing_config

    echo ""
    echo -e "${BOLD}System:${NC}"
    echo "  OS: $DETECTED_OS"
    echo "  Package Manager: $DETECTED_PKG_MGR"
    echo "  Platform Family: $PLATFORM_FAMILY"
    echo "  Desktop: $DETECTED_DESKTOP"

    echo ""
    echo -e "${BOLD}Prerequisites:${NC}"
    echo "  Node.js: ${DETECTED_NODE_VERSION:-not installed}"
    echo "  Python: ${DETECTED_PYTHON_VERSION:-not installed}"
    echo "  pipx: ${DETECTED_PIPX:-false}"

    echo ""
    echo -e "${BOLD}Client Tools:${NC}"
    echo "  kg CLI: ${DETECTED_KG_VERSION:-not installed}"
    echo "  kg-fuse: ${DETECTED_FUSE_VERSION:-not installed}"

    echo ""
    echo -e "${BOLD}Configuration:${NC}"
    echo "  API URL: ${API_URL:-not configured}"
    echo "  API Version: ${API_VERSION:-unknown}"

    if [[ -f "$CONFIG_FILE" ]]; then
        echo "  Config File: $CONFIG_FILE"
    fi
}

show_summary() {
    # Show installation summary and next steps
    log_step "Installation Complete"

    echo ""
    echo -e "${BOLD}Installed:${NC}"
    [[ -n "$DETECTED_KG_VERSION" ]] && echo "  kg CLI: $DETECTED_KG_VERSION"
    [[ -n "$DETECTED_FUSE_VERSION" ]] && echo "  kg-fuse: $DETECTED_FUSE_VERSION"

    echo ""
    echo -e "${BOLD}Configuration:${NC}"
    echo "  API URL: $API_URL"
    [[ -n "$API_VERSION" ]] && echo "  Platform Version: $API_VERSION"
    [[ -n "$FUSE_MOUNT_DIR" ]] && echo "  FUSE Mount: $FUSE_MOUNT_DIR"

    # Show web UI URL
    local web_url="${API_URL%/api}"
    echo ""
    echo -e "${BOLD}Web UI:${NC}"
    echo "  $web_url"
    echo "  (The web UI shares capabilities with the CLI)"

    echo ""
    echo -e "${BOLD}Next steps:${NC}"
    echo ""
    echo "  To verify installation:"
    echo "    kg health"
    echo ""
    echo "  To add knowledge:"
    echo "    kg ingest file.pdf"
    echo "    kg ingest directory/"
    echo ""
    echo "  To explore knowledge:"
    echo "    kg search \"your query\""
    echo "    kg ontology list"
    [[ -n "$FUSE_MOUNT_DIR" ]] && echo "    ls $FUSE_MOUNT_DIR"
    echo ""
}

run_install() {
    # Run installation flow
    log_step "Installing Knowledge Graph Client Tools"

    # Ensure prerequisites
    ensure_prerequisites

    # Install kg CLI
    install_kg_cli

    # Install FUSE if requested
    if [[ "$INSTALL_FUSE" == true ]]; then
        install_kg_fuse
        configure_fuse
    fi

    # Configure CLI
    if [[ -n "$API_URL" ]]; then
        configure_cli
    fi

    # Save config if requested
    if [[ "$SAVE_CONFIG" == true ]]; then
        save_config
    fi

    # Show summary
    show_summary
}

run_upgrade() {
    # Run upgrade flow
    log_step "Upgrading Knowledge Graph Client Tools"

    # Upgrade kg CLI if installed
    if [[ -n "$DETECTED_KG_VERSION" ]]; then
        upgrade_kg_cli
    fi

    # Upgrade kg-fuse if installed
    if [[ -n "$DETECTED_FUSE_VERSION" ]]; then
        upgrade_kg_fuse
    fi

    log_success "Upgrade complete"
}

run_uninstall() {
    # Run uninstall flow
    log_step "Uninstalling Knowledge Graph Client Tools"

    # Confirm if interactive
    if [[ "$INTERACTIVE" == true ]]; then
        if ! prompt_bool "Are you sure you want to uninstall?" "n"; then
            log_info "Uninstall cancelled"
            exit 0
        fi
    fi

    # Uninstall kg-fuse first (if installed)
    if [[ -n "$DETECTED_FUSE_VERSION" ]]; then
        uninstall_kg_fuse
    fi

    # Uninstall kg CLI
    if [[ -n "$DETECTED_KG_VERSION" ]]; then
        uninstall_kg_cli
    fi

    # Optionally remove config
    if [[ "$INTERACTIVE" == true ]]; then
        if prompt_bool "Remove configuration files?" "n"; then
            rm -rf "$CONFIG_DIR"
            log_success "Configuration removed"
        fi
    fi

    log_success "Uninstall complete"
}

run_interactive() {
    # Run interactive installation flow
    log_step "Knowledge Graph Client Manager v$CLIENT_MANAGER_VERSION"

    # Try to load existing config
    if load_config; then
        log_info "Loaded configuration from $CONFIG_FILE"
    fi

    # Detect existing state
    detect_existing_installs
    detect_existing_config

    # Show lifecycle menu
    show_lifecycle_menu

    # Execute selected mode
    case "$MODE" in
        install)
            # Prompt for missing configuration
            if [[ -z "$API_URL" ]]; then
                API_URL=$(prompt_value "API URL" "https://kg.example.com/api")
            fi

            # Verify API connection
            if ! verify_api_connection "$API_URL"; then
                log_warning "Could not verify API connection, but continuing..."
            fi

            # Prompt for credentials
            if [[ -z "$USERNAME" ]]; then
                USERNAME=$(prompt_value "Username" "admin")
            fi
            PASSWORD=$(prompt_password "Password")

            # Ask about FUSE
            if prompt_bool "Install FUSE filesystem driver?" "n"; then
                INSTALL_FUSE=true
                FUSE_MOUNT_DIR=$(prompt_value "Mount directory" "$HOME/Knowledge")
                if prompt_bool "Start FUSE on login?" "n"; then
                    FUSE_AUTOSTART=true
                fi
            fi

            # Ask about saving config
            if prompt_bool "Save configuration for future updates?" "y"; then
                SAVE_CONFIG=true
            fi

            # Run installation
            run_install
            ;;

        upgrade)
            run_upgrade
            ;;

        configure)
            # Reconfiguration flow
            API_URL=$(prompt_value "API URL" "$API_URL")
            verify_api_connection "$API_URL" || true
            USERNAME=$(prompt_value "Username" "$USERNAME")
            PASSWORD=$(prompt_password "Password")
            configure_cli
            save_config
            log_success "Configuration updated"
            ;;

        uninstall)
            run_uninstall
            ;;
    esac
}

init() {
    # Initialize the script - detect platform and set up config paths
    detect_os

    # Set config directory based on platform
    CONFIG_DIR=$(get_config_dir)
    CONFIG_FILE="$CONFIG_DIR/client-manager.conf"
}

main() {
    # Main entry point
    parse_args "$@"

    # Initialize (detect OS, set paths)
    init

    # Route to appropriate handler
    case "$MODE" in
        status)
            show_status
            ;;
        install|upgrade|uninstall)
            if [[ "$INTERACTIVE" == true ]]; then
                run_interactive
            else
                # Headless mode
                detect_prerequisites
                detect_existing_installs

                case "$MODE" in
                    install) run_install ;;
                    upgrade) run_upgrade ;;
                    uninstall) run_uninstall ;;
                esac
            fi
            ;;
        *)
            log_error "Unknown mode: $MODE"
            exit 1
            ;;
    esac
}

# Run main with all arguments
main "$@"
