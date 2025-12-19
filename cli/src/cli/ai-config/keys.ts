/**
 * API Keys Commands (ADR-031, ADR-041)
 * Manages API keys for AI providers
 */

import { Command } from 'commander';
import { KnowledgeGraphClient } from '../../api/client';
import * as colors from '../colors';
import { separator } from '../colors';
import { prompt, promptPassword } from './utils';

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
