# 1.10.0 B1 하루 (DIRECTION-B §12): no horizontal overflow at 320 / 375 / 390 for the conversation — long title, long URL, wide table, 5 source chips + 2 memory chips (dark + light)
import json, sys
from playwright.sync_api import sync_playwright
from b1_common import *
R = []; errs = []; ROWS = []
def check(n, ok, x=''): R.append(bool(ok)); print('PASS' if ok else 'FAIL', n, '' if ok else x)
reset()
LONG_TITLE = '아주아주아주 긴 대화 제목입니다 ' * 6 + 'https://example.com/' + 'a' * 120
URL = 'https://example.com/' + 'very-long-path-segment/' * 12 + '?q=' + 'x' * 80
TABLE = '| 항목 | 값 | 설명 | 비고 | 기타 |\n|---|---|---|---|---|\n| ' + ' | '.join(['긴내용' * 8] * 5) + ' |\n| a | b | c | d | e |'
CODE = '```\n' + 'const veryLongLine = ' + '"x".repeat(100) + ' * 6 + '1;\n```'
MEM5 = MEM3 + [{'id': 'm4', 'text': '아주 아주 아주 아주 긴 기억 문장이 여기에 들어갑니다 정말로'}, {'id': 'm5', 'text': '짧은 기억'}]
seed(LONG_TITLE, [
  {'role': 'user', 'content': '링크 줘: ' + URL + ' 그리고 ' + 'ㅋ' * 200, 'created_at': at(7, 41)},
  {'role': 'assistant', 'content': f'여기 있어요 {URL}\n\n{TABLE}\n\n{CODE}', 'created_at': at(7, 42), 'sources': S5, 'memory_refs': MEM5},
  {'role': 'assistant', 'content': '확인 카드', 'created_at': at(7, 43), 'pending_actions': [ACT]},
], actions=[ACT], memory=True)
with sync_playwright() as p:
    b = p.chromium.launch()
    for scheme in ['dark', 'light']:
        for w in (320, 375, 390):
            ctx = new_ctx(b, w=w, h=800, scheme=scheme); pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
            open_thread(pg, '아주아주'); pg.wait_for_timeout(600)
            m = pg.evaluate("""(()=>{const d=document.documentElement,m=document.getElementById('messages'),vw=innerWidth;let worst=0,who='';
              for(const e of m.querySelectorAll('.msg, .msg *, .confirm-card, .confirm-card *, .mchips, .sources')){const r=e.getBoundingClientRect(); if(r.width&&e.closest('pre,.tbl,.table-wrap,.md-table,table')==null&&r.right>vw+0.5&&r.right-vw>worst){worst=r.right-vw;who=e.className||e.tagName}}
              return {doc:d.scrollWidth,vw,body:document.body.scrollWidth,msgs:m.scrollWidth,cw:m.clientWidth,worst,who,chips:m.querySelectorAll('.sources .sc').length,mem:m.querySelectorAll('.mchips .chp').length,more:m.querySelector('.mchips .chp-more')?.textContent||'',title:document.getElementById('threadTitle')?.scrollWidth||document.querySelector('#chatTitle,.navbar .title')?.scrollWidth||0}})()""")
            ok = m['doc'] <= m['vw'] and m['body'] <= m['vw'] and m['msgs'] <= m['cw'] and m['worst'] <= 0.5
            check(f'{scheme} {w}px: no horizontal overflow (document {m["doc"]}≤{w}, #messages {m["msgs"]}≤{m["cw"]})', ok, m)
            check(f'{scheme} {w}px: 5 sources → 2 chips + "+3" (3 elements), memory → 2 chips + "+3"', m['chips'] == 3 and m['mem'] == 2 and m['more'] == '+3', m)
            ROWS.append([scheme, w, m['doc'], m['msgs'], m['cw'], 'OK' if ok else 'OVERFLOW'])
            # the wide table / code scroll on their own
            sc = pg.evaluate("""(()=>{const out=[];for(const e of document.querySelectorAll('#messages pre, #messages table, #messages .tbl, #messages .table-wrap')){const s=getComputedStyle(e);out.push([e.tagName,e.scrollWidth>e.clientWidth?s.overflowX:'fit',e.getBoundingClientRect().right<=innerWidth+0.5])}return out})()""")
            check(f'{scheme} {w}px: wide table/code stay inside the column (scroll on their own)', all(x[2] for x in sc) and len(sc) >= 1, sc)
            ctx.close()
    check('no console errors', not errs, errs)
    b.close()
print('| scheme | width | document.scrollWidth | #messages.scrollWidth | #messages.clientWidth | result |\n|---|---|---|---|---|---|')
for r in ROWS: print('| ' + ' | '.join(map(str, r)) + ' |')
json.dump(ROWS, open('/tmp/b1_overflow_rows.json', 'w'))
print(f'{sum(R)}/{len(R)} checks'); raise SystemExit(0 if all(R) else 1)
