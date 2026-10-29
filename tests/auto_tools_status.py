"""AUTO-TOOLS-SPEC §13 · the tool status line (.tline > .tstat), failure notes (text only, no action), the note restored after a reload, stop, chips/sheet, escaping, motion.
Mock scripts (PRO.atScript) replay tool_call / tool_result events; selected_by / count / error_code are the proposed (optional) fields."""
from at_common import *
FIVE = [src(i, d) for i, d in enumerate(['news.example.com', 'blog.example.org', 'docs.example.net', 'a.example.com', 'b.example.com'], 1)]
ANS = '검색 결과에 따르면 빠릅니다[1][2].'
with sync_playwright() as p:
    b = p.chromium.launch()
    server(auto=True)
    ctx, pg = launch(b)
    # ── S2 → S3 → S4 → answer ──
    script([S(call(), .3), S(result(sources=FIVE, count=5), 1.2), T(ANS, 2.6)], FIVE[:2])
    send(pg); pg.wait_for_timeout(700)
    ts = tstat(pg)
    check('S2 line: 웹에서 찾고 있어요 + “검색어”', ts and ts['r1'] == '웹에서 찾고 있어요' and ts['r2'] == '“카카오 오늘 소식”', ts)
    a = pg.evaluate("(()=>{const e=document.querySelector('.tstat');return {role:e.getAttribute('role'),live:e.getAttribute('aria-live'),atomic:e.getAttribute('aria-atomic'),icon:e.querySelector('svg').getAttribute('aria-hidden'),h:e.getBoundingClientRect().height}})()")
    check('.tstat role=status aria-live=polite aria-atomic=true, icon aria-hidden', a['role'] == 'status' and a['live'] == 'polite' and a['atomic'] == 'true' and a['icon'] == 'true', a)
    check('two rows → ≥ 40px', a['h'] >= 40, a)
    check('2.0.0: no one-time hint, no localStorage key (even for selected_by:model)', pg.locator('.tline .hint, .hint-chg').count() == 0 and pg.evaluate("localStorage.getItem('llmchat.autoHintSeen')") is None)
    check('2.0.0: the request has no web_search field', 'web_search' not in db()['state']['lastBody'], db()['state']['lastBody'])
    pg.evaluate("window.__t0=document.querySelector('.tstat')")
    check('S3: 출처 5개를 읽고 있어요 · 첫 도메인 외 4곳', wait_tstat(pg, '출처 5개를 읽고 있어요', 4000) and 'news.example.com 외 4곳' in tstat(pg)['r2'], tstat(pg))
    check('the same .tstat node is reused', pg.evaluate("document.querySelector('.tstat')===window.__t0 && document.querySelectorAll('.tstat').length===1"))
    check('S4: 답변을 쓰고 있어요', wait_tstat(pg, '답변을 쓰고 있어요', 4000), tstat(pg))
    # first token → the line leaves (opacity transition, then removed) and the answer starts in its place
    pg.wait_for_function("()=>!!document.querySelector('.msg.assistant .md')", timeout=8000)
    op = pg.evaluate("(()=>{const l=document.querySelector('.tline');return l?{out:l.classList.contains('out'),pos:getComputedStyle(l).position}:null})()")
    check('first token: line fades out of the flow (.out, absolute) …', op is None or (op['out'] and op['pos'] == 'absolute'), op)
    pg.wait_for_timeout(300)
    check('… and is removed from the DOM', pg.locator('.tline, .tstat').count() == 0)
    check('settles with chips; no note when cited', settle(pg) and pg.locator('.msg.assistant .sources').count() == 1 and pg.locator('.tnote').count() == 0)
    fresh_chat(pg); script([S(call(id='t2', q='두 번째'), .3), S(result(id='t2', sources=FIVE[:2]), 1.2), T(ANS, 1.5)], FIVE[:2]); send(pg); pg.wait_for_timeout(1000)
    check('second search: still no hint', pg.locator('.tline .hint').count() == 0 and pg.locator('.tstat').count() == 1)
    settle(pg)
    ctx.close()
    # selected_by absent (old server) → today's flow still works
    ctx, pg = launch(b); script([S(call(by=''), .3), S(result(sources=FIVE[:1]), 1.2), T(ANS, 1.5)], FIVE[:1]); send(pg); pg.wait_for_timeout(800)
    check('no selected_by → line still shown', ((tstat(pg) or {}).get('r1') == '웹에서 찾고 있어요'), tstat(pg))
    check('N=1 → 출처 1개 and no second row', wait_tstat(pg, '출처 1개를 읽고 있어요', 4000) and tstat(pg)['r2'] == '', tstat(pg)); settle(pg)
    ctx.close()
    # ── web_fetch + bad URL, www. stripped ──
    ctx, pg = launch(b)
    script([S(call(tool='web_fetch', url='https://www.example.com/notes', by=''), .3), S(result(tool='web_fetch', sources=FIVE[:1]), 1.4), T(ANS, 1.0)], FIVE[:1]); send(pg); pg.wait_for_timeout(700)
    ts = tstat(pg); check('web_fetch: 페이지를 읽고 있어요 + domain without www.', ts and ts['r1'] == '페이지를 읽고 있어요' and ts['r2'] == 'example.com', ts); settle(pg)
    fresh_chat(pg); script([S(call(tool='web_fetch', url='not a url', by=''), .3), S(result(tool='web_fetch', sources=FIVE[:1]), 1.4), T(ANS, 1.0)], FIVE[:1]); send(pg); pg.wait_for_timeout(700)
    ts = tstat(pg); check('bad URL → 웹 페이지, no error', ts and ts['r2'] == '웹 페이지' and not pg.errs, (ts, pg.errs)); settle(pg)
    # unknown tool name → ignored (no line, no chip), reply fine
    fresh_chat(pg); script([S(call(tool='mystery_tool', by=''), .3), S(result(tool='mystery_tool', sources=FIVE[:1]), .5), T(ANS, .5)]); send(pg); pg.wait_for_timeout(500)
    check('unknown tool → no line', pg.locator('.tstat').count() == 0); settle(pg)
    check('unknown tool → no chips, answer shown', pg.locator('.msg.assistant .sources').count() == 0 and '빠릅니다' in pg.locator('.msg.assistant').last.inner_text())
    # ── old order (call+result at once) and result without call ──
    fresh_chat(pg); script([S(call(by=''), 0), S(result(sources=FIVE), 0), T(ANS, 1.2)], FIVE[:2]); send(pg); pg.wait_for_timeout(500)
    check('old order: lands on S3 without error', wait_tstat(pg, '출처 5개를 읽고 있어요', 3000) and not pg.errs, (tstat(pg), pg.errs)); settle(pg)
    fresh_chat(pg); script([S(result(id='zz', sources=FIVE[:3]), 0), T(ANS, 1.2)], FIVE[:2]); send(pg); pg.wait_for_timeout(500)
    check('result without call: S3, no error', wait_tstat(pg, '출처 3개를 읽고 있어요', 3000) and not pg.errs, (tstat(pg), pg.errs)); settle(pg)
    # ── 3 searches → one .tstat reused, throttled ≥ 1 s ──
    fresh_chat(pg)
    pg.evaluate("window.__max=0;window.__texts=[];window.__iv=setInterval(()=>{const n=document.querySelectorAll('.tstat').length;window.__max=Math.max(window.__max,n);const e=document.querySelector('.tstat .t1 span.on');if(e&&window.__texts[window.__texts.length-1]!==e.textContent)window.__texts.push(e.textContent)},40)")
    items = []
    for i in (1, 2, 3): items += [S(call(id=f'r{i}', q=f'검색 {i}', by='model', rnd=i), .15), S(result(id=f'r{i}', sources=FIVE[:2]), .15)]
    script(items + [T(ANS, 2.5)], FIVE[:2]); send(pg); settle(pg, 14000)
    m = pg.evaluate("[window.__max, window.__texts]")
    check('3 searches in a turn → exactly one .tstat at any time', m[0] == 1, m)
    check('texts swapped in place (S2/S3 repeated)', m[1].count('웹에서 찾고 있어요') >= 2 or len(m[1]) >= 3, m)
    # throttle: measure gaps between text changes while three fast updates are queued
    fresh_chat(pg)
    pg.evaluate("window.__ch=[];window.__iv2=setInterval(()=>{const e=document.querySelector('.tstat .t1 span.on');if(e&&(!window.__ch.length||window.__ch[window.__ch.length-1][1]!==e.textContent))window.__ch.push([performance.now(),e.textContent])},30)")
    script([S(call(id='k1', q='빠른 1', by=''), .1), S(result(id='k1', sources=FIVE[:2]), .1), S(call(id='k2', q='빠른 2', by='', rnd=2), .1), S(result(id='k2', sources=FIVE[:3]), .1), T(ANS, 3.5)], FIVE[:2]); send(pg); settle(pg, 14000)
    ch = pg.evaluate("window.__ch"); gaps = [ch[i + 1][0] - ch[i][0] for i in range(len(ch) - 1)]
    check('updates are ≥ ~1 s apart (throttle)', len(ch) >= 2 and all(g >= 850 for g in gaps), (gaps, [c[1] for c in ch]))
    # ── S9: 6 s after the call → "· 조금 걸려요", once, hidden from the live region ──
    fresh_chat(pg); script([S(call(id='sl', q='느린 검색', by='model'), .2), S(result(id='sl', sources=FIVE[:2]), 7.2), T(ANS, .6)], FIVE[:2]); send(pg); pg.wait_for_timeout(5200)
    check('no 조금 걸려요 before 6 s', pg.locator('.tstat .slow').count() == 0)
    pg.wait_for_timeout(1700)
    sl = pg.evaluate("(()=>{const s=[...document.querySelectorAll('.tstat .slow')];return {n:s.length,t:s[0]&&s[0].textContent,hid:s[0]&&s[0].getAttribute('aria-hidden')}})()")
    check('· 조금 걸려요 once, aria-hidden (never re-read)', sl['n'] == 1 and '조금 걸려요' in (sl['t'] or '') and sl['hid'] == 'true', sl); settle(pg, 14000)
    # ── PIM tools keep their own copy and never grow web chips ──
    fresh_chat(pg); script([S({'object': 'chat.completion.tool_call', 'id': 'pc', 'tool': 'calendar_list_events', 'args': {}, 'round': 1}, .3), T('일정이 없어요.', 1.8)]); send(pg); pg.wait_for_timeout(700)
    txt = pg.evaluate("(()=>{const e=[...document.querySelectorAll('.msg.assistant .tstat')].pop();return e?e.textContent:''})()")
    check('calendar tool → PIM copy, not the web copy', txt and '웹' not in txt and '출처' not in txt, txt); settle(pg)
    check('… and no web chips', pg.locator('.msg.assistant .sources').count() == 0)
    check('no page errors so far', not pg.errs, pg.errs)
    ctx.close()

    # ── §5.1 failure notes ──
    CASES = [  # name, tool_result extras, status-line copy, note title, sub
        ('ok, 0 results', dict(status='ok'), '검색 결과가 없어요', '검색 결과를 찾지 못했어요', '학습한 내용으로 답했어요'),
        ('timeout', dict(status='timeout'), '검색이 오래 걸려 멈췄어요', '검색 시간이 초과됐어요', '지금까지 확인한 내용으로 답했어요'),
        ('search_unavailable', dict(status='error', error_code='search_unavailable'), '지금은 검색을 쓸 수 없어요', '최신 정보를 확인하지 못했어요', '검색이 잠시 안 돼서 학습한 내용으로 답했어요'),
        ('rate_limited', dict(status='error', error_code='rate_limited'), '검색 요청이 많아요', '검색 요청이 많아요', '잠시 뒤에는 다시 검색할 수 있어요'),
        ('budget_exhausted', dict(status='error', error_code='budget_exhausted'), '검색 한도에 도달했어요', '한 번에 할 수 있는 검색을 다 썼어요', '지금까지 찾은 내용으로 답했어요'),
        ('blocked', dict(status='blocked', blocked_count=2), '차단된 주소는 열지 않았어요', '일부 페이지는 열지 않았어요', '안전하지 않은 주소라 건너뛰었어요'),
        ('kill_switch', dict(status='error', error_code='kill_switch'), '지금은 검색을 쓸 수 없어요', '웹 검색을 쓸 수 없어요', '관리 설정으로 꺼져 있어요'),
        ('permission_denied', dict(status='error', error_code='permission_denied'), '지금은 검색을 쓸 수 없어요', '웹 검색을 쓸 수 없어요', '관리 설정으로 꺼져 있어요'),
        ('denied status', dict(status='denied'), '지금은 검색을 쓸 수 없어요', '웹 검색을 쓸 수 없어요', '관리 설정으로 꺼져 있어요'),
        ('query_rejected', dict(status='error', error_code='query_rejected'), '검색어에 보낼 수 없는 내용이 있어요', '검색하지 않았어요', '개인 정보처럼 보이는 내용은 밖으로 보내지 않아요'),
        ('unknown code', dict(status='error', error_code='weird_code_x', message='SECRET internal failure trace'), '검색하지 못했어요', '최신 정보를 확인하지 못했어요', '검색이 안 돼서 학습한 내용으로 답했어요'),
        ('error without code', dict(status='error', detail='SECRET trace detail'), '검색하지 못했어요', '최신 정보를 확인하지 못했어요', '검색이 안 돼서 학습한 내용으로 답했어요')]
    ctx, pg = launch(b)
    for name, extra, line, title, sub in CASES:
        fresh_chat(pg)
        script([S(call(id='f1', q='내 번호 010-1234-5678'), .3), S(result(id='f1', **extra), .5), T('답변이에요.', 2.2)])
        send(pg); pg.wait_for_timeout(1200)
        mid = tstat(pg)
        check(f'{name}: status line copy', wait_tstat(pg, line, 3000), tstat(pg))
        if name == 'query_rejected': check(f'{name}: the rejected query is not shown once rejected', '010' not in (tstat(pg) or {}).get('r2', ''), tstat(pg))
        settle(pg, 12000)
        n = pg.evaluate("(()=>{const n=document.querySelector('.msg.assistant .tnote');if(!n)return null;const a=n.closest('.msg').querySelector('.actions');return {t:n.textContent,role:n.getAttribute('role'),b:n.querySelector('b').textContent,btn:n.querySelectorAll('button,a,[role=button]').length,color:getComputedStyle(n.querySelector('b')).color,before:a?!!(n.compareDocumentPosition(a)&4):null,warn:!!n.querySelector('svg')}})()")
        check(f'{name}: note title/sub, role=status, above the action row', n and n['b'] == title and sub in n['t'] and n['role'] == 'status' and n['before'] is True, n)
        check(f'{name}: text only — no 「웹에서 다시 찾기」, no button/link/retry in the note', n and n['btn'] == 0 and '다시 찾기' not in n['t'] and pg.locator('.tnote .retry').count() == 0, n)
        check(f'{name}: no server string leaks', pg.locator('.msg.assistant').last.inner_text().find('SECRET') < 0 and 'internal' not in pg.locator('.msg.assistant').last.inner_text())
    # persists after the stream ended; chips absent
    check('note stays after the stream ended', pg.locator('.tnote').count() == 1)
    # duplicate_query / tainted: silent
    for code in ('duplicate_query', 'tainted'):
        fresh_chat(pg); script([S(call(id='d1', q='같은 검색'), .3), S(result(id='d1', status='error', error_code=code), .4), T('답변이에요.', 2.0)]); send(pg); pg.wait_for_timeout(1500)
        check(f'{code}: line unchanged (no failure copy)', (tstat(pg) or {}).get('r1') in ('웹에서 찾고 있어요', '답변을 쓰고 있어요'), tstat(pg)); settle(pg, 9000)
        check(f'{code}: no note', pg.locator('.tnote').count() == 0)
    # partial failure + cited → no note;  blocked + cited → note
    fresh_chat(pg); script([S(call(id='p1', q='첫 검색'), .2), S(result(id='p1', status='error', error_code='search_unavailable'), .2), S(call(id='p2', q='둘째', rnd=2), .2), S(result(id='p2', sources=FIVE[:2]), .2), T(ANS, 2.4)], FIVE[:2]); send(pg); settle(pg, 12000)
    check('partial failure with cited sources → no note, chips shown', pg.locator('.tnote').count() == 0 and pg.locator('.msg.assistant .sources').count() == 1)
    fresh_chat(pg); script([S(call(id='b1', q='차단'), .2), S(result(id='b1', status='blocked', blocked_count=1, sources=FIVE[:2]), .3), T(ANS, 2.4)], FIVE[:2]); send(pg); settle(pg, 12000)
    check('blocked + cited sources → note allowed (blocked is the exception)', pg.locator('.tnote').count() == 1 and pg.locator('.msg.assistant .sources').count() == 1)
    check('no page errors (failures)', not pg.errs, pg.errs)
    ctx.close()
    # ── restore after a reload: metadata.fresh:'unverified' → the generic note comes back (text only), nothing else changes ──
    server(auto=True); ctx, pg = launch(b)
    put('/pro/set', {'atFresh': 'unverified'})
    script([S(call(id='u1', q='복원 검색'), .2), S(result(id='u1', sources=FIVE[:1]), .3), T('답변이에요.', 1.2)], FIVE[:1]); send(pg); settle(pg, 12000)
    put('/pro/set', {'atFresh': None})
    pg.evaluate("localStorage.removeItem('llmchat.convs')"); pg.reload(); pg.wait_for_timeout(1200)
    if not pg.is_visible('#input'): pg.evaluate("document.querySelector('#convList li.row .row-main').click()"); pg.wait_for_timeout(1500)
    pg.wait_for_timeout(500)
    n = pg.evaluate("(()=>{const n=document.querySelector('.msg.assistant .tnote');return n?{b:n.querySelector('b').textContent,t:n.textContent,btn:n.querySelectorAll('button,a').length,role:n.getAttribute('role')}:null})()")
    check('after reload: fresh:unverified → note 「최신 정보를 확인하지 못했어요」, role=status, no action', n and n['b'] == '최신 정보를 확인하지 못했어요' and n['role'] == 'status' and n['btn'] == 0, n)
    check('after reload: no query line (queries are never stored)', pg.locator('.tq').count() == 0)
    # reason from metadata.tools[]: last status≠ok → §5.1 copy; tools[] empty → 검색하지 않고…; a joined query shows up in the sheet line
    def reload_case(tag, fresh, tools, items, srcs=None):
        server(auto=True); ctx.close(); c2, p2 = launch(b); put('/pro/set', {'atFresh': fresh, 'atTools': tools, 'atPersistedMeta': False})
        script(items, srcs); send(p2); settle(p2, 12000); put('/pro/set', {'atFresh': None, 'atTools': None, 'atPersistedMeta': True})
        p2.evaluate("localStorage.removeItem('llmchat.convs')"); p2.reload(); p2.wait_for_timeout(1200)
        if not p2.is_visible('#input'): p2.evaluate("document.querySelector('#convList li.row .row-main').click()"); p2.wait_for_timeout(1500)
        p2.wait_for_timeout(500); return c2, p2
    ctx, pg = reload_case('timeout', 'unverified', [{'tool': 'web_search', 'selected_by': 'model', 'status': 'timeout'}], [S(call(id='w1', q='q'), .2), S(result(id='w1', status='timeout'), .2), T('답변이에요.', 1.0)])
    nt = pg.evaluate("(()=>{const n=document.querySelector('.msg.assistant .tnote');return n?n.querySelector('b').textContent:null})()")
    check('reload: tools[] last status=timeout → 「검색 시간이 초과됐어요」', nt == '검색 시간이 초과됐어요', nt)
    ctx, pg = reload_case('nosearch', 'unverified', [], [T('답변이에요.', 1.0)])
    nt = pg.evaluate("(()=>{const n=document.querySelector('.msg.assistant .tnote');return n?n.textContent:null})()")
    check('reload: fresh:unverified + tools[] empty → 「검색하지 않고 학습한 내용으로 답했어요」', nt and '검색하지 않고 학습한 내용으로 답했어요' in nt, nt)
    ctx, pg = reload_case('query', 'ok', [{'tool': 'web_search', 'selected_by': 'model', 'status': 'ok', 'count': 2, 'query': '서버가 붙인 검색어'}], [S(call(id='w2', q='실시간'), .2), S(result(id='w2', sources=FIVE[:2]), .2), T(ANS, 1.0)], FIVE[:2])
    pg.locator('.msg.assistant .sources .sc').first.click(); pg.wait_for_timeout(700)
    tq = pg.evaluate("[...document.querySelectorAll('.tq')].map(e=>e.textContent)")
    check('reload: a server-joined metadata.tools[].query is shown in the sheet line; fresh:ok → no note', pg.locator('.tnote').count() == 0 and len(tq) == 1 and '서버가 붙인 검색어' in tq[0] and 'Eve가 필요하다고 판단해 검색했어요' in tq[0], tq)
    # live: persisted.fresh is the authority over the tool_result
    server(auto=True); ctx.close(); ctx, pg = launch(b); put('/pro/set', {'atFresh': 'ok', 'atTools': []})
    script([S(call(id='l1', q='q'), .2), S(result(id='l1', status='timeout'), .2), T('답변이에요.', 1.0)]); send(pg); settle(pg, 12000)
    check('live: persisted.fresh:ok wins over a failed tool_result → no note', pg.locator('.tnote').count() == 0)
    server(auto=True); fresh_chat(pg); put('/pro/set', {'atFresh': 'unverified', 'atTools': []})
    script([S(call(id='l2', q='q'), .2), S(result(id='l2', sources=FIVE[:2]), .2), T(ANS, 1.0)], FIVE[:2]); send(pg); settle(pg, 12000)
    check('live: persisted.fresh:unverified shows the note even with cited sources', pg.locator('.tnote').count() == 1 and pg.locator('.msg.assistant .sources').count() == 1)
    put('/pro/set', {'atFresh': None, 'atTools': None})
    ctx.close()

    # ── stop: the line goes at once, no chips/note, …/cancel called ──
    server(auto=True); ctx, pg = launch(b)
    script([S({'message_id': 'msg_at_stop', 'thread_id': 't'}, 0, name='eve.meta'), S(call(id='s1', q='멈출 검색'), .2), S(result(id='s1', status='error', error_code='search_unavailable'), 8), T('늦은 답', 1)]); send(pg); pg.wait_for_timeout(1200)
    check('before stop the line is there', pg.locator('.tstat').count() == 1)
    pg.click('#sendBtn'); pg.wait_for_timeout(100)
    op = pg.evaluate("(()=>{const l=document.querySelector('.tline');return l?{out:l.classList.contains('out'),op:getComputedStyle(l).opacity}:null})()")
    check('stop: line already leaving (or gone) within 100 ms', op is None or op['out'], op)
    pg.wait_for_timeout(300)
    check('stop: line removed from the DOM', pg.locator('.tline').count() == 0)
    check('stop: no chips, no note; stopped mark shown', pg.locator('.tnote').count() == 0 and pg.locator('.msg.assistant .sources').count() == 0 and pg.locator('.msg.assistant .stopped').count() == 1)
    check('stop: …/cancel called', len(db()['state'].get('cancels', [])) >= 1, db()['state'].get('cancels'))
    pg.wait_for_timeout(1500); check('stop: nothing reappears later', pg.locator('.tline, .tnote').count() == 0)
    ctx.close()
    done(); b.close()
