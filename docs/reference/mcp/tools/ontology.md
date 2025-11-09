# ontology

> Auto-generated from MCP tool schema

### ontology

Manage ontologies (knowledge domains/collections): list all, get info, list files, or delete. Use action parameter to specify operation.

**Parameters:**

- `action` (`string`) **(required)** - Operation: "list" (all ontologies), "info" (details), "files" (source files), "delete" (remove)
  - Allowed values: `list`, `info`, `files`, `delete`
- `ontology_name` (`string`) - Ontology name (required for info, files, delete)
- `force` (`boolean`) - Confirm deletion (required for delete)
  - Default: `false`

---
