/**
 * kg admin user - User management commands (admin only)
 *
 * Subcommands: list, get, create, update, delete, apikey
 */

import { Command } from 'commander';
import prompts from 'prompts';
import { getConfig } from '../lib/config.js';
import { AuthClient, UserCreateRequest, UserUpdateRequest } from '../lib/auth/auth-client.js';
import { TokenManager } from '../lib/auth/token-manager.js';
import { AuthChallenge } from '../lib/auth/challenge.js';
import { Table } from '../lib/table.js';

/**
 * Ensure user is logged in (has OAuth credentials or valid token)
 *
 * ADR-054: Updated to support OAuth client credentials
 * - Checks for OAuth credentials first (preferred)
 * - Falls back to legacy JWT tokens
 * - Gets fresh OAuth access token if using client credentials
 */
async function requireAuth(): Promise<{ token: string; authClient: AuthClient; username: string }> {
  const config = getConfig();

  // Check if user is authenticated (OAuth credentials or JWT token)
  if (!config.isAuthenticated()) {
    console.error('');
    console.error('\x1b[31m❌ Authentication required\x1b[0m');
    console.error('   This command requires authentication.');
    console.error('');
    console.error('   Please login first:');
    console.error('     \x1b[36mkg login\x1b[0m');
    console.error('');
    process.exit(1);
  }

  const apiUrl = config.getApiUrl();
  const authClient = new AuthClient(apiUrl);

  // Get OAuth client credentials (ADR-054)
  const oauthCreds = config.getOAuthCredentials();
  if (!oauthCreds) {
    console.error('\x1b[31m❌ No OAuth credentials found. Please login: kg login\x1b[0m\n');
    process.exit(1);
  }

  // Get fresh access token using client credentials grant
  const tokenResponse = await authClient.getOAuthToken({
    grant_type: 'client_credentials',
    client_id: oauthCreds.client_id,
    client_secret: oauthCreds.client_secret,
    scope: oauthCreds.scopes.join(' ')
  });

  return {
    token: tokenResponse.access_token,
    authClient,
    username: oauthCreds.username || 'unknown'
  };
}

/**
 * Prompt for password (hidden input)
 */
async function promptPassword(confirmRequired: boolean = false): Promise<string> {
  const response = await prompts({
    type: 'password',
    name: 'password',
    message: 'Password',
  });

  // Handle Ctrl+C
  if (response.password === undefined) {
    throw new Error('Cancelled');
  }

  const password = response.password;

  if (!confirmRequired) {
    return password;
  }

  // Confirm password
  const confirmResponse = await prompts({
    type: 'password',
    name: 'password',
    message: 'Confirm password',
  });

  // Handle Ctrl+C
  if (confirmResponse.password === undefined) {
    throw new Error('Cancelled');
  }

  if (password !== confirmResponse.password) {
    console.error('\x1b[31m❌ Passwords do not match\x1b[0m');
    throw new Error('Passwords do not match');
  }

  return password;
}

/**
 * List users command
 */
async function listUsersCommand(options: { role?: string; skip?: number; limit?: number }) {
  const { token, authClient } = await requireAuth();

  try {
    const skip = options.skip || 0;
    const limit = options.limit || 50;
    const response = await authClient.listUsers(token, skip, limit, options.role);

    if (response.users.length === 0) {
      console.log('');
      console.log('No users found.');
      console.log('');
      return;
    }

    // Format as table using Table utility
    const table = new Table({
      columns: [
        { header: 'ID', field: 'id', width: 'auto', type: 'value' },
        { header: 'Username', field: 'username', width: 'auto', type: 'text' },
        { header: 'Role', field: 'role', width: 'auto', type: 'value' },
        { header: 'Created', field: 'created_at', width: 'auto', type: 'timestamp' },
        {
          header: 'Last Login',
          field: 'last_login',
          width: 'auto',
          type: 'timestamp',
          customFormat: (val) => val || 'Never'
        },
        {
          header: 'Status',
          field: 'disabled',
          width: 'auto',
          type: 'text',
          customFormat: (val) => val ? '\x1b[31mDisabled\x1b[0m' : '\x1b[32mActive\x1b[0m'
        }
      ]
    });

    table.print(response.users);

    if (response.total > skip + limit) {
      console.log(`Showing ${skip + 1}-${skip + response.users.length} of ${response.total}`);
      console.log(`Use --skip and --limit for pagination\n`);
    }
  } catch (error: any) {
    if (error.response?.status === 403) {
      console.error('\n\x1b[31m❌ Permission denied\x1b[0m');
      console.error('   This command requires admin role.\n');
    } else {
      console.error(`\n\x1b[31m❌ Error: ${error.message}\x1b[0m\n`);
    }
    process.exit(1);
  }
}

/**
 * Get user command
 */
