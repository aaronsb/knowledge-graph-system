# FUSE Filesystem Guide

**Browse your knowledge graph like a filesystem.**

The FUSE driver (`kg-fuse`) mounts your knowledge graph as a virtual filesystem. Navigate ontologies, create semantic queries with `mkdir`, ingest documents by copying files, and configure searches through simple file operations — all from your terminal or file manager.

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
# or
kg-fuse update
```

## Setup

### 1. Create OAuth Credentials

```bash
kg oauth create --for fuse
```

### 2. Initialize a Mount

```bash
kg-fuse init ~/Knowledge
```

This validates the path, detects credentials, and optionally sets up autostart.

### 3. Mount and Unmount

```bash
kg-fuse mount           # Start all configured mounts
kg-fuse unmount         # Stop all mounts
kg-fuse status          # Check what's running
```

## Filesystem Structure

```
~/Knowledge/
├── ontology/                              # System-managed ontology listing
│   ├── Machine Intelligence/              # An ontology from your graph
│   │   ├── .ontology                      # Ontology stats (concepts, docs, relationships)
│   │   ├── documents/                     # Source documents (read-only)
│   │   │   ├── .documents                 # Document listing with count
│   │   │   ├── research-paper.md          # Text document content
│   │   │   └── diagram.png               # Image document (raw bytes)
│   │   ├── ingest/                        # Drop box for new documents
│   │   │   ├── .ingest                    # Usage instructions
│   │   │   └── paper.md.ingesting         # Job status (appears during processing)
│   │   └── neural networks/               # Your query (created with mkdir)
│   │       ├── .meta/                     # Query control plane
│   │       │   ├── limit                  # Max results (default: 50)
│   │       │   ├── threshold              # Min similarity (default: 0.7)
│   │       │   ├── exclude                # Terms to exclude (NOT)
│   │       │   ├── union                  # Terms to add (OR)
│   │       │   └── query.toml             # Full query state (read-only)
│   │       ├── images/                    # Image evidence from matching concepts
│   │       └── Neural-Networks.concept.md # Search result
│   └── Economics/
│       └── ...
│
└── my-research/                           # Global query (searches all ontologies)
    ├── .meta/
    └── Results.concept.md
```

## Browsing and Exploring

### Discover What You Have

Every ontology has contextual dotfiles that tell you what's inside without needing API calls or CLI commands:

```bash
ls ~/Knowledge/ontology/
# Machine Intelligence  Economics  Architecture

# Quick stats: how many concepts, documents, relationships?
cat ~/Knowledge/ontology/Machine\ Intelligence/.ontology
# # Machine Intelligence
# - Source Count: 16
# - Concept Count: 101
# - Relationship Count: 101

# What documents are in this ontology?
cat ~/Knowledge/ontology/Machine\ Intelligence/documents/.documents
# # Machine Intelligence — Documents (7)
# - the_hallway.md
# - neural_architecture.pdf
# ...
```

This is useful when you have many ontologies and want to quickly understand what each one contains — no need to open a browser or run queries.

### Read Source Documents

```bash
# List documents
ls ~/Knowledge/ontology/Machine\ Intelligence/documents/

# Read a document (rendered as markdown with YAML frontmatter)
cat ~/Knowledge/ontology/Machine\ Intelligence/documents/the_hallway.md
```

Documents include their original content plus metadata about extracted concepts (if tag generation is enabled).

## Searching with Queries

Directories you create become semantic searches. The directory name is the search term.

### Scoped Queries

Search within a single ontology:

```bash
mkdir ~/Knowledge/ontology/Machine\ Intelligence/neural\ networks
ls ~/Knowledge/ontology/Machine\ Intelligence/neural\ networks/
# Neural-Networks.concept.md  Plasticity-Problem.concept.md  images/  .meta/
```

This is useful when you know which ontology has the knowledge you're looking for and want to avoid noise from other domains.

### Global Queries

Search across all ontologies at once:

```bash
mkdir ~/Knowledge/distributed\ systems
ls ~/Knowledge/distributed\ systems/
# Shows concepts from every ontology that matches
```

This is useful for cross-cutting research — finding how different knowledge domains relate to the same topic.

### Nested Queries (AND Logic)

Each directory level adds an AND constraint, progressively narrowing results:

```bash
mkdir ~/Knowledge/ontology/Economics/inflation
mkdir ~/Knowledge/ontology/Economics/inflation/monetary\ policy

