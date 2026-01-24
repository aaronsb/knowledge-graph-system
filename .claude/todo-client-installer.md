# Client Installer Architecture

## Overview

A user-friendly installer for Knowledge Graph clients (CLI, MCP server, FUSE driver).
Follows the same patterns as `install.sh` (platform installer):

- **Configuration-first** - All options defined as variables at top
- **Dual-mode** - Interactive prompts OR command-line flags
- **Three-tier prompts** - Previous value → Auto-detected → Default
- **Config persistence** - Save/load choices to XDG config
- **Staged verification** - Test each step before proceeding
- **Multi-platform** - Linux (Arch, Ubuntu, Fedora) + macOS

**Key difference from platform installer:**
- **Dual-use** - Detects existing install, offers upgrade (platform uses operator.sh after install)

**One-liner install:**
```bash
curl -fsSL https://raw.githubusercontent.com/aaronsb/knowledge-graph-system/main/client-install.sh | bash
```

---

## What Gets Installed

| Component | Source | Install Method | Root Required |
|-----------|--------|----------------|---------------|
| **fuse3/macfuse** | System package | pacman/apt/dnf/brew | Yes |
| **kg CLI** | npm | `npm install -g` to ~/.local | No |
| **kg-mcp-server** | npm (same package) | Included with CLI | No |
| **kg-fuse** | PyPI | `pipx install` | No |

---

## Platform Support

| Platform | Package Manager | FUSE | Node | Python/pipx | Autostart |
|----------|-----------------|------|------|-------------|-----------|
| Arch Linux | pacman | `fuse3` | `nodejs npm` | `python-pipx` | systemd user / KDE autostart |
| Ubuntu/Debian | apt | `fuse3` | `nodejs npm` | `pipx` | systemd user / GNOME autostart |
| Fedora/RHEL | dnf | `fuse3` | `nodejs npm` | `pipx` | systemd user |
| macOS | brew | `macfuse` | `node` | `pipx` | launchd plist |

**macOS Notes:**
- FUSE support via macFUSE (requires kernel extension approval in Security settings)
- macFUSE has limitations compared to Linux FUSE3
- Node.js often pre-installed or via Xcode CLI tools
- pipx via `brew install pipx`

---

## Script Structure (matching install.sh)

```bash
#!/bin/bash
# ============================================================================
# Knowledge Graph Client Installer
# ============================================================================
CLIENT_INSTALLER_VERSION="0.1.0"

# ============================================================================
# SECTION 1: CONFIGURATION VARIABLES
# ============================================================================

# --- Platform Connection ---
API_URL=""                          # Platform API URL (e.g., https://kg.example.com/api)
USERNAME=""                         # Admin username for authentication
PASSWORD=""                         # Admin password (prompted, not saved to config)

# --- Component Selection ---
INSTALL_CLI=true                    # kg CLI (required, always true)
INSTALL_MCP=true                    # MCP server config
INSTALL_FUSE=false                  # FUSE driver

# --- FUSE Options ---
FUSE_MOUNT_DIR=""                   # Default: ~/Knowledge
FUSE_AUTOSTART=false                # Configure autostart on login

# --- State ---
INTERACTIVE=false                   # Interactive or headless mode
MODE="install"                      # install, upgrade, uninstall, status

# --- Config File (XDG-compliant) ---
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/kg"
CONFIG_FILE="$CONFIG_DIR/client-install.conf"

# ============================================================================
# SECTION 2: UTILITY FUNCTIONS (ported from install.sh)
# ============================================================================
# - log_info, log_success, log_warning, log_error, log_step
# - prompt_value, prompt_password, prompt_bool, prompt_select
# - prompt_with_fallback (three-tier: previous → detected → default)
# - save_config, load_config

# ============================================================================
# SECTION 3: DETECTION FUNCTIONS
# ============================================================================
# - detect_os (linux-arch, linux-ubuntu, linux-fedora, macos)
# - detect_package_manager (pacman, apt, dnf, brew)
# - detect_node, detect_python, detect_pipx
# - detect_existing_install (CLI version, FUSE version)
# - detect_desktop_environment (KDE, GNOME, macOS)

# ============================================================================
# SECTION 4: VERIFICATION FUNCTIONS
# ============================================================================
# - verify_api_url (curl test)
# - verify_login (kg login + kg health)
# - verify_cli_install (kg --version)
# - verify_fuse_install (kg-fuse --help)

# ============================================================================
# SECTION 5: INSTALLATION FUNCTIONS
# ============================================================================
# - install_prerequisites (node, python, pipx, fuse)
# - install_cli
# - install_fuse
# - configure_mcp
# - configure_fuse_autostart

# ============================================================================
# SECTION 6: MAIN FLOW
# ============================================================================
```