async function getUserCommand(userId: string) {
  const { token, authClient } = await requireAuth();

  try {
    const user = await authClient.getUser(token, parseInt(userId));

    console.log('');
    console.log('\x1b[1mUser Details\x1b[0m');
    console.log('');
    console.log(`ID:         ${user.id}`);
    console.log(`Username:   ${user.username}`);
    console.log(`Role:       ${user.role}`);
    console.log(`Created:    ${new Date(user.created_at).toLocaleString()}`);
    console.log(`Last Login: ${user.last_login ? new Date(user.last_login).toLocaleString() : 'Never'}`);
    console.log(`Status:     ${user.disabled ? '\x1b[31mDisabled\x1b[0m' : '\x1b[32mActive\x1b[0m'}`);
    console.log('');
  } catch (error: any) {
    if (error.response?.status === 404) {
      console.error(`\n\x1b[31m❌ User not found: ${userId}\x1b[0m\n`);
    } else if (error.response?.status === 403) {
      console.error('\n\x1b[31m❌ Permission denied\x1b[0m');
      console.error('   This command requires admin role.\n');
    } else {
      console.error(`\n\x1b[31m❌ Error: ${error.message}\x1b[0m\n`);
    }
    process.exit(1);
  }
}

/**
 * Create user command
 */
async function createUserCommand(username: string, options: { role: string; password?: string }) {
  const { token, authClient } = await requireAuth();

  // Validate role
  const validRoles = ['read_only', 'contributor', 'curator', 'admin'];
  if (!validRoles.includes(options.role)) {
    console.error(`\n\x1b[31m❌ Invalid role: ${options.role}\x1b[0m`);
    console.error(`   Valid roles: ${validRoles.join(', ')}\n`);
    process.exit(1);
  }

  console.log('');
  console.log(`Creating user: ${username}`);
  console.log(`Role: ${options.role}`);
  console.log('');

  // Get password (from option or prompt)
  try {
    const password = options.password || await promptPassword(true);

    const request: UserCreateRequest = {
      username,
      password,
      role: options.role as any
    };

    const user = await authClient.createUser(token, request);

    console.log('');
    console.log('\x1b[32m✅ User created successfully!\x1b[0m');
    console.log(`   ID: ${user.id}`);
    console.log(`   Username: ${user.username}`);
    console.log(`   Role: ${user.role}`);
    console.log(`   Created: ${new Date(user.created_at).toLocaleString()}`);
    console.log('');
  } catch (error: any) {
    if (error.message === 'Passwords do not match' || error.message === 'Cancelled') {
      process.exit(1);
    }

    if (error.response?.status === 400) {
      console.error('\n\x1b[31m❌ Validation error\x1b[0m');
      console.error(`   ${error.response.data.detail || 'Invalid user data'}\n`);
    } else if (error.response?.status === 409) {
      console.error('\n\x1b[31m❌ Username already exists\x1b[0m');
      console.error(`   Username "${username}" is already taken.\n`);
    } else if (error.response?.status === 403) {
      console.error('\n\x1b[31m❌ Permission denied\x1b[0m');
      console.error('   This command requires admin role.\n');
    } else {
      console.error(`\n\x1b[31m❌ Error: ${error.message}\x1b[0m\n`);
    }
    process.exit(1);
  }
}

/**
 * Update user command
 */
async function updateUserCommand(
  userId: string,
  options: { role?: string; password?: string | boolean; disable?: boolean; enable?: boolean }
) {
  const { token, authClient, username: currentUsername } = await requireAuth();

  // Validate role if provided
  if (options.role) {
    const validRoles = ['read_only', 'contributor', 'curator', 'admin'];
    if (!validRoles.includes(options.role)) {
      console.error(`\n\x1b[31m❌ Invalid role: ${options.role}\x1b[0m`);
      console.error(`   Valid roles: ${validRoles.join(', ')}\n`);
      process.exit(1);
    }
  }

  try {
    // Get user details first
    const user = await authClient.getUser(token, parseInt(userId));

    console.log('');
    console.log(`Updating user: ${user.username} (ID: ${user.id})`);
    console.log('');

    const request: UserUpdateRequest = {};

    // Handle password change
    if (options.password) {
      try {
        // If password is a string, use it directly; if true, prompt for it
        const newPassword = typeof options.password === 'string'
          ? options.password
          : await promptPassword(true);
        request.password = newPassword;
      } catch (error: any) {
        if (error.message === 'Passwords do not match' || error.message === 'Cancelled') {
          process.exit(1);
        }
        throw error;
      }
    }

    // Handle role change (requires challenge if promoting to admin)
    if (options.role) {
      if (options.role === 'admin' && user.role !== 'admin') {
        // TODO(ADR-054): Re-implement AuthChallenge with OAuth support for sensitive operations
        console.log('');
        console.log(`\x1b[33m⚠️  Warning: Promoting user "${user.username}" to admin role\x1b[0m`);
        console.log('');
      }
      request.role = options.role as any;
    }

    // Handle disable/enable
    if (options.disable) {
      request.disabled = true;
    } else if (options.enable) {
      request.disabled = false;
    }

    // Update user
    const updatedUser = await authClient.updateUser(token, parseInt(userId), request);

    console.log('');
    console.log('\x1b[32m✅ User updated successfully!\x1b[0m');
    console.log(`   ID: ${updatedUser.id}`);
    console.log(`   Username: ${updatedUser.username}`);
    console.log(`   Role: ${updatedUser.role}`);
    console.log(`   Status: ${updatedUser.disabled ? '\x1b[31mDisabled\x1b[0m' : '\x1b[32mActive\x1b[0m'}`);
    console.log('');
  } catch (error: any) {
    if (error.response?.status === 404) {
      console.error(`\n\x1b[31m❌ User not found: ${userId}\x1b[0m\n`);
    } else if (error.response?.status === 403) {
      console.error('\n\x1b[31m❌ Permission denied\x1b[0m');
      console.error('   This command requires admin role.\n');
    } else if (error.response?.status === 400) {
      console.error('\n\x1b[31m❌ Validation error\x1b[0m');
      console.error(`   ${error.response.data.detail || 'Invalid user data'}\n`);
    } else {
      console.error(`\n\x1b[31m❌ Error: ${error.message}\x1b[0m\n`);
    }
    process.exit(1);
  }
}

