/**
 * Health check command
 */

import { Command } from 'commander';
import chalk from 'chalk';
import { createClientFromEnv } from '../api/client';

export const healthCommand = new Command('health')
  .description('Check API server health')
  .showHelpAfterError()
  .action(async () => {
    try {
      const client = createClientFromEnv();

      console.log(chalk.blue('Checking API health...'));
      const health = await client.health();

      console.log(chalk.green('✓ API is healthy'));
      console.log(JSON.stringify(health, null, 2));

      // Get info
      const info = await client.info();
      console.log(chalk.blue('\nAPI Info:'));
      console.log(JSON.stringify(info, null, 2));
    } catch (error: any) {
      console.error(chalk.red('✗ API health check failed'));
      console.error(chalk.red(error.message));
      process.exit(1);
    }
  });
