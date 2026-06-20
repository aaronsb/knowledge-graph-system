---
id: 05.004.R
domain: query
mode: reference
---

# Cypher Patterns

openCypher queries for exploring and analyzing a Kappa Graph. All examples run against Apache AGE 1.7.0 on PostgreSQL 18 via the `knowledge_graph` AGE graph.

---

## Graph data model

**Nodes**

| Label | Key properties |
|---|---|
| `Concept` | `concept_id`, `label`, `embedding` (1536-dim vector), `search_terms` (array) |
| `Instance` | `instance_id`, `quote` |
| `Source` | `source_id`, `document`, `paragraph`, `full_text`, `type` |
| `Ontology` | `ontology_id`, `name`, `embedding`, `search_terms`, `lifecycle_state` |

**Edges**

| Pattern | Meaning |
|---|---|
| `(Concept)-[:EVIDENCED_BY]->(Instance)` | Concept is supported by this text fragment |
| `(Instance)-[:FROM_SOURCE]->(Source)` | Fragment originates from this source chunk |
| `(Concept)-[:APPEARS]->(Source)` | Concept is present in this source chunk |
| `(Concept)-[:IMPLIES\|SUPPORTS\|CONTRADICTS\|ENABLES\|PART_OF {confidence: float}]->(Concept)` | Typed semantic relationship between concepts |
| `(Source)-[:SCOPED_BY]->(Ontology)` | Source chunk belongs to this ontology |

**Indexes**

| Name | Type | Target |
|---|---|---|
| `concept-embeddings` | Vector (cosine, 1536-dim) | `Concept.embedding` |
| `ontology-embeddings` | Vector (cosine, 1536-dim) | `Ontology.embedding` |
| `instance_fulltext` | Full-text | `Instance.quote` |
| `concept_fulltext` | Full-text | `Concept.label`, `Concept.search_terms` |

---

## Running queries

### kg CLI
```bash
kg search query "your search term"
kg database stats
```

### psql direct access
```sql
docker exec -it knowledge-graph-postgres psql -U admin -d knowledge_graph

SELECT * FROM cypher('knowledge_graph', $$
  MATCH (c:Concept) RETURN c.label LIMIT 10
$$) AS (label agtype);
```

### REST API
```bash
curl http://localhost:8000/queries/stats
```

Apache AGE requires wrapping every openCypher statement in `SELECT * FROM cypher('knowledge_graph', $$ ... $$) AS (col agtype)`. The kg CLI and API server handle this automatically.

---

## Apache AGE constraints

These differ from Neo4j behavior and affect every query in this document.

