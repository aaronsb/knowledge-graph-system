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
import { registerAuthAdminCommand } from './auth-admin';
import { createRbacCommand } from './rbac';
import { createEmbeddingCommand, createExtractionCommand, createKeysCommand } from './ai-config';

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
 * Prompt user to hold Enter key for specified duration
 * "Human CAPTCHA" - requires physical key press, resistant to automation
 *
 * Implements dual-timeout safety mechanism:
 * - 10-second inactivity timeout: Detects AI agents (provides helpful guidance)
 * - 3-second hold requirement: Confirms deliberate human action
 *
 * Uses polling approach: Every 500ms, checks if Enter is pressed
 * - If Enter detected: Add 500ms to progress
 * - If Enter not detected: Fail with "Released too early"
 * - When progress >= 3000ms: Success
 *
 * Timeline for humans: Read (2-3s) + Hold (3s) = ~5-6s total → Success
 * Timeline for AI: Read (instant) + Wait → 10s timeout → Helpful message
 *
 * @param message - Message to display
 * @param durationMs - Duration to hold in milliseconds (default: 3000ms / 3s)
 * @param timeoutMs - Inactivity timeout for AI detection (default: 10000ms / 10s)
 * @returns Promise that resolves true if held long enough, false if cancelled/timeout
 */
