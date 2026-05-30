/**
 * Catalog Browse Commands (ADR-501)
 *
 * Filesystem-like browse of the knowledge graph's ontology -> document ->
 * concept hierarchy. Answers "what's actually in here?" structurally, as
 * opposed to semantic search (`kg search`).
 *
 *   kg catalog ls                 → list ontologies (root)
 *   kg catalog ls <id>            → list children of a node (kind auto-resolved)
 *   kg catalog ls <id> -q neural  → filter children by name fragment
 *   kg catalog stat <id>          → single-node detail (the stat call)
 *
 * Every subcommand supports --json for scripting / machine consumption.
 */

import { Command } from 'commander';
import { createClientFromEnv } from '../api/client';
import * as colors from './colors';
import { coloredCount, separator } from './colors';
import { setCommandHelp } from './help-formatter';
import type { CatalogNode } from '../types';

/** Pluralize a node kind for summary lines (ontology -> ontologies). */
function pluralKind(kind: string): string {
  return kind === 'ontology' ? 'ontologies' : `${kind}s`;
}

/** Glyph per node kind — keeps the tree scannable at a glance. */
function kindGlyph(kind: string): string {
  switch (kind) {
    case 'ontology': return '▸';
    case 'document': return '▤';
    case 'concept': return '•';
    default: return '-';
  }
}

/** Render one catalog row in the formatted (non-JSON) view. */
function printNode(node: CatalogNode): void {
  const glyph = kindGlyph(node.kind);
  const count =
    node.child_count != null && node.kind !== 'concept'
      ? colors.status.dim(`  (${node.child_count})`)
      : '';
  const ct = node.content_type ? colors.status.dim(` [${node.content_type}]`) : '';
  console.log(`  ${glyph} ${colors.ui.value(node.name)}${count}${ct}`);
  console.log(`      ${colors.status.dim(node.id)}`);
}

export const catalogCommand = setCommandHelp(
  new Command('catalog'),
  'Browse the graph: ontologies → documents → concepts',
  'Deterministic, filesystem-like browse of what is stored in the knowledge graph. ' +
    'Walk from ontologies down to documents and concepts, filter by name fragment, ' +
    'and inspect single nodes. Distinct from "kg search" (semantic) and "kg storage" ' +
    '(raw S3 admin). Add --json to any subcommand for machine-readable output.'
)
  .showHelpAfterError('(add --help for additional information)')
  .showSuggestionAfterError()
  .addCommand(
    new Command('ls')
      .description('List children of a node, or root ontologies if no id given')
      .argument('[id]', 'Parent node id (ontology or document). Omit to list ontologies.')
      .option('-k, --kind <kind>', 'Parent kind hint (ontology|document) if id is ambiguous')
      .option('-q, --query <fragment>', 'Filter children by case-insensitive name fragment')
      .option('-s, --sort <field>', 'Sort: name | child_count | created', 'name')
      .option('-l, --limit <n>', 'Max results', '100')
      .option('-o, --offset <n>', 'Pagination offset', '0')
      .option('--json', 'Output raw JSON instead of formatted text for scripting')
      .action(async (id: string | undefined, options: any) => {
        try {
          const client = createClientFromEnv();
          const result = await client.listCatalogChildren({
            parent: id,
            parent_kind: options.kind,
            q: options.query,
            sort: options.sort,
            limit: parseInt(options.limit, 10),
            offset: parseInt(options.offset, 10),
          });

          if (options.json) {
            console.log(JSON.stringify(result, null, 2));
            return;
          }

          console.log('\n' + separator());
          const where = id ? `children of ${id}` : 'ontologies';
          console.log(colors.ui.title(`Catalog — ${where}`));
          console.log(separator());

          if (result.nodes.length === 0) {
            console.log(`\n  ${colors.status.dim('(empty)')}`);
          } else {
            console.log('');
            result.nodes.forEach(printNode);
          }

          const shown = result.offset + result.nodes.length;
          const label =
            result.total === 1 ? result.child_kind : pluralKind(result.child_kind);
          console.log(
            `\n  ${colors.stats.label(label + ':')} ` +
              `${coloredCount(result.total)} total` +
              (shown < result.total ? colors.status.dim(`  (showing ${result.offset + 1}-${shown})`) : '')
          );
          if (result.query) {
            console.log(`  ${colors.stats.label('Filter:')} ${colors.ui.value(result.query)}`);
          }
          if (result.stale) {
            console.log(`  ${colors.status.dim('⚠ index lagging current graph epoch — counts may be slightly behind')}`);
          }
          console.log('\n' + separator());
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to list catalog'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('stat')
      .description('Show full metadata for a single catalog node')
      .argument('<id>', 'Node id (ontology_id, document_id, or concept_id)')
      .option('-k, --kind <kind>', 'Disambiguate kind if id collides across kinds')
      .option('--json', 'Output raw JSON instead of formatted text for scripting')
      .action(async (id: string, options: any) => {
        try {
          const client = createClientFromEnv();
          const node = await client.getCatalogNode(id, options.kind);

          if (options.json) {
            console.log(JSON.stringify(node, null, 2));
            return;
          }

          console.log('\n' + separator());
          console.log(colors.ui.title(`${kindGlyph(node.kind)} ${node.name}`));
          console.log(separator());
          console.log(`\n  ${colors.ui.key('Kind:')} ${colors.ui.value(node.kind)}`);
          console.log(`  ${colors.ui.key('ID:')} ${colors.ui.value(node.id)}`);
          if (node.parent_id) {
            console.log(`  ${colors.ui.key('Parent:')} ${colors.ui.value(node.parent_id)}`);
          }
          if (node.child_count != null && node.kind !== 'concept') {
            console.log(`  ${colors.ui.key('Children:')} ${coloredCount(node.child_count)}`);
          }
          if (node.content_type) {
            console.log(`  ${colors.ui.key('Content type:')} ${colors.ui.value(node.content_type)}`);
          }
          if (node.graph_epoch != null) {
            console.log(`  ${colors.ui.key('Indexed at epoch:')} ${colors.ui.value(String(node.graph_epoch))}`);
          }
          const props = Object.entries(node.properties || {});
          if (props.length > 0) {
            console.log(`\n  ${colors.stats.section('Properties')}`);
            for (const [k, v] of props) {
              console.log(`    ${colors.ui.key(k + ':')} ${colors.ui.value(String(v))}`);
            }
          }
          console.log('\n' + separator());
        } catch (error: any) {
          if (error.response?.status === 404) {
            console.error(colors.status.error(`✗ Catalog node '${id}' not found`));
          } else {
            console.error(colors.status.error('✗ Failed to stat catalog node'));
            console.error(colors.status.error(error.response?.data?.detail || error.message));
          }
          process.exit(1);
        }
      })
  );
