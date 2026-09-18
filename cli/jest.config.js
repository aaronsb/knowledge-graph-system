/** @type {import('jest').Config} */
module.exports = {
  preset: 'ts-jest',
  // tests/** sits outside tsconfig.json's include, so ts-jest is the only
  // type-check those files get. Give it a tsconfig that adds the jest globals.
  // TS151002 (hybrid module kind wants isolatedModules) is informational under
  // nodenext with CJS emit; type-checking stays on.
  transform: {
    '^.+\\.ts$': ['ts-jest', { tsconfig: 'tsconfig.test.json', diagnostics: { ignoreCodes: [151002] } }],
  },
  testEnvironment: 'node',
  roots: ['<rootDir>/src', '<rootDir>/tests'],
  testMatch: ['**/__tests__/**/*.ts', '**/*.test.ts', '**/*.spec.ts'],
  moduleFileExtensions: ['ts', 'js', 'json'],
  collectCoverageFrom: [
    'src/**/*.ts',
    '!src/**/*.d.ts',
    '!src/version.ts', // Generated file
  ],
  coverageDirectory: 'coverage',
  coverageReporters: ['text', 'lcov', 'html'],
  verbose: true,

  // Timeout for tests (some may need to start API server)
  testTimeout: 30000,

  // Setup file for global test configuration
  setupFilesAfterEnv: ['<rootDir>/tests/setup.ts'],

  // Global setup/teardown to start/stop API server
  globalSetup: '<rootDir>/tests/globalSetup.ts',
  globalTeardown: '<rootDir>/tests/globalTeardown.ts',
};
