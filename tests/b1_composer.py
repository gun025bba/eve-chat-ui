# 1.10.0 B1 하루 (DIRECTION-B-SPEC §9.1): one-line composer — send/stop, multi-line growth, placeholder. 2.0.0: no + / web-search control (the request has no web_search field)
from playwright.sync_api import sync_playwright
from b1_common import *
R = []; errs = []
def check(n, ok, x=''): R.append(bool(ok)); print('PASS' if ok else 'FAIL', n, '' if ok else x)
reset()
with sync_playwright() as p:
    b = p.chromium.launch()
    for scheme in ['dark', 'light']:
        ctx = new_ctx(b, scheme=scheme); pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto(B + '/ui/#/'); pg.reload(); pg.wait_for_timeout(1200)
        if pg.evaluate("document.getElementById('app').dataset.route") != 'chat': pg.evaluate("__app.newChat()"); pg.wait_for_timeout(500)
        ev = pg.evaluate; t = scheme + ': '
        check(t + 'placeholder "지금 일을 남겨요", 17px input, --label-3 placeholder', pg.get_attribute('#input', 'placeholder') == '지금 일을 남겨요' and ev("getComputedStyle(document.getElementById('input')).fontSize") == '17px')
        f = ev("""(()=>{const f=document.querySelector('#composer .field'),r=f.getBoundingClientRect(),s=getComputedStyle(f),c=document.getElementById('composer').getBoundingClientRect(),sb=document.getElementById('sendBtn');
          return {h:r.height,rad:s.borderTopLeftRadius,l:r.left,rr:innerWidth-r.right,pb:innerHeight-r.bottom,np:!document.getElementById('plusBtn')&&!document.getElementById('plusMenu'),il:parseFloat(getComputedStyle(document.getElementById('input')).paddingLeft),so:getComputedStyle(sb).opacity,sp:getComputedStyle(sb).pointerEvents,bf:s.backdropFilter,mat:s.backgroundColor,sh:s.boxShadow}})()""")
        check(t + 'capsule: 44px, radius 22, 12px side margins, ≥10px from the bottom', abs(f['h'] - 44) < 1 and f['rad'] == '22px' and abs(f['l'] - 12) < 1 and abs(f['rr'] - 12) < 1 and f['pb'] >= 10, f)
        check(t + 'no + / web-search control; input padding-left is 14px; no blur (opaque material)', f['np'] and f['il'] == 14 and f['bf'] in ('none', '') and f['mat'].startswith('rgb('), f)
        check(t + 'send is hidden and not tappable while empty', f['so'] == '0' and f['sp'] == 'none', f)
        pg.fill('#input', '안녕'); pg.wait_for_timeout(300)
        s = ev("(()=>{const b=document.getElementById('sendBtn'),r=b.getBoundingClientRect(),c=getComputedStyle(b);return {o:c.opacity,pe:c.pointerEvents,w:r.width,h:r.height,bg:c.backgroundColor,fh:document.querySelector('#composer .field').getBoundingClientRect().height}})()")
        check(t + 'send appears on input: 36px accent circle', s['o'] == '1' and s['pe'] != 'none' and s['w'] == 36 and s['h'] == 36, s)
        pg.fill('#input', 'a\nb\nc'); pg.wait_for_timeout(200)
        h5 = ev("document.querySelector('#composer .field').getBoundingClientRect().height"); rad = ev("getComputedStyle(document.querySelector('#composer .field')).borderTopLeftRadius")
        pg.fill('#input', '\n'.join(str(i) for i in range(30))); pg.wait_for_timeout(200)
        h30 = ev("document.querySelector('#composer .field').getBoundingClientRect().height")
        check(t + 'multi-line grows up (radius stays 22), capped at 120px', 44 < h5 < 120 and rad == '22px' and h30 <= 120.5, [h5, rad, h30])
        # buttons stay at the bottom edge while the field grows
        pb = ev("(()=>{const f=document.querySelector('#composer .field').getBoundingClientRect(),p=document.getElementById('sendBtn').getBoundingClientRect();return Math.abs((f.bottom-p.bottom)-4)<1.5})()")
        check(t + 'send stays anchored to the bottom while it grows', pb)
        pg.fill('#input', '')
        # send → stop
        pg.fill('#input', 'slow stop test'); pg.click('#sendBtn'); pg.wait_for_timeout(1200)
        st = ev("(()=>{const b=document.getElementById('sendBtn'),c=getComputedStyle(b);return {stop:b.classList.contains('stop'),op:c.opacity,pe:c.pointerEvents,dis:b.disabled,lab:b.getAttribute('aria-label')}})()")
        check(t + 'while generating the send circle is a visible, tappable stop', st['stop'] and st['op'] == '1' and st['pe'] != 'none' and not st['dis'] and st['lab'] == '생성 중지', st)
        pg.click('#sendBtn'); pg.wait_for_timeout(900)
        check(t + 'stop returns to hidden send (empty input)', ev("(()=>{const b=document.getElementById('sendBtn');return !b.classList.contains('stop')&&getComputedStyle(b).opacity==='0'})()"))
        check(t + 'no transition: all anywhere in the composer', ev("[...document.querySelectorAll('#composer, #composer *')].every(e=>getComputedStyle(e).transitionProperty!=='all'||parseFloat(getComputedStyle(e).transitionDuration)===0)"))
        ctx.close()
    check('no console errors', not errs, errs)
    b.close()
print(f'{sum(R)}/{len(R)} checks'); raise SystemExit(0 if all(R) else 1)
