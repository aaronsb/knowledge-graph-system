---
id: 07.002.H
domain: ui
mode: how-to
---

# Use the FUSE Drive

`kg-fuse` mounts your Kappa Graph as a virtual filesystem. Browse ontologies as directories, create semantic queries with `mkdir`, ingest documents by copying files, and tune search results through virtual files — all from your terminal or file manager.

The Python API reference for kg-fuse is at [reference/fuse.md](../reference/fuse.md). Design rationale is in [ADR-715](../architecture/user-interfaces/ADR-715-semantic-fuse-filesystem.md) and [ADR-715.1](../architecture/user-interfaces/ADR-715.1-fuse-implementation-specifics.md).

---

## Prerequisites

- Linux with FUSE3
- Python 3.11+
- A running Kappa Graph API
- `kg` CLI installed and authenticated (Node 20.12.0+)

---

## Install

### 1. Install FUSE3

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

To upgrade later:

```bash
pipx upgrade kg-fuse
# or
kg-fuse update
```

---

## Set up a mount

### 1. Create OAuth credentials

```bash
kg oauth create --for fuse
```

This writes credentials to `~/.config/kg/config.json`, which kg-fuse reads automatically.

### 2. Initialise a mount point

```bash
kg-fuse init ~/Knowledge
```

This validates the path, detects credentials from `~/.config/kg/config.json`, and optionally configures autostart. Mount configuration is written to `~/.config/kg/fuse.json`.

### 3. Mount and unmount

```bash
kg-fuse mount     # start all configured mounts
kg-fuse unmount   # stop all mounts
kg-fuse status    # show what is running
```

---

## Filesystem layout

```
~/Knowledge/
├── ontology/                              # all knowledge domains
│   ├── Machine Intelligence/              # one ontology
│   │   ├── .ontology                      # stats: concepts, docs, relationships
│   │   ├── documents/                     # source documents (read-only)
│   │   │   ├── .documents                 # document listing with count
│   │   │   ├── research-paper.md
│   │   │   └── diagram.png
│   │   ├── ingest/                        # drop box for new documents
│   │   │   ├── .ingest                    # usage instructions
│   │   │   └── paper.md.ingesting         # job tracker (appears during processing)
│   │   └── neural networks/               # query you created with mkdir
│   │       ├── .meta/                     # query controls
│   │       │   ├── limit                  # max results (default: 50)
│   │       │   ├── threshold              # min similarity (default: 0.7)
│   │       │   ├── exclude                # NOT filter terms (one per line)
│   │       │   ├── union                  # OR expansion terms (one per line)
│   │       │   └── query.toml             # full query state (read-only)
│   │       ├── images/                    # image evidence from matching concepts
│   │       └── Neural-Networks.concept.md
│   └── Economics/
│       └── ...
│
└── my-research/                           # global query (searches all ontologies)
    ├── .meta/
    └── Results.concept.md
```

### Unix operations mapped to graph operations

| Unix operation | Graph operation |
|---|---|
| `ls ontology/` | List all ontologies |
| `cat ontology/Economics/.ontology` | View ontology stats |
| `ls ontology/Economics/documents/` | List source documents |
| `mkdir ontology/Economics/inflation` | Create semantic query for "inflation" |
| `ls ontology/Economics/inflation/` | Execute query, show matching concepts |
| `cat Monetary-Policy.concept.md` | Read concept with evidence and relationships |
| `echo 0.8 > .meta/threshold` | Set query precision |
| `echo "noise" >> .meta/exclude` | Add NOT filter |
| `cp paper.pdf ontology/Economics/ingest/` | Ingest document |
| `mkdir ontology/New-Domain` | Create a new ontology |
| `rmdir ontology/Economics/inflation` | Remove query (does not affect the graph) |
| `rmdir ontology/New-Domain` | Delete ontology (requires write-protect override) |
| `rm ontology/Economics/documents/old.md` | Delete document (requires write-protect override) |
| `ln -s ../ontology/Econ query/Econ` | Restrict global query to specific ontologies |

---

## Browse ontologies

Each ontology directory contains contextual dotfiles that describe its contents without requiring API calls:

```bash
ls ~/Knowledge/ontology/
# Machine Intelligence  Economics  Architecture

cat ~/Knowledge/ontology/Machine\ Intelligence/.ontology
# # Machine Intelligence
# - Source Count: 16
# - Concept Count: 101
# - Relationship Count: 101

cat ~/Knowledge/ontology/Machine\ Intelligence/documents/.documents
# # Machine Intelligence — Documents (7)
# - the_hallway.md
# - neural_architecture.pdf
# ...
```

To read a source document:

```bash
cat ~/Knowledge/ontology/Machine\ Intelligence/documents/the_hallway.md
```

