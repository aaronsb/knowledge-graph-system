---
id: 8.H.04
domain: ai
mode: how-to
---

# Analyze a Polarity Axis

Polarity axis analysis positions concepts along a semantic spectrum defined by two opposing poles. Given a "positive" and a "negative" concept, the feature projects related concepts onto a −1 to +1 scale and measures how well each concept aligns with either pole — or sits orthogonal to the axis entirely.

Implemented in ADR-813. API endpoint: `POST /query/polarity-axis`. CLI: `kg polarity analyze`. MCP tool: `analyze_polarity_axis`.

---

## Find your pole concept IDs

Polarity analysis requires concept IDs, not labels. Use `kg search` to locate them:

```bash
kg search "modern operating model" --limit 1 --json | jq -r '.results[0].concept_id'
# → sha256:abc123...

kg search "traditional hierarchy" --limit 1 --json | jq -r '.results[0].concept_id'
# → sha256:def456...
```

Good poles are semantically opposite along a single dimension: Modern ↔ Traditional, Centralized ↔ Distributed, Empirical ↔ Theoretical. Poles that differ across multiple dimensions (Car ↔ Airplane) or are near-synonyms produce weak axes.

---

## Run the analysis

### CLI

```bash
# Default: auto-discover up to 20 related concepts, 1 graph hop
kg polarity analyze \
  --positive sha256:abc123 \
  --negative sha256:def456

# Expand the candidate pool
kg polarity analyze \
  --positive sha256:abc123 \
  --negative sha256:def456 \
  --max-candidates 50 \
  --max-hops 2

# Save result as a persistent artifact
kg polarity analyze \
  --positive sha256:abc123 \
  --negative sha256:def456 \
  --save-artifact

# JSON output for scripting
kg polarity analyze \
  --positive sha256:abc123 \
  --negative sha256:def456 \
  --json > analysis.json
```

Discovery mode controls how candidates are selected when `--candidates` is not supplied:

| `--discovery-mode` | Behaviour |
|---|---|
| `conservative` | Degree-ranked neighbours only |
| `balanced` (default) | 80% degree-ranked + 20% random |
| `novelty` | Random only |

Override with `--discovery-pct <0.0–1.0>` for a custom mix.

### MCP

```
analyze_polarity_axis(
  positive_pole_id="sha256:abc123",
  negative_pole_id="sha256:def456",
  auto_discover=true,
  max_candidates=20,
  max_hops=1
)
```

Pass `candidate_ids` as an array to project a specific set of concepts instead of auto-discovering.

### API

```bash
curl -X POST http://localhost:8000/query/polarity-axis \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "positive_pole_id": "sha256:abc123",
    "negative_pole_id": "sha256:def456",
    "auto_discover": true,
    "max_candidates": 20,
    "max_hops": 1
  }'
```

---

## Read the output

### Axis quality

```
Positive pole: Modern Ways of Working
  Grounding: 0.104
Negative pole: Traditional Operating Models
  Grounding: -0.040
Magnitude: 0.9735
Quality: strong
```

**Magnitude** measures semantic distinctness between poles. A magnitude above 0.9 is strong; below 0.5 means the poles are too similar to form a useful axis. **Quality** is `strong` when magnitude exceeds the threshold, `weak` otherwise. If the axis is weak, try more opposing concepts.

### Statistics

```
Total concepts: 20
Position range: [-0.734, 0.266]
Mean position: -0.079
Mean axis distance: 0.923

Direction distribution:
  Positive (> 0.3):    0
  Neutral  (-0.3–0.3): 18
  Negative (< -0.3):   2
```

**Mean position** near 0 means the candidate set is balanced across the axis. **Mean axis distance** near 1.0 means most concepts are orthogonal to this dimension — the axis does not explain the candidate set well.

### Concept projections

Each concept in the result carries:

| Field | Meaning |
|---|---|
| `position` | −1 (negative pole) to +1 (positive pole) |
| `direction` | `positive`, `neutral`, or `negative` |
| `grounding` | Evidence reliability score |
| `axis_distance` | Orthogonality — how far the concept sits off the axis |

