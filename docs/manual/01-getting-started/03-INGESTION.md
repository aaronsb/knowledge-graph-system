# Ingesting Documents

How to add documents to your knowledge graph.

## Overview

Ingestion is how documents become knowledge. When you ingest a document:

1. The system stores the original text
2. Splits it into manageable chunks
3. Extracts concepts from each chunk
4. Discovers relationships between concepts
5. Calculates grounding based on evidence

## Supported Formats

| Format | Extension | Notes |
|--------|-----------|-------|
| Plain text | `.txt` | Direct processing |
| Markdown | `.md` | Preserves structure |
| PDF | `.pdf` | Text extraction |
| Word | `.docx` | Text extraction |
| Web pages | URL | Fetches and processes |

## Using the CLI

The `kg ingest` command has three subcommands: `file`, `directory`, and `text`. The `--ontology` (`-o`) flag is **required** for `file` and `text`.

### Basic File Ingestion

```bash
kg ingest file /path/to/document.pdf -o "research-papers"
```

By default, jobs auto-approve and processing starts immediately. Use `--no-approve` to require manual approval (job enters `awaiting_approval` until you run `kg job approve <id>`).

### Require Manual Approval

```bash
kg ingest file /path/to/document.pdf -o "research-papers" --no-approve
```

### Wait for Completion

By default, ingestion submits the job and returns immediately. Pass `-w` to wait and stream progress:

```bash
kg ingest file /path/to/document.pdf -o "research-papers" -w
```

### Specify an Ontology

The `-o`/`--ontology` flag groups concepts into a named collection. If the ontology doesn't exist, it's created automatically.

### Ingest a Directory

```bash
kg ingest directory /path/to/docs/ -o "codebase" -r --depth all
```

Use `-r/--recurse` with `--depth <n>` (or `--depth all`) for recursive scans. Pass `--directories-as-ontologies` to auto-create an ontology per subdirectory.

### Ingest Raw Text

```bash
kg ingest text "Some text content" -o "notes"
```

### Check Job Status

```bash
kg job list
kg job status <job-id>
kg job status <job-id> --watch    # live updates
```

## Using the Web Interface

1. **Navigate to Ingest** in the top menu
2. **Upload file(s)** using the file picker or drag-and-drop
3. **Select ontology** (or create new)
4. **Review cost estimate** - shows expected tokens and cost
5. **Approve** to start processing
6. **Monitor progress** in the Jobs view

## Using the API

```bash
curl -X POST "http://localhost:8000/ingest" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@document.pdf" \
  -F "ontology=research"
```

Response includes a job ID for tracking.

## What Happens During Ingestion

### 1. Document Storage

The original document is stored in Garage (object storage). You can always retrieve it later.

### 2. Chunking

Documents are split into chunks of roughly 1000 words, with overlap to preserve context across boundaries. This ensures:
- Each chunk is small enough to process
- Ideas that span page breaks aren't lost

### 3. Concept Extraction

Each chunk is analyzed by an AI model (GPT-4, Claude, etc.) to extract:
- **Concepts**: The key ideas
- **Types**: What kind of idea (claim, definition, entity, etc.)
- **Relationships**: How concepts in this chunk relate

### 4. Matching

New concepts are compared to existing ones. If a concept already exists:
- They're merged (same idea, more evidence)
- Grounding increases (more sources confirm it)

If concepts conflict:
- Both are kept
- Contradiction is noted
- Sources are preserved for both views

### 5. Grounding Calculation

After extraction, grounding scores are calculated:
- How many sources mention this concept?
- Do they agree or disagree?
- How strong is the evidence?

## Cost Estimation

Before processing, the system estimates:
- Number of chunks
- Expected tokens (input + output)
- Approximate cost (based on your AI provider's pricing)

This is why jobs require approval by default - so you can review before incurring costs.

## Ontologies

Ontologies are collections of related knowledge. Use them to:
- Separate different topics (research vs meeting-notes)
- Query specific domains
- Control who can access what

```bash
# Create by ingesting with a new name
kg ingest file paper1.pdf -o "climate-research"

# List ontologies
kg ontology list

# View ontology details (file count, concepts, evidence)
kg ontology info "climate-research"
```

## Tips

### Start Small
Ingest a few documents first to understand the output before processing large collections.

### Use Meaningful Ontology Names
You'll query by ontology later. Names like "research-2024" are clearer than "stuff".

### Review Extractions
After ingesting, search for concepts and verify they match what you expected. This helps you understand how the system interprets your documents.

### Re-ingest if Needed
If extraction quality improves (new models, updated prompts), you can re-ingest documents (use `--force` to bypass duplicate detection). The system deduplicates based on content hashes.

## Troubleshooting

### Job Stuck in `awaiting_approval`
Approve it:
```bash
kg job approve <job-id>
```

Auto-approve is the default; jobs only enter `awaiting_approval` when `--no-approve` was passed.

### Extraction Seems Wrong
Check the active AI extraction provider/model:
```bash
kg admin extraction config
```

Different models have different extraction quality.

### Out of Memory
Large documents with many chunks can exhaust memory. Try:
- Splitting into smaller files
- Reducing `MAX_CONCURRENT_JOBS` in configuration
- Using a machine with more RAM

## Next Steps

- [Exploring Knowledge](../../guides/exploring.md) - Navigate what you've ingested
- [Understanding Grounding](../../guides/understanding-grounding.md) - Interpret confidence scores
