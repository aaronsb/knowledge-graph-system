# Polarity Axis Analysis - User Guide

**Feature:** ADR-070 Polarity Axis Analysis for Bidirectional Semantic Dimensions
**Status:** Implemented (2025-11-30)
**API:** POST /query/polarity-axis
**CLI:** `kg polarity analyze`
**MCP:** `analyze_polarity_axis`

---

## Overview

Polarity axis analysis enables you to explore **conceptual spectrums** in your knowledge graph - implicit semantic dimensions along which concepts naturally organize themselves. Unlike relationship traversal which follows explicit edges, polarity analysis reveals the emergent structure of your knowledge through vector mathematics.

**Think of it as asking:** "Where does this concept fall on the spectrum between X and Y?"

### What It Does

Given two opposing concepts (poles), polarity axis analysis:
1. **Projects concepts onto the axis** - Positions each concept on a -1 to +1 scale
2. **Measures alignment** - Determines which pole each concept aligns with
3. **Calculates orthogonality** - Shows which concepts don't fit this dimension
4. **Validates with grounding** - Checks if position correlates with reliability

### Real-World Example

```
Question: "Where does 'Agile' fall between Modern and Traditional approaches?"

Modern Ways of Working ●────────────────────────● Traditional Operating Models
                       │         ↑               │
                  +1.0 │    Agile (+0.72)        │ -1.0
                       │                         │
                       ├─ DevOps (+0.58)         │
                       ├─ Waterfall (-0.45) ─────┤
                       │                         │
                       └─────────────────────────┘
```

The axis reveals semantic positioning that might not be captured by explicit relationship edges.

---

## Quick Start

### Using the CLI

```bash
# Basic analysis with auto-discovery
kg polarity analyze \
  --positive sha256:0d5be_chunk1_a2ccadba \
  --negative sha256:0f72d_chunk1_9a13bb20

# Limit candidates
kg polarity analyze \
  --positive <modern-id> \
  --negative <traditional-id> \
  --max-candidates 30

# Output JSON for scripting
kg polarity analyze \
  --positive <pole1-id> \
  --negative <pole2-id> \
  --json > analysis.json
```

### Using the MCP Tool

```python
analyze_polarity_axis(
  positive_pole_id="sha256:0d5be_chunk1_a2ccadba",
  negative_pole_id="sha256:0f72d_chunk1_9a13bb20",
  auto_discover=true,
  max_candidates=20
)
```

### Using the API

```bash
curl -X POST http://localhost:8000/query/polarity-axis \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "positive_pole_id": "sha256:0d5be_chunk1_a2ccadba",
    "negative_pole_id": "sha256:0f72d_chunk1_9a13bb20",
    "auto_discover": true,
    "max_candidates": 20,
    "max_hops": 2
  }'
```

---

## Understanding the Output

### Axis Metadata

```
Polarity Axis: Modern Ways of Working ↔ Traditional Operating Models

Positive Pole: Modern Ways of Working
  Grounding: Weak (0.104, 10%)
  ID: sha256:0d5be_chunk1_a2ccadba

Negative Pole: Traditional Operating Models
  Grounding: Negative (-0.040, -4%)
  ID: sha256:0f72d_chunk1_9a13bb20

Axis Magnitude: 0.9735
Axis Quality: ✓ Strong (poles are semantically distinct)
```

**What this tells you:**
- **Axis Magnitude:** How semantically distinct the poles are (0.9735 is strong)
- **Axis Quality:** Strong = good axis, Weak = poles may be too similar
- **Pole Grounding:** Reliability of each pole concept

### Statistics

```
Total Concepts: 20
Position Range: [-0.734, 0.266]
Mean Position: -0.079 (balanced)
Mean Axis Distance: 0.923 (orthogonal spread)

Direction Distribution:
- Positive (>0.3): 0 concepts
- Neutral (-0.3 to 0.3): 18 concepts
- Negative (<-0.3): 2 concepts
```

**Interpreting statistics:**
- **Position Range:** How spread out concepts are along the axis
- **Mean Position:** Axis balance (near 0 = balanced, ±1 = skewed)
- **Mean Axis Distance:** How orthogonal concepts are (higher = more multi-dimensional)
- **Direction Distribution:** How concepts cluster

