# 14 - Advanced Query Patterns

**Part:** II - Configuration
**Reading Time:** ~18 minutes
**Prerequisites:** [Section 06 - Querying Your Knowledge Graph](06-querying-your-knowledge-graph.md), [Section 04 - Understanding Concepts and Relationships](04-understanding-concepts-and-relationships.md)

---

This section covers advanced query patterns for complex graph exploration beyond basic semantic search. Learn how to use fuzzy matching, find paths between concepts, analyze relationship patterns, and perform custom scoring to discover non-obvious connections in your knowledge graph.

## Beyond Vector Search

Section 06 introduced semantic search using vector embeddings:

```bash
kg search query "linear thinking"
```

This finds concepts semantically similar to your query. But sometimes you need more:

- **Fuzzy text matching** - Find concepts containing specific words
- **Path finding** - Discover how concepts connect
- **Relationship analysis** - Analyze connection types
- **Custom scoring** - Rank results by domain-specific criteria

These patterns use openCypher queries directly against the Apache AGE graph database.

## Accessing openCypher

### Via PostgreSQL Client

Connect directly to the database:

```bash
docker exec -it knowledge-graph-postgres psql -U admin -d knowledge_graph
```

Then run openCypher queries:

```sql
SELECT * FROM cypher('knowledge_graph', $$
    MATCH (c:Concept)
    WHERE c.label CONTAINS 'authentication'
    RETURN c.label
$$) as (label agtype);
```

### Via API (Advanced)

The API server exposes openCypher endpoints for custom queries (admin access required).

**Important:** All examples below show raw openCypher. When using AGE, wrap in `SELECT * FROM cypher('knowledge_graph', $$ ... $$) as (...)`.

## Fuzzy Label Matching

Semantic search finds similar concepts. Fuzzy matching finds concepts containing specific text.

### When to Use Fuzzy Matching

✅ **Use fuzzy matching when:**
- Looking for exact keywords ("API key", "authentication")
- Searching for technical terms that might appear in variations
- Finding all concepts related to a specific project or document
- Debugging: "Where did this concept come from?"

❌ **Use semantic search when:**
- Looking for conceptual similarity ("security" → "encryption", "access control")
- Exploring related ideas
- Finding concepts in unfamiliar domains

### CONTAINS - Most Common Pattern

Finds concepts where the label contains the search term:

```cypher
MATCH (c:Concept)
WHERE c.label CONTAINS "authentication"
RETURN c.label, c.concept_id
LIMIT 20
```

**Matches:**
- "authentication"
- "user authentication"
- "OAuth authentication flow"
- "multi-factor authentication"

**Doesn't match:**
- "Authentication" (case-sensitive)
- "auth" (partial word)

### Case-Insensitive CONTAINS (Recommended)

Most robust for user queries:

```cypher
MATCH (c:Concept)
WHERE toLower(c.label) CONTAINS toLower("authentication")
RETURN c.label, c.concept_id
LIMIT 20
```

**Matches:**
- "Authentication"
- "USER AUTHENTICATION"
- "OAuth Authentication Flow"
- "Multi-Factor Authentication"

This handles any case variation.

### STARTS WITH / ENDS WITH

For prefix or suffix matching:

```cypher
MATCH (c:Concept)
WHERE c.label STARTS WITH "authentication"
RETURN c.label
LIMIT 20
```

**STARTS WITH matches:**
- "authentication"
- "authentication flow"
- "authentication mechanism"

