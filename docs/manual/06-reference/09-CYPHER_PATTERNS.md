# Advanced Cypher Query Patterns for Apache AGE

This document contains advanced Cypher query patterns for complex graph exploration beyond basic vector search.

## Table of Contents

1. [Fuzzy Label Matching](#fuzzy-label-matching)
2. [Path Finding with Scoring](#path-finding-with-scoring)
3. [Regex-Based Concept Matching](#regex-based-concept-matching)
4. [Weighted Path Analysis](#weighted-path-analysis)

---

## Fuzzy Label Matching

When you need flexible matching instead of exact labels, use `WHERE` clauses with various string operators.

### Basic Exact Match (for reference)

```cypher
MATCH (c:Concept {label: "agile"})
OPTIONAL MATCH evidence = (c)-[:EVIDENCED_BY]->(i:Instance)-[:FROM_SOURCE]->(s:Source)
OPTIONAL MATCH concepts = (c)-[r]-(c2:Concept)
RETURN c, evidence, concepts
LIMIT 30
```

### 1. CONTAINS - Most Common for Fuzzy Matching

Finds concepts where label contains the search term anywhere.

```cypher
MATCH (c:Concept)
WHERE c.label CONTAINS "agile"
OPTIONAL MATCH evidence = (c)-[:EVIDENCED_BY]->(i:Instance)-[:FROM_SOURCE]->(s:Source)
OPTIONAL MATCH concepts = (c)-[r]-(c2:Concept)
RETURN c, evidence, concepts
LIMIT 30
```

**Matches:** "agile", "agile methodology", "being agile", "Agile Manifesto"

### 2. Case-Insensitive CONTAINS (Recommended)

Most robust for user queries - handles any case variation.

```cypher
MATCH (c:Concept)
WHERE toLower(c.label) CONTAINS toLower("agile")
OPTIONAL MATCH evidence = (c)-[:EVIDENCED_BY]->(i:Instance)-[:FROM_SOURCE]->(s:Source)
OPTIONAL MATCH concepts = (c)-[r]-(c2:Concept)
RETURN c, evidence, concepts
LIMIT 30
```

**Matches:** "Agile", "AGILE", "agile methodology", "Being Agile"

### 3. STARTS WITH / ENDS WITH

For prefix or suffix matching.

```cypher
MATCH (c:Concept)
WHERE c.label STARTS WITH "agile"
-- or WHERE c.label ENDS WITH "agile"
OPTIONAL MATCH evidence = (c)-[:EVIDENCED_BY]->(i:Instance)-[:FROM_SOURCE]->(s:Source)
OPTIONAL MATCH concepts = (c)-[r]-(c2:Concept)
RETURN c, evidence, concepts
LIMIT 30
```

**STARTS WITH matches:** "agile", "agile methodology", "agile practices"
**ENDS WITH matches:** "being agile", "truly agile"

### 4. Regular Expression - Most Flexible

Full pattern matching with regex support.

```cypher
MATCH (c:Concept)
WHERE c.label =~ "(?i).*agile.*"
-- (?i) makes it case-insensitive
-- .* matches any characters before/after
OPTIONAL MATCH evidence = (c)-[:EVIDENCED_BY]->(i:Instance)-[:FROM_SOURCE]->(s:Source)
OPTIONAL MATCH concepts = (c)-[r]-(c2:Concept)
RETURN c, evidence, concepts
LIMIT 30
```

**Regex Patterns:**
- `(?i)` - Case insensitive flag
- `.*` - Match any characters (zero or more)
- `(agile|scrum)` - Match alternatives
- `^agile` - Must start with "agile"
- `agile$` - Must end with "agile"

### 5. Multiple Conditions with OR

Search for multiple related terms at once.

```cypher
MATCH (c:Concept)
WHERE c.label CONTAINS "agile"
   OR c.label CONTAINS "scrum"
   OR c.label =~ "(?i).*kanban.*"
OPTIONAL MATCH evidence = (c)-[:EVIDENCED_BY]->(i:Instance)-[:FROM_SOURCE]->(s:Source)
OPTIONAL MATCH concepts = (c)-[r]-(c2:Concept)
RETURN c, evidence, concepts
LIMIT 30
```

---

## Path Finding with Scoring

Find connections between concepts with various scoring strategies.

### 1. Shortest Path with Regex Matching

Simple shortest path between fuzzy-matched concepts.

```cypher
MATCH (start:Concept), (end:Concept)
WHERE start.label =~ "(?i).*agile.*"
  AND end.label =~ "(?i).*human.*"
MATCH path = shortestPath((start)-[*]-(end))
RETURN start.label, end.label, path, length(path) as pathLength
ORDER BY pathLength ASC
LIMIT 10
```

**Returns:** Shortest connection between any "agile" and "human" concepts.

### 2. All Paths with Length Limit

More comprehensive - finds multiple paths up to specified depth.

```cypher
MATCH (start:Concept), (end:Concept)
WHERE start.label =~ "(?i).*agile.*"
  AND end.label =~ "(?i).*human.*"
MATCH path = (start)-[*1..5]-(end)
WITH path, length(path) as pathLength,
     [n in nodes(path) | n.label] as nodeLabels
RETURN nodeLabels, pathLength
ORDER BY pathLength ASC
LIMIT 20
```

**Parameters:**
- `[*1..5]` - Paths between 1 and 5 hops
- Adjust `LIMIT` to control result count

### 3. Weighted Path (If Relationships Have Scores)

Accumulate relationship weights for path scoring.

```cypher
MATCH (start:Concept), (end:Concept)
WHERE start.label =~ "(?i).*agile.*"
  AND end.label =~ "(?i).*human.*"
MATCH path = (start)-[rels*1..5]-(end)
WITH path,
     reduce(score = 0, r in rels | score + coalesce(r.weight, 1)) as totalScore,
     length(path) as pathLength
RETURN [n in nodes(path) | n.label] as concepts,
       [r in relationships(path) | type(r)] as relationships,
       totalScore,
       pathLength
ORDER BY totalScore DESC, pathLength ASC
LIMIT 10
```

**Use when:** Your graph has `weight` or `confidence` properties on relationships.

### 4. Multiple Start/End Concepts with Best Path

Search across multiple concept variations simultaneously.

```cypher
MATCH (start:Concept), (end:Concept)
WHERE start.label =~ "(?i).*(agile|scrum|lean).*"
  AND end.label =~ "(?i).*(human|person|people).*"
MATCH path = shortestPath((start)-[*..6]-(end))
WHERE length(path) > 0
WITH start, end, path, length(path) as pathLength
RETURN start.label as fromConcept,
       end.label as toConcept,
       [n in nodes(path) | n.label] as pathConcepts,
       pathLength
ORDER BY pathLength ASC
LIMIT 15
```

**Matches:**
- Start: "agile", "scrum", "lean", "lean agile", "scrum methodology"
- End: "human", "person", "people", "human nature"

### 5. Detailed Path with Relationship Types

See what kinds of relationships connect concepts.

```cypher
MATCH (start:Concept), (end:Concept)
WHERE start.label =~ "(?i).*agile.*"
  AND end.label =~ "(?i).*human.*"
MATCH path = (start)-[*1..5]-(end)
RETURN [n in nodes(path) | n.label] as concepts,
       [r in relationships(path) | type(r)] as relationshipTypes,
       length(path) as hops
ORDER BY hops ASC
LIMIT 10
```

**Output includes:** Concept labels AND relationship types (SUPPORTS, IMPLIES, etc.)

---

## Regex-Based Concept Matching

Key patterns for flexible concept discovery.

### Case-Insensitive Anywhere Match

```cypher
WHERE c.label =~ "(?i).*pattern.*"
```

### Starts With Pattern

```cypher
WHERE c.label =~ "(?i)^pattern.*"
```

### Ends With Pattern

```cypher
WHERE c.label =~ "(?i).*pattern$"
```

### Exact Match (Case Insensitive)

```cypher
WHERE c.label =~ "(?i)^pattern$"
```

### Multiple Alternatives

```cypher
WHERE c.label =~ "(?i).*(pattern1|pattern2|pattern3).*"
```

### Complex Patterns

```cypher
-- Match "agile" followed by optional space and any word
WHERE c.label =~ "(?i)agile\\s*\\w+"

-- Match concepts containing numbers
WHERE c.label =~ ".*\\d+.*"

-- Match concepts that are 2-3 words
WHERE c.label =~ "^\\w+\\s+\\w+(\\s+\\w+)?$"
```

---

## Weighted Path Analysis

Custom scoring based on domain-specific criteria.

### Example: Score Paths by Relevant Intermediate Concepts

```cypher
MATCH (start:Concept), (end:Concept)
WHERE start.label =~ "(?i).*agile.*"
  AND end.label =~ "(?i).*human.*"
MATCH path = (start)-[*1..5]-(end)
WITH path,
     length(path) as pathLength,
     size([n in nodes(path) WHERE n.label CONTAINS "team" OR n.label CONTAINS "collaboration"]) as relevantNodes
WITH path, pathLength, relevantNodes,
     (relevantNodes * 10 - pathLength) as customScore
RETURN [n in nodes(path) | n.label] as concepts,
       pathLength,
       relevantNodes,
       customScore
ORDER BY customScore DESC
LIMIT 10
```

**Scoring Logic:**
- +10 points for each "team" or "collaboration" concept in path
- -1 point for each hop (shorter paths preferred)
- Higher score = more relevant path

### Example: Relationship Type Preferences

```cypher
MATCH (start:Concept), (end:Concept)
WHERE start.label =~ "(?i).*agile.*"
  AND end.label =~ "(?i).*human.*"
MATCH path = (start)-[rels*1..5]-(end)
WITH path,
     length(path) as pathLength,
     size([r in rels WHERE type(r) = 'SUPPORTS']) as supportsCount,
     size([r in rels WHERE type(r) = 'IMPLIES']) as impliesCount
WITH path, pathLength, supportsCount, impliesCount,
     (supportsCount * 5 + impliesCount * 3 - pathLength) as customScore
RETURN [n in nodes(path) | n.label] as concepts,
       [r in relationships(path) | type(r)] as relTypes,
       pathLength,
       supportsCount,
       impliesCount,
       customScore
ORDER BY customScore DESC
LIMIT 10
```

**Scoring Logic:**
- +5 points for each SUPPORTS relationship
- +3 points for each IMPLIES relationship
- -1 point for each hop
- Prioritizes strong conceptual connections

---

## Usage with AGE

### Important Notes for Apache AGE

1. **Wrap all Cypher in SELECT:**
   ```cypher
   SELECT * FROM cypher('knowledge_graph', $$
       MATCH (c:Concept)
       WHERE c.label =~ "(?i).*pattern.*"
       RETURN c
   $$) as (c agtype);
   ```

2. **ORDER BY Restrictions:**
   - AGE doesn't support ORDER BY with path variables directly
   - Use WITH clause to extract sortable values first:
   ```cypher
   MATCH path = shortestPath(...)
   WITH path, length(path) as len
   RETURN path, len
   ORDER BY len  -- Now works!
   ```

3. **Result Type Casting:**
   - AGE returns `agtype` values
   - Parse with `_parse_agtype()` in Python
   - Extract column names with `_extract_column_spec()`

---

## Integration Examples

### Add Fuzzy Search to API

```python
def fuzzy_search_concepts(
    self,
    search_term: str,
    match_type: str = "contains",  # contains, starts_with, regex
    limit: int = 10
) -> List[Dict[str, Any]]:
    """Search concepts with fuzzy label matching."""

    if match_type == "contains":
        where_clause = f"WHERE toLower(c.label) CONTAINS toLower('{search_term}')"
    elif match_type == "starts_with":
        where_clause = f"WHERE c.label STARTS WITH '{search_term}'"
    elif match_type == "regex":
        where_clause = f"WHERE c.label =~ '(?i){search_term}'"
    else:
        raise ValueError(f"Invalid match_type: {match_type}")

    query = f"""
    MATCH (c:Concept)
    {where_clause}
    RETURN c.concept_id as concept_id, c.label as label
    LIMIT {limit}
    """

    return self._execute_cypher(query)
```

### Add Scored Path Finding

```python
def find_scored_path(
    self,
    from_pattern: str,
    to_pattern: str,
    max_hops: int = 5,
    scoring_keywords: List[str] = []
) -> List[Dict[str, Any]]:
    """Find paths with custom relevance scoring."""

    keyword_conditions = " OR ".join([
        f'n.label CONTAINS "{kw}"' for kw in scoring_keywords
    ])

    query = f"""
    MATCH (start:Concept), (end:Concept)
    WHERE start.label =~ '(?i).*{from_pattern}.*'
      AND end.label =~ '(?i).*{to_pattern}.*'
    MATCH path = (start)-[*1..{max_hops}]-(end)
    WITH path,
         length(path) as pathLength,
         size([n in nodes(path) WHERE {keyword_conditions}]) as relevantNodes
    WITH path, pathLength, relevantNodes,
         (relevantNodes * 10 - pathLength) as score
    RETURN
        [n in nodes(path) | n.label] as concepts,
        pathLength,
        score
    ORDER BY score DESC
    LIMIT 10
    """

    return self._execute_cypher(query)
```

---

## References

- [Apache AGE Documentation](https://age.apache.org/age-manual/master/intro/overview.html)
- [Cypher Query Language](https://neo4j.com/docs/cypher-manual/current/)
- [AGE vs Neo4j Differences](../../architecture/ADR-016-apache-age-migration.md)

---

**Last Updated:** 2025-10-08
**Apache AGE Migration:** ADR-016
