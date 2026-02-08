/**
 * Vocabulary Consolidation Commands
 * AI-assisted consolidation and manual merge (ADR-032)
 */

import { Command } from 'commander';
import { createClientFromEnv } from '../../api/client';
import * as colors from '../colors';
import { coloredCount, separator } from '../colors';

export function createConsolidateCommand(): Command {
  return new Command('consolidate')
    .description('AI-assisted vocabulary consolidation workflow (AITL - AI-in-the-loop, ADR-032). Analyzes vocabulary via embeddings, identifies similar pairs above threshold, presents merge recommendations.')
    .option('-t, --target <size>', 'Target vocabulary size', '90')
    .option('--threshold <value>', 'Auto-execute threshold (0.0-1.0)', '0.90')
    .option('--dry-run', 'Preview candidates without executing (no merges, no pruning)')
    .option('--no-prune-unused', 'Skip pruning vocabulary types with 0 uses')
    .action(async (options) => {
      try {
        const client = createClientFromEnv();
        const targetSize = parseInt(options.target);
        const threshold = parseFloat(options.threshold);
        const dryRun = options.dryRun || false;
        const pruneUnused = options.pruneUnused !== false;

        // Validate inputs
        if (isNaN(targetSize) || targetSize < 30 || targetSize > 200) {
          console.error(colors.status.error('✗ Target size must be between 30 and 200'));
          process.exit(1);
        }

        if (isNaN(threshold) || threshold < 0 || threshold > 1) {
          console.error(colors.status.error('✗ Threshold must be between 0.0 and 1.0'));
          process.exit(1);
        }

        // Show mode
        console.log('\n' + separator());
        console.log(colors.ui.title('🔄 Vocabulary Consolidation'));
        console.log(separator());

        if (dryRun) {
          console.log(`\n${colors.ui.key('Mode:')} ${colors.status.dim('DRY RUN')} (preview only)`);
        } else {
          console.log(`\n${colors.ui.key('Mode:')} ${colors.status.success('EXECUTE')} (merge + prune)`);
        }

        console.log(`${colors.ui.key('Target Size:')} ${coloredCount(targetSize)}`);
        console.log(`${colors.ui.key('Auto-Execute Threshold:')} ${colors.ui.value((threshold * 100).toFixed(0) + '%')}`);
        console.log(`${colors.ui.key('Prune Unused:')} ${pruneUnused ? colors.status.success('Enabled') : colors.status.dim('Disabled')}`);

        // Run consolidation
        console.log('\n' + colors.status.dim('Running LLM-based consolidation workflow...'));
        console.log(colors.status.dim('This may take a few minutes depending on vocabulary size.\n'));

        const result = await client.consolidateVocabulary({
          target_size: targetSize,
          batch_size: 1,
          auto_execute_threshold: threshold,
          dry_run: dryRun,
          prune_unused: pruneUnused
        });

        // Display results
        console.log('\n' + separator());
        console.log(colors.ui.title('📊 Consolidation Results'));
        console.log(separator());

        console.log('\n' + colors.stats.section('Summary'));
        console.log(`  ${colors.stats.label('Initial Size:')} ${coloredCount(result.initial_size)}`);
        console.log(`  ${colors.stats.label('Final Size:')} ${coloredCount(result.final_size)}`);
        if (result.size_reduction > 0) {
          console.log(`  ${colors.stats.label('Reduction:')} ${colors.status.success('-' + result.size_reduction)}`);
        } else {
          console.log(`  ${colors.stats.label('Reduction:')} ${colors.status.dim('0')}`);
        }
        console.log(`  ${colors.stats.label('Merged:')} ${coloredCount(result.auto_executed.length)}`);
        console.log(`  ${colors.stats.label('Rejected:')} ${coloredCount(result.rejected.length)}`);
        if (result.pruned_count !== undefined && result.pruned_count > 0) {
          console.log(`  ${colors.stats.label('Pruned:')} ${colors.status.success(result.pruned_count.toString())}`);
        }

        // Auto-executed merges
        // Filter out no-op merges (same type → same type)
        const actualMerges = result.auto_executed.filter(
          (m: any) => m.deprecated !== m.target
        );
        const skippedSelfMerges = result.auto_executed.length - actualMerges.length;

        if (actualMerges.length > 0) {
          console.log('\n' + colors.stats.section(dryRun ? 'Proposed Merges' : 'Executed Merges'));
          console.log(separator(80, '─'));
          actualMerges.forEach((merge: any) => {
            const status = merge.error ? '✗' : '✓';
            const statusColor = merge.error ? colors.status.error : colors.status.success;
            console.log(`\n${statusColor(status)} ${merge.deprecated} → ${merge.target}`);
            console.log(`   ${colors.ui.key('Similarity:')} ${colors.ui.value((merge.similarity * 100).toFixed(1) + '%')}`);
            console.log(`   ${colors.ui.key('Reasoning:')} ${colors.status.dim(merge.reasoning)}`);
            const edgesUpdated = merge.edges_updated ?? 0;
            if (!dryRun && edgesUpdated > 0) {
              console.log(`   ${colors.ui.key('Edges Updated:')} ${coloredCount(edgesUpdated)}`);
            }
            if (merge.error) {
              console.log(`   ${colors.status.error('ERROR:')} ${merge.error}`);
            }
          });
        }
        if (skippedSelfMerges > 0) {
          console.log(`\n${colors.status.dim(`  (${skippedSelfMerges} self-referencing merge(s) skipped)`)}`);
        }

        // Rejected
        if (result.rejected.length > 0) {
          console.log('\n' + colors.stats.section(`Rejected Merges (showing first 10 of ${result.rejected.length})`));
          console.log(separator(80, '─'));
          result.rejected.slice(0, 10).forEach((reject: any) => {
            console.log(`\n✗ ${reject.type1} + ${reject.type2}`);
            console.log(`   ${colors.ui.key('Reasoning:')} ${colors.status.dim(reject.reasoning)}`);
          });
        }

        console.log('\n' + separator());
        console.log(colors.status.success('✓ ' + result.message));
        console.log(separator());
      } catch (error: any) {
        console.error(colors.status.error('✗ Failed to consolidate vocabulary'));
        console.error(colors.status.error(error.response?.data?.detail || error.message));
        process.exit(1);
      }
    });
}

