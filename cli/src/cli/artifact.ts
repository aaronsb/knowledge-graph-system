/**
 * Artifact Management Commands (ADR-083)
 *
 * CLI commands for artifact persistence - storing and retrieving computed results.
 */

import { Command } from 'commander';
import { createClientFromEnv } from '../api/client';
import * as colors from './colors';
import { coloredCount, separator } from './colors';
import { Table } from '../lib/table';
import { setCommandHelp } from './help-formatter';

/**
 * Standard hint shown when an artifact is stale, pointing at the reconcile path.
 * "Stale" means the graph has advanced past the epoch the artifact was computed
 * at (ADR-207) — the payload is still readable, just no longer current.
 */
const STALE_HINT = (id: string | number) =>
  colors.status.dim(`  Stale: the graph changed since this was computed. ` +
    `Recompute with "kg artifact regenerate ${id}".`);

export const artifactCommand = setCommandHelp(
  new Command('artifact'),
  'Manage your artifacts (stored computation results)',
  'Manage artifacts - persistent storage for computed results like polarity analyses, projections, and query results. ' +
  'Each artifact records the graph epoch it was computed at, so the platform can tell you when one has gone stale ' +
  '(the graph changed underneath it) and recompute it on request (ADR-207).\n\n' +
  'This is the user-facing surface for the results you create. For backend object-storage diagnostics ' +
  '(S3 buckets, stored objects, integrity, retention) see the admin command "kg storage".'
)
  .alias('art')
  .showHelpAfterError('(add --help for additional information)')
  .showSuggestionAfterError()
  .addCommand(
    new Command('list')
      .description('List your artifacts. Shows metadata without payloads for efficiency. Filter by type, representation, or ontology.')
      .option('-t, --type <type>', 'Filter by artifact type (polarity_analysis, projection, etc.)')
      .option('-r, --representation <rep>', 'Filter by representation/source (cli, polarity_explorer, etc.)')
      .option('-o, --ontology <name>', 'Filter by ontology')
      .option('-l, --limit <n>', 'Maximum artifacts to return', '20')
      .option('--offset <n>', 'Skip N artifacts (for pagination)', '0')
      .option('-v, --verbose', 'Show storage tier (inline/garage) — an implementation detail hidden by default')
      .option('-j, --json', 'Output raw JSON instead of formatted table')
      .action(async (options) => {
        try {
          const client = createClientFromEnv();
          const result = await client.listArtifacts({
            artifact_type: options.type,
            representation: options.representation,
            ontology: options.ontology,
            limit: parseInt(options.limit),
            offset: parseInt(options.offset),
          });

          if (options.json) {
            console.log(JSON.stringify(result, null, 2));
            return;
          }

          if (result.artifacts.length === 0) {
            console.log(colors.status.warning('\n⚠ No artifacts found'));
            if (options.type || options.representation || options.ontology) {
              console.log(colors.status.dim('  Try removing filters to see all artifacts'));
            }
            return;
          }

          console.log('\n' + colors.ui.title('📦 Artifacts'));
          console.log(colors.status.dim(`  Showing ${result.artifacts.length} of ${result.total} artifacts\n`));

          const columns: any[] = [
            {
              header: 'ID',
              field: 'id',
              type: 'count',
              width: 8,
              align: 'right'
            },
            {
              header: 'Type',
              field: 'artifact_type',
              type: 'heading',
              width: 20
            },
            {
              header: 'Name',
              field: 'name',
              type: 'text',
              width: 'flex',
              priority: 2
            },
            {
              header: 'Fresh',
              field: 'is_fresh',
              type: 'text',
              width: 8,
              customFormat: (val: boolean) => val ? colors.status.success('✓') : colors.status.warning('○')
            },
            {
              header: 'Created',
              field: 'created_at',
              type: 'timestamp',
              width: 12
            }
          ];

          // Storage tier is an implementation detail (inline vs Garage), not a
          // user concern — surface it only under --verbose (ADR-207 audience split).
          if (options.verbose) {
            columns.splice(4, 0, {
              header: 'Storage',
              field: 'storage',
              type: 'text',
              width: 10
            });
          }

          const table = new Table({ columns });

          // Transform for display
          const displayData = result.artifacts.map(a => ({
            ...a,
            name: a.name || colors.status.dim('(unnamed)'),
            storage: a.has_inline_result ? 'inline' : 'garage',
            created_at: new Date(a.created_at).toLocaleDateString()
          }));

          table.print(displayData);

          // Point users at the reconcile path when any listed artifact is stale.
          const staleCount = result.artifacts.filter(a => !a.is_fresh).length;
          if (staleCount > 0) {
            console.log(colors.status.dim(
              `\n  ○ ${staleCount} stale (graph changed since computed). ` +
              `Recompute one with "kg artifact regenerate <id>", or clear stale ones with "kg artifact cleanup".`
            ));
          }

          if (result.total > result.artifacts.length) {
            console.log(colors.status.dim(`\n  Use --offset ${result.offset + result.limit} to see more`));
          }
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to list artifacts'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('show')
      .description('Show artifact metadata by ID. Does not include the payload - use "payload" command for that.')
      .argument('<id>', 'Artifact ID')
      .option('-v, --verbose', 'Show storage tier (inline/garage) — an implementation detail hidden by default')
      .action(async (id, options) => {
        try {
          const client = createClientFromEnv();
          const artifact = await client.getArtifact(parseInt(id));

          console.log('\n' + separator());
          console.log(colors.ui.title(`📦 Artifact ${artifact.id}`));
          console.log(separator());

          console.log('\n' + colors.stats.section('Metadata'));
          console.log(`  ${colors.stats.label('Type:')} ${colors.concept.label(artifact.artifact_type)}`);
          console.log(`  ${colors.stats.label('Representation:')} ${artifact.representation}`);
          console.log(`  ${colors.stats.label('Name:')} ${artifact.name || colors.status.dim('(unnamed)')}`);
          console.log(`  ${colors.stats.label('Owner ID:')} ${artifact.owner_id ?? colors.status.dim('(none)')}`);

          console.log('\n' + colors.stats.section('Freshness'));
          console.log(`  ${colors.stats.label('Graph Epoch:')} ${artifact.graph_epoch}`);
          console.log(`  ${colors.stats.label('Is Fresh:')} ${artifact.is_fresh ? colors.status.success('Yes ✓') : colors.status.warning('No (graph has changed)')}`);
          if (!artifact.is_fresh) {
            console.log(STALE_HINT(artifact.id));
          }

          // Storage tier is an implementation detail; show it only under --verbose
          // (ADR-207 audience split — "kg storage" is the admin diagnostic surface).
          if (options.verbose) {
            console.log('\n' + colors.stats.section('Storage'));
            console.log(`  ${colors.stats.label('Location:')} ${artifact.has_inline_result ? 'Inline (PostgreSQL)' : 'Garage S3'}`);
            if (artifact.garage_key) {
              console.log(`  ${colors.stats.label('Garage Key:')} ${colors.status.dim(artifact.garage_key)}`);
            }
          }

          console.log('\n' + colors.stats.section('Timestamps'));
          console.log(`  ${colors.stats.label('Created:')} ${new Date(artifact.created_at).toLocaleString()}`);
          if (artifact.expires_at) {
            console.log(`  ${colors.stats.label('Expires:')} ${new Date(artifact.expires_at).toLocaleString()}`);
          }

          if (artifact.ontology) {
            console.log('\n' + colors.stats.section('Context'));
            console.log(`  ${colors.stats.label('Ontology:')} ${artifact.ontology}`);
          }

          if (artifact.concept_ids && artifact.concept_ids.length > 0) {
            console.log(`  ${colors.stats.label('Concepts:')} ${artifact.concept_ids.length} concept(s)`);
          }

          if (artifact.parameters && Object.keys(artifact.parameters).length > 0) {
            console.log('\n' + colors.stats.section('Parameters'));
            for (const [key, value] of Object.entries(artifact.parameters)) {
              const displayValue = typeof value === 'object' ? JSON.stringify(value) : String(value);
              console.log(`  ${colors.stats.label(key + ':')} ${displayValue}`);
            }
          }

          console.log('\n' + separator());
          console.log(colors.status.dim(`  Use "kg artifact payload ${artifact.id}" to retrieve the full payload`));
          console.log(separator());
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to get artifact'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('payload')
      .description('Get artifact with full payload. For large artifacts stored in Garage, this fetches from object storage.')
      .argument('<id>', 'Artifact ID')
      .option('-j, --json', 'Output raw JSON payload only')
      .action(async (id, options) => {
        try {
          const client = createClientFromEnv();
          const artifact = await client.getArtifactPayload(parseInt(id));

          if (options.json) {
            // Raw JSON output for piping
            console.log(JSON.stringify(artifact.payload, null, 2));
            return;
          }

          console.log('\n' + separator());
          console.log(colors.ui.title(`📦 Artifact ${artifact.id} Payload`));
          console.log(separator());

          console.log(`\n  ${colors.stats.label('Type:')} ${artifact.artifact_type}`);
          console.log(`  ${colors.stats.label('Name:')} ${artifact.name || colors.status.dim('(unnamed)')}`);
          console.log(`  ${colors.stats.label('Fresh:')} ${artifact.is_fresh ? colors.status.success('Yes') : colors.status.warning('No')}`);

          console.log('\n' + colors.stats.section('Payload'));
          console.log(separator(80, '─'));
          console.log(JSON.stringify(artifact.payload, null, 2));
          console.log(separator(80, '─'));
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to get artifact payload'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('create')
      .description('Create a test artifact (for API validation). Creates a simple artifact with provided parameters.')
      .requiredOption('-t, --type <type>', 'Artifact type (polarity_analysis, projection, query_result, etc.)')
      .option('-n, --name <name>', 'Human-readable name')
      .option('-o, --ontology <name>', 'Associated ontology')
      .option('--payload <json>', 'JSON payload (default: simple test payload)', '{"test": true, "created_via": "cli"}')
      .action(async (options) => {
        try {
          let payload: Record<string, any>;
          try {
            payload = JSON.parse(options.payload);
          } catch (e) {
            console.error(colors.status.error('✗ Invalid JSON payload'));
            process.exit(1);
          }

          const client = createClientFromEnv();
          const result = await client.createArtifact({
            artifact_type: options.type,
            representation: 'cli',
            name: options.name,
            parameters: { created_via: 'kg artifact create' },
            payload,
            ontology: options.ontology,
          });

          console.log('\n' + separator());
          console.log(colors.status.success(`✓ Created artifact ${result.id}`));
          console.log(separator());
          console.log(`  ${colors.ui.key('Type:')} ${result.artifact_type}`);
          console.log(`  ${colors.ui.key('Name:')} ${result.name || colors.status.dim('(unnamed)')}`);
          console.log(`  ${colors.ui.key('Storage:')} ${result.storage_location}`);
          console.log(`  ${colors.ui.key('Graph Epoch:')} ${result.graph_epoch}`);
          if (result.garage_key) {
            console.log(`  ${colors.ui.key('Garage Key:')} ${colors.status.dim(result.garage_key)}`);
          }
          console.log('\n' + separator());
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to create artifact'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('delete')
      .description('Delete an artifact. Removes both database record and any Garage-stored payload.')
      .argument('<id>', 'Artifact ID')
      .option('-f, --force', 'Skip confirmation prompt')
      .action(async (id, options) => {
        try {
          if (!options.force) {
            console.log('\n' + separator());
            console.log(colors.status.warning('⚠️  Delete Artifact'));
            console.log(separator());
            console.log(`\nThis will delete artifact ${colors.concept.label(id)}`);
            console.log('If stored in Garage, the object will also be removed.');
            console.log('\nUse ' + colors.ui.key('--force') + ' flag to confirm deletion\n');
            return;
          }

          const client = createClientFromEnv();
          await client.deleteArtifact(parseInt(id));

          console.log('\n' + separator());
          console.log(colors.status.success(`✓ Deleted artifact ${id}`));
          console.log(separator());
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to delete artifact'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('regenerate')
      .description('Recompute a stale artifact from its stored parameters (ADR-207). Enqueues an auto-approved job; the result is saved as a NEW artifact and the original is preserved. Supported types: polarity_analysis, projection.')
      .alias('regen')
      .argument('<id>', 'Artifact ID')
      .action(async (id) => {
        try {
          const client = createClientFromEnv();
          const result = await client.regenerateArtifact(parseInt(id));

          console.log('\n' + separator());
          console.log(colors.status.success(`✓ Regeneration queued for artifact ${id}`));
          console.log(separator());
          console.log(`  ${colors.stats.label('Job ID:')} ${result.job_id}`);
          console.log(`  ${colors.stats.label('Status:')} ${result.status}`);
          console.log(colors.status.dim(
            `\n  Track it with "kg job status ${result.job_id}". ` +
            `The recomputed result is saved as a new artifact — the original is preserved.`
          ));
          console.log(separator());
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to regenerate artifact'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('cleanup')
      .description('Remove stale artifacts in bulk — those whose graph epoch is behind the current graph (ADR-207). Previews by default; pass --force to delete. Regeneratable types can be recomputed afterward with "kg artifact regenerate".')
      .option('-t, --type <type>', 'Only clean up artifacts of this type')
      .option('-o, --ontology <name>', 'Only clean up artifacts in this ontology')
      .option('-f, --force', 'Actually delete (default is a dry-run preview)')
      .action(async (options) => {
        try {
          const client = createClientFromEnv();

          // Page through all matching artifacts (list returns max 500 per page)
          // and collect the stale ones. Freshness is computed server-side per row.
          const pageSize = 500;
          const stale: any[] = [];
          let offset = 0;
          let total = Infinity;
          while (offset < total) {
            const page = await client.listArtifacts({
              artifact_type: options.type,
              ontology: options.ontology,
              limit: pageSize,
              offset,
            });
            total = page.total;
            for (const a of page.artifacts) {
              if (!a.is_fresh) stale.push(a);
            }
            if (page.artifacts.length === 0) break;
            offset += page.artifacts.length;
          }

          if (stale.length === 0) {
            console.log(colors.status.success('\n✓ No stale artifacts to clean up'));
            return;
          }

          console.log('\n' + separator());
          console.log(colors.ui.title(`🧹 ${options.force ? 'Cleaning up' : 'Stale artifacts (preview)'}`));
          console.log(separator());
          for (const a of stale) {
            const label = a.name ? `${a.name} ` : '';
            console.log(`  ${colors.concept.label('#' + a.id)} ${colors.status.dim(a.artifact_type)} ${label}${colors.status.dim('(epoch ' + a.graph_epoch + ')')}`);
          }

          if (!options.force) {
            console.log('\n' + colors.status.warning(`⚠ ${stale.length} stale artifact(s) would be deleted.`));
            console.log(colors.status.dim('  Re-run with --force to delete them, or recompute one with "kg artifact regenerate <id>".'));
            console.log(separator());
            return;
          }

          let deleted = 0;
          const failures: Array<{ id: number; error: string }> = [];
          for (const a of stale) {
            try {
              await client.deleteArtifact(a.id);
              deleted++;
            } catch (err: any) {
              failures.push({ id: a.id, error: err.response?.data?.detail || err.message });
            }
          }

          console.log('\n' + separator());
          console.log(colors.status.success(`✓ Deleted ${deleted} stale artifact(s)`));
          if (failures.length > 0) {
            console.log(colors.status.error(`✗ Failed to delete ${failures.length}:`));
            for (const f of failures) {
              console.log(colors.status.error(`  #${f.id}: ${f.error}`));
            }
          }
          console.log(separator());
          if (failures.length > 0) process.exit(1);
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to clean up artifacts'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  );
