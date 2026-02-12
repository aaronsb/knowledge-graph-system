# document

> Auto-generated from MCP tool schema

### document

Work with documents: list all, show content, or get concepts (ADR-084).

Three actions available:
- "list": List all documents with optional ontology filter
- "show": Retrieve document content from Garage storage
- "concepts": Get all concepts extracted from a document

Documents are aggregated from source chunks and stored in Garage (S3-compatible storage).
Use search tool with type="documents" to find documents semantically. Use document (action: "concepts") to see what was extracted, then concept (action: "details") or source to drill into specifics.

**Parameters:**

- `action` (`string`) **(required)** - Operation: "list" (all documents), "show" (content), "concepts" (extracted concepts)
  - Allowed values: `list`, `show`, `concepts`
- `document_id` (`string`) - Document ID (required for show, concepts). Format: sha256:...
- `include_details` (`boolean`) - Include full concept details (evidence, relationships, grounding) in one call. Default: false for lightweight list.
  - Default: `false`
- `ontology` (`string`) - Filter by ontology name (for list)
- `limit` (`number`) - Max documents to return for list (default: 50)
  - Default: `50`
- `offset` (`number`) - Number to skip for pagination (default: 0)
  - Default: `0`

---
