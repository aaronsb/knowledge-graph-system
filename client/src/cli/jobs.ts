/**
 * Job management commands
 */

import { Command } from 'commander';
import chalk from 'chalk';
import { table } from 'table';
import { createClientFromEnv } from '../api/client';
import { JobStatus } from '../types';

export const jobsCommand = new Command('jobs')
  .description('Manage and monitor ingestion jobs');

// Get job status
jobsCommand
  .command('status <job-id>')
  .description('Get job status')
  .option('-w, --watch', 'Watch job until completion', false)
  .action(async (jobId: string, options) => {
    try {
      const client = createClientFromEnv();

      if (options.watch) {
        // Poll until completion
        console.log(chalk.blue(`Watching job ${jobId}...`));
        console.log(chalk.gray('Press Ctrl+C to stop\n'));

        const finalJob = await client.pollJob(jobId, (job: JobStatus) => {
          // Clear line and rewrite
          process.stdout.write('\r\x1b[K');  // Clear line

          if (job.status === 'queued') {
            process.stdout.write(chalk.yellow(`Status: ${job.status}`));
          } else if (job.status === 'processing' && job.progress) {
            const p = job.progress;
            if (p.percent !== undefined) {
              const conceptsTotal = (p.concepts_created || 0) + (p.concepts_linked || 0);
              const hitRate = conceptsTotal > 0 ? Math.round((p.concepts_linked || 0) / conceptsTotal * 100) : 0;
              process.stdout.write(
                chalk.blue(`Processing: ${p.percent}% `) +
                chalk.gray(`(${p.chunks_processed}/${p.chunks_total} chunks) `) +
                chalk.gray(`| Concepts: ${conceptsTotal} (${hitRate}% reused) `) +
                chalk.gray(`| Rels: ${p.relationships_created || 0}`)
              );
            } else {
              process.stdout.write(chalk.blue(`Processing: ${p.stage}`));
            }
          }
        });

        console.log();  // New line after polling
        printJobStatus(finalJob);
      } else {
        // Single fetch
        const job = await client.getJob(jobId);
        printJobStatus(job);
      }
    } catch (error: any) {
      console.error(chalk.red('\n✗ Failed to get job status'));
      console.error(chalk.red(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

// Helper function to display jobs table
async function displayJobsList(status?: string, clientId?: string, limit: number = 20) {
  const client = createClientFromEnv();

  const jobs = await client.listJobs(status, clientId, limit);

  if (jobs.length === 0) {
    console.log(chalk.gray('No jobs found'));
    return;
  }

  // Build table
  const data = [
    ['Job ID', 'Client', 'Status', 'Ontology', 'Created', 'Progress'],
  ];

  for (const job of jobs) {
    const progress = getProgressString(job);
    const created = new Date(job.created_at).toLocaleString();

    data.push([
      job.job_id.substring(0, 12) + '...',
      (job.client_id || 'anonymous').substring(0, 10),
      colorizeStatus(job.status),
      job.ontology || '-',
      created,
      progress,
    ]);
  }

  console.log(table(data));
  console.log(chalk.gray(`\nShowing ${jobs.length} job(s)`));
}

// List command with subcommands
const listCommand = new Command('list')
  .description('List recent jobs (optionally filtered)')
  .option('-s, --status <status>', 'Filter by status (pending|awaiting_approval|approved|queued|processing|completed|failed|cancelled)')
  .option('-c, --client <client-id>', 'Filter by client ID (view specific user\'s jobs)')
  .option('-l, --limit <n>', 'Maximum jobs to return', '20')
  .action(async (options) => {
    try {
      await displayJobsList(options.status, options.client, parseInt(options.limit));
    } catch (error: any) {
      console.error(chalk.red('✗ Failed to list jobs'));
      console.error(chalk.red(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

// List subcommands for common filters
listCommand
  .command('pending')
  .description('List jobs awaiting approval')
  .option('-c, --client <client-id>', 'Filter by client ID')
  .option('-l, --limit <n>', 'Maximum jobs to return', '20')
  .action(async (options) => {
    try {
      console.log(chalk.blue('Jobs awaiting approval:\n'));
      await displayJobsList('awaiting_approval', options.client, parseInt(options.limit));
    } catch (error: any) {
      console.error(chalk.red('✗ Failed to list jobs'));
      console.error(chalk.red(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

listCommand
  .command('approved')
  .description('List approved jobs (queued or processing)')
  .option('-c, --client <client-id>', 'Filter by client ID')
  .option('-l, --limit <n>', 'Maximum jobs to return', '20')
  .action(async (options) => {
    try {
      console.log(chalk.blue('Approved jobs:\n'));
      await displayJobsList('approved', options.client, parseInt(options.limit));
    } catch (error: any) {
      console.error(chalk.red('✗ Failed to list jobs'));
      console.error(chalk.red(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

listCommand
  .command('done')
  .description('List completed jobs')
  .option('-c, --client <client-id>', 'Filter by client ID')
  .option('-l, --limit <n>', 'Maximum jobs to return', '20')
  .action(async (options) => {
    try {
      console.log(chalk.green('Completed jobs:\n'));
      await displayJobsList('completed', options.client, parseInt(options.limit));
    } catch (error: any) {
      console.error(chalk.red('✗ Failed to list jobs'));
      console.error(chalk.red(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

listCommand
  .command('failed')
  .description('List failed jobs')
  .option('-c, --client <client-id>', 'Filter by client ID')
  .option('-l, --limit <n>', 'Maximum jobs to return', '20')
  .action(async (options) => {
    try {
      console.log(chalk.red('Failed jobs:\n'));
      await displayJobsList('failed', options.client, parseInt(options.limit));
    } catch (error: any) {
      console.error(chalk.red('✗ Failed to list jobs'));
      console.error(chalk.red(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

listCommand
  .command('cancelled')
  .description('List cancelled jobs')
  .option('-c, --client <client-id>', 'Filter by client ID')
  .option('-l, --limit <n>', 'Maximum jobs to return', '20')
  .action(async (options) => {
    try {
      console.log(chalk.yellow('Cancelled jobs:\n'));
      await displayJobsList('cancelled', options.client, parseInt(options.limit));
    } catch (error: any) {
      console.error(chalk.red('✗ Failed to list jobs'));
      console.error(chalk.red(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

// Add list command to jobs
jobsCommand.addCommand(listCommand);

// Approve job(s) (ADR-014)
jobsCommand
  .command('approve <job-id-or-filter>')
  .description('Approve a job or all jobs matching filter (pending, approved, etc.)')
  .option('-c, --client <client-id>', 'Filter by client ID (for batch operations)')
  .action(async (jobIdOrFilter: string, options) => {
    try {
      const client = createClientFromEnv();

      // Check if it's a job ID or a status filter
      if (jobIdOrFilter.startsWith('job_')) {
        // Single job approval
        console.log(chalk.blue(`Approving job ${jobIdOrFilter}...`));
        const result = await client.approveJob(jobIdOrFilter);

        console.log(chalk.green('✓ Job approved'));
        console.log(chalk.gray(`  Status: ${result.status}`));
        console.log(chalk.gray('\nUse `kg jobs status --watch` to monitor progress'));
      } else {
        // Batch approval by status filter
        const statusMap: Record<string, string> = {
          'pending': 'awaiting_approval',
          'awaiting': 'awaiting_approval',
        };
        const status = statusMap[jobIdOrFilter] || jobIdOrFilter;

        console.log(chalk.blue(`Finding jobs with status: ${status}...`));
        const jobs = await client.listJobs(status, options.client, 100);

        if (jobs.length === 0) {
          console.log(chalk.gray('No jobs found matching filter'));
          return;
        }

        console.log(chalk.blue(`Found ${jobs.length} job(s). Approving...\n`));

        let approved = 0;
        let failed = 0;

        for (const job of jobs) {
          try {
            await client.approveJob(job.job_id);
            console.log(chalk.green(`✓ Approved: ${job.job_id.substring(0, 12)}... (${job.ontology})`));
            approved++;
          } catch (error: any) {
            console.log(chalk.red(`✗ Failed: ${job.job_id.substring(0, 12)}... - ${error.message}`));
            failed++;
          }
        }

        console.log(chalk.blue(`\nSummary: ${approved} approved, ${failed} failed`));
      }
    } catch (error: any) {
      console.error(chalk.red('✗ Failed to approve job(s)'));
      console.error(chalk.red(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

// Cancel job(s)
jobsCommand
  .command('cancel <job-id-or-filter>')
  .description('Cancel a job or all jobs matching filter (pending, queued, etc.)')
  .option('-c, --client <client-id>', 'Filter by client ID (for batch operations)')
  .action(async (jobIdOrFilter: string, options) => {
    try {
      const client = createClientFromEnv();

      // Check if it's a job ID or a status filter
      if (jobIdOrFilter.startsWith('job_')) {
        // Single job cancellation
        console.log(chalk.blue(`Cancelling job ${jobIdOrFilter}...`));
        const result = await client.cancelJob(jobIdOrFilter);

        if (result.cancelled) {
          console.log(chalk.green('✓ Job cancelled'));
        } else {
          console.log(chalk.yellow('⚠ Job could not be cancelled'));
        }
      } else {
        // Batch cancellation by status filter
        const statusMap: Record<string, string> = {
          'pending': 'awaiting_approval',
          'awaiting': 'awaiting_approval',
        };
        const status = statusMap[jobIdOrFilter] || jobIdOrFilter;

        console.log(chalk.blue(`Finding jobs with status: ${status}...`));
        const jobs = await client.listJobs(status, options.client, 100);

        if (jobs.length === 0) {
          console.log(chalk.gray('No jobs found matching filter'));
          return;
        }

        console.log(chalk.blue(`Found ${jobs.length} job(s). Cancelling...\n`));

        let cancelled = 0;
        let failed = 0;

        for (const job of jobs) {
          try {
            await client.cancelJob(job.job_id);
            console.log(chalk.yellow(`✓ Cancelled: ${job.job_id.substring(0, 12)}... (${job.ontology})`));
            cancelled++;
          } catch (error: any) {
            console.log(chalk.red(`✗ Failed: ${job.job_id.substring(0, 12)}... - ${error.message}`));
            failed++;
          }
        }

        console.log(chalk.blue(`\nSummary: ${cancelled} cancelled, ${failed} failed`));
      }
    } catch (error: any) {
      console.error(chalk.red('✗ Failed to cancel job(s)'));
      console.error(chalk.red(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

/**
 * Print detailed job status
 */
function printJobStatus(job: JobStatus) {
  console.log(chalk.blue('\nJob Status:'));
  console.log(chalk.gray(`  ID: ${job.job_id}`));
  console.log(chalk.gray(`  Type: ${job.job_type}`));
  console.log(`  Status: ${colorizeStatus(job.status)}`);

  if (job.ontology) {
    console.log(chalk.gray(`  Ontology: ${job.ontology}`));
  }

  console.log(chalk.gray(`  Created: ${new Date(job.created_at).toLocaleString()}`));

  if (job.started_at) {
    console.log(chalk.gray(`  Started: ${new Date(job.started_at).toLocaleString()}`));
  }

  if (job.completed_at) {
    console.log(chalk.gray(`  Completed: ${new Date(job.completed_at).toLocaleString()}`));

    const duration = (new Date(job.completed_at).getTime() - new Date(job.created_at).getTime()) / 1000;
    console.log(chalk.gray(`  Duration: ${duration.toFixed(1)}s`));
  }

  // ADR-014: Show analysis when available
  if (job.analysis) {
    console.log(chalk.blue('\nPre-Ingestion Analysis:'));

    const a = job.analysis;
    if (a.file_stats) {
      console.log(chalk.gray(`  File: ${a.file_stats.filename} (${a.file_stats.size_human})`));
      console.log(chalk.gray(`  Words: ${a.file_stats.word_count.toLocaleString()}`));
      console.log(chalk.gray(`  Estimated chunks: ~${a.file_stats.estimated_chunks}`));
    }

    if (a.cost_estimate) {
      console.log(chalk.blue('\n💰 Cost Estimate:'));
      const ce = a.cost_estimate;
      console.log(chalk.gray(`  Extraction (${ce.extraction.model}):`));
      console.log(chalk.gray(`    Tokens: ${ce.extraction.tokens_low.toLocaleString()}-${ce.extraction.tokens_high.toLocaleString()}`));
      console.log(chalk.gray(`    Cost: $${ce.extraction.cost_low.toFixed(2)}-$${ce.extraction.cost_high.toFixed(2)}`));

      console.log(chalk.gray(`  Embeddings (${ce.embeddings.model}):`));
      console.log(chalk.gray(`    Concepts: ${ce.embeddings.concepts_low}-${ce.embeddings.concepts_high}`));
      console.log(chalk.gray(`    Cost: $${ce.embeddings.cost_low.toFixed(2)}-$${ce.embeddings.cost_high.toFixed(2)}`));

      console.log(chalk.bold(`  Total: $${ce.total.cost_low.toFixed(2)}-$${ce.total.cost_high.toFixed(2)}`));
    }

    if (a.warnings && a.warnings.length > 0) {
      console.log(chalk.yellow('\n⚠️  Warnings:'));
      a.warnings.forEach((w: string) => console.log(chalk.yellow(`  • ${w}`)));
    }

    if (job.status === 'awaiting_approval') {
      console.log(chalk.blue('\n📌 Next Steps:'));
      console.log(chalk.gray(`  Approve: kg jobs approve ${job.job_id}`));
      console.log(chalk.gray(`  Cancel:  kg jobs cancel ${job.job_id}`));
    }
  }

  if (job.progress) {
    console.log(chalk.blue('\nProgress:'));
    const p = job.progress;
    if (p.percent !== undefined) {
      console.log(chalk.gray(`  ${p.percent}% complete`));
    }
    if (p.chunks_total) {
      console.log(chalk.gray(`  Chunks: ${p.chunks_processed}/${p.chunks_total}`));
    }

    // Concept statistics
    const conceptsNew = p.concepts_created || 0;
    const conceptsLinked = p.concepts_linked || 0;
    const conceptsTotal = conceptsNew + conceptsLinked;
    if (conceptsTotal > 0) {
      const hitRate = Math.round((conceptsLinked / conceptsTotal) * 100);
      console.log(chalk.gray(`  Concepts: ${conceptsTotal} total (${conceptsNew} new, ${conceptsLinked} reused)`));
      console.log(chalk.gray(`  Hit rate: ${hitRate}% (existing concepts reused)`));
    }

    if (p.instances_created) {
      console.log(chalk.gray(`  Instances: ${p.instances_created}`));
    }
    if (p.relationships_created) {
      console.log(chalk.gray(`  Relationships: ${p.relationships_created}`));
    }
  }

  if (job.result) {
    console.log(chalk.blue('\nResults:'));
    const r = job.result;

    if (r.stats) {
      console.log(chalk.gray(`  Chunks processed: ${r.stats.chunks_processed}`));
      console.log(chalk.gray(`  Concepts created: ${r.stats.concepts_created}`));
      console.log(chalk.gray(`  Sources created: ${r.stats.sources_created}`));
      console.log(chalk.gray(`  Relationships: ${r.stats.relationships_created}`));
    }

    if (r.cost) {
      console.log(chalk.blue('\nCost:'));
      console.log(chalk.gray(`  Extraction: ${r.cost.extraction}`));
      console.log(chalk.gray(`  Embeddings: ${r.cost.embeddings}`));
      console.log(chalk.gray(`  Total: ${r.cost.total}`));
    }
  }

  if (job.error) {
    console.log(chalk.red('\nError:'));
    console.log(chalk.red(`  ${job.error}`));
  }
}

/**
 * Get progress string for table display
 */
function getProgressString(job: JobStatus): string {
  if (job.status === 'completed') {
    return chalk.green('✓');
  }

  if (job.status === 'failed') {
    return chalk.red('✗');
  }

  if (job.status === 'cancelled') {
    return chalk.yellow('⚠');
  }

  if (job.progress?.percent !== undefined) {
    return `${job.progress.percent}%`;
  }

  return '-';
}

/**
 * Colorize status
 */
function colorizeStatus(status: string): string {
  switch (status) {
    case 'completed':
      return chalk.green(status);
    case 'failed':
      return chalk.red(status);
    case 'processing':
      return chalk.blue(status);
    case 'approved':
      return chalk.cyan(status);
    case 'awaiting_approval':
      return chalk.yellow(status);
    case 'pending':
      return chalk.gray(status);
    case 'queued':
      return chalk.yellow(status);
    case 'cancelled':
      return chalk.gray(status);
    default:
      return status;
  }
}
