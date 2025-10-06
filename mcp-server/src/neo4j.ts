import neo4j, { Driver, Session } from 'neo4j-driver';

let driver: Driver | null = null;

/**
 * Initialize Neo4j driver connection
 */
export function initializeDriver(): Driver {
  if (driver) {
    return driver;
  }

  const uri = process.env.NEO4J_URI || 'bolt://localhost:7687';
  const username = process.env.NEO4J_USER || 'neo4j';
  const password = process.env.NEO4J_PASSWORD || 'password';

  driver = neo4j.driver(uri, neo4j.auth.basic(username, password));
  return driver;
}

/**
 * Close Neo4j driver connection
 */
export async function closeDriver(): Promise<void> {
  if (driver) {
    await driver.close();
    driver = null;
  }
}

/**
 * Get a Neo4j session
 */
function getSession(): Session {
  if (!driver) {
    throw new Error('Neo4j driver not initialized');
  }
  return driver.session();
}

/**
 * Vector search for concepts using embedding similarity
 * @param embedding - The query embedding vector
 * @param threshold - Similarity threshold (0-1)
 * @param limit - Maximum number of results
 * @returns Array of matching concepts with similarity scores and evidence quotes
 */
export async function vectorSearch(
  embedding: number[],
  threshold: number = 0.7,
  limit: number = 10,
  offset: number = 0
): Promise<any[]> {
  const session = getSession();
  try {
    // Convert to Neo4j integers
    const limitInt = neo4j.int(Math.floor(limit));
    const offsetInt = neo4j.int(Math.floor(offset));
    const fetchLimit = neo4j.int(Math.floor(limit) + Math.floor(offset));

    const result = await session.run(
      `
      CALL db.index.vector.queryNodes('concept-embeddings', $fetchLimit, $embedding)
      YIELD node, score
      WHERE score >= $threshold
      WITH node, score
      OPTIONAL MATCH (node)-[:EVIDENCED_BY]->(i:Instance)-[:FROM_SOURCE]->(s:Source)
      WITH node, score,
           collect({quote: i.quote, source: s.document, paragraph: s.paragraph}) AS evidence
      RETURN node.concept_id AS concept_id,
             node.label AS label,
             node.search_terms AS search_terms,
             score,
             evidence[0..1] AS sample_evidence
      ORDER BY score DESC
      SKIP $offset
      LIMIT $limit
      `,
      { embedding, threshold, fetchLimit, offset: offsetInt, limit: limitInt }
    );

    return result.records.map(record => ({
      concept_id: record.get('concept_id'),
      label: record.get('label'),
      search_terms: record.get('search_terms'),
      similarity: record.get('score'),
      evidence: record.get('sample_evidence')
    }));
  } finally {
    await session.close();
  }
}

/**
 * Get detailed information about a specific concept
 * @param conceptId - The concept ID
 * @returns Concept details including evidence quotes and relationships
 */
export async function getConceptDetails(conceptId: string): Promise<any> {
  const session = getSession();
  try {
    // Get concept details
    const conceptResult = await session.run(
      `
      MATCH (c:Concept {concept_id: $conceptId})
      RETURN c.concept_id AS concept_id,
             c.label AS label,
             c.search_terms AS search_terms
      `,
      { conceptId }
    );

    if (conceptResult.records.length === 0) {
      return null;
    }

    const concept = {
      concept_id: conceptResult.records[0].get('concept_id'),
      label: conceptResult.records[0].get('label'),
      search_terms: conceptResult.records[0].get('search_terms')
    };

    // Get evidence instances with source information
    const evidenceResult = await session.run(
      `
      MATCH (c:Concept {concept_id: $conceptId})-[:EVIDENCED_BY]->(i:Instance)-[:FROM_SOURCE]->(s:Source)
      RETURN i.instance_id AS instance_id,
             i.quote AS quote,
             s.document AS source_document,
             s.paragraph AS paragraph,
             s.full_text AS full_context
      ORDER BY s.paragraph
      `,
      { conceptId }
    );

    const evidence = evidenceResult.records.map(record => ({
      instance_id: record.get('instance_id'),
      quote: record.get('quote'),
      source: {
        document: record.get('source_document'),
        paragraph: record.get('paragraph'),
        full_context: record.get('full_context')
      }
    }));

    // Get source appearances
    const sourcesResult = await session.run(
      `
      MATCH (c:Concept {concept_id: $conceptId})-[:APPEARS_IN]->(s:Source)
      RETURN DISTINCT s.document AS document,
             count(*) AS occurrences
      ORDER BY occurrences DESC
      `,
      { conceptId }
    );

    const sources = sourcesResult.records.map(record => ({
      document: record.get('document'),
      occurrences: record.get('occurrences').toNumber()
    }));

    // Get relationships to other concepts
    const relationshipsResult = await session.run(
      `
      MATCH (c:Concept {concept_id: $conceptId})-[r]->(related:Concept)
      RETURN type(r) AS relationship_type,
             related.concept_id AS related_concept_id,
             related.label AS related_label,
             r.confidence AS confidence
      ORDER BY r.confidence DESC
      `,
      { conceptId }
    );

    const relationships = relationshipsResult.records.map(record => ({
      type: record.get('relationship_type'),
      related_concept: {
        concept_id: record.get('related_concept_id'),
        label: record.get('related_label')
      },
      confidence: record.get('confidence')
    }));

    return {
      concept,
      evidence,
      sources,
      relationships
    };
  } finally {
    await session.close();
  }
}

