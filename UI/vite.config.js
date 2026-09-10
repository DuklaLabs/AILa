import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// SPA se servíruje přes ailacore.admin.mount_admin_ui pod /admin/rbac/ na
// stejném originu jako API (kvůli cookie session dl_session). `base` musí sedět
// s tou cestou, ať buildnuté odkazy na /assets/... platí.
// https://vite.dev/config/
export default defineConfig({
  base: '/admin/rbac/',
  plugins: [react()],
  server: {
    // `npm run dev` proti lokálně běžícímu AccessRequestu (port 8003)
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET || 'http://localhost:8003',
        changeOrigin: true,
      },
    },
  },
})
