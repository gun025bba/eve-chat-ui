// npm install --prefix /tmp/eve-bench --ignore-scripts --save-exact
//   preact@11.1.0 react@19.3.1 react-dom@19.3.1 svelte@5.57.3
// node tools/benchmark.mjs /tmp/eve-bench

import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import { gzipSync } from 'node:zlib';
import { build } from 'vite';

const root = resolve(process.argv[2]);
const require = createRequire(`${root}/package.json`);
const { compile } = require('svelte/compiler');
const sources = {
  preact: `import {h,render} from 'preact';
    window.apply=text=>render(h('article',null,h('div',{class:'md'},text)),document.getElementById('root'));`,
  react: `import {createElement as h} from 'react'; import {createRoot} from 'react-dom/client';
    import {flushSync} from 'react-dom'; const root=createRoot(document.getElementById('root'));
    window.apply=text=>flushSync(()=>root.render(h('article',null,h('div',{className:'md'},text))));`,
  svelte: `import {mount,flushSync} from 'svelte'; import View from './View.svelte';
    const view=mount(View,{target:document.getElementById('root')});
    window.apply=text=>flushSync(()=>view.update(text));`,
};
writeFileSync(
  `${root}/View.svelte`,
  `<script>let text=''; export function update(value){text=value;}</script>
  <article><div class="md">{text}</div></article>`,
);
const stats = {};
for (const [name, source] of Object.entries(sources)) {
  writeFileSync(`${root}/${name}.js`, source);
  const outDir = `${root}/dist/${name}`;
  await build({
    configFile: false,
    root,
    logLevel: 'error',
    define: { 'process.env.NODE_ENV': '"production"' },
    plugins: [
      {
        name: 'svelte-probe',
        transform(code, id) {
          if (id.endsWith('.svelte')) return compile(code, { filename: id, generate: 'client', dev: false }).js.code;
        },
      },
    ],
    build: {
      outDir,
      target: 'safari16.4',
      minify: true,
      lib: { entry: `${root}/${name}.js`, formats: ['iife'], name: 'Probe', fileName: () => 'probe.js' },
    },
  });
  const bytes = readFileSync(`${outDir}/probe.js`);
  stats[name] = { bytes: bytes.length, gzip: gzipSync(bytes).length, jsRequests: 1 };
  writeFileSync(`${outDir}/index.html`, '<!doctype html><div id="root"></div><script src="probe.js"></script>');
}
// Same helpers used by generate()/patchLive, then identical plain-text component sinks.
// This isolates renderer cost; it does not pretend to measure network or a migrated generate().
const app = createRequire(import.meta.url)('../.cache/unit/helpers.cjs');
const text = '## Stream\n\nA **token** with [1] citation.\n\n'.repeat(200);
const replay = [];
for (let end = 32; end <= text.length; end += 32) {
  const value = text.slice(0, end);
  const start = performance.now();
  app.renderMarkdown(value.slice(app.stableCut(value)));
  replay.push({ text: value, helperMs: performance.now() - start });
}
mkdirSync(`${root}/dist`, { recursive: true });
writeFileSync(`${root}/dist/replay.json`, JSON.stringify(replay));
writeFileSync(`${root}/dist/sizes.json`, JSON.stringify(stats, null, 2));
console.log(JSON.stringify(stats));