### Grounding Correlation

```
Pearson r: -0.258
p-value: 0.2712
Interpretation: Weak negative correlation

→ Weak correlation: Position and grounding are loosely related
```

**What correlation means:**

| Pearson r | Meaning | Interpretation |
|-----------|---------|----------------|
| **r > 0.7** | Strong positive | Concepts toward positive pole have higher grounding |
| **0.3 < r < 0.7** | Moderate positive | Some correlation with positive pole reliability |
| **-0.3 < r < 0.3** | Weak/None | Position and grounding independent |
| **-0.7 < r < -0.3** | Moderate negative | Concepts toward negative pole have higher grounding |
| **r < -0.7** | Strong negative | Strong reliability bias toward negative pole |

**When to trust correlation:**
- **p-value < 0.05:** Statistically significant
- **p-value > 0.05:** May be random chance (typical with small samples)

### Concept Projections

```
Positive Direction (toward Modern Ways of Working)
1. Work Management
   Position: 0.266 | Grounding: Weak (0.000, 0%) | Axis distance: 0.8299
   ID: sha256:f024f_chunk1_563d25ec

Neutral (balanced between poles)
2. Agile Work Item Management Tool
   Position: 0.159 | Grounding: Negative (-0.017, -2%) | Axis distance: 0.9507
   ID: sha256:0d5be_chunk3_e5c473cb

Negative Direction (toward Traditional Operating Models)
3. Enterprise Operating Model
   Position: -0.734 | Grounding: Weak (0.148, 15%) | Axis distance: 0.6672
   ID: sha256:0d5be_chunk1_d22215ed
```

**Reading projections:**
- **Position:** Where on the spectrum (-1 = negative pole, +1 = positive pole)
- **Grounding:** Reliability of this concept
- **Axis Distance:** How well this dimension explains the concept
- **Direction:** Categorical alignment (positive/neutral/negative)

---

## Interpreting Results

### Position Values

```
         -1.0                    0.0                   +1.0
Negative Pole ●─────────────────●─────────────────● Positive Pole
              │                 │                 │
         Strong            Balanced           Strong
        Alignment         Position          Alignment
```

**Position ranges:**
- **-1.0 to -0.3:** Strong alignment with negative pole
- **-0.3 to +0.3:** Neutral/balanced between poles
- **+0.3 to +1.0:** Strong alignment with positive pole

### Axis Distance (Orthogonality)

**Low distance (< 0.5):** Concept lies close to the axis
- This dimension explains the concept well
- Concept is "on the spectrum"

**High distance (> 0.8):** Concept is orthogonal to the axis
- Other dimensions are more relevant
- Concept introduces third dimension

**Example:**
```
Security Concept on Modern ↔ Traditional axis:
  Position: 0.12 (slightly modern)
  Axis Distance: 1.45 (very high!)

→ Interpretation: Security is orthogonal to modernization
  (it's a separate concern, not on this spectrum)
```

### Grounding Correlation Patterns

**Strong positive correlation (r > 0.7):**
```
Modern ●────────────────────────────● Traditional
  ↑                                      ↓
High Grounding                    Low Grounding

→ This is a VALUE POLARITY
→ Positive pole represents "good" practices
→ Negative pole represents problems/anti-patterns
```

**Strong negative correlation (r < -0.7):**
```
Centralized ●───────────────────────● Decentralized
     ↓                                       ↑
Low Grounding                        High Grounding

→ Reverse value polarity
→ Negative pole has higher reliability
→ May indicate context preference
```

**Weak correlation (|r| < 0.3):**
```
Empirical ●─────────────────────────● Theoretical
    ↑                                      ↑
Both poles have positive grounding

→ NOT a value polarity
→ Both approaches are valid
→ Represents descriptive dimension, not good/bad
```

---

## Practical Use Cases

### 1. Understanding Organizational Transformation

**Goal:** Map where practices fall on the modernization spectrum

```bash
kg search "modern operating model" --limit 1 --json | jq -r '.results[0].concept_id'
# → sha256:abc123...

kg search "traditional hierarchy" --limit 1 --json | jq -r '.results[0].concept_id'
# → sha256:def456...

kg polarity analyze --positive sha256:abc123 --negative sha256:def456
```

