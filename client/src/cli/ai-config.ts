/**
 * AI Configuration Commands (ADR-039, ADR-041)
 *
 * Manages AI provider configuration:
 * - Embedding models (local/API-based)
 * - Extraction models (GPT-4, Claude)
 * - API keys with validation
 *
 * Command structure:
 *   kg admin embedding config   - Show embedding configuration
 *   kg admin embedding set      - Update embedding configuration
 *   kg admin extraction config  - Show extraction configuration
 *   kg admin extraction set     - Update extraction configuration
 *   kg admin keys list          - List API keys with status
 *   kg admin keys set           - Set API key for provider
 *   kg admin keys delete        - Delete API key
 */

import { Command } from 'commander';
import * as readline from 'readline';
import { KnowledgeGraphClient } from '../api/client';
import * as colors from './colors';
import { separator } from './colors';

/**
 * Prompt for input from user (hidden for sensitive data)
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

/**
 * Prompt for regular input from user
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

// ========== Embedding Commands ==========

/**
 * Show current embedding configuration
 */
function createEmbeddingConfigCommand(client: KnowledgeGraphClient): Command {
  return new Command('config')
    .description('Show current embedding configuration')
    .action(async () => {
      try {
        console.log('\n' + separator());
        console.log(colors.ui.title('🎯 Embedding Configuration'));
        console.log(separator());

        const config = await client.getEmbeddingConfig();

        console.log(`\n  ${colors.ui.key('Provider:')} ${colors.ui.value(config.provider)}`);
        console.log(`  ${colors.ui.key('Model:')} ${colors.ui.value(config.model)}`);
        console.log(`  ${colors.ui.key('Dimensions:')} ${colors.ui.value(config.dimensions)}`);

        if (config.precision) {
          console.log(`  ${colors.ui.key('Precision:')} ${colors.ui.value(config.precision)}`);
        }

        if (config.resource_allocation) {
          console.log(`\n  ${colors.ui.header('Resource Allocation:')}`);
          console.log(`    ${colors.ui.key('Device:')} ${colors.ui.value(config.resource_allocation.device)}`);
          console.log(`    ${colors.ui.key('Max Memory:')} ${colors.ui.value(config.resource_allocation.max_memory_mb + ' MB')}`);
          console.log(`    ${colors.ui.key('Threads:')} ${colors.ui.value(config.resource_allocation.num_threads)}`);
          console.log(`    ${colors.ui.key('Batch Size:')} ${colors.ui.value(config.resource_allocation.batch_size)}`);
        }

        console.log(`\n  ${colors.status.dim('Config ID: ' + config.config_id)}`);
        console.log('\n' + separator() + '\n');

      } catch (error: any) {
        console.error(colors.status.error('✗ Failed to get embedding configuration'));
        console.error(colors.status.error(error.response?.data?.detail || error.message));
        process.exit(1);
      }
    });
}

/**
 * Update embedding configuration
 */
function createEmbeddingSetCommand(client: KnowledgeGraphClient): Command {
  return new Command('set')
    .description('Update embedding configuration')
    .option('--provider <provider>', 'Provider: local or openai')
    .option('--model <model>', 'Model name')
    .option('--dimensions <dims>', 'Embedding dimensions', parseInt)
    .option('--precision <precision>', 'Precision: float16, float32, int8')
    .option('--device <device>', 'Device: cpu, cuda, mps')
    .option('--memory <mb>', 'Max memory in MB', parseInt)
    .option('--threads <n>', 'Number of threads', parseInt)
    .option('--batch-size <n>', 'Batch size', parseInt)
    .action(async (options) => {
      try {
        console.log('\n' + separator());
        console.log(colors.ui.title('🎯 Update Embedding Configuration'));
        console.log(separator());

        const config: any = {};

        if (options.provider) config.provider = options.provider;
        if (options.model) config.model_name = options.model;
        if (options.dimensions) config.dimensions = options.dimensions;
        if (options.precision) config.precision = options.precision;
        if (options.device) config.device = options.device;
        if (options.memory) config.max_memory_mb = options.memory;
        if (options.threads) config.num_threads = options.threads;
        if (options.batchSize) config.batch_size = options.batchSize;

        if (Object.keys(config).length === 0) {
          console.error(colors.status.error('\n✗ No configuration options provided'));
          console.log(colors.status.dim('  Use --help to see available options\n'));
          process.exit(1);
        }

        const result = await client.updateEmbeddingConfig(config);

        console.log('\n' + colors.status.success('✓ Configuration updated successfully'));
        console.log(`\n  ${colors.ui.key('Config ID:')} ${colors.ui.value(result.config_id)}`);

        if (result.reload_required) {
          console.log(`\n  ${colors.status.warning('⚠️  API restart required to apply changes')}`);
          console.log(`  ${colors.status.dim('Run: ./scripts/stop-api.sh && ./scripts/start-api.sh')}`);
        }

        console.log('\n' + separator() + '\n');

      } catch (error: any) {
        console.error(colors.status.error('✗ Failed to update embedding configuration'));
        console.error(colors.status.error(error.response?.data?.detail || error.message));
        process.exit(1);
      }
    });
}

