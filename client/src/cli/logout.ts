/**
 * kg logout - End authentication session
 *
 * Revokes OAuth client credentials and clears stored tokens from config file.
 * ADR-054: Updated to support OAuth client revocation.
 */

import { Command } from 'commander';
import { getConfig } from '../lib/config.js';
import { AuthClient } from '../lib/auth/auth-client.js';

interface LogoutOptions {
  forget?: boolean;
}

/**
 * Logout command handler
 */
async function logoutCommand(options: LogoutOptions) {
  const config = getConfig();

  // If --forget flag is set and not logged in, just clear the username
  if (!config.isAuthenticated() && options.forget) {
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
  if (!config.isAuthenticated()) {
    console.log('');
    console.log('\x1b[33m⚠️  Not logged in\x1b[0m');
    console.log('   You are not currently logged in.');
    console.log('');
    console.log('   To login, run:');
    console.log('     \x1b[36mkg login\x1b[0m');
    console.log('');
    process.exit(0);
  }

  const apiUrl = config.getApiUrl();
  const authClient = new AuthClient(apiUrl);

  // Get OAuth credentials (must exist since isAuthenticated() passed)
  const oauthCreds = config.getOAuthCredentials();
  if (!oauthCreds) {
    console.error('\n\x1b[31m❌ Error: No OAuth credentials found\x1b[0m\n');
    process.exit(1);
  }

  const username = oauthCreds.username || 'unknown';

  try {
    try {
      // Get fresh access token to authenticate the revocation request
      const tokenResponse = await authClient.getOAuthToken({
        grant_type: 'client_credentials',
        client_id: oauthCreds.client_id,
        client_secret: oauthCreds.client_secret,
        scope: oauthCreds.scopes.join(' ')
      });

      // Revoke the OAuth client
      await authClient.deletePersonalOAuthClient(tokenResponse.access_token, oauthCreds.client_id);

      // Clear OAuth credentials from config
      config.delete('auth.oauth_client_id');
      config.delete('auth.oauth_client_secret');
      config.delete('auth.oauth_client_name');
      config.delete('auth.oauth_scopes');
      config.delete('auth.oauth_created_at');
    } catch (error: any) {
      // If revocation fails, still clear local credentials
      console.log('');
      console.log('\x1b[33m⚠️  Warning: Failed to revoke OAuth client on server\x1b[0m');
      console.log(`   ${error.message || 'Unknown error'}`);
      console.log('   Clearing local credentials anyway...');
      console.log('');

      // Clear OAuth credentials anyway
      config.delete('auth.oauth_client_id');
      config.delete('auth.oauth_client_secret');
      config.delete('auth.oauth_client_name');
      config.delete('auth.oauth_scopes');
      config.delete('auth.oauth_created_at');
    }

    // Clear saved username if --forget flag is set
    if (options.forget) {
      const savedUsername = config.get('username');
      if (savedUsername) {
        config.delete('username');
        config.delete('auth.username');
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
  } catch (error: any) {
    console.error(`\n\x1b[31m❌ Error: ${error.message}\x1b[0m\n`);
    process.exit(1);
  }
}

/**
 * Logout command object (for documentation generation)
 */
export const logoutCommand_obj = new Command('logout')
  .description('End authentication session - revokes OAuth client and clears credentials (use --forget to also clear saved username)')
  .option('--forget', 'Also forget saved username (requires username prompt on next login)')
  .action(logoutCommand);

/**
 * Register logout command
 */
export function registerLogoutCommand(program: Command): void {
  program.addCommand(logoutCommand_obj);
}
