/**
 * Health command functional tests
 *
 * Tests: kg health
 * Tests CLI health check against real API server
 */

import { exec } from 'child_process';
import { promisify } from 'util';
import { getApiServer } from '../helpers/api-server';

const execAsync = promisify(exec);
const KG_CLI = 'node dist/index.js';

describe('kg health', () => {
  beforeAll(async () => {
    // Ensure API server is running
    const server = getApiServer();
    const isRunning = await server.isRunning();
    if (!isRunning) {
      await server.start();
    }
  });

  it('should return healthy status', async () => {
    const { stdout } = await execAsync(`${KG_CLI} health`);

    expect(stdout).toContain('healthy');
  }, 10000);

  it('should exit with code 0 on success', async () => {
    try {
      await execAsync(`${KG_CLI} health`);
      // If no error thrown, exit code was 0
      expect(true).toBe(true);
    } catch (error: any) {
      // Should not throw on success
      fail(`Command failed with exit code ${error.code}: ${error.message}`);
    }
  });
});
