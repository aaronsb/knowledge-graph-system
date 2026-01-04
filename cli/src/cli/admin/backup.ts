/**
 * Admin Backup Commands
 * Backup, list-backups, and restore operations (ADR-036)
 */

import { Command } from 'commander';
import * as fs from 'fs';
import * as path from 'path';
import { createClientFromEnv } from '../../api/client';
import { getConfig } from '../../lib/config';
import * as colors from '../colors';
import { separator, coloredCount } from '../colors';
import { prompt, promptPassword, trackJobWithSSE } from './utils';

export function createBackupCommand(): Command {
  return new Command('backup')
    .description('Create database backup (ADR-036) - full system or per-ontology, in restorable JSON or Gephi GEXF format')
    .option('--type <type>', 'Backup type: "full" (entire graph) or "ontology" (single namespace)')
    .option('--ontology <name>', 'Ontology name (required if --type ontology)')
    .option('--output <filename>', 'Custom output filename (auto-generated if not specified)')
    .option('--format <format>', 'Export format: "archive" (tar.gz with documents, default), "json" (graph only), or "gexf" (Gephi visualization)', 'archive')
    .action(async (options) => {
      try {
        const client = createClientFromEnv();

        console.log('\n' + separator());
        console.log(colors.ui.title('💾 Database Backup'));
        console.log(separator());

        let backupType: 'full' | 'ontology' = 'full';
        let ontologyName: string | undefined;
        let format: 'archive' | 'json' | 'gexf' = options.format || 'archive';

        // Validate format
        if (format !== 'archive' && format !== 'json' && format !== 'gexf') {
          console.error(colors.status.error('✗ Invalid format. Must be "archive", "json", or "gexf"'));
          process.exit(1);
        }

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

        // Get backup directory and ensure it exists
        const config = getConfig();
        const backupDir = config.ensureBackupDir();

        // Determine output path
        let savePath: string;
        const fileExtension = format === 'archive' ? '.tar.gz' : (format === 'gexf' ? '.gexf' : '.json');

        if (options.output) {
          const hasExtension = options.output.endsWith('.json') || options.output.endsWith('.gexf') || options.output.endsWith('.tar.gz');
          savePath = path.join(backupDir, hasExtension ? options.output : `${options.output}${fileExtension}`);
        } else {
          const timestamp = new Date().toISOString().replace(/[:.]/g, '-').split('T')[0];
          savePath = path.join(backupDir, `temp_${timestamp}${fileExtension}`);
        }

        // Download backup with progress tracking
        const ora = require('ora');
        const spinner = ora('Preparing backup...').start();

        try {
          const result = await client.createBackup(
            {
              backup_type: backupType,
              ontology_name: ontologyName,
              format: format
            },
            savePath,
            (downloaded: number, total: number, percent: number) => {
              const downloadedMB = (downloaded / (1024 * 1024)).toFixed(2);
              const totalMB = (total / (1024 * 1024)).toFixed(2);
              spinner.text = `Downloading ${format.toUpperCase()} backup... ${percent}% (${downloadedMB}/${totalMB} MB)`;
            }
          );

          spinner.succeed('Backup download complete!');

          console.log('\n' + separator());
          console.log(colors.status.success('✓ Backup Complete'));
          console.log(separator());
          console.log(`\n  ${colors.ui.key('File:')} ${colors.ui.value(result.filename)}`);
          console.log(`  ${colors.ui.key('Path:')} ${colors.ui.value(result.path)}`);
          console.log(`  ${colors.ui.key('Size:')} ${colors.ui.value((result.size / (1024 * 1024)).toFixed(2) + ' MB')}`);
          console.log(`\n  ${colors.status.dim('Backup saved to: ' + backupDir)}`);
          console.log('\n' + separator() + '\n');

        } catch (downloadError) {
          spinner.fail('Backup download failed');
          throw downloadError;
        }

      } catch (error: any) {
        console.error(colors.status.error('✗ Backup failed'));
        console.error(colors.status.error(error.response?.data?.detail || error.message));
        process.exit(1);
      }
    });
}

export function createListBackupsCommand(): Command {
  return new Command('list-backups')
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

        // Read backup files (archive, json, gexf formats)
        const files = fs.readdirSync(backupDir)
          .filter(f => f.endsWith('.tar.gz') || f.endsWith('.json') || f.endsWith('.jsonl') || f.endsWith('.gexf'))
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
          .sort((a, b) => new Date(b.created).getTime() - new Date(a.created).getTime());

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
}

