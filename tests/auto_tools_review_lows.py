"""2.0.1, QA Lows: source date in .sd, count:0 restored after a reload, live/reload notice agree, '· 조금 걸려요' leaves with the result."""
from at_common import *
OLD = src(1, 'news.example.com', published='2020-01-02')
S3 = [OLD, src(2, 'b.example.org'), src(3, 'c.example.net')]
ANS = '검색 결과에 따르면 빠릅니다[1][2].'
NOTE = "(()=>{const n=document.querySelector('.msg.assistant .tnote');return n?n.querySelector('b').textContent+'|'+n.querySelector('span').textContent:null})()"
with sync_playwright() as p:
    b = p.chromium.launch()
    # ── QA Low 1: the source date sits in .sd next to the domain (list and sheet) ──
    server(auto=True); ctx, pg = launch(b)
    script([S(call(id='d1', q='날짜'), .2), S(result(id='d1', sources=S3[:2]), .3), T(ANS, .6)], S3[:2]); send(pg); settle(pg, 12000)
    pg.locator('.msg.assistant .sources .sc').first.click(); pg.wait_for_timeout(500)
    sd = pg.evaluate("[...document.querySelectorAll('.msg.assistant .src-item .sd')].map(e=>e.textContent)")
    check('.sd = 「도메인 · 날짜」 when published is given, just the domain otherwise', sd == ['news.example.com · 2020년 1월 2일', 'b.example.org'], sd)
    ctx.close()
    # ── QA Low 2: persisted tools[] count:0 → 「검색 결과를 찾지 못했어요」 after a reload ──
    def reload_case(fresh, tools, items, srcs=None, meta=True):
        server(auto=True); c, pg = launch(b); put('/pro/set', {'atFresh': fresh, 'atTools': tools, 'atPersistedMeta': meta})
        script(items, srcs); send(pg); settle(pg, 12000); live = pg.evaluate(NOTE); put('/pro/set', {'atFresh': None, 'atTools': None, 'atPersistedMeta': True})
        reload_last(pg); return c, pg, live
    c, pg, live = reload_case('unverified', [{'tool': 'web_search', 'selected_by': 'model', 'status': 'ok', 'count': 0}], [S(call(id='z1', q='없는 것'), .2), S(result(id='z1', status='ok', sources=[]), .2), T('답변이에요.', 1.0)], meta=False)
    n = pg.evaluate(NOTE); check('reload: tools[] status ok + count:0 → 검색 결과를 찾지 못했어요', n and n.startswith('검색 결과를 찾지 못했어요'), n)
    st = storage(pg); check('tools[] keeps count (stored as {"count":0})', '"count":0' in st.replace(' ', ''), st[:160]); c.close()
    # ── QA Low 3: persisted without tools[] → the live note and the reloaded note agree ──
    c, pg, live = reload_case('unverified', [], [S(call(id='n1', q='x'), 0) ] and [T('코스피는 오늘 ' + '답변이에요.', 1.0)], meta=['fresh'])
    pg.wait_for_timeout(200); n = pg.evaluate(NOTE)
    check('persisted has fresh only, no web tool: live note == reloaded note (검색하지 않고 학습한 내용으로…)', live and live == n and '검색하지 않고' in live, (live, n)); c.close()
    # a turn that DID search (tool_result failed) but persisted has no tools[]: the live failure copy is what the stream saw
    c, pg, live = reload_case('unverified', [{'tool': 'web_search', 'selected_by': 'model', 'status': 'timeout'}], [S(call(id='n2', q='x'), .2), S(result(id='n2', status='timeout'), .2), T('답변이에요.', 1.0)], meta=['fresh'])
    n = pg.evaluate(NOTE); check('searched + timeout, persisted fresh only: live == reload', live and live == n and live.startswith('검색 시간이 초과됐어요'), (live, n)); c.close()
    # ── QA Low 4: '· 조금 걸려요' goes away with the result, not just its timer ──
    server(auto=True); ctx, pg = launch(b)
    script([S(call(id='sl', q='느린 검색'), .2), S(result(id='sl', sources=S3[:2]), 7.0), T(ANS, 2.0)], S3[:2]); send(pg)
    pg.wait_for_function("()=>document.querySelectorAll('.tstat .slow').length===1", timeout=10000); check('(precondition) the slow note is shown after 6 s', True)
    pg.wait_for_function("()=>!document.querySelector('.tstat .slow')", timeout=6000); check('the slow note is removed when the result arrives (line still there)', pg.locator('.tstat').count() == 1)
    settle(pg, 12000); check('no page errors', not pg.errs, pg.errs); ctx.close()
    done()
