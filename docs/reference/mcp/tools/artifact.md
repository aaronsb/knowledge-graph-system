# artifact

> Auto-generated from MCP tool schema

### artifact

Manage saved artifacts (ADR-083). Artifacts persist computed results like search results, projections, and polarity analyses for later recall.

Three actions available:
- "list": List artifacts with optional filtering by type, representation, or ontology
- "show": Get artifact metadata by ID (without payload)
- "payload": Get artifact with full payload (for reusing stored analysis)

Use artifacts to:
- Recall previously computed analyses without re-running expensive queries
- Share analysis results across sessions
- Track analysis history with parameters and timestamps
- Check freshness (is_fresh indicates if graph has changed since artifact creation)

**Parameters:**

- `action` (`string`) **(required)** - Operation: "list" (list artifacts), "show" (metadata only), "payload" (full result)
  - Allowed values: `list`, `show`, `payload`
- `artifact_id` (`number`) - Artifact ID (required for show, payload)
- `artifact_type` (`string`) - Filter by type: search_result, projection, polarity_analysis, query_result, etc.
- `representation` (`string`) - Filter by source: cli, mcp_server, polarity_explorer, embedding_landscape, etc.
- `ontology` (`string`) - Filter by associated ontology name
- `limit` (`number`) - Max artifacts to return for list (default: 20)
  - Default: `20`
- `offset` (`number`) - Number to skip for pagination (default: 0)
  - Default: `0`

---
