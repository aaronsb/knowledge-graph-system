/**
 * MCP Server Markdown Formatters
 *
 * Formats API responses as markdown-style text for AI agents.
 * No ANSI colors - just clean structure with headers, indentation, bullets.
 */

import type {
  SearchResponse,
  ConceptDetailsResponse,
  FindConnectionBySearchResponse,
  RelatedConceptsResponse,
} from '../types/index.js';

/**
 * Format grounding strength as text (no colors)
 */
function formatGroundingStrength(grounding: number): string {
  const groundingPercent = (grounding * 100).toFixed(0);
  const groundingValue = grounding.toFixed(3);

  let indicator: string;
  let interpretation: string;

  if (grounding >= 0.7) {
    indicator = '✓ Strong';
    interpretation = 'Well-supported by evidence';
  } else if (grounding >= 0.3) {
    indicator = '⚡ Moderate';
    interpretation = 'Mixed evidence, use with caution';
  } else if (grounding >= 0) {
    indicator = '◯ Weak';
    interpretation = 'More contradictions than support';
  } else if (grounding >= -0.3) {
    indicator = '⚠ Negative';
    interpretation = 'Evidence leans toward contradiction';
  } else {
    indicator = '✗ Contradicted';
    interpretation = 'Evidence suggests concept is incorrect or outdated';
  }

  return `${indicator} (${groundingValue}, ${groundingPercent}%) - ${interpretation}`;
}

/**
 * Format search results as markdown
 */
export function formatSearchResults(result: SearchResponse): string {
  let output = `# Search Results: "${result.query}"\n\n`;
  output += `Found ${result.count} concepts (threshold: ${(result.threshold_used || 0.7) * 100}%)\n\n`;

  if (result.count === 0) {
    output += '⚠ No concepts found matching this query.\n';
    return output;
  }

  output += '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n';

  result.results.forEach((concept, i) => {
    output += `## ${i + 1}. ${concept.label}\n\n`;
    output += `- **ID:** ${concept.concept_id}\n`;
    output += `- **Similarity:** ${(concept.score * 100).toFixed(1)}%\n`;
    output += `- **Documents:** ${concept.documents.join(', ')}\n`;
    output += `- **Evidence:** ${concept.evidence_count} instances\n`;

    if (concept.grounding_strength !== undefined && concept.grounding_strength !== null) {
      output += `- **Grounding:** ${formatGroundingStrength(concept.grounding_strength)}\n`;
    }

    if (concept.sample_evidence && concept.sample_evidence.length > 0) {
      output += `\n### Sample Evidence (${concept.sample_evidence.length} of ${concept.evidence_count}):\n\n`;
      concept.sample_evidence.forEach((inst, idx) => {
        const truncated = inst.quote.length > 120 ? inst.quote.substring(0, 120) + '...' : inst.quote;
        output += `${idx + 1}. **${inst.document}** (para ${inst.paragraph}) [source_id: ${inst.source_id}]\n`;
        output += `   > "${truncated}"\n\n`;
      });
      output += `💡 Tip: Use get_concept_details("${concept.concept_id}") to see all ${concept.evidence_count} evidence instances\n`;
    }

    output += '\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n';
  });

  if (result.below_threshold_count && result.below_threshold_count > 0 && result.suggested_threshold) {
    const thresholdPercent = (result.suggested_threshold * 100).toFixed(0);
    output += `\n💡 **Hint:** ${result.below_threshold_count} additional concept(s) available at ${thresholdPercent}% threshold\n`;
  }

  output += '\n--- Grounding Strength ---\n';
  output += 'Higher grounding (>0.7) indicates well-supported concepts.\n';
  output += 'Negative grounding suggests the document presents this as a problem or outdated approach.\n';

  return output;
}

/**
 * Format concept details as markdown
 */
