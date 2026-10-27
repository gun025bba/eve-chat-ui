# 1.5.0 compact sources (design 2deb88d SOURCES-SPEC stage 2): merged citation capsules, 44px collapsed row,
# inline expand/highlight, >6 → 5 + 모두 보기 sheet, server-only favicons, chips, motion, streaming fade-in, 390px no h-scroll
from playwright.sync_api import sync_playwright
import os, json, urllib.request
B = 'http://127.0.0.1:' + os.environ.get('EVE_PORT', '8765')
R = []
def check(n, ok, x=''): R.append(bool(ok)); print('PASS' if ok else 'FAIL', n, '' if ok else x)
def put(p): urllib.request.urlopen(urllib.request.Request(B + p, method='PUT'))
LONG = '아주 긴 제목 ' * 20
SRC = [{'n': i, 'title': (LONG if i == 1 else f'출처 제목 {i}'), 'url': f'https://www.site{i % 4}.example.com/very/long/path/{i}/' + 'x' * 120,
        'domain': f'www.site{i % 4}.example.com'} for i in range(1, 9)]
SRC[0]['favicon'] = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
SRC[1]['favicon'] = 'https://evil.example/favicon.ico'
MD = '첫 문장[1][2]. 둘째[3]. 일곱[7]. 링크 ' + 'https://example.com/' + 'y' * 200 + '\n\n| ' + ' | '.join(['wide-col'] * 30) + ' |\n|' + '---|' * 30
JS = """([md, src, few]) => { const m = document.getElementById('messages'); const d = document.createElement('div'); d.className = 'msg assistant'; d.id = few ? 'few' : 'many';
  d.innerHTML = '<div class="bubble"><div class="md">' + renderMarkdown(md, src) + '</div>' + renderSources(src) + '</div>'; m.appendChild(d); return true }"""
