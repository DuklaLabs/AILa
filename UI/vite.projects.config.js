import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Druhá SPA vedle RBAC konzole: projektový systém. Servíruje ji služba Projects
// přes ailacore.admin.mount_spa pod /app/projects/ na stejném originu jako API
// (kvůli cookie session dl_session). `base` musí sedět s tou cestou.
export default defineConfig({
  base: '/app/projects/',
  plugins: [react()],
  build: {
    outDir: 'dist-projects',
    rollupOptions: { input: 'index.projects.html' },
  },
  server: {
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET || 'http://localhost:8006',
        changeOrigin: true,
      },
    },
  },
})
