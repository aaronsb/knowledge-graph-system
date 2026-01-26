/**
 * Edge CRUD Commands (ADR-089 Phase 2)
 *
 * Direct creation, listing, and management of edges (relationships) in the knowledge graph.
 * Supports both non-interactive (flags) and interactive (-i) modes.
 */

import { Command } from 'commander';
import { createClientFromEnv } from '../api/client';
import * as colors from './colors';
import { separator } from './colors';
import { Table } from '../lib/table';
import { setCommandHelp } from './help-formatter';
import { EdgeCreate } from '../types';
import {
  validateConceptId,
  validateVocabTerm,
  resolveConceptByLabel,
} from '../lib/validation';
import {
  textInput,
  selectOption,
  confirmYesNo,
  withSpinner,
  handleCliError,
} from '../lib/interactive';

export const edgeCommand = setCommandHelp(
  new Command('edge'),
  'Manage edges (relationships) in the knowledge graph',
  'Create, list, and delete edges between concepts. Edges represent relationships like IMPLIES, SUPPORTS, CONTRADICTS, etc. Use --from/--to with concept IDs or --from-label/--to-label for semantic lookup by label.'
)
  .alias('e')
  .showHelpAfterError('(add --help for additional information)')
  .showSuggestionAfterError()
  .addCommand(createListCommand())
  .addCommand(createCreateCommand())
  .addCommand(createDeleteCommand());

function createListCommand(): Command {
  return new Command('list')
    .description('List edges with optional filters.')
    .option('--from <id>', 'Filter by source concept ID')
    .option('--to <id>', 'Filter by target concept ID')
    .option('--type <type>', 'Filter by relationship type')
    .option('--category <cat>', 'Filter by category')
    .option('--limit <n>', 'Maximum results (default: 50)', '50')
    .option('--offset <n>', 'Pagination offset', '0')
    .option('--json', 'Output as JSON')
    .action(async (options) => {
      try {
        const client = createClientFromEnv();
        const params = {
          from_concept_id: options.from,
          to_concept_id: options.to,
          relationship_type: options.type,
          category: options.category,
          limit: parseInt(options.limit, 10),
          offset: parseInt(options.offset, 10),
        };

        const result = await client.listEdges(params);

        if (options.json) {
          console.log(JSON.stringify(result, null, 2));
          return;
        }

        if (result.edges.length === 0) {
          console.log(colors.status.warning('\nNo edges found.'));
          return;
        }

        console.log('\n' + colors.ui.title('🔗 Edges'));
        console.log(separator());
        console.log(colors.status.dim(`Showing ${result.edges.length} of ${result.total} edges\n`));

        const table = new Table({
          columns: [
            { header: 'From', field: 'from_concept_id', type: 'concept_id', width: 15 },
            { header: 'Type', field: 'relationship_type', type: 'heading', width: 20 },
            { header: 'To', field: 'to_concept_id', type: 'concept_id', width: 15 },
            { header: 'Category', field: 'category', type: 'text', width: 15 },
            { header: 'Conf', field: (row: any) => (row.confidence * 100).toFixed(0) + '%', type: 'text', width: 6, align: 'right' as const },
          ],
        });

        table.print(result.edges as any);

        if (result.total > result.edges.length) {
          console.log(colors.status.dim(`\nUse --offset ${result.offset + result.edges.length} to see more`));
        }
      } catch (error: any) {
        handleCliError(error, 'Failed to list edges');
      }
    });
}

