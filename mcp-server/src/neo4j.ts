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
  const username = process.env.NEO4J_USERNAME || 'neo4j';
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
 * @returns Array of matching concepts with similarity scores
 */
export async function vectorSearch(
  embedding: number[],
  threshold: number = 0.7,
  limit: number = 10
): Promise<any[]> {
  const session = getSession();
  try {
    const result = await session.run(
      `
      CALL db.index.vector.queryNodes('concept_embeddings', $limit, $embedding)
      YIELD node, score
      WHERE score >= $threshold
      RETURN node.id AS id,
             node.name AS name,
             node.description AS description,
             node.type AS type,
             score
      ORDER BY score DESC
      `,
      { embedding, threshold, limit }
    );

    return result.records.map(record => ({
      id: record.get('id'),
      name: record.get('name'),
      description: record.get('description'),
      type: record.get('type'),
      similarity: record.get('score')
    }));
  } finally {
    await session.close();
  }
}

/**
 * Get detailed information about a specific concept
 * @param conceptId - The concept ID
 * @returns Concept details including instances and relationships
 */
export async function getConceptDetails(conceptId: string): Promise<any> {
  const session = getSession();
  try {
    // Get concept details
    const conceptResult = await session.run(
      `
      MATCH (c:Concept {id: $conceptId})
      RETURN c.id AS id,
             c.name AS name,
             c.description AS description,
             c.type AS type,
             c.metadata AS metadata
      `,
      { conceptId }
    );

    if (conceptResult.records.length === 0) {
      return null;
    }

    const concept = {
      id: conceptResult.records[0].get('id'),
      name: conceptResult.records[0].get('name'),
      description: conceptResult.records[0].get('description'),
      type: conceptResult.records[0].get('type'),
      metadata: conceptResult.records[0].get('metadata')
    };

    // Get instances
    const instancesResult = await session.run(
      `
      MATCH (c:Concept {id: $conceptId})-[:HAS_INSTANCE]->(i:Instance)
      RETURN i.id AS id,
             i.content AS content,
             i.source AS source,
             i.timestamp AS timestamp,
             i.metadata AS metadata
      ORDER BY i.timestamp DESC
      `,
      { conceptId }
    );

    const instances = instancesResult.records.map(record => ({
      id: record.get('id'),
      content: record.get('content'),
      source: record.get('source'),
      timestamp: record.get('timestamp'),
      metadata: record.get('metadata')
    }));

    // Get relationships
    const relationshipsResult = await session.run(
      `
      MATCH (c:Concept {id: $conceptId})-[r]->(related:Concept)
      RETURN type(r) AS relationshipType,
             related.id AS relatedId,
             related.name AS relatedName,
             related.type AS relatedType,
             r.strength AS strength,
             r.metadata AS metadata
      `,
      { conceptId }
    );

    const relationships = relationshipsResult.records.map(record => ({
      type: record.get('relationshipType'),
      relatedConcept: {
        id: record.get('relatedId'),
        name: record.get('relatedName'),
        type: record.get('relatedType')
      },
      strength: record.get('strength'),
      metadata: record.get('metadata')
    }));

    return {
      concept,
      instances,
      relationships
    };
  } finally {
    await session.close();
  }
}

/**
 * Find concepts related to a given concept through graph traversal
 * @param conceptId - The starting concept ID
 * @param relationshipTypes - Optional array of relationship types to filter
 * @param maxDepth - Maximum traversal depth (default: 2)
 * @returns Array of related concepts with path information
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

    const result = await session.run(
      `
      MATCH path = (start:Concept {id: $conceptId})-[${relTypeFilter}*1..$maxDepth]->(related:Concept)
      WITH related, path, relationships(path) AS rels
      RETURN DISTINCT related.id AS id,
             related.name AS name,
             related.description AS description,
             related.type AS type,
             length(path) AS distance,
             [r IN rels | type(r)] AS relationshipPath,
             [r IN rels | r.strength] AS strengthPath
      ORDER BY distance, related.name
      `,
      { conceptId, maxDepth }
    );

    return result.records.map(record => ({
      id: record.get('id'),
      name: record.get('name'),
      description: record.get('description'),
      type: record.get('type'),
      distance: record.get('distance').toNumber(),
      relationshipPath: record.get('relationshipPath'),
      strengthPath: record.get('strengthPath')
    }));
  } finally {
    await session.close();
  }
}
