import { defineConfig } from 'vite'
import blitsVitePlugins from '@lightningjs/blits/vite'

export default defineConfig({
  // Relative base so the build works from a file:// origin inside the
  // Android WebView, not just from a web server root.
  base: './',

  plugins: [...blitsVitePlugins],

  resolve: {
    mainFields: ['browser', 'module', 'jsnext:main', 'jsnext'],
  },

  server: {
    headers: {
      'Cross-Origin-Opener-Policy': 'same-origin',
      'Cross-Origin-Embedder-Policy': 'require-corp',
    },
  },

  worker: {
    format: 'es',
  },
})