Documents are rendered as markdown with YAML frontmatter that includes extracted-concept metadata (when tag generation is enabled).

---

## Query with directories

Directory names become semantic search terms. Creating a directory executes the query; listing it shows results.

### Scoped query (single ontology)

```bash
mkdir ~/Knowledge/ontology/Machine\ Intelligence/neural\ networks
ls ~/Knowledge/ontology/Machine\ Intelligence/neural\ networks/
# Neural-Networks.concept.md  Plasticity-Problem.concept.md  images/  .meta/
```

### Global query (all ontologies)

```bash
mkdir ~/Knowledge/distributed\ systems
ls ~/Knowledge/distributed\ systems/
# concepts from every ontology that matches
```

### Nested query (AND logic)

Each additional directory level adds an AND constraint:

```bash
mkdir ~/Knowledge/ontology/Economics/inflation
mkdir ~/Knowledge/ontology/Economics/inflation/monetary\ policy

ls ~/Knowledge/ontology/Economics/inflation/
# concepts matching "inflation"

ls ~/Knowledge/ontology/Economics/inflation/monetary\ policy/
# concepts matching "inflation" AND "monetary policy"
```

### Remove a query

```bash
rmdir ~/Knowledge/ontology/Economics/inflation
# also removes nested queries; does not affect graph data
```

### Read a concept file

Each result is a markdown file with YAML frontmatter:

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

---

## Tune query results

Every query directory has a `.meta/` subdirectory. Write to these files and the next `ls` shows updated results.

### Control files

| File | Type | Default | Effect |
|---|---|---|---|
| `limit` | integer | `50` | Max results returned |
| `threshold` | float 0.0–1.0 | `0.7` | Min similarity score |
| `exclude` | lines of text | empty | Semantic NOT filter |
| `union` | lines of text | empty | Semantic OR expansion |
| `query.toml` | TOML | — | Debug view (read-only) |

### Examples

```bash
# Fewer, more precise results
echo 0.85 > .meta/threshold
echo 10 > .meta/limit

# Broader, exploratory results
echo 0.3 > .meta/threshold
echo 100 > .meta/limit

# Exclude irrelevant concepts
echo "deprecated" >> .meta/exclude
echo "legacy" >> .meta/exclude

# Broaden with related terms
echo "governance" >> .meta/union
echo "compliance" >> .meta/union

# Clear a filter
: > .meta/exclude

# Inspect current state
cat .meta/query.toml
```

---

## Restrict a global query to specific ontologies

Global queries (created at the mount root) search all ontologies. Link specific ontologies into the query directory to restrict scope:

```bash
mkdir ~/Knowledge/my-research
ln -s ../ontology/Economics ~/Knowledge/my-research/Economics
ln -s ../ontology/Architecture ~/Knowledge/my-research/Architecture

ls ~/Knowledge/my-research/
# concepts from Economics and Architecture only
```

---

## Ingest documents

Each ontology has an `ingest/` directory. Copying a file into it submits it to the API.

```bash
cp research-paper.pdf ~/Knowledge/ontology/Economics/ingest/

# A .ingesting file appears while processing
ls ~/Knowledge/ontology/Economics/ingest/
# .ingest  research-paper.pdf.ingesting

cat ~/Knowledge/ontology/Economics/ingest/research-paper.pdf.ingesting
# # Ingestion Job: job_abc123
# # Status: running
# [progress]
# stage = "extracting_concepts"
# percent = 45

# After processing, the document appears in documents/
ls ~/Knowledge/ontology/Economics/documents/
# .documents  research-paper.pdf
```

Supported formats: text, markdown, PDF, and images (.png, .jpg, .gif, .webp, .bmp).

Ingestion via FUSE is auto-approved — no manual approval step.

### Batch ingestion

```bash
for f in ~/papers/*.md; do
    cp "$f" ~/Knowledge/ontology/Research/ingest/
done
```

### File manager integration

The `ingest/` directory works with Dolphin and GNOME Files. Drag files from your desktop or paste from the clipboard.

---

## Manage ontologies

### Create an ontology

```bash
mkdir ~/Knowledge/ontology/My-Research
ls ~/Knowledge/ontology/My-Research/
# .ontology  documents/  ingest/
```

This creates the ontology on the platform via the API.

### Delete an ontology

