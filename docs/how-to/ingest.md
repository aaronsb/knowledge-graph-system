---
id: 3.H.01
domain: ingest
mode: how-to
---

# Ingest Documents

Add documents to Kappa Graph so their concepts and relationships become queryable.

## Supported formats

| Format | Extension |
|--------|-----------|
| Plain text | `.txt` |
| Markdown | `.md` |
| PDF | `.pdf` |
| Word | `.docx` |
| Images | `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.bmp` |

Images are described by the configured vision model before chunking; the resulting text is ingested as a normal document.

## How ingestion works

Submitting a document creates an ingestion job. The job passes through these stages:

1. **pending (analyzing)** — cost estimation runs without calling the AI extraction model.
2. **awaiting_approval** — estimates are ready; the job waits for approval.
3. **approved** — approved manually or automatically; the lane manager picks it up.
4. **processing** — documents are chunked (~1000 words, 200-word overlap), each chunk is analyzed by the extraction model, and concepts are upserted to the graph.
5. **completed** — all concepts and relationships are in the graph.

The CLI auto-approves by default. The API does not; use `auto_approve=true` to skip manual approval when calling the API directly.

## Ingest a file

```bash
kg ingest file /path/to/document.pdf -o "research-papers"
```

The `-o`/`--ontology` flag is required. If the named ontology does not exist, it is created.

**Wait for completion** (polls until done and streams progress):

```bash
kg ingest file /path/to/document.pdf -o "research-papers" -w
```

**Require manual approval** (job pauses at `awaiting_approval`):

```bash
kg ingest file /path/to/document.pdf -o "research-papers" --no-approve
```

**Re-ingest after a model or prompt update** (bypasses duplicate detection):

```bash
kg ingest file /path/to/document.pdf -o "research-papers" --force
```

## Ingest a directory

```bash
kg ingest directory /path/to/docs/ -o "codebase" -r --depth all
```

`-r`/`--recurse` with `--depth <n>` or `--depth all` controls how deep the scan goes. Pass `--directories-as-ontologies` to create one ontology per subdirectory automatically.

## Ingest raw text

```bash
kg ingest text "Some text content" -o "notes"
```

Useful for piped output or programmatically generated content. Chunking behavior is identical to file ingestion.

## Check job status

```bash
kg job list
kg job status <job-id>
kg job status <job-id> --watch    # streams live updates
```

## Use the web interface

1. Navigate to **Ingest** in the top menu.
2. Upload files using the file picker or drag-and-drop.
3. Select an ontology (or type a new name to create one).
4. Review the cost estimate — tokens and approximate cost appear before processing starts.
5. Click **Approve** to begin processing.
6. Monitor progress in the **Jobs** view.

## Use the API

```bash
# File upload
curl -X POST "http://localhost:8000/ingest" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@document.pdf" \
  -F "ontology=research" \
  -F "auto_approve=true"

# Raw text
curl -X POST "http://localhost:8000/ingest/text" \
  -H "Authorization: Bearer $TOKEN" \
  -F "text=Some text content" \
  -F "ontology=notes" \
  -F "auto_approve=true"
```

Both endpoints return a `job_id`. Poll `GET /jobs/<job_id>` for status or stream progress with `GET /jobs/<job_id>/stream`.

## Manage ontologies

Ontologies are named collections of related knowledge. Use them to separate topics and control access.

```bash
# List all ontologies
kg ontology list

# View details (file count, concept count, evidence)
kg ontology info "climate-research"
```

An ontology in the **frozen** lifecycle state rejects new ingestion. Set it back to `active` before ingesting.

## Troubleshooting

**Job stuck in `awaiting_approval`**

The job was submitted with `--no-approve`. Approve it:

```bash
kg job approve job <job-id>
```

**Extraction results look wrong**

Check which AI extraction provider and model are active:

```bash
kg admin extraction config
```

Different models produce different extraction quality. See [Configure AI Providers](ai-providers.md) to switch providers.

**Duplicate detected unexpectedly**

The system hashes document content (SHA-256) and skips re-ingestion of identical content in the same ontology. Use `--force` to override:

```bash
kg ingest file document.pdf -o "research" --force
```

**Memory exhaustion on large documents**

Large documents with many chunks can exhaust available memory. Reduce load by splitting the document into smaller files, or lower `MAX_CONCURRENT_JOBS` in the platform configuration (requires an API restart).
