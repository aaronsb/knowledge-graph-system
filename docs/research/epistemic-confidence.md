# Epistemic Confidence: Philosophy and Mathematics

This document explains the two-dimensional epistemic model used in the Knowledge Graph System to honestly represent what we know and what remains uncertain.

## Part I: The Philosophy of Epistemic Honesty

### The Problem of the Lone Witness

When a knowledge graph contains a concept supported by only one source, we face a fundamental epistemic limitation: we cannot triangulate truth from a single perspective. This is not a bug in the system—it is an honest reflection of the limits of knowledge.

Consider: if someone tells you "the sky is green," and no other source corroborates or contradicts this claim, what do you actually know? You know that *one person claims* the sky is green. You do not know whether the sky is green. The claim exists in epistemic isolation.

This principle extends directly to how we calculate grounding strength in knowledge graphs. The grounding strength metric, ranging from -1.0 to 1.0, indicates the validity of concepts based on evidence consistency and relationship support. But what happens when there's only one piece of evidence? The metric correctly returns a value near zero—not because the concept is false, but because we genuinely cannot determine its epistemic status.

### Why Single-Source Grounding Should Be Zero

A grounding score of zero for single-source content is the *correct* answer, not a failure of the system.

**Grounding Requires Triangulation**

The probabilistic truth convergence method projects concepts onto semantic dimensions formed by opposing relationship types (SUPPORTS vs CONTRADICTS, VALIDATES vs REFUTES). With only one source, there is no axis—no tension between perspectives to measure against. You cannot triangulate a position from a single point.

**Zero Means "Unknown," Not "Unsupported"**

A grounding of 0% doesn't mean the concept is false or lacks merit. It means the system honestly cannot determine whether the concept is supported or contradicted. This is epistemic humility, not failure.

**Single Sources Are Epistemically Opaque**

A lone assertion is:
- Not corroborated (no independent verification)
- Not contested (no challenges to evaluate)
- Just... asserted

The concept might be true, might be false—we genuinely cannot know from the graph structure alone. This opacity is a feature, not a bug.

### The Danger of False Authority

One might argue: "But ADRs are authoritative! They're the source of truth for our architecture." This argument contains a subtle error.

**Authority Is Not Truth**

Declaring a source "authoritative" is an argument from authority—a classic logical fallacy. The ADR is authoritative *because we wrote it*, creating a circular justification. Real truth emerges from:
- Independent corroboration across sources
- Survival under scrutiny and contradiction
- Integration with diverse domains of knowledge

**The Graph Should Not Privilege Sources**

If we weighted certain sources higher because "we trust them," we would be:
- Undermining the entire purpose of evidence-based grounding
- Creating echo chambers where our own assertions reinforce themselves
- Defeating the system's ability to surface genuine contradictions

A single source, no matter how "authoritative," provides zero diversity. The authenticated diversity metric would correctly show this—you cannot have diverse support from a single perspective.

---

## Part II: The Two-Dimensional Epistemic Model

Rather than hiding uncertainty, we surface it through two orthogonal dimensions:

### Dimension 1: Grounding (Direction)

The grounding strength calculation determines where a concept falls on the support-contradiction spectrum:
- **Positive grounding** (> 0.2): Evidence supports the concept across multiple sources
- **Zero grounding** (-0.2 to 0.2): Unknown or unclear direction—insufficient data to determine
- **Negative grounding** (< -0.2): Evidence contradicts the concept

### Dimension 2: Confidence (Data Richness)

The confidence dimension measures how much neighborhood data exists:
- **Confident**: Rich neighborhood with many connections, diverse sources, multiple relationship types
- **Tentative**: Some signal but limited data, few sources
- **Insufficient**: Sparse neighborhood, possibly single source

### The 3×3 Display Matrix

Together, these dimensions produce honest labels:

