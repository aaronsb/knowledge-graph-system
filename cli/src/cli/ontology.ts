/**
 * Ontology Management Commands
 */

import { Command } from 'commander';
import { createClientFromEnv } from '../api/client';
import * as colors from './colors';
import { coloredCount, separator } from './colors';
import { Table } from '../lib/table';
import { setCommandHelp } from './help-formatter';

export const ontologyCommand = setCommandHelp(
  new Command('ontology'),
  'Manage ontologies (knowledge domains)',
  'Manage ontologies (knowledge domains). Ontologies are named collections that organize concepts into knowledge domains. Each ontology groups related documents and concepts together, making it easier to organize and query knowledge by topic or project.'
)
  .alias('onto')  // Short alias
  .showHelpAfterError('(add --help for additional information)')
  .showSuggestionAfterError()
  .addCommand(
    new Command('list')
      .description('List all ontologies in the knowledge graph. Shows a table with ontology name, file count, chunk count, and concept count. Use this to get a bird\'s-eye view of all knowledge domains, verify ingestion results, and understand how knowledge is distributed.')
      .action(async () => {
        try {
          const client = createClientFromEnv();
          const result = await client.listOntologies();

          if (result.count === 0) {
            console.log(colors.status.warning('\n⚠ No ontologies found'));
            return;
          }

          console.log('\n' + colors.ui.title('📚 Ontologies in Knowledge Graph'));

          // Use Table system for consistent formatting
          const table = new Table({
            columns: [
              {
                header: 'Ontology',
                field: 'ontology',
                type: 'heading',
                width: 'flex',
                priority: 3
              },
              {
                header: 'State',
                field: 'lifecycle_state',
                type: 'text',
                width: 8,
                align: 'left'
              },
              {
                header: 'Files',
                field: 'file_count',
                type: 'count',
                width: 10,
                align: 'right'
              },
              {
                header: 'Chunks',
                field: 'source_count',
                type: 'count',
                width: 10,
                align: 'right'
              },
              {
                header: 'Concepts',
                field: 'concept_count',
                type: 'count',
                width: 12,
                align: 'right'
              }
            ]
          });

          table.print(result.ontologies.map(o => ({
            ...o,
            lifecycle_state: o.lifecycle_state ?? '—',
          })));
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to list ontologies'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('info')
      .description('Get detailed information about a specific ontology. Shows statistics (files, chunks, concepts, evidence, relationships) and lists all source files. Use this to understand ontology composition, verify expected files are present, and troubleshoot ingestion issues.')
      .showHelpAfterError()
      .argument('<name>', 'Ontology name')
      .action(async (name) => {
        try {
          const client = createClientFromEnv();
          const info = await client.getOntologyInfo(name);

          console.log('\n' + separator());
          console.log(colors.ui.title(`📖 Ontology: ${name}`));
          console.log(separator());

          console.log('\n' + colors.stats.section('Statistics'));
          console.log(`  ${colors.stats.label('Files:')} ${coloredCount(info.statistics.file_count)}`);
          console.log(`  ${colors.stats.label('Chunks:')} ${coloredCount(info.statistics.source_count)}`);
          console.log(`  ${colors.stats.label('Concepts:')} ${coloredCount(info.statistics.concept_count)}`);
          console.log(`  ${colors.stats.label('Evidence:')} ${coloredCount(info.statistics.instance_count)}`);
          console.log(`  ${colors.stats.label('Relationships:')} ${coloredCount(info.statistics.relationship_count)}`);

          // ADR-200: Node properties
          if (info.node) {
            console.log('\n' + colors.stats.section('Graph Node'));
            console.log(`  ${colors.stats.label('ID:')} ${info.node.ontology_id}`);
            console.log(`  ${colors.stats.label('State:')} ${info.node.lifecycle_state}`);
            console.log(`  ${colors.stats.label('Epoch:')} ${coloredCount(info.node.creation_epoch)}`);
            console.log(`  ${colors.stats.label('Embedding:')} ${info.node.has_embedding ? colors.status.success('yes') : colors.status.dim('no')}`);
            if (info.node.created_by) {
              console.log(`  ${colors.stats.label('Created By:')} ${info.node.created_by}`);
            }
            if (info.node.description) {
              console.log(`  ${colors.stats.label('Description:')} ${info.node.description}`);
            }
            if (info.node.search_terms.length > 0) {
              console.log(`  ${colors.stats.label('Search terms:')} ${info.node.search_terms.join(', ')}`);
            }
          }

          if (info.files.length > 0) {
            console.log('\n' + colors.ui.header('Files'));
            console.log(separator(80, '─'));
            info.files.forEach(file => {
              console.log(`  ${colors.ui.bullet('●')} ${colors.evidence.document(file)}`);
            });
          }
          console.log('\n' + separator());
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to get ontology info'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('files')
      .description('List files in a specific ontology with per-file statistics (chunks and concepts). Shows which files contributed most concepts and helps identify files that may need re-ingestion. Original file paths are preserved, though temporary paths may appear for text-based ingestion.')
      .showHelpAfterError()
      .argument('<name>', 'Ontology name')
      .action(async (name) => {
        try {
          const client = createClientFromEnv();
          const result = await client.getOntologyFiles(name);

          console.log('\n' + separator());
          console.log(colors.ui.title(`📁 Files in: ${name}`));
          console.log(separator());
          console.log(colors.status.success(`\n✓ Found ${result.count} files:\n`));

          result.files.forEach(file => {
            console.log(colors.evidence.document(file.file_path));
            console.log(`  ${colors.ui.key('Chunks:')} ${coloredCount(file.chunk_count)}`);
            console.log(`  ${colors.ui.key('Concepts:')} ${coloredCount(file.concept_count)}`);
            console.log();
          });
          console.log(separator());
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to get ontology files'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('create')
      .description('Create an ontology before ingesting any documents (ADR-200: directed growth). This pre-creates the Ontology graph node with an embedding, making the ontology discoverable in the vector space immediately. Useful for planning knowledge domains before populating them.')
      .showHelpAfterError()
      .argument('<name>', 'Ontology name')
      .option('-d, --description <text>', 'What this knowledge domain covers')
      .action(async (name, options) => {
        try {
          const client = createClientFromEnv();
          const result = await client.createOntology(name, options.description || '');

          console.log('\n' + separator());
          console.log(colors.status.success(`✓ Created ontology "${result.name}"`));
          console.log(separator());
          console.log(`  ${colors.ui.key('ID:')} ${result.ontology_id}`);
          console.log(`  ${colors.ui.key('State:')} ${result.lifecycle_state}`);
          console.log(`  ${colors.ui.key('Embedding:')} ${result.has_embedding ? colors.status.success('generated') : colors.status.dim('none')}`);
          if (result.description) {
            console.log(`  ${colors.ui.key('Description:')} ${result.description}`);
          }
          console.log('\n' + separator());
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to create ontology'));
          const detail = error.response?.data?.detail || error.message;
          console.error(colors.status.error(detail));

          if (detail.includes('already exists')) {
            console.error(colors.status.dim('\n  Hint: Use "kg ontology info ' + name + '" to see the existing ontology'));
          }

          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('lifecycle')
      .description('Change ontology lifecycle state (ADR-200 Phase 2). States: active (normal), pinned (immune to demotion), frozen (read-only — rejects ingest and rename).')
      .showHelpAfterError()
      .argument('<name>', 'Ontology name')
      .argument('<state>', 'Target state: active, pinned, or frozen')
      .action(async (name, state) => {
        const validStates = ['active', 'pinned', 'frozen'];
        if (!validStates.includes(state)) {
          console.error(colors.status.error(`✗ Invalid state "${state}". Must be one of: ${validStates.join(', ')}`));
          process.exit(1);
        }

        try {
          const client = createClientFromEnv();
          const result = await client.updateOntologyLifecycle(name, state as any);

          console.log('\n' + separator());
          if (result.previous_state === result.new_state) {
            console.log(colors.status.dim(`  Ontology "${name}" is already ${result.new_state} (no-op)`));
          } else {
            console.log(colors.status.success(`✓ Ontology "${name}" lifecycle: ${result.previous_state} → ${result.new_state}`));
          }
          console.log(separator());
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to update ontology lifecycle'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('rename')
      .description('Rename an ontology while preserving all its data (concepts, sources, relationships). This is a non-destructive operation useful for reorganization, archiving old ontologies, fixing typos, or improving clarity. Atomic transaction ensures all-or-nothing updates. Requires confirmation unless -y flag is used.')
      .showHelpAfterError()
      .argument('<old-name>', 'Current ontology name')
      .argument('<new-name>', 'New ontology name')
      .option('-y, --yes', 'Skip confirmation prompt')
      .action(async (oldName, newName, options) => {
        try {
          if (!options.yes) {
            console.log('\n' + separator());
            console.log(colors.status.warning('⚠️  Rename Ontology'));
            console.log(separator());
            console.log(`\nRename: ${colors.concept.label(oldName)} → ${colors.concept.label(newName)}`);
            console.log(`This will update all Source nodes in the ontology.`);
            console.log('\nUse ' + colors.ui.key('-y') + ' or ' + colors.ui.key('--yes') + ' flag to proceed\n');
            return;
          }

          const client = createClientFromEnv();
          const result = await client.renameOntology(oldName, newName);

          console.log('\n' + separator());
          console.log(colors.status.success(`✓ Renamed ontology "${result.old_name}" → "${result.new_name}"`));
          console.log(separator());
          console.log(`  ${colors.ui.key('Sources updated:')} ${coloredCount(result.sources_updated)}`);
          console.log('\n' + separator());
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to rename ontology'));
          const detail = error.response?.data?.detail || error.message;
          console.error(colors.status.error(detail));

          // Provide helpful hints based on error
          if (detail.includes('does not exist')) {
            console.error(colors.status.dim('\n  Hint: Use "kg ontology list" to see available ontologies'));
          } else if (detail.includes('already exists')) {
            console.error(colors.status.dim('\n  Hint: Choose a different name or delete the existing ontology first'));
          }

          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('delete')
      .description('Delete an ontology and ALL its data (concepts, sources, evidence instances, relationships). This is a DESTRUCTIVE operation that CANNOT BE UNDONE. Use this to remove test data, delete old projects, or free up space. Requires --force flag for confirmation. Consider alternatives: rename to add "Archive" suffix, or export data first (future feature).')
      .showHelpAfterError()
      .argument('<name>', 'Ontology name')
      .option('-f, --force', 'Skip confirmation and force deletion')
      .action(async (name, options) => {
        try {
          if (!options.force) {
            console.log('\n' + separator());
            console.log(colors.status.warning('⚠️  WARNING: This action cannot be undone!'));
            console.log(separator());
            console.log(`\nThis will delete all data for ontology ${colors.concept.label(name)}`);
            console.log('\nUse ' + colors.ui.key('--force') + ' flag to confirm deletion\n');
            return;
          }

          const client = createClientFromEnv();
          const result = await client.deleteOntology(name, true);

          console.log('\n' + separator());
          console.log(colors.status.success(`✓ Deleted ontology "${result.ontology}"`));
          console.log(separator());
          console.log(`  ${colors.ui.key('Sources deleted:')} ${coloredCount(result.sources_deleted)}`);
          if (result.orphaned_concepts_deleted > 0) {
            console.log(`  ${colors.ui.key('Orphaned concepts cleaned:')} ${coloredCount(result.orphaned_concepts_deleted)}`);
          }
          console.log('\n' + separator());
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to delete ontology'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  );