| Constraint | Detail |
|---|---|
| No `shortestPath()` | AGE does not implement Neo4j's `shortestPath()` or `SHORTEST` keyword. Use variable-length patterns or application-level BFS (ADR-506). See [AGE issue #2162](https://github.com/apache/age/issues/2162). |
| `ORDER BY` on paths | AGE does not support `ORDER BY` on path variables directly. Extract a sortable value with `WITH` first. |
| Variable-length path cost | `-[*1..N]-` enumerates all paths (exponential). Keep `N ≤ 4` for interactive queries. See [AGE issue #195](https://github.com/apache/age/issues/195). |
| Result type | AGE returns `agtype`. Parse with `_parse_agtype()` in Python; extract column names with `_extract_column_spec()`. |

---

## Concept lookup

### Exact match

```cypher
MATCH (c:Concept {label: "agile"})
OPTIONAL MATCH evidence = (c)-[:EVIDENCED_BY]->(i:Instance)-[:FROM_SOURCE]->(s:Source)
OPTIONAL MATCH concepts  = (c)-[r]-(c2:Concept)
RETURN c, evidence, concepts
LIMIT 30
```

### Case-insensitive substring match

```cypher
MATCH (c:Concept)
WHERE toLower(c.label) CONTAINS toLower("agile")
OPTIONAL MATCH evidence = (c)-[:EVIDENCED_BY]->(i:Instance)-[:FROM_SOURCE]->(s:Source)
OPTIONAL MATCH concepts  = (c)-[r]-(c2:Concept)
RETURN c, evidence, concepts
LIMIT 30
```

### Prefix and suffix match

```cypher
MATCH (c:Concept)
WHERE c.label STARTS WITH "agile"
-- or WHERE c.label ENDS WITH "agile"
RETURN c.label
LIMIT 30
```

### Regex match

```cypher
MATCH (c:Concept)
WHERE c.label =~ "(?i).*agile.*"
RETURN c.label
LIMIT 30
```

| Regex token | Meaning |
|---|---|
| `(?i)` | Case-insensitive |
| `.*` | Any characters |
| `(a\|b)` | Alternatives |
| `^agile` | Anchored start |
| `agile$` | Anchored end |

### Multiple terms

```cypher
MATCH (c:Concept)
WHERE c.label CONTAINS "agile"
   OR c.label CONTAINS "scrum"
   OR c.label =~ "(?i).*kanban.*"
OPTIONAL MATCH evidence = (c)-[:EVIDENCED_BY]->(i:Instance)-[:FROM_SOURCE]->(s:Source)
OPTIONAL MATCH concepts  = (c)-[r]-(c2:Concept)
RETURN c, evidence, concepts
LIMIT 30
```

---

## Evidence queries

### Trace a concept to source quotes (tabular)

```cypher
MATCH (c:Concept {label: "Human Variety"})
      -[:EVIDENCED_BY]->(i:Instance)
      -[:FROM_SOURCE]->(s:Source)
RETURN c.label, i.quote, s.document, s.paragraph
LIMIT 5
```

### Concepts with most evidence

```cypher
MATCH (c:Concept)-[:EVIDENCED_BY]->(i:Instance)
WITH c, count(i) AS evidence_count
RETURN c.label, evidence_count
ORDER BY evidence_count DESC
LIMIT 10
```

### Full evidence chain (visual)

```cypher
MATCH path = (c:Concept {label: "Human Variety"})
             -[:EVIDENCED_BY]->(i:Instance)
             -[:FROM_SOURCE]->(s:Source)
RETURN path
LIMIT 10
```

### Concept neighborhood with evidence

```cypher
MATCH (c:Concept {label: "Human Variety"})
OPTIONAL MATCH evidence = (c)-[:EVIDENCED_BY]->(i:Instance)-[:FROM_SOURCE]->(s:Source)
OPTIONAL MATCH concepts  = (c)-[r]-(c2:Concept)
RETURN c, evidence, concepts
LIMIT 30
```

---

## Cross-document analysis

### Concepts appearing in multiple documents

```cypher
MATCH (c:Concept)-[:APPEARS]->(s:Source)
WITH c, collect(DISTINCT s.document) AS documents
WHERE size(documents) > 1
RETURN c.label, documents, size(documents) AS doc_count
ORDER BY doc_count DESC
```

### Compare coverage across two documents

```cypher
MATCH (c:Concept)-[:APPEARS]->(s:Source)
WHERE s.document IN ["Document A", "Document B"]
WITH c.label AS concept,
     collect(DISTINCT s.document) AS docs
RETURN concept,
       size(docs) AS appears_in,
       CASE WHEN size(docs) = 2 THEN "both" ELSE docs[0] END AS where
ORDER BY appears_in DESC, concept
```

### Unique concepts per document

```cypher
MATCH (c:Concept)-[:APPEARS]->(s:Source)
WITH c, collect(DISTINCT s.document) AS documents
WHERE size(documents) = 1
WITH documents[0] AS document, count(c) AS unique_concepts
RETURN document, unique_concepts
ORDER BY unique_concepts DESC
```

### Concepts bridging two documents

```cypher
MATCH (c:Concept)-[:APPEARS]->(s1:Source {document: "Document A"})
MATCH (c)-[:APPEARS]->(s2:Source {document: "Document B"})
MATCH (c)-[:EVIDENCED_BY]->(i1:Instance)-[:FROM_SOURCE]->(s1)
MATCH (c)-[:EVIDENCED_BY]->(i2:Instance)-[:FROM_SOURCE]->(s2)
RETURN c.label AS bridging_concept, i1.quote AS quote_from_A, i2.quote AS quote_from_B
```

---

## Relationship exploration

### Concept implications network (visual)

```cypher
MATCH path = (c:Concept)-[:IMPLIES]->(related:Concept)
RETURN path
LIMIT 30
```

### Filter by relationship type

```cypher
MATCH path = (c1:Concept)-[r:IMPLIES|SUPPORTS]->(c2:Concept)
RETURN path
LIMIT 50
```

### Contradictions

```cypher
MATCH path = (c1:Concept)-[:CONTRADICTS]->(c2:Concept)
RETURN path
```

### All relationships for a concept

```cypher
MATCH (c:Concept {label: "Human Variety"})
MATCH path = (c)-[r]->(related:Concept)
RETURN path
```

### Neighborhood within N hops

```cypher
MATCH path = (start:Concept {label: "Requisite Variety"})
             -[*1..2]-(related:Concept)
WHERE start <> related
RETURN path
LIMIT 50
```

### Directional traversal

```cypher
MATCH path = (start:Concept {label: "Requisite Variety"})
             -[:IMPLIES|SUPPORTS*1..3]->(related:Concept)
RETURN path
LIMIT 30
```

---

## Path finding

Apache AGE does not support `shortestPath()`. Use bounded variable-length patterns instead.

### All paths up to N hops

```cypher
MATCH (start:Concept), (end:Concept)
WHERE start.label =~ "(?i).*agile.*"
  AND end.label   =~ "(?i).*human.*"
MATCH path = (start)-[*1..4]-(end)
WITH path, length(path) AS pathLength,
     [n IN nodes(path) | n.label] AS nodeLabels
RETURN nodeLabels, pathLength
ORDER BY pathLength ASC
LIMIT 20
```

Keep the upper bound at `4` for interactive queries to avoid exponential enumeration.

### With relationship types displayed

```cypher
MATCH (start:Concept), (end:Concept)
WHERE start.label =~ "(?i).*agile.*"
  AND end.label   =~ "(?i).*human.*"
MATCH path = (start)-[*1..4]-(end)
RETURN [n IN nodes(path) | n.label]         AS concepts,
       [r IN relationships(path) | type(r)] AS relationship_types,
       length(path)                          AS hops
ORDER BY hops ASC
LIMIT 10
```

### Multiple start/end patterns

```cypher
MATCH (start:Concept), (end:Concept)
WHERE start.label =~ "(?i).*(agile|scrum|lean).*"
  AND end.label   =~ "(?i).*(human|person|people).*"
MATCH path = (start)-[*1..4]-(end)
WITH start, end, path, length(path) AS pathLength
RETURN start.label AS fromConcept,
       end.label   AS toConcept,
       [n IN nodes(path) | n.label] AS pathConcepts,
       pathLength
ORDER BY pathLength ASC
LIMIT 15
```

### Weighted path (when relationships carry scores)

```cypher
MATCH (start:Concept), (end:Concept)
WHERE start.label =~ "(?i).*agile.*"
  AND end.label   =~ "(?i).*human.*"
MATCH path = (start)-[rels*1..4]-(end)
WITH path,
     reduce(score = 0, r IN rels | score + coalesce(r.weight, 1)) AS totalScore,
     length(path) AS pathLength
RETURN [n IN nodes(path) | n.label]         AS concepts,
       [r IN relationships(path) | type(r)] AS relTypes,
       totalScore,
       pathLength
ORDER BY totalScore DESC, pathLength ASC
LIMIT 10
```

### Custom domain scoring

```cypher
MATCH (start:Concept), (end:Concept)
WHERE start.label =~ "(?i).*agile.*"
  AND end.label   =~ "(?i).*human.*"
MATCH path = (start)-[*1..4]-(end)
WITH path,
     length(path) AS pathLength,
     size([n IN nodes(path)
           WHERE n.label CONTAINS "team" OR n.label CONTAINS "collaboration"]) AS relevantNodes
WITH path, pathLength, relevantNodes,
     (relevantNodes * 10 - pathLength) AS customScore
RETURN [n IN nodes(path) | n.label] AS concepts,
       pathLength,
       relevantNodes,
       customScore
ORDER BY customScore DESC
LIMIT 10
```

Scoring: +10 per "team" or "collaboration" node in the path; −1 per hop.

### Relationship-type scoring

```cypher
MATCH (start:Concept), (end:Concept)
WHERE start.label =~ "(?i).*agile.*"
  AND end.label   =~ "(?i).*human.*"
MATCH path = (start)-[rels*1..4]-(end)
WITH path,
     length(path)                                          AS pathLength,
     size([r IN rels WHERE type(r) = 'SUPPORTS'])         AS supportsCount,
     size([r IN rels WHERE type(r) = 'IMPLIES'])          AS impliesCount
WITH path, pathLength, supportsCount, impliesCount,
     (supportsCount * 5 + impliesCount * 3 - pathLength)  AS customScore
RETURN [n IN nodes(path) | n.label]         AS concepts,
       [r IN relationships(path) | type(r)] AS relTypes,
       pathLength,
       supportsCount,
       impliesCount,
       customScore
ORDER BY customScore DESC
LIMIT 10
```

Scoring: +5 per SUPPORTS edge, +3 per IMPLIES edge, −1 per hop.

---

## Semantic search

### Find similar concepts by embedding

```cypher
MATCH (c:Concept {label: "Human Variety"})
CALL db.index.vector.queryNodes('concept-embeddings', 5, c.embedding)
YIELD node, score
RETURN node.label, score
```

### Semantic clusters

```cypher
MATCH (c:Concept)
CALL db.index.vector.queryNodes('concept-embeddings', 3, c.embedding)
YIELD node, score
WHERE node <> c AND score >= 0.85
WITH c, collect({concept: node.label, similarity: score}) AS similar_concepts
WHERE size(similar_concepts) > 0
RETURN c.label AS concept, similar_concepts
ORDER BY size(similar_concepts) DESC
LIMIT 10
```

### Full-text search on quotes

```cypher
CALL db.index.fulltext.queryNodes('instance_fulltext', 'AI systems')
YIELD node, score
MATCH (node)-[:FROM_SOURCE]->(s:Source)
RETURN node.quote, s.document, score
LIMIT 10
```

### Full-text search on concepts

```cypher
CALL db.index.fulltext.queryNodes('concept_fulltext', 'variety OR diversity')
YIELD node, score
RETURN node.label, node.search_terms, score
ORDER BY score DESC
LIMIT 10
```

---

## Statistics and metrics

### Node counts by type

```cypher
MATCH (n)
RETURN labels(n)[0] AS type, count(n) AS count
ORDER BY count DESC
```

### All relationship types

```cypher
MATCH (c1:Concept)-[r]->(c2:Concept)
RETURN DISTINCT type(r) AS relationship_type, count(*) AS count
ORDER BY count DESC
```

### Relationship density

```cypher
MATCH (c:Concept)
WITH count(c) AS total_concepts
MATCH (c1:Concept)-[r]->(c2:Concept)
WITH total_concepts, count(r) AS total_relationships
RETURN total_concepts,
       total_relationships,
       toFloat(total_relationships) / (total_concepts * (total_concepts - 1)) AS density
```

### Hub analysis (concept connectivity)

```cypher
MATCH (c:Concept)
OPTIONAL MATCH (c)-[r_out]->(other:Concept)
OPTIONAL MATCH (c)<-[r_in]-(other2:Concept)
WITH c, count(DISTINCT r_out) AS outbound, count(DISTINCT r_in) AS inbound
RETURN c.label,
       outbound,
       inbound,
       outbound + inbound AS total_connections
ORDER BY total_connections DESC
LIMIT 10
```

### Document statistics

```cypher
MATCH (s:Source)
WITH s.document AS doc, count(DISTINCT s) AS chunks
MATCH (c:Concept)-[:APPEARS]->(s2:Source {document: doc})
WITH doc, chunks, count(DISTINCT c) AS concepts
MATCH (i:Instance)-[:FROM_SOURCE]->(s3:Source {document: doc})
RETURN doc, chunks, concepts, count(i) AS instances
ORDER BY concepts DESC
```

### Average evidence per concept

```cypher
MATCH (c:Concept)-[:EVIDENCED_BY]->(i:Instance)
WITH count(i) AS evidence_count
RETURN avg(evidence_count) AS avg_evidence,
       min(evidence_count) AS min_evidence,
       max(evidence_count) AS max_evidence
```

---

## Debugging and validation

### Orphaned concepts (no evidence)

```cypher
MATCH (c:Concept)
WHERE NOT (c)-[:EVIDENCED_BY]->()
RETURN c.concept_id, c.label
```

### Orphaned instances (no source)

```cypher
MATCH (i:Instance)
WHERE NOT (i)-[:FROM_SOURCE]->()
RETURN i.instance_id, i.quote
LIMIT 10
```

### Concepts missing embeddings

```cypher
MATCH (c:Concept)
WHERE c.embedding IS NULL
RETURN count(c) AS concepts_missing_embeddings
```

### Concepts from a specific ontology

```cypher
MATCH (c:Concept)-[:APPEARS]->(s:Source {document: "WattsTest"})
RETURN DISTINCT c.label, c.search_terms
ORDER BY c.label
```

---

## AGE `ORDER BY` workaround

AGE does not sort on path variables directly. Extract the sort key with `WITH` first.

```cypher
-- Fails in AGE:
MATCH path = (start)-[*1..4]-(end)
RETURN path
ORDER BY length(path)

-- Works:
MATCH path = (start)-[*1..4]-(end)
WITH path, length(path) AS len
RETURN path, len
ORDER BY len
```

---

## References

- Apache AGE documentation: <https://age.apache.org/age-manual/master/intro/overview.html>
- openCypher language reference: <https://s3.amazonaws.com/artifacts.opencypher.org/openCypher9.pdf>
- AGE vs Neo4j differences: ADR-208
- Path-finding optimization: ADR-506
- AGE `shortestPath()` issue: <https://github.com/apache/age/issues/2162>
- AGE variable-length path performance: <https://github.com/apache/age/issues/195>
