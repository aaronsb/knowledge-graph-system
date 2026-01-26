/**
 * Concept CRUD Commands (ADR-089 Phase 2)
 *
 * Direct creation, listing, and management of concepts in the knowledge graph.
 * Supports both non-interactive (flags) and interactive (-i) modes.
 */

import { Command } from 'commander';
import { createClientFromEnv } from '../api/client';
import * as colors from './colors';
import { separator } from './colors';
import { Table } from '../lib/table';
import { setCommandHelp } from './help-formatter';
import { MatchingMode, CreationMethod } from '../types';
import {
  textInput,
  selectOption,
  confirmYesNo,
  withSpinner,
  handleCliError,
} from '../lib/interactive';

export const conceptCommand = setCommandHelp(
  new Command('concept'),
  'Manage concepts in the knowledge graph',
  'Create, list, show, and delete concepts. Concepts are the fundamental nodes in the knowledge graph. When creating concepts, the description is embedded and similarity-matched against existing concepts (same as automatic ingestion). Use matching modes to control duplicate handling.'
)
  .alias('c')
  .showHelpAfterError('(add --help for additional information)')
  .showSuggestionAfterError()
  .addCommand(createListCommand())
  .addCommand(createShowCommand())
  .addCommand(createCreateCommand())
  .addCommand(createDeleteCommand());

function createListCommand(): Command {
  return new Command('list')
    .description('List concepts with optional filters. Shows concept ID, label, ontology, and creation method.')
    .option('--ontology <name>', 'Filter by ontology')
    .option('--label <text>', 'Filter by label (contains)')
    .option('--creation-method <method>', 'Filter by creation method (cli, mcp, api, llm_extraction, import)')
    .option('--limit <n>', 'Maximum results (default: 50)', '50')
    .option('--offset <n>', 'Pagination offset', '0')
    .option('--json', 'Output as JSON')
    .action(async (options) => {
      try {
        const client = createClientFromEnv();
        const params = {
          ontology: options.ontology,
          label_contains: options.label,
          creation_method: options.creationMethod,
          limit: parseInt(options.limit, 10),
          offset: parseInt(options.offset, 10),
        };

        const result = await client.listConceptsCRUD(params);

        if (options.json) {
          console.log(JSON.stringify(result, null, 2));
          return;
        }

        if (result.concepts.length === 0) {
          console.log(colors.status.warning('\nNo concepts found.'));
          if (options.ontology) {
            console.log(colors.status.dim(`  Ontology filter: ${options.ontology}`));
          }
          return;
        }

        console.log('\n' + colors.ui.title('📚 Concepts'));
        console.log(separator());
        console.log(colors.status.dim(`Showing ${result.concepts.length} of ${result.total} concepts\n`));

        const table = new Table({
          columns: [
            { header: 'ID', field: 'concept_id', type: 'concept_id', width: 15 },
            { header: 'Label', field: 'label', type: 'heading', width: 'flex', priority: 3 },
            { header: 'Ontology', field: (row: any) => row.ontology || '-', type: 'text', width: 20 },
            { header: 'Created By', field: (row: any) => row.creation_method || '-', type: 'text', width: 15 },
          ],
        });

        table.print(result.concepts as any);

        if (result.total > result.concepts.length) {
          console.log(colors.status.dim(`\nUse --offset ${result.offset + result.concepts.length} to see more`));
        }
      } catch (error: any) {
        handleCliError(error, 'Failed to list concepts');
      }
    });
}

