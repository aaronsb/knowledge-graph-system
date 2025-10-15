/**
 * Vocabulary Management Commands (ADR-032)
 */

import { Command } from 'commander';
import { createClientFromEnv } from '../api/client';
import * as colors from './colors';
import { coloredCount, separator } from './colors';

export const vocabularyCommand = new Command('vocabulary')
  .alias('vocab')
  .description('Edge vocabulary management and optimization (ADR-032)')
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
    new Command('review')
      .description('Show vocabulary optimization recommendations (HITL workflow)')
      .action(async () => {
        try {
          const client = createClientFromEnv();
          const recommendations = await client.getVocabularyRecommendations();

          console.log('\n' + separator());
          console.log(colors.ui.title('🔍 Vocabulary Recommendations'));
          console.log(separator());

          // Context
          console.log('\n' + colors.stats.section('Context'));
          const zoneColors: Record<string, (text: string) => string> = {
            comfort: colors.status.success,
            watch: colors.status.warning,
            emergency: colors.status.error,
            block: colors.status.error
          };
          const zoneColor = zoneColors[recommendations.zone] || colors.ui.value;
          console.log(`  ${colors.stats.label('Vocabulary Size:')} ${coloredCount(recommendations.vocab_size)}`);
          console.log(`  ${colors.stats.label('Zone:')} ${zoneColor(recommendations.zone.toUpperCase())}`);
          console.log(`  ${colors.stats.label('Aggressiveness:')} ${colors.ui.value((recommendations.aggressiveness * 100).toFixed(1) + '%')}`);

          // Auto-execute recommendations
          if (recommendations.auto_execute.length > 0) {
            console.log('\n' + colors.stats.section('Auto-Execute (No Review Required)'));
            console.log(separator(80, '─'));
            recommendations.auto_execute.forEach((rec: any, idx: number) => {
              const actionColor = rec.action_type === 'merge' ? colors.status.warning : colors.status.dim;
              console.log(`\n${colors.stats.label(`[${idx + 1}]`)} ${actionColor(rec.action_type.toUpperCase())}`);
              console.log(`    ${colors.ui.key('Edge Type:')} ${colors.getRelationshipColor(rec.edge_type)(rec.edge_type)}`);
              if (rec.target_type) {
                console.log(`    ${colors.ui.key('Target:')} ${colors.getRelationshipColor(rec.target_type)(rec.target_type)}`);
              }
              console.log(`    ${colors.ui.key('Reasoning:')} ${colors.status.dim(rec.reasoning)}`);
              if (rec.metadata) {
                if (rec.metadata.similarity !== undefined) {
                  console.log(`    ${colors.ui.key('Similarity:')} ${colors.ui.value((rec.metadata.similarity * 100).toFixed(1) + '%')}`);
                }
                if (rec.metadata.value_score !== undefined) {
                  console.log(`    ${colors.ui.key('Value Score:')} ${colors.ui.value(rec.metadata.value_score.toFixed(2))}`);
                }
              }
            });
          }

          // Needs review recommendations
          if (recommendations.needs_review.length > 0) {
            console.log('\n' + colors.stats.section('Needs Review (Human Approval Required)'));
            console.log(separator(80, '─'));
            recommendations.needs_review.forEach((rec: any, idx: number) => {
              const actionColor = rec.action_type === 'merge' ? colors.status.warning : colors.status.dim;
              const reviewBadge = rec.review_level === 'human' ? colors.status.error(' [HUMAN]') : colors.status.warning(' [AI]');
              console.log(`\n${colors.stats.label(`[${idx + 1}]`)} ${actionColor(rec.action_type.toUpperCase())}${reviewBadge}`);
              console.log(`    ${colors.ui.key('Edge Type:')} ${colors.getRelationshipColor(rec.edge_type)(rec.edge_type)}`);
              if (rec.target_type) {
                console.log(`    ${colors.ui.key('Target:')} ${colors.getRelationshipColor(rec.target_type)(rec.target_type)}`);
              }
              console.log(`    ${colors.ui.key('Reasoning:')} ${colors.status.dim(rec.reasoning)}`);
              if (rec.metadata) {
                if (rec.metadata.similarity !== undefined) {
                  console.log(`    ${colors.ui.key('Similarity:')} ${colors.ui.value((rec.metadata.similarity * 100).toFixed(1) + '%')}`);
                }
                if (rec.metadata.value_score !== undefined) {
                  console.log(`    ${colors.ui.key('Value Score:')} ${colors.ui.value(rec.metadata.value_score.toFixed(2))}`);
                }
              }
            });
            console.log('\n' + colors.status.dim('  Use "kg vocab merge" to manually merge edge types'));
          }

          if (recommendations.auto_execute.length === 0 && recommendations.needs_review.length === 0) {
            console.log('\n' + colors.status.success('✓ No recommendations at this time'));
          } else {
            console.log('\n' + colors.status.dim(`  Generated: ${recommendations.generated_at}`));
          }

          console.log('\n' + separator());
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to get recommendations'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('config')
      .description('Show vocabulary configuration')
      .action(async () => {
        try {
          const client = createClientFromEnv();
          const config = await client.getVocabularyConfig();

          console.log('\n' + separator());
          console.log(colors.ui.title('⚙️  Vocabulary Configuration'));
          console.log(separator());

          console.log('\n' + colors.stats.section('Thresholds'));
          console.log(`  ${colors.stats.label('Minimum:')} ${coloredCount(config.vocab_min)}`);
          console.log(`  ${colors.stats.label('Maximum:')} ${coloredCount(config.vocab_max)}`);
          console.log(`  ${colors.stats.label('Emergency:')} ${coloredCount(config.vocab_emergency)}`);
          console.log(`  ${colors.stats.label('Category Min:')} ${coloredCount(config.category_min)}`);
          console.log(`  ${colors.stats.label('Category Max:')} ${coloredCount(config.category_max)}`);

          console.log('\n' + colors.stats.section('Pruning'));
          console.log(`  ${colors.stats.label('Mode:')} ${colors.ui.value(config.pruning_mode.toUpperCase())}`);
          console.log(`  ${colors.stats.label('Aggressiveness Profile:')} ${colors.ui.value(config.aggressiveness_profile)}`);
          console.log(`  ${colors.stats.label('Auto-Expand:')} ${config.auto_expand_enabled ? colors.status.success('✓ Enabled') : colors.status.dim('✗ Disabled')}`);

          console.log('\n' + colors.stats.section('Synonym Detection'));
          console.log(`  ${colors.stats.label('Strong Threshold:')} ${colors.ui.value((config.synonym_threshold_strong * 100).toFixed(0) + '%')}`);
          console.log(`  ${colors.stats.label('Moderate Threshold:')} ${colors.ui.value((config.synonym_threshold_moderate * 100).toFixed(0) + '%')}`);

          console.log('\n' + colors.stats.section('Value Scoring'));
          console.log(`  ${colors.stats.label('Low Value Threshold:')} ${colors.ui.value(config.low_value_threshold.toFixed(1))}`);

          console.log('\n' + colors.stats.section('Models'));
          console.log(`  ${colors.stats.label('Embedding Model:')} ${colors.ui.value(config.embedding_model)}`);

          console.log('\n' + separator());
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to get vocabulary config'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('analysis')
      .description('Detailed vocabulary analysis with value scores and synonyms')
      .action(async () => {
        try {
          const client = createClientFromEnv();
          const analysis = await client.getVocabularyAnalysis();

          console.log('\n' + separator());
          console.log(colors.ui.title('📊 Vocabulary Analysis'));
          console.log(separator());

          // Context
          console.log('\n' + colors.stats.section('Context'));
          const zoneColors: Record<string, (text: string) => string> = {
            comfort: colors.status.success,
            watch: colors.status.warning,
            emergency: colors.status.error,
            block: colors.status.error
          };
          const zoneColor = zoneColors[analysis.zone] || colors.ui.value;
          console.log(`  ${colors.stats.label('Vocabulary Size:')} ${coloredCount(analysis.vocab_size)} of ${coloredCount(analysis.vocab_max)}`);
          console.log(`  ${colors.stats.label('Zone:')} ${zoneColor(analysis.zone.toUpperCase())}`);
          console.log(`  ${colors.stats.label('Aggressiveness:')} ${colors.ui.value((analysis.aggressiveness * 100).toFixed(1) + '%')}`);

          // Category distribution
          if (Object.keys(analysis.category_distribution).length > 0) {
            console.log('\n' + colors.stats.section('Category Distribution'));
            Object.entries(analysis.category_distribution)
              .sort(([, a]: any, [, b]: any) => b - a)
              .forEach(([category, count]: any) => {
                console.log(`  ${colors.stats.label(category + ':')} ${coloredCount(count)}`);
              });
          }

          // Synonym candidates
          if (analysis.synonym_candidates.length > 0) {
            console.log('\n' + colors.stats.section('Synonym Candidates'));
            console.log(separator(80, '─'));
            console.log(
              colors.status.dim(
                `${'TYPE 1'.padEnd(20)} ${'TYPE 2'.padEnd(20)} ${'SIMILARITY'.padStart(12)} ${'STRENGTH'.padStart(12)}`
              )
            );
            console.log(separator(80, '─'));

            analysis.synonym_candidates
              .sort((a: any, b: any) => b.similarity - a.similarity)
              .slice(0, 10)  // Top 10
              .forEach((candidate: any) => {
                const simColor = candidate.similarity >= 0.90
                  ? colors.status.error
                  : candidate.similarity >= 0.70
                    ? colors.status.warning
                    : colors.status.dim;
                const strengthBadge = candidate.is_strong_match
                  ? colors.status.error('[STRONG]')
                  : colors.status.dim('[' + candidate.strength.toUpperCase() + ']');

                console.log(
                  `${colors.getRelationshipColor(candidate.type1)(candidate.type1.padEnd(20))} ` +
                  `${colors.getRelationshipColor(candidate.type2)(candidate.type2.padEnd(20))} ` +
                  `${simColor((candidate.similarity * 100).toFixed(1).padStart(11) + '%')} ` +
                  `${strengthBadge.padStart(12)}`
                );
              });

            if (analysis.synonym_candidates.length > 10) {
              console.log(separator(80, '─'));
              console.log(colors.status.dim(`  ... and ${analysis.synonym_candidates.length - 10} more`));
            }
          }

          // Low value types
          if (analysis.low_value_types.length > 0) {
            console.log('\n' + colors.stats.section('Low Value Types (Pruning Candidates)'));
            console.log(separator(80, '─'));
            console.log(
              colors.status.dim(
                `${'TYPE'.padEnd(25)} ${'EDGES'.padStart(8)} ${'TRAVERSAL'.padStart(12)} ${'SCORE'.padStart(10)}`
              )
            );
            console.log(separator(80, '─'));

            analysis.low_value_types
              .sort((a: any, b: any) => a.value_score - b.value_score)
              .slice(0, 10)  // Bottom 10
              .forEach((type: any) => {
                const scoreColor = type.value_score < 0.5 ? colors.status.error : colors.status.warning;
                console.log(
                  `${colors.getRelationshipColor(type.relationship_type)(type.relationship_type.padEnd(25))} ` +
                  `${coloredCount(type.edge_count.toString().padStart(8))} ` +
                  `${colors.ui.value(type.avg_traversal.toFixed(2).padStart(12))} ` +
                  `${scoreColor(type.value_score.toFixed(2).padStart(10))}`
                );
              });

            if (analysis.low_value_types.length > 10) {
              console.log(separator(80, '─'));
              console.log(colors.status.dim(`  ... and ${analysis.low_value_types.length - 10} more`));
            }
          }

          console.log('\n' + separator());
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to get vocabulary analysis'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('merge')
      .description('Merge one edge type into another')
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
  );
