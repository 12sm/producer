import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/analyze': 'http://127.0.0.1:7862',
      '/listen': 'http://127.0.0.1:7862',
      '/search': 'http://127.0.0.1:7862',
      '/vocab': 'http://127.0.0.1:7862',
      '/session': 'http://127.0.0.1:7862',
      '/health': 'http://127.0.0.1:7862',
      '/audio': 'http://127.0.0.1:7862',
    },
  },
})