**What you discover:**
- Which practices are genuinely modern vs traditional
- Synthesis concepts that balance both (neutral position)
- Whether "modern" correlates with better outcomes (grounding)

### 2. Finding Balanced Solutions

**Goal:** Identify concepts that synthesize two opposing approaches

```bash
kg polarity analyze \
  --positive <centralized-id> \
  --negative <distributed-id> \
  --max-candidates 50
```

**Look for:**
- Concepts with position near 0.0 (balanced)
- Low axis distance (truly on the spectrum)
- Positive grounding (reliable synthesis)

**Example result:**
```
Federated Architecture
  Position: 0.08 (nearly neutral)
  Grounding: +0.62 (reliable)
  Axis Distance: 0.34 (on spectrum)

→ This is a SYNTHESIS concept
→ Balances centralized control with distributed execution
```

### 3. Validating Relationship Types

**Goal:** Check if PREVENTS relationships create meaningful axes

```bash
# Find opposing concepts connected by PREVENTS
kg search "legacy systems" --limit 1  # Get ID
kg search "digital transformation" --limit 1  # Get ID

kg polarity analyze --positive <digital-id> --negative <legacy-id>
```

**Strong axis indicators:**
- High magnitude (> 0.8)
- Strong grounding correlation (|r| > 0.7)
- Low p-value (< 0.05)

**Weak axis indicators:**
- Low magnitude (< 0.5) → Concepts aren't really opposites
- No correlation (|r| < 0.1) → PREVENTS might be incorrectly applied

### 4. Exploring Knowledge Dimensions

**Goal:** Discover implicit dimensions in your knowledge base

**Strategy:** Try different pole pairs and observe patterns

```bash
# Try obvious opposites
kg polarity analyze --positive <simple-id> --negative <complex-id>
kg polarity analyze --positive <fast-id> --negative <slow-id>

# Try conceptual opposites
kg polarity analyze --positive <local-id> --negative <global-id>
kg polarity analyze --positive <top-down-id> --negative <bottom-up-id>
```

**What to look for:**
- Axes with high magnitude (strong semantic distinction)
- Axes where grounding correlation reveals value preferences
- Concepts that appear on multiple axes (central ideas)

### 5. Pedagogical Ordering

**Goal:** Order concepts along a learning progression

```bash
kg polarity analyze \
  --positive <advanced-concept-id> \
  --negative <beginner-concept-id> \
  --max-candidates 100
```

**Use position to create learning path:**
```
-1.0 (Beginner)          0.0 (Intermediate)       +1.0 (Advanced)
     ├─ Basic Concept (-0.89)
     ├─ Foundational Pattern (-0.62)
     ├─ Intermediate Technique (+0.12)
     ├─ Advanced Strategy (+0.71)
     └─ Expert Approach (+0.94)
```

---

## Choosing Good Pole Pairs

### What Makes a Good Axis?

**Strong semantic opposition:**
```
✅ Good: Modern ↔ Traditional
✅ Good: Centralized ↔ Distributed
✅ Good: Empirical ↔ Theoretical
❌ Bad: Blue ↔ Red (no semantic opposition)
❌ Bad: Apple ↔ Orange (different, not opposite)
```

**Clear conceptual dimension:**
```
✅ Good: Simple ↔ Complex
✅ Good: Fast ↔ Slow
✅ Good: Local ↔ Global
❌ Bad: Car ↔ Airplane (multi-dimensional differences)
```

### Testing Axis Quality

**Check axis magnitude:**
- **> 0.9:** Excellent opposition
- **0.7 - 0.9:** Good opposition
- **0.5 - 0.7:** Moderate opposition
- **< 0.5:** Weak opposition (consider different poles)

**Check grounding correlation:**
- **|r| > 0.7:** Strong value polarity (reveals preferences)
- **0.3 < |r| < 0.7:** Moderate correlation (mixed values)
- **|r| < 0.3:** No value polarity (descriptive dimension)

### Pole Selection Strategies