export function formatConceptDetails(concept: ConceptDetailsResponse): string {
  let output = `# Concept Details: ${concept.label}\n\n`;
  output += `- **ID:** ${concept.concept_id}\n`;
  output += `- **Search Terms:** ${concept.search_terms.join(', ')}\n`;
  output += `- **Documents:** ${concept.documents.join(', ')}\n`;

  if (concept.grounding_strength !== undefined && concept.grounding_strength !== null) {
    output += `- **Grounding:** ${formatGroundingStrength(concept.grounding_strength)}\n`;
  }

  output += `\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n`;

  output += `\n## Evidence (${concept.instances.length} instances)\n\n`;
  concept.instances.forEach((inst, i) => {
    output += `${i + 1}. **${inst.document}** (para ${inst.paragraph})\n`;
    output += `   > "${inst.quote}"\n\n`;
  });

  if (concept.relationships.length > 0) {
    output += `\n## Relationships (${concept.relationships.length})\n\n`;
    concept.relationships.forEach(rel => {
      const confidence = rel.confidence ? ` [${(rel.confidence * 100).toFixed(0)}%]` : '';
      output += `- **${rel.rel_type}** → ${rel.to_label} (${rel.to_id})${confidence}\n`;
    });
  } else {
    output += '\n⚠ No outgoing relationships\n';
  }

  if (concept.grounding_strength !== undefined && concept.grounding_strength !== null) {
    output += '\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n';
    output += '\n--- Grounding Strength ---\n';
    output += `Score: ${concept.grounding_strength.toFixed(3)} (${(concept.grounding_strength * 100).toFixed(0)}%)\n`;
    output += 'Meaning: Grounding measures probabilistic truth convergence based on SUPPORTS vs CONTRADICTS relationships.\n';
    output += 'Higher values (>0.7) indicate reliable concepts. Lower values (<0.3) suggest historical/incorrect information.\n';
  }

  return output;
}

/**
 * Format connection paths as markdown
 */
export function formatConnectionPaths(result: FindConnectionBySearchResponse): string {
  let output = `# Connection Found\n\n`;
  output += `**From:** ${result.from_concept?.label || result.from_query} (${(result.from_similarity! * 100).toFixed(1)}% match)\n`;
  output += `**To:** ${result.to_concept?.label || result.to_query} (${(result.to_similarity! * 100).toFixed(1)}% match)\n`;
  output += `**Max hops:** ${result.max_hops}\n\n`;

  if (result.count === 0) {
    output += `⚠ No connection found within ${result.max_hops} hops\n`;
    return output;
  }

  output += `Found ${result.count} path(s):\n\n`;
  output += '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n';

  result.paths.forEach((path, i) => {
    output += `## Path ${i + 1} (${path.hops} hops)\n\n`;

    path.nodes.forEach((node, j) => {
      output += `### ${node.label}\n`;
      output += `- ID: ${node.id}\n`;

      if (node.grounding_strength !== undefined && node.grounding_strength !== null) {
        output += `- Grounding: ${formatGroundingStrength(node.grounding_strength)}\n`;
      }

      if (node.sample_evidence && node.sample_evidence.length > 0) {
        output += `- Evidence (${node.sample_evidence.length} sample${node.sample_evidence.length > 1 ? 's' : ''}):\n`;
        node.sample_evidence.forEach((inst, idx) => {
          const truncated = inst.quote.length > 100 ? inst.quote.substring(0, 100) + '...' : inst.quote;
          output += `  ${idx + 1}. **${inst.document}** (para ${inst.paragraph}) [source_id: ${inst.source_id}]\n`;
          output += `     > "${truncated}"\n`;
        });
        output += `  💡 Tip: Use get_concept_details("${node.id}") to see all evidence instances\n`;
      }

      if (j < path.relationships.length) {
        output += `\n    ↓ **${path.relationships[j]}**\n\n`;
      }
    });

    output += '\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n';
  });

  output += '\n--- Grounding Strength ---\n';
  output += 'Interpretation: Higher grounding (>0.7) indicates well-supported concepts.\n';
  output += 'Negative grounding suggests the document presents this as a problem or outdated approach.\n';

  return output;
}

/**
 * Format related concepts as markdown
 */
export function formatRelatedConcepts(result: RelatedConceptsResponse): string {
  let output = `# Related Concepts\n\n`;
  output += `**Starting from:** ${result.concept_id}\n`;
  output += `**Max depth:** ${result.max_depth}\n`;
  output += `**Found:** ${result.count} concepts\n\n`;

  if (result.count === 0) {
    output += '⚠ No related concepts found\n';
    return output;
  }

  output += '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n';

  let currentDistance = -1;
  result.results.forEach(concept => {
    if (concept.distance !== currentDistance) {
      currentDistance = concept.distance;
      output += `\n## Distance ${currentDistance}\n\n`;
    }

    output += `- **${concept.label}** (${concept.concept_id})\n`;
    output += `  Path: ${concept.path_types.join(' → ')}\n\n`;
  });

  return output;
}
