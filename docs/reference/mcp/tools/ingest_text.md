# ingest_text

> Auto-generated from MCP tool schema

### ingest_text

Submit text content to the knowledge graph for concept extraction. Automatically processes and extracts concepts, relationships, and evidence. Specify which ontology (knowledge domain) to add the concepts to. The system will chunk the text, extract concepts using LLM, and add them to the graph. Returns a job ID for tracking progress.

**Parameters:**

- `text` (`string`) **(required)** - Text content to ingest into the knowledge graph
- `ontology` (`string`) **(required)** - Ontology/collection name (ask user which knowledge domain this belongs to, e.g., "Project Documentation", "Research Notes", "Meeting Notes")
- `filename` (`string`) - Optional filename for source tracking (default: "text_input")
- `auto_approve` (`boolean`) - Auto-approve and start processing immediately (default: true). Set to false to require manual approval.
  - Default: `true`
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
