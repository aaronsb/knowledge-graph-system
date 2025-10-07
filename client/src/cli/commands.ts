/**
 * CLI Command Registration
 */

import { Command } from 'commander';
import { ingestCommand } from './ingest';
import { jobsCommand } from './jobs';
import { healthCommand } from './health';

export function registerCommands(program: Command) {
  program
    .name('kg')
    .description('Knowledge Graph CLI - interact with the knowledge graph API')
    .version('0.1.0');

  // Register subcommands
  program.addCommand(healthCommand);
  program.addCommand(ingestCommand);
  program.addCommand(jobsCommand);

  // Global options
  program.option(
    '--api-url <url>',
    'API base URL',
    process.env.KG_API_URL || 'http://localhost:8000'
  );

  program.option('--client-id <id>', 'Client ID for multi-tenancy', process.env.KG_CLIENT_ID);

  program.option('--api-key <key>', 'API key for authentication', process.env.KG_API_KEY);

  // Set global options in environment for client to pick up
  program.hook('preAction', (thisCommand, actionCommand) => {
    const opts = thisCommand.opts();
    if (opts.apiUrl) process.env.KG_API_URL = opts.apiUrl;
    if (opts.clientId) process.env.KG_CLIENT_ID = opts.clientId;
    if (opts.apiKey) process.env.KG_API_KEY = opts.apiKey;
  });
}
