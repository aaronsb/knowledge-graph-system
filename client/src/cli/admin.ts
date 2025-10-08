/**
 * Admin Commands
 *
 * System administration: status, backup, restore, reset
 */

import { Command } from 'commander';
import * as readline from 'readline';
import * as fs from 'fs';
import * as path from 'path';
import { createClientFromEnv } from '../api/client';
import { getConfig } from '../lib/config';
import * as colors from './colors';
import { separator } from './colors';
import { configureColoredHelp } from './help-formatter';

/**
 * Prompt for input from user
 */
function prompt(question: string): Promise<string> {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
  });

  return new Promise((resolve) => {
    rl.question(question, (answer) => {
      rl.close();
      resolve(answer);
    });
  });
}

/**
 * Prompt for password (hidden input)
 */
function promptPassword(question: string): Promise<string> {
  return new Promise((resolve) => {
    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout
    });

    // @ts-ignore - _writeToOutput exists but not in types
    rl._writeToOutput = function(stringToWrite: string) {
      if (stringToWrite.charCodeAt(0) === 13) { // carriage return
        // @ts-ignore
        rl.output.write('\n');
      } else {
        // Don't display password characters
      }
    };

    rl.question(question, (password) => {
      rl.close();
      console.log(); // New line after password input
      resolve(password);
    });
  });
}

// ========== Status Command ==========

