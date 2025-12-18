/**
 * Vocabulary Sync Command
 * Sync missing edge types from graph to vocabulary (ADR-077)
 */

import { Command } from 'commander';
import { createClientFromEnv } from '../../api/client';
import * as colors from '../colors';
import { coloredCount, separator } from '../colors';

export function createSyncCommand(): Command {
  return new Command('sync')
    .description('Sync missing edge types from graph to vocabulary (ADR-077). Discovers edge types used in the graph but not registered in vocabulary table/VocabType nodes. Use --dry-run first to preview, then --execute to sync.')
    .option('--dry-run', 'Preview missing types without syncing (default)', true)
    .option('--execute', 'Actually sync missing types to vocabulary', false)
    .option('--json', 'Output as JSON for scripting')
    .action(async (options) => {
      try {
        const client = createClientFromEnv();
        const dryRun = !options.execute;

        const result = await client.syncVocabulary(dryRun);

        if (options.json) {
          console.log(JSON.stringify(result, null, 2));
          return;
        }

        console.log('\n' + separator());
        console.log(colors.ui.title('🔄 Vocabulary Sync'));
        console.log(separator());

        // Stats
        console.log(`\n${colors.stats.section('Graph Analysis')}`);
        console.log(`  ${colors.stats.label('Edge types in graph:')} ${coloredCount(result.total_graph_types)}`);
        console.log(`  ${colors.stats.label('Types in vocabulary:')} ${coloredCount(result.total_vocab_types)}`);
        console.log(`  ${colors.stats.label('Missing types:')} ${coloredCount(result.missing.length)}`);

        if (result.system_types.length > 0) {
          console.log(`  ${colors.stats.label('System types (skipped):')} ${colors.status.dim(result.system_types.join(', '))}`);
        }

        // Missing types
        if (result.missing.length > 0) {
          console.log(`\n${colors.stats.section('Missing Types')}`);
          for (const type of result.missing) {
            console.log(`  ${colors.status.warning('→')} ${colors.concept.label(type)}`);
          }
        }

        // Synced types (if executed)
        if (result.synced.length > 0) {
          console.log(`\n${colors.stats.section('Synced Types')}`);
          for (const type of result.synced) {
            console.log(`  ${colors.status.success('✓')} ${colors.concept.label(type)}`);
          }
        }

        // Failed types
        if (result.failed.length > 0) {
          console.log(`\n${colors.stats.section('Failed Types')}`);
          for (const fail of result.failed) {
            console.log(`  ${colors.status.error('✗')} ${colors.concept.label(fail.type)}: ${fail.error}`);
          }
        }

        console.log('\n' + separator());
        if (dryRun) {
          console.log(colors.status.dim('  Dry run mode - no changes made'));
          if (result.missing.length > 0) {
            console.log(colors.status.dim('  Run with --execute to sync missing types'));
          }
        } else {
          console.log(colors.status.success('✓ ' + result.message));
        }
        console.log(separator());

      } catch (error: any) {
        console.error(colors.status.error('✗ Failed to sync vocabulary'));
        console.error(colors.status.error(error.response?.data?.detail || error.message));
        process.exit(1);
      }
    });
}
