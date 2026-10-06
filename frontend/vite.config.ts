import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import tailwindcss from "@tailwindcss/vite";


// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    watch: {
      usePolling: true,
    },
    hmr: {
      clientPort: 5174, // host port from docker-compose ("5174:5173")
    },
  },
})

