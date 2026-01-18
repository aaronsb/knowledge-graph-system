# Exploring Knowledge

How to find and navigate concepts in your knowledge graph.

## Overview

After ingesting documents, you have a graph of interconnected concepts. Exploring means:
- **Searching** - Finding concepts by meaning
- **Navigating** - Following relationships between concepts
- **Connecting** - Discovering paths between ideas
- **Verifying** - Tracing concepts back to sources

## Semantic Search

Search finds concepts by meaning, not just keywords.

### CLI

```bash
kg search "climate change effects"
```

Returns concepts semantically similar to your query, even if they use different words.

**With options:**
```bash
# Limit results
kg search --limit 20 "economic policy"

# Filter by ontology
kg search --ontology "research" "neural networks"

# Show more detail
kg search --verbose "machine learning"
```

### Web Interface

1. Use the **search bar** at the top
2. Results show concepts ranked by similarity
3. Click any concept to see details

### Understanding Results

Each result shows:
- **Concept name** - The extracted idea
- **Similarity score** - How close to your query (0-1)
- **Grounding** - How well-supported (-1 to +1)
- **Source count** - How many documents mention it

## Viewing Concept Details

### CLI

```bash
kg concept details <concept-id>
```

Shows:
- Full concept information
- All evidence (source text that led to this concept)
- Relationships to other concepts
- Grounding breakdown

### Web Interface

Click any concept to open its detail view:
- **Evidence panel** - Original text excerpts
- **Relationships panel** - Connected concepts
- **Sources panel** - Documents where it appears

## Navigating Relationships

Concepts connect to other concepts. Explore these connections:

### Find Related Concepts

```bash
kg concept related <concept-id>
```

Returns concepts directly connected, grouped by relationship type:
- Supports
- Contradicts
- Implies
- Causes
- Part of

### Filter by Relationship Type

```bash
kg concept related <concept-id> --type SUPPORTS
kg concept related <concept-id> --type CONTRADICTS
```

### Explore Deeper

```bash
# Go 2 hops out
kg concept related <concept-id> --depth 2

# Go 3 hops
kg concept related <concept-id> --depth 3
```

More hops = more concepts, but further from the original.

## Finding Connections

Discover how two concepts relate:

### CLI

```bash
kg concept connect --from "concept A" --to "concept B"
```

Finds paths between concepts, showing how ideas chain together.

**Options:**
```bash
# Limit path length
kg concept connect --from "X" --to "Y" --max-hops 3

# Use concept IDs for precision
kg concept connect --from-id abc123 --to-id def456
```

### What Paths Show

A path might look like:
```
Climate Change
  ──[CAUSES]──> Sea Level Rise
  ──[AFFECTS]──> Coastal Cities
  ──[IMPLIES]──> Migration Patterns
```

This reveals the chain of reasoning connecting distant ideas.

## Exploring Contradictions

Find where sources disagree:

### Search for Contested Concepts

```bash
kg search "vaccination effects" --show-contested
```

Look for concepts with mixed grounding (scores near 0).

### View Both Sides

When you find a contested concept:
```bash
kg concept details <concept-id>
```

The evidence section shows which sources support and which contradict.

### Filter by Epistemic Status

```bash
kg vocabulary list --status CONTESTED
```

Shows relationship types that have mixed evidence across the graph.

## Exploring by Source

Start from a document and see what was extracted:

### List Sources in an Ontology

```bash
kg ontology files <ontology-name>
```

### View Document's Concepts

In the web interface:
1. Navigate to **Documents**
2. Select a document
3. See all concepts extracted from it

## Visual Exploration (Web)

The web interface provides visual navigation:

### Graph View
- Concepts as nodes
- Relationships as edges
- Click to focus
- Drag to rearrange
- Zoom to explore

### Filters
- By ontology
- By grounding threshold
- By relationship type
- By date range

### Highlighting
- Hover to see connections
- Click to lock focus
- Double-click to expand neighborhood

## Exploration Strategies

### Start Broad, Narrow Down
1. Search for a general topic
2. Find a relevant concept
3. Explore its relationships
4. Follow promising connections

### Follow Contradictions
1. Look for low-grounding concepts
2. Check which sources disagree
3. Understand both perspectives
4. Form your own view

### Map a Topic
1. Search for the central concept
2. Get all related concepts (depth 2-3)
3. Look for clusters and bridges
4. Identify key relationships

### Verify Claims
1. Find the concept
2. Check its grounding score
3. Read the source evidence
4. Trace to original documents

## Tips

### Use Specific Queries
"Effects of sleep deprivation on memory" finds more relevant concepts than "sleep".

### Check Grounding Before Trusting
High grounding (> 0.7) means many sources agree. Low or negative means contested or contradicted.

### Explore Neighborhoods
The most interesting insights often come from concepts 2-3 hops away from your starting point.

### Compare Ontologies
If you have separate knowledge bases, search both to see how different document sets treat the same topics.

## Next Steps

- [Understanding Grounding](understanding-grounding.md) - Interpret confidence scores
- [Querying](querying.md) - Programmatic access via CLI, API, and MCP
