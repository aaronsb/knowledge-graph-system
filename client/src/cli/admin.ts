/**
 * Admin Commands
 *
 * System administration: status, backup, restore, reset
 */

import { Command } from 'commander';
import * as readline from 'readline';
import * as fs from 'fs';
import * as path from 'path';
import { createClientFromEnv } from '../api/client';
import { getConfig } from '../lib/config';
import * as colors from './colors';
import { separator } from './colors';
import { configureColoredHelp } from './help-formatter';
import { JobProgressStream, trackJobProgress } from '../lib/job-stream';
import type { JobStatus, JobProgress } from '../types';

/**
 * Prompt for input from user
 */
function prompt(question: string): Promise<string> {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
  });

  return new Promise((resolve) => {
    rl.question(question, (answer) => {
      rl.close();
      resolve(answer);
    });
  });
}

/**
 * Prompt for password (hidden input)
 */
function promptPassword(question: string): Promise<string> {
  return new Promise((resolve) => {
    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout
    });

    // @ts-ignore - _writeToOutput exists but not in types
    rl._writeToOutput = function(stringToWrite: string) {
      if (stringToWrite.charCodeAt(0) === 13) { // carriage return
        // @ts-ignore
        rl.output.write('\n');
      } else {
        // Don't display password characters
      }
    };

    rl.question(question, (password) => {
      rl.close();
      console.log(); // New line after password input
      resolve(password);
    });
  });
}

/**
 * Track job progress with SSE streaming (ADR-018 Phase 1)
 *
 * Tries Server-Sent Events first for real-time updates (<500ms latency).
 * Falls back to polling if SSE fails or is unavailable.
 *
 * @param client - API client
 * @param jobId - Job ID to track
 * @param spinner - Ora spinner for status updates
 * @returns Promise that resolves with final job status
 */
async function trackJobWithSSE(
  client: ReturnType<typeof createClientFromEnv>,
  jobId: string,
  spinner: any
): Promise<JobStatus> {
  return new Promise(async (resolve, reject) => {
    const baseUrl = process.env.API_BASE_URL || 'http://localhost:8000';

    // Try SSE first
    const stream = await trackJobProgress(baseUrl, jobId, {
      onProgress: (progress: JobProgress) => {
        spinner = updateSpinnerForProgress(spinner, progress);
      },
      onCompleted: async (result) => {
        // Complete the final stage
        const state: ProgressState = (spinner as any).__progressState;
        if (state && state.currentStage) {
          const finalStats = state.stageStats.get(state.currentStage);
          if (finalStats) {
            const progressBar = createProgressBar(finalStats.total, finalStats.total);
            state.spinner.succeed(getStageName(state.currentStage) + ` ${progressBar} ${finalStats.total}/${finalStats.total}`);
          } else {
            state.spinner.succeed(getStageName(state.currentStage));
          }
        } else {
          spinner.succeed('Restore complete!');
        }

        // Fetch final job status for complete information
        try {
          const finalJob = await client.getJobStatus(jobId);
          resolve(finalJob);
        } catch (error) {
          reject(error);
        }
      },
      onFailed: (error) => {
        spinner.fail('Restore failed');
        reject(new Error(error));
      },
      onCancelled: (message) => {
        spinner.fail('Restore cancelled');
        reject(new Error(message));
      },
      onError: async (error) => {
        // SSE failed - fall back to polling
        console.log(colors.status.dim('\nSSE unavailable, using polling...'));
        try {
          const finalJob = await client.pollJob(jobId, (job) => {
            if (job.progress) {
              spinner = updateSpinnerForProgress(spinner, job.progress);
            }
          });
          resolve(finalJob);
        } catch (pollError) {
          reject(pollError);
        }
      }
    }, true); // useSSE = true

    // If stream is null, SSE was explicitly disabled - use polling fallback
    if (!stream) {
      console.log(colors.status.dim('Using polling for progress updates...'));
      try {
        const finalJob = await client.pollJob(jobId, (job) => {
          if (job.progress) {
            spinner = updateSpinnerForProgress(spinner, job.progress);
          }
        });
        resolve(finalJob);
      } catch (pollError) {
        reject(pollError);
      }
    }
  });
}

/**
 * State tracker for multi-line progress display
 */
