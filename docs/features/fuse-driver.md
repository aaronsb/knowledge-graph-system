# FUSE Driver

A semantic filesystem that lets you browse your knowledge graph using standard Unix commands. Create directories to define queries, list them to see results, read files to get concept details, and copy files to ingest new documents.

![FUSE filesystem in Dolphin file manager](../media/fuse/fuse-file-manager.png)
*Knowledge graph mounted as a filesystem — ontologies are folders, queries are directories you create, and concepts appear as files. Integrates with Dolphin and GNOME Files. Use `grep`, `tree`, `cp -r`, or any Unix tool on your semantic data.*

## Installation

```bash
pipx install kg-fuse
```

## Quick Start

```bash
# Create OAuth credentials
kg oauth create --for fuse

# Set up and mount
kg-fuse init ~/Knowledge
kg-fuse mount

# Explore
ls ~/Knowledge/ontology/
cat ~/Knowledge/ontology/Economics/.ontology
mkdir ~/Knowledge/ontology/Economics/inflation
ls ~/Knowledge/ontology/Economics/inflation/
cat ~/Knowledge/ontology/Economics/inflation/Monetary-Policy.concept.md

# Unmount
kg-fuse unmount
```

---

## How It Works

The filesystem maps knowledge graph operations to Unix semantics:

| Unix Operation | Knowledge Graph Operation |
|----------------|---------------------------|
| `ls ontology/` | List all ontologies |
| `cat ontology/Economics/.ontology` | View ontology stats (concepts, docs, relationships) |
| `ls ontology/Economics/documents/` | List source documents |
| `cat ontology/Economics/documents/.documents` | View document listing with count |
| `mkdir ontology/Economics/inflation` | Create semantic query for "inflation" in Economics |
| `ls ontology/Economics/inflation/` | Execute query, show matching concepts |
| `cat Concept.concept.md` | Read concept with evidence and relationships |
| `echo 0.8 > .meta/threshold` | Tune query precision |
| `echo "noise" >> .meta/exclude` | Filter out irrelevant results |
| `cp paper.pdf ontology/Economics/ingest/` | Ingest document into Economics |
| `cat paper.pdf.ingesting` | Check ingestion job progress |
| `rm ontology/Economics/documents/old.md` | Delete a document from the graph |
| `mkdir ontology/New-Domain` | Create a new ontology |
| `rmdir ontology/New-Domain` | Delete an ontology (if write-protect allows) |
| `rmdir ontology/Economics/inflation` | Remove query (not the concepts) |
| `ln -s ../ontology/Econ query/Econ` | Link ontology into a global query (OR) |

---

## Filesystem Structure

```
~/Knowledge/
├── ontology/                           # All knowledge domains
│   ├── Economics/                      # An ontology
│   │   ├── .ontology                   # Stats: concept count, doc count, etc.
│   │   ├── documents/                  # Source documents (read-only)
│   │   │   ├── .documents              # Document listing with count
│   │   │   ├── research-paper.md       # Text document
│   │   │   └── diagram.png            # Image document
│   │   ├── ingest/                     # Drop box for new documents
│   │   │   ├── .ingest                 # Usage instructions
│   │   │   └── paper.md.ingesting      # Job tracker (during processing)
│   │   └── inflation/                  # Your query
│   │       ├── .meta/                  # Query controls
│   │       │   ├── limit               # Max results (default: 50)
│   │       │   ├── threshold           # Min similarity (default: 0.7)
│   │       │   ├── exclude             # Terms to filter out (NOT)
│   │       │   ├── union               # Terms to add (OR)
│   │       │   └── query.toml          # Debug view (read-only)
│   │       ├── images/                 # Image evidence from concepts
│   │       ├── Monetary-Policy.concept.md
│   │       └── Supply-Chain.concept.md
│   └── Architecture/                   # Another ontology
│
└── global-search/                      # Query across ALL ontologies
    ├── .meta/
    └── Results.concept.md
```

---

## Contextual Info Files

Each directory has a dotfile that describes its contents:

| File | Location | Content |
|------|----------|---------|
| `.ontology` | `ontology/{name}/` | Concept count, document count, relationship count, description |
| `.documents` | `ontology/{name}/documents/` | Document listing with count |
| `.ingest` | `ontology/{name}/ingest/` | Usage instructions for the drop box |

