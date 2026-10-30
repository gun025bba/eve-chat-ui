import { escapeHtml } from './text.js';

interface ToolResult {
  error_code?: unknown;
  status?: unknown;
  count?: unknown;
  sources?: unknown;
  blocked_count?: unknown;
}
interface FreshMessage {
  fresh?: unknown;
  tools?: unknown;
}

/* §7 `.tq`: one line per web_search query (max 3) at the top of the opened list / sheet; reason only when
selected_by is known. Absent info (reload) → '' */
export function renderToolQueries(tools: unknown): string {
  const qs = (Array.isArray(tools) ? tools : []).filter((t) => t && typeof t.q === 'string' && t.q.trim()).slice(0, 3);
  if (!qs.length) return '';
  const by = qs.find((t) => t.by === 'model')?.by,
    why = by === 'model' ? 'Eve가 필요하다고 판단해 검색했어요' : '';
  return qs
    .map(
      (t, i) =>
        `<div class="tq"><span>검색어 <q>${escapeHtml(t.q)}</q>` + `${i === 0 && why ? ` · ${why}` : ''}</span></div>`,
    )
    .join('');
}
/* AUTO-TOOLS-SPEC §5.1: web tool failure → fixed copy by key (never a server string). [status line, note
title, note sub]  — the note is text only (no action) */
export const TOOL_FAIL: Record<string, [string, string, string]> = {
  empty: ['검색 결과가 없어요', '검색 결과를 찾지 못했어요', '학습한 내용으로 답했어요'],
  timeout: ['검색이 오래 걸려 멈췄어요', '검색 시간이 초과됐어요', '지금까지 확인한 내용으로 답했어요'],
  search_unavailable: [
    '지금은 검색을 쓸 수 없어요',
    '최신 정보를 확인하지 못했어요',
    '검색이 잠시 안 돼서 학습한 내용으로 답했어요',
  ],
  rate_limited: ['검색 요청이 많아요', '검색 요청이 많아요', '잠시 뒤에는 다시 검색할 수 있어요'],
  budget_exhausted: [
    '검색 한도에 도달했어요',
    '한 번에 할 수 있는 검색을 다 썼어요',
    '지금까지 찾은 내용으로 답했어요',
  ],
  blocked: ['차단된 주소는 열지 않았어요', '일부 페이지는 열지 않았어요', '안전하지 않은 주소라 건너뛰었어요'],
  denied: ['지금은 검색을 쓸 수 없어요', '웹 검색을 쓸 수 없어요', '관리 설정으로 꺼져 있어요'],
  query_rejected: [
    '검색어에 보낼 수 없는 내용이 있어요',
    '검색하지 않았어요',
    '개인 정보처럼 보이는 내용은 밖으로 보내지 않아요',
  ],
  nosearch: ['', '최신 정보를 확인하지 못했어요', '검색하지 않고 학습한 내용으로 답했어요'],
  unknown: ['검색하지 못했어요', '최신 정보를 확인하지 못했어요', '검색이 안 돼서 학습한 내용으로 답했어요'],
};
/* tool_result (web tools only) → a TOOL_FAIL key, or null when nothing is wrong / nothing is to be shown
(duplicate_query, tainted). Reads optional fields defensively. */
export function toolFailKey(j: ToolResult): string | null {
  const code = typeof j?.error_code === 'string' ? j.error_code : '',
    st = typeof j?.status === 'string' ? j.status : 'ok';
  if (code === 'duplicate_query' || code === 'tainted') return null;
  if (code === 'permission_denied' || code === 'scope_denied' || code === 'kill_switch') return 'denied';
  if (TOOL_FAIL[code] && code !== 'empty' && code !== 'unknown') return code;
  if (code === 'invalid_arguments' || code) return 'unknown';
  if (st === 'ok') {
    const n =
      Number.isFinite(+(j.count as number)) && j.count != null
        ? +(j.count as number)
        : Array.isArray(j.sources)
          ? j.sources.length
          : null;
    return n === 0 || (n == null && +(j.blocked_count as number) > 0) ? 'empty' : null;
  } // 6.0.0: blocked_count = items the server dropped as suspect; nothing usable left → the empty note
  if (st === 'timeout') return 'timeout';
  if (st === 'blocked') return 'blocked';
  if (st === 'denied') return 'denied';
  return 'unknown';
}
/* #134 messages.metadata / persisted: tools[] {tool, selected_by, status, error_code?, count?, query? (only
if the server joins it)} → the shape the UI keeps */
export const mapTools = (a: unknown) =>
  Array.isArray(a)
    ? a
        .filter((x) => x && typeof x === 'object')
        .map((x) => ({
          tool: x.tool,
          q: typeof x.query === 'string' ? x.query.trim() : '',
          by: x.selected_by === 'model' || x.selected_by === 'user' ? x.selected_by : '',
          status: x.status,
          error_code: x.error_code,
          count: x.count,
        }))
    : null;
/* AUTO-TOOLS-SPEC v2 §5: the note comes back from the stored fresh:'unverified'; the reason from tools[]
(last status≠ok → §5.1 copy; tools[] empty → 검색하지 않고…; otherwise the generic copy). No fresh / 'ok' → none. */
export function freshNote(m?: FreshMessage | null): { key: string } | null {
  if (m?.fresh !== 'unverified') return null;
  const t = Array.isArray(m.tools) ? m.tools : null,
    bad = t && [...t].reverse().find((x) => x?.status && x.status !== 'ok');
  return {
    key:
      (bad && toolFailKey({ status: bad.status, error_code: bad.error_code, count: bad.count })) ||
      (t && !t.length ? 'nosearch' : 'unknown'),
  };
}
