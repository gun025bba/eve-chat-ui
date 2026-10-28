/* Eve memory UI (PROACTIVE-MEMORY-SPEC Part B @ eve-chat-ui-design 68a6981; API: eve-serving ui-api-contract §3.9).
 * Behind a feature flag, OFF by default: localStorage 'eve.flag.memory' === '1' turns it on.
 * Flag off → init() returns null and touches nothing (the settings section stays `hidden`).
 * Server memory off (GW_MEMORY_ENABLED=false: no settings.memory block / bare 404 on /v1/memory) → section stays hidden.
 * In-chat 기억해/잊어줘 cards live in proactive.js. Server calls and field names: memory-api.js only. */
(function () {
  const FLAG = 'eve.flag.memory', BACKUP_SEEN = 'eve.mem.backupNoteSeen', UNDO_MS = 2800;
  const enabled = () => { try { return localStorage.getItem(FLAG) === '1'; } catch { return false; } };
  const KIND = { profile: '프로필', preference: '선호', fact: '사실', task: '할 일' };
  const MSG = {
    on: 'Eve가 대화에 참고할 정보를 기억해요. 저장할 때는 항상 먼저 물어봐요.',
    off: '꺼져 있어요. 저장된 메모리는 남아 있지만 대화에 쓰지 않아요',
    kill: '지금은 메모리 기능을 쓸 수 없어요',
    offline: '서버에 연결되면 설정할 수 있어요.',
    empty: '아직 기억한 게 없어요', emptySub: "대화 중에 '기억해'라고 하거나 + 로 직접 추가할 수 있어요",
    loadErr: '메모리를 불러오지 못했어요',
    ro: '지금은 메모리를 바꿀 수 없어요'
  };
  const SAVE_ERR = { secret_detected: '비밀번호·키·카드번호처럼 보이는 내용은 저장할 수 없어요', invalid: '300자까지 쓸 수 있어요',
    cap_exceeded: '메모리가 가득 찼어요', busy: '지금 요청이 많아요. 잠시 후 다시 시도해 주세요', internal: '저장하지 못했어요. 잠시 후 다시 시도해 주세요' };
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
      list = $('memList'), state = $('memState'), retry = $('memRetry'), banner = $('memBanner'), addB = $('memAdd'), wipeB = $('memWipe'),
      form = $('memForm'), expG = $('memExportGroup'), expB = $('memExport'), total = $('memTotal'), kindI = $('memKind'), textI = $('memText'), formErr = $('memFormErr'), sheet = $('memWipeSheet');
    if (!sec) return null;
    let st = { serverOn: false, enabled: true, readOnly: false, kill: false }, items = [], loaded = false, editing = null;
    const pending = new Map();                                 // id → {it, timer}: deletes waiting for the undo toast to close
    const ro = () => st.readOnly || st.kill;
    // toasts render inside the settings sheet (the app toast sits under the modal dialog and can't be tapped there)
    const tEl = $('memToast'), tText = $('memToastText'), tAct = $('memToastAct'); let tT = 0;
    function toast(text, act, fn, ms) {
      if (view.hidden) return h.showToast(text, act, fn, ms);
      tText.textContent = text; tAct.textContent = act || ''; tAct.hidden = !act; tAct.onclick = () => { hide(); fn && fn(); };
      tEl.hidden = false; clearTimeout(tT); const dur = ms || 3000; tT = setTimeout(hide, dur);
      tEl.onfocusin = () => clearTimeout(tT);                         // paused while focus is inside the toast
      tEl.onfocusout = () => { clearTimeout(tT); tT = setTimeout(hide, dur); };
      function hide() { clearTimeout(tT); tEl.hidden = true; }
    }
    function paint() {
      sec.hidden = !st.serverOn;
      sw.checked = st.enabled && !st.kill; sw.disabled = st.kill || !h.isServer();
      note.textContent = !h.isServer() ? MSG.offline : st.kill ? MSG.kill : st.enabled ? MSG.on : MSG.off;
      note.classList.toggle('warn', st.kill);
      open.disabled = !h.isServer();
      count.textContent = loaded ? `${items.length}개` : '';
      banner.hidden = !ro(); view.classList.toggle('mem-off', !st.enabled);
      addB.disabled = wipeB.disabled = ro(); if (ro()) { form.hidden = true; sheet.hidden = true; }
      const n = items.filter(i => !pending.has(i.id)).length;
      wipeB.parentElement.hidden = loaded && !n; expG.hidden = !loaded || !n;           // export works in read-only/off too
      total.hidden = !loaded; total.textContent = `${n} / 200`;
      list.querySelectorAll('button').forEach(b => { b.disabled = ro(); });
    }
    function showState(text, sub, canRetry) {
      state.textContent = ''; state.hidden = !text; retry.hidden = !canRetry;
      if (text) { state.appendChild(el('span', 'mem-state-t', text)); if (sub) state.appendChild(el('span', 'mem-state-s', sub)); }
    }
    // a write just said read-only / kill switch: keep that until the sheet reopens
    async function reread() {   // returns after paint
       try { const s = await api.getSettings(); st.enabled = s.enabled; st.kill = !s.available; } catch {} paint(); }
    // shared write-error handling (§3.9.8 / spec C): returns true if handled as a state change
    function writeBlocked(k) {
      if (k === 'read_only') { st.readOnly = true; paint(); renderList(); reread(); return true; }
      if (k === 'kill_switch') { reread().then(renderList); return true; }   // fallback for a mid-session change: settings decide
      if (k === 'off') { st.serverOn = false; paint(); return true; }
      return false;
    }
    function renderList() {
      list.textContent = '';
      const shown = items.filter(i => !pending.has(i.id));
      if (!shown.length) { showState(MSG.empty, MSG.emptySub, false); paint(); return; }
      showState('', '', false);
      const now = Date.now();
      order(shown).forEach(it => {
        const li = el('li', 'mem-row'); li.dataset.id = it.id;
        const expired = it.kind === 'task' && it.expiresAt && it.expiresAt <= now;
        li.setAttribute('aria-label', [KIND[it.kind], it.text, it.pinned ? '고정됨' : ''].filter(Boolean).join(', '));
        const main = el('div', 'mem-main');
        main.appendChild(el('p', 'mem-text', it.text));     // textContent only: never HTML
        const meta = [KIND[it.kind]]; if (it.pinned) meta.unshift('고정됨'); if (it.confidence === 'confirmed') meta.push('대화에서');
        if (it.kind === 'task' && it.expiresAt) meta.push(expired ? '만료됨' : D.format(new Date(it.expiresAt)) + ' 만료');
        main.appendChild(el('p', 'mem-meta', meta.join(' · ')));
        if (expired) li.classList.add('expired');
        const ed = el('button', 'mem-edit', '편집'); ed.type = 'button'; ed.setAttribute('aria-label', '편집: ' + it.text); ed.onclick = () => openForm(it);
        const del = el('button', 'mem-del', '삭제'); del.type = 'button'; del.setAttribute('aria-label', '삭제: ' + it.text); del.onclick = () => softDelete(it);
        li.append(main, ed, del); list.appendChild(li); swipe(li, it);
      });
      paint();
    }
    function swipe(li, it) {                                  // swipe left past 80px → delete (same as the button)
      let x0 = null;
      li.addEventListener('pointerdown', e => { if (!ro() && e.pointerType !== 'mouse') x0 = e.clientX; });
      li.addEventListener('pointermove', e => { if (x0 != null) li.style.transform = `translateX(${Math.min(0, e.clientX - x0)}px)`; });
      const end = e => { if (x0 == null) return; const dx = e.clientX - x0; x0 = null; li.style.transform = ''; if (dx < -80) softDelete(it); };
      li.addEventListener('pointerup', end); li.addEventListener('pointercancel', () => { x0 = null; li.style.transform = ''; });
    }
    // single delete: no confirm. Hide → toast '삭제됨 · 되돌리기' 2.8s → DELETE after it closes (pagehide commits at once).
    function softDelete(it) {
      if (ro() || pending.has(it.id)) return;
      const p = { it, timer: setTimeout(() => commit(it.id), UNDO_MS) }; pending.set(it.id, p); renderList();
      let first = false; try { first = !localStorage.getItem(BACKUP_SEEN); if (first) localStorage.setItem(BACKUP_SEEN, '1'); } catch {}
      toast('삭제됨' + (first ? ' · 백업에는 최대 7일 남아요' : ''), '되돌리기', () => { clearTimeout(p.timer); pending.delete(it.id); renderList(); }, UNDO_MS);
    }
    async function commit(id, keepalive) {
      const p = pending.get(id); if (!p) return; clearTimeout(p.timer);
      try { await api.deleteItem(id, keepalive); pending.delete(id); items = items.filter(x => x.id !== id); renderList(); }
      catch (e) {
        if (keepalive) return;
        const k = M.errState(e); pending.delete(id);
        if (k === 'not_found') { items = items.filter(x => x.id !== id); renderList(); return; }   // already gone
        renderList();
        if (writeBlocked(k)) return;
        toast(k === 'network' ? '연결이 끊겨 지우지 못했어요' : '지우지 못했어요', '다시 시도', () => softDelete(p.it), 4000);
      }
    }
    const flushDeletes = () => { for (const id of [...pending.keys()]) commit(id, true); };
    window.addEventListener('pagehide', flushDeletes);
    function openForm(it) {
      if (ro()) return;
      editing = it || null; form.hidden = false; formErr.hidden = true; kindI.disabled = !!it;
      kindI.value = it ? it.kind : 'preference'; textI.value = it ? it.text : ''; textI.focus();
    }
    const submit = async () => {
      const text = textI.value.trim(); if (!text) return;
      const save = $('memFormSave'); save.disabled = true; formErr.hidden = true; textI.removeAttribute('aria-invalid');
      try {
        const r = editing ? await api.edit(editing, text) : await api.add(kindI.value, text);
        items = items.filter(x => x.id !== r.id).concat(r); form.hidden = true; editing = null; renderList();
      } catch (e) {
        const k = M.errState(e);
        if (writeBlocked(k)) { form.hidden = true; return; }
        if (k === 'conflict' || k === 'not_found') { form.hidden = true; editing = null; loadList(); return; }   // changed elsewhere: show the current list
        if (k === 'off') { form.hidden = true; return; }
        textI.setAttribute('aria-invalid', 'true');
        formErr.textContent = k === 'network' ? '연결이 끊겨 저장하지 못했어요' : SAVE_ERR[k] || SAVE_ERR.invalid; formErr.hidden = false;
        if (k === 'internal' || k === 'network' || k === 'busy') { const rb = el('button', 'btn', '다시 시도'); rb.type = 'button'; rb.onclick = submit; formErr.append(' ', rb); }
      } finally { save.disabled = false; }
    };
    $('memFormSave').onclick = submit;
    textI.addEventListener('keydown', ev => { if (ev.key === 'Enter' && !ev.shiftKey && !ev.isComposing) { ev.preventDefault(); submit(); } });
    $('memFormCancel').onclick = () => { form.hidden = true; editing = null; };
    addB.onclick = () => openForm(null);
    wipeB.onclick = () => { if (!ro()) { sheet.hidden = false; $('memWipeNo').focus(); } };
    $('memWipeNo').onclick = () => { sheet.hidden = true; wipeB.focus(); };
    sheet.addEventListener('keydown', ev => {                 // focus trap inside the wipe-all sheet
      if (ev.key === 'Escape') { ev.preventDefault(); ev.stopPropagation(); $('memWipeNo').click(); return; }
      if (ev.key !== 'Tab') return;
      const f = [$('memWipeYes'), $('memWipeNo')], i = f.indexOf(document.activeElement);
      ev.preventDefault(); f[(i + (ev.shiftKey ? f.length - 1 : 1)) % f.length].focus();
    });
    const today = () => { const d = new Date(), z = n => String(n).padStart(2, '0'); return `eve-memory-${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}.json`; };
    expB.onclick = async () => {                              // device-only file: share sheet on iOS, else download
      expB.disabled = true; expB.textContent = '내보내는 중…';
      try {
        const j = await api.exportAll(), name = today(), blob = new Blob([JSON.stringify(j, null, 2)], { type: 'application/json' });
        const file = typeof File === 'function' ? new File([blob], name, { type: 'application/json' }) : null;
        const ios = /iP(hone|ad|od)/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
        if (ios && file && navigator.canShare?.({ files: [file] })) {
          try { await navigator.share({ files: [file] }); } catch (e) { if (e && e.name !== 'AbortError') throw e; }
        } else {
          const a = document.createElement('a'), u = URL.createObjectURL(blob); a.href = u; a.download = name; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(u), 1000);
        }
      } catch (e) { if (M.errState(e) === 'off') { st.serverOn = false; paint(); } else toast('내보내지 못했어요', '', null, 3000); }
      finally { expB.disabled = false; expB.textContent = '메모리 내보내기'; }
    };
    $('memWipeYes').onclick = async () => {
      const b = $('memWipeYes'); b.disabled = true;
      try { await api.deleteAll(); pending.forEach(p => clearTimeout(p.timer)); pending.clear(); items = []; sheet.hidden = true; renderList(); }
      catch (e) { const k = M.errState(e); sheet.hidden = true; if (!writeBlocked(k)) toast(k === 'network' ? '연결이 끊겨 지우지 못했어요' : '지우지 못했어요', '', null, 3000); }
      finally { b.disabled = false; }
    };
    async function loadList() {
      list.textContent = ''; showState('불러오는 중…', '', false);
      try { items = await api.list(); loaded = true; renderList(); }
      catch (e) {
        const k = M.errState(e);
        if (k === 'off') { st.serverOn = false; paint(); return; }    // GET /v1/memory 404 = server memory off (no item to miss): unavailable, not an error
        showState(MSG.loadErr, '', true);
      }
    }
    async function openSettings() {
      view.hidden = true; open.setAttribute('aria-expanded', 'false'); loaded = false; items = []; form.hidden = true; sheet.hidden = true;
      if (!h.isServer()) { st.serverOn = false; paint(); return; }
      try { const s = await api.getSettings(); st = { serverOn: true, enabled: s.enabled, kill: !s.available, readOnly: false }; }   // memory_available=false → shown, toggle disabled + footer
      catch { st.serverOn = false; paint(); return; }             // settings unreadable → keep memory UI hidden
      paint();
      api.list().then(x => { items = x; loaded = true; paint(); }).catch(e => { if (M.errState(e) === 'off') { st.serverOn = false; paint(); } });
    }
    sw.addEventListener('change', async () => {               // optimistic, rollback on failure (same as 선톡 toggle)
      const on = sw.checked, prev = st.enabled; st.enabled = on; paint();
      try { await api.setEnabled(on); }
      catch (e) {
        st.enabled = prev; const k = M.errState(e); paint();
        if (!writeBlocked(k)) toast(k === 'network' ? '연결이 끊겨 설정을 저장하지 못했어요' : '설정을 저장하지 못했어요', '', null, 3000);
      }
    });
    open.addEventListener('click', () => { view.hidden = !view.hidden; open.setAttribute('aria-expanded', String(!view.hidden)); if (!view.hidden) loadList(); });
    retry.addEventListener('click', loadList);
    /* B5 first-run intro sheet #memIntro (design 824725d). Once per launch at most; seen = localStorage OR server ui.memory_intro_seen. */
    const INTRO_SEEN = 'eve.mem.introSeen', ix = $('memIntro'), iScrim = $('memIntroScrim');
    let introTried = false, introPrev = null, introTimer = 0;
    const localSeen = () => { try { return localStorage.getItem(INTRO_SEEN) === '1'; } catch { return false; } };
    function intro() {
      if (introTried || !ix || localSeen() || !h.isServer() || !h.route || h.route() !== 'list') return;
      introTried = true;
      clearTimeout(introTimer);
      introTimer = setTimeout(async () => {
        let s; try { s = await api.getSettings(); } catch { return; }   // unreadable/offline: skip this launch, no seen
        if (!s.available || !s.enabled || s.introSeen || localSeen()) return;            // memory_available=false → no seen either
        if (!h.isServer() || h.route() !== 'list' || (h.busy && h.busy())) return;   // another sheet/card up: skip this launch
        showIntro();
      }, 600);
    }
    function introFocusables() { return [...ix.querySelectorAll('button')].filter(b => !b.disabled && !b.hidden); }
    function showIntro() {
      introPrev = document.activeElement;
      iScrim.hidden = false; ix.hidden = false; void ix.offsetWidth; ix.classList.add('show'); iScrim.classList.add('show');
      try { localStorage.setItem(INTRO_SEEN, '1'); } catch {}
      api.markIntroSeen().catch(() => {});                                      // 400 (key not in contract yet) or anything else: ignore
      $('memIntroTitle').focus();
    }
    function closeIntro(after) {
      if (ix.hidden) return;
      ix.classList.remove('show'); iScrim.classList.remove('show');
      const done = () => { ix.hidden = true; iScrim.hidden = true; ix.style.transform = '';
        if (after) after(); else if (introPrev && introPrev.focus && document.contains(introPrev)) introPrev.focus(); };
      matchMedia('(prefers-reduced-motion: reduce)').matches ? setTimeout(done, 200) : setTimeout(done, 380);
    }
    if (ix) {
      $('memIntroOk').onclick = () => closeIntro();
      iScrim.onclick = () => closeIntro();
      $('memIntroSettings').onclick = () => closeIntro(() => {                   // open Settings › 메모리, focus the toggle; never turns memory off
        h.openSettings && h.openSettings();
        let n = 0; const t = setInterval(() => {
          if (!sec.hidden || ++n > 40) { clearInterval(t); if (!sec.hidden) { sec.scrollIntoView({ block: 'center' }); sw.focus(); } }
        }, 75);
      });
      ix.addEventListener('keydown', ev => {
        if (ev.key === 'Escape') { ev.preventDefault(); ev.stopPropagation(); closeIntro(); return; }
        if (ev.key !== 'Tab') return;
        const f = introFocusables(), i = f.indexOf(document.activeElement); ev.preventDefault();
        f[i < 0 ? (ev.shiftKey ? f.length - 1 : 0) : (i + (ev.shiftKey ? f.length - 1 : 1)) % f.length].focus();
      });
      document.addEventListener('focusin', ev => { if (!ix.hidden && !ix.contains(ev.target)) $('memIntroTitle').focus(); });
      let y0 = null;                                                             // swipe down = 좋아요
      ix.addEventListener('pointerdown', e => { if (e.target.closest('button')) return; y0 = e.clientY; });
      ix.addEventListener('pointermove', e => { if (y0 != null) ix.style.transform = `translateY(${Math.max(0, e.clientY - y0)}px)`; });
      const end = e => { if (y0 == null) return; const dy = e.clientY - y0; y0 = null; ix.style.transform = ''; if (dy > 80) closeIntro(); };
      ix.addEventListener('pointerup', end); ix.addEventListener('pointercancel', () => { y0 = null; ix.style.transform = ''; });
    }
    /* DIRECTION-B §5/§8.1: "참고한 기억" chip is shown only while memory is effectively on (memory_available AND memory.enabled); unknown → off */
    const active = () => !!(h.isServer() && st.serverOn && st.enabled && !st.kill);
    let okAt = 0;
    async function ensure() { if (!(h.isServer() && st.serverOn && Date.now() - okAt < 60000)) { try { const s = await api.getSettings(); st = Object.assign({}, st, { serverOn: true, enabled: s.enabled, kill: !s.available }); okAt = Date.now(); } catch { st = Object.assign({}, st, { serverOn: false }); } } return active(); }
    return { openSettings, flag: true, flushDeletes, intro, closeIntro, active, ensure };
  }
  self.EveMemory = { init, FLAG, order };
})();