function createCreateCommand(): Command {
  return new Command('create')
    .description('Create an edge between two concepts.')
    .option('--from <id>', 'Source concept ID')
    .option('--to <id>', 'Target concept ID')
    .option('--from-label <text>', 'Source concept (search by label)')
    .option('--to-label <text>', 'Target concept (search by label)')
    .option('--type <type>', 'Relationship type (e.g., IMPLIES, SUPPORTS)')
    .option('--category <cat>', 'Relationship category (auto-inferred if omitted)')
    .option('--confidence <n>', 'Confidence score 0-1 (default: 1.0)', '1.0')
    .option('--create-vocab', 'Create vocabulary term if it does not exist')
    .option('--json', 'Output as JSON')
    .option('-i, --interactive', 'Guided wizard mode')
    .option('-y, --yes', 'Skip confirmation prompts')
    .action(async (options) => {
      try {
        const client = createClientFromEnv();

        let fromConceptId: string;
        let toConceptId: string;
        let relationshipType: string;
        let category: string | undefined = options.category;
        let confidence: number = parseFloat(options.confidence) || 1.0;

        if (options.interactive) {
          // Interactive wizard mode
          console.log('\n' + colors.ui.title('🔗 Create Edge'));
          console.log(separator());
          console.log();

          // Get source concept
          const fromResult = await textInput('Source concept (ID or search term)');
          if (fromResult.cancelled || !fromResult.value) {
            console.log(colors.status.dim('\nCancelled.'));
            return;
          }

          // Try to resolve as ID first, then as label
          if (fromResult.value.startsWith('c_')) {
            const validFrom = await validateConceptId(client, fromResult.value);
            if (!validFrom.valid) {
              console.log(colors.status.error(validFrom.error!));
              return;
            }
            fromConceptId = validFrom.data!.concept_id;
            console.log(colors.status.success(`  → ${validFrom.data!.label}`));
          } else {
            const resolved = await resolveConceptByLabel(client, fromResult.value);
            if (!resolved.valid) {
              console.log(colors.status.error(resolved.error!));
              return;
            }
            fromConceptId = resolved.data!.concept_id;
            console.log(colors.status.success(`  → ${resolved.data!.label} (${resolved.data!.similarity.toFixed(0)}% match)`));
          }

          // Get target concept
          const toResult = await textInput('Target concept (ID or search term)');
          if (toResult.cancelled || !toResult.value) {
            console.log(colors.status.dim('\nCancelled.'));
            return;
          }

          if (toResult.value.startsWith('c_')) {
            const validTo = await validateConceptId(client, toResult.value);
            if (!validTo.valid) {
              console.log(colors.status.error(validTo.error!));
              return;
            }
            toConceptId = validTo.data!.concept_id;
            console.log(colors.status.success(`  → ${validTo.data!.label}`));
          } else {
            const resolved = await resolveConceptByLabel(client, toResult.value);
            if (!resolved.valid) {
              console.log(colors.status.error(resolved.error!));
              return;
            }
            toConceptId = resolved.data!.concept_id;
            console.log(colors.status.success(`  → ${resolved.data!.label} (${resolved.data!.similarity.toFixed(0)}% match)`));
          }

          // Get relationship type
          const typeResult = await textInput('Relationship type (e.g., IMPLIES, SUPPORTS)');
          if (typeResult.cancelled || !typeResult.value) {
            console.log(colors.status.dim('\nCancelled.'));
            return;
          }
          relationshipType = typeResult.value.toUpperCase().replace(/\s+/g, '_');

          // Validate vocab term
          const vocabResult = await validateVocabTerm(client, relationshipType, false);
          if (!vocabResult.valid) {
            console.log(colors.status.warning(`  Vocabulary term '${relationshipType}' not found.`));
            if (vocabResult.data?.similar_terms?.length) {
              console.log(colors.status.dim('  Similar terms:'));
              for (const t of vocabResult.data.similar_terms.slice(0, 3)) {
                console.log(colors.status.dim(`    - ${t.term} (${(t.similarity * 100).toFixed(0)}%)`));
              }
            }
            const createNew = await confirmYesNo('Create new vocabulary term?', false);
            if (!createNew) {
              console.log(colors.status.dim('\nCancelled.'));
              return;
            }
            // Will create with --create-vocab
            options.createVocab = true;
          }

          // Confidence
          const confResult = await textInput('Confidence (0-1)', '1.0');
          if (!confResult.cancelled && confResult.value) {
            confidence = parseFloat(confResult.value) || 1.0;
          }

          // Confirm
          console.log('\n' + separator());
          console.log(colors.ui.header('Summary:'));
          console.log(`  ${fromConceptId} -[${relationshipType}]-> ${toConceptId}`);
          console.log(`  ${colors.ui.key('Confidence:')} ${(confidence * 100).toFixed(0)}%`);
          console.log();

          const confirmed = await confirmYesNo('Create this edge?', true);
          if (!confirmed) {
            console.log(colors.status.dim('\nCancelled.'));
            return;
          }
        } else {
          // Non-interactive mode
          const hasFromId = !!options.from;
          const hasToId = !!options.to;
          const hasFromLabel = !!options.fromLabel;
          const hasToLabel = !!options.toLabel;

          if (!hasFromId && !hasFromLabel) {
            console.error(colors.status.error('✗ Missing required option: --from or --from-label'));
            process.exit(1);
          }
          if (!hasToId && !hasToLabel) {
            console.error(colors.status.error('✗ Missing required option: --to or --to-label'));
            process.exit(1);
          }
          if (!options.type) {
            console.error(colors.status.error('✗ Missing required option: --type'));
            process.exit(1);
          }

          // Resolve source concept
          if (hasFromId) {
            const validFrom = await validateConceptId(client, options.from);
            if (!validFrom.valid) {
              console.error(colors.status.error(`✗ From concept: ${validFrom.error}`));
              process.exit(1);
            }
            fromConceptId = validFrom.data!.concept_id;
          } else {
            const resolved = await resolveConceptByLabel(client, options.fromLabel);
            if (!resolved.valid) {
              console.error(colors.status.error(`✗ From concept: ${resolved.error}`));
              process.exit(1);
            }
            fromConceptId = resolved.data!.concept_id;
            if (!options.json) {
              console.log(colors.status.info(`Resolved --from-label "${options.fromLabel}" → ${resolved.data!.concept_id}`));
            }
          }

          // Resolve target concept
          if (hasToId) {
            const validTo = await validateConceptId(client, options.to);
            if (!validTo.valid) {
              console.error(colors.status.error(`✗ To concept: ${validTo.error}`));
              process.exit(1);
            }
            toConceptId = validTo.data!.concept_id;
          } else {
            const resolved = await resolveConceptByLabel(client, options.toLabel);
            if (!resolved.valid) {
              console.error(colors.status.error(`✗ To concept: ${resolved.error}`));
              process.exit(1);
            }
            toConceptId = resolved.data!.concept_id;
            if (!options.json) {
              console.log(colors.status.info(`Resolved --to-label "${options.toLabel}" → ${resolved.data!.concept_id}`));
            }
          }

          relationshipType = options.type.toUpperCase().replace(/\s+/g, '_');

          // Validate vocab term
          const vocabResult = await validateVocabTerm(client, relationshipType, options.createVocab);
          if (!vocabResult.valid) {
            console.error(colors.status.error(`✗ Relationship type: ${vocabResult.error}`));
            process.exit(1);
          }
          if (vocabResult.warning) {
            console.log(colors.status.warning(`⚠ ${vocabResult.warning}`));
          }
          relationshipType = vocabResult.data!.term;
        }

        // Create the edge
        const request: EdgeCreate = {
          from_concept_id: fromConceptId,
          to_concept_id: toConceptId,
          relationship_type: relationshipType,
          confidence,
          source: 'api_creation',
        };
        if (category) {
          request.category = category as any;
        }

        const result = await withSpinner('Creating edge...', async () => {
          return client.createEdge(request);
        });

        if (options.json) {
          console.log(JSON.stringify(result, null, 2));
          return;
        }

        console.log(colors.status.success(`\n✓ Created edge: ${result.edge_id}`));
        console.log(`  ${result.from_concept_id} -[${result.relationship_type}]-> ${result.to_concept_id}`);
      } catch (error: any) {
        handleCliError(error, 'Failed to create edge');
      }
    });
}

