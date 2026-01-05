# ingest

> Auto-generated from MCP tool schema

### ingest

Ingest content into the knowledge graph: submit text, inspect files, ingest files, or ingest directories. Use action parameter to specify operation.

**Parameters:**

- `action` (`string`) **(required)** - Operation: "text" (raw text), "inspect-file" (validate), "file" (ingest files), "directory" (ingest directory)
  - Allowed values: `text`, `inspect-file`, `file`, `directory`
- `text` (`string`) - Text content to ingest (required for text action)
- `ontology` (`string`) - Ontology name (required for text/file/directory, optional for directory - defaults to dir name)
- `filename` (`string`) - Optional filename for source tracking (text action)
- `processing_mode` (`string`) - Processing mode (text action, default: serial)
  - Allowed values: `serial`, `parallel`
  - Default: `"serial"`
- `target_words` (`number`) - Words per chunk (text action, default: 1000)
  - Default: `1000`
- `overlap_words` (`number`) - Overlap between chunks (text action, default: 200)
  - Default: `200`
- `path` (`any`) - File/directory path (required for inspect-file/file/directory). For file action: single path string OR array for batch
- `auto_approve` (`boolean`) - Auto-approve processing (file/directory actions, default: true)
  - Default: `true`
- `force` (`boolean`) - Force re-ingestion (file/directory actions, default: false)
  - Default: `false`
- `recursive` (`boolean`) - Process subdirectories recursively (directory action, default: false)
  - Default: `false`
- `limit` (`number`) - Number of files to show per page (directory action, default: 10)
  - Default: `10`
- `offset` (`number`) - Number of files to skip for pagination (directory action, default: 0)
  - Default: `0`

---
