/**
 * Database Commands
 */

import { Command } from 'commander';
import { createClientFromEnv } from '../api/client';
import * as colors from './colors';
import { coloredCount, separator } from './colors';
import { setCommandHelp } from './help-formatter';

export const databaseCommand = setCommandHelp(
  new Command('database'),
  'Database operations and information',
  'Database operations and information. Provides read-only queries for PostgreSQL + Apache AGE database health, statistics, and connection details.'
)
  .alias('db')  // Short alias
  .showHelpAfterError('(add --help for additional information)')
  .showSuggestionAfterError()
  .addCommand(
    new Command('stats')
      .description('Show comprehensive database statistics including node counts (Concepts, Sources, Instances) and relationship type breakdown. Useful for monitoring graph growth and understanding extraction patterns.')
      .action(async () => {
        try {
          const client = createClientFromEnv();
          const stats = await client.getDatabaseStats();

          console.log('\n' + separator());
          console.log(colors.ui.title('📊 Database Statistics'));
          console.log(separator());

          console.log('\n' + colors.stats.section('Nodes'));
          console.log(`  ${colors.stats.label('Concepts:')} ${coloredCount(stats.nodes.concepts)}`);
          console.log(`  ${colors.stats.label('Sources:')} ${coloredCount(stats.nodes.sources)}`);
          console.log(`  ${colors.stats.label('Instances:')} ${coloredCount(stats.nodes.instances)}`);

          console.log('\n' + colors.stats.section('Relationships'));
          console.log(`  ${colors.stats.label('Total:')} ${coloredCount(stats.relationships.total)}`);

          if (stats.relationships.by_type.length > 0) {
            console.log('\n' + colors.stats.section('By Type'));
            stats.relationships.by_type.forEach(rel => {
              const relColor = colors.getRelationshipColor(rel.rel_type);
              console.log(`  ${relColor(rel.rel_type)}: ${coloredCount(rel.count)}`);
            });
          }

          // Display graph metrics counters (ADR-065)
          if (stats.metrics) {
            console.log('\n' + colors.stats.section('Graph Metrics'));

            // Show vocabulary change counter
            if (stats.metrics.vocabulary_change_counter) {
              const vocabMetric = stats.metrics.vocabulary_change_counter;
              const deltaColor = vocabMetric.delta === 0
                ? colors.status.success
                : vocabMetric.delta < 5
                  ? colors.ui.value
                  : colors.status.warning;

              console.log(`  ${colors.stats.label('Vocabulary Changes:')} ${coloredCount(vocabMetric.counter)}`);
              console.log(`  ${colors.stats.label('Since Last Measurement:')} ${deltaColor(vocabMetric.delta + ' changes')}`);

              if (vocabMetric.last_measured_at) {
                const measuredDate = new Date(vocabMetric.last_measured_at).toLocaleString();
                console.log(`  ${colors.stats.label('Last Measured:')} ${colors.status.dim(measuredDate)}`);
              }
            }

            // Show epistemic measurement counter
            if (stats.metrics.epistemic_measurement_counter) {
              const epistemicMetric = stats.metrics.epistemic_measurement_counter;
              console.log(`  ${colors.stats.label('Epistemic Measurements:')} ${coloredCount(epistemicMetric.counter)}`);
            }
          }

          console.log('\n' + separator());
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to get database stats'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('info')
      .description('Show database connection information including URI, username, connection status, PostgreSQL version, and Apache AGE edition. Use for troubleshooting connection issues and capturing environment details for bug reports.')
      .action(async () => {
        try {
          const client = createClientFromEnv();
          const info = await client.getDatabaseInfo();

          console.log('\n' + separator());
          console.log(colors.ui.title('🔌 Database Connection'));
          console.log(separator());
          console.log(`\n${colors.ui.key('URI:')} ${colors.ui.value(info.uri)}`);
          console.log(`${colors.ui.key('User:')} ${colors.ui.value(info.user)}`);

          if (info.connected) {
            console.log(`${colors.ui.key('Status:')} ${colors.status.success('✓ Connected')}`);
            if (info.version) {
              console.log(`${colors.ui.key('Version:')} ${colors.ui.value(info.version)}`);
            }
            if (info.edition) {
              console.log(`${colors.ui.key('Edition:')} ${colors.ui.value(info.edition)}`);
            }
          } else {
            console.log(`${colors.ui.key('Status:')} ${colors.status.error('✗ Disconnected')}`);
            if (info.error) {
              console.log(`${colors.status.error('Error:')} ${info.error}`);
            }
          }
          console.log('\n' + separator());
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to get database info'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('health')
      .description('Check database health and connectivity with detailed checks for: connectivity (PostgreSQL reachable), age_extension (Apache AGE loaded), and graph (schema exists). Use for startup verification and diagnosing which component is failing.')
      .action(async () => {
        try {
          const client = createClientFromEnv();
          const health = await client.getDatabaseHealth();

          console.log('\n' + separator());
          console.log(colors.ui.title('💚 Database Health'));
          console.log(separator());

          const statusColor = health.status === 'healthy'
            ? colors.status.success
            : health.status === 'degraded'
              ? colors.status.warning
              : colors.status.error;

          const statusIcon = health.status === 'healthy' ? '✓' : health.status === 'degraded' ? '⚠' : '✗';
          console.log(`\n${colors.ui.key('Status:')} ${statusColor(`${statusIcon} ${health.status.toUpperCase()}`)}`);
          console.log(`${colors.ui.key('Responsive:')} ${health.responsive ? colors.status.success('✓ Yes') : colors.status.error('✗ No')}`);

          if (Object.keys(health.checks).length > 0) {
            console.log('\n' + colors.ui.header('Health Checks'));
            console.log(separator(80, '─'));
            for (const [checkName, checkData] of Object.entries(health.checks)) {
              if (typeof checkData === 'object' && checkData.status) {
                const checkColor = checkData.status === 'ok' ? colors.status.success : colors.status.warning;
                const checkIcon = checkData.status === 'ok' ? '✓' : '⚠';
                const countInfo = checkData.count !== undefined ? ` ${colors.status.dim(`(${checkData.count})`)}` : '';
                console.log(`  ${colors.ui.key(checkName + ':')} ${checkColor(checkIcon + ' ' + checkData.status)}${countInfo}`);
              } else {
                console.log(`  ${colors.ui.key(checkName + ':')} ${colors.status.success(checkData)}`);
              }
            }
          }

          if (health.error) {
            console.log('\n' + colors.status.error(`Error: ${health.error}`));
          }
          console.log('\n' + separator());
        } catch (error: any) {
          console.error(colors.status.error('✗ Health check failed'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('query')
      .description('Execute a custom openCypher/GQL query (ADR-048). Use --namespace for safety: "concept" operates on Concept/Source/Instance nodes (default namespace), "vocab" operates on VocabType/VocabCategory nodes, omit for raw queries (mixed types, use with caution). Examples: kg db query "MATCH (c:Concept) WHERE c.label =~ \'.*recursive.*\' RETURN c.label LIMIT 5" --namespace concept')
      .argument('<query>', 'openCypher/GQL query string')
      .option('--namespace <type>', 'Namespace for safety: "concept", "vocab", or omit for raw (ADR-048)')
      .option('--params <json>', 'Query parameters as JSON string (e.g., \'{"min_score": 0.8}\')')
      .option('--limit <n>', 'Convenience: Append LIMIT to query (overrides query LIMIT)', parseInt)
      .action(async (query: string, options) => {
        try {
          const client = createClientFromEnv();

          // Add LIMIT if provided via --limit flag
          let finalQuery = query;
          if (options.limit) {
            // Simple append - user can use this or put LIMIT in query
            if (!query.toUpperCase().includes('LIMIT')) {
              finalQuery = `${query} LIMIT ${options.limit}`;
            }
          }

          // Parse params if provided
          let params = undefined;
          if (options.params) {
            try {
              params = JSON.parse(options.params);
            } catch (e) {
              console.error(colors.status.error('✗ Invalid JSON in --params'));
              process.exit(1);
            }
          }

          // Determine namespace (undefined means null for raw queries)
          const namespace = options.namespace || null;

          console.log('\n' + separator());
          console.log(colors.ui.title('🔍 Cypher Query'));
          console.log(separator());
          console.log(`\n${colors.ui.key('Query:')} ${colors.status.dim(finalQuery)}`);

          if (namespace) {
            console.log(`${colors.ui.key('Namespace:')} ${colors.status.success(namespace)} ${colors.status.dim('(namespace-safe, ADR-048)')}`);
          } else {
            console.log(`${colors.ui.key('Namespace:')} ${colors.status.warning('raw')} ${colors.status.dim('(no label injection, use with caution)')}`);
          }

          if (params) {
            console.log(`${colors.ui.key('Parameters:')} ${colors.status.dim(JSON.stringify(params))}`);
          }

          const result = await client.executeCypherQuery(finalQuery, params, namespace);

          if (!result.success) {
            console.log('\n' + colors.status.error('✗ Query failed'));
            console.log(colors.status.error(result.error || 'Unknown error'));
            console.log('\n' + separator());
            process.exit(1);
          }

          if (result.warning) {
            console.log('\n' + colors.status.warning(`⚠ ${result.warning}`));
          }

          console.log('\n' + colors.stats.section(`Results (${result.rows_returned} rows)`));
          console.log(separator(80, '─'));

          if (result.rows_returned === 0) {
            console.log(colors.status.dim('  No results returned'));
          } else {
            // Pretty-print results as table
            result.results.forEach((row: any, idx: number) => {
              console.log(`\n${colors.stats.label(`Row ${idx + 1}:`)}`);
              for (const [key, value] of Object.entries(row)) {
                const valueStr = typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value);
                console.log(`  ${colors.ui.key(key + ':')} ${colors.ui.value(valueStr)}`);
              }
            });
          }

          console.log('\n' + separator());
        } catch (error: any) {
          console.error(colors.status.error('✗ Query execution failed'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('counters')
      .description('Show graph metrics counters organized by type (ADR-079). Counters track: snapshot counts (concepts, edges, sources, vocab_types), activity counters (ingestion, consolidation events), and legacy structure counters. Use --refresh to update from current graph state.')
      .option('--refresh', 'Refresh counters from current graph state before displaying')
      .action(async (options) => {
        try {
          const client = createClientFromEnv();

          // If refresh requested, do that first
          if (options.refresh) {
            console.log('\n' + colors.status.dim('Refreshing counters from graph state...'));
            const refreshResult = await client.refreshDatabaseCounters();
            if (refreshResult.changed_count > 0) {
              console.log(colors.status.success(`✓ ${refreshResult.changed_count} counters updated`));
            } else {
              console.log(colors.status.dim('  No counters changed'));
            }
          }

          const data = await client.getDatabaseCounters();

          console.log('\n' + separator());
          console.log(colors.ui.title('📊 Graph Metrics Counters'));
          console.log(separator());

          // Display current snapshot
          if (data.current_snapshot) {
            console.log('\n' + colors.stats.section('Current Graph Snapshot'));
            const snap = data.current_snapshot;
            console.log(`  ${colors.stats.label('Concepts:')} ${coloredCount(snap.concepts)}`);
            console.log(`  ${colors.stats.label('Edges:')} ${coloredCount(snap.edges)}`);
            console.log(`  ${colors.stats.label('Sources:')} ${coloredCount(snap.sources)}`);
            console.log(`  ${colors.stats.label('Vocab Types:')} ${coloredCount(snap.vocab_types)}`);
            console.log(`  ${colors.stats.label('Total Objects:')} ${coloredCount(snap.total_objects)}`);
          }

          // Display counters by type
          const counters = data.counters;

          if (counters.snapshot && counters.snapshot.length > 0) {
            console.log('\n' + colors.stats.section('Snapshot Counters'));
            console.log(colors.status.dim('  (Current counts from COUNT(*) queries)'));
            for (const c of counters.snapshot) {
              const deltaStr = c.delta !== 0 ? ` (${c.delta > 0 ? '+' : ''}${c.delta})` : '';
              const deltaColor = c.delta === 0 ? colors.status.dim : c.delta > 0 ? colors.status.success : colors.status.warning;
              console.log(`  ${colors.stats.label(c.name + ':')} ${coloredCount(c.value)}${deltaColor(deltaStr)}`);
            }
          }

          if (counters.activity && counters.activity.length > 0) {
            console.log('\n' + colors.stats.section('Activity Counters'));
            console.log(colors.status.dim('  (Application-incremented event counters)'));
            for (const c of counters.activity) {
              const deltaStr = c.delta !== 0 ? ` (${c.delta > 0 ? '+' : ''}${c.delta})` : '';
              const deltaColor = c.delta === 0 ? colors.status.dim : c.delta > 0 ? colors.status.success : colors.status.warning;
              console.log(`  ${colors.stats.label(c.name + ':')} ${coloredCount(c.value)}${deltaColor(deltaStr)}`);
            }
          }

          if (counters.legacy_structure && counters.legacy_structure.length > 0) {
            console.log('\n' + colors.stats.section('Legacy Structure Counters'));
            console.log(colors.status.dim('  (Historical counters, kept for compatibility)'));
            for (const c of counters.legacy_structure) {
              console.log(`  ${colors.stats.label(c.name + ':')} ${coloredCount(c.value)}`);
            }
          }

          console.log('\n' + separator());
          console.log(colors.status.dim('  Tip: Use --refresh to update counters from current graph state'));
          console.log('\n' + separator());
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to get graph counters'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  );
