import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        // Required for SSE (EventSource) streams to pass through correctly
        headers: { Connection: 'keep-alive' }
      }
    }
  }
})
