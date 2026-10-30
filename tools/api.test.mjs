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
              'src/features/auth/model.ts',
              'src/api/threads.ts',
              'src/api/gateway.ts',
              'src/api/thread-models.js',
              'src/api/operations.js',
              'src/features/conversations/outbox.js',
              'src/features/conversations/state.ts',
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
const {
  createClient,
  createThreadModels,
  createOperations,
  createOutbox,
  createConversationState,
  createThreadsAPI,
  createGatewayRequests,
  normCode,
  fmtCode,
  notice,
} = createRequire(import.meta.url)('../.cache/api/contracts.cjs');

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

test('conversation state loads only the selected cache and keeps instances isolated', () => {
  const keys = { mode: 'llmchat.mode', srv: 'llmchat.srvcache', convs: 'llmchat.convs', current: 'llmchat.current' };
  const calls = [];
  const cached = [{ id: 'server-thread' }];
  const server = createConversationState({
    keys,
    load: (key, fallback) => {
      calls.push(key);
      return { [keys.mode]: 'server', [keys.srv]: cached, [keys.current]: 'server-thread' }[key] ?? fallback;
    },
  });
  assert.deepEqual(calls, [keys.mode, keys.srv, keys.current]);
  assert.equal(server.convs, cached);
  assert.equal(server.currentId, 'server-thread');
  const local = createConversationState({ keys, load: (key, fallback) => (key === keys.mode ? 'invalid' : fallback) });
  assert.equal(local.mode, 'local');
  assert.deepEqual(local.convs, []);
  server.archivedList.push({ id: 'archived' });
  server.nextCursor = 'cursor';
  server.threadsLoading = true;
  assert.deepEqual(local.archivedList, []);
  assert.equal(local.nextCursor, null);
  assert.equal(local.threadsLoading, false);
  assert.equal(local.persistOff, false);
});

test('thread reads, cancellation and import retain exact paths and request bodies', async () => {
  const calls = [];
  const api = createThreadsAPI(async (...args) => calls.push(args));
  await api.list();
  await api.list('page /?');
  await api.archived();
  await api.thread('thread/1');
  await api.messages('thread/1', 50, 'message/2');
  await api.messages('thread/1', 4);
  await api.search('한 글&?');
  await api.cancel('thread/1', 'message/2');
  await api.importThreads('{"threads":[]}');
  assert.deepEqual(calls, [
    ['/v1/threads?limit=20&archived=false'],
    ['/v1/threads?limit=20&archived=false&cursor=page%20%2F%3F'],
    ['/v1/threads?limit=50&archived=true'],
    ['/v1/threads/thread%2F1'],
    ['/v1/threads/thread%2F1/messages?limit=50&before=message%2F2'],
    ['/v1/threads/thread%2F1/messages?limit=4'],
    ['/v1/search?limit=20&q=%ED%95%9C%20%EA%B8%80%26%3F'],
    ['/v1/threads/thread%2F1/messages/message%2F2/cancel', { method: 'POST' }],
    ['/v1/threads/import', { method: 'POST', body: '{"threads":[]}' }],
  ]);
});

test('gateway raw requests preserve CSRF, cookies, stream cursors and persistence fallback', async () => {
  const calls = [];
  const gateway = createGatewayRequests({ apiBase: () => '', request: async (...args) => calls.push(args) });
  const signal = new AbortController().signal;
  await gateway.identity();
  await gateway.models('');
  await gateway.pair('ABCD-EFGH');
  await gateway.resume('t/1', 'm/2', 4, signal);
  await gateway.chat({
    model: 'model',
    messages: [{ role: 'user', content: 'hello' }],
    signal,
    threadId: 't/1',
    replaceId: 'm/2',
  });
  await gateway.chat({ messages: [], signal, replaceId: 'ignored-without-persistence' });
  assert.deepEqual(calls[0], ['/whoami', { cache: 'no-store' }]);
  assert.deepEqual(calls[1], ['/v1/models']);
  assert.deepEqual(calls[2], [
    '/v1/pair',
    {
      method: 'POST',
      cache: 'no-store',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-Eve-Request': '1' },
      body: '{"code":"ABCD-EFGH"}',
    },
  ]);
  assert.deepEqual(calls[3], [
    '/v1/threads/t%2F1/messages/m%2F2/stream',
    {
      cache: 'no-store',
      signal,
      headers: { 'Content-Type': 'application/json', 'X-Eve-Request': '1', 'Last-Event-ID': '4' },
    },
  ]);
  assert.equal(calls[4][0], '/v1/chat/completions');
  assert.deepEqual(calls[4][1].headers, { 'Content-Type': 'application/json', 'X-Eve-Request': '1' });
  assert.equal(calls[4][1].signal, signal);
  assert.deepEqual(JSON.parse(calls[4][1].body), {
    model: 'model',
    messages: [{ role: 'user', content: 'hello' }],
    stream: true,
    stream_options: { include_usage: true },
    thread_id: 't/1',
    replace_message_id: 'm/2',
  });
  assert.equal(calls[5][1].body, '{"messages":[],"stream":true,"stream_options":{"include_usage":true}}');
});

test('pairing model keeps Crockford normalization and identity-specific notices', () => {
  assert.equal(normCode('o il u-2a$bc'), '011V2ABC');
  assert.equal(fmtCode(normCode('o il u-2a$bc')), '011V-2ABC');
  assert.equal(normCode('abcdefgh-more'), 'ABCDEFGH');
  assert.equal(normCode(null), '');
  assert.equal(fmtCode('ABCD'), 'ABCD');
  assert.equal(notice('identity_not_allowed', true).pair, false);
  assert.equal(notice('invalid_session', false).title, '다시 연결해 주세요');
  assert.equal(notice(undefined, true).title, '다시 연결해 주세요');
  assert.equal(notice('<img src=x>', false).title, '이 기기를 연결해 주세요');
});
