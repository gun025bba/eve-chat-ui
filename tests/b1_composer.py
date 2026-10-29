# 1.10.0 B1 하루 (DIRECTION-B-SPEC §9.1): one-line composer — + menu (web search), send/stop, multi-line growth, placeholder
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
        f = ev("""(()=>{const f=document.querySelector('#composer .field'),r=f.getBoundingClientRect(),s=getComputedStyle(f),c=document.getElementById('composer').getBoundingClientRect(),pl=document.getElementById('plusBtn').getBoundingClientRect(),sb=document.getElementById('sendBtn');
          return {h:r.height,rad:s.borderTopLeftRadius,l:r.left,rr:innerWidth-r.right,pb:innerHeight-r.bottom,plw:pl.width,plh:pl.height,pll:pl.left-r.left,so:getComputedStyle(sb).opacity,sp:getComputedStyle(sb).pointerEvents,bf:s.backdropFilter,mat:s.backgroundColor,sh:s.boxShadow}})()""")
        check(t + 'capsule: 44px, radius 22, 12px side margins, ≥10px from the bottom', abs(f['h'] - 44) < 1 and f['rad'] == '22px' and abs(f['l'] - 12) < 1 and abs(f['rr'] - 12) < 1 and f['pb'] >= 10, f)
        check(t + '+ is 36x36 inside the capsule (6px padding); no blur (opaque material)', f['plw'] == 36 and f['plh'] == 36 and abs(f['pll'] - 6) < 1 and f['bf'] in ('none', '') and f['mat'].startswith('rgb('), f)
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
        pb = ev("(()=>{const f=document.querySelector('#composer .field').getBoundingClientRect(),p=document.getElementById('plusBtn').getBoundingClientRect();return Math.abs((f.bottom-p.bottom)-4)<1.5})()")
        check(t + '+ and send stay anchored to the bottom while it grows', pb)
        pg.fill('#input', '')
        # + menu
        check(t + 'menu closed at rest (hidden, aria-expanded=false)', pg.is_hidden('#plusMenu') and pg.get_attribute('#plusBtn', 'aria-expanded') == 'false')
        pg.click('#plusBtn'); pg.wait_for_timeout(450)
        m = ev("""(()=>{const m=document.getElementById('plusMenu'),w=document.getElementById('webBtn'),s=getComputedStyle(m);return {vis:!m.hidden,op:s.opacity,tf:s.transform,role:m.getAttribute('role'),txt:w.textContent.trim(),wr:w.getAttribute('role'),ac:w.getAttribute('aria-checked'),h:w.getBoundingClientRect().height,bf:s.backdropFilter,exp:document.getElementById('plusBtn').getAttribute('aria-expanded')}})()""")
        check(t + '+ opens the menu: "웹 검색" row (menuitemcheckbox, 44px), spring scale settles to 1, no blur', m['vis'] and m['op'] == '1' and m['tf'] in ('none', 'matrix(1, 0, 0, 1, 0, 0)') and m['txt'] == '웹 검색' and m['wr'] == 'menuitemcheckbox' and m['ac'] == 'false' and abs(m['h'] - 44) < 1 and m['exp'] == 'true' and m['bf'] in ('none', ''), m)
        pg.keyboard.press('Escape'); pg.wait_for_timeout(350)
        check(t + 'Escape closes the menu', pg.is_hidden('#plusMenu') and pg.get_attribute('#plusBtn', 'aria-expanded') == 'false')
        pg.click('#plusBtn'); pg.wait_for_timeout(300); pg.mouse.click(200, 300); pg.wait_for_timeout(350)
        check(t + 'tap outside closes the menu', pg.is_hidden('#plusMenu'))
        pg.click('#plusBtn'); pg.wait_for_timeout(300); pg.click('#webBtn'); pg.wait_for_timeout(450)
        w = ev("(()=>{const b=document.getElementById('plusBtn'),s=getComputedStyle(b),g=b.querySelector('.i-globe'),pl=b.querySelector('.i-plus');return {on:b.classList.contains('web-on'),bg:s.backgroundColor,gd:getComputedStyle(g).display,pd:getComputedStyle(pl).display,ls:localStorage.getItem('llmchat.webSearch'),ac:document.getElementById('webBtn').getAttribute('aria-checked'),lab:b.getAttribute('aria-label')}})()")
        check(t + 'web on: + turns into a globe (accent) on rgba(10,132,255,.16); menu closes; check set; persisted', w['on'] and w['gd'] != 'none' and w['pd'] == 'none' and w['bg'] == 'rgba(10, 132, 255, 0.16)' and w['ac'] == 'true' and w['ls'] in ('1', 'true', 'auto') and pg.is_hidden('#plusMenu'), w)
        pg.reload(); pg.wait_for_timeout(1200)
        if pg.evaluate("document.getElementById('app').dataset.route") != 'chat': pg.evaluate("__app.newChat()"); pg.wait_for_timeout(500)
        check(t + 'web-on state survives a reload', pg.evaluate("document.getElementById('plusBtn').classList.contains('web-on')"))
        pg.click('#plusBtn'); pg.wait_for_timeout(300); pg.click('#webBtn'); pg.wait_for_timeout(300)
        check(t + 'toggling off restores the plus', not pg.evaluate("document.getElementById('plusBtn').classList.contains('web-on')") and pg.evaluate("localStorage.getItem('llmchat.webSearch')") not in ('1', 'true'))
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