export function createMergeCommand(): Command {
  return new Command('merge')
    .description('Manually merge one edge type into another. Redirects all edges from deprecated type to target type.')
    .argument('<deprecated-type>', 'Edge type to deprecate (becomes inactive)')
    .argument('<target-type>', 'Target edge type to merge into (receives all edges)')
    .option('-r, --reason <text>', 'Reason for merge (audit trail)')
    .option('-u, --user <email>', 'User performing the merge', 'cli-user')
    .action(async (deprecatedType, targetType, options) => {
      try {
        const client = createClientFromEnv();

        console.log('\n' + colors.status.warning('⚠️  Merging edge types...'));
        console.log(`  ${colors.ui.key('Deprecated:')} ${colors.getRelationshipColor(deprecatedType)(deprecatedType)}`);
        console.log(`  ${colors.ui.key('Target:')} ${colors.getRelationshipColor(targetType)(targetType)}`);
        if (options.reason) {
          console.log(`  ${colors.ui.key('Reason:')} ${colors.status.dim(options.reason)}`);
        }

        const result = await client.mergeEdgeTypes({
          deprecated_type: deprecatedType,
          target_type: targetType,
          performed_by: options.user,
          reason: options.reason
        });

        if (result.success) {
          console.log('\n' + colors.status.success('✓ Merge completed successfully'));
          console.log(`  ${colors.stats.label('Edges Updated:')} ${coloredCount(result.edges_updated)}`);
          console.log(`  ${colors.stats.label('Vocabulary Updated:')} ${coloredCount(result.vocab_updated)}`);
          console.log(`\n  ${colors.status.dim(result.message)}`);
        } else {
          console.error(colors.status.error('✗ Merge failed'));
        }
      } catch (error: any) {
        console.error(colors.status.error('✗ Failed to merge edge types'));
        console.error(colors.status.error(error.response?.data?.detail || error.message));
        process.exit(1);
      }
    });
}
