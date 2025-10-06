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
  limit: number = 10
): Promise<any[]> {
  const session = getSession();
  try {
    const result = await session.run(
      `
      CALL db.index.vector.queryNodes('concept-embeddings', $limit, $embedding)
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
             evidence[0..3] AS sample_evidence
      ORDER BY score DESC
      `,
      { embedding, threshold, limit }
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

    const result = await session.run(
      `
      MATCH path = (start:Concept {concept_id: $conceptId})-[${relTypeFilter}*1..$maxDepth]->(related:Concept)
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
      `,
      { conceptId, maxDepth }
    );

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
