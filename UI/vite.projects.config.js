import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Druhá SPA vedle RBAC konzole: projektový systém. Servíruje ji služba Projects
// přes ailacore.admin.mount_spa pod /app/projects/ uvnitř sebe sama, a Projects
// samotná běží na podcestě /projects (viz Gateway/Caddyfile, URL_PREFIX).
// `base` musí sedět s výslednou cestou. VITE_API_BASE stejně posouvá i vlastní
// API base v api.js.
export default defineConfig({
  base: '/projects/app/projects/',
  define: {
    'import.meta.env.VITE_API_BASE': JSON.stringify('/projects/api'),
  },
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
