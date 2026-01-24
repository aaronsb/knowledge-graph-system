# FUSE Filesystem Guide

**Browse your knowledge graph like a filesystem.**

The FUSE driver (`kg-fuse`) mounts your knowledge graph as a virtual filesystem. Navigate ontologies, create semantic queries with `mkdir`, and configure searches through simple file operations.

## Prerequisites

- Linux with FUSE3 library
- Python 3.11+
- Running Knowledge Graph API
- `kg` CLI (for OAuth setup)

## Installation

### 1. Install System Dependencies

```bash
# Arch Linux
sudo pacman -S fuse3

# Debian/Ubuntu
sudo apt install fuse3

# Fedora
sudo dnf install fuse3
```

### 2. Install kg CLI (if not already installed)

```bash
npm install -g @aaronsb/kg-cli
```

### 3. Install kg-fuse

```bash
pipx install kg-fuse
```

### Upgrade

```bash
pipx upgrade kg-fuse
```

## Setup

### 1. Create OAuth Credentials

```bash
kg oauth create --for fuse
```

This writes credentials to `~/.config/kg-fuse/config.toml`.

### 2. Create Mount Point

```bash
sudo mkdir -p /mnt/knowledge
sudo chown $USER:$USER /mnt/knowledge
```

### 3. Mount the Filesystem

```bash
# Mount (runs in background by default)
kg-fuse /mnt/knowledge

# Or run in foreground for debugging
kg-fuse /mnt/knowledge -f
```

### 4. Unmount When Done

```bash
# Normal unmount
fusermount -u /mnt/knowledge

# Force unmount if stuck
fusermount -uz /mnt/knowledge
```

## Filesystem Structure

```
/mnt/knowledge/
├── ontology/                          # System-managed (read-only structure)
│   ├── Strategy-As-Code/              # Ontology from your graph
│   │   ├── documents/                 # Source documents (read-only)
│   │   │   └── whitepaper.md          # Original ingested document
│   │   └── leadership/                # Your query (created with mkdir)
│   │       ├── .meta/                 # Query control plane
│   │       │   ├── limit              # Max results (default: 50)
│   │       │   ├── threshold          # Min similarity (default: 0.7)
│   │       │   ├── exclude            # Terms to exclude
│   │       │   ├── union              # Terms to add
│   │       │   └── query.toml         # Full query state (read-only)
│   │       └── Leadership.concept.md  # Search results
│   └── test-concepts/
│       └── documents/
│
└── my-research/                       # Global query (all ontologies)
    ├── .meta/
    └── Results.concept.md
```

## Basic Usage

### Browse Ontologies

```bash
# List all ontologies
ls /mnt/knowledge/ontology/

# List documents in an ontology
ls /mnt/knowledge/ontology/Strategy-As-Code/documents/

# Read a source document
cat /mnt/knowledge/ontology/Strategy-As-Code/documents/whitepaper.md
```

### Create Queries

Directories you create become semantic searches. The directory name is the search term.

```bash
# Scoped query (searches only this ontology)
mkdir /mnt/knowledge/ontology/Strategy-As-Code/leadership
ls /mnt/knowledge/ontology/Strategy-As-Code/leadership/
# Shows: .meta/  Leadership.concept.md  Strategy.concept.md  ...

# Global query (searches all ontologies)
mkdir /mnt/knowledge/machine-learning
ls /mnt/knowledge/machine-learning/
# Shows results from every ontology
```

### Read Concept Files

Concept files (`.concept.md`) contain full details with YAML frontmatter:

```bash
cat /mnt/knowledge/ontology/Strategy-As-Code/leadership/Leadership.concept.md
```

Output:
```yaml
---
id: sha256:abc123...
label: Leadership
grounding: 0.82
documents:
  - Strategy-As-Code
sources:
  - whitepaper.md
relationships:
  - type: IMPLIES
    target: Strategy
---

# Leadership

## Evidence

### Instance 1 from whitepaper.md (para 3)
> Leadership in technology organizations requires...
```

### Nested Queries (AND Logic)

Each directory level adds an AND constraint:

```bash
mkdir /mnt/knowledge/ontology/Strategy-As-Code/leadership
mkdir /mnt/knowledge/ontology/Strategy-As-Code/leadership/communication

# Results match "leadership" AND "communication"
ls /mnt/knowledge/ontology/Strategy-As-Code/leadership/communication/
```

### Remove Queries

```bash
rmdir /mnt/knowledge/ontology/Strategy-As-Code/leadership
# Also removes nested queries (leadership/communication, etc.)
```

## Query Configuration (.meta)

Every query directory has a `.meta/` subdirectory with virtual configuration files.

### View Current Settings

```bash
cat .meta/limit      # Shows: "# Maximum number of concepts...\n50"
cat .meta/threshold  # Shows: "# Minimum similarity...\n0.7"
cat .meta/query.toml # Shows full query state (read-only)
```

