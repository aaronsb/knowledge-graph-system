/**
 * Vocabulary Epistemic Status Commands
 * Knowledge validation state based on grounding patterns (ADR-065)
 */

import { Command } from 'commander';
import { createClientFromEnv } from '../../api/client';
import * as colors from '../colors';
import { coloredCount, separator } from '../colors';

export function createEpistemicStatusCommand(): Command {
  const epistemicCommand = new Command('epistemic-status')
    .description('Epistemic status classification for vocabulary types (ADR-065). Shows knowledge validation state based on grounding patterns.');

  // kg vocab epistemic-status list
  epistemicCommand.addCommand(
    new Command('list')
      .description('List all vocabulary types with their epistemic status classifications and statistics.')
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
  );

  // kg vocab epistemic-status show <type>
  epistemicCommand.addCommand(
    new Command('show')
      .description('Show detailed epistemic status for a specific vocabulary type.')
      .argument('<type>', 'Relationship type to show (e.g., IMPLIES, SUPPORTS)')
      .action(async (type: string) => {
        try {
          const client = createClientFromEnv();
          const result = await client.getEpistemicStatus(type);

          console.log('\n' + separator());
          console.log(colors.ui.title(`📊 Epistemic Status: ${colors.getRelationshipColor(type)(type)}`));
          console.log(separator());

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
  );

  // kg vocab epistemic-status measure
  epistemicCommand.addCommand(
    new Command('measure')
      .description('Run epistemic status measurement for all vocabulary types (ADR-065).')
      .option('--sample-size <n>', 'Edges to sample per type (default: 100)', (val) => parseInt(val, 10), 100)
      .option('--no-store', 'Run measurement without storing to database')
      .option('--verbose', 'Include detailed statistics in output')
      .action(async (options) => {
        try {
          const client = createClientFromEnv();

          const sampleSize = options.sampleSize || 100;
          const store = options.store !== false;
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
  );

  return epistemicCommand;
}
