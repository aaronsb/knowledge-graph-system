# Installation Scripts

End-user installation scripts for deploying the Knowledge Graph system.

## Overview

Installation scripts provide a simple, one-command way to get the system running. They combine building and deployment steps with initialization and verification.

## Scripts

### `install-local.sh`
Install from locally built source:
```bash
./install-local.sh [options]
```

Options:
- `--prefix <path>` - Installation directory (default: `/usr/local`)
- `--skip-database` - Don't set up database
- `--skip-cli` - Don't install CLI tool
- `--dev` - Development mode (no optimizations)

Use case:
- Testing local changes before release
- Development environments
- Air-gapped deployments

### `install-remote.sh`
Install from GitHub release:
```bash
./install-remote.sh [options]
```

Options:
- `--version <tag>` - Version to install (e.g., v0.2.0)
- `--latest` - Install latest release (default)
- `--prefix <path>` - Installation directory
- `--no-docker` - Skip Docker components

Use case:
- Production deployments
- End-user installations
- CI/CD deployments

## Quick Start

### For End Users (Recommended)
```bash
# Install latest release
curl -fsSL https://raw.githubusercontent.com/aaronsb/knowledge-graph-system/main/build/install/install-remote.sh | bash

# Or specific version
curl -fsSL https://raw.githubusercontent.com/aaronsb/knowledge-graph-system/main/build/install/install-remote.sh | bash -s -- --version v0.2.0
```

### For Developers
```bash
# Clone repo first
git clone https://github.com/aaronsb/knowledge-graph-system.git
cd knowledge-graph-system

# Install from source
./build/install/install-local.sh
```

## What Gets Installed

### System Components
- **Database** (Docker container)
  - PostgreSQL 16 + Apache AGE
  - Data volume: `/var/lib/postgresql/data`

- **API Server** (Docker container or systemd service)
  - FastAPI server
  - Python dependencies
  - Configuration in `/etc/kg/`

- **CLI Tool** (Binary)
  - Installed to `$PREFIX/bin/kg`
  - Shell completions (bash, zsh, fish)

- **MCP Server** (Binary)
  - Installed to `$PREFIX/bin/kg-mcp-server`
  - Claude Desktop integration

### Configuration Files
- `/etc/kg/config.yml` - System configuration
- `~/.kg/` - User-specific settings
- `.env` - Environment variables (local mode only)

### Data Directories
- `/var/lib/kg/` - System data
- `~/.kg/data/` - User data (embeddings cache, etc.)
- `logs/` - Log files

## Installation Process

Both scripts follow similar steps:

1. **Prerequisites Check**
   - Verify Docker installed
   - Check disk space
   - Validate permissions

2. **Download/Build**
   - Remote: Pull from GitHub
   - Local: Build from source

3. **Install Components**
   - Database container
   - API server
   - CLI + MCP tools

4. **Initialize System**
   - Start services
   - Run migrations
   - Seed data

5. **Verify Installation**
   - Health checks
   - Test connections
   - Display status

## Configuration

### During Installation
```bash
# Interactive configuration
./install-remote.sh --configure

# Non-interactive (use defaults)
./install-remote.sh --yes

# Custom configuration file
./install-remote.sh --config /path/to/config.yml
```

### After Installation
```bash
# Edit system config
sudo vim /etc/kg/config.yml

# Edit user config
vim ~/.kg/config.yml

# Reconfigure
kg config set api.url http://localhost:8000
```

## Verification

After installation, verify the system:

```bash
# Check version
kg --version

# Check health
kg health

# Test database
kg database stats

# Run sample query
kg search query "test"
```

## Uninstallation

To remove the system:

```bash
# Stop services
docker-compose down

# Remove Docker volumes (data will be lost!)
docker volume prune

# Remove binaries
sudo rm /usr/local/bin/kg
sudo rm /usr/local/bin/kg-mcp-server

# Remove config
sudo rm -rf /etc/kg
rm -rf ~/.kg

# Remove system data
sudo rm -rf /var/lib/kg
```

Or use the uninstall script (if provided):
```bash
./uninstall.sh
```

## Upgrading

### From Local Installation
```bash
# Pull latest changes
git pull origin main

# Rebuild and reinstall
./build/install/install-local.sh --upgrade
```

### From Remote Installation
```bash
# Upgrade to latest
./build/install/install-remote.sh --upgrade

# Upgrade to specific version
./build/install/install-remote.sh --upgrade --version v0.2.1
```

## Troubleshooting

### Installation fails with "permission denied"
```bash
# Run with sudo
sudo ./install-remote.sh

# Or install to user directory
./install-remote.sh --prefix ~/.local
```

### Docker not found
```bash
# Install Docker first
curl -fsSL https://get.docker.com | sh

# Or follow official instructions
# https://docs.docker.com/get-docker/
```

### Port conflicts
```bash
# Check ports before installing
lsof -i :8000  # API
lsof -i :5432  # PostgreSQL

# Or specify different ports
./install-remote.sh --api-port 8001 --db-port 5433
```

### Installation hangs
```bash
# Check logs
tail -f /tmp/kg-install.log

# Increase timeout
./install-remote.sh --timeout 600
```

## Platform Support

| Platform | Local Install | Remote Install | Status |
|----------|---------------|----------------|--------|
| Linux (x64) | ✓ | ✓ | Tested |
| Linux (ARM64) | ✓ | ✓ | Tested |
| macOS (Intel) | ✓ | ✓ | Tested |
| macOS (Apple Silicon) | ✓ | ✓ | Tested |
| Windows (WSL2) | ✓ | ✓ | Tested |
| Windows (native) | ⏳ | ⏳ | Planned |

## See Also

- [Deployment Guide](../../docs/guides/DEPLOYMENT.md)
- [Build Scripts](../local/README.md)
- [Configuration Reference](../../docs/reference/configuration.md)
