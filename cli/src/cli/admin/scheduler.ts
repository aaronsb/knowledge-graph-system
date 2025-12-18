/**
 * Admin Scheduler Commands
 * Job scheduler management (ADR-014)
 */

import { Command } from 'commander';
import { createClientFromEnv } from '../../api/client';
import * as colors from '../colors';
import { separator, coloredCount } from '../colors';

export function createSchedulerCommand(): Command {
  const schedulerCommand = new Command('scheduler')
    .description('Job scheduler management (ADR-014 job queue) - monitor worker status, cleanup stale jobs');

  // scheduler status
  schedulerCommand.addCommand(
    new Command('status')
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
                console.log(`  ${colors.ui.key(jobStatus + ':')} ${coloredCount(count as number)}`);
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
      })
  );

  // scheduler cleanup
  schedulerCommand.addCommand(
    new Command('cleanup')
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
      })
  );

  return schedulerCommand;
}
