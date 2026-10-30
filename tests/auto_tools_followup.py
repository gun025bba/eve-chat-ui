"""2.0.1, design Lows: stop clears the .tq/note, status line counts sources.length, one fade constant, queries never stored."""
from at_common import *
OLD = src(1, 'news.example.com', published='2020-01-02')
S3 = [OLD, src(2, 'b.example.org'), src(3, 'c.example.net')]
ANS = '검색 결과에 따르면 빠릅니다[1][2].'
js = open(os.path.join(os.path.dirname(__file__), '..', 'app.js'), encoding='utf-8').read()
with sync_playwright() as p:
    b = p.chromium.launch()
    # ── design Low 3: one named constant for the 160 ms fade ──
    check('source: TS_FADE_MS is the one fade constant (no bare setTimeout(…, 160) in the status line)', js.count('TS_FADE_MS') >= 3 and not re.search(r'setTimeout\(\(\) => (cur|w)\.remove\(\), 160\)', js))
    # ── design Low 1: stop after a tool_result that named sources → no .tq, no note ──
    server(auto=True); ctx, pg = launch(b)
    script([S({'message_id': 'msg_fu_stop', 'thread_id': 't'}, 0, name='eve.meta'), S(call(id='s1', q='멈출 검색'), .2), S(result(id='s1', sources=S3[:2]), .3), T('늦은 답', 8)], S3[:2]); send(pg); pg.wait_for_timeout(1500)
    pg.click('#sendBtn'); pg.wait_for_timeout(1200)
    html = pg.evaluate("[...document.querySelectorAll('.msg.assistant')].pop().innerHTML")
    check('stop after sources: no .tq and no .tnote remain; stopped mark shown', 'class="tq"' not in html and 'tnote' not in html and pg.locator('.msg.assistant .stopped').count() == 1, html[:300])
    check('stop: the saved message does not carry the query', '멈출 검색' not in storage(pg))
    ctx.close()
    # ── design Low 2: "출처 N개" is the number of sources shown, not a server count ──
    server(auto=True); ctx, pg = launch(b)
    script([S(call(id='c1', q='개수'), .2), S(result(id='c1', sources=S3[:2], count=9), .3), T(ANS, 3)], S3[:2]); send(pg)
    check('status line counts sources.length (2), not count (9)', wait_tstat(pg, '출처 2개를 읽고 있어요', 4000) and not wait_tstat(pg, '출처 9개', 300))
    settle(pg, 12000); ctx.close()
    # ── design Low 4: tools[].query is shown this session but never written to localStorage ──
    server(auto=True); ctx, pg = launch(b); put('/pro/set', {'atFresh': 'ok', 'atTools': [{'tool': 'web_search', 'selected_by': 'model', 'status': 'ok', 'count': 2, 'query': '서버가 붙인 비밀 검색어'}]})
    script([S(call(id='q1', q='내가 보낸 검색어'), .2), S(result(id='q1', sources=S3[:2]), .3), T(ANS, .6)], S3[:2]); send(pg); settle(pg, 12000); put('/pro/set', {'atFresh': None, 'atTools': None})
    st = storage(pg); check('persist(): neither the live query nor the server-joined query is in localStorage', '내가 보낸 검색어' not in st and '서버가 붙인 비밀 검색어' not in st and '"count":2' in st.replace(' ', ''), st[:200])
    pg.locator('.msg.assistant .sources .sc').first.click(); pg.wait_for_timeout(600)
    check('…and the live sheet still shows the query this session', pg.locator('.tq').count() == 1 and '내가 보낸 검색어' in pg.locator('.tq').first.inner_text())
    ctx.close()
    done()
