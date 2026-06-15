/**
 * Admin Commands (ADR-712)
 * System administration: status, backup, restore, scheduler, AI config
 */

import { Command } from 'commander';
import { createClientFromEnv } from '../../api/client';
import { setCommandHelp, configureColoredHelp } from '../help-formatter';
import { registerAuthAdminCommand } from '../auth-admin';
import { createRbacCommand } from '../rbac';
import { createEmbeddingCommand, createExtractionCommand, createVisionCommand, createKeysCommand } from '../ai-config';

// Import split command modules
import { createStatusCommand } from './status';
import { createBackupCommand, createListBackupsCommand, createRestoreCommand, createVerifyBackupCommand } from './backup';
import { createSchedulerCommand } from './scheduler';
import { createWorkersCommand } from './workers';

// Create command instances
const statusCommand = createStatusCommand();
const backupCommand = createBackupCommand();
const listBackupsCommand = createListBackupsCommand();
const restoreCommand = createRestoreCommand();
const verifyBackupCommand = createVerifyBackupCommand();
const schedulerCommand = createSchedulerCommand();
const workersCommand = createWorkersCommand();

// Main admin command
export const adminCommand = setCommandHelp(
  new Command('admin'),
  'System administration and management',
  'System administration and management - health monitoring, backup/restore, database operations, user/RBAC management, AI model configuration (requires authentication for destructive operations)'
)
  .showHelpAfterError('(add --help for additional information)')
  .showSuggestionAfterError()
  .addCommand(statusCommand)
  .addCommand(backupCommand)
  .addCommand(listBackupsCommand)
  .addCommand(restoreCommand)
  .addCommand(verifyBackupCommand)
  .addCommand(schedulerCommand)
  .addCommand(workersCommand);

// ADR-403: Register user management commands
registerAuthAdminCommand(adminCommand);

// ADR-404: Register RBAC management commands
const client = createClientFromEnv();
const rbacCommand = createRbacCommand(client);
configureColoredHelp(rbacCommand);
adminCommand.addCommand(rbacCommand);

// ADR-804, ADR-805, ADR-802: Register AI configuration commands
const embeddingCommand = createEmbeddingCommand(client);
const extractionCommand = createExtractionCommand(client);
const visionCommand = createVisionCommand(client);
const keysCommand = createKeysCommand(client);

configureColoredHelp(embeddingCommand);
configureColoredHelp(extractionCommand);
configureColoredHelp(visionCommand);
configureColoredHelp(keysCommand);

adminCommand.addCommand(embeddingCommand);
adminCommand.addCommand(extractionCommand);
adminCommand.addCommand(visionCommand);
adminCommand.addCommand(keysCommand);

// Configure colored help for all admin commands
[statusCommand, backupCommand, listBackupsCommand, restoreCommand, verifyBackupCommand, schedulerCommand, workersCommand].forEach(configureColoredHelp);
