# Knowledge Graph FUSE Driver

Mount the knowledge graph as a filesystem.

## Installation

```bash
# System dependency
sudo pacman -S fuse3  # Arch
sudo apt install fuse3  # Debian/Ubuntu

# Install kg-fuse
cd fuse
pip install -e .
```

## Usage

First, create OAuth credentials for the FUSE client:

```bash
kg auth client create --name fuse-client --scopes read write
```

Then mount:

```bash
kg-fuse /mnt/knowledge \
  --api-url http://localhost:8000 \
  --client-id fuse-client \
  --client-secret YOUR_SECRET
```

Unmount with:

```bash
fusermount -u /mnt/knowledge
# or just Ctrl+C if running in foreground
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

See ADR-069 for full design rationale.
