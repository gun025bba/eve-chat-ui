# Regression: chat header title/subtitle must not sit under a backdrop-filter / at-rest will-change layer (iOS standalone blur)
from playwright.sync_api import sync_playwright
R=[]
def check(n, ok, x=''): R.append(bool(ok)); print('PASS' if ok else 'FAIL', n, x)
JS="""()=>{const out={};let e=document.querySelector('#title');const bad=[];
for(let n=e;n;n=n.parentElement){const cs=getComputedStyle(n);if(cs.filter!=='none'||cs.backdropFilter!=='none'||cs.willChange!=='auto'||(cs.transform!=='none'&&n.id!=='app'))bad.push(n.id||n.className)}
out.bad=bad;out.glass=getComputedStyle(document.querySelector('#topbar'),'::after').backdropFilter;
out.frac=['#title','#modelName'].map(s=>Object.values(document.querySelector(s).getBoundingClientRect().toJSON()).some(v=>v%1)) ;return out}"""
with sync_playwright() as p:
    b=p.chromium.launch()
    for sa in (False,True):
        c=b.new_context(viewport={'width':393,'height':852},device_scale_factor=3,is_mobile=True,has_touch=True)
        c.add_init_script("localStorage.setItem('llmchat.settings',JSON.stringify({base:'',model:'mlx-community/Qwen3-30B-A3B-4bit'}))")
        if sa: c.add_init_script("Object.defineProperty(navigator,'standalone',{get:()=>true})")
        pg=c.new_page(); pg.goto('http://127.0.0.1:8765/ui/'); pg.wait_for_timeout(1000)
        pg.wait_for_function("document.querySelector('#app').dataset.route==='chat'")
        r=pg.evaluate(JS); m='standalone' if sa else 'tab'
        check(f'{m}: no filter/will-change/transform above title at rest', not r['bad'], str(r['bad']))
        check(f'{m}: glass on #topbar::after', 'blur' in r['glass'], r['glass'])
        check(f'{m}: integer title/subtitle rects', not any(r['frac']))
        c.close()
    b.close()
print('RESULT:', 'ALL PASS' if all(R) else f'{R.count(False)} FAIL')
