# 1.2.2 iOS polish: status-bar strip, composer autofill attrs, no horizontal scroll from sources, transform/opacity-only animations
import os, re
from playwright.sync_api import sync_playwright
B = 'http://127.0.0.1:' + os.environ.get('EVE_PORT', '8765')
R = []
def check(name, ok, extra=''): R.append(bool(ok)); print(('PASS' if ok else 'FAIL'), name, extra)
css = open(os.path.join(os.path.dirname(__file__), '..', 'styles.css')).read()
html = open(os.path.join(os.path.dirname(__file__), '..', 'index.html')).read()
check('status-bar-style default (1.6.0: no translucent blur) + viewport-fit=cover', 'apple-mobile-web-app-status-bar-style" content="default"' in html and 'black-translucent' not in html and 'viewport-fit=cover' in html)
check('no transition:all', not re.search(r'transition:\s*all', css))
check('no height/left/top transitions or keyframes', not re.search(r'transition:[^;}]*\b(height|top|left|max-height)\b', css) and not re.search(r'@keyframes [\w-]+\{[^}]*\b(left|top|height):', css))
errs = []
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark').new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(B + '/ui/#/'); pg.wait_for_timeout(1500)
    check('version 1.6.0', pg.evaluate('__app.version') == '1.6.0')
    a = pg.evaluate("(()=>{const i=document.getElementById('input');return [i.tagName,i.name,i.getAttribute('autocomplete'),i.getAttribute('autocorrect'),i.getAttribute('autocapitalize'),i.getAttribute('enterkeyhint')]})()")
    check('composer: textarea, non-name name, autocomplete off, autocorrect off (1.6.0)/autocapitalize/enterkeyhint', a == ['TEXTAREA', '', 'off', 'off', 'sentences', 'send'] and not re.search(r'name|contact|tel|email', a[1]), a)
    s = pg.evaluate("(()=>[...document.querySelectorAll('.navbar,#topbar')].map(n=>{const c=getComputedStyle(n);return [c.backgroundColor,c.backdropFilter||c.webkitBackdropFilter||'none']}))()")
    check('1.3.2: every header opaque, no backdrop-filter', s and all(not bg.startswith('rgba') and bg != 'transparent' and bf == 'none' for bg, bf in s), s)
    pg.evaluate("""(()=>{const m=document.getElementById('messages');const d=document.createElement('div');d.className='msg assistant';
      const long='https://example.com/'+'a'.repeat(400);
      d.innerHTML='<div class="bubble"><div class="md"><p>'+long+'</p><table><tr>'+'<td>wide-cell-content</td>'.repeat(30)+'</tr></table><div class="codeblock"><pre><code>'+'const x = 1; '.repeat(80)+'</code></pre></div></div><div class="sources"><h4>출처</h4><ol><li><a href="#"><span class="sn">1</span><span class="st">'+'아주긴제목'.repeat(100)+'</span><span class="sd">'+'x'.repeat(200)+'.com</span></a></li></ol></div></div>';
      m.appendChild(d)})()""")
    w = pg.evaluate("(()=>{const m=document.getElementById('messages');return [m.scrollWidth,m.clientWidth,getComputedStyle(m).overflowX,getComputedStyle(document.querySelector('.sources .st')).textOverflow,getComputedStyle(document.querySelector('.sources a')).marginLeft,getComputedStyle(document.querySelector('.sources ol')).gridTemplateColumns.split(' ').length]})()")
    check('390px: long title + URL + wide table + long code → #messages scrollWidth <= clientWidth', w[0] <= w[1] and w[2] == 'clip' and w[3] == 'ellipsis', w)
    check('sources: no negative margin, single defined grid column', w[4] == '0px' and w[5] == 1, w)
    check('no page errors', not errs, errs)
    b.close()
print(f'{sum(R)}/{len(R)} passed'); raise SystemExit(0 if all(R) else 1)
