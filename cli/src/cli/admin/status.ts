/**
 * Admin Status Command
 * System health and status monitoring
 */

import { Command } from 'commander';
import { createClientFromEnv } from '../../api/client';
import * as colors from '../colors';
import { separator, coloredCount } from '../colors';

export function createStatusCommand(): Command {
  return new Command('status')
    .description('Show comprehensive system health status (Docker containers, database connections, environment configuration, job scheduler)')
    .action(async () => {
      try {
        const client = createClientFromEnv();

        console.log('\n' + separator());
        console.log(colors.ui.title('📊 System Status'));
        console.log(separator());

        const status = await client.getSystemStatus();

        // Docker
        console.log('\n' + colors.ui.header('Docker'));
        if (status.docker.running) {
          console.log(`  ${colors.status.success('✓')} PostgreSQL container running`);
          if (status.docker.container_name) {
            console.log(`    ${colors.ui.key('Container:')} ${colors.ui.value(status.docker.container_name)}`);
          }
          if (status.docker.status) {
            console.log(`    ${colors.ui.key('Status:')} ${colors.ui.value(status.docker.status)}`);
          }
        } else {
          console.log(`  ${colors.status.error('✗')} PostgreSQL not running`);
          console.log(`    ${colors.status.dim('Run: docker-compose up -d')}`);
        }

        // Database Connection
        console.log('\n' + colors.ui.header('Database Connection'));
        if (status.database_connection.connected) {
          console.log(`  ${colors.status.success('✓')} Connected to PostgreSQL + AGE`);
          console.log(`    ${colors.ui.key('URI:')} ${colors.ui.value(status.database_connection.uri)}`);
        } else {
          console.log(`  ${colors.status.error('✗')} Cannot connect to PostgreSQL`);
          if (status.database_connection.error) {
            console.log(`    ${colors.status.error(status.database_connection.error)}`);
          }
        }

        // Database Stats
        if (status.database_stats) {
          console.log('\n' + colors.ui.header('Database Statistics'));
          console.log(`  ${colors.ui.key('Concepts:')} ${coloredCount(status.database_stats.concepts)}`);
          console.log(`  ${colors.ui.key('Sources:')} ${coloredCount(status.database_stats.sources)}`);
          console.log(`  ${colors.ui.key('Instances:')} ${coloredCount(status.database_stats.instances)}`);
          console.log(`  ${colors.ui.key('Relationships:')} ${coloredCount(status.database_stats.relationships)}`);
        }

        // Python Environment
        console.log('\n' + colors.ui.header('Python Environment'));
        if (status.python_env.venv_exists) {
          console.log(`  ${colors.status.success('✓')} Virtual environment exists`);
          if (status.python_env.python_version) {
            console.log(`    ${colors.ui.key('Version:')} ${colors.ui.value(status.python_env.python_version)}`);
          }
        } else {
          console.log(`  ${colors.status.error('✗')} Virtual environment not found`);
          console.log(`    ${colors.status.dim('Run: ./scripts/setup.sh')}`);
        }

        // Configuration
        console.log('\n' + colors.ui.header('Configuration'));
        if (status.configuration.env_exists) {
          console.log(`  ${colors.status.success('✓')} .env file exists`);

          const anthropicStatus = status.configuration.anthropic_key_configured
            ? colors.status.success('configured')
            : colors.status.error('missing');
          console.log(`    ${colors.ui.key('ANTHROPIC_API_KEY:')} ${anthropicStatus}`);

          const openaiStatus = status.configuration.openai_key_configured
            ? colors.status.success('configured')
            : colors.status.error('missing');
          console.log(`    ${colors.ui.key('OPENAI_API_KEY:')} ${openaiStatus}`);
        } else {
          console.log(`  ${colors.status.error('✗')} .env file not found`);
          console.log(`    ${colors.status.dim('Run: ./scripts/setup.sh')}`);
        }

        // Access Points
        if (status.neo4j_browser_url) {
          console.log('\n' + colors.ui.header('Access Points'));
          console.log(`  ${colors.ui.key('PostgreSQL:')} ${colors.ui.value(status.neo4j_browser_url)}`);
          console.log(`  ${colors.ui.key('Credentials:')} ${colors.status.dim(process.env.POSTGRES_USER || 'admin')}/${colors.status.dim('password')}`);
        }

        console.log('\n' + separator() + '\n');

      } catch (error: any) {
        console.error(colors.status.error('✗ Failed to get system status'));
        console.error(colors.status.error(error.response?.data?.detail || error.message));
        process.exit(1);
      }
    });
}
