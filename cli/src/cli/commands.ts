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
import { conceptCommand } from './concept';
import { edgeCommand } from './edge';
import { batchCommand } from './batch';
import { storageCommand } from './storage';
import { catalogCommand } from './catalog';
import { programCommand } from './program';
import { registerLoginCommand, loginCommand_obj } from './login';
import { registerLogoutCommand, logoutCommand_obj } from './logout';
import { registerOAuthCommand, oauthCommand } from './oauth';
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

  // Show auto-approve status (ADR-300) - only if enabled
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

/**
 * Subcommands registered under `kg`, in display order.
 *
 * Module-level and exported so the doc generator
 * (cli/scripts/simple-doc-gen.mjs) derives the command list from the same
 * source the CLI registers — this is what prevents the two from drifting (the
 * generator previously kept its own hardcoded list, which silently went stale
 * and dropped commands like `catalog`).
 */
export const subcommands: Command[] = [
  healthCommand,
  configCommand,
  mcpConfigCommand,
  ingestCommand,
  jobsCommand,
  searchCommand,
  documentCommand,  // ADR-507: Document search
  databaseCommand,
  ontologyCommand,
  sourceCommand,
  vocabularyCommand,
  conceptCommand,   // ADR-308: Concept CRUD
  edgeCommand,      // ADR-308: Edge CRUD
  batchCommand,     // ADR-308: Batch operations
  adminCommand,
  polarityCommand,
  projectionCommand,
  artifactCommand,
  groupCommand,
  queryDefCommand,
  programCommand,   // ADR-500: GraphProgram notarization
  storageCommand,
  catalogCommand,   // ADR-501: Catalog browse facade
];

/**
 * Full set of top-level commands for documentation: the subcommands plus the
 * auth commands. The auth commands are wired into the program via their own
 * register*() functions (which attach actions/options), but they also expose
 * Command objects so the doc generator can describe them.
 *
 * Order mirrors runtime registration (subcommands first, then auth) so the
 * generated docs match `kg --help`; keep them aligned if registration moves.
 */
export const documentedCommands: Command[] = [
  ...subcommands,
  loginCommand_obj,
  logoutCommand_obj,
  oauthCommand,
];

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

  // Register subcommands with colored help (see the exported `subcommands`
  // registry above — single source of truth shared with the doc generator).
  subcommands.forEach(cmd => {
    configureColoredHelp(cmd);
    program.addCommand(cmd);
  });

  // ADR-403: Register authentication commands (login, logout)
  registerLoginCommand(program);
  registerLogoutCommand(program);

  // ADR-406: Register OAuth client management commands
  registerOAuthCommand(program);

  // ADR-709: Register Unix-style verb shortcuts (ls, rm, stat, cat)
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