interface ProgressState {
  currentStage: string | null;
  spinner: any;
  stageStats: Map<string, { items: number; total: number }>;
}

/**
 * Update spinner text based on job progress (shared logic for SSE and polling)
 *
 * Shows each stage on a new line for better visibility of progress history.
 */
function updateSpinnerForProgress(spinner: any, progress: JobProgress): any {
  const ora = require('ora');

  // Initialize progress state if not exists
  if (!(spinner as any).__progressState) {
    (spinner as any).__progressState = {
      currentStage: null,
      spinner: spinner,
      stageStats: new Map()
    } as ProgressState;
  }

  const state: ProgressState = (spinner as any).__progressState;

  // Detect stage change
  const stageChanged = state.currentStage && state.currentStage !== progress.stage;

  if (stageChanged) {
    // Complete previous stage with final stats and progress bar
    const prevStats = state.stageStats.get(state.currentStage!);
    if (prevStats) {
      const progressBar = createProgressBar(prevStats.total, prevStats.total);
      state.spinner.succeed(getStageName(state.currentStage!) + ` ${progressBar} ${prevStats.total}/${prevStats.total}`);
    } else {
      state.spinner.succeed(getStageName(state.currentStage!));
    }

    // Start new spinner for new stage
    state.spinner = ora(getStageName(progress.stage)).start();
    state.currentStage = progress.stage;
  } else if (!state.currentStage) {
    // First stage
    state.currentStage = progress.stage;
    state.spinner.start();
  }

  // Update current stage stats
  if (progress.message) {
    // Extract items from message: "Restoring concepts: 10/114 (8%)"
    const match = progress.message.match(/(\d+)\/(\d+)/);
    if (match) {
      state.stageStats.set(progress.stage, {
        items: parseInt(match[1]),
        total: parseInt(match[2])
      });
    }
  }

  // Update spinner text based on stage
  switch (progress.stage) {
    case 'creating_checkpoint':
      state.spinner.text = `Creating checkpoint backup... ${progress.percent || 0}%`;
      break;
    case 'loading_backup':
      state.spinner.text = `Loading backup file... ${progress.percent || 0}%`;
      break;
    case 'restoring_concepts':
    case 'restoring_sources':
    case 'restoring_instances':
    case 'restoring_relationships':
      if (progress.message) {
        // Extract current/total from message: "Restoring concepts: 10/114 (8%)"
        const match = progress.message.match(/(\d+)\/(\d+)/);
        if (match) {
          const current = parseInt(match[1]);
          const total = parseInt(match[2]);
          const progressBar = createProgressBar(current, total);
          const stageName = getStageName(progress.stage);
          state.spinner.text = `${stageName} ${progressBar} ${current}/${total}`;
        } else {
          state.spinner.text = progress.message;
        }
      } else if (progress.items_total && progress.items_processed !== undefined) {
        const stageName = getStageName(progress.stage);
        const progressBar = createProgressBar(progress.items_processed, progress.items_total);
        state.spinner.text = `${stageName} ${progressBar} ${progress.items_processed}/${progress.items_total}`;
      } else {
        state.spinner.text = `${getStageName(progress.stage)} ${progress.percent || 0}%`;
      }
      break;
    case 'rollback':
      state.spinner.fail('Restore failed - rolling back to checkpoint');
      state.spinner = ora(progress.message || 'Rolling back...').start();
      state.currentStage = progress.stage;
      break;
    case 'completed':
      state.spinner.text = `Restore complete! ${progress.percent || 100}%`;
      break;
    default:
      if (progress.message) {
        state.spinner.text = progress.message;
      } else {
        state.spinner.text = `Restoring... ${progress.percent || 0}%`;
      }
  }

  return state.spinner;
}

/**
 * Get user-friendly stage name
 */
function getStageName(stage: string): string {
  const stageNames: Record<string, string> = {
    'creating_checkpoint': 'Creating checkpoint backup',
    'loading_backup': 'Loading backup file',
    'restoring_concepts': 'Restoring concepts',
    'restoring_sources': 'Restoring sources',
    'restoring_instances': 'Restoring instances',
    'restoring_relationships': 'Restoring relationships',
    'completed': 'Restore complete',
    'rollback': 'Rolling back'
  };

  return stageNames[stage] || stage;
}

