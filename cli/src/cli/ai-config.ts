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
 * Create a new embedding configuration
 */
function createEmbeddingCreateCommand(client: KnowledgeGraphClient): Command {
  return new Command('create')
    .description('Create a new embedding configuration (inactive)')
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
        console.log(colors.ui.title('➕ Create Embedding Configuration'));
        console.log(separator());

        const config: any = {};

        if (options.provider) config.provider = options.provider;
        if (options.model) config.model_name = options.model;
        if (options.dimensions) config.embedding_dimensions = options.dimensions;
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

        console.log('\n' + colors.status.success('✓ Configuration created successfully'));
        console.log(`\n  ${colors.ui.key('Config ID:')} ${colors.ui.value(result.config_id)}`);
        console.log(`  ${colors.ui.key('Status:')} ${colors.status.dim('Inactive')}`);

        console.log('\n' + colors.status.warning('⚠️  Next steps:'));
        console.log(colors.status.dim(`  1. Review: kg admin embedding list`));
        console.log(colors.status.dim(`  2. Activate: kg admin embedding activate ${result.config_id}`));
        console.log(colors.status.dim(`  3. Apply: kg admin embedding reload\n`));

        console.log(separator() + '\n');

      } catch (error: any) {
        console.error(colors.status.error('✗ Failed to create embedding configuration'));
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
 * List all embedding configurations
 */
function createEmbeddingListCommand(client: KnowledgeGraphClient): Command {
  return new Command('list')
    .description('List all embedding configurations')
    .action(async () => {
      try {
        console.log('\n' + separator());
        console.log(colors.ui.title('📋 Embedding Configurations'));
        console.log(separator());

        const configs = await client.listEmbeddingConfigs();

        if (configs.length === 0) {
          console.log(colors.status.dim('\n  No configurations found\n'));
        } else {
          console.log('');
          for (const config of configs) {
            const activeMarker = config.active ? colors.status.success('✓ ACTIVE') : colors.status.dim('○ Inactive');
            const deleteProtected = config.delete_protected ? '🔒' : '';
            const changeProtected = config.change_protected ? '🔐' : '';
            const protection = [deleteProtected, changeProtected].filter(p => p).join(' ');

            console.log(`  ${activeMarker} ${colors.ui.header(`Config ${config.id}`)} ${protection}`);
            console.log(`    ${colors.ui.key('Provider:')} ${colors.ui.value(config.provider)}`);

            if (config.model_name) {
              console.log(`    ${colors.ui.key('Model:')} ${colors.ui.value(config.model_name)}`);
            }

            if (config.embedding_dimensions) {
              console.log(`    ${colors.ui.key('Dimensions:')} ${colors.ui.value(config.embedding_dimensions)}`);
            }

            if (config.delete_protected || config.change_protected) {
              const flags = [];
              if (config.delete_protected) flags.push('delete-protected');
              if (config.change_protected) flags.push('change-protected');
              console.log(`    ${colors.ui.key('Protection:')} ${colors.status.warning(flags.join(', '))}`);
            }

            console.log(`    ${colors.status.dim('Updated: ' + new Date(config.updated_at).toLocaleString())}`);
            console.log(`    ${colors.status.dim('By: ' + config.updated_by)}`);
            console.log('');
          }
        }

        console.log(separator() + '\n');

      } catch (error: any) {
        console.error(colors.status.error('✗ Failed to list embedding configurations'));
        console.error(colors.status.error(error.response?.data?.detail || error.message));
        process.exit(1);
      }
    });
}

/**
 * Protect an embedding configuration
 */
function createEmbeddingProtectCommand(client: KnowledgeGraphClient): Command {
  return new Command('protect')
    .description('Enable protection flags on an embedding configuration')
    .argument('<config-id>', 'Configuration ID', parseInt)
    .option('--delete', 'Enable delete protection')
    .option('--change', 'Enable change protection')
    .action(async (configId: number, options) => {
      try {
        console.log('\n' + separator());
        console.log(colors.ui.title(`🔒 Protect Config ${configId}`));
        console.log(separator());

        if (!options.delete && !options.change) {
          console.error(colors.status.error('\n✗ Must specify at least one protection flag'));
          console.log(colors.status.dim('  Use --delete and/or --change\n'));
          process.exit(1);
        }

        const result = await client.protectEmbeddingConfig(
          configId,
          options.delete ? true : undefined,
          options.change ? true : undefined
        );

        console.log('\n' + colors.status.success('✓ Protection enabled'));

        const flags = [];
        if (options.delete) flags.push('delete-protected');
        if (options.change) flags.push('change-protected');

        console.log(`\n  ${colors.ui.key('Config ID:')} ${colors.ui.value(configId)}`);
        console.log(`  ${colors.ui.key('Flags:')} ${colors.status.warning(flags.join(', '))}`);
        console.log('\n' + separator() + '\n');

      } catch (error: any) {
        console.error(colors.status.error('✗ Failed to set protection'));
        console.error(colors.status.error(error.response?.data?.detail || error.message));
        process.exit(1);
      }
    });
}

/**
 * Unprotect an embedding configuration
 */
function createEmbeddingUnprotectCommand(client: KnowledgeGraphClient): Command {
  return new Command('unprotect')
    .description('Disable protection flags on an embedding configuration')
    .argument('<config-id>', 'Configuration ID', parseInt)
    .option('--delete', 'Disable delete protection')
    .option('--change', 'Disable change protection')
    .action(async (configId: number, options) => {
      try {
        console.log('\n' + separator());
        console.log(colors.ui.title(`🔓 Unprotect Config ${configId}`));
        console.log(separator());

        if (!options.delete && !options.change) {
          console.error(colors.status.error('\n✗ Must specify at least one protection flag'));
          console.log(colors.status.dim('  Use --delete and/or --change\n'));
          process.exit(1);
        }

        const result = await client.protectEmbeddingConfig(
          configId,
          options.delete ? false : undefined,
          options.change ? false : undefined
        );

        console.log('\n' + colors.status.success('✓ Protection disabled'));

        const flags = [];
        if (options.delete) flags.push('delete-protection');
        if (options.change) flags.push('change-protection');

        console.log(`\n  ${colors.ui.key('Config ID:')} ${colors.ui.value(configId)}`);
        console.log(`  ${colors.ui.key('Removed:')} ${colors.status.dim(flags.join(', '))}`);
        console.log('\n' + separator() + '\n');

      } catch (error: any) {
        console.error(colors.status.error('✗ Failed to remove protection'));
        console.error(colors.status.error(error.response?.data?.detail || error.message));
        process.exit(1);
      }
    });
}

/**
 * Activate an embedding configuration
 */
function createEmbeddingActivateCommand(client: KnowledgeGraphClient): Command {
  return new Command('activate')
    .description('Activate an embedding configuration (with automatic protection)')
    .argument('<config-id>', 'Configuration ID', parseInt)
    .option('--force', 'Force activation even with dimension mismatch (dangerous!)')
    .action(async (configId: number, options: any) => {
      try {
        console.log('\n' + separator());
        console.log(colors.ui.title(`🔄 Activate Config ${configId}`));
        console.log(separator());

        if (options.force) {
          console.log(colors.status.warning('\n⚠️  FORCE MODE: Bypassing dimension safety check'));
          console.log(colors.status.dim('  This may break vector search if dimensions change!\n'));
        }

        console.log(colors.status.info('\nActivating configuration...'));
        console.log(colors.status.dim('  • Unlocking current config (change protection)'));
        console.log(colors.status.dim('  • Switching to new config'));
        console.log(colors.status.dim('  • Locking new config (delete + change protection)'));

        const result = await client.activateEmbeddingConfig(configId, options.force);

        console.log('\n' + colors.status.success('✓ Configuration activated successfully'));

        console.log(`\n  ${colors.ui.key('Config ID:')} ${colors.ui.value(result.config_id)}`);
        console.log(`  ${colors.ui.key('Provider:')} ${colors.ui.value(result.provider)}`);

        if (result.model) {
          console.log(`  ${colors.ui.key('Model:')} ${colors.ui.value(result.model)}`);
        }

        if (result.dimensions) {
          console.log(`  ${colors.ui.key('Dimensions:')} ${colors.ui.value(result.dimensions)}`);
        }

        console.log('\n' + colors.status.warning('⚠️  Next step: Hot reload to apply changes'));
        console.log(colors.status.dim('  Run: kg admin embedding reload\n'));
        console.log(separator() + '\n');

      } catch (error: any) {
        console.error(colors.status.error('✗ Failed to activate configuration'));
        console.error(colors.status.error(error.response?.data?.detail || error.message));
        process.exit(1);
      }
    });
}

/**
 * Delete an embedding configuration
 */
function createEmbeddingDeleteCommand(client: KnowledgeGraphClient): Command {
  return new Command('delete')
    .description('Delete an embedding configuration')
    .argument('<config-id>', 'Configuration ID', parseInt)
    .action(async (configId: number) => {
      try {
        console.log('\n' + separator());
        console.log(colors.ui.title(`🗑️  Delete Config ${configId}`));
        console.log(separator());

        // Confirm deletion
        const confirm = await prompt(`\nDelete embedding config ${configId}? (yes/no): `);
        if (confirm.toLowerCase() !== 'yes') {
          console.log(colors.status.dim('Cancelled\n'));
          process.exit(0);
        }

        const result = await client.deleteEmbeddingConfig(configId);

        console.log('\n' + colors.status.success('✓ Configuration deleted'));
        console.log(`\n  ${colors.ui.key('Config ID:')} ${colors.ui.value(configId)}`);
        console.log('\n' + separator() + '\n');

      } catch (error: any) {
        console.error(colors.status.error('✗ Failed to delete configuration'));
        console.error(colors.status.error(error.response?.data?.detail || error.message));
        process.exit(1);
      }
    });
}

/**
 * Show comprehensive embedding status (ADR-068 Phase 4)
 */
function createEmbeddingStatusCommand(client: KnowledgeGraphClient): Command {
  return new Command('status')
    .description('Show comprehensive embedding coverage across all graph text entities with hash verification')
    .option('--ontology <name>', 'Limit status to specific ontology namespace')
    .action(async (options) => {
      try {
        console.log(separator());
        console.log(colors.ui.title('📊 Embedding Coverage Status'));
        if (options.ontology) {
          console.log(colors.status.dim(`   Ontology: ${options.ontology}`));
        }
        console.log(separator());

        const status = await client.getEmbeddingStatus(options.ontology);

        // Active Config
        if (status.active_config) {
          console.log();
          console.log(colors.ui.header('Active Embedding Configuration:'));
          console.log(`  ${colors.ui.key('Provider:')} ${colors.ui.value(status.active_config.provider)}`);
          console.log(`  ${colors.ui.key('Model:')} ${colors.ui.value(status.active_config.model_name)}`);
          console.log(`  ${colors.ui.key('Dimensions:')} ${colors.ui.value(status.active_config.embedding_dimensions.toString())}`);
        }

        // Concepts
        console.log();
        console.log(colors.ui.header('Concepts (AGE Graph Nodes):'));
        console.log(`  ${colors.ui.key('Total:')} ${colors.ui.value(status.concepts.total.toString())}`);
        console.log(`  ${colors.status.success('✓ With embeddings:')} ${colors.ui.value(status.concepts.with_embeddings.toString())} (${status.concepts.percentage}%)`);
        if (status.concepts.without_embeddings > 0) {
          console.log(`  ${colors.status.warning('✗ Without embeddings:')} ${colors.ui.value(status.concepts.without_embeddings.toString())}`);
        }
        if (status.concepts.incompatible_embeddings > 0) {
          console.log(`  ${colors.status.error('⚠  Incompatible:')} ${colors.ui.value(status.concepts.incompatible_embeddings.toString())} (model/dimension mismatch)`);
        }

        // Sources
        console.log();
        console.log(colors.ui.header('Sources (Text Chunks):'));
        console.log(`  ${colors.ui.key('Total:')} ${colors.ui.value(status.sources.total.toString())}`);
        console.log(`  ${colors.status.success('✓ With embeddings:')} ${colors.ui.value(status.sources.with_embeddings.toString())} (${status.sources.percentage}%)`);
        if (status.sources.without_embeddings > 0) {
          console.log(`  ${colors.status.warning('✗ Without embeddings:')} ${colors.ui.value(status.sources.without_embeddings.toString())}`);
        }
        if (status.sources.stale_embeddings > 0) {
          console.log(`  ${colors.status.error('⚠  Stale embeddings:')} ${colors.ui.value(status.sources.stale_embeddings.toString())} (hash mismatch - source changed)`);
        }
        if (status.sources.incompatible_embeddings > 0) {
          console.log(`  ${colors.status.error('⚠  Incompatible:')} ${colors.ui.value(status.sources.incompatible_embeddings.toString())} (model/dimension mismatch)`);
        }

        // Vocabulary
        console.log();
        console.log(colors.ui.header('Vocabulary (Relationship Types):'));
        console.log(`  ${colors.ui.key('Total:')} ${colors.ui.value(status.vocabulary.total.toString())}`);
        console.log(`  ${colors.status.success('✓ With embeddings:')} ${colors.ui.value(status.vocabulary.with_embeddings.toString())} (${status.vocabulary.percentage}%)`);
        if (status.vocabulary.without_embeddings > 0) {
          console.log(`  ${colors.status.warning('✗ Without embeddings:')} ${colors.ui.value(status.vocabulary.without_embeddings.toString())}`);
        }
        if (status.vocabulary.incompatible_embeddings > 0) {
          console.log(`  ${colors.status.error('⚠  Incompatible:')} ${colors.ui.value(status.vocabulary.incompatible_embeddings.toString())} (model/dimension mismatch)`);
        }

        // Images (future)
        if (status.images && status.images.total > 0) {
          console.log();
          console.log(colors.ui.header('Images:'));
          console.log(`  ${colors.ui.key('Total:')} ${colors.ui.value(status.images.total.toString())}`);
          console.log(`  ${colors.status.success('✓ With embeddings:')} ${colors.ui.value(status.images.with_embeddings.toString())} (${status.images.percentage}%)`);
        } else if (status.images && status.images.note) {
          console.log();
          console.log(colors.ui.header('Images:'));
          console.log(`  ${colors.status.dim(status.images.note)}`);
        }

        // Summary
        console.log();
        console.log(separator());
        console.log(colors.ui.header('Overall Summary:'));
        console.log(`  ${colors.ui.key('Total Entities:')} ${colors.ui.value(status.summary.total_entities.toString())}`);
        console.log(`  ${colors.status.success('✓ With Embeddings:')} ${colors.ui.value(status.summary.total_with_embeddings.toString())} (${status.summary.overall_percentage}%)`);
        if (status.summary.total_without_embeddings > 0) {
          console.log(`  ${colors.status.warning('✗ Without Embeddings:')} ${colors.ui.value(status.summary.total_without_embeddings.toString())}`);
        }
        if (status.summary.total_incompatible > 0) {
          console.log(`  ${colors.status.error('⚠  Incompatible:')} ${colors.ui.value(status.summary.total_incompatible.toString())} (requires regeneration)`);
        }
        console.log(separator());
        console.log();

      } catch (error: any) {
        console.error();
        console.error(colors.status.error('✗ Failed to get embedding status'));
        console.error(colors.status.dim(`  ${error.message || error}`));
        console.error();
        process.exit(1);
      }
    });
}

/**
 * Regenerate embeddings (ADR-068 Phase 4)
 */
function createEmbeddingRegenerateCommand(client: KnowledgeGraphClient): Command {
  const cmd = new Command('regenerate')
    .description('Regenerate vector embeddings for all graph text entities: concepts, sources, vocabulary (ADR-068 Phase 4) - useful after changing embedding model or repairing missing embeddings')
    .option('--type <type>', 'Type of embeddings to regenerate: concept, source, vocabulary, all')
    .option('--only-missing', 'Only generate for entities without embeddings (skip existing) - applies to concept and source types', false)
    .option('--only-incompatible', 'Only regenerate embeddings with mismatched model/dimensions (for model migrations)', false)
    .option('--ontology <name>', 'Limit regeneration to specific ontology namespace - applies to concept and source types')
    .option('--limit <n>', 'Maximum number of entities to process (useful for testing/batching)', parseInt)
    .option('--status', 'Show embedding status before regeneration (diagnostic mode)', false)
    .action(async (options) => {
      // If --status flag is set, show status and exit (reuse status command logic)
      if (options.status) {
        const statusCommand = createEmbeddingStatusCommand(client);
        await statusCommand.parseAsync(['status', ...(options.ontology ? ['--ontology', options.ontology] : [])], { from: 'user' });
        return;
      }

      // If no --type provided, show help and exit
      if (!options.type) {
        console.log();
        console.log(colors.status.warning('⚠  No --type specified'));
        console.log();
        console.log(colors.ui.header('Usage:'));
        console.log('  kg admin embedding regenerate --type <type> [options]');
        console.log();
        console.log(colors.ui.header('Required:'));
        console.log('  --type <type>           Type: concept, source, vocabulary, all');
        console.log();
        console.log(colors.ui.header('Options:'));
        console.log('  --only-missing          Only generate for entities without embeddings');
        console.log('  --only-incompatible     Only regenerate embeddings with model/dimension mismatch');
        console.log('  --ontology <name>       Limit to specific ontology (concept/source only)');
        console.log('  --limit <n>             Maximum number of entities to process');
        console.log('  --status                Show embedding status first (diagnostic mode)');
        console.log();
        console.log(colors.ui.header('Examples:'));
        console.log('  kg admin embedding regenerate --type concept --only-missing');
        console.log('  kg admin embedding regenerate --type source --only-incompatible');
        console.log('  kg admin embedding regenerate --type all');
        console.log('  kg admin embedding regenerate --status  # Show status first');
        console.log();
        console.log(colors.status.dim('Tip: Run "kg admin embedding status" to check current coverage'));
        console.log();
        process.exit(0);
      }

      // Normal regeneration flow
      try {
        // Validate embedding type
        const validTypes = ['concept', 'source', 'vocabulary', 'all'];
        const embeddingType = options.type;

        if (!validTypes.includes(embeddingType)) {
          console.error();
          console.error(colors.status.error(`✗ Invalid --type: ${embeddingType}`));
          console.error(colors.status.dim(`  Valid types: ${validTypes.join(', ')}`));
          console.error();
          process.exit(1);
        }

        // Validate flag combination
        if (options.onlyMissing && options.onlyIncompatible) {
          console.error();
          console.error(colors.status.error('✗ Cannot use both --only-missing and --only-incompatible'));
          console.error(colors.status.dim('  Choose one: missing (no embeddings) or incompatible (wrong model/dimensions)'));
          console.error();
          process.exit(1);
        }

        console.log(separator());
        console.log(colors.ui.title(`🔄 Regenerating ${embeddingType.charAt(0).toUpperCase() + embeddingType.slice(1)} Embeddings`));
        console.log(separator());

        const params: any = {
          embedding_type: embeddingType,
          only_missing: options.onlyMissing || false,
          only_incompatible: options.onlyIncompatible || false
        };

        if (options.ontology) {
          params.ontology = options.ontology;
        }

        if (options.limit) {
          params.limit = options.limit;
        }

        console.log();
        console.log(colors.status.info('Starting regeneration...'));
        console.log(colors.status.dim(`  Type: ${embeddingType}`));
        if (options.ontology) {
          console.log(colors.status.dim(`  Ontology: ${options.ontology}`));
        }
        if (options.onlyMissing) {
          console.log(colors.status.dim('  Mode: Only missing embeddings'));
        }
        if (options.onlyIncompatible) {
          console.log(colors.status.dim('  Mode: Only incompatible embeddings (model migration)'));
        }
        if (options.limit) {
          console.log(colors.status.dim(`  Limit: ${options.limit} entities`));
        }
        console.log();

        const result = await client.regenerateEmbeddings(params);

        console.log(separator());
        console.log(colors.status.success('✓ Regeneration completed'));

        // Handle 'all' type response (has totals and per-type results)
        if (embeddingType === 'all' && result.totals) {
          console.log(`  ${colors.stats.label('Total Processed:')} ${colors.stats.value(result.totals.processed_count.toString())} / ${result.totals.target_count}`);

          if (result.totals.failed_count > 0) {
            console.log(`  ${colors.status.error('Total Failed:')} ${result.totals.failed_count}`);
          }

          console.log(`  ${colors.status.dim('Total Duration:')} ${result.totals.duration_ms}ms`);

          console.log();
          console.log(colors.ui.header('Breakdown:'));

          if (result.results.concepts) {
            console.log(`  ${colors.ui.key('Concepts:')} ${colors.stats.value(result.results.concepts.processed_count.toString())} / ${result.results.concepts.target_count} (${result.results.concepts.duration_ms}ms)`);
          }

          if (result.results.sources) {
            console.log(`  ${colors.ui.key('Sources:')} ${colors.stats.value(result.results.sources.processed_count.toString())} / ${result.results.sources.target_count} (${result.results.sources.duration_ms}ms)`);
          }

          if (result.results.vocabulary) {
            console.log(`  ${colors.ui.key('Vocabulary:')} ${colors.stats.value(result.results.vocabulary.processed_count.toString())} / ${result.results.vocabulary.target_count} (${result.results.vocabulary.duration_ms}ms)`);
          }
        } else {
          // Single type response
          console.log(`  ${colors.stats.label('Processed:')} ${colors.stats.value(result.processed_count.toString())} / ${result.target_count}`);

          if (result.failed_count > 0) {
            console.log(`  ${colors.status.error('Failed:')} ${result.failed_count}`);
          }

          console.log(`  ${colors.status.dim('Duration:')} ${result.duration_ms}ms`);

          if (result.embedding_model && result.embedding_provider) {
            console.log(`  ${colors.status.dim('Model:')} ${result.embedding_provider}/${result.embedding_model}`);
          }

          if (result.errors && result.errors.length > 0) {
            console.log();
            console.log(colors.status.error('Errors:'));
            result.errors.slice(0, 5).forEach((err: string) => {
              console.log(colors.status.dim(`  ${err}`));
            });
            if (result.errors.length > 5) {
              console.log(colors.status.dim(`  ... and ${result.errors.length - 5} more`));
            }
          }
        }

        console.log(separator());
        console.log();

      } catch (error: any) {
        console.error();
        console.error(colors.status.error('✗ Failed to regenerate embeddings'));
        console.error(colors.status.dim(`  ${error.message || error}`));
        console.error();
        process.exit(1);
      }
    });

  return cmd;
}

/**
 * Embedding command group
 */
export function createEmbeddingCommand(client: KnowledgeGraphClient): Command {
  const embeddingCommand = new Command('embedding')
    .description('Manage embedding model configuration (ADR-039)');

  embeddingCommand.addCommand(createEmbeddingListCommand(client));
  embeddingCommand.addCommand(createEmbeddingCreateCommand(client));
  embeddingCommand.addCommand(createEmbeddingActivateCommand(client));
  embeddingCommand.addCommand(createEmbeddingReloadCommand(client));
  embeddingCommand.addCommand(createEmbeddingProtectCommand(client));
  embeddingCommand.addCommand(createEmbeddingUnprotectCommand(client));
  embeddingCommand.addCommand(createEmbeddingDeleteCommand(client));
  embeddingCommand.addCommand(createEmbeddingStatusCommand(client));
  embeddingCommand.addCommand(createEmbeddingRegenerateCommand(client));

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

        // Show rate limiting configuration (ADR-049)
        if (config.max_concurrent_requests !== undefined || config.max_retries !== undefined) {
          console.log(`\n  ${colors.ui.header('Rate Limiting Configuration:')}`);
          if (config.max_concurrent_requests !== undefined) {
            console.log(`    ${colors.ui.key('Max Concurrent Requests:')} ${colors.ui.value(config.max_concurrent_requests)}`);
          }
          if (config.max_retries !== undefined) {
            console.log(`    ${colors.ui.key('Max Retries:')} ${colors.ui.value(config.max_retries)}`);
          }
        }

        // Show local provider configuration (ADR-042)
        if (config.provider === 'ollama' || config.provider === 'vllm') {
          console.log(`\n  ${colors.ui.header('Local Inference Configuration:')}`);
          if (config.base_url) {
            console.log(`    ${colors.ui.key('Base URL:')} ${colors.ui.value(config.base_url)}`);
          }
          if (config.temperature !== undefined) {
            console.log(`    ${colors.ui.key('Temperature:')} ${colors.ui.value(config.temperature)}`);
          }
          if (config.top_p !== undefined) {
            console.log(`    ${colors.ui.key('Top P:')} ${colors.ui.value(config.top_p)}`);
          }
          if (config.gpu_layers !== undefined) {
            console.log(`    ${colors.ui.key('GPU Layers:')} ${colors.ui.value(config.gpu_layers === -1 ? 'auto' : config.gpu_layers)}`);
          }
          if (config.num_threads !== undefined) {
            console.log(`    ${colors.ui.key('CPU Threads:')} ${colors.ui.value(config.num_threads)}`);
          }
          if (config.thinking_mode !== undefined) {
            console.log(`    ${colors.ui.key('Thinking Mode:')} ${colors.ui.value(config.thinking_mode)}`);
          }
        }

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
    .option('--provider <provider>', 'Provider: openai, anthropic, ollama, or vllm')
    .option('--model <model>', 'Model name (e.g., gpt-4o, mistral:7b-instruct)')
    .option('--vision', 'Enable vision support')
    .option('--no-vision', 'Disable vision support')
    .option('--json-mode', 'Enable JSON mode')
    .option('--no-json-mode', 'Disable JSON mode')
    .option('--max-tokens <n>', 'Max tokens', parseInt)
    .option('--base-url <url>', 'Base URL for local providers (e.g., http://localhost:11434)')
    .option('--temperature <n>', 'Sampling temperature 0.0-1.0 (default: 0.1)', parseFloat)
    .option('--top-p <n>', 'Nucleus sampling threshold 0.0-1.0 (default: 0.9)', parseFloat)
    .option('--gpu-layers <n>', 'GPU layers: -1=auto, 0=CPU only, >0=specific count', parseInt)
    .option('--num-threads <n>', 'CPU threads for inference (default: 4)', parseInt)
    .option('--thinking-mode <mode>', 'Thinking mode: off, low, medium, high (Ollama 0.12.x+)')
    .action(async (options) => {
      try {
        console.log('\n' + separator());
        console.log(colors.ui.title('🤖 Update AI Extraction Configuration'));
        console.log(separator());

        const config: any = {};

        // Common options
        if (options.provider) config.provider = options.provider;
        if (options.model) config.model_name = options.model;
        if (options.vision !== undefined) config.supports_vision = options.vision;
        if (options.jsonMode !== undefined) config.supports_json_mode = options.jsonMode;
        if (options.maxTokens) config.max_tokens = options.maxTokens;

        // Local provider options (ADR-042)
        if (options.baseUrl) config.base_url = options.baseUrl;
        if (options.temperature !== undefined) config.temperature = options.temperature;
        if (options.topP !== undefined) config.top_p = options.topP;
        if (options.gpuLayers !== undefined) config.gpu_layers = options.gpuLayers;
        if (options.numThreads !== undefined) config.num_threads = options.numThreads;
        if (options.thinkingMode) {
          // Validate thinking mode
          const validModes = ['off', 'low', 'medium', 'high'];
          if (!validModes.includes(options.thinkingMode)) {
            console.error(colors.status.error(`\n✗ Invalid thinking mode: ${options.thinkingMode}`));
            console.log(colors.status.dim('  Valid options: off, low, medium, high\n'));
            process.exit(1);
          }
          config.thinking_mode = options.thinkingMode;
        }

        if (Object.keys(config).length === 0) {
          console.error(colors.status.error('\n✗ No configuration options provided'));
          console.log(colors.status.dim('  Use --help to see available options\n'));
          process.exit(1);
        }

        // Validate provider-specific requirements
        if (config.provider === 'ollama' || config.provider === 'vllm') {
          if (!config.model_name && !options.model) {
            console.error(colors.status.error('\n✗ Model name required for local providers'));
            console.log(colors.status.dim('  Example: --model mistral:7b-instruct\n'));
            process.exit(1);
          }
        }

        const result = await client.updateExtractionConfig(config);

        console.log('\n' + colors.status.success('✓ Configuration updated successfully'));
        console.log(`\n  ${colors.ui.key('Config ID:')} ${colors.ui.value(result.config_id)}`);

        // Show helpful next steps for Ollama
        if (config.provider === 'ollama') {
          console.log(`\n  ${colors.ui.header('Next Steps:')}`);
          console.log(`    1. Ensure Ollama is running: ${colors.status.dim('./scripts/start-ollama.sh -y')}`);
          console.log(`    2. Pull model: ${colors.status.dim(`docker exec kg-ollama ollama pull ${config.model_name || '<model>'}`)}`);
          console.log(`    3. Test extraction: ${colors.status.dim('kg admin extraction test')}`);
        }

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