---

## Bootstrap Chain

```
┌─────────────────────────────────────────────────────────────────┐
│  1. Install CLI (always)                                        │
│     npm install -g @aaronsb/kg-cli --prefix ~/.local            │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. Configure & Authenticate (ONE TIME - caches credentials)    │
│     kg config set api-url https://kg.example.com/api            │
│     kg login -u USER -p PASS --remember-username                │
│     → Stores OAuth client in ~/.config/kg/config.json           │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. Verify Connection                                           │
│     kg health                                                   │
│     → Confirms credentials work, platform is reachable          │
└─────────────────────┬───────────────────────────────────────────┘
                      │
          ┌───────────┼───────────┐
          ▼           │           ▼
┌──────────────────┐  │  ┌──────────────────────┐
│  IF MCP selected │  │  │  IF FUSE selected    │
│  ────────────────│  │  │  ────────────────────│
│  kg oauth        │  │  │  install fuse3       │
│    create-mcp    │  │  │  pipx install kg-fuse│
│  print config    │  │  │  kg oauth create     │
│    snippet       │  │  │    --for fuse        │
└──────────────────┘  │  └──────────┬───────────┘
                      │             │
                      │             ▼
                      │    ┌──────────────────────┐
                      │    │  IF autostart wanted │
                      │    │  ────────────────────│
                      │    │  Linux: .desktop     │
                      │    │  macOS: launchd      │
                      │    └──────────────────────┘
                      │
                      ▼
              ┌───────────────┐
              │  Show Summary │
              └───────────────┘
```

**Branching Logic:**
- CLI is always installed (required for everything else)
- MCP OAuth only created if user selects MCP
- FUSE package + OAuth only installed if user selects FUSE
- FUSE autostart only configured if user wants it AND selected FUSE

**OAuth Commands:**
```bash
# For MCP server (creates OAuth client for AI assistants)
kg oauth create-mcp

# For FUSE driver (creates OAuth client for filesystem)
kg oauth create --for fuse
```

---

## Staged Verification

Each step is verified before proceeding:

| Step | Verification | Failure Action |
|------|--------------|----------------|
| API URL entered | `curl -s $API_URL/health` | Prompt to re-enter or continue anyway |
| CLI installed | `kg --version` | Abort with error |
| Login | `kg login` exit code | Prompt to re-enter credentials |
| Health check | `kg health` | Warn but continue (might be network issue) |
| FUSE installed | `kg-fuse --help` | Abort FUSE setup |
| FUSE OAuth | `kg oauth create` exit code | Warn, offer retry |

---

## Interactive Flow

### Phase 1: Detection & Mode Selection

```
┌─────────────────────────────────────────────────────────────────┐
│  Knowledge Graph Client Installer v0.1.0                        │
└─────────────────────────────────────────────────────────────────┘

Detecting environment...
  OS: Arch Linux (pacman)
  Node.js: v22.3.0 ✓
  Python: 3.12.1 ✓
  pipx: installed ✓
  Desktop: KDE Plasma

Checking existing installation...
  kg CLI: v0.6.5 (installed)
  kg-fuse: v0.1.1 (installed)

What would you like to do?
  (1) Upgrade existing installation
  (2) Reconfigure (change API URL, add components)
  (3) Uninstall
  (4) Fresh install (removes existing)

> 1
```

### Phase 2: Configuration (three-tier prompts)

```
Platform Configuration
──────────────────────

Knowledge Graph API URL
  Previous: https://kg.example.com/api
  Enter new value or press Enter to keep: _

Username
  Previous: admin
  Enter new value or press Enter to keep: _

Password: ********
```

### Phase 3: Component Selection

