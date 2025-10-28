# get_concept_details

> Auto-generated from MCP tool schema

### get_concept_details

Retrieve ALL evidence (quoted text) and relationships for a concept. Use to see the complete picture: ALL quotes, source locations, SUPPORTS/CONTRADICTS relationships. Contradicted concepts (negative grounding) are VALUABLE - show problems/outdated approaches.

**Parameters:**

- `concept_id` (`string`) **(required)** - The unique concept identifier (from search results or graph traversal)
- `include_grounding` (`boolean`) - Include grounding_strength calculation (ADR-044: probabilistic truth convergence). Default: true. Set to false only for faster queries when grounding not needed.
  - Default: `true`

---
