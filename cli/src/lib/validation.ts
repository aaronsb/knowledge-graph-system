/**
 * Shared validation module for concept/edge CRUD (ADR-089 Phase 2).
 *
 * These validators are used by both interactive wizard and non-interactive
 * flag-based creation. They ensure graph integrity at all control levels
 * (envelope protection).
 */

import { KnowledgeGraphClient } from '../api/client';

/**
 * Validation result structure.
 */
export interface ValidationResult<T = any> {
  valid: boolean;
  error?: string;
  warning?: string;
  data?: T;
}

/**
 * Concept match result from similarity search.
 */
export interface ConceptMatchResult {
  matched: boolean;
  concept_id?: string;
  label?: string;
  similarity?: number;
  created?: boolean;
}

/**
 * Vocabulary term validation result.
 */
export interface VocabTermResult {
  exists: boolean;
  created?: boolean;
  term: string;
  similar_terms?: Array<{ term: string; similarity: number }>;
}

/**
 * Validate that an ontology exists.
 */
export async function validateOntology(
  client: KnowledgeGraphClient,
  ontologyName: string
): Promise<ValidationResult<{ ontology: string }>> {
  try {
    const ontologies = await client.listOntologies();
    const exists = ontologies.ontologies.some(
      (o) => o.ontology.toLowerCase() === ontologyName.toLowerCase()
    );

    if (exists) {
      // Find exact case match
      const match = ontologies.ontologies.find(
        (o) => o.ontology.toLowerCase() === ontologyName.toLowerCase()
      );
      return {
        valid: true,
        data: { ontology: match!.ontology },
      };
    }

    return {
      valid: false,
      error: `Ontology '${ontologyName}' not found. Use 'kg ontology list' to see available ontologies.`,
    };
  } catch (error: any) {
    return {
      valid: false,
      error: `Failed to validate ontology: ${error.message}`,
    };
  }
}

/**
 * Validate that a concept ID exists.
 */
export async function validateConceptId(
  client: KnowledgeGraphClient,
  conceptId: string
): Promise<ValidationResult<{ concept_id: string; label: string }>> {
  try {
    const concept = await client.getConceptById(conceptId);
    return {
      valid: true,
      data: {
        concept_id: concept.concept_id,
        label: concept.label,
      },
    };
  } catch (error: any) {
    if (error.response?.status === 404) {
      return {
        valid: false,
        error: `Concept '${conceptId}' not found.`,
      };
    }
    return {
      valid: false,
      error: `Failed to validate concept: ${error.response?.data?.detail || error.message}`,
    };
  }
}

/**
 * Validate a vocabulary term exists, optionally creating it.
 */
export async function validateVocabTerm(
  client: KnowledgeGraphClient,
  term: string,
  createIfMissing: boolean = false
): Promise<ValidationResult<VocabTermResult>> {
  try {
    // Normalize the term (uppercase, underscores)
    const normalizedTerm = term.toUpperCase().replace(/\s+/g, '_').replace(/[^A-Z0-9_]/g, '');

    if (!normalizedTerm) {
      return {
        valid: false,
        error: 'Vocabulary term cannot be empty after normalization.',
      };
    }

    // Try to get similar terms - if the API succeeds, the term exists
    // (API returns 404 if term not found)
    try {
      const similar = await client.getSimilarTypes(normalizedTerm, 5);

      // API succeeded, term exists
      return {
        valid: true,
        data: {
          exists: true,
          term: similar.relationship_type || normalizedTerm,
          similar_terms: similar.similar_types?.slice(0, 3).map((t: any) => ({
            term: t.relationship_type,
            similarity: t.similarity,
          })),
        },
      };
    } catch (apiError: any) {
      // 404 means term doesn't exist, other errors are actual failures
      if (apiError.response?.status !== 404) {
        throw apiError;
      }
    }

    // Term doesn't exist (got 404)
    if (!createIfMissing) {
      return {
        valid: false,
        error: `Vocabulary term '${normalizedTerm}' not found. Use --create-vocab to create it.`,
        data: {
          exists: false,
          term: normalizedTerm,
          similar_terms: [], // Can't get similar terms for non-existent type
        },
      };
    }

    // Create the new vocab term
    try {
      await client.addEdgeType({
        relationship_type: normalizedTerm,
        category: 'structural', // Default category
        description: `User-created vocabulary term: ${normalizedTerm}`,
        is_builtin: false,
      });

      return {
        valid: true,
        warning: `Created new vocabulary term '${normalizedTerm}'.`,
        data: {
          exists: false,
          created: true,
          term: normalizedTerm,
        },
      };
    } catch (createError: any) {
      return {
        valid: false,
        error: `Failed to create vocabulary term: ${createError.response?.data?.detail || createError.message}`,
      };
    }
  } catch (error: any) {
    return {
      valid: false,
      error: `Failed to validate vocabulary term: ${error.response?.data?.detail || error.message}`,
    };
  }
}

/**
 * Search for vocabulary terms by similarity.
 */