**1. Use PREVENTS/CONTRADICTS relationships:**
```bash
# Find concepts with PREVENTS relationships
kg search "digital transformation" --limit 1
# Look at details, find what it PREVENTS
kg concept details <concept-id> | grep PREVENTS

# Use those as pole pair
```

**2. Use domain knowledge:**
- Think of natural opposites in your field
- Consider dimensions experts care about
- Look for trade-offs (speed vs accuracy, etc.)

**3. Explore existing axes:**
- Start with obvious opposites
- See what concepts cluster
- Try orthogonal dimensions

---

## Advanced Techniques

### Multi-Axis Analysis

**Strategy:** Analyze the same concepts across multiple axes

```bash
# Axis 1: Modernization
kg polarity analyze --positive <modern-id> --negative <traditional-id> --json > axis1.json

# Axis 2: Centralization
kg polarity analyze --positive <central-id> --negative <distributed-id> --json > axis2.json

# Axis 3: Complexity
kg polarity analyze --positive <complex-id> --negative <simple-id> --json > axis3.json
```

**Cross-reference positions:**
```python
# Find concepts that are:
# - Modern (+0.8 on axis 1)
# - Distributed (+0.7 on axis 2)
# - Complex (+0.6 on axis 3)

import json

axis1 = json.load(open('axis1.json'))
axis2 = json.load(open('axis2.json'))
axis3 = json.load(open('axis3.json'))

# Build position map
concepts = {}
for proj in axis1['projections']:
    cid = proj['concept_id']
    concepts[cid] = {'label': proj['label'], 'modern': proj['position']}

for proj in axis2['projections']:
    cid = proj['concept_id']
    if cid in concepts:
        concepts[cid]['distributed'] = proj['position']

for proj in axis3['projections']:
    cid = proj['concept_id']
    if cid in concepts:
        concepts[cid]['complex'] = proj['position']

# Filter for target profile
for cid, data in concepts.items():
    if (data.get('modern', 0) > 0.8 and
        data.get('distributed', 0) > 0.7 and
        data.get('complex', 0) > 0.6):
        print(f"{data['label']}: modern={data['modern']:.2f}, distributed={data['distributed']:.2f}, complex={data['complex']:.2f}")
```

### Tracking Axis Evolution

**Strategy:** Re-run analysis as your knowledge base grows

```bash
# Initial analysis
kg polarity analyze --positive <p1> --negative <n1> --json > snapshot_2025-01-01.json

# After adding documents (later)
kg polarity analyze --positive <p1> --negative <n1> --json > snapshot_2025-02-01.json

# Compare positions
diff snapshot_2025-01-01.json snapshot_2025-02-01.json
```

**What changes mean:**
- **Position shifts:** Concepts accumulate new evidence
- **New concepts appear:** Knowledge base expansion
- **Correlation changes:** Value preferences evolve

### Identifying Orthogonal Concepts

**Goal:** Find concepts that don't fit current axes

```bash
kg polarity analyze --positive <p1> --negative <n1> --json | \
  jq '.projections[] | select(.axis_distance > 1.0) | {label, axis_distance, position}'
```

**High axis distance concepts:**
- May represent new dimensions
- Could be entry points for different pole pairs
- Might be multi-dimensional (need multiple axes to explain)

---

## Performance & Limitations

### Performance Characteristics

**Execution time:** ~2-3 seconds for 20 concepts
- Fast enough for interactive exploration
- Suitable for on-demand analysis
- No job queue overhead

**Scaling:**
- ~100ms per concept (including grounding calculation)
- 50 concepts ≈ 5 seconds
- 100 concepts ≈ 10 seconds

**Bottlenecks:**
- Grounding strength calculation (most expensive)
- Graph traversal for auto-discovery
- 768-dimensional vector operations

### Current Limitations

**1. No axis persistence**
- Each analysis is computed fresh
- Can't save axes for later reuse
- Future: Could add `:PolarityAxis` nodes (ADR-070 Alternative 3)

**2. No auto-discovery of axes**
- Must specify pole pairs manually
- Future: Could add `/query/discover-polarity-axes` endpoint

**3. Single-axis projection only**
- Projects onto 1D axis
- Future: Could extend to 2D projections (two orthogonal axes)

