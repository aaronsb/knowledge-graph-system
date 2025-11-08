/**
 * Example: Refactored Jobs List using Table utility with type-based formatting
 */

import { Table } from './table';
import { JobStatus } from '../types';

// Define the jobs table configuration once
export function createJobsTable(fullId: boolean = false) {
  return new Table<JobStatus>({
    columns: [
      {
        header: 'Job ID',
        field: 'job_id',
        type: 'job_id',
        width: 'flex',
        priority: 2,
        maxWidth: fullId ? 40 : 30,
        minWidth: fullId ? 38 : 20
      },
      {
        header: 'Client',
        field: 'client_id',
        type: 'user',
        width: 12,
        customFormat: (id) => id || 'anonymous',
        truncate: true
      },
      {
        header: 'Status',
        field: 'status',
        type: 'status',
        width: 18
      },
      {
        header: 'Ontology',
        field: 'ontology',
        type: 'heading',
        width: 'flex',
        priority: 1,
        customFormat: (name) => name || '-',
        truncate: true
      },
      {
        header: 'Created',
        field: 'created_at',
        type: 'timestamp',
        width: 18
      },
      {
        header: 'Progress',
        field: (job) => job.progress?.percent,
        type: 'progress',
        width: 10,
        customFormat: (percent, job) => {
          if (job.status === 'completed') return '✓';
          if (job.status === 'failed') return '✗';
          if (job.status === 'cancelled') return '⊗';
          return percent !== undefined ? String(percent) : '-';
        }
      }
    ],
    spacing: 2,
    showHeader: true,
    showSeparator: true
  });
}

// Usage:
// const table = createJobsTable(fullId);
// table.print(jobs);

// Or for other tables:

/*
// Ontology list table
const ontologyTable = new Table({
  columns: [
    { header: 'Ontology', field: 'ontology', type: 'heading', width: 'flex' },
    { header: 'Files', field: 'file_count', type: 'count', width: 10, align: 'right' },
    { header: 'Concepts', field: 'concept_count', type: 'count', width: 10, align: 'right' },
    { header: 'Sources', field: 'source_count', type: 'count', width: 10, align: 'right' }
  ]
});

// Search results table
const searchTable = new Table({
  columns: [
    { header: 'Concept', field: 'label', type: 'value', width: 'flex', priority: 2 },
    { header: 'ID', field: 'concept_id', type: 'concept_id', width: 25 },
    { header: 'Similarity', field: 'score', width: 12, align: 'right', customFormat: (s) => `${(s * 100).toFixed(1)}%` },
    { header: 'Evidence', field: 'evidence_count', type: 'count', width: 10, align: 'right' }
  ]
});

// Backup files table
const backupTable = new Table({
  columns: [
    { header: 'Filename', field: 'filename', type: 'value', width: 'flex', priority: 2 },
    { header: 'Size', field: 'size_mb', width: 12, align: 'right', customFormat: (mb) => `${mb.toFixed(2)} MB` },
    { header: 'Created', field: 'created', type: 'timestamp', width: 20 }
  ]
});
*/
