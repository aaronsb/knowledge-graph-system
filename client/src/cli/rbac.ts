/**
 * RBAC Management CLI Commands (ADR-028)
 *
 * Commands for managing roles, permissions, and resource types in the dynamic RBAC system.
 */

import { Command } from 'commander';
import { KnowledgeGraphClient } from '../api/client';
import {
  ResourceCreate,
  RoleCreate,
  PermissionCreate,
  UserRoleAssign,
} from '../types';
import * as colors from './colors';
import { status } from './colors';
import ansis from 'ansis';

/**
 * Create RBAC management commands
 */
export function createRbacCommands(client: KnowledgeGraphClient): Command {
  const rbac = new Command('rbac')
    .description('Manage roles, permissions, and access control (ADR-028)')
    .alias('role');

  // ========== Resource Commands ==========

  const resources = new Command('resources')
    .description('Manage resource types')
    .alias('resource');

  resources
    .command('list')
    .description('List all registered resource types')
    .action(async () => {
      try {
        const resources = await client.listResources();

        console.log(`\n${ansis.bold}Resource Types${ansis.reset} (${resources.length}):\n`);

        for (const resource of resources) {
          console.log(`${status.info}${resource.resource_type}${ansis.reset}`);
          if (resource.description) {
            console.log(`  ${status.dim}${resource.description}${ansis.reset}`);
          }
          console.log(`  Actions: ${resource.available_actions.join(', ')}`);
          console.log(`  Scoping: ${resource.supports_scoping ? 'Supported' : 'Not supported'}`);
          if (resource.parent_type) {
            console.log(`  Parent: ${resource.parent_type}`);
          }
          console.log();
        }
      } catch (error: any) {
        console.error(`${status.error}✗ Failed to list resources${ansis.reset}`);
        if (error.response?.status === 401 || error.response?.status === 403) {
          console.error(`${status.warning}  Requires admin or curator role${ansis.reset}`);
        } else {
          console.error(`  ${error.response?.data?.detail || error.message}`);
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

        console.log(`\n${status.success}✓ Resource type created${ansis.reset}`);
        console.log(`  Type: ${status.info}${created.resource_type}${ansis.reset}`);
        console.log(`  Actions: ${created.available_actions.join(', ')}`);
        console.log(`  Registered by: ${created.registered_by || 'system'}`);
      } catch (error: any) {
        console.error(`${status.error}✗ Failed to create resource type${ansis.reset}`);
        if (error.response?.status === 401 || error.response?.status === 403) {
          console.error(`${status.warning}  Requires admin role${ansis.reset}`);
        } else if (error.response?.status === 409) {
          console.error(`  Resource type '${options.type}' already exists`);
        } else {
          console.error(`  ${error.response?.data?.detail || error.message}`);
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
        const roles = await client.listRoles(options.all);

        console.log(`\n${ansis.bold}Roles${ansis.reset} (${roles.length}):\n`);

        for (const role of roles) {
          const roleStatus = role.is_active ? status.success + '●' : status.dim + '○';
          const builtin = role.is_builtin ? ` ${status.dim}(builtin)${ansis.reset}` : '';

          console.log(`${roleStatus} ${status.info}${role.role_name}${ansis.reset}${builtin}`);
          console.log(`  ${role.display_name}`);
          if (role.description) {
            console.log(`  ${status.dim}${role.description}${ansis.reset}`);
          }
          if (role.parent_role) {
            console.log(`  Inherits from: ${role.parent_role}`);
          }
          console.log();
        }
      } catch (error: any) {
        console.error(`${status.error}✗ Failed to list roles${ansis.reset}`);
        if (error.response?.status === 401 || error.response?.status === 403) {
          console.error(`${status.warning}  Requires admin or curator role${ansis.reset}`);
        } else {
          console.error(`  ${error.response?.data?.detail || error.message}`);
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

        console.log(`\n${ansis.bold}Role: ${status.info}${role.display_name}${ansis.reset}`);
        console.log(`ID: ${role.role_name}`);
        if (role.description) {
          console.log(`Description: ${role.description}`);
        }
        console.log(`Status: ${role.is_active ? status.success + 'Active' : status.dim + 'Inactive'}${ansis.reset}`);
        console.log(`Builtin: ${role.is_builtin ? 'Yes' : 'No'}`);
        if (role.parent_role) {
          console.log(`Inherits from: ${role.parent_role}`);
        }
        console.log(`Created: ${new Date(role.created_at).toLocaleString()}`);

        if (permissions.length > 0) {
          console.log(`\n${ansis.bold}Permissions${ansis.reset} (${permissions.length}):`);
          for (const perm of permissions) {
            const grantIcon = perm.granted ? status.success + '✓' : status.error + '✗';
            console.log(`${grantIcon} ${perm.action} on ${perm.resource_type} (${perm.scope_type})${ansis.reset}`);
          }
        }
      } catch (error: any) {
        console.error(`${status.error}✗ Failed to get role details${ansis.reset}`);
        if (error.response?.status === 404) {
          console.error(`  Role '${roleName}' not found`);
        } else if (error.response?.status === 401 || error.response?.status === 403) {
          console.error(`${status.warning}  Requires admin or curator role${ansis.reset}`);
        } else {
          console.error(`  ${error.response?.data?.detail || error.message}`);
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

        console.log(`\n${status.success}✓ Role created${ansis.reset}`);
        console.log(`  Name: ${status.info}${created.role_name}${ansis.reset}`);
        console.log(`  Display: ${created.display_name}`);
        if (created.parent_role) {
          console.log(`  Inherits from: ${created.parent_role}`);
        }
      } catch (error: any) {
        console.error(`${status.error}✗ Failed to create role${ansis.reset}`);
        if (error.response?.status === 401 || error.response?.status === 403) {
          console.error(`${status.warning}  Requires admin role${ansis.reset}`);
        } else if (error.response?.status === 409) {
          console.error(`  Role '${options.name}' already exists`);
        } else {
          console.error(`  ${error.response?.data?.detail || error.message}`);
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
              `${status.warning}⚠ Delete role '${roleName}'? This cannot be undone. [y/N]: ${ansis.reset}`,
              (answer: string) => {
                readline.close();
                if (answer.toLowerCase() !== 'y') {
                  console.log('Cancelled');
                  process.exit(0);
                }
                resolve();
              }
            );
          });
        }

        await client.deleteRole(roleName);

        console.log(`${status.success}✓ Role '${roleName}' deleted${ansis.reset}`);
      } catch (error: any) {
        console.error(`${status.error}✗ Failed to delete role${ansis.reset}`);
        if (error.response?.status === 404) {
          console.error(`  Role '${roleName}' not found`);
        } else if (error.response?.status === 403) {
          console.error(`  Cannot delete builtin roles or roles with users`);
        } else if (error.response?.status === 409) {
          console.error(`  Cannot delete role with assigned users`);
        } else {
          console.error(`  ${error.response?.data?.detail || error.message}`);
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
        const perms = await client.listPermissions(options.role, options.resourceType);

        console.log(`\n${ansis.bold}Permissions${ansis.reset} (${perms.length}):\n`);

        // Group by role
        const byRole = new Map<string, typeof perms>();
        for (const perm of perms) {
          if (!byRole.has(perm.role_name)) {
            byRole.set(perm.role_name, []);
          }
          byRole.get(perm.role_name)!.push(perm);
        }

        for (const [roleName, rolePerms] of byRole) {
          console.log(`${status.info}${roleName}${ansis.reset}:`);
          for (const perm of rolePerms) {
            const grantIcon = perm.granted ? status.success + '  ✓' : status.error + '  ✗';
            console.log(`${grantIcon} ${perm.action} on ${perm.resource_type} (${perm.scope_type})${ansis.reset}`);
          }
          console.log();
        }
      } catch (error: any) {
        console.error(`${status.error}✗ Failed to list permissions${ansis.reset}`);
        if (error.response?.status === 401 || error.response?.status === 403) {
          console.error(`${status.warning}  Requires admin or curator role${ansis.reset}`);
        } else {
          console.error(`  ${error.response?.data?.detail || error.message}`);
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
        console.log(`\n${status.success}✓ Permission ${grantType}${ansis.reset}`);
        console.log(`  Role: ${created.role_name}`);
        console.log(`  Action: ${created.action} on ${created.resource_type}`);
        console.log(`  Scope: ${created.scope_type}`);
      } catch (error: any) {
        console.error(`${status.error}✗ Failed to grant permission${ansis.reset}`);
        if (error.response?.status === 401 || error.response?.status === 403) {
          console.error(`${status.warning}  Requires admin role${ansis.reset}`);
        } else if (error.response?.status === 404) {
          console.error(`  Role or resource type not found`);
        } else if (error.response?.status === 409) {
          console.error(`  Permission already exists with this scope`);
        } else {
          console.error(`  ${error.response?.data?.detail || error.message}`);
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

        console.log(`${status.success}✓ Permission revoked${ansis.reset}`);
      } catch (error: any) {
        console.error(`${status.error}✗ Failed to revoke permission${ansis.reset}`);
        if (error.response?.status === 404) {
          console.error(`  Permission ${permissionId} not found`);
        } else if (error.response?.status === 401 || error.response?.status === 403) {
          console.error(`${status.warning}  Requires admin role${ansis.reset}`);
        } else {
          console.error(`  ${error.response?.data?.detail || error.message}`);
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

        console.log(`\n${ansis.bold}Role Assignments for User ${userId}${ansis.reset} (${assignments.length}):\n`);

        for (const assignment of assignments) {
          console.log(`${status.info}${assignment.role_name}${ansis.reset}`);
          console.log(`  Scope: ${assignment.scope_type || 'global'}${assignment.scope_id ? ' - ' + assignment.scope_id : ''}`);
          console.log(`  Assigned: ${new Date(assignment.assigned_at).toLocaleString()}`);
          if (assignment.expires_at) {
            console.log(`  Expires: ${new Date(assignment.expires_at).toLocaleString()}`);
          }
          console.log();
        }
      } catch (error: any) {
        console.error(`${status.error}✗ Failed to list user roles${ansis.reset}`);
        if (error.response?.status === 401 || error.response?.status === 403) {
          console.error(`${status.warning}  Requires admin or curator role${ansis.reset}`);
        } else {
          console.error(`  ${error.response?.data?.detail || error.message}`);
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

        console.log(`\n${status.success}✓ Role assigned${ansis.reset}`);
        console.log(`  User: ${created.user_id}`);
        console.log(`  Role: ${created.role_name}`);
        console.log(`  Scope: ${created.scope_type || 'global'}`);
      } catch (error: any) {
        console.error(`${status.error}✗ Failed to assign role${ansis.reset}`);
        if (error.response?.status === 401 || error.response?.status === 403) {
          console.error(`${status.warning}  Requires admin role${ansis.reset}`);
        } else if (error.response?.status === 404) {
          console.error(`  User or role not found`);
        } else if (error.response?.status === 409) {
          console.error(`  User already has this role assignment`);
        } else {
          console.error(`  ${error.response?.data?.detail || error.message}`);
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

        console.log(`${status.success}✓ Role assignment removed${ansis.reset}`);
      } catch (error: any) {
        console.error(`${status.error}✗ Failed to remove role assignment${ansis.reset}`);
        if (error.response?.status === 404) {
          console.error(`  Assignment ${assignmentId} not found`);
        } else if (error.response?.status === 401 || error.response?.status === 403) {
          console.error(`${status.warning}  Requires admin role${ansis.reset}`);
        } else {
          console.error(`  ${error.response?.data?.detail || error.message}`);
        }
        process.exit(1);
      }
    });

  rbac.addCommand(userRoles);

  return rbac;
}
