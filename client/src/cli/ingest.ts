/**
 * Ingestion commands
 */

import { Command } from 'commander';
import chalk from 'chalk';
import ora from 'ora';
import * as fs from 'fs';
import * as nodePath from 'path';  // Renamed to avoid shadowing with parameter names
import * as os from 'os';  // ADR-051: Get hostname for provenance
import { createClientFromEnv } from '../api/client';
import { IngestRequest, JobStatus, DuplicateJobResponse, JobSubmitResponse } from '../types';
import { getConfig } from '../lib/config';

export const ingestCommand = new Command('ingest')
  .description('Ingest documents into the knowledge graph. Processes documents and extracts concepts, relationships, and evidence. Supports three modes: single file (one document), directory (batch ingest multiple files), and raw text (ingest text directly without a file). All operations create jobs (ADR-014) that can be monitored via "kg job" commands. Workflow: submit → chunk (semantic boundaries ~1000 words with overlap) → create job → optional approval → process (LLM extract, embed concepts, match existing, insert graph) → complete.')
  .showHelpAfterError('(add --help for additional information)')
  .showSuggestionAfterError();

// Ingest file command
ingestCommand
  .command('file <path>')
  .description('Ingest a single document file. Reads file, chunks text into semantic segments (~1000 words with overlap), submits job, returns job ID. Optionally waits for completion with -w. Supports text files (.txt, .md, .rst), PDF documents (.pdf), and other API-supported formats. By default: auto-approves (starts immediately), uses serial processing (chunks see previous concepts for clean deduplication, slower but higher quality), detects duplicates (file hash checked, returns existing job if found). Use --force to bypass duplicate detection, --parallel for faster processing of large documents (may create duplicate concepts), --no-approve to require manual approval (ADR-014), -w to wait for completion (polls until complete, shows progress).')
  .requiredOption('-o, --ontology <name>', 'Ontology/collection name (named collection or knowledge domain)')
  .option('-f, --force', 'Force re-ingestion even if duplicate (bypasses hash check, creates new job)', false)
  .option('--no-approve', 'Require manual approval before processing (job enters awaiting_approval state, must approve via "kg job approve <id>"). Default: auto-approve.')
  .option('--parallel', 'Process in parallel (all chunks simultaneously, chunks don\'t see each other, may duplicate concepts, faster). Default: serial (sequential, cleaner deduplication, recommended).', false)
  .option('--filename <name>', 'Override filename for tracking (displayed in ontology files list)')
  .option('--target-words <n>', 'Target words per chunk (actual may vary based on natural boundaries, range 500-2000 typically effective)', '1000')
  .option('--overlap-words <n>', 'Word overlap between chunks (provides context continuity, helps LLM understand cross-chunk relationships)', '200')
  .option('-w, --wait', 'Wait for job completion (polls status, shows progress, returns final results). Default: submit and exit (returns immediately with job ID, monitor via "kg job status <id>").', false)
  .showHelpAfterError()
  .action(async (path: string, options) => {
    try {
      // Validate file exists
      if (!fs.existsSync(path)) {
        console.error(chalk.red(`✗ File not found: ${path}`));
        process.exit(1);
      }

      const client = createClientFromEnv();
      const config = getConfig();

      // Default to auto-approve (options.approve is true by default due to --no-approve pattern)
      // Only require approval if user explicitly passes --no-approve flag
      const autoApprove = options.approve !== false;

      const request: IngestRequest = {
        ontology: options.ontology,
        filename: options.filename,
        force: options.force,
        auto_approve: autoApprove,  // ADR-014: Auto-approve flag
        processing_mode: options.parallel ? 'parallel' : 'serial',
        options: {
          target_words: parseInt(options.targetWords),
          overlap_words: parseInt(options.overlapWords),
        },
        // ADR-051: Source provenance metadata
        source_type: 'file',
        source_path: nodePath.resolve(path),  // Convert to absolute path
        source_hostname: os.hostname(),
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

      // If --wait flag provided, poll for completion
      if (options.wait) {
        await pollJobWithProgress(client, submitResult.job_id);
      } else {
        // Default: submit and exit (like walking away from the counter)
        console.log(chalk.gray(`\nMonitor progress: ${chalk.cyan(`kg jobs status ${submitResult.job_id} --watch`)}`));
      }
    } catch (error: any) {
      console.error(chalk.red('\n✗ Ingestion failed'));
      console.error(chalk.red(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

// Ingest directory command
ingestCommand
  .command('directory <dir>')
  .description('Ingest all matching files from a directory (batch processing). Scans directory for files matching patterns (default *.md *.txt), optionally recurses into subdirectories (-r with depth limit), groups files by ontology (single ontology via -o OR auto-create from subdirectory names via --directories-as-ontologies), and submits batch jobs. Use --dry-run to preview what would be ingested without submitting (checks duplicates, shows skip/submit counts). Directory-as-ontology mode: each subdirectory becomes separate ontology named after directory, useful for organizing knowledge domains by folder structure. Examples: "physics/" → "physics" ontology, "chemistry/organic/" → "organic" ontology.')
  .option('-o, --ontology <name>', 'Ontology/collection name (required unless --directories-as-ontologies). Single ontology receives all files.')
  .option('-p, --pattern <patterns...>', 'File patterns to match (glob patterns like *.md *.txt)', ['*.md', '*.txt'])
  .option('-r, --recurse', 'Recursively scan subdirectories. Use "--recurse --depth all" for unlimited depth, "--recurse --depth 2" for 2 levels, etc.', false)
  .option('-d, --depth <n>', 'Maximum recursion depth: 0=current dir only, 1=one level, 2=two levels, "all"=unlimited (use with --recurse)', '0')
  .option('--directories-as-ontologies', 'Use directory names as ontology names (auto-creates ontologies from folder structure, cannot be combined with -o)', false)
  .option('-f, --force', 'Force re-ingestion even if duplicate (bypasses hash check for all files)', false)
  .option('--dry-run', 'Show what would be ingested without submitting jobs (validates files, checks duplicates, displays skip/submit counts, cancels test jobs)', false)
  .option('--no-approve', 'Require manual approval before processing (default: auto-approve)')
  .option('--parallel', 'Process in parallel (faster but may create duplicate concepts)', false)
  .option('--target-words <n>', 'Target words per chunk', '1000')
  .option('--overlap-words <n>', 'Overlap between chunks', '200')
  .showHelpAfterError()
  .action(async (dir: string, options) => {
    try {
      // Validate directory exists
      if (!fs.existsSync(dir)) {
        console.error(chalk.red(`✗ Directory not found: ${dir}`));
        process.exit(1);
      }

      if (!fs.statSync(dir).isDirectory()) {
        console.error(chalk.red(`✗ Not a directory: ${dir}`));
        process.exit(1);
      }

      // Validate options: either --ontology or --directories-as-ontologies required
      if (!options.ontology && !options.directoriesAsOntologies) {
        console.error(chalk.red('✗ Either --ontology or --directories-as-ontologies is required'));
        console.error(chalk.gray('  Use --ontology to specify a single ontology'));
        console.error(chalk.gray('  Use --directories-as-ontologies to auto-create ontologies from directory structure'));
        process.exit(1);
      }

      if (options.ontology && options.directoriesAsOntologies) {
        console.error(chalk.red('✗ Cannot use both --ontology and --directories-as-ontologies'));
        console.error(chalk.gray('  Choose one: specify ontology or use directory names'));
        process.exit(1);
      }

      const client = createClientFromEnv();

      // Determine depth
      const maxDepth = options.depth === 'all' ? Infinity : parseInt(options.depth);
      const recurse = options.recurse || maxDepth > 0;

      // Collect matching files (with directory info if using directories as ontologies)
      const filesWithDirs = options.directoriesAsOntologies
        ? collectFilesWithDirectories(dir, options.pattern, recurse, maxDepth)
        : collectFiles(dir, options.pattern, recurse, maxDepth).map(f => ({ file: f, ontologyDir: dir }));

      if (filesWithDirs.length === 0) {
        console.log(chalk.yellow(`\n⚠ No files found matching patterns: ${options.pattern.join(', ')}`));
        return;
      }

      // Group files by ontology if using directory names
      const filesByOntology = new Map<string, string[]>();
      for (const { file, ontologyDir } of filesWithDirs) {
        const ontologyName = options.directoriesAsOntologies
          ? nodePath.basename(ontologyDir)
          : options.ontology;

        if (!filesByOntology.has(ontologyName)) {
          filesByOntology.set(ontologyName, []);
        }
        filesByOntology.get(ontologyName)!.push(file);
      }

      console.log(chalk.blue(`\n📂 Found ${filesWithDirs.length} file(s):`));
      if (options.directoriesAsOntologies) {
        console.log(chalk.gray(`  Ontologies: ${filesByOntology.size}`));
        for (const [ontology, files] of filesByOntology) {
          console.log(chalk.gray(`  • ${ontology}: ${files.length} file(s)`));
        }
      } else {
        filesWithDirs.forEach(({ file }) => console.log(chalk.gray(`  • ${nodePath.relative(dir, file)}`)));
      }

      // Dry-run mode: check duplicates without submitting
      if (options.dryRun) {
        console.log(chalk.blue(`\n🔍 Dry-run mode: Checking for duplicates...\n`));

        let wouldSubmit = 0;
        let wouldSkip = 0;
        const skipDetails: string[] = [];
        const submitDetails: string[] = [];

        for (const { file: filePath, ontologyDir } of filesWithDirs) {
          const ontologyName = options.directoriesAsOntologies
            ? nodePath.basename(ontologyDir)
            : options.ontology;

          const request: IngestRequest = {
            ontology: ontologyName,
            filename: nodePath.basename(filePath),
            force: options.force,
            auto_approve: false,  // Don't matter for dry-run, but set conservative
            processing_mode: 'serial',
            // ADR-051: Source provenance metadata
            source_type: 'file',
            source_path: nodePath.resolve(filePath),
            source_hostname: os.hostname(),
          };

          try {
            // This will check for duplicates without auto-approving
            const result = await client.ingestFile(filePath, request);

            const displayPath = options.directoriesAsOntologies
              ? `[${ontologyName}] ${nodePath.basename(filePath)}`
              : nodePath.relative(dir, filePath);

            if ('duplicate' in result && result.duplicate) {
              wouldSkip++;
              skipDetails.push(`  ${chalk.yellow('○')} ${chalk.gray(displayPath)}`);
            } else {
              // It created a pending job - we need to cancel it
              const submitResult = result as JobSubmitResponse;
              await client.cancelJob(submitResult.job_id);
              wouldSubmit++;
              submitDetails.push(`  ${chalk.green('✓')} ${displayPath}`);
            }
          } catch (error: any) {
            wouldSkip++;
            skipDetails.push(`  ${chalk.red('✗')} ${chalk.gray(nodePath.relative(dir, filePath))} ${chalk.dim(`(${error.message})`)}`);
          }
        }

        console.log(chalk.blue(`\n📊 Dry-run Summary:`));
        console.log(chalk.gray(`  Total files: ${filesWithDirs.length}`));
        console.log(chalk.green(`  Would submit: ${wouldSubmit}`));
        console.log(chalk.yellow(`  Would skip (duplicates): ${wouldSkip}`));

        if (submitDetails.length > 0) {
          console.log(chalk.green(`\n✓ Files that would be ingested:`));
          submitDetails.forEach(line => console.log(line));
        }

        if (skipDetails.length > 0) {
          console.log(chalk.yellow(`\n○ Files that would be skipped:`));
          skipDetails.forEach(line => console.log(line));
        }

        console.log(chalk.blue(`\n💡 To proceed with ingestion, run without --dry-run flag\n`));
        return;
      }

      // Normal mode: actually submit jobs
      // Default to auto-approve
      const autoApprove = options.approve !== false;

      console.log(chalk.blue(`\nSubmitting ${filesWithDirs.length} ingestion jobs...`));
      if (!options.directoriesAsOntologies) {
        console.log(chalk.gray(`  Ontology: ${options.ontology}`));
      }
      console.log(chalk.gray(`  Auto-approve: ${autoApprove ? 'yes' : 'no'}\n`));

      const jobIds: string[] = [];
      let submitted = 0;
      let skipped = 0;

      for (const { file: filePath, ontologyDir } of filesWithDirs) {
        const ontologyName = options.directoriesAsOntologies
          ? nodePath.basename(ontologyDir)
          : options.ontology;
        const request: IngestRequest = {
          ontology: ontologyName,
          filename: nodePath.basename(filePath),
          force: options.force,
          auto_approve: autoApprove,
          processing_mode: options.parallel ? 'parallel' : 'serial',
          options: {
            target_words: parseInt(options.targetWords),
            overlap_words: parseInt(options.overlapWords),
          },
          // ADR-051: Source provenance metadata
          source_type: 'file',
          source_path: nodePath.resolve(filePath),
          source_hostname: os.hostname(),
        };

        try {
          const result = await client.ingestFile(filePath, request);

          if ('duplicate' in result && result.duplicate) {
            const displayPath = options.directoriesAsOntologies
              ? `[${ontologyName}] ${nodePath.basename(filePath)}`
              : nodePath.relative(dir, filePath);
            console.log(chalk.yellow(`⚠ Skipped (duplicate): ${displayPath}`));
            skipped++;
          } else {
            const submitResult = result as JobSubmitResponse;
            jobIds.push(submitResult.job_id);
            const displayPath = options.directoriesAsOntologies
              ? `[${ontologyName}] ${nodePath.basename(filePath)}`
              : nodePath.relative(dir, filePath);
            console.log(chalk.green(`✓ Queued: ${displayPath} → ${submitResult.job_id.substring(0, 12)}...`));
            submitted++;
          }
        } catch (error: any) {
          const displayPath = options.directoriesAsOntologies
            ? `[${ontologyName}] ${nodePath.basename(filePath)}`
            : nodePath.relative(dir, filePath);
          console.log(chalk.red(`✗ Failed: ${displayPath} - ${error.message}`));
          skipped++;
        }
      }

      console.log(chalk.blue(`\n📊 Summary:`));
      console.log(chalk.gray(`  Submitted: ${submitted}`));
      console.log(chalk.gray(`  Skipped: ${skipped}`));

      if (jobIds.length > 0) {
        console.log(chalk.blue('\n📌 Next steps:'));
        if (autoApprove) {
          console.log(chalk.gray(`  Monitor all: ${chalk.cyan(`kg jobs list`)}`));
          console.log(chalk.gray(`  View details: ${chalk.cyan(`kg jobs status <job-id>`)}`));
        } else {
          console.log(chalk.gray(`  Approve all pending: ${chalk.cyan(`kg jobs approve pending`)}`));
          console.log(chalk.gray(`  View pending: ${chalk.cyan(`kg jobs list pending`)}`));
        }
      }
    } catch (error: any) {
      console.error(chalk.red('\n✗ Directory ingestion failed'));
      console.error(chalk.red(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

// Ingest text command
ingestCommand
  .command('text <text>')
  .description('Ingest raw text directly without a file. Submits text content as ingestion job, useful for quick testing/prototyping, ingesting programmatically generated text, API/script integration, and processing text from other commands. Can pipe command output via xargs or use multiline text with heredoc syntax. Text is chunked (default 1000 words per chunk) and processed like file ingestion. Use --filename to customize displayed name in ontology files list (default: text_input). Behavior same as file ingestion: auto-approves by default, detects duplicates, supports --wait for synchronous completion.')
  .requiredOption('-o, --ontology <name>', 'Ontology/collection name (named collection or knowledge domain)')
  .option('-f, --force', 'Force re-ingestion even if duplicate (bypasses content hash check)', false)
  .option('--no-approve', 'Require manual approval before processing (default: auto-approve)')
  .option('--parallel', 'Process in parallel (faster but may create duplicate concepts)', false)
  .option('--filename <name>', 'Filename for tracking (displayed in ontology files list, temporary path context)', 'text_input')
  .option('--target-words <n>', 'Target words per chunk', '1000')
  .option('-w, --wait', 'Wait for job completion (polls until complete, shows progress). Default: submit and exit.', false)
  .showHelpAfterError()
  .action(async (text: string, options) => {
    try {
      const client = createClientFromEnv();
      const config = getConfig();

      // Default to auto-approve (options.approve is true by default due to --no-approve pattern)
      // Only require approval if user explicitly passes --no-approve flag
      const autoApprove = options.approve !== false;

      const request: IngestRequest = {
        ontology: options.ontology,
        filename: options.filename,
        force: options.force,
        auto_approve: autoApprove,  // ADR-014: Auto-approve flag
        processing_mode: options.parallel ? 'parallel' : 'serial',
        options: {
          target_words: parseInt(options.targetWords),
        },
        // ADR-051: Source provenance metadata (stdin/direct text input)
        source_type: 'stdin',
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

      // If --wait flag provided, poll for completion
      if (options.wait) {
        await pollJobWithProgress(client, submitResult.job_id);
      } else {
        // Default: submit and exit (like walking away from the counter)
        console.log(chalk.gray(`\nMonitor progress: ${chalk.cyan(`kg jobs status ${submitResult.job_id} --watch`)}`));
      }
    } catch (error: any) {
      console.error(chalk.red('\n✗ Ingestion failed'));
      console.error(chalk.red(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

/**
 * Collect files matching patterns from directory
 */
function collectFiles(dir: string, patterns: string[], recurse: boolean, maxDepth: number, currentDepth: number = 0): string[] {
  const files: string[] = [];

  // Don't recurse beyond max depth
  if (currentDepth > maxDepth) {
    return files;
  }

  const entries = fs.readdirSync(dir, { withFileTypes: true });

  for (const entry of entries) {
    const fullPath = nodePath.join(dir, entry.name);

    if (entry.isDirectory() && recurse && currentDepth < maxDepth) {
      // Recurse into subdirectory
      files.push(...collectFiles(fullPath, patterns, recurse, maxDepth, currentDepth + 1));
    } else if (entry.isFile()) {
      // Check if file matches any pattern
      const matches = patterns.some(pattern => {
        // Convert glob pattern to regex
        const regexPattern = pattern
          .replace(/\./g, '\\.')
          .replace(/\*/g, '.*')
          .replace(/\?/g, '.');
        const regex = new RegExp(`^${regexPattern}$`, 'i');
        return regex.test(entry.name);
      });

      if (matches) {
        files.push(fullPath);
      }
    }
  }

  return files;
}

/**
 * Collect files with their parent directory info for ontology mapping
 */
function collectFilesWithDirectories(
  baseDir: string,
  patterns: string[],
  recurse: boolean,
  maxDepth: number,
  currentDepth: number = 0
): Array<{ file: string; ontologyDir: string }> {
  const results: Array<{ file: string; ontologyDir: string }> = [];

  // Don't recurse beyond max depth
  if (currentDepth > maxDepth) {
    return results;
  }

  const entries = fs.readdirSync(baseDir, { withFileTypes: true });

  for (const entry of entries) {
    const fullPath = nodePath.join(baseDir, entry.name);

    if (entry.isDirectory() && recurse && currentDepth < maxDepth) {
      // Recurse into subdirectory - subdirectory becomes the ontology
      const subResults = collectFilesWithDirectories(fullPath, patterns, recurse, maxDepth, currentDepth + 1);
      results.push(...subResults);
    } else if (entry.isFile()) {
      // Check if file matches any pattern
      const matches = patterns.some(pattern => {
        // Convert glob pattern to regex
        const regexPattern = pattern
          .replace(/\./g, '\\.')
          .replace(/\*/g, '.*')
          .replace(/\?/g, '.');
        const regex = new RegExp(`^${regexPattern}$`, 'i');
        return regex.test(entry.name);
      });

      if (matches) {
        // Use immediate parent directory as ontology
        results.push({
          file: fullPath,
          ontologyDir: baseDir
        });
      }
    }
  }

  return results;
}

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
          const conceptsTotal = (p.concepts_created || 0) + (p.concepts_linked || 0);
          const hitRate = conceptsTotal > 0 ? Math.round((p.concepts_linked || 0) / conceptsTotal * 100) : 0;
          spinner.text = `Processing... ${p.percent}% (${p.chunks_processed}/${p.chunks_total} chunks) | Concepts: ${conceptsTotal} (${hitRate}% reused) | Relationships: ${p.relationships_created || 0}`;
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
    } else if (finalJob.status === 'awaiting_approval') {
      spinner.info('Job awaiting approval');
      console.log(chalk.blue('\n📋 Job requires approval before processing'));
      console.log(chalk.gray(`  Job ID: ${jobId}`));
      console.log(chalk.gray(`\n  To approve: ${chalk.cyan(`kg jobs approve ${jobId}`)}`));
      console.log(chalk.gray(`  To cancel:  ${chalk.cyan(`kg jobs cancel ${jobId}`)}`));
      console.log(chalk.gray(`  To monitor: ${chalk.cyan(`kg jobs status ${jobId} --watch`)}`));
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