export function createRestoreCommand(): Command {
  return new Command('restore')
    .description('Restore a database backup (requires authentication)')
    .option('--file <name>', 'Backup filename (from configured directory)')
    .option('--path <path>', 'Custom backup file path (overrides configured directory)')
    .option('--merge', 'Merge into existing ontology if it exists (default: error if ontology exists)', false)
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
          backupFilePath = options.path;
          backupFilename = path.basename(backupFilePath);
        } else if (options.file) {
          backupFilePath = path.join(backupDir, options.file);
          backupFilename = options.file;
        } else {
          // Interactive selection
          if (!fs.existsSync(backupDir)) {
            console.error(colors.status.error('\n✗ No backups available - directory does not exist'));
            console.log(colors.status.dim(`Directory: ${backupDir}\n`));
            process.exit(1);
          }

          const backups = fs.readdirSync(backupDir)
            .filter(f => f.endsWith('.tar.gz') || f.endsWith('.json') || f.endsWith('.jsonl'))
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

        const username = config.get('username') || config.getClientId();
        if (!username) {
          console.error(colors.status.error('✗ Username not configured. Run: kg config set username <your-username>'));
          process.exit(1);
        }

        console.log(colors.status.dim(`Using username: ${username}`));
        const password = await promptPassword('Password: ');

        if (!password) {
          console.error(colors.status.error('✗ Password required'));
          process.exit(1);
        }

        // Upload backup with progress tracking
        const ora = require('ora');
        let spinner = ora('Uploading backup...').start();

        try {
          const uploadResult = await client.restoreBackup(
            backupFilePath,
            username,
            password,
            !options.merge,
            options.deps,
            (uploaded: number, total: number, percent: number) => {
              const uploadedMB = (uploaded / (1024 * 1024)).toFixed(2);
              const totalMB = (total / (1024 * 1024)).toFixed(2);
              spinner.text = `Uploading backup... ${percent}% (${uploadedMB}/${totalMB} MB)`;
            }
          );

          spinner.succeed('Backup uploaded successfully!');

          if (uploadResult.backup_stats) {
            console.log(colors.status.dim(`\nBackup contains: ${uploadResult.backup_stats.concepts || 0} concepts, ${uploadResult.backup_stats.sources || 0} sources`));
          }

          if (uploadResult.integrity_warnings > 0) {
            console.log(colors.status.warning(`⚠️  Backup has ${uploadResult.integrity_warnings} validation warnings`));
          }

          // Track restore job progress with SSE
          spinner = ora('Preparing restore...').start();
          const jobId = uploadResult.job_id;

          const finalJob = await trackJobWithSSE(client, jobId, spinner);

          if (finalJob.status === 'completed') {
            spinner.succeed('Restore completed successfully!');

            console.log('\n' + separator());
            console.log(colors.status.success('✓ Restore Complete'));
            console.log(separator());

            if (finalJob.result?.restore_stats) {
              const stats = finalJob.result.restore_stats;
              console.log('\n' + colors.ui.header('Restored:'));
              console.log(`  ${colors.ui.key('Concepts:')} ${coloredCount(stats.concepts || 0)}`);
              console.log(`  ${colors.ui.key('Sources:')} ${coloredCount(stats.sources || 0)}`);
              console.log(`  ${colors.ui.key('Instances:')} ${coloredCount(stats.instances || 0)}`);
              console.log(`  ${colors.ui.key('Relationships:')} ${coloredCount(stats.relationships || 0)}`);
            }

            if (finalJob.result?.checkpoint_created) {
              console.log('\n' + colors.status.dim('✓ Checkpoint backup created and deleted after successful restore'));
            }

            console.log('\n' + separator() + '\n');

          } else if (finalJob.status === 'failed') {
            spinner.fail('Restore failed');

            console.log('\n' + separator());
            console.log(colors.status.error('✗ Restore Failed'));
            console.log(separator());

            if (finalJob.error) {
              console.log(`\n  ${colors.status.error(finalJob.error)}`);
            }

            if (finalJob.error && finalJob.error.includes('rolled back')) {
              console.log(`\n  ${colors.status.success('✓ Database rolled back to checkpoint - no data loss')}`);
            }

            console.log('\n' + separator() + '\n');
            process.exit(1);
          }

        } catch (uploadError) {
          spinner.fail('Restore upload failed');
          throw uploadError;
        }

      } catch (error: any) {
        console.error(colors.status.error('✗ Restore failed'));
        console.error(colors.status.error(error.response?.data?.detail || error.message));
        process.exit(1);
      }
    });
}
