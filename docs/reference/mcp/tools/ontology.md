# ontology

> Auto-generated from MCP tool schema

### ontology

Manage ontologies (knowledge domains/collections): list all, get info, list files, or delete. Use action parameter to specify operation.

**Parameters:**

- `action` (`string`) **(required)** - Operation: "list" (all ontologies), "info" (details), "files" (source files), "create" (new ontology), "rename" (change name), "delete" (remove), "lifecycle" (set state), "scores" (cached scores), "score" (recompute one), "score_all" (recompute all), "candidates" (top concepts), "affinity" (cross-ontology overlap), "reassign" (move sources), "dissolve" (non-destructive demotion)
  - Allowed values: `list`, `info`, `files`, `create`, `rename`, `delete`, `lifecycle`, `scores`, `score`, `score_all`, `candidates`, `affinity`, `reassign`, `dissolve`
- `ontology_name` (`string`) - Ontology name (required for info, files, create, rename, delete)
- `description` (`string`) - What this knowledge domain covers (for create action)
- `new_name` (`string`) - New ontology name (required for rename action)
- `lifecycle_state` (`string`) - Target lifecycle state (required for lifecycle action)
  - Allowed values: `active`, `pinned`, `frozen`
- `force` (`boolean`) - Confirm deletion (required for delete)
  - Default: `false`
- `target_ontology` (`string`) - Target ontology for reassign/dissolve actions
- `source_ids` (`array`) - Source IDs to move (for reassign action)
- `limit` (`number`) - Max results for candidates/affinity (default: 20/10)

---
