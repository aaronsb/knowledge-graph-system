/**
 * Health check command
 */

import { Command } from 'commander';
import chalk from 'chalk';
import { createClientFromEnv } from '../api/client';
import { setCommandHelp } from './help-formatter';

export const healthCommand = setCommandHelp(
  new Command('health'),
  'Check API server health',
  'Check API server health and retrieve service information. Verifies the server is running and responsive. Use this as a first diagnostic step before running other commands.'
)
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