/**
 * Hot reload embedding model
 */
function createEmbeddingReloadCommand(client: KnowledgeGraphClient): Command {
  return new Command('reload')
    .description('Hot reload embedding model (zero-downtime)')
    .action(async () => {
      try {
        console.log('\n' + separator());
        console.log(colors.ui.title('🔄 Hot Reload Embedding Model'));
        console.log(separator());

        console.log(colors.status.info('\nReloading model from database configuration...'));
        const result = await client.reloadEmbeddingModel();

        console.log('\n' + colors.status.success('✓ Hot reload successful'));
        console.log(`\n  ${colors.ui.key('Provider:')} ${colors.ui.value(result.provider)}`);

        if (result.model) {
          console.log(`  ${colors.ui.key('Model:')} ${colors.ui.value(result.model)}`);
        }

        if (result.dimensions) {
          console.log(`  ${colors.ui.key('Dimensions:')} ${colors.ui.value(result.dimensions)}`);
        }

        console.log(`\n  ${colors.status.dim('Next embedding request will use new configuration')}`);
        console.log('\n' + separator() + '\n');

      } catch (error: any) {
        console.error(colors.status.error('✗ Hot reload failed'));
        console.error(colors.status.error(error.response?.data?.detail || error.message));
        process.exit(1);
      }
    });
}

/**
 * Embedding command group
 */
export function createEmbeddingCommand(client: KnowledgeGraphClient): Command {
  const embeddingCommand = new Command('embedding')
    .description('Manage embedding model configuration (ADR-039)');

  embeddingCommand.addCommand(createEmbeddingConfigCommand(client));
  embeddingCommand.addCommand(createEmbeddingSetCommand(client));
  embeddingCommand.addCommand(createEmbeddingReloadCommand(client));

  return embeddingCommand;
}

// ========== Extraction Commands ==========

/**
 * Show current extraction configuration
 */
function createExtractionConfigCommand(client: KnowledgeGraphClient): Command {
  return new Command('config')
    .description('Show current AI extraction configuration')
    .action(async () => {
      try {
        console.log('\n' + separator());
        console.log(colors.ui.title('🤖 AI Extraction Configuration'));
        console.log(separator());

        const config = await client.getExtractionConfig();

        console.log(`\n  ${colors.ui.key('Provider:')} ${colors.ui.value(config.provider)}`);
        console.log(`  ${colors.ui.key('Model:')} ${colors.ui.value(config.model)}`);
        console.log(`  ${colors.ui.key('Vision Support:')} ${config.supports_vision ? colors.status.success('Yes') : colors.status.dim('No')}`);
        console.log(`  ${colors.ui.key('JSON Mode:')} ${config.supports_json_mode ? colors.status.success('Yes') : colors.status.dim('No')}`);
        console.log(`  ${colors.ui.key('Max Tokens:')} ${colors.ui.value(config.max_tokens)}`);

        console.log(`\n  ${colors.status.dim('Config ID: ' + config.config_id)}`);
        console.log('\n' + separator() + '\n');

      } catch (error: any) {
        console.error(colors.status.error('✗ Failed to get extraction configuration'));
        console.error(colors.status.error(error.response?.data?.detail || error.message));
        process.exit(1);
      }
    });
}

