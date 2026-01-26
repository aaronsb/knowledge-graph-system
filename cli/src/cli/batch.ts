/**
 * Batch Operations Commands (ADR-089 Phase 1b)
 *
 * Import batch JSON files containing concepts and edges.
 */

import { Command } from 'commander';
import * as fs from 'fs';
import { createClientFromEnv } from '../api/client';
import * as colors from './colors';
import { separator } from './colors';
import { setCommandHelp } from './help-formatter';
import { BatchCreateRequest } from '../types';
import { handleCliError } from '../lib/interactive';

export const batchCommand = setCommandHelp(
  new Command('batch'),
  'Batch graph operations',
  'Batch operations for creating concepts and edges in a single transaction. Import JSON files that define concepts and their relationships. All operations are atomic - if any item fails, the entire batch is rolled back.'
)
  .alias('b')
  .showHelpAfterError('(add --help for additional information)')
  .showSuggestionAfterError()
  .addCommand(
    new Command('create')
      .description('Import a batch JSON file to create concepts and edges atomically. The JSON must contain ontology, concepts array, and optional edges array. All operations succeed or all are rolled back.')
      .argument('<file>', 'Path to batch JSON file')
      .option('--json', 'Output result as JSON')
      .option('--dry-run', 'Validate without creating (not yet implemented)')
      .action(async (file: string, options: { json?: boolean; dryRun?: boolean }) => {
        try {
          // Read and parse the JSON file
          if (!fs.existsSync(file)) {
            console.error(colors.status.error(`✗ File not found: ${file}`));
            process.exit(1);
          }

          const content = fs.readFileSync(file, 'utf-8');
          let request: BatchCreateRequest;

          try {
            request = JSON.parse(content);
          } catch (parseError) {
            console.error(colors.status.error('✗ Invalid JSON file'));
            console.error(colors.status.error((parseError as Error).message));
            process.exit(1);
          }

          // Basic validation
          if (!request.ontology) {
            console.error(colors.status.error('✗ Missing required field: ontology'));
            process.exit(1);
          }

          if ((!request.concepts || request.concepts.length === 0) &&
              (!request.edges || request.edges.length === 0)) {
            console.error(colors.status.error('✗ Batch must contain at least one concept or edge'));
            process.exit(1);
          }

          // Check for edge references to concepts not in the batch
          if (request.edges && request.edges.length > 0 && request.concepts) {
            const batchLabels = new Set(
              request.concepts.map((c) => c.label.toLowerCase())
            );
            const unreferencedEdges: string[] = [];

            for (const edge of request.edges) {
              const fromInBatch = batchLabels.has(edge.from_label.toLowerCase());
              const toInBatch = batchLabels.has(edge.to_label.toLowerCase());

              if (!fromInBatch || !toInBatch) {
                const missing: string[] = [];
                if (!fromInBatch) missing.push(`from: "${edge.from_label}"`);
                if (!toInBatch) missing.push(`to: "${edge.to_label}"`);
                unreferencedEdges.push(
                  `  ${edge.from_label} -[${edge.relationship_type}]-> ${edge.to_label} (${missing.join(', ')} not in batch)`
                );
              }
            }

            if (unreferencedEdges.length > 0 && !options.json) {
              console.log(colors.status.warning('\n⚠️  Some edges reference concepts not in this batch file:'));
              for (const edge of unreferencedEdges.slice(0, 5)) {
                console.log(colors.status.dim(edge));
              }
              if (unreferencedEdges.length > 5) {
                console.log(colors.status.dim(`  ... and ${unreferencedEdges.length - 5} more`));
              }
              console.log(colors.status.dim('  These edges will resolve to existing concepts in the database, or fail if not found.\n'));
            }
          }

          if (options.dryRun) {
            console.log(colors.status.warning('Dry-run mode not yet implemented by API.'));
            console.log(colors.status.info('File validation passed:'));
            console.log(`  Ontology: ${request.ontology}`);
            console.log(`  Concepts: ${request.concepts?.length || 0}`);
            console.log(`  Edges: ${request.edges?.length || 0}`);
            return;
          }

          const client = createClientFromEnv();

          if (!options.json) {
            console.log();
            console.log(colors.ui.title('📦 Batch Import'));
            console.log(separator());
            console.log(`  ${colors.ui.key('File:')} ${file}`);
            console.log(`  ${colors.ui.key('Ontology:')} ${request.ontology}`);
            console.log(`  ${colors.ui.key('Concepts:')} ${request.concepts?.length || 0}`);
            console.log(`  ${colors.ui.key('Edges:')} ${request.edges?.length || 0}`);
            console.log();
            console.log(colors.status.dim('Creating...'));
          }

          const result = await client.batchCreate(request);

          if (options.json) {
            console.log(JSON.stringify(result, null, 2));
            return;
          }

          console.log();
          console.log(separator());

          // Show results
          if (result.errors.length > 0) {
            console.log(colors.status.warning('⚠️  Completed with errors:'));
            for (const error of result.errors) {
              console.log(`  ${colors.status.error('✗')} ${error}`);
            }
            console.log();
          } else {
            console.log(colors.status.success('✓ Batch import successful'));
          }

          console.log(`  ${colors.ui.key('Concepts created:')} ${colors.status.success(result.concepts_created.toString())}`);
          console.log(`  ${colors.ui.key('Concepts matched:')} ${colors.status.info(result.concepts_matched.toString())}`);
          console.log(`  ${colors.ui.key('Edges created:')} ${colors.status.success(result.edges_created.toString())}`);

          // Show individual results if verbose
          if (result.concept_results.length > 0) {
            console.log();
            console.log(colors.ui.header('Concept Results:'));
            for (const cr of result.concept_results) {
              const statusIcon = cr.status === 'created' ? colors.status.success('✓') :
                                cr.status === 'matched' ? colors.status.info('≈') :
                                colors.status.error('✗');
              const statusText = cr.status === 'created' ? 'created' :
                                cr.status === 'matched' ? 'matched existing' : 'error';
              console.log(`  ${statusIcon} ${colors.concept.label(cr.label)} - ${statusText}${cr.id ? ` (${cr.id})` : ''}`);
              if (cr.error) {
                console.log(`    ${colors.status.error(cr.error)}`);
              }
            }
          }

          if (result.edge_results.length > 0) {
            console.log();
            console.log(colors.ui.header('Edge Results:'));
            for (const er of result.edge_results) {
              const statusIcon = er.status === 'created' ? colors.status.success('✓') :
                                er.status === 'error' ? colors.status.error('✗') : '?';
              console.log(`  ${statusIcon} ${er.label}`);
              if (er.error) {
                console.log(`    ${colors.status.error(er.error)}`);
              }
            }
          }

          console.log();
          console.log(separator());

          // Exit with error code if there were failures
          if (result.errors.length > 0 && result.concepts_created === 0 && result.edges_created === 0) {
            process.exit(1);
          }
        } catch (error: any) {
          handleCliError(error, 'Batch import failed');
        }
      })
  )
  .addCommand(
    new Command('template')
      .description('Output a template batch JSON file to stdout. Redirect to a file to customize.')
      .option('--with-edges', 'Include example edges in template')
      .action((options: { withEdges?: boolean }) => {
        const template: BatchCreateRequest = {
          ontology: 'my-ontology',
          matching_mode: 'auto',
          creation_method: 'import',
          concepts: [
            {
              label: 'Example Concept A',
              description: 'A brief description of concept A',
              search_terms: ['alt term', 'synonym'],
            },
            {
              label: 'Example Concept B',
              description: 'A brief description of concept B',
            },
          ],
        };

        if (options.withEdges) {
          template.edges = [
            {
              from_label: 'Example Concept A',
              to_label: 'Example Concept B',
              relationship_type: 'IMPLIES',
              category: 'logical_truth',
              confidence: 0.9,
            },
          ];
        }

        console.log(JSON.stringify(template, null, 2));
      })
  );
