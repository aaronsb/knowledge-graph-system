# graph

> Auto-generated from MCP tool schema

### graph

Create, edit, delete, and list concepts and edges in the knowledge graph (ADR-089).

This tool provides deterministic graph editing without going through the LLM ingest pipeline.
Use for manual curation, agent-driven knowledge building, and precise graph manipulation.

**Actions:**
- "create": Create a new concept or edge
- "edit": Update an existing concept or edge
- "delete": Delete a concept or edge
- "list": List concepts or edges with filters

**Entity Types:**
- "concept": Knowledge graph concepts (nodes)
- "edge": Relationships between concepts

**Matching Modes (for create):**
- "auto": Link to existing if match found, create if not (default)
- "force_create": Always create new, even if similar exists
- "match_only": Only link to existing, error if no match

**Semantic Resolution:**
- Use `from_label`/`to_label` to reference concepts by name instead of ID
- Resolution uses vector similarity (75% threshold) to find matching concepts
- Near-misses (60-75%) return "Did you mean?" suggestions with concept IDs

**Examples:**
- Create concept: `{action: "create", entity: "concept", label: "CAP Theorem", ontology: "distributed-systems"}`
- Create edge: `{action: "create", entity: "edge", from_label: "CAP Theorem", to_label: "Partition Tolerance", relationship_type: "REQUIRES"}`
- List concepts: `{action: "list", entity: "concept", ontology: "distributed-systems"}`
- Delete concept: `{action: "delete", entity: "concept", concept_id: "c_abc123"}`

**Queue Mode** (batch multiple operations in one call):
```json
{
  "action": "queue",
  "operations": [
    {"op": "create", "entity": "concept", "label": "A", "ontology": "test"},
    {"op": "create", "entity": "concept", "label": "B", "ontology": "test"},
    {"op": "create", "entity": "edge", "from_label": "A", "to_label": "B", "relationship_type": "IMPLIES"}
  ]
}
```
Queue executes sequentially, continues past errors by default (set continue_on_error=false to stop on first error). Max 20 operations.

**Parameters:**

- `action` (`string`) **(required)** - Operation to perform. Use "queue" to batch multiple operations.
  - Allowed values: `create`, `edit`, `delete`, `list`, `queue`
- `entity` (`string`) - Entity type (required for create/edit/delete/list, not for queue)
  - Allowed values: `concept`, `edge`
- `operations` (`array`) - Array of operations for queue action (max 20). Each has op, entity, and action-specific fields.
- `continue_on_error` (`boolean`) - For queue: continue executing after errors (default: true). Set false to stop on first error.
  - Default: `true`
- `label` (`string`) - Concept label (required for create concept)
- `ontology` (`string`) - Ontology/namespace (required for create concept, optional filter for list)
- `description` (`string`) - Concept description (optional)
- `search_terms` (`array`) - Alternative search terms for the concept
- `matching_mode` (`string`) - How to handle similar existing concepts (default: auto)
  - Allowed values: `auto`, `force_create`, `match_only`
  - Default: `"auto"`
- `from_concept_id` (`string`) - Source concept ID (for edge create/delete)
- `to_concept_id` (`string`) - Target concept ID (for edge create/delete)
- `from_label` (`string`) - Source concept by label (semantic resolution)
- `to_label` (`string`) - Target concept by label (semantic resolution)
- `relationship_type` (`string`) - Edge relationship type (e.g., IMPLIES, SUPPORTS, CONTRADICTS)
- `category` (`string`) - Semantic category of the relationship (default: structural)
  - Allowed values: `logical_truth`, `causal`, `structural`, `temporal`, `comparative`, `functional`, `definitional`
  - Default: `"structural"`
- `confidence` (`number`) - Edge confidence 0.0-1.0 (default: 1.0)
  - Default: `1`
- `concept_id` (`string`) - Concept ID (for edit/delete concept)
- `label_contains` (`string`) - Filter concepts by label substring (for list)
- `creation_method` (`string`) - Filter by creation method (for list)
- `source` (`string`) - Filter edges by source (for list)
- `limit` (`number`) - Max results to return (default: 20)
  - Default: `20`
- `offset` (`number`) - Number to skip for pagination (default: 0)
  - Default: `0`
- `cascade` (`boolean`) - For concept delete: also delete orphaned synthetic sources (default: false)
  - Default: `false`

---