**Axis distance** is the most important field for filtering:

- **< 0.5** — concept lies close to the axis; this dimension explains it well
- **> 1.0** — concept is largely orthogonal; other dimensions are more relevant

High-distance concepts can be good starting points for a different axis.

### Grounding correlation

```
Pearson r: -0.258
p-value: 0.271
Interpretation: Weak negative correlation
```

| Pearson r | Meaning |
|---|---|
| r > 0.7 | Strong positive correlation — concepts near the positive pole have higher grounding |
| 0.3–0.7 | Moderate positive correlation |
| −0.3–0.3 | No correlation — position and grounding are independent |
| −0.7 to −0.3 | Moderate negative correlation |
| r < −0.7 | Strong negative correlation — negative pole has higher grounding |

Trust the correlation only when p-value < 0.05. With fewer than ~30 concepts, correlations are often not statistically significant.

A weak or absent correlation is often correct — Empirical ↔ Theoretical and Local ↔ Global are descriptive axes where neither pole is "better."

---

## Common patterns

### Find synthesis concepts

Concepts with position near 0.0 and low axis distance are balanced between the poles:

```bash
kg polarity analyze \
  --positive sha256:centralized-id \
  --negative sha256:distributed-id \
  --max-candidates 50 \
  --json | \
  jq '[.projections[] | select((.position | fabs) < 0.15 and .axis_distance < 0.5)]'
```

### Find orthogonal concepts

Concepts that do not fit the current axis may anchor a different one:

```bash
kg polarity analyze --positive <p1> --negative <n1> --json | \
  jq '[.projections[] | select(.axis_distance > 1.0) | {label, axis_distance, position}]'
```

### Multi-axis comparison

Run analyses across several axes and cross-reference by concept ID:

```bash
kg polarity analyze --positive <modern-id>      --negative <traditional-id>   --json > axis1.json
kg polarity analyze --positive <centralized-id> --negative <distributed-id>   --json > axis2.json
```

Then join on `concept_id` to find concepts with a specific profile across both axes — for example, modern and distributed.

### Track how positions shift over time

Re-run the same pole pair after adding documents and diff the JSON:

```bash
kg polarity analyze --positive <p1> --negative <n1> --json > snapshot-before.json
# ... ingest new documents ...
kg polarity analyze --positive <p1> --negative <n1> --json > snapshot-after.json
diff snapshot-before.json snapshot-after.json
```

Position shifts mean concepts have accumulated new evidence. New concepts appearing in the result mean the graph has expanded into this area.

---

## Performance

Synchronous analysis runs in roughly 2–3 seconds for 20 candidates. Scaling is approximately linear: 50 candidates ≈ 5 seconds, 100 candidates ≈ 10 seconds. The grounding calculation and 2-hop graph traversal are the dominant costs.

Use `--save-artifact` when the result should persist across sessions. This routes the request through the async job queue and stores the payload as an artifact retrievable with `kg artifact payload <id>`.

---

## Troubleshooting

**Axis quality is weak.** The poles are not semantically distinct. Check whether they are near-synonyms, then try more opposing concepts.

**All concepts cluster near one pole.** Your knowledge base has asymmetric coverage of this dimension. Accept the clustering as a signal, or try different poles that better span the content you have ingested.

**Very high axis distances across the board.** The axis does not explain the candidate set — the space is multi-dimensional along this query. High-distance concepts are good candidates for pole pairs on a different axis.

**No grounding correlation.** This is normal for descriptive axes. It only warrants investigation if you expected a value polarity, the magnitude is high (> 0.8), and the sample is large (> 30 concepts).

---

## Related

- ADR-813 — Polarity Axis Analysis design decision
- ADR-811 — Polarity Axis Triangulation for Grounding
- ADR-808 — Probabilistic Truth Convergence (grounding calculation)
- [Explore and Query](query.md) — finding concept IDs and traversing relationships