function createDeleteCommand(): Command {
  return new Command('delete')
    .description('Delete an edge by its composite key (from, type, to).')
    .argument('<from>', 'Source concept ID')
    .argument('<type>', 'Relationship type')
    .argument('<to>', 'Target concept ID')
    .option('-f, --force', 'Skip confirmation')
    .option('--json', 'Output as JSON')
    .action(async (from: string, type: string, to: string, options) => {
      try {
        const client = createClientFromEnv();

        if (!options.force) {
          console.log('\n' + separator());
          console.log(colors.status.warning('⚠️  Delete Edge'));
          console.log(separator());
          console.log();
          console.log(`  ${from} -[${type}]-> ${to}`);
          console.log();
          console.log(colors.status.warning('This action cannot be undone.'));
          console.log();

          const confirmed = await confirmYesNo('Delete this edge?', false);
          if (!confirmed) {
            console.log(colors.status.dim('\nCancelled.'));
            return;
          }
        }

        await client.deleteEdge(from, type, to);

        if (options.json) {
          console.log(JSON.stringify({ deleted: true, from, type, to }));
          return;
        }

        console.log(colors.status.success(`\n✓ Deleted edge: ${from} -[${type}]-> ${to}`));
      } catch (error: any) {
        handleCliError(error, 'Failed to delete edge', {
          notFoundMessage: `Edge not found: ${from} -[${type}]-> ${to}`,
        });
      }
    });
}
