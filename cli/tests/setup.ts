/**
 * Global test setup for Jest
 *
 * Configures test environment and utilities for functional/integration testing
 * of the Knowledge Graph CLI against a real API server.
 */

// Extend Jest timeout for integration tests that start real servers
jest.setTimeout(30000);

// Suppress console output during tests (unless TEST_VERBOSE=true)
if (!process.env.TEST_VERBOSE) {
  global.console = {
    ...console,
    log: jest.fn(),
    debug: jest.fn(),
    info: jest.fn(),
    warn: jest.fn(),
    // Keep error for debugging test failures
    error: console.error,
  };
}

// Set test environment variables
process.env.NODE_ENV = 'test';
process.env.API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000';

// Mock AI provider for tests (no real API calls)
process.env.AI_PROVIDER = 'mock';
process.env.MOCK_MODE = 'default';
