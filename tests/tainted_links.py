"""AUTO-TOOLS-SPEC §8 (M-7) · a tainted message links only URLs that are in its own sources; markdown images become alt text. A turn that got a web tool_result is tainted while streaming; the server's `tainted` flag wins when sent."""
from at_common import *
OK = src(1, 'example.com', url='https://Example.com:443/news/a/?x=1#top')
SRC = [OK, src(2, 'docs.example.org')]
BODY = '자세히는 [공식](https://example.com/news/a?x=1) 와 [문서](https://docs.example.org/p2) 참고[1]. [피싱](https://evil.example/login?u=1) ![로고](https://evil.example/pixel.png) 끝.'
def links(pg): return pg.evaluate("[...document.querySelectorAll('.msg.assistant .md a:not(.cite a)')].map(a=>a.getAttribute('href'))")
def md_text(pg): return pg.evaluate("[...document.querySelectorAll('.msg.assistant .md')].pop().textContent")
def reload_last(pg):
    pg.evaluate("localStorage.removeItem('llmchat.convs')"); pg.reload(); pg.wait_for_timeout(1200)
    if not pg.is_visible('#input'): pg.evaluate("document.querySelector('#convList li.row .row-main').click()"); pg.wait_for_timeout(1500)
    pg.wait_for_timeout(500)
WEB = [{'tool': 'web_search', 'selected_by': 'model', 'status': 'ok', 'count': 2}]
with sync_playwright() as p:
    b = p.chromium.launch()
    # ── pure: the normalization (lower-case host, default port, #fragment, trailing slash; the query stays) ──
    server(auto=True); ctx, pg = launch(b)
    r = pg.evaluate("[normUrl('https://Example.com:443/a/?x=1#f'), normUrl('http://example.com:80/'), normUrl('https://example.com/a?x=2'), normUrl('javascript:alert(1)'), normUrl('https://example.com:8443/a')]")
    check('normUrl: host/port/fragment/trailing slash normalised, query kept, non-http refused', r == ['https://example.com/a?x=1', 'http://example.com', 'https://example.com/a?x=2', '', 'https://example.com:8443/a'], r)
    r = pg.evaluate("renderMarkdown('[a](https://x.example/p) ![i](https://x.example/i.png)', [{n:1,url:'https://x.example/p'}], true)")
    check('renderMarkdown(tainted): allowed link kept, image → alt text only', r.count('<a ') == 1 and 'img-link' not in r and '>i<' not in r and 'i' in r, r)
    ctx.close()
    # ── live: a web tool_result makes the turn tainted at once; after the turn there is no server flag, the tools[] still say so ──
    def turn(tool=True, meta=None, text=BODY, items=None):
        server(auto=True); ctx, pg = launch(b); put('/pro/set', dict({'atTools': WEB if tool else None, 'atFresh': 'ok' if tool else None}, **(meta or {})))
        script(items or ([S(call(id='m1', q='뉴스'), .2), S(result(id='m1', sources=SRC), .3)] if tool else []) + [T(text, .4)], SRC if tool else []); send(pg); settle(pg, 12000)
        put('/pro/set', {'atTools': None, 'atFresh': None, 'atTainted': None}); return ctx, pg
    ctx, pg = turn()
    check('live+tainted: only source URLs are links (fragment/default port/slash ignored; others are text)', links(pg) == ['https://example.com/news/a?x=1', 'https://docs.example.org/p2'], links(pg))
    t = md_text(pg); check('live+tainted: the phishing link text and the image alt stay as text, nothing is fetched', '피싱' in t and '로고' in t and pg.locator('.msg.assistant .md img').count() == 0 and 'evil.example' not in pg.evaluate("[...document.querySelectorAll('.msg.assistant .md')].pop().innerHTML"), t)
    check('live+tainted: the [1] citation capsule still links (it points into sources)', pg.locator('.msg.assistant .md sup.cite a').count() == 1)
    stored = pg.evaluate("Object.keys(localStorage).map(k=>localStorage.getItem(k)).join(' ')"); check('tainted flag is stored with the message', '"tainted":true' in stored, stored[:120])
    reload_last(pg)
    check('after reload (server message, tools[] has web_search, no flag): still tainted', links(pg) == ['https://example.com/news/a?x=1', 'https://docs.example.org/p2'], links(pg))
    ctx.close()
    # ── streaming itself is already restricted (before persisted arrives): the line is held by a long gap before the end ──
    server(auto=True); ctx, pg = launch(b)
    script([S(call(id='m2', q='뉴스'), .2), S(result(id='m2', sources=SRC), .3), T('앞부분 [피싱](https://evil.example/a) 입니다.\n\n', .2), T('뒷부분', 5)], SRC); send(pg); pg.wait_for_timeout(2500)
    mid = pg.evaluate("[...document.querySelectorAll('.msg.assistant .md a')].map(a=>a.getAttribute('href'))")
    check('while streaming (no persisted yet) the web tool_result already restricts links', mid == [] and '피싱' in md_text(pg), mid)
    settle(pg, 12000); ctx.close()
    # ── no web tool → ordinary rendering (all links, image link kept) ──
    ctx, pg = turn(tool=False, text='[링크](https://evil.example/x) ![그림](https://evil.example/i.png)')
    check('no web tool_result, no flag: links render as before (incl. the image link)', links(pg) == ['https://evil.example/x', 'https://evil.example/i.png'], links(pg)); ctx.close()
    # ── the server flag wins: false releases a web turn; true restricts a turn without any tool event ──
    ctx, pg = turn(meta={'atTainted': False}); check('persisted.tainted:false releases the guess', 'https://evil.example/login?u=1' in links(pg), links(pg)); ctx.close()
    ctx, pg = turn(tool=False, meta={'atTainted': True}, text='[링크](https://evil.example/x)'); check('persisted.tainted:true restricts even without a web tool_result', links(pg) == [], links(pg))
    reload_last(pg); check('…and after a reload (metadata.tainted)', links(pg) == [] and '링크' in md_text(pg), links(pg)); ctx.close()
    # ── stop: a stopped web turn keeps the restriction ──
    server(auto=True); ctx, pg = launch(b)
    script([S({'message_id': 'msg_tl_stop', 'thread_id': 't'}, 0, name='eve.meta'), S(call(id='m3', q='뉴스'), .2), S(result(id='m3', sources=SRC), .2), T('중간 [피싱](https://evil.example/s)', .2), T('…', 8)], SRC); send(pg); pg.wait_for_timeout(1500); pg.click('#sendBtn'); pg.wait_for_timeout(900)
    check('stopped web turn: still no foreign link', pg.locator('.msg.assistant .md a[href*="evil"]').count() == 0 and pg.locator('.msg.assistant .stopped').count() == 1)
    ctx.close()
    check('no page errors', not pg.errs, pg.errs)
    done()
