# openCypher Query Examples

Practical openCypher queries for exploring and analyzing the knowledge graph. These queries work with Apache AGE (PostgreSQL graph extension) and other openCypher-compliant graph databases.

## Query Types

Queries are organized into two main categories:

**📊 Data-Driven Results** - Tabular output for analysis, statistics, and reporting
**🕸️ Graph-Driven Results** - Visual network views for exploration and relationships

## Table of Contents

### Data-Driven Results (Tables & Statistics)
- [Node Counts & Lists](#node-counts--lists)
- [Evidence Analysis](#evidence-analysis)
- [Cross-Document Analysis](#cross-document-analysis)
- [Vector & Text Search](#vector--text-search)
- [Metrics & Statistics](#metrics--statistics)
- [Debugging & Validation](#debugging--validation)

### Graph-Driven Results (Network Views)
- [Concept Networks](#concept-networks)
- [Evidence Chains (Visual)](#evidence-chains-visual)
- [Relationship Exploration](#relationship-exploration)
- [Path Finding](#path-finding)
- [Neighborhood Views](#neighborhood-views)

---

# 📊 Data-Driven Results

Queries that return tabular data, counts, and statistics. Best for analysis and reporting.

## Node Counts & Lists

### Count all nodes by type

```cypher
MATCH (n)
RETURN labels(n)[0] AS type, count(n) AS count
ORDER BY count DESC
```

### View sample concepts with labels

```cypher
MATCH (c:Concept)
RETURN c.concept_id, c.label, c.search_terms
LIMIT 10
```

### Find all documents (ontologies) ingested

```cypher
MATCH (s:Source)
RETURN DISTINCT s.document as ontology
ORDER BY ontology
```

### List all concepts from a specific ontology

```cypher
MATCH (c:Concept)-[:APPEARS]->(s:Source {document: "WattsTest"})
RETURN DISTINCT c.label, c.search_terms
ORDER BY c.label
```

### All relationship types in the graph

```cypher
MATCH (c1:Concept)-[r]->(c2:Concept)
RETURN DISTINCT type(r) as relationship_type, count(*) as count
ORDER BY count DESC
```

---

## Evidence Analysis

### Trace concept back to source quotes (tabular)

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

### Find all quotes for a concept

```cypher
MATCH (c:Concept {label: "Requisite Variety"})
      -[:EVIDENCED_BY]->(i:Instance)
RETURN i.quote
```

### Concepts appearing in multiple sources

```cypher
MATCH (c:Concept)-[:APPEARS]->(s:Source)
WITH c, count(DISTINCT s) as source_count
WHERE source_count > 1
RETURN c.label, source_count
ORDER BY source_count DESC
LIMIT 10
```

---

## Cross-Document Analysis

### Concepts appearing in multiple documents

```cypher
MATCH (c:Concept)-[:APPEARS]->(s:Source)
WITH c, collect(DISTINCT s.document) as documents
WHERE size(documents) > 1
RETURN c.label, documents, size(documents) as doc_count
ORDER BY doc_count DESC
```

### Compare concept coverage across two documents

```cypher
MATCH (c:Concept)-[:APPEARS]->(s:Source)
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
MATCH (c:Concept)-[:APPEARS]->(s:Source)
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
MATCH (c:Concept)-[:APPEARS]->(s1)
WITH s1, s2, collect(c) as concepts1
MATCH (c:Concept)-[:APPEARS]->(s2)
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

## Vector & Text Search

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

## Debugging & Validation

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

### Check vector index status

```cypher
SHOW INDEXES
YIELD name, type, entityType, labelsOrTypes, properties, state
WHERE type = "VECTOR"
RETURN name, state, labelsOrTypes, properties
```

### View database schema

```cypher
CALL db.schema.visualization()
```

---

# 🕸️ Graph-Driven Results

Queries that return visual network graphs. Best viewed in PostgreSQL clients with graph visualization support or exported for visualization.

## Concept Networks

### View all concepts and their relationships

```cypher
MATCH (c:Concept)
OPTIONAL MATCH path = (c)-[r]-(c2:Concept)
RETURN c, path
LIMIT 50
```

### Only connected concepts (network view)

```cypher
MATCH path = (c1:Concept)-[r]-(c2:Concept)
RETURN path
LIMIT 50
```

### Concepts from specific ontology with relationships

```cypher
MATCH (c:Concept)-[:APPEARS]->(s:Source {document: "WattsTest"})
WITH DISTINCT c
OPTIONAL MATCH path = (c)-[r]-(c2:Concept)
RETURN c, path
LIMIT 50
```

### Concept network by relationship type

```cypher
MATCH path = (c1:Concept)-[r:IMPLIES|SUPPORTS]->(c2:Concept)
RETURN path
LIMIT 50
```

### High-connectivity concept hubs (visual)

```cypher
MATCH (c:Concept)
WHERE size((c)-[]-()) > 3
MATCH path = (c)-[r]-(other:Concept)
RETURN path
LIMIT 100
```

---

## Evidence Chains (Visual)

### Full evidence chain for a concept

```cypher
MATCH path = (c:Concept {label: "AI Sandwich Systems Model"})
             -[:EVIDENCED_BY]->(i:Instance)
             -[:FROM_SOURCE]->(s:Source)
RETURN path
LIMIT 10
```

### Multi-hop evidence path

```cypher
MATCH path = (c:Concept)-[:APPEARS]->(s:Source)
             <-[:FROM_SOURCE]-(i:Instance)
             <-[:EVIDENCED_BY]-(c)
RETURN path
LIMIT 20
```

### Concepts with their evidence network

```cypher
MATCH (c:Concept {label: "Human Variety"})
OPTIONAL MATCH evidence = (c)-[:EVIDENCED_BY]->(i:Instance)-[:FROM_SOURCE]->(s:Source)
OPTIONAL MATCH concepts = (c)-[r]-(c2:Concept)
RETURN c, evidence, concepts
LIMIT 30
```

---

## Relationship Exploration

### Concept implications network

```cypher
MATCH path = (c:Concept)-[r:IMPLIES]->(related:Concept)
RETURN path
LIMIT 30
```

### Support relationships

```cypher
MATCH path = (c1:Concept)-[:SUPPORTS]->(c2:Concept)
RETURN path
LIMIT 30
```

### Contradictions visualization

```cypher
MATCH path = (c1:Concept)-[:CONTRADICTS]->(c2:Concept)
RETURN path
```

### All relationships for a specific concept

```cypher
MATCH (c:Concept {label: "Human Variety"})
MATCH path = (c)-[r]->(related:Concept)
RETURN path
```

### Multi-relationship network

```cypher
MATCH path = (c:Concept)-[r:IMPLIES|SUPPORTS|CONTRADICTS|PART_OF]-(other:Concept)
RETURN path
LIMIT 50
```

---

## Path Finding

### Shortest path between two concepts

```cypher
MATCH path = shortestPath(
  (c1:Concept {label: "Human Variety"})
  -[*]-(c2:Concept {label: "AI Transformation"})
)
RETURN path
```

### All paths between concepts (up to 4 hops)

```cypher
MATCH path = (c1:Concept {label: "Human Variety"})
             -[*1..4]-(c2:Concept {label: "AI Transformation"})
WHERE c1 <> c2
RETURN path
LIMIT 10
```

### Concepts within N hops (network expansion)

```cypher
MATCH path = (start:Concept {label: "Requisite Variety"})
             -[*1..2]-(related:Concept)
WHERE start <> related
RETURN path
LIMIT 50
```

### Directional path exploration

```cypher
MATCH path = (start:Concept {label: "Requisite Variety"})
             -[:IMPLIES|SUPPORTS*1..3]->(related:Concept)
RETURN path
LIMIT 30
```

---

## Neighborhood Views

### Complete neighborhood around a concept

```cypher
MATCH (c:Concept {label: "AI Sandwich Systems Model"})
OPTIONAL MATCH out = (c)-[r1:IMPLIES|SUPPORTS]->(out_c:Concept)
OPTIONAL MATCH in = (in_c:Concept)-[r2:IMPLIES|SUPPORTS]->(c)
OPTIONAL MATCH evidence = (c)-[:EVIDENCED_BY]->(i:Instance)
RETURN c, out, in, evidence
```

### Two-hop neighborhood

```cypher
MATCH (c:Concept {label: "Human Variety"})
MATCH path = (c)-[*1..2]-(related)
RETURN path
LIMIT 100
```

### Neighborhood with evidence

```cypher
MATCH (c:Concept {label: "Requisite Variety"})
OPTIONAL MATCH concept_path = (c)-[r]-(related:Concept)
OPTIONAL MATCH evidence_path = (c)-[:EVIDENCED_BY]->(i:Instance)-[:FROM_SOURCE]->(s:Source)
RETURN c, concept_path, evidence_path
LIMIT 50
```

### Cross-document bridge concepts

```cypher
MATCH (c:Concept)-[:APPEARS]->(s1:Source),
      (c)-[:APPEARS]->(s2:Source)
WHERE s1.document <> s2.document
MATCH path = (s1)<-[:APPEARS]-(c)-[:APPEARS]->(s2)
RETURN path
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
MATCH (c:Concept)-[:APPEARS]->(s:Source)
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
MATCH (c:Concept)-[:APPEARS]->(s2:Source {document: doc})
WITH doc, chunks, count(DISTINCT c) as concepts
MATCH (i:Instance)-[:FROM_SOURCE]->(s3:Source {document: doc})
RETURN doc,
       chunks,
       concepts,
       count(i) as instances
ORDER BY concepts DESC
```

---

## Advanced Examples

### Find concepts bridging two documents

```cypher
MATCH (c:Concept)-[:APPEARS]->(s1:Source {document: "Document A"})
MATCH (c)-[:APPEARS]->(s2:Source {document: "Document B"})
MATCH (c)-[:EVIDENCED_BY]->(i1:Instance)-[:FROM_SOURCE]->(s1)
MATCH (c)-[:EVIDENCED_BY]->(i2:Instance)-[:FROM_SOURCE]->(s2)
RETURN c.label as bridging_concept,
       i1.quote as quote_from_A,
       i2.quote as quote_from_B
```

### Concept evolution across document chunks

```cypher
MATCH (c:Concept {label: "Human Variety"})-[:APPEARS]->(s:Source)
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

---

## Query Tips

### Choosing Between Data vs Graph Views

**Use Data-Driven queries when:**
- You need counts, statistics, or metrics
- Exporting data to spreadsheets or reports
- Running aggregations or analytics
- Debugging data quality issues
- Searching for specific information

**Use Graph-Driven queries when:**
- Exploring concept relationships visually
- Understanding network structure
- Finding paths between concepts
- Discovering clusters and patterns
- Presenting to stakeholders

### Performance

- Use `LIMIT` on graph queries to avoid overwhelming visualizations (50-100 nodes max)
- Data queries can handle larger limits for reporting
- Create parameters: `:param ontology => "WattsTest"`
- Use `PROFILE` to analyze performance: `PROFILE MATCH ...`

### Graph Visualization Tips

For Apache AGE graph visualization:
1. Use the **kg CLI** for querying and results display
2. Export results to **GraphML** or **JSON** for visualization in tools like Gephi or Cytoscape
3. Use **PostgreSQL clients** (pgAdmin, DBeaver) for tabular query results
4. Graph visualization support is limited compared to Neo4j Browser - consider exporting for complex visualizations

### Formatting Results

```cypher
// Pretty-print for data analysis
MATCH (c:Concept)
RETURN c.label as Concept,
       size(c.search_terms) as SearchTermCount,
       toString(c.concept_id) as ID
LIMIT 5
```

### Using Parameters

```cypher
:param ontology => "WattsTest"
:param concept_label => "Human Variety"

// Then use in queries
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
- `(Concept)-[:APPEARS]->(Source)`
- `(Concept)-[:IMPLIES|SUPPORTS|CONTRADICTS {confidence: float}]->(Concept)`

**Indexes:**
- Vector index: `concept-embeddings` on Concept.embedding
- Full-text: `instance_fulltext` on Instance.quote
- Full-text: `concept_fulltext` on Concept(label, search_terms)

---

## Running Queries

### kg CLI (Recommended)
```bash
# Use the kg CLI for most queries
kg search query "your search term"
kg database stats
```

### PostgreSQL psql (Direct Database Access)
```bash
# Access PostgreSQL container directly
docker exec -it knowledge-graph-postgres psql -U postgres -d knowledge_graph

# Then run AGE queries wrapped in SELECT
SELECT * FROM cypher('knowledge_graph', $$
  MATCH (c:Concept) RETURN c.label
$$) as (label agtype);
```

### Via API (TypeScript Client)
```bash
# API server provides REST endpoints for graph operations
curl http://localhost:8000/queries/stats
```

### Query Format Notes
- Apache AGE requires wrapping openCypher in `SELECT * FROM cypher('graph_name', $$ ... $$)`
- Results are returned as `agtype` which needs type casting for PostgreSQL operations
- Use the kg CLI or API server for simplified query execution

---

## Further Resources

- [Apache AGE Documentation](https://age.apache.org/age-manual/master/intro/overview.html)
- [openCypher Language Reference](https://s3.amazonaws.com/artifacts.opencypher.org/openCypher9.pdf)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [AGE GitHub Repository](https://github.com/apache/age)
