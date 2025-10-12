/**
 * kg logout - End authentication session
 *
 * Clears stored JWT token from config file.
 */

import { Command } from 'commander';
import { getConfig } from '../lib/config.js';
import { TokenManager } from '../lib/auth/token-manager.js';

interface LogoutOptions {
  forget?: boolean;
}

/**
 * Logout command handler
 */
async function logoutCommand(options: LogoutOptions) {
  const config = getConfig();
  const tokenManager = new TokenManager(config);

  // If --forget flag is set and not logged in, just clear the username
  if (!tokenManager.isLoggedIn() && options.forget) {
    const savedUsername = config.get('username');
    if (savedUsername) {
      config.delete('username');
      console.log('');
      console.log('\x1b[32m✅ Forgot saved username\x1b[0m');
      console.log(`   Cleared: ${savedUsername}`);
      console.log('');
      console.log('   To login, run:');
      console.log('     \x1b[36mkg login\x1b[0m');
      console.log('');
    } else {
      console.log('');
      console.log('\x1b[33m⚠️  No saved username to forget\x1b[0m');
      console.log('');
    }
    process.exit(0);
  }

  // Check if logged in (for normal logout)
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

  // Clear saved username if --forget flag is set
  if (options.forget) {
    const savedUsername = config.get('username');
    if (savedUsername) {
      config.delete('username');
      console.log('');
      console.log('\x1b[32m✅ Logged out successfully!\x1b[0m');
      console.log(`   User: ${username}`);
      console.log(`   \x1b[2m(Forgot username "${savedUsername}")\x1b[0m`);
    } else {
      console.log('');
      console.log('\x1b[32m✅ Logged out successfully!\x1b[0m');
      console.log(`   User: ${username}`);
    }
  } else {
    // Display success message
    console.log('');
    console.log('\x1b[32m✅ Logged out successfully!\x1b[0m');
    console.log(`   User: ${username}`);

    const savedUsername = config.get('username');
    if (savedUsername) {
      console.log(`   \x1b[2m(Username "${savedUsername}" remembered for next login)\x1b[0m`);
    }
  }

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
    .description('End authentication session')
    .option('--forget', 'Also forget saved username')
    .action(logoutCommand);
}
