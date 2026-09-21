import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  base: '/static/dist/',
  server: {
    proxy: { '/open': 'http://127.0.0.1:9003', '/api': 'http://127.0.0.1:9003' },
  },
  build: { outDir: '../static/dist', emptyOutDir: true },
})
