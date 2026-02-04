/**
 * API Server Test Helper
 *
 * Manages starting/stopping the FastAPI server for integration tests.
 * Tests run against a real API server (no mocks) for functional coverage.
 */

import { spawn, ChildProcess } from 'child_process';
import axios from 'axios';
import * as path from 'path';

export class ApiServerHelper {
  private process: ChildProcess | null = null;
  private readonly baseUrl: string;
  private readonly serverPath: string;
  private readonly maxStartupTime = 15000; // 15 seconds

  constructor(baseUrl: string = 'http://localhost:8000') {
    this.baseUrl = baseUrl;
    // Path to API server relative to client/tests
    this.serverPath = path.resolve(__dirname, '../../../api/app/main.py');
  }

  /**
   * Start the API server and wait for it to be ready
   */
  async start(): Promise<void> {
    if (this.process) {
      throw new Error('API server already running');
    }

    // Start uvicorn server
    this.process = spawn(
      'python3',
      [
        '-m', 'uvicorn',
        'api.app.main:app',
        '--host', '0.0.0.0',
        '--port', '8000',
        '--log-level', 'warning'
      ],
      {
        cwd: path.resolve(__dirname, '../../..'), // Project root
        env: {
          ...process.env,
          AI_PROVIDER: 'mock',
          MOCK_MODE: 'default',
          JOB_DB_PATH: ':memory:',
          QUEUE_TYPE: 'inmemory',
        },
        stdio: ['ignore', 'pipe', 'pipe']
      }
    );

    // Capture output for debugging
    if (process.env.TEST_VERBOSE) {
      this.process.stdout?.on('data', (data) => {
        console.log(`[API] ${data.toString()}`);
      });
    }

    this.process.stderr?.on('data', (data) => {
      if (process.env.TEST_VERBOSE) {
        console.error(`[API ERROR] ${data.toString()}`);
      }
    });

    // Wait for server to be ready
    await this.waitForReady();
  }

  /**
   * Stop the API server
   */
  async stop(): Promise<void> {
    if (!this.process) {
      return;
    }

    return new Promise((resolve) => {
      this.process!.on('exit', () => {
        this.process = null;
        resolve();
      });

      this.process!.kill('SIGTERM');

      // Force kill after 5 seconds if not exited
      setTimeout(() => {
        if (this.process) {
          this.process.kill('SIGKILL');
        }
      }, 5000);
    });
  }

  /**
   * Wait for server to respond to health check
   */
  private async waitForReady(): Promise<void> {
    const startTime = Date.now();

    while (Date.now() - startTime < this.maxStartupTime) {
      try {
        const response = await axios.get(`${this.baseUrl}/health`, {
          timeout: 1000,
        });

        if (response.status === 200 && response.data.status === 'healthy') {
          return; // Server is ready
        }
      } catch (error) {
        // Server not ready yet, continue waiting
      }

      // Wait 500ms before next attempt
      await new Promise(resolve => setTimeout(resolve, 500));
    }

    throw new Error(`API server failed to start within ${this.maxStartupTime}ms`);
  }

  /**
   * Check if server is running
   */
  async isRunning(): Promise<boolean> {
    try {
      const response = await axios.get(`${this.baseUrl}/health`, {
        timeout: 1000,
      });
      return response.status === 200;
    } catch {
      return false;
    }
  }

  /**
   * Get base URL
   */
  getBaseUrl(): string {
    return this.baseUrl;
  }
}

// Global server instance for tests
let globalServer: ApiServerHelper | null = null;

/**
 * Get or create global API server instance
 */
export function getApiServer(): ApiServerHelper {
  if (!globalServer) {
    globalServer = new ApiServerHelper();
  }
  return globalServer;
}

/**
 * Jest global setup to start API server before all tests
 */
export async function setupApiServer(): Promise<void> {
  const server = getApiServer();
  await server.start();
}

/**
 * Jest global teardown to stop API server after all tests
 */
export async function teardownApiServer(): Promise<void> {
  const server = getApiServer();
  await server.stop();
}
