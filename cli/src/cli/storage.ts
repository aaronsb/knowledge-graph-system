/**
 * Storage Admin Commands
 *
 * Read-only diagnostics for S3-compatible object storage.
 * Provides independent visibility into stored objects, metadata,
 * integrity checks, and retention policies.
 */

import { Command } from 'commander';
import { createClientFromEnv } from '../api/client';
import * as colors from './colors';
import { coloredCount, separator } from './colors';
import { setCommandHelp } from './help-formatter';

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  const value = bytes / Math.pow(1024, i);
  return `${value.toFixed(i > 0 ? 1 : 0)} ${units[i]}`;
}

export const storageCommand = setCommandHelp(
  new Command('storage'),
  'Storage diagnostics and inspection',
  'Read-only diagnostics for S3-compatible object storage. List objects, inspect metadata, verify integrity after cascade deletes, and view retention policies. Useful for integration testing and debugging storage behavior.'
)
  .showHelpAfterError('(add --help for additional information)')
  .showSuggestionAfterError()
  .addCommand(
    new Command('health')
      .description('Check storage backend connectivity and bucket accessibility')
      .action(async () => {
        try {
          const client = createClientFromEnv();
          const health = await client.getStorageHealth();

          console.log('\n' + separator());
          console.log(colors.ui.title('Storage Health'));
          console.log(separator());

          if (health.healthy) {
            console.log(`\n  ${colors.status.success('✓ Storage healthy')}`);
          } else {
            console.log(`\n  ${colors.status.error('✗ Storage unhealthy')}`);
          }
          console.log(`  ${colors.ui.key('Bucket:')} ${colors.ui.value(health.bucket || 'unknown')}`);
          console.log(`  ${colors.ui.key('Endpoint:')} ${colors.ui.value(health.endpoint || 'unknown')}`);
          if (health.error) {
            console.log(`  ${colors.status.error('Error:')} ${health.error}`);
          }
          console.log('\n' + separator());
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to check storage health'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('stats')
      .description('Show storage usage statistics by category (sources, images, projections, artifacts)')
      .action(async () => {
        try {
          const client = createClientFromEnv();
          const stats = await client.getStorageStats();

          console.log('\n' + separator());
          console.log(colors.ui.title('Storage Statistics'));
          console.log(separator());

          console.log(`\n  ${colors.stats.label('Total Objects:')} ${coloredCount(stats.total_objects)}`);
          console.log(`  ${colors.stats.label('Total Size:')} ${colors.ui.value(formatBytes(stats.total_bytes))}`);

          console.log('\n' + colors.stats.section('By Category'));
          for (const [category, data] of Object.entries(stats.by_category) as [string, any][]) {
            const count = data.count || 0;
            const size = data.size_bytes || 0;
            console.log(`  ${colors.stats.label(category + ':')} ${coloredCount(count)} objects, ${colors.ui.value(formatBytes(size))}`);
          }

          console.log('\n' + separator());
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to get storage stats'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('list')
      .description('List objects in storage with optional prefix filter. Examples: kg storage list --prefix sources/ --limit 20')
      .option('-p, --prefix <prefix>', 'S3 key prefix filter (e.g. sources/, images/My_Ontology/)')
      .option('-l, --limit <n>', 'Maximum objects to return', parseInt, 50)
      .option('-o, --offset <n>', 'Number of objects to skip', parseInt, 0)
      .action(async (options) => {
        try {
          const client = createClientFromEnv();
          const result = await client.listStorageObjects({
            prefix: options.prefix || '',
            limit: options.limit,
            offset: options.offset,
          });

          console.log('\n' + separator());
          console.log(colors.ui.title('Storage Objects'));
          console.log(separator());

          if (result.prefix) {
            console.log(`\n  ${colors.ui.key('Prefix:')} ${colors.ui.value(result.prefix)}`);
          }
          console.log(`  ${colors.ui.key('Showing:')} ${colors.ui.value(`${result.offset + 1}-${result.offset + result.objects.length} of ${result.total}`)}`);

          if (result.objects.length === 0) {
            console.log(`\n  ${colors.status.dim('No objects found')}`);
          } else {
            console.log('\n' + separator(80, '─'));
            for (const obj of result.objects) {
              const modified = new Date(obj.last_modified).toLocaleString();
              console.log(`  ${colors.ui.value(obj.key)}`);
              console.log(`    ${colors.status.dim(`${formatBytes(obj.size)}  ${modified}  ${obj.etag}`)}`);
            }
          }

          if (result.total > result.offset + result.objects.length) {
            const nextOffset = result.offset + result.limit;
            console.log(`\n  ${colors.status.dim(`More objects available. Use --offset ${nextOffset} to see next page.`)}`);
          }

          console.log('\n' + separator());
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to list storage objects'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('inspect')
      .description('Inspect metadata for a single object without downloading content. Use the full S3 key from "kg storage list".')
      .argument('<key>', 'S3 object key (e.g. sources/My_Ontology/abc123.md)')
      .action(async (key: string) => {
        try {
          const client = createClientFromEnv();
          const metadata = await client.getStorageObjectMetadata(key);

          console.log('\n' + separator());
          console.log(colors.ui.title('Object Metadata'));
          console.log(separator());

          console.log(`\n  ${colors.ui.key('Key:')} ${colors.ui.value(metadata.key)}`);
          console.log(`  ${colors.ui.key('Size:')} ${colors.ui.value(formatBytes(metadata.size))}`);
          console.log(`  ${colors.ui.key('Content-Type:')} ${colors.ui.value(metadata.content_type || 'unknown')}`);
          console.log(`  ${colors.ui.key('Last Modified:')} ${colors.ui.value(new Date(metadata.last_modified).toLocaleString())}`);
          console.log(`  ${colors.ui.key('ETag:')} ${colors.status.dim(metadata.etag)}`);

          const customMeta = metadata.metadata;
          if (customMeta && Object.keys(customMeta).length > 0) {
            console.log('\n' + colors.stats.section('Custom Metadata'));
            for (const [k, v] of Object.entries(customMeta)) {
              console.log(`  ${colors.ui.key(k + ':')} ${colors.ui.value(String(v))}`);
            }
          }

          console.log('\n' + separator());
        } catch (error: any) {
          if (error.response?.status === 404) {
            console.error(colors.status.error(`✗ Object not found: ${key}`));
          } else {
            console.error(colors.status.error('✗ Failed to inspect object'));
            console.error(colors.status.error(error.response?.data?.detail || error.message));
          }
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('integrity')
      .description('Cross-reference S3 objects against graph nodes. Finds orphaned objects (in S3 but not graph) and missing objects (in graph but not S3). Essential for verifying cascade deletes.')
      .option('--ontology <name>', 'Scope check to a specific ontology')
      .option('--category <type>', 'Storage category: sources, images', 'sources')
      .action(async (options) => {
        try {
          const client = createClientFromEnv();
          const result = await client.checkStorageIntegrity({
            ontology: options.ontology,
            category: options.category,
          });

          console.log('\n' + separator());
          console.log(colors.ui.title('Storage Integrity Check'));
          console.log(separator());

          if (result.ontology) {
            console.log(`\n  ${colors.ui.key('Ontology:')} ${colors.ui.value(result.ontology)}`);
          }
          console.log(`  ${colors.ui.key('Category:')} ${colors.ui.value(result.category)}`);
          console.log(`  ${colors.ui.key('Checked At:')} ${colors.status.dim(new Date(result.checked_at).toLocaleString())}`);

          console.log(`\n  ${colors.stats.label('S3 Objects:')} ${coloredCount(result.s3_objects)}`);
          console.log(`  ${colors.stats.label('Graph References:')} ${coloredCount(result.graph_references)}`);

          if (result.is_consistent) {
            console.log(`\n  ${colors.status.success('✓ Storage is consistent — no orphans or missing objects')}`);
          } else {
            if (result.orphaned_in_s3.length > 0) {
              console.log(`\n  ${colors.status.warning(`⚠ ${result.orphaned_in_s3.length} orphaned in S3 (no graph reference):`)}`);
              for (const key of result.orphaned_in_s3) {
                console.log(`    ${colors.status.dim(key)}`);
              }
            }

            if (result.missing_from_s3.length > 0) {
              console.log(`\n  ${colors.status.error(`✗ ${result.missing_from_s3.length} missing from S3 (graph points to absent object):`)}`);
              for (const key of result.missing_from_s3) {
                console.log(`    ${colors.status.dim(key)}`);
              }
            }
          }

          console.log('\n' + separator());
        } catch (error: any) {
          console.error(colors.status.error('✗ Integrity check failed'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('retention')
      .description('Show current retention policy configuration for each storage category')
      .action(async () => {
        try {
          const client = createClientFromEnv();
          const result = await client.getStorageRetention();

          console.log('\n' + separator());
          console.log(colors.ui.title('Retention Policies'));
          console.log(separator());

          for (const [category, policy] of Object.entries(result.policies) as [string, any][]) {
            console.log(`\n  ${colors.stats.section(category)}`);
            for (const [key, value] of Object.entries(policy)) {
              console.log(`    ${colors.ui.key(key + ':')} ${colors.ui.value(String(value))}`);
            }
          }

          console.log('\n' + separator());
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to get retention policies'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  );
