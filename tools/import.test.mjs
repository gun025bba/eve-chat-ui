import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import test from 'node:test';
import { build } from 'vite';

await build({
  configFile: false,
  logLevel: 'error',
  build: {
    outDir: '.cache/import',
    target: 'node20',
    lib: { entry: 'src/api/import.ts', formats: ['cjs'], fileName: () => 'import.cjs' },
  },
});
const { createImportBody, importOutcome } = createRequire(import.meta.url)('../.cache/import/import.cjs');
const local = {
  id: 'L1',
  title: '로컬',
  created: 10000,
  archived: true,
  messages: [
    { role: 'user', content: 'question', created: 8000 },
    { role: 'assistant', content: '<think>why</think>\nanswer', pendingActions: [{ confirm_token: 'not-saved' }] },
    { role: 'tool', content: 'not-saved' },
  ],
};
test('import payload preserves time offsets and splits reasoning without confirmation metadata', () => {
  const body = createImportBody([local], () => 'chosen-model');
  assert.equal(
    body,
    JSON.stringify({
      threads: [
        {
          client_id: 'local:L1',
          title: '로컬',
          created_at: '1970-01-01T00:00:07.000Z',
          archived: true,
          messages: [
            { client_id: 'local:L1:0', role: 'user', created_at: '1970-01-01T00:00:08.000Z', content: 'question' },
            {
              client_id: 'local:L1:1',
              role: 'assistant',
              created_at: '1970-01-01T00:00:08.000Z',
              content: 'answer',
              reasoning: 'why',
              model: 'chosen-model',
            },
          ],
        },
      ],
    }),
  );
  assert.ok(!body.includes('not-saved'));
});
test('import results preserve legacy mappings, duplicate success and partial failure messages', () => {
  assert.deepEqual(importOutcome({ mapping: [{ client_id: 'local:L1', id: 'server-id' }] }, [local]), {
    ok: ['L1'],
    fail: [],
  });
  assert.deepEqual(importOutcome({ results: [{ client_id: 'local:L1', status: 'exists' }] }, [local]).ok, ['L1']);
  assert.deepEqual(
    importOutcome({ results: [{ client_id: 'local:L1', status: 'failed', error: { message: '<img src=x>' } }] }, [
      local,
    ]),
    {
      ok: [],
      fail: [{ id: 'L1', title: '로컬', reason: '<img src=x>' }],
    },
  );
  assert.equal(importOutcome(null, [local]).fail[0].reason, '응답에 결과가 없어요');
});