/**
 * Create a visual progress bar using Unicode characters
 *
 * @param current - Current progress value
 * @param total - Total value
 * @param width - Width of the progress bar (default: 20)
 * @returns Progress bar string
 */
function createProgressBar(current: number, total: number, width: number = 20): string {
  if (total === 0) return '░'.repeat(width);

  const percent = Math.min(current / total, 1);
  const filled = Math.floor(percent * width);
  const empty = width - filled;

  // Unicode block characters for smooth progress
  return '█'.repeat(filled) + '░'.repeat(empty);
}

// ========== Status Command ==========

const statusCommand = new Command('status')
  .description('Show system status (Docker, database, environment)')
  .action(async () => {
    try {
      const client = createClientFromEnv();

      console.log('\n' + separator());
      console.log(colors.ui.title('📊 System Status'));
      console.log(separator());

      const status = await client.getSystemStatus();

      // Docker
      console.log('\n' + colors.ui.header('Docker'));
      if (status.docker.running) {
        console.log(`  ${colors.status.success('✓')} PostgreSQL container running`);
        if (status.docker.container_name) {
          console.log(`    ${colors.ui.key('Container:')} ${colors.ui.value(status.docker.container_name)}`);
        }
        if (status.docker.status) {
          console.log(`    ${colors.ui.key('Status:')} ${colors.ui.value(status.docker.status)}`);
        }
      } else {
        console.log(`  ${colors.status.error('✗')} PostgreSQL not running`);
        console.log(`    ${colors.status.dim('Run: docker-compose up -d')}`);
      }

      // Database Connection
      console.log('\n' + colors.ui.header('Database Connection'));
      if (status.database_connection.connected) {
        console.log(`  ${colors.status.success('✓')} Connected to PostgreSQL + AGE`);
        console.log(`    ${colors.ui.key('URI:')} ${colors.ui.value(status.database_connection.uri)}`);
      } else {
        console.log(`  ${colors.status.error('✗')} Cannot connect to PostgreSQL`);
        if (status.database_connection.error) {
          console.log(`    ${colors.status.error(status.database_connection.error)}`);
        }
      }

      // Database Stats
      if (status.database_stats) {
        console.log('\n' + colors.ui.header('Database Statistics'));
        console.log(`  ${colors.ui.key('Concepts:')} ${colors.coloredCount(status.database_stats.concepts)}`);
        console.log(`  ${colors.ui.key('Sources:')} ${colors.coloredCount(status.database_stats.sources)}`);
        console.log(`  ${colors.ui.key('Instances:')} ${colors.coloredCount(status.database_stats.instances)}`);
        console.log(`  ${colors.ui.key('Relationships:')} ${colors.coloredCount(status.database_stats.relationships)}`);
      }

      // Python Environment
      console.log('\n' + colors.ui.header('Python Environment'));
      if (status.python_env.venv_exists) {
        console.log(`  ${colors.status.success('✓')} Virtual environment exists`);
        if (status.python_env.python_version) {
          console.log(`    ${colors.ui.key('Version:')} ${colors.ui.value(status.python_env.python_version)}`);
        }
      } else {
        console.log(`  ${colors.status.error('✗')} Virtual environment not found`);
        console.log(`    ${colors.status.dim('Run: ./scripts/setup.sh')}`);
      }

      // Configuration
      console.log('\n' + colors.ui.header('Configuration'));
      if (status.configuration.env_exists) {
        console.log(`  ${colors.status.success('✓')} .env file exists`);

        const anthropicStatus = status.configuration.anthropic_key_configured
          ? colors.status.success('configured')
          : colors.status.error('missing');
        console.log(`    ${colors.ui.key('ANTHROPIC_API_KEY:')} ${anthropicStatus}`);

        const openaiStatus = status.configuration.openai_key_configured
          ? colors.status.success('configured')
          : colors.status.error('missing');
        console.log(`    ${colors.ui.key('OPENAI_API_KEY:')} ${openaiStatus}`);
      } else {
        console.log(`  ${colors.status.error('✗')} .env file not found`);
        console.log(`    ${colors.status.dim('Run: ./scripts/setup.sh')}`);
      }

      // Access Points
      if (status.neo4j_browser_url) {
        console.log('\n' + colors.ui.header('Access Points'));
        console.log(`  ${colors.ui.key('PostgreSQL:')} ${colors.ui.value(status.neo4j_browser_url)}`);
        console.log(`  ${colors.ui.key('Credentials:')} ${colors.status.dim(process.env.POSTGRES_USER || 'admin')}/${colors.status.dim('password')}`);
      }

      console.log('\n' + separator() + '\n');

    } catch (error: any) {
      console.error(colors.status.error('✗ Failed to get system status'));
      console.error(colors.status.error(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

// ========== Backup Command ==========

const backupCommand = new Command('backup')
  .description('Create a database backup')
  .option('--type <type>', 'Backup type: "full" or "ontology"')
  .option('--ontology <name>', 'Ontology name (required if type is ontology)')
  .option('--output <filename>', 'Custom output filename')
  .action(async (options) => {
    try {
      const client = createClientFromEnv();

      console.log('\n' + separator());
      console.log(colors.ui.title('💾 Database Backup'));
      console.log(separator());

      let backupType: 'full' | 'ontology' = 'full';
      let ontologyName: string | undefined;

      // Interactive mode if no options provided
      if (!options.type) {
        console.log('\n' + colors.ui.key('Backup Options:'));
        console.log('  1) Full database backup (all ontologies)');
        console.log('  2) Specific ontology backup');
        console.log('');

        const choice = await prompt('Select option [1-2]: ');

        if (choice === '1') {
          backupType = 'full';
        } else if (choice === '2') {
          backupType = 'ontology';
          ontologyName = await prompt('Enter ontology name: ');
        } else {
          console.log(colors.status.error('Invalid option'));
          process.exit(1);
        }
      } else {
        backupType = options.type as 'full' | 'ontology';
        ontologyName = options.ontology;
      }

      // Validate
      if (backupType === 'ontology' && !ontologyName) {
        console.error(colors.status.error('✗ Ontology name required for ontology backup'));
        process.exit(1);
      }

      // Get backup directory and ensure it exists
      const config = getConfig();
      const backupDir = config.ensureBackupDir();

      // Determine output path
      let savePath: string;
      if (options.output) {
        // Custom filename specified
        savePath = path.join(backupDir, options.output.endsWith('.json') ? options.output : `${options.output}.json`);
      } else {
        // Use timestamped filename (will be overwritten with server-provided name)
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-').split('T')[0];
        savePath = path.join(backupDir, `temp_${timestamp}.json`);
      }

      // Download backup with progress tracking using ora
      const ora = require('ora');
      const spinner = ora('Preparing backup...').start();

      try {
        const result = await client.createBackup(
          {
            backup_type: backupType,
            ontology_name: ontologyName
          },
          savePath,
          (downloaded: number, total: number, percent: number) => {
            const downloadedMB = (downloaded / (1024 * 1024)).toFixed(2);
            const totalMB = (total / (1024 * 1024)).toFixed(2);
            spinner.text = `Downloading backup... ${percent}% (${downloadedMB}/${totalMB} MB)`;
          }
        );

        spinner.succeed('Backup download complete!');

        console.log('\n' + separator());
        console.log(colors.status.success('✓ Backup Complete'));
        console.log(separator());
        console.log(`\n  ${colors.ui.key('File:')} ${colors.ui.value(result.filename)}`);
        console.log(`  ${colors.ui.key('Path:')} ${colors.ui.value(result.path)}`);
        console.log(`  ${colors.ui.key('Size:')} ${colors.ui.value((result.size / (1024 * 1024)).toFixed(2) + ' MB')}`);
        console.log(`\n  ${colors.status.dim('Backup saved to: ' + backupDir)}`);
        console.log('\n' + separator() + '\n');

      } catch (downloadError) {
        spinner.fail('Backup download failed');
        throw downloadError;
      }

    } catch (error: any) {
      console.error(colors.status.error('✗ Backup failed'));
      console.error(colors.status.error(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

// ========== List Backups Command ==========

const listBackupsCommand = new Command('list-backups')
  .description('List available backup files from configured directory')
  .action(async () => {
    try {
      const config = getConfig();
      const backupDir = config.getBackupDir();

      // Ensure backup directory exists
      if (!fs.existsSync(backupDir)) {
        console.log('\n' + separator());
        console.log(colors.ui.title('📁 Available Backups'));
        console.log(separator());
        console.log(`\n  ${colors.status.dim('No backups found - directory does not exist')}`);
        console.log(`  ${colors.status.dim(`Directory: ${backupDir}`)}`);
        console.log(`  ${colors.status.dim('Run "kg admin backup" to create your first backup')}\n`);
        console.log(separator() + '\n');
        return;
      }

      // Read backup files
      const files = fs.readdirSync(backupDir)
        .filter(f => f.endsWith('.json') || f.endsWith('.jsonl'))
        .map(filename => {
          const filepath = path.join(backupDir, filename);
          const stats = fs.statSync(filepath);
          return {
            filename,
            path: filepath,
            size_mb: stats.size / (1024 * 1024),
            created: stats.mtime.toISOString()
          };
        })
        .sort((a, b) => new Date(b.created).getTime() - new Date(a.created).getTime()); // newest first

      console.log('\n' + separator());
      console.log(colors.ui.title(`📁 Available Backups (${files.length})`));
      console.log(separator());

      if (files.length === 0) {
        console.log(`\n  ${colors.status.dim('No backups found')}`);
        console.log(`  ${colors.status.dim(`Directory: ${backupDir}`)}`);
        console.log(`  ${colors.status.dim('Run "kg admin backup" to create your first backup')}\n`);
      } else {
        console.log('');
        files.forEach((backup, i) => {
          console.log(`  ${colors.ui.bullet(`${i + 1}.`)} ${colors.ui.value(backup.filename)}`);
          console.log(`     ${colors.status.dim(`Size: ${backup.size_mb.toFixed(2)} MB`)}`);
          console.log(`     ${colors.status.dim(`Created: ${new Date(backup.created).toLocaleString()}`)}`);
        });
        console.log(`\n  ${colors.status.dim(`Directory: ${backupDir}`)}`);
      }

      console.log('\n' + separator() + '\n');

    } catch (error: any) {
      console.error(colors.status.error('✗ Failed to list backups'));
      console.error(colors.status.error(error.message));
      process.exit(1);
    }
  });

// ========== Restore Command ==========

const restoreCommand = new Command('restore')
  .description('Restore a database backup (requires authentication)')
  .option('--file <name>', 'Backup filename (from configured directory)')
  .option('--path <path>', 'Custom backup file path (overrides configured directory)')
  .option('--overwrite', 'Overwrite existing data', false)
  .option('--deps <action>', 'How to handle external dependencies: prune, stitch, defer', 'prune')
  .action(async (options) => {
    try {
      const client = createClientFromEnv();
      const config = getConfig();
      const backupDir = config.getBackupDir();

      console.log('\n' + separator());
      console.log(colors.ui.title('📥 Database Restore'));
      console.log(colors.status.warning('⚠️  Potentially destructive operation - authentication required'));
      console.log(separator());

      // Determine backup file path
      let backupFilePath: string;
      let backupFilename: string;

      if (options.path) {
        // Custom path specified
        backupFilePath = options.path;
        backupFilename = path.basename(backupFilePath);
      } else if (options.file) {
        // Filename specified, use configured directory
        backupFilePath = path.join(backupDir, options.file);
        backupFilename = options.file;
      } else {
        // Interactive selection from configured directory
        if (!fs.existsSync(backupDir)) {
          console.error(colors.status.error('\n✗ No backups available - directory does not exist'));
          console.log(colors.status.dim(`Directory: ${backupDir}\n`));
          process.exit(1);
        }

        const backups = fs.readdirSync(backupDir)
          .filter(f => f.endsWith('.json') || f.endsWith('.jsonl'))
          .map(filename => {
            const filepath = path.join(backupDir, filename);
            const stats = fs.statSync(filepath);
            return {
              filename,
              path: filepath,
              size_mb: stats.size / (1024 * 1024)
            };
          })
          .sort((a, b) => b.size_mb - a.size_mb);

        if (backups.length === 0) {
          console.error(colors.status.error('\n✗ No backups available'));
          console.log(colors.status.dim(`Directory: ${backupDir}\n`));
          process.exit(1);
        }

        console.log('\n' + colors.ui.key('Available Backups:'));
        backups.slice(0, 10).forEach((backup, i) => {
          console.log(`  ${i + 1}. ${backup.filename} (${backup.size_mb.toFixed(2)} MB)`);
        });

        const choice = await prompt('\nSelect backup [1-10] or enter filename: ');

        if (/^\d+$/.test(choice)) {
          const index = parseInt(choice) - 1;
          if (index >= 0 && index < backups.length) {
            backupFilePath = backups[index].path;
            backupFilename = backups[index].filename;
          } else {
            console.error(colors.status.error('✗ Invalid selection'));
            process.exit(1);
          }
        } else {
          backupFilename = choice;
          backupFilePath = path.join(backupDir, choice);
        }
      }

      // Verify file exists
      if (!fs.existsSync(backupFilePath)) {
        console.error(colors.status.error(`\n✗ Backup file not found: ${backupFilePath}\n`));
        process.exit(1);
      }

      console.log(colors.status.dim(`\nBackup file: ${backupFilePath}`));
      const fileStats = fs.statSync(backupFilePath);
      console.log(colors.status.dim(`Size: ${(fileStats.size / (1024 * 1024)).toFixed(2)} MB`));

      // Get authentication
      // NOTE: Placeholder auth for testing (see ADR-016 for future auth system)
      // Currently validates: username exists in config, password length >= 4
      // Future: Will validate against proper auth system with hashed passwords
      console.log('\n' + colors.status.warning('Authentication required:'));

      // Get username from config
      const username = config.get('username') || config.getClientId();
      if (!username) {
        console.error(colors.status.error('✗ Username not configured. Run: kg config set username <your-username>'));
        process.exit(1);
      }

      console.log(colors.status.dim(`Using username: ${username}`));
      const password = await promptPassword('Password: ');

      if (!password) {
        console.error(colors.status.error('✗ Password required'));
        process.exit(1);
      }

      // Upload backup with progress tracking (ADR-015 Phase 2)
      const ora = require('ora');
      let spinner = ora('Uploading backup...').start();

      try {
        const uploadResult = await client.restoreBackup(
          backupFilePath,
          username,
          password,
          options.overwrite,
          options.deps,
          (uploaded: number, total: number, percent: number) => {
            const uploadedMB = (uploaded / (1024 * 1024)).toFixed(2);
            const totalMB = (total / (1024 * 1024)).toFixed(2);
            spinner.text = `Uploading backup... ${percent}% (${uploadedMB}/${totalMB} MB)`;
          }
        );

        spinner.succeed('Backup uploaded successfully!');

        // Show backup stats if available
        if (uploadResult.backup_stats) {
          console.log(colors.status.dim(`\nBackup contains: ${uploadResult.backup_stats.concepts || 0} concepts, ${uploadResult.backup_stats.sources || 0} sources`));
        }

        if (uploadResult.integrity_warnings > 0) {
          console.log(colors.status.warning(`⚠️  Backup has ${uploadResult.integrity_warnings} validation warnings`));
        }

        // Track restore job progress with SSE streaming (ADR-018 Phase 1)
        // Falls back to polling if SSE fails
        spinner = ora('Preparing restore...').start();
        const jobId = uploadResult.job_id;

        const finalJob = await trackJobWithSSE(client, jobId, spinner);

        if (finalJob.status === 'completed') {
          spinner.succeed('Restore completed successfully!');

          console.log('\n' + separator());
          console.log(colors.status.success('✓ Restore Complete'));
          console.log(separator());

          // Show restore statistics if available
          if (finalJob.result?.restore_stats) {
            const stats = finalJob.result.restore_stats;
            console.log('\n' + colors.ui.header('Restored:'));
            console.log(`  ${colors.ui.key('Concepts:')} ${colors.coloredCount(stats.concepts || 0)}`);
            console.log(`  ${colors.ui.key('Sources:')} ${colors.coloredCount(stats.sources || 0)}`);
            console.log(`  ${colors.ui.key('Instances:')} ${colors.coloredCount(stats.instances || 0)}`);
            console.log(`  ${colors.ui.key('Relationships:')} ${colors.coloredCount(stats.relationships || 0)}`);
          }

          // Show checkpoint info
          if (finalJob.result?.checkpoint_created) {
            console.log('\n' + colors.status.dim('✓ Checkpoint backup created and deleted after successful restore'));
          }

          console.log('\n' + separator() + '\n');

        } else if (finalJob.status === 'failed') {
          spinner.fail('Restore failed');

          console.log('\n' + separator());
          console.log(colors.status.error('✗ Restore Failed'));
          console.log(separator());

          if (finalJob.error) {
            console.log(`\n  ${colors.status.error(finalJob.error)}`);
          }

          // Check if rollback happened
          if (finalJob.error && finalJob.error.includes('rolled back')) {
            console.log(`\n  ${colors.status.success('✓ Database rolled back to checkpoint - no data loss')}`);
          }

          console.log('\n' + separator() + '\n');
          process.exit(1);
        }

      } catch (uploadError) {
        spinner.fail('Restore upload failed');
        throw uploadError;
      }

    } catch (error: any) {
      console.error(colors.status.error('✗ Restore failed'));
      console.error(colors.status.error(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

// ========== Reset Command ==========

const resetCommand = new Command('reset')
  .description('Reset database - DESTRUCTIVE (requires authentication)')
  .option('--no-logs', 'Do not clear log files')
  .option('--no-checkpoints', 'Do not clear checkpoint files')
  .action(async (options) => {
    try {
      const client = createClientFromEnv();

      console.log('\n' + separator());
      console.log(colors.status.error('🔄 DATABASE RESET - DESTRUCTIVE OPERATION'));
      console.log(separator());

      console.log(colors.status.error('\n⚠️  WARNING: This will DELETE ALL graph data!'));
      console.log(colors.status.dim('This operation will:'));
      console.log(colors.status.dim('  - Stop all containers'));
      console.log(colors.status.dim('  - Delete the PostgreSQL database'));
      console.log(colors.status.dim('  - Remove all data volumes'));
      console.log(colors.status.dim('  - Restart with a clean database'));
      console.log(colors.status.dim('  - Re-initialize AGE schema'));

      const confirm = await prompt('\nType "yes" to confirm: ');

      if (confirm.toLowerCase() !== 'yes') {
        console.log(colors.status.dim('\nCancelled\n'));
        process.exit(0);
      }

      // Get authentication
      // NOTE: Placeholder auth for testing (see ADR-016 for future auth system)
      // Currently validates: username exists in config, password length >= 4
      // Future: Will validate against proper auth system with hashed passwords
      console.log('\n' + colors.status.warning('Authentication required:'));

      const config = getConfig();
      // Get username from config
      const username = config.get('username') || config.getClientId();
      if (!username) {
        console.error(colors.status.error('✗ Username not configured. Run: kg config set username <your-username>'));
        process.exit(1);
      }

      console.log(colors.status.dim(`Using username: ${username}`));
      const password = await promptPassword('Password: ');

      if (!password) {
        console.error(colors.status.error('✗ Password required'));
        process.exit(1);
      }

      console.log(colors.status.info('\nResetting database (this may take a minute)...'));

      const result = await client.resetDatabase({
        username,
        password,
        confirm: true,
        clear_logs: options.logs !== false,
        clear_checkpoints: options.checkpoints !== false
      });

      console.log('\n' + separator());
      console.log(colors.status.success('✓ Reset Complete'));
      console.log(separator());

      console.log('\n' + colors.ui.header('Schema Validation:'));
      console.log(`  ${colors.ui.key('Constraints:')} ${colors.coloredCount(result.schema_validation.constraints_count)}/3`);
      console.log(`  ${colors.ui.key('Vector Index:')} ${result.schema_validation.vector_index_exists ? colors.status.success('Yes') : colors.status.error('No')}`);
      console.log(`  ${colors.ui.key('Nodes:')} ${colors.coloredCount(result.schema_validation.node_count)}`);
      console.log(`  ${colors.ui.key('Test Passed:')} ${result.schema_validation.schema_test_passed ? colors.status.success('Yes') : colors.status.error('No')}`);

      if (result.warnings.length > 0) {
        console.log(`\n  ${colors.status.warning('Warnings:')}`);
        result.warnings.forEach(w => console.log(`    ${colors.status.dim('• ' + w)}`));
      }

      console.log('\n' + colors.status.success('✅ Database is now empty and ready for fresh data'));
      console.log('\n' + separator() + '\n');

    } catch (error: any) {
      console.error(colors.status.error('✗ Reset failed'));
      console.error(colors.status.error(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

// ========== Scheduler Commands (ADR-014) ==========

const schedulerStatusCommand = new Command('status')
  .description('Show job scheduler status and configuration')
  .action(async () => {
    try {
      const client = createClientFromEnv();

      console.log('\n' + separator());
      console.log(colors.ui.title('⏱️  Job Scheduler Status'));
      console.log(separator());

      const status = await client.getSchedulerStatus();

      // Running status
      console.log('\n' + colors.ui.header('Scheduler'));
      if (status.running) {
        console.log(`  ${colors.status.success('✓')} Running`);
      } else {
        console.log(`  ${colors.status.error('✗')} Not running`);
      }

      // Configuration
      console.log('\n' + colors.ui.header('Configuration'));
      console.log(`  ${colors.ui.key('Cleanup Interval:')} ${colors.ui.value(status.config.cleanup_interval + 's')} (${(status.config.cleanup_interval / 3600).toFixed(1)}h)`);
      console.log(`  ${colors.ui.key('Approval Timeout:')} ${colors.ui.value(status.config.approval_timeout + 'h')}`);
      console.log(`  ${colors.ui.key('Completed Retention:')} ${colors.ui.value(status.config.completed_retention + 'h')}`);
      console.log(`  ${colors.ui.key('Failed Retention:')} ${colors.ui.value(status.config.failed_retention + 'h')}`);

      // Statistics
      if (status.stats) {
        console.log('\n' + colors.ui.header('Job Statistics'));

        if (status.stats.jobs_by_status) {
          Object.entries(status.stats.jobs_by_status).forEach(([jobStatus, count]) => {
            console.log(`  ${colors.ui.key(jobStatus + ':')} ${colors.coloredCount(count as number)}`);
          });
        }

        if (status.stats.last_cleanup) {
          console.log(`\n  ${colors.ui.key('Last Cleanup:')} ${colors.ui.value(new Date(status.stats.last_cleanup).toLocaleString())}`);
        }

        if (status.stats.next_cleanup) {
          console.log(`  ${colors.ui.key('Next Cleanup:')} ${colors.ui.value(new Date(status.stats.next_cleanup).toLocaleString())}`);
        }
      }

      console.log('\n' + separator() + '\n');

    } catch (error: any) {
      console.error(colors.status.error('✗ Failed to get scheduler status'));
      console.error(colors.status.error(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

const schedulerCleanupCommand = new Command('cleanup')
  .description('Manually trigger scheduler cleanup (cancels expired jobs, deletes old jobs)')
  .action(async () => {
    try {
      const client = createClientFromEnv();

      console.log('\n' + separator());
      console.log(colors.ui.title('🧹 Manual Scheduler Cleanup'));
      console.log(separator());

      console.log(colors.status.info('\nTriggering cleanup...'));

      const result = await client.triggerSchedulerCleanup();

      console.log('\n' + separator());
      console.log(colors.status.success('✓ Cleanup Complete'));
      console.log(separator());

      if (result.message) {
        console.log(`\n  ${colors.ui.value(result.message)}`);
      }

      if (result.note) {
        console.log(`  ${colors.status.dim(result.note)}`);
      }

      console.log('\n' + separator() + '\n');

    } catch (error: any) {
      console.error(colors.status.error('✗ Cleanup failed'));
      console.error(colors.status.error(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

const schedulerCommand = new Command('scheduler')
  .description('Job scheduler management (ADR-014)')
  .addCommand(schedulerStatusCommand)
  .addCommand(schedulerCleanupCommand);

// ========== Main Admin Command ==========

export const adminCommand = new Command('admin')
  .description('System administration (status, backup, restore, reset, scheduler)')
  .addCommand(statusCommand)
  .addCommand(backupCommand)
  .addCommand(listBackupsCommand)
  .addCommand(restoreCommand)
  .addCommand(resetCommand)
  .addCommand(schedulerCommand);

// Configure colored help for all admin commands
[statusCommand, backupCommand, listBackupsCommand, restoreCommand, resetCommand, schedulerCommand, schedulerStatusCommand, schedulerCleanupCommand].forEach(configureColoredHelp);
