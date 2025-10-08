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
  .description('Manage kg CLI configuration')
  .addCommand(
    new Command('get')
      .description('Get configuration value(s)')
      .argument('[key]', 'Configuration key (supports dot notation, e.g., "mcp.enabled")')
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
      .description('Set configuration value')
      .argument('<key>', 'Configuration key (supports dot notation)')
      .argument('<value>', 'Value to set')
      .option('--json', 'Parse value as JSON')
      .action(async (key, value, options) => {
        try {
          const config = getConfig();

          // Parse value if --json flag
          let parsedValue = value;
          if (options.json) {
            try {
              parsedValue = JSON.parse(value);
            } catch (e) {
              console.error(colors.status.error('✗ Invalid JSON value'));
              process.exit(1);
            }
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
          } else {
            console.log('\n' + separator());
            console.log(colors.ui.title('⚙️  Configuration'));
            console.log(separator());

            // Display config keys and values
            console.log();

            // Simple top-level keys
            if (allConfig.username !== undefined) {
              console.log(`${colors.ui.key('username:')} ${colors.ui.value(allConfig.username)}`);
            }
            if (allConfig.secret !== undefined) {
              console.log(`${colors.ui.key('secret:')} ${colors.status.dim('***hidden***')}`);
            }
            if (allConfig.api_url !== undefined) {
              console.log(`${colors.ui.key('api_url:')} ${colors.ui.value(allConfig.api_url)}`);
            }
            if (allConfig.backup_dir !== undefined) {
              console.log(`${colors.ui.key('backup_dir:')} ${colors.ui.value(allConfig.backup_dir)}`);
            }

            // Auto-approve with boolean value
            if (allConfig.auto_approve !== undefined) {
              const value = allConfig.auto_approve ? colors.status.warning('true') : colors.status.dim('false');
              console.log(`${colors.ui.key('auto_approve:')} ${value}`);
            }

            // MCP configuration (nested)
            if (allConfig.mcp) {
              console.log();
              console.log(colors.ui.key('mcp:'));

              if (allConfig.mcp.enabled !== undefined) {
                const value = allConfig.mcp.enabled ? colors.status.success('true') : colors.status.dim('false');
                console.log(`  ${colors.ui.key('enabled:')} ${value}`);
              }

              if (allConfig.mcp.tools && Object.keys(allConfig.mcp.tools).length > 0) {
                console.log(`  ${colors.ui.key('tools:')}`);
                Object.entries(allConfig.mcp.tools).forEach(([name, toolConfig]: [string, any]) => {
                  const status = toolConfig.enabled ? colors.status.success('✓') : colors.status.dim('✗');
                  console.log(`    ${status} ${colors.ui.value(name)}`);
                });
              }
            }

            // Config file location and usage hint
            console.log();
            console.log(colors.status.dim(`Config file: ${config.getConfigPath()}`));
            console.log(colors.status.dim(`Usage: kg config set <key> <value>`));
            console.log('\n' + separator());
          }
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
      .description('Show MCP tool configuration')
      .argument('[tool]', 'Specific MCP tool name')
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
            // Show all tools
            const tools = config.listMcpTools();

            if (options.json) {
              console.log(JSON.stringify({ tools }, null, 2));
            } else {
              console.log('\n' + separator());
              console.log(colors.ui.title('🔧 MCP Tools'));
              console.log(separator());

              Object.entries(tools).forEach(([name, toolConfig]) => {
                const statusIcon = toolConfig.enabled ? colors.status.success('✓') : colors.status.dim('✗');
                console.log(`\n${statusIcon} ${colors.ui.key(name)}`);
                if (toolConfig.description) {
                  console.log(`  ${colors.status.dim(toolConfig.description)}`);
                }
              });
              console.log('\n' + separator());
            }
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
      .description('Enable/disable auto-approval of jobs (ADR-014)')
      .argument('[value]', 'Enable (true/on/yes) or disable (false/off/no)', 'status')
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
      .description('Authenticate and update API secret/key')
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
  );

// Configure colored help for all config subcommands
configCommand.commands.forEach(configureColoredHelp);
