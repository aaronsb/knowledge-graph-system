# ingest-file

> Auto-generated from MCP tool schema

### ingest-file

Ingest a single file into the knowledge graph (ADR-062). Validates against allowlist, reads content, handles images with vision AI automatically. Just submit the path - system handles everything else.

**Parameters:**

- `path` (`string`) **(required)** - File path to ingest (absolute or relative, ~ supported)
- `ontology` (`string`) **(required)** - Ontology name for categorization
- `auto_approve` (`boolean`) - Auto-approve processing (default: true)
  - Default: `true`
- `force` (`boolean`) - Force re-ingestion of already processed files (default: false)
  - Default: `false`

---
