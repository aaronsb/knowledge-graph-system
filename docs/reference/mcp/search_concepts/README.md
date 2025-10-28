# search_concepts

> Auto-generated from MCP tool schema

### search_concepts

Search for concepts using semantic similarity. Your ENTRY POINT to the graph. Returns grounding strength + evidence samples. Then use: get_concept_details (all evidence), find_connection_by_search (paths), find_related_concepts (neighbors). Use 2-3 word phrases (e.g., "linear thinking patterns").

**Parameters:**

- `query` (`string`) **(required)** - Search query text (2-3 word phrases work best, e.g., "linear thinking patterns")
- `limit` (`number`) - Maximum number of results to return (default: 10, max: 100)
  - Default: `10`
- `min_similarity` (`number`) - Minimum similarity score 0.0-1.0 (default: 0.7 for 70%, lower to 0.5-0.6 for broader matches)
  - Default: `0.7`
- `offset` (`number`) - Number of results to skip for pagination (default: 0)
  - Default: `0`

---
