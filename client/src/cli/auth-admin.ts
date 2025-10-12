/**
 * kg admin user - User management commands (admin only)
 *
 * Subcommands: list, get, create, update, delete, apikey
 */

import { Command } from 'commander';
import * as readline from 'readline';
import { getConfig } from '../lib/config.js';
import { AuthClient, UserCreateRequest, UserUpdateRequest } from '../lib/auth/auth-client.js';
import { TokenManager } from '../lib/auth/token-manager.js';
import { AuthChallenge } from '../lib/auth/challenge.js';
import { Table } from '../lib/table.js';

/**
 * Ensure user is logged in and has admin role
 */
function requireAuth(): { token: string; tokenManager: TokenManager; authClient: AuthClient } {
  const config = getConfig();
  const tokenManager = new TokenManager(config);

  if (!tokenManager.isLoggedIn()) {
    console.error('');
    console.error('\x1b[31m❌ Authentication required\x1b[0m');
    console.error('   This command requires authentication.');
    console.error('');
    console.error('   Please login first:');
    console.error('     \x1b[36mkg login\x1b[0m');
    console.error('');
    process.exit(1);
  }

  const tokenInfo = tokenManager.getToken();
  if (!tokenInfo) {
    console.error('\x1b[31m❌ Token expired. Please login again: kg login\x1b[0m\n');
    process.exit(1);
  }

  const apiUrl = config.getApiUrl();
  const authClient = new AuthClient(apiUrl);

  return {
    token: tokenInfo.access_token,
    tokenManager,
    authClient
  };
}

/**
 * Prompt for password (hidden input)
 */
async function promptPassword(confirmRequired: boolean = false): Promise<string> {
  return new Promise((resolve, reject) => {
    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout
    });

    // Disable echo for password input
    const stdin = process.stdin as any;
    const wasRaw = stdin.isRaw;
    if (stdin.setRawMode) {
      stdin.setRawMode(true);
    }

    let password = '';
    let confirming = false;
    let passwordFirst = '';

    const prompt = confirming ? 'Confirm password: ' : 'Password: ';
    process.stdout.write(prompt);

    stdin.on('data', (char: Buffer) => {
      const c = char.toString('utf8');

      switch (c) {
        case '\n':
        case '\r':
        case '\u0004':  // Ctrl+D
          // Enter pressed
          process.stdout.write('\n');

          if (confirmRequired && !confirming) {
            // First password entered, now confirm
            passwordFirst = password;
            password = '';
            confirming = true;
            process.stdout.write('Confirm password: ');
          } else if (confirmRequired && confirming) {
            // Confirmation entered, check match
            stdin.removeAllListeners('data');
            if (stdin.setRawMode) {
              stdin.setRawMode(wasRaw);
            }
            rl.close();

            if (password === passwordFirst) {
              resolve(password);
            } else {
              console.error('\x1b[31m❌ Passwords do not match\x1b[0m');
              reject(new Error('Passwords do not match'));
            }
          } else {
            // No confirmation required
            stdin.removeAllListeners('data');
            if (stdin.setRawMode) {
              stdin.setRawMode(wasRaw);
            }
            rl.close();
            resolve(password);
          }
          break;
        case '\u0003':  // Ctrl+C
          // Cancel
          process.stdout.write('\n');
          stdin.removeAllListeners('data');
          if (stdin.setRawMode) {
            stdin.setRawMode(wasRaw);
          }
          rl.close();
          reject(new Error('Cancelled'));
          break;
        case '\u007f':  // Backspace
          if (password.length > 0) {
            password = password.slice(0, -1);
            process.stdout.write('\b \b');
          }
          break;
        default:
          // Normal character - add to password and show asterisk
          if (c.charCodeAt(0) >= 32) {  // Printable characters only
            password += c;
            process.stdout.write('*');
          }
          break;
      }
    });
  });
}

/**
 * List users command
 */
async function listUsersCommand(options: { role?: string; skip?: number; limit?: number }) {
  const { token, authClient } = requireAuth();

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
  const { token, authClient } = requireAuth();

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
async function createUserCommand(username: string, options: { role: string }) {
  const { token, authClient } = requireAuth();

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

  // Prompt for password
  try {
    const password = await promptPassword(true);

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
  options: { role?: string; password?: boolean; disable?: boolean; enable?: boolean }
) {
  const { token, authClient, tokenManager } = requireAuth();

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
        const newPassword = await promptPassword(true);
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
        // Promoting to admin requires re-authentication
        const challenge = new AuthChallenge(authClient, tokenManager);
        const newToken = await challenge.challenge({
          reason: `Promote user "${user.username}" to admin role`,
          username: tokenManager.getUsername() || undefined,
          allowCancel: true
        });

        if (!newToken) {
          console.log('Operation cancelled.');
          process.exit(0);
        }

        // Use new token for the update
        request.role = options.role as any;
        const updatedUser = await authClient.updateUser(newToken.access_token, parseInt(userId), request);

        console.log('');
        console.log('\x1b[32m✅ User updated successfully!\x1b[0m');
        console.log(`   Username: ${updatedUser.username}`);
        console.log(`   Role: ${updatedUser.role} (changed from ${user.role})`);
        console.log('');
        return;
      } else {
        request.role = options.role as any;
      }
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
  const { token, authClient, tokenManager } = requireAuth();

  try {
    // Get user details first
    const user = await authClient.getUser(token, parseInt(userId));

    console.log('');
    console.log('\x1b[33m⚠️  WARNING: Delete user\x1b[0m');
    console.log(`   This will permanently delete user: ${user.username} (ID: ${user.id})`);
    console.log('   This action cannot be undone!');
    console.log('');

    // Confirm deletion (requires re-authentication)
    const challenge = new AuthChallenge(authClient, tokenManager);
    const newToken = await challenge.challenge({
      reason: `Delete user "${user.username}"`,
      username: tokenManager.getUsername() || undefined,
      allowCancel: true
    });

    if (!newToken) {
      console.log('Operation cancelled.');
      process.exit(0);
    }

    // Delete user
    await authClient.deleteUser(newToken.access_token, parseInt(userId));

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
    .description('Create new user (prompts for password)')
    .requiredOption('--role <role>', 'User role (read_only, contributor, curator, admin)')
    .action(createUserCommand);

  // kg admin user update
  userCommand
    .command('update <user_id>')
    .description('Update user details')
    .option('--role <role>', 'Change user role')
    .option('--password', 'Change password (prompts for new password)')
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
