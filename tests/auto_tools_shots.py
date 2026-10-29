# AUTO-TOOLS-SPEC §14 · 10 required screenshots, 390px dark + light, from the real app against tests/mock.py:
#   python auto_tools_shots.py <outdir>      (EVE_PORT = mock port)
from at_common import *
import sys
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
SRC5 = [src(1, 'weather.go.kr', title='서울 주간 날씨 예보: 화요일부터 기온 뚝', published='2026-10-27'), src(2, 'news.example.com', title='기상청 중기예보 해설'), src(3, 'blog.example.org', title='이번 주 서울 옷차림 가이드'), src(4, 'docs.example.net', title='미세먼지 전망'), src(5, 'b.example.com', title='Korea weather news')]
ANS = '이번 주 서울은 화요일부터 기온이 크게 떨어져요[1][2]. 수요일에는 비 소식이 있어요[3].'
LONGQ = '서울 강남구 역삼동 근처에서 오늘 저녁에 문을 연 비건 레스토랑과 주차 가능한 카페 추천 목록과 영업시간 정리'
def shot(pg, name, sch): pg.screenshot(path=f'{out}/{name}-{sch}.png')
def step(sch, init='', auto=True, fn=None):
    server(auto=auto); ctx, pg = launch(b, scheme=sch, init=init, mobile=True); fn(pg); ctx.close()
with sync_playwright() as p:
    b = p.chromium.launch()
    for sch in ('dark', 'light'):
        # 1 searching (auto, with the hint)  2 long query  3 reading 5 sources
        def f1(pg):
            script([S(call(q='서울 주간 날씨'), .2), S(result(sources=SRC5, count=5), 2.2), T(ANS, 9)], SRC5); send(pg, '이번 주 서울 날씨 어때?'); pg.wait_for_timeout(1400); shot(pg, '01-searching-auto-hint', sch)
            pg.wait_for_function("()=>document.querySelector('.tstat')?.textContent.includes('출처 5개')", timeout=8000); pg.wait_for_timeout(500); shot(pg, '03-reading-5-sources', sch)
        step(sch, fn=f1)
        def f2(pg):
            script([S(call(q=LONGQ), .2), S(result(sources=SRC5), 9), T(ANS, .1)], SRC5); send(pg, '맛집 알려줘'); pg.wait_for_timeout(1500); shot(pg, '02-searching-long-query', sch)
        step(sch, fn=f2)
        # 4 done (chips + citation)  7 sheet auto
        def f4(pg):
            script([S(call(q='서울 주간 날씨'), .2), S(result(sources=SRC5, count=5), .4), T(ANS, .4)], SRC5); send(pg, '이번 주 서울 날씨 어때?'); settle(pg, 12000); pg.wait_for_timeout(400); shot(pg, '04-done-chips-cite', sch)
            pg.locator('.msg.assistant .sources .sc').first.click(); pg.wait_for_timeout(700); shot(pg, '07-sources-sheet-auto-tq', sch)
        step(sch, fn=f4)
        def f7(pg):
            script([S(call(q='서울 주간 날씨', by='user'), .2), S(result(sources=SRC5, count=5), .4), T(ANS, .4)], SRC5); send(pg, '이번 주 서울 날씨 어때?'); settle(pg, 12000)
            pg.locator('.msg.assistant .sources .sc').first.click(); pg.wait_for_timeout(700); shot(pg, '07-sources-sheet-user-tq', sch)
        step(sch, fn=f7)
        # 5 no result  6 timeout
        def f5(pg):
            script([S(call(q='존재하지 않는 키워드 qzxv'), .2), S(result(status='ok', sources=[]), .4), T('검색에서는 찾지 못했어요. 제가 아는 범위에서 말씀드릴게요.', .4)]); send(pg, 'qzxv가 뭐야?'); settle(pg, 12000); pg.wait_for_timeout(400); shot(pg, '05-no-result-note', sch)
        step(sch, fn=f5)
        def f6(pg):
            script([S(call(q='오늘 환율'), .2), S(result(status='timeout'), .4), T('지금까지 확인한 내용으로 말씀드릴게요.', .4)]); send(pg, '오늘 환율 알려줘'); settle(pg, 12000); pg.wait_for_timeout(400); shot(pg, '06-timeout-note', sch)
        step(sch, fn=f6)
        # 8 + menu, 3 modes (design preview: force gate open) and the + button in each state
        def f8(pg):
            openm = lambda: (pg.click('#plusBtn'), pg.wait_for_timeout(450))
            openm(); shot(pg, '08-plus-menu-3-modes', sch); pg.keyboard.press('Escape'); pg.wait_for_timeout(300)
            for m in ('auto', 'force', 'off'):
                openm(); pg.click(f'#plusMenu .mode[data-mode={m}]'); pg.wait_for_timeout(2600); pg.locator('#composer').screenshot(path=f'{out}/08-plus-button-{m}-{sch}.png')
            openm(); shot(pg, '08-plus-menu-off-checked', sch)
        step(sch, init="window.__eveFlags={forceMode:true};", fn=f8)
        # 9 legacy single-row menu (server without auto)
        def f9(pg): pg.click('#plusBtn'); pg.wait_for_timeout(450); shot(pg, '09-menu-legacy-single-row', sch)
        step(sch, auto=False, fn=f9)
        # 10 right after stop
        def f10(pg):
            script([S({'message_id': 'msg_at_stop', 'thread_id': 't'}, 0, name='eve.meta'), S(call(q='서울 주간 날씨'), .2), S(result(sources=SRC5), 20), T(ANS, .1)], SRC5); send(pg, '이번 주 서울 날씨 어때?'); pg.wait_for_timeout(1500)
            pg.click('#sendBtn'); pg.wait_for_timeout(700); shot(pg, '10-after-stop', sch)
        step(sch, fn=f10)
    b.close()
print('shots →', out)
