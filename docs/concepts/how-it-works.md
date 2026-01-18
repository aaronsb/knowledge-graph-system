# How It Works

A conceptual overview. No code, no implementation details - just the model.

## The Flow

```
Documents → Extraction → Connection → Grounding
```

### 1. Documents Go In

You provide documents: PDFs, text files, markdown, web pages. The system stores the original text so you can always go back to the source.

Documents are split into manageable chunks - roughly page-sized pieces that can be processed individually while preserving context.

### 2. Ideas Come Out

Each chunk is analyzed to extract the key ideas. Not keywords - *concepts*.

A concept is a meaningful unit of thought: "inflation reduces purchasing power" or "sleep deprivation impairs memory" or "the French Revolution began in 1789."

The extraction finds:
- What the concept is (the idea itself)
- What type it is (claim, definition, event, entity, etc.)
- How it relates to other concepts in the same chunk

### 3. Connections Form

Concepts don't exist in isolation. The system discovers relationships:

| Relationship | Meaning |
|--------------|---------|
| **Supports** | This concept provides evidence for that one |
| **Contradicts** | These concepts are in tension |
| **Implies** | If this is true, that follows |
| **Causes** | This leads to that |
| **Part of** | This belongs to a larger whole |

When a new concept matches one that already exists, they're merged. The connection grows stronger. When they conflict, both views are preserved with their sources.

### 4. Grounding Accumulates

As more documents come in, concepts gain *grounding* - a measure of how well-supported they are.

- A concept mentioned in one source has low grounding
- The same concept confirmed across many sources has high grounding
- A concept that some sources support and others contradict has mixed grounding

Grounding isn't just a count. It considers:
- How many sources mention the concept
- Whether sources agree or disagree
- The strength of the supporting evidence

## What Gets Remembered

The system maintains five types of information:

### Concepts
The ideas themselves. Each concept has:
- A name or description
- A type (claim, entity, event, etc.)
- Grounding score (how well-supported)

### Relationships
How concepts connect. Each relationship has:
- Source concept and target concept
- Type (supports, contradicts, implies, etc.)
- Evidence for why this connection exists

### Sources
The original text chunks. Each source has:
- The actual text
- Which document it came from
- Where in the document (for highlighting)

### Evidence
The link between concepts and sources. Shows exactly which text led to which concept.

### Ontologies
Collections of related knowledge. You might have one ontology for "climate research" and another for "company policies." They can be queried separately or together.

## How Queries Work

When you search, you're not matching keywords. You're finding concepts similar in *meaning* to what you're looking for.

Ask about "economic downturn" and you'll find concepts about recessions, market crashes, and financial crises - even if none of them use the exact phrase "economic downturn."

Results include:
- The matching concepts
- Their grounding scores (how reliable)
- The sources they came from (where to verify)
- Related concepts (what else connects)

## How Contradiction Works

Traditional databases assume consistency - if two things conflict, one is wrong. This system assumes **reality is messy**.

When sources disagree, the system:
1. Keeps both viewpoints
2. Records which sources support which view
3. Notes that a contradiction exists
4. Lets you (or an AI) reason about the disagreement

This is crucial for:
- Research where experts disagree
- Historical documents with conflicting accounts
- Evolving knowledge where old information conflicts with new

## The Epistemic Layer

*Epistemic* means "relating to knowledge." This system has an epistemic layer that most databases lack.

It doesn't just store *what* is claimed. It tracks:
- **Confidence**: How well-supported is this claim?
- **Controversy**: Do sources agree or disagree?
- **Provenance**: Where did this claim originate?
- **Freshness**: When was this last confirmed?

This matters because knowledge isn't certain. An AI using this system can say "this is well-established" vs "this is contested" vs "this comes from a single source and should be verified."

## What This Enables

For humans: Search that understands meaning. Sources that trace back. Contradictions made visible.

For AI agents: Memory that persists. Confidence that's grounded. Uncertainty that's explicit.

For both: Knowledge that accumulates over time without losing track of where it came from.

---

Next: [Glossary](glossary.md) - Terms explained in plain language
