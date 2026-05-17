import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import electron from 'vite-plugin-electron'
import electronRenderer from 'vite-plugin-electron-renderer'
import { resolve } from 'path'

const isElectron = process.env.MODE === 'electron'

export default defineConfig({
  plugins: [
    vue(),
    ...(isElectron ? [
      electron([
        {
          entry: 'src/main/index.ts',
          vite: {
            build: {
              outDir: 'dist/main',
              rollupOptions: { external: ['electron'] },
            },
          },
        },
        {
          entry: 'src/preload/index.ts',
          onstart(args) { args.reload() },
          vite: { build: { outDir: 'dist/preload' } },
        },
      ]),
      electronRenderer(),
    ] : []),
  ],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src/renderer'),
    },
  },
  server: {
    port: 1420,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
      },
      '/ws': {
        target: 'http://127.0.0.1:8000',
        ws: true,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist/renderer',
    target: 'esnext',
  },
})