Ontology deletion requires an explicit write-protect override (see [Write protection](#write-protection) below):

```bash
rmdir ~/Knowledge/ontology/My-Research
```

Deletion removes the ontology and all its documents from the graph. This is irreversible.

---

## Delete documents

Document deletion also requires an explicit override:

```bash
rm ~/Knowledge/ontology/Economics/documents/old-paper.md
```

The concepts extracted from the document remain in the graph; they may have evidence from other sources.

---

## Write protection

Destructive operations are disabled by default. Enable them per-mount in `~/.config/kg/fuse.json`:

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

Changes are hot-reloaded — no remount required.

---

## Full configuration reference

kg-fuse uses two files, both in `~/.config/kg/`:

| File | Owner | Purpose |
|---|---|---|
| `config.json` | `kg` CLI | Auth credentials and `api_url` — read-only for kg-fuse |
| `fuse.json` | kg-fuse | Mount definitions, cache, tags, write-protect |

A complete `fuse.json`:

```json
{
  "auth_client_id": "kg-cli-admin-ba93368c",
  "mounts": {
    "/home/user/Knowledge": {
      "tags": { "enabled": true, "threshold": 0.5 },
      "cache": { "epoch_check_interval": 5.0 },
      "jobs": { "hide_jobs": false },
      "write_protect": {
        "allow_ontology_delete": false,
        "allow_document_delete": false
      }
    }
  }
}
```

`fuse.json` is hot-reloaded; most changes take effect within seconds without remounting.

---

## Example workflows

### Research session

```bash
cd ~/Knowledge/ontology/Machine\ Intelligence

cat .ontology   # check what's here

mkdir "agent architecture"
cd "agent architecture"

echo 0.8 > .meta/threshold     # raise precision
echo "deprecated" >> .meta/exclude

ls *.concept.md
cat "Agent-Model.concept.md"

mkdir reasoning   # drill deeper with AND logic
ls reasoning/
```

### Build a new knowledge domain

```bash
mkdir ~/Knowledge/ontology/Project-Notes

cp ~/docs/design-doc.md ~/Knowledge/ontology/Project-Notes/ingest/
cp ~/docs/meeting-notes.md ~/Knowledge/ontology/Project-Notes/ingest/

# Wait for processing to finish
cat ~/Knowledge/ontology/Project-Notes/.ontology

mkdir ~/Knowledge/ontology/Project-Notes/architecture\ decisions
ls ~/Knowledge/ontology/Project-Notes/architecture\ decisions/
```

### Unix tool integration

```bash
# Grep across all concepts in an ontology
grep -r "consensus" ~/Knowledge/ontology/Architecture/

# Count concepts matching a query
ls ~/Knowledge/ontology/Economics/inflation/*.concept.md | wc -l

# Copy results for offline reference
cp -r ~/Knowledge/ontology/Economics/inflation/ ~/notes/

# Diff two concept files
diff ~/Knowledge/ontology/Economics/inflation/CPI.concept.md \
     ~/Knowledge/ontology/Economics/inflation/PPI.concept.md

# Tree view
tree ~/Knowledge/ontology/Machine\ Intelligence/ -L 2
```

### Obsidian as a graph viewer

Concept files use wikilink-style relationships (`[[Concept.concept]]`). Point Obsidian at the mount point and its graph view renders concept relationships natively — no plugin required. Frontmatter includes tags, relationships, and source attribution.

### Automated ingestion

Any program that writes files can feed the graph:

```bash
# Speech-to-text → graph
whisper-cli record --output ~/Knowledge/ontology/Meetings/ingest/standup.md

# File watcher for continuous ingestion
inotifywait -m ~/incoming/ -e close_write | while read dir event file; do
    cp ~/incoming/"$file" ~/Knowledge/ontology/Auto-Ingest/ingest/
done
```

### Remote access

```bash
ssh server "cat ~/Knowledge/ontology/Economics/.ontology"
sshfs server:~/Knowledge ~/remote-knowledge
```

---

## Troubleshooting

### Mount issues

```bash
kg-fuse status

# Repair orphaned mounts or stale PIDs
kg-fuse repair

# Force unmount if repair does not help
fusermount -uz ~/Knowledge
kg-fuse mount
```

### Query returns no results

```bash
# Check query state
cat .meta/query.toml

# Lower the threshold
echo 0.3 > .meta/threshold

# Verify the ontology has documents
cat ../.ontology
ls ../documents/
```

### Ingestion appears stuck

```bash
# Check job status
cat ~/Knowledge/ontology/My-Ont/ingest/*.ingesting

# Re-list to trigger cleanup if the .ingesting file persists after completion
ls ~/Knowledge/ontology/My-Ont/ingest/
```

---

## Architecture notes

- **Hologram model**: documents and concepts are read-only projections from the graph; the filesystem is a view, not a copy.
- **Epoch-gated caching**: tracks the graph change counter; serves cached data instantly while refreshing in the background.
- **Client-side queries**: query definitions stored in `~/.local/share/kg-fuse/mounts/<id>/queries.toml`.
- **Write-back ingestion**: files are buffered locally then submitted to the API on close.
- **Non-POSIX by design**: concepts can appear in multiple places; results change as the graph evolves.
