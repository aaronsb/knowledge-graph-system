/**
 * Jest Global Teardown
 *
 * Runs once after all test suites.
 * Stops the API server.
 */

import { teardownApiServer } from './helpers/api-server';

export default async function globalTeardown() {
  console.log('\n👋 Stopping API server...\n');
  await teardownApiServer();
  console.log('✅ API server stopped\n');
}
