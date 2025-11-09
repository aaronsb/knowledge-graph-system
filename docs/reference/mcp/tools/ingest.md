# ingest

> Auto-generated from MCP tool schema

### ingest

Submit text content for concept extraction. Chunks text, extracts concepts using LLM, and adds them to the specified ontology. Returns job ID for tracking.

**Parameters:**

- `text` (`string`) **(required)** - Text content to ingest
- `ontology` (`string`) **(required)** - Ontology name (e.g., "Project Documentation", "Research Notes")
- `filename` (`string`) - Optional filename for source tracking
- `auto_approve` (`boolean`) - Auto-approve processing (default: true)
  - Default: `true`
- `force` (`boolean`) - Force re-ingestion (default: false)
  - Default: `false`
- `processing_mode` (`string`) - Processing mode (default: serial)
  - Allowed values: `serial`, `parallel`
  - Default: `"serial"`
- `target_words` (`number`) - Words per chunk (default: 1000)
  - Default: `1000`
- `overlap_words` (`number`) - Overlap between chunks (default: 200)
  - Default: `200`

---
