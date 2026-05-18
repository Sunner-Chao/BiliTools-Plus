import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import electron from 'vite-plugin-electron'
import electronRenderer from 'vite-plugin-electron-renderer'
import { resolve } from 'path'

export default defineConfig(({ mode }) => {
  const isElectron = mode === 'electron'
  const backendTarget = process.env.VITE_API_BASE_URL || 'http://127.0.0.1:8001'

  return {
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
    host: '127.0.0.1',
    port: 1420,
    strictPort: true,
    proxy: {
      '/api': {
        target: backendTarget,
        changeOrigin: true,
        secure: false,
      },
      '/ws': {
        target: backendTarget,
        ws: true,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist/renderer',
    target: 'esnext',
  },
}
})
