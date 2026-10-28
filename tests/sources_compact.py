# 1.5.0 compact sources (2deb88d) → 1.9.0 chips (REFRESH-SPEC §1.5): merged citation capsules, ≤2 26px chips + +N (replaces the 44px row),
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
        pg.goto(B + '/ui/#/'); pg.wait_for_timeout(900); pg.evaluate("__app.newChat()"); pg.wait_for_timeout(500)
        pg.evaluate("document.querySelector('#messages .empty')?.remove()")
        pg.evaluate(JS, [MD, SRC, False]); pg.evaluate(JS, ['하나[1] 둘[2]', SRC[:3], True]); pg.wait_for_timeout(300)
        if not reduce:
            caps = pg.locator('#many .md sup.cite a')
            check('consecutive [1][2] → one capsule 1·2', caps.first.inner_text() == '1·2', caps.first.inner_text())
            check('capsule aria-label lists sources w/o www.', caps.first.get_attribute('aria-label') == '출처 1, site1.example.com; 출처 2, site2.example.com', caps.first.get_attribute('aria-label'))
            cs = pg.evaluate("(()=>{const a=document.querySelector('#many sup.cite a'),r=a.getBoundingClientRect(),s=getComputedStyle(a),b=getComputedStyle(a,'::before');return {h:r.height,bg:s.backgroundColor,c:s.color,num:s.fontVariantNumeric,hw:r.width-2*parseFloat(b.left),hh:r.height-2*parseFloat(b.top)}})()")
            acc = pg.evaluate("(()=>{const e=document.createElement('i');e.style.color='var(--accent)';document.body.appendChild(e);const c=getComputedStyle(e).color;e.remove();return c})()")
            check('capsule visual 16px, var(--accent) on 16% accent mix', cs['h'] == 16 and cs['c'] == acc and 'tabular' in cs['num'] and ('srgb' in cs['bg'] or cs['bg'].startswith('rgba(10, 132, 255, 0.16')), [cs, acc])
            mono = pg.evaluate("(()=>{const m=document.querySelector('#many .fav.mono'),s=getComputedStyle(m);return {fs:s.fontSize,lh:s.lineHeight,ls:s.letterSpacing,clip:m.scrollWidth<=m.clientWidth}})()")
            check('monogram 9px/14px in chip, not clipped', mono['fs'] == '9px' and mono['lh'] == '14px' and mono['ls'] == 'normal' and mono['clip'], mono)
            g = pg.evaluate("""(()=>{const m=document.getElementById('messages');const t=document.createElement('div');t.className='msg assistant';t.id='glue';
              const src=[{n:1,title:'a',url:'https://a.example/'},{n:2,title:'b',url:'https://b.example/'}];
              t.innerHTML='<div class="bubble"><div class="md">'+renderMarkdown('짧은말[1]. 그리고 끝[1][2]」 **굵게**[2]! 아주아주아주아주긴단어입니다요[1]?', src)+'</div></div>';m.appendChild(t);
              const gs=[...t.querySelectorAll('.cite-glue')].map(x=>x.textContent);const ws=getComputedStyle(t.querySelector('.cite-glue')).whiteSpace;
              const html=t.innerHTML;t.remove();return {gs,ws,wj:html.includes('\u2060'),all:t.querySelectorAll('sup.cite').length}})()""")
            check('cite-glue: word + capsule + punctuation', g['gs'][0] == '짧은말1.' and g['gs'][1] == '끝1·2」', g)
            check('cite-glue: tag-ending word glues capsule only', g['gs'][2] == '2!', g)
            check('cite-glue: >12-char word glues capsule + punct only', g['gs'][3] == '1?', g)
            check('cite-glue nowrap, no U+2060', g['ws'] == 'nowrap' and not g['wj'], g)
            check('capsule ::before hit area ≥44', cs['hh'] >= 44 and cs['hw'] >= 16 + 12, cs)
            row = pg.evaluate("""(()=>{const s=document.querySelector('#many .sources'),r=s.querySelector('.src-row'),cs=[...r.querySelectorAll('.sc')],ins=cs.map(c=>c.querySelector('.sc-in')),rb=r.getBoundingClientRect();
              const st=getComputedStyle(ins[0]);return {sec:s.getBoundingClientRect().height,rowH:rb.height,n:cs.length,txt:cs.map(c=>(c.querySelector('.sc-n')||c).textContent.trim()),h:ins.map(x=>x.getBoundingClientRect().height),tops:ins.map(x=>Math.round(x.getBoundingClientRect().top)),
              hit:cs.map(c=>[c.getBoundingClientRect().width,c.getBoundingClientRect().height]),fav:[...r.querySelectorAll('.sc .fav')].map(f=>f.getBoundingClientRect().width),rad:st.borderRadius,bg:st.backgroundColor,sh:st.boxShadow,td:st.transitionDuration,ft:st.fontSize+'/'+st.fontWeight,
              exp:cs.map(c=>c.getAttribute('aria-expanded')),ctl:cs.every(c=>!!document.getElementById(c.getAttribute('aria-controls'))),labs:cs.map(c=>c.getAttribute('aria-label')),oneLine:r.scrollWidth<=r.clientWidth,
              imgs:[...r.querySelectorAll('.fav img')].map(i=>i.src.slice(0,10)),mono:[...r.querySelectorAll('.fav.mono')].map(x=>x.textContent),listHidden:s.querySelector('.src-list').hidden,old:!!s.querySelector('.src-n,.src-chev,.favs')}})()""")
            l1 = pg.evaluate("(()=>{const e=document.createElement('i');e.style.background='var(--layer-1)';document.body.appendChild(e);const c=getComputedStyle(e).backgroundColor;e.remove();return c})()")
            check('collapsed: chips only (no 44px row text/chevron), list hidden', row['n'] == 3 and row['listHidden'] and not row['old'], row)
            check('≤2 domain chips + "+N" (N = sources w/o a chip)', row['txt'][:2] == ['site1.example.com', 'site2.example.com'] and row['txt'][2] == '+4', row['txt'])
            check('chip capsule 26px tall, radius 13, 14px favicon', all(h == 26 for h in row['h']) and row['rad'] == '13px' and set(row['fav']) == {14}, row)
            check('chip tokens: layer-1 bg, .5px hair inset, caption 12/500, no transitions', row['bg'] == l1 and '0.5px' in row['sh'] and row['ft'] == '12px/500' and row['td'] == '0s', [row['bg'], l1, row['sh'], row['ft'], row['td']])
            check('one line: same top, row ≤ one 44px touch row, no overflow', len(set(row['tops'])) == 1 and row['rowH'] == 44 and row['sec'] == 44 and row['oneLine'], row)
            check('touch targets ≥44 (chip, +N)', all(h == 44 for _, h in row['hit']) and row['hit'][2][0] >= 44, row['hit'])
            check('aria: expanded=false + controls list, labels', row['exp'] == ['false'] * 3 and row['ctl'] and row['labs'] == ['출처 site1.example.com', '출처 site2.example.com', '출처 4개 더 보기'], row)
            check('server data: favicon used; external URL → monogram', row['imgs'] == ['data:image'] and row['mono'] == ['S'], row)
            check('no favicon.ico / external image requests', not any('favicon' in u or 'evil' in u for u in reqs), [u for u in reqs if 'favicon' in u or 'evil' in u])
            fw = pg.evaluate("[...document.querySelectorAll('#few .sc')].map(c=>(c.querySelector('.sc-n')||c).textContent.trim())")
            check('few (3 sources, 3 domains): 2 chips + +1, no 모두 보기', fw == ['site1.example.com', 'site2.example.com', '+1'] and pg.locator('#few .src-all').count() == 0, fw)
        # tap capsule → expand, scroll, highlight
        pg.locator('#many .md sup.cite a').nth(1).click(); pg.wait_for_timeout(120)
        st = pg.evaluate("(()=>{const s=document.querySelector('#many .sources'),it=s.querySelector('.src-item[data-n=\"3\"]');return {exp:s.querySelector('.sc').getAttribute('aria-expanded'),hidden:s.querySelector('.src-list').hidden,hl:it.classList.contains('hl'),items:s.querySelectorAll('.src-list .src-item').length,all:!!s.querySelector('.src-all')}})()")
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
            check('motion var(--d-2) var(--ease-standard), opacity/transform only', '0.2s' in tr[0] and '0.32, 0.72, 0, 1' in tr[1] and 'height' not in tr[2] and 'width' not in tr[2], tr)
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
        pg.click('#srcSheet .src-close'); pg.wait_for_timeout(60)
        check(tag + 'sheet closes via animateOut (closing state)', pg.evaluate("document.getElementById('srcSheet').classList.contains('closing')"))
        pg.wait_for_timeout(500); check(tag + 'sheet closed', not pg.evaluate("document.getElementById('srcSheet').open"))
        pg.click('#many .sc'); pg.wait_for_timeout(50)
        if not reduce: check('collapse waits for transitionend (still visible mid-fade)', not pg.evaluate("document.querySelector('#many .src-list').hidden"))
        pg.wait_for_timeout(400)
        check(tag + 'row toggle collapses (aria-expanded=false, hidden)', pg.evaluate("(()=>{const s=document.querySelector('#many .sources');return s.querySelector('.sc').getAttribute('aria-expanded')==='false'&&s.querySelector('.src-list').hidden})()"))
        pg.click('#many .sc'); pg.wait_for_timeout(400)
        pg.click('#many .src-all'); pg.wait_for_timeout(300)
        pg.evaluate("document.getElementById('srcSheet').close()"); pg.click('#many .sc'); pg.wait_for_timeout(300); pg.evaluate("document.getElementById('messages').scrollTop=0"); pg.wait_for_timeout(100)
        pg.click('#many .sc', force=True); pg.wait_for_timeout(600)
        if not reduce:
            pg.evaluate("document.getElementById('messages').scrollTop=0"); pg.wait_for_timeout(100)
            pg.evaluate("document.querySelector('#few .sc').click()"); pg.wait_for_timeout(700)
            v = pg.evaluate("(()=>{const r=document.querySelector('#few .src-list').getBoundingClientRect(),m=document.getElementById('messages').getBoundingClientRect();return [r.bottom,m.bottom,document.getElementById('messages').scrollTop]})()")
            check('expanding on last message scrolls list into view (nearest)', v[0] <= v[1] + 1 and v[2] > 0, v)
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
    pg.goto(B + '/ui/#/'); pg.wait_for_timeout(900); pg.evaluate("__app.newChat()"); pg.wait_for_timeout(400)
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
    b.close(); put('/csp/off')  # restore mock state (csrf_all expects CSP off)
print(f"{sum(R)}/{len(R)} passed" if all(R) else f"FAILED {R.count(False)}/{len(R)}")