**4. Limited to concept embeddings**
- Can't analyze concepts without embeddings
- Requires ADR-045 (Unified Embedding Generation)

### Best Practices

**Do:**
- ✅ Start with max_candidates=20 for quick exploration
- ✅ Check axis quality (magnitude) before interpreting results
- ✅ Use grounding correlation to identify value polarities
- ✅ Compare multiple axes to understand multi-dimensional space
- ✅ Use axis distance to identify orthogonal concepts

**Don't:**
- ❌ Over-interpret weak axes (magnitude < 0.5)
- ❌ Assume correlation implies causation
- ❌ Ignore high axis distance (orthogonality matters!)
- ❌ Use poles that aren't semantically opposite
- ❌ Expect perfect linear relationships (knowledge is messy)

---

## Troubleshooting

### "Axis quality: Weak"

**Problem:** Pole concepts aren't semantically distinct

**Solutions:**
1. Choose more opposing concepts
2. Check if poles are actually synonyms
3. Try different pole pair entirely

### "No grounding correlation"

**This is often normal!**

Not all axes are value polarities:
- Empirical ↔ Theoretical (both valid)
- Local ↔ Global (context-dependent)
- Fast ↔ Slow (trade-offs exist)

**Only concerned if:**
- You expected a value polarity
- AND magnitude is high (> 0.8)
- AND sample size is large (> 30 concepts)

### "All concepts clustered near one pole"

**Possible causes:**
1. Your knowledge base has bias toward one pole
2. Poles aren't balanced in representation
3. Pole selection doesn't match domain

**Solution:** Try different pole pairs or accept the bias as signal

### "Very high axis distances"

**This means:** Concepts are multi-dimensional

**It's not a problem!** It reveals:
- Your knowledge can't be reduced to this single axis
- Other dimensions are relevant
- These concepts might be good poles for OTHER axes

---

## Further Reading

- **ADR-070:** Full architectural decision record
- **ADR-058:** Polarity Axis Triangulation for Grounding (related technique)
- **ADR-044:** Probabilistic Truth Convergence (grounding calculation)
- **Research:** [Large Concept Models](https://arxiv.org/abs/2412.08821) - Meta AI, Dec 2024

---

## Quick Reference

### CLI Commands

```bash
# Basic analysis
kg polarity analyze --positive <id1> --negative <id2>

# With options
kg polarity analyze \
  --positive <id1> \
  --negative <id2> \
  --max-candidates 30 \
  --max-hops 2 \
  --json

# Find concept IDs first
kg search "modern" --limit 1 --json | jq -r '.results[0].concept_id'
```

### MCP Tool

```python
analyze_polarity_axis(
  positive_pole_id="<id1>",
  negative_pole_id="<id2>",
  auto_discover=true,
  max_candidates=20,
  max_hops=2
)
```

### API Endpoint

```bash
POST /query/polarity-axis
{
  "positive_pole_id": "<id1>",
  "negative_pole_id": "<id2>",
  "candidate_ids": ["<id3>", "<id4>"],  // optional
  "auto_discover": true,
  "max_candidates": 20,
  "max_hops": 2
}
```

### Output Structure

```json
{
  "success": true,
  "axis": {
    "positive_pole": {"concept_id": "...", "label": "...", "grounding": 0.12},
    "negative_pole": {"concept_id": "...", "label": "...", "grounding": -0.04},
    "magnitude": 0.97,
    "axis_quality": "strong"
  },
  "projections": [
    {
      "concept_id": "...",
      "label": "...",
      "position": 0.25,
      "direction": "positive",
      "grounding": 0.15,
      "axis_distance": 0.83,
      "similarity_to_positive": 0.72,
      "similarity_to_negative": 0.45
    }
  ],
  "statistics": {
    "total_concepts": 20,
    "position_range": [-0.73, 0.27],
    "mean_position": -0.08,
    "mean_axis_distance": 0.92,
    "direction_distribution": {"positive": 0, "neutral": 18, "negative": 2}
  },
  "grounding_correlation": {
    "pearson_r": -0.26,
    "p_value": 0.27,
    "interpretation": "Weak negative correlation"
  }
}
```
