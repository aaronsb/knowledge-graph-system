# Client Installer Refactor: Platform Modules

## Goal

Reorganize client-install.sh to cleanly handle platform differences without spaghetti code.

## Key Insight

Two orthogonal dimensions:

| Dimension | Values | Governs |
|-----------|--------|---------|
| **Package Manager** | pacman, apt, dnf, brew | Installing packages (node, pipx, fuse3) |
| **Platform Family** | linux, macos | Service management, autostart, paths |

Desktop environment (KDE/GNOME/XFCE) doesn't matter because:
- XDG autostart spec works on all Linux desktops
- FUSE operations (fusermount) are the same across Linux

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     CONFIGURATION                                │
│  (Variables, URLs, package names - already at top)              │
├─────────────────────────────────────────────────────────────────┤
│                     UTILITIES                                    │
│  (Logging, prompts, config save/load - already exists)          │
├─────────────────────────────────────────────────────────────────┤
│                 PACKAGE MANAGER ADAPTERS                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │  pacman  │ │   apt    │ │   dnf    │ │   brew   │           │
│  ├──────────┤ ├──────────┤ ├──────────┤ ├──────────┤           │
│  │ _node()  │ │ _node()  │ │ _node()  │ │ _node()  │           │
│  │ _pipx()  │ │ _pipx()  │ │ _pipx()  │ │ _pipx()  │           │
│  │ _fuse()  │ │ _fuse()  │ │ _fuse()  │ │ _fuse()  │           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
├─────────────────────────────────────────────────────────────────┤
│                 PLATFORM FAMILY ADAPTERS                         │
│  ┌─────────────────────────┐ ┌─────────────────────────┐        │
│  │         linux           │ │         macos           │        │
│  ├─────────────────────────┤ ├─────────────────────────┤        │
│  │ _stop_fuse()            │ │ _stop_fuse()            │        │
│  │ _start_fuse()           │ │ _start_fuse()           │        │
│  │ _configure_autostart()  │ │ _configure_autostart()  │        │
│  │ _remove_autostart()     │ │ _remove_autostart()     │        │
│  │ _get_config_dir()       │ │ _get_config_dir()       │        │
│  └─────────────────────────┘ └─────────────────────────┘        │
├─────────────────────────────────────────────────────────────────┤
│                     DISPATCH LAYER                               │
│  install_node()      → ${PKG_MGR}_install_node                  │
│  install_pipx()      → ${PKG_MGR}_install_pipx                  │
│  stop_fuse()         → ${PLATFORM}_stop_fuse                    │
│  start_fuse()        → ${PLATFORM}_start_fuse                   │
│  configure_autostart → ${PLATFORM}_configure_autostart          │
├─────────────────────────────────────────────────────────────────┤
│                     INSTALLATION LOGIC                           │
│  (Prerequisites, clients, OAuth - uses dispatch layer)          │
├─────────────────────────────────────────────────────────────────┤
│                     MAIN FLOW                                    │
│  (Detection, lifecycle menu, mode handlers)                     │
└─────────────────────────────────────────────────────────────────┘
```

## Variables

```bash
# Detected during init
DETECTED_OS=""           # linux-arch, linux-ubuntu, linux-fedora, macos
DETECTED_PKG_MGR=""      # pacman, apt, dnf, brew
DETECTED_DESKTOP=""      # kde, gnome, xfce, macos (informational only)

# Derived for dispatch
PLATFORM_FAMILY=""       # linux, macos (for service management)
```

## Package Manager Adapters

Each package manager gets these functions:

```bash
# Pattern: {pkg_mgr}_install_{package}

pacman_install_node()     # sudo pacman -S --noconfirm nodejs npm
pacman_install_pipx()     # sudo pacman -S --noconfirm python-pipx
pacman_install_fuse()     # sudo pacman -S --noconfirm fuse3

apt_install_node()        # NodeSource setup + apt install
apt_install_pipx()        # sudo apt install -y pipx
apt_install_fuse()        # sudo apt install -y fuse3

dnf_install_node()        # sudo dnf install -y nodejs npm
dnf_install_pipx()        # sudo dnf install -y pipx
dnf_install_fuse()        # sudo dnf install -y fuse3

brew_install_node()       # brew install node
brew_install_pipx()       # brew install pipx
brew_install_fuse()       # brew install --cask macfuse
```

## Platform Family Adapters

Each platform family gets these functions:

```bash
# Pattern: {platform}_action()

# Linux - uses XDG standards
linux_stop_fuse()              # fusermount -u or fusermount3 -u
linux_start_fuse()             # nohup kg-fuse $mount_dir &
linux_configure_autostart()    # ~/.config/autostart/kg-fuse.desktop
linux_remove_autostart()       # rm ~/.config/autostart/kg-fuse.desktop
linux_get_config_dir()         # ${XDG_CONFIG_HOME:-~/.config}/kg

# macOS - uses launchd and Library paths
macos_stop_fuse()              # umount or diskutil unmount
macos_start_fuse()             # nohup or launchctl
macos_configure_autostart()    # ~/Library/LaunchAgents/com.kg.fuse.plist
macos_remove_autostart()       # launchctl unload + rm plist
macos_get_config_dir()         # ~/Library/Application Support/kg
```

## Dispatch Functions

Simple dispatch based on detected values:

```bash
install_node() {
    local fn="${DETECTED_PKG_MGR}_install_node"
    if declare -f "$fn" > /dev/null; then
        "$fn"
    else
        log_error "No install_node adapter for $DETECTED_PKG_MGR"
        return 1
    fi
}

stop_fuse() {
    local fn="${PLATFORM_FAMILY}_stop_fuse"
    "$fn" "$@"
}
```

## Implementation Order

1. [ ] Add PLATFORM_FAMILY derivation to detection
2. [ ] Create package manager adapter section with all functions
3. [ ] Create platform family adapter section with all functions
4. [ ] Create dispatch layer
5. [ ] Update existing code to use dispatch functions
6. [ ] Test on Arch (pacman + linux)
7. [ ] Test on macOS (brew + macos) - if available
8. [ ] Clean up old inline case statements

## File Organization

Keep everything in single file (for curl|bash), but with clear section markers:

```bash
# ============================================================================
# SECTION: PACKAGE MANAGER ADAPTERS - PACMAN (Arch Linux)
# ============================================================================

# ============================================================================
# SECTION: PACKAGE MANAGER ADAPTERS - APT (Ubuntu/Debian)
# ============================================================================

# ============================================================================
# SECTION: PACKAGE MANAGER ADAPTERS - DNF (Fedora/RHEL)
# ============================================================================

# ============================================================================
# SECTION: PACKAGE MANAGER ADAPTERS - BREW (macOS)
# ============================================================================

# ============================================================================
# SECTION: PLATFORM ADAPTERS - LINUX
# ============================================================================

# ============================================================================
# SECTION: PLATFORM ADAPTERS - MACOS
# ============================================================================

# ============================================================================
# SECTION: DISPATCH LAYER
# ============================================================================
```

## Benefits

- **Isolation**: Each adapter is self-contained
- **Testability**: Can test adapters individually
- **Extensibility**: Add new package manager = add one section
- **Readability**: Clear where to look for platform-specific code
- **Single file**: Still works with curl|bash
