  const ULID = /^[0-9A-HJKMNP-TV-Z]{26}$/;
  const PUSH_HOSTS = ['web.push.apple.com'];          // exact host, mirrors the server allowlist (PM §2.2.1)
  const POLL_MS = 60000, LS_PUSH = 'eve.push', LS_KID = 'eve.push.kid';
  const icon = (n, c = '') => `<svg class="i${c ? ' ' + c : ''}" aria-hidden="true"><use href="#i-${n}"/></svg>`;   // Eve sprite (design a197571)
  const svg = d => `<svg class="i" viewBox="0 0 24 24" aria-hidden="true">${d}</svg>`;          // glyphs not in the sprite
  const IC = {
    sparkle: icon('sparkle'), eye: icon('eye'), uturn: icon('followup'), 'sun-horizon': icon('sun-horizon'), bell: icon('bell'),
    wrench: svg('<path d="M14.7 6.3a4 4 0 0 0 5 5L13 18l-3 3-4-4 3-3 6.7-6.7a4 4 0 0 0-1-1z"/>'),
    brain: icon('memory'), trash: icon('trash'), warn: icon('warning'), check: icon('check'), err: icon('info')
  };
  const T = new Intl.DateTimeFormat('ko-KR', { hour: 'numeric', minute: '2-digit' });
  const DAYS = ['일요일', '월요일', '화요일', '수요일', '목요일', '금요일', '토요일'];
  function when(ms) {                                  // spec A2: 오늘 / 어제 / 이번 주 요일 / M월 D일
    const d = new Date(ms), now = new Date(), t = T.format(d);
    const day0 = x => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
    const diff = Math.round((day0(now) - day0(d)) / 864e5);
    if (diff === 0) return t; if (diff === 1) return '어제 ' + t;
    if (diff > 1 && diff < 7) return DAYS[d.getDay()] + ' ' + t;
    return `${d.getMonth() + 1}월 ${d.getDate()}일 ${t}`;
  }
  const hm = s => { const m = /^(\d{2}):(\d{2})$/.exec(s || ''); if (!m) return s || ''; const d = new Date(2000, 0, 1, +m[1], +m[2]); return T.format(d); };

  /* ================= §C shared .confirm-card (spec v2 C1–C4) ================= */
  const sanitize = a => { const o = Object.assign({}, a); delete o.confirm_token; delete o.token_expires_at; return o; };
  function variantOf(x) {                              // spec C4
    if (x.tool === 'memory.propose') return x.op === 'delete' ? 'forget' : 'remember';
    if (x.tool === 'proactive.propose_followup') return 'proactive';
    return 'tool';
  }
  // danger (spec §F-1): only send verbs and delete ops are red; write stays accent
  const dangerOf = (x, variant) => variant === 'forget' || x.op === 'delete' || x.verbs.includes('send') || x.verbs.includes('delete');
  const DENIED = { secret_detected: '비밀번호나 키처럼 보여서 진행하지 않았어요', cap_exceeded: '허용된 한도를 넘어서 진행하지 않았어요', tainted: '외부 내용이 섞인 요청이라 진행하지 않았어요',
    scope_denied: '이 작업은 할 수 있는 권한이 없어요', item_gone: '그사이 지워진 항목이 있어서 진행하지 않았어요',
    conflict: '이미 처리된 요청이에요', payload_mismatch: '내용이 바뀌어서 진행하지 않았어요', expired: '시간이 지나 진행하지 않았어요', not_found: '대상을 찾을 수 없어요', kill_switch: '지금은 이 기능을 쓸 수 없어요', writes_disabled: '지금은 쓰기가 꺼져 있어서 진행하지 않았어요', memory_read_only: '지금은 메모리를 바꿀 수 없어요', invalid: '요청 내용이 올바르지 않아 진행하지 않았어요' };
  const CROSS = '다른 서버에 연결돼 있어 여기서는 승인할 수 없어요. 설정에서 서버 주소를 비우면 돼요';
  const RTF = new Intl.DateTimeFormat('ko-KR', { month: 'long', day: 'numeric' }), YTF = new Intl.DateTimeFormat('ko-KR', { year: 'numeric', month: 'long', day: 'numeric' });
  function shortDate(iso) {                            // spec B2: 오늘 / N일 전 / 10월 21일 / 2025년 3월 2일
    const d = new Date(iso); if (isNaN(d)) return '';
    const now = new Date(), day0 = x => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime(), diff = Math.round((day0(now) - day0(d)) / 864e5);
    if (diff <= 0) return '오늘'; if (diff < 7) return diff + '일 전';
    return (d.getFullYear() === now.getFullYear() ? RTF : YTF).format(d);
  }
  /* 1.10.0 pim write cards (eve-serving #78: reminders_add / reminders_complete). Same .confirm-card; only the rows and error copy are pim-aware. */
  const PIM = x => x.scopes.some(c => /^(reminders|calendar)\./.test(c));
  const CAL = x => x.scopes.some(c => /^calendar\./.test(c));
  const OUTCOME_UNKNOWN = x => (CAL(x) ? '일정이 만들어졌는지' : '리마인더가 만들어졌는지') + ' 확인하지 못했어요. ' + (CAL(x) ? '캘린더' : '미리 알림') + ' 앱에서 확인해 주세요. 다시 시도하면 중복될 수 있어서 다시 보내지 않아요';
  const EXEC_ERR = { pim_unavailable: 'Mac의 캘린더 연동에 연결하지 못했어요. 잠시 후 다시 시도해 주세요', permission_denied: '캘린더·리마인더 접근이 허용되지 않았어요. Mac 설정을 확인해 주세요', timeout: '응답이 늦어서 실행하지 못했어요. 잠시 후 다시 시도해 주세요', invalid_arguments: '요청 내용이 올바르지 않아 진행하지 않았어요' };
  /* PIM confirm rows (eve-serving #66 §11.4): one shared card, fixed row names 제목·시간·목록/캘린더·장소·메모. `display` is server-made (Asia/Seoul) and shown as given;
     id / method / verb and the raw start·end·all_day·calendar_id are execution detail, never rows. */
  const PIM_HIDE = new Set(['verb', 'method', 'id', 'start', 'end', 'all_day', 'calendar_id', 'due', 'display', 'title', 'list', 'calendar', 'location', 'notes']);
  function pimRows(x, Pim) {
    const v = x.view || {}, cal = CAL(x), rows = [], s = k => (typeof v[k] === 'string' && v[k] !== '' ? v[k] : null);
    const add = (k, label, text, raw) => rows.push([k, label, text, raw == null || raw === text ? null : raw]);
    add('title', '제목', s('title') || '(제목 없음)');
    let when = s('display');
    if (!when) { if (cal && s('start')) when = Pim.fmtRange(v.start, v.end, v.all_day === true); else if (s('due')) when = Pim.fmtDue(v.due); }
    if (when) add('when', '시간', when); else if (!cal && ('due' in v || 'display' in v)) add('when', '시간', '기한 없음');
    if (cal) add('calendar', '캘린더', s('calendar') || (v.calendar_id == null ? '기본 캘린더' : '선택한 캘린더'));
    else if ('list' in v || x.tool === 'reminders_add') add('list', '목록', s('list') || '기본 목록');
    if (s('location')) add('location', '장소', v.location);
    if (s('notes')) add('notes', '메모', v.notes);
    Object.keys(v).filter(k => !PIM_HIDE.has(k)).forEach(k => { const val = v[k], raw = typeof val === 'string' ? val : JSON.stringify(val); add(k, k, raw); });   // unknown extra keys stay visible (never silently dropped)
    return rows;
  }
  const VERB_LABEL = { add: '추가', update: '변경', send: '보내기', delete: '삭제', run: '실행' };
  const VERB_DONE = { add: '추가했어요', update: '변경했어요', send: '보냈어요', delete: '삭제했어요', run: '실행했어요' };
  const verbOf = x => typeof x.verb === 'string' && Object.hasOwn(VERB_LABEL, x.verb) ? x.verb : 'run';   // own keys only ('constructor', '__proto__' → run)   // architect: payload_view.verb; unknown → run
  const VAR = {
    remember: { ic: 'brain', title: () => '메모리에 저장할까요?', primary: () => '저장', secondary: '취소', done: () => '저장했어요' },
    forget: { ic: 'trash', title: x => x.ambiguous ? '어떤 걸 지울까요?' : '메모리에서 지울까요?', primary: (x, n) => `${n}개 지우기`, secondary: '취소', done: (x, n) => `${n}개 지웠어요` },
    proactive: { ic: 'bell', title: () => '다시 알려 드릴까요?', primary: () => '알림 예약', secondary: '괜찮아요', done: x => x.display ? `${x.display}에 알려 드릴게요` : '알림을 예약했어요' },
    tool: { ic: 'wrench', title: x => x.summary || x.tool || '작업을 실행할까요?', primary: x => VERB_LABEL[verbOf(x)], secondary: '취소', done: x => VERB_DONE[verbOf(x)] }
  };
  const EXPIRED = '시간이 지나 취소됐어요';
  const deniedText = c => DENIED[c] || (c ? DENIED.invalid : '진행하지 않았어요');   // SSE denied without code → generic; unknown API code → invalid

export default function createPresentation({ proactiveAPI, Pim }) {
  return { ULID, PUSH_HOSTS, POLL_MS, LS_PUSH, LS_KID, icon, svg, IC, T, DAYS, when, hm, sanitize, variantOf, dangerOf, DENIED, CROSS, RTF, YTF, shortDate, PIM, CAL, OUTCOME_UNKNOWN, EXEC_ERR, PIM_HIDE, VERB_LABEL, VERB_DONE, verbOf, VAR, EXPIRED, deniedText,
    F: () => proactiveAPI.FIELDS, pimRows: x => pimRows(x, Pim) };
}
