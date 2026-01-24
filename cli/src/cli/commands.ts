/**
 * CLI Command Registration
 */

import { Command } from 'commander';
import pkg from '../../package.json';
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
import { adminCommand } from './admin';
import { vocabularyCommand } from './vocabulary';
import { mcpConfigCommand } from './mcp-config';
import { polarityCommand } from './polarity';
import { projectionCommand } from './projection';
import { sourceCommand } from './source';
import { documentCommand } from './document';
import { artifactCommand } from './artifact';
import { groupCommand } from './group';
import { queryDefCommand } from './query-def';
import { registerLoginCommand } from './login';
import { registerLogoutCommand } from './logout';
import { registerOAuthCommand } from './oauth';
import { createVerbRouter } from './verb-router';
import { createHelpCommand } from './help';
import { createClientFromEnv } from '../api/client';
import { VERSION_INFO } from '../version';
import { getConfig } from '../lib/config';

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

  // Show auto-approve status (ADR-014) - only if enabled
  const config = getConfig();
  const autoApprove = config.getAutoApprove();
  if (autoApprove) {
    console.log(`  ${colors.ui.key('Auto-Approve:')} ${colors.status.warning('enabled')} ${colors.status.dim('(jobs skip manual review)')}`);
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
    .version(pkg.version)
    .showHelpAfterError('(add --help for additional information)')
    .showSuggestionAfterError();

  // Configure colored help for main command
  configureColoredHelp(program);

  // Create client for command that need it
  const client = createClientFromEnv();

  // Register subcommands with colored help
  const subcommands = [
    healthCommand,
    configCommand,
    mcpConfigCommand,
    ingestCommand,
    jobsCommand,
    searchCommand,
    documentCommand,  // ADR-084: Document search
    databaseCommand,
    ontologyCommand,
    sourceCommand,
    vocabularyCommand,
    adminCommand,
    polarityCommand,
    projectionCommand,
    artifactCommand,
    groupCommand,
    queryDefCommand,
  ];

  subcommands.forEach(cmd => {
    configureColoredHelp(cmd);
    program.addCommand(cmd);
  });

  // ADR-027: Register authentication commands (login, logout)
  registerLoginCommand(program);
  registerLogoutCommand(program);

  // ADR-054: Register OAuth client management commands
  registerOAuthCommand(program);

  // ADR-029: Register Unix-style verb shortcuts (ls, rm, stat, cat)
  const verbCommands = createVerbRouter(program);
  verbCommands.forEach(cmd => {
    configureColoredHelp(cmd);
    program.addCommand(cmd);
  });

  // Register help command with commandmap subcommand
  const helpCommand = createHelpCommand(program);
  configureColoredHelp(helpCommand);
  program.addCommand(helpCommand);
}
