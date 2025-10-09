/**
 * Jest Global Setup
 *
 * Runs once before all test suites.
 * Starts the API server for functional/integration tests.
 */

import { setupApiServer } from './helpers/api-server';

export default async function globalSetup() {
  console.log('\n🚀 Starting API server for tests...\n');
  await setupApiServer();
  console.log('✅ API server ready\n');
}
