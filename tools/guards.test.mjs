import assert from 'node:assert/strict';
import test from 'node:test';
import { checkImports } from './check-imports.mjs';
import { measure, violations } from './check-size.mjs';

test('ratchet rejects growth, new unsafe sinks and oversized functions; permits reduction', () => {
  const baseline = { 'old.js': { lines: 20, innerHTML: 2 } };
  assert.deepEqual(violations({ 'old.js': { lines: 19, innerHTML: 1 } }, baseline), []);
  assert.equal(violations({ 'old.js': { lines: 21 }, 'new.js': { innerHTML: 1 } }, baseline).length, 2);
  const metrics = measure('large.ts', `function large() {\n${'  step();\n'.repeat(61)}}`);
  assert.equal(metrics.functions, 3);
  assert.equal(measure('sink.ts', "element['innerHTML'] += userText;").innerHTML, 1);
});

test('dependency gate rejects cycles, upward edges, feature coupling and lazy imports', () => {
  assert.deepEqual(checkImports({ 'src/app/boot.ts': "import '../lib/text';", 'src/lib/text.ts': 'export {};' }), []);
  for (const sources of [
    { 'src/lib/a.ts': "import '../app/b';", 'src/app/b.ts': 'export {};' },
    { 'src/features/a/x.ts': "import '../b/y';", 'src/features/b/y.ts': 'export {};' },
    { 'src/lib/a.ts': "import './b';", 'src/lib/b.ts': "import './a';" },
    { 'src/main.ts': "import('./app/boot');" },
    { 'src/lib/a.ts': "fetch('/v1/threads');" },
    { 'src/lib/a.ts': "import '../../app.js';" },
    { 'src/app/a.ts': "require('../features/thing');" },
  ])
    assert.ok(checkImports(sources).length, JSON.stringify(sources));
});
