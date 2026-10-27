# Regression (v12): exactly one visible header title node, no view-transition-name, no font synthesis, real weight; version label
from playwright.sync_api import sync_playwright
R=[]
def check(n, ok, x=''): R.append(bool(ok)); print('PASS' if ok else 'FAIL', n, x)
with sync_playwright() as p:
    b=p.chromium.launch(); c=b.new_context(viewport={'width':393,'height':852},is_mobile=True,has_touch=True)
    c.add_init_script("localStorage.setItem('llmchat.settings',JSON.stringify({base:'',model:'mlx-community/Qwen3-30B-A3B-4bit'}))")
    pg=c.new_page(); pg.goto('http://127.0.0.1:'+__import__('os').environ.get('EVE_PORT','8765')+'/ui/'); pg.wait_for_timeout(1000)
    r=pg.evaluate("""()=>{const tb=document.querySelector('#topbar');const t=document.querySelector('#title').textContent.trim();
     const vis=[...tb.querySelectorAll('*')].filter(e=>{const cs=getComputedStyle(e);const r=e.getBoundingClientRect();
       return [...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim()===t)&&cs.visibility!=='hidden'&&cs.display!=='none'&&r.width>0});
     const cs=getComputedStyle(document.querySelector('#title'));
     return {n:vis.length,vtn:cs.viewTransitionName||'none',vtw:getComputedStyle(document.querySelector('#titleWrap')).viewTransitionName||'none',
       chatVtn:getComputedStyle(document.querySelector('#chatView')).viewTransitionName||'none',
       syn:cs.fontSynthesis||cs.webkitFontSynthesis,w:cs.fontWeight,tr:cs.transitionDuration,an:cs.animationName,
       ver:document.querySelector('#appVersion')?.textContent,appv:window.__app&&window.__app.version}}""")
    print(r)
    check('one visible title node', r['n']==1, r['n'])
    check('no view-transition-name on title/wrap', r['vtn']=='none' and r['vtw']=='none')
    check('no VT name on chatView at rest', r['chatVtn']=='none', r['chatVtn'])
    check('font-synthesis none', r['syn'] in ('none',), r['syn'])
    check('real weight 700', r['w']=='700', r['w'])
    check('no title transition/animation', r['tr'] in ('0s',) and r['an']=='none')
    check('version label 1.3.1', (r['ver'] or '').startswith('v1.3.1') and r['appv']=='1.3.1', r['ver'])
    b.close()
print('ALL PASS' if all(R) else 'SOME FAIL'); raise SystemExit(0 if all(R) else 1)
