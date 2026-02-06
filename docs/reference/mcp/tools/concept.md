# concept

> Auto-generated from MCP tool schema

### concept

Work with concepts: get details (ALL evidence + relationships), find related concepts (neighborhood exploration), or discover connections (paths between concepts).

PERFORMANCE CRITICAL: For "connect" action, use threshold >= 0.75 to avoid database overload. Lower thresholds create exponentially larger searches that can hang for minutes. Start with threshold=0.8, max_hops=3, then adjust if needed.

For multi-step workflows (search → connect → expand → filter), compose these into a GraphProgram instead of making individual calls. See the program tool and program/syntax resource.

**Parameters:**

- `action` (`string`) **(required)** - Operation: "details" (get ALL evidence), "related" (explore neighborhood), "connect" (find paths)
  - Allowed values: `details`, `related`, `connect`
- `concept_id` (`string`) - Concept ID (required for details, related)
- `include_grounding` (`boolean`) - Include grounding_strength (default: true)
  - Default: `true`
- `include_diversity` (`boolean`) - Include diversity metrics for details action (default: false, adds ~100-500ms)
  - Default: `false`
- `diversity_max_hops` (`number`) - Max hops for diversity calculation (default: 2)
  - Default: `2`
- `truncate_evidence` (`boolean`) - Truncate evidence full_text context to 200 chars (default: true for token efficiency). Set false for complete context.
  - Default: `true`
- `max_depth` (`number`) - Max traversal depth for related (1-5, default: 2)
  - Default: `2`
- `relationship_types` (`array`) - Filter relationships (e.g., ["SUPPORTS", "CONTRADICTS"])
- `include_epistemic_status` (`array`) - Only include relationships with these epistemic statuses (e.g., ["AFFIRMATIVE", "CONTESTED"])
- `exclude_epistemic_status` (`array`) - Exclude relationships with these epistemic statuses (e.g., ["HISTORICAL", "INSUFFICIENT_DATA"])
- `connection_mode` (`string`) - Connection mode: "exact" (IDs) or "semantic" (phrases)
  - Allowed values: `exact`, `semantic`
  - Default: `"semantic"`
- `from_id` (`string`) - Starting concept ID (for exact mode)
- `to_id` (`string`) - Target concept ID (for exact mode)
- `from_query` (`string`) - Starting phrase (for semantic mode, 2-3 words)
- `to_query` (`string`) - Target phrase (for semantic mode, 2-3 words)
- `max_hops` (`number`) - Max path length (default: 3). WARNING: Values >5 combined with threshold <0.75 can cause severe performance issues.
  - Default: `3`
- `threshold` (`number`) - Similarity threshold for semantic mode (default: 0.75). PERFORMANCE GUIDE: 0.85+ = precise/fast, 0.75-0.84 = balanced, 0.60-0.74 = exploratory/SLOW, <0.60 = DANGEROUS (can hang database for minutes)
  - Default: `0.75`

---
