import { resolve } from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  base: '/Remis/',
  plugins: [react()],
  server: {
    open: '/Remis/',
  },
  preview: {
    open: '/Remis/',
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        home: resolve(import.meta.dirname, 'index.html'),
        engineering: resolve(import.meta.dirname, 'engineering/index.html'),
        aventine: resolve(import.meta.dirname, 'aventine/index.html'),
        codex: resolve(import.meta.dirname, 'codex/index.html'),
        guide: resolve(import.meta.dirname, 'guide/index.html'),
        roadmap: resolve(import.meta.dirname, 'roadmap/index.html'),
        notFound: resolve(import.meta.dirname, '404.html'),
      },
    },
  },
})