### Modify Settings

```bash
# Set result limit
echo 20 > .meta/limit

# Set minimum similarity (0.0-1.0)
echo 0.85 > .meta/threshold

# Exclude terms (semantic NOT)
echo "deprecated" >> .meta/exclude
echo "legacy" >> .meta/exclude

# Add terms (semantic OR)
echo "management" >> .meta/union

# View combined state
cat .meta/query.toml
```

### Clear Lists

```bash
# Clear exclude list (truncate to empty)
: > .meta/exclude

# Clear union list
: > .meta/union
```

### Configuration Reference

| File | Type | Read | Write | Effect |
|------|------|------|-------|--------|
| `limit` | Integer | Current value | Set new value | Max results returned |
| `threshold` | Float (0.0-1.0) | Current value | Set new value | Min similarity score |
| `exclude` | Text (lines) | Current terms | Append term | Semantic NOT filter |
| `union` | Text (lines) | Current terms | Append term | Semantic OR expansion |
| `query.toml` | TOML | Full state | — | Debug view (read-only) |

## Example Workflows

### Research Workflow

```bash
# Mount
kg-fuse /mnt/kg

# Create focused research query
mkdir /mnt/kg/ontology/Strategy-As-Code/governance
cd /mnt/kg/ontology/Strategy-As-Code/governance

# Tune for precision
echo 0.8 > .meta/threshold
echo 10 > .meta/limit

# Exclude irrelevant terms
echo "compliance" >> .meta/exclude

# Review results
ls *.concept.md
cat "Risk Management.concept.md"

# Drill down
mkdir risk
ls risk/
```

### Cross-Ontology Analysis

```bash
# Global query searches everything
mkdir /mnt/kg/distributed-systems
cd /mnt/kg/distributed-systems

# Check what ontologies contributed
cat .meta/query.toml

# Read concepts from multiple sources
cat "Consensus.concept.md"  # Might be from different ontologies
```

### Quick Exploration

```bash
# Fast browse with low threshold
mkdir /mnt/kg/ontology/my-ont/broad-search
echo 0.3 > /mnt/kg/ontology/my-ont/broad-search/.meta/threshold
echo 100 > /mnt/kg/ontology/my-ont/broad-search/.meta/limit
ls /mnt/kg/ontology/my-ont/broad-search/
```

## Write Support (Ingestion)

The FUSE driver supports document ingestion through standard file operations.

### Create an Ontology

```bash
# Create a new ontology (directory under /ontology/)
mkdir /mnt/kg/ontology/my-new-ontology
```

### Ingest Documents

Copy files directly into an ontology directory to trigger ingestion:

```bash
# Copy a document to ingest it
cp research-paper.md /mnt/kg/ontology/my-new-ontology/

# The file "disappears" after ingestion (black hole semantics)
# It will appear in documents/ once processing completes
ls /mnt/kg/ontology/my-new-ontology/documents/
```

**How it works:**
1. `cp` creates a temporary file and writes content
2. On file close, content is POSTed to `/ingest` API
3. Ingestion is auto-approved (no manual approval needed)
4. File disappears from ontology root
5. After processing, document appears in `documents/`

### Batch Ingestion

```bash
# Ingest multiple documents
for f in papers/*.md; do
    cp "$f" /mnt/kg/ontology/research/
done

# Check job status
kg job list
```

## Troubleshooting

### Mount Fails

```bash
# Check if already mounted
mount | grep kg-fuse

# Force unmount stale mount
fusermount -uz /mnt/knowledge

# Check API is running
curl https://kg.example.com/api/health
```

### Permission Errors

```bash
# Ensure you have FUSE access
groups  # Should include 'fuse' group

# Check mount point is empty directory you own
ls -la /mnt/knowledge
```

### Transport Endpoint Not Connected

This happens when the FUSE process dies but the mount remains:

```bash
fusermount -uz /mnt/knowledge
kg-fuse /mnt/knowledge
```

### Query Returns No Results

```bash
# Check query settings
cat .meta/query.toml

# Lower threshold
echo 0.3 > .meta/threshold

# Verify ontology has documents
ls ../documents/
```

## Architecture Notes

- **Hologram model**: Documents and concepts are read-only projections from the graph
- **Write as ingestion**: Writing to ontology directories triggers document ingestion
- **Client-side queries**: Query definitions stored in `~/.local/share/kg-fuse/queries.toml`
- **Caching**: Results cached for 30 seconds to reduce API calls
- **OAuth**: Uses standard OAuth 2.0 client credentials flow

## Related Documentation

- [ADR-069: Semantic FUSE Filesystem](../architecture/user-interfaces/ADR-069-semantic-fuse-filesystem.md) - Design rationale
- [ADR-069a: Implementation Specifics](../architecture/user-interfaces/ADR-069a-fuse-implementation-specifics.md) - Technical details
