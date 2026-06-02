import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) {
            return undefined
          }
          if (/[\\/]node_modules[\\/](react|react-dom|react-router|react-router-dom|scheduler)[\\/]/.test(id)) {
            return 'vendor-react'
          }
          if (/[\\/]node_modules[\\/](@chakra-ui|@emotion|framer-motion)[\\/]/.test(id)) {
            return 'vendor-chakra'
          }
          if (/[\\/]node_modules[\\/](@tanstack[\\/]react-query|@supabase[\\/]supabase-js)[\\/]/.test(id)) {
            return 'vendor-data'
          }
          return undefined
        },
      },
    },
  },
})
