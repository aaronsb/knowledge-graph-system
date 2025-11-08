# inspect-file

> Auto-generated from MCP tool schema

### inspect-file

Validate and inspect a file before ingestion (ADR-062). Checks path allowlist, shows metadata (size, type, permissions), and returns validation result. Use this to verify files are allowed before attempting ingestion.

**Parameters:**

- `path` (`string`) **(required)** - File path to inspect (absolute or relative, ~ supported)

---
