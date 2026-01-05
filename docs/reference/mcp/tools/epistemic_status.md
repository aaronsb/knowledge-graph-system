# epistemic_status

> Auto-generated from MCP tool schema

### epistemic_status

Vocabulary epistemic status classification (ADR-065 Phase 2). Knowledge validation state for relationship types.

Three actions available:
- "list": List all vocabulary types with epistemic status classifications (AFFIRMATIVE/CONTESTED/CONTRADICTORY/HISTORICAL/INSUFFICIENT_DATA/UNCLASSIFIED)
- "show": Get detailed status for a specific relationship type
- "measure": Run measurement to calculate epistemic status for all types (admin operation)

EPISTEMIC STATUS CLASSIFICATIONS:
- AFFIRMATIVE: High avg grounding >0.8 (well-established knowledge)
- CONTESTED: Mixed grounding 0.2-0.8 (debated/mixed validation)
- CONTRADICTORY: Low grounding <-0.5 (contradicted knowledge)
- HISTORICAL: Temporal vocabulary (detected by name)
- INSUFFICIENT_DATA: <3 successful measurements
- UNCLASSIFIED: Doesn't fit known patterns

Use for filtering relationships by epistemic reliability, identifying contested knowledge areas, and curating high-confidence vs exploratory subgraphs.

**Parameters:**

- `action` (`string`) **(required)** - Operation: "list" (all types), "show" (specific type), "measure" (run measurement)
  - Allowed values: `list`, `show`, `measure`
- `status_filter` (`string`) - Filter by status for list action: AFFIRMATIVE, CONTESTED, CONTRADICTORY, HISTORICAL, INSUFFICIENT_DATA, UNCLASSIFIED
- `relationship_type` (`string`) - Relationship type to show (required for show action, e.g., "IMPLIES", "SUPPORTS")
- `sample_size` (`number`) - Edges to sample per type for measure action (default: 100)
  - Default: `100`
- `store` (`boolean`) - Store results to database for measure action (default: true)
  - Default: `true`
- `verbose` (`boolean`) - Include detailed statistics for measure action (default: false)
  - Default: `false`

---
