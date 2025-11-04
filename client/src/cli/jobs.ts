/**
 * Job management commands
 */

import { Command } from 'commander';
import chalk from 'chalk';
import { createClientFromEnv } from '../api/client';
import { JobStatus } from '../types';
import * as colors from './colors';
import { Table } from '../lib/table';
import { setCommandHelp } from './help-formatter';

export const jobsCommand = setCommandHelp(
  new Command('job'),
  'Manage and monitor ingestion jobs',
  'Manage and monitor ingestion jobs through their lifecycle (pending → approval → processing → completed/failed)'
)
  .alias('jobs')  // Plural alias for backwards compatibility
  .showHelpAfterError('(add --help for additional information)')
  .showSuggestionAfterError();

// Get job status
jobsCommand
  .command('status <job-id>')
  .description('Get detailed status information for a job (progress, costs, errors) - use --watch to poll until completion')
  .showHelpAfterError()
  .option('-w, --watch', 'Watch job until completion (polls every few seconds)', false)
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

// Helper function to display jobs list using Table utility
async function displayJobsList(status?: string, clientId?: string, limit: number = 20, fullId: boolean = false, offset: number = 0) {
  const client = createClientFromEnv();
  const jobs = await client.listJobs(status, clientId, limit, offset);

  if (jobs.length === 0) {
    console.log(colors.status.dim('\nNo jobs found\n'));
    return;
  }

  // Create table with dynamic configuration
  const table = new Table<JobStatus>({
    columns: [
      {
        header: 'Job ID',
        field: 'job_id',
        type: 'job_id',
        width: 'flex',
        priority: 3,
        maxWidth: fullId ? 40 : 30,
        minWidth: fullId ? 38 : 20
      },
      {
        header: 'Source',
        field: (job) => job.source_path || job.filename || '-',
        type: 'text',
        width: 'flex',
        priority: 1,
        customFormat: (source, job) => {
          if (!source || source === '-') return colors.status.dim('-');
          // Show full path if available, otherwise just filename
          return source;
        },
        truncate: true
      },
      {
        header: 'User',
        field: 'username',
        type: 'user',
        width: 12,
        customFormat: (username) => username || 'unknown',
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
        priority: 2,
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
          // Special case: show icons for terminal states
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

  // Render table
  table.print(jobs);

  // Helpful tip
  if (!fullId && jobs.length > 0) {
    console.log(colors.status.dim('Tip: Use --full-id to show complete job IDs\n'));
  }
}

// List command with subcommands
const listCommand = new Command('list')
  .description('List recent jobs with optional filtering by status or user - includes subcommands for common filters')
  .option('-s, --status <status>', 'Filter by status (pending|awaiting_approval|approved|queued|processing|completed|failed|cancelled)')
  .option('-c, --client <user-id>', 'Filter by user ID (view specific user\'s jobs)')
  .option('-l, --limit <n>', 'Maximum jobs to return (max: 500, default: 100)', '100')
  .option('-o, --offset <n>', 'Number of jobs to skip for pagination (default: 0)', '0')
  .option('--full-id', 'Show full job IDs without truncation', false)
  .showHelpAfterError()
  .action(async (options) => {
    try {
      const limit = parseInt(options.limit);
      const offset = parseInt(options.offset);
      await displayJobsList(options.status, options.client, limit, options.fullId, offset);
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
  .option('-c, --client <user-id>', 'Filter by user ID')
  .option('-l, --limit <n>', 'Maximum jobs to return', '20')
  .option('--full-id', 'Show full job IDs (no truncation)', false)
  .action(async (options) => {
    try {
      console.log(chalk.blue('Jobs awaiting approval:\n'));
      await displayJobsList('awaiting_approval', options.client, parseInt(options.limit), options.fullId);
    } catch (error: any) {
      console.error(chalk.red('✗ Failed to list jobs'));
      console.error(chalk.red(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

listCommand
  .command('approved')
  .description('List approved jobs (queued or processing)')
  .option('-c, --client <user-id>', 'Filter by user ID')
  .option('-l, --limit <n>', 'Maximum jobs to return', '20')
  .option('--full-id', 'Show full job IDs (no truncation)', false)
  .action(async (options) => {
    try {
      console.log(chalk.blue('Approved jobs:\n'));
      await displayJobsList('approved', options.client, parseInt(options.limit), options.fullId);
    } catch (error: any) {
      console.error(chalk.red('✗ Failed to list jobs'));
      console.error(chalk.red(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

listCommand
  .command('done')
  .description('List completed jobs')
  .option('-c, --client <user-id>', 'Filter by user ID')
  .option('-l, --limit <n>', 'Maximum jobs to return', '20')
  .option('--full-id', 'Show full job IDs (no truncation)', false)
  .action(async (options) => {
    try {
      console.log(chalk.green('Completed jobs:\n'));
      await displayJobsList('completed', options.client, parseInt(options.limit), options.fullId);
    } catch (error: any) {
      console.error(chalk.red('✗ Failed to list jobs'));
      console.error(chalk.red(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

listCommand
  .command('failed')
  .description('List failed jobs')
  .option('-c, --client <user-id>', 'Filter by user ID')
  .option('-l, --limit <n>', 'Maximum jobs to return', '20')
  .option('--full-id', 'Show full job IDs (no truncation)', false)
  .action(async (options) => {
    try {
      console.log(chalk.red('Failed jobs:\n'));
      await displayJobsList('failed', options.client, parseInt(options.limit), options.fullId);
    } catch (error: any) {
      console.error(chalk.red('✗ Failed to list jobs'));
      console.error(chalk.red(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

listCommand
  .command('cancelled')
  .description('List cancelled jobs')
  .option('-c, --client <user-id>', 'Filter by user ID')
  .option('-l, --limit <n>', 'Maximum jobs to return', '20')
  .option('--full-id', 'Show full job IDs (no truncation)', false)
  .action(async (options) => {
    try {
      console.log(chalk.yellow('Cancelled jobs:\n'));
      await displayJobsList('cancelled', options.client, parseInt(options.limit), options.fullId);
    } catch (error: any) {
      console.error(chalk.red('✗ Failed to list jobs'));
      console.error(chalk.red(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

// Add list command to jobs
jobsCommand.addCommand(listCommand);

// Approve job(s) (ADR-014)
const approveCommand = new Command('approve')
  .description('Approve jobs for processing (ADR-014 approval workflow) - single job, batch pending, or filter by status')
  .showHelpAfterError();

// Approve single job
approveCommand
  .command('job <job-id>')
  .description('Approve a specific job by ID after reviewing cost estimates')
  .action(async (jobId: string) => {
    try {
      const client = createClientFromEnv();
      console.log(chalk.blue(`Approving job ${jobId}...`));
      const result = await client.approveJob(jobId);

      console.log(chalk.green('✓ Job approved'));
      console.log(chalk.gray(`  Status: ${result.status}`));
      console.log(chalk.gray(`\nMonitor: ${chalk.cyan(`kg jobs status ${jobId} --watch`)}`));
    } catch (error: any) {
      console.error(chalk.red('✗ Failed to approve job'));
      console.error(chalk.red(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

// Approve all pending jobs
approveCommand
  .command('pending')
  .description('Approve all jobs awaiting approval (batch operation with confirmation)')
  .option('-c, --client <user-id>', 'Filter by user ID')
  .option('-l, --limit <n>', 'Maximum jobs to approve (default: 100)', '100')
  .action(async (options) => {
    try {
      const client = createClientFromEnv();

      console.log(chalk.blue('Finding jobs awaiting approval...\n'));
      const jobs = await client.listJobs('awaiting_approval', options.client, parseInt(options.limit));

      if (jobs.length === 0) {
        console.log(chalk.gray('No pending jobs found'));
        return;
      }

      console.log(chalk.blue(`Found ${jobs.length} pending job(s):\n`));

      let approved = 0;
      let failed = 0;

      for (const job of jobs) {
        try {
          await client.approveJob(job.job_id);
          console.log(chalk.green(`✓ Approved: ${job.job_id.substring(0, 12)}... (${job.ontology || 'unknown'})`));
          approved++;
        } catch (error: any) {
          console.log(chalk.red(`✗ Failed: ${job.job_id.substring(0, 12)}... - ${error.message}`));
          failed++;
        }
      }

      console.log(chalk.blue(`\nSummary: ${approved} approved, ${failed} failed`));
      console.log(chalk.gray(`\nMonitor jobs: ${chalk.cyan('kg jobs list')}`));
    } catch (error: any) {
      console.error(chalk.red('✗ Failed to approve pending jobs'));
      console.error(chalk.red(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

// Legacy: approve with ID or filter
approveCommand
  .command('filter <status>')
  .description('Approve all jobs matching status filter')
  .option('-c, --client <user-id>', 'Filter by user ID')
  .action(async (statusFilter: string, options) => {
      try {
        const client = createClientFromEnv();

        const statusMap: Record<string, string> = {
          'pending': 'awaiting_approval',
          'awaiting': 'awaiting_approval',
        };
        const status = statusMap[statusFilter] || statusFilter;

        console.log(chalk.blue(`Finding jobs with status: ${status}...\n`));
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
            console.log(chalk.green(`✓ Approved: ${job.job_id.substring(0, 12)}... (${job.ontology || 'unknown'})`));
            approved++;
          } catch (error: any) {
            console.log(chalk.red(`✗ Failed: ${job.job_id.substring(0, 12)}... - ${error.message}`));
            failed++;
          }
        }

        console.log(chalk.blue(`\nSummary: ${approved} approved, ${failed} failed`));
      } catch (error: any) {
        console.error(chalk.red('✗ Failed to approve jobs'));
        console.error(chalk.red(error.response?.data?.detail || error.message));
        process.exit(1);
      }
    });

jobsCommand.addCommand(approveCommand);

// Cancel job(s)
jobsCommand
  .command('cancel <job-id-or-filter>')
  .description('Cancel a specific job by ID or batch cancel using filters (all, pending, running, queued, approved)')
  .showHelpAfterError()
  .option('-c, --client <user-id>', 'Filter by user ID for batch operations')
  .option('-l, --limit <n>', 'Maximum jobs to cancel for safety (default: 100)', '100')
  .action(async (jobIdOrFilter: string, options) => {
    try {
      const client = createClientFromEnv();
      const limit = parseInt(options.limit);

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
        const statusMap: Record<string, string | undefined> = {
          'all': undefined,  // No filter = all jobs
          'pending': 'awaiting_approval',
          'awaiting': 'awaiting_approval',
          'approved': 'approved',
          'queued': 'queued',
          'running': 'processing',
          'processing': 'processing',
        };

        const filter = jobIdOrFilter.toLowerCase();

        // Check if it's a known filter
        if (!(filter in statusMap)) {
          console.error(chalk.red(`✗ Unknown filter: "${jobIdOrFilter}"`));
          console.error(chalk.gray('\nSupported filters:'));
          console.error(chalk.gray('  all        - All cancellable jobs'));
          console.error(chalk.gray('  pending    - Jobs awaiting approval'));
          console.error(chalk.gray('  approved   - Approved jobs (not yet started)'));
          console.error(chalk.gray('  queued     - Queued jobs'));
          console.error(chalk.gray('  running    - Currently processing jobs'));
          process.exit(1);
        }

        const status = statusMap[filter];

        const filterDisplay = status || 'all cancellable jobs';
        console.log(chalk.blue(`Finding ${filterDisplay}...`));
        const jobs = await client.listJobs(status, options.client, limit);

        if (jobs.length === 0) {
          console.log(chalk.gray(`No jobs found matching filter: ${jobIdOrFilter}`));
          return;
        }

        // Filter to only cancellable statuses (not completed, failed, or already cancelled)
        const cancellableStatuses = ['awaiting_approval', 'approved', 'queued', 'processing'];
        const cancellableJobs = jobs.filter(j => cancellableStatuses.includes(j.status));

        if (cancellableJobs.length === 0) {
          console.log(chalk.yellow(`Found ${jobs.length} job(s), but none are cancellable`));
          console.log(chalk.gray('Only jobs in these states can be cancelled: awaiting_approval, approved, queued, processing'));
          return;
        }

        if (cancellableJobs.length < jobs.length) {
          console.log(chalk.yellow(`Found ${jobs.length} job(s), ${cancellableJobs.length} are cancellable\n`));
        } else {
          console.log(chalk.blue(`Found ${cancellableJobs.length} job(s). Cancelling...\n`));
        }

        let cancelled = 0;
        let failed = 0;

        for (const job of cancellableJobs) {
          try {
            await client.cancelJob(job.job_id);
            console.log(chalk.yellow(`✓ Cancelled: ${job.job_id.substring(0, 12)}... (${job.status}) - ${job.ontology || 'N/A'}`));
            cancelled++;
          } catch (error: any) {
            const errorMsg = error.response?.data?.detail || error.message || 'Unknown error';
            console.log(chalk.red(`✗ Failed: ${job.job_id.substring(0, 12)}... - ${errorMsg}`));
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

// Clear all jobs
jobsCommand
  .command('clear')
  .description('Clear ALL jobs from database - DESTRUCTIVE operation requiring --confirm flag (use for dev/testing cleanup)')
  .option('--confirm', 'Confirm deletion (REQUIRED for safety)', false)
  .showHelpAfterError()
  .action(async (options) => {
    try {
      if (!options.confirm) {
        console.error(chalk.red('✗ Confirmation required'));
        console.error(chalk.yellow('\n⚠️  This will DELETE ALL jobs from the database!'));
        console.error(chalk.gray('\nTo confirm, run: ') + chalk.cyan('kg jobs clear --confirm'));
        process.exit(1);
      }

      const client = createClientFromEnv();

      console.log(chalk.yellow('\n⚠️  Clearing ALL jobs from database...'));
      const result = await client.clearAllJobs(true);

      console.log(chalk.green(`\n✓ ${result.message}`));
      console.log(chalk.gray(`  Jobs deleted: ${result.jobs_deleted}\n`));
    } catch (error: any) {
      console.error(chalk.red('✗ Failed to clear jobs'));
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
  // Format job status with icons
  let statusDisplay: string = job.status;
  switch (job.status) {
    case 'completed':
      statusDisplay = colors.status.success('✓ completed');
      break;
    case 'failed':
      statusDisplay = colors.status.error('✗ failed');
      break;
    case 'processing':
      statusDisplay = colors.status.info('⚙ processing');
      break;
    case 'approved':
      statusDisplay = colors.status.success('✓ approved');
      break;
    case 'awaiting_approval':
      statusDisplay = colors.status.warning('⏸ awaiting approval');
      break;
    case 'pending':
      statusDisplay = colors.status.dim('○ pending');
      break;
    case 'queued':
      statusDisplay = colors.status.info('⋯ queued');
      break;
    case 'cancelled':
      statusDisplay = colors.status.dim('⊗ cancelled');
      break;
    default:
      statusDisplay = colors.status.dim(job.status);
  }
  console.log(`  Status: ${statusDisplay}`);

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

