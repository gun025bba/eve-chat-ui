# Regression (v11): chat header title/subtitle crisp at rest and during/after scroll, tab + standalone (display-mode emulated)
from playwright.sync_api import sync_playwright
R=[]
def check(n, ok, x=''): R.append(bool(ok)); print('PASS' if ok else 'FAIL', n, x)
JS="""()=>{const out={bad:[]};
for(const s of ['#title','#modelName']){const e=document.querySelector(s);const cs=getComputedStyle(e);
 if(cs.opacity!=='1')out.bad.push(s+' opacity '+cs.opacity);
 if(cs.textShadow!=='none')out.bad.push(s+' text-shadow');
 if(!/^rgb\\(/.test(cs.color))out.bad.push(s+' color '+cs.color);
 for(let n=e;n;n=n.parentElement){const c=getComputedStyle(n);const id=n.id||n.className||n.tagName;
  if(c.filter!=='none')out.bad.push(id+' filter '+c.filter);
  if(c.backdropFilter!=='none'&&c.backdropFilter)out.bad.push(id+' backdrop '+c.backdropFilter);
  if(c.opacity!=='1')out.bad.push(id+' opacity '+c.opacity);
  if(c.willChange!=='auto')out.bad.push(id+' will-change');
  if(c.mixBlendMode!=='normal')out.bad.push(id+' blend');
  if(c.transform!=='none'&&!['app'].includes(n.id)&&!/matrix\\(1, 0, 0, 1, 0, 0\\)/.test(c.transform))out.bad.push(id+' transform '+c.transform);}}
const tb=document.querySelector('#topbar');for(const p of ['::before','::after']){const c=getComputedStyle(tb,p);if(c.content!=='none'&&c.backdropFilter&&c.backdropFilter!=='none')out.bad.push('topbar'+p+' backdrop')}
const bg=getComputedStyle(tb).backgroundColor;out.bg=bg;if(!/^rgb\\(/.test(bg))out.bad.push('topbar bg not opaque '+bg);
out.anims=document.getAnimations().filter(a=>a.effect&&a.effect.target&&tb.contains(a.effect.target)&&a.effect.target.closest('#titleWrap')).length;
out.frac=['#title','#modelName'].map(s=>Object.values(document.querySelector(s).getBoundingClientRect().toJSON()).some(v=>v%1));return out}"""
with sync_playwright() as p:
    b=p.chromium.launch()
    for sa in (False,True):
        for scheme in ('dark','light'):
            c=b.new_context(viewport={'width':393,'height':852},device_scale_factor=3,is_mobile=True,has_touch=True,color_scheme=scheme)
            c.add_init_script("localStorage.setItem('llmchat.settings',JSON.stringify({base:'',model:'mlx-community/Qwen3-30B-A3B-4bit'}))")
            if sa: c.add_init_script("Object.defineProperty(navigator,'standalone',{get:()=>true})")
            pg=c.new_page()
            if sa: c.new_cdp_session(pg).send('Emulation.setEmulatedMedia',{'features':[{'name':'display-mode','value':'standalone'}]})
            pg.goto('http://127.0.0.1:8765/ui/'); pg.wait_for_timeout(1000)
            pg.wait_for_function("document.querySelector('#app').dataset.route==='chat'")
            m=('standalone' if sa else 'tab')+'/'+scheme
            if sa: print('info display-mode standalone media matches:', pg.evaluate("matchMedia('(display-mode: standalone)').matches"), '(app keys off navigator.standalone)')
            r=pg.evaluate(JS)
            check(f'{m}: rest crisp', not r['bad'], str(r['bad'])); check(f'{m}: no title animations', r['anims']==0)
            check(f'{m}: integer rects', not any(r['frac']))
            pg.evaluate("(()=>{const b=document.querySelector('#messages');b.style.minHeight='3000px';const s=b.closest('[id]')||b;})()")
            pg.evaluate("(()=>{const el=[...document.querySelectorAll('#chatView *')].find(e=>e.scrollHeight>e.clientHeight+10&&getComputedStyle(e).overflowY!=='visible');if(el){el.scrollTop=300;el.dispatchEvent(new Event('scroll'))}})()")
            pg.wait_for_timeout(60); r=pg.evaluate(JS); check(f'{m}: mid-scroll crisp', not r['bad'], str(r['bad']))
            pg.wait_for_timeout(600); r=pg.evaluate(JS); check(f'{m}: after-scroll crisp', not r['bad'], str(r['bad']))
            c.close()
    b.close()
print('RESULT:', 'ALL PASS' if all(R) else f'{R.count(False)} FAIL')
