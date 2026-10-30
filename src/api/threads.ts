type API = (path: string, options?: RequestInit) => Promise<unknown>;

export function createThreadsAPI(api: API) {
  return {
    list: (cursor?: string | null) =>
      api(`/v1/threads?limit=20&archived=false${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`),
    archived: () => api('/v1/threads?limit=50&archived=true'),
    thread: (id: string) => api(`/v1/threads/${encodeURIComponent(id)}`),
    messages: (id: string, limit: number, before?: string) =>
      api(
        `/v1/threads/${encodeURIComponent(id)}/messages?limit=${limit}` +
          (before ? `&before=${encodeURIComponent(before)}` : ''),
      ),
    search: (query: string) => api(`/v1/search?limit=20&q=${encodeURIComponent(query)}`),
    cancel: (threadId: string, messageId: string) =>
      api(`/v1/threads/${encodeURIComponent(threadId)}/messages/${encodeURIComponent(messageId)}/cancel`, {
        method: 'POST',
      }),
    importThreads: (body: string) => api('/v1/threads/import', { method: 'POST', body }),
  };
}
