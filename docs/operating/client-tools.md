# Client Tools

Tools for connecting to a Knowledge Graph platform.

## Installation

### All-in-one Installer

```bash
curl -fsSL https://raw.githubusercontent.com/aaronsb/knowledge-graph-system/main/client-manager.sh | bash
```

This interactive installer:
- Detects your OS (Arch, Ubuntu, Fedora, macOS)
- Installs prerequisites if needed (Node.js, pipx)
- Installs the kg CLI from npm
- Optionally installs the FUSE driver from PyPI
- Configures authentication

### Manual Installation

**kg CLI only:**
```bash
npm install -g @aaronsb/kg-cli
kg config set api_url https://kg.example.com/api
kg login
```

**FUSE driver:**
```bash
pipx install kg-fuse
```

## Components

### kg CLI

Command-line interface for the knowledge graph.

```bash
kg health              # Check connection
kg search "query"      # Search concepts
kg ingest file.pdf     # Ingest documents
kg --help              # All commands
```

See [CLI Reference](../reference/cli/README.md) for full documentation.

### MCP Server

Enables AI assistants (Claude, etc.) to use the knowledge graph.

```bash
kg mcp-config          # Configure for Claude Desktop
kg oauth create-mcp    # Create MCP OAuth client
```

See [MCP Reference](../reference/mcp/README.md) for tool documentation.

### FUSE Filesystem

Mount the knowledge graph as a filesystem.

```bash
kg-fuse ~/Knowledge    # Mount at ~/Knowledge
ls ~/Knowledge/        # Browse ontologies
cat ~/Knowledge/query/your\ search  # Semantic queries
```

See [FUSE Guide](../guides/FUSE_FILESYSTEM.md) for details.

## Upgrading

```bash
# Using the installer
./client-manager.sh --upgrade

# Manual
npm update -g @aaronsb/kg-cli
pipx upgrade kg-fuse
```

## Uninstalling

```bash
# Using the installer
./client-manager.sh --uninstall

# Manual
npm uninstall -g @aaronsb/kg-cli
pipx uninstall kg-fuse
```

## Troubleshooting

### "Command not found" after installation

Ensure `~/.local/bin` is in your PATH:
```bash
export PATH="$HOME/.local/bin:$PATH"
```

Add to your shell profile (`~/.bashrc`, `~/.zshrc`) for persistence.

### Authentication issues

```bash
kg logout              # Clear credentials
kg login               # Re-authenticate
```

### Connection refused

Check the API URL:
```bash
kg config get api_url
curl -s https://kg.example.com/api/health
```
