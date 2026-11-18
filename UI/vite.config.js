import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// SPA se servíruje přes ailacore.admin.mount_admin_ui pod /admin/rbac/ uvnitř
// AccessRequestu, který sám běží na podcestě /access (viz Gateway/Caddyfile,
// URL_PREFIX). `base` musí sedět s výslednou cestou, ať buildnuté odkazy na
// /assets/... platí. VITE_API_BASE stejně posouvá i vlastní API base v api.js.
// https://vite.dev/config/
export default defineConfig({
  base: '/access/admin/rbac/',
  define: {
    'import.meta.env.VITE_API_BASE': JSON.stringify('/access/api/rbac'),
  },
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
