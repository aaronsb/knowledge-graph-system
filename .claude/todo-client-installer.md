# Client Installer Architecture

## Overview

A user-friendly installer for Knowledge Graph clients (CLI, MCP server, FUSE driver).

**One-liner install:**
```bash
curl -fsSL https://raw.githubusercontent.com/aaronsb/knowledge-graph-system/main/client-install.sh | bash
```

---

## What Gets Installed

| Component | Source | Install Method | Root Required |
|-----------|--------|----------------|---------------|
| **fuse3** | System package | pacman/apt/dnf | Yes |
| **kg CLI** | npm | `npm install -g` to ~/.local | No |
| **kg-mcp-server** | npm (same package) | Included with CLI | No |
| **kg-fuse** | PyPI | `pipx install` | No |

---

## Bootstrap Chain

The CLI is the keystone - it's needed to authenticate and create OAuth clients for other components.

**Key insight:** After `kg login`, credentials are cached. All subsequent `kg` commands work without re-authenticating.

```
┌─────────────────────────────────────────────────────────────────┐
│  1. Install CLI                                                 │
│     npm install -g @aaronsb/kg-cli --prefix ~/.local            │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. Configure & Authenticate (ONE TIME - caches credentials)    │
│     kg config set api-url https://kg.example.com/api            │
│     kg login -u admin -p secret --remember-username             │
│     → Creates OAuth client, stores in ~/.config/kg/config.json  │
└─────────────────────┬───────────────────────────────────────────┘
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
┌──────────────────────┐  ┌──────────────────────┐
│  3a. MCP Setup       │  │  3b. FUSE Setup      │
│  (no auth needed -   │  │  pipx install kg-fuse│
│   uses cached creds) │  │  kg oauth create     │
│  kg mcp-config       │  │    --for fuse        │
└──────────────────────┘  └──────────────────────┘
```

**Non-interactive login (for scripted install):**
```bash
kg login -u "$USERNAME" -p "$PASSWORD" --remember-username
```

---

## Proposed Flow

### Phase 1: Environment Detection

```
Detecting environment...
  OS: Arch Linux
  Package manager: pacman
  Node.js: v22.3.0 ✓
  Python: 3.11.8 ✓
  pipx: installed ✓
```

**Missing prerequisites:**
- If Node.js missing: offer to install via package manager
- If Python < 3.11: warn, offer to continue anyway
- If pipx missing: offer to install

### Phase 2: Configuration

```
┌─────────────────────────────────────────────────────────────────┐
│  Knowledge Graph Client Installer                               │
└─────────────────────────────────────────────────────────────────┘

What's your Knowledge Graph API URL?
  > https://kg.example.com/api

What would you like to install?
  [x] CLI (kg command - required)
  [x] MCP Server (for AI assistants like Claude)
  [x] FUSE Driver (mount as filesystem)

Note: FUSE requires the fuse3 system package (needs sudo).
```

### Phase 3: System Dependencies (if FUSE selected)

```
Installing system dependencies...

The FUSE driver requires fuse3. This needs sudo access.
  sudo pacman -S fuse3

Continue? [Y/n]
```

### Phase 4: User-level Installation

```
Installing CLI...
  npm install -g @aaronsb/kg-cli --prefix ~/.local
  ✓ kg command available

Installing FUSE driver...
  pipx install kg-fuse
  ✓ kg-fuse command available
```

### Phase 5: Authentication

```
┌─────────────────────────────────────────────────────────────────┐
│  Authentication                                                 │
└─────────────────────────────────────────────────────────────────┘

To configure the clients, you need to authenticate with the platform.

How would you like to authenticate?
  (1) Browser login (opens browser for OAuth)
  (2) Admin password (for headless/server environments)

> 1

Opening browser for authentication...
  ✓ Logged in as aaron@example.com
```

### Phase 6: Client Configuration

```
Configuring MCP server...
  ✓ Config written to ~/.config/kg/mcp.json

Configuring FUSE driver...
  Creating OAuth client for FUSE...
  ✓ Config written to ~/.config/kg-fuse/config.toml
```

### Phase 7: Summary

```
┌─────────────────────────────────────────────────────────────────┐
│  Installation Complete                                          │
└─────────────────────────────────────────────────────────────────┘

Installed:
  ✓ kg CLI (v0.6.4)
  ✓ kg-mcp-server (included with CLI)
  ✓ kg-fuse (v0.1.1)

Configuration:
  API URL: https://kg.example.com/api
  CLI config: ~/.config/kg/config.json
  FUSE config: ~/.config/kg-fuse/config.toml

Quick start:
  kg health              # Check connection
  kg search "topic"      # Search concepts
  kg-fuse /mnt/kg        # Mount filesystem

MCP Server (add to Claude config):
  {
    "mcpServers": {
      "knowledge-graph": {
        "command": "kg-mcp-server"
      }
    }
  }

To uninstall:
  client-install.sh --uninstall
```

---

## XDG Config Locations

| Component | Config Path | Created By |
|-----------|-------------|------------|
| CLI | `~/.config/kg/config.json` | `kg login` |
| MCP | `~/.config/kg/mcp.json` | `kg mcp-config` |
| FUSE | `~/.config/kg-fuse/config.toml` | `kg oauth create --for fuse` |
| Installer state | `~/.config/kg/installer.conf` | `client-install.sh` |

---

## Uninstall Support

```bash
client-install.sh --uninstall
```

```
What would you like to uninstall?
  [x] CLI
  [x] MCP Server (included with CLI)
  [x] FUSE Driver
  [ ] Configuration files (keep by default)

Uninstalling...
  npm uninstall -g @aaronsb/kg-cli
  pipx uninstall kg-fuse
  ✓ Uninstalled (config files preserved)

To remove config files:
  rm -rf ~/.config/kg ~/.config/kg-fuse
```

---

## Package Manager Support

| Distro | Package Manager | fuse3 Package | Node Install |
|--------|-----------------|---------------|--------------|
| Arch | pacman | `fuse3` | `nodejs npm` |
| Ubuntu/Debian | apt | `fuse3` | `nodejs npm` |
| Fedora/RHEL | dnf | `fuse3` | `nodejs npm` |
| macOS | brew | `macfuse` (limited) | `node` |

---

## Edge Cases to Handle

1. **No platform yet**: User might be installing clients before platform is ready
   - Allow skipping auth, configure API URL only
   - Can run `kg login` later

2. **Multiple platforms**: User might have multiple KG instances
   - Support profiles? (`kg --profile work`)
   - Or just document re-running installer

3. **Corporate proxy**: npm/pip might need proxy config
   - Detect from environment variables
   - Document manual workarounds

4. **Existing installation**: Upgrade vs fresh install
   - Detect existing versions
   - Offer upgrade path

5. **PATH issues**: ~/.local/bin not in PATH
   - Detect and warn
   - Offer to add to shell rc file

---

## Questions for Discussion

1. **Single script or modular?**
   - Single `client-install.sh` (simpler)
   - vs. `install-cli.sh`, `install-fuse.sh` (more flexible)

2. **Profile support?**
   - Do we need multiple platform profiles now?
   - Or defer to future version?

3. **Offline/air-gapped support?**
   - Download tarballs for npm/pip?
   - Or document manual process only?

4. **MCP config format?**
   - Auto-detect Claude Desktop location?
   - Or just print config snippet to copy?

5. **Version pinning?**
   - Install latest by default?
   - Or pin to tested versions?
