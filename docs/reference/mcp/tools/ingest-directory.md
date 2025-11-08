# ingest-directory

> Auto-generated from MCP tool schema

### ingest-directory

Ingest all files from a directory (ADR-062). Validates against allowlist, processes recursively if requested, auto-names ontology by directory structure. Skips blocked files automatically.

**Parameters:**

- `path` (`string`) **(required)** - Directory path to ingest (absolute or relative, ~ supported)
- `ontology` (`string`) - Ontology name (optional - defaults to directory name)
- `recursive` (`boolean`) - Process subdirectories recursively (default: false)
  - Default: `false`
- `auto_approve` (`boolean`) - Auto-approve processing (default: true)
  - Default: `true`
- `force` (`boolean`) - Force re-ingestion (default: false)
  - Default: `false`
- `limit` (`number`) - Number of files to show per page (default: 10)
  - Default: `10`
- `offset` (`number`) - Number of files to skip for pagination (default: 0)
  - Default: `0`

---
