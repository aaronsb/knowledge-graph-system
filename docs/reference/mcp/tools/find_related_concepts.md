# find_related_concepts

> Auto-generated from MCP tool schema

### find_related_concepts

Explore concept neighborhood. Discovers what's connected and how (SUPPORTS, CONTRADICTS, ENABLES). Returns concepts grouped by distance. Use depth=1-2 for neighbors, 3-4 for broader exploration.

**Parameters:**

- `concept_id` (`string`) **(required)** - Starting concept ID for traversal
- `max_depth` (`number`) - Maximum traversal depth in hops (1-5, default: 2). Depth 1-2 is fast, 3-4 moderate, 5 can be slow.
  - Default: `2`
- `relationship_types` (`array`) - Optional filter for specific relationship types (e.g., ["IMPLIES", "SUPPORTS", "CONTRADICTS"])

---
