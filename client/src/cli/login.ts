/**
 * kg login - Authenticate with username/password
 *
 * Prompts for username and password, calls /auth/login endpoint,
 * and stores JWT token in config file.
 */

import { Command } from 'commander';
import * as readline from 'readline';
import { getConfig } from '../lib/config.js';
import { AuthClient } from '../lib/auth/auth-client.js';
import { TokenManager } from '../lib/auth/token-manager.js';

interface LoginOptions {
  username?: string;
}

/**
 * Prompt for input (username)
 */
async function promptInput(question: string, defaultValue?: string): Promise<string> {
  return new Promise((resolve) => {
    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout
    });

    const prompt = defaultValue ? `${question} [${defaultValue}]: ` : `${question}: `;

    rl.question(prompt, (answer) => {
      rl.close();
      resolve(answer.trim() || defaultValue || '');
    });
  });
}

/**
 * Prompt for password (hidden input)
 */
async function promptPassword(): Promise<string> {
  return new Promise((resolve) => {
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

    process.stdout.write('Password: ');

    stdin.on('data', (char: Buffer) => {
      const c = char.toString('utf8');

      switch (c) {
        case '\n':
        case '\r':
        case '\u0004':  // Ctrl+D
          // Enter pressed - submit password
          process.stdout.write('\n');
          stdin.removeAllListeners('data');
          if (stdin.setRawMode) {
            stdin.setRawMode(wasRaw);
          }
          rl.close();
          resolve(password);
          break;
        case '\u0003':  // Ctrl+C
          // Cancel
          process.stdout.write('\n');
          stdin.removeAllListeners('data');
          if (stdin.setRawMode) {
            stdin.setRawMode(wasRaw);
          }
          rl.close();
          console.log('\nLogin cancelled.');
          process.exit(0);
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
 * Login command handler
 */
async function loginCommand(options: LoginOptions) {
  const config = getConfig();
  const tokenManager = new TokenManager(config);

  // Check if already logged in
  if (tokenManager.isLoggedIn()) {
    const currentUsername = tokenManager.getUsername();
    const currentRole = tokenManager.getRole();
    const expiresIn = tokenManager.getMinutesUntilExpiration();

    console.log('');
    console.log('\x1b[33m⚠️  Already logged in\x1b[0m');
    console.log(`   Username: ${currentUsername}`);
    console.log(`   Role: ${currentRole}`);
    console.log(`   Token expires in: ${expiresIn} minutes`);
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
    username = await promptInput('Username');
  } else {
    console.log(`Username: ${username}`);
  }

  if (!username) {
    console.error('\x1b[31m❌ Username is required\x1b[0m\n');
    process.exit(1);
  }

  // Get password (always prompt, never pre-fill for security)
  const password = await promptPassword();

  if (!password) {
    console.error('\x1b[31m❌ Password is required\x1b[0m\n');
    process.exit(1);
  }

  // Attempt login
  console.log('');
  console.log('Authenticating...');

  try {
    const apiUrl = config.getApiUrl();
    const authClient = new AuthClient(apiUrl);

    const loginResponse = await authClient.login({ username, password });

    // Store token
    const tokenInfo = TokenManager.fromLoginResponse(loginResponse);
    tokenManager.storeToken(tokenInfo);

    // Display success message
    console.log('');
    console.log('\x1b[32m✅ Logged in successfully!\x1b[0m');
    console.log(`   Username: ${loginResponse.user.username}`);
    console.log(`   Role: ${loginResponse.user.role}`);
    console.log(`   Token expires: ${tokenManager.getExpirationString()} (in ${loginResponse.expires_in / 60} minutes)`);
    console.log('');
    console.log('   Run \x1b[36mkg logout\x1b[0m to end your session.');
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
 * Register login command
 */
export function registerLoginCommand(program: Command): void {
  program
    .command('login')
    .description('Authenticate with username and password')
    .option('-u, --username <username>', 'Username (will prompt if not provided)')
    .action(loginCommand);
}
