# Cross-Ontology Knowledge Linking: A Practical Example

## Overview

This guide demonstrates one of the knowledge graph system's most powerful capabilities: **automatic semantic linking across knowledge domains**. Unlike traditional documentation systems that require manual tagging or explicit cross-references, this system discovers and creates connections automatically through semantic understanding.

## What Makes This Special

Most knowledge management systems work like this:
- **GitHub Issues/Wikis:** Manual cross-references, explicit tags, hierarchical organization
- **Document Management:** File/folder hierarchies, manual categorization, keyword search
- **Traditional Databases:** Rigid schemas, explicit foreign keys, manual relationship definition

This knowledge graph works differently:
- **Write naturally** about any topic
- **No manual tagging** or categorization required
- **Automatic concept extraction** from context
- **Semantic relationship discovery** between concepts
- **Cross-ontology linking** when concepts span domains

## Real-World Demonstration

### The Experiment

We conducted a live test to demonstrate cross-ontology linking:

**Step 1: Created technical documentation**
- Wrote detailed implementation notes about ADR-068 Phase 4 (unified embedding regeneration)
- Ingested into ontology: `ADR-068-Phase4-Implementation`
- Result: 8 concepts extracted, 7 relationships discovered

**Step 2: Found an existing AI concept**
- Searched for "AI Models" in the graph
- Found existing concept from `AI-Applications` ontology
- This concept had no prior connection to ADR-068 work

**Step 3: Wrote bridging content**
- Created article about "Managing Embedding Models in Production AI Systems"
- Discussed both AI models generally AND our specific ADR-068 implementation
- Ingested into ontology: `AI-Applications` (different from ADR-068 ontology)

### What Happened Automatically

The knowledge graph:

1. **Merged concepts across ontologies:**
   ```
   "Unified Embedding Regeneration"
   Documents: ADR-068-Phase4-Implementation, AI-Applications
   Evidence: 2 instances (was 1)
   Diversity: 39.2% with 10 related concepts (was 7)
   ```

2. **Created cross-ontology relationship paths:**
   ```
   Embedding Models (AI-Applications)
     ↓ REQUIRES
   Model Migration (AI-Applications)
     ↓ ADDRESSES
   Unified Embedding Regeneration (ADR-068-Phase4-Implementation)
   ```

3. **Discovered semantic connections:**
   - Embedding models require migration strategies
   - Migration challenges are addressed by unified regeneration
   - Migration requires compatibility checking systems

**Time to create these connections:** ~15 seconds during ingestion
**Manual effort required:** Zero - just write naturally
**Cost:** $0.02 for LLM extraction

## Comparison: Knowledge Graph vs GitHub API

We also compared retrieving this information via traditional means:

### GitHub Issues Approach

```json
{
  "title": "Add GraphQueryFacade methods for source embedding operations",
  "labels": ["enhancement", "query-safety", "embeddings"],
  "body": "Markdown text with context...",
  "created_at": "2025-11-29T03:57:50Z"
}
```

**Capabilities:**
- ✓ Stores structured metadata
- ✓ Returns flat JSON
- ✗ No semantic understanding
- ✗ No automatic relationship discovery
- ✗ Can't query: "What validates the regeneration system?"
- ✗ Can't traverse: "What does GraphQueryFacade facilitate?"
- ✗ Labels are just strings - no semantic meaning

### Knowledge Graph Approach

```
Unified Embedding Regeneration
  Similarity: 79.8% match for "embedding regeneration compatibility"
  Grounding: 15% (weak but diverse support)
  Diversity: 38.2% (7 related concepts)

  Relationships discovered:
  - Bug Fix SUPPORTS Unified Regeneration
  - Testing VALIDATES Unified Regeneration
  - Compatibility Checking INCLUDES Unified Regeneration
  - GraphQueryFacade FACILITATES Unified Regeneration
```

**Capabilities:**
- ✓ Automatic concept extraction
- ✓ Semantic similarity search
- ✓ Relationship discovery
- ✓ Cross-ontology linking
- ✓ Can query: "What validates this?" → Testing and Verification
- ✓ Can traverse: Distance 1, Distance 2 relationship paths
- ✓ Grounding and diversity metrics
- ✓ Evidence samples with sources

## Practical Applications

### 1. Documentation That Remembers Context

**Traditional approach:**
```
You: "Where did we document the embedding regeneration bug fix?"
Search: Returns 15 files mentioning "embedding" or "bug"
You: Manually read through each to find the right context
```

