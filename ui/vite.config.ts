import { defineConfig, loadEnv } from 'vite'
import preact from '@preact/preset-vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const proxyTarget = env.VITE_PROXYLENS_BASE_URL || 'http://127.0.0.1:8000'

  return {
    plugins: [preact()],
    server: {
      proxy: {
        '/__proxylens': {
          target: proxyTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/__proxylens/, ''),
        },
      },
    },
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: './src/test/setup.ts',
    },
  }
})