| Grounding \ Confidence | Confident | Tentative | Insufficient |
|------------------------|-----------|-----------|--------------|
| **Positive** (≥0.2)    | Well-supported | Some support (limited data) | Possibly supported (needs exploration) |
| **Neutral** (-0.2 to 0.2) | Balanced perspectives | Unclear | Unexplored |
| **Negative** (≤-0.2)   | Contested | Possibly contested | Unknown (needs exploration) |

---

## Part III: The Mathematics of Confidence

The confidence score uses a **Michaelis-Menten saturation function**, not a linear scale or sigmoid. This mathematical choice codifies the "Diminishing Returns of Evidence" principle.

### The Saturation Function

```
confidence_score = composite / (composite + k)
```

Where:
- `composite` = weighted sum of evidence signals
- `k` = 2.0 (half-saturation constant)

### Why Hyperbolic, Not Sigmoid?

**Sigmoid (S-curve)**: Starts slow, accelerates, then flattens. This would imply that the first piece of evidence is weak, and you need a "critical mass" before confidence jumps. That would be *wrong* for knowledge—the first witness is the most important one (going from "unknown" to "known").

**Hyperbolic (Our Implementation)**: Starts steep and flattens immediately. The derivative is highest at x=0. This correctly models that:
- The first source provides the biggest leap in information (from 0 to 1)
- The second provides corroboration
- The 50th provides almost zero marginal utility

### The Composite Score Calculation

```python
composite = (
    relationship_count / 10.0 +    # 10 relationships → 1.0 contribution
    source_count / 5.0 +           # 5 sources → 1.0 contribution
    evidence_count / 10.0 +        # 10 evidence instances → 1.0 contribution
    relationship_type_diversity    # Already 0-1
)
```

### The Half-Saturation Constant (k = 2.0)

The constant k = 2.0 means a composite score of 2.0 reaches 50% confidence. To hit that "half-trusted" mark:

- **Relationships alone**: Need 20 relationships (20/10 = 2.0)
- **Sources alone**: Need 10 sources (10/5 = 2.0)
- **Diversity alone**: Perfect diversity (1.0) gets you halfway to half-saturation

**The Insight**: Semantic diversity is the most efficient way to gain confidence. A concept with low diversity must brute-force its way to confidence with massive counts (20+ edges), whereas a diverse concept climbs the curve much faster.

This perfectly enforces the philosophy that echo chambers (low diversity) should not gain unearned confidence through repetition.

### Saturation Prevents "Truth Inflation"

In linear systems, if Document A has 5 links and Document B has 5,000 links, Document B looks 1,000x more important.

In our nonlinear system, because of the asymptote at 1.0:
- Concept A (Composite ~1.5) → Confidence ≈ 42%
- Concept B (Composite ~150) → Confidence ≈ 98%

We successfully cap the influence of massive "hub" nodes. A concept mentioned 5,000 times is not "more true" than one mentioned 50 times; it's just more *famous*. Our math reflects that truth saturates.

### Deliberate Curve Selection Across Domains

The system uses different nonlinear functions for different purposes:

| Domain | Function | Behavior | Rationale |
|--------|----------|----------|-----------|
| **Epistemic Confidence** | Saturation (hyperbolic) | Start fast, flatten | Early evidence is high-value |
| **Vocabulary Expansion** | Cubic Bezier | Start slow, accelerate | Resist expansion until pressure builds |

This shows deliberate system design: confidence should be *eager* (acknowledge early signals) but vocabulary creation should be *lazy* (resist expansion until evidence accumulates).

---

## Part IV: Semantic Diversity and Echo Chambers

### What Diversity Measures

Semantic diversity isn't just counting sources—it measures how *different* those sources are. A concept supported by five paragraphs from the same document has low diversity. A concept supported by physics, biology, and philosophy has high diversity.

### Authenticated Diversity

Authenticated diversity combines grounding direction with semantic diversity to distinguish "diverse support" from "diverse contradiction."

