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
const helpers = loaded.browserHelpers || loaded.default || loaded;

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

test('untrusted citations stay escaped, local dates stay stable and render context does not leak', () => {
  assert.equal(helpers.srcDate('bad'), '');
  const now = new Date(2026, 9, 30, 12);
  assert.equal(helpers.srcDate('2026-10-30', now), '오늘');
  assert.equal(helpers.srcDate('2026-10-29', now), '어제');
  assert.equal(helpers.srcDate('2025-01-01', now), '2025년 1월 1일');
  assert.equal(helpers.renderSources([{ n: 1, url: 'javascript:alert(1)' }]), '');
  const citations = [{ n: 1, url: 'https://example.com/', title: '<img src=x>' }];
  assert.match(helpers.renderMarkdown('answer[1]', citations), /class="cite"/);
  assert.doesNotMatch(helpers.renderMarkdown('answer[1]'), /class="cite"/);
  assert.doesNotMatch(helpers.renderSources(citations), /<img src=x>/);
  assert.equal(helpers.toolFailKey({ error_code: 'permission_denied' }), 'denied');
  assert.equal(helpers.toolFailKey({ error_code: 'tainted' }), null);
  assert.equal(helpers.toolFailKey({ status: 'ok', count: 0 }), 'empty');
  assert.equal(helpers.toolFailKey({ error_code: 'untrusted-server-message' }), 'unknown');
});
