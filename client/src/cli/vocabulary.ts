/**
 * Vocabulary Management Commands (ADR-032)
 * Simplified structure with clear intent and purpose
 */

import { Command } from 'commander';
import { createClientFromEnv } from '../api/client';
import * as colors from './colors';
import { coloredCount, separator } from './colors';

export const vocabularyCommand = new Command('vocabulary')
  .alias('vocab')
  .description('Edge vocabulary management and consolidation (ADR-032)')
  .showHelpAfterError('(add --help for additional information)')
  .showSuggestionAfterError()
  .addCommand(
    new Command('status')
      .description('Show current vocabulary status and zone')
      .action(async () => {
        try {
          const client = createClientFromEnv();
          const status = await client.getVocabularyStatus();

          console.log('\n' + separator());
          console.log(colors.ui.title('📚 Vocabulary Status'));
          console.log(separator());

          // Zone indicator with color
          const zoneColors: Record<string, (text: string) => string> = {
            comfort: colors.status.success,
            watch: colors.status.warning,
            emergency: colors.status.error,
            block: colors.status.error
          };
          const zoneColor = zoneColors[status.zone] || colors.ui.value;
          const zoneIcons: Record<string, string> = {
            comfort: '✓',
            watch: '⚠',
            emergency: '🚨',
            block: '🛑'
          };
          const zoneIcon = zoneIcons[status.zone] || '';

          console.log('\n' + colors.stats.section('Current State'));
          console.log(`  ${colors.stats.label('Vocabulary Size:')} ${coloredCount(status.vocab_size)}`);
          console.log(`  ${colors.stats.label('Zone:')} ${zoneColor(`${zoneIcon} ${status.zone.toUpperCase()}`)}`);
          console.log(`  ${colors.stats.label('Aggressiveness:')} ${colors.ui.value((status.aggressiveness * 100).toFixed(1) + '%')}`);
          console.log(`  ${colors.stats.label('Profile:')} ${colors.ui.value(status.profile)}`);

          console.log('\n' + colors.stats.section('Thresholds'));
          console.log(`  ${colors.stats.label('Minimum:')} ${coloredCount(status.vocab_min)}`);
          console.log(`  ${colors.stats.label('Maximum:')} ${coloredCount(status.vocab_max)}`);
          console.log(`  ${colors.stats.label('Emergency:')} ${coloredCount(status.vocab_emergency)}`);

          console.log('\n' + colors.stats.section('Edge Types'));
          console.log(`  ${colors.stats.label('Builtin:')} ${coloredCount(status.builtin_types)}`);
          console.log(`  ${colors.stats.label('Custom:')} ${coloredCount(status.custom_types)}`);
          console.log(`  ${colors.stats.label('Categories:')} ${coloredCount(status.categories)}`);

          console.log('\n' + separator());
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to get vocabulary status'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('list')
      .description('List all edge types with statistics')
      .option('--inactive', 'Include inactive/deprecated types')
      .option('--no-builtin', 'Exclude builtin types')
      .action(async (options) => {
        try {
          const client = createClientFromEnv();
          const response = await client.listEdgeTypes(
            options.inactive || false,
            options.builtin !== false
          );

          console.log('\n' + separator());
          console.log(colors.ui.title('📋 Edge Types'));
          console.log(separator());

          console.log(`\n${colors.ui.key('Total:')} ${coloredCount(response.total)}`);
          console.log(`${colors.ui.key('Active:')} ${coloredCount(response.active)}`);
          console.log(`${colors.ui.key('Builtin:')} ${coloredCount(response.builtin)}`);
          console.log(`${colors.ui.key('Custom:')} ${coloredCount(response.custom)}`);

          if (response.types.length > 0) {
            console.log('\n' + separator(80, '─'));
            console.log(
              colors.status.dim(
                `${'TYPE'.padEnd(25)} ${'CATEGORY'.padEnd(15)} ${'EDGES'.padStart(8)} ${'STATUS'.padStart(10)}`
              )
            );
            console.log(separator(80, '─'));

            response.types.forEach((type: any) => {
              const relColor = colors.getRelationshipColor(type.relationship_type);
              const statusIcon = type.is_active ? '✓' : '✗';
              const statusColor = type.is_active ? colors.status.success : colors.status.dim;
              const builtinMark = type.is_builtin ? colors.status.dim(' [B]') : '';
              const edgeCount = type.edge_count !== null && type.edge_count !== undefined ? type.edge_count : 0;

              console.log(
                `${relColor(type.relationship_type.padEnd(25))} ` +
                `${colors.ui.value(type.category.padEnd(15))} ` +
                `${String(edgeCount).padStart(8)} ` +
                `${statusColor(statusIcon.padStart(10))}${builtinMark}`
              );
            });

            console.log(separator(80, '─'));
          }

          console.log();
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to list edge types'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('consolidate')
      .description('AI-assisted vocabulary consolidation workflow (AITL)')
      .option('-t, --target <size>', 'Target vocabulary size', '90')
      .option('--threshold <value>', 'Auto-execute threshold (0.0-1.0)', '0.90')
      .option('--dry-run', 'Evaluate candidates without executing merges')
      .option('--auto', 'Auto-execute high confidence merges (AITL mode)')
      .action(async (options) => {
        try {
          const client = createClientFromEnv();
          const targetSize = parseInt(options.target);
          const threshold = parseFloat(options.threshold);
          const dryRun = options.dryRun || false;
          const autoMode = options.auto || false;

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
            console.log(`\n${colors.ui.key('Mode:')} ${colors.status.dim('DRY RUN')} (validation only)`);
          } else if (autoMode) {
            console.log(`\n${colors.ui.key('Mode:')} ${colors.status.warning('AUTO')} (AITL - auto-execute)`);
          } else {
            console.log(`\n${colors.ui.key('Mode:')} ${colors.ui.value('DEFAULT')} (dry-run validation)`);
          }

          console.log(`${colors.ui.key('Target Size:')} ${coloredCount(targetSize)}`);
          console.log(`${colors.ui.key('Auto-Execute Threshold:')} ${colors.ui.value((threshold * 100).toFixed(0) + '%')}`);

          // Run consolidation
          console.log('\n' + colors.status.dim('Running LLM-based consolidation workflow...'));
          console.log(colors.status.dim('This may take a few minutes depending on vocabulary size.\n'));

          const result = await client.consolidateVocabulary({
            target_size: targetSize,
            batch_size: 1,
            auto_execute_threshold: threshold,
            dry_run: dryRun || !autoMode  // Dry-run if not in auto mode
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

          // Auto-executed merges
          if (result.auto_executed.length > 0) {
            console.log('\n' + colors.stats.section('Auto-Executed Merges'));
            console.log(separator(80, '─'));
            result.auto_executed.forEach((merge: any) => {
              const status = merge.error ? '✗' : '✓';
              const statusColor = merge.error ? colors.status.error : colors.status.success;
              console.log(`\n${statusColor(status)} ${merge.deprecated} → ${merge.target}`);
              console.log(`   ${colors.ui.key('Similarity:')} ${colors.ui.value((merge.similarity * 100).toFixed(1) + '%')}`);
              console.log(`   ${colors.ui.key('Reasoning:')} ${colors.status.dim(merge.reasoning)}`);
              if (merge.edges_updated !== undefined) {
                console.log(`   ${colors.ui.key('Edges Updated:')} ${coloredCount(merge.edges_updated)}`);
              }
              if (merge.error) {
                console.log(`   ${colors.status.error('ERROR:')} ${merge.error}`);
              }
            });
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
      })
  )
  .addCommand(
    new Command('merge')
      .description('Manually merge one edge type into another')
      .argument('<deprecated-type>', 'Edge type to deprecate')
      .argument('<target-type>', 'Target edge type to merge into')
      .option('-r, --reason <text>', 'Reason for merge')
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
      })
  )
  .addCommand(
    new Command('generate-embeddings')
      .description('Generate embeddings for vocabulary types')
      .option('--force', 'Regenerate ALL embeddings regardless of existing state')
      .option('--all', 'Process all active types (not just missing)')
      .action(async (options) => {
        try {
          const client = createClientFromEnv();

          // Determine mode
          const forceRegenerate = options.force || false;
          const onlyMissing = !options.all;

          let modeDescription = '';
          if (forceRegenerate) {
            modeDescription = colors.status.warning('ALL vocabulary types (force regenerate)');
          } else if (onlyMissing) {
            modeDescription = colors.ui.value('vocabulary types WITHOUT embeddings (default)');
          } else {
            modeDescription = colors.ui.value('all active vocabulary types');
          }

          console.log('\n' + separator());
          console.log(colors.ui.title('🔄 Generating Vocabulary Embeddings'));
          console.log(separator());
          console.log(`\n  ${colors.ui.key('Mode:')} ${modeDescription}`);
          console.log('\n' + colors.status.dim('  Generating embeddings via OpenAI API...'));

          const result = await client.generateVocabularyEmbeddings(
            forceRegenerate,
            onlyMissing
          );

          console.log('\n' + separator());
          if (result.success) {
            console.log(colors.status.success('✓ Embedding generation completed successfully'));
          } else {
            console.log(colors.status.warning('⚠️  Embedding generation completed with failures'));
          }
          console.log(`  ${colors.stats.label('Generated:')} ${coloredCount(result.generated)}`);
          console.log(`  ${colors.stats.label('Skipped:')} ${coloredCount(result.skipped)}`);
          if (result.failed > 0) {
            console.log(`  ${colors.stats.label('Failed:')} ${colors.status.error(result.failed.toString())}`);
          } else {
            console.log(`  ${colors.stats.label('Failed:')} ${coloredCount(result.failed)}`);
          }
          console.log('\n' + separator());

        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to generate embeddings'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  );