/**
 * Find concepts related to a given concept through graph traversal
 * @param conceptId - The starting concept ID
 * @param relationshipTypes - Optional array of relationship types to filter (IMPLIES, SUPPORTS, CONTRADICTS)
 * @param maxDepth - Maximum traversal depth (default: 2)
 * @returns Array of related concepts with path information and sample evidence
 */
export async function findRelatedConcepts(
  conceptId: string,
  relationshipTypes?: string[],
  maxDepth: number = 2
): Promise<any[]> {
  const session = getSession();
  try {
    // Build relationship type filter
    const relTypeFilter = relationshipTypes && relationshipTypes.length > 0
      ? `:${relationshipTypes.join('|')}`
      : '';

    // Build query dynamically since Cypher doesn't allow parameters in relationship ranges
    const query = `
      MATCH path = (start:Concept {concept_id: $conceptId})-[${relTypeFilter}*1..${maxDepth}]->(related:Concept)
      WITH related, path, relationships(path) AS rels
      OPTIONAL MATCH (related)-[:EVIDENCED_BY]->(i:Instance)
      WITH related, path, rels, collect(i.quote)[0..2] AS sample_quotes
      RETURN DISTINCT related.concept_id AS concept_id,
             related.label AS label,
             related.search_terms AS search_terms,
             length(path) AS distance,
             [r IN rels | type(r)] AS relationship_path,
             [r IN rels | r.confidence] AS confidence_path,
             sample_quotes
      ORDER BY distance, related.label
    `;

    const result = await session.run(query, { conceptId });

    return result.records.map(record => ({
      concept_id: record.get('concept_id'),
      label: record.get('label'),
      search_terms: record.get('search_terms'),
      distance: record.get('distance').toNumber(),
      relationship_path: record.get('relationship_path'),
      confidence_path: record.get('confidence_path'),
      sample_evidence: record.get('sample_quotes')
    }));
  } finally {
    await session.close();
  }
}

/**
 * List all ontologies in the database with concept counts
 * @returns Array of ontology objects with names and statistics
 */
export async function listOntologies(): Promise<any[]> {
  const session = getSession();
  try {
    const result = await session.run(
      `
      MATCH (s:Source)
      WITH DISTINCT s.document AS ontology
      OPTIONAL MATCH (c:Concept)-[:APPEARS_IN]->(src:Source {document: ontology})
      RETURN ontology,
             count(DISTINCT c) AS concept_count,
             count(DISTINCT src) AS source_count
      ORDER BY ontology
      `
    );

    return result.records.map(record => ({
      name: record.get('ontology'),
      concepts: record.get('concept_count').toNumber(),
      sources: record.get('source_count').toNumber()
    }));
  } finally {
    await session.close();
  }
}

/**
 * Get detailed statistics for a specific ontology
 * @param ontologyName - The name of the ontology
 * @returns Ontology statistics object
 */
