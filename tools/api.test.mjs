import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import test from 'node:test';
import { build } from 'vite';

await build({
  configFile: false,
  logLevel: 'error',
  plugins: [
    {
      name: 'api-contract-entry',
      resolveId: (id) => (id.endsWith('eve:api-contract') ? '\0eve:api-contract' : undefined),
      load: (id) =>
        id === '\0eve:api-contract'
          ? [
              'src/api/client.js',
              'src/api/thread-models.js',
              'src/api/operations.js',
              'src/features/conversations/outbox.js',
            ]
              .map((path) => `export * from ${JSON.stringify(resolve(path))};`)
              .join('\n')
          : undefined,
    },
  ],
  build: {
    outDir: '.cache/api',
    target: 'node20',
    lib: { entry: 'eve:api-contract', formats: ['cjs'], fileName: () => 'contracts.cjs' },
  },
});
const { createClient, createThreadModels, createOperations, createOutbox } = createRequire(import.meta.url)(
  '../.cache/api/contracts.cjs',
);

test('request client preserves headers, 204, identity loss and ambiguous outcomes', async () => {
  const calls = [],
    auth = [];
  const replies = [
    new Response(null, { status: 204 }),
    new Response('{"error_code":"identity_not_allowed"}', { status: 403 }),
    new Response('{"error_code":"scope_denied"}', { status: 403 }),
    new Response('{"error_code":"outcome_unknown","outcome_unknown":true}', { status: 502 }),
  ];
  const api = createClient({
    apiBase: () => '',
    onAuthFail: (code) => auth.push(code),
    errorMessage: (status) => `HTTP ${status}`,
    request: async (...args) => {
      calls.push(args);
      return replies.shift();
    },
  });
  assert.equal(await api('/v1/example', { method: 'DELETE', headers: { Extra: 'kept' } }), null);
  assert.deepEqual(calls[0][1].headers, { Extra: 'kept', 'Content-Type': 'application/json', 'X-Eve-Request': '1' });
  await assert.rejects(api('/whoami'), { http: 403, code: 'identity_not_allowed' });
  await assert.rejects(api('/v1/example'), { http: 403, code: 'scope_denied' });
  await assert.rejects(api('/v1/example'), { http: 502, code: 'outcome_unknown', outcomeUnknown: true });
  assert.deepEqual(auth, ['identity_not_allowed']);
});

test('thread models scrub confirmation secrets and operations retain feedback bodies', async () => {
  const models = createThreadModels({ fields: null, pinSet: () => new Set(['t1']), usageText: () => 'usage' });
  const message = models.fromServerMsg({
    id: 'm1',
    role: 'assistant',
    content: 'answer',
    created_at: '2026-10-30T00:00:00Z',
    pending_actions: [{ action_id: 'a1', confirm_token: 'test-token', token_expires_at: 'never', summary: 'confirm' }],
  });
  assert.deepEqual(message.pendingActions, [{ action_id: 'a1', summary: 'confirm' }]);
  assert.equal(models.fromServerThread({ id: 't1' }).pinned, true);
  const calls = [];
  const operation = createOperations(async (...args) => {
    calls.push(args);
  });
  await operation({ op: 'feedback', payload: { id: 'm1', rating: 'down', reasons: ['other'], comment: 'note' } });
  assert.deepEqual(calls[0], [
    '/v1/messages/m1/feedback',
    { method: 'PUT', body: '{"rating":"down","reasons":["other"],"comment":"note"}' },
  ]);
});

function queueFor(t, runOp) {
  t.mock.method(globalThis, 'setInterval', () => 0);
  t.mock.method(globalThis, 'setTimeout', () => 0);
  const writes = [];
  const queue = createOutbox({
    mode: () => 'server',
    load: () => [],
    storageKey: 'llmchat.outbox',
    runOp,
    save: (key, value) => writes.push([key, JSON.parse(JSON.stringify(value))]),
    isNet: (error) => !error.http,
    renderSync() {},
    fbReasonRejected() {},
    showToast() {
      throw Error('Unexpected rollback toast');
    },
  });
  return { queue, writes };
}

test('outbox coalesces keys, retains its storage format and caps retries at sixty seconds', async (t) => {
  const { queue, writes } = queueFor(t, async () => {
    throw Object.assign(new Error('offline'), { http: 503 });
  });
  queue.enqueue('patch', 'same', { id: 't1', patch: { title: 'old' } });
  queue.enqueue('patch', 'same', { id: 't1', patch: { title: 'new' } });
  assert.equal(queue.state.items.length, 1);
  assert.deepEqual(Object.keys(writes.at(-1)[1][0]), ['op', 'key', 'payload', 'tries', 'nextAt']);
  assert.equal(writes.at(-1)[0], 'llmchat.outbox');
  for (let retry = 0; retry < 7; retry++) {
    queue.state.items[0].nextAt = 0;
    await queue.flushOutbox();
  }
  assert.equal(queue.state.items[0].tries, 7);
  assert.ok(queue.state.items[0].nextAt - Date.now() <= 60000);
  assert.ok(queue.state.items[0].nextAt - Date.now() >= 59000);
});

test('outbox prevents concurrent replay and removes successful writes', async (t) => {
  let finish,
    count = 0;
  const { queue } = queueFor(t, () => {
    count++;
    return new Promise((resolve) => {
      finish = resolve;
    });
  });
  queue.enqueue('archive', 'a1', { id: 't1' });
  const first = queue.flushOutbox();
  await queue.flushOutbox();
  assert.equal(count, 1);
  finish();
  await first;
  assert.equal(queue.state.items.length, 0);
});