```
Components to Install
─────────────────────

[✓] CLI (kg command) - required
[✓] MCP Server configuration (for Claude, Cursor, etc.)
[ ] FUSE Driver (mount as filesystem)

Change selection? [y/N]: y

Install FUSE driver? [y/N]: y

FUSE Configuration
──────────────────

Mount directory
  Default: ~/Knowledge
  Enter path or press Enter for default: _

Start FUSE automatically on login? [y/N]: y
```

### Phase 4: Verification & Installation

```
Verifying API connection...
  Testing https://kg.example.com/api/health
  ✓ API reachable

Installing CLI...
  npm install -g @aaronsb/kg-cli --prefix ~/.local
  ✓ kg v0.6.5 installed

Authenticating...
  kg login -u admin --remember-username
  ✓ Logged in successfully

Verifying connection...
  kg health
  ✓ Platform healthy (125 concepts, 2 ontologies)

Installing FUSE driver...
  pipx install kg-fuse
  ✓ kg-fuse v0.1.1 installed

Configuring FUSE...
  kg oauth create --for fuse
  ✓ OAuth client created
  ✓ Config written to ~/.config/kg-fuse/config.toml

Setting up FUSE autostart...
  ✓ Created ~/.config/autostart/kg-fuse.desktop
```

### Phase 5: Summary

```
┌─────────────────────────────────────────────────────────────────┐
│  Installation Complete                                          │
└─────────────────────────────────────────────────────────────────┘

Installed:
  ✓ kg CLI v0.6.5
  ✓ kg-mcp-server (included with CLI)
  ✓ kg-fuse v0.1.1

Configuration:
  API URL: https://kg.example.com/api
  CLI config: ~/.config/kg/config.json
  FUSE config: ~/.config/kg-fuse/config.toml
  FUSE mount: ~/Knowledge (autostart enabled)

Quick start:
  kg health                    # Check connection
  kg search "topic"            # Search concepts
  kg-fuse ~/Knowledge          # Mount (or reboot for autostart)

MCP Server - add to your AI assistant config:
┌─────────────────────────────────────────────────────────────────┐
│  {                                                              │
│    "mcpServers": {                                              │
│      "knowledge-graph": {                                       │
│        "command": "kg-mcp-server"                               │
│      }                                                          │
│    }                                                            │
│  }                                                              │
└─────────────────────────────────────────────────────────────────┘

Save these settings for future installs/upgrades? [Y/n]: y
  ✓ Saved to ~/.config/kg/client-install.conf
```

---

## Command-Line Flags

```bash
# Fresh install (headless)
client-install.sh \
  --api-url https://kg.example.com/api \
  --username admin \
  --password secret \
  --install-fuse \
  --fuse-mount ~/Knowledge \
  --fuse-autostart

# Upgrade existing
client-install.sh --upgrade

# Uninstall
client-install.sh --uninstall [--remove-config]

# Check status
client-install.sh --status

# Use saved config
client-install.sh --config ~/.config/kg/client-install.conf
```

---

## FUSE Autostart

### Linux (KDE/GNOME)

Create `~/.config/autostart/kg-fuse.desktop`:

```ini
[Desktop Entry]
Type=Application
Name=Knowledge Graph FUSE
Comment=Mount knowledge graph filesystem
Exec=kg-fuse /home/USER/Knowledge
Terminal=false
StartupNotify=false
```

### macOS (launchd)

Create `~/Library/LaunchAgents/com.kg.fuse.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.kg.fuse</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/USER/.local/bin/kg-fuse</string>
        <string>/Users/USER/Knowledge</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
```

Load with: `launchctl load ~/Library/LaunchAgents/com.kg.fuse.plist`

---

## XDG Config Locations

| Component | Linux | macOS |
|-----------|-------|-------|
| CLI config | `~/.config/kg/config.json` | `~/Library/Application Support/kg/config.json` |
| FUSE config | `~/.config/kg-fuse/config.toml` | `~/Library/Application Support/kg-fuse/config.toml` |
| Installer config | `~/.config/kg/client-install.conf` | `~/Library/Application Support/kg/client-install.conf` |
| FUSE autostart | `~/.config/autostart/kg-fuse.desktop` | `~/Library/LaunchAgents/com.kg.fuse.plist` |

---

## Error Handling

