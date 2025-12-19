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

/**
 * Display polarity analysis result
 */
function displayPolarityResult(result: any, options: any): void {
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
  if (result.projections && result.projections.length > 0) {
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
  .option('--discovery-mode <mode>', 'Discovery strategy: conservative (pure degree), balanced (80/20 - DEFAULT), novelty (pure random)', 'balanced')
  .option('--discovery-pct <number>', 'Custom discovery percentage (0.0-1.0, overrides --discovery-mode)')
  .option('--max-workers <number>', 'Maximum parallel workers for 2-hop queries', '8')
  .option('--chunk-size <number>', 'Concepts per worker chunk', '20')
  .option('--timeout <number>', 'Wall-clock timeout in seconds', '120')
  .option('--save-artifact', 'Save result as persistent artifact (uses async job)')
  .option('--json', 'Output raw JSON instead of formatted text')
  .action(async (options) => {
    try {
      const client = createClientFromEnv();

      // Parse discovery mode to percentage
      let discoveryPct: number;
      if (options.discoveryPct !== undefined) {
        // Custom percentage overrides mode
        discoveryPct = parseFloat(options.discoveryPct);
        if (discoveryPct < 0 || discoveryPct > 1) {
          throw new Error('discovery-pct must be between 0.0 and 1.0');
        }
      } else {
        // Map mode to percentage
        const modeMap: Record<string, number> = {
          'conservative': 0.0,
          'balanced': 0.2,
          'novelty': 1.0
        };
        discoveryPct = modeMap[options.discoveryMode.toLowerCase()];
        if (discoveryPct === undefined) {
          throw new Error(`Invalid discovery-mode: ${options.discoveryMode}. Must be: conservative, balanced, or novelty`);
        }
      }

      console.log(colors.ui.header('Polarity Axis Analysis'));
      console.log(separator());
      console.log();

      if (!options.json) {
        console.log(`${colors.ui.key('Positive pole:')} ${options.positive}`);
        console.log(`${colors.ui.key('Negative pole:')} ${options.negative}`);
        if (options.candidates) {
          console.log(`${colors.ui.key('Candidates:')} ${options.candidates.length} concepts`);
        } else {
          const modeLabel = discoveryPct === 0.0 ? 'conservative (pure degree)' :
                            discoveryPct === 1.0 ? 'novelty (pure random)' :
                            `balanced (${Math.round((1-discoveryPct)*100)}% degree + ${Math.round(discoveryPct*100)}% random)`;
          console.log(`${colors.ui.key('Discovery:')} Auto (max ${options.maxCandidates} concepts, ${options.maxHops} hops, ${modeLabel})`);
        }
        if (options.saveArtifact) {
          console.log(`${colors.ui.key('Artifact:')} ${colors.status.success('Will save result')}`);
        }
        console.log();
        console.log(colors.status.info('⏳ Analyzing polarity axis...'));
      }

      // If saving artifact, use async job endpoint
      if (options.saveArtifact) {
        const jobResponse = await client.submitPolarityJob({
          positive_pole_id: options.positive,
          negative_pole_id: options.negative,
          candidate_ids: options.candidates,
          auto_discover: options.autoDiscover !== false,
          max_candidates: parseInt(options.maxCandidates),
          max_hops: parseInt(options.maxHops),
          discovery_slot_pct: discoveryPct,
          max_workers: parseInt(options.maxWorkers),
          chunk_size: parseInt(options.chunkSize),
          timeout_seconds: parseFloat(options.timeout),
          create_artifact: true
        });

        if (!options.json) {
          console.log();
          console.log(colors.status.info(`Job submitted: ${jobResponse.job_id}`));
          console.log(colors.status.info('Waiting for completion...'));
        }

        // Poll for job completion
        let jobStatus = await client.getJob(jobResponse.job_id);
        while (jobStatus.status !== 'completed' && jobStatus.status !== 'failed') {
          await new Promise(resolve => setTimeout(resolve, 1000));
          jobStatus = await client.getJob(jobResponse.job_id);
          if (!options.json && jobStatus.progress) {
            process.stdout.write(`\r${colors.status.dim(jobStatus.progress)}          `);
          }
        }

        if (!options.json) {
          console.log();
        }

        if (jobStatus.status === 'failed') {
          console.error(colors.status.error(`\n❌ Job failed: ${jobStatus.error}`));
          process.exit(1);
        }

        // Get the artifact
        const artifactId = jobStatus.result?.artifact_id;
        if (artifactId) {
          const artifact = await client.getArtifactPayload(artifactId);

          if (options.json) {
            console.log(JSON.stringify({ ...artifact.payload, artifact_id: artifactId }, null, 2));
            return;
          }

          // Display results with artifact info
          console.log();
          console.log(colors.status.success(`✅ Artifact saved: ${artifactId}`));
          console.log(colors.status.dim(`   View with: kg artifact show ${artifactId}`));
          console.log(colors.status.dim(`   Payload:   kg artifact payload ${artifactId}`));
          console.log();

          // Use artifact payload as result
          const result = artifact.payload;
          displayPolarityResult(result, options);
          return;
        } else {
          // No artifact created, show job result
          if (options.json) {
            console.log(JSON.stringify(jobStatus.result, null, 2));
          } else {
            console.log(colors.status.warning('Job completed but no artifact was created'));
            console.log(JSON.stringify(jobStatus.result, null, 2));
          }
          return;
        }
      }

      // Standard synchronous analysis
      const result = await client.analyzePolarityAxis({
        positive_pole_id: options.positive,
        negative_pole_id: options.negative,
        candidate_ids: options.candidates,
        auto_discover: options.autoDiscover !== false,
        max_candidates: parseInt(options.maxCandidates),
        max_hops: parseInt(options.maxHops),
        discovery_slot_pct: discoveryPct,
        max_workers: parseInt(options.maxWorkers),
        chunk_size: parseInt(options.chunkSize),
        timeout_seconds: parseFloat(options.timeout)
      });

      if (options.json) {
        console.log(JSON.stringify(result, null, 2));
        return;
      }

      console.log();
      displayPolarityResult(result, options);

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
