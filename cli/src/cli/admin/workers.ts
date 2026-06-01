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
  const lanesCommand = new Command('lanes')
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
      });

  // workers lanes set <lane> — update a lane's configuration
  lanesCommand.addCommand(
      new Command('set')
        .description('Update a worker lane (slots, poll interval, stale timeout, enable/disable)')
        .argument('<lane>', 'Lane name (e.g. interactive, maintenance, system)')
        .option('--max-slots <n>', 'Max concurrent jobs in this lane (0–16)', (v) => parseInt(v, 10))
        .option('--poll-interval <ms>', 'Poll interval in milliseconds (500–120000)', (v) => parseInt(v, 10))
        .option('--stale-timeout <min>', 'Stale job timeout in minutes (5–1440)', (v) => parseInt(v, 10))
        .option('--enable', 'Enable the lane')
        .option('--disable', 'Disable the lane')
        .action(async (lane: string, opts: any) => {
          try {
            if (opts.enable && opts.disable) {
              console.error(colors.status.error('✗ Cannot use both --enable and --disable'));
              process.exit(1);
            }

            const body: {
              max_slots?: number;
              poll_interval_ms?: number;
              stale_timeout_minutes?: number;
              enabled?: boolean;
            } = {};
            if (opts.maxSlots !== undefined) body.max_slots = opts.maxSlots;
            if (opts.pollInterval !== undefined) body.poll_interval_ms = opts.pollInterval;
            if (opts.staleTimeout !== undefined) body.stale_timeout_minutes = opts.staleTimeout;
            if (opts.enable) body.enabled = true;
            if (opts.disable) body.enabled = false;

            if (Object.keys(body).length === 0) {
              console.error(colors.status.error('✗ Nothing to update'));
              console.error(colors.status.dim('  Provide at least one of: --max-slots, --poll-interval, --stale-timeout, --enable, --disable'));
              process.exit(1);
            }

            const client = createClientFromEnv();
            const result = await client.updateWorkerLane(lane, body);

            console.log('\n' + separator());
            console.log(colors.ui.title(`⚙️  Updated lane: ${lane}`));
            console.log(separator());
            for (const [field, change] of Object.entries(result.changed)) {
              console.log(`  ${colors.ui.key(field + ':')} ${colors.status.dim(String(change.old))} → ${colors.ui.value(String(change.new))}`);
            }
            console.log(colors.status.dim('\n  Changes take effect on the next poll cycle.'));
            console.log(separator() + '\n');
          } catch (error: any) {
            console.error(colors.status.error('✗ Failed to update worker lane'));
            const detail = error.response?.data?.detail;
            if (Array.isArray(detail)) {
              // FastAPI validation errors: [{loc, msg, ...}]
              for (const e of detail) {
                const field = Array.isArray(e.loc) ? e.loc[e.loc.length - 1] : 'request';
                console.error(colors.status.error(`  ${field}: ${e.msg}`));
              }
            } else {
              console.error(colors.status.error(detail || error.message));
            }
            process.exit(1);
          }
        })
    );

  workersCommand.addCommand(lanesCommand);

  return workersCommand;
}
