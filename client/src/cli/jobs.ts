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
              process.stdout.write(
                chalk.blue(`Processing: ${p.percent}% `) +
                chalk.gray(`(${p.chunks_processed}/${p.chunks_total} chunks)`)
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

// List jobs
jobsCommand
  .command('list')
  .description('List recent jobs')
  .option('-s, --status <status>', 'Filter by status (queued|processing|completed|failed|cancelled)')
  .option('-l, --limit <n>', 'Maximum jobs to return', '20')
  .action(async (options) => {
    try {
      const client = createClientFromEnv();

      const jobs = await client.listJobs(options.status, parseInt(options.limit));

      if (jobs.length === 0) {
        console.log(chalk.gray('No jobs found'));
        return;
      }

      // Build table
      const data = [
        ['Job ID', 'Type', 'Status', 'Ontology', 'Created', 'Progress'],
      ];

      for (const job of jobs) {
        const progress = getProgressString(job);
        const created = new Date(job.created_at).toLocaleString();

        data.push([
          job.job_id.substring(0, 12) + '...',
          job.job_type,
          colorizeStatus(job.status),
          job.ontology || '-',
          created,
          progress,
        ]);
      }

      console.log(table(data));
      console.log(chalk.gray(`\nShowing ${jobs.length} job(s)`));
    } catch (error: any) {
      console.error(chalk.red('✗ Failed to list jobs'));
      console.error(chalk.red(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

// Cancel job
jobsCommand
  .command('cancel <job-id>')
  .description('Cancel a queued job')
  .action(async (jobId: string) => {
    try {
      const client = createClientFromEnv();

      console.log(chalk.blue(`Cancelling job ${jobId}...`));
      const result = await client.cancelJob(jobId);

      if (result.cancelled) {
        console.log(chalk.green('✓ Job cancelled'));
      } else {
        console.log(chalk.yellow('⚠ Job could not be cancelled'));
      }
    } catch (error: any) {
      console.error(chalk.red('✗ Failed to cancel job'));
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

  if (job.progress) {
    console.log(chalk.blue('\nProgress:'));
    const p = job.progress;
    if (p.percent !== undefined) {
      console.log(chalk.gray(`  ${p.percent}% complete`));
    }
    if (p.chunks_total) {
      console.log(chalk.gray(`  Chunks: ${p.chunks_processed}/${p.chunks_total}`));
    }
    if (p.concepts_created) {
      console.log(chalk.gray(`  Concepts: ${p.concepts_created}`));
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
    case 'queued':
      return chalk.yellow(status);
    case 'cancelled':
      return chalk.gray(status);
    default:
      return status;
  }
}
