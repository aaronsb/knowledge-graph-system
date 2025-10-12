/**
 * kg logout - End authentication session
 *
 * Clears stored JWT token from config file.
 */

import { Command } from 'commander';
import { getConfig } from '../lib/config.js';
import { TokenManager } from '../lib/auth/token-manager.js';

/**
 * Logout command handler
 */
async function logoutCommand() {
  const config = getConfig();
  const tokenManager = new TokenManager(config);

  // Check if logged in
  if (!tokenManager.isLoggedIn()) {
    console.log('');
    console.log('\x1b[33m⚠️  Not logged in\x1b[0m');
    console.log('   You are not currently logged in.');
    console.log('');
    console.log('   To login, run:');
    console.log('     \x1b[36mkg login\x1b[0m');
    console.log('');
    process.exit(0);
  }

  const username = tokenManager.getUsername();

  // Clear token
  tokenManager.clearToken();

  // Display success message
  console.log('');
  console.log('\x1b[32m✅ Logged out successfully!\x1b[0m');
  console.log(`   User: ${username}`);
  console.log('');
  console.log('   To login again, run:');
  console.log('     \x1b[36mkg login\x1b[0m');
  console.log('');
}

/**
 * Register logout command
 */
export function registerLogoutCommand(program: Command): void {
  program
    .command('logout')
    .description('End authentication session (clear stored token)')
    .action(logoutCommand);
}
