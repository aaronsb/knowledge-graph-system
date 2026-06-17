---
id: 06.004.H
domain: vocab
mode: how-to
---

# Filter by Epistemic Status

Epistemic status filtering narrows relationship queries to only those vocabulary types whose grounding patterns meet a confidence threshold. Before filtering is available, you must measure and store those patterns with the CLI.

---

## Epistemic status classifications

The system assigns each vocabulary type one of seven statuses based on its average grounding score across a sampled set of edges.

| Status | Average grounding | Meaning |
|---|---|---|
| `WELL_GROUNDED` | > 0.8 | High-confidence, well-supported relationships |
| `MIXED_GROUNDING` | 0.15 – 0.8 | Variable validation; evidence exists on both sides |
| `WEAK_GROUNDING` | 0.0 – 0.15 | Emerging evidence; pattern not yet established |
| `POORLY_GROUNDED` | −0.5 – 0.0 | Weak negative grounding; uncertain |
| `CONTRADICTED` | < −0.5 | Strong negative grounding; relationships are refuted |
| `HISTORICAL` | N/A | Temporal vocabulary detected by name pattern |
| `INSUFFICIENT_DATA` | N/A | Fewer than 3 measurements; cannot classify |

Statuses are temporal measurements, not permanent labels. As your graph grows, re-run measurement to keep them current.

---

## Step 1: Measure epistemic status

Run the measurement command to analyze grounding patterns and store results to the database:

```bash
kg vocab epistemic-status measure
```

Flags:

| Flag | Default | Effect |
|---|---|---|
| `--sample-size <n>` | `100` | Edges sampled per vocabulary type |
| `--no-store` | off | Run analysis without writing to the database |
| `--verbose` | off | Include per-type uncertainty metrics in output |

Example output:

```
Epistemic Status Measurement Report
=================================

Summary:
  MIXED_GROUNDING: 1
  POORLY_GROUNDED: 6
  INSUFFICIENT_DATA: 28

MIXED_GROUNDING (1)
  • ENABLES
    8 measurements from 8/8 edges | avg grounding: +0.232

Storing epistemic statuses to VocabType nodes...
✓ Stored 35/35 epistemic statuses to VocabType nodes
  Phase 2 query filtering now available via GraphQueryFacade.match_concept_relationships()
```

When to increase sample size:

| `--sample-size` | Measurement time | Precision | When to use |
|---|---|---|---|
| 20 | ~10 s | Low | Quick check |
| 100 (default) | ~30 s | Medium | Standard use |
| 500 | ~2 min | High | Important decisions |
| 1000 | ~5 min | Very high | Research validation |

---

## Step 2: Query with epistemic status filters

Pass `include_epistemic_status` or `exclude_epistemic_status` to `GraphQueryFacade.match_concept_relationships()`.

**Include only high-confidence relationships:**

```python
from api.app.lib.age_client import AGEClient

client = AGEClient()
facade = client.facade

well_grounded = facade.match_concept_relationships(
    include_epistemic_status=["WELL_GROUNDED"],
    limit=10
)
```

**Exclude historical relationships (current state only):**

```python
current = facade.match_concept_relationships(
    exclude_epistemic_status=["HISTORICAL"],
    limit=50
)
```

**Dialectical query — find tension and contradiction:**

```python
contested = facade.match_concept_relationships(
    include_epistemic_status=["MIXED_GROUNDING", "CONTRADICTED"],
    limit=20
)
```

**Combine with relationship type and confidence filters:**

```python
reliable_causal = facade.match_concept_relationships(
    rel_types=["ENABLES", "CAUSES", "REQUIRES"],
    include_epistemic_status=["WELL_GROUNDED"],
    where="r.confidence > 0.8"
)
```

Queries without epistemic status parameters return all relationships — backward-compatible behavior is unchanged.

---

## Troubleshooting

**Query returns empty with `include_epistemic_status`**

Measurement has not been stored. Run `kg vocab epistemic-status measure` (without `--no-store`), then retry.

Verify storage:

```python
vocab_types = facade.match_vocab_types(
    where="v.epistemic_status IS NOT NULL"
)
for vt in vocab_types:
    props = vt['v']['properties']
    print(f"{props['name']}: {props['epistemic_status']} (avg: {props['epistemic_stats']['avg_grounding']:.3f})")
```

**All types show `INSUFFICIENT_DATA`**

The graph is too small or too new to classify. Options:

- Increase sample size: `kg vocab epistemic-status measure --sample-size 500`
- Ingest more documents and re-measure
- Check that grounding calculation is returning non-zero values

**A status looks wrong**

Run with `--verbose` to see per-type uncertainty metrics. If new data has shifted grounding patterns, re-run measurement at a larger sample size.

---

## Keeping statuses current

Epistemic statuses are not recalculated automatically when the graph changes. Treat stored statuses as "last known measurement." Re-run measurement:

- After large ingestion batches
- Before publishing research results or consensus views
- When investigating anomalies in query results

Check when statuses were last measured via the `v.status_measured_at` property on `VocabType` nodes.

---

## Related

- ADR-610 — Vocabulary-Based Provenance Relationships
- ADR-808 — Probabilistic Truth Convergence (grounding calculation)
- `api/app/lib/query_facade.py` — `GraphQueryFacade.match_concept_relationships()`
- [Grounding and Epistemic Confidence](../explanation/grounding.md)