const statusCommand = new Command('status')
  .description('Show system status (Docker, database, environment)')
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
        console.log(`  ${colors.status.success('✓')} Neo4j container running`);
        if (status.docker.container_name) {
          console.log(`    ${colors.ui.key('Container:')} ${colors.ui.value(status.docker.container_name)}`);
        }
        if (status.docker.status) {
          console.log(`    ${colors.ui.key('Status:')} ${colors.ui.value(status.docker.status)}`);
        }
      } else {
        console.log(`  ${colors.status.error('✗')} Neo4j not running`);
        console.log(`    ${colors.status.dim('Run: docker-compose up -d')}`);
      }

      // Database Connection
      console.log('\n' + colors.ui.header('Database Connection'));
      if (status.database_connection.connected) {
        console.log(`  ${colors.status.success('✓')} Connected to Neo4j`);
        console.log(`    ${colors.ui.key('URI:')} ${colors.ui.value(status.database_connection.uri)}`);
      } else {
        console.log(`  ${colors.status.error('✗')} Cannot connect to Neo4j`);
        if (status.database_connection.error) {
          console.log(`    ${colors.status.error(status.database_connection.error)}`);
        }
      }

      // Database Stats
      if (status.database_stats) {
        console.log('\n' + colors.ui.header('Database Statistics'));
        console.log(`  ${colors.ui.key('Concepts:')} ${colors.coloredCount(status.database_stats.concepts)}`);
        console.log(`  ${colors.ui.key('Sources:')} ${colors.coloredCount(status.database_stats.sources)}`);
        console.log(`  ${colors.ui.key('Instances:')} ${colors.coloredCount(status.database_stats.instances)}`);
        console.log(`  ${colors.ui.key('Relationships:')} ${colors.coloredCount(status.database_stats.relationships)}`);
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
      if (status.neo4j_browser_url || status.bolt_url) {
        console.log('\n' + colors.ui.header('Access Points'));
        if (status.neo4j_browser_url) {
          console.log(`  ${colors.ui.key('Neo4j Browser:')} ${colors.ui.value(status.neo4j_browser_url)}`);
        }
        if (status.bolt_url) {
          console.log(`  ${colors.ui.key('Bolt Protocol:')} ${colors.ui.value(status.bolt_url)}`);
        }
        console.log(`  ${colors.ui.key('Credentials:')} ${colors.status.dim('neo4j/password')}`);
      }

      console.log('\n' + separator() + '\n');

    } catch (error: any) {
      console.error(colors.status.error('✗ Failed to get system status'));
      console.error(colors.status.error(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

// ========== Backup Command ==========

const backupCommand = new Command('backup')
  .description('Create a database backup')
  .option('--type <type>', 'Backup type: "full" or "ontology"')
  .option('--ontology <name>', 'Ontology name (required if type is ontology)')
  .option('--output <filename>', 'Custom output filename')
  .action(async (options) => {
    try {
      const client = createClientFromEnv();

      console.log('\n' + separator());
      console.log(colors.ui.title('💾 Database Backup'));
      console.log(separator());

      let backupType: 'full' | 'ontology' = 'full';
      let ontologyName: string | undefined;

      // Interactive mode if no options provided
      if (!options.type) {
        console.log('\n' + colors.ui.key('Backup Options:'));
        console.log('  1) Full database backup (all ontologies)');
        console.log('  2) Specific ontology backup');
        console.log('');

        const choice = await prompt('Select option [1-2]: ');

        if (choice === '1') {
          backupType = 'full';
        } else if (choice === '2') {
          backupType = 'ontology';
          ontologyName = await prompt('Enter ontology name: ');
        } else {
          console.log(colors.status.error('Invalid option'));
          process.exit(1);
        }
      } else {
        backupType = options.type as 'full' | 'ontology';
        ontologyName = options.ontology;
      }

      // Validate
      if (backupType === 'ontology' && !ontologyName) {
        console.error(colors.status.error('✗ Ontology name required for ontology backup'));
        process.exit(1);
      }

      console.log(colors.status.info('\nCreating backup...'));

      // TODO: Implement ADR-015 streaming architecture
      // See: docs/ADR-015-backup-restore-streaming.md
      //
      // Current limitation: API creates backup on server-side
      // Target: API should stream backup data to client
      //   1. API creates backup in memory/temp
      //   2. Stream backup JSON to client with progress bar
      //   3. Client saves to configured directory (~/.local/share/kg/backups)
      //   4. API deletes temp file immediately
      const result = await client.createBackup({
        backup_type: backupType,
        ontology_name: ontologyName,
        output_filename: options.output
      });

      console.log('\n' + separator());
      console.log(colors.status.success('✓ Backup Complete'));
      console.log(colors.status.warning('⚠ Backup created on server-side (./backups)'));
      console.log(colors.status.dim('   TODO: Download to configured directory'));
      console.log(separator());
      console.log(`\n  ${colors.ui.key('File:')} ${colors.ui.value(result.backup_file)}`);
      console.log(`  ${colors.ui.key('Size:')} ${colors.ui.value(result.file_size_mb.toFixed(2) + ' MB')}`);

      if (result.statistics) {
        console.log(`\n  ${colors.ui.header('Statistics:')}`);
        Object.entries(result.statistics).forEach(([key, value]) => {
          console.log(`    ${colors.ui.key(key + ':')} ${colors.coloredCount(value)}`);
        });
      }

      if (result.integrity_assessment?.has_external_deps) {
        console.log(`\n  ${colors.status.warning('⚠ This backup has external dependencies')}`);
        console.log(`    ${colors.status.dim('External references:')} ${result.integrity_assessment.external_dependencies_count}`);
      }

      console.log('\n' + separator() + '\n');

    } catch (error: any) {
      console.error(colors.status.error('✗ Backup failed'));
      console.error(colors.status.error(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

// ========== List Backups Command ==========

const listBackupsCommand = new Command('list-backups')
  .description('List available backup files from configured directory')
  .action(async () => {
    try {
      const config = getConfig();
      const backupDir = config.getBackupDir();

      // Ensure backup directory exists
      if (!fs.existsSync(backupDir)) {
        console.log('\n' + separator());
        console.log(colors.ui.title('📁 Available Backups'));
        console.log(separator());
        console.log(`\n  ${colors.status.dim('No backups found - directory does not exist')}`);
        console.log(`  ${colors.status.dim(`Directory: ${backupDir}`)}`);
        console.log(`  ${colors.status.dim('Run "kg admin backup" to create your first backup')}\n`);
        console.log(separator() + '\n');
        return;
      }

      // Read backup files
      const files = fs.readdirSync(backupDir)
        .filter(f => f.endsWith('.json') || f.endsWith('.jsonl'))
        .map(filename => {
          const filepath = path.join(backupDir, filename);
          const stats = fs.statSync(filepath);
          return {
            filename,
            path: filepath,
            size_mb: stats.size / (1024 * 1024),
            created: stats.mtime.toISOString()
          };
        })
        .sort((a, b) => new Date(b.created).getTime() - new Date(a.created).getTime()); // newest first

      console.log('\n' + separator());
      console.log(colors.ui.title(`📁 Available Backups (${files.length})`));
      console.log(separator());

      if (files.length === 0) {
        console.log(`\n  ${colors.status.dim('No backups found')}`);
        console.log(`  ${colors.status.dim(`Directory: ${backupDir}`)}`);
        console.log(`  ${colors.status.dim('Run "kg admin backup" to create your first backup')}\n`);
      } else {
        console.log('');
        files.forEach((backup, i) => {
          console.log(`  ${colors.ui.bullet(`${i + 1}.`)} ${colors.ui.value(backup.filename)}`);
          console.log(`     ${colors.status.dim(`Size: ${backup.size_mb.toFixed(2)} MB`)}`);
          console.log(`     ${colors.status.dim(`Created: ${new Date(backup.created).toLocaleString()}`)}`);
        });
        console.log(`\n  ${colors.status.dim(`Directory: ${backupDir}`)}`);
      }

      console.log('\n' + separator() + '\n');

    } catch (error: any) {
      console.error(colors.status.error('✗ Failed to list backups'));
      console.error(colors.status.error(error.message));
      process.exit(1);
    }
  });

// ========== Restore Command ==========

const restoreCommand = new Command('restore')
  .description('Restore a database backup (requires authentication)')
  .option('--file <name>', 'Backup filename (from configured directory)')
  .option('--path <path>', 'Custom backup file path (overrides configured directory)')
  .option('--overwrite', 'Overwrite existing data', false)
  .option('--deps <action>', 'How to handle external dependencies: prune, stitch, defer', 'prune')
  .action(async (options) => {
    try {
      const client = createClientFromEnv();
      const config = getConfig();
      const backupDir = config.getBackupDir();

      console.log('\n' + separator());
      console.log(colors.ui.title('📥 Database Restore'));
      console.log(colors.status.warning('⚠️  Potentially destructive operation - authentication required'));
      console.log(separator());

      // Determine backup file path
      let backupFilePath: string;
      let backupFilename: string;

      if (options.path) {
        // Custom path specified
        backupFilePath = options.path;
        backupFilename = path.basename(backupFilePath);
      } else if (options.file) {
        // Filename specified, use configured directory
        backupFilePath = path.join(backupDir, options.file);
        backupFilename = options.file;
      } else {
        // Interactive selection from configured directory
        if (!fs.existsSync(backupDir)) {
          console.error(colors.status.error('\n✗ No backups available - directory does not exist'));
          console.log(colors.status.dim(`Directory: ${backupDir}\n`));
          process.exit(1);
        }

        const backups = fs.readdirSync(backupDir)
          .filter(f => f.endsWith('.json') || f.endsWith('.jsonl'))
          .map(filename => {
            const filepath = path.join(backupDir, filename);
            const stats = fs.statSync(filepath);
            return {
              filename,
              path: filepath,
              size_mb: stats.size / (1024 * 1024)
            };
          })
          .sort((a, b) => b.size_mb - a.size_mb);

        if (backups.length === 0) {
          console.error(colors.status.error('\n✗ No backups available'));
          console.log(colors.status.dim(`Directory: ${backupDir}\n`));
          process.exit(1);
        }

        console.log('\n' + colors.ui.key('Available Backups:'));
        backups.slice(0, 10).forEach((backup, i) => {
          console.log(`  ${i + 1}. ${backup.filename} (${backup.size_mb.toFixed(2)} MB)`);
        });

        const choice = await prompt('\nSelect backup [1-10] or enter filename: ');

        if (/^\d+$/.test(choice)) {
          const index = parseInt(choice) - 1;
          if (index >= 0 && index < backups.length) {
            backupFilePath = backups[index].path;
            backupFilename = backups[index].filename;
          } else {
            console.error(colors.status.error('✗ Invalid selection'));
            process.exit(1);
          }
        } else {
          backupFilename = choice;
          backupFilePath = path.join(backupDir, choice);
        }
      }

      // Verify file exists
      if (!fs.existsSync(backupFilePath)) {
        console.error(colors.status.error(`\n✗ Backup file not found: ${backupFilePath}\n`));
        process.exit(1);
      }

      console.log(colors.status.dim(`\nBackup file: ${backupFilePath}`));
      const fileStats = fs.statSync(backupFilePath);
      console.log(colors.status.dim(`Size: ${(fileStats.size / (1024 * 1024)).toFixed(2)} MB`));

      // Get authentication
      console.log('\n' + colors.status.warning('Authentication required:'));
      const username = await prompt('Username: ');
      const password = await promptPassword('Password: ');

      if (!username || !password) {
        console.error(colors.status.error('✗ Username and password required'));
        process.exit(1);
      }

      console.log(colors.status.info('\nRestoring backup...'));

      // TODO: Implement ADR-015 streaming architecture
      // See: docs/ADR-015-backup-restore-streaming.md
      //
      // Current limitation: API expects server-side filename
      // Target: Client should stream file data to API
      //   1. Read backup file from local directory
      //   2. Upload via multipart with progress bar
      //   3. API saves to temp location
      //   4. API runs integrity checks
      //   5. API performs restore with progress updates
      //   6. API deletes temp file
      const result = await client.restoreBackup({
        username,
        password,
        backup_file: backupFilename,
        overwrite: options.overwrite,
        handle_external_deps: options.deps
      });

      console.log('\n' + separator());
      console.log(colors.status.success('✓ Restore Complete'));
      console.log(separator());
      console.log(`\n  ${colors.ui.value(result.message)}`);

      if (result.warnings.length > 0) {
        console.log(`\n  ${colors.status.warning('Warnings:')}`);
        result.warnings.forEach(w => console.log(`    ${colors.status.dim('• ' + w)}`));
      }

      console.log('\n' + separator() + '\n');

    } catch (error: any) {
      console.error(colors.status.error('✗ Restore failed'));
      console.error(colors.status.error(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

// ========== Reset Command ==========

const resetCommand = new Command('reset')
  .description('Reset database - DESTRUCTIVE (requires authentication)')
  .option('--no-logs', 'Do not clear log files')
  .option('--no-checkpoints', 'Do not clear checkpoint files')
  .action(async (options) => {
    try {
      const client = createClientFromEnv();

      console.log('\n' + separator());
      console.log(colors.status.error('🔄 DATABASE RESET - DESTRUCTIVE OPERATION'));
      console.log(separator());

      console.log(colors.status.error('\n⚠️  WARNING: This will DELETE ALL graph data!'));
      console.log(colors.status.dim('This operation will:'));
      console.log(colors.status.dim('  - Stop all containers'));
      console.log(colors.status.dim('  - Delete the Neo4j database'));
      console.log(colors.status.dim('  - Remove all data volumes'));
      console.log(colors.status.dim('  - Restart with a clean database'));
      console.log(colors.status.dim('  - Re-initialize schema'));

      const confirm = await prompt('\nType "yes" to confirm: ');

      if (confirm.toLowerCase() !== 'yes') {
        console.log(colors.status.dim('\nCancelled\n'));
        process.exit(0);
      }

      // Get authentication
      console.log('\n' + colors.status.warning('Authentication required:'));
      const username = await prompt('Username: ');
      const password = await promptPassword('Password: ');

      if (!username || !password) {
        console.error(colors.status.error('✗ Username and password required'));
        process.exit(1);
      }

      console.log(colors.status.info('\nResetting database (this may take a minute)...'));

      const result = await client.resetDatabase({
        username,
        password,
        confirm: true,
        clear_logs: options.logs !== false,
        clear_checkpoints: options.checkpoints !== false
      });

      console.log('\n' + separator());
      console.log(colors.status.success('✓ Reset Complete'));
      console.log(separator());

      console.log('\n' + colors.ui.header('Schema Validation:'));
      console.log(`  ${colors.ui.key('Constraints:')} ${colors.coloredCount(result.schema_validation.constraints_count)}/3`);
      console.log(`  ${colors.ui.key('Vector Index:')} ${result.schema_validation.vector_index_exists ? colors.status.success('Yes') : colors.status.error('No')}`);
      console.log(`  ${colors.ui.key('Nodes:')} ${colors.coloredCount(result.schema_validation.node_count)}`);
      console.log(`  ${colors.ui.key('Test Passed:')} ${result.schema_validation.schema_test_passed ? colors.status.success('Yes') : colors.status.error('No')}`);

      if (result.warnings.length > 0) {
        console.log(`\n  ${colors.status.warning('Warnings:')}`);
        result.warnings.forEach(w => console.log(`    ${colors.status.dim('• ' + w)}`));
      }

      console.log('\n' + colors.status.success('✅ Database is now empty and ready for fresh data'));
      console.log('\n' + separator() + '\n');

    } catch (error: any) {
      console.error(colors.status.error('✗ Reset failed'));
      console.error(colors.status.error(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

// ========== Scheduler Commands (ADR-014) ==========

const schedulerStatusCommand = new Command('status')
  .description('Show job scheduler status and configuration')
  .action(async () => {
    try {
      const client = createClientFromEnv();

      console.log('\n' + separator());
      console.log(colors.ui.title('⏱️  Job Scheduler Status'));
      console.log(separator());

      const status = await client.getSchedulerStatus();

      // Running status
      console.log('\n' + colors.ui.header('Scheduler'));
      if (status.running) {
        console.log(`  ${colors.status.success('✓')} Running`);
      } else {
        console.log(`  ${colors.status.error('✗')} Not running`);
      }

      // Configuration
      console.log('\n' + colors.ui.header('Configuration'));
      console.log(`  ${colors.ui.key('Cleanup Interval:')} ${colors.ui.value(status.config.cleanup_interval + 's')} (${(status.config.cleanup_interval / 3600).toFixed(1)}h)`);
      console.log(`  ${colors.ui.key('Approval Timeout:')} ${colors.ui.value(status.config.approval_timeout + 'h')}`);
      console.log(`  ${colors.ui.key('Completed Retention:')} ${colors.ui.value(status.config.completed_retention + 'h')}`);
      console.log(`  ${colors.ui.key('Failed Retention:')} ${colors.ui.value(status.config.failed_retention + 'h')}`);

      // Statistics
      if (status.stats) {
        console.log('\n' + colors.ui.header('Job Statistics'));

        if (status.stats.jobs_by_status) {
          Object.entries(status.stats.jobs_by_status).forEach(([jobStatus, count]) => {
            console.log(`  ${colors.ui.key(jobStatus + ':')} ${colors.coloredCount(count as number)}`);
          });
        }

        if (status.stats.last_cleanup) {
          console.log(`\n  ${colors.ui.key('Last Cleanup:')} ${colors.ui.value(new Date(status.stats.last_cleanup).toLocaleString())}`);
        }

        if (status.stats.next_cleanup) {
          console.log(`  ${colors.ui.key('Next Cleanup:')} ${colors.ui.value(new Date(status.stats.next_cleanup).toLocaleString())}`);
        }
      }

      console.log('\n' + separator() + '\n');

    } catch (error: any) {
      console.error(colors.status.error('✗ Failed to get scheduler status'));
      console.error(colors.status.error(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

const schedulerCleanupCommand = new Command('cleanup')
  .description('Manually trigger scheduler cleanup (cancels expired jobs, deletes old jobs)')
  .action(async () => {
    try {
      const client = createClientFromEnv();

      console.log('\n' + separator());
      console.log(colors.ui.title('🧹 Manual Scheduler Cleanup'));
      console.log(separator());

      console.log(colors.status.info('\nTriggering cleanup...'));

      const result = await client.triggerSchedulerCleanup();

      console.log('\n' + separator());
      console.log(colors.status.success('✓ Cleanup Complete'));
      console.log(separator());

      if (result.message) {
        console.log(`\n  ${colors.ui.value(result.message)}`);
      }

      if (result.note) {
        console.log(`  ${colors.status.dim(result.note)}`);
      }

      console.log('\n' + separator() + '\n');

    } catch (error: any) {
      console.error(colors.status.error('✗ Cleanup failed'));
      console.error(colors.status.error(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

const schedulerCommand = new Command('scheduler')
  .description('Job scheduler management (ADR-014)')
  .addCommand(schedulerStatusCommand)
  .addCommand(schedulerCleanupCommand);

// ========== Main Admin Command ==========

export const adminCommand = new Command('admin')
  .description('System administration (status, backup, restore, reset, scheduler)')
  .addCommand(statusCommand)
  .addCommand(backupCommand)
  .addCommand(listBackupsCommand)
  .addCommand(restoreCommand)
  .addCommand(resetCommand)
  .addCommand(schedulerCommand);

// Configure colored help for all admin commands
[statusCommand, backupCommand, listBackupsCommand, restoreCommand, resetCommand, schedulerCommand, schedulerStatusCommand, schedulerCleanupCommand].forEach(configureColoredHelp);