# First level: concepts matching "inflation"
ls ~/Knowledge/ontology/Economics/inflation/

# Second level: concepts matching "inflation" AND "monetary policy"
ls ~/Knowledge/ontology/Economics/inflation/monetary\ policy/
```

This is useful for drilling into a topic — start broad, then focus by adding subdirectories.

### Read Concept Files

Each concept result is a markdown file with full context:

```bash
cat ~/Knowledge/ontology/Economics/inflation/Monetary-Policy.concept.md
```

```yaml
---
id: sha256:abc123...
label: Monetary Policy
aliases:
  - central bank policy
  - money supply management
documents:
  - Economics
sources:
  - research-paper.pdf
relationships:
  - type: INFLUENCES
    target: "[[Inflation.concept]]"
tags:
  - concept/Inflation
  - ontology/Economics
---

# Monetary Policy

## Evidence

### Instance 1 from research-paper.pdf (para 3)
> The Federal Reserve uses open market operations to influence...
```

### Remove Queries

```bash
rmdir ~/Knowledge/ontology/Economics/inflation
# Also removes nested queries (inflation/monetary policy, etc.)
```

Query directories are client-side — removing them doesn't affect the graph.

## Query Configuration (.meta)

Every query directory has a `.meta/` subdirectory with virtual configuration files. Changes take effect immediately — the next `ls` shows updated results.

### View Current Settings

```bash
cat .meta/limit      # "50"
cat .meta/threshold  # "0.7"
cat .meta/query.toml # Full state (read-only debug view)
```

### Tune Results

```bash
# Fewer, more precise results
echo 0.85 > .meta/threshold
echo 10 > .meta/limit

# Broader, exploratory results
echo 0.3 > .meta/threshold
echo 100 > .meta/limit
```

### Filter and Expand

```bash
# Exclude irrelevant concepts (semantic NOT)
echo "deprecated" >> .meta/exclude
echo "legacy" >> .meta/exclude

# Broaden the search (semantic OR)
echo "governance" >> .meta/union
echo "compliance" >> .meta/union

# Clear a filter list
: > .meta/exclude
```

This is useful for iterative exploration — you can tune a query interactively, watching how results change with each adjustment, without leaving the filesystem.

### Configuration Reference

| File | Type | Read | Write | Effect |
|------|------|------|-------|--------|
| `limit` | Integer | Current value | Set new value | Max results returned |
| `threshold` | Float (0.0-1.0) | Current value | Set new value | Min similarity score |
| `exclude` | Text (lines) | Current terms | Append term | Semantic NOT filter |
| `union` | Text (lines) | Current terms | Append term | Semantic OR expansion |
| `query.toml` | TOML | Full state | Read-only | Debug view |

## Ontology Management

### Create an Ontology

```bash
mkdir ~/Knowledge/ontology/My-Research
ls ~/Knowledge/ontology/My-Research/
# .ontology  documents/  ingest/
```

This creates the ontology on the platform via the API. The `.ontology`, `documents/`, and `ingest/` subdirectories appear automatically.

### Delete an Ontology

Ontology deletion is gated by write protection (off by default):

```bash
# Enable in fuse.json first:
# "write_protect": { "allow_ontology_delete": true }

rmdir ~/Knowledge/ontology/My-Research
```

This deletes the ontology and all its documents from the graph — it's irreversible.

## Document Ingestion

Each ontology has an `ingest/` directory — a drop box for new documents.

### Ingest a Document

```bash
# Copy a file into the ingest directory
cp research-paper.md ~/Knowledge/ontology/Economics/ingest/

# A job status file appears while processing
ls ~/Knowledge/ontology/Economics/ingest/
# .ingest  research-paper.md.ingesting

# Check progress
cat ~/Knowledge/ontology/Economics/ingest/research-paper.md.ingesting
# # Ingestion Job: job_abc123
# # Status: running
# [progress]
# stage = "extracting_concepts"
# percent = 45

