/**
 * Concept and search result formatters
 */

import type {
  SearchResponse,
  ConceptDetailsResponse,
  FindConnectionBySearchResponse,
  RelatedConceptsResponse,
} from '../../types/index.js';
import { formatGroundingStrength, formatGroundingWithConfidence } from './utils.js';

/**
 * Format search results as markdown
 */
export function formatSearchResults(result: SearchResponse): string {
  let output = `# Search: "${result.query}"\n\n`;
  output += `Found ${result.count} concepts (threshold: ${(result.threshold_used || 0.7) * 100}%)\n\n`;

  if (result.count === 0) {
    output += 'No concepts found matching this query.\n';
    return output;
  }

  result.results.forEach((concept, i) => {
    output += `## ${i + 1}. ${concept.label}\n`;
    if (concept.description) {
      output += `${concept.description}\n\n`;
    }
    output += `ID: ${concept.concept_id}\n`;
    output += `Similarity: ${(concept.score * 100).toFixed(1)}%\n`;
    output += `Documents: ${concept.documents.join(', ')}\n`;
    output += `Evidence: ${concept.evidence_count} instances\n`;

    if (concept.grounding_strength !== undefined || concept.grounding_display) {
      output += `Grounding: ${formatGroundingWithConfidence(concept.grounding_strength, concept.grounding_display, concept.confidence_score)}\n`;
    }

    if (concept.diversity_score !== undefined && concept.diversity_score !== null && concept.diversity_related_count !== undefined) {
      output += `Diversity: ${(concept.diversity_score * 100).toFixed(1)}% (${concept.diversity_related_count} related concepts)\n`;
    }

    if (concept.authenticated_diversity !== undefined && concept.authenticated_diversity !== null) {
      const authDiv = concept.authenticated_diversity;
      const sign = authDiv >= 0 ? '+' : '';
      // Near-zero values (|authDiv| < 0.05) are "unclear" - grounding too weak to authenticate
      const status = Math.abs(authDiv) < 0.05 ? 'unclear ◯' :
                     authDiv > 0.3 ? 'diverse support ✅' :
                     authDiv > 0 ? 'some support ✓' :
                     authDiv > -0.3 ? 'weak contradiction ⚠' :
                     'diverse contradiction ❌';
      output += `Authenticated: ${sign}${(Math.abs(authDiv) * 100).toFixed(1)}% (${status})\n`;
    }

    if (concept.sample_evidence && concept.sample_evidence.length > 0) {
      output += `\nSample Evidence (${concept.sample_evidence.length} of ${concept.evidence_count}):\n`;
      concept.sample_evidence.forEach((inst, idx) => {
        const truncated = inst.quote.length > 120 ? inst.quote.substring(0, 120) + '...' : inst.quote;
        output += `${idx + 1}. ${inst.document} (para ${inst.paragraph}): "${truncated}"\n`;
        // ADR-057: Indicate if this evidence has an image
        if (inst.has_image && inst.source_id) {
          output += `   [IMAGE] Use get_source_image("${inst.source_id}") to view original image\n`;
        }
      });
      output += `Tip: Use get_concept_details("${concept.concept_id}") for all evidence\n`;
    }

    output += '\n';
  });

  if (result.below_threshold_count && result.below_threshold_count > 0 && result.suggested_threshold) {
    const thresholdPercent = (result.suggested_threshold * 100).toFixed(0);
    output += `Note: ${result.below_threshold_count} additional concepts available at ${thresholdPercent}% threshold\n`;
  }

  return output;
}

/**
 * Format concept details as markdown
 * @param concept - The concept details to format
 * @param truncateEvidence - Whether to truncate full_text context to 200 chars (default: true)
 */