export async function searchVocabTerms(
  client: KnowledgeGraphClient,
  query: string,
  limit: number = 5
): Promise<ValidationResult<Array<{ term: string; similarity: number }>>> {
  try {
    const similar = await client.getSimilarTypes(query, limit);

    if (!similar.similar_types || similar.similar_types.length === 0) {
      return {
        valid: true,
        data: [],
      };
    }

    return {
      valid: true,
      data: similar.similar_types.map((t: any) => ({
        term: t.relationship_type,
        similarity: t.similarity,
      })),
    };
  } catch (error: any) {
    return {
      valid: false,
      error: `Failed to search vocabulary: ${error.response?.data?.detail || error.message}`,
    };
  }
}

/**
 * Search for concepts by label similarity.
 */
export async function searchConceptsByLabel(
  client: KnowledgeGraphClient,
  query: string,
  ontology?: string,
  limit: number = 5
): Promise<ValidationResult<Array<{ concept_id: string; label: string; similarity: number }>>> {
  try {
    const results = await client.searchConcepts({
      query,
      limit,
      min_similarity: 0.5, // Lower threshold for search
      ontology, // Filter by ontology if specified
    });

    return {
      valid: true,
      data: results.results.map((r) => ({
        concept_id: r.concept_id,
        label: r.label,
        similarity: r.score,
      })),
    };
  } catch (error: any) {
    return {
      valid: false,
      error: `Failed to search concepts: ${error.response?.data?.detail || error.message}`,
    };
  }
}

/**
 * Match a concept description against existing concepts.
 * Uses the same similarity matching as automatic ingestion.
 *
 * @param description Description to match
 * @param ontology Target ontology
 * @param matchingMode How to handle matches: auto, force_create, match_only
 */
export async function matchConceptByDescription(
  client: KnowledgeGraphClient,
  description: string,
  ontology: string,
  matchingMode: 'auto' | 'force_create' | 'match_only' = 'auto'
): Promise<ValidationResult<ConceptMatchResult>> {
  if (matchingMode === 'force_create') {
    // Skip matching entirely
    return {
      valid: true,
      data: {
        matched: false,
        created: false,
      },
    };
  }

  try {
    // Search for similar concepts using the description
    const results = await client.searchConcepts({
      query: description,
      limit: 3,
      min_similarity: 0.85, // High threshold for matching
    });

    if (results.results.length > 0) {
      const best = results.results[0];
      return {
        valid: true,
        data: {
          matched: true,
          concept_id: best.concept_id,
          label: best.label,
          similarity: best.score,
        },
      };
    }

    // No match found
    if (matchingMode === 'match_only') {
      return {
        valid: false,
        error: 'No matching concept found and matching_mode is match_only.',
      };
    }

    return {
      valid: true,
      data: {
        matched: false,
      },
    };
  } catch (error: any) {
    return {
      valid: false,
      error: `Failed to match concept: ${error.response?.data?.detail || error.message}`,
    };
  }
}

/**
 * Validate all components of an edge creation request.
 */
export async function validateEdgeCreation(
  client: KnowledgeGraphClient,
  fromConceptId: string,
  toConceptId: string,
  relationshipType: string,
  options: {
    createVocab?: boolean;
  } = {}
): Promise<ValidationResult<{
  from: { concept_id: string; label: string };
  to: { concept_id: string; label: string };
  type: string;
}>> {
  const errors: string[] = [];

  // Validate from concept
  const fromResult = await validateConceptId(client, fromConceptId);
  if (!fromResult.valid) {
    errors.push(`From concept: ${fromResult.error}`);
  }

  // Validate to concept
  const toResult = await validateConceptId(client, toConceptId);
  if (!toResult.valid) {
    errors.push(`To concept: ${toResult.error}`);
  }

  // Validate vocab term
  const vocabResult = await validateVocabTerm(client, relationshipType, options.createVocab);
  if (!vocabResult.valid) {
    errors.push(`Relationship type: ${vocabResult.error}`);
  }

  if (errors.length > 0) {
    return {
      valid: false,
      error: errors.join('\n'),
    };
  }

  return {
    valid: true,
    warning: vocabResult.warning,
    data: {
      from: fromResult.data!,
      to: toResult.data!,
      type: vocabResult.data!.term,
    },
  };
}

/**
 * Resolve a concept by label (semantic lookup).
 * Searches for the best matching concept by label.
 */
export async function resolveConceptByLabel(
  client: KnowledgeGraphClient,
  label: string,
  ontology?: string
): Promise<ValidationResult<{ concept_id: string; label: string; similarity: number }>> {
  try {
    // First try exact label match via list
    const listResult = await client.listConceptsCRUD({
      label_contains: label,
      ontology,
      limit: 10,
    });

    // Check for exact match
    const exactMatch = listResult.concepts.find(
      (c) => c.label.toLowerCase() === label.toLowerCase()
    );

    if (exactMatch) {
      return {
        valid: true,
        data: {
          concept_id: exactMatch.concept_id,
          label: exactMatch.label,
          similarity: 1.0,
        },
      };
    }

    // Fall back to semantic search
    const searchResult = await client.searchConcepts({
      query: label,
      limit: 1,
      min_similarity: 0.7,
    });

    if (searchResult.results.length > 0) {
      const best = searchResult.results[0];
      return {
        valid: true,
        data: {
          concept_id: best.concept_id,
          label: best.label,
          similarity: best.score,
        },
      };
    }

    return {
      valid: false,
      error: `No concept found matching label '${label}'.`,
    };
  } catch (error: any) {
    return {
      valid: false,
      error: `Failed to resolve concept: ${error.response?.data?.detail || error.message}`,
    };
  }
}
