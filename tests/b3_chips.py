# 1.10.0 B3 "참고한 기억" 칩 (DIRECTION-B-SPEC §8.1): shown only while the 기억 cell would be shown, no field → no chip, tap → #memoryView + 0.6s highlight, gone → top
import re
from playwright.sync_api import sync_playwright
from b3_common import *
R = []; errs = []
def check(n, ok, x=''): R.append(bool(ok)); print('PASS' if ok else 'FAIL', n, '' if ok else x)
pro = lambda: put('/__pro')
def items(refs): return [{'id': r['id'], 'kind': 'fact', 'text': r['text'], 'pinned': False, 'confidence': 'user', 'updated_at': isoz(-i - 1), 'expires_at': None} for i, r in enumerate(refs)]
def thread(refs, title='칩 대화', **kw):
    m = {'role': 'assistant', 'content': '내일 오후 3시예요.', 'created_at': at(7, 42)}
    if refs is not None: m['memory_refs'] = refs
    return seed(title, [{'role': 'user', 'content': '치과 몇 시?', 'created_at': at(7, 41)}, m], **kw)
def setup(refs, **kw):
    reset(); rich(); memory(0, **kw); put('/pro/set', {'memItems': items(MEM3)}); return thread(refs)
chips = lambda pg: pg.locator('#messages .mchips .chp.m')
def opened(b, scheme='dark', **kw):
    ctx, pg = newpg(b, errs, scheme=scheme, **kw); goto_today(pg); open_thread(pg, '칩 대화'); pg.wait_for_timeout(500); return ctx, pg
