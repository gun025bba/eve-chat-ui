# 1.10.0 B1 하루 §13 screenshots → review-shots/1.10.0/b1/ (390px @2x dark+light, 320px, light contrast). Not part of the suite (writes files; needs a running mock: EVE_PORT=<port> python b1_shots.py).
import json, os, re
from playwright.sync_api import sync_playwright
from b1_common import *
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'review-shots', '1.10.0', 'b1'); os.makedirs(OUT, exist_ok=True)
def lum(c):
    f = lambda v: v / 255 / 12.92 if v / 255 <= .03928 else ((v / 255 + .055) / 1.055) ** 2.4
    return .2126 * f(c[0]) + .7152 * f(c[1]) + .0722 * f(c[2])
def ratio(a, b): la, lb = lum(a), lum(b); return (max(la, lb) + .05) / (min(la, lb) + .05)
def rgba(s): return [float(x) for x in re.findall(r'[\d.]+', s)]
def over(fg, bg): a = fg[3] if len(fg) > 3 else 1; return [fg[i] * a + bg[i] * (1 - a) for i in range(3)]
reset()
ANS = '내일 오후 3시예요. 역삼동 치과로 잡혀 있고, 30분 전에 알려 드릴게요.'
def conv(title, answer_extra, n=''):
    return seed(title, [{'role': 'user', 'content': '내일 치과 몇 시였지?', 'created_at': at(7, 41)}, dict({'role': 'assistant', 'content': ANS, 'created_at': at(7, 42)}, **answer_extra)], memory=True)
conv('S01 대화', {})
conv('S02 출처 1', {'sources': S1}); conv('S02 출처 2', {'sources': S2}); conv('S02 출처 5', {'sources': S5})
conv('S03 기억', {'memory_refs': MEM3})
seed('S04 확인 카드', [{'role': 'user', 'content': '내일 오후 3시에 치과 일정 추가해 줘', 'created_at': at(7, 41)}, {'role': 'assistant', 'content': '치과 일정을 추가할까요?', 'created_at': at(7, 42), 'pending_actions': [ACT]}], actions=[ACT])
seed('S06 칩 다섯', [{'role': 'user', 'content': '치과 위치 알려줘', 'created_at': at(7, 41)}, {'role': 'assistant', 'content': ANS, 'created_at': at(7, 42), 'sources': S5, 'memory_refs': MEM3}])
seed('S07 대비', [{'role': 'user', 'content': '어제 얘기한 거 이어서', 'created_at': at(23, 50, -1)}, {'role': 'assistant', 'content': '네, 이어서 할게요.', 'created_at': at(23, 51, -1)},
  {'role': 'user', 'content': '내일 치과 일정 추가해 줘', 'created_at': at(7, 41)}, {'role': 'assistant', 'content': '치과 일정을 추가할까요?', 'created_at': at(7, 42), 'pending_actions': [dict(ACT, action_id='01JACT00000000000000000002')]}], actions=[dict(ACT, action_id='01JACT00000000000000000002')])
CT = {}
with sync_playwright() as p:
    for scheme in ['dark', 'light']:
        b = p.webkit.launch(); dev = dict(p.devices['iPhone 14']); dev['device_scale_factor'] = 2
        def mk(w=390):
            d = dict(dev); d['viewport'] = {'width': w, 'height': 844}; d['screen'] = {'width': w, 'height': 844}
            ctx = b.new_context(**d, color_scheme=scheme); ctx.add_init_script("Object.defineProperty(navigator,'standalone',{get:()=>true})")
            ctx.add_init_script("if(!sessionStorage.getItem('s')){sessionStorage.setItem('s',1);" + SETTINGS + "}"); return ctx
        shot = lambda pg, name: pg.screenshot(path=f'{OUT}/{name}-{scheme}.png')
        ctx = mk(); pg = ctx.new_page()
        def go(title, w=None): open_thread(pg, title); pg.wait_for_timeout(700)
        go('S01'); shot(pg, '01-conversation')
        for n in (1, 2, 5):
            go(f'S02 출처 {n}'); shot(pg, f'02-sources-{n}-collapsed')
            pg.locator('.sources .sc').first.click(); pg.wait_for_timeout(700); shot(pg, f'02-sources-{n}-expanded')
        go('S03'); shot(pg, '03-memory-chip')
        go('S04'); shot(pg, '04-confirm-pending')
        pg.locator('.confirm-card .cc-primary').click(); pg.wait_for_timeout(1200); shot(pg, '04-confirm-confirmed')
        go('S01'); pg.fill('#input', 'slow stream'); pg.click('#sendBtn'); pg.wait_for_timeout(1500)
        pg.fill('#input', '다음에는\n이것도 알아봐 줘\n그리고 정리해서 알려줘'); pg.wait_for_timeout(600); shot(pg, '05-streaming-multiline')
        pg.keyboard.press('Escape'); pg.click('#sendBtn'); pg.wait_for_timeout(500)   # stop the stream
        ctx.close()
        ctx = mk(320); pg = ctx.new_page(); go('S06'); pg.screenshot(path=f'{OUT}/06-320-five-chips-{scheme}.png')
        sc = pg.evaluate("document.documentElement.scrollWidth"); CT.setdefault('320 scrollWidth', {})[scheme] = sc; ctx.close()
        ctx = mk(); pg = ctx.new_page(); go('S07')
        if scheme == 'light': shot(pg, '07-contrast-light')
        v = pg.evaluate("""(()=>{const g=s=>getComputedStyle(document.querySelector(s)),pr=document.createElement('i');pr.style.background='var(--bg)';document.body.appendChild(pr);const bg=getComputedStyle(pr).backgroundColor;pr.remove();const card=g('.confirm-card').backgroundColor;
          return {bg,card,sub:g('.msg.user .who').color,tm:g('.msg.user .tm').color,day:g('.day-sep').color,pend:g('.confirm-card .cc-head svg').color,brand:g('.msg.assistant .who').color,subVar:getComputedStyle(document.documentElement).getPropertyValue('--sub').trim(),pendVar:getComputedStyle(document.documentElement).getPropertyValue('--pend').trim()}})()""")
        bg = rgba(v['bg'])[:3]; card = over(rgba(v['card']), bg)
        CT[scheme] = {'--sub on bg (who/time)': round(ratio(over(rgba(v['sub']), bg), bg), 2), '--sub on bg (day-sep)': round(ratio(over(rgba(v['day']), bg), bg), 2), '--pend on card': round(ratio(over(rgba(v['pend']), card), card), 2), '--brand on bg': round(ratio(over(rgba(v['brand']), bg), bg), 2), 'tokens': [v['subVar'], v['pendVar']]}
        ctx.close(); b.close()
print(json.dumps(CT, ensure_ascii=False, indent=1)); json.dump(CT, open('/tmp/b1_contrast.json', 'w'), ensure_ascii=False)
