import { defineConfig } from 'vite';
import { resolve } from 'node:path';

export default defineConfig({
  build: {
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        technik: resolve(__dirname, 'technik.html'),
        pipeline: resolve(__dirname, 'pipeline.html'),
        klinik: resolve(__dirname, 'klinik.html'),
        team: resolve(__dirname, 'team.html'),
      },
    },
  },
});
