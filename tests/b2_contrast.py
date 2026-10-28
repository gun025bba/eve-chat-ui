# 1.10.0 B2: contrast numbers for --sub (secondary text) and --pend on the surfaces they sit on, dark + light (WCAG 2.x; ≥4.5:1 text)
import json
from playwright.sync_api import sync_playwright
from b2_common import *
R = []
def check(n, ok, x=''): R.append(bool(ok)); print('PASS' if ok else 'FAIL', n, '' if ok else x)
JS = """(()=>{const lum=c=>{const f=v=>{v/=255;return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4)};return .2126*f(c[0])+.7152*f(c[1])+.0722*f(c[2])};
 const parse=s=>{const m=s.match(/rgba?\\(([^)]+)\\)/)[1].split(',').map(x=>parseFloat(x));return m.length<4?[...m,1]:m};
 const over=(fg,bg)=>[0,1,2].map(i=>fg[i]*fg[3]+bg[i]*(1-fg[3]));
 const col=(v,host)=>{const e=document.createElement('i');e.style.cssText='position:absolute;color:'+v;host.appendChild(e);const c=getComputedStyle(e).color;e.remove();return parse(c)};
 const bgOf=el=>{for(let n=el;n;n=n.parentElement){const c=parse(getComputedStyle(n).backgroundColor);if(c[3]>.99)return c}return [255,255,255,1]};
 const cr=(a,b)=>{const x=lum(a),y=lum(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05)};
 const out={};const host=document.querySelector('#todayView');
 const surf={'bg':bgOf(document.querySelector('#todayView .scroller, #todayView')),'card(layer-1)':col('var(--layer-1)',host),'material':col('var(--material)',host)};
 const sub=col('var(--sub)',host),pend=col('var(--pend)',host);
 for(const [k,s] of Object.entries(surf)){out['--sub on '+k]=+cr(over(sub,s),s).toFixed(2);out['--pend on '+k]=+cr(pend.slice(0,3),s).toFixed(2)}
 const tm=document.querySelector('#todayList .ev .tm');if(tm){const c=parse(getComputedStyle(tm).color);out['rail time on bg']=+cr(over(c,surf.bg),surf.bg).toFixed(2)}
 return out})()"""
OUT = {}
with sync_playwright() as p:
    b = p.chromium.launch(); reset(); rich(); older()
    for scheme in ['dark', 'light']:
        ctx = new_ctx(b, scheme=scheme); pg = ctx.new_page(); goto_today(pg); OUT[scheme] = pg.evaluate(JS); ctx.close()
        for k, v in OUT[scheme].items(): check(f'{scheme}: {k} = {v}:1 ≥ 4.5', v >= 4.5, v)
    b.close()
print(json.dumps(OUT, ensure_ascii=False, indent=1)); json.dump(OUT, open('/tmp/b2_contrast.json', 'w'))
print(f'{sum(R)}/{len(R)} checks'); raise SystemExit(0 if all(R) else 1)