function createShowCommand(): Command {
  return new Command('show')
    .description('Show detailed information about a concept by ID.')
    .argument('<id>', 'Concept ID (e.g., c_abc123)')
    .option('--json', 'Output as JSON')
    .action(async (id: string, options) => {
      try {
        const client = createClientFromEnv();
        const concept = await client.getConceptById(id);

        if (options.json) {
          console.log(JSON.stringify(concept, null, 2));
          return;
        }

        console.log('\n' + separator());
        console.log(colors.ui.title(`📖 Concept: ${concept.label}`));
        console.log(separator());
        console.log();
        console.log(`${colors.ui.key('ID:')} ${colors.concept.id(concept.concept_id)}`);
        console.log(`${colors.ui.key('Label:')} ${colors.concept.label(concept.label)}`);
        if (concept.description) {
          console.log(`${colors.ui.key('Description:')} ${concept.description}`);
        }
        if (concept.ontology) {
          console.log(`${colors.ui.key('Ontology:')} ${concept.ontology}`);
        }
        console.log(`${colors.ui.key('Creation Method:')} ${concept.creation_method || 'unknown'}`);
        console.log(`${colors.ui.key('Has Embedding:')} ${concept.has_embedding ? colors.status.success('Yes') : colors.status.warning('No')}`);

        if (concept.search_terms && concept.search_terms.length > 0) {
          console.log(`${colors.ui.key('Search Terms:')} ${concept.search_terms.join(', ')}`);
        }

        console.log('\n' + separator());
      } catch (error: any) {
        handleCliError(error, 'Failed to get concept', {
          notFoundMessage: `Concept not found: ${id}`,
        });
      }
    });
}

function createCreateCommand(): Command {
  return new Command('create')
    .description('Create a new concept. Description is embedded and similarity-matched against existing concepts.')
    .option('--label <name>', 'Concept label (required)')
    .option('--ontology <name>', 'Target ontology (required)')
    .option('--description <text>', 'Concept description (used for embedding match)')
    .option('--search-terms <terms>', 'Comma-separated search terms')
    .option('--matching-mode <mode>', 'auto|force_create|match_only (default: auto)', 'auto')
    .option('--json', 'Output as JSON')
    .option('-i, --interactive', 'Guided wizard mode')
    .option('-y, --yes', 'Skip confirmation prompts')
    .action(async (options) => {
      try {
        const client = createClientFromEnv();

        let label: string;
        let ontology: string;
        let description: string | undefined;
        let searchTerms: string[] | undefined;
        let matchingMode: MatchingMode = (options.matchingMode as MatchingMode) || 'auto';

        if (options.interactive) {
          // Interactive wizard mode
          console.log('\n' + colors.ui.title('📝 Create New Concept'));
          console.log(separator());
          console.log();

          // Get ontology
          const ontologies = await client.listOntologies();
          if (ontologies.ontologies.length === 0) {
            console.log(colors.status.warning('No ontologies found. Create one first with kg ingest.'));
            return;
          }

          const ontologyResult = await selectOption(
            'Select ontology:',
            ontologies.ontologies.map((o) => ({
              label: o.ontology,
              value: o.ontology,
              description: `${o.concept_count} concepts, ${o.file_count} files`,
            }))
          );

          if (ontologyResult.cancelled || !ontologyResult.selected) {
            console.log(colors.status.dim('\nCancelled.'));
            return;
          }
          ontology = ontologyResult.selected.value;

          // Get label
          const labelResult = await textInput('Label');
          if (labelResult.cancelled || !labelResult.value) {
            console.log(colors.status.dim('\nCancelled.'));
            return;
          }
          label = labelResult.value;

          // Get description
          const descResult = await textInput('Description (optional, used for similarity matching)');
          if (!descResult.cancelled && descResult.value) {
            description = descResult.value;
          }

          // Get search terms
          const termsResult = await textInput('Search terms (optional, comma-separated)');
          if (!termsResult.cancelled && termsResult.value) {
            searchTerms = termsResult.value.split(',').map((t) => t.trim()).filter(Boolean);
          }

          // Matching mode
          const modeResult = await selectOption('Matching mode:', [
            { label: 'auto', value: 'auto', description: 'Match existing if similar, create if not (recommended)' },
            { label: 'force_create', value: 'force_create', description: 'Always create new, skip matching' },
            { label: 'match_only', value: 'match_only', description: 'Only link to existing, fail if no match' },
          ]);

          if (modeResult.cancelled) {
            console.log(colors.status.dim('\nCancelled.'));
            return;
          }
          matchingMode = (modeResult.selected?.value as MatchingMode) || 'auto';

          // Confirm
          console.log('\n' + separator());
          console.log(colors.ui.header('Summary:'));
          console.log(`  ${colors.ui.key('Ontology:')} ${ontology}`);
          console.log(`  ${colors.ui.key('Label:')} ${label}`);
          if (description) console.log(`  ${colors.ui.key('Description:')} ${description}`);
          if (searchTerms?.length) console.log(`  ${colors.ui.key('Search Terms:')} ${searchTerms.join(', ')}`);
          console.log(`  ${colors.ui.key('Matching Mode:')} ${matchingMode}`);
          console.log();

          const confirmed = await confirmYesNo('Create this concept?', true);
          if (!confirmed) {
            console.log(colors.status.dim('\nCancelled.'));
            return;
          }
        } else {
          // Non-interactive mode - require flags
          if (!options.label) {
            console.error(colors.status.error('✗ Missing required option: --label'));
            console.log(colors.status.dim('\nUse -i for interactive mode, or provide required options:'));
            console.log(colors.status.dim('  kg concept create --label "My Concept" --ontology my-ontology'));
            process.exit(1);
          }
          if (!options.ontology) {
            console.error(colors.status.error('✗ Missing required option: --ontology'));
            console.log(colors.status.dim('\nUse -i for interactive mode, or provide required options:'));
            console.log(colors.status.dim('  kg concept create --label "My Concept" --ontology my-ontology'));
            process.exit(1);
          }

          label = options.label;
          ontology = options.ontology;
          description = options.description;
          searchTerms = options.searchTerms?.split(',').map((t: string) => t.trim()).filter(Boolean);
        }

        // Create the concept
        const result = await withSpinner('Creating concept...', async () => {
          return client.createConcept({
            label,
            ontology,
            description,
            search_terms: searchTerms,
            matching_mode: matchingMode,
            creation_method: 'cli' as CreationMethod,
          });
        });

        if (options.json) {
          console.log(JSON.stringify(result, null, 2));
          return;
        }

        console.log();
        if (result.matched_existing) {
          console.log(colors.status.info(`≈ Matched existing concept: ${result.concept_id}`));
          console.log(colors.status.dim('  (Use --matching-mode force_create to create new anyway)'));
        } else {
          console.log(colors.status.success(`✓ Created concept: ${result.concept_id}`));
        }
        console.log(`  ${colors.ui.key('Label:')} ${result.label}`);
        console.log(`  ${colors.ui.key('Has Embedding:')} ${result.has_embedding ? 'Yes' : 'No'}`);
      } catch (error: any) {
        handleCliError(error, 'Failed to create concept');
      }
    });
}

