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
    const { exitCode } = await execAsync(`${KG_CLI} health`).catch((err) => ({
      exitCode: err.code,
    }));

    expect(exitCode).toBeUndefined(); // undefined means exit code 0
  });
});