export async function getOntologyInfo(ontologyName: string): Promise<any> {
  const session = getSession();
  try {
    // Get basic stats
    const statsResult = await session.run(
      `
      MATCH (s:Source {document: $ontologyName})
      WITH s
      OPTIONAL MATCH (c:Concept)-[:APPEARS_IN]->(s)
      OPTIONAL MATCH (c)-[:EVIDENCED_BY]->(i:Instance)
      OPTIONAL MATCH (c)-[r:IMPLIES|SUPPORTS|CONTRADICTS|PART_OF]->(other:Concept)
      RETURN count(DISTINCT s) AS sources,
             count(DISTINCT c) AS concepts,
             count(DISTINCT i) AS instances,
             count(DISTINCT r) AS relationships,
             collect(DISTINCT s.file_path) AS files
      `,
      { ontologyName }
    );

    if (statsResult.records.length === 0) {
      return null;
    }

    const stats = statsResult.records[0];

    // Get relationship breakdown
    const relResult = await session.run(
      `
      MATCH (s:Source {document: $ontologyName})<-[:APPEARS_IN]-(c:Concept)
      OPTIONAL MATCH (c)-[r]->(other:Concept)
      WHERE type(r) IN ['IMPLIES', 'SUPPORTS', 'CONTRADICTS', 'PART_OF']
      RETURN type(r) AS rel_type, count(r) AS count
      ORDER BY count DESC
      `,
      { ontologyName }
    );

    const relationships: any = {};
    relResult.records.forEach(record => {
      const relType = record.get('rel_type');
      if (relType) {
        relationships[relType] = record.get('count').toNumber();
      }
    });

    return {
      name: ontologyName,
      sources: stats.get('sources').toNumber(),
      concepts: stats.get('concepts').toNumber(),
      instances: stats.get('instances').toNumber(),
      total_relationships: stats.get('relationships').toNumber(),
      relationships,
      files: stats.get('files')
    };
  } finally {
    await session.close();
  }
}

/**
 * Find shortest path between two concepts
 * @param fromId - Starting concept ID
 * @param toId - Target concept ID
 * @param maxHops - Maximum path length (default: 100)
 * @returns Array of paths with nodes and relationships
 */
export async function findShortestPath(
  fromId: string,
  toId: string,
  maxHops: number = 100
): Promise<any[]> {
  const session = getSession();
  try {
    // Ensure integer value for Neo4j
    const maxHopsInt = Math.floor(maxHops);

    // Build query dynamically since Cypher doesn't allow parameters in relationship ranges
    const query = `
      MATCH path = shortestPath(
        (from:Concept {concept_id: $fromId})-[*..${maxHopsInt}]-(to:Concept {concept_id: $toId})
      )
      WITH path, [rel in relationships(path) | type(rel)] as rel_types
      RETURN
        [node in nodes(path) | {id: node.concept_id, label: node.label}] as path_nodes,
        rel_types,
        length(path) as hops
      LIMIT 10
    `;

    const result = await session.run(query, { fromId, toId });

    return result.records.map(record => ({
      nodes: record.get('path_nodes'),
      relationships: record.get('rel_types'),
      hops: record.get('hops').toNumber()
    }));
  } finally {
    await session.close();
  }
}

/**
 * Get overall database statistics
 * @returns Database statistics object
 */
export async function getDatabaseStats(): Promise<any> {
  const session = getSession();
  try {
    // Get node counts
    const nodeResult = await session.run(
      `
      MATCH (c:Concept)
      WITH count(c) AS concepts
      MATCH (s:Source)
      WITH concepts, count(s) AS sources
      MATCH (i:Instance)
      RETURN concepts, sources, count(i) AS instances
      `
    );

    const nodes = nodeResult.records[0];

    // Get relationship counts
    const relResult = await session.run(
      `
      MATCH ()-[r]->()
      RETURN count(r) AS total
      `
    );

    const totalRels = relResult.records[0].get('total').toNumber();

    // Get concept relationship breakdown
    const conceptRelResult = await session.run(
      `
      MATCH (c:Concept)-[r]->(other:Concept)
      WHERE type(r) IN ['IMPLIES', 'SUPPORTS', 'CONTRADICTS', 'PART_OF']
      RETURN type(r) AS rel_type, count(r) AS count
      ORDER BY count DESC
      `
    );

    const conceptRelationships: any = {};
    conceptRelResult.records.forEach(record => {
      const relType = record.get('rel_type');
      conceptRelationships[relType] = record.get('count').toNumber();
    });

    // Get ontology count
    const ontologyResult = await session.run(
      `
      MATCH (s:Source)
      RETURN count(DISTINCT s.document) AS ontologies
      `
    );

    return {
      nodes: {
        concepts: nodes.get('concepts').toNumber(),
        sources: nodes.get('sources').toNumber(),
        instances: nodes.get('instances').toNumber()
      },
      relationships: {
        total: totalRels,
        concept_relationships: conceptRelationships
      },
      ontologies: ontologyResult.records[0].get('ontologies').toNumber()
    };
  } finally {
    await session.close();
  }
}
