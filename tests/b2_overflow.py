# 1.10.0 B2 하루 (DIRECTION-B §12): no horizontal scroll at 320 / 375 / 390 on Today, the conversation (long title, long URL, wide table, 5 chips + 2 memory chips) and 기록 — dark + light
import json
from playwright.sync_api import sync_playwright
from b2_common import *
R = []; errs = []; ROWS = []
def check(n, ok, x=''): R.append(bool(ok)); print('PASS' if ok else 'FAIL', n, '' if ok else x)
reset()
LONG = '아주아주아주 긴 대화 제목입니다 ' * 6 + 'https://example.com/' + 'a' * 120
URL = 'https://example.com/' + 'very-long-path-segment/' * 12 + '?q=' + 'x' * 80
TABLE = '| 항목 | 값 | 설명 | 비고 | 기타 |\n|---|---|---|---|---|\n| ' + ' | '.join(['긴내용' * 8] * 5) + ' |\n| a | b | c | d | e |'
MEM5 = MEM3 + [{'id': 'm4', 'text': '아주 아주 아주 아주 긴 기억 문장이 여기에 들어갑니다 정말로'}, {'id': 'm5', 'text': '짧은 기억'}]
seed(LONG, [{'role': 'user', 'content': '링크 줘: ' + URL + ' ' + 'ㅋ' * 200, 'created_at': at(7, 41)},
            {'role': 'assistant', 'content': f'여기 있어요 {URL}\n\n{TABLE}\n\n```\n' + 'const veryLongLine = ' + '"x".repeat(100) + ' * 6 + '1;\n```', 'created_at': at(7, 42), 'sources': S5, 'memory_refs': MEM5}], memory=True)
put('/b2/seed', dict(title=LONG + ' 선톡', created=at(8, 0), updated=at(8, 0), messages=[pro_msg('긴 선톡 ' + URL + ' ' + 'ㅎ' * 150, 8, 0, job='아주아주 긴 작업 이름 ' * 4, tkind='briefing')]))
rich(); older()
PAGES = [('Today', '#/', lambda pg: None), ('Log', '#/log', lambda pg: None), ('Conversation', None, lambda pg: open_thread(pg, '아주아주'))]
with sync_playwright() as p:
    b = p.chromium.launch()
    for scheme in ['dark', 'light']:
        for w in (320, 375, 390):
            for name, h, act in PAGES:
                ctx = new_ctx(b, w=w, h=800, scheme=scheme); pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
                if h: goto_today(pg, h, wait=1600)
                else: act(pg)
                pg.wait_for_timeout(500)
                m = pg.evaluate("(()=>{const s=document.scrollingElement;let worst=0,who='';for(const e of document.querySelectorAll('#app .screen:not([inert]) *')){const r=e.getBoundingClientRect();if(r.width&&r.right>innerWidth+.5&&!e.closest('pre,.tbl,.table-wrap,table,.wk')&&r.right-innerWidth>worst){worst=r.right-innerWidth;who=(e.id||e.className||e.tagName)+''}}return {sw:s.scrollWidth,cw:s.clientWidth,worst,who}})()")
                ok = m['sw'] <= m['cw'] and m['worst'] <= .5; check(f'{scheme} {w}px {name}: scrollWidth {m["sw"]} ≤ clientWidth {m["cw"]}', ok, m); ROWS.append([name, scheme, w, m['sw'], m['cw'], 'OK' if ok else 'OVERFLOW'])
                ctx.close()
    check('no page errors', not errs, errs); b.close()
print('| screen | scheme | width | scrollWidth | clientWidth | result |\n|---|---|---|---|---|---|')
for r in ROWS: print('| ' + ' | '.join(map(str, r)) + ' |')
json.dump(ROWS, open('/tmp/b2_overflow_rows.json', 'w')); print(f'{sum(R)}/{len(R)} checks'); raise SystemExit(0 if all(R) else 1)
