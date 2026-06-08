import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

// https://vite.dev/config/
const __dirname = dirname(fileURLToPath(import.meta.url));
const packageJson = JSON.parse(readFileSync(join(__dirname, 'package.json'), 'utf-8'));
const backendPort = process.env.VITE_BACKEND_PORT || process.env.REMIS_BACKEND_PORT || process.env.BACKEND_PORT || 1453;
console.log(`[Vite Config] Proxying /api to http://127.0.0.1:${backendPort}`);

export default defineConfig({
  plugins: [
    react()
  ],
  base: './',
  define: {
    __APP_VERSION__: JSON.stringify(packageJson.version),
  },
  server: {
    port: 5174,
    strictPort: true,
    host: '127.0.0.1',
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${backendPort}`,
        changeOrigin: true,
      },
    },
  },
  build: {
    chunkSizeWarningLimit: 2800,
    rollupOptions: {
      output: {
        manualChunks(id) {
          const normalized = id.replace(/\\/g, '/');
          if (!normalized.includes('/node_modules/')) return undefined;
          if (normalized.includes('/@monaco-editor/')) {
            return 'vendor-monaco';
          }
          if (normalized.includes('/monaco-editor/')) {
            return 'vendor-monaco';
          }
          if (normalized.includes('/@mantine/')) {
            return 'vendor-mantine';
          }
          if (
            normalized.includes('/react/') ||
            normalized.includes('/react-dom/') ||
            normalized.includes('/react-router') ||
            normalized.includes('/scheduler/')
          ) {
            return 'vendor-react';
          }
          if (normalized.includes('/@tabler/icons-react/')) {
            return 'vendor-icons';
          }
          if (normalized.includes('/recharts/') || normalized.includes('/d3-')) {
            return 'vendor-charts';
          }
          if (
            normalized.includes('/konva/') ||
            normalized.includes('/react-konva/')
          ) {
            return 'vendor-konva';
          }
          if (normalized.includes('/html2canvas/')) {
            return 'vendor-html2canvas';
          }
          if (
            normalized.includes('/react-markdown/') ||
            normalized.includes('/remark-') ||
            normalized.includes('/rehype-') ||
            normalized.includes('/micromark') ||
            normalized.includes('/mdast-') ||
            normalized.includes('/hast-') ||
            normalized.includes('/unist-')
          ) {
            return 'vendor-markdown';
          }
          if (normalized.includes('/@tauri-apps/')) {
            return 'vendor-tauri';
          }
          if (normalized.includes('/@dnd-kit/')) {
            return 'vendor-dnd';
          }
          if (normalized.includes('/i18next') || normalized.includes('/react-i18next/')) {
            return 'vendor-i18n';
          }
          return undefined;
        },
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/setupTests.js',
  },
})
