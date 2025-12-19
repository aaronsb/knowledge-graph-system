/**
 * Vocabulary Status Commands
 * Status overview and list of all edge types (ADR-032)
 */

import { Command } from 'commander';
import { createClientFromEnv } from '../../api/client';
import * as colors from '../colors';
import { coloredCount, separator } from '../colors';
import { plotBezierCurve, formatCurveSummary, type CurveMarker, type ZoneLabel } from '../curve-viz';

export function createStatusCommand(): Command {
  return new Command('status')
    .description('Show current vocabulary status including size, zone (GREEN/WATCH/DANGER/EMERGENCY per ADR-032), aggressiveness, and thresholds.')
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
    });
}

export function createListCommand(): Command {
  return new Command('list')
    .description('List all edge types with statistics, categories, and confidence scores (ADR-047).')
    .option('--inactive', 'Include inactive/deprecated types')
    .option('--no-builtin', 'Exclude builtin types')
    .option('--sort <fields>', 'Sort by comma-separated fields: edges, type, conf, grounding, category, status (default: edges)')
    .option('--json', 'Output as JSON for programmatic use')
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
                  if (aVal !== bVal) return bVal - aVal;
                  break;
                case 'grounding':
                  aVal = a.avg_grounding ?? -999;
                  bVal = b.avg_grounding ?? -999;
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
                  break;
              }
            }
            return 0;
          });
        }

        // JSON output mode
        if (options.json) {
          console.log(JSON.stringify(response, null, 2));
          return;
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
    });
}
