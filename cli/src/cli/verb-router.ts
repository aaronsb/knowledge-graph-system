/**
 * Verb Router - Unix-style command shortcuts
 *
 * Provides Unix-familiar verbs (ls, rm, stat, cat) that delegate to
 * primary noun→verb commands.
 *
 * Examples:
 *   kg ls job        → kg job list
 *   kg rm job 123    → kg job cancel 123
 *   kg stat database → kg database stats
 *   kg cat concept X → kg search details X
 *
 * Architecture: Clean delegation with no business logic
 * See: ADR-029 - CLI Theory of Operation
 *
 * User-configurable aliases:
 *   Commands can have user-defined aliases via config.aliases
 *   Example: config.aliases.cat = ['bat'] allows 'kg bat' as alias for 'kg cat'
 */

import { Command } from 'commander';
import * as colors from './colors';
import { getConfig } from '../lib/config';

/**
 * Resource routing map
 * Maps resource names to their primary command paths
 */
const RESOURCE_ROUTES = {
  // Jobs
  job: ['job'],
  jobs: ['job'],

  // Ontologies
  ontology: ['ontology'],
  ontologies: ['ontology'],
  onto: ['ontology'],

  // Database
  database: ['database'],
  db: ['database'],

  // Config
  config: ['config'],
  cfg: ['config'],

  // Roles (RBAC)
  role: ['admin', 'rbac', 'role'],
  roles: ['admin', 'rbac', 'role'],

  // Permissions (RBAC)
  permission: ['admin', 'rbac', 'permission'],
  permissions: ['admin', 'rbac', 'permission'],
  perm: ['admin', 'rbac', 'permission'],

  // Resources (RBAC)
  resource: ['admin', 'rbac', 'resource'],
  resources: ['admin', 'rbac', 'resource'],
  res: ['admin', 'rbac', 'resource'],

  // Backups
  backup: ['admin'],
  backups: ['admin'],

  // Users
  user: ['admin', 'user'],
  users: ['admin', 'user'],

  // Concepts (via search)
  concept: ['search'],
  concepts: ['search'],

  // Artifacts (ADR-083)
  artifact: ['artifact'],
  artifacts: ['artifact'],

  // Sources (ADR-081)
  source: ['source'],
  sources: ['source'],
};

/**
 * Execute a command by re-invoking the CLI with new arguments
 *
 * This is a workaround since Commander.js doesn't support dynamic command execution well.
 * We spawn a new process with the correct command structure.
 *
 * @param path - Command path (e.g., ['job', 'list'])
 * @param args - Additional arguments
 */
function executeCommand(rootCommand: Command, path: string[], args: string[] = []): void {
  const { spawn } = require('child_process');
  const { resolve } = require('path');

  // Build full command: kg <path> <args>
  const fullArgs = [...path, ...args];

  // kg is symlinked to dist/index.js
  // __dirname is dist/cli, so go up one level to dist/index.js
  const kgPath = resolve(__dirname, '..', 'index.js');

  // Execute kg with the new arguments (no shell for security)
  const child = spawn(process.execPath, [kgPath, ...fullArgs], {
    stdio: 'inherit'
  });

  child.on('exit', (code: number) => {
    process.exit(code || 0);
  });

  child.on('error', (error: Error) => {
    console.error(colors.status.error(`✗ Failed to execute command: ${error.message}`));
    process.exit(1);
  });
}

/**
 * Get resource route path
 */
function getResourceRoute(resource: string): string[] | null {
  const route = RESOURCE_ROUTES[resource.toLowerCase() as keyof typeof RESOURCE_ROUTES];
  return route || null;
}

/**
 * Apply user-configured aliases to a command (ADR-029)
 *
 * Loads aliases from config and applies them to the command using .alias()
 *
 * @param cmd The command to apply aliases to
 * @param commandName Name of the command (used to lookup aliases in config)
 */
function applyAliases(cmd: Command, commandName: string): void {
  try {
    const config = getConfig();
    const aliases = config.getCommandAliases(commandName);

    // Apply each alias
    for (const alias of aliases) {
      cmd.alias(alias);
    }
  } catch (error) {
    // Silently fail if config can't be loaded - aliases are optional
    // This prevents blocking CLI usage if config is corrupted
  }
}

/**
 * Create the ls (list) verb command
 */
