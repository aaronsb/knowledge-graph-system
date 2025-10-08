/**
 * CLI Command Registration
 */

import { Command } from 'commander';
import cfonts from 'cfonts';
import * as colors from './colors';
import { configureColoredHelp } from './help-formatter';
import { ingestCommand } from './ingest';
import { jobsCommand } from './jobs';
import { healthCommand } from './health';
import { searchCommand } from './search';
import { databaseCommand } from './database';
import { ontologyCommand } from './ontology';
import { configCommand } from './config';
import { createClientFromEnv } from '../api/client';
import { VERSION_INFO } from '../version';

/**
 * Display stylized banner with API status
 */
async function showBanner() {
  cfonts.say('Knowledge|Graph', {
    font: 'chrome',
    colors: ['#00D7FF', '#00D7AF', '#00D787'],  // Cyan → Teal → Green tricolor gradient
    align: 'left',
    space: true,
    gradient: true,
    letterSpacing: 1,
    lineHeight: 1,
  });

  console.log(colors.status.dim('  Multi-dimensional knowledge exploration through concept graphs\n'));

  // Show API URL and status
  const apiUrl = process.env.KG_API_URL || 'http://localhost:8000';
  try {
    const client = createClientFromEnv();
    await client.health();
    console.log(`  ${colors.ui.key('API:')} ${colors.ui.value(apiUrl)} ${colors.status.success('✓')}`);
  } catch (error) {
    console.log(`  ${colors.ui.key('API:')} ${colors.ui.value(apiUrl)} ${colors.status.error('✗')}`);
  }

  // Show version info
  const parts: string[] = [];
  parts.push(colors.ui.value(VERSION_INFO.tag));
  if (VERSION_INFO.commit) parts.push(colors.status.dim(VERSION_INFO.commit));
  console.log(`  ${colors.ui.key('Build:')} ${parts.join(' ')}`);

  console.log(); // Empty line
}

export async function registerCommands(program: Command) {
  // Show banner ONLY if kg is run without any arguments
  if (process.argv.length === 2) {
    await showBanner();
  }

  program
    .name('kg')
    .description('Knowledge Graph CLI - interact with the knowledge graph API')
    .version('0.1.0');

  // Configure colored help for main command
  configureColoredHelp(program);

  // Register subcommands with colored help
  const subcommands = [
    healthCommand,
    configCommand,
    ingestCommand,
    jobsCommand,
    searchCommand,
    databaseCommand,
    ontologyCommand
  ];

  subcommands.forEach(cmd => {
    configureColoredHelp(cmd);
    program.addCommand(cmd);
  });

  // Global options
  program.option(
    '--api-url <url>',
    'API base URL'
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
