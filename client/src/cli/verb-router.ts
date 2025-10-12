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
 */

import { Command } from 'commander';
import * as colors from './colors';

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
 * Create the ls (list) verb command
 */
function createLsCommand(rootCommand: Command): Command {
  return new Command('ls')
    .description('List resources (Unix-style shortcut)')
    .argument('<resource>', 'Resource type: job, ontology, backup, config, role, permission, resource, user')
    .option('--json', 'Output as JSON')
    .action(async (resource: string, options) => {
      const route = getResourceRoute(resource);

      if (!route) {
        console.error(colors.status.error(`✗ Unknown resource: ${resource}`));
        console.log(colors.status.dim('\nAvailable resources:'));
        console.log(colors.status.dim('  job, ontology, backup, config, role, permission, resource, user'));
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
        console.error(colors.status.error('✗ Use "kg search query <text>" to search concepts'));
        process.exit(1);
      } else {
        executeCommand(rootCommand, route, listArgs);
      }
    });
}

/**
 * Create the stat (status/statistics) verb command
 */
function createStatCommand(rootCommand: Command): Command {
  return new Command('stat')
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
}

/**
 * Create the rm (remove/cancel/delete) verb command
 */
function createRmCommand(rootCommand: Command): Command {
  return new Command('rm')
    .description('Remove or delete resources (Unix-style shortcut)')
    .argument('<resource>', 'Resource type: job, ontology, role, permission, user')
    .argument('<id>', 'Resource identifier')
    .option('-f, --force', 'Skip confirmation')
    .option('--json', 'Output as JSON')
    .action(async (resource: string, id: string, options) => {
      const route = getResourceRoute(resource);

      if (!route) {
        console.error(colors.status.error(`✗ Unknown resource: ${resource}`));
        console.log(colors.status.dim('\nAvailable resources: job, ontology, role, user'));
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
      } else {
        console.error(colors.status.error(`✗ rm not supported for ${resource}`));
        process.exit(1);
      }

      if (options.json) {
        args.push('--json');
      }

      executeCommand(rootCommand, route, args);
    });
}

/**
 * Create the cat (display/show details) verb command
 */
function createCatCommand(rootCommand: Command): Command {
  return new Command('cat')
    .description('Display resource details (Unix-style shortcut)')
    .argument('<resource>', 'Resource type: concept, config, job, role, ontology')
    .argument('<id>', 'Resource identifier or key')
    .option('--json', 'Output as JSON')
    .action(async (resource: string, id: string, options) => {
      const args: string[] = [];

      if (options.json) {
        args.push('--json');
      }

      // Route based on resource type
      if (resource === 'concept' || resource === 'concepts') {
        executeCommand(rootCommand, ['search', 'details'], [id, ...args]);
      } else if (resource === 'config' || resource === 'cfg') {
        executeCommand(rootCommand, ['config', 'get'], [id, ...args]);
      } else if (resource === 'job' || resource === 'jobs') {
        executeCommand(rootCommand, ['job', 'status'], [id, ...args]);
      } else if (resource === 'role' || resource === 'roles') {
        executeCommand(rootCommand, ['admin', 'rbac', 'role', 'get'], [id, ...args]);
      } else if (resource === 'ontology' || resource === 'ontologies' || resource === 'onto') {
        executeCommand(rootCommand, ['ontology', 'info'], [id, ...args]);
      } else {
        console.error(colors.status.error(`✗ Unknown resource: ${resource}`));
        console.log(colors.status.dim('\nAvailable resources: concept, config, job, role, ontology'));
        console.log(colors.status.dim('\nExample: kg cat concept abc-123'));
        process.exit(1);
      }
    });
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
