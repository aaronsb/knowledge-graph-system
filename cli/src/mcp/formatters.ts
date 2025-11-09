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

    if (concept.grounding_strength !== undefined && concept.grounding_strength !== null) {
      output += `Grounding: ${formatGroundingStrength(concept.grounding_strength)}\n`;
    }

    if (concept.diversity_score !== undefined && concept.diversity_score !== null && concept.diversity_related_count !== undefined) {
      output += `Diversity: ${(concept.diversity_score * 100).toFixed(1)}% (${concept.diversity_related_count} related concepts)\n`;
    }

    if (concept.authenticated_diversity !== undefined && concept.authenticated_diversity !== null) {
      const authDiv = concept.authenticated_diversity;
      const sign = authDiv >= 0 ? '+' : '';
      const status = authDiv > 0.3 ? 'diverse support ✅' :
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
 */
export function formatConceptDetails(concept: ConceptDetailsResponse): string {
  let output = `# Concept: ${concept.label}\n\n`;
  if (concept.description) {
    output += `${concept.description}\n\n`;
  }
  output += `ID: ${concept.concept_id}\n`;
  output += `Search Terms: ${concept.search_terms.join(', ')}\n`;
  output += `Documents: ${concept.documents.join(', ')}\n`;

  if (concept.grounding_strength !== undefined && concept.grounding_strength !== null) {
    output += `Grounding: ${formatGroundingStrength(concept.grounding_strength)}\n`;
  }

  if (concept.diversity_score !== undefined && concept.diversity_score !== null && concept.diversity_related_count !== undefined) {
    output += `Diversity: ${(concept.diversity_score * 100).toFixed(1)}% (${concept.diversity_related_count} related concepts)\n`;
  }

  if (concept.authenticated_diversity !== undefined && concept.authenticated_diversity !== null) {
    const authDiv = concept.authenticated_diversity;
    const sign = authDiv >= 0 ? '+' : '';
    const status = authDiv > 0.3 ? 'diverse support ✅' :
                   authDiv > 0 ? 'some support ✓' :
                   authDiv > -0.3 ? 'weak contradiction ⚠' :
                   'diverse contradiction ❌';
    output += `Authenticated: ${sign}${(Math.abs(authDiv) * 100).toFixed(1)}% (${status})\n`;
  }

  output += `\n## Evidence (${concept.instances.length} instances)\n\n`;
  concept.instances.forEach((inst, i) => {
    output += `${i + 1}. ${inst.document} (para ${inst.paragraph}): "${inst.quote}"\n`;
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
      if (node.description) {
        output += `${node.description}\n`;
      }

      if (node.grounding_strength !== undefined && node.grounding_strength !== null) {
        output += `Grounding: ${formatGroundingStrength(node.grounding_strength)}\n`;
      }

      if (node.sample_evidence && node.sample_evidence.length > 0) {
        output += `Evidence samples:\n`;
        node.sample_evidence.forEach((inst, idx) => {
          const truncated = inst.quote.length > 100 ? inst.quote.substring(0, 100) + '...' : inst.quote;
          output += `  ${idx + 1}. ${inst.document} (para ${inst.paragraph}): "${truncated}"\n`;
          // ADR-057: Indicate if this evidence has an image
          if (inst.has_image && inst.source_id) {
            output += `     [IMAGE] get_source_image("${inst.source_id}")\n`;
          }
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