function createLsCommand(rootCommand: Command): Command {
  const cmd = new Command('ls')
    .description('List resources (Unix-style shortcut)')
    .argument('<resource>', 'Resource type: job, ontology, backup, config, role, permission, resource, user, artifact, source')
    .option('--json', 'Output as JSON')
    .option('-o, --ontology <name>', 'Filter by ontology (for sources)')
    .action(async (resource: string, options) => {
      const route = getResourceRoute(resource);

      if (!route) {
        console.error(colors.status.error(`✗ Unknown resource: ${resource}`));
        console.log(colors.status.dim('\nAvailable resources:'));
        console.log(colors.status.dim('  job, ontology, backup, config, role, permission, resource, user, artifact, source'));
        console.log(colors.status.dim('\nExample: kg ls job'));
        process.exit(1);
      }

      // Special handling for different list commands
      const listArgs = ['list'];
      if (options.json) {
        listArgs.push('--json');
      }

      // Handle special cases
      if (resource === 'backup' || resource === 'backups') {
        executeCommand(rootCommand, [...route, 'list-backups'], []);
      } else if (resource === 'concept' || resource === 'concepts') {
        console.error(colors.status.error('✗ Use "kg search <text>" to search concepts'));
        process.exit(1);
      } else if (resource === 'source' || resource === 'sources') {
        // Sources support ontology filter
        if (options.ontology) {
          listArgs.push('--ontology', options.ontology);
        }
        executeCommand(rootCommand, route, listArgs);
      } else {
        executeCommand(rootCommand, route, listArgs);
      }
    });

  // Apply user-configured aliases (ADR-029)
  applyAliases(cmd, 'ls');

  return cmd;
}

/**
 * Create the stat (status/statistics) verb command
 */
function createStatCommand(rootCommand: Command): Command {
  const cmd = new Command('stat')
    .description('Show status or statistics (Unix-style shortcut)')
    .argument('<resource>', 'Resource type: job, database')
    .argument('[id]', 'Resource identifier (for jobs)')
    .option('--json', 'Output as JSON')
    .action(async (resource: string, id: string | undefined, options) => {
      const route = getResourceRoute(resource);

      if (!route) {
        console.error(colors.status.error(`✗ Unknown resource: ${resource}`));
        console.log(colors.status.dim('\nAvailable resources: job, database'));
        console.log(colors.status.dim('\nExamples:'));
        console.log(colors.status.dim('  kg stat job abc-123'));
        console.log(colors.status.dim('  kg stat database'));
        process.exit(1);
      }

      const args: string[] = [];

      // Determine verb based on resource
      if (resource === 'job' || resource === 'jobs') {
        if (!id) {
          console.error(colors.status.error('✗ Job ID required'));
          console.log(colors.status.dim('Example: kg stat job abc-123'));
          process.exit(1);
        }
        args.push('status', id);
      } else if (resource === 'database' || resource === 'db') {
        args.push('stats');
      } else {
        console.error(colors.status.error(`✗ stat not supported for ${resource}`));
        process.exit(1);
      }

      if (options.json) {
        args.push('--json');
      }

      executeCommand(rootCommand, route, args);
    });

  // Apply user-configured aliases (ADR-029)
  applyAliases(cmd, 'stat');

  return cmd;
}

/**
 * Create the rm (remove/cancel/delete) verb command
 */
function createRmCommand(rootCommand: Command): Command {
  const cmd = new Command('rm')
    .description('Remove or delete resources (Unix-style shortcut)')
    .argument('<resource>', 'Resource type: job, ontology, role, permission, user, artifact')
    .argument('<id>', 'Resource identifier')
    .option('-f, --force', 'Skip confirmation')
    .option('--json', 'Output as JSON')
    .action(async (resource: string, id: string, options) => {
      const route = getResourceRoute(resource);

      if (!route) {
        console.error(colors.status.error(`✗ Unknown resource: ${resource}`));
        console.log(colors.status.dim('\nAvailable resources: job, ontology, role, user, artifact'));
        console.log(colors.status.dim('\nExample: kg rm job abc-123'));
        process.exit(1);
      }

      const args: string[] = [];

      // Determine verb based on resource
      if (resource === 'job' || resource === 'jobs') {
        args.push('cancel', id);
      } else if (resource === 'ontology' || resource === 'ontologies' || resource === 'onto') {
        args.push('delete', id);
        if (options.force) args.push('--force');
      } else if (resource === 'role' || resource === 'roles') {
        args.push('delete', id);
        if (options.force) args.push('--force');
      } else if (resource === 'user' || resource === 'users') {
        args.push('delete', id);
        if (options.force) args.push('--force');
      } else if (resource === 'artifact' || resource === 'artifacts') {
        args.push('delete', id);
      } else {
        console.error(colors.status.error(`✗ rm not supported for ${resource}`));
        process.exit(1);
      }

      if (options.json) {
        args.push('--json');
      }

      executeCommand(rootCommand, route, args);
    });

  // Apply user-configured aliases (ADR-029)
  applyAliases(cmd, 'rm');

  return cmd;
}

