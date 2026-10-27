/* Eve memory UI (PROACTIVE-MEMORY-SPEC Part B, eve-serving memory.md §4/§13 + ui-api-contract §2/§3.3).
 * Behind a feature flag, OFF by default: localStorage 'eve.flag.memory' === '1' turns it on.
 * Flag off → init() returns null and touches nothing (the settings section stays `hidden`).
 * Scope: Settings › 메모리 toggle (memory.enabled via PATCH /v1/settings) + saved-memory list with
 * confirm-before-delete. No add/edit screen yet, never prefilled from URL/model text (MEM §4 S5-H3/S5-R3).
 * The in-chat remember/forget cards live in proactive.js (§C confirm-card, reissue → approve, no SSE token).
 * Server calls and field names: memory-api.js only. */
(function () {
  const FLAG = 'eve.flag.memory';
  const enabled = () => { try { return localStorage.getItem(FLAG) === '1'; } catch { return false; } };
  const KIND = { profile: '프로필', preference: '선호', fact: '사실', task: '할 일' };
  const MSG = {
    unavailable: '지금은 메모리 기능을 쓸 수 없어요.',
    read_only: '지금은 메모리를 바꿀 수 없어요. 저장된 메모리는 그대로 남아 있어요.',
    network: '메모리를 불러오지 못했어요. 연결을 확인해 주세요.',
    error: '메모리를 불러오지 못했어요.',
    on: 'Eve가 대화에 참고할 정보를 기억해요. 저장할 때는 항상 먼저 물어봐요.',
    off: '꺼져 있어요. 저장된 메모리는 남아 있지만 대화에 쓰지 않아요.',
    offline: '서버에 연결되면 설정할 수 있어요.'
  };
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const D = new Intl.DateTimeFormat('ko-KR', { month: 'long', day: 'numeric' });
  function order(items) {                                   // spec B3 = injection order (MEM §3): pinned → live tasks → rest by updated_at desc
    const now = Date.now(), live = i => i.kind === 'task' && (!i.expiresAt || i.expiresAt > now);
    const rank = i => i.pinned ? 0 : live(i) ? 1 : 2;
    return items.slice().sort((a, b) => rank(a) - rank(b) || b.updatedAt - a.updatedAt);
  }
  function init(h) {
    if (!enabled() || !self.EveMemoryAPI) return null;
    const M = self.EveMemoryAPI, api = M.make(h.api), $ = id => document.getElementById(id);
    const sec = $('memSection'), sw = $('sMemory'), note = $('sMemNote'), open = $('memOpen'), count = $('memCount'), view = $('memoryView'),
      list = $('memList'), state = $('memState'), retry = $('memRetry'), banner = $('memBanner');
    if (!sec) return null;
    sec.hidden = false;
    let st = { enabled: true, readOnly: false, available: true }, items = [], loaded = false;
    function paint() {
      const blocked = !st.available || st.readOnly;
      sw.checked = st.available && st.enabled; sw.disabled = blocked || !h.isServer();
      note.textContent = !h.isServer() ? MSG.offline : !st.available ? MSG.unavailable : st.readOnly ? MSG.read_only : st.enabled ? MSG.on : MSG.off;
      note.classList.toggle('warn', blocked);
      open.disabled = !st.available || !h.isServer();
      count.textContent = loaded ? `${items.length}개` : '';
      banner.hidden = !st.readOnly; view.classList.toggle('mem-off', !st.enabled);
    }
    function showState(text, canRetry) { state.textContent = text || ''; state.hidden = !text; retry.hidden = !canRetry; }
    function renderList() {
      list.textContent = '';
      if (!items.length) { showState('아직 기억한 게 없어요. 대화 중에 “기억해”라고 하면 저장하기 전에 물어봐요.', false); return; }
      showState('', false);
      const now = Date.now();
      order(items).forEach(it => {
        const li = el('li', 'mem-row'); li.dataset.id = it.id;
        const expired = it.kind === 'task' && it.expiresAt && it.expiresAt <= now;
        li.setAttribute('aria-label', [KIND[it.kind], it.text, it.pinned ? '고정됨' : ''].filter(Boolean).join(', '));
        const main = el('div', 'mem-main');
        main.appendChild(el('p', 'mem-text', it.text));     // textContent only: never HTML
        const meta = [KIND[it.kind]]; if (it.pinned) meta.unshift('고정됨'); if (it.confidence === 'confirmed') meta.push('대화에서');
        if (it.kind === 'task' && it.expiresAt) meta.push(expired ? '만료됨' : D.format(new Date(it.expiresAt)) + ' 만료');
        main.appendChild(el('p', 'mem-meta', meta.join(' · ')));
        if (expired) li.classList.add('expired');
        const del = el('button', 'mem-del', '삭제'); del.type = 'button'; del.disabled = st.readOnly; del.setAttribute('aria-label', '삭제: ' + it.text);
        del.onclick = () => askDelete(li, it);
        li.append(main, del); list.appendChild(li);
      });
    }
    function askDelete(li, it) {                              // confirm step before the write
      if (li.querySelector('.mem-confirm')) return;
      list.querySelectorAll('.mem-confirm').forEach(c => c.remove());
      const box = el('div', 'mem-confirm'); box.setAttribute('role', 'group'); box.setAttribute('aria-label', '삭제 확인');
      box.appendChild(el('p', 'mem-confirm-q', '이 메모리를 지울까요? 지우면 되돌릴 수 없어요.'));
      const no = el('button', 'btn', '취소'), yes = el('button', 'btn danger', '삭제'); no.type = yes.type = 'button';
      no.onclick = () => box.remove();
      yes.onclick = async () => {
        yes.disabled = no.disabled = true; yes.textContent = '지우는 중…';
        try { await api.deleteItem(it.id); gone(); h.showToast('삭제했어요', '', null, 1600); }
        catch (e) {
          const k = M.errState(e);
          if (k === 'not_found' || (e.http === 404 && e.code !== 'kill_switch')) { gone(); h.showToast('이미 지워진 항목이에요', '', null, 1600); return; }
          if (k === 'read_only') { st.readOnly = true; paint(); renderList(); h.showToast('지금은 메모리를 바꿀 수 없어요', '', null, 3000); return; }
          if (k === 'unavailable') { st.available = false; paint(); h.showToast(MSG.unavailable, '', null, 3000); return; }
          yes.disabled = no.disabled = false; yes.textContent = '삭제';
          h.showToast(k === 'network' ? '연결이 끊겨 지우지 못했어요' : '지우지 못했어요', '다시 시도', () => yes.click(), 4000);
        }
      };
      box.append(no, yes); li.appendChild(box); no.focus();
      function gone() { items = items.filter(x => x.id !== it.id); paint(); renderList(); }
    }
    async function loadList() {
      list.textContent = ''; showState('불러오는 중…', false);
      try { items = await api.list(); loaded = true; paint(); renderList(); }
      catch (e) {
        const k = M.errState(e);
        if (k === 'unavailable') { st.available = false; view.hidden = true; paint(); return; }
        if (k === 'read_only') { st.readOnly = true; paint(); }
        showState(k === 'read_only' ? MSG.read_only : MSG[k] || MSG.error, k === 'network' || k === 'error');
      }
    }
    async function openSettings() {
      view.hidden = true; open.setAttribute('aria-expanded', 'false'); loaded = false; items = [];
      if (!h.isServer()) { paint(); return; }
      sw.disabled = true;
      try { st = M.FIELDS.settings(await api.getSettings() || {}); }
      catch (e) { const k = M.errState(e); st = { enabled: false, readOnly: k === 'read_only', available: k !== 'unavailable' && k !== 'network' && k !== 'error' }; if (k === 'network' || k === 'error') { paint(); note.textContent = '설정을 불러오지 못했어요.'; return; } }
      paint();
      if (st.available) api.list().then(x => { items = x; loaded = true; paint(); }).catch(e => { if (M.errState(e) === 'unavailable') { st.available = false; paint(); } });
    }
    sw.addEventListener('change', async () => {               // optimistic, rollback on failure (same as 선톡 toggle)
      const on = sw.checked, prev = st.enabled; st.enabled = on; paint();
      try { await api.setEnabled(on); }
      catch (e) {
        st.enabled = prev; const k = M.errState(e);
        if (k === 'read_only') st.readOnly = true; if (k === 'unavailable') st.available = false;
        paint(); h.showToast(k === 'network' ? '연결이 끊겨 설정을 저장하지 못했어요' : '설정을 저장하지 못했어요', '', null, 3000);
      }
    });
    open.addEventListener('click', () => { view.hidden = !view.hidden; open.setAttribute('aria-expanded', String(!view.hidden)); if (!view.hidden) loadList(); });
    retry.addEventListener('click', loadList);
    return { openSettings, flag: true };
  }
  self.EveMemory = { init, FLAG, order };
})();