function promptHoldEnter(message: string, durationMs: number = 3000, timeoutMs: number = 10000): Promise<boolean> {
  return new Promise((resolve) => {
    const pollInterval = 500; // Poll every 500ms
    let accumulated = 0; // Accumulated time in ms
    let interval: NodeJS.Timeout | null = null;
    let inactivityTimeout: NodeJS.Timeout | null = null;
    let enterPressed = false; // Track if Enter is currently pressed
    let started = false;
    let decompressionMode = false; // "Drain" mode - wait for Space after success

    // Show instruction
    process.stdout.write(`\n${message}\n`);
    process.stdout.write(colors.status.warning(`Hold ${colors.ui.value('[Enter]')} for ${durationMs / 1000} seconds to confirm...\n`));
    process.stdout.write(colors.status.dim('(Physical confirmation required - prevents accidental AI/automation execution)\n'));
    process.stdout.write(colors.status.dim('(Press Ctrl+C to cancel)\n\n'));

    // Enter raw mode to capture key events
    if (process.stdin.isTTY) {
      process.stdin.setRawMode(true);
    }
    process.stdin.resume();
    process.stdin.setEncoding('utf8');

    const updateProgress = () => {
      const barWidth = 30;
      const progress = Math.min(accumulated / durationMs, 1);
      const filled = Math.floor(progress * barWidth);
      const empty = barWidth - filled;
      const bar = '█'.repeat(filled) + '░'.repeat(empty);
      const percent = Math.floor(progress * 100);

      process.stdout.write('\r' + colors.status.info(`${bar} ${percent}%`));
    };

    const cleanup = () => {
      if (interval) clearInterval(interval);
      if (inactivityTimeout) clearTimeout(inactivityTimeout);
      if (process.stdin.isTTY) {
        process.stdin.setRawMode(false);
      }
      process.stdin.pause();
      process.stdin.removeAllListeners('data');
      process.stdout.write('\n\n');
    };

    // AI detection: 10-second inactivity timeout
    inactivityTimeout = setTimeout(() => {
      cleanup();
      process.stdout.write('\n' + separator());
      process.stdout.write(colors.status.warning('\n⏱️  No input detected after 10 seconds.\n'));
      process.stdout.write('\n' + colors.status.dim('If you\'re an AI agent reading this:\n'));
      process.stdout.write(colors.status.dim('  This operation will ') + colors.status.error('PERMANENTLY DELETE') + colors.status.dim(' all graph data.\n'));
      process.stdout.write(colors.status.dim('  You cannot undo this action.\n'));
      process.stdout.write('\n' + colors.status.info('  → Please ask your human to run this command directly.\n'));
      process.stdout.write(colors.status.info('  → They will need to hold Enter for 3 seconds.\n'));
      process.stdout.write('\n' + colors.status.dim('Exiting...\n'));
      process.stdout.write(separator() + '\n\n');
      resolve(false);
    }, timeoutMs);

    const onKeyPress = (key: string) => {
      // Ctrl+C always cancels
      if (key === '\u0003') {
        cleanup();
        process.stdout.write(colors.status.dim('Cancelled\n\n'));
        resolve(false);
        return;
      }

      // Decompression mode: drain Enter events, wait for Space
      if (decompressionMode) {
        if (key === '\r' || key === '\n') {
          // Ignore Enter keypresses - just drain them
          return;
        } else if (key === ' ') {
          // Space pressed - user ready to continue
          cleanup();
          process.stdout.write(colors.status.success('✓ Ready!\n'));
          resolve(true);
          return;
        }
        // Ignore all other keys in decompression mode
        return;
      }

      // Enter key pressed (both \r and \n)
      if (key === '\r' || key === '\n') {
        enterPressed = true;

        if (!started) {
          // First Enter press - cancel inactivity timeout, start polling
          started = true;
          if (inactivityTimeout) {
            clearTimeout(inactivityTimeout);
            inactivityTimeout = null;
          }

          // Start polling every 500ms
          interval = setInterval(() => {
            if (enterPressed) {
              // Enter still pressed - add 500ms to accumulated time
              accumulated += pollInterval;
              updateProgress();

              // Success - accumulated enough time
              if (accumulated >= durationMs) {
                // Clear the interval, but DON'T cleanup yet
                if (interval) clearInterval(interval);
                interval = null;

                // Show success and wait for user to release Enter and press Space
                process.stdout.write(colors.status.success('\n✓ Confirmed! You\'re probably human! 👩‍💻\n'));
                process.stdout.write(colors.status.info('Release Enter and press [Space] to continue...\n'));

                // Switch to "decompression mode" - drain Enter events, wait for Space
                // This prevents Enter keypresses from bleeding into the next prompt
                decompressionMode = true;
              }
            } else {
              // Enter not pressed during this poll - released too early
              cleanup();
              process.stdout.write(colors.status.warning('\n✗ Released too early\n\n'));
              resolve(false);
            }

            // Reset flag for next poll
            enterPressed = false;
          }, pollInterval);

          updateProgress();
        }
      } else {
        // Any other key - cancel
        if (started && !decompressionMode) {
          cleanup();
          process.stdout.write(colors.status.warning('\n✗ Cancelled\n\n'));
          resolve(false);
        }
      }
    };

    process.stdin.on('data', onKeyPress);
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
        // Finalize the multi-progress display
        const logUpdate = require('log-update').default || require('log-update');
        const state: MultiProgressState = (spinner as any).__multiProgress;

        if (state) {
          // Mark all stages as completed and render final state
          state.orderedStages.forEach(stageName => {
            const stageData = state.stages.get(stageName)!;
            if (stageData.status === 'active') {
              stageData.status = 'completed';
              if (stageData.total === 0 && stageData.current > 0) {
                stageData.total = stageData.current;
              }
            }
          });

          // Render final state
          const lines: string[] = [];
          state.orderedStages.forEach(stageName => {
            const stageData = state.stages.get(stageName)!;
            if (stageData.total > 0) {
              const progressBar = createProgressBar(stageData.total, stageData.total);
              lines.push(colors.status.success('✓') + ` ${stageData.name} ${progressBar} ${stageData.total}/${stageData.total}`);
            } else if (stageData.status === 'completed') {
              lines.push(colors.status.success('✓') + ` ${stageData.name}`);
            }
          });

          // Finalize and persist the output
          logUpdate(lines.join('\n'));
          logUpdate.done();
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
 * Multi-line progress display using log-update
 * Pre-allocates all stage lines and updates them in place
 */
interface MultiProgressState {
  stages: Map<string, StageProgress>;
  orderedStages: string[];
}

interface StageProgress {
  name: string;
  status: 'waiting' | 'active' | 'completed';
  current: number;
  total: number;
}

/**
 * Update multi-line progress display (pre-allocated lines)
 */
function updateSpinnerForProgress(spinner: any, progress: JobProgress): any {
  const logUpdate = require('log-update').default || require('log-update');

  // Initialize multi-progress state
  if (!(spinner as any).__multiProgress) {
    const stages = new Map<string, StageProgress>();
    const orderedStages = [
      'creating_checkpoint',
      'loading_backup',
      'restoring_concepts',
      'restoring_sources',
      'restoring_instances',
      'restoring_relationships'
    ];

    // Pre-allocate all stages
    orderedStages.forEach(stage => {
      stages.set(stage, {
        name: getStageName(stage),
        status: 'waiting',
        current: 0,
        total: 0
      });
    });

    (spinner as any).__multiProgress = {
      stages,
      orderedStages
    } as MultiProgressState;
  }

  const state: MultiProgressState = (spinner as any).__multiProgress;

  // Update the specific stage with progress
  if (state.stages.has(progress.stage)) {
    const stageData = state.stages.get(progress.stage)!;

    // Extract current/total from message
    if (progress.message) {
      const match = progress.message.match(/(\d+)\/(\d+)/);
      if (match) {
        stageData.current = parseInt(match[1]);
        stageData.total = parseInt(match[2]);
        stageData.status = stageData.current === stageData.total ? 'completed' : 'active';
      } else {
        stageData.status = 'active';
      }
    } else if (progress.items_total && progress.items_processed !== undefined) {
      stageData.current = progress.items_processed;
      stageData.total = progress.items_total;
      stageData.status = stageData.current === stageData.total ? 'completed' : 'active';
    } else {
      stageData.status = 'active';
    }
  }

  // Render all stages
  const lines: string[] = [];
  state.orderedStages.forEach(stageName => {
    const stageData = state.stages.get(stageName)!;

    if (stageData.status === 'completed') {
      const progressBar = createProgressBar(stageData.total, stageData.total);
      lines.push(colors.status.success('✓') + ` ${stageData.name} ${progressBar} ${stageData.total}/${stageData.total}`);
    } else if (stageData.status === 'active') {
      if (stageData.total > 0) {
        const progressBar = createProgressBar(stageData.current, stageData.total);
        lines.push(colors.status.info('⠋') + ` ${stageData.name} ${progressBar} ${stageData.current}/${stageData.total}`);
      } else {
        lines.push(colors.status.info('⠋') + ` ${stageData.name}...`);
      }
    } else {
      // waiting
      lines.push(colors.status.dim('○') + ` ${stageData.name}`);
    }
  });

  // Update all lines at once
  logUpdate(lines.join('\n'));

  return spinner;
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
  .option('--format <format>', 'Export format: "json" (native, restorable) or "gexf" (Gephi visualization)', 'json')
  .action(async (options) => {
    try {
      const client = createClientFromEnv();

      console.log('\n' + separator());
      console.log(colors.ui.title('💾 Database Backup'));
      console.log(separator());

      let backupType: 'full' | 'ontology' = 'full';
      let ontologyName: string | undefined;
      let format: 'json' | 'gexf' = options.format || 'json';

      // Validate format
      if (format !== 'json' && format !== 'gexf') {
        console.error(colors.status.error('✗ Invalid format. Must be "json" or "gexf"'));
        process.exit(1);
      }

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
      const fileExtension = format === 'gexf' ? '.gexf' : '.json';

      if (options.output) {
        // Custom filename specified - ensure correct extension
        const hasExtension = options.output.endsWith('.json') || options.output.endsWith('.gexf');
        savePath = path.join(backupDir, hasExtension ? options.output : `${options.output}${fileExtension}`);
      } else {
        // Use timestamped filename (will be overwritten with server-provided name)
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-').split('T')[0];
        savePath = path.join(backupDir, `temp_${timestamp}${fileExtension}`);
      }

      // Download backup with progress tracking using ora
      const ora = require('ora');
      const spinner = ora('Preparing backup...').start();

      try {
        const result = await client.createBackup(
          {
            backup_type: backupType,
            ontology_name: ontologyName,
            format: format
          },
          savePath,
          (downloaded: number, total: number, percent: number) => {
            const downloadedMB = (downloaded / (1024 * 1024)).toFixed(2);
            const totalMB = (total / (1024 * 1024)).toFixed(2);
            spinner.text = `Downloading ${format.toUpperCase()} backup... ${percent}% (${downloadedMB}/${totalMB} MB)`;
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
  .option('--merge', 'Merge into existing ontology if it exists (default: error if ontology exists)', false)
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
          !options.merge,  // Invert: merge=false means overwrite=true (create new concepts)
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

      // "Human CAPTCHA" - physical confirmation required
      // This deliberate friction reduces risk of accidental execution by AI agents or automation
      const confirmed = await promptHoldEnter(
        colors.status.error('🚨 This action cannot be undone!')
      );

      if (!confirmed) {
        console.log(colors.status.dim('Cancelled\n'));
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
      console.log(colors.status.dim(`\n  Note: "Constraints" = PostgreSQL schemas (kg_api, kg_auth, kg_logs)`));
      console.log(colors.status.dim(`        "Vector Index" = AGE graph exists (Apache AGE doesn't use Neo4j indexes)`));

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
  .description('System administration (status, backup, restore, reset, scheduler, user, rbac, embedding, extraction, keys)')
  .showHelpAfterError('(add --help for additional information)')
  .showSuggestionAfterError()
  .addCommand(statusCommand)
  .addCommand(backupCommand)
  .addCommand(listBackupsCommand)
  .addCommand(restoreCommand)
  .addCommand(resetCommand)
  .addCommand(schedulerCommand);

// ADR-027: Register user management commands
registerAuthAdminCommand(adminCommand);

// ADR-028: Register RBAC management commands
const client = createClientFromEnv();
const rbacCommand = createRbacCommand(client);
configureColoredHelp(rbacCommand);
adminCommand.addCommand(rbacCommand);

// ADR-039, ADR-041: Register AI configuration commands
const embeddingCommand = createEmbeddingCommand(client);
const extractionCommand = createExtractionCommand(client);
const keysCommand = createKeysCommand(client);

configureColoredHelp(embeddingCommand);
configureColoredHelp(extractionCommand);
configureColoredHelp(keysCommand);

adminCommand.addCommand(embeddingCommand);
adminCommand.addCommand(extractionCommand);
adminCommand.addCommand(keysCommand);

// Configure colored help for all admin commands
[statusCommand, backupCommand, listBackupsCommand, restoreCommand, resetCommand, schedulerCommand, schedulerStatusCommand, schedulerCleanupCommand].forEach(configureColoredHelp);
