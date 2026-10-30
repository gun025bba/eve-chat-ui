export const normBase = (b) => (b || '').trim().replace(/\/+$/, '').replace(/\/v1$/, '');
// '' => relative /v1/... (same origin)
export const headers = (_method) => ({ 'Content-Type': 'application/json', 'X-Eve-Request': '1' });
// sent on every request (GET too): body-less POST/DELETE included
export const authCode = (j) => {
  try {
    if (typeof j === 'string') j = JSON.parse(j);
  } catch {
    return '';
  }
  return (j && (j.error_code || j.error?.code)) || '';
};
export const isAuthFail = (status, code) => status === 401 || (status === 403 && code === 'identity_not_allowed');
export function createClient({ apiBase, onAuthFail, errorMessage, request = (...args) => fetch(...args) }) {
  async function api(path, opts = {}) {
    const r = await request(apiBase() + path, {
      cache: 'no-store',
      ...opts,
      headers: { ...(opts.headers || {}), ...headers() },
    });
    if (r.status === 204) return null;
    const t = await r.text();
    let j = null;
    try {
      j = JSON.parse(t);
    } catch {}
    if (!r.ok) {
      const code = j?.error_code || j?.error?.code; // 선톡/actions API: {error_code}; older APIs: {error:{code}}
      if (isAuthFail(r.status, code)) {
        onAuthFail(code);
      }
      // body: parsed error JSON (502 outcome_unknown / briefing preview carry fields beside error_code);
      // outcomeUnknown: eve-serving #78 approve 502
      throw Object.assign(new Error(errorMessage(r.status, t)), {
        http: r.status,
        code,
        body: j && typeof j === 'object' ? j : null,
        outcomeUnknown: typeof j?.outcome_unknown === 'boolean' ? j.outcome_unknown : undefined,
      });
    }
    return j;
  }
  return api;
}
