/**
 * kg oauth - OAuth client management commands (ADR-054)
 *
 * Manage personal OAuth clients for CLI, MCP, scripts, etc.
 */

import { Command } from 'commander';
import { getConfig } from '../lib/config.js';
import { AuthClient } from '../lib/auth/auth-client.js';
import { Table } from '../lib/table.js';
import { createClientFromEnv } from '../api/client.js';
import axios from 'axios';

/**
 * Require authentication and return OAuth access token
 */
async function requireAuth(): Promise<{ token: string; authClient: AuthClient; username: string }> {
  const config = getConfig();

  if (!config.isAuthenticated()) {
    console.error('\x1b[31m❌ Authentication required\x1b[0m');
    console.error('   Please login first: kg login');
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
 * List personal OAuth clients
 */
async function listClientsCommand() {
  try {
    const { token } = await requireAuth();
    const config = getConfig();
    const apiUrl = config.getApiUrl();

    // Call API to list personal OAuth clients
    const response = await axios.get(`${apiUrl}/auth/oauth/clients/personal`, {
      headers: { Authorization: `Bearer ${token}` }
    });

    const { clients, total } = response.data;

    if (total === 0) {
      console.log('\n\x1b[33m⚠️  No OAuth clients found\x1b[0m');
      console.log('   Create one with: kg login\n');
      return;
    }

    // Display as table
    const table = new Table({
      columns: [
        { header: 'Client ID', field: 'client_id', type: 'value', width: 'auto' },
        { header: 'Name', field: 'client_name', type: 'value', width: 'auto' },
        { header: 'Scopes', field: 'scopes', type: 'value', width: 'auto' },
        { header: 'Created', field: 'created_at', type: 'timestamp', width: 'auto' },
        { header: 'Status', field: 'is_active', type: 'text', width: 'auto',
          customFormat: (val: boolean) => val ? '\x1b[32m✓ Active\x1b[0m' : '\x1b[31m✗ Inactive\x1b[0m'
        }
      ]
    });

    const tableData = clients.map((client: any) => ({
      ...client,
      scopes: client.scopes.join(', ')
    }));

    console.log('');
    table.print(tableData);
    console.log('');
    console.log(`\x1b[2mShowing ${total} client(s)\x1b[0m`);
    console.log('');

  } catch (error: any) {
    console.error(`\n\x1b[31m❌ Error: ${error.message}\x1b[0m\n`);
    process.exit(1);
  }
}

/**
 * Create MCP OAuth client and display config
 */
async function createMcpClientCommand(options: { name?: string }) {
  try {
    const { token, username } = await requireAuth();
    const config = getConfig();
    const apiUrl = config.getApiUrl();

    const clientName = options.name || `kg MCP Server (${username})`;

    console.log('\n🔐 Creating OAuth client for MCP server...\n');

    // Create additional personal OAuth client (using bearer token)
    const formData = new URLSearchParams();
    formData.append('client_name', clientName);
    formData.append('scope', 'read:* write:*');

    const response = await axios.post(
      `${apiUrl}/auth/oauth/clients/personal/new`,
      formData,
      {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/x-www-form-urlencoded'
        }
      }
    );

    const client = response.data;

    console.log('\x1b[32m✅ OAuth client created successfully!\x1b[0m\n');
    console.log('═'.repeat(80));
    console.log('\x1b[1mCLAUDE DESKTOP CONFIG\x1b[0m');
    console.log('═'.repeat(80));
    console.log('');
    console.log('Add this to your Claude Desktop config:');
    console.log('');
    console.log('  "knowledge-graph": {');
    console.log('    "command": "kg-mcp-server",');
    console.log('    "env": {');
    console.log(`      "KG_OAUTH_CLIENT_ID": "${client.client_id}",`);
    console.log(`      "KG_OAUTH_CLIENT_SECRET": "${client.client_secret}",`);
    console.log('      "KG_API_URL": "http://localhost:8000"');
    console.log('    }');
    console.log('  }');
    console.log('');
    console.log('═'.repeat(80));
    console.log('');
    console.log('\x1b[33m⚠️  IMPORTANT:\x1b[0m');
    console.log('  • Keep these credentials secure!');
    console.log('  • Client secret is shown only once');
    console.log('  • To revoke: \x1b[36mkg oauth revoke ' + client.client_id + '\x1b[0m');
    console.log('');

    // Also show command to add via claude mcp
    console.log('\x1b[2mOr add using claude CLI:\x1b[0m');
    console.log('');
    console.log(`  claude mcp add knowledge-graph kg-mcp-server \\`);
    console.log(`    --env KG_OAUTH_CLIENT_ID=${client.client_id} \\`);
    console.log(`    --env KG_OAUTH_CLIENT_SECRET=${client.client_secret} \\`);
    console.log(`    --env KG_API_URL=http://localhost:8000 \\`);
    console.log(`    -s local`);
    console.log('');

  } catch (error: any) {
    console.error(`\n\x1b[31m❌ Error: ${error.response?.data?.detail || error.message}\x1b[0m\n`);
    process.exit(1);
  }
}

/**
 * Revoke OAuth client
 */
async function revokeClientCommand(clientId: string, options: { force?: boolean }) {
  try {
    const { token, authClient } = await requireAuth();
    const config = getConfig();
    const currentClient = config.getOAuthCredentials();

    // Check if user is trying to revoke their current CLI client
    if (currentClient && currentClient.client_id === clientId) {
      if (!options.force) {
        console.log('\n\x1b[33m⚠️  Warning: This is your current CLI OAuth client\x1b[0m');
        console.log(`   Client ID: ${clientId}`);
        console.log('   Revoking this will log you out.');
        console.log('');
        console.log('   To proceed, use: \x1b[36mkg oauth revoke ' + clientId + ' --force\x1b[0m');
        console.log('   Or use: \x1b[36mkg logout\x1b[0m\n');
        process.exit(0);
      }
    }

    console.log(`\n🗑️  Revoking OAuth client ${clientId}...\n`);

    // Delete the OAuth client
    await authClient.deletePersonalOAuthClient(token, clientId);

    console.log('\x1b[32m✅ OAuth client revoked successfully!\x1b[0m\n');

    // If they revoked their current client, clear config
    if (currentClient && currentClient.client_id === clientId) {
      config.delete('auth.oauth_client_id');
      config.delete('auth.oauth_client_secret');
      config.delete('auth.oauth_client_name');
      config.delete('auth.oauth_scopes');
      config.delete('auth.oauth_created_at');

      console.log('\x1b[33m⚠️  You have been logged out\x1b[0m');
      console.log('   To login again: \x1b[36mkg login\x1b[0m\n');
    }

  } catch (error: any) {
    console.error(`\n\x1b[31m❌ Error: ${error.response?.data?.detail || error.message}\x1b[0m\n`);
    process.exit(1);
  }
}

/**
 * OAuth command group object (for documentation generation)
 */
export const oauthCommand = new Command('oauth')
  .description('Manage OAuth clients (list, create for MCP, revoke)');

oauthCommand
  .command('clients')
  .alias('list')
  .description('List your personal OAuth clients')
  .action(listClientsCommand);

oauthCommand
  .command('create-mcp')
  .description('Create OAuth client for MCP server and display config')
  .option('--name <name>', 'Custom client name')
  .action(createMcpClientCommand);

oauthCommand
  .command('revoke <client-id>')
  .description('Revoke an OAuth client')
  .option('--force', 'Force revocation even if it\'s your current CLI client')
  .action(revokeClientCommand);

/**
 * Register oauth command group
 */
export function registerOAuthCommand(program: Command): void {
  program.addCommand(oauthCommand);
}
