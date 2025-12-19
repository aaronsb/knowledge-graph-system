/**
 * Admin Commands (ADR-036)
 * System administration: status, backup, restore, scheduler, AI config
 */

import { Command } from 'commander';
import { createClientFromEnv } from '../../api/client';
import { setCommandHelp, configureColoredHelp } from '../help-formatter';
import { registerAuthAdminCommand } from '../auth-admin';
import { createRbacCommand } from '../rbac';
import { createEmbeddingCommand, createExtractionCommand, createKeysCommand } from '../ai-config';

// Import split command modules
import { createStatusCommand } from './status';
import { createBackupCommand, createListBackupsCommand, createRestoreCommand } from './backup';
import { createSchedulerCommand } from './scheduler';

// Create command instances
const statusCommand = createStatusCommand();
const backupCommand = createBackupCommand();
const listBackupsCommand = createListBackupsCommand();
const restoreCommand = createRestoreCommand();
const schedulerCommand = createSchedulerCommand();

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
  .addCommand(schedulerCommand);

// ADR-027: Register user management commands
registerAuthAdminCommand(adminCommand);

// ADR-028: Register RBAC management commands
const client = createClientFromEnv();
const rbacCommand = createRbacCommand(client);
configureColoredHelp(rbacCommand);
adminCommand.addCommand(rbacCommand);

// ADR-039, ADR-041: Register AI configuration commands
const embeddingCommand = createEmbeddingCommand(client);
const extractionCommand = createExtractionCommand(client);
const keysCommand = createKeysCommand(client);

configureColoredHelp(embeddingCommand);
configureColoredHelp(extractionCommand);
configureColoredHelp(keysCommand);

adminCommand.addCommand(embeddingCommand);
adminCommand.addCommand(extractionCommand);
adminCommand.addCommand(keysCommand);

// Configure colored help for all admin commands
[statusCommand, backupCommand, listBackupsCommand, restoreCommand, schedulerCommand].forEach(configureColoredHelp);
