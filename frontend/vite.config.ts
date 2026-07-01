import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0', // Allows access from outside the container
    port: 5173,
    strictPort: true,
    hmr: {
      clientPort: 5173 // Ensure HMR websocket uses the same port
    },
    proxy: {
      '/api': {
        target: 'http://isha-backend:8000', // Uses Docker internal DNS to hit the backend container
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://isha-backend:8000',
        ws: true,
      }
    }
  },
})