| Error | Recovery |
|-------|----------|
| API unreachable | Prompt to re-enter URL or continue (configure later) |
| Auth failed | Prompt to re-enter credentials (3 attempts) |
| npm install fails | Check node version, offer to install node |
| pipx install fails | Check python version, offer to install pipx |
| FUSE mount fails | Check fuse installed, check permissions |
| macFUSE not approved | Guide user to System Preferences > Security |

---

## Code Style & Clarity

The script should be **inspectable and understandable** by users who want to verify what it does before running.

**Principles:**
- Clear section headers with `# ====` separators
- Inline comments explaining "why" not just "what"
- Each function has a docstring-style comment
- Branching logic is explicit with comments
- No obscure shell tricks - prefer readability

**Example:**
```bash
# ============================================================================
# INSTALL FUSE DRIVER
# ============================================================================
# Only runs if user selected FUSE. Installs the Python package and creates
# a dedicated OAuth client for filesystem access.

install_fuse() {
    # Skip if user didn't want FUSE
    if [ "$INSTALL_FUSE" != "true" ]; then
        log_info "Skipping FUSE installation (not selected)"
        return 0
    fi

    log_step "Installing FUSE driver"

    # Install system FUSE library (requires sudo)
    # This provides the kernel interface for userspace filesystems
    install_fuse_system_package

    # Install kg-fuse from PyPI via pipx
    # pipx isolates Python dependencies in its own virtualenv
    log_info "Installing kg-fuse..."
    if ! pipx install kg-fuse; then
        log_error "Failed to install kg-fuse"
        return 1
    fi

    # Create OAuth client specifically for FUSE
    # This is separate from the CLI credentials for security isolation
    log_info "Creating FUSE OAuth client..."
    if ! kg oauth create --for fuse; then
        log_error "Failed to create FUSE OAuth client"
        return 1
    fi

    log_success "FUSE driver installed"
}
```

---

## Implementation Tasks

### Phase 1: Script Skeleton
- [ ] Create `client-install.sh` with section structure
- [ ] Add version and header comments
- [ ] Port logging functions from `install.sh`
- [ ] Port prompt functions from `install.sh`
- [ ] Add config save/load functions

### Phase 2: Detection
- [ ] `detect_os()` - linux-arch, linux-ubuntu, linux-fedora, macos
- [ ] `detect_package_manager()` - pacman, apt, dnf, brew
- [ ] `detect_node()` - version check, PATH check
- [ ] `detect_python()` - version check (3.11+)
- [ ] `detect_pipx()` - installed check
- [ ] `detect_existing_install()` - kg version, kg-fuse version
- [ ] `detect_desktop_environment()` - KDE, GNOME, macOS

### Phase 3: Installation Functions
- [ ] `install_node()` - via package manager
- [ ] `install_pipx()` - via package manager
- [ ] `install_fuse_system_package()` - fuse3/macfuse
- [ ] `install_cli()` - npm install to ~/.local
- [ ] `install_fuse()` - pipx install kg-fuse

### Phase 4: Configuration Functions
- [ ] `configure_api_url()` - kg config set
- [ ] `authenticate()` - kg login with credentials
- [ ] `create_mcp_oauth()` - kg oauth create-mcp
- [ ] `create_fuse_oauth()` - kg oauth create --for fuse
- [ ] `configure_fuse_autostart()` - .desktop or launchd

### Phase 5: Verification Functions
- [ ] `verify_api_reachable()` - curl health endpoint
- [ ] `verify_cli_installed()` - kg --version
- [ ] `verify_logged_in()` - kg health
- [ ] `verify_fuse_installed()` - kg-fuse --help

### Phase 6: Main Flow
- [ ] Flag parsing (--api-url, --username, etc.)
- [ ] Mode detection (install/upgrade/uninstall/status)
- [ ] Interactive prompts with three-tier defaults
- [ ] Branching logic for component selection
- [ ] Summary display
- [ ] Config save prompt

### Phase 7: Testing
- [ ] Test fresh install on Arch Linux
- [ ] Test upgrade on Arch Linux
- [ ] Test uninstall on Arch Linux
- [ ] Test on Ubuntu (VM or container)
- [ ] Test on macOS (if available)

### Phase 8: Documentation
- [ ] Update docs/operating/ with client install guide
- [ ] Add to main README
- [ ] Update FUSE guide with new install method
