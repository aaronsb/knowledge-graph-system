# Knowledge Graph FUSE Driver

Mount the knowledge graph as a filesystem.

## Installation

### Prerequisites

**System FUSE library** (required):
```bash
sudo pacman -S fuse3       # Arch
sudo apt install fuse3     # Debian/Ubuntu
sudo dnf install fuse3     # Fedora
```

**kg CLI** (for OAuth setup):
```bash
npm install -g @aaronsb/kg-cli
```

### Install kg-fuse

```bash
pipx install kg-fuse
```

### Upgrade

```bash
pipx upgrade kg-fuse
```

## Setup

Create OAuth credentials (one-time):

```bash
kg oauth create --for fuse
```

This writes credentials to `~/.config/kg-fuse/config.toml`.

## Usage

```bash
# Mount (reads credentials from config)
kg-fuse /mnt/knowledge

# Or run in foreground for debugging
kg-fuse /mnt/knowledge -f
```

Unmount:

```bash
fusermount -u /mnt/knowledge
# or just Ctrl+C if running in foreground
```

### Manual Credentials

You can also pass credentials directly:

```bash
kg-fuse /mnt/knowledge \
  --api-url https://kg.example.com/api \
  --client-id YOUR_CLIENT_ID \
  --client-secret YOUR_SECRET
```

## Filesystem Structure

```
/mnt/knowledge/
├── ontology-a/          # Each ontology is a directory
│   ├── doc1.md          # Documents in that ontology
│   └── doc2.md
└── ontology-b/
    └── doc3.md
```

### Read: Browse Documents

```bash
ls /mnt/knowledge/                    # List ontologies
ls /mnt/knowledge/my-ontology/        # List documents
cat /mnt/knowledge/my-ontology/doc.md # Read document
```

### Write: Ingest Documents (future)

```bash
cp report.pdf /mnt/knowledge/my-ontology/
# File "disappears" into ingestion pipeline
# Creates job, extracts concepts, links to graph
```

## Debug Mode

```bash
kg-fuse /mnt/knowledge --debug -f
```

## Architecture

The FUSE driver is an independent client that:
- Authenticates via OAuth (like CLI, MCP server)
- Makes HTTP requests to the API server
- Caches directory listings (30s TTL)
- Defaults to `localhost:8000` if unconfigured (fail-safe: won't accidentally query external endpoints)

See ADR-069 for full design rationale.
