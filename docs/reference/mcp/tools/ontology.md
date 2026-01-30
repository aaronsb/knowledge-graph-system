# ontology

> Auto-generated from MCP tool schema

### ontology

Manage ontologies (knowledge domains/collections): list all, get info, list files, or delete. Use action parameter to specify operation.

**Parameters:**

- `action` (`string`) **(required)** - Operation: "list" (all ontologies), "info" (details), "files" (source files), "create" (new ontology), "rename" (change name), "delete" (remove), "lifecycle" (set state)
  - Allowed values: `list`, `info`, `files`, `create`, `rename`, `delete`, `lifecycle`
- `ontology_name` (`string`) - Ontology name (required for info, files, create, rename, delete)
- `description` (`string`) - What this knowledge domain covers (for create action)
- `new_name` (`string`) - New ontology name (required for rename action)
- `lifecycle_state` (`string`) - Target lifecycle state (required for lifecycle action)
  - Allowed values: `active`, `pinned`, `frozen`
- `force` (`boolean`) - Confirm deletion (required for delete)
  - Default: `false`

---
