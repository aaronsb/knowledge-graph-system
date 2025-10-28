/**
 * Configuration Commands
 */

import { Command } from 'commander';
import { getConfig } from '../lib/config';
import * as readline from 'readline';
import { createClientFromEnv } from '../api/client';
import * as colors from './colors';
import { separator } from './colors';
import { configureColoredHelp } from './help-formatter';
import { Table } from '../lib/table';

/**
 * Prompt for input from user
 */
function prompt(question: string): Promise<string> {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
  });

  return new Promise((resolve) => {
    rl.question(question, (answer) => {
      rl.close();
      resolve(answer);
    });
  });
}

/**
 * Prompt for password (hidden input)
 */
function promptPassword(question: string): Promise<string> {
  return new Promise((resolve) => {
    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout
    });

    // @ts-ignore - _writeToOutput exists but not in types
    rl._writeToOutput = function(stringToWrite: string) {
      if (stringToWrite.charCodeAt(0) === 13) { // carriage return
        // @ts-ignore
        rl.output.write('\n');
      } else {
        // Don't display password characters
      }
    };

    rl.question(question, (password) => {
      rl.close();
      console.log(); // New line after password input
      resolve(password);
    });
  });
}

export const configCommand = new Command('config')
  .alias('cfg')  // Short alias
  .description('Manage kg CLI configuration settings. Controls API connection, authentication tokens, MCP tool preferences, and job auto-approval. Configuration stored in JSON file (typically ~/.kg/config.json).')
  .showHelpAfterError('(add --help for additional information)')
  .showSuggestionAfterError()
  .addCommand(
    new Command('get')
      .description('Get one or all configuration values. Supports dot notation for nested keys (e.g., "mcp.enabled", "client.id").')
      .argument('[key]', 'Configuration key (supports dot notation, e.g., "mcp.enabled"). Omit to show all configuration.')
      .option('--json', 'Output as JSON')
      .action(async (key, options) => {
        try {
          const config = getConfig();

          if (!key) {
            // Show all config
            const allConfig = config.getAll();

            if (options.json) {
              console.log(JSON.stringify(allConfig, null, 2));
            } else {
              console.log('\n' + separator());
              console.log(colors.ui.title('⚙️  Current Configuration'));
              console.log(separator());
              console.log('\n' + colors.ui.value(JSON.stringify(allConfig, null, 2)));
              console.log('\n' + separator());
            }
          } else {
            // Show specific key
            const value = config.get(key);

            if (value === undefined) {
              console.error(colors.status.error(`✗ Configuration key '${key}' not found`));
              process.exit(1);
            }

            if (options.json) {
              console.log(JSON.stringify({ [key]: value }, null, 2));
            } else {
              console.log(`\n${colors.ui.key(key + ':')} ${colors.ui.value(typeof value === 'object' ? JSON.stringify(value, null, 2) : value)}\n`);
            }
          }
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to get config'));
          console.error(colors.status.error(error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('set')
      .description('Set a configuration value. Auto-detects data types (boolean, number, JSON). Use --string to force literal string interpretation.')
      .argument('<key>', 'Configuration key (supports dot notation, e.g., "apiUrl", "mcp.enabled")')
      .argument('<value>', 'Value to set (auto-detects JSON arrays/objects, booleans, numbers)')
      .option('--json', 'Force parse value as JSON')
      .option('--string', 'Force treat value as string (no JSON parsing)')
      .action(async (key, value, options) => {
        try {
          const config = getConfig();

          let parsedValue: any = value;

          // If --string flag, treat as literal string
          if (options.string) {
            parsedValue = value;
          }
          // If --json flag or value looks like JSON, try to parse
          else if (options.json || value.startsWith('[') || value.startsWith('{')) {
            try {
              parsedValue = JSON.parse(value);
            } catch (e) {
              if (options.json) {
                // Only error if --json was explicitly requested
                console.error(colors.status.error('✗ Invalid JSON value'));
                process.exit(1);
              }
              // Otherwise treat as string
              parsedValue = value;
            }
          }
          // Auto-detect boolean and number values
          else if (value === 'true' || value === 'false') {
            parsedValue = value === 'true';
          } else if (!isNaN(Number(value)) && value.trim() !== '') {
            parsedValue = Number(value);
          }

          config.set(key, parsedValue);
          console.log(colors.status.success(`✓ Set ${colors.ui.key(key)} = ${colors.ui.value(typeof parsedValue === 'object' ? JSON.stringify(parsedValue) : parsedValue)}`));
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to set config'));
          console.error(colors.status.error(error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('delete')
      .description('Delete configuration key')
      .argument('<key>', 'Configuration key to delete')
      .action(async (key) => {
        try {
          const config = getConfig();
          config.delete(key);
          console.log(colors.status.success(`✓ Deleted ${colors.ui.key(key)}`));
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to delete config key'));
          console.error(colors.status.error(error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('list')
      .description('List all configuration')
      .option('--json', 'Output as JSON')
      .action(async (options) => {
        try {
          const config = getConfig();
          const allConfig = config.getAll();

          if (options.json) {
            console.log(JSON.stringify(allConfig, null, 2));
            return;
          }

          console.log('\n' + separator());
          console.log(colors.ui.title('⚙️  Configuration'));
          console.log(separator());

          // Build flat config rows for table display
          const configRows: Array<{ key: string; value: string; category: string }> = [];

          // Authentication section
          if (allConfig.username !== undefined) {
            configRows.push({
              key: 'username',
              value: allConfig.username,
              category: 'auth'
            });
          }
          if (allConfig.secret !== undefined) {
            configRows.push({
              key: 'secret',
              value: '***hidden***',
              category: 'auth'
            });
          }
          if (allConfig.auth?.token !== undefined) {
            const isValid = config.isAuthenticated();
            configRows.push({
              key: 'auth.token',
              value: isValid ? '✓ valid' : '✗ expired',
              category: 'auth'
            });
          }

          // Connection section
          if (allConfig.api_url !== undefined) {
            configRows.push({
              key: 'api_url',
              value: allConfig.api_url,
              category: 'connection'
            });
          }

          // Behavior section
          if (allConfig.backup_dir !== undefined) {
            configRows.push({
              key: 'backup_dir',
              value: allConfig.backup_dir,
              category: 'behavior'
            });
          }
          if (allConfig.auto_approve !== undefined) {
            configRows.push({
              key: 'auto_approve',
              value: allConfig.auto_approve ? 'true' : 'false',
              category: 'behavior'
            });
          }

          // MCP section
          if (allConfig.mcp?.enabled !== undefined) {
            configRows.push({
              key: 'mcp.enabled',
              value: allConfig.mcp.enabled ? 'true' : 'false',
              category: 'mcp'
            });
          }
          if (allConfig.mcp?.tools) {
            const toolCount = Object.keys(allConfig.mcp.tools).length;
            const enabledCount = Object.values(allConfig.mcp.tools).filter(t => t.enabled).length;
            configRows.push({
              key: 'mcp.tools',
              value: `${enabledCount}/${toolCount} enabled`,
              category: 'mcp'
            });
          }

          if (configRows.length === 0) {
            console.log(colors.status.dim('\nNo configuration found\n'));
            console.log(colors.status.dim(`Run: kg config init\n`));
            return;
          }

          // Create table
          const table = new Table<{ key: string; value: string; category: string }>({
            columns: [
              {
                header: 'Key',
                field: 'key',
                type: 'heading',
                width: 'flex',
                priority: 2
              },
              {
                header: 'Value',
                field: 'value',
                type: 'value',
                width: 'flex',
                priority: 3,
                customFormat: (val, row) => {
                  // Special formatting based on key
                  if (row.key === 'secret') return colors.status.dim(val);
                  if (row.key === 'auto_approve' && val === 'true') return colors.status.warning(val);
                  if (row.key === 'auto_approve' && val === 'false') return colors.status.dim(val);
                  if (row.key.startsWith('mcp.') && val.includes('true')) return colors.status.success(val);
                  if (row.key.startsWith('mcp.') && val.includes('false')) return colors.status.dim(val);
                  if (row.key.startsWith('auth.token')) {
                    if (val.includes('valid')) return colors.status.success(val);
                    if (val.includes('expired')) return colors.status.warning(val);
                  }
                  return val;
                }
              },
              {
                header: 'Category',
                field: 'category',
                type: 'text',
                width: 'auto',
                customFormat: (type) => {
                  switch (type) {
                    case 'auth': return colors.ui.value('auth');
                    case 'connection': return colors.ui.value('connection');
                    case 'behavior': return colors.ui.value('behavior');
                    case 'mcp': return colors.ui.value('mcp');
                    default: return type;
                  }
                }
              }
            ],
            spacing: 2,
            showHeader: true,
            showSeparator: true
          });

          table.print(configRows);

          // Helpful footer
          console.log(colors.status.dim(`Config file: ${config.getConfigPath()}`));
          console.log(colors.status.dim(`Usage: kg config set <key> <value>`));
          console.log(colors.status.dim(`MCP tools: kg config mcp list\n`));
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to list config'));
          console.error(colors.status.error(error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('path')
      .description('Show configuration file path')
      .action(() => {
        const config = getConfig();
        console.log('\n' + colors.ui.key('Config file:') + ' ' + colors.ui.value(config.getConfigPath()));
        console.log(colors.status.dim(`(Directory: ${config.getConfigDir()})\n`));
      })
  )
  .addCommand(
    new Command('init')
      .description('Initialize configuration file with defaults')
      .option('-f, --force', 'Overwrite existing configuration')
      .action(async (options) => {
        try {
          const config = getConfig();

          if (config.exists() && !options.force) {
            console.log(colors.status.warning('\n⚠ Configuration file already exists'));
            console.log(colors.status.dim(`Use --force to overwrite: ${config.getConfigPath()}\n`));
            return;
          }

          config.init();
          console.log(colors.status.success('✓ Configuration initialized'));
          console.log(colors.status.dim(`Location: ${config.getConfigPath()}\n`));
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to initialize config'));
          console.error(colors.status.error(error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('reset')
      .description('Reset configuration to defaults')
      .option('-y, --yes', 'Skip confirmation')
      .action(async (options) => {
        try {
          const config = getConfig();

          if (!options.yes) {
            const answer = await prompt(
              colors.status.warning('⚠️  This will reset all configuration to defaults. Continue? (y/N) ')
            );

            if (answer.toLowerCase() !== 'y') {
              console.log(colors.status.dim('Cancelled\n'));
              return;
            }
          }

          config.reset();
          console.log(colors.status.success('✓ Configuration reset to defaults'));
          console.log(colors.status.dim(`Location: ${config.getConfigPath()}\n`));
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to reset config'));
          console.error(colors.status.error(error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('enable-mcp')
      .description('Enable an MCP tool')
      .argument('<tool>', 'MCP tool name')
      .action(async (tool) => {
        try {
          const config = getConfig();
          config.enableMcpTool(tool);
          console.log(colors.status.success(`✓ Enabled MCP tool: ${colors.ui.value(tool)}`));
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to enable MCP tool'));
          console.error(colors.status.error(error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('disable-mcp')
      .description('Disable an MCP tool')
      .argument('<tool>', 'MCP tool name')
      .action(async (tool) => {
        try {
          const config = getConfig();
          config.disableMcpTool(tool);
          console.log(colors.status.success(`✓ Disabled MCP tool: ${colors.ui.value(tool)}`));
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to disable MCP tool'));
          console.error(colors.status.error(error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('mcp')
      .description('Show MCP tool configuration status. Lists all MCP tools with enabled/disabled status and descriptions. Specify a tool name to see details for that tool.')
      .argument('[tool]', 'Specific MCP tool name (optional). Omit to show all MCP tools.')
      .option('--json', 'Output as JSON')
      .action(async (tool, options) => {
        try {
          const config = getConfig();

          if (tool) {
            // Show specific tool
            const status = config.getMcpToolStatus(tool);
            const tools = config.listMcpTools();
            const toolConfig = tools[tool];

            if (!toolConfig) {
              console.error(colors.status.error(`✗ MCP tool '${tool}' not found`));
              process.exit(1);
            }

            if (options.json) {
              console.log(JSON.stringify({ [tool]: toolConfig }, null, 2));
            } else {
              console.log('\n' + separator());
              console.log(colors.ui.title(`MCP Tool: ${tool}`));
              console.log(separator());
              const statusText = status ? colors.status.success('✓ enabled') : colors.status.dim('✗ disabled');
              console.log(`\n${colors.ui.key('Status:')} ${statusText}`);
              if (toolConfig.description) {
                console.log(`${colors.ui.key('Description:')} ${colors.ui.value(toolConfig.description)}`);
              }
              console.log('\n' + separator());
            }
          } else {
            // Show all tools as table
            const tools = config.listMcpTools();

            if (options.json) {
              console.log(JSON.stringify({ tools }, null, 2));
              return;
            }

            console.log('\n' + separator());
            console.log(colors.ui.title('🔧 MCP Tools'));
            console.log(separator());

            const toolRows = Object.entries(tools).map(([name, toolConfig]) => ({
              name,
              enabled: toolConfig.enabled,
              description: toolConfig.description || '-'
            }));

            if (toolRows.length === 0) {
              console.log(colors.status.dim('\nNo MCP tools configured\n'));
              return;
            }

            const table = new Table<{ name: string; enabled: boolean; description: string }>({
              columns: [
                {
                  header: 'Tool Name',
                  field: 'name',
                  type: 'heading',
                  width: 'flex',
                  priority: 2
                },
                {
                  header: 'Enabled',
                  field: 'enabled',
                  type: 'text',
                  width: 10,
                  customFormat: (enabled) => enabled ? colors.status.success('✓') : colors.status.dim('✗')
                },
                {
                  header: 'Description',
                  field: 'description',
                  type: 'text',
                  width: 'flex',
                  priority: 3,
                  truncate: true
                }
              ],
              spacing: 2,
              showHeader: true,
              showSeparator: true
            });

            table.print(toolRows);

            console.log(colors.status.dim(`Enable tool: kg config enable-mcp <tool-name>`));
            console.log(colors.status.dim(`Disable tool: kg config disable-mcp <tool-name>\n`));
          }
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to get MCP config'));
          console.error(colors.status.error(error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('auto-approve')
      .description('Enable or disable automatic approval of ingestion jobs. When enabled, jobs skip the cost estimate review step and start processing immediately (ADR-014).')
      .argument('[value]', 'Enable (true/on/yes) or disable (false/off/no). Omit to show current status.', 'status')
      .action(async (value) => {
        try {
          const config = getConfig();

          // If no value, show current status
          if (value === 'status') {
            const current = config.getAutoApprove();
            console.log('\n' + separator());
            console.log(colors.ui.title('🔄 Auto-Approve Configuration'));
            console.log(separator());
            const statusText = current ? colors.status.success('✓ enabled') : colors.status.dim('✗ disabled');
            console.log(`\n${colors.ui.key('Status:')} ${statusText}`);
            console.log(colors.status.dim('\nWhen enabled, all jobs are automatically approved without manual review'));
            console.log(colors.status.dim('Override: Use --yes flag on individual ingest commands\n'));
            console.log(separator());
            return;
          }

          // Parse boolean value
          const enableValues = ['true', 'on', 'yes', 'enable', 'enabled', '1'];
          const disableValues = ['false', 'off', 'no', 'disable', 'disabled', '0'];

          let newValue: boolean;
          if (enableValues.includes(value.toLowerCase())) {
            newValue = true;
          } else if (disableValues.includes(value.toLowerCase())) {
            newValue = false;
          } else {
            console.error(colors.status.error(`✗ Invalid value: ${value}`));
            console.log(colors.status.dim('Use: true/false, on/off, yes/no, enable/disable'));
            process.exit(1);
          }

          config.setAutoApprove(newValue);
          const statusText = newValue ? colors.status.success('enabled') : colors.status.dim('disabled');
          console.log(colors.status.success(`✓ Auto-approve ${statusText}`));

          if (newValue) {
            console.log(colors.status.warning('\n⚠️  All jobs will now be automatically approved'));
            console.log(colors.status.dim('Jobs will skip the analysis review step and start processing immediately\n'));
          }
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to configure auto-approve'));
          console.error(colors.status.error(error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('update-secret')
      .description('Authenticate with username/password and update the stored API secret or key. Password is never stored; only the resulting authentication token is persisted.')
      .option('-u, --username <username>', 'Username (will prompt if not provided)')
      .action(async (options) => {
        try {
          const config = getConfig();

          // Get username
          let username = options.username || config.get('username');
          if (!username) {
            username = await prompt('Username: ');
          }

          // Get password (never stored)
          const password = await promptPassword('Password: ');

          if (!password) {
            console.error(colors.status.error('✗ Password is required'));
            process.exit(1);
          }

          console.log(colors.status.info('\nAuthenticating...'));

          // TODO: Call API endpoint to authenticate and get new secret
          // For now, this is a placeholder
          console.log('\n' + separator());
          console.log(colors.status.warning('⚠️  API authentication endpoint not yet implemented'));
          console.log(separator());
          console.log(colors.status.dim('\nThis feature will be available in a future update'));
          console.log(colors.status.dim('\nExpected flow:'));
          console.log(colors.status.dim('1. POST /auth/login with username + password'));
          console.log(colors.status.dim('2. Server validates credentials'));
          console.log(colors.status.dim('3. Server generates salted API key'));
          console.log(colors.status.dim('4. Key is stored in config (password is never stored)\n'));

          // When implemented:
          // const client = createClientFromEnv();
          // const response = await client.authenticate(username, password);
          // config.set('username', username);
          // config.set('secret', response.api_key);
          // console.log(colors.status.success('✓ API secret updated successfully'));

        } catch (error: any) {
          console.error(colors.status.error('✗ Authentication failed'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('json')
      .description('JSON-based configuration operations (machine-friendly)')
      .addCommand(
        new Command('get')
          .description('Get entire configuration as JSON')
          .action(() => {
            const config = getConfig();
            const allConfig = config.getAll();
            console.log(JSON.stringify(allConfig, null, 2));
          })
      )
      .addCommand(
        new Command('set')
          .description('Set configuration from JSON (full or partial)')
          .argument('<json>', 'JSON string or path to JSON file')
          .action(async (jsonInput) => {
            try {
              const config = getConfig();

              let parsedConfig: any;

              // Check if input is a file path
              if (jsonInput.endsWith('.json')) {
                const fs = require('fs');
                if (fs.existsSync(jsonInput)) {
                  const fileContent = fs.readFileSync(jsonInput, 'utf-8');
                  parsedConfig = JSON.parse(fileContent);
                } else {
                  // Not a file, try to parse as JSON string
                  parsedConfig = JSON.parse(jsonInput);
                }
              } else {
                // Parse as JSON string
                parsedConfig = JSON.parse(jsonInput);
              }

              // Apply each key-value pair
              const keys = Object.keys(parsedConfig);
              for (const key of keys) {
                config.set(key, parsedConfig[key]);
              }

              console.log(colors.status.success(`✓ Set ${keys.length} configuration value(s)`));
            } catch (error: any) {
              console.error(colors.status.error('✗ Failed to set config from JSON'));
              if (error instanceof SyntaxError) {
                console.error(colors.status.error('Invalid JSON syntax'));
              } else {
                console.error(colors.status.error(error.message));
              }
              process.exit(1);
            }
          })
      )
      .addCommand(
        new Command('dto')
          .description('Output configuration template/schema')
          .action(() => {
            const template = {
              username: "your-username",
              secret: "your-api-key",
              api_url: "http://localhost:8000",
              backup_dir: "~/.local/share/kg/backups",
              auto_approve: false,
              mcp: {
                enabled: true,
                tools: {
                  search_concepts: { enabled: true, description: "Search for concepts using natural language" },
                  get_concept_details: { enabled: true, description: "Get detailed information about a concept" },
                  find_related_concepts: { enabled: true, description: "Find concepts related through graph traversal" },
                  find_connection: { enabled: true, description: "Find shortest path between concepts" },
                  ingest_document: { enabled: true, description: "Ingest a document into the knowledge graph" },
                  list_ontologies: { enabled: true, description: "List all ontologies" },
                  get_database_stats: { enabled: true, description: "Get database statistics" }
                }
              },
              auth: {
                token: "your-jwt-token",
                token_type: "bearer",
                expires_at: 0,
                username: "your-username",
                role: "your-role"
              }
            };

            console.log(colors.status.dim('# kg Configuration Template (DTO)\n'));
            console.log(JSON.stringify(template, null, 2));
            console.log(colors.status.dim('\n# Usage:'));
            console.log(colors.status.dim('# kg config json set \'{"username": "alice", "auto_approve": true}\''));
            console.log(colors.status.dim('# kg config json set config.json'));
          })
      )
  );

// Configure colored help for all config subcommands
configCommand.commands.forEach(configureColoredHelp);
