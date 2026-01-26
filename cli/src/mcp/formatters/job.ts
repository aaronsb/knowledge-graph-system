/**
 * Job formatters
 */

import type { JobStatus } from '../../types/index.js';

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
