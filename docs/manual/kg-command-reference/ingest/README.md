# kg ingest

Ingest documents into the knowledge graph.

## Usage

```bash
kg ingest [options] [command]
```

## Description

The `ingest` command processes documents and extracts concepts, relationships, and evidence into the knowledge graph. It supports three ingestion modes:

1. **Single file** - Ingest one document
2. **Directory** - Batch ingest multiple files
3. **Raw text** - Ingest text directly without a file

All ingestion operations create jobs that can be monitored via `kg job` commands.

## Options

| Option | Description |
|--------|-------------|
| `-h, --help` | Display help for command |

## Subcommands

| Command | Description | Doc |
|---------|-------------|-----|
| `file <path>` | Ingest a document file | [↓](#file) |
| `directory <dir>` | Ingest all matching files from a directory | [↓](#directory) |
| `text <text>` | Ingest raw text | [↓](#text) |

## Command Tree

```
kg ingest
├── file <path>
├── directory <dir>
└── text <text>
```

---

## Subcommand Details

### file

Ingest a single document file.

**Usage:**
```bash
kg ingest file [options] <path>
```

**Arguments:**
- `<path>` - Path to the document file

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --ontology <name>` | Ontology/collection name (required) | - |
| `-f, --force` | Force re-ingestion even if duplicate | `false` |
| `--no-approve` | Require manual approval before processing | auto-approve |
| `--parallel` | Process in parallel (vs serial for clean concept matching) | `false` |
| `--filename <name>` | Override filename for tracking | actual filename |
| `--target-words <n>` | Target words per chunk | `1000` |
| `--overlap-words <n>` | Overlap between chunks | `200` |
| `-w, --wait` | Wait for job completion (default: submit and exit) | `false` |
| `-h, --help` | Display help for command | - |

**Examples:**

```bash
# Basic ingestion
kg ingest file -o "My Research" paper.pdf

# With custom chunking
kg ingest file -o "Documentation" \
  --target-words 1500 \
  --overlap-words 300 \
  readme.md

# Force re-ingestion
kg ingest file -o "Notes" -f notes.txt

# Wait for completion
kg ingest file -o "Papers" -w research-paper.pdf

# Require manual approval
kg ingest file -o "Sensitive" --no-approve confidential.txt

# Parallel processing (faster but may create duplicate concepts)
kg ingest file -o "Large Corpus" --parallel big-document.txt
```

**Behavior:**

1. Reads the file from disk
2. Chunks the text into semantic segments (~1000 words with overlap)
3. Submits an ingestion job to the API
4. Returns job ID for monitoring
5. Optionally waits for completion with `-w` flag

**Supported File Types:**
- Text files (.txt, .md, .rst)
- PDF documents (.pdf)
- Other formats supported by the API

---

### directory

Ingest all matching files from a directory.

**Usage:**
```bash
kg ingest directory [options] <dir>
```

**Arguments:**
- `<dir>` - Directory path to scan

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --ontology <name>` | Ontology/collection name (required unless `--directories-as-ontologies`) | - |
| `-p, --pattern <patterns...>` | File patterns to match (e.g., `*.md *.txt`) | `*.md *.txt` |
| `-r, --recurse` | Recursively scan subdirectories | `false` |
| `-d, --depth <n>` | Maximum recursion depth (number or "all") | `0` |
| `--directories-as-ontologies` | Use directory names as ontology names | `false` |
| `-f, --force` | Force re-ingestion even if duplicate | `false` |
| `--dry-run` | Show what would be ingested without submitting jobs | `false` |
| `--no-approve` | Require manual approval before processing | auto-approve |
| `--parallel` | Process in parallel (vs serial for clean concept matching) | `false` |
| `--target-words <n>` | Target words per chunk | `1000` |
| `--overlap-words <n>` | Overlap between chunks | `200` |
| `-h, --help` | Display help for command | - |

**Examples:**

```bash
# Basic directory ingestion
kg ingest directory -o "Documentation" ./docs/

# Custom file patterns
kg ingest directory -o "Code Docs" -p "*.md" "*.rst" ./src/

# Recursive with depth limit
kg ingest directory -o "Project" -r -d 3 ./

# Recursive all levels
kg ingest directory -o "Everything" -r -d all ./

# Use directory names as ontologies
kg ingest directory --directories-as-ontologies -r ./knowledge-base/

# Dry run to preview
kg ingest directory -o "Test" --dry-run ./docs/

# Force re-ingestion of all files
kg ingest directory -o "Archive" -f -r ./old-docs/
```

**Directory-as-Ontology Mode:**

When using `--directories-as-ontologies`:
- Each subdirectory becomes a separate ontology
- Directory name is used as ontology name
- Files in root directory are skipped (or use parent dir name)
- Useful for organizing knowledge domains by folder structure

```bash
# File structure:
# knowledge-base/
# ├── physics/
# │   ├── quantum.md
# │   └── relativity.md
# └── chemistry/
#     └── organic.md

kg ingest directory --directories-as-ontologies -r ./knowledge-base/

# Creates ontologies: "physics", "chemistry"
```

**Dry Run Output:**

```
Would ingest 15 files:
  docs/README.md → "Documentation"
  docs/guide.md → "Documentation"
  docs/api/endpoints.md → "Documentation"
  ...

Total: 15 files, estimated ~45 chunks
```

---

### text

Ingest raw text directly without a file.

**Usage:**
```bash
kg ingest text [options] <text>
```

**Arguments:**
- `<text>` - Raw text content to ingest

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --ontology <name>` | Ontology/collection name (required) | - |
| `-f, --force` | Force re-ingestion even if duplicate | `false` |
| `--no-approve` | Require manual approval before processing | auto-approve |
| `--parallel` | Process in parallel (vs serial for clean concept matching) | `false` |
| `--filename <name>` | Filename for tracking | `text_input` |
| `--target-words <n>` | Target words per chunk | `1000` |
| `-w, --wait` | Wait for job completion (default: submit and exit) | `false` |
| `-h, --help` | Display help for command | - |

**Examples:**

```bash
# Simple text ingestion
kg ingest text -o "Notes" "This is some important information about concepts."

# From command output (pipe)
echo "Neural networks are computational models..." | xargs kg ingest text -o "AI Notes"

# From file with custom filename
cat research.txt | xargs kg ingest text -o "Research" --filename "research-notes"

# Multiline text
kg ingest text -o "Ideas" "$(cat << 'EOF'
Concepts can be interconnected.
Relationships form a graph structure.
Evidence supports each concept.
EOF
)"

# With wait
kg ingest text -o "Quick Test" -w "Testing the knowledge graph system."
```

**Use Cases:**
- Quick testing/prototyping
- Ingesting programmatically generated text
- API/script integration
- Processing text from other commands

---

## Common Options Explained

### Ontology (`-o, --ontology`)

**Required** for all ingestion commands (except directory with `--directories-as-ontologies`).

An ontology is a named collection or knowledge domain that groups related concepts. Examples:
- "Research Papers 2024"
- "Company Documentation"
- "Personal Notes"
- "Project XYZ"

### Chunking Parameters

**`--target-words <n>`** (default: 1000)
- Target size for each semantic chunk
- Actual chunks may be larger/smaller based on natural boundaries
- Range: 500-2000 typically effective

**`--overlap-words <n>`** (default: 200)
- Word overlap between adjacent chunks
- Provides context continuity
- Helps LLM understand cross-chunk relationships

**Example:**
```
Text: 1500 words total
Chunking: target=1000, overlap=200

Chunk 1: words 1-1100 (natural boundary at 1100)
Chunk 2: words 900-1500 (starts 200 words before end of chunk 1)
```

### Processing Mode (`--parallel`)

**Serial (default):**
- Processes chunks sequentially
- Each chunk sees concepts from previous chunks
- Cleaner concept deduplication
- Slower but higher quality

**Parallel (`--parallel`):**
- Processes all chunks simultaneously
- Chunks don't see each other's concepts
- May create duplicate concepts
- Faster for large documents

**Recommendation:** Use serial unless speed is critical.

### Force Re-ingestion (`-f, --force`)

By default, duplicate detection prevents re-ingesting the same content:
- File hash checked against existing sources
- Returns existing job if found

With `--force`:
- Bypasses duplicate detection
- Creates new ingestion job
- Useful for:
  - Testing extraction changes
  - Re-processing after system updates
  - Ingesting multiple versions

### Manual Approval (`--no-approve`)

**Auto-approve (default):**
- Job starts processing immediately after submission
- Uses `autoApprove` config setting

**Manual approval (`--no-approve`):**
- Job enters `awaiting_approval` state
- Must approve via: `kg job approve <job-id>`
- Allows reviewing cost estimate first

Related: ADR-014 (Job Approval Workflow)

### Wait for Completion (`-w, --wait`)

**Submit and exit (default):**
```bash
kg ingest file -o "Docs" readme.md
# Returns immediately with job ID
# Monitor with: kg job status <job-id>
```

**Wait for completion (`-w`):**
```bash
kg ingest file -o "Docs" -w readme.md
# Polls job status until complete
# Shows progress updates
# Returns final results
```

Useful for:
- Synchronous workflows
- Scripts that need results
- Interactive testing

---

## Job Creation and Monitoring

All ingestion commands create jobs with these phases:

1. **Submission** - File uploaded/text submitted
2. **Job Created** - Returns `job_<id>`
3. **Approval** (if not auto-approved) - Waiting for `kg job approve`
4. **Processing** - Extraction and graph insertion
5. **Completion** - Results available

**Monitor Jobs:**
```bash
# List all jobs
kg job list

# Check specific job
kg job status job_abc123

# Follow job logs
kg job logs job_abc123 --follow
```

---

## Ingestion Workflow

```
┌──────────────┐
│ Submit File  │
└──────┬───────┘
       │
       v
┌──────────────┐
│   Chunking   │ (semantic boundaries, overlap)
└──────┬───────┘
       │
       v
┌──────────────┐
│  Create Job  │ (returns job_id)
└──────┬───────┘
       │
       v
    ┌──┴──┐
    │Auto?│
    └──┬──┘
   Yes │ No
       │  │
       │  v
       │ ┌────────────┐
       │ │  Approval  │ (kg job approve)
       │ └──────┬─────┘
       │        │
       v        v
┌─────────────────┐
│   Processing    │
│ • LLM Extract   │
│ • Embed Concepts│
│ • Match Existing│
│ • Insert Graph  │
└────────┬────────┘
         │
         v
┌─────────────────┐
│    Complete     │
└─────────────────┘
```

---

## Common Use Cases

### Single Document Research

```bash
kg ingest file -o "AI Research" -w paper.pdf
kg search query "transformer architecture"
```

### Documentation Project

```bash
# Ingest all markdown
kg ingest directory -o "Project Docs" -r -p "*.md" ./docs/

# Verify
kg database stats
kg ontology info "Project Docs"
```

### Knowledge Base Organization

```bash
# Organize by subdirectory
kg ingest directory --directories-as-ontologies -r ./knowledge-base/

# Creates separate ontologies per topic
```

### Testing Extraction Changes

```bash
# Force re-ingest to test new prompt/model
kg ingest file -o "Test" -f test-doc.md

# Compare results
kg search details concept_123
```

### Batch Processing Script

```bash
#!/bin/bash
for file in ./papers/*.pdf; do
  echo "Ingesting: $file"
  kg ingest file -o "Research Papers 2024" "$file"
done

# Monitor all jobs
kg job list --status processing
```

---

## Performance Considerations

### Small Documents (<5000 words)
```bash
kg ingest file -o "Notes" -w small-doc.txt
# Fast, wait for completion
```

### Large Documents (>50000 words)
```bash
kg ingest file -o "Book" \
  --target-words 1500 \
  --overlap-words 250 \
  large-book.txt
# Higher chunk size = fewer chunks = faster
# Monitor separately, don't wait
```

### Batch Directories
```bash
# Process in parallel if concepts independent
kg ingest directory -o "Archive" --parallel -r ./old-docs/

# Otherwise use serial for better deduplication
kg ingest directory -o "Research" -r ./papers/
```

---

## Troubleshooting

### Job Stuck in Pending

```bash
# Check job status
kg job status job_abc123

# If awaiting approval
kg job approve job_abc123

# If processing but stalled
kg admin status
# Check worker health
```

### Duplicate Detection Issues

```bash
# Force re-ingest
kg ingest file -o "Docs" -f document.txt

# Or delete existing source
kg ontology info "Docs"  # Find source ID
# Then use API to delete source
```

### Poor Concept Extraction

```bash
# Try different chunking
kg ingest file -o "Test" \
  --target-words 800 \
  --overlap-words 300 \
  document.txt

# Check extraction model
kg admin extraction status
```

---

## Related Commands

- [`kg job`](../job/) - Monitor and manage ingestion jobs
- [`kg ontology`](../ontology/) - Manage ontologies
- [`kg search`](../search/) - Query extracted concepts
- [`kg database stats`](../database/#stats) - View ingestion statistics
- [`kg admin extraction`](../admin/#extraction) - Configure extraction settings

---

## See Also

- [Ingestion Guide](../../01-getting-started/ingestion.md)
- [Chunking Strategies](../../06-reference/chunking.md)
- [Job Management](../../06-reference/jobs.md)
- [ADR-014: Job Approval Workflow](../../../architecture/ADR-014-job-approval-workflow.md)
