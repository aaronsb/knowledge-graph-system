# kg search

Search for concepts and explore the graph.

## Usage

```bash
kg search [options] [command]
```

## Description

The `search` command provides the primary interface for querying and exploring the knowledge graph. It supports four types of exploration:

1. **query** - Natural language semantic search for concepts
2. **details** - Deep dive into a specific concept with all evidence
3. **related** - Discover nearby concepts through graph traversal
4. **connect** - Find paths between concepts (the "how are these connected?" question)

All search commands use vector embeddings for semantic similarity and the graph structure for relationship discovery.

## Options

| Option | Description |
|--------|-------------|
| `-h, --help` | Display help for command |

## Subcommands

| Command | Description | Doc |
|---------|-------------|-----|
| `query <query>` | Search for concepts using natural language | [↓](#query) |
| `details <concept-id>` | Get detailed information about a concept | [↓](#details) |
| `related <concept-id>` | Find concepts related through graph traversal | [↓](#related) |
| `connect <from> <to>` | Find shortest path between two concepts | [↓](#connect) |

## Command Tree

```
kg search
├── query <query>
├── details <concept-id>
├── related <concept-id>
└── connect <from> <to>
```

---

## Subcommand Details

### query

Search for concepts using natural language.

**Usage:**
```bash
kg search query [options] <query>
```

**Arguments:**
- `<query>` - Natural language search query

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-l, --limit <number>` | Maximum results | `10` |
| `--min-similarity <number>` | Minimum similarity score (0.0-1.0) | `0.7` |
| `--show-evidence` | Show sample evidence quotes from source text | `false` |
| `--no-grounding` | Disable grounding strength calculation (faster) | enabled |
| `--json` | Output raw JSON instead of formatted text | `false` |
| `-h, --help` | Display help for command | - |

**How It Works:**

1. Query text is embedded using the same model as concepts
2. Vector similarity search finds closest semantic matches
3. Results are ranked by similarity score
4. Optional grounding strength shows how well-evidenced each concept is

**Examples:**

```bash
# Basic search
kg search query "machine learning"

# More results
kg search query "neural networks" -l 20

# Lower similarity threshold (broader matches)
kg search query "AI" --min-similarity 0.5

# With evidence quotes
kg search query "transformer architecture" --show-evidence

# Fast search (skip grounding calculation)
kg search query "deep learning" --no-grounding

# JSON output for scripting
kg search query "GPT" --json
```

**Output Example:**

```
Search Results for: "machine learning"

1. Machine Learning Algorithms (0.92) [concept_abc123]
   Grounding: ████████░░ 84% (12 evidence, 3 supporting rels)
   "Algorithms that learn patterns from data..."

2. Neural Network Training (0.87) [concept_def456]
   Grounding: ███████░░░ 76% (8 evidence, 2 supporting rels)
   "Process of optimizing neural network parameters..."

3. Supervised Learning (0.83) [concept_ghi789]
   Grounding: █████████░ 91% (15 evidence, 4 supporting rels)
   "Learning from labeled training data..."
```

**Similarity Scores:**

- `0.9-1.0` - Excellent match, highly relevant
- `0.8-0.9` - Good match, relevant
- `0.7-0.8` - Moderate match, possibly relevant
- `0.5-0.7` - Weak match, tangentially related
- `<0.5` - Poor match, likely irrelevant

**Tips:**

- Use specific phrases: "transformer architecture" better than "transformer"
- Lower threshold for exploratory searches: `--min-similarity 0.5`
- Use `--show-evidence` to verify relevance
- Results include concept IDs for follow-up with `details` or `related`

---

### details

Get comprehensive information about a specific concept.

**Usage:**
```bash
kg search details [options] <concept-id>
```

**Arguments:**
- `<concept-id>` - Concept ID to retrieve

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--no-grounding` | Disable grounding strength calculation (faster) | enabled |
| `--json` | Output raw JSON instead of formatted text | `false` |
| `-h, --help` | Display help for command | - |

**What You Get:**

1. **Core Information**
   - Concept label
   - Search terms/aliases
   - Grounding strength (probabilistic truth, ADR-044)

2. **All Evidence**
   - Complete quotes from source documents
   - Source locations and context
   - Instance IDs for provenance

3. **Relationships**
   - Outgoing edges (IMPLIES, ENABLES, etc.)
   - Relationship types and direction
   - Target concepts

4. **Sources**
   - Documents where concept appears
   - Paragraph locations
   - Ontology classification

**Examples:**

```bash
# Get concept details
kg search details concept_abc123

# Fast version (skip grounding)
kg search details concept_abc123 --no-grounding

# JSON for processing
kg search details concept_abc123 --json | jq '.evidence | length'
```

**Output Example:**

```
Concept: Machine Learning Algorithms
ID: concept_abc123
Grounding Strength: ████████░░ 84% (strong evidence)

Search Terms:
  - machine learning algorithms
  - ML algorithms
  - learning algorithms

Evidence (12 instances):

  [1] "Machine learning algorithms learn patterns from data without
       explicit programming. They improve through experience..."
      Source: ai-overview.md (paragraph 3)
      Instance: instance_xyz789

  [2] "Common ML algorithms include decision trees, random forests,
       and neural networks..."
      Source: algorithms.md (paragraph 1)
      Instance: instance_abc456

  ... (10 more)

Relationships (Outgoing):
  IMPLIES → Neural Networks (concept_def456)
  ENABLES → Pattern Recognition (concept_ghi789)
  REQUIRES → Training Data (concept_jkl012)
  CATEGORIZED_AS → Computational Methods (concept_mno345)

Sources:
  - ai-overview.md (Ontology: AI Fundamentals)
  - algorithms.md (Ontology: Technical Docs)
  - ml-basics.txt (Ontology: Educational Content)
```

**Use Cases:**

- Verify search results before citing
- Explore evidence provenance
- Understand concept relationships
- Navigate to related concepts

---

### related

Find concepts related through graph traversal.

**Usage:**
```bash
kg search related [options] <concept-id>
```

**Arguments:**
- `<concept-id>` - Starting concept ID

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-d, --depth <number>` | Maximum traversal depth (1-5) | `2` |
| `-t, --types <types...>` | Filter by relationship types | all types |
| `--json` | Output raw JSON instead of formatted text | `false` |
| `-h, --help` | Display help for command | - |

**How It Works:**

Performs breadth-first graph traversal from the starting concept:

- **Depth 1**: Direct neighbors (1 hop away)
- **Depth 2**: Neighbors of neighbors (2 hops)
- **Depth 3+**: Extended neighborhood

Results are grouped by distance from the starting point.

**Examples:**

```bash
# Find nearby concepts (2 hops)
kg search related concept_abc123

# Immediate neighbors only
kg search related concept_abc123 -d 1

# Deeper exploration
kg search related concept_abc123 -d 4

# Filter by relationship type
kg search related concept_abc123 -t IMPLIES ENABLES

# Multiple types
kg search related concept_abc123 --types CAUSES PREVENTS SUPPORTS

# JSON output
kg search related concept_abc123 --json
```

**Output Example:**

```
Related Concepts from: Machine Learning Algorithms

Distance 1 (Direct neighbors - 5 concepts):
  [IMPLIES] → Neural Networks (concept_def456)
  [ENABLES] → Pattern Recognition (concept_ghi789)
  [REQUIRES] → Training Data (concept_jkl012)
  [PART_OF] → Artificial Intelligence (concept_mno345)
  [SUPPORTS] → Predictive Modeling (concept_pqr678)

Distance 2 (2 hops away - 12 concepts):
  [via Neural Networks]
    [CONTAINS] → Hidden Layers (concept_stu901)
    [USES] → Backpropagation (concept_vwx234)

  [via Training Data]
    [INCLUDES] → Labeled Examples (concept_yza567)
    [REQUIRES] → Data Preprocessing (concept_bcd890)

  ... (8 more)

Total: 17 related concepts found
```

**Relationship Type Filtering:**

Common useful types:
- `IMPLIES` / `IMPLIED_BY` - Logical relationships
- `CAUSES` / `RESULTS_FROM` - Causal chains
- `ENABLES` / `PREVENTED_BY` - Dependencies
- `PART_OF` / `CONTAINS` - Compositional
- `SIMILAR_TO` / `CONTRASTS_WITH` - Semantic
- `SUPPORTS` / `CONTRADICTS` - Evidential

See `kg vocab list` for all available types.

**Performance:**

- Depth 1-2: Fast (<1s)
- Depth 3: Moderate (~2-5s)
- Depth 4-5: Slow (can explore hundreds of concepts)

**Tips:**

- Start with depth 2 for exploration
- Use type filters to find specific relationship patterns
- Depth 4-5 can reveal surprising indirect connections

---

### connect

Find shortest paths between two concepts.

**Usage:**
```bash
kg search connect [options] <from> <to>
```

**Arguments:**
- `<from>` - Starting concept (exact ID or 2-3 word phrase)
- `<to>` - Target concept (exact ID or 2-3 word phrase)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--max-hops <number>` | Maximum path length | `5` |
| `--min-similarity <number>` | Semantic similarity threshold for phrase matching (0.0-1.0) | `0.5` |
| `--show-evidence` | Show sample evidence quotes for each concept in paths | `false` |
| `--no-grounding` | Disable grounding strength calculation (faster) | enabled |
| `--json` | Output raw JSON instead of formatted text | `false` |
| `-h, --help` | Display help for command | - |

**Two Modes:**

1. **Exact ID Mode**: Use concept IDs directly
   ```bash
   kg search connect concept_abc123 concept_def456
   ```

2. **Phrase Match Mode**: Use natural language descriptions
   ```bash
   kg search connect "machine learning" "neural networks"
   ```

**How Phrase Matching Works:**

1. Embeds both phrases
2. Finds best matching concepts using similarity threshold
3. Searches for paths between matched concepts
4. Returns up to 5 shortest paths

**Examples:**

```bash
# Using exact IDs
kg search connect concept_abc123 concept_def456

# Using phrases
kg search connect "machine learning" "computer vision"

# Lower similarity for broader matches
kg search connect "ML algorithms" "image recognition" --min-similarity 0.3

# Longer paths
kg search connect "quantum computing" "cryptography" --max-hops 7

# With evidence
kg search connect "AGE database" "graph queries" --show-evidence

# JSON output
kg search connect "concept A" "concept B" --json
```

**Output Example:**

```
Finding paths from "machine learning" to "computer vision"...

Matched concepts:
  From: Machine Learning Algorithms (concept_abc123, similarity: 0.89)
  To: Computer Vision Systems (concept_def456, similarity: 0.92)

Found 3 paths:

Path 1 (length: 3):
  Machine Learning Algorithms
    [ENABLES] →
  Pattern Recognition
    [APPLIED_TO] →
  Image Processing
    [PART_OF] →
  Computer Vision Systems

Path 2 (length: 4):
  Machine Learning Algorithms
    [INCLUDES] →
  Neural Networks
    [SPECIALIZED_TO] →
  Convolutional Networks
    [DESIGNED_FOR] →
  Image Recognition
    [COMPONENT_OF] →
  Computer Vision Systems

Path 3 (length: 4):
  Machine Learning Algorithms
    [REQUIRES] →
  Training Data
    [INCLUDES] →
  Image Datasets
    [USED_BY] →
  Vision Models
    [IMPLEMENTS] →
  Computer Vision Systems

Shortest path: 3 hops
```

**Phrase Matching Tips:**

✅ **Good phrases (2-3 words, specific):**
- "transformer architecture"
- "AGE benefits"
- "licensing issues"

❌ **Poor phrases (too generic):**
- "features"
- "issues"
- "system"

**When Phrases Don't Match:**

The command provides helpful feedback:

```
Could not find concept matching "my vague term"
Closest matches were:
  - My Specific Term (similarity: 0.48, below threshold 0.50)
  - Another Related Term (similarity: 0.45)

Try:
  - Lower --min-similarity threshold (e.g., 0.3)
  - Use more specific 2-3 word phrases
  - Search first: kg search query "my vague term"
```

**Performance:**

- Short paths (2-3 hops): Fast (~1s)
- Medium paths (4-5 hops): Moderate (~2-5s)
- Long paths (6-7+ hops): Slower (exploring large subgraph)
- No path exists: Fast to determine (exhaustive search up to max-hops)

**Use Cases:**

- "How is X related to Y?"
- Discover unexpected connections
- Validate relationship chains
- Find reasoning paths
- Explore conceptual bridges

---

## Search Patterns and Workflows

### Discovery Workflow

```bash
# 1. Start with broad search
kg search query "machine learning" -l 20

# 2. Explore interesting result
kg search details concept_abc123

# 3. Find related concepts
kg search related concept_abc123

# 4. Trace connections
kg search connect concept_abc123 concept_xyz789
```

### Research Workflow

```bash
# Find core concept
kg search query "transformer architecture" --show-evidence

# Get all evidence
kg search details concept_abc123

# Find supporting concepts
kg search related concept_abc123 -t SUPPORTS EVIDENCED_BY

# Find contradictions
kg search related concept_abc123 -t CONTRADICTS
```

### Exploratory Analysis

```bash
# Cast wide net
kg search query "AI safety" --min-similarity 0.5 -l 50

# Explore neighborhood
kg search related concept_abc123 -d 3

# Find bridges between domains
kg search connect "AI safety" "software engineering"
```

---

## Understanding Grounding Strength

**What is Grounding?** (ADR-044)

Grounding strength represents probabilistic truth convergence - how well-evidenced and supported a concept is:

- **High (>80%)**: Strong evidence, multiple sources, supporting relationships
- **Medium (60-80%)**: Moderate evidence, some support
- **Low (<60%)**: Weak evidence, contradictions present, or newly added

**Calculation:**
- Number of evidence instances
- Supporting vs contradicting relationships
- Source diversity
- Relationship coherence

**Use Grounding To:**
- Assess concept reliability
- Prioritize well-evidenced concepts
- Identify concepts needing more evidence
- Detect controversial concepts (contradictions present)

---

## JSON Output

All search commands support `--json` for machine processing:

```bash
# Query results
kg search query "ML" --json | jq '.[].concept_id'

# Concept details
kg search details concept_abc123 --json | jq '.evidence | length'

# Related concepts
kg search related concept_abc123 --json | jq '.by_distance["1"] | length'

# Paths
kg search connect "A" "B" --json | jq '.paths | length'
```

---

## Performance Tips

### Fast Searches
```bash
# Skip grounding calculation
kg search query "term" --no-grounding
kg search details concept_abc123 --no-grounding
```

### Efficient Exploration
```bash
# Start with small depth
kg search related concept_abc123 -d 1

# Then expand if needed
kg search related concept_abc123 -d 3
```

### Phrase Matching
```bash
# Use specific phrases
kg search connect "specific phrase A" "specific phrase B"

# Not generic terms
# ❌ kg search connect "features" "issues"
```

---

## Troubleshooting

### No Results Found

```bash
# Try broader search
kg search query "term" --min-similarity 0.5 -l 50

# Check what concepts exist
kg database stats
kg ontology list
```

### Phrase Not Matching

```bash
# Lower similarity threshold
kg search connect "phrase" "target" --min-similarity 0.3

# Or search first to find exact IDs
kg search query "phrase"
# Use returned concept ID
```

### Slow Queries

```bash
# Disable grounding
kg search query "term" --no-grounding

# Reduce depth/hops
kg search related concept_abc123 -d 2
kg search connect "A" "B" --max-hops 4
```

---

## Related Commands

- [`kg ingest`](../ingest/) - Add content to search
- [`kg database stats`](../database/#stats) - View search space size
- [`kg ontology list`](../ontology/#list) - See knowledge domains
- [`kg vocab list`](../vocabulary/) - See relationship types

---

## See Also

- [Search Guide](../../01-getting-started/searching.md)
- [Graph Exploration](../../06-reference/graph-exploration.md)
- [ADR-044: Probabilistic Truth Convergence](../../../architecture/ADR-044-probabilistic-truth-convergence.md)
- [Vector Search Technical Details](../../06-reference/vector-search.md)
