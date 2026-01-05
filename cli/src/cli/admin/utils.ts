/**
 * Admin Utility Functions
 * Shared utilities for admin commands
 */

import * as readline from 'readline';
import * as colors from '../colors';
import { separator } from '../colors';
import { createClientFromEnv } from '../../api/client';
import { trackJobProgress } from '../../lib/job-stream';
import type { JobStatus, JobProgress } from '../../types';

/**
 * Prompt for input from user
 */
export function prompt(question: string): Promise<string> {
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
export function promptPassword(question: string): Promise<string> {
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
 */
export function promptHoldEnter(message: string, durationMs: number = 3000, timeoutMs: number = 10000): Promise<boolean> {
  return new Promise((resolve) => {
    const pollInterval = 500;
    let accumulated = 0;
    let interval: NodeJS.Timeout | null = null;
    let inactivityTimeout: NodeJS.Timeout | null = null;
    let enterPressed = false;
    let started = false;
    let decompressionMode = false;

    process.stdout.write(`\n${message}\n`);
    process.stdout.write(colors.status.warning(`Hold ${colors.ui.value('[Enter]')} for ${durationMs / 1000} seconds to confirm...\n`));
    process.stdout.write(colors.status.dim('(Physical confirmation required - prevents accidental AI/automation execution)\n'));
    process.stdout.write(colors.status.dim('(Press Ctrl+C to cancel)\n\n'));

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
      if (key === '\u0003') {
        cleanup();
        process.stdout.write(colors.status.dim('Cancelled\n\n'));
        resolve(false);
        return;
      }

      if (decompressionMode) {
        if (key === '\r' || key === '\n') {
          return;
        } else if (key === ' ') {
          cleanup();
          process.stdout.write(colors.status.success('✓ Ready!\n'));
          resolve(true);
          return;
        }
        return;
      }

      if (key === '\r' || key === '\n') {
        enterPressed = true;

        if (!started) {
          started = true;
          if (inactivityTimeout) {
            clearTimeout(inactivityTimeout);
            inactivityTimeout = null;
          }

          interval = setInterval(() => {
            if (enterPressed) {
              accumulated += pollInterval;
              updateProgress();

              if (accumulated >= durationMs) {
                if (interval) clearInterval(interval);
                interval = null;

                process.stdout.write(colors.status.success('\n✓ Confirmed! You\'re probably human! 👩‍💻\n'));
                process.stdout.write(colors.status.info('Release Enter and press [Space] to continue...\n'));
                decompressionMode = true;
              }
            } else {
              cleanup();
              process.stdout.write(colors.status.warning('\n✗ Released too early\n\n'));
              resolve(false);
            }
            enterPressed = false;
          }, pollInterval);

          updateProgress();
        }
      } else {
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
 * Multi-line progress display state
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
 * Create a visual progress bar
 */
export function createProgressBar(current: number, total: number, width: number = 20): string {
  if (total === 0) return '░'.repeat(width);
  const percent = Math.min(current / total, 1);
  const filled = Math.floor(percent * width);
  const empty = width - filled;
  return '█'.repeat(filled) + '░'.repeat(empty);
}

/**
 * Update multi-line progress display
 */
function updateSpinnerForProgress(spinner: any, progress: JobProgress): any {
  const logUpdate = require('log-update').default || require('log-update');

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

    orderedStages.forEach(stage => {
      stages.set(stage, {
        name: getStageName(stage),
        status: 'waiting',
        current: 0,
        total: 0
      });
    });

    (spinner as any).__multiProgress = { stages, orderedStages } as MultiProgressState;
  }

  const state: MultiProgressState = (spinner as any).__multiProgress;

  if (state.stages.has(progress.stage)) {
    const stageData = state.stages.get(progress.stage)!;

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
      lines.push(colors.status.dim('○') + ` ${stageData.name}`);
    }
  });

  logUpdate(lines.join('\n'));
  return spinner;
}

/**
 * Track job progress with polling (simpler alternative to SSE)
 *
 * Used for restore operations where SSE has timing issues with EventSource library.
 */
export async function trackJobWithPolling(
  client: ReturnType<typeof createClientFromEnv>,
  jobId: string,
  spinner: any
): Promise<JobStatus> {
  return client.pollJob(jobId, (job) => {
    if (job.progress) {
      spinner = updateSpinnerForProgress(spinner, job.progress);
    }
  });
}

/**
 * Track job progress with SSE streaming (ADR-018 Phase 1)
 */
export async function trackJobWithSSE(
  client: ReturnType<typeof createClientFromEnv>,
  jobId: string,
  spinner: any
): Promise<JobStatus> {
  const baseUrl = process.env.API_BASE_URL || 'http://localhost:8000';
  let settled = false; // Track if promise is already resolved/rejected
  let stream: ReturnType<typeof trackJobProgress> extends Promise<infer T> ? T : never = null;

  return new Promise((resolve, reject) => {
    const safeResolve = (job: JobStatus) => {
      if (settled) return;
      settled = true;
      // Close stream before resolving to prevent late errors
      if (stream) {
        try { stream.close(); } catch { /* ignore */ }
      }
      resolve(job);
    };

    const safeReject = (error: Error) => {
      if (settled) return;
      settled = true;
      if (stream) {
        try { stream.close(); } catch { /* ignore */ }
      }
      reject(error);
    };

    trackJobProgress(baseUrl, jobId, {
      onProgress: (progress: JobProgress) => {
        if (settled) return;
        spinner = updateSpinnerForProgress(spinner, progress);
      },
      onCompleted: (result) => {
        if (settled) return;

        try {
          const logUpdate = require('log-update').default || require('log-update');
          const state: MultiProgressState = (spinner as any).__multiProgress;

          if (state) {
            state.orderedStages.forEach(stageName => {
              const stageData = state.stages.get(stageName)!;
              if (stageData.status === 'active') {
                stageData.status = 'completed';
                if (stageData.total === 0 && stageData.current > 0) {
                  stageData.total = stageData.current;
                }
              }
            });

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

            logUpdate(lines.join('\n'));
            logUpdate.done();
          }
        } catch { /* ignore UI errors */ }

        // SSE already provides the result - construct JobStatus from it
        const jobStatus: JobStatus = {
          job_id: jobId,
          job_type: 'restore',
          status: 'completed',
          result: result,
          created_at: new Date().toISOString()
        };
        safeResolve(jobStatus);
      },
      onFailed: (error) => {
        spinner.fail('Restore failed');
        safeReject(new Error(error));
      },
      onCancelled: (message) => {
        spinner.fail('Restore cancelled');
        safeReject(new Error(message));
      },
      onError: (error) => {
        if (settled) {
          // Silently ignore errors after job completed - this is normal when SSE closes
          return;
        }
        // Fall back to polling
        client.pollJob(jobId, (job) => {
          if (job.progress) {
            spinner = updateSpinnerForProgress(spinner, job.progress);
          }
        }).then(safeResolve).catch(safeReject);
      }
    }, true).then(s => {
      stream = s;
      if (!stream && !settled) {
        // SSE unavailable, use polling
        client.pollJob(jobId, (job) => {
          if (job.progress) {
            spinner = updateSpinnerForProgress(spinner, job.progress);
          }
        }).then(safeResolve).catch(safeReject);
      }
    }).catch(err => {
      // SSE setup failed, fall back to polling
      if (!settled) {
        client.pollJob(jobId, (job) => {
          if (job.progress) {
            spinner = updateSpinnerForProgress(spinner, job.progress);
          }
        }).then(safeResolve).catch(safeReject);
      }
    });
  });
}
