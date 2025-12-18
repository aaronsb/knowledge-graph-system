/**
 * Vocabulary Configuration Commands
 * Show and update vocabulary configuration settings
 */

import { Command } from 'commander';
import { createClientFromEnv } from '../../api/client';
import * as colors from '../colors';
import { coloredCount, separator } from '../colors';
import { Table } from '../../lib/table';

export function createConfigCommand(): Command {
  return new Command('config')
    .description('Show or update vocabulary configuration. No args: display config. With args: update properties (e.g., "kg vocab config vocab_max 275").')
    .argument('[properties...]', 'Property assignments: key value [key value...]')
    .action(async (properties: string[]) => {
      // If properties provided, update config
      if (properties && properties.length > 0) {
        if (properties.length % 2 !== 0) {
          console.error(colors.status.error('✗ Properties must be provided as key-value pairs'));
          console.error(colors.status.dim('  Usage: kg vocab config <key> <value> [<key> <value>...]'));
          console.error(colors.status.dim('  Example: kg vocab config vocab_max 275 vocab_emergency 350'));
          process.exit(1);
        }

        try {
          const client = createClientFromEnv();

          // Get logged-in user from OAuth credentials
          const { getConfig } = require('../../lib/config');
          const configManager = getConfig();
          const credentials = configManager.getOAuthCredentials();
          const username = credentials?.username || 'cli-user';

          const updates: any = {
            updated_by: username
          };

          // Parse key-value pairs
          for (let i = 0; i < properties.length; i += 2) {
            const key = properties[i];
            const value = properties[i + 1];

            // Parse value based on type
            if (key === 'vocab_min' || key === 'vocab_max' || key === 'vocab_emergency') {
              updates[key] = parseInt(value);
            } else if (key === 'auto_expand_enabled') {
              updates[key] = value.toLowerCase() === 'true';
            } else if (key === 'synonym_threshold_strong' || key === 'synonym_threshold_moderate' ||
                      key === 'low_value_threshold' || key === 'consolidation_similarity_threshold') {
              updates[key] = parseFloat(value);
            } else if (key === 'pruning_mode' || key === 'aggressiveness_profile' || key === 'embedding_model') {
              updates[key] = value;
            } else {
              console.error(colors.status.error(`✗ Unknown property: ${key}`));
              process.exit(1);
            }
          }

          // Update config
          await client.updateVocabularyConfig(updates);

          console.log(colors.status.success('\n✓ Configuration updated successfully\n'));

        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to update vocabulary configuration'));
          if (error.response?.data?.detail) {
            console.error(colors.status.error(JSON.stringify(error.response.data.detail, null, 2)));
          } else {
            console.error(colors.status.error(error.message || String(error)));
          }
          process.exit(1);
        }
      }

      // Display config (either after update or when called with no args)
      try {
        const client = createClientFromEnv();

        console.log('\n' + separator());
        console.log(colors.ui.title('📋 Vocabulary Configuration'));
        console.log(separator());

        const config = await client.getVocabularyConfigDetail();

        // Zone color mapping
        const zoneColors: Record<string, (text: string) => string> = {
          comfort: colors.status.success,
          watch: colors.status.warning,
          merge: colors.status.warning,
          mixed: colors.status.warning,
          emergency: colors.status.error,
          block: colors.status.error
        };
        const zoneColor = zoneColors[config.zone] || colors.ui.value;

        // Current state table
        console.log(`\n${colors.stats.section('Current State')}\n`);

        const stateRows = [
          { metric: 'Vocabulary Size', value: config.current_size.toString() },
          { metric: 'Zone', value: config.zone.toUpperCase() },
          { metric: 'Aggressiveness', value: (config.aggressiveness * 100).toFixed(1) + '%' }
        ];

        const stateTable = new Table<typeof stateRows[0]>({
          columns: [
            {
              header: 'Metric',
              field: 'metric',
              type: 'heading',
              width: 'auto',
              priority: 2
            },
            {
              header: 'Value',
              field: 'value',
              type: 'value',
              width: 'flex',
              priority: 3
            }
          ]
        });

        stateTable.print(stateRows);

        // Configuration table
        console.log(`\n${colors.stats.section('Configuration Parameters')}`);
        console.log(colors.status.dim('Use `kg vocab config <property> <value>` to update:\n'));

        const configRows = [
          { parameter: 'Minimum Threshold', value: config.vocab_min.toString(), property: 'vocab_min' },
          { parameter: 'Maximum Threshold', value: config.vocab_max.toString(), property: 'vocab_max' },
          { parameter: 'Emergency Threshold', value: config.vocab_emergency.toString(), property: 'vocab_emergency' },
          { parameter: 'Pruning Mode', value: config.pruning_mode, property: 'pruning_mode' },
          { parameter: 'Aggressiveness Profile', value: config.aggressiveness_profile, property: 'aggressiveness_profile' },
          { parameter: 'Auto-expand', value: config.auto_expand_enabled ? 'true' : 'false', property: 'auto_expand_enabled' },
          { parameter: 'Synonym (Strong)', value: config.synonym_threshold_strong.toFixed(2), property: 'synonym_threshold_strong' },
          { parameter: 'Synonym (Moderate)', value: config.synonym_threshold_moderate.toFixed(2), property: 'synonym_threshold_moderate' },
          { parameter: 'Low Value Threshold', value: config.low_value_threshold.toFixed(1), property: 'low_value_threshold' },
          { parameter: 'Consolidation Threshold', value: config.consolidation_similarity_threshold.toFixed(2), property: 'consolidation_similarity_threshold' },
          { parameter: 'Embedding Model', value: config.embedding_model, property: '(managed via kg admin embedding)' },
        ];

        const table = new Table<typeof configRows[0]>({
          columns: [
            {
              header: 'Parameter',
              field: 'parameter',
              type: 'heading',
              width: 'flex',
              priority: 2
            },
            {
              header: 'Value',
              field: 'value',
              type: 'value',
              width: 'auto',
              priority: 3
            },
            {
              header: 'Property Name',
              field: 'property',
              type: 'value',
              width: 'flex',
              priority: 1
            }
          ]
        });

        table.print(configRows);
        console.log('\n' + separator());

      } catch (error: any) {
        console.error(colors.status.error('✗ Failed to get vocabulary configuration'));
        console.error(colors.status.error(error.response?.data?.detail || error.message));
        process.exit(1);
      }
    });
}