export function formatConceptDetails(concept: ConceptDetailsResponse, truncateEvidence: boolean = true): string {
  let output = `# Concept: ${concept.label}\n\n`;
  if (concept.description) {
    output += `${concept.description}\n\n`;
  }
  output += `ID: ${concept.concept_id}\n`;
  output += `Search Terms: ${concept.search_terms.join(', ')}\n`;
  output += `Documents: ${concept.documents.join(', ')}\n`;

  if (concept.grounding_strength !== undefined || concept.grounding_display) {
    output += `Grounding: ${formatGroundingWithConfidence(concept.grounding_strength, concept.grounding_display, concept.confidence_score)}\n`;
  }

  if (concept.diversity_score !== undefined && concept.diversity_score !== null && concept.diversity_related_count !== undefined) {
    output += `Diversity: ${(concept.diversity_score * 100).toFixed(1)}% (${concept.diversity_related_count} related concepts)\n`;
  }

  if (concept.authenticated_diversity !== undefined && concept.authenticated_diversity !== null) {
    const authDiv = concept.authenticated_diversity;
    const sign = authDiv >= 0 ? '+' : '';
    // Near-zero values (|authDiv| < 0.05) are "unclear" - grounding too weak to authenticate
    const status = Math.abs(authDiv) < 0.05 ? 'unclear ◯' :
                   authDiv > 0.3 ? 'diverse support ✅' :
                   authDiv > 0 ? 'some support ✓' :
                   authDiv > -0.3 ? 'weak contradiction ⚠' :
                   'diverse contradiction ❌';
    output += `Authenticated: ${sign}${(Math.abs(authDiv) * 100).toFixed(1)}% (${status})\n`;
  }

  output += `\n## Evidence (${concept.instances.length} instances)\n\n`;
  concept.instances.forEach((inst, i) => {
    output += `${i + 1}. ${inst.document} (para ${inst.paragraph}): "${inst.quote}"\n`;

    // Include full context for chapter/verse citation if available
    if (inst.full_text) {
      // Extract chapter/verse from full_text (e.g., "# Chapter 46\n\n1. So Israel...")
      const chapterMatch = inst.full_text.match(/^#\s*Chapter\s+(\d+)/i);
      if (chapterMatch) {
        output += `   Context: Chapter ${chapterMatch[1]}\n`;
      }
      // Show full context or truncated based on parameter
      const cleanedContext = inst.full_text.replace(/^#[^\n]*\n+/, '');
      if (cleanedContext && cleanedContext !== inst.quote) {
        if (truncateEvidence && cleanedContext.length > 200) {
          // Truncate to 200 chars for token efficiency
          output += `   Full context: ${cleanedContext.substring(0, 200)}...\n`;
        } else {
          // Show complete context
          output += `   Full context: ${cleanedContext}\n`;
        }
      }
    }

    // ADR-057: Indicate if this evidence has an image
    if (inst.has_image && inst.source_id) {
      output += `   Source: ${inst.source_id} [IMAGE AVAILABLE]\n`;
      output += `   Use get_source_image("${inst.source_id}") to view and verify the original image\n`;
    }
  });

  if (concept.relationships.length > 0) {
    output += `\n## Relationships (${concept.relationships.length})\n\n`;
    concept.relationships.forEach(rel => {
      const confidence = rel.confidence ? ` (${(rel.confidence * 100).toFixed(0)}%)` : '';
      output += `${rel.rel_type} -> ${rel.to_label}${confidence}\n`;
    });
  } else {
    output += '\nNo outgoing relationships\n';
  }

  return output;
}

/**
 * Format connection paths as markdown
 * Enhanced to match CLI output with full concept details, evidence samples, and path visualization
 */
export function formatConnectionPaths(result: FindConnectionBySearchResponse): string {
  let output = `# Connection: ${result.from_concept?.label || result.from_query} -> ${result.to_concept?.label || result.to_query}\n\n`;
  output += `From Match: ${(result.from_similarity! * 100).toFixed(1)}%\n`;
  output += `To Match: ${(result.to_similarity! * 100).toFixed(1)}%\n`;
  output += `Max Hops: ${result.max_hops}\n\n`;

  if (result.count === 0) {
    output += `No connection found within ${result.max_hops} hops\n`;
    return output;
  }

  output += `Found ${result.count} path(s):\n\n`;

  result.paths.forEach((path, pathIdx) => {
    output += `## Path ${pathIdx + 1} (${path.hops} hop${path.hops !== 1 ? 's' : ''})\n\n`;

    // Full path visualization with arrows
    output += '### Path Overview\n\n';
    const pathSegments: string[] = [];
    path.nodes.forEach((node, j) => {
      pathSegments.push(node.label);
      if (j < path.relationships.length) {
        pathSegments.push(`↓ ${path.relationships[j]}`);
      }
    });
    output += pathSegments.join('\n') + '\n\n';

    // Detailed concept information for each node
    path.nodes.forEach((node, nodeIdx) => {
      output += `### ${nodeIdx + 1}. ${node.label}\n\n`;

      // Concept ID and description
      output += `**ID:** ${node.id}\n`;
      if (node.description) {
        output += `**Description:** ${node.description}\n`;
      }

      // Grounding strength with confidence-awareness
      if (node.grounding_strength !== undefined || node.grounding_display) {
        output += `**Grounding:** ${formatGroundingWithConfidence(node.grounding_strength, node.grounding_display, node.confidence_score)}\n`;
      }

      // Diversity metrics if available
      if (node.diversity_score !== undefined && node.diversity_score !== null && node.diversity_related_count !== undefined) {
        output += `**Diversity:** ${(node.diversity_score * 100).toFixed(1)}% (${node.diversity_related_count} related concepts)\n`;
      }

      // Authenticated diversity if available
      if (node.authenticated_diversity !== undefined && node.authenticated_diversity !== null) {
        const authDiv = node.authenticated_diversity;
        const sign = authDiv >= 0 ? '+' : '';
        // Near-zero values (|authDiv| < 0.05) are "unclear" - grounding too weak to authenticate
        const status = Math.abs(authDiv) < 0.05 ? 'unclear ◯' :
                       authDiv > 0.3 ? 'diverse support ✅' :
                       authDiv > 0 ? 'some support ✓' :
                       authDiv > -0.3 ? 'weak contradiction ⚠' :
                       'diverse contradiction ❌';
        output += `**Authenticated:** ${sign}${(Math.abs(authDiv) * 100).toFixed(1)}% (${status})\n`;
      }

      // Evidence samples (limit to 3 for token efficiency)
      if (node.sample_evidence && node.sample_evidence.length > 0) {
        const evidenceCount = node.sample_evidence.length;
        output += `\n**Evidence (${evidenceCount} sample${evidenceCount !== 1 ? 's' : ''}):**\n\n`;

        node.sample_evidence.slice(0, 3).forEach((inst, idx) => {
          const truncated = inst.quote.length > 150 ? inst.quote.substring(0, 150) + '...' : inst.quote;
          output += `${idx + 1}. ${inst.document} (para ${inst.paragraph}):\n`;
          output += `   "${truncated}"\n`;

          // ADR-057: Image availability
          if (inst.has_image && inst.source_id) {
            output += `   [IMAGE AVAILABLE] Use get_source_image("${inst.source_id}") to view\n`;
          }
        });

        if (evidenceCount > 3) {
          output += `   ... and ${evidenceCount - 3} more samples\n`;
          output += `   Use get_concept_details("${node.id}") for all evidence\n`;
        }
      }

      // Show relationship to next node
      if (nodeIdx < path.relationships.length) {
        output += `\n**→ ${path.relationships[nodeIdx]}**\n`;
      }

      output += '\n';
    });

    output += '---\n\n';
  });

  return output;
}

/**
 * Format related concepts as markdown
 */
export function formatRelatedConcepts(result: RelatedConceptsResponse): string {
  let output = `# Related Concepts\n\n`;
  output += `From: ${result.concept_id}\n`;
  output += `Max Depth: ${result.max_depth}\n`;
  output += `Found: ${result.count} concepts\n\n`;

  if (result.count === 0) {
    output += 'No related concepts found\n';
    return output;
  }

  let currentDistance = -1;
  result.results.forEach(concept => {
    if (concept.distance !== currentDistance) {
      currentDistance = concept.distance;
      output += `\n## Distance ${currentDistance}\n\n`;
    }

    output += `${concept.label} (${concept.concept_id})\n`;
    output += `Path: ${concept.path_types.join(' -> ')}\n`;
  });

  return output;
}
