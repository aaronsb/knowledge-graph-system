# Understanding Grounding

How to interpret confidence, contradiction, and epistemic status.

## What Is Grounding?

Grounding measures how well-supported a concept is across your sources. It answers: "How much should I trust this idea?"

Unlike a simple count ("mentioned 5 times"), grounding considers:
- **Agreement**: Do sources confirm each other?
- **Contradiction**: Do sources disagree?
- **Evidence strength**: How directly does source text support the concept?

## The Grounding Scale

Grounding scores range from **-1.0 to +1.0**:

| Score Range | Meaning | Interpretation |
|-------------|---------|----------------|
| **0.8 to 1.0** | Strongly supported | Multiple sources agree strongly |
| **0.5 to 0.8** | Well supported | Good evidence, some sources confirm |
| **0.2 to 0.5** | Moderately supported | Some evidence, room for uncertainty |
| **-0.2 to 0.2** | Mixed or insufficient | Sources disagree, or too few sources |
| **-0.5 to -0.2** | Contested | More contradiction than support |
| **-1.0 to -0.5** | Contradicted | Strong evidence against |

## Reading Grounding in Practice

### High Grounding (> 0.7)

```
Concept: "Sleep deprivation impairs memory consolidation"
Grounding: 0.85
Sources: 12
```

**What this means:**
- 12 sources mention this concept
- They largely agree
- You can cite this with confidence

**Still verify:** Check the actual sources if making important decisions.

### Moderate Grounding (0.3 - 0.7)

```
Concept: "Coffee consumption prevents heart disease"
Grounding: 0.45
Sources: 8
```

**What this means:**
- Some sources support this
- Evidence is mixed or qualified
- Treat as "possibly true" rather than "established"

**Action:** Look at the evidence to understand nuances.

### Low or Negative Grounding (< 0.3)

```
Concept: "Vitamin C cures the common cold"
Grounding: -0.15
Sources: 6
```

**What this means:**
- Sources disagree significantly
- Some support, some contradict
- This is a contested claim

**Action:** Examine both sides before drawing conclusions.

## How Grounding Is Calculated

### Evidence Accumulation

Each time a concept appears in a source, evidence accumulates:

```
Document 1: "Studies confirm X..." → +evidence
Document 2: "X is well-established..." → +evidence
Document 3: "X has been demonstrated..." → +evidence
```

More confirming sources = higher grounding.

### Contradiction Detection

When sources disagree:

```
Document 1: "X causes Y"
Document 2: "X does not cause Y"
```

Both are recorded. Grounding reflects the balance:
- More support than contradiction → positive grounding
- More contradiction than support → negative grounding
- Equal → near-zero grounding

### Relationship Strength

Not all mentions are equal. The system considers:
- Direct claims vs passing mentions
- Central thesis vs tangential reference
- Explicit statements vs implied connections

## Epistemic Status

Beyond grounding scores, concepts and relationships have epistemic status:

| Status | Meaning |
|--------|---------|
| **Affirmative** | High grounding, well-established |
| **Contested** | Significant disagreement between sources |
| **Contradictory** | Strong evidence against |
| **Historical** | Was accurate in its time period |
| **Insufficient Data** | Too few sources to judge |

### Checking Epistemic Status

```bash
# See status for relationship types
kg vocabulary list --status CONTESTED

# Filter concepts by status
kg search "topic" --status AFFIRMATIVE
```

## Working with Contradictions

Contradictions are features, not bugs. They reveal:
- Where experts disagree
- Evolving knowledge over time
- Different perspectives or contexts

### Finding Contradictions

Look for concepts with:
- Grounding near 0
- Multiple sources with opposing views
- Relationships marked CONTRADICTS

```bash
# Search and note low-grounding results
kg search "controversial topic"

# Get details to see both sides
kg concept details <concept-id>
```

### Understanding Both Sides

The evidence section shows which sources support and which contradict:

```
Evidence:
  [+] "Research by Smith shows X is true..."
  [+] "Jones et al. confirmed that X..."
  [-] "However, Brown's study found X is false..."
  [-] "Recent work contradicts earlier findings on X..."
```

### Making Decisions with Contradictions

1. **Count isn't everything** - One rigorous study may outweigh many weak ones
2. **Check recency** - Newer research may supersede older
3. **Consider context** - Different conditions may explain disagreement
4. **Acknowledge uncertainty** - Some questions don't have clear answers

## Grounding vs. Truth

**Grounding measures evidence in your knowledge base, not absolute truth.**

A concept with high grounding means:
- ✅ Your sources agree on this
- ❌ Does NOT mean it's universally true

A concept with low grounding means:
- ✅ Your sources disagree or lack evidence
- ❌ Does NOT mean it's false

**The quality of grounding depends on the quality of your sources.**

## Practical Guidelines

### For Research

- Use high-grounding concepts as established foundations
- Investigate low-grounding concepts as areas of uncertainty
- Document which sources you're relying on

### For Decision-Making

- Prefer high-grounding concepts for critical decisions
- For contested topics, understand both sides before deciding
- Be explicit about uncertainty when grounding is low

### For AI Assistants

When using MCP, the AI should:
- Check grounding before making claims
- Caveat low-grounding information appropriately
- Cite sources for important statements
- Acknowledge contradictions when they exist

## Improving Grounding

### Add More Sources

Grounding improves with more evidence:
```bash
kg ingest additional-sources/*.pdf --ontology research
```

### Update with Recent Research

Newer sources may resolve old contradictions:
```bash
kg ingest latest-study.pdf --ontology research
```

### Separate Domains

Different ontologies can have different evidence bases:
```bash
# Medical research has high grounding for X
kg search --ontology medical "treatment X"

# General news has low grounding for X
kg search --ontology news "treatment X"
```

## Summary

| Question | Look At |
|----------|---------|
| "Can I trust this?" | Grounding score |
| "Where did this come from?" | Evidence section |
| "Do sources agree?" | Grounding sign (+/-) and evidence |
| "How established is this?" | Epistemic status |
| "What's the other side?" | CONTRADICTS relationships |

Grounding gives you the tools to reason about knowledge quality, not just knowledge content. Use it to make informed decisions about what to trust and where to dig deeper.

## Next Steps

- [Exploring Knowledge](exploring.md) - Navigate the graph
- [Concepts: How It Works](../concepts/how-it-works.md) - Deeper understanding
- [Concepts: Glossary](../concepts/glossary.md) - Term definitions