/**
 * Update extraction configuration
 */
function createExtractionSetCommand(client: KnowledgeGraphClient): Command {
  return new Command('set')
    .description('Update AI extraction configuration')
    .option('--provider <provider>', 'Provider: openai or anthropic')
    .option('--model <model>', 'Model name (e.g., gpt-4o, claude-sonnet-4)')
    .option('--vision', 'Enable vision support')
    .option('--no-vision', 'Disable vision support')
    .option('--json-mode', 'Enable JSON mode')
    .option('--no-json-mode', 'Disable JSON mode')
    .option('--max-tokens <n>', 'Max tokens', parseInt)
    .action(async (options) => {
      try {
        console.log('\n' + separator());
        console.log(colors.ui.title('🤖 Update AI Extraction Configuration'));
        console.log(separator());

        const config: any = {};

        if (options.provider) config.provider = options.provider;
        if (options.model) config.model_name = options.model;
        if (options.vision !== undefined) config.supports_vision = options.vision;
        if (options.jsonMode !== undefined) config.supports_json_mode = options.jsonMode;
        if (options.maxTokens) config.max_tokens = options.maxTokens;

        if (Object.keys(config).length === 0) {
          console.error(colors.status.error('\n✗ No configuration options provided'));
          console.log(colors.status.dim('  Use --help to see available options\n'));
          process.exit(1);
        }

        const result = await client.updateExtractionConfig(config);

        console.log('\n' + colors.status.success('✓ Configuration updated successfully'));
        console.log(`\n  ${colors.ui.key('Config ID:')} ${colors.ui.value(result.config_id)}`);

        if (result.reload_required) {
          console.log(`\n  ${colors.status.warning('⚠️  API restart required to apply changes')}`);
          console.log(`  ${colors.status.dim('Run: ./scripts/stop-api.sh && ./scripts/start-api.sh')}`);
        }

        console.log('\n' + separator() + '\n');

      } catch (error: any) {
        console.error(colors.status.error('✗ Failed to update extraction configuration'));
        console.error(colors.status.error(error.response?.data?.detail || error.message));
        process.exit(1);
      }
    });
}

/**
 * Extraction command group
 */
export function createExtractionCommand(client: KnowledgeGraphClient): Command {
  const extractionCommand = new Command('extraction')
    .description('Manage AI extraction model configuration (ADR-041)');

  extractionCommand.addCommand(createExtractionConfigCommand(client));
  extractionCommand.addCommand(createExtractionSetCommand(client));

  return extractionCommand;
}

// ========== API Keys Commands ==========

/**
 * List API keys with validation status
 */
function createKeysListCommand(client: KnowledgeGraphClient): Command {
  return new Command('list')
    .description('List API keys with validation status')
    .action(async () => {
      try {
        console.log('\n' + separator());
        console.log(colors.ui.title('🔑 API Keys'));
        console.log(separator());

        const keys = await client.listApiKeys();

        console.log('');
        for (const key of keys) {
          const statusIcon = key.configured
            ? (key.validation_status === 'valid' ? colors.status.success('✓') : colors.status.warning('⚠'))
            : colors.status.dim('○');

          console.log(`  ${statusIcon} ${colors.ui.header(key.provider)}`);

          if (key.configured) {
            console.log(`    ${colors.ui.key('Status:')} ${key.validation_status === 'valid' ? colors.status.success('Valid') : colors.status.warning('Invalid')}`);

            if (key.masked_key) {
              console.log(`    ${colors.ui.key('Key:')} ${colors.status.dim(key.masked_key)}`);
            }

            if (key.last_validated_at) {
              const date = new Date(key.last_validated_at);
              console.log(`    ${colors.ui.key('Last Validated:')} ${colors.status.dim(date.toLocaleString())}`);
            }

            if (key.validation_error) {
              console.log(`    ${colors.ui.key('Error:')} ${colors.status.error(key.validation_error)}`);
            }
          } else {
            console.log(`    ${colors.status.dim('Not configured')}`);
          }

          console.log('');
        }

        console.log(separator() + '\n');

      } catch (error: any) {
        console.error(colors.status.error('✗ Failed to list API keys'));
        console.error(colors.status.error(error.response?.data?.detail || error.message));
        process.exit(1);
      }
    });
}

