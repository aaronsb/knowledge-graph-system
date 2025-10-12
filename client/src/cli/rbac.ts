/**
 * RBAC Management CLI Commands (ADR-028)
 *
 * Commands for managing roles, permissions, and resource types in the dynamic RBAC system.
 */

import { Command } from 'commander';
import { KnowledgeGraphClient } from '../api/client';
import {
  ResourceCreate,
  ResourceRead,
  RoleCreate,
  RoleRead,
  PermissionCreate,
  PermissionRead,
  UserRoleAssign,
  UserRoleRead,
} from '../types';
import * as colors from './colors';
import { Table } from '../lib/table';
import { separator } from './colors';

/**
 * Create RBAC management subcommand for admin
 */
export function createRbacCommand(client: KnowledgeGraphClient): Command {
  const rbac = new Command('rbac')
    .description('Manage roles, permissions, and access control (ADR-028)');

  // ========== Resource Commands ==========

  const resources = new Command('resources')
    .description('Manage resource types')
    .alias('resource');

  resources
    .command('list')
    .description('List all registered resource types')
    .action(async () => {
      try {
        const resourceList = await client.listResources();

        if (resourceList.length === 0) {
          console.log(colors.status.dim('\nNo resources registered\n'));
          return;
        }

        const table = new Table<ResourceRead>({
          columns: [
            {
              header: 'Resource Type',
              field: 'resource_type',
              type: 'heading',
              width: 'auto',
            },
            {
              header: 'Description',
              field: 'description',
              type: 'text',
              width: 'auto',
              maxWidth: 35,
              truncate: true,
              customFormat: (desc) => desc || '-',
            },
            {
              header: 'Actions',
              field: (r) => r.available_actions.join(', '),
              type: 'value',
              width: 'flex',
              priority: 2,
            },
            {
              header: 'Scoping',
              field: (r) => r.supports_scoping ? 'Yes' : 'No',
              type: 'text',
              width: 'auto',
            },
          ],
          spacing: 2,
          showHeader: true,
          showSeparator: true,
        });

        table.print(resourceList);

      } catch (error: any) {
        console.error(colors.status.error('\n✗ Failed to list resources'));
        if (error.response?.status === 401 || error.response?.status === 403) {
          console.error(colors.status.warning('  Requires admin or curator role\n'));
        } else {
          console.error(`  ${error.response?.data?.detail || error.message}\n`);
        }
        process.exit(1);
      }
    });

  resources
    .command('create')
    .description('Register a new resource type')
    .requiredOption('-t, --type <type>', 'Resource type name')
    .requiredOption('-a, --actions <actions...>', 'Available actions (space-separated)')
    .option('-d, --description <desc>', 'Resource description')
    .option('-p, --parent <parent>', 'Parent resource type')
    .option('-s, --scoping', 'Enable instance scoping', false)
    .action(async (options) => {
      try {
        const resource: ResourceCreate = {
          resource_type: options.type,
          description: options.description,
          parent_type: options.parent,
          available_actions: options.actions,
          supports_scoping: options.scoping,
          metadata: {},
        };

        const created = await client.createResource(resource);

        console.log(colors.status.success('\n✓ Resource type created'));
        console.log(`  Type: ${colors.ui.value(created.resource_type)}`);
        console.log(`  Actions: ${created.available_actions.join(', ')}`);
        console.log(`  Registered by: ${created.registered_by || 'system'}\n`);
      } catch (error: any) {
        console.error(colors.status.error('\n✗ Failed to create resource type'));
        if (error.response?.status === 401 || error.response?.status === 403) {
          console.error(colors.status.warning('  Requires admin role\n'));
        } else if (error.response?.status === 409) {
          console.error(`  Resource type '${options.type}' already exists\n`);
        } else {
          console.error(`  ${error.response?.data?.detail || error.message}\n`);
        }
        process.exit(1);
      }
    });

  rbac.addCommand(resources);

  // ========== Role Commands ==========

  const roles = new Command('roles')
    .description('Manage roles')
    .alias('role');

  roles
    .command('list')
    .description('List all roles')
    .option('--all', 'Include inactive roles', false)
    .action(async (options) => {
      try {
        const roleList = await client.listRoles(options.all);

        if (roleList.length === 0) {
          console.log(colors.status.dim('\nNo roles found\n'));
          return;
        }

        const table = new Table<RoleRead>({
          columns: [
            {
              header: 'Role Name',
              field: 'role_name',
              type: 'heading',
              width: 'flex',
              priority: 2,
            },
            {
              header: 'Display Name',
              field: 'display_name',
              type: 'value',
              width: 'flex',
              priority: 1,
            },
            {
              header: 'Active',
              field: (r) => r.is_active,
              type: 'text',
              width: 8,
              customFormat: (active) => active ? '●' : '○',
            },
            {
              header: 'Builtin',
              field: (r) => r.is_builtin ? 'Yes' : 'No',
              type: 'text',
              width: 8,
            },
            {
              header: 'Parent',
              field: 'parent_role',
              type: 'text',
              width: 'auto',
              customFormat: (p) => p || '-',
            },
          ],
          spacing: 2,
          showHeader: true,
          showSeparator: true,
        });

        table.print(roleList);

      } catch (error: any) {
        console.error(colors.status.error('\n✗ Failed to list roles'));
        if (error.response?.status === 401 || error.response?.status === 403) {
          console.error(colors.status.warning('  Requires admin or curator role\n'));
        } else {
          console.error(`  ${error.response?.data?.detail || error.message}\n`);
        }
        process.exit(1);
      }
    });

  roles
    .command('show <role>')
    .description('Show role details')
    .action(async (roleName: string) => {
      try {
        const role = await client.getRole(roleName);
        const permissions = await client.listPermissions(roleName);

        console.log('\n' + separator());
        console.log(colors.ui.title(`Role: ${role.display_name}`));
        console.log(separator());
        console.log(`\n  ${colors.ui.key('ID:')} ${colors.ui.value(role.role_name)}`);
        if (role.description) {
          console.log(`  ${colors.ui.key('Description:')} ${role.description}`);
        }
        console.log(`  ${colors.ui.key('Status:')} ${role.is_active ? colors.status.success('Active') : colors.status.dim('Inactive')}`);
        console.log(`  ${colors.ui.key('Builtin:')} ${role.is_builtin ? 'Yes' : 'No'}`);
        if (role.parent_role) {
          console.log(`  ${colors.ui.key('Inherits from:')} ${colors.ui.value(role.parent_role)}`);
        }
        console.log(`  ${colors.ui.key('Created:')} ${new Date(role.created_at).toLocaleString()}`);

        if (permissions.length > 0) {
          console.log(`\n${colors.ui.header('Permissions')} (${permissions.length}):`);
          for (const perm of permissions) {
            const grantIcon = perm.granted ? colors.status.success('✓') : colors.status.error('✗');
            console.log(`  ${grantIcon} ${perm.action} on ${colors.ui.value(perm.resource_type)} (${perm.scope_type})`);
          }
        }

        console.log('\n' + separator() + '\n');

      } catch (error: any) {
        console.error(colors.status.error('\n✗ Failed to get role details'));
        if (error.response?.status === 404) {
          console.error(`  Role '${roleName}' not found\n`);
        } else if (error.response?.status === 401 || error.response?.status === 403) {
          console.error(colors.status.warning('  Requires admin or curator role\n'));
        } else {
          console.error(`  ${error.response?.data?.detail || error.message}\n`);
        }
        process.exit(1);
      }
    });

  roles
    .command('create')
    .description('Create a new role')
    .requiredOption('-n, --name <name>', 'Role name (e.g., data_scientist)')
    .requiredOption('-d, --display <display>', 'Display name')
    .option('--description <desc>', 'Role description')
    .option('-p, --parent <parent>', 'Parent role to inherit from')
    .action(async (options) => {
      try {
        const role: RoleCreate = {
          role_name: options.name,
          display_name: options.display,
          description: options.description,
          parent_role: options.parent,
          metadata: {},
        };

        const created = await client.createRole(role);

        console.log(colors.status.success('\n✓ Role created'));
        console.log(`  Name: ${colors.ui.value(created.role_name)}`);
        console.log(`  Display: ${created.display_name}`);
        if (created.parent_role) {
          console.log(`  Inherits from: ${created.parent_role}`);
        }
        console.log();
      } catch (error: any) {
        console.error(colors.status.error('\n✗ Failed to create role'));
        if (error.response?.status === 401 || error.response?.status === 403) {
          console.error(colors.status.warning('  Requires admin role\n'));
        } else if (error.response?.status === 409) {
          console.error(`  Role '${options.name}' already exists\n`);
        } else {
          console.error(`  ${error.response?.data?.detail || error.message}\n`);
        }
        process.exit(1);
      }
    });

  roles
    .command('delete <role>')
    .description('Delete a role')
    .option('--force', 'Skip confirmation', false)
    .action(async (roleName: string, options) => {
      try {
        // Confirm deletion unless --force
        if (!options.force) {
          const readline = require('readline').createInterface({
            input: process.stdin,
            output: process.stdout,
          });

          await new Promise<void>((resolve, reject) => {
            readline.question(
              colors.status.warning(`\n⚠ Delete role '${roleName}'? This cannot be undone. [y/N]: `),
              (answer: string) => {
                readline.close();
                if (answer.toLowerCase() !== 'y') {
                  console.log('Cancelled\n');
                  process.exit(0);
                }
                resolve();
              }
            );
          });
        }

        await client.deleteRole(roleName);

        console.log(colors.status.success(`\n✓ Role '${roleName}' deleted\n`));
      } catch (error: any) {
        console.error(colors.status.error('\n✗ Failed to delete role'));
        if (error.response?.status === 404) {
          console.error(`  Role '${roleName}' not found\n`);
        } else if (error.response?.status === 403) {
          console.error('  Cannot delete builtin roles or roles with users\n');
        } else if (error.response?.status === 409) {
          console.error('  Cannot delete role with assigned users\n');
        } else {
          console.error(`  ${error.response?.data?.detail || error.message}\n`);
        }
        process.exit(1);
      }
    });

  rbac.addCommand(roles);

  // ========== Permission Commands ==========

  const permissions = new Command('permissions')
    .description('Manage permissions')
    .alias('perm');

  permissions
    .command('list')
    .description('List permissions')
    .option('-r, --role <role>', 'Filter by role name')
    .option('-t, --resource-type <type>', 'Filter by resource type')
    .action(async (options) => {
      try {
        const permList = await client.listPermissions(options.role, options.resourceType);

        if (permList.length === 0) {
          console.log(colors.status.dim('\nNo permissions found\n'));
          return;
        }

        const table = new Table<PermissionRead>({
          columns: [
            {
              header: 'Role',
              field: 'role_name',
              type: 'heading',
              width: 'flex',
              priority: 1,
            },
            {
              header: 'Action',
              field: 'action',
              type: 'value',
              width: 'auto',
            },
            {
              header: 'Resource',
              field: 'resource_type',
              type: 'heading',
              width: 'flex',
              priority: 2,
            },
            {
              header: 'Scope',
              field: 'scope_type',
              type: 'text',
              width: 12,
            },
            {
              header: 'Granted',
              field: (p) => p.granted,
              type: 'text',
              width: 8,
              customFormat: (granted) => granted ? '✓' : '✗',
            },
          ],
          spacing: 2,
          showHeader: true,
          showSeparator: true,
        });

        table.print(permList);

      } catch (error: any) {
        console.error(colors.status.error('\n✗ Failed to list permissions'));
        if (error.response?.status === 401 || error.response?.status === 403) {
          console.error(colors.status.warning('  Requires admin or curator role\n'));
        } else {
          console.error(`  ${error.response?.data?.detail || error.message}\n`);
        }
        process.exit(1);
      }
    });

  permissions
    .command('grant')
    .description('Grant a permission to a role')
    .requiredOption('-r, --role <role>', 'Role name')
    .requiredOption('-t, --resource-type <type>', 'Resource type')
    .requiredOption('-a, --action <action>', 'Action (read, write, delete, etc.)')
    .option('-s, --scope <scope>', 'Scope type (global, instance, filter)', 'global')
    .option('--scope-id <id>', 'Scope ID for instance scoping')
    .option('--deny', 'Create explicit deny (default is grant)', false)
    .action(async (options) => {
      try {
        const permission: PermissionCreate = {
          role_name: options.role,
          resource_type: options.resourceType,
          action: options.action,
          scope_type: options.scope,
          scope_id: options.scopeId,
          granted: !options.deny,
        };

        const created = await client.createPermission(permission);

        const grantType = created.granted ? 'granted' : 'denied';
        console.log(colors.status.success(`\n✓ Permission ${grantType}`));
        console.log(`  Role: ${created.role_name}`);
        console.log(`  Action: ${created.action} on ${created.resource_type}`);
        console.log(`  Scope: ${created.scope_type}\n`);
      } catch (error: any) {
        console.error(colors.status.error('\n✗ Failed to grant permission'));
        if (error.response?.status === 401 || error.response?.status === 403) {
          console.error(colors.status.warning('  Requires admin role\n'));
        } else if (error.response?.status === 404) {
          console.error('  Role or resource type not found\n');
        } else if (error.response?.status === 409) {
          console.error('  Permission already exists with this scope\n');
        } else {
          console.error(`  ${error.response?.data?.detail || error.message}\n`);
        }
        process.exit(1);
      }
    });

  permissions
    .command('revoke <permission-id>')
    .description('Revoke a permission (use permission ID from list)')
    .action(async (permissionId: string) => {
      try {
        await client.deletePermission(parseInt(permissionId));

        console.log(colors.status.success(`\n✓ Permission revoked\n`));
      } catch (error: any) {
        console.error(colors.status.error('\n✗ Failed to revoke permission'));
        if (error.response?.status === 404) {
          console.error(`  Permission ${permissionId} not found\n`);
        } else if (error.response?.status === 401 || error.response?.status === 403) {
          console.error(colors.status.warning('  Requires admin role\n'));
        } else {
          console.error(`  ${error.response?.data?.detail || error.message}\n`);
        }
        process.exit(1);
      }
    });

  rbac.addCommand(permissions);

  // ========== User Role Assignment Commands ==========

  const userRoles = new Command('assign')
    .description('Assign roles to users');

  userRoles
    .command('list <user-id>')
    .description('List role assignments for a user')
    .action(async (userId: string) => {
      try {
        const assignments = await client.listUserRoles(parseInt(userId));

        if (assignments.length === 0) {
          console.log(colors.status.dim(`\nNo role assignments for user ${userId}\n`));
          return;
        }

        const table = new Table<UserRoleRead>({
          columns: [
            {
              header: 'Role',
              field: 'role_name',
              type: 'heading',
              width: 'flex',
              priority: 2,
            },
            {
              header: 'Scope Type',
              field: 'scope_type',
              type: 'text',
              width: 'auto',
              customFormat: (s) => s || 'global',
            },
            {
              header: 'Scope ID',
              field: 'scope_id',
              type: 'value',
              width: 'auto',
              customFormat: (id) => id || '-',
            },
            {
              header: 'Assigned',
              field: 'assigned_at',
              type: 'timestamp',
              width: 18,
            },
            {
              header: 'Expires',
              field: 'expires_at',
              type: 'timestamp',
              width: 18,
              customFormat: (exp) => exp ? new Date(exp).toLocaleString() : 'Never',
            },
          ],
          spacing: 2,
          showHeader: true,
          showSeparator: true,
        });

        table.print(assignments);

      } catch (error: any) {
        console.error(colors.status.error('\n✗ Failed to list user roles'));
        if (error.response?.status === 401 || error.response?.status === 403) {
          console.error(colors.status.warning('  Requires admin or curator role\n'));
        } else {
          console.error(`  ${error.response?.data?.detail || error.message}\n`);
        }
        process.exit(1);
      }
    });

  userRoles
    .command('add')
    .description('Assign a role to a user')
    .requiredOption('-u, --user-id <id>', 'User ID')
    .requiredOption('-r, --role <role>', 'Role name')
    .option('-s, --scope <scope>', 'Scope type (global, workspace, ontology, etc.)', 'global')
    .option('--scope-id <id>', 'Scope ID (e.g., workspace ID)')
    .action(async (options) => {
      try {
        const assignment: UserRoleAssign = {
          user_id: parseInt(options.userId),
          role_name: options.role,
          scope_type: options.scope,
          scope_id: options.scopeId,
        };

        const created = await client.assignUserRole(assignment);

        console.log(colors.status.success('\n✓ Role assigned'));
        console.log(`  User: ${created.user_id}`);
        console.log(`  Role: ${created.role_name}`);
        console.log(`  Scope: ${created.scope_type || 'global'}\n`);
      } catch (error: any) {
        console.error(colors.status.error('\n✗ Failed to assign role'));
        if (error.response?.status === 401 || error.response?.status === 403) {
          console.error(colors.status.warning('  Requires admin role\n'));
        } else if (error.response?.status === 404) {
          console.error('  User or role not found\n');
        } else if (error.response?.status === 409) {
          console.error('  User already has this role assignment\n');
        } else {
          console.error(`  ${error.response?.data?.detail || error.message}\n`);
        }
        process.exit(1);
      }
    });

  userRoles
    .command('remove <assignment-id>')
    .description('Remove a role assignment (use assignment ID from list)')
    .action(async (assignmentId: string) => {
      try {
        await client.revokeUserRole(parseInt(assignmentId));

        console.log(colors.status.success(`\n✓ Role assignment removed\n`));
      } catch (error: any) {
        console.error(colors.status.error('\n✗ Failed to remove role assignment'));
        if (error.response?.status === 404) {
          console.error(`  Assignment ${assignmentId} not found\n`);
        } else if (error.response?.status === 401 || error.response?.status === 403) {
          console.error(colors.status.warning('  Requires admin role\n'));
        } else {
          console.error(`  ${error.response?.data?.detail || error.message}\n`);
        }
        process.exit(1);
      }
    });

  rbac.addCommand(userRoles);

  return rbac;
}
