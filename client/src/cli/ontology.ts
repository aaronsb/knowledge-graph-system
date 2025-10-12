/**
 * Ontology Management Commands
 */

import { Command } from 'commander';
import { createClientFromEnv } from '../api/client';
import * as colors from './colors';
import { coloredCount, separator } from './colors';
import { Table } from '../lib/table';

export const ontologyCommand = new Command('ontology')
  .alias('onto')  // Short alias
  .description('Manage ontologies (knowledge domains)')
  .showHelpAfterError('(add --help for additional information)')
  .showSuggestionAfterError()
  .addCommand(
    new Command('list')
      .description('List all ontologies')
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

          table.print(result.ontologies);
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to list ontologies'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('info')
      .description('Get detailed information about an ontology')
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
      .description('List files in an ontology')
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
    new Command('rename')
      .description('Rename an ontology')
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
      .description('Delete an ontology and all its data')
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