/**
 * Set API key for a provider
 */
function createKeysSetCommand(client: KnowledgeGraphClient): Command {
  return new Command('set')
    .description('Set API key for a provider (validates before storing)')
    .argument('<provider>', 'Provider name (openai or anthropic)')
    .option('--key <key>', 'API key (will prompt if not provided)')
    .action(async (provider: string, options) => {
      try {
        console.log('\n' + separator());
        console.log(colors.ui.title(`🔑 Set ${provider} API Key`));
        console.log(separator());

        // Validate provider
        if (!['openai', 'anthropic'].includes(provider.toLowerCase())) {
          console.error(colors.status.error('\n✗ Invalid provider'));
          console.log(colors.status.dim('  Supported: openai, anthropic\n'));
          process.exit(1);
        }

        // Get API key
        let apiKey = options.key;
        if (!apiKey) {
          console.log(colors.status.warning('\n⚠️  API key will be validated before storage'));
          console.log(colors.status.dim('  A minimal API call will be made to verify the key\n'));
          apiKey = await promptPassword(`Enter ${provider} API key: `);
        }

        if (!apiKey) {
          console.error(colors.status.error('✗ API key required\n'));
          process.exit(1);
        }

        // Set key (validates automatically)
        console.log(colors.status.info('Validating API key...'));
        const result = await client.setApiKey(provider.toLowerCase(), apiKey);

        console.log('\n' + colors.status.success('✓ API key configured and validated'));
        console.log(`\n  ${colors.ui.key('Provider:')} ${colors.ui.value(result.provider)}`);
        console.log(`  ${colors.ui.key('Status:')} ${colors.status.success(result.validation_status)}`);

        console.log('\n' + separator() + '\n');

      } catch (error: any) {
        console.error(colors.status.error('✗ Failed to set API key'));
        console.error(colors.status.error(error.response?.data?.detail || error.message));
        process.exit(1);
      }
    });
}

/**
 * Delete API key for a provider
 */
function createKeysDeleteCommand(client: KnowledgeGraphClient): Command {
  return new Command('delete')
    .description('Delete API key for a provider')
    .argument('<provider>', 'Provider name (openai or anthropic)')
    .action(async (provider: string) => {
      try {
        console.log('\n' + separator());
        console.log(colors.ui.title(`🔑 Delete ${provider} API Key`));
        console.log(separator());

        // Validate provider
        if (!['openai', 'anthropic'].includes(provider.toLowerCase())) {
          console.error(colors.status.error('\n✗ Invalid provider'));
          console.log(colors.status.dim('  Supported: openai, anthropic\n'));
          process.exit(1);
        }

        // Confirm deletion
        const confirm = await prompt(`\nDelete ${provider} API key? (yes/no): `);
        if (confirm.toLowerCase() !== 'yes') {
          console.log(colors.status.dim('Cancelled\n'));
          process.exit(0);
        }

        const result = await client.deleteApiKey(provider.toLowerCase());

        console.log('\n' + colors.status.success('✓ API key deleted'));
        console.log(`\n  ${colors.ui.key('Provider:')} ${colors.ui.value(result.provider)}`);

        console.log('\n' + separator() + '\n');

      } catch (error: any) {
        console.error(colors.status.error('✗ Failed to delete API key'));
        console.error(colors.status.error(error.response?.data?.detail || error.message));
        process.exit(1);
      }
    });
}

/**
 * Keys command group
 */
export function createKeysCommand(client: KnowledgeGraphClient): Command {
  const keysCommand = new Command('keys')
    .description('Manage API keys for AI providers (ADR-031, ADR-041)');

  keysCommand.addCommand(createKeysListCommand(client));
  keysCommand.addCommand(createKeysSetCommand(client));
  keysCommand.addCommand(createKeysDeleteCommand(client));

  return keysCommand;
}