**Knowledge graph approach:**
```
You: Search for "embedding regeneration bug fix"
Graph: Returns Bug Fix concept with:
  - Exact description of what was fixed
  - Links to related concepts (what it supports, what caused it)
  - Evidence samples from source documents
  - Grounding showing how well-supported the concept is
```

### 2. Cross-Domain Knowledge Discovery

**Scenario:** You're working on AI model management and want to understand how it relates to your production systems.

**Traditional approach:**
- Search for "AI models" in one folder/repo
- Search for "production systems" in another
- Manually figure out connections
- Hope you didn't miss anything

**Knowledge graph approach:**
```
Query: concept.connect(from="AI models", to="production systems")
Graph: Returns relationship paths showing:
  - AI Models → requires → Model Migration
  - Model Migration → addresses → Unified Regeneration
  - Unified Regeneration → part of → Production Systems
```

### 3. Evolving Knowledge Over Time

**The power:** As you add new content, the graph automatically integrates it with existing knowledge.

Example from our experiment:
- **Day 1:** Document ADR-068 implementation (creates concepts)
- **Day 30:** Write about AI model management (mentions ADR-068 concepts)
- **Result:** Automatic cross-linking happens during ingestion
- **Benefit:** Your knowledge base becomes more interconnected over time without manual maintenance

## Technical Implementation Notes

### How Cross-Ontology Linking Works

1. **Concept Extraction:** LLM analyzes text and extracts concepts with descriptions
2. **Similarity Matching:** New concepts are compared against all existing concepts via embedding similarity
3. **Concept Merging:** If similarity exceeds threshold (~70-75%), concepts are treated as the same entity
4. **Evidence Accumulation:** Each source that mentions the concept adds to its evidence
5. **Relationship Discovery:** LLM identifies semantic relationships between concepts in the same chunk
6. **Cross-Ontology Paths:** Graph traversal can find paths between concepts from different ontologies

### Configuration

**Similarity thresholds:**
- Default concept matching: 70%
- Search results: 70% (adjustable with `--min-similarity`)
- Relationship discovery: Extracted by LLM, not threshold-based

**Ontology isolation:**
- Sources are isolated per ontology (can query by ontology)
- Concepts are global (automatically merge across ontologies)
- Relationships span ontologies when concepts match

## Best Practices

### Writing for Optimal Linking

1. **Use consistent terminology:** The graph matches semantically, but consistent terms help
2. **Provide context:** More context = better concept extraction and relationship discovery
3. **Write naturally:** Don't force keywords or tags - semantic understanding works best with natural language
4. **Bridge domains explicitly:** When connecting different topics, explain the relationship

### Querying Across Ontologies

```bash
# Search all ontologies (default)
kg search query "embedding regeneration"

# Search specific ontology
kg admin embedding status --ontology "AI-Applications"

# Find concept relationships
kg search details <concept-id>

# Find paths between concepts (via MCP)
mcp concept.connect(from_query="concept A", to_query="concept B")
```

### Ontology Organization

**Recommended approach:**
- **Domain-based ontologies:** Group by subject area (AI-Applications, Infrastructure, etc.)
- **Project-based ontologies:** Group by project or ADR when implementation-specific
- **Let concepts merge:** Don't worry about duplication - the graph handles it

**Anti-patterns:**
- Don't create too many tiny ontologies (harder to discover connections)
- Don't manually try to enforce connections (let semantic matching work)
- Don't treat ontologies like strict boundaries (concepts should flow between them)

## Conclusion

The knowledge graph transforms documentation from a **filing system** into a **thinking partner** that:

- Remembers what you write
- Understands semantic relationships
- Discovers connections automatically
- Answers questions about your work
- Gets smarter as you add more content

Unlike traditional systems that require manual organization and explicit linking, this system works the way you think - by understanding meaning and context, not just keywords and hierarchies.

## Further Reading

- [Architecture Documentation](../architecture/ARCHITECTURE.md) - Overall system design
- [ADR-048: GraphQueryFacade](../architecture/ADR-048-query-facade-namespace-safety.md) - Query safety and namespace isolation
- [ADR-068: Unified Embedding Regeneration](../architecture/ADR-068-unified-embedding-regeneration.md) - The example used in this guide
- [API Documentation](../reference/api/) - REST API reference
- [MCP Integration](../reference/mcp/) - Claude Desktop integration