with sync_playwright() as p:
    b = p.chromium.launch(); put('/auth/on'); put('/reset'); put('/csp/on')
    for reduce in [False, True]:
        tag = '[reduced] ' if reduce else ''
        ctx = b.new_context(viewport={'width': 390, 'height': 844}, has_touch=True, is_mobile=True, reduced_motion='reduce' if reduce else 'no-preference')
        pg = ctx.new_page(); errs = []; reqs = []
        pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('request', lambda r: reqs.append(r.url))
        pg.goto(B + '/ui/#/'); pg.wait_for_timeout(900); pg.click('#newChat'); pg.wait_for_timeout(500)
        pg.evaluate("document.querySelector('#messages .empty')?.remove()")
        pg.evaluate(JS, [MD, SRC, False]); pg.evaluate(JS, ['하나[1] 둘[2]', SRC[:3], True]); pg.wait_for_timeout(300)
        if not reduce:
            caps = pg.locator('#many .md sup.cite a')
            check('consecutive [1][2] → one capsule 1·2', caps.first.inner_text() == '1·2', caps.first.inner_text())
            check('capsule aria-label lists sources w/o www.', caps.first.get_attribute('aria-label') == '출처 1, site1.example.com; 출처 2, site2.example.com', caps.first.get_attribute('aria-label'))
            cs = pg.evaluate("(()=>{const a=document.querySelector('#many sup.cite a'),r=a.getBoundingClientRect(),s=getComputedStyle(a),b=getComputedStyle(a,'::before');return {h:r.height,bg:s.backgroundColor,c:s.color,num:s.fontVariantNumeric,hw:r.width-2*parseFloat(b.left),hh:r.height-2*parseFloat(b.top)}})()")
            check('capsule visual 16px, blue on tinted', cs['h'] == 16 and cs['c'] == 'rgb(10, 132, 255)' and 'tabular' in cs['num'], cs)
            check('capsule ::before hit area ≥44', cs['hh'] >= 44 and cs['hw'] >= 16 + 12, cs)
            row = pg.evaluate("(()=>{const s=document.querySelector('#many .sources'),r=s.querySelector('.src-row'),rr=r.getBoundingClientRect();return {sec:s.getBoundingClientRect().height,h:rr.height,txt:r.textContent.trim(),exp:r.getAttribute('aria-expanded'),ctl:!!document.getElementById(r.getAttribute('aria-controls')),favs:r.querySelectorAll('.fav').length,imgs:[...r.querySelectorAll('.fav img')].map(i=>i.src.slice(0,10)),mono:[...r.querySelectorAll('.fav.mono')].map(x=>x.textContent),listHidden:s.querySelector('.src-list').hidden}})()")
            check('collapsed: one 44px row, list hidden', row['h'] == 44 and row['sec'] == 44 and row['listHidden'], row)
            check('row text 출처 8개 ›', row['txt'].endswith('출처 8개›'), row['txt'])
            check('row aria-expanded=false + aria-controls', row['exp'] == 'false' and row['ctl'], row)
            check('≤3 favicons, unique domains', row['favs'] == 3, row)
            check('server data: favicon used; external URL → monogram', row['imgs'] == ['data:image'] and row['mono'] == ['S', 'S'], row)
            check('no favicon.ico / external image requests', not any('favicon' in u or 'evil' in u for u in reqs), [u for u in reqs if 'favicon' in u or 'evil' in u])
            check('few: 출처 3개 count, no 모두 보기', pg.locator('#few .src-n').inner_text() == '출처 3개' and pg.locator('#few .src-all').count() == 0)
        # tap capsule → expand, scroll, highlight
        pg.locator('#many .md sup.cite a').nth(1).click(); pg.wait_for_timeout(120)
        st = pg.evaluate("(()=>{const s=document.querySelector('#many .sources'),it=s.querySelector('.src-item[data-n=\"3\"]');return {exp:s.querySelector('.src-row').getAttribute('aria-expanded'),hidden:s.querySelector('.src-list').hidden,hl:it.classList.contains('hl'),items:s.querySelectorAll('.src-list .src-item').length,all:!!s.querySelector('.src-all')}})()")
        check(tag + 'capsule tap expands + highlights item 3', st['exp'] == 'true' and not st['hidden'] and st['hl'], st)
        check(tag + 'URL unchanged (no navigation)', '#/' in pg.url and len(pg.context.pages) == 1, pg.url)
        check(tag + '>6 → 5 items + 모두 보기', st['items'] == 5 and st['all'], st)
        pg.wait_for_timeout(700)
        check(tag + 'highlight clears after 0.6s', not pg.evaluate("document.querySelector('#many .src-item[data-n=\"3\"]').classList.contains('hl')"))
        it = pg.evaluate("""(()=>{const a=document.querySelector('#many .src-item[data-n="1"] a'),s=getComputedStyle(a),t=getComputedStyle(a.querySelector('.st')),d=getComputedStyle(a.querySelector('.sd'));
          return {cols:s.gridTemplateColumns,minh:a.getBoundingClientRect().height,clamp:t.webkitLineClamp,th:a.querySelector('.st').getBoundingClientRect().height,dov:d.textOverflow,dws:d.whiteSpace,dom:a.querySelector('.sd').textContent,lab:a.getAttribute('aria-label'),tgt:a.target,rel:a.rel,ml:s.marginLeft,role:a.closest('ol').getAttribute('role')}})()""")
        if not reduce:
            check('item grid 20px + minmax(0,1fr)', it['cols'].startswith('20px '), it)
            check('title clamped to 2 lines (≤40px)', it['clamp'] == '2' and it['th'] <= 40.5, it)
            check('domain ellipsis, www. stripped', it['dov'] == 'ellipsis' and it['dws'] == 'nowrap' and it['dom'] == 'site1.example.com', it)
            check('item a11y label + new tab + list role', it['lab'].startswith('1. ') and it['lab'].endswith('site1.example.com, 새 창에서 열림') and it['tgt'] == '_blank' and it['rel'] == 'noopener noreferrer' and it['role'] == 'list', it)
            check('no negative margins', it['ml'] == '0px', it)
            tr = pg.evaluate("(()=>{const l=document.querySelector('#many .src-list'),s=getComputedStyle(l);return [s.transitionDuration,s.transitionTimingFunction,s.transitionProperty]})()")
            check('motion 280ms cubic-bezier(.32,.72,0,1), opacity/transform only', '0.28s' in tr[0] and '0.32, 0.72, 0, 1' in tr[1] and 'height' not in tr[2] and 'width' not in tr[2], tr)
        else:
            tr = pg.evaluate("(()=>{const l=document.querySelector('#many .src-list'),s=getComputedStyle(l),i=getComputedStyle(l.querySelector('.src-item'));return [s.transitionDuration,i.animationName,s.opacity]})()")
            check(tag + 'instant (no slide/stagger, already opaque)', tr[1] == 'none' and tr[2] == '1', tr)
        # 7th source via capsule → sheet
        pg.locator('#many .md sup.cite a').nth(2).click(); pg.wait_for_timeout(400)
        sh = pg.evaluate("(()=>{const d=document.getElementById('srcSheet');return d&&{open:d.open,items:d.querySelectorAll('.src-item').length,hl:!!d.querySelector('.src-item[data-n=\"7\"].hl'),grab:!!d.querySelector('.grabber'),chips:[...d.querySelectorAll('.src-chip')].map(c=>{const s=getComputedStyle(c);return [c.textContent,s.maxWidth,s.textOverflow,s.whiteSpace]}),wrap:getComputedStyle(d.querySelector('.src-chips')).flexWrap,sw:d.scrollWidth<=d.clientWidth}})()")
        check(tag + 'capsule for hidden item opens sheet + highlights 7', sh and sh['open'] and sh['items'] == 8 and sh['hl'] and sh['grab'], sh)
        if sh and not reduce:
            check('chips: domain only, 160px ellipsis, wrap', all(c[1] == '160px' and c[2] == 'ellipsis' and c[3] == 'nowrap' and not c[0].startswith('www.') for c in sh['chips']) and sh['wrap'] == 'wrap' and len(sh['chips']) == 4, sh)
            check('sheet no horizontal scroll', sh['sw'], sh)
        pg.evaluate("document.getElementById('srcSheet').close()"); pg.wait_for_timeout(200)
        pg.click('#many .src-row'); pg.wait_for_timeout(400)
        check(tag + 'row toggle collapses (aria-expanded=false, hidden)', pg.evaluate("(()=>{const s=document.querySelector('#many .sources');return s.querySelector('.src-row').getAttribute('aria-expanded')==='false'&&s.querySelector('.src-list').hidden})()"))
        pg.click('#many .src-row'); pg.wait_for_timeout(400)
        pg.click('#many .src-all'); pg.wait_for_timeout(300)
        check(tag + '모두 보기 opens sheet', pg.evaluate("document.getElementById('srcSheet').open")); pg.evaluate("document.getElementById('srcSheet').close()")
        for w in [390, 375, 320]:
            pg.set_viewport_size({'width': w, 'height': 844}); pg.wait_for_timeout(200)
            sw = pg.evaluate("(()=>{const m=document.getElementById('messages');return [m.scrollWidth,m.clientWidth,document.documentElement.scrollWidth]})()")
            check(f'{tag}{w}px: no horizontal scroll (expanded)', sw[0] <= sw[1] and sw[2] <= w, sw)
        check(tag + 'no page errors', not errs, errs); ctx.close()
    # streaming: capsules only while streaming, row fades in after done
    put('/webdisabled/off')
    ctx = b.new_context(viewport={'width': 390, 'height': 844}); pg = ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.add_init_script("localStorage.setItem('llmchat.webSearch','1');localStorage.setItem('eve.mem.introSeen','1')")
    pg.goto(B + '/ui/#/'); pg.wait_for_timeout(900); pg.click('#newChat'); pg.wait_for_timeout(400)
    pg.fill('#input', 'ws 질문'); pg.click('#sendBtn')
    seen = {'cite_no_row': False}
    for _ in range(200):
        pg.wait_for_timeout(50)
        r = pg.evaluate("(()=>{const b=[...document.querySelectorAll('.msg.assistant .bubble')].pop();return b?{live:!!b.querySelector('.md.cursor'),cite:!!b.querySelector('sup.cite'),row:!!b.querySelector('.sources'),fresh:!!b.querySelector('.sources.fresh'),anim:b.querySelector('.sources')?getComputedStyle(b.querySelector('.sources')).animationName+' '+getComputedStyle(b.querySelector('.sources')).animationDuration:''}:null})()")
        if r and r['live'] and r['row']: check('streaming: no sources row while live', False, r); break
        if r and r['live'] and r['cite']: seen['cite_no_row'] = True
        if r and not r['live'] and r['row']: seen['first'] = r; break
    pg.wait_for_timeout(2500)
    fin0 = seen.get('first') or {}
    fin = pg.evaluate("(()=>{const s=[...document.querySelectorAll('.msg.assistant .sources')].pop();return s&&{fresh:s.classList.contains('fresh'),anim:getComputedStyle(s).animationName,dur:getComputedStyle(s).animationDuration}})()")
    check('streaming: capsules shown before row', seen['cite_no_row'], seen)
    check('done: row appears with 120ms fade', fin0.get('fresh') and fin0.get('anim') == 'srcFade 0.12s', fin0)
    check('done: row still present after persist', bool(fin), fin)
    check('stream: no page errors', not errs, errs)
    b.close()
print(f"{sum(R)}/{len(R)} passed" if all(R) else f"FAILED {R.count(False)}/{len(R)}")
