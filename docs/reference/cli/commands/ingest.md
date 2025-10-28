# kg ingest

> Auto-generated

## ingest

Ingest documents into the knowledge graph

**Usage:**
```bash
kg ingest [options]
```

**Subcommands:**

- `file` - Ingest a document file
- `directory` - Ingest all matching files from a directory
- `text` - Ingest raw text

---

### file

Ingest a document file

**Usage:**
```bash
kg file <path>
```

**Arguments:**

- `<path>` - Required

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --ontology <name>` | Ontology/collection name | - |
| `-f, --force` | Force re-ingestion even if duplicate | `false` |
| `--no-approve` | Require manual approval before processing (default: auto-approve) | - |
| `--parallel` | Process in parallel (default: serial for clean concept matching) | `false` |
| `--filename <name>` | Override filename for tracking | - |
| `--target-words <n>` | Target words per chunk | `"1000"` |
| `--overlap-words <n>` | Overlap between chunks | `"200"` |
| `-w, --wait` | Wait for job completion (default: submit and exit) | `false` |

### directory

Ingest all matching files from a directory

**Usage:**
```bash
kg directory <dir>
```

**Arguments:**

- `<dir>` - Required

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --ontology <name>` | Ontology/collection name (required unless --directories-as-ontologies) | - |
| `-p, --pattern <patterns...>` | File patterns to match (e.g., *.md *.txt) | `["*.md","*.txt"]` |
| `-r, --recurse` | Recursively scan subdirectories | `false` |
| `-d, --depth <n>` | Maximum recursion depth (number or "all") | `"0"` |
| `--directories-as-ontologies` | Use directory names as ontology names | `false` |
| `-f, --force` | Force re-ingestion even if duplicate | `false` |
| `--dry-run` | Show what would be ingested without submitting jobs | `false` |
| `--no-approve` | Require manual approval before processing (default: auto-approve) | - |
| `--parallel` | Process in parallel (default: serial for clean concept matching) | `false` |
| `--target-words <n>` | Target words per chunk | `"1000"` |
| `--overlap-words <n>` | Overlap between chunks | `"200"` |

### text

Ingest raw text

**Usage:**
```bash
kg text <text>
```

**Arguments:**

- `<text>` - Required

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --ontology <name>` | Ontology/collection name | - |
| `-f, --force` | Force re-ingestion even if duplicate | `false` |
| `--no-approve` | Require manual approval before processing (default: auto-approve) | - |
| `--parallel` | Process in parallel (default: serial for clean concept matching) | `false` |
| `--filename <name>` | Filename for tracking | `"text_input"` |
| `--target-words <n>` | Target words per chunk | `"1000"` |
| `-w, --wait` | Wait for job completion (default: submit and exit) | `false` |