/**
 * Create the cat (display/show details) verb command
 *
 * Aliases are loaded from user config (ADR-029)
 */
function createCatCommand(rootCommand: Command): Command {
  const cmd = new Command('cat')
    .description('Display resource details (Unix-style shortcut)')
    .argument('<resource>', 'Resource type: concept, artifact, source, config, job, role, ontology')
    .argument('[id]', 'Resource identifier or key (optional for config and job)')
    .option('--json', 'Output as JSON')
    .option('--payload', 'Show full payload (for artifacts)')
    .action(async (resource: string, id: string | undefined, options) => {
      const args: string[] = [];

      if (options.json) {
        args.push('--json');
      }

      // Route based on resource type
      if (resource === 'concept' || resource === 'concepts') {
        if (!id) {
          console.error(colors.status.error('✗ Concept ID required'));
          console.log(colors.status.dim('Example: kg cat concept abc-123'));
          process.exit(1);
        }
        executeCommand(rootCommand, ['search', 'details'], [id, ...args]);
      } else if (resource === 'artifact' || resource === 'artifacts') {
        if (!id) {
          console.error(colors.status.error('✗ Artifact ID required'));
          console.log(colors.status.dim('Example: kg cat artifact 123'));
          process.exit(1);
        }
        if (options.payload) {
          // Show artifact with payload
          executeCommand(rootCommand, ['artifact', 'payload'], [id, ...args]);
        } else {
          // Show artifact metadata
          executeCommand(rootCommand, ['artifact', 'show'], [id, ...args]);
        }
      } else if (resource === 'source' || resource === 'sources') {
        if (!id) {
          console.error(colors.status.error('✗ Source ID required'));
          console.log(colors.status.dim('Example: kg cat source sha256:abc123_chunk1'));
          process.exit(1);
        }
        // Show source metadata
        executeCommand(rootCommand, ['source', 'info'], [id, ...args]);
      } else if (resource === 'config' || resource === 'cfg') {
        if (id) {
          // Show specific config key
          executeCommand(rootCommand, ['config', 'get'], [id, ...args]);
        } else {
          // List all config
          executeCommand(rootCommand, ['config', 'list'], args);
        }
      } else if (resource === 'job' || resource === 'jobs') {
        if (id) {
          // Show specific job status
          executeCommand(rootCommand, ['job', 'status'], [id, ...args]);
        } else {
          // List all jobs
          executeCommand(rootCommand, ['job', 'list'], args);
        }
      } else if (resource === 'role' || resource === 'roles') {
        if (!id) {
          console.error(colors.status.error('✗ Role name required'));
          console.log(colors.status.dim('Example: kg cat role admin'));
          process.exit(1);
        }
        executeCommand(rootCommand, ['admin', 'rbac', 'role', 'get'], [id, ...args]);
      } else if (resource === 'ontology' || resource === 'ontologies' || resource === 'onto') {
        if (!id) {
          console.error(colors.status.error('✗ Ontology name required'));
          console.log(colors.status.dim('Example: kg cat ontology "My Ontology"'));
          process.exit(1);
        }
        executeCommand(rootCommand, ['ontology', 'info'], [id, ...args]);
      } else {
        console.error(colors.status.error(`✗ Unknown resource: ${resource}`));
        console.log(colors.status.dim('\nAvailable resources: concept, artifact, source, config, job, role, ontology'));
        console.log(colors.status.dim('\nExample: kg cat concept abc-123'));
        process.exit(1);
      }
    });

  // Apply user-configured aliases (ADR-029)
  applyAliases(cmd, 'cat');

  return cmd;
}

/**
 * Create the complete verb router with all Unix-style verbs
 */
export function createVerbRouter(rootCommand: Command): Command[] {
  return [
    createLsCommand(rootCommand),
    createStatCommand(rootCommand),
    createRmCommand(rootCommand),
    createCatCommand(rootCommand),
  ];
}
