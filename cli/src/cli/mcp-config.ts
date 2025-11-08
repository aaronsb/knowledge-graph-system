/**
 * MCP File Access Configuration Commands
 *
 * ADR-062: MCP File Ingestion Security Model
 *
 * Manage path allowlist for secure file/directory ingestion from MCP server.
 */

import { Command } from 'commander';
import { McpAllowlistManager } from '../lib/mcp-allowlist';
import * as colors from './colors';
import { separator } from './colors';
import { setCommandHelp } from './help-formatter';
import { Table } from '../lib/table';
import * as fs from 'fs';
import { getConfig } from '../lib/config';
import { AuthClient } from '../lib/auth/auth-client';
import axios from 'axios';

export const mcpConfigCommand = setCommandHelp(
  new Command('mcp-config'),
  'Manage MCP file access allowlist',
  `Manage path allowlist for secure file/directory ingestion from MCP server.

Security Model (ADR-062):
- Fail-secure validation (blocked patterns checked first)
- Explicit allowlist (no access without configuration)
- CLI-only management (agent can read, not write)
- Path resolution prevents traversal attacks

Configuration stored in: ~/.config/kg/mcp-allowed-paths.json`
)
  .showHelpAfterError('(add --help for additional information)')
  .showSuggestionAfterError()
  .addCommand(
    new Command('init-allowlist')
      .description('Initialize allowlist with safe defaults')
      .action(async () => {
        try {
          const manager = new McpAllowlistManager();
          await manager.initialize();

          const config = manager.getConfig();
          if (!config) {
            console.error(colors.status.error('✗ Failed to initialize allowlist'));
            process.exit(1);
          }

          console.log(colors.status.success(`✓ Initialized allowlist at: ${manager.getAllowlistPath()}`));
          console.log();
          console.log(colors.status.info('Default configuration:'));
          console.log(colors.status.dim('  Allowed directories: (none - add with: kg mcp-config allow-dir)'));
          console.log(colors.status.dim(`  Allowed patterns: ${config.allowed_patterns.join(', ')}`));
          console.log(colors.status.dim(`  Blocked patterns: ${config.blocked_patterns.length} patterns`));
          console.log(colors.status.dim(`  Max file size: ${config.max_file_size_mb}MB`));
          console.log();
          console.log(colors.status.info('Next steps:'));
          console.log(colors.ui.command('  kg mcp-config allow-dir ~/Documents/research'));
          console.log(colors.ui.command('  kg mcp-config allow-dir ~/Projects/*/docs'));

        } catch (error: any) {
          console.error(colors.status.error(`✗ Error: ${error.message}`));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('allow-dir')
      .description('Add allowed directory')
      .argument('<directory>', 'Directory path (supports ~ and glob patterns like ~/Projects/*/docs)')
      .action(async (directory) => {
        try {
          const manager = new McpAllowlistManager();
          manager.addAllowedDirectory(directory);

          console.log(colors.status.success(`✓ Added allowed directory: ${directory}`));
          console.log();
          console.log(colors.status.info('Test access:'));
          console.log(colors.ui.command(`  kg mcp-config test-path ${directory}/example.md`));

        } catch (error: any) {
          console.error(colors.status.error(`✗ Error: ${error.message}`));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('remove-dir')
      .description('Remove allowed directory')
      .argument('<directory>', 'Directory path to remove')
      .action(async (directory) => {
        try {
          const manager = new McpAllowlistManager();
          manager.removeAllowedDirectory(directory);

          console.log(colors.status.success(`✓ Removed allowed directory: ${directory}`));

        } catch (error: any) {
          console.error(colors.status.error(`✗ Error: ${error.message}`));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('allow-pattern')
      .description('Add allowed file pattern')
      .argument('<pattern>', 'Glob pattern (e.g., "**/*.md", "**/*.png")')
      .action(async (pattern) => {
        try {
          const manager = new McpAllowlistManager();
          manager.addAllowedPattern(pattern);

          console.log(colors.status.success(`✓ Added allowed pattern: ${pattern}`));

        } catch (error: any) {
          console.error(colors.status.error(`✗ Error: ${error.message}`));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('remove-pattern')
      .description('Remove allowed file pattern')
      .argument('<pattern>', 'Pattern to remove')
      .action(async (pattern) => {
        try {
          const manager = new McpAllowlistManager();
          manager.removeAllowedPattern(pattern);

          console.log(colors.status.success(`✓ Removed allowed pattern: ${pattern}`));

        } catch (error: any) {
          console.error(colors.status.error(`✗ Error: ${error.message}`));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('block-pattern')
      .description('Add blocked file pattern (security)')
      .argument('<pattern>', 'Glob pattern to block (e.g., "**/.env*", "**/*.key")')
      .action(async (pattern) => {
        try {
          const manager = new McpAllowlistManager();
          manager.addBlockedPattern(pattern);

          console.log(colors.status.success(`✓ Added blocked pattern: ${pattern}`));
          console.log(colors.status.dim('  Files matching this pattern will be rejected for security'));

        } catch (error: any) {
          console.error(colors.status.error(`✗ Error: ${error.message}`));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('unblock-pattern')
      .description('Remove blocked file pattern')
      .argument('<pattern>', 'Pattern to unblock')
      .action(async (pattern) => {
        try {
          const manager = new McpAllowlistManager();
          manager.removeBlockedPattern(pattern);

          console.log(colors.status.success(`✓ Removed blocked pattern: ${pattern}`));

        } catch (error: any) {
          console.error(colors.status.error(`✗ Error: ${error.message}`));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('show-allowlist')
      .description('Show current allowlist configuration')
      .option('--json', 'Output as JSON')
      .action(async (options) => {
        try {
          const manager = new McpAllowlistManager();
          const config = manager.getConfig();

          if (!config) {
            console.log(colors.status.warning('⚠ Allowlist not initialized'));
            console.log();
            console.log(colors.status.info('Initialize with:'));
            console.log(colors.ui.command('  kg mcp-config init-allowlist'));
            return;
          }

          if (options.json) {
            console.log(JSON.stringify(config, null, 2));
            return;
          }

          console.log(colors.ui.header('MCP File Access Allowlist'));
          console.log(separator());
          console.log();

          console.log(colors.ui.subtitle(`Allowed Directories (${config.allowed_directories.length})`));
          if (config.allowed_directories.length === 0) {
            console.log(colors.status.dim('  (none - add with: kg mcp-config allow-dir ~/path)'));
          } else {
            config.allowed_directories.forEach(dir => {
              console.log(colors.status.success(`  ✓ ${dir}`));
            });
          }
          console.log();

          console.log(colors.ui.subtitle(`Allowed File Patterns (${config.allowed_patterns.length})`));
          config.allowed_patterns.forEach(pattern => {
            console.log(colors.status.success(`  ✓ ${pattern}`));
          });
          console.log();

          console.log(colors.ui.subtitle(`Blocked Patterns (${config.blocked_patterns.length})`));
          config.blocked_patterns.forEach(pattern => {
            console.log(colors.status.error(`  ✗ ${pattern}`));
          });
          console.log();

          console.log(colors.ui.subtitle('Limits'));
          console.log(`  Max file size: ${config.max_file_size_mb}MB`);
          console.log(`  Max files per directory: ${config.max_files_per_directory}`);
          console.log();

          console.log(colors.status.dim(`Configuration file: ${manager.getAllowlistPath()}`));

        } catch (error: any) {
          console.error(colors.status.error(`✗ Error: ${error.message}`));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('test-path')
      .description('Test if a path would be allowed')
      .argument('<path>', 'File or directory path to test')
      .action(async (testPath) => {
        try {
          const manager = new McpAllowlistManager();
          const result = manager.validatePath(testPath);

          console.log(colors.ui.header('Path Validation Test'));
          console.log(separator());
          console.log();
          console.log(colors.ui.subtitle(`Path: ${testPath}`));
          console.log();

          if (result.allowed) {
            console.log(colors.status.success('✓ ALLOWED'));

            // Check if file exists
            if (fs.existsSync(testPath)) {
              const stats = fs.statSync(testPath);
              const sizeMB = stats.size / (1024 * 1024);
              console.log(colors.status.dim(`  File exists: ${sizeMB.toFixed(2)}MB`));
            } else {
              console.log(colors.status.dim('  File does not exist (but path would be allowed)'));
            }
          } else {
            console.log(colors.status.error('✗ DENIED'));
            console.log();
            console.log(colors.ui.subtitle('Reason:'));
            console.log(`  ${result.reason}`);

            if (result.hint) {
              console.log();
              console.log(colors.ui.subtitle('Hint:'));
              console.log(`  ${result.hint}`);
            }
          }

        } catch (error: any) {
          console.error(colors.status.error(`✗ Error: ${error.message}`));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('oauth')
      .description('Create OAuth client for MCP server')
      .option('--name <name>', 'Custom client name')
      .action(async (options) => {
        try {
          // Require authentication
          const config = getConfig();
          if (!config.isAuthenticated()) {
            console.error(colors.status.error('✗ Authentication required'));
            console.log('   Please login first: kg login');
            process.exit(1);
          }

          const apiUrl = config.getApiUrl();
          const authClient = new AuthClient(apiUrl);

          // Get OAuth client credentials
          const oauthCreds = config.getOAuthCredentials();
          if (!oauthCreds) {
            console.error(colors.status.error('✗ No OAuth credentials found. Please login: kg login'));
            process.exit(1);
          }

          // Get fresh access token
          const tokenResponse = await authClient.getOAuthToken({
            grant_type: 'client_credentials',
            client_id: oauthCreds.client_id,
            client_secret: oauthCreds.client_secret,
            scope: oauthCreds.scopes.join(' ')
          });

          const token = tokenResponse.access_token;
          const username = oauthCreds.username || 'unknown';
          const clientName = options.name || `kg MCP Server (${username})`;

          console.log();
          console.log(colors.status.info('🔐 Creating OAuth client for MCP server...'));
          console.log();

          // Create additional personal OAuth client
          const formData = new URLSearchParams();
          formData.append('client_name', clientName);
          formData.append('scope', 'read:* write:*');

          const response = await axios.post(
            `${apiUrl}/auth/oauth/clients/personal/new`,
            formData,
            {
              headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/x-www-form-urlencoded'
              }
            }
          );

          const client = response.data;

          console.log(colors.status.success('✅ OAuth client created successfully!'));
          console.log();
          console.log('═'.repeat(80));
          console.log(colors.ui.header('CLAUDE DESKTOP CONFIG'));
          console.log('═'.repeat(80));
          console.log();
          console.log('Add this to your Claude Desktop config:');
          console.log();
          console.log('  "knowledge-graph": {');
          console.log('    "command": "kg-mcp-server",');
          console.log('    "env": {');
          console.log(`      "KG_OAUTH_CLIENT_ID": "${client.client_id}",`);
          console.log(`      "KG_OAUTH_CLIENT_SECRET": "${client.client_secret}",`);
          console.log('      "KG_API_URL": "http://localhost:8000"');
          console.log('    }');
          console.log('  }');
          console.log();
          console.log('═'.repeat(80));
          console.log();
          console.log(colors.status.warning('⚠️  IMPORTANT:'));
          console.log('  • Keep these credentials secure!');
          console.log('  • Client secret is shown only once');
          console.log(colors.ui.command(`  • To revoke: kg oauth revoke ${client.client_id}`));
          console.log();
          console.log(colors.status.dim('Or add using claude CLI:'));
          console.log();
          console.log(`  claude mcp add knowledge-graph kg-mcp-server \\`);
          console.log(`    --env KG_OAUTH_CLIENT_ID=${client.client_id} \\`);
          console.log(`    --env KG_OAUTH_CLIENT_SECRET=${client.client_secret} \\`);
          console.log(`    --env KG_API_URL=http://localhost:8000 \\`);
          console.log(`    -s local`);
          console.log();

        } catch (error: any) {
          console.error(colors.status.error(`✗ Error: ${error.response?.data?.detail || error.message}`));
          process.exit(1);
        }
      })
  );
