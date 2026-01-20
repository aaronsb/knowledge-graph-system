import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Allow access from any host in dev mode (container accessed via various hostnames)
    allowedHosts: true,
  },
})
