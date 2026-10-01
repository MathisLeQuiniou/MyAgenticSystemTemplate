import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],

  base: './',

  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    allowedHosts: [
      'all',
      'localhost',
      '127.0.0.1',
      '0.0.0.0'
    ]
  },

  build: {
    outDir: 'dist',
    assetsDir: 'assets',
  }
});
