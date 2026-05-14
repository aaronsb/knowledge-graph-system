/// <reference types="vitest" />
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// Separate config (not vite.config.ts) so the dev container's bind-mount
// of vite.config.ts doesn't need to be re-established when running tests.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    // setupFiles run before any test module imports — necessary for the
    // localStorage shim Zustand persist captures at module load time.
    setupFiles: ['./src/test-setup.ts'],
  },
});
