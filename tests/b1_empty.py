# 1.10.0 B1 하루: the empty screen is gone — a new chat is just the "지금" rail event; no centered logo, headline, subtitle or suggestion cards
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
        if pg.evaluate("document.getElementById('app').dataset.route") != 'chat': pg.click('#newChat'); pg.wait_for_timeout(600)
        t = scheme + ': '
        r = pg.evaluate("""(()=>{const m=document.getElementById('messages'),n=m.querySelector('.rail-now');return {kids:m.children.length,now:!!n,who:n?.querySelector('.who-n')?.textContent,hint:n?.querySelector('.tx')?.textContent,tm:n?.querySelector('.tm')?.textContent,
          msgs:m.querySelectorAll('.msg').length,forbid:m.querySelectorAll('.empty,.mark,.mark-tile,.chip,.chips,h1,img').length,text:m.innerText,body:document.body.innerText}})()""")
        check(t + 'empty chat = exactly one "지금" event (not a message)', r['kids'] == 1 and r['now'] and r['who'] == '지금' and r['msgs'] == 0 and r['hint'] == '아래에 한 줄로 남기면 오늘 기록에 쌓여요.', r)
        check(t + 'time of the "지금" event = current KST HH:mm', __import__('re').fullmatch(r'\d\d:\d\d', r['tm'] or ''), r['tm'])
        check(t + 'forbidden elements nowhere: logo, headline, subtitle, suggestion cards', r['forbid'] == 0 and '무엇을 도와드릴까요' not in r['body'] and '로컬 · 비공개' not in r['text'] and '도와' not in r['text'], r)
        dot = pg.evaluate("(()=>{const d=document.querySelector('.rail-now .dot'),s=getComputedStyle(d),w=document.querySelector('.rail-now .who');return {bg:s.backgroundColor,sh:s.boxShadow,wc:getComputedStyle(w).color}})()")
        check(t + '"지금" dot = --accent with a 5px ring; label in --accent', dot['bg'] in ('rgb(10, 132, 255)', 'rgb(0, 122, 255)') and '5px' in dot['sh'], dot)
        pg.fill('#input', '안녕'); pg.click('#sendBtn'); pg.wait_for_timeout(1500)
        check(t + 'first message replaces the "지금" event', pg.evaluate("document.querySelectorAll('#messages .rail-now').length") == 0 and pg.evaluate("document.querySelectorAll('#messages .msg').length") >= 2)
        ctx.close()
    check('no console errors', not errs, errs)
    b.close()
print(f'{sum(R)}/{len(R)} checks'); raise SystemExit(0 if all(R) else 1)
