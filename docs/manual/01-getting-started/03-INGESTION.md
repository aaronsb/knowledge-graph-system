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

### Basic Ingestion

```bash
kg ingest /path/to/document.pdf
```

This creates a job that requires approval (to confirm cost estimate).

### Auto-Approve

Skip the approval step:

```bash
kg ingest --auto-approve /path/to/document.pdf
```

### Specify an Ontology

Organize documents into collections:

```bash
kg ingest --ontology "research-papers" /path/to/paper.pdf
```

If the ontology doesn't exist, it's created automatically.

### Ingest Multiple Files

```bash
kg ingest --ontology "project-docs" doc1.md doc2.md doc3.pdf
```

### Ingest a Directory

```bash
kg ingest --ontology "codebase" --recursive /path/to/docs/
```

### Check Job Status

```bash
kg job list
kg job status <job-id>
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
kg ingest --ontology "climate-research" paper1.pdf

# List ontologies
kg ontology list

# Query specific ontology
kg search --ontology "climate-research" "temperature effects"
```

## Tips

### Start Small
Ingest a few documents first to understand the output before processing large collections.

### Use Meaningful Ontology Names
You'll query by ontology later. Names like "research-2024" are clearer than "stuff".

### Review Extractions
After ingesting, search for concepts and verify they match what you expected. This helps you understand how the system interprets your documents.

### Re-ingest if Needed
If extraction quality improves (new models, updated prompts), you can re-ingest documents. The system deduplicates based on content hashes.

## Troubleshooting

### Job Stuck in Pending
Approve it:
```bash
kg job approve <job-id>
```

Or use `--auto-approve` when ingesting.

### Extraction Seems Wrong
Check which AI provider you're using:
```bash
kg config show
```

Different models have different extraction quality.

### Out of Memory
Large documents with many chunks can exhaust memory. Try:
- Splitting into smaller files
- Reducing `MAX_CONCURRENT_JOBS` in configuration
- Using a machine with more RAM

## Next Steps

- [Exploring Knowledge](exploring.md) - Navigate what you've ingested
- [Understanding Grounding](understanding-grounding.md) - Interpret confidence scores
