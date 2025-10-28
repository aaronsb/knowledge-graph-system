/**
 * MCP Server Markdown Formatters
 *
 * Formats API responses as markdown-style text for AI agents.
 * Optimized for token efficiency - minimal Unicode, plain structure.
 */

import type {
  SearchResponse,
  ConceptDetailsResponse,
  FindConnectionBySearchResponse,
  RelatedConceptsResponse,
  JobStatus,
} from '../types/index.js';

/**
 * Format grounding strength as text (token-efficient)
 */
function formatGroundingStrength(grounding: number): string {
  const groundingPercent = (grounding * 100).toFixed(0);
  const groundingValue = grounding.toFixed(3);

  let level: string;
  if (grounding >= 0.7) level = 'Strong';
  else if (grounding >= 0.3) level = 'Moderate';
  else if (grounding >= 0) level = 'Weak';
  else if (grounding >= -0.3) level = 'Negative';
  else level = 'Contradicted';

  return `${level} (${groundingValue}, ${groundingPercent}%)`;
}

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
    output += `ID: ${concept.concept_id}\n`;
    output += `Similarity: ${(concept.score * 100).toFixed(1)}%\n`;
    output += `Documents: ${concept.documents.join(', ')}\n`;
    output += `Evidence: ${concept.evidence_count} instances\n`;

    if (concept.grounding_strength !== undefined && concept.grounding_strength !== null) {
      output += `Grounding: ${formatGroundingStrength(concept.grounding_strength)}\n`;
    }

    if (concept.sample_evidence && concept.sample_evidence.length > 0) {
      output += `\nSample Evidence (${concept.sample_evidence.length} of ${concept.evidence_count}):\n`;
      concept.sample_evidence.forEach((inst, idx) => {
        const truncated = inst.quote.length > 120 ? inst.quote.substring(0, 120) + '...' : inst.quote;
        output += `${idx + 1}. ${inst.document} (para ${inst.paragraph}): "${truncated}"\n`;
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
 */
export function formatConceptDetails(concept: ConceptDetailsResponse): string {
  let output = `# Concept: ${concept.label}\n\n`;
  output += `ID: ${concept.concept_id}\n`;
  output += `Search Terms: ${concept.search_terms.join(', ')}\n`;
  output += `Documents: ${concept.documents.join(', ')}\n`;

  if (concept.grounding_strength !== undefined && concept.grounding_strength !== null) {
    output += `Grounding: ${formatGroundingStrength(concept.grounding_strength)}\n`;
  }

  output += `\n## Evidence (${concept.instances.length} instances)\n\n`;
  concept.instances.forEach((inst, i) => {
    output += `${i + 1}. ${inst.document} (para ${inst.paragraph}): "${inst.quote}"\n`;
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

  result.paths.forEach((path, i) => {
    output += `## Path ${i + 1} (${path.hops} hops)\n\n`;

    path.nodes.forEach((node, j) => {
      output += `${node.label} (${node.id})\n`;

      if (node.grounding_strength !== undefined && node.grounding_strength !== null) {
        output += `Grounding: ${formatGroundingStrength(node.grounding_strength)}\n`;
      }

      if (node.sample_evidence && node.sample_evidence.length > 0) {
        output += `Evidence samples:\n`;
        node.sample_evidence.forEach((inst, idx) => {
          const truncated = inst.quote.length > 100 ? inst.quote.substring(0, 100) + '...' : inst.quote;
          output += `  ${idx + 1}. ${inst.document} (para ${inst.paragraph}): "${truncated}"\n`;
        });
      }

      if (j < path.relationships.length) {
        output += `  [${path.relationships[j]}]\n`;
      }
    });

    output += '\n';
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

/**
 * Format job status as markdown (token-efficient)
 */
export function formatJobStatus(job: JobStatus): string {
  let output = `# Job: ${job.job_id}\n\n`;
  output += `Type: ${job.job_type}\n`;
  output += `Status: ${job.status}`;

  // Add stage info if available
  if (job.progress?.stage) {
    output += ` (${job.progress.stage})`;
  }
  output += '\n';

  // Ontology and processing mode
  if (job.ontology) {
    output += `Ontology: ${job.ontology}\n`;
  }
  if (job.processing_mode) {
    output += `Processing Mode: ${job.processing_mode}\n`;
  }

  // Progress information
  if (job.progress) {
    const p = job.progress;
    output += '\n## Progress\n\n';

    if (p.percent !== undefined) {
      output += `Completion: ${p.percent}%\n`;
    }

    if (p.chunks_total !== undefined) {
      const processed = p.chunks_processed || 0;
      output += `Chunks: ${processed}/${p.chunks_total}\n`;
    }

    if (p.concepts_created !== undefined || p.concepts_linked !== undefined) {
      if (p.concepts_created !== undefined) {
        output += `Concepts Created: ${p.concepts_created}\n`;
      }
      if (p.concepts_linked !== undefined) {
        output += `Concepts Linked: ${p.concepts_linked}\n`;
      }
    }

    if (p.sources_created !== undefined) {
      output += `Sources Created: ${p.sources_created}\n`;
    }

    if (p.instances_created !== undefined) {
      output += `Instances Created: ${p.instances_created}\n`;
    }

    if (p.relationships_created !== undefined) {
      output += `Relationships Created: ${p.relationships_created}\n`;
    }

    if (p.message) {
      output += `Message: ${p.message}\n`;
    }
  }

  // Cost estimate (for awaiting_approval status)
  if (job.status === 'awaiting_approval' && job.analysis?.cost_estimate) {
    const cost = job.analysis.cost_estimate;
    output += '\n## Cost Estimate\n\n';
    if (cost.total) {
      output += `Total: $${cost.total.cost_low.toFixed(4)} - $${cost.total.cost_high.toFixed(4)} ${cost.total.currency}\n`;
    }
    if (cost.extraction) {
      output += `Extraction: $${cost.extraction.cost_low.toFixed(4)} - $${cost.extraction.cost_high.toFixed(4)}\n`;
    }
    if (cost.embeddings) {
      output += `Embeddings: $${cost.embeddings.cost_low.toFixed(4)} - $${cost.embeddings.cost_high.toFixed(4)}\n`;
    }
  }

  // Result (for completed jobs)
  if (job.result) {
    output += '\n## Result\n\n';
    if (job.result.stats) {
      output += `Concepts Created: ${job.result.stats.concepts_created || 0}\n`;
      output += `Concepts Linked: ${job.result.stats.concepts_linked || 0}\n`;
      output += `Sources Created: ${job.result.stats.sources_created || 0}\n`;
      output += `Instances Created: ${job.result.stats.instances_created || 0}\n`;
      output += `Relationships Created: ${job.result.stats.relationships_created || 0}\n`;
      output += `Chunks Processed: ${job.result.stats.chunks_processed || 0}\n`;
    }
    if (job.result.cost) {
      output += `Cost: ${job.result.cost.total}\n`;
    }
  }

  // Error (for failed jobs)
  if (job.error) {
    output += '\n## Error\n\n';
    output += `${job.error}\n`;
  }

  // Timestamps
  output += '\n## Timeline\n\n';
  output += `Created: ${job.created_at}\n`;
  if (job.started_at) {
    output += `Started: ${job.started_at}\n`;
  }
  if (job.completed_at) {
    output += `Completed: ${job.completed_at}\n`;
  }
  if (job.approved_at) {
    output += `Approved: ${job.approved_at} (by ${job.approved_by || 'unknown'})\n`;
  }
  if (job.expires_at) {
    output += `Expires: ${job.expires_at}\n`;
  }

  return output;
}
