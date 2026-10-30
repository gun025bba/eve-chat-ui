import { headers } from './client.js';

type Chat = {
  model?: string;
  messages: unknown[];
  signal: AbortSignal;
  threadId?: string;
  replaceId?: string | null;
};

type Options = { apiBase: () => string; request?: typeof fetch };

export function createGatewayRequests({ apiBase, request = (...args) => fetch(...args) }: Options) {
  return {
    identity: () => request(`${apiBase()}/whoami`, { cache: 'no-store' }),
    models: (base: string) => request(`${base}/v1/models`),
    pair: (code: string) =>
      request(`${apiBase()}/v1/pair`, {
        method: 'POST',
        cache: 'no-store',
        credentials: 'same-origin',
        headers: headers('POST'),
        body: JSON.stringify({ code }),
      }),
    resume: (threadId: string, messageId: string, sequence: number, signal: AbortSignal) =>
      request(
        `${apiBase()}/v1/threads/${encodeURIComponent(threadId)}/messages/${encodeURIComponent(messageId)}/stream`,
        {
          cache: 'no-store',
          signal,
          headers: { ...headers(), 'Last-Event-ID': String(sequence) },
        },
      ),
    chat: ({ model, messages, signal, threadId, replaceId }: Chat) =>
      request(`${apiBase()}/v1/chat/completions`, {
        method: 'POST',
        headers: headers('POST'),
        signal,
        body: JSON.stringify(
          Object.assign(
            { model, messages, stream: true, stream_options: { include_usage: true } },
            threadId !== undefined ? { thread_id: threadId } : {},
            threadId !== undefined && replaceId ? { replace_message_id: replaceId } : {},
          ),
        ),
      }),
  };
}