function createDeleteCommand(): Command {
  return new Command('delete')
    .description('Delete a concept by ID. Requires --force flag or interactive confirmation.')
    .argument('<id>', 'Concept ID to delete')
    .option('--cascade', 'Also delete orphaned synthetic sources')
    .option('-f, --force', 'Skip confirmation')
    .option('--json', 'Output as JSON')
    .action(async (id: string, options) => {
      try {
        const client = createClientFromEnv();

        // First, get the concept to show what will be deleted
        let concept;
        try {
          concept = await client.getConceptById(id);
        } catch (error: any) {
          handleCliError(error, 'Failed to get concept', {
            notFoundMessage: `Concept not found: ${id}`,
          });
          return; // handleCliError exits, but TypeScript needs this
        }

        if (!options.force) {
          console.log('\n' + separator());
          console.log(colors.status.warning('⚠️  Delete Concept'));
          console.log(separator());
          console.log();
          console.log(`  ${colors.ui.key('ID:')} ${concept.concept_id}`);
          console.log(`  ${colors.ui.key('Label:')} ${concept.label}`);
          if (concept.ontology) {
            console.log(`  ${colors.ui.key('Ontology:')} ${concept.ontology}`);
          }
          console.log();
          console.log(colors.status.warning('This action cannot be undone.'));
          console.log();

          const confirmed = await confirmYesNo('Delete this concept?', false);
          if (!confirmed) {
            console.log(colors.status.dim('\nCancelled.'));
            return;
          }
        }

        await client.deleteConcept(id, options.cascade);

        if (options.json) {
          console.log(JSON.stringify({ deleted: true, concept_id: id }));
          return;
        }

        console.log(colors.status.success(`\n✓ Deleted concept: ${id}`));
      } catch (error: any) {
        handleCliError(error, 'Failed to delete concept');
      }
    });
}
