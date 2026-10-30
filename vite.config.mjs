import { readFileSync } from 'node:fs';
import { defineConfig } from 'vite';
import { legacyAssets } from './tools/build-assets.mjs';

const { version } = JSON.parse(readFileSync(new URL('./package.json', import.meta.url)));

export default defineConfig({
  base: '/ui/',
  publicDir: false,
  plugins: [legacyAssets(version)],
  build: {
    target: 'safari16.4',
    assetsInlineLimit: 0,
    minify: false,
    cssMinify: false,
    sourcemap: false,
    lib: { entry: 'src/main.ts', name: 'EveBoot', formats: ['iife'], fileName: () => 'app.js' },
  },
});
