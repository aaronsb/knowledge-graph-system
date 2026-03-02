/**
 * Admin Workers Commands (ADR-100)
 * Worker lane management - monitor slot utilization, queue depth, active jobs
 */

import { Command } from 'commander';
import { createClientFromEnv } from '../../api/client';
import * as colors from '../colors';
import { separator, coloredCount } from '../colors';

function formatDuration(startedAt: string | null): string {
  if (!startedAt) return 'unknown';
  const utcTimestamp = startedAt.endsWith('Z') ? startedAt : startedAt + 'Z';
  const seconds = Math.floor((Date.now() - new Date(utcTimestamp).getTime()) / 1000);
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}

export function createWorkersCommand(): Command {
  const workersCommand = new Command('workers')
    .description('Worker lane management (ADR-100) - monitor slot utilization, queue depth, active jobs')
    .action(async () => {
      try {
        const client = createClientFromEnv();

        console.log('\n' + separator());
        console.log(colors.ui.title('⚙️  Worker Status'));
        console.log(separator());

        const status = await client.getWorkerStatus();

        // Slot summary
        console.log('\n' + colors.ui.header('Slot Utilization'));
        console.log(`  ${colors.ui.key('Slots In Use:')} ${coloredCount(status.slots_in_use)}/${colors.ui.value(String(status.total_slots))}`);
        console.log(`  ${colors.ui.key('Running Jobs:')} ${coloredCount(status.running_count)}`);
        console.log(`  ${colors.ui.key('Queued Jobs:')}  ${coloredCount(status.total_queued)}`);

        // Lane summary
        console.log('\n' + colors.ui.header('Lanes'));
        for (const lane of status.lanes) {
          const icon = lane.enabled ? colors.status.success('✓') : colors.status.error('✗');
          const label = lane.enabled
            ? colors.ui.value(`${lane.max_slots} slots`)
            : colors.status.dim('disabled');
          console.log(`  ${icon} ${colors.ui.key(lane.name + ':')} ${label}`);
        }

        // Running jobs
        if (status.running_jobs.length > 0) {
          console.log('\n' + colors.ui.header('Active Jobs'));
          for (const job of status.running_jobs) {
            const shortId = job.job_id.substring(0, 8);
            const duration = formatDuration(job.started_at);
            console.log(`  ${colors.ui.key(shortId + '...')} ${colors.ui.value(job.job_type)} ${colors.status.dim(`(${duration})`)}`);
          }
        }

        // Queue depth
        if (status.queued_by_type.length > 0) {
          console.log('\n' + colors.ui.header('Queue Depth'));
          for (const q of status.queued_by_type) {
            console.log(`  ${colors.ui.key(q.job_type + ':')} ${coloredCount(q.count)}`);
          }
        }

        console.log('\n' + separator() + '\n');

      } catch (error: any) {
        console.error(colors.status.error('✗ Failed to get worker status'));
        console.error(colors.status.error(error.response?.data?.detail || error.message));
        process.exit(1);
      }
    });

  // workers lanes subcommand
  workersCommand.addCommand(
    new Command('lanes')
      .description('Show worker lane configuration and utilization')
      .action(async () => {
        try {
          const client = createClientFromEnv();

          console.log('\n' + separator());
          console.log(colors.ui.title('⚙️  Worker Lanes'));
          console.log(separator());

          const result = await client.getWorkerLanes();

          for (const lane of result.lanes) {
            const icon = lane.enabled ? colors.status.success('✓') : colors.status.error('✗');
            console.log(`\n  ${icon} ${colors.ui.header(lane.name)}`);
            console.log(`    ${colors.ui.key('Job Types:')}     ${colors.ui.value(lane.job_types.join(', '))}`);
            console.log(`    ${colors.ui.key('Slots:')}         ${coloredCount(lane.running_jobs)}/${colors.ui.value(String(lane.max_slots))} (${lane.slots_available} available, ${lane.queued_jobs} queued)`);
            console.log(`    ${colors.ui.key('Poll Interval:')} ${colors.ui.value(`${(lane.poll_interval_ms / 1000).toFixed(1)}s`)}`);
            console.log(`    ${colors.ui.key('Stale Timeout:')} ${colors.ui.value(`${lane.stale_timeout_minutes}m`)}`);
          }

          console.log('\n' + separator() + '\n');

        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to get worker lanes'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  );

  return workersCommand;
}
