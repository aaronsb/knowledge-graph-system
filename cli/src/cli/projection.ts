/**
 * Projection Commands (ADR-078)
 *
 * Manage embedding landscape projections for visualization.
 */

import { Command } from 'commander';
import { createClientFromEnv } from '../api/client';
import * as colors from './colors';
import { Table } from '../lib/table';
import { setCommandHelp } from './help-formatter';

export const projectionCommand = setCommandHelp(
  new Command('projection'),
  'Manage embedding projections for visualization',
  'Manage t-SNE/UMAP projections of concept embeddings. Projections reduce high-dimensional embeddings to 3D coordinates for the Embedding Landscape Explorer visualization. Use this to compute, view, and manage projection datasets.'
)
  .alias('proj')
  .showHelpAfterError('(add --help for additional information)')
  .showSuggestionAfterError()
  .addCommand(
    new Command('list')
      .description('List projection status for all ontologies. Shows which ontologies have cached projections and their statistics.')
      .action(async () => {
        try {
          const client = createClientFromEnv();

          // Get all ontologies
          const ontologies = await client.listOntologies();

          if (ontologies.count === 0) {
            console.log(colors.status.warning('\nNo ontologies found'));
            return;
          }

          console.log('\n' + colors.ui.title('Embedding Projections'));

          const rows: any[] = [];

          for (const ont of ontologies.ontologies) {
            try {
              const proj = await client.getProjection(ont.ontology);
              rows.push({
                ontology: ont.ontology,
                status: 'cached',
                concepts: proj.statistics.concept_count,
                algorithm: proj.algorithm,
                computed: new Date(proj.computed_at).toLocaleString(),
                changelist: proj.changelist_id.slice(0, 20)
              });
            } catch (error: any) {
              if (error.response?.status === 404) {
                rows.push({
                  ontology: ont.ontology,
                  status: 'not computed',
                  concepts: ont.concept_count,
                  algorithm: '-',
                  computed: '-',
                  changelist: '-'
                });
              } else {
                rows.push({
                  ontology: ont.ontology,
                  status: 'error',
                  concepts: ont.concept_count,
                  algorithm: '-',
                  computed: '-',
                  changelist: '-'
                });
              }
            }
          }

          const table = new Table({
            columns: [
              { header: 'Ontology', field: 'ontology', type: 'heading', width: 'flex', priority: 3 },
              { header: 'Status', field: 'status', type: 'text', width: 14 },
              { header: 'Concepts', field: 'concepts', type: 'count', width: 10, align: 'right' },
              { header: 'Algorithm', field: 'algorithm', type: 'text', width: 10 },
              { header: 'Computed', field: 'computed', type: 'text', width: 20 }
            ]
          });

          table.print(rows);

        } catch (error: any) {
          console.error(colors.status.error('Failed to list projections'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('info')
      .description('Get detailed projection info for an ontology')
      .argument('<ontology>', 'Ontology name')
      .action(async (ontology: string) => {
        try {
          const client = createClientFromEnv();
          const proj = await client.getProjection(ontology);

          console.log('\n' + colors.ui.title(`Projection: ${ontology}`));
          console.log();
          console.log(`  Algorithm:    ${colors.stats.value(proj.algorithm)}`);
          console.log(`  Concepts:     ${colors.stats.value(proj.statistics.concept_count.toString())}`);
          console.log(`  Dimensions:   ${proj.statistics.embedding_dims} → 3D`);
          console.log(`  Computed:     ${new Date(proj.computed_at).toLocaleString()}`);
          console.log(`  Time:         ${proj.statistics.computation_time_ms}ms`);
          console.log(`  Changelist:   ${proj.changelist_id}`);

          if (proj.parameters.perplexity) {
            console.log(`  Perplexity:   ${proj.parameters.perplexity}`);
          }
          if (proj.statistics.grounding_range) {
            console.log(`  Grounding:    [${proj.statistics.grounding_range[0].toFixed(2)}, ${proj.statistics.grounding_range[1].toFixed(2)}]`);
          }

          // Show sample concepts
          console.log('\n' + colors.ui.subtitle('Sample Concepts (first 5):'));
          const sample = proj.concepts.slice(0, 5);
          for (const c of sample) {
            console.log(`  ${colors.concept.label(c.label)}`);
            console.log(`    Position: (${c.x.toFixed(2)}, ${c.y.toFixed(2)}, ${c.z.toFixed(2)})`);
          }

        } catch (error: any) {
          if (error.response?.status === 404) {
            console.error(colors.status.error(`No projection found for '${ontology}'`));
            console.log(colors.status.dim(`Run: kg projection regenerate ${ontology}`));
          } else {
            console.error(colors.status.error('Failed to get projection'));
            console.error(colors.status.error(error.response?.data?.detail || error.message));
          }
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('regenerate')
      .description('Compute or recompute projection for an ontology')
      .argument('<ontology>', 'Ontology name (or "all" for all ontologies)')
      .option('-f, --force', 'Force recomputation even if cached')
      .option('-a, --algorithm <algo>', 'Algorithm: tsne or umap', 'tsne')
      .option('-p, --perplexity <n>', 't-SNE perplexity (5-100)', '30')
      .option('--grounding', 'Include grounding strength')
      .option('--diversity', 'Include diversity scores (slower)')
      .action(async (ontology: string, options) => {
        try {
          const client = createClientFromEnv();

          const regenerateOne = async (ont: string) => {
            const result = await client.regenerateProjection(ont, {
              force: options.force || false,
              algorithm: options.algorithm,
              perplexity: parseInt(options.perplexity),
              include_grounding: options.grounding || true,
              include_diversity: options.diversity || false
            });

            if (result.status === 'computed') {
              console.log(colors.status.success(`${ont}: ${result.message}`));
            } else if (result.status === 'queued') {
              console.log(colors.status.info(`${ont}: ${result.message} (job: ${result.job_id})`));
            } else if (result.status === 'skipped') {
              console.log(colors.status.dim(`${ont}: ${result.message}`));
            }
          };

          if (ontology.toLowerCase() === 'all') {
            console.log(colors.ui.title('Regenerating all projections...'));
            const ontologies = await client.listOntologies();
            for (const ont of ontologies.ontologies) {
              await regenerateOne(ont.ontology);
            }
          } else {
            await regenerateOne(ontology);
          }

        } catch (error: any) {
          console.error(colors.status.error('Failed to regenerate projection'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('invalidate')
      .description('Delete cached projection for an ontology')
      .argument('<ontology>', 'Ontology name')
      .action(async (ontology: string) => {
        try {
          const client = createClientFromEnv();
          const result = await client.invalidateProjection(ontology);
          console.log(colors.status.success(result.message));
        } catch (error: any) {
          if (error.response?.status === 404) {
            console.log(colors.status.dim(`No cached projection for '${ontology}'`));
          } else {
            console.error(colors.status.error('Failed to invalidate projection'));
            console.error(colors.status.error(error.response?.data?.detail || error.message));
            process.exit(1);
          }
        }
      })
  )
  .addCommand(
    new Command('data')
      .description('Get full projection data as JSON (for visualization pipelines)')
      .argument('<ontology>', 'Ontology name')
      .option('-o, --output <file>', 'Write to file instead of stdout')
      .option('--pretty', 'Pretty-print JSON output')
      .action(async (ontology: string, options) => {
        try {
          const client = createClientFromEnv();
          const proj = await client.getProjection(ontology);

          const jsonOutput = options.pretty
            ? JSON.stringify(proj, null, 2)
            : JSON.stringify(proj);

          if (options.output) {
            const fs = await import('fs');
            fs.writeFileSync(options.output, jsonOutput);
            console.error(colors.status.success(`Wrote projection data to ${options.output}`));
            console.error(colors.status.dim(`  ${proj.statistics.concept_count} concepts, ${proj.algorithm} algorithm`));
          } else {
            console.log(jsonOutput);
          }

        } catch (error: any) {
          if (error.response?.status === 404) {
            console.error(colors.status.error(`No projection found for '${ontology}'`));
            console.error(colors.status.dim(`Run: kg projection regenerate ${ontology}`));
          } else {
            console.error(colors.status.error('Failed to get projection data'));
            console.error(colors.status.error(error.response?.data?.detail || error.message));
          }
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('algorithms')
      .description('List available projection algorithms')
      .action(async () => {
        try {
          const client = createClientFromEnv();
          const result = await client.getProjectionAlgorithms();

          console.log('\n' + colors.ui.title('Available Algorithms'));
          console.log();
          for (const algo of result.available) {
            const marker = algo === result.default ? colors.status.success(' (default)') : '';
            console.log(`  ${colors.stats.value(algo)}${marker}`);
          }
          console.log();
        } catch (error: any) {
          console.error(colors.status.error('Failed to get algorithms'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  );
