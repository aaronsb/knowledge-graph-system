/**
 * Ingestion commands
 */

import { Command } from 'commander';
import chalk from 'chalk';
import ora from 'ora';
import * as fs from 'fs';
import { createClientFromEnv } from '../api/client';
import { IngestRequest, JobStatus, DuplicateJobResponse, JobSubmitResponse } from '../types';

export const ingestCommand = new Command('ingest')
  .description('Ingest documents into the knowledge graph');

// Ingest file command
ingestCommand
  .command('file <path>')
  .description('Ingest a document file')
  .requiredOption('-o, --ontology <name>', 'Ontology/collection name')
  .option('-f, --force', 'Force re-ingestion even if duplicate', false)
  .option('--filename <name>', 'Override filename for tracking')
  .option('--target-words <n>', 'Target words per chunk', '1000')
  .option('--overlap-words <n>', 'Overlap between chunks', '200')
  .option('--no-wait', 'Submit and exit (don\'t wait for completion)')
  .action(async (path: string, options) => {
    try {
      // Validate file exists
      if (!fs.existsSync(path)) {
        console.error(chalk.red(`✗ File not found: ${path}`));
        process.exit(1);
      }

      const client = createClientFromEnv();

      const request: IngestRequest = {
        ontology: options.ontology,
        filename: options.filename,
        force: options.force,
        options: {
          target_words: parseInt(options.targetWords),
          overlap_words: parseInt(options.overlapWords),
        },
      };

      console.log(chalk.blue('Submitting document for ingestion...'));
      console.log(chalk.gray(`  File: ${path}`));
      console.log(chalk.gray(`  Ontology: ${request.ontology}`));

      const result = await client.ingestFile(path, request);

      // Check if duplicate
      if ('duplicate' in result && result.duplicate) {
        const dupResult = result as DuplicateJobResponse;
        console.log(chalk.yellow('\n⚠ Duplicate detected'));
        console.log(chalk.gray(`  Existing job: ${dupResult.existing_job_id}`));
        console.log(chalk.gray(`  Status: ${dupResult.status}`));
        console.log(chalk.gray(`\n  ${dupResult.message}`));

        if (dupResult.use_force) {
          console.log(chalk.gray(`  ${dupResult.use_force}`));
        }

        if (dupResult.result) {
          console.log(chalk.green('\n✓ Previous ingestion completed:'));
          printJobResult(dupResult.result);
        }

        return;
      }

      // Type narrowed: result is JobSubmitResponse
      const submitResult = result as JobSubmitResponse;
      console.log(chalk.green(`\n✓ Job submitted: ${submitResult.job_id}`));

      if (options.wait) {
        await pollJobWithProgress(client, submitResult.job_id);
      } else {
        console.log(chalk.gray(`\nPoll status with: kg jobs status ${submitResult.job_id}`));
      }
    } catch (error: any) {
      console.error(chalk.red('\n✗ Ingestion failed'));
      console.error(chalk.red(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

// Ingest text command
ingestCommand
  .command('text <text>')
  .description('Ingest raw text')
  .requiredOption('-o, --ontology <name>', 'Ontology/collection name')
  .option('-f, --force', 'Force re-ingestion even if duplicate', false)
  .option('--filename <name>', 'Filename for tracking', 'text_input')
  .option('--target-words <n>', 'Target words per chunk', '1000')
  .option('--no-wait', 'Submit and exit (don\'t wait for completion)')
  .action(async (text: string, options) => {
    try {
      const client = createClientFromEnv();

      const request: IngestRequest = {
        ontology: options.ontology,
        filename: options.filename,
        force: options.force,
        options: {
          target_words: parseInt(options.targetWords),
        },
      };

      console.log(chalk.blue('Submitting text for ingestion...'));
      console.log(chalk.gray(`  Text length: ${text.length} chars`));
      console.log(chalk.gray(`  Ontology: ${request.ontology}`));

      const result = await client.ingestText(text, request);

      // Check if duplicate
      if ('duplicate' in result && result.duplicate) {
        const dupResult = result as DuplicateJobResponse;
        console.log(chalk.yellow('\n⚠ Duplicate detected'));
        console.log(chalk.gray(`  ${dupResult.message}`));
        return;
      }

      // Type narrowed: result is JobSubmitResponse
      const submitResult = result as JobSubmitResponse;
      console.log(chalk.green(`\n✓ Job submitted: ${submitResult.job_id}`));

      if (options.wait) {
        await pollJobWithProgress(client, submitResult.job_id);
      } else {
        console.log(chalk.gray(`\nPoll status with: kg jobs status ${submitResult.job_id}`));
      }
    } catch (error: any) {
      console.error(chalk.red('\n✗ Ingestion failed'));
      console.error(chalk.red(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

/**
 * Poll job with progress spinner
 */
async function pollJobWithProgress(client: any, jobId: string) {
  const spinner = ora('Queued...').start();

  try {
    const finalJob = await client.pollJob(jobId, (job: JobStatus) => {
      if (job.status === 'processing' && job.progress) {
        const p = job.progress;
        if (p.percent !== undefined) {
          spinner.text = `Processing... ${p.percent}% (${p.chunks_processed}/${p.chunks_total} chunks, ${p.concepts_created || 0} concepts)`;
        } else {
          spinner.text = `Processing... ${p.stage}`;
        }
      } else if (job.status === 'queued') {
        spinner.text = 'Queued...';
      }
    });

    if (finalJob.status === 'completed') {
      spinner.succeed('Ingestion completed!');
      printJobResult(finalJob.result);
    } else if (finalJob.status === 'failed') {
      spinner.fail(`Ingestion failed: ${finalJob.error}`);
      process.exit(1);
    } else if (finalJob.status === 'cancelled') {
      spinner.warn('Ingestion cancelled');
    }
  } catch (error: any) {
    spinner.fail('Polling failed');
    throw error;
  }
}

/**
 * Print job result summary
 */
function printJobResult(result: any) {
  if (!result) return;

  console.log(chalk.blue('\nResults:'));
  if (result.stats) {
    console.log(chalk.gray(`  Chunks processed: ${result.stats.chunks_processed}`));
    console.log(chalk.gray(`  Concepts created: ${result.stats.concepts_created}`));
    console.log(chalk.gray(`  Sources created: ${result.stats.sources_created}`));
    console.log(chalk.gray(`  Relationships: ${result.stats.relationships_created}`));
  }

  if (result.cost) {
    console.log(chalk.blue('\nCost:'));
    console.log(chalk.gray(`  Extraction: ${result.cost.extraction}`));
    console.log(chalk.gray(`  Embeddings: ${result.cost.embeddings}`));
    console.log(chalk.gray(`  Total: ${result.cost.total}`));
  }
}
