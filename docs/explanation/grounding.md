# Grounding and Epistemic Confidence

Grounding measures how well-supported a concept is across your corpus — not whether the concept is universally true. A concept with high grounding means your sources agree on it. A concept with low or negative grounding means your sources disagree, or too few have weighed in. The quality of grounding depends entirely on the quality and diversity of the sources you ingest.

---

## The grounding score

Each concept carries a grounding score on a **−1.0 to +1.0** scale:

| Score range | Label | What it means |
|---|---|---|
| 0.8 to 1.0 | Strongly supported | Multiple sources agree strongly |
| 0.5 to 0.8 | Well supported | Good evidence, sources confirm |
| 0.2 to 0.5 | Moderately supported | Some evidence, room for uncertainty |
| −0.2 to 0.2 | Mixed or insufficient | Sources disagree, or too few sources |
| −0.5 to −0.2 | Contested | More contradiction than support |
| −1.0 to −0.5 | Contradicted | Strong evidence against |

The score reflects the balance of confirming versus contradicting evidence across sources, weighted by relationship strength. It does not reflect the volume of ingested text alone — a concept mentioned 500 times in the same document does not accumulate grounding the way a concept mentioned 50 times across 10 independent sources does.

### How the score is calculated

Each concept-to-source relationship contributes evidence in one direction. The system tracks:

- **Agreement**: sources that confirm the concept (shifts score positive)
- **Contradiction**: sources that challenge it (shifts score negative)
- **Relationship strength**: direct claims carry more weight than passing mentions

When sources disagree, both sides are recorded. Grounding reflects the balance:

```
Source A: "X causes Y"        → +evidence
Source B: "X does not cause Y" → −evidence
```

A concept supported more than contradicted carries positive grounding. A concept contradicted more than supported carries negative grounding. Equal tension lands near zero.

---

## The confidence dimension

Grounding tells you the direction of evidence. Confidence tells you how much evidence exists to make that direction meaningful.

A concept with grounding 0.8 from a single passing mention is not the same as one with grounding 0.8 from 15 independent sources. The confidence dimension captures this distinction.

Confidence is computed from three signals gathered from the concept's graph neighborhood:

```python
composite = (
    relationship_count / 10.0 +    # 10 relationships → 1.0 contribution
    source_count / 5.0 +           # 5 sources → 1.0 contribution
    evidence_count / 10.0 +        # 10 evidence instances → 1.0 contribution
    relationship_type_diversity    # 0–1 (unique edge types / total edges)
)
confidence_score = composite / (composite + 2.0)
```

The saturation function (`composite / (composite + k)`) reflects diminishing returns: the first source contributes more information than the fiftieth. A concept with two sources and a concept with two hundred are not proportionally different in reliability — the function flattens toward 1.0 as evidence accumulates.

This prevents "truth inflation" where a concept's importance in one corpus makes it appear epistemically stronger than a lesser-cited concept that has better cross-domain corroboration.

Three confidence levels map from these scores:

| Level | Thresholds |
|---|---|
| **Confident** | ≥5 relationships, ≥3 sources, ≥3 evidence instances |
| **Tentative** | ≥2 relationships, or ≥1 source, or ≥1 evidence instance |
| **Insufficient** | Below tentative thresholds |

### Semantic diversity and echo chambers

Relationship type diversity matters. A concept supported by five paragraphs from the same document, all connected by identical edge types, has lower diversity than a concept supported by sources from different domains, connected by varied relationship types (SUPPORTS, VALIDATES, IMPLIES, CONFIRMS).

Authenticated diversity combines grounding direction with semantic diversity to distinguish "diverse support" from "diverse contradiction." To avoid false signals from near-zero grounding values, the system applies a saturation step before multiplying:

```
saturated_grounding = grounding / (|grounding| + 0.3)
authenticated_diversity = saturated_grounding × diversity
```

A concept with grounding −0.017 (essentially unclear) and 46% diversity would naively appear as "diverse contradiction." The saturation step reduces the contribution to near zero, which is the honest answer: direction is unclear, so diversity cannot amplify a signal that doesn't exist.

