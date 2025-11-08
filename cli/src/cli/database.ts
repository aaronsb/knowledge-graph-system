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
  );
