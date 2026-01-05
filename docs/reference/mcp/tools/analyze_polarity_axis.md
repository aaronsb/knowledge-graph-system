# analyze_polarity_axis

> Auto-generated from MCP tool schema

### analyze_polarity_axis

Analyze bidirectional semantic dimension (polarity axis) between two concept poles (ADR-070).

Projects concepts onto an axis formed by opposing semantic poles (e.g., Modern ↔ Traditional, Centralized ↔ Distributed). Returns:
- Axis quality and magnitude (semantic distinctness)
- Concept positions along the axis (-1 to +1)
- Direction distribution (positive/neutral/negative)
- Grounding correlation patterns
- Statistical analysis of projections

PERFORMANCE: Direct query pattern, ~2-3 seconds execution time.

Use Cases:
- Explore conceptual spectrums and gradients
- Identify position-grounding correlation patterns
- Discover concepts balanced between opposing ideas
- Map semantic dimensions in the knowledge graph

**Parameters:**

- `positive_pole_id` (`string`) **(required)** - Concept ID for positive pole (e.g., ID for "Modern")
- `negative_pole_id` (`string`) **(required)** - Concept ID for negative pole (e.g., ID for "Traditional")
- `candidate_ids` (`array`) - Specific concept IDs to project onto axis (optional)
- `auto_discover` (`boolean`) - Auto-discover related concepts if candidate_ids not provided (default: true)
  - Default: `true`
- `max_candidates` (`number`) - Maximum candidates for auto-discovery (default: 20, max: 100)
  - Default: `20`
- `max_hops` (`number`) - Maximum graph hops for auto-discovery (1-3, default: 1)
  - Default: `1`

---