/**
 * Delete user command
 */
async function deleteUserCommand(userId: string, options: { yes?: boolean }) {
  const { token, authClient } = await requireAuth();

  try {
    // Get user details first
    const user = await authClient.getUser(token, parseInt(userId));

    console.log('');
    console.log('\x1b[33m⚠️  WARNING: Delete user\x1b[0m');
    console.log(`   This will permanently delete user: ${user.username} (ID: ${user.id})`);
    console.log('   This action cannot be undone!');
    console.log('');

    // TODO(ADR-054): Re-implement AuthChallenge with OAuth support
    // For now, require manual confirmation
    if (!options.yes) {
      const confirmation = await prompts({
        type: 'confirm',
        name: 'confirm',
        message: `Are you sure you want to delete user "${user.username}"?`,
        initial: false
      });

      if (!confirmation.confirm) {
        console.log('Operation cancelled.');
        process.exit(0);
      }
    }

    // Delete user
    await authClient.deleteUser(token, parseInt(userId));

    console.log('');
    console.log('\x1b[32m✅ User deleted successfully!\x1b[0m');
    console.log(`   Username: ${user.username}`);
    console.log(`   ID: ${user.id}`);
    console.log('');
  } catch (error: any) {
    if (error.response?.status === 404) {
      console.error(`\n\x1b[31m❌ User not found: ${userId}\x1b[0m\n`);
    } else if (error.response?.status === 403) {
      console.error('\n\x1b[31m❌ Permission denied\x1b[0m');
      console.error('   This command requires admin role.\n');
    } else if (error.response?.status === 400 && error.response.data.detail?.includes('delete yourself')) {
      console.error('\n\x1b[31m❌ Cannot delete yourself\x1b[0m');
      console.error('   You cannot delete your own user account.\n');
    } else {
      console.error(`\n\x1b[31m❌ Error: ${error.message}\x1b[0m\n`);
    }
    process.exit(1);
  }
}

/**
 * Register admin user commands
 */
export function registerAuthAdminCommand(program: Command): void {
  const userCommand = program
    .command('user')
    .description('User management commands (admin only)');

  // kg admin user list
  userCommand
    .command('list')
    .description('List all users')
    .option('--role <role>', 'Filter by role (read_only, contributor, curator, admin)')
    .option('--skip <n>', 'Skip first N users (pagination)', '0')
    .option('--limit <n>', 'Limit results (default: 50)', '50')
    .action((options) => listUsersCommand({
      role: options.role,
      skip: parseInt(options.skip),
      limit: parseInt(options.limit)
    }));

  // kg admin user get
  userCommand
    .command('get <user_id>')
    .description('Get user details by ID')
    .action(getUserCommand);

  // kg admin user create
  userCommand
    .command('create <username>')
    .description('Create new user')
    .requiredOption('--role <role>', 'User role (read_only, contributor, curator, admin)')
    .option('-p, --password <password>', 'Password (prompts if not provided)')
    .action(createUserCommand);

  // kg admin user update
  userCommand
    .command('update <user_id>')
    .description('Update user details')
    .option('--role <role>', 'Change user role')
    .option('-p, --password [password]', 'Change password (prompts if no value provided)')
    .option('--disable', 'Disable user account')
    .option('--enable', 'Enable user account')
    .action(updateUserCommand);

  // kg admin user delete
  userCommand
    .command('delete <user_id>')
    .description('Delete user (requires re-authentication)')
    .option('--yes', 'Skip confirmation prompt')
    .action(deleteUserCommand);
}