# After processing completes, the .ingesting file disappears
# and the document appears in documents/
ls ~/Knowledge/ontology/Economics/documents/
# .documents  research-paper.md
```

### How Ingestion Works

1. `cp` creates a file in `ingest/` and writes content
2. On file close, content is POSTed to the ingestion API
3. A `.ingesting` status file appears showing job progress
4. Ingestion is auto-approved (no manual step needed)
5. After processing, the job file disappears and the document appears in `documents/`

### Batch Ingestion

```bash
# Ingest a directory of papers
for f in ~/papers/*.md; do
    cp "$f" ~/Knowledge/ontology/Research/ingest/
done
```

### Supported Formats

The `ingest/` directory accepts text, markdown, PDF, and image files (.png, .jpg, .gif, .webp, .bmp). The `.ingest` dotfile in each ingest directory reminds you of this:

```bash
cat ~/Knowledge/ontology/Economics/ingest/.ingest
# # Economics — Ingest
#
# Drop or copy files here to ingest them into the knowledge graph.
#
# Supported formats: text, markdown, PDF, and images.
# Files are processed automatically after upload.
```

### File Manager Integration

The `ingest/` directory works with graphical file managers like Dolphin and GNOME Files. Drag files from your desktop or paste from the clipboard — they'll be ingested automatically.

## Document Deletion

Documents can be deleted with `rm`, gated by write protection:

```bash
# Enable in fuse.json first:
# "write_protect": { "allow_document_delete": true }

rm ~/Knowledge/ontology/Economics/documents/old-paper.md
```

This deletes the document from the graph via the API. The concepts extracted from it remain (they may have evidence from other documents too).

## Cross-Ontology Queries with Symlinks

Global queries (created at the mount root) search all ontologies by default. You can restrict them to specific ontologies using symlinks:

```bash
# Create a global query
mkdir ~/Knowledge/my-research

# Link specific ontologies into it (OR logic)
ln -s ../ontology/Economics ~/Knowledge/my-research/Economics
ln -s ../ontology/Architecture ~/Knowledge/my-research/Architecture

# Now "my-research" only searches Economics and Architecture
ls ~/Knowledge/my-research/
```

This is useful when you want to compare concepts across a specific subset of ontologies without including everything.

## Write Protection

Destructive operations (ontology deletion, document deletion) are disabled by default. Enable them per-mount in `~/.config/kg/fuse.json`:

```json
{
  "mounts": {
    "/home/user/Knowledge": {
      "write_protect": {
        "allow_ontology_delete": false,
        "allow_document_delete": false
      }
    }
  }
}
```

Changes are hot-reloaded — no remount needed. This is useful for shared or production mounts where accidental deletion would be costly.

## Example Workflows

### Research Session

```bash
# Start from an ontology you know has relevant data
cd ~/Knowledge/ontology/Machine\ Intelligence

# Quick stats
cat .ontology

# Create a focused query
mkdir "agent architecture"
cd "agent architecture"

# Too many results? Raise the threshold
echo 0.8 > .meta/threshold

# Filter out noise
echo "deprecated" >> .meta/exclude

# Read the results
ls *.concept.md
cat "Agent-Model.concept.md"

# Drill deeper
mkdir reasoning
ls reasoning/
```

### Building a New Knowledge Domain

```bash
# Create the ontology
mkdir ~/Knowledge/ontology/Project-Notes

# Ingest your documents
cp ~/docs/design-doc.md ~/Knowledge/ontology/Project-Notes/ingest/
cp ~/docs/meeting-notes.md ~/Knowledge/ontology/Project-Notes/ingest/

# Wait for processing, then explore what was extracted
cat ~/Knowledge/ontology/Project-Notes/.ontology
ls ~/Knowledge/ontology/Project-Notes/documents/

# Query the newly ingested knowledge
mkdir ~/Knowledge/ontology/Project-Notes/architecture\ decisions
ls ~/Knowledge/ontology/Project-Notes/architecture\ decisions/
```

### Quick Lookup

```bash
# "What does the graph know about X?"
mkdir ~/Knowledge/ontology/Economics/stagflation
cat ~/Knowledge/ontology/Economics/stagflation/*.concept.md
rmdir ~/Knowledge/ontology/Economics/stagflation
```

### Cross-Domain Exploration

```bash
# Search everything, then narrow
mkdir ~/Knowledge/distributed\ systems
echo 0.5 > ~/Knowledge/distributed\ systems/.meta/threshold
ls ~/Knowledge/distributed\ systems/
# Concepts from multiple ontologies appear together
```

### Unix Tool Integration

Since it's a real filesystem, every tool that works with files works with your knowledge graph:

```bash
# Grep across all concepts in an ontology
grep -r "consensus" ~/Knowledge/ontology/Architecture/

# Copy query results for offline reference
cp -r ~/Knowledge/ontology/Economics/inflation/ ~/notes/

# Tree view of an ontology
tree ~/Knowledge/ontology/Machine\ Intelligence/ -L 2

# Open in your editor
vim ~/Knowledge/ontology/Economics/inflation/Monetary-Policy.concept.md

# Count concepts matching a query
ls ~/Knowledge/ontology/Economics/inflation/*.concept.md | wc -l

# Diff two concept files
diff ~/Knowledge/ontology/Economics/inflation/CPI.concept.md \
     ~/Knowledge/ontology/Economics/inflation/PPI.concept.md
```

### External Program Integration

Any program that reads or writes files can interact with the knowledge graph without knowing about it:

```bash
# Obsidian: point a vault at the mount — wikilinks in concept files
# render as a navigable graph natively (no plugin needed)

# Speech-to-text: have a transcription tool write directly to ingest/
whisper-cli record --output ~/Knowledge/ontology/Meeting-Notes/ingest/standup.md

# Automated ingestion: a cron job or watcher that drops files
inotifywait -m ~/incoming/ -e close_write | while read dir event file; do
    cp ~/incoming/"$file" ~/Knowledge/ontology/Auto-Ingest/ingest/
done

# Backup: snapshot an ontology's documents
rsync -av ~/Knowledge/ontology/Economics/documents/ ~/backup/economics/

# Remote access: browse from another machine
ssh server "cat ~/Knowledge/ontology/Economics/.ontology"
sshfs server:~/Knowledge ~/remote-knowledge
```

### Obsidian as a Graph Viewer

The FUSE filesystem presents concepts as markdown files with wikilink-style relationships (`[[Concept.concept]]`). Point Obsidian at the mount point and its graph view renders your knowledge graph natively — no plugin required. Concept frontmatter includes tags, relationships, and source attribution that Obsidian can index and display.

## Troubleshooting

### Mount Issues

```bash
# Check status
kg-fuse status

# Repair orphaned mounts or stale PIDs
kg-fuse repair

# Manual force unmount (if repair doesn't help)
fusermount -uz ~/Knowledge
kg-fuse mount
```

### Query Returns No Results

```bash
# Check the query state
cat .meta/query.toml

# Lower the threshold
echo 0.3 > .meta/threshold

# Verify the ontology actually has documents
cat ../.ontology
ls ../documents/
```

### Ingestion Seems Stuck

```bash
# Check the job status file
cat ~/Knowledge/ontology/My-Ont/ingest/*.ingesting

# If the .ingesting file persists after the job is done,
# re-list the directory to trigger cleanup
ls ~/Knowledge/ontology/My-Ont/ingest/
```

## Architecture Notes

- **Hologram model**: Documents and concepts are read-only projections from the graph — the filesystem is a view, not a copy
- **Epoch-gated caching**: Tracks the graph change counter; serves stale data instantly while refreshing in the background
- **Client-side queries**: Query definitions stored in `~/.local/share/kg-fuse/mounts/<id>/queries.toml`
- **Write-back ingestion**: Files are buffered locally then submitted to the API on close
- **OAuth**: Uses standard OAuth 2.0 client credentials flow, shared with `kg` CLI

## Related Documentation

- [ADR-069: Semantic FUSE Filesystem](../architecture/user-interfaces/ADR-069-semantic-fuse-filesystem.md) — Design rationale
- [ADR-069.1: Implementation Specifics](../architecture/user-interfaces/ADR-069.1-fuse-implementation-specifics.md) — Technical details
- [FUSE Driver Feature Page](../features/fuse-driver.md) — Quick overview
- [FUSE Package README](../../fuse/README.md) — CLI reference and configuration
