import assert from 'node:assert/strict';
import { mkdirSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';
import { build } from 'vite';

mkdirSync('.cache/unit', { recursive: true });
await build({
  configFile: false,
  logLevel: 'error',
  build: {
    outDir: '.cache/unit',
    target: 'node20',
    minify: false,
    lib: { entry: 'src/legacy/app.js', formats: ['cjs'], fileName: () => 'helpers.cjs' },
  },
});
const loaded = createRequire(import.meta.url)('../.cache/unit/helpers.cjs');
const helpers = loaded.default || loaded;

test('SSE keeps CRLF, multiline data, comments, last event/id and chunk boundaries', () => {
  const input = ': ping\r\nevent: old\r\nevent: token\r\nid: 7\r\ndata: first\r\ndata: second\r\n\r\ndata: tail';
  for (let cut = 0; cut <= input.length; cut++) {
    const events = [];
    const parser = helpers.createSSEParser((...values) => events.push(values));
    parser.push(input.slice(0, cut));
    parser.push(input.slice(cut));
    parser.flush();
    parser.flush();
    assert.deepEqual(events, [
      ['first\nsecond', 'token', '7'],
      ['tail', null, null],
    ]);
  }
});

test('think blocks and stop markers retain streaming and finalized semantics', () => {
  assert.deepEqual(helpers.splitThink(' <think> reasoning'), { think: 'reasoning', answer: '', thinking: true });
  assert.deepEqual(helpers.splitThink('<think> x </think>\nanswer'), { think: 'x', answer: 'answer', thinking: false });
  assert.deepEqual(helpers.splitThink('answer'), { think: null, answer: 'answer', thinking: false });
  assert.equal(helpers.stripStopMark('answer\n\n*(중지됨)*  '), 'answer');
  assert.equal(helpers.stripStopMark(null), '');
});
