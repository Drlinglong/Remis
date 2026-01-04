import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
const backendPort = process.env.BACKEND_PORT || 8081;
console.log(`[Vite Config] Proxying /api to http://127.0.0.1:${backendPort}`);

export default defineConfig({
  plugins: [react()],
  base: './',
  server: {
    port: 5174,
    host: '127.0.0.1',
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${backendPort}`,
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/setupTests.js',
  },
})