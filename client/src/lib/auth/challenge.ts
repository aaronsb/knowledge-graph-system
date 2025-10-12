/**
 * Authentication Challenge
 *
 * Re-authentication prompt for sensitive operations (e.g., delete user, reset database).
 * Requires user to re-enter password before proceeding.
 */

import * as readline from 'readline';
import { AuthClient, LoginRequest } from './auth-client.js';
import { TokenManager, TokenInfo } from './token-manager.js';

export interface ChallengeOptions {
  reason: string;           // Why re-auth is required (e.g., "Delete user account")
  username?: string;        // Pre-fill username (from current token)
  allowCancel?: boolean;    // Allow user to cancel (default: true)
}

export class AuthChallenge {
  constructor(
    private authClient: AuthClient,
    private tokenManager: TokenManager
  ) {}

  /**
   * Prompt user to re-authenticate for sensitive operation
   *
   * @param options Challenge options
   * @returns New token on success, null on cancel
   * @throws Error if authentication fails
   */
  async challenge(options: ChallengeOptions): Promise<TokenInfo | null> {
    const allowCancel = options.allowCancel !== false;

    console.log('');
    console.log(`\x1b[33m⚠️  Authentication Challenge\x1b[0m`);
    console.log(`   Reason: ${options.reason}`);
    console.log('');
    console.log('   For security, please re-enter your password to continue.');
    if (allowCancel) {
      console.log('   Press Ctrl+C to cancel.');
    }
    console.log('');

    // Get username (use provided or prompt)
    let username = options.username;
    if (!username) {
      username = await this.promptUsername();
    } else {
      console.log(`   Username: ${username}`);
    }

    // Get password (always prompt, never pre-fill for security)
    const password = await this.promptPassword();

    // Validate credentials
    try {
      const loginResponse = await this.authClient.login({ username, password });
      const tokenInfo = TokenManager.fromLoginResponse(loginResponse);

      console.log('   \x1b[32m✅ Authentication successful\x1b[0m');
      console.log('');

      return tokenInfo;
    } catch (error: any) {
      if (error.response?.status === 401) {
        console.error('   \x1b[31m❌ Authentication failed: Invalid username or password\x1b[0m');
        console.log('');

        // Allow retry
        if (allowCancel) {
          const retry = await this.promptRetry();
          if (retry) {
            return this.challenge(options);
          }
        }
      } else {
        console.error('   \x1b[31m❌ Authentication failed:', error.message, '\x1b[0m');
        console.log('');
      }

      return null;
    }
  }

  /**
   * Prompt for username
   */
  private async promptUsername(): Promise<string> {
    return new Promise((resolve) => {
      const rl = readline.createInterface({
        input: process.stdin,
        output: process.stdout
      });

      rl.question('   Username: ', (answer) => {
        rl.close();
        resolve(answer.trim());
      });
    });
  }

  /**
   * Prompt for password (hidden input)
   */
  private async promptPassword(): Promise<string> {
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

      process.stdout.write('   Password: ');

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
   * Prompt to retry after failed authentication
   */
  private async promptRetry(): Promise<boolean> {
    return new Promise((resolve) => {
      const rl = readline.createInterface({
        input: process.stdin,
        output: process.stdout
      });

      rl.question('   Retry? (y/N): ', (answer) => {
        rl.close();
        const retry = answer.trim().toLowerCase() === 'y';
        resolve(retry);
      });
    });
  }
}