**Doesn't match:**
- "user authentication" (doesn't start with it)

```cypher
MATCH (c:Concept)
WHERE c.label ENDS WITH "authentication"
RETURN c.label
LIMIT 20
```

**ENDS WITH matches:**
- "authentication"
- "user authentication"
- "token-based authentication"

### Regular Expression - Most Flexible

Full pattern matching with regex:

```cypher
MATCH (c:Concept)
WHERE c.label =~ "(?i).*authentication.*"
RETURN c.label
LIMIT 20
```

**Regex patterns:**
- `(?i)` - Case insensitive flag
- `.*` - Match any characters (zero or more)
- `(auth|token)` - Match alternatives
- `^authentication` - Must start with "authentication"
- `authentication$` - Must end with "authentication"

**Examples:**

```cypher
-- Match "authentication" OR "authorization"
WHERE c.label =~ "(?i).*(authentication|authorization).*"

-- Match concepts starting with "auth"
WHERE c.label =~ "(?i)^auth.*"

-- Match multi-word concepts (2-3 words)
WHERE c.label =~ "^\\w+\\s+\\w+(\\s+\\w+)?$"

-- Match concepts containing numbers
WHERE c.label =~ ".*\\d+.*"
```

### Multiple Conditions with OR

Search for multiple related terms:

```cypher
MATCH (c:Concept)
WHERE c.label CONTAINS "authentication"
   OR c.label CONTAINS "authorization"
   OR c.label CONTAINS "access control"
RETURN c.label
LIMIT 30
```

Finds all security-related concepts matching any of these terms.

## Path Finding Between Concepts

Discover how concepts connect through relationships.

### Shortest Path

Find the shortest connection between two concepts:

```cypher
MATCH (start:Concept {label: "Authentication"}),
      (end:Concept {label: "Encryption"})
MATCH path = shortestPath((start)-[*]-(end))
RETURN [n in nodes(path) | n.label] as concepts,
       [r in relationships(path) | type(r)] as relationships,
       length(path) as hops
LIMIT 1
```

**Returns:**

```
concepts: ["Authentication", "Security", "Encryption"]
relationships: ["REQUIRES", "USES"]
hops: 2
```

This shows: Authentication → REQUIRES → Security → USES → Encryption

### Shortest Path with Fuzzy Matching

Combine path finding with regex for flexible concept selection:

```cypher
MATCH (start:Concept), (end:Concept)
WHERE start.label =~ "(?i).*authentication.*"
  AND end.label =~ "(?i).*encryption.*"
MATCH path = shortestPath((start)-[*]-(end))
RETURN start.label as from,
       end.label as to,
       [n in nodes(path) | n.label] as pathConcepts,
       length(path) as hops
ORDER BY hops ASC
LIMIT 10
```

Finds shortest paths between ANY authentication-related concept and ANY encryption-related concept.

### All Paths with Length Limit

Find multiple paths up to specified depth:

```cypher
MATCH (start:Concept {label: "Authentication"}),
      (end:Concept {label: "Encryption"})
MATCH path = (start)-[*1..5]-(end)
RETURN [n in nodes(path) | n.label] as concepts,
       [r in relationships(path) | type(r)] as relationships,
       length(path) as hops
ORDER BY hops ASC
LIMIT 20
```

**Parameters:**
- `[*1..5]` - Paths between 1 and 5 hops
- Returns multiple routes (not just shortest)
- See all possible connection patterns

**Use when:**
- Exploring different semantic routes
- Understanding redundant connections
- Finding alternative explanations

### Path with Detailed Relationship Types

See what kinds of relationships connect concepts:

```cypher
MATCH (start:Concept), (end:Concept)
WHERE start.label =~ "(?i).*microservices.*"
  AND end.label =~ "(?i).*resilience.*"
MATCH path = (start)-[*1..4]-(end)
WITH path,
     [n in nodes(path) | n.label] as concepts,
     [r in relationships(path) | type(r)] as relTypes,
     length(path) as hops
RETURN concepts, relTypes, hops
ORDER BY hops ASC
LIMIT 10
```

**Example output:**

```
concepts: ["Microservices", "Distributed Systems", "Fault Tolerance", "Resilience"]
relTypes: ["PART_OF", "REQUIRES", "ENABLES"]
hops: 3
```

Shows: Microservices are PART_OF Distributed Systems, which REQUIRES Fault Tolerance, which ENABLES Resilience.

### Multiple Start/End Concepts

Search across multiple concept variations:

```cypher
MATCH (start:Concept), (end:Concept)
WHERE start.label =~ "(?i).*(authentication|auth|login).*"
  AND end.label =~ "(?i).*(security|encryption|crypto).*"
MATCH path = shortestPath((start)-[*..6]-(end))
WHERE length(path) > 0
RETURN start.label as fromConcept,
       end.label as toConcept,
       [n in nodes(path) | n.label] as pathConcepts,
       length(path) as hops
ORDER BY hops ASC
LIMIT 15
```

**Matches:**
- Start: "authentication", "OAuth authentication", "login flow", "auth tokens"
- End: "security", "encryption", "cryptography", "data security"

Finds connections across terminology variations.

## Weighted Path Analysis

Rank paths by custom criteria beyond just length.

### Score by Relevant Intermediate Concepts

Prefer paths passing through domain-relevant concepts:

```cypher
MATCH (start:Concept), (end:Concept)
WHERE start.label =~ "(?i).*microservices.*"
  AND end.label =~ "(?i).*reliability.*"
MATCH path = (start)-[*1..5]-(end)
WITH path,
     length(path) as pathLength,
     size([n in nodes(path) WHERE n.label CONTAINS "fault" OR n.label CONTAINS "resilience"]) as relevantNodes
WITH path, pathLength, relevantNodes,
     (relevantNodes * 10 - pathLength) as customScore
RETURN [n in nodes(path) | n.label] as concepts,
       pathLength,
       relevantNodes,
       customScore
ORDER BY customScore DESC
LIMIT 10
```

**Scoring logic:**
- +10 points for each "fault" or "resilience" concept in path
- -1 point for each hop (shorter paths preferred)
- Higher score = more relevant path

**Example:**

```
Path A: Microservices → Distributed Systems → Reliability (2 hops, 0 relevant)
Score: (0 * 10) - 2 = -2

Path B: Microservices → Fault Tolerance → Resilience → Reliability (3 hops, 2 relevant)
Score: (2 * 10) - 3 = 17

Path B wins despite being longer - it passes through fault tolerance concepts.
```

### Score by Relationship Type Preferences

Prefer certain relationship types:

```cypher
MATCH (start:Concept), (end:Concept)
WHERE start.label =~ "(?i).*testing.*"
  AND end.label =~ "(?i).*quality.*"
MATCH path = (start)-[rels*1..5]-(end)
WITH path,
     length(path) as pathLength,
     size([r in rels WHERE type(r) = 'ENABLES']) as enablesCount,
     size([r in rels WHERE type(r) = 'IMPLIES']) as impliesCount,
     size([r in rels WHERE type(r) = 'SUPPORTS']) as supportsCount
WITH path, pathLength, enablesCount, impliesCount, supportsCount,
     (enablesCount * 5 + impliesCount * 3 + supportsCount * 2 - pathLength) as customScore
RETURN [n in nodes(path) | n.label] as concepts,
       [r in relationships(path) | type(r)] as relTypes,
       pathLength,
       enablesCount,
       impliesCount,
       supportsCount,
       customScore
ORDER BY customScore DESC
LIMIT 10
```

**Scoring logic:**
- +5 points for each `ENABLES` relationship (strong causal link)
- +3 points for each `IMPLIES` relationship (logical connection)
- +2 points for each `SUPPORTS` relationship (evidential connection)
- -1 point for each hop

Prioritizes paths with strong conceptual connections.

### Weighted Path (Relationship Properties)

If relationships have `weight` or `confidence` properties:

```cypher
MATCH (start:Concept {label: "Neural Networks"}),
      (end:Concept {label: "Image Recognition"})
MATCH path = (start)-[rels*1..5]-(end)
WITH path,
     reduce(score = 0.0, r in rels | score + coalesce(r.confidence, 0.5)) as totalConfidence,
     length(path) as pathLength
RETURN [n in nodes(path) | n.label] as concepts,
       [r in relationships(path) | type(r)] as relationships,
       totalConfidence,
       pathLength
ORDER BY totalConfidence DESC, pathLength ASC
LIMIT 10
```

**Scoring logic:**
- Sum confidence scores of all relationships
- Higher total confidence = more reliable path
- Break ties with shorter path length

## Relationship Analysis

Analyze patterns in how concepts connect.

### Count Relationships by Type

```cypher
MATCH (c1:Concept)-[r]->(c2:Concept)
RETURN type(r) as relationshipType,
       count(*) as count
ORDER BY count DESC
```

**Example output:**

```
relationshipType: SUPPORTS, count: 347
relationshipType: IMPLIES, count: 289
relationshipType: PART_OF, count: 234
relationshipType: REQUIRES, count: 187
```

Shows which relationship types dominate your graph.

### Find Highly Connected Concepts

```cypher
MATCH (c:Concept)
WITH c, size((c)-[]-()) as connectionCount
WHERE connectionCount > 10
RETURN c.label,
       connectionCount
ORDER BY connectionCount DESC
LIMIT 20
```

Finds "hub" concepts with many connections (potential key concepts).

### Find Concepts with Specific Relationship Patterns

```cypher
MATCH (c:Concept)
WHERE size((c)-[:IMPLIES]->()) > 5
  AND size((c)-[:CONTRADICTS]->()) > 2
RETURN c.label,
       size((c)-[:IMPLIES]->()) as impliesCount,
       size((c)-[:CONTRADICTS]->()) as contradictsCount
ORDER BY impliesCount DESC
```

Finds concepts that imply many things but also contradict several (nuanced concepts).

### Analyze Relationship Directions

```cypher
MATCH (c:Concept {label: "Authentication"})
OPTIONAL MATCH (c)-[out]->(c2:Concept)
OPTIONAL MATCH (c3:Concept)-[in]->(c)
RETURN c.label as concept,
       count(DISTINCT out) as outgoingCount,
       count(DISTINCT in) as incomingCount,
       collect(DISTINCT type(out)) as outgoingTypes,
       collect(DISTINCT type(in)) as incomingTypes
```

Shows what a concept connects TO vs what connects TO it.

## Traversal Depth Control

### Fixed Depth Traversal

Explore concepts exactly N hops away:

```cypher
MATCH (start:Concept {label: "Microservices"})
MATCH (start)-[*3]-(distant:Concept)
RETURN DISTINCT distant.label
LIMIT 20
```

Finds concepts exactly 3 hops from "Microservices" (not 1, not 2, exactly 3).

### Variable Depth with Filters

```cypher
MATCH (start:Concept {label: "Authentication"})
MATCH path = (start)-[*1..3]-(related:Concept)
WHERE ALL(n in nodes(path) WHERE n.label <> "Generic Concept")
  AND related <> start
RETURN DISTINCT related.label,
       length(path) as distance
ORDER BY distance ASC
LIMIT 30
```

**Filters:**
- Exclude paths through "Generic Concept" (noise reduction)
- Exclude the starting concept itself
- Return concepts 1-3 hops away

### Find Concepts in Specific Distance Range

```cypher
MATCH (start:Concept {label: "Neural Networks"})
MATCH path = (start)-[*2..4]-(related:Concept)
WHERE length(path) >= 2 AND length(path) <= 4
RETURN DISTINCT related.label,
       min(length(path)) as minDistance
ORDER BY minDistance ASC, related.label
LIMIT 40
```

Finds concepts 2-4 hops away (not too close, not too far).

## Cross-Document Concept Analysis

### Find Concepts Appearing in Multiple Documents

```cypher
MATCH (c:Concept)-[:APPEARS_IN]->(s:Source)
WITH c, collect(DISTINCT s.document) as documents
WHERE size(documents) > 1
RETURN c.label,
       documents,
       size(documents) as documentCount
ORDER BY documentCount DESC
LIMIT 20
```

Finds concepts discussed across multiple sources (important cross-cutting themes).

### Find Document-Specific Concepts

```cypher
MATCH (c:Concept)-[:APPEARS_IN]->(s:Source)
WHERE s.document = "architecture-decisions.md"
RETURN c.label,
       count(*) as occurrences
ORDER BY occurrences DESC
LIMIT 30
```

Concepts unique to a specific document.

### Analyze Concept Overlap Between Documents

```cypher
MATCH (s1:Source {document: "doc1.md"})<-[:APPEARS_IN]-(c:Concept)-[:APPEARS_IN]->(s2:Source {document: "doc2.md"})
RETURN count(DISTINCT c) as sharedConcepts,
       collect(DISTINCT c.label) as conceptList
```

Measures semantic similarity between documents.

## Apache AGE Specific Considerations

### Wrapping Queries in SELECT

All openCypher queries must be wrapped for AGE:

```sql
SELECT * FROM cypher('knowledge_graph', $$
    MATCH (c:Concept)
    WHERE c.label CONTAINS 'authentication'
    RETURN c.label
$$) as (label agtype);
```

**Important:**
- Graph name: `'knowledge_graph'`
- Query wrapped in `$$ ... $$`
- Result columns specified: `as (label agtype)`

### ORDER BY Restrictions

AGE doesn't support ORDER BY with path variables directly. Use WITH clause first:

```cypher
-- Won't work in AGE
MATCH path = shortestPath((start)-[*]-(end))
RETURN path
ORDER BY length(path)  -- Error!

-- Works in AGE
MATCH path = shortestPath((start)-[*]-(end))
WITH path, length(path) as len
RETURN path, len
ORDER BY len  -- Now works!
```

Always extract sortable values in WITH clause before ORDER BY.

### Result Type Casting

AGE returns `agtype` values. In Python:

```python
from psycopg2.extras import Json

# AGE query result
result = cursor.fetchall()

# Parse agtype column
for row in result:
    label = row[0]  # Still wrapped in agtype
    # Parse with: json.loads(label) or custom parser
```

The API server handles this automatically in `_parse_agtype()`.

## Practical Query Patterns

### Debug: Where Did This Concept Come From?

```cypher
MATCH (c:Concept {concept_id: "some-concept-id"})
MATCH (c)-[:EVIDENCED_BY]->(i:Instance)-[:FROM_SOURCE]->(s:Source)
RETURN c.label as concept,
       i.quote as evidence,
       s.document as sourceDocument,
       s.paragraph as paragraph
```

Traces concept back to original source quotes.

### Find All Concepts from a Source

```cypher
MATCH (s:Source {document: "architecture-decisions.md"})
MATCH (s)<-[:FROM_SOURCE]-(i:Instance)<-[:EVIDENCED_BY]-(c:Concept)
RETURN DISTINCT c.label
ORDER BY c.label
```

Lists all concepts extracted from a document.

### Verify Relationship Evidence

```cypher
MATCH (c1:Concept {label: "Microservices"})-[r:REQUIRES]->(c2:Concept {label: "API Gateway"})
MATCH (c1)-[:EVIDENCED_BY]->(i1:Instance)-[:FROM_SOURCE]->(s:Source)
WHERE i1.quote CONTAINS 'gateway' OR i1.quote CONTAINS 'API'
RETURN r as relationship,
       i1.quote as supportingEvidence,
       s.document as source
```

Checks if a relationship is supported by evidence.

### Find Contradictions

```cypher
MATCH (c1:Concept)-[:CONTRADICTS]->(c2:Concept)
RETURN c1.label as concept1,
       c2.label as concept2
ORDER BY c1.label
LIMIT 20
```

Lists all pairs of contradicting concepts.

### Explore Concept Neighborhood

```cypher
MATCH (center:Concept {label: "Authentication"})
MATCH (center)-[r]-(neighbor:Concept)
RETURN center.label as centerConcept,
       type(r) as relationship,
       neighbor.label as relatedConcept
ORDER BY type(r), neighbor.label
```

Shows all directly connected concepts with relationship types.

## Performance Tips

### Limit Traversal Depth

```cypher
-- Good: Limited depth
MATCH path = (start)-[*1..5]-(end)

-- Bad: Unlimited depth (can be very slow)
MATCH path = (start)-[*]-(end)
```

Always specify maximum depth for variable-length paths.

### Use LIMIT Generously

```cypher
MATCH (c:Concept)
WHERE c.label CONTAINS 'authentication'
RETURN c
LIMIT 50  -- Always limit large result sets
```

Prevents overwhelming the client with thousands of results.

### Filter Early

```cypher
-- Good: Filter in WHERE before traversal
MATCH (start:Concept)
WHERE start.label =~ '(?i).*auth.*'
MATCH path = (start)-[*1..3]-(end)

-- Less efficient: Match everything, then filter
MATCH path = (start:Concept)-[*1..3]-(end:Concept)
WHERE start.label =~ '(?i).*auth.*'
```

Apply filters as early as possible in the query.

### Use DISTINCT Wisely

```cypher
-- If you know results are unique, skip DISTINCT
MATCH (c:Concept {concept_id: 'abc123'})
RETURN c  -- No DISTINCT needed (concept_id is unique)

-- Use DISTINCT when aggregating or traversing
MATCH (c:Concept)-[*1..3]-(related:Concept)
RETURN DISTINCT related.label  -- Needed: multiple paths to same concept
```

DISTINCT has overhead - only use when necessary.

## What's Next

Now that you understand advanced querying, you can:

- **[Section 15 - Integration with Claude Desktop (MCP)](15-integration-with-claude-desktop-mcp.md)**: Use the graph with Claude
- **[Section 62 - Query Examples Gallery](62-query-examples-gallery.md)**: Library of useful queries

For technical details:
- **Architecture:** [ADR-016 - Apache AGE Migration](architecture/ADR-016-apache-age-migration.md)
- **API Reference:** [api/CYPHER_PATTERNS.md](api/CYPHER_PATTERNS.md)
- **AGE Manual:** https://age.apache.org/age-manual/master/intro/overview.html

---

← [Previous: Managing Relationship Vocabulary](13-managing-relationship-vocabulary.md) | [Documentation Index](README.md) | [Next: Integration with Claude Desktop (MCP) →](15-integration-with-claude-desktop-mcp.md)
