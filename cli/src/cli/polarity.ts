/**
 * Polarity Axis Analysis Commands (ADR-070)
 */

import { Command } from 'commander';
import { createClientFromEnv } from '../api/client';
import * as colors from './colors';
import { separator } from './colors';
import { setCommandHelp } from './help-formatter';

/**
 * Format axis position for display
 */
function formatPosition(position: number): string {
  const formatted = position.toFixed(3);
  if (position > 0.3) {
    return colors.status.success(`${formatted} (→ positive pole)`);
  } else if (position < -0.3) {
    return colors.status.error(`${formatted} (← negative pole)`);
  } else {
    return colors.status.dim(`${formatted} (⚖  neutral)`);
  }
}

/**
 * Format grounding strength for display (ADR-044)
 */
function formatGrounding(grounding: number): string {
  const formatted = grounding.toFixed(3);
  if (grounding >= 0.7) {
    return colors.status.success(`✓ ${formatted}`);
  } else if (grounding >= 0) {
    return colors.status.dim(`◯ ${formatted}`);
  } else {
    return colors.status.error(`✗ ${formatted}`);
  }
}

const analyzeCommand = setCommandHelp(
  new Command('analyze'),
  'Analyze bidirectional semantic dimension (polarity axis)',
  'Project concepts onto axis formed by two opposing poles (e.g., Modern ↔ Traditional)'
)
  .showHelpAfterError()
  .requiredOption('--positive <concept-id>', 'Positive pole concept ID')
  .requiredOption('--negative <concept-id>', 'Negative pole concept ID')
  .option('--candidates <ids...>', 'Specific concept IDs to project (space-separated)')
  .option('--no-auto-discover', 'Disable auto-discovery of related concepts')
  .option('--max-candidates <number>', 'Maximum candidates for auto-discovery', '20')
  .option('--max-hops <number>', 'Maximum graph hops for auto-discovery (1-3)', '1')
  .option('--json', 'Output raw JSON instead of formatted text')
  .action(async (options) => {
    try {
      const client = createClientFromEnv();

      console.log(colors.ui.header('Polarity Axis Analysis'));
      console.log(separator());
      console.log();

      if (!options.json) {
        console.log(`${colors.ui.key('Positive pole:')} ${options.positive}`);
        console.log(`${colors.ui.key('Negative pole:')} ${options.negative}`);
        if (options.candidates) {
          console.log(`${colors.ui.key('Candidates:')} ${options.candidates.length} concepts`);
        } else {
          console.log(`${colors.ui.key('Discovery:')} Auto (max ${options.maxCandidates} concepts, ${options.maxHops} hops)`);
        }
        console.log();
        console.log(colors.status.info('⏳ Analyzing polarity axis...'));
      }

      const result = await client.analyzePolarityAxis({
        positive_pole_id: options.positive,
        negative_pole_id: options.negative,
        candidate_ids: options.candidates,
        auto_discover: options.autoDiscover !== false,
        max_candidates: parseInt(options.maxCandidates),
        max_hops: parseInt(options.maxHops)
      });

      if (options.json) {
        console.log(JSON.stringify(result, null, 2));
        return;
      }

      console.log();
      console.log(colors.ui.header('Polarity Axis'));
      console.log(separator());
      console.log();

      // Axis info
      console.log(`${colors.ui.key('Positive pole:')} ${colors.status.success(result.axis.positive_pole.label)}`);
      console.log(`  Grounding: ${formatGrounding(result.axis.positive_pole.grounding)}`);
      console.log();
      console.log(`${colors.ui.key('Negative pole:')} ${colors.status.error(result.axis.negative_pole.label)}`);
      console.log(`  Grounding: ${formatGrounding(result.axis.negative_pole.grounding)}`);
      console.log();
      console.log(`${colors.ui.key('Magnitude:')} ${result.axis.magnitude.toFixed(4)}`);
      console.log(`${colors.ui.key('Quality:')} ${result.axis.axis_quality === 'strong' ? colors.status.success('strong') : colors.status.warning('weak')}`);
      console.log();

      // Statistics
      console.log(colors.ui.header('Statistics'));
      console.log(separator());
      console.log();
      console.log(`${colors.ui.key('Total concepts:')} ${result.statistics.total_concepts}`);
      console.log(`${colors.ui.key('Position range:')} [${result.statistics.position_range[0].toFixed(3)}, ${result.statistics.position_range[1].toFixed(3)}]`);
      console.log(`${colors.ui.key('Mean position:')} ${result.statistics.mean_position.toFixed(3)}`);
      console.log(`${colors.ui.key('Mean axis distance:')} ${result.statistics.mean_axis_distance.toFixed(3)}`);
      console.log();

      // Direction distribution
      console.log(colors.ui.header('Direction Distribution'));
      console.log(separator());
      console.log();
      console.log(`${colors.status.success('Positive:')} ${result.statistics.direction_distribution.positive}`);
      console.log(`${colors.status.dim('Neutral:')}  ${result.statistics.direction_distribution.neutral}`);
      console.log(`${colors.status.error('Negative:')} ${result.statistics.direction_distribution.negative}`);
      console.log();

      // Grounding correlation
      console.log(colors.ui.header('Grounding Correlation'));
      console.log(separator());
      console.log();
      console.log(`${colors.ui.key('Pearson r:')} ${result.grounding_correlation.pearson_r.toFixed(3)}`);
      console.log(`${colors.ui.key('p-value:')} ${result.grounding_correlation.p_value.toFixed(4)}`);
      console.log(`${colors.ui.key('Interpretation:')} ${result.grounding_correlation.interpretation}`);
      console.log();

      // Projections
      if (result.projections.length > 0) {
        console.log(colors.ui.header(`Projections (${result.projections.length} concepts)`));
        console.log(separator());
        console.log();

        for (const proj of result.projections) {
          console.log(colors.concept.label(proj.label));
          console.log(`  Position: ${formatPosition(proj.position)}`);
          console.log(`  Direction: ${proj.direction}`);
          console.log(`  Grounding: ${formatGrounding(proj.grounding)}`);
          console.log(`  Axis distance: ${proj.axis_distance.toFixed(4)}`);
          console.log();
        }
      }

      console.log(separator());
      console.log(colors.status.success('✅ Analysis complete'));

    } catch (error: any) {
      if (error.response) {
        console.error(colors.status.error(`\n❌ API Error: ${error.response.status}`));
        console.error(colors.status.error(error.response.data.detail || error.message));
      } else {
        console.error(colors.status.error(`\n❌ Error: ${error.message}`));
      }
      process.exit(1);
    }
  });

export const polarityCommand = setCommandHelp(
  new Command('polarity'),
  'Polarity axis analysis commands (ADR-070)',
  'Analyze bidirectional semantic dimensions between concept poles'
)
  .showHelpAfterError()
  .addCommand(analyzeCommand);
