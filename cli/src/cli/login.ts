/**
 * kg login - Authenticate with username/password (OAuth 2.0)
 *
 * Creates a personal OAuth client using GitHub CLI-style authentication.
 * Stores long-lived client credentials (client_id + client_secret) in config file.
 *
 * ADR-054: Unified OAuth Architecture
 * - All clients use OAuth 2.0 flows (no JWT sessions)
 * - kg CLI uses personal OAuth clients (client credentials grant)
 * - Similar to: gh auth login, gcloud auth login, aws configure
 */

import { Command } from 'commander';
import prompts from 'prompts';
import { getConfig } from '../lib/config.js';
import { AuthClient } from '../lib/auth/auth-client.js';
import { setCommandHelp } from './help-formatter.js';

interface LoginOptions {
  username?: string;
}

/**
 * Login command handler
 */
async function loginCommand(options: LoginOptions) {
  const config = getConfig();

  // Check if already logged in (has OAuth client credentials)
  const existingCreds = config.getOAuthCredentials();
  if (existingCreds) {
    console.log('');
    console.log('\x1b[33m⚠️  Already logged in\x1b[0m');
    console.log(`   Username: ${existingCreds.username || 'unknown'}`);
    console.log(`   Client: ${existingCreds.client_name}`);
    console.log(`   Client ID: ${existingCreds.client_id}`);
    console.log(`   Scopes: ${existingCreds.scopes.join(', ')}`);
    console.log('');
    console.log('   To login as a different user, logout first:');
    console.log('     \x1b[36mkg logout\x1b[0m');
    console.log('');
    process.exit(0);
  }

  console.log('');
  console.log('\x1b[1mKnowledge Graph Login\x1b[0m');
  console.log('');

  // Get username (from option, config, or prompt)
  let username = options.username || config.get('username');
  if (!username) {
    const response = await prompts({
      type: 'text',
      name: 'username',
      message: 'Username',
    });

    // Handle Ctrl+C
    if (response.username === undefined) {
      console.log('\nLogin cancelled.');
      process.exit(0);
    }

    username = response.username;
  } else {
    console.log(`Username: ${username}`);
  }

  if (!username) {
    console.error('\x1b[31m❌ Username is required\x1b[0m\n');
    process.exit(1);
  }

  // Get password (always prompt, never pre-fill for security)
  const passwordResponse = await prompts({
    type: 'password',
    name: 'password',
    message: 'Password',
  });

  // Handle Ctrl+C
  if (passwordResponse.password === undefined) {
    console.log('\nLogin cancelled.');
    process.exit(0);
  }

  const password = passwordResponse.password;

  if (!password) {
    console.error('\x1b[31m❌ Password is required\x1b[0m\n');
    process.exit(1);
  }

  // Create personal OAuth client
  console.log('');
  console.log('Creating OAuth client credentials...');

  try {
    const apiUrl = config.getApiUrl();
    const authClient = new AuthClient(apiUrl);

    // Create personal OAuth client (GitHub CLI-style)
    const oauthClient = await authClient.createPersonalOAuthClient({
      username,
      password,
      scope: 'read:* write:*'
    });

    // Store OAuth client credentials
    config.storeOAuthCredentials({
      client_id: oauthClient.client_id,
      client_secret: oauthClient.client_secret,
      client_name: oauthClient.client_name,
      scopes: oauthClient.scopes,
      created_at: oauthClient.created_at,
      username: username
    });

    // Ask to remember username if it's not already saved
    const savedUsername = config.get('username');
    if (!savedUsername || savedUsername !== username) {
      const rememberResponse = await prompts({
        type: 'confirm',
        name: 'remember',
        message: `Remember username "${username}" for future logins?`,
        initial: true
      });

      if (rememberResponse.remember) {
        config.set('username', username);
      }
    }

    // Display success message
    console.log('');
    console.log('\x1b[32m✅ Logged in successfully!\x1b[0m');
    console.log(`   Username: ${username}`);
    console.log(`   Client ID: ${oauthClient.client_id}`);
    console.log(`   Client Name: ${oauthClient.client_name}`);
    console.log(`   Scopes: ${oauthClient.scopes.join(', ')}`);
    console.log('');
    console.log('   \x1b[1mIMPORTANT:\x1b[0m Your credentials are stored securely in:');
    console.log(`   ${config.getConfigPath()}`);
    console.log('');
    console.log('   \x1b[33m⚠️  Keep your client credentials secure!\x1b[0m');
    console.log('   • These credentials provide full access to your account');
    console.log('   • Run \x1b[36mkg logout\x1b[0m to revoke this client');
    console.log('   • If compromised, logout and login again to rotate credentials');
    console.log('');
  } catch (error: any) {
    if (error.response?.status === 401) {
      console.error('');
      console.error('\x1b[31m❌ Authentication failed\x1b[0m');
      console.error('   Invalid username or password.');
      console.error('');
      process.exit(1);
    } else if (error.code === 'ECONNREFUSED') {
      console.error('');
      console.error('\x1b[31m❌ Connection failed\x1b[0m');
      console.error(`   Could not connect to API server at ${config.getApiUrl()}`);
      console.error('');
      console.error('   Make sure the API server is running:');
      console.error('     \x1b[36m./scripts/start-api.sh\x1b[0m');
      console.error('');
      process.exit(1);
    } else {
      console.error('');
      console.error('\x1b[31m❌ Login failed\x1b[0m');
      console.error(`   ${error.message}`);
      console.error('');
      process.exit(1);
    }
  }
}

/**
 * Login command object (for documentation generation)
 */
export const loginCommand_obj = setCommandHelp(
  new Command('login'),
  'Authenticate with username and password',
  'Authenticate with username and password - creates personal OAuth client credentials (required for admin commands)'
)
  .option('-u, --username <username>', 'Username (will prompt if not provided - can be saved for future logins)')
  .action(loginCommand);

/**
 * Register login command
 */
export function registerLoginCommand(program: Command): void {
  program.addCommand(loginCommand_obj);
}
