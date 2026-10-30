"""AUTO-TOOLS-SPEC §13 / 2.0.0 · the no-web_search contract (no + menu), chips/sheet .tq, layout, motion, tokens."""
from assets_common import source_path
from at_common import *
S2 = [src(1, 'news.example.com', published='2026-10-27'), src(2, 'blog.example.org', published='2025-03-02')]
ANS = '검색 결과에 따르면 빠릅니다[1][2].'
with sync_playwright() as p:
    b = p.chromium.launch()
    # ── 2.0.0 contract: no + menu / web toggle, no web_search field, old keys cleaned, no forceMode code ──
    def body(pg): return db()['state']['lastBody']
    server(auto=True); ctx, pg = launch(b, init="localStorage.setItem('llmchat.webSearch','force');localStorage.setItem('llmchat.autoHintSeen','1');window.__eveFlags={forceMode:true};")
    check('no + button / menu / web row in either composer', pg.evaluate("!document.querySelector('#plusBtn,#plusMenu,#webBtn,#tPlus,#tMenu,#tWeb,.plus,.plus-menu,.mode')"))
    check('old localStorage keys (mode, one-time hint) are removed at start', pg.evaluate("localStorage.getItem('llmchat.webSearch')") is None and pg.evaluate("localStorage.getItem('llmchat.autoHintSeen')") is None)
    check('the composer text starts inside the capsule (no empty gap where + was)', pg.evaluate("getComputedStyle(document.getElementById('input')).paddingLeft") == '14px' and pg.evaluate("document.getElementById('tInput')?getComputedStyle(document.getElementById('tInput')).paddingLeft:'14px'") == '14px')
    for q in ('그냥 질문', '오늘 날씨 알려줘'):
        pg.evaluate("__app.newChat()"); pg.wait_for_timeout(250); send(pg, q); pg.wait_for_timeout(1500)
        check(f'request body for 「{q}」 has no web_search (a forceMode flag is ignored)', 'web_search' not in body(pg), body(pg))
    js = open(source_path(os.path.join(os.path.dirname(__file__), '..', 'app.js')), encoding='utf-8').read(); css0 = open(source_path(os.path.join(os.path.dirname(__file__), '..', 'styles.css')), encoding='utf-8').read()
    check('source: no forceMode / FORCE_MODE / tools_default_mode / web_search request / hint handler', not re.search(r'forceMode|FORCE_MODE|tools_default_mode|web_search:\s|hint-chg|tsHint', js))
    check('source: no .hint / .retry / plus-menu CSS', not re.search(r'\.tline \.hint|\.tnote \.retry|\.plus-menu|\.plus\b', css0))
    ctx.close()
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
    check('.tq line for selected_by:user: just “검색어”, no reason text', len(tq) == 1 and '카카오 오늘 소식' in tq[0] and '판단' not in tq[0], tq)
    ctx.close()
    ctx, pg = run('model'); tq = pg.evaluate("[...document.querySelectorAll('.msg.assistant .tq')].map(e=>e.textContent)")
    check('auto: .tq reads 검색어 “…” · Eve가 필요하다고 판단해 검색했어요', tq == ['검색어 카카오 오늘 소식 · Eve가 필요하다고 판단해 검색했어요'] and pg.evaluate("getComputedStyle(document.querySelector('.msg.assistant .tq q')).quotes") == '"“" "”"', tq)
    pub = pg.evaluate("[...document.querySelectorAll('.msg.assistant .src-item, .msg.assistant .src-chip, .msg.assistant .sources [data-n]')].map(e=>e.textContent)")
    check('published date shown when given (10월 27일 / 2025.03.02 style) and absent otherwise', any('news.example.com' in t for t in pub), pub)
    pg.reload(); pg.wait_for_timeout(1500)
    check('after reload: chips kept, no .tq, no .tnote', pg.locator('.msg.assistant .sources').count() == 1 and pg.locator('.tq, .tnote, .tline').count() == 0)
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
    css = open(source_path(os.path.join(os.path.dirname(__file__), '..', 'styles.css')), encoding='utf-8').read()
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