These are useful for quickly understanding what's in each ontology without running queries or opening a browser.

---

## Query Control

Every query directory has a `.meta/` folder for tuning results.

### Adjust Precision

```bash
# Fewer, more relevant results
echo 0.85 > .meta/threshold

# More results, broader matching
echo 0.3 > .meta/threshold
```

### Limit Results

```bash
echo 20 > .meta/limit
```

### Exclude Terms

```bash
echo "deprecated" >> .meta/exclude
echo "legacy" >> .meta/exclude
```

### Broaden Search

```bash
echo "monetary" >> .meta/union
echo "fiscal" >> .meta/union
```

### View Query State

```bash
cat .meta/query.toml
```

---

## Document Ingestion

Each ontology has a dedicated `ingest/` drop box:

```bash
# Copy files to ingest them
cp research-paper.pdf ~/Knowledge/ontology/Economics/ingest/

# A .ingesting file tracks progress
cat ~/Knowledge/ontology/Economics/ingest/research-paper.pdf.ingesting
# Status: running, stage: extracting_concepts, percent: 45

# After processing, the document appears in documents/
ls ~/Knowledge/ontology/Economics/documents/
```

Supports text, markdown, PDF, and images (.png, .jpg, .gif, .webp, .bmp). Works with file managers too — drag and drop files into `ingest/` from Dolphin or GNOME Files.

---

## Document and Ontology Deletion

Destructive operations are gated by write protection (off by default):

```bash
# Delete a document (requires allow_document_delete: true)
rm ~/Knowledge/ontology/Economics/documents/old-paper.md

# Delete an ontology (requires allow_ontology_delete: true)
rmdir ~/Knowledge/ontology/Deprecated-Domain
```

Configure in `~/.config/kg/fuse.json` under the mount's `write_protect` section. Changes are hot-reloaded.

---

## Concept Files

Each concept appears as a markdown file with YAML frontmatter:

- **Label, aliases, and description**
- **Evidence quotes** with source attribution
- **Relationships** to other concepts (wikilink format)
- **Grounding strength** score
- **Tags** for Obsidian/Logseq integration

---

## Use Cases

### Grep Through Knowledge

```bash
grep -r "distributed" ~/Knowledge/ontology/Architecture/
```

### Editor Integration

```bash
vim ~/Knowledge/ontology/Economics/inflation/Monetary-Policy.concept.md
```

### Automated Ingestion

Any program that writes files can feed the knowledge graph:

```bash
# Speech-to-text transcription → knowledge graph
whisper-cli record --output ~/Knowledge/ontology/Meetings/ingest/standup.md

# File watcher for continuous ingestion
inotifywait -m ~/incoming/ -e close_write | while read dir event file; do
    cp ~/incoming/"$file" ~/Knowledge/ontology/Auto-Ingest/ingest/
done
```

### Obsidian as a Graph Viewer

The FUSE filesystem presents concepts as markdown with wikilink-style relationships. Point Obsidian at the mount point and its graph view renders your knowledge graph natively — no plugin required.

![Obsidian graph view of knowledge graph](../media/obsidian-use-case/obsidian-graph-view.png)
*Obsidian's built-in graph view rendering concept relationships from the FUSE mount*

![Obsidian concept detail](../media/obsidian-use-case/obsidian-concept-detail.png)
*A concept file showing properties, evidence, and knowledge metadata in Obsidian*

### Remote Access

Since it's a real filesystem, remote access works natively:

```bash
ssh server "cat ~/Knowledge/ontology/Economics/.ontology"
scp -r server:~/Knowledge/ontology/Economics/inflation/ ./local-copy/
sshfs server:~/Knowledge ~/remote-knowledge
```

---

## Configuration

Config stored in `~/.config/kg/fuse.json`:

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

Settings are hot-reloaded — edit the file while mounted and changes take effect within seconds.

Generate credentials with `kg oauth create --for fuse`.

---

## Notes

- **Non-POSIX by design** — Like Google Drive, the filesystem intentionally violates some POSIX expectations. Concepts can appear in multiple places, results change as the graph evolves.
- **Read-heavy** — Optimized for exploration. Write operations (ingestion) are async.
- **OAuth required** — Uses the same authentication as CLI and MCP.
- **File manager friendly** — Reports virtual free space so Dolphin/GNOME Files don't disable paste; dotfiles keep directories non-empty so drag targets work.
