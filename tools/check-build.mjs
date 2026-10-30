import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { filesIn } from './build-assets.mjs';

const expected = JSON.parse(readFileSync('tools/deploy-files.json', 'utf8'));
const actual = filesIn('dist')
  .map((name) => name.slice(5))
  .sort();
assert.deepEqual(actual, expected, 'Deployment must contain exactly the reviewed artifact list');
const { version } = JSON.parse(readFileSync('package.json', 'utf8'));
const worker = readFileSync('dist/sw.js', 'utf8');
const sourceWorker = readFileSync('sw.js', 'utf8');
const rules = (text) => text.slice(text.indexOf("self.addEventListener('install'"));
assert.equal(rules(worker), rules(sourceWorker), 'SW lifecycle, fetch and push policies must stay unchanged');
const app = readFileSync('dist/app.js', 'utf8');
assert.ok(['var', 'const'].some((kind) => app.includes(`${kind} APP_VERSION = ${JSON.stringify(version)}`)));
assert.ok(!app.includes('__EVE_VERSION__'));
const prefix = worker.slice(0, worker.indexOf("self.addEventListener('install'"));
const { assets, shell, cache } = vm.runInNewContext(`${prefix}; ({assets: ASSETS, shell: SHELL, cache: CACHE})`);
assert.equal(cache, `llmchat-${version}`);
assert.deepEqual(
  Array.from(shell, (name) => name.split('?')[0]).sort(),
  actual.filter((name) => name !== 'sw.js'),
);
assert.ok(assets.every((name) => name.endsWith(`?v=${version}`)));
for (const name of actual.filter((name) => name.endsWith('.html'))) {
  const html = readFileSync(`dist/${name}`, 'utf8');
  assert.ok(!html.includes('__EVE_VERSION__'), `${name}: unresolved version`);
  assert.doesNotMatch(html, /<style\b|\sstyle\s*=|<script\b(?![^>]*\bsrc=)/i, `${name}: inline content`);
  for (const match of html.matchAll(/(?:src|href)="([^"]+)"/g)) {
    const url = match[1];
    assert.doesNotMatch(url, /^(?:https?:)?\/\//, 'No external resources');
    if (/\.(?:js|css)\?/.test(url)) assert.ok(shell.includes(url.replace('/ui/', '')), `Uncached ${url}`);
  }
}
for (const name of actual.filter((name) => name.endsWith('.js'))) {
  assert.doesNotMatch(readFileSync(`dist/${name}`, 'utf8'), /\beval\s*\(|new\s+Function\s*\(|\bimport\s*\(/);
}
for (const name of actual.filter((name) => !['app.js', 'sw.js', 'index.html', 'offline.html'].includes(name))) {
  assert.deepEqual(readFileSync(`dist/${name}`), readFileSync(name), `${name}: unexpected content change`);
}
console.log(`Artifact gate: ${actual.length} files, complete precache, version ${version}, no inline HTML content`);
