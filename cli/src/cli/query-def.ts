/**
 * Query Definition Commands (ADR-083)
 *
 * CLI commands for managing saved query definitions.
 */

import { Command } from 'commander';
import { createClientFromEnv } from '../api/client';
import * as colors from './colors';
import { separator } from './colors';
import { Table } from '../lib/table';
import { setCommandHelp } from './help-formatter';

export const queryDefCommand = setCommandHelp(
  new Command('query-def'),
  'Manage saved query definitions',
  'Manage saved query definitions - recipes that can be re-executed to generate artifacts. Supports block diagrams, cypher queries, searches, polarity analyses, and connection paths.'
)
  .alias('qd')
  .showHelpAfterError('(add --help for additional information)')
  .showSuggestionAfterError()
  .addCommand(
    new Command('list')
      .description('List query definitions')
      .option('-t, --type <type>', 'Filter by type (block_diagram, cypher, search, polarity, connection)')
      .option('-l, --limit <n>', 'Maximum to return', '20')
      .action(async (options) => {
        try {
          const client = createClientFromEnv();
          const result = await client.listQueryDefinitions({
            definition_type: options.type,
            limit: parseInt(options.limit)
          });

          if (result.definitions.length === 0) {
            console.log(colors.status.warning('\nNo query definitions found'));
            return;
          }

          console.log('\n' + colors.ui.title('Query Definitions'));
          console.log(colors.status.dim(`  Showing ${result.definitions.length} of ${result.total}\n`));

          const table = new Table({
            columns: [
              { header: 'ID', field: 'id', type: 'count', width: 8, align: 'right' },
              { header: 'Type', field: 'definition_type', type: 'heading', width: 15 },
              { header: 'Name', field: 'name', type: 'text', width: 'flex' },
              { header: 'Updated', field: 'updated_at', type: 'timestamp', width: 12 }
            ]
          });

          table.print(result.definitions.map(d => ({
            ...d,
            updated_at: new Date(d.updated_at).toLocaleDateString()
          })));

        } catch (error: any) {
          console.error(colors.status.error('Failed to list query definitions'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('show')
      .description('Show a query definition')
      .argument('<id>', 'Definition ID')
      .action(async (id) => {
        try {
          const client = createClientFromEnv();
          const def = await client.getQueryDefinition(parseInt(id));

          console.log('\n' + separator());
          console.log(colors.ui.title(`Query Definition ${def.id}`));
          console.log(separator());

          console.log(`\n  ${colors.stats.label('Name:')} ${def.name}`);
          console.log(`  ${colors.stats.label('Type:')} ${colors.concept.label(def.definition_type)}`);
          console.log(`  ${colors.stats.label('Owner:')} ${def.owner_id ?? colors.status.dim('(system)')}`);
          console.log(`  ${colors.stats.label('Created:')} ${new Date(def.created_at).toLocaleString()}`);
          console.log(`  ${colors.stats.label('Updated:')} ${new Date(def.updated_at).toLocaleString()}`);

          console.log('\n' + colors.stats.section('Definition'));
          console.log(separator(80, '─'));
          console.log(JSON.stringify(def.definition, null, 2));
          console.log(separator(80, '─'));

        } catch (error: any) {
          console.error(colors.status.error('Failed to get query definition'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('create')
      .description('Create a query definition')
      .requiredOption('-n, --name <name>', 'Definition name')
      .requiredOption('-t, --type <type>', 'Type: block_diagram, cypher, search, polarity, connection')
      .requiredOption('-d, --definition <json>', 'Definition as JSON')
      .action(async (options) => {
        try {
          let definition: Record<string, any>;
          try {
            definition = JSON.parse(options.definition);
          } catch {
            console.error(colors.status.error('Invalid JSON for definition'));
            process.exit(1);
          }

          const client = createClientFromEnv();
          const result = await client.createQueryDefinition({
            name: options.name,
            definition_type: options.type,
            definition
          });

          console.log(colors.status.success(`Created query definition "${result.name}" (ID ${result.id})`));

        } catch (error: any) {
          console.error(colors.status.error('Failed to create query definition'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('delete')
      .description('Delete a query definition')
      .argument('<id>', 'Definition ID')
      .option('-f, --force', 'Skip confirmation')
      .action(async (id, options) => {
        try {
          if (!options.force) {
            console.log(colors.status.warning(`Use --force to confirm deletion of definition ${id}`));
            return;
          }

          const client = createClientFromEnv();
          await client.deleteQueryDefinition(parseInt(id));

          console.log(colors.status.success(`Deleted query definition ${id}`));

        } catch (error: any) {
          console.error(colors.status.error('Failed to delete query definition'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  );