**The Problem with Binary Sign**

A naive implementation uses `sign(grounding) × diversity`, but this treats -0.017 the same as -0.9. A concept with grounding of -0.017 (essentially zero/unclear) would show "diverse contradiction" if it has good diversity—a false signal.

**Signed Saturation Solution**

We apply Michaelis-Menten saturation to grounding before multiplying by diversity:

```
saturated_grounding = grounding / (|grounding| + k)
authenticated_diversity = saturated_grounding × diversity
```

With k = 0.3:
- High grounding (±0.9) → ±0.75 weight
- Medium grounding (±0.3) → ±0.50 weight
- Low grounding (±0.1) → ±0.25 weight
- Near-zero (±0.02) → ±0.06 weight (minimal contribution)

**Example: "Cloud Storage Bucket"**
- Grounding: -0.017 (essentially unclear)
- Diversity: 46%
- Old binary sign: `-1 × 0.46 = -0.46` → "diverse contradiction ❌"
- New saturation: `-0.017/(0.017+0.3) × 0.46 = -0.025` → minimal (honest)

The saturation function works symmetrically on both sides of zero, preventing false contradiction signals from floating-point noise while still properly weighting strong positive or negative grounding.

For single-source content:
- Grounding ≈ 0 (can't determine direction)
- Diversity is low (single perspective)
- Authenticated diversity ≈ 0 × low = near zero

The math correctly reflects epistemic uncertainty.

### Echo Chambers and Circular Reasoning

A single source is the ultimate echo chamber—it only agrees with itself. Even if the source emphatically supports a concept, that support is circular. The source agrees with what it said. That's not evidence; that's tautology.

---

## Part V: The Path Forward

### What Single-Source Content Tells Us

When we see single-source content with "Unclear" grounding, the system honestly communicates:

*"This concept exists. One source describes it. We cannot yet determine if it's true, contested, or just an isolated claim. More sources would help us triangulate."*

This is valuable information:
1. **The concept has been articulated** — Someone thought it worth expressing
2. **Further research could strengthen or challenge it** — A candidate for investigation
3. **We should hold the claim lightly** — Until corroborated, treat as hypothesis

### The Convergence Process

1. **Initial state**: Concept appears with one source. Grounding = 0, Confidence = low.
2. **Corroboration arrives**: Second source supports it. Grounding shifts positive, confidence increases.
3. **Or contradiction arrives**: Second source challenges it. Grounding shifts negative, we discover contestation.
4. **Multiple sources accumulate**: The concept's true epistemic status emerges from the balance of evidence.

### The Alternative: Manufactured Certainty

What would it look like to "fix" single-source grounding?

- **Boost by source type**: "ADRs get +0.5 grounding bonus" — But this is argument from authority
- **Assume support if not contradicted**: "No contradiction = positive" — But absence of evidence isn't evidence
- **Use source count as proxy**: "Any source = some support" — But one person can be wrong

All these "fixes" manufacture certainty where none exists. They make the system lie about what it knows.

---

## Conclusion: Embracing Epistemic Limits

The goal is not to make every concept look well-grounded. The goal is to accurately represent the epistemic state of our knowledge—including its limits.

When the system reports "Unclear [45% conf]" for a single-source concept, it's being maximally honest:
- "I have some neighborhood data (45% confidence)"
- "But I can't determine if this concept is supported or contradicted (Unclear)"
- "More sources would help me give you a better answer"

The knowledge graph is not an oracle. It's a map of what we've learned from multiple sources, with honest uncertainty markers for territories we've only glimpsed from one vantage point. Those "Unclear" markers are not failures—they're the most honest thing the system can say.

---

## References

- **ADR-044**: Authenticated Diversity (sign × diversity)
- **ADR-063**: Semantic Diversity Metrics
- **ADR-070**: Polarity Axis Analysis
- **Implementation**: `api/api/services/confidence_analyzer.py`
