# find_connection

> Auto-generated from MCP tool schema

### find_connection

Find shortest paths between two concepts using exact concept IDs. Uses graph traversal to find up to 5 shortest paths. For semantic phrase matching, use find_connection_by_search instead.

**Parameters:**

- `from_id` (`string`) **(required)** - Starting concept ID (exact match required)
- `to_id` (`string`) **(required)** - Target concept ID (exact match required)
- `max_hops` (`number`) - Maximum path length to search (1-10 hops, default: 5)
  - Default: `5`

---
