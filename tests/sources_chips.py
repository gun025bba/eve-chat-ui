# 1.9.0 source chips: chip/+N behaviour, counts, one-line guard at narrow widths, dark+light, contrast ≥4.5:1, focus ring not clipped, no transitions
import os, re
from playwright.sync_api import sync_playwright
B = 'http://127.0.0.1:' + os.environ.get('EVE_PORT', '8765')
R = []
def check(n, ok, x=''): R.append(bool(ok)); print('PASS' if ok else 'FAIL', n, '' if ok else x)
def S(specs): return [{'n': i, 'title': f'제목 {i}', 'url': f'https://{d}/p/{i}', 'domain': d} for i, d in enumerate(specs, 1)]
CASES = {
  'one': S(['a.example.com']),
  'two': S(['a.example.com', 'b.example.com']),
  'dup': S(['a.example.com', 'a.example.com', 'b.example.com', 'b.example.com']),   # 4 sources, 2 domains → no +N
  'five': S(['a.example.com', 'b.example.com', 'c.example.com', 'd.example.com', 'a.example.com']),   # c, d → +3 (incl. 5th? a has chip → c,d = 2)
  'long': S(['www.an-extremely-long-subdomain-name.really-long-registered-domain-example.co.kr', 'another.very-long-hostname-for-the-second-chip.example.org', 'c.example.com', 'd.example.com']),
  'nine': S([f'h{i}.example.com' for i in range(1, 10)]),
}
JS = """([id, src]) => { const m = document.getElementById('messages'); const d = document.createElement('div'); d.className = 'msg assistant'; d.id = id;
  d.innerHTML = '<div class="bubble"><div class="md">' + renderMarkdown('답변[1]', src) + '</div>' + renderSources(src) + '</div>'; m.appendChild(d); return true }"""