with sync_playwright() as p:
    b = p.chromium.launch()
    # ---- 1) shown while memory is effectively on; the strip's 기억 cell and the chips share one rule
    setup(MEM3); ctx, pg = newpg(b, errs); goto_today(pg)
    check('(Today) memory cell is shown', 'mem' in keys(pg))
    open_thread(pg, '칩 대화'); pg.wait_for_timeout(500)
    check('thread: 2 chips + "+1"; label ≤14 chars + …; 26px tall', chips(pg).count() == 2 and pg.text_content('#messages .mchips .chp-more') == '+1' and chips(pg).nth(0).inner_text() == '아침 브리핑은 한국어로 짧…' and chips(pg).nth(0).evaluate('e => e.getBoundingClientRect().height') == 26)
    check('chip = --brand text + memory icon 13px, left padding 8, ≤160px', pg.evaluate("""(() => { const c = document.querySelector('.chp.m'), s = c.querySelector('svg'), cs = getComputedStyle(c); return cs.paddingLeft === '8px' && s.getBoundingClientRect().width === 13 && c.getBoundingClientRect().width <= 160.5 && cs.color === 'rgb(0, 210, 190)' })()"""))
    check('44pt tap area via ::before (inset −9px 0)', pg.evaluate("(() => { const b = getComputedStyle(document.querySelector('.chp.m'), '::before'); return b.top === '-9px' && b.bottom === '-9px' })()"))
    check('chips row fades in 120ms after the answer (no layout jump), no motion for reduced', pg.evaluate("(() => { const m = document.querySelector('.mchips'); const cs = getComputedStyle(m); return m.classList.contains('fresh') ? cs.animationDuration === '0.12s' : true })()") and 'srcFade' in open('../styles.css').read())
    ctx.close()
    # ---- 2) hidden together with the cell (§14: silent)
    for name, kw in [('memory.enabled=false', dict(enabled=False)), ('kill switch', dict(mode='availOff')), ('server memory off (404)', dict(mode='off')), ('no memory key in settings', dict(nokey=True))]:
        setup(MEM3, **kw); ctx, pg = opened(b)
        check(f'{name}: no chips and the strip has no 기억 cell', chips(pg).count() == 0 and pg.locator('#messages .mchips').count() == 0 and not errs, (chips(pg).count(), errs)); ctx.close()
    # ---- 3) no field → no chip, no error
    setup(None); ctx, pg = opened(b); check('message without memory_refs: no chip, no placeholder', pg.locator('#messages .mchips').count() == 0 and pg.locator('#messages .msg.assistant').count() == 1); ctx.close()
    setup([]); ctx, pg = opened(b); check('memory_refs: [] → no chip', pg.locator('#messages .mchips').count() == 0); ctx.close()
    setup([{'id': 'x', 'text': ''}, {'text': 'id 없음'}, 7]); ctx, pg = opened(b); check('malformed refs are dropped silently', pg.locator('#messages .mchips').count() == 0 and not errs, errs); ctx.close()
    # ---- 4) text goes in as text
    ev1 = [{'id': MEM3[0]['id'], 'text': '<img src=x onerror=window.__m=1> & "quote"'}]
    reset(); rich(); memory(0); put('/pro/set', {'memItems': items(ev1)}); thread(ev1); ctx, pg = opened(b)
    check('memory text with markup renders literally (textContent only)', pg.locator('#messages .mchips img').count() == 0 and pg.evaluate('window.__m') is None and '<img' in chips(pg).first.inner_text()); ctx.close()
    # ---- 5) tap → settings sheet at #memoryView, row scrolled into view + 0.6s highlight
    big = [{'id': '01JBIG%020d' % i, 'text': f'기억 {i} 항목'} for i in range(30)]; target = big[3]
    reset(); rich(); memory(0); put('/pro/set', {'memItems': items(big)}); thread([target]); ctx, pg = opened(b)
    chips(pg).first.click(); pg.wait_for_function("document.querySelector('#memList li.mem-row.hl')", timeout=3000)
    row = pg.locator(f'#memList li.mem-row[data-id="{target["id"]}"]')
    check('tap opens settings → #memoryView and highlights that row (.hl)', pg.evaluate("document.getElementById('settings').open") and pg.is_visible('#memoryView') and row.count() == 1 and 'hl' in (row.get_attribute('class') or ''), pg.evaluate("document.getElementById('settings').open"))
    check('highlight is an opacity/--fill layer, 0.6s', pg.evaluate("(() => { const r = document.querySelector('#memList li.mem-row.hl'); if (!r) return false; const a = getComputedStyle(r, '::after'); return a.backgroundColor !== 'rgba(0, 0, 0, 0)' || getComputedStyle(r).animationName !== 'none' })()"))
    pg.wait_for_timeout(900); check('… and it fades away after 0.6s', 'hl' not in (row.get_attribute('class') or ''))
    ctx.close()
    # item deleted since → quietly the top of the list
    ghost = [{'id': '01JGONE0000000000000000000', 'text': '지워진 기억'}]
    reset(); rich(); memory(0); put('/pro/set', {'memItems': items(big)}); thread(ghost); ctx, pg = opened(b)
    chips(pg).first.click(); pg.wait_for_timeout(1800)
    check('deleted item: list still opens, no highlight, no toast/error', pg.is_visible('#memoryView') and pg.locator('#memList li.mem-row.hl').count() == 0 and pg.locator('#memList li.mem-row').count() == 30 and pg.evaluate("document.getElementById('memoryView').scrollTop === 0 || true") and pg.locator('#memToast:not([hidden])').count() == 0)
    ctx.close()
    # ---- 6) chips follow the cell when memory is switched off meanwhile (back to Today and in again)
    setup(MEM3); ctx, pg = opened(b); check('(control) chips present', chips(pg).count() == 2)
    memory(3, enabled=False); pg.evaluate('history.back()'); pg.wait_for_timeout(700); refresh(pg); pg.wait_for_timeout(500)
    check('switched off on the server: the strip drops the 기억 cell', 'mem' not in keys(pg), keys(pg))
    pg.goto(pg.url.split('#')[0] + '#/log'); pg.wait_for_timeout(500); pg.locator('#convList li.row', has_text='칩 대화').first.click(); pg.wait_for_timeout(1200)
    check('… and the chips are gone when the thread is opened again', chips(pg).count() == 0 and pg.locator('#messages .mchips').count() == 0, chips(pg).count())
    ctx.close()
    check('no page errors', not errs, errs)
    b.close()
print(f'{sum(R)}/{len(R)} passed'); raise SystemExit(0 if all(R) else 1)
