import { fileURLToPath } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

const frontend = fileURLToPath(new URL('./', import.meta.url))

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, frontend, 'PHARMACY_')
  const backend = env.PHARMACY_PROXY_TARGET || 'http://127.0.0.1:4000'
  const proxy = { '/api': backend, '/media': backend }

  return {
    root: fileURLToPath(new URL('./apps/pharmacy/', import.meta.url)),
    envDir: frontend,
    cacheDir: fileURLToPath(new URL('./node_modules/.vite-pharmacy/', import.meta.url)),
    plugins: [react()],
    css: { postcss: frontend },
    server: { host: '0.0.0.0', port: 3001, strictPort: true, proxy, fs: { allow: [frontend] } },
    preview: { host: '0.0.0.0', port: 3001, strictPort: true, proxy },
    build: { outDir: fileURLToPath(new URL('./dist-pharmacy/', import.meta.url)), emptyOutDir: true },
  }
})
