/**
 * Vocabulary Management Commands (ADR-032)
 * Simplified structure with clear intent and purpose
 */

import { Command } from 'commander';
import { createClientFromEnv } from '../api/client';
import * as colors from './colors';
import { coloredCount, separator } from './colors';
import { plotBezierCurve, formatCurveSummary, type CurveMarker, type ZoneLabel } from './curve-viz';
import { Table } from '../lib/table';
import { setCommandHelp } from './help-formatter';

export const vocabularyCommand = setCommandHelp(
  new Command('vocabulary'),
  'Vocabulary management and consolidation',
  'Edge vocabulary management and consolidation. Manages relationship types between concepts including builtin types (30 predefined), custom types (LLM-extracted from documents), categories (semantic groupings), consolidation (AI-assisted merging via AITL - ADR-032), and auto-categorization (probabilistic via embeddings - ADR-047). Features zone-based management (GREEN/WATCH/DANGER/EMERGENCY) and LLM-determined relationship direction (ADR-049).'
)
  .alias('vocab')
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

          // Fetch and display aggressiveness curve
          try {
            const profile = await client.getAggressivenessProfile(status.profile);

            console.log('\n' + colors.stats.section('Aggressiveness Curve'));
            console.log(`  ${colors.stats.label('Profile:')} ${colors.ui.value(formatCurveSummary(profile))}`);
            if (profile.description) {
              console.log(`  ${colors.status.dim(profile.description)}`);
            }

            // Calculate normalized position and create markers
            const range = status.vocab_emergency - status.vocab_min;
            // Detect terminal width and calculate optimal chart width
            const terminalWidth = process.stdout.columns || 80;
            // Reserve space for Y-axis labels (6 chars) + margins (4 chars)
            const chartWidth = Math.min(Math.max(40, terminalWidth - 10), 120);

            const currentNormalized = Math.max(0, Math.min(1, (status.vocab_size - status.vocab_min) / range));
            const maxNormalized = Math.max(0, Math.min(1, (status.vocab_max - status.vocab_min) / range));

            const markers: CurveMarker[] = [
              { position: 0, char: '│', label: `${status.vocab_min}` },
              { position: maxNormalized, char: '│', label: `MAX:${status.vocab_max}` },
              {
                position: currentNormalized,
                char: '▼',
                label: `YOU:${status.vocab_size}`,
                drawVerticalLine: true,
                color: zoneColor
              },
              { position: 1, char: '│', label: `${status.vocab_emergency}` }
            ];

            // Calculate zone widths based on dynamic chart width
            const zoneWidth = Math.floor(chartWidth / 3);
            const zones: ZoneLabel[] = [
              { label: 'GREEN', width: zoneWidth, color: colors.status.success },
              { label: 'WATCH', width: zoneWidth, color: colors.status.warning },
              { label: 'DANGER/EMERGENCY', width: zoneWidth, color: colors.status.error }
            ];

            console.log('\n' + colors.status.dim('Y-axis: Consolidation aggressiveness | X-axis: Vocabulary size'));
            console.log(plotBezierCurve(
              profile.control_x1,
              profile.control_y1,
              profile.control_x2,
              profile.control_y2,
              { markers, zones, points: chartWidth, height: 12 }
            ));
          } catch (error: any) {
            console.log('\n' + colors.status.dim('  (Unable to load aggressiveness curve)'));
          }

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
      .description('List all edge types with statistics, categories, and confidence scores (ADR-047). Shows TYPE (colored by semantic), CATEGORY (composition, causation, logical, etc.), CONF (confidence score with ⚠ for ambiguous), GROUNDING (epistemic status avg_grounding), EDGES (usage count), STATUS (active ✓), and [B] flag for builtin types. Use this for vocabulary overview, finding consolidation candidates, reviewing auto-categorization accuracy, identifying unused types, and auditing quality.')
      .option('--inactive', 'Include inactive/deprecated types')
      .option('--no-builtin', 'Exclude builtin types')
      .option('--sort <fields>', 'Sort by comma-separated fields: edges, type, conf, grounding, category, status (case-insensitive). Default: edges (descending)')
      .action(async (options) => {
        try {
          const client = createClientFromEnv();
          const response = await client.listEdgeTypes(
            options.inactive || false,
            options.builtin !== false
          );

          // Sort types based on --sort option (default: edges descending)
          if (response.types.length > 0) {
            const sortFields = options.sort
              ? options.sort.toLowerCase().split(',').map((f: string) => f.trim())
              : ['edges'];

            response.types.sort((a: any, b: any) => {
              for (const field of sortFields) {
                let aVal: any, bVal: any;

                switch (field) {
                  case 'edges':
                    aVal = a.edge_count ?? 0;
                    bVal = b.edge_count ?? 0;
                    // Descending for edges
                    if (aVal !== bVal) return bVal - aVal;
                    break;
                  case 'type':
                    aVal = a.relationship_type?.toLowerCase() ?? '';
                    bVal = b.relationship_type?.toLowerCase() ?? '';
                    if (aVal !== bVal) return aVal.localeCompare(bVal);
                    break;
                  case 'conf':
                  case 'confidence':
                    aVal = a.category_confidence ?? -1;
                    bVal = b.category_confidence ?? -1;
                    // Descending for confidence
                    if (aVal !== bVal) return bVal - aVal;
                    break;
                  case 'grounding':
                    aVal = a.avg_grounding ?? -999;
                    bVal = b.avg_grounding ?? -999;
                    // Descending for grounding
                    if (aVal !== bVal) return bVal - aVal;
                    break;
                  case 'category':
                    aVal = a.category?.toLowerCase() ?? '';
                    bVal = b.category?.toLowerCase() ?? '';
                    if (aVal !== bVal) return aVal.localeCompare(bVal);
                    break;
                  case 'status':
                    aVal = a.epistemic_status?.toLowerCase() ?? 'zzz';
                    bVal = b.epistemic_status?.toLowerCase() ?? 'zzz';
                    if (aVal !== bVal) return aVal.localeCompare(bVal);
                    break;
                  default:
                    // Unknown field, skip
                    break;
                }
              }
              return 0;
            });
          }

          console.log('\n' + separator());
          console.log(colors.ui.title('📋 Edge Types'));
          console.log(separator());

          console.log(`\n${colors.ui.key('Total:')} ${coloredCount(response.total)}`);
          console.log(`${colors.ui.key('Active:')} ${coloredCount(response.active)}`);
          console.log(`${colors.ui.key('Builtin:')} ${coloredCount(response.builtin)}`);
          console.log(`${colors.ui.key('Custom:')} ${coloredCount(response.custom)}`);

          if (response.types.length > 0) {
            console.log('\n' + separator(105, '─'));
            console.log(
              colors.status.dim(
                `${'TYPE'.padEnd(25)} ${'CATEGORY'.padEnd(15)} ${'CONF'.padStart(6)} ${'GROUNDING'.padStart(10)} ${'EDGES'.padStart(8)} ${'STATUS'.padStart(10)}`
              )
            );
            console.log(separator(105, '─'));

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

              // ADR-065: Show grounding if available
              let groundingDisplay = '';
              if (type.avg_grounding !== null && type.avg_grounding !== undefined) {
                const groundingVal = type.avg_grounding;
                let groundingColor = colors.status.dim;

                // Color based on grounding value
                if (groundingVal > 0.8) groundingColor = colors.status.success;
                else if (groundingVal >= 0.15) groundingColor = colors.status.warning;
                else if (groundingVal >= 0.0) groundingColor = colors.ui.value;
                else if (groundingVal >= -0.5) groundingColor = colors.status.dim;
                else groundingColor = colors.status.error;

                groundingDisplay = groundingColor(groundingVal.toFixed(3).padStart(6));
              } else {
                groundingDisplay = colors.status.dim('    --');
              }

              console.log(
                `${relColor(type.relationship_type.padEnd(25))} ` +
                `${colors.ui.value(type.category.padEnd(15))} ` +
                `${confDisplay.padStart(6)} ` +
                `${groundingDisplay.padStart(10)} ` +
                `${String(edgeCount).padStart(8)} ` +
                `${statusColor(statusIcon.padStart(10))}${builtinMark}`
              );
            });

            console.log(separator(105, '─'));
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
      .description('AI-assisted vocabulary consolidation workflow (AITL - AI-in-the-loop, ADR-032). Analyzes vocabulary via embeddings, identifies similar pairs above threshold, presents merge recommendations with confidence, and executes or prompts based on mode. Workflow: 1) analyze vocabulary, 2) identify candidates, 3) present recommendations, 4) execute or prompt, 5) apply merges (deprecate source, redirect edges), 6) prune unused types (default). Modes: interactive (default, prompts each), dry-run (shows candidates without executing), AITL auto (auto-executes high confidence). Threshold guidelines: 0.95+ very conservative, 0.90-0.95 balanced AITL, 0.85-0.90 aggressive requires review, <0.85 very aggressive manual review.')
      .option('-t, --target <size>', 'Target vocabulary size', '90')
      .option('--threshold <value>', 'Auto-execute threshold (0.0-1.0)', '0.90')
      .option('--dry-run', 'Evaluate candidates without executing merges')
      .option('--auto', 'Auto-execute high confidence merges (AITL mode)')
      .option('--no-prune-unused', 'Skip pruning vocabulary types with 0 uses (default: prune enabled)')
      .action(async (options) => {
        try {
          const client = createClientFromEnv();
          const targetSize = parseInt(options.target);
          const threshold = parseFloat(options.threshold);
          const dryRun = options.dryRun || false;
          const autoMode = options.auto || false;
          const pruneUnused = options.pruneUnused !== false;  // Default: true (prune enabled)

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
          console.log(`${colors.ui.key('Prune Unused:')} ${pruneUnused ? colors.status.success('Enabled') : colors.status.dim('Disabled')}`);

          // Run consolidation
          console.log('\n' + colors.status.dim('Running LLM-based consolidation workflow...'));
          console.log(colors.status.dim('This may take a few minutes depending on vocabulary size.\n'));

          const result = await client.consolidateVocabulary({
            target_size: targetSize,
            batch_size: 1,
            auto_execute_threshold: threshold,
            dry_run: dryRun || !autoMode,  // Dry-run if not in auto mode
            prune_unused: pruneUnused  // Pass prune flag
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
      .description('Refresh category assignments for vocabulary types using latest embeddings (ADR-047, ADR-053). As of ADR-053, new edge types are automatically categorized during ingestion, so this command is primarily needed when category seeds change. Use when category seed definitions are updated (seeds currently defined in code, future: database-configurable), after embedding model changes, or for migrating pre-ADR-053 uncategorized types. This is a non-destructive operation (doesn\'t affect edges), preserves manual assignments, and records audit trail per type.')
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
  )
  .addCommand(
    new Command('similar')
      .description('Find similar edge types via embedding similarity (ADR-053). Shows types with highest cosine similarity - useful for synonym detection and consolidation. Use --limit to control results (1-100, default 10). Similar types with high similarity (>0.90) are strong merge candidates for vocabulary consolidation (ADR-052).')
      .argument('<type>', 'Relationship type to analyze (e.g., IMPLIES)')
      .option('--limit <n>', 'Number of results to return (1-100)', '10')
      .action(async (type: string, options: { limit: string }) => {
        try {
          const client = createClientFromEnv();
          const limit = parseInt(options.limit, 10);

          if (isNaN(limit) || limit < 1 || limit > 100) {
            console.error(colors.status.error('✗ Limit must be between 1 and 100'));
            process.exit(1);
          }

          const data = await client.getSimilarTypes(type, limit, false);

          console.log('\n' + separator());
          console.log(colors.ui.title(`📊 Most Similar to ${type}`));
          console.log(separator());
          console.log();
          console.log(`${colors.ui.key('Type:')} ${type}`);
          console.log(`${colors.ui.key('Category:')} ${data.category}`);
          console.log(`${colors.ui.key('Compared:')} ${data.total_compared} types`);
          console.log();
          console.log(colors.status.dim('──────────────────────────────────────────────────────────────'));
          console.log(colors.status.dim('TYPE                      SIMILARITY  CATEGORY          USAGE'));
          console.log(colors.status.dim('──────────────────────────────────────────────────────────────'));

          for (const similar of data.similar_types) {
            const typeColor = colors.concept.label;
            const simScore = (similar.similarity * 100).toFixed(0) + '%';
            const simColor = similar.similarity >= 0.90 ? colors.status.success :
                           similar.similarity >= 0.75 ? colors.status.warning :
                           colors.status.dim;

            console.log(
              `${typeColor(similar.relationship_type.padEnd(25))} ` +
              `${simColor(simScore.padEnd(11))} ` +
              `${similar.category.padEnd(17)} ` +
              `${colors.status.dim(similar.usage_count.toString())}`
            );
          }

          console.log(colors.status.dim('──────────────────────────────────────────────────────────────'));
          console.log();
          console.log(colors.status.dim('💡 Similarity ≥90%: Strong merge candidates (ADR-052)'));
          console.log(colors.status.dim('   Similarity 75-90%: Review for potential consolidation'));

        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to find similar types'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('opposite')
      .description('Find opposite (least similar) edge types via embedding similarity (ADR-053). Shows types with lowest cosine similarity - useful for understanding semantic range and antonyms. Use --limit to control results (1-100, default 5).')
      .argument('<type>', 'Relationship type to analyze (e.g., IMPLIES)')
      .option('--limit <n>', 'Number of results to return (1-100)', '5')
      .action(async (type: string, options: { limit: string }) => {
        try {
          const client = createClientFromEnv();
          const limit = parseInt(options.limit, 10);

          if (isNaN(limit) || limit < 1 || limit > 100) {
            console.error(colors.status.error('✗ Limit must be between 1 and 100'));
            process.exit(1);
          }

          const data = await client.getSimilarTypes(type, limit, true);  // reverse=true for opposites

          console.log('\n' + separator());
          console.log(colors.ui.title(`📊 Least Similar to ${type} (Opposites)`));
          console.log(separator());
          console.log();
          console.log(`${colors.ui.key('Type:')} ${type}`);
          console.log(`${colors.ui.key('Category:')} ${data.category}`);
          console.log(`${colors.ui.key('Compared:')} ${data.total_compared} types`);
          console.log();
          console.log(colors.status.dim('──────────────────────────────────────────────────────────────'));
          console.log(colors.status.dim('TYPE                      SIMILARITY  CATEGORY          USAGE'));
          console.log(colors.status.dim('──────────────────────────────────────────────────────────────'));

          for (const similar of data.similar_types) {
            const typeColor = colors.concept.label;
            const simScore = (similar.similarity * 100).toFixed(0) + '%';

            console.log(
              `${typeColor(similar.relationship_type.padEnd(25))} ` +
              `${colors.status.dim(simScore.padEnd(11))} ` +
              `${similar.category.padEnd(17)} ` +
              `${colors.status.dim(similar.usage_count.toString())}`
            );
          }

          console.log(colors.status.dim('──────────────────────────────────────────────────────────────'));

        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to find opposite types'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('analyze')
      .description('Detailed analysis of vocabulary type for quality assurance (ADR-053). Shows category fit, similar types in same/other categories, and detects potential miscategorization. Use this to verify auto-categorization accuracy and identify types that may need reclassification.')
      .argument('<type>', 'Relationship type to analyze (e.g., STORES)')
      .action(async (type: string) => {
        try {
          const client = createClientFromEnv();
          const data = await client.analyzeVocabularyType(type);

          console.log('\n' + separator(64, '═'));
          console.log(colors.ui.title(`🔍 Vocabulary Analysis: ${type}`));
          console.log(separator(64, '═'));
          console.log();
          console.log(`${colors.ui.key('Category:')} ${data.category}`);
          console.log(`${colors.ui.key('Category Fit:')} ${(data.category_fit * 100).toFixed(0)}%`);

          if (data.potential_miscategorization) {
            console.log();
            console.log(colors.status.warning('⚠️  Potential Miscategorization Detected'));
            console.log(colors.status.dim(`   ${data.suggestion}`));
          } else {
            console.log(colors.status.success('\n✓ Category assignment looks good'));
          }

          console.log();
          console.log(colors.status.dim('────────────────────────────────────────────────────────────────'));
          console.log(colors.ui.header('Most Similar in Same Category:'));
          console.log(colors.status.dim('────────────────────────────────────────────────────────────────'));

          if (data.most_similar_same_category.length > 0) {
            for (const similar of data.most_similar_same_category) {
              const simScore = (similar.similarity * 100).toFixed(0) + '%';
              console.log(
                `  ${colors.concept.label(similar.relationship_type.padEnd(25))} ` +
                `${colors.status.success(simScore.padEnd(6))} ` +
                `${colors.status.dim(`(${similar.usage_count} uses)`)}`
              );
            }
          } else {
            console.log(colors.status.dim('  No other types in this category'));
          }

          console.log();
          console.log(colors.status.dim('────────────────────────────────────────────────────────────────'));
          console.log(colors.ui.header('Most Similar in Other Categories:'));
          console.log(colors.status.dim('────────────────────────────────────────────────────────────────'));

          if (data.most_similar_other_categories.length > 0) {
            for (const similar of data.most_similar_other_categories) {
              const simScore = (similar.similarity * 100).toFixed(0) + '%';
              console.log(
                `  ${colors.concept.label(similar.relationship_type.padEnd(25))} ` +
                `${colors.status.warning(simScore.padEnd(6))} ` +
                `${colors.status.dim(similar.category.padEnd(15))} ` +
                `${colors.status.dim(`(${similar.usage_count} uses)`)}`
              );
            }
          } else {
            console.log(colors.status.dim('  No similar types in other categories'));
          }

          console.log(separator(64, '═'));

        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to analyze type'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('config')
      .description('Show or update vocabulary configuration. No args: display config table. With args: update properties directly using database key names (e.g., "kg vocab config vocab_max 275 vocab_emergency 350"). Property names shown in config table.')
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
            const { getConfig } = require('../lib/config');
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

            // Fetch and display updated config (fall through to display code)

          } catch (error: any) {
            console.error(colors.status.error('✗ Failed to update vocabulary configuration'));
            if (error.response?.data?.detail) {
              console.error(colors.status.error(JSON.stringify(error.response.data.detail, null, 2)));
            } else {
              console.error(colors.status.error(error.message || String(error)));
            }
            process.exit(1);
          }
          // Fall through to display code below
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
          console.log(colors.status.dim('Use `kg vocab config <property> <value>` to update (e.g., `kg vocab config vocab_max 275`):\n'));

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
      })
  )
  .addCommand(
    new Command('config-update')
      .description('[DEPRECATED: Use `kg vocab config <property> <value>` instead] Update vocabulary configuration settings. Supports updating multiple properties at once including thresholds (min, max, emergency), pruning mode (naive, hitl, aitl), aggressiveness profile, synonym thresholds, auto-expand setting, and consolidation threshold. Changes are persisted to database and take effect immediately. Use this for runtime threshold adjustments, switching pruning modes, changing aggressiveness profiles, tuning synonym detection, and enabling/disabling auto-expand.')
      .option('--min <n>', 'Minimum vocabulary size (e.g., 30)', parseInt)
      .option('--max <n>', 'Maximum vocabulary size (e.g., 225-275)', parseInt)
      .option('--emergency <n>', 'Emergency threshold (e.g., 300-400)', parseInt)
      .option('--mode <mode>', 'Pruning mode: naive, hitl, aitl')
      .option('--profile <name>', 'Aggressiveness profile name')
      .option('--auto-expand', 'Enable automatic expansion')
      .option('--no-auto-expand', 'Disable automatic expansion')
      .option('--synonym-strong <n>', 'Strong synonym threshold (0.7-1.0)', parseFloat)
      .option('--synonym-moderate <n>', 'Moderate synonym threshold (0.5-0.9)', parseFloat)
      .option('--low-value <n>', 'Low value score threshold (0.0-10.0)', parseFloat)
      .option('--consolidation-threshold <n>', 'Auto-merge threshold (0.5-1.0)', parseFloat)
      .action(async (options) => {
        // Deprecation warning
        console.log(colors.status.warning('\n⚠️  DEPRECATED: config-update will be removed in a future version.'));
        console.log(colors.status.dim('    Use: kg vocab config <property> <value>'));
        console.log(colors.status.dim('    Example: kg vocab config vocab_max 275 vocab_emergency 350\n'));

        try {
          const client = createClientFromEnv();

          // Build update request
          const updates: any = { updated_by: 'cli' };

          if (options.min !== undefined) updates.vocab_min = options.min;
          if (options.max !== undefined) updates.vocab_max = options.max;
          if (options.emergency !== undefined) updates.vocab_emergency = options.emergency;
          if (options.mode) updates.pruning_mode = options.mode;
          if (options.profile) updates.aggressiveness_profile = options.profile;
          if (options.autoExpand !== undefined) updates.auto_expand_enabled = options.autoExpand;
          if (options.synonymStrong !== undefined) updates.synonym_threshold_strong = options.synonymStrong;
          if (options.synonymModerate !== undefined) updates.synonym_threshold_moderate = options.synonymModerate;
          if (options.lowValue !== undefined) updates.low_value_threshold = options.lowValue;
          if (options.consolidationThreshold !== undefined) updates.consolidation_similarity_threshold = options.consolidationThreshold;

          if (Object.keys(updates).length === 1) { // Only 'updated_by'
            console.error(colors.status.error('✗ No configuration fields provided for update'));
            console.error(colors.status.dim('\nUse --help to see available options'));
            process.exit(1);
          }

          console.log('\n' + separator());
          console.log(colors.ui.title('📝 Updating Vocabulary Configuration'));
          console.log(separator());

          const result = await client.updateVocabularyConfig(updates);

          console.log('\n' + colors.status.success('✓ Configuration updated successfully'));
          console.log(`\n  ${colors.stats.label('Updated fields:')} ${colors.ui.value(result.updated_fields.join(', '))}`);

          // Show new values
          console.log(`\n${colors.stats.section('New Configuration')}`);
          if (result.config.vocab_min) console.log(`  ${colors.stats.label('Minimum:')} ${coloredCount(result.config.vocab_min)}`);
          if (result.config.vocab_max) console.log(`  ${colors.stats.label('Maximum:')} ${coloredCount(result.config.vocab_max)}`);
          if (result.config.vocab_emergency) console.log(`  ${colors.stats.label('Emergency:')} ${coloredCount(result.config.vocab_emergency)}`);
          if (result.config.pruning_mode) console.log(`  ${colors.stats.label('Mode:')} ${colors.ui.value(result.config.pruning_mode)}`);
          if (result.config.aggressiveness_profile) console.log(`  ${colors.stats.label('Profile:')} ${colors.ui.value(result.config.aggressiveness_profile)}`);

          console.log(`\n  ${colors.stats.label('Current Size:')} ${coloredCount(result.config.current_size)}`);

          const zoneColors: Record<string, (text: string) => string> = {
            comfort: colors.status.success,
            watch: colors.status.warning,
            merge: colors.status.warning,
            mixed: colors.status.warning,
            emergency: colors.status.error,
            block: colors.status.error
          };
          const zoneColor = zoneColors[result.config.zone] || colors.ui.value;
          console.log(`  ${colors.stats.label('Zone:')} ${zoneColor(result.config.zone.toUpperCase())}`);
          console.log(`  ${colors.stats.label('Aggressiveness:')} ${colors.ui.value((result.config.aggressiveness * 100).toFixed(1) + '%')}`);

          console.log('\n' + separator());

        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to update vocabulary configuration'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('profiles')
      .description('List all aggressiveness profiles including builtin profiles (8 predefined Bezier curves) and custom profiles (user-created curves). Shows profile name, control points (x1, y1, x2, y2 for cubic Bezier), description, and builtin flag. Use this to view available profiles for configuration, review custom profiles, understand Bezier curve parameters, and identify profiles for deletion. Builtin profiles: linear, ease, ease-in, ease-out, ease-in-out, aggressive (recommended), gentle, exponential.')
      .action(async () => {
        try {
          const client = createClientFromEnv();

          console.log('\n' + separator());
          console.log(colors.ui.title('🎨 Aggressiveness Profiles'));
          console.log(separator());

          const result = await client.listAggressivenessProfiles();

          console.log(`\n  ${colors.stats.label('Total Profiles:')} ${coloredCount(result.total)}`);
          console.log(`  ${colors.stats.label('Builtin:')} ${coloredCount(result.builtin)}`);
          console.log(`  ${colors.stats.label('Custom:')} ${coloredCount(result.custom)}`);

          console.log(`\n${colors.stats.section('Profiles')}`);

          for (const profile of result.profiles) {
            const builtinFlag = profile.is_builtin ? colors.status.dim(' [B]') : '';
            console.log(`\n  ${colors.ui.value(profile.profile_name)}${builtinFlag}`);
            console.log(`    ${colors.stats.label('Control Points:')} (${profile.control_x1.toFixed(2)}, ${profile.control_y1.toFixed(2)}) (${profile.control_x2.toFixed(2)}, ${profile.control_y2.toFixed(2)})`);
            console.log(`    ${colors.stats.label('Description:')} ${colors.status.dim(profile.description)}`);
          }

          console.log('\n' + separator());

        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to list aggressiveness profiles'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('profiles-show')
      .description('Show details for a specific aggressiveness profile including full Bezier curve parameters, description, builtin status, and timestamps. Use this to inspect profile details before using, verify control point values, understand profile behavior, and check creation/update times.')
      .argument('<name>', 'Profile name')
      .action(async (name: string) => {
        try {
          const client = createClientFromEnv();

          console.log('\n' + separator());
          console.log(colors.ui.title(`🎨 Profile: ${name}`));
          console.log(separator());

          const profile = await client.getAggressivenessProfile(name);

          console.log(`\n  ${colors.stats.label('Profile Name:')} ${colors.ui.value(profile.profile_name)}`);
          console.log(`  ${colors.stats.label('Builtin:')} ${profile.is_builtin ? colors.status.success('Yes') : colors.ui.value('No')}`);

          console.log(`\n${colors.stats.section('Bezier Curve Parameters')}`);
          console.log(`  ${colors.stats.label('Control Point 1:')} (${colors.ui.value(profile.control_x1.toFixed(2))}, ${colors.ui.value(profile.control_y1.toFixed(2))})`);
          console.log(`  ${colors.stats.label('Control Point 2:')} (${colors.ui.value(profile.control_x2.toFixed(2))}, ${colors.ui.value(profile.control_y2.toFixed(2))})`);

          console.log(`\n${colors.stats.section('Description')}`);
          console.log(`  ${colors.status.dim(profile.description)}`);

          if (profile.created_at) {
            console.log(`\n${colors.stats.section('Metadata')}`);
            console.log(`  ${colors.stats.label('Created:')} ${colors.status.dim(new Date(profile.created_at).toLocaleString())}`);
            if (profile.updated_at) {
              console.log(`  ${colors.stats.label('Updated:')} ${colors.status.dim(new Date(profile.updated_at).toLocaleString())}`);
            }
          }

          console.log('\n' + separator());

        } catch (error: any) {
          console.error(colors.status.error(`✗ Failed to get profile: ${name}`));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('profiles-create')
      .description('Create a custom aggressiveness profile with Bezier curve parameters. Profiles control how aggressively vocabulary consolidation operates as size approaches thresholds. Bezier curve defined by two control points (x1, y1) and (x2, y2) where X is normalized vocabulary size (0.0-1.0) and Y is aggressiveness multiplier. Use this to create deployment-specific curves, experiment with consolidation behavior, tune for specific vocabulary growth patterns, and optimize for production workloads. Cannot overwrite builtin profiles.')
      .requiredOption('--name <name>', 'Profile name (3-50 chars)')
      .requiredOption('--x1 <n>', 'First control point X (0.0-1.0)', parseFloat)
      .requiredOption('--y1 <n>', 'First control point Y (-2.0 to 2.0)', parseFloat)
      .requiredOption('--x2 <n>', 'Second control point X (0.0-1.0)', parseFloat)
      .requiredOption('--y2 <n>', 'Second control point Y (-2.0 to 2.0)', parseFloat)
      .requiredOption('--description <desc>', 'Profile description (min 10 chars)')
      .action(async (options) => {
        try {
          const client = createClientFromEnv();

          console.log('\n' + separator());
          console.log(colors.ui.title('🎨 Creating Aggressiveness Profile'));
          console.log(separator());

          console.log(`\n  ${colors.stats.label('Name:')} ${colors.ui.value(options.name)}`);
          console.log(`  ${colors.stats.label('Control Point 1:')} (${colors.ui.value(options.x1.toFixed(2))}, ${colors.ui.value(options.y1.toFixed(2))})`);
          console.log(`  ${colors.stats.label('Control Point 2:')} (${colors.ui.value(options.x2.toFixed(2))}, ${colors.ui.value(options.y2.toFixed(2))})`);
          console.log(`  ${colors.stats.label('Description:')} ${colors.status.dim(options.description)}`);

          const profile = await client.createAggressivenessProfile({
            profile_name: options.name,
            control_x1: options.x1,
            control_y1: options.y1,
            control_x2: options.x2,
            control_y2: options.y2,
            description: options.description
          });

          console.log('\n' + colors.status.success('✓ Profile created successfully'));
          console.log(`\n  ${colors.stats.label('Profile Name:')} ${colors.ui.value(profile.profile_name)}`);
          console.log(`  ${colors.stats.label('Created:')} ${colors.status.dim(new Date(profile.created_at).toLocaleString())}`);

          console.log('\n' + separator());

        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to create aggressiveness profile'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('profiles-delete')
      .description('Delete a custom aggressiveness profile. Removes the profile permanently from the database. Cannot delete builtin profiles (protected by database trigger). Use this to remove unused custom profiles, clean up experimental curves, and maintain profile list. Safety: builtin profiles cannot be deleted, atomic operation, immediate effect.')
      .argument('<name>', 'Profile name to delete')
      .action(async (name: string) => {
        try {
          const client = createClientFromEnv();

          console.log('\n' + separator());
          console.log(colors.ui.title('🗑️  Deleting Aggressiveness Profile'));
          console.log(separator());

          console.log(`\n  ${colors.stats.label('Profile:')} ${colors.ui.value(name)}`);

          const result = await client.deleteAggressivenessProfile(name);

          console.log('\n' + colors.status.success('✓ Profile deleted successfully'));
          console.log(`\n  ${colors.stats.label('Message:')} ${colors.status.dim(result.message)}`);

          console.log('\n' + separator());

        } catch (error: any) {
          console.error(colors.status.error(`✗ Failed to delete profile: ${name}`));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('epistemic-status')
      .description('Epistemic status classification for vocabulary types (ADR-065 Phase 2). Shows knowledge validation state based on grounding patterns: WELL_GROUNDED (avg >0.8, well-established), MIXED_GROUNDING (0.15-0.8, variable validation), WEAK_GROUNDING (0.0-0.15, emerging evidence), POORLY_GROUNDED (-0.5-0.0, uncertain), CONTRADICTED (<-0.5, refuted), HISTORICAL (temporal vocabulary), INSUFFICIENT_DATA (<3 measurements). Results are temporal measurements that change as graph evolves. Use for filtering relationships by epistemic reliability, identifying contested knowledge, tracking knowledge validation trends, and curating high-confidence vs exploratory subgraphs.')
      .addCommand(
        new Command('list')
          .description('List all vocabulary types with their epistemic status classifications and statistics. Shows TYPE, STATUS (color-coded), AVG GROUNDING (reliability score), SAMPLED (edges analyzed), and MEASURED AT (timestamp). Filter by status using --status flag. Sorted by highest grounding first. Use for overview of epistemic landscape, finding high-confidence types for critical queries, identifying contested/contradictory types needing review, and tracking temporal evolution of knowledge validation.')
          .option('--status <status>', 'Filter by status: WELL_GROUNDED, MIXED_GROUNDING, WEAK_GROUNDING, POORLY_GROUNDED, CONTRADICTED, HISTORICAL, INSUFFICIENT_DATA')
          .action(async (options) => {
            try {
              const client = createClientFromEnv();
              const result = await client.listEpistemicStatus(options.status);

              console.log('\n' + separator());
              console.log(colors.ui.title('📊 Epistemic Status'));
              console.log(separator());

              // Display staleness information
              if (result.last_measurement_at) {
                const measurementDate = new Date(result.last_measurement_at).toLocaleString();
                console.log(`\n${colors.ui.key('Last Measurement:')} ${colors.ui.value(measurementDate)}`);

                const delta = result.vocabulary_changes_since_measurement ?? 0;
                let stalenessText = '';
                let stalenessColor = colors.status.success;

                if (delta === 0) {
                  stalenessText = 'No changes since measurement (fresh)';
                  stalenessColor = colors.status.success;
                } else if (delta < 5) {
                  stalenessText = `${delta} vocabulary change${delta > 1 ? 's' : ''} since measurement`;
                  stalenessColor = colors.ui.value;
                } else if (delta < 10) {
                  stalenessText = `${delta} vocabulary changes since measurement (consider re-measuring)`;
                  stalenessColor = colors.status.warning;
                } else {
                  stalenessText = `${delta} vocabulary changes since measurement (re-measurement recommended)`;
                  stalenessColor = colors.status.warning;
                }

                console.log(`${colors.ui.key('Staleness:')} ${stalenessColor(stalenessText)}`);
              }

              console.log(`\n${colors.ui.key('Total Types:')} ${coloredCount(result.total)}`);

              if (result.types.length > 0) {
                // Sort by avg_grounding descending (highest first)
                const sortedTypes = [...result.types].sort((a, b) => {
                  const aGrounding = a.stats?.avg_grounding ?? -999;
                  const bGrounding = b.stats?.avg_grounding ?? -999;
                  return bGrounding - aGrounding;
                });

                console.log('\n' + separator(75, '─'));
                console.log(
                  colors.status.dim(
                    `${'TYPE'.padEnd(25)} ${'STATUS'.padEnd(20)} ${'AVG GROUNDING'.padStart(13)} ${'SAMPLED'.padStart(10)}`
                  )
                );
                console.log(separator(75, '─'));

                sortedTypes.forEach((type: any) => {
                  const relColor = colors.getRelationshipColor(type.relationship_type);

                  // Color-code status (grounding-based terminology)
                  const statusColors: Record<string, (text: string) => string> = {
                    WELL_GROUNDED: colors.status.success,
                    MIXED_GROUNDING: colors.status.warning,
                    WEAK_GROUNDING: colors.ui.value,
                    POORLY_GROUNDED: colors.status.dim,
                    CONTRADICTED: colors.status.error,
                    HISTORICAL: colors.ui.value,
                    INSUFFICIENT_DATA: colors.status.dim
                  };
                  const statusColor = statusColors[type.epistemic_status] || colors.ui.value;

                  const avgGrounding = type.stats?.avg_grounding !== undefined
                    ? type.stats.avg_grounding.toFixed(3).padStart(6)
                    : '  --  ';

                  const sampledEdges = type.stats?.sampled_edges !== undefined
                    ? String(type.stats.sampled_edges).padStart(7)
                    : '    -- ';

                  console.log(
                    `${relColor(type.relationship_type.padEnd(25))} ` +
                    `${statusColor(type.epistemic_status.padEnd(20))} ` +
                    `${avgGrounding.padStart(13)} ` +
                    `${sampledEdges.padStart(10)}`
                  );
                });

                console.log(separator(75, '─'));
              }

              console.log();
            } catch (error: any) {
              console.error(colors.status.error('✗ Failed to list epistemic status'));
              console.error(colors.status.error(error.response?.data?.detail || error.message));
              process.exit(1);
            }
          })
      )
      .addCommand(
        new Command('show')
          .description('Show detailed epistemic status for a specific vocabulary type including full grounding statistics, measurement timestamp, and rationale. Displays classification (WELL_GROUNDED/MIXED_GROUNDING/etc.), average grounding (reliability), standard deviation (consistency), min/max range (outliers), sample sizes (measurement scope), total edges (population), and measurement timestamp (temporal context). Use for deep-diving on specific types, understanding classification rationale, verifying measurement quality, and tracking individual type evolution.')
          .argument('<type>', 'Relationship type to show (e.g., IMPLIES, SUPPORTS)')
          .action(async (type: string) => {
            try {
              const client = createClientFromEnv();
              const result = await client.getEpistemicStatus(type);

              console.log('\n' + separator());
              console.log(colors.ui.title(`📊 Epistemic Status: ${colors.getRelationshipColor(type)(type)}`));
              console.log(separator());

              // Status with color (grounding-based terminology)
              const statusColors: Record<string, (text: string) => string> = {
                WELL_GROUNDED: colors.status.success,
                MIXED_GROUNDING: colors.status.warning,
                WEAK_GROUNDING: colors.ui.value,
                POORLY_GROUNDED: colors.status.dim,
                CONTRADICTED: colors.status.error,
                HISTORICAL: colors.ui.value,
                INSUFFICIENT_DATA: colors.status.dim
              };
              const statusColor = statusColors[result.epistemic_status] || colors.ui.value;

              console.log(`\n${colors.stats.section('Classification')}`);
              console.log(`  ${colors.stats.label('Status:')} ${statusColor(result.epistemic_status)}`);

              if (result.stats) {
                console.log(`\n${colors.stats.section('Grounding Statistics')}`);
                console.log(`  ${colors.stats.label('Average Grounding:')} ${colors.ui.value(result.stats.avg_grounding.toFixed(3))}`);
                console.log(`  ${colors.stats.label('Std Deviation:')} ${colors.ui.value(result.stats.std_grounding.toFixed(3))}`);
                console.log(`  ${colors.stats.label('Min Grounding:')} ${colors.ui.value(result.stats.min_grounding.toFixed(3))}`);
                console.log(`  ${colors.stats.label('Max Grounding:')} ${colors.ui.value(result.stats.max_grounding.toFixed(3))}`);

                console.log(`\n${colors.stats.section('Measurement Scope')}`);
                console.log(`  ${colors.stats.label('Measured Concepts:')} ${coloredCount(result.stats.measured_concepts)}`);
                console.log(`  ${colors.stats.label('Sampled Edges:')} ${coloredCount(result.stats.sampled_edges)}`);
                console.log(`  ${colors.stats.label('Total Edges:')} ${coloredCount(result.stats.total_edges)}`);
              }

              if (result.status_measured_at || result.vocabulary_changes_since_measurement !== undefined) {
                console.log(`\n${colors.stats.section('Measurement Context')}`);

                if (result.status_measured_at) {
                  console.log(`  ${colors.stats.label('Measured At:')} ${colors.status.dim(new Date(result.status_measured_at).toLocaleString())}`);
                }

                if (result.vocabulary_changes_since_measurement !== undefined) {
                  const delta = result.vocabulary_changes_since_measurement;
                  let stalenessText = '';
                  let stalenessColor = colors.status.success;

                  if (delta === 0) {
                    stalenessText = 'No changes since measurement (fresh)';
                    stalenessColor = colors.status.success;
                  } else if (delta < 5) {
                    stalenessText = `${delta} vocabulary change${delta > 1 ? 's' : ''} since measurement`;
                    stalenessColor = colors.ui.value;
                  } else if (delta < 10) {
                    stalenessText = `${delta} vocabulary changes since measurement (consider re-measuring)`;
                    stalenessColor = colors.status.warning;
                  } else {
                    stalenessText = `${delta} vocabulary changes since measurement (re-measurement recommended)`;
                    stalenessColor = colors.status.warning;
                  }

                  console.log(`  ${colors.stats.label('Staleness:')} ${stalenessColor(stalenessText)}`);
                }

                console.log(`  ${colors.status.dim('Note: Results are temporal - rerun measurement as graph evolves')}`);
              }

              console.log('\n' + separator());

            } catch (error: any) {
              if (error.response?.status === 404) {
                console.error(colors.status.error(`✗ Vocabulary type not found: ${type}`));
              } else {
                console.error(colors.status.error('✗ Failed to get epistemic status'));
                console.error(colors.status.error(error.response?.data?.detail || error.message));
              }
              process.exit(1);
            }
          })
      )
      .addCommand(
        new Command('measure')
          .description('Run epistemic status measurement for all vocabulary types (ADR-065 Phase 2). Samples edges (default 100 per type), calculates grounding dynamically for target concepts (bounded recursion), classifies epistemic patterns (AFFIRMATIVE/CONTESTED/CONTRADICTORY/HISTORICAL), and optionally stores results to VocabType nodes. Measurement is temporal and observer-dependent - results change as graph evolves. Use --sample-size to control precision vs speed (larger samples = more accurate but slower), --no-store for analysis without persistence, --verbose for detailed statistics. This enables Phase 2 query filtering via GraphQueryFacade.match_concept_relationships().')
          .option('--sample-size <n>', 'Edges to sample per type (default: 100)', (val) => parseInt(val, 10), 100)
          .option('--no-store', 'Run measurement without storing to database')
          .option('--verbose', 'Include detailed statistics in output')
          .action(async (options) => {
            try {
              const client = createClientFromEnv();

              const sampleSize = options.sampleSize || 100;
              const store = options.store !== false;  // Default: true
              const verbose = options.verbose || false;

              console.log('\n' + separator());
              console.log(colors.ui.title('🔬 Measuring Epistemic Status'));
              console.log(separator());

              console.log(`\n  ${colors.ui.key('Sample Size:')} ${coloredCount(sampleSize)} edges per type`);
              console.log(`  ${colors.ui.key('Store Results:')} ${store ? colors.status.success('Yes') : colors.status.dim('No')}`);
              console.log(`  ${colors.ui.key('Verbose Output:')} ${verbose ? colors.ui.value('Yes') : colors.status.dim('No')}`);

              console.log('\n' + colors.status.dim('Running dynamic grounding measurement...'));
              console.log(colors.status.dim('This may take several minutes depending on vocabulary size and sample size.\n'));

              const result = await client.measureEpistemicStatus({
                sample_size: sampleSize,
                store: store,
                verbose: verbose
              });

              console.log('\n' + separator());
              console.log(colors.ui.title('📊 Measurement Results'));
              console.log(separator());

              console.log('\n' + colors.stats.section('Summary'));
              console.log(`  ${colors.stats.label('Total Types:')} ${coloredCount(result.total_types)}`);
              console.log(`  ${colors.stats.label('Stored:')} ${store ? coloredCount(result.stored_count) : colors.status.dim('N/A (--no-store)')}`);
              console.log(`  ${colors.stats.label('Timestamp:')} ${colors.status.dim(result.measurement_timestamp)}`);

              if (result.classifications) {
                console.log('\n' + colors.stats.section('Classifications'));
                const statusColors: Record<string, (text: string) => string> = {
                  WELL_GROUNDED: colors.status.success,
                  MIXED_GROUNDING: colors.status.warning,
                  WEAK_GROUNDING: colors.ui.value,
                  POORLY_GROUNDED: colors.status.dim,
                  CONTRADICTED: colors.status.error,
                  HISTORICAL: colors.ui.value,
                  INSUFFICIENT_DATA: colors.status.dim
                };

                // Sort by grounding quality (best to worst)
                const statusOrder = [
                  'WELL_GROUNDED',
                  'MIXED_GROUNDING',
                  'WEAK_GROUNDING',
                  'POORLY_GROUNDED',
                  'CONTRADICTED',
                  'HISTORICAL',
                  'INSUFFICIENT_DATA'
                ];

                const sortedEntries = Object.entries(result.classifications).sort((a, b) => {
                  const aIndex = statusOrder.indexOf(a[0]);
                  const bIndex = statusOrder.indexOf(b[0]);
                  // If status not in order list, put at end
                  if (aIndex === -1) return 1;
                  if (bIndex === -1) return -1;
                  return aIndex - bIndex;
                });

                for (const [status, count] of sortedEntries) {
                  const statusColor = statusColors[status] || colors.ui.value;
                  console.log(`  ${statusColor(status.padEnd(20))}: ${coloredCount(count as number)}`);
                }
              }

              if (result.sample_results && result.sample_results.length > 0) {
                // Sort by avg_grounding descending (highest first)
                const sortedResults = [...result.sample_results].sort((a, b) => {
                  const aGrounding = a.stats?.avg_grounding ?? -999;
                  const bGrounding = b.stats?.avg_grounding ?? -999;
                  return bGrounding - aGrounding;
                });

                const sampleSize = Math.min(10, sortedResults.length);
                console.log(`\n${colors.stats.section(`Sample Results (${sampleSize} of ${sortedResults.length})`)}`);

                for (let i = 0; i < sampleSize; i++) {
                  const sample = sortedResults[i];
                  const statusColors: Record<string, (text: string) => string> = {
                    WELL_GROUNDED: colors.status.success,
                    MIXED_GROUNDING: colors.status.warning,
                    WEAK_GROUNDING: colors.ui.value,
                    POORLY_GROUNDED: colors.status.dim,
                    CONTRADICTED: colors.status.error,
                    HISTORICAL: colors.ui.value,
                    INSUFFICIENT_DATA: colors.status.dim
                  };
                  const statusColor = statusColors[sample.epistemic_status] || colors.ui.value;

                  const avgGrounding = sample.stats?.avg_grounding !== undefined
                    ? sample.stats.avg_grounding.toFixed(3)
                    : '--';

                  console.log(
                    `  ${colors.getRelationshipColor(sample.relationship_type)(sample.relationship_type.padEnd(25))} → ` +
                    `${statusColor(sample.epistemic_status.padEnd(18))} (avg: ${avgGrounding})`
                  );
                }
              }

              console.log('\n' + separator());
              console.log(colors.status.success('✓ ' + result.message));
              if (store) {
                console.log(colors.status.dim('\n  Phase 2 query filtering now available via API'));
              } else {
                console.log(colors.status.dim('\n  Use without --no-store to enable Phase 2 query filtering'));
              }
              console.log(separator());

            } catch (error: any) {
              console.error(colors.status.error('✗ Failed to measure epistemic status'));
              console.error(colors.status.error(error.response?.data?.detail || error.message));
              process.exit(1);
            }
          })
      )
  );
