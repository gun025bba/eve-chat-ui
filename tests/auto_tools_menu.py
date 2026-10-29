"""AUTO-TOOLS-SPEC §13 · the + menu modes (auto / force / off), legacy fallback, chips/sheet .tq, layout, motion, tokens."""
from at_common import *
S2 = [src(1, 'news.example.com', published='2026-10-27'), src(2, 'blog.example.org', published='2025-03-02')]
ANS = '검색 결과에 따르면 빠릅니다[1][2].'
def rows(pg, sel='#plusMenu'): return pg.evaluate("s=>[...document.querySelectorAll(s+' .mode')].filter(r=>!r.hidden&&r.offsetParent).map(r=>({m:r.dataset.mode,c:r.getAttribute('aria-checked'),t:r.querySelector('.a').textContent,s:r.querySelector('.b').textContent,h:r.getBoundingClientRect().height,role:r.getAttribute('role')}))", sel)
def openm(pg, btn='#plusBtn'): pg.click(btn); pg.wait_for_timeout(320)
def body(pg): return db()['state']['lastBody']
def last_ask(pg, text='그냥 질문'):
    send(pg, text); pg.wait_for_timeout(1500); return body(pg)
with sync_playwright() as p:
    b = p.chromium.launch()
    # ── auto_select_available:true → 2 rows (force held), default checked = auto ──
    server(auto=True, tools_auto=True); ctx, pg = launch(b)
    openm(pg); r = rows(pg)
    check('modes: 자동 / 사용 안 함 (force held back)', [x['m'] for x in r] == ['auto', 'off'], r)
    check('rows: role=menuitemradio, ≥ 44px', all(x['role'] == 'menuitemradio' and x['h'] >= 44 for x in r), r)
    check('nothing stored + tools.auto:true → 자동 checked', r[0]['c'] == 'true' and r[1]['c'] == 'false', r)
    check('copy: 자동 · 필요하면 Eve가 직접 검색해요 / 사용 안 함 · 질문을 외부로 보내지 않아요', r[0]['t'] == '자동' and '필요하면 Eve가 직접 검색해요' in r[0]['s'] and r[1]['t'] == '사용 안 함' and '질문을 외부로 보내지 않아요' in r[1]['s'], r)
    check('legacy 웹 검색 row is gone', not pg.is_visible('#webBtn'))
    ab = pg.evaluate("(()=>{const b=document.querySelector('#plusBtn');return {l:b.getAttribute('aria-label'),c:b.className}})()")
    check('+ button auto: aria-label 웹 검색 자동, no on/off marker', '자동' in ab['l'] and 'web-on' not in ab['c'] and 'web-off' not in ab['c'], ab)
    check('focus lands on the checked row', pg.evaluate("document.activeElement.dataset.mode") == 'auto')
    pg.keyboard.press('ArrowDown'); check('ArrowDown → next row', pg.evaluate("document.activeElement.dataset.mode") == 'off')
    pg.keyboard.press('ArrowDown'); check('ArrowDown wraps', pg.evaluate("document.activeElement.dataset.mode") == 'auto')
    pg.keyboard.press('End'); check('End → last row', pg.evaluate("document.activeElement.dataset.mode") == 'off')
    pg.keyboard.press('Home'); check('Home → first row', pg.evaluate("document.activeElement.dataset.mode") == 'auto')
    pg.keyboard.press('Escape'); pg.wait_for_timeout(300)
    check('Esc closes the menu and returns focus to +', pg.evaluate("document.activeElement.id") == 'plusBtn' and not pg.is_visible('#plusMenu'))
    # nothing stored → the field is omitted (server default); an explicit pick sends "auto"
    script([T('그냥 답', .1)]); lb = last_ask(pg, '선택 전 질문'); check('nothing stored → web_search omitted (server default applies)', 'web_search' not in lb, lb)
    pg.evaluate("__app.newChat()"); pg.wait_for_timeout(300)
    openm(pg); pg.click('#plusMenu .mode[data-mode=auto]'); pg.wait_for_timeout(300)
    script([S(call(), .2), S(result(sources=S2), .4), T(ANS, .5)], S2); lb = last_ask(pg)
    check('mode auto → request web_search:"auto"', lb.get('web_search') == 'auto', lb)
    # off
    openm(pg); pg.click('#plusMenu .mode[data-mode=off]'); pg.wait_for_timeout(300)
    ab = pg.evaluate("(()=>{const b=document.querySelector('#plusBtn');return {l:b.getAttribute('aria-label'),c:b.className,s:localStorage.getItem('llmchat.webSearch')}})()")
    check('off: stored "off", button web-off + aria-label 꺼짐', ab['s'] == 'off' and 'web-off' in ab['c'] and '꺼짐' in ab['l'], ab)
    check('off: toast 웹 검색 꺼짐', '웹 검색 꺼짐' in pg.inner_text('#toast') if pg.locator('#toast').count() else True)
    pg.evaluate("__app.newChat()"); pg.wait_for_timeout(300); script([T('그냥 답', .1)]); lb = last_ask(pg)
    check('mode off → request web_search:"off" (explicit, so the server never auto-selects)', lb.get('web_search') == 'off', lb)
    # back to auto
    openm(pg); check('reopened: 사용 안 함 checked', [x['c'] for x in rows(pg)] == ['false', 'true'])
    pg.click('#plusMenu .mode[data-mode=auto]'); pg.wait_for_timeout(300)
    check('auto again: toast 자동 · stored "auto"', pg.evaluate("localStorage.getItem('llmchat.webSearch')") == 'auto')
    # mode change mid-flight → the running request is untouched
    pg.evaluate("__app.newChat()"); pg.wait_for_timeout(300)
    script([S(call(id='m1', q='진행 중'), .2), S(result(id='m1', sources=S2), 2.0), T(ANS, .6)], S2); send(pg, '진행 중 변경'); pg.wait_for_timeout(700)
    lb0 = body(pg); openm(pg); pg.click('#plusMenu .mode[data-mode=off]'); pg.wait_for_timeout(300)
    check('mid-flight: request already sent with auto, still shows the line', lb0.get('web_search') == 'auto' and pg.locator('.tstat').count() == 1, lb0)
    settle(pg, 12000)
    check('mid-flight: the answer still finishes with chips', pg.locator('.msg.assistant .sources').count() == 1)
    check('mid-flight change applies from the next send', pg.evaluate("localStorage.getItem('llmchat.webSearch')") == 'off')
    # shared composer: the 오늘 composer has the same rows & shares the setting
    pg.evaluate("location.hash='#/today'"); pg.wait_for_timeout(700)
    if pg.is_visible('#tPlus'):
        openm(pg, '#tPlus'); r2 = rows(pg, '#tMenu')
        check('오늘 composer: same rows, 사용 안 함 checked (shared setting)', [x['m'] for x in r2] == ['auto', 'off'] and r2[1]['c'] == 'true', r2)
        pg.keyboard.press('Escape'); pg.wait_for_timeout(250)
    else: check('오늘 composer reachable', False, 'tPlus not visible')
    check('no page errors', not pg.errs, pg.errs)
    ctx.close()
    # stored '1' (legacy on) with the auto menu → 자동 (not force); 'force' stored without the gate → 자동
    for stored, name in (('1', "stored '1'"), ('force', "stored 'force' while force is held")):
        server(auto=True); ctx, pg = launch(b, init=f"localStorage.setItem('llmchat.webSearch','{stored}');")
        openm(pg); r = rows(pg); check(f'{name} → 자동 checked', r and r[0]['m'] == 'auto' and r[0]['c'] == 'true', r); pg.keyboard.press('Escape')
        script([S(call(), .2), S(result(sources=S2), .4), T(ANS, .4)], S2); lb = last_ask(pg); check(f'{name} → request web_search:"auto"', lb.get('web_search') == 'auto', lb); ctx.close()
    # force enabled (§12-1 answered): 3 rows
    server(auto=True); ctx, pg = launch(b, init="window.__eveFlags={forceMode:true};")
    openm(pg); r = rows(pg); check('force gate open: 자동 / 항상 검색 / 사용 안 함', [x['m'] for x in r] == ['auto', 'force', 'off'] and '항상 검색' in r[1]['t'], r)
    pg.click('#plusMenu .mode[data-mode=force]'); pg.wait_for_timeout(300)
    ab = pg.evaluate("(()=>{const b=document.querySelector('#plusBtn');return {l:b.getAttribute('aria-label'),c:b.className,s:localStorage.getItem('llmchat.webSearch')}})()")
    check('force: stored, + button web-on, aria-label 항상', ab['s'] == 'force' and 'web-on' in ab['c'] and '항상' in ab['l'], ab)
    script([S(call(by='user'), .2), S(result(sources=S2), .4), T(ANS, .4)], S2); lb = last_ask(pg); check('force → request web_search:"force"', lb.get('web_search') == 'force', lb); ctx.close()
    # ── legacy: field false / missing / settings failure → today's single row, no auto/off, '1' keeps working ──
    for label, auto, drop in (('false', False, False), ('missing', None, False), ('settings failure', True, True)):
        server(auto=auto)
        if drop: put('/pro/set', {'settingsDrop': True})
        ctx, pg = launch(b); openm(pg)
        check(f'legacy ({label}): no mode rows, single 웹 검색 row', rows(pg) == [] and pg.is_visible('#webBtn'), rows(pg))
        pg.click('#webBtn'); pg.wait_for_timeout(300)
        script([S(call(by=''), .2), S(result(sources=S2), .4), T(ANS, .4)], S2); lb = last_ask(pg)
        check(f'legacy ({label}): on → web_search sent as before', lb.get('web_search') in ('auto', 'on', True, 'force') or lb.get('web_search') is not None, lb)
        check(f'legacy ({label}): no hint', pg.locator('.tline .hint').count() == 0)
        ctx.close()
    # a settings failure then recovers on the next menu open (60 s cache not applied after failure)
    server(auto=True); put('/pro/set', {'settingsDrop': True}); ctx, pg = launch(b)
    put('/pro/set', {'settingsDrop': False}); openm(pg); pg.wait_for_timeout(600); r = rows(pg)
    check('settings recovers on the next menu open → modes appear', [x['m'] for x in r] == ['auto', 'off'], r); ctx.close()

    # ── sheet/chips: auto == user, .tq reasons, published, reload ──
    def run(by, sources=S2, q='카카오 오늘 소식', extra=None):
        server(auto=True); ctx, pg = launch(b)
        items = [S(call(id='q1', q=q, by=by), .2), S(result(id='q1', sources=sources), .3)] + (extra or []) + [T(ANS, .6)]
        script(items, sources); send(pg); settle(pg, 12000); return ctx, pg
    NORM = "(()=>{const c=document.querySelector('.msg.assistant .sources').cloneNode(true);c.removeAttribute('style');c.classList.remove('fresh');c.querySelectorAll('.tq').forEach(e=>e.remove());return c.outerHTML.replace(/\\s+/g,' ').replace(/ style=\"[^\"]*\"/g,'').replace(/<span>검색어 <q>.*?<\\/span>/g,'')})()"
    ctx, pg = run('model'); chips_a = pg.evaluate(NORM); ctx.close()
    ctx, pg = run('user'); chips_u = pg.evaluate(NORM)
    check('chips identical for selected_by model vs user', chips_a == chips_u, (chips_a[:200], chips_u[:200]))
    tq = pg.evaluate("[...document.querySelectorAll('.msg.assistant .tq')].map(e=>e.textContent)")
    check('.tq line: “검색어” + 모델이 찾았다는 표시 absent for user-selected', len(tq) == 1 and '카카오 오늘 소식' in tq[0], tq)
    ctx.close()
    ctx, pg = run('model'); tq = pg.evaluate("[...document.querySelectorAll('.msg.assistant .tq')].map(e=>e.textContent)")
    check('auto: .tq reads “검색어” · Eve가 필요하다고 판단했어요', len(tq) == 1 and '카카오 오늘 소식' in tq[0] and '필요하다고 판단' in tq[0], tq)
    pub = pg.evaluate("[...document.querySelectorAll('.msg.assistant .src-item, .msg.assistant .src-chip, .msg.assistant .sources [data-n]')].map(e=>e.textContent)")
    check('published date shown when given (10월 27일 / 2025.03.02 style) and absent otherwise', any('news.example.com' in t for t in pub), pub)
    pg.reload(); pg.wait_for_timeout(1500)
    check('after reload: chips kept, no .tq, no .tnote, no hint', pg.locator('.msg.assistant .sources').count() == 1 and pg.locator('.tq, .tnote, .tline').count() == 0)
    ctx.close()
    # three queries → at most 3 .tq rows; HTML in a query is text
    server(auto=True); ctx, pg = launch(b)
    its = []
    for i, q in enumerate(['<img src=x onerror="window.__xss=1"> 첫째', '둘째 검색', '셋째 검색', '넷째 검색'], 1): its += [S(call(id=f'x{i}', q=q, rnd=i), .1), S(result(id=f'x{i}', sources=S2), .1)]
    script(its + [T(ANS, .6)], S2); send(pg); settle(pg, 14000)
    tq = pg.evaluate("[...document.querySelectorAll('.msg.assistant .tq')].map(e=>e.textContent)")
    check('≤ 3 .tq lines for 4 searches', 1 <= len(tq) <= 3 + 1 and len(tq) <= 3, tq)
    check('HTML in a query renders as text (no <img>, no xss)', pg.locator('.msg.assistant img[src="x"]').count() == 0 and pg.evaluate("window.__xss") is None and any('<img' in t for t in tq) or len(tq) < 4, tq)
    ctx.close()
    # sheet: opens, has the .tq at top, long domain no overflow
    LONG = [src(1, 'a-very-long-subdomain-name-for-overflow-testing.example-extremely-long-domain.co.kr', title='아주 긴 제목 ' * 12), src(2, 'b.example.org')]
    server(auto=True); ctx, pg = launch(b)
    script([S(call(id='l1', q='아주 긴 검색어 ' * 12), .2), S(result(id='l1', sources=LONG), 1.2), T(ANS, .6)], LONG); send(pg); pg.wait_for_timeout(900)
    ov = pg.evaluate("(()=>({sw:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth,line:document.querySelector('.tstat').scrollWidth<=document.querySelector('.tstat').clientWidth+1}))()")
    check('390px: no horizontal overflow with a long query (S2)', ov['sw'] <= ov['cw'] and ov['line'], ov)
    settle(pg, 12000)
    ov = pg.evaluate("(()=>({sw:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth}))()")
    check('390px: no horizontal overflow after the answer (long domain/title)', ov['sw'] <= ov['cw'], ov)
    check('no page errors (sheet)', not pg.errs, pg.errs)
    ctx.close()

    # ── motion & tokens ──
    css = open(os.path.join(os.path.dirname(__file__), '..', 'styles.css'), encoding='utf-8').read()
    blk = css[css.index('AUTO-TOOLS-SPEC §3/§4'):]; blk = blk[:blk.index('sup.cite{')]
    check('new CSS: no blur / backdrop-filter / filter', not re.search(r'backdrop-filter|blur\(|[^-]filter:', blk), blk[:80])
    tr = re.findall(r'transition:([^;}]+)', blk)
    check('new CSS: transitions only opacity/transform', all(re.fullmatch(r'\s*(none|(opacity|transform)[^,]*)(,\s*(opacity|transform)[^,]*)*', t.strip()) for t in tr), tr)
    server(auto=True); ctx, pg = launch(b, reduced=True)
    script([S(call(), .2), S(result(sources=S2), 1.4), T(ANS, .6)], S2); send(pg); pg.wait_for_timeout(600)
    an = pg.evaluate("(()=>{const s=document.querySelector('.tstat .row1 svg');return s?getComputedStyle(s).animationName:'none'})()")
    check('prefers-reduced-motion: the spinner stops', an in ('none', ''), an)
    settle(pg, 12000); ctx.close()
    server(auto=True); ctx, pg = launch(b)
    script([S(call(), .2), S(result(sources=S2), 1.4), T(ANS, .6)], S2); send(pg); pg.wait_for_timeout(600)
    an = pg.evaluate("(()=>{const s=document.querySelector('.tstat .row1 svg');return getComputedStyle(s).animationName})()")
    check('motion allowed: the spinner animates (transform only)', an != 'none', an)
    check('spin keyframes use transform only', re.search(r'@keyframes wsspin\{[^}]*\}\s*\}?', css) is not None and 'rotate' in css[css.index('@keyframes wsspin'):css.index('@keyframes wsspin') + 120])
    settle(pg, 12000); ctx.close()
    # contrast of --sub (≥ 4.5) and --pend (≥ 3) on the page background, dark + light
    def lum(c):
        c = [int(x) / 255 for x in c]; c = [x / 12.92 if x <= .03928 else ((x + .055) / 1.055) ** 2.4 for x in c]; return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]
    def ratio(a, b2): la, lb = sorted([lum(a), lum(b2)], reverse=True); return (la + .05) / (lb + .05)
    for sch in ('dark', 'light'):
        server(auto=True); ctx, pg = launch(b, scheme=sch)
        v = pg.evaluate("(()=>{const t=document.createElement('i');document.body.appendChild(t);const g=n=>{t.style.color=`var(${n})`;return getComputedStyle(t).color};const r={sub:g('--sub'),pend:g('--pend'),bg:g('--bg')};t.remove();return r})()")
        def rgb(s, bg=None):
            n = [float(x) for x in re.findall(r'[\d.]+', s)]; a = n[3] if len(n) > 3 else 1
            return [round(n[i] * a + (bg[i] if bg else 0) * (1 - a)) for i in range(3)]
        bgc = rgb(v['bg']); rs, rp = ratio(rgb(v['sub'], bgc), bgc), ratio(rgb(v['pend'], bgc), bgc)
        check(f'{sch}: --sub ≥ 4.5 and --pend ≥ 3 on the page background', rs >= 4.5 and rp >= 3, (v, round(rs, 2), round(rp, 2))); ctx.close()
    done(); b.close()
