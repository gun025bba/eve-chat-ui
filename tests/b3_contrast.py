# 1.10.0 B3: contrast of the status strip (numbers, labels, icons colours, nav subtitle) and the sheets' text on the surfaces they sit on, dark + light (WCAG 2.x; ≥4.5:1 text)
import json
from playwright.sync_api import sync_playwright
from b3_common import *
R = []; errs = []
def check(n, ok, x=''): R.append(bool(ok)); print('PASS' if ok else 'FAIL', n, '' if ok else x)
JS = """(open) => { const lum=c=>{const f=v=>{v/=255;return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4)};return .2126*f(c[0])+.7152*f(c[1])+.0722*f(c[2])};
 const parse=s=>{const m=s.match(/rgba?\\(([^)]+)\\)/)[1].split(',').map(x=>parseFloat(x));return m.length<4?[...m,1]:m};
 const over=(fg,bg)=>[0,1,2].map(i=>fg[i]*fg[3]+bg[i]*(1-fg[3]));
 const bgOf=el=>{let acc=[];for(let n=el;n;n=n.parentElement){const cs=getComputedStyle(n);let c=parse(cs.backgroundColor);if(c[3]<.99&&cs.backgroundImage!=='none'){const g=(cs.backgroundImage.match(/rgba?\\([^)]+\\)/)||[])[0];if(g)c=parse(g)}acc.push(c);if(c[3]>.99){let r=c;for(let i=acc.length-2;i>=0;i--)r=over(acc[i],r).concat([1]);return r}}return [255,255,255,1]};
 const cr=(a,b)=>{const x=lum(a),y=lum(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05)};
 const out={};
 const txt=(name,el)=>{if(!el)return;const bg=bgOf(el),c=parse(getComputedStyle(el).color);out[name]=+cr(over(c,bg),bg).toFixed(2)};
 const cell=k=>document.querySelector('.stc[data-k='+k+']');
 for(const k of ['mem','pend','sch']){const c=cell(k);if(!c)continue;txt('strip '+k+' number',c.querySelector('.sn'));txt('strip '+k+' label',c.querySelector('.sl span'));const ic=c.querySelector('.sl svg');if(ic){const bg=bgOf(c),col=parse(getComputedStyle(ic).color);out['strip '+k+' icon (non-text ≥3)']=+cr(over(col,bg),bg).toFixed(2)}}
 txt('nav subtitle',document.getElementById('todayNavSub'));
 if(open){txt('sheet title',document.getElementById('ssTitle'));txt('sheet subtitle',document.getElementById('ssSub'));txt('sheet footnote',document.getElementById('ssFoot'));
  txt('sheet 곧 만료 (--pend)',document.querySelector('#ssList .ss-x'));
  for(const [nm,q] of [['row','#ssList .ss-row, #ssList .ss-ev:not(.past)'],['past row','#ssList .ss-ev.past']]){const r=document.querySelector(q);if(r){for(const s of ['.ss-t','.ss-m','.ss-tm']){const e=r.querySelector(s);if(e)txt('sheet '+nm+' '+s,e)}}}}
 return out }"""
OUT = {}
with sync_playwright() as p:
    b = p.chromium.launch()
    for scheme in ['dark', 'light']:
        reset(); rich(); memory(12); seed_act(act(1, title='치과 예약', exp=60 * 24 * 3), title='치과'); seed_act(act(2, title='장보기', exp=5, verb='remind'), title='장보기')
        brief_thread([ev('이미 지난 일정', 0, 1), ev('저녁 약속', 23, 30)], count=2)
        ctx, pg = newpg(b, errs, scheme=scheme); goto_today(pg); pg.wait_for_timeout(400)
        o = pg.evaluate(JS, False)
        pg.locator('.stc[data-k=sch]').click(); pg.wait_for_timeout(600); o.update({'(sch) ' + k: v for k, v in pg.evaluate(JS, True).items() if k.startswith('sheet')}); pg.keyboard.press('Escape'); pg.wait_for_timeout(450)
        pg.locator('.stc[data-k=pend]').click(); pg.wait_for_timeout(600); o.update({'(pend) ' + k: v for k, v in pg.evaluate(JS, True).items() if k.startswith('sheet')})
        OUT[scheme] = o; ctx.close()
        for k, v in o.items():
            lim = 3.0 if 'non-text' in k else 4.5
            check(f'{scheme}: {k} = {v}:1 ≥ {lim}', v >= lim, v)
        check(f'{scheme}: measured strip + sheet values', len(o) >= 20, len(o))
    check('no page errors', not errs, errs); b.close()
print(json.dumps(OUT, ensure_ascii=False, indent=1)); json.dump(OUT, open('/tmp/b3_contrast.json', 'w'))
print(f'{sum(R)}/{len(R)} checks'); raise SystemExit(0 if all(R) else 1)
