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
  SourceSearchResponse,
} from '../types/index.js';

/**
 * Format grounding strength as text (token-efficient)
 * This is the fallback when grounding_display is not available.
 */
function formatGroundingStrength(grounding: number): string {
  const groundingValue = grounding.toFixed(3);
  const percentValue = grounding * 100;

  // Use ≈ symbol when value is very close to zero but not exactly zero
  const groundingPercent = (Math.abs(percentValue) < 0.1 && percentValue !== 0)
    ? `≈${percentValue >= 0 ? '0' : '-0'}`
    : percentValue.toFixed(0);

  let level: string;
  if (grounding >= 0.7) level = 'Strong';
  else if (grounding >= 0.3) level = 'Moderate';
  else if (grounding >= 0) level = 'Weak';
  else if (grounding >= -0.3) level = 'Negative';
  else level = 'Contradicted';

  return `${level} (${groundingValue}, ${groundingPercent}%)`;
}

/**
 * Format grounding with confidence-awareness (grounding × confidence two-dimensional model)
 *
 * Uses grounding_display when available (categorical label from API).
 * Includes numeric confidence_score alongside the label for quantitative insight.
 * Falls back to raw grounding score display for backwards compatibility.
 */
function formatGroundingWithConfidence(
  grounding: number | undefined | null,
  groundingDisplay: string | undefined | null,
  confidenceScore: number | undefined | null = null
): string {
  // Format confidence score as percentage if available
  const confScoreStr = confidenceScore !== undefined && confidenceScore !== null
    ? ` [${(confidenceScore * 100).toFixed(0)}% conf]`
    : '';

  // If we have a grounding_display label from the API, use it directly
  if (groundingDisplay) {
    return `${groundingDisplay}${confScoreStr}`;
  }

  // Fall back to raw grounding score display if available
  if (grounding !== undefined && grounding !== null) {
    return formatGroundingStrength(grounding);
  }

  // No grounding information available
  return 'Unexplored';
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

/**
 * Format job list as markdown (token-efficient summary view)
 */
export function formatJobList(jobs: JobStatus[]): string {
  let output = `# Ingestion Jobs\n\n`;
  output += `Total: ${jobs.length} job(s)\n\n`;

  if (jobs.length === 0) {
    output += 'No jobs found.\n';
    return output;
  }

  // Group by status for quick overview
  const byStatus: { [key: string]: JobStatus[] } = {};
  jobs.forEach(job => {
    const status = job.status;
    if (!byStatus[status]) byStatus[status] = [];
    byStatus[status].push(job);
  });

  // Status summary
  output += '## Status Summary\n\n';
  const statusOrder = ['processing', 'awaiting_approval', 'pending', 'approved', 'queued', 'completed', 'failed', 'cancelled'];
  statusOrder.forEach(status => {
    if (byStatus[status] && byStatus[status].length > 0) {
      const icon = status === 'completed' ? '✓' :
                   status === 'processing' ? '▶' :
                   status === 'awaiting_approval' ? '⏳' :
                   status === 'failed' ? '✗' :
                   status === 'cancelled' ? '⊘' : '○';
      output += `- ${icon} **${status}**: ${byStatus[status].length}\n`;
    }
  });
  output += '\n';

  // Detailed list
  output += '## Jobs\n\n';

  jobs.forEach((job, idx) => {
    const statusIcon = job.status === 'completed' ? '✓' :
                       job.status === 'processing' ? '▶' :
                       job.status === 'awaiting_approval' ? '⏳' :
                       job.status === 'failed' ? '✗' :
                       job.status === 'cancelled' ? '⊘' : '○';

    // Header with status and filename
    const filename = job.filename || job.analysis?.file_stats?.filename || 'Unknown';
    output += `### ${idx + 1}. ${statusIcon} ${filename}\n\n`;

    // Core info
    output += `- **Job ID:** ${job.job_id}\n`;
    output += `- **Status:** ${job.status}`;
    if (job.progress?.stage) {
      output += ` (${job.progress.stage})`;
    }
    output += '\n';

    if (job.ontology) {
      output += `- **Ontology:** ${job.ontology}\n`;
    }

    // Progress for processing jobs
    if (job.status === 'processing' && job.progress) {
      const p = job.progress;
      if (p.percent !== undefined) {
        output += `- **Progress:** ${p.percent}%`;
        if (p.chunks_total !== undefined) {
          output += ` (${p.chunks_processed || 0}/${p.chunks_total} chunks)`;
        }
        output += '\n';
      }
      if (p.concepts_created !== undefined) {
        output += `- **Created:** ${p.concepts_created} concepts, ${p.sources_created || 0} sources\n`;
      }
    }

    // Cost for awaiting_approval
    if (job.status === 'awaiting_approval' && job.analysis?.cost_estimate?.total) {
      const cost = job.analysis.cost_estimate.total;
      output += `- **Est. Cost:** $${cost.cost_low.toFixed(3)} - $${cost.cost_high.toFixed(3)}\n`;
    }

    // Results for completed jobs
    if (job.status === 'completed' && job.result?.stats) {
      const s = job.result.stats;
      output += `- **Result:** ${s.concepts_created || 0} concepts, ${s.relationships_created || 0} relationships\n`;
      if (job.result.cost?.total) {
        output += `- **Cost:** ${job.result.cost.total}\n`;
      }
    }

    // Error for failed jobs
    if (job.status === 'failed' && job.error) {
      const truncatedError = job.error.length > 100 ? job.error.substring(0, 100) + '...' : job.error;
      output += `- **Error:** ${truncatedError}\n`;
    }

    output += '\n';
  });

  // Usage hints
  output += '## Actions\n\n';
  output += '- Use `job` tool with action "status" and job_id for full details\n';
  output += '- Use `job` tool with action "approve" to start awaiting jobs\n';
  output += '- Use `job` tool with action "cancel" to cancel pending jobs\n';

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

/**
 * Format inspect-file result as markdown
 */
export function formatInspectFileResult(result: any): string {
  let output = `# File Inspection: ${result.path}\n\n`;

  // Validation status
  if (result.validation.allowed) {
    output += `Status: ✓ ALLOWED\n\n`;
  } else {
    output += `Status: ✗ DENIED\n`;
    output += `Reason: ${result.validation.reason}\n`;
    if (result.validation.hint) {
      output += `Hint: ${result.validation.hint}\n`;
    }
    output += '\n';
  }

  // File existence
  if (result.exists) {
    output += `## File Metadata\n\n`;
    if (result.metadata) {
      const m = result.metadata;
      output += `Type: ${m.type}\n`;
      output += `Size: ${m.size_mb.toFixed(2)} MB (${m.size_bytes.toLocaleString()} bytes)\n`;
      output += `MIME Type: ${m.mime_type}\n`;
      output += `Modified: ${new Date(m.modified).toLocaleString()}\n`;
      output += `Image: ${m.is_image ? 'Yes' : 'No'}\n`;
      output += `Permissions: ${m.permissions.readable ? 'readable' : ''}${m.permissions.readable && m.permissions.writable ? ', ' : ''}${m.permissions.writable ? 'writable' : ''}\n`;
    }
    if (result.error) {
      output += `\nError: ${result.error}\n`;
    }
  } else {
    output += `File does not exist\n`;
  }

  return output;
}

/**
 * Format ingest-file result as markdown
 */
export function formatIngestFileResult(result: any): string {
  // Handle batch ingestion
  if (result.batch) {
    let output = `# Batch File Ingestion\n\n`;
    output += `Ontology: ${result.ontology}\n`;
    output += `Total Files: ${result.total_files}\n`;
    output += `Successful: ${result.successful}\n`;
    output += `Failed: ${result.failed}\n\n`;

    if (result.results && result.results.length > 0) {
      output += `## Submitted Files\n\n`;
      result.results.forEach((r: any, idx: number) => {
        const filename = r.file.split('/').pop();
        const typeLabel = r.type === 'image' ? '🖼️' : '📄';
        if (r.status === 'submitted' && r.job_id) {
          output += `${idx + 1}. ✓ ${typeLabel} ${filename}\n`;
          output += `   Job ID: ${r.job_id}\n`;
        } else if (r.status === 'duplicate') {
          output += `${idx + 1}. ⊘ ${typeLabel} ${filename} (already ingested)\n`;
        } else if (r.status === 'not_implemented') {
          output += `${idx + 1}. ⏸ ${filename} (${r.type} - not implemented yet)\n`;
        }
      });
    }

    if (result.errors && result.errors.length > 0) {
      output += `\n## Errors\n\n`;
      result.errors.forEach((e: any, idx: number) => {
        const filename = e.file.split('/').pop();
        output += `${idx + 1}. ✗ ${filename}\n`;
        output += `   ${e.error}\n`;
      });
    }

    return output;
  }

  // Handle single file ingestion
  const typeIcon = result.type === 'image' ? '🖼️' : '📄';
  let output = `# File Ingestion: ${typeIcon} ${result.file}\n\n`;

  if (result.status === 'not_implemented') {
    output += `Status: Not Implemented\n`;
    output += `Type: ${result.type}\n`;
    output += `Message: ${result.message}\n`;
    if (result.next_phase) {
      output += `\nNext Phase: ${result.next_phase}\n`;
    }
  } else if (result.status === 'submitted') {
    output += `Status: ✓ Submitted Successfully\n\n`;
    output += `## Job Details\n\n`;
    output += `Job ID: ${result.job_id}\n`;
    output += `Ontology: ${result.ontology}\n`;
    output += `Type: ${result.type === 'image' ? '🖼️ Image' : '📄 Text'}\n`;
    output += `Size: ${(result.size_bytes / 1024).toFixed(2)} KB\n\n`;
    output += `Track progress: Use job tool with action "status" and job_id "${result.job_id}"\n`;
  } else if (result.status === 'duplicate') {
    output += `Status: Duplicate Detected\n\n`;
    output += `This file has already been ingested.\n`;
    if (result.duplicate_job_id) {
      output += `Existing Job ID: ${result.duplicate_job_id}\n`;
    }
    output += `\nTo force re-ingestion, set force=true\n`;
  }

  return output;
}

/**
 * Format ingest-directory result as markdown
 */
export function formatIngestDirectoryResult(result: any): string {
  let output = `# Directory Ingestion: ${result.directory}\n\n`;

  if (result.status === 'not_implemented') {
    output += `Status: Not Implemented (Preview Mode)\n`;
    output += `Ontology: ${result.ontology}\n\n`;
    output += `## Scan Results\n\n`;
    output += `Files Found: ${result.files_found}\n`;
    output += `Files Skipped: ${result.files_skipped} (blocked by security patterns)\n\n`;

    if (result.files && result.files.length > 0) {
      const pagination = result.pagination;
      const startNum = pagination ? pagination.offset + 1 : 1;
      const endNum = pagination ? pagination.offset + result.files.length : result.files.length;

      output += `## Files (showing ${startNum}-${endNum} of ${result.files_found})\n\n`;
      result.files.forEach((file: string, idx: number) => {
        const basename = file.split('/').pop();
        const fileNum = pagination ? pagination.offset + idx + 1 : idx + 1;
        output += `${fileNum}. ${basename}\n`;
      });

      // Pagination navigation
      if (pagination && (pagination.offset > 0 || pagination.has_more)) {
        output += `\n## Navigation\n\n`;
        if (pagination.offset > 0) {
          const prevOffset = Math.max(0, pagination.offset - pagination.limit);
          output += `Previous: Use offset=${prevOffset}, limit=${pagination.limit}\n`;
        }
        if (pagination.has_more) {
          const nextOffset = pagination.offset + pagination.limit;
          output += `Next: Use offset=${nextOffset}, limit=${pagination.limit}\n`;
        }
      }
    }

    if (result.next_phase) {
      output += `\n${result.next_phase}\n`;
    }

    output += `\nFor now, use ingest-file on individual files from the list above.\n`;
  } else if (result.status === 'submitted') {
    output += `Status: ✓ Batch Submission Started\n\n`;
    output += `## Summary\n\n`;
    output += `Ontology: ${result.ontology}\n`;
    output += `Files Queued: ${result.files_queued}\n`;
    output += `Files Skipped: ${result.files_skipped}\n\n`;
    if (result.job_ids && result.job_ids.length > 0) {
      output += `## Job IDs\n\n`;
      result.job_ids.forEach((id: string, idx: number) => {
        output += `${idx + 1}. ${id}\n`;
      });
    }
  }

  return output;
}

// ============================================================================
// MCP Resource Formatters
// ============================================================================

export function formatDatabaseStats(result: any): string {
  let output = `# Database Statistics\n\n`;

  if (result.graph_name) {
    output += `Graph: ${result.graph_name}\n\n`;
  }

  output += `## Nodes\n\n`;
  output += `Concepts: ${result.concept_count?.toLocaleString() || 0}\n`;
  output += `Sources: ${result.source_count?.toLocaleString() || 0}\n`;
  output += `Instances: ${result.instance_count?.toLocaleString() || 0}\n`;
  output += `Total: ${result.total_node_count?.toLocaleString() || 0}\n\n`;

  output += `## Relationships\n\n`;
  output += `Total: ${result.total_edge_count?.toLocaleString() || 0}\n\n`;

  if (result.ontologies && result.ontologies.length > 0) {
    output += `## Ontologies (${result.ontologies.length})\n\n`;
    result.ontologies.forEach((ont: any, idx: number) => {
      output += `${idx + 1}. ${ont.ontology_name} (${ont.concept_count} concepts)\n`;
    });
  }

  return output;
}

export function formatDatabaseInfo(result: any): string {
  let output = `# Database Information\n\n`;

  if (result.database) {
    output += `Database: ${result.database}\n`;
  }
  if (result.version) {
    output += `PostgreSQL: ${result.version}\n`;
  }
  if (result.age_version) {
    output += `Apache AGE: ${result.age_version}\n`;
  }
  if (result.graph_name) {
    output += `Graph: ${result.graph_name}\n`;
  }

  return output;
}

export function formatDatabaseHealth(result: any): string {
  let output = `# Database Health\n\n`;

  const status = result.status || result.healthy;
  if (status === 'healthy' || status === true) {
    output += `Status: ✓ Healthy\n`;
  } else {
    output += `Status: ✗ Unhealthy\n`;
  }

  if (result.graph_available !== undefined) {
    output += `Graph Available: ${result.graph_available ? '✓ Yes' : '✗ No'}\n`;
  }

  if (result.connection) {
    output += `Connection: ${result.connection}\n`;
  }

  return output;
}

export function formatSystemStatus(result: any): string {
  let output = `# System Status\n\n`;

  if (result.scheduler) {
    output += `## Job Scheduler\n\n`;
    output += `Status: ${result.scheduler.running ? '✓ Running' : '✗ Stopped'}\n`;
    if (result.scheduler.active_jobs !== undefined) {
      output += `Active Jobs: ${result.scheduler.active_jobs}\n`;
    }
    if (result.scheduler.pending_jobs !== undefined) {
      output += `Pending Jobs: ${result.scheduler.pending_jobs}\n`;
    }
    output += `\n`;
  }

  if (result.resources) {
    output += `## Resource Usage\n\n`;
    if (result.resources.cpu_percent !== undefined) {
      output += `CPU: ${result.resources.cpu_percent}%\n`;
    }
    if (result.resources.memory_percent !== undefined) {
      output += `Memory: ${result.resources.memory_percent}%\n`;
    }
    if (result.resources.disk_percent !== undefined) {
      output += `Disk: ${result.resources.disk_percent}%\n`;
    }
  }

  return output;
}

export function formatApiHealth(result: any): string {
  let output = `# API Health\n\n`;

  if (result.status === 'healthy' || result.healthy === true) {
    output += `Status: ✓ Healthy\n`;
  } else {
    output += `Status: ✗ Unhealthy\n`;
  }

  if (result.timestamp) {
    output += `Timestamp: ${new Date(result.timestamp).toLocaleString()}\n`;
  }

  if (result.version) {
    output += `Version: ${result.version}\n`;
  }

  return output;
}

export function formatMcpAllowedPaths(result: any): string {
  if (!result.configured) {
    let output = `# MCP File Access Allowlist\n\n`;
    output += `Status: ✗ Not Configured\n\n`;
    if (result.message) {
      output += `${result.message}\n\n`;
    }
    if (result.hint) {
      output += `Hint: ${result.hint}\n`;
    }
    return output;
  }

  let output = `# MCP File Access Allowlist\n\n`;
  output += `Status: ✓ Configured\n`;
  output += `Version: ${result.version}\n\n`;

  if (result.allowed_directories && result.allowed_directories.length > 0) {
    output += `## Allowed Directories (${result.allowed_directories.length})\n\n`;
    result.allowed_directories.forEach((dir: string, idx: number) => {
      output += `${idx + 1}. ${dir}\n`;
    });
    output += `\n`;
  }

  if (result.allowed_patterns && result.allowed_patterns.length > 0) {
    output += `## Allowed Patterns (${result.allowed_patterns.length})\n\n`;
    result.allowed_patterns.forEach((pattern: string, idx: number) => {
      output += `${idx + 1}. ${pattern}\n`;
    });
    output += `\n`;
  }

  if (result.blocked_patterns && result.blocked_patterns.length > 0) {
    output += `## Blocked Patterns (${result.blocked_patterns.length})\n\n`;
    result.blocked_patterns.forEach((pattern: string, idx: number) => {
      output += `${idx + 1}. ${pattern}\n`;
    });
    output += `\n`;
  }

  output += `## Limits\n\n`;
  output += `Max File Size: ${result.max_file_size_mb} MB\n`;
  output += `Max Files Per Directory: ${result.max_files_per_directory}\n`;

  if (result.config_path) {
    output += `\nConfig Path: ${result.config_path}\n`;
  }

  return output;
}

/**
 * Format epistemic status interpretation hint
 */
function formatEpistemicStatusInterpretation(status: string): string {
  const interpretations: { [key: string]: string } = {
    'WELL_GROUNDED': 'Well-established knowledge with strong evidence support (avg grounding >0.8). Highly reliable for reasoning.',
    'MIXED_GROUNDING': 'Variable validation - grounding ranges 0.15-0.8 (15-80% net support). Represents mixed evidence or evolving understanding.',
    'WEAK_GROUNDING': 'Weak positive grounding 0.0-0.15 (0-15% net support). Developing evidence, emerging knowledge. Use for exploratory reasoning.',
    'POORLY_GROUNDED': 'Weak negative grounding -0.5-0.0 (0-50% net contradiction). Uncertain, liminal knowledge. Unclear epistemic status.',
    'CONTRADICTED': 'Strong negative grounding <-0.5 (>50% net contradiction). Refuted claims, contradicted by evidence.',
    'HISTORICAL': 'Temporal vocabulary with past-tense markers. Important for understanding evolution of concepts over time.',
    'INSUFFICIENT_DATA': 'Less than 3 measurements available. Need more graph data to establish epistemic status.',
  };
  return interpretations[status] || 'Unknown epistemic status classification.';
}

/**
 * Format epistemic status list (ADR-065)
 */
export function formatEpistemicStatusList(result: any): string {
  let output = '# Epistemic Status Classification\n\n';
  output += `Total vocabulary types: ${result.total}\n\n`;

  if (!result.types || result.types.length === 0) {
    output += '**No epistemic status data available.**\n\n';
    output += 'Run measurement first using the "measure" action to calculate epistemic status for all vocabulary types.\n\n';
    output += '**What This Means:** Epistemic status reflects how well-established each relationship type is based on evidence grounding. ';
    output += 'Without measurement, you cannot filter relationships by reliability or identify contested knowledge areas.\n';
    return output;
  }

  // Add staleness header (ADR-065 Phase 2 counter-based tracking)
  if (result.last_measurement_at) {
    const measurementDate = new Date(result.last_measurement_at).toLocaleString();
    output += `**Last Measurement:** ${measurementDate}\n`;

    const delta = result.vocabulary_changes_since_measurement ?? 0;
    let stalenessText = '';

    if (delta === 0) {
      stalenessText = 'No changes since measurement (fresh)';
    } else if (delta < 5) {
      stalenessText = `${delta} vocabulary change${delta > 1 ? 's' : ''} since measurement`;
    } else if (delta < 10) {
      stalenessText = `${delta} vocabulary changes since measurement (consider re-measuring)`;
    } else {
      stalenessText = `${delta} vocabulary changes since measurement (re-measurement recommended)`;
    }

    output += `**Staleness:** ${stalenessText}\n\n`;
  }

  // Summary by classification
  const classificationCounts: { [key: string]: number } = {};
  result.types.forEach((type: any) => {
    const status = type.epistemic_status || 'UNKNOWN';
    classificationCounts[status] = (classificationCounts[status] || 0) + 1;
  });

  output += '## Classification Summary\n\n';
  Object.entries(classificationCounts)
    .sort((a, b) => b[1] - a[1])  // Sort by count descending
    .forEach(([status, count]) => {
      output += `- **${status}**: ${count} types\n`;
    });
  output += '\n';

  // Detailed table (removed "Measured At" column - all types measured together)
  output += '## Vocabulary Types\n\n';
  output += '| Relationship Type | Status | Avg Grounding | Sampled Edges |\n';
  output += '|-------------------|--------|---------------|---------------|\n';

  result.types.forEach((type: any) => {
    const avgGrounding = type.stats?.avg_grounding !== undefined
      ? type.stats.avg_grounding.toFixed(3)
      : '--';
    const sampledEdges = type.stats?.sampled_edges !== undefined
      ? type.stats.sampled_edges.toString()
      : '--';

    output += `| ${type.relationship_type} | ${type.epistemic_status} | ${avgGrounding} | ${sampledEdges} |\n`;
  });

  output += '\n## Interpretation Guide\n\n';
  output += '**How to use this data:**\n';
  output += '- **WELL_GROUNDED types** → Use for high-confidence reasoning and reliable knowledge extraction (>80% net support)\n';
  output += '- **MIXED_GROUNDING types** → Variable validation (15-80% net support), explore dialectical patterns or uncertainty\n';
  output += '- **WEAK_GROUNDING types** → Emerging evidence (0-15% net support), use for exploratory reasoning\n';
  output += '- **POORLY_GROUNDED types** → Uncertain knowledge (0-50% net contradiction), unclear epistemic status\n';
  output += '- **CONTRADICTED types** → Refuted claims (>50% net contradiction), contradicted by evidence\n';
  output += '- **INSUFFICIENT_DATA types** → Need more document ingestion to establish epistemic patterns\n\n';
  output += '**Next Steps:**\n';
  output += '- Use `epistemic_status` with action "show" to get detailed statistics for a specific type\n';
  output += '- Filter concept searches by epistemic status to curate high-confidence vs exploratory subgraphs\n';
  output += '- Ingest more documents to move types from INSUFFICIENT_DATA to measurable classifications\n';

  return output;
}

/**
 * Format epistemic status details for a specific type (ADR-065)
 */
export function formatEpistemicStatusDetails(result: any): string {
  const relType = result.relationship_type || 'Unknown';
  const status = result.epistemic_status || 'UNKNOWN';

  let output = `# Epistemic Status: ${relType}\n\n`;
  output += `**Classification:** ${status}\n\n`;
  output += `**Interpretation:** ${formatEpistemicStatusInterpretation(status)}\n\n`;

  if (result.stats) {
    output += '## Grounding Statistics\n\n';
    output += `- **Average Grounding:** ${result.stats.avg_grounding.toFixed(3)} `;
    if (result.stats.avg_grounding > 0.8) {
      output += '(Strong support - well-established)\n';
    } else if (result.stats.avg_grounding > 0.15) {
      output += '(Mixed validation - debated or uncertain)\n';
    } else if (result.stats.avg_grounding >= 0) {
      output += '(Weak support - emerging or poorly grounded)\n';
    } else {
      output += '(Contradicted - refuted or historical)\n';
    }

    if (result.stats.std_grounding !== undefined) {
      output += `- **Standard Deviation:** ${result.stats.std_grounding.toFixed(3)} `;
      if (result.stats.std_grounding > 0.3) {
        output += '(High variance - highly contested)\n';
      } else if (result.stats.std_grounding > 0.15) {
        output += '(Moderate variance - some disagreement)\n';
      } else {
        output += '(Low variance - consistent validation)\n';
      }
    }

    output += `- **Range:** ${result.stats.min_grounding.toFixed(3)} to ${result.stats.max_grounding.toFixed(3)}\n`;
    output += `- **Measurements:** ${result.stats.measured_concepts} concepts sampled\n`;
    output += `- **Sampled Edges:** ${result.stats.sampled_edges} of ${result.stats.total_edges} total\n`;
  }

  // Add measurement context with staleness (ADR-065 Phase 2)
  output += '\n## Measurement Context\n\n';
  if (result.status_measured_at) {
    output += `- **Measured At:** ${new Date(result.status_measured_at).toLocaleString()}\n`;
  }

  const delta = result.vocabulary_changes_since_measurement ?? 0;
  let stalenessText = '';

  if (delta === 0) {
    stalenessText = 'No changes since measurement (fresh)';
  } else if (delta < 5) {
    stalenessText = `${delta} vocabulary change${delta > 1 ? 's' : ''} since measurement`;
  } else if (delta < 10) {
    stalenessText = `${delta} vocabulary changes since measurement (consider re-measuring)`;
  } else {
    stalenessText = `${delta} vocabulary changes since measurement (re-measurement recommended)`;
  }

  output += `- **Staleness:** ${stalenessText}\n`;
  output += `- **Note:** Results are temporal - rerun measurement as graph evolves\n`;

  if (result.rationale) {
    output += `\n## Classification Rationale\n\n${result.rationale}\n`;
  }

  output += '\n## Practical Implications\n\n';
  if (status === 'WELL_GROUNDED') {
    output += '**This relationship type is highly reliable.**\n';
    output += '- Use in high-confidence reasoning chains\n';
    output += '- Good candidate for automated inference\n';
    output += '- Represents well-established domain knowledge\n';
  } else if (status === 'MIXED_GROUNDING') {
    output += '**This relationship type has variable validation.**\n';
    output += '- Represents mixed evidence or evolving understanding\n';
    output += '- Explore both supporting and contradicting evidence\n';
    output += '- Good for identifying knowledge gaps or areas of uncertainty\n';
  } else if (status === 'WEAK_GROUNDING') {
    output += '**This relationship type has emerging evidence.**\n';
    output += '- Weak positive grounding (0.0-0.15) indicates developing knowledge\n';
    output += '- May strengthen with more document ingestion\n';
    output += '- Use for exploratory reasoning, but verify claims\n';
  } else if (status === 'POORLY_GROUNDED') {
    output += '**This relationship type has uncertain validation.**\n';
    output += '- Weak negative grounding (-0.5-0.0) indicates unclear support\n';
    output += '- May represent liminal or contested knowledge\n';
    output += '- Use cautiously - verify before using in reasoning\n';
  } else if (status === 'CONTRADICTED') {
    output += '**This relationship type is contradicted by evidence.**\n';
    output += '- May represent refuted claims or historical misconceptions\n';
    output += '- Use cautiously - validate before using in reasoning\n';
    output += '- Useful for understanding evolution of knowledge\n';
  } else if (status === 'INSUFFICIENT_DATA') {
    output += '**Not enough data to establish epistemic pattern.**\n';
    output += '- Need more documents using this relationship type\n';
    output += '- Current measurements: <3 successful samples\n';
    output += '- Re-measure after ingesting more content\n';
  }

  return output;
}

/**
 * Format epistemic status measurement results (ADR-065)
 */
export function formatEpistemicStatusMeasurement(result: any): string {
  let output = '# Epistemic Status Measurement Results\n\n';
  output += `**Measured:** ${result.total_types} vocabulary types\n`;
  output += `**Stored:** ${result.stored_count} types updated in database\n\n`;

  if (result.classifications && Object.keys(result.classifications).length > 0) {
    output += '## Classification Distribution\n\n';
    Object.entries(result.classifications)
      .sort((a: any, b: any) => b[1] - a[1])  // Sort by count descending
      .forEach(([status, count]) => {
        output += `- **${status}**: ${count}\n`;
      });
    output += '\n';
  }

  if (result.sample_results && result.sample_results.length > 0) {
    output += '## Sample Results (Top 10)\n\n';
    output += '| Type | Status | Avg Grounding | Interpretation |\n';
    output += '|------|--------|---------------|----------------|\n';

    result.sample_results.forEach((sample: any) => {
      const avgGrounding = sample.stats?.avg_grounding !== undefined
        ? sample.stats.avg_grounding.toFixed(3)
        : '--';

      let interpretation = '';
      if (sample.epistemic_status === 'WELL_GROUNDED') {
        interpretation = '✓ Reliable';
      } else if (sample.epistemic_status === 'MIXED_GROUNDING') {
        interpretation = '⚠ Variable';
      } else if (sample.epistemic_status === 'WEAK_GROUNDING') {
        interpretation = '~ Emerging';
      } else if (sample.epistemic_status === 'POORLY_GROUNDED') {
        interpretation = '? Uncertain';
      } else if (sample.epistemic_status === 'CONTRADICTED') {
        interpretation = '✗ Refuted';
      } else if (sample.epistemic_status === 'INSUFFICIENT_DATA') {
        interpretation = '? Need data';
      } else {
        interpretation = '- Other';
      }

      output += `| ${sample.relationship_type} | ${sample.epistemic_status} | ${avgGrounding} | ${interpretation} |\n`;
    });
    output += '\n';
  }

  output += '## What This Means\n\n';
  output += 'Epistemic status measurement evaluates how well-established each vocabulary relationship type is based on:\n';
  output += '1. **Grounding strength** of target concepts (evidence support)\n';
  output += '2. **Consistency** across multiple samples (standard deviation)\n';
  output += '3. **Sample size** (measured vs total edges)\n\n';

  output += '**Key Insights:**\n';
  output += '- **WELL_GROUNDED types** represent well-established knowledge patterns (>80% net support)\n';
  output += '- **MIXED_GROUNDING types** show variable validation or mixed evidence (15-80% net support)\n';
  output += '- **WEAK_GROUNDING types** represent emerging knowledge (0-15% net support)\n';
  output += '- **POORLY_GROUNDED types** have uncertain validation (0-50% net contradiction)\n';
  output += '- **CONTRADICTED types** may represent refuted claims (>50% net contradiction)\n';
  output += '- **INSUFFICIENT_DATA types** need more document ingestion\n\n';

  output += '**Next Actions:**\n';
  output += '1. Review MIXED_GROUNDING types to identify knowledge gaps or dialectical patterns\n';
  output += '2. Use WELL_GROUNDED types for high-confidence reasoning and inference\n';
  output += '3. Investigate CONTRADICTED types to understand knowledge evolution\n';
  output += '4. Ingest more documents to move INSUFFICIENT_DATA types to measurable states\n';

  return output;
}

/**
 * Format source search results as markdown (ADR-068 Phase 5)
 *
 * Optimized for MCP/AI consumption - shows matched chunks with offsets
 * and related concepts extracted from those sources.
 */
export function formatSourceSearchResults(result: SourceSearchResponse): string {
  let output = `# Source Search: "${result.query}"\n\n`;
  output += `Found ${result.count} source passage(s) (threshold: ${(result.threshold_used || 0.7) * 100}%)\n\n`;

  if (result.count === 0) {
    output += 'No source passages found matching this query.\n\n';
    output += '**Tips:**\n';
    output += '- Source search uses text embeddings, not concept embeddings\n';
    output += '- Try broader queries or lower similarity thresholds\n';
    output += '- Use concept search to find concepts, then view their evidence\n';
    return output;
  }

  result.results.forEach((source, i) => {
    output += `## ${i + 1}. ${source.document} (para ${source.paragraph})\n\n`;
    output += `- **Source ID:** ${source.source_id}\n`;
    output += `- **Similarity:** ${(source.similarity * 100).toFixed(1)}%\n`;

    if (source.is_stale) {
      output += `- **Status:** ⚠ Stale embedding (source text changed since embedding)\n`;
    }

    output += `\n**Matched Chunk** [offset ${source.matched_chunk.start_offset}:${source.matched_chunk.end_offset}]:\n\n`;
    output += `> ${source.matched_chunk.chunk_text}\n\n`;

    if (source.full_text) {
      const truncated = source.full_text.length > 300
        ? source.full_text.substring(0, 300) + '...'
        : source.full_text;
      output += `**Full Context:**\n\n${truncated}\n\n`;
    }

    if (source.concepts && source.concepts.length > 0) {
      output += `**Concepts Extracted** (${source.concepts.length}):\n\n`;
      source.concepts.slice(0, 5).forEach(concept => {
        output += `- **${concept.label}** (${concept.concept_id})\n`;
        if (concept.description) {
          output += `  ${concept.description}\n`;
        }
        output += `  Evidence: "${concept.instance_quote}"\n`;
      });

      if (source.concepts.length > 5) {
        output += `\n... and ${source.concepts.length - 5} more concepts\n`;
      }
      output += '\n';
    }
  });

  output += '**Next Steps:**\n';
  output += '- Use concept IDs with `concept` tool (action: "details") to explore further\n';
  output += '- Use `concept` tool (action: "connect") to find relationships between concepts\n';
  output += '- Adjust similarity threshold if results are too broad or too narrow\n';

  return output;
}

/**
 * Format polarity axis analysis results as markdown (ADR-070)
 *
 * Optimized for MCP/AI consumption - shows axis definition, projections,
 * statistics, and grounding correlation patterns.
 */
export function formatPolarityAxisResults(result: any): string {
  let output = `# Polarity Axis Analysis\n\n`;

  // Axis definition
  output += `## Polarity Axis: ${result.axis.positive_pole.label} ↔ ${result.axis.negative_pole.label}\n\n`;

  output += `**Positive Pole:** ${result.axis.positive_pole.label}\n`;
  output += `  Grounding: ${formatGroundingStrength(result.axis.positive_pole.grounding)}\n`;
  output += `  ID: ${result.axis.positive_pole.concept_id}\n\n`;

  output += `**Negative Pole:** ${result.axis.negative_pole.label}\n`;
  output += `  Grounding: ${formatGroundingStrength(result.axis.negative_pole.grounding)}\n`;
  output += `  ID: ${result.axis.negative_pole.concept_id}\n\n`;

  output += `**Axis Magnitude:** ${result.axis.magnitude.toFixed(4)}\n`;

  const qualityLabel = result.axis.axis_quality === 'strong'
    ? '✓ Strong (poles are semantically distinct)'
    : '⚠ Weak (poles may be too similar)';
  output += `**Axis Quality:** ${qualityLabel}\n\n`;

  // Statistics
  output += `## Statistics\n\n`;
  output += `- **Total Concepts:** ${result.statistics.total_concepts}\n`;
  output += `- **Position Range:** [${result.statistics.position_range[0].toFixed(3)}, ${result.statistics.position_range[1].toFixed(3)}]\n`;
  output += `- **Mean Position:** ${result.statistics.mean_position.toFixed(3)} `;

  if (result.statistics.mean_position > 0.2) {
    output += '(skewed toward positive pole)\n';
  } else if (result.statistics.mean_position < -0.2) {
    output += '(skewed toward negative pole)\n';
  } else {
    output += '(balanced)\n';
  }

  output += `- **Mean Axis Distance:** ${result.statistics.mean_axis_distance.toFixed(3)} (orthogonal spread)\n\n`;

  // Direction distribution
  output += `**Direction Distribution:**\n`;
  output += `- Positive (>0.3): ${result.statistics.direction_distribution.positive} concepts\n`;
  output += `- Neutral (-0.3 to 0.3): ${result.statistics.direction_distribution.neutral} concepts\n`;
  output += `- Negative (<-0.3): ${result.statistics.direction_distribution.negative} concepts\n\n`;

  // Grounding correlation
  output += `## Grounding Correlation\n\n`;
  output += `**Pearson r:** ${result.grounding_correlation.pearson_r.toFixed(3)}\n`;
  output += `**p-value:** ${result.grounding_correlation.p_value.toFixed(4)}\n`;
  output += `**Interpretation:** ${result.grounding_correlation.interpretation}\n\n`;

  // Add practical interpretation
  const r = result.grounding_correlation.pearson_r;
  if (Math.abs(r) < 0.1) {
    output += `→ No correlation: Position and grounding are independent\n\n`;
  } else if (r > 0.3) {
    output += `→ Positive correlation: Concepts near positive pole tend to have higher grounding\n\n`;
  } else if (r < -0.3) {
    output += `→ Negative correlation: Concepts near negative pole tend to have higher grounding\n\n`;
  } else {
    output += `→ Weak correlation: Position and grounding are loosely related\n\n`;
  }

  // Projections (top concepts for each direction)
  if (result.projections && result.projections.length > 0) {
    output += `## Concept Projections (${result.projections.length} total)\n\n`;

    // Sort by position
    const sorted = [...result.projections].sort((a, b) => b.position - a.position);

    // Show top 5 positive
    const positive = sorted.filter(p => p.direction === 'positive').slice(0, 5);
    if (positive.length > 0) {
      output += `### Positive Direction (toward ${result.axis.positive_pole.label})\n\n`;
      positive.forEach((proj, i) => {
        output += `${i + 1}. **${proj.label}**\n`;
        output += `   Position: ${proj.position.toFixed(3)} | `;
        output += `Grounding: ${formatGroundingStrength(proj.grounding)} | `;
        output += `Axis distance: ${proj.axis_distance.toFixed(4)}\n`;
        output += `   ID: ${proj.concept_id}\n`;
      });
      output += '\n';
    }

    // Show neutral concepts (if any)
    const neutral = sorted.filter(p => p.direction === 'neutral').slice(0, 3);
    if (neutral.length > 0) {
      output += `### Neutral (balanced between poles)\n\n`;
      neutral.forEach((proj, i) => {
        output += `${i + 1}. **${proj.label}**\n`;
        output += `   Position: ${proj.position.toFixed(3)} | `;
        output += `Grounding: ${formatGroundingStrength(proj.grounding)} | `;
        output += `Axis distance: ${proj.axis_distance.toFixed(4)}\n`;
        output += `   ID: ${proj.concept_id}\n`;
      });
      output += '\n';
    }

    // Show top 5 negative
    const negative = sorted.filter(p => p.direction === 'negative').slice(-5).reverse();
    if (negative.length > 0) {
      output += `### Negative Direction (toward ${result.axis.negative_pole.label})\n\n`;
      negative.forEach((proj, i) => {
        output += `${i + 1}. **${proj.label}**\n`;
        output += `   Position: ${proj.position.toFixed(3)} | `;
        output += `Grounding: ${formatGroundingStrength(proj.grounding)} | `;
        output += `Axis distance: ${proj.axis_distance.toFixed(4)}\n`;
        output += `   ID: ${proj.concept_id}\n`;
      });
      output += '\n';
    }
  }

  output += `## How to Use This Analysis\n\n`;
  output += `**Understanding Positions:**\n`;
  output += `- Position closer to +1.0 → More aligned with "${result.axis.positive_pole.label}"\n`;
  output += `- Position closer to -1.0 → More aligned with "${result.axis.negative_pole.label}"\n`;
  output += `- Position near 0.0 → Balanced or orthogonal to this dimension\n\n`;

  output += `**Axis Distance (orthogonality):**\n`;
  output += `- Low distance → Concept lies close to the axis (well-explained by this dimension)\n`;
  output += `- High distance → Concept is orthogonal (other dimensions more relevant)\n\n`;

  output += `**Next Steps:**\n`;
  output += `- Use concept IDs with \`concept\` tool (action: "details") to explore individual concepts\n`;
  output += `- Use \`concept\` tool (action: "connect") to find paths between concepts on the axis\n`;
  output += `- Try different pole pairs to explore other semantic dimensions\n`;
  output += `- Compare grounding patterns across positions to identify reliability trends\n`;

  return output;
}

/**
 * Format document search results (ADR-084)
 */
export function formatDocumentSearchResults(result: any): string {
  let output = `# Document Search: "${result.query || 'documents'}"\n\n`;
  output += `Found ${result.total_matches} document(s)\n\n`;

  if (result.documents.length === 0) {
    output += 'No documents found matching this query.\n';
    return output;
  }

  result.documents.forEach((doc: any, i: number) => {
    output += `## ${i + 1}. ${doc.filename}\n\n`;
    output += `Document ID: ${doc.document_id}\n`;
    output += `Ontology: ${doc.ontology}\n`;
    output += `Similarity: ${(doc.best_similarity * 100).toFixed(1)}%\n`;
    output += `Source Chunks: ${doc.source_count}\n`;

    if (doc.concept_ids && doc.concept_ids.length > 0) {
      const conceptPreview = doc.concept_ids.slice(0, 5).join(', ');
      const more = doc.concept_ids.length > 5 ? ` (+${doc.concept_ids.length - 5} more)` : '';
      output += `Concepts: ${conceptPreview}${more}\n`;
    }

    output += '\n';
  });

  // Usage hints
  output += '## Next Steps\n\n';
  output += '- Use `document` tool with action "show" to view document content\n';
  output += '- Use `document` tool with action "concepts" to see all extracted concepts\n';
  output += '- Use `concept` tool to explore individual concepts in detail\n';

  return output;
}

/**
 * Format document list (ADR-084)
 */
export function formatDocumentList(result: any): string {
  let output = `# Documents\n\n`;
  output += `Showing ${result.documents.length} of ${result.total} documents\n\n`;

  if (result.documents.length === 0) {
    output += 'No documents found.\n';
    return output;
  }

  result.documents.forEach((doc: any, i: number) => {
    output += `${i + 1}. **${doc.filename}**\n`;
    output += `   - ID: ${doc.document_id.substring(0, 50)}...\n`;
    output += `   - Ontology: ${doc.ontology}\n`;
    output += `   - Type: ${doc.content_type || 'document'}\n`;
    output += `   - Sources: ${doc.source_count}, Concepts: ${doc.concept_count}\n`;
    output += '\n';
  });

  if (result.total > result.documents.length) {
    output += `Use offset=${result.offset + result.documents.length} to see more.\n`;
  }

  return output;
}

/**
 * Format document content (ADR-084)
 */
export function formatDocumentContent(result: any): string {
  let output = `# Document Content\n\n`;
  output += `Type: ${result.content_type}\n`;
  output += `Chunks: ${result.chunks.length}\n\n`;

  if (result.content_type === 'image') {
    if (result.content.prose) {
      output += '## Image Description\n\n';
      output += result.content.prose + '\n\n';
    }
    if (result.content.image) {
      output += `[Image data: ${result.content.image.length} bytes base64]\n`;
    }
  } else {
    if (result.content.document) {
      output += '## Content\n\n';
      output += result.content.document + '\n';
    } else if (result.content.error) {
      output += `Error: ${result.content.error}\n`;
    } else {
      output += 'No content available.\n';
    }
  }

  return output;
}

/**
 * Format document concepts (ADR-084)
 */
export function formatDocumentConcepts(result: any): string {
  let output = `# Concepts: ${result.filename}\n\n`;
  output += `Document: ${result.document_id}\n`;
  output += `Total: ${result.total} concept(s)\n\n`;

  if (result.concepts.length === 0) {
    output += 'No concepts found for this document.\n';
    return output;
  }

  result.concepts.forEach((concept: any, i: number) => {
    output += `${i + 1}. **${concept.name}**\n`;
    output += `   - ID: ${concept.concept_id}\n`;
    output += `   - Source: ${concept.source_id}\n`;
    output += `   - Instances: ${concept.instance_count}\n`;
    output += '\n';
  });

  // Usage hints
  output += '## Next Steps\n\n';
  output += '- Use `concept` tool with action "details" for full concept information\n';
  output += '- Use `concept` tool with action "connect" to find relationships between concepts\n';
  output += '- Or use `include_details: true` to get full details in one call\n';

  return output;
}

/**
 * Format document concepts with full details (ADR-084)
 * Used when include_details=true - fetches all concept info in one call
 */
// ============================================================================
// Graph CRUD Formatters (ADR-089 Phase 3a)
// ============================================================================

/**
 * Format a created/updated concept for MCP output
 */
export function formatGraphConceptResult(result: any, action: string): string {
  let output = `# ${action === 'create' ? 'Created' : action === 'edit' ? 'Updated' : 'Deleted'} Concept\n\n`;

  if (action === 'delete') {
    output += `Concept deleted successfully.\n`;
    return output;
  }

  output += `**Label:** ${result.label}\n`;
  output += `**ID:** ${result.concept_id}\n`;
  output += `**Ontology:** ${result.ontology || 'N/A'}\n`;

  if (result.description) {
    output += `**Description:** ${result.description}\n`;
  }

  if (result.search_terms && result.search_terms.length > 0) {
    output += `**Search Terms:** ${result.search_terms.join(', ')}\n`;
  }

  output += `**Creation Method:** ${result.creation_method || 'mcp'}\n`;
  output += `**Has Embedding:** ${result.has_embedding ? 'Yes' : 'Pending'}\n`;

  if (result.matched_existing) {
    output += `\n⚠️ **Matched Existing Concept** - no new concept created\n`;
  }

  return output;
}

/**
 * Format a created/updated edge for MCP output
 */
export function formatGraphEdgeResult(result: any, action: string): string {
  let output = `# ${action === 'create' ? 'Created' : action === 'edit' ? 'Updated' : 'Deleted'} Edge\n\n`;

  if (action === 'delete') {
    output += `Edge deleted successfully.\n`;
    return output;
  }

  output += `**Relationship:** ${result.from_label || result.from_concept_id} → [${result.relationship_type}] → ${result.to_label || result.to_concept_id}\n\n`;
  output += `**From Concept:** ${result.from_concept_id}\n`;
  output += `**To Concept:** ${result.to_concept_id}\n`;
  output += `**Type:** ${result.relationship_type}\n`;
  output += `**Category:** ${result.category}\n`;
  output += `**Confidence:** ${(result.confidence * 100).toFixed(0)}%\n`;
  output += `**Source:** ${result.source}\n`;

  if (result.created_at) {
    output += `**Created:** ${result.created_at}\n`;
  }

  return output;
}

/**
 * Format concept list for MCP output
 */
export function formatGraphConceptList(result: any): string {
  let output = `# Concepts\n\n`;
  output += `Showing ${result.concepts.length} of ${result.total} concepts\n\n`;

  if (result.concepts.length === 0) {
    output += 'No concepts found matching the filters.\n';
    return output;
  }

  result.concepts.forEach((concept: any, i: number) => {
    output += `${i + 1}. **${concept.label}**\n`;
    output += `   - ID: ${concept.concept_id}\n`;
    if (concept.ontology) {
      output += `   - Ontology: ${concept.ontology}\n`;
    }
    if (concept.description) {
      const truncated = concept.description.length > 80
        ? concept.description.substring(0, 80) + '...'
        : concept.description;
      output += `   - Description: ${truncated}\n`;
    }
    output += `   - Method: ${concept.creation_method || 'unknown'}\n`;
    output += `   - Embedding: ${concept.has_embedding ? '✓' : '⏳'}\n`;
    output += '\n';
  });

  if (result.total > result.offset + result.concepts.length) {
    output += `Use offset=${result.offset + result.limit} to see more.\n`;
  }

  return output;
}

/**
 * Format edge list for MCP output
 */
export function formatGraphEdgeList(result: any): string {
  let output = `# Edges\n\n`;
  output += `Showing ${result.edges.length} of ${result.total} edges\n\n`;

  if (result.edges.length === 0) {
    output += 'No edges found matching the filters.\n';
    return output;
  }

  result.edges.forEach((edge: any, i: number) => {
    output += `${i + 1}. **${edge.relationship_type}**\n`;
    output += `   - From: ${edge.from_concept_id}\n`;
    output += `   - To: ${edge.to_concept_id}\n`;
    output += `   - Category: ${edge.category}\n`;
    output += `   - Confidence: ${(edge.confidence * 100).toFixed(0)}%\n`;
    output += `   - Source: ${edge.source}\n`;
    output += '\n';
  });

  if (result.total > result.offset + result.edges.length) {
    output += `Use offset=${result.offset + result.limit} to see more.\n`;
  }

  return output;
}

/**
 * Format batch create response for MCP output
 */
export function formatGraphBatchResult(result: any): string {
  let output = `# Batch Create Results\n\n`;

  output += `## Summary\n\n`;
  output += `- **Concepts Created:** ${result.concepts_created}\n`;
  output += `- **Concepts Matched:** ${result.concepts_matched}\n`;
  output += `- **Edges Created:** ${result.edges_created}\n`;

  if (result.errors && result.errors.length > 0) {
    output += `- **Errors:** ${result.errors.length}\n`;
  }

  if (result.concept_results && result.concept_results.length > 0) {
    output += `\n## Concept Results\n\n`;
    result.concept_results.forEach((item: any, i: number) => {
      const statusIcon = item.status === 'created' ? '✓' : item.status === 'matched' ? '⊘' : '✗';
      output += `${i + 1}. ${statusIcon} **${item.label}** - ${item.status}`;
      if (item.id) {
        output += ` (${item.id})`;
      }
      if (item.error) {
        output += ` - ${item.error}`;
      }
      output += '\n';
    });
  }

  if (result.edge_results && result.edge_results.length > 0) {
    output += `\n## Edge Results\n\n`;
    result.edge_results.forEach((item: any, i: number) => {
      const statusIcon = item.status === 'created' ? '✓' : item.status === 'error' ? '✗' : '⊘';
      output += `${i + 1}. ${statusIcon} **${item.label}** - ${item.status}`;
      if (item.id) {
        output += ` (${item.id})`;
      }
      if (item.error) {
        output += ` - ${item.error}`;
      }
      output += '\n';
    });
  }

  if (result.errors && result.errors.length > 0) {
    output += `\n## Errors\n\n`;
    result.errors.forEach((error: string, i: number) => {
      output += `${i + 1}. ${error}\n`;
    });
  }

  return output;
}

/**
 * Queue operation result type for formatter
 */
interface QueueOperationResult {
  index: number;
  status: 'ok' | 'error';
  op: string;
  entity: string;
  label?: string;
  id?: string;
  relationship?: string;
  count?: number;
  total?: number;
  matched_existing?: boolean;
  concepts?: Array<{ id: string; label: string }>;
  edges?: Array<{ from: string; type: string; to: string }>;
  error?: string;
}

/**
 * Queue execution result type for formatter
 */
interface QueueExecutionResult {
  results: QueueOperationResult[];
  stopIndex: number;
  successCount: number;
  errorCount: number;
}

/**
 * Format queue execution results for MCP output
 */
export function formatGraphQueueResult(
  queueResult: QueueExecutionResult,
  totalOperations: number
): string {
  const { results, stopIndex, successCount, errorCount } = queueResult;

  let output = `# Queue Results\n\n`;
  output += `**Executed:** ${results.length} of ${totalOperations} operations\n`;
  output += `**Success:** ${successCount} | **Errors:** ${errorCount}\n`;
  if (stopIndex >= 0) {
    output += `**Stopped at:** operation ${stopIndex + 1} (error)\n`;
  }
  output += '\n## Operations\n\n';

  results.forEach((r) => {
    const icon = r.status === 'ok' ? '✓' : '✗';
    output += `${r.index}. ${icon} **${r.op} ${r.entity}**`;
    if (r.status === 'ok') {
      if (r.label) output += ` - ${r.label}`;
      if (r.id) output += ` (${r.id})`;
      if (r.relationship) output += ` - ${r.relationship}`;
      if (r.count !== undefined) output += ` - ${r.count}/${r.total} results`;
      if (r.matched_existing) output += ' ⚠️ matched existing';
    } else {
      output += ` - ${r.error}`;
    }
    output += '\n';
  });

  // Include list results inline for convenience
  const listResults = results.filter((r) => r.status === 'ok' && r.op === 'list');
  if (listResults.length > 0) {
    output += '\n## List Results\n\n';
    listResults.forEach((r) => {
      output += `### Operation ${r.index}: ${r.entity} list\n\n`;
      if (r.entity === 'concept' && r.concepts) {
        r.concepts.slice(0, 10).forEach((c, i) => {
          output += `${i + 1}. ${c.label} (${c.id})\n`;
        });
        if (r.concepts.length > 10) {
          output += `... and ${r.concepts.length - 10} more\n`;
        }
      } else if (r.entity === 'edge' && r.edges) {
        r.edges.slice(0, 10).forEach((e, i) => {
          output += `${i + 1}. ${e.from} -[${e.type}]-> ${e.to}\n`;
        });
        if (r.edges.length > 10) {
          output += `... and ${r.edges.length - 10} more\n`;
        }
      }
      output += '\n';
    });
  }

  return output;
}

export function formatDocumentConceptsDetailed(docResult: any, conceptDetails: any[]): string {
  let output = `# Concepts: ${docResult.filename}\n\n`;
  output += `Document: ${docResult.document_id}\n`;
  output += `Total: ${conceptDetails.length} unique concept(s)\n\n`;

  if (conceptDetails.length === 0) {
    output += 'No concepts found for this document.\n';
    return output;
  }

  conceptDetails.forEach((concept: any, i: number) => {
    if (concept.error) {
      output += `## ${i + 1}. ${concept.label}\n\n`;
      output += `ID: ${concept.concept_id}\n`;
      output += `Status: Failed to load\n\n`;
      return;
    }

    output += `## ${i + 1}. ${concept.label}\n\n`;

    if (concept.description) {
      output += `${concept.description}\n\n`;
    }

    output += `ID: ${concept.concept_id}\n`;
    output += `Documents: ${concept.documents?.join(', ') || 'Unknown'}\n`;
    output += `Evidence: ${concept.instances?.length || 0} instances\n`;

    // Grounding with confidence
    if (concept.grounding_strength !== undefined || concept.grounding_display) {
      const grounding = concept.grounding_display || formatGroundingStrength(concept.grounding_strength);
      output += `Grounding: ${grounding}\n`;
    }

    // Sample evidence (max 2)
    if (concept.instances && concept.instances.length > 0) {
      output += `\n### Evidence Samples\n\n`;
      concept.instances.slice(0, 2).forEach((inst: any, idx: number) => {
        const truncated = inst.quote.length > 120 ? inst.quote.substring(0, 120) + '...' : inst.quote;
        output += `${idx + 1}. ${inst.document} (para ${inst.paragraph}):\n`;
        output += `   "${truncated}"\n`;
      });
      if (concept.instances.length > 2) {
        output += `   ... and ${concept.instances.length - 2} more\n`;
      }
    }

    // Relationships (max 5)
    if (concept.relationships && concept.relationships.length > 0) {
      output += `\n### Relationships (${concept.relationships.length})\n\n`;
      concept.relationships.slice(0, 5).forEach((rel: any) => {
        const confidence = rel.confidence ? ` (${(rel.confidence * 100).toFixed(0)}%)` : '';
        output += `${rel.rel_type} -> ${rel.to_label}${confidence}\n`;
      });
      if (concept.relationships.length > 5) {
        output += `... and ${concept.relationships.length - 5} more\n`;
      }
    }

    output += '\n---\n\n';
  });

  return output;
}
