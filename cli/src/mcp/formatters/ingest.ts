/**
 * Ingest formatters
 */

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
