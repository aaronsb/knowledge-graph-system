# find_connection_by_search

> Auto-generated from MCP tool schema

### find_connection_by_search

Discover HOW concepts connect. Find paths between ideas, trace problem→solution chains, see grounding+evidence at each step. Returns narrative flow through the graph. Use 2-3 word phrases (e.g., "licensing issues", "AGE benefits").

**Parameters:**

- `from_query` (`string`) **(required)** - Semantic phrase for starting concept (use specific 2-3 word phrases for best results)
- `to_query` (`string`) **(required)** - Semantic phrase for target concept (use specific 2-3 word phrases)
- `max_hops` (`number`) - Maximum path length to search (default: 5)
  - Default: `5`
- `threshold` (`number`) - Minimum similarity threshold 0.0-1.0 (default: 0.5 for 50%, lower to 0.3-0.4 for weaker matches)
  - Default: `0.5`

---