---

## The 3×3 display matrix

Grounding and confidence combine into a single display label that surfaces in the CLI, the web UI, and the MCP tool responses:

| Grounding \ Confidence | Confident | Tentative | Insufficient |
|---|---|---|---|
| **Positive** (≥0.2) | Well-supported | Some support (limited data) | Possibly supported (needs exploration) |
| **Neutral** (−0.2 to 0.2) | Balanced perspectives | Unclear | Unexplored |
| **Negative** (≤−0.2) | Contested | Possibly contested | Unknown (needs exploration) |

"Unexplored" does not mean the concept is wrong. It means the system cannot determine direction from the current corpus — a concept with one source is epistemically opaque. More sources may shift it in either direction.

---

## Epistemic status labels

Beyond numeric grounding, concepts and vocabulary relationships carry a categorical epistemic status used for filtering queries:

| Status | Grounding range | Meaning |
|---|---|---|
| WELL_GROUNDED | > 0.8 | Multiple sources in strong agreement |
| MIXED_GROUNDING | 0.15–0.8 | Variable evidence, contested |
| WEAK_GROUNDING | 0.0–0.15 | Weak positive evidence, emerging |
| POORLY_GROUNDED | −0.5–0.0 | Weak negative evidence, uncertain |
| CONTRADICTED | < −0.5 | Strong evidence against |
| HISTORICAL | — | Temporal vocabulary (WAS, FORMER) |
| INSUFFICIENT_DATA | — | Fewer than 3 measurements |

```bash
# List vocabulary types by epistemic status
kg vocab epistemic-status list --status MIXED_GROUNDING

# Show detail for a specific type
kg vocab epistemic-status show SUPPORTS
```

See [Filter by Epistemic Status](../how-to/epistemic-status.md) for query patterns.

---

## Single-source content

When a concept appears in only one source, grounding returns near zero — and this is the correct answer.

Triangulating a position requires at least two vantage points. With one source, there is no axis: no corroboration, no contradiction, just an assertion. The concept might be true, might be false — the graph cannot determine which. "Unclear [low confidence]" is the most honest thing the system can say.

What single-source content does communicate:

1. The concept has been articulated and extracted into the graph.
2. It is a candidate for further research — more sources may corroborate or challenge it.
3. Until corroborated, treat the concept as a hypothesis rather than a finding.

"Boosting" single-source concepts by source type (treating an ADR as "authoritative" and awarding it extra grounding) would manufacture certainty where none exists. The graph treats all sources uniformly so that genuine corroboration — not declaration of authority — determines grounding.

---

## Contradictions as information

Contradictions are not errors. A concept with negative grounding, or with both supporting and contradicting edges, reveals:

- Areas where your sources disagree (domain disputes, evolving knowledge)
- Context dependence (the same claim may be true in one condition, false in another)
- Temporal shifts (older sources contradict newer ones)

```bash
# Search for a contested topic — note grounding sign in results
kg search "contested claim"

# Inspect both sides
kg concept show <concept-id>
```

The evidence section on a concept shows which sources land on each side:

```
Evidence:
  [+] "Research by Smith confirms X..."
  [+] "Jones et al. demonstrated X under conditions Y..."
  [-] "Brown's study found X does not hold when Z..."
  [-] "Recent work contradicts earlier findings..."
```

When evaluating contradictions: source count is not the only factor. Recency, study rigor, and whether different conditions explain the disagreement all matter. The graph surfaces the balance; the reader interprets the context.

---

## Improving grounding

Grounding improves as you ingest more evidence:

```bash
# Add additional sources to an ontology
kg ingest additional-sources/*.pdf --ontology research

# Inspect what an ontology currently contains
kg ontology info research
```

If you maintain separate ontologies for different domains (medical, legal, news), grounding operates per-ontology. A concept may be well-grounded in one corpus and contradicted in another — which is the correct answer if your sources disagree across domains.

---

## References

- ADR-044: Probabilistic Truth Convergence (grounding direction)
- ADR-063: Semantic Diversity as Authenticity Signal
- Implementation: `api/app/services/confidence_analyzer.py`
