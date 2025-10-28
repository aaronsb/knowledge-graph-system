# ingest_text

> Auto-generated from MCP tool schema

### ingest_text

Ingest raw text content into the knowledge graph. Creates a job with cost estimation. Use auto_approve=true to skip approval or approve manually with approve_job.

**Parameters:**

- `text` (`string`) **(required)** - Text content to ingest
- `ontology` (`string`) **(required)** - Ontology/collection name to organize concepts
- `filename` (`string`) - Optional filename for source tracking (default: "text_input")
- `auto_approve` (`boolean`) - Auto-approve job and skip manual review (default: false)
  - Default: `false`
- `force` (`boolean`) - Force re-ingestion even if content already exists (default: false)
  - Default: `false`
- `processing_mode` (`string`) - Processing mode: serial (clean, recommended) or parallel (fast, may duplicate concepts)
  - Allowed values: `serial`, `parallel`
  - Default: `"serial"`
- `target_words` (`number`) - Target words per chunk (default: 1000, range: 500-2000)
  - Default: `1000`
- `overlap_words` (`number`) - Word overlap between chunks for context (default: 200)
  - Default: `200`

---
