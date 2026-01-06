# FUSE Filesystem Guide

**Browse your knowledge graph like a filesystem.**

The FUSE driver (`kg-fuse`) mounts your knowledge graph as a virtual filesystem. Navigate ontologies, create semantic queries with `mkdir`, and configure searches through simple file operations.

## Prerequisites

- Linux with FUSE support (most distributions)
- Python 3.11+
- Running Knowledge Graph API (`./operator.sh start`)
- OAuth credentials for FUSE access

## Installation

```bash
# Install with pipx (recommended)
cd fuse/
pipx install .

# Or with pip
pip install .
```

## Setup

### 1. Create OAuth Credentials

```bash
# Generate FUSE-specific OAuth client
kg oauth create --for fuse

# This writes to ~/.config/kg/config.json with client_id and client_secret
```

### 2. Mount the Filesystem

```bash
# Mount to any empty directory
kg-fuse /mnt/knowledge

# Or with explicit config path
kg-fuse --config ~/.config/kg/config.json /mnt/knowledge
```

### 3. Unmount When Done

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

## Troubleshooting

### Mount Fails

```bash
# Check if already mounted
mount | grep kg-fuse

# Force unmount stale mount
fusermount -uz /mnt/knowledge

# Check API is running
curl http://localhost:8000/health
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

- **Read-only hologram**: Documents and concepts are read-only projections from the graph
- **Client-side queries**: Query definitions stored in `~/.local/share/kg-fuse/queries.toml`
- **Caching**: Results cached for 30 seconds to reduce API calls
- **OAuth**: Uses standard OAuth 2.0 client credentials flow

## Related Documentation

- [ADR-069: Semantic FUSE Filesystem](../architecture/user-interfaces/ADR-069-semantic-fuse-filesystem.md) - Design rationale
- [ADR-069a: Implementation Specifics](../architecture/user-interfaces/ADR-069a-fuse-implementation-specifics.md) - Technical details
