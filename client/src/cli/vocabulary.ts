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
  .description('Edge vocabulary management and consolidation. Manages relationship types between concepts including builtin types (30 predefined), custom types (LLM-extracted from documents), categories (semantic groupings), consolidation (AI-assisted merging via AITL - ADR-032), and auto-categorization (probabilistic via embeddings - ADR-047). Features zone-based management (GREEN/WATCH/DANGER/EMERGENCY) and LLM-determined relationship direction (ADR-049).')
  .showHelpAfterError('(add --help for additional information)')
  .showSuggestionAfterError()
  .addCommand(
    new Command('status')
      .description('Show current vocabulary status including size, zone (GREEN/WATCH/DANGER/EMERGENCY per ADR-032), aggressiveness (growth above minimum), and thresholds. Shows breakdown of builtin types, custom types, and categories. Use this to monitor vocabulary health, check zone before consolidation, track growth over time, and trigger consolidation workflows when needed.')
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
      .description('List all edge types with statistics, categories, and confidence scores (ADR-047). Shows TYPE (colored by semantic), CATEGORY (composition, causation, logical, etc.), CONF (confidence score with ⚠ for ambiguous), EDGES (usage count), STATUS (active ✓), and [B] flag for builtin types. Use this for vocabulary overview, finding consolidation candidates, reviewing auto-categorization accuracy, identifying unused types, and auditing quality.')
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
            console.log('\n' + separator(95, '─'));
            console.log(
              colors.status.dim(
                `${'TYPE'.padEnd(25)} ${'CATEGORY'.padEnd(15)} ${'CONF'.padStart(6)} ${'EDGES'.padStart(8)} ${'STATUS'.padStart(10)}`
              )
            );
            console.log(separator(95, '─'));

            response.types.forEach((type: any) => {
              const relColor = colors.getRelationshipColor(type.relationship_type);
              const statusIcon = type.is_active ? '✓' : '✗';
              const statusColor = type.is_active ? colors.status.success : colors.status.dim;
              const builtinMark = type.is_builtin ? colors.status.dim(' [B]') : '';
              const edgeCount = type.edge_count !== null && type.edge_count !== undefined ? type.edge_count : 0;

              // ADR-047: Show confidence if available
              let confDisplay = '';
              if (type.category_confidence !== null && type.category_confidence !== undefined) {
                const confPercent = (type.category_confidence * 100).toFixed(0);
                const confNum = type.category_confidence;
                let confColor = colors.status.dim;
                if (confNum >= 0.70) confColor = colors.status.success;
                else if (confNum >= 0.50) confColor = colors.status.warning;
                else confColor = colors.status.error;

                const ambiguous = type.category_ambiguous ? colors.status.warning('⚠') : '';
                confDisplay = confColor(confPercent.padStart(3) + '%') + ambiguous;
              } else if (type.category_source === 'builtin') {
                confDisplay = colors.status.dim('  --  ');
              } else {
                confDisplay = colors.status.dim('  --  ');
              }

              console.log(
                `${relColor(type.relationship_type.padEnd(25))} ` +
                `${colors.ui.value(type.category.padEnd(15))} ` +
                `${confDisplay.padStart(6)} ` +
                `${String(edgeCount).padStart(8)} ` +
                `${statusColor(statusIcon.padStart(10))}${builtinMark}`
              );
            });

            console.log(separator(95, '─'));
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
      .description('AI-assisted vocabulary consolidation workflow (AITL - AI-in-the-loop, ADR-032). Analyzes vocabulary via embeddings, identifies similar pairs above threshold, presents merge recommendations with confidence, and executes or prompts based on mode. Workflow: 1) analyze vocabulary, 2) identify candidates, 3) present recommendations, 4) execute or prompt, 5) apply merges (deprecate source, redirect edges), 6) iterate until target reached. Modes: interactive (default, prompts each), dry-run (shows candidates without executing), AITL auto (auto-executes high confidence). Threshold guidelines: 0.95+ very conservative, 0.90-0.95 balanced AITL, 0.85-0.90 aggressive requires review, <0.85 very aggressive manual review.')
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
      .description('Manually merge one edge type into another for consolidation or correction. Validates both types exist, redirects all edges from deprecated type to target type, marks deprecated type as inactive, records audit trail (reason, user, timestamp), and preserves edge provenance. This is a non-destructive, atomic operation useful for manual consolidation, fixing misnamed types from extraction, bulk scripted operations, and targeted category cleanup. Safety: edges preserved, atomic transaction, audit trail for compliance, can be reviewed in inactive types list.')
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
      })
  )
  .addCommand(
    new Command('generate-embeddings')
      .description('Generate vector embeddings for vocabulary types (required for consolidation and categorization). Identifies types without embeddings, generates embeddings using configured embedding model, stores embeddings for similarity comparison, and enables consolidation and auto-categorization. Use after fresh install (bootstrap vocabulary embeddings), after ingestion introduces new custom types, when switching embedding models (regenerate), or for inconsistency fixes (force regeneration if corrupted). Performance: ~100-200ms per embedding (OpenAI), ~20-50ms per embedding (local models), parallel generation (batches of 10).')
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

          // Fetch active embedding config to show correct provider
          const embeddingConfig = await client.getEmbeddingConfig();
          const providerName = embeddingConfig.provider === 'openai' ? 'OpenAI' :
                               embeddingConfig.provider === 'local' ? 'local embeddings' :
                               embeddingConfig.provider;
          const modelInfo = embeddingConfig.model ? ` (${embeddingConfig.model})` : '';
          console.log('\n' + colors.status.dim(`  Generating embeddings via ${providerName}${modelInfo}...`));

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
  )
  .addCommand(
    new Command('category-scores')
      .description('Show category similarity scores for a specific relationship type (ADR-047). Displays assigned category, confidence score (calculated as max_score/second_max_score * 100), ambiguous flag (set when runner-up within 20% of winner), runner-up category if ambiguous, and similarity to all category seeds (0-100%) sorted by similarity with visual bar chart. Use this to verify auto-categorization makes sense, debug low confidence assignments, understand why confidence is low, resolve ambiguity between close categories, and audit all types for misassignments.')
      .argument('<type>', 'Relationship type to analyze (e.g., CAUSES, ENABLES)')
      .action(async (relationshipType: string) => {
        try {
          const client = createClientFromEnv();
          const result = await client.getCategoryScores(relationshipType);

          console.log('\n' + separator());
          console.log(colors.ui.title(`📊 Category Scores: ${colors.getRelationshipColor(relationshipType)(relationshipType)}`));
          console.log(separator());

          console.log(`\n${colors.stats.section('Assignment')}`);
          console.log(`  ${colors.stats.label('Category:')} ${colors.ui.value(result.category)}`);

          // Confidence with color coding
          const confPercent = (result.confidence * 100).toFixed(0);
          let confColor = colors.status.dim;
          if (result.confidence >= 0.70) confColor = colors.status.success;
          else if (result.confidence >= 0.50) confColor = colors.status.warning;
          else confColor = colors.status.error;

          console.log(`  ${colors.stats.label('Confidence:')} ${confColor(confPercent + '%')}`);
          console.log(`  ${colors.stats.label('Ambiguous:')} ${result.ambiguous ? colors.status.warning('Yes') : colors.status.success('No')}`);

          if (result.ambiguous && result.runner_up_category) {
            const runnerUpPercent = (result.runner_up_score * 100).toFixed(0);
            console.log(`  ${colors.stats.label('Runner-up:')} ${colors.ui.value(result.runner_up_category)} (${runnerUpPercent}%)`);
          }

          console.log(`\n${colors.stats.section('Similarity to Category Seeds')}`);

          // Sort categories by score
          const sortedScores = Object.entries(result.scores)
            .sort((a: any, b: any) => b[1] - a[1]);

          for (const [category, score] of sortedScores) {
            const scoreNum = score as number;
            const percent = (scoreNum * 100).toFixed(0).padStart(3);
            const barLength = Math.round(scoreNum * 20);
            const bar = '█'.repeat(barLength);

            // Highlight primary category
            const catDisplay = category === result.category
              ? colors.status.success(category.padEnd(15))
              : colors.ui.value(category.padEnd(15));

            console.log(`  ${catDisplay} ${percent}%  ${bar}`);
          }

          console.log('\n' + separator());

        } catch (error: any) {
          if (error.response?.status === 404) {
            console.error(colors.status.error(`✗ Relationship type not found: ${relationshipType}`));
            console.error(colors.status.dim('  Make sure the type exists and has an embedding'));
          } else {
            console.error(colors.status.error('✗ Failed to get category scores'));
            console.error(colors.status.error(error.response?.data?.detail || error.message));
          }
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('refresh-categories')
      .description('Refresh category assignments for vocabulary types using latest embeddings (ADR-047). Identifies types needing category refresh, recalculates similarity to all category seeds, assigns best-matching category, updates confidence scores, and flags ambiguous assignments. Use after embedding model changes (recalculate with new model), category definition updates (refresh after changing seed terms), periodic maintenance (quarterly review), or quality improvement (re-evaluate low confidence). This is a non-destructive operation (doesn\'t affect edges), preserves manual assignments, and records audit trail per type.')
      .option('--computed-only', 'Refresh only types with category_source=computed (excludes manual assignments)')
      .action(async (options) => {
        try {
          const client = createClientFromEnv();
          const onlyComputed = options.computedOnly || false;

          console.log('\n' + separator());
          console.log(colors.ui.title('🔄 Refreshing Category Assignments'));
          console.log(separator());

          const modeDesc = onlyComputed
            ? 'computed categories only (category_source=computed)'
            : 'all active types (default)';
          console.log(`\n  ${colors.ui.key('Mode:')} ${colors.ui.value(modeDesc)}`);
          console.log(colors.status.dim('\n  Computing category scores via embedding similarity...'));

          const result = await client.refreshCategories(onlyComputed);

          console.log('\n' + separator());
          console.log(colors.status.success('✓ Category refresh completed'));
          console.log(`  ${colors.stats.label('Refreshed:')} ${coloredCount(result.refreshed_count)}`);
          console.log(`  ${colors.stats.label('Skipped:')} ${coloredCount(result.skipped_count)}`);

          if (result.failed_count > 0) {
            console.log(`  ${colors.stats.label('Failed:')} ${colors.status.error(result.failed_count.toString())}`);
          } else {
            console.log(`  ${colors.stats.label('Failed:')} ${coloredCount(result.failed_count)}`);
          }

          // Show some examples if any were refreshed
          if (result.assignments && result.assignments.length > 0) {
            const sampleSize = Math.min(5, result.assignments.length);
            console.log(`\n${colors.stats.section(`Sample Results (${sampleSize} of ${result.assignments.length})`)}`);

            for (let i = 0; i < sampleSize; i++) {
              const assignment = result.assignments[i];
              const confPercent = (assignment.confidence * 100).toFixed(0);
              const ambiguous = assignment.ambiguous ? colors.status.warning(' ⚠') : '';
              console.log(
                `  ${colors.getRelationshipColor(assignment.relationship_type)(assignment.relationship_type.padEnd(25))} → ` +
                `${colors.ui.value(assignment.category.padEnd(12))} (${confPercent}%)${ambiguous}`
              );
            }
          }

          console.log('\n' + separator());

        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to refresh categories'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  );
