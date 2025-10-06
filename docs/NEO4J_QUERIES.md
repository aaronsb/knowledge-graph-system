# Neo4j Query Examples

Practical Cypher queries for exploring and analyzing the knowledge graph.

## Table of Contents

- [Basic Exploration](#basic-exploration)
- [Evidence Chains](#evidence-chains)
- [Concept Relationships](#concept-relationships)
- [Cross-Document Analysis](#cross-document-analysis)
- [Vector Search](#vector-search)
- [Graph Traversal](#graph-traversal)
- [Metrics & Statistics](#metrics--statistics)
- [Debugging](#debugging)

---

## Basic Exploration

### Count nodes by type

```cypher
MATCH (n:Concept) RETURN count(n) as concepts
UNION
MATCH (n:Instance) RETURN count(n) as instances
UNION
MATCH (n:Source) RETURN count(n) as sources
```

### View random concepts with their labels

```cypher
MATCH (c:Concept)
RETURN c.concept_id, c.label, c.search_terms
LIMIT 10
```

### Find all documents ingested

```cypher
MATCH (s:Source)
RETURN DISTINCT s.document
ORDER BY s.document
```

### List all concepts from a specific document

```cypher
MATCH (c:Concept)-[:APPEARS_IN]->(s:Source {document: "Variety as a fulcrum"})
RETURN DISTINCT c.label, c.search_terms
ORDER BY c.label
```

---

## Evidence Chains

### Trace concept back to source quotes

```cypher
MATCH (c:Concept {label: "Human Variety"})
      -[:EVIDENCED_BY]->(i:Instance)
      -[:FROM_SOURCE]->(s:Source)
RETURN c.label,
       i.quote,
       s.document,
       s.paragraph
LIMIT 5
```

### Concepts with most evidence

```cypher
MATCH (c:Concept)-[:EVIDENCED_BY]->(i:Instance)
WITH c, count(i) as evidence_count
RETURN c.label, evidence_count
ORDER BY evidence_count DESC
LIMIT 10
```

### Full provenance path

```cypher
MATCH path = (c:Concept {label: "AI Sandwich Systems Model"})
             -[:EVIDENCED_BY]->(i:Instance)
             -[:FROM_SOURCE]->(s:Source)
RETURN path
LIMIT 3
```

### Find all quotes for a concept

```cypher
MATCH (c:Concept {label: "Requisite Variety"})
      -[:EVIDENCED_BY]->(i:Instance)
RETURN i.quote
```

---

## Concept Relationships

### Find what a concept implies

```cypher
MATCH (c:Concept {label: "Requisite Variety"})
      -[r:IMPLIES]->(related:Concept)
RETURN c.label as from_concept,
       related.label as implies,
       r.confidence
```

### Find all relationship types in graph

```cypher
MATCH (c1:Concept)-[r]->(c2:Concept)
RETURN DISTINCT type(r) as relationship_type, count(*) as count
ORDER BY count DESC
```

### Concepts that support each other

```cypher
MATCH (c1:Concept)-[:SUPPORTS]->(c2:Concept)
RETURN c1.label, c2.label
LIMIT 10
```

### Contradictions in the graph

```cypher
MATCH (c1:Concept)-[:CONTRADICTS]->(c2:Concept)
RETURN c1.label as concept,
       c2.label as contradicts
```

### All relationships for a specific concept

```cypher
MATCH (c:Concept {label: "Human Variety"})-[r]->(related:Concept)
RETURN type(r) as relationship,
       related.label as related_concept,
       r.confidence as confidence
ORDER BY r.confidence DESC
```

---

## Cross-Document Analysis

### Concepts appearing in multiple documents

```cypher
MATCH (c:Concept)-[:APPEARS_IN]->(s:Source)
WITH c, collect(DISTINCT s.document) as documents
WHERE size(documents) > 1
RETURN c.label, documents, size(documents) as doc_count
ORDER BY doc_count DESC
```

### Compare concept coverage across two documents

```cypher
MATCH (c:Concept)-[:APPEARS_IN]->(s:Source)
WHERE s.document IN ["Variety as a fulcrum", "Alan Watts Lecture"]
WITH c.label as concept,
     collect(DISTINCT s.document) as docs
RETURN concept,
       size(docs) as appears_in,
       CASE WHEN size(docs) = 2 THEN "both" ELSE docs[0] END as where
ORDER BY appears_in DESC, concept
```

### Unique concepts per document

```cypher
MATCH (c:Concept)-[:APPEARS_IN]->(s:Source)
WITH c, collect(DISTINCT s.document) as documents
WHERE size(documents) = 1
WITH documents[0] as document, count(c) as unique_concepts
RETURN document, unique_concepts
ORDER BY unique_concepts DESC
```

### Concept overlap between documents (matrix)

```cypher
MATCH (s1:Source), (s2:Source)
WHERE s1.document < s2.document
MATCH (c:Concept)-[:APPEARS_IN]->(s1)
WITH s1, s2, collect(c) as concepts1
MATCH (c:Concept)-[:APPEARS_IN]->(s2)
WITH s1.document as doc1,
     s2.document as doc2,
     concepts1,
     collect(c) as concepts2
WITH doc1, doc2,
     [c IN concepts1 WHERE c IN concepts2] as overlap
RETURN doc1, doc2, size(overlap) as shared_concepts
ORDER BY shared_concepts DESC
```

---

## Vector Search

### Find similar concepts by embedding

```cypher
MATCH (c:Concept {label: "Human Variety"})
CALL db.index.vector.queryNodes('concept-embeddings', 5, c.embedding)
YIELD node, score
RETURN node.label, score
```

### Vector search with custom embedding

```cypher
// Note: Replace [...] with actual 1536-dimensional embedding vector
CALL db.index.vector.queryNodes('concept-embeddings', 10, [...])
YIELD node, score
WHERE score >= 0.8
RETURN node.label, node.search_terms, score
ORDER BY score DESC
```

### Full-text search on instance quotes

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

### Hybrid search: vector + full-text

```cypher
// Full-text search
CALL db.index.fulltext.queryNodes('concept_fulltext', 'human capability')
YIELD node as ft_node, score as ft_score
WITH collect({node: ft_node, score: ft_score}) as fulltext_results

// Vector search (using embedding from a seed concept)
MATCH (seed:Concept {label: "Human Variety"})
CALL db.index.vector.queryNodes('concept-embeddings', 10, seed.embedding)
YIELD node as vec_node, score as vec_score
WITH fulltext_results, collect({node: vec_node, score: vec_score}) as vector_results

// Combine and deduplicate
UNWIND fulltext_results + vector_results as result
RETURN DISTINCT result.node.label,
       max(result.score) as best_score
ORDER BY best_score DESC
LIMIT 10
```

---

## Graph Traversal

### Find concepts within 2 hops of a starting concept

```cypher
MATCH path = (start:Concept {label: "Requisite Variety"})
             -[*1..2]-(related:Concept)
WHERE start <> related
RETURN DISTINCT related.label,
       length(path) as hops
ORDER BY hops, related.label
```

### Shortest path between two concepts

```cypher
MATCH path = shortestPath(
  (c1:Concept {label: "Human Variety"})
  -[*]-(c2:Concept {label: "AI Transformation"})
)
RETURN path
```

### All paths between two concepts (up to 4 hops)

```cypher
MATCH path = (c1:Concept {label: "Human Variety"})
             -[*1..4]-(c2:Concept {label: "AI Transformation"})
WHERE c1 <> c2
RETURN path
LIMIT 5
```

### Neighborhood around a concept

```cypher
MATCH (c:Concept {label: "AI Sandwich Systems Model"})
OPTIONAL MATCH (c)-[r1:IMPLIES|SUPPORTS]->(out:Concept)
OPTIONAL MATCH (in:Concept)-[r2:IMPLIES|SUPPORTS]->(c)
OPTIONAL MATCH (c)-[:EVIDENCED_BY]->(i:Instance)
RETURN c, out, in, i, r1, r2
```

### Explore concept network (outbound relationships)

```cypher
MATCH (start:Concept {label: "Requisite Variety"})
      -[r:IMPLIES|SUPPORTS|CONTRADICTS*1..3]->(related:Concept)
WITH DISTINCT related, min(length(r)) as distance
RETURN related.label, distance
ORDER BY distance, related.label
LIMIT 20
```

---

## Metrics & Statistics

### Average evidence per concept

```cypher
MATCH (c:Concept)-[:EVIDENCED_BY]->(i:Instance)
WITH count(i) as evidence_count
RETURN avg(evidence_count) as avg_evidence,
       min(evidence_count) as min_evidence,
       max(evidence_count) as max_evidence
```

### Relationship density

```cypher
MATCH (c:Concept)
WITH count(c) as total_concepts
MATCH (c1:Concept)-[r]->(c2:Concept)
WITH total_concepts, count(r) as total_relationships
RETURN total_concepts,
       total_relationships,
       toFloat(total_relationships) / (total_concepts * (total_concepts - 1)) as density
```

### Sources per concept (chunking effectiveness)

```cypher
MATCH (c:Concept)-[:APPEARS_IN]->(s:Source)
WITH c, count(DISTINCT s) as source_count
RETURN source_count as chunks_per_concept,
       count(*) as num_concepts
ORDER BY chunks_per_concept DESC
```

### Distribution of relationship types

```cypher
MATCH (c1:Concept)-[r]->(c2:Concept)
WITH type(r) as rel_type, count(*) as count
RETURN rel_type, count
ORDER BY count DESC
```

### Concept connectivity (hub analysis)

```cypher
MATCH (c:Concept)
OPTIONAL MATCH (c)-[r_out]->(other:Concept)
OPTIONAL MATCH (c)<-[r_in]-(other2:Concept)
WITH c, count(DISTINCT r_out) as outbound, count(DISTINCT r_in) as inbound
RETURN c.label,
       outbound,
       inbound,
       outbound + inbound as total_connections
ORDER BY total_connections DESC
LIMIT 10
```

### Document statistics

```cypher
MATCH (s:Source)
WITH s.document as doc, count(DISTINCT s) as chunks
MATCH (c:Concept)-[:APPEARS_IN]->(s2:Source {document: doc})
WITH doc, chunks, count(DISTINCT c) as concepts
MATCH (i:Instance)-[:FROM_SOURCE]->(s3:Source {document: doc})
RETURN doc,
       chunks,
       concepts,
       count(i) as instances
ORDER BY concepts DESC
```

---

## Debugging

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
RETURN count(c) as concepts_missing_embeddings
```

### Instances missing quotes

```cypher
MATCH (i:Instance)
WHERE i.quote IS NULL OR i.quote = ""
RETURN count(i) as instances_missing_quotes
```

### Broken relationship references

```cypher
// Find relationships referencing non-existent concept IDs
MATCH (c:Concept)-[r]->(target)
WHERE NOT exists((target:Concept))
RETURN c.concept_id, c.label, type(r), target
LIMIT 10
```

### View database schema

```cypher
CALL db.schema.visualization()
```

### View indexes

```cypher
SHOW INDEXES
```

### Check vector index status

```cypher
SHOW INDEXES
YIELD name, type, entityType, labelsOrTypes, properties, state
WHERE type = "VECTOR"
RETURN name, state, labelsOrTypes, properties
```

### Sample of each node type

```cypher
MATCH (c:Concept)
WITH c LIMIT 1
MATCH (i:Instance)
WITH c, i LIMIT 1
MATCH (s:Source)
WITH c, i, s LIMIT 1
RETURN c as sample_concept,
       i as sample_instance,
       s as sample_source
```

---

## Advanced Examples

### Find concepts bridging two documents

```cypher
MATCH (c:Concept)-[:APPEARS_IN]->(s1:Source {document: "Document A"})
MATCH (c)-[:APPEARS_IN]->(s2:Source {document: "Document B"})
MATCH (c)-[:EVIDENCED_BY]->(i1:Instance)-[:FROM_SOURCE]->(s1)
MATCH (c)-[:EVIDENCED_BY]->(i2:Instance)-[:FROM_SOURCE]->(s2)
RETURN c.label as bridging_concept,
       i1.quote as quote_from_A,
       i2.quote as quote_from_B
```

### Concept evolution across document chunks

```cypher
MATCH (c:Concept {label: "Human Variety"})-[:APPEARS_IN]->(s:Source)
MATCH (c)-[:EVIDENCED_BY]->(i:Instance)-[:FROM_SOURCE]->(s)
RETURN c.label,
       s.document,
       s.paragraph,
       i.quote
ORDER BY s.paragraph
```

### Find central concepts (high betweenness centrality approximation)

```cypher
MATCH (c:Concept)
MATCH path = (c1:Concept)-[*]-(c)-[*]-(c2:Concept)
WHERE c1 <> c2 AND c <> c1 AND c <> c2
WITH c, count(DISTINCT path) as paths_through
RETURN c.label, paths_through
ORDER BY paths_through DESC
LIMIT 10
```

### Semantic clusters (concepts with similar embeddings)

```cypher
MATCH (c:Concept)
CALL db.index.vector.queryNodes('concept-embeddings', 3, c.embedding)
YIELD node, score
WHERE node <> c AND score >= 0.85
WITH c, collect({concept: node.label, similarity: score}) as similar_concepts
WHERE size(similar_concepts) > 0
RETURN c.label as concept, similar_concepts
ORDER BY size(similar_concepts) DESC
LIMIT 10
```

---

## Query Tips

### Performance

- Use `LIMIT` on exploratory queries to avoid overwhelming results
- Create parameters for frequently used values: `:param document => "Variety as a fulcrum"`
- Use `PROFILE` or `EXPLAIN` to analyze query performance: `PROFILE MATCH ...`

### Formatting Results

```cypher
// Pretty-print multiple properties
MATCH (c:Concept)
RETURN c.label as Concept,
       size(c.search_terms) as SearchTermCount,
       toString(c.concept_id) as ID
LIMIT 5
```

### Exporting Results

```cypher
// From Neo4j Browser, use Download button or:
// apoc.export.json.query() if APOC plugin installed
```

### Using Parameters in Neo4j Browser

```cypher
:param concept_label => "Human Variety"

MATCH (c:Concept {label: $concept_label})
RETURN c
```

---

## Schema Reference

**Nodes:**
- `Concept`: concept_id, label, embedding (1536-dim vector), search_terms (array)
- `Instance`: instance_id, quote
- `Source`: source_id, document, paragraph, full_text

**Relationships:**
- `(Concept)-[:EVIDENCED_BY]->(Instance)`
- `(Instance)-[:FROM_SOURCE]->(Source)`
- `(Concept)-[:APPEARS_IN]->(Source)`
- `(Concept)-[:IMPLIES|SUPPORTS|CONTRADICTS {confidence: float}]->(Concept)`

**Indexes:**
- Vector index: `concept-embeddings` on Concept.embedding
- Full-text: `instance_fulltext` on Instance.quote
- Full-text: `concept_fulltext` on Concept(label, search_terms)

---

## Running Queries

### Neo4j Browser
1. Open: http://localhost:7474
2. Login: neo4j / password
3. Paste query into editor
4. Click Run or press Ctrl+Enter

### Python CLI
```bash
python cli.py query "MATCH (c:Concept) RETURN count(c)"
```

### Cypher Shell
```bash
docker exec -it knowledge-graph-neo4j cypher-shell -u neo4j -p password
```

---

## Further Resources

- [Neo4j Cypher Manual](https://neo4j.com/docs/cypher-manual/)
- [Graph Data Science Library](https://neo4j.com/docs/graph-data-science/)
- [APOC Procedures](https://neo4j.com/docs/apoc/)
