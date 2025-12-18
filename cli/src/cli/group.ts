/**
 * Group Management Commands (ADR-082)
 *
 * CLI commands for managing groups and group membership.
 */

import { Command } from 'commander';
import { createClientFromEnv } from '../api/client';
import * as colors from './colors';
import { separator } from './colors';
import { Table } from '../lib/table';
import { setCommandHelp } from './help-formatter';

export const groupCommand = setCommandHelp(
  new Command('group'),
  'Manage groups and membership',
  'Manage groups for collaborative access control. Groups allow sharing resources with multiple users. System groups (public, admins) are managed by the platform.'
)
  .alias('grp')
  .showHelpAfterError('(add --help for additional information)')
  .showSuggestionAfterError()
  .addCommand(
    new Command('list')
      .description('List all groups')
      .option('--no-system', 'Exclude system groups (public, admins)')
      .action(async (options) => {
        try {
          const client = createClientFromEnv();
          const result = await client.listGroups({
            include_system: options.system !== false,
            include_member_count: true
          });

          if (result.groups.length === 0) {
            console.log(colors.status.warning('\nNo groups found'));
            return;
          }

          console.log('\n' + colors.ui.title('Groups'));

          const table = new Table({
            columns: [
              { header: 'ID', field: 'id', type: 'count', width: 8, align: 'right' },
              { header: 'Name', field: 'group_name', type: 'heading', width: 20 },
              { header: 'Display Name', field: 'display_name', type: 'text', width: 'flex' },
              { header: 'Members', field: 'member_count', type: 'count', width: 10, align: 'right' },
              { header: 'System', field: 'is_system', type: 'text', width: 8,
                customFormat: (v: boolean) => v ? colors.status.dim('yes') : '' }
            ]
          });

          table.print(result.groups.map(g => ({
            ...g,
            display_name: g.display_name || colors.status.dim('(none)')
          })));

        } catch (error: any) {
          console.error(colors.status.error('Failed to list groups'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('members')
      .description('List members of a group')
      .argument('<group-id>', 'Group ID')
      .action(async (groupId) => {
        try {
          const client = createClientFromEnv();
          const result = await client.listGroupMembers(parseInt(groupId));

          console.log('\n' + separator());
          console.log(colors.ui.title(`Group: ${result.group_name} (ID ${result.group_id})`));
          console.log(separator());

          if (result.members.length === 0) {
            console.log(colors.status.warning('\nNo members'));
            if (result.group_id === 1) {
              console.log(colors.status.dim('  Note: All authenticated users are implicit members of "public"'));
            }
          } else {
            console.log(`\n${colors.status.success(`${result.total} member(s):`)}\n`);
            result.members.forEach(m => {
              console.log(`  ${colors.ui.bullet('●')} ${colors.concept.label(m.username)} (ID ${m.user_id})`);
              console.log(`    ${colors.status.dim(`Added: ${new Date(m.added_at).toLocaleString()}`)}`);
            });
          }
          console.log('\n' + separator());

        } catch (error: any) {
          console.error(colors.status.error('Failed to list group members'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('create')
      .description('Create a new group (admin only)')
      .requiredOption('-n, --name <name>', 'Group name (unique identifier)')
      .option('-d, --display <name>', 'Display name')
      .option('--description <text>', 'Group description')
      .action(async (options) => {
        try {
          const client = createClientFromEnv();
          const result = await client.createGroup({
            group_name: options.name,
            display_name: options.display,
            description: options.description
          });

          console.log('\n' + separator());
          console.log(colors.status.success(`Created group "${result.group_name}" (ID ${result.id})`));
          console.log(separator());

        } catch (error: any) {
          console.error(colors.status.error('Failed to create group'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('add-member')
      .description('Add a user to a group (admin only)')
      .argument('<group-id>', 'Group ID')
      .argument('<user-id>', 'User ID to add')
      .action(async (groupId, userId) => {
        try {
          const client = createClientFromEnv();
          const result = await client.addGroupMember(parseInt(groupId), parseInt(userId));

          console.log(colors.status.success(`Added user ${result.username} (ID ${result.user_id}) to group`));

        } catch (error: any) {
          console.error(colors.status.error('Failed to add member'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('remove-member')
      .description('Remove a user from a group (admin only)')
      .argument('<group-id>', 'Group ID')
      .argument('<user-id>', 'User ID to remove')
      .action(async (groupId, userId) => {
        try {
          const client = createClientFromEnv();
          await client.removeGroupMember(parseInt(groupId), parseInt(userId));

          console.log(colors.status.success(`Removed user ${userId} from group ${groupId}`));

        } catch (error: any) {
          console.error(colors.status.error('Failed to remove member'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  );