with sync_playwright() as p:
    b = p.chromium.launch()
    for scheme in ['dark', 'light']:
        ctx = b.new_context(viewport={'width': 390, 'height': 844}, has_touch=True, is_mobile=True, color_scheme=scheme); pg = ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.add_init_script("localStorage.setItem('eve.mem.introSeen','1')")
        pg.goto(B + '/ui/#/'); pg.wait_for_timeout(900); pg.click('#newChat'); pg.wait_for_timeout(400)
        pg.evaluate("document.querySelector('#messages .empty')?.remove()")
        for k, v in CASES.items(): pg.evaluate(JS, [k, v])
        pg.wait_for_timeout(200)
        txt = lambda k: pg.evaluate(f"[...document.querySelectorAll('#{k} .sc')].map(c=>(c.querySelector('.sc-n')||c).textContent.trim())")
        t = scheme + ': '
        check(t + '1 source → 1 chip, no +N', txt('one') == ['a.example.com'], txt('one'))
        check(t + '2 distinct sources → 2 chips, no +N', txt('two') == ['a.example.com', 'b.example.com'], txt('two'))
        check(t + '4 sources / 2 domains → 2 chips, no +N', txt('dup') == ['a.example.com', 'b.example.com'], txt('dup'))
        check(t + '5 sources → 2 chips + "+2" (c, d)', txt('five') == ['a.example.com', 'b.example.com', '+2'], txt('five'))
        check(t + '9 sources → +7', txt('nine')[-1] == '+7' and len(txt('nine')) == 3, txt('nine'))
        # page-level: colours come from tokens in both schemes
        c = pg.evaluate("(()=>{const i=document.querySelector('#five .sc-in'),s=getComputedStyle(i),t=document.createElement('i');t.style.background='var(--layer-1)';t.style.color='var(--label)';document.body.appendChild(t);const r={bg:s.backgroundColor,c:s.color,tb:getComputedStyle(t).backgroundColor,tc:getComputedStyle(t).color};t.remove();return r})()")
        check(t + 'chip bg = --layer-1, text = --label (not --label-2)', c['bg'] == c['tb'] and c['c'] == c['tc'], c)
        def lum(rgb): 
            f = lambda v: (v / 255 / 12.92) if v / 255 <= .03928 else ((v / 255 + .055) / 1.055) ** 2.4
            return .2126 * f(rgb[0]) + .7152 * f(rgb[1]) + .0722 * f(rgb[2])
        def ratio(a, b): x, y = sorted([lum(a), lum(b)], reverse=True); return (x + .05) / (y + .05)
        num = lambda sx: [float(v) for v in re.findall(r'[\d.]+', sx)[:3]]
        cc = pg.evaluate("(()=>{const o={};for(const [k,sel] of [['chip','#five .sc:not(.sc-more) .sc-in'],['more','#five .sc-more .sc-in']]){const s=getComputedStyle(document.querySelector(sel));o[k]=[s.color,s.backgroundColor]}document.querySelector('#five .sc').setAttribute('aria-expanded','true');o.open=[getComputedStyle(document.querySelector('#five .sc-in')).color,getComputedStyle(document.querySelector('#five .sc-in')).backgroundColor];document.querySelector('#five .sc').setAttribute('aria-expanded','false');return o})()")
        check(t + 'chip, +N and expanded chip text ≥ 4.5:1', all(ratio(num(a), num(b)) >= 4.5 for a, b in cc.values()), {k: round(ratio(num(a), num(b)), 2) for k, (a, b) in cc.items()})
        if scheme == 'light': check('light: contrast on #F2F2F7 chip bg', cc['chip'][1] == 'rgb(242, 242, 247)' and ratio(num(cc['chip'][0]), [242, 242, 247]) >= 4.5, cc)
        tr = pg.evaluate("[...document.querySelectorAll('#five .sc, #five .sc-in')].map(e=>getComputedStyle(e).transitionDuration)")
        check(t + 'no transitions on chips (pressed state is instant)', all(d == '0s' for d in tr), tr)
        # keyboard focus ring: 2px accent, 1px offset, fully inside the clipping row (first/last chip included)
        pg.keyboard.press('Tab')  # make sure keyboard modality, then focus chips explicitly
        fr = []
        for idx in range(3):
            pg.evaluate("i => document.querySelectorAll('#five .sc')[i].focus({focusVisible: true})", idx)
            fr.append(pg.evaluate("(()=>{const f=document.activeElement,i=f.querySelector('.sc-in'),s=getComputedStyle(i),r=i.getBoundingClientRect(),row=f.closest('.src-row').getBoundingClientRect(),o=3;const a=document.createElement('i');a.style.color='var(--accent)';document.body.appendChild(a);const ac=getComputedStyle(a).color;a.remove();return {style:s.outlineStyle,w:s.outlineWidth,off:s.outlineOffset,col:s.outlineColor===ac,inside:r.left-o>=row.left&&r.right+o<=row.right&&r.top-o>=row.top&&r.bottom+o<=row.bottom,own:getComputedStyle(f).outlineStyle}})()"))
        check(t + 'focus-visible: 2px solid accent, 1px offset, on the capsule (button itself has none)', all(x['style'] == 'solid' and x['w'] == '2px' and x['off'] == '1px' and x['col'] and x['own'] == 'none' for x in fr), fr)
        check(t + 'focus ring not clipped by the row (first, second, +N)', all(x['inside'] for x in fr), fr)
        pg.evaluate("document.activeElement.blur()")
        no = pg.evaluate("(()=>{const i=document.querySelector('#five .sc-in');return getComputedStyle(i).outlineStyle})()")
        check(t + 'no ring when not focused', no == 'none', no)
        # tap a chip: list opens, every chip of that answer reflects expanded; tap again closes
        pg.locator('#five .sc').first.click(); pg.wait_for_timeout(450)
        st = pg.evaluate("(()=>{const s=document.querySelector('#five .sources');return {exp:[...s.querySelectorAll('.sc')].map(c=>c.getAttribute('aria-expanded')),hidden:s.querySelector('.src-list').hidden,items:s.querySelectorAll('.src-item').length,open:s.classList.contains('open'),bg:getComputedStyle(s.querySelector('.sc-in')).backgroundColor}})()")
        check(t + 'chip tap opens the v1 list (all 5 items), chips stay', st['exp'] == ['true'] * 3 and not st['hidden'] and st['items'] == 5 and st['open'], st)
        pg.locator('#five .sc').first.click(); pg.wait_for_timeout(450)
        check(t + 'chip tap again collapses', pg.evaluate("document.querySelector('#five .src-list').hidden") and pg.evaluate("[...document.querySelectorAll('#five .sc')].every(c=>c.getAttribute('aria-expanded')==='false')"))
        pg.locator('#five .sc-more').click(); pg.wait_for_timeout(450)
        check(t + '+N tap opens the list too', not pg.evaluate("document.querySelector('#five .src-list').hidden") and pg.evaluate("document.querySelector('#five .sc-more').getAttribute('aria-expanded')") == 'true')
        pg.locator('#five .sc').nth(1).click(); pg.wait_for_timeout(450)
        check(t + 'any chip toggles (2nd chip collapses)', pg.evaluate("document.querySelector('#five .src-list').hidden"))
        pg.locator('#nine .sc-more').click(); pg.wait_for_timeout(450)
        check(t + '9 sources: list = 5 + 모두 보기 (v1 kept)', pg.evaluate("document.querySelectorAll('#nine .src-item').length") == 5 and pg.locator('#nine .src-all').count() == 1)
        pg.click('#nine .src-all'); pg.wait_for_timeout(400)
        check(t + '모두 보기 sheet lists all 9', pg.evaluate("document.querySelectorAll('#srcSheet .src-item').length") == 9)
        pg.evaluate("document.getElementById('srcSheet').close()")
        # one-line + overflow guard at narrow widths, with very long domains
        for w in [390, 375, 320]:
            pg.set_viewport_size({'width': w, 'height': 844}); pg.wait_for_timeout(200)
            g = pg.evaluate("""(()=>{const o={};for(const k of ['one','two','dup','five','long','nine']){const r=document.querySelector('#'+k+' .src-row'),ins=[...r.querySelectorAll('.sc-in')].map(x=>x.getBoundingClientRect());
              o[k]={tops:new Set(ins.map(x=>Math.round(x.top))).size,right:Math.max(...ins.map(x=>x.right)),rw:r.getBoundingClientRect().right,h:r.getBoundingClientRect().height,clip:r.scrollWidth<=r.clientWidth,ell:[...r.querySelectorAll('.sc-n')].map(n=>n.scrollWidth>n.clientWidth)}}
              const m=document.getElementById('messages');o.m=[m.scrollWidth,m.clientWidth,document.documentElement.scrollWidth];return o})()""")
            ok = g['m'][0] <= g['m'][1] and g['m'][2] <= w and all(g[k]['tops'] == 1 and round(g[k]['h']) == 44 and g[k]['clip'] and g[k]['right'] <= w - 16 + 1 for k in CASES)
            check(f'{t}{w}px: chips on one line, inside the 16px margin, no horizontal scroll', ok, g)
            if w == 320: check(t + '320px: long domains ellipsize', any(g['long']['ell']), g['long'])
        pg.set_viewport_size({'width': 390, 'height': 844})
        css = pg.evaluate("(()=>{const bad=[];for(const sh of document.styleSheets)for(const r of sh.cssRules){const t=r.cssText||'';if(/transition:\\s*all\\b|transition-property:\\s*all\\b/.test(t)&&/\\.sc|src-row|src-list/.test(t))bad.push(t.slice(0,80))}return bad})()")
        check(t + 'no transition:all on chip/list rules', not css, css)
        check(t + 'no page errors', not errs, errs); ctx.close()
    b.close()
print(f"{sum(R)}/{len(R)} passed" if all(R) else f"FAILED {R.count(False)}/{len(R)}"); raise SystemExit(0 if all(R) else 1)
