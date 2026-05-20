import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    proxy: {
      '/api/v1': { target: 'http://api:8000', changeOrigin: true },
      '/mock': { target: 'http://api:8000', changeOrigin: true },
    }
  }
})
