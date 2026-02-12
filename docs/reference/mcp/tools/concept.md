# concept

> Auto-generated from MCP tool schema

### concept

Work with concepts: get details (ALL evidence + relationships), find related concepts (neighborhood exploration), or discover connections (paths between concepts).

For "connect" action, defaults (threshold=0.5, max_hops=5) match the CLI and work well for most queries. Use higher thresholds (0.75+) only if you need to narrow results for precision. Note: connect traverses semantic edges only (IMPLIES, SUPPORTS, CONTRADICTS, etc.) — manually-created edges with no traversal history may not appear in paths. Use program/Cypher for comprehensive traversal.

If connect returns no paths or you need to combine multiple lookups, escalate to the program tool — one composed query replaces many individual calls. Do not repeat connect hoping for different results.

For multi-step workflows (search → connect → expand → filter), compose these into a GraphProgram instead of making individual calls. For example, seed from a search then expand via Cypher using $W_IDS to reference accumulated concept IDs. See the program tool and program/syntax resource for this and other composition patterns.

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
- `relationship_types` (`array`) - Filter relationships (e.g., ["SUPPORTS", "CONTRADICTS"]). Constrains traversal, not just results — omit for broadest results, then narrow.
- `include_epistemic_status` (`array`) - Only include relationships with these epistemic statuses (e.g., ["AFFIRMATIVE", "CONTESTED"])
- `exclude_epistemic_status` (`array`) - Exclude relationships with these epistemic statuses (e.g., ["HISTORICAL", "INSUFFICIENT_DATA"])
- `connection_mode` (`string`) - Connection mode: "exact" (IDs) or "semantic" (phrases)
  - Allowed values: `exact`, `semantic`
  - Default: `"semantic"`
- `from_id` (`string`) - Starting concept ID (for exact mode)
- `to_id` (`string`) - Target concept ID (for exact mode)
- `from_query` (`string`) - Starting phrase (for semantic mode, 2-3 words)
- `to_query` (`string`) - Target phrase (for semantic mode, 2-3 words)
- `max_hops` (`number`) - Max path length (default: 5). Higher values find longer paths but take more time.
  - Default: `5`
- `threshold` (`number`) - Similarity threshold for semantic mode (default: 0.5). Lower values find broader matches. The API enforces backend safety limits.
  - Default: `0.5`

---
