import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Třetí SPA vedle RBAC konzole a Projects: portálový shell (LabOrchestratorDashboard).
// Servíruje ho přímo Caddy jako statické soubory na kořeni domény (aila.localhost),
// ne žádná z FastAPI služeb – proto base '/' místo podadresáře jako u ostatních dvou.
export default defineConfig({
  base: '/',
  plugins: [react()],
  build: {
    outDir: 'dist-portal',
    rollupOptions: { input: 'index.portal.html' },
  },
})
