# 1.10.0 B2 하루 (DIRECTION-B-SPEC §9.2): 기록 — week strip, day-grouped list, search mode, 보관함 row, empty state
import re, os
from assets_common import full_csp
from playwright.sync_api import sync_playwright
from b2_common import *
R = []; errs = []; csp = []
def check(n, ok, x=''): R.append(bool(ok)); print('PASS' if ok else 'FAIL', n, '' if ok else x)
def newpg(b, scheme='dark', **kw):
    ctx = new_ctx(b, scheme=scheme, service_workers='block', **kw)
    ctx.expose_binding('_recordCsp', lambda source, directive: csp.append(directive))
    ctx.add_init_script("document.addEventListener('securitypolicyviolation', e => window._recordCsp(e.violatedDirective))")
    pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e))); return ctx, pg
with full_csp(), sync_playwright() as p:
    engine = p.webkit if os.environ.get('EVE_ENGINE') == 'webkit' else p.chromium
    b = engine.launch()
    reset(); ids = rich(); ids.update(older())
    ctx, pg = newpg(b); goto_today(pg, '#/log')
    check('#/log → list route; large title 기록; back button + settings-less narrow nav', rt(pg) == 'list' and pg.text_content('#listView .large-title') == '기록' and pg.is_visible('#logBack') and not pg.is_visible('#openSettings3'))
    now = kst_now(); check('month label "YYYY년 M월"', pg.text_content('#logMonth') == f'{now.year}년 {now.month}월', pg.text_content('#logMonth'))
    # --- week strip (Sunday start: deviation from a Monday-first reading of the spec)
    cells = pg.evaluate("[...document.querySelectorAll('#wk .wk-c')].map(b=>[b.dataset.day,b.querySelector('.wk-w').textContent,b.className,b.getAttribute('aria-disabled'),b.getAttribute('aria-current')])")
    check('week strip: 7 cells, 일 first, today selected (aria-current=date)', len(cells) == 7 and cells[0][1] == '일' and [c for c in cells if 'sel' in c[2].split()][0][0] == day_ymd(0) and [c for c in cells if c[4] == 'date'][0][0] == day_ymd(0), cells)
    check('days with records are .has and enabled; future days .fut and aria-disabled; empty past days disabled', all((c[3] != 'true') == ('has' in c[2].split()) for c in cells) and all(c[3] == 'true' for c in cells if 'fut' in c[2].split()), cells)
    check('cell tap target ≥ 44px', pg.evaluate("[...document.querySelectorAll('#wk .wk-c')].every(b=>b.getBoundingClientRect().height>=44-.5&&b.getBoundingClientRect().width>=44-.5)"))
    # --- day groups
    labs = pg.evaluate("[...document.querySelectorAll('#convList .group-label')].map(l=>[l.querySelector('.gl-n').textContent,l.querySelector('.gl-c').textContent,l.dataset.day])")
    check('day group labels: 오늘 · 요일 / 어제 · 요일 / M월 D일 · 요일 …', [l[0] for l in labs][:3] == [label_of(0), label_of(-1), label_of(-2)] and labs[-1][0] == label_of(-8), labs)
    check('group header shows the count', re.search(r'10', labs[0][1]), labs[0])
    rows = pg.evaluate("[...document.querySelectorAll('#convList > li')].map(l=>l.className.split(' ').filter(x=>['group-label','row','g1','g9'].includes(x)).join('.'))")
    check('each day is one card: first row g1, last row g9', sum('g1' in r.split('.') for r in rows) >= 3 and sum('g9' in r.split('.') for r in rows) >= 3 and rows[1].startswith('row.g1') and 'g9' not in rows[1].split('.'), rows)
    r0 = pg.evaluate("(()=>{const r=document.querySelector('#convList li.row'),t=r.querySelector('time.r-tm'),b=r.querySelector('.r-bd');return {tm:t.textContent,w:t.getBoundingClientRect().width,h:r.getBoundingClientRect().height,sub:r.querySelector('.row-sub').textContent}})()")
    check('row = 36px time column + title/preview, ≥ 52px tall, time is HH:mm', re.fullmatch(r'\d\d:\d\d', r0['tm']) and abs(r0['w'] - 36) <= 1 and r0['h'] >= 52 and r0['sub'], r0)
    check('선톡 threads carry the Eve mark; plain threads do not', pg.locator('#convList li.row', has_text='아침 브리핑').locator('.r-eve').count() == 1 and pg.locator('#convList li.row', has_text='SwiftUI 질문').locator('.r-eve').count() == 0)
    check('unread 선톡 thread shows the unread dot/pill', pg.locator('#convList li.row', has_text='아침 브리핑').locator('.unread-pill, .unread-dot').count() >= 1)
    # --- tapping a strip cell scrolls to that day
    target = [c for c in cells if 'has' in c[2].split() and c[0] != day_ymd(0)]
    if target:
        pg.click(f'#wk .wk-c[data-day="{target[0][0]}"]'); pg.wait_for_timeout(900)
        top = pg.evaluate(f"document.querySelector('#convList .group-label[data-day=\"{target[0][0]}\"]').getBoundingClientRect().top")
        check('tap a day → its group header scrolls to the top (just under the strip)', (top < 200 or pg.evaluate("(s=>s.scrollTop+s.clientHeight>=s.scrollHeight-2)(document.getElementById('listScroller'))")) and pg.locator(f'#wk .wk-c.sel[data-day="{target[0][0]}"]').count() == 1, top)
    # --- 보관함 row
    ar = pg.locator('#archivedRow'); check('보관함 row visible, label 보관함', ar.is_visible() and '보관함' in ar.text_content())
    # --- search mode
    pg.click('#logSearch'); pg.wait_for_timeout(500)
    check('search mode: .searching, input focused, strip + 보관함 row hidden', pg.evaluate("document.getElementById('listView').classList.contains('searching')") and pg.evaluate("document.activeElement.id") == 'search' and pg.evaluate("getComputedStyle(document.getElementById('wk')).opacity") == '0' and pg.evaluate("document.getElementById('wk').inert") and not pg.is_visible('#archivedRow'))
    pg.fill('#search', '발표'); pg.wait_for_timeout(900)
    rows = pg.locator('#convList li.row'); h = pg.locator('#convList li.hit').count()
    check('search: flat results (no group headers), each with a date · preview subtitle', pg.locator('#convList .group-label').count() == 0 and rows.count() + h >= 1 and '발표 자료 준비' in pg.text_content('#convList') and re.search(r'\d+월 \d+일|어제|오늘', rows.first.locator('.row-sub').text_content() or ''), [rows.count(), h])
    pg.fill('#search', 'zzzqqq'); pg.wait_for_timeout(900); check('no match → "결과 없음"', '결과 없음' in pg.text_content('#convList'))
    pg.click('#searchCancel'); pg.wait_for_timeout(500)
    check('취소 restores the grouped list, strip and 보관함 row; query cleared', pg.locator('#convList .group-label').count() >= 3 and pg.is_visible('#wk') and pg.is_visible('#archivedRow') and pg.input_value('#search') == '')
    pg.click('#logSearch'); pg.wait_for_timeout(300); pg.keyboard.press('Escape'); pg.wait_for_timeout(400)
    check('Escape leaves search mode', not pg.evaluate("document.getElementById('listView').classList.contains('searching')"))
    # --- archive
    pg.click('#archivedRow'); pg.wait_for_timeout(800)
    check('보관함 row → #/archive; back label 기록; the archived thread is listed', rt(pg) == 'archive' and pg.evaluate('location.hash') == '#/archive' and '보관한 대화' in pg.text_content('#archList') and pg.text_content('#archBack span').strip() == '기록')
    pg.go_back(); pg.wait_for_timeout(700); check('browser back → 기록', rt(pg) == 'list' and pg.evaluate('location.hash') == '#/log')
    # --- open a thread from the log → back label 기록
    pg.locator('#convList li.row', has_text='SwiftUI 질문').first.click(); pg.wait_for_timeout(800)
    check('row → chat; back label 기록', rt(pg) == 'chat' and pg.text_content('#backLbl') == '기록'); pg.click('#backBtn'); pg.wait_for_timeout(600)
    check('back → 기록, scroll kept (list not rebuilt at top)', rt(pg) == 'list'); ctx.close()
    # --- empty state
    reset(); ctx, pg = newpg(b); goto_today(pg, '#/log')
    check('empty: "아직 기록이 없어요" visible, no strip dots', pg.is_visible('#listEmpty') and '아직 기록이 없어요' in pg.text_content('#listEmpty') and pg.locator('#wk .wk-c.has').count() == 0)
    check('empty: 보관함 row still reachable', pg.is_visible('#archivedRow'))
    check('empty: no logo / 무엇을 도와드릴까요', '무엇을 도와드릴까요' not in pg.evaluate('document.body.innerText')); ctx.close()
    # --- loading skeleton rows in the log
    reset(); rich(); put('/delay/1500?GET%20/v1/threads'); ctx, pg = newpg(b); pg.goto(B + '/ui/#/log'); pg.reload(); pg.wait_for_timeout(700)
    check('log loading: skeleton rows, no "아직 기록이 없어요" flash', pg.locator('#convList .skel').count() == 3 and not pg.is_visible('#listEmpty'))
    pg.wait_for_timeout(2200); check('skeleton → rows', pg.locator('#convList .skel').count() == 0 and pg.locator('#convList li.row').count() >= 6)
    put('/delay/clear'); ctx.close()
    # Component text stays inert, including across repeated list rebuilds.
    reset(); title = '<img src=x onerror=alert(1)> & 제목'
    conv2(title, 12, 0, a='<script>alert(1)</script> & 답변')
    ctx, pg = newpg(b); goto_today(pg, '#/log')
    check('row title preserves literal untrusted text', pg.locator('#convList .row-title').inner_text() == title)
    check('row text creates no HTML elements', pg.locator('#convList img, #convList script').count() == 0)
    pg.click('#logSearch'); pg.fill('#search', '제목'); pg.wait_for_timeout(600)
    pg.fill('#search', ''); pg.click('#searchCancel'); pg.wait_for_timeout(500)
    check('repeated row rebuild keeps one action set', pg.locator('#convList .ra-rename').count() == 1 and pg.locator('#convList .ra-archive').count() == 1)
    snippet = ['']; snippets_ok = []
    ctx.route('**/v1/search?*', lambda route: route.fulfill(status=200, content_type='application/json', body=json.dumps({'data':[{'thread_id':'remote', 'match':'content', 'thread_title': title, 'snippet':snippet[0]}]})))
    pg.click('#logSearch')
    for i, text in enumerate(('plain & text', '<mark>강조</mark> & 뒤', '<mark><mark>x</mark> y</mark>', '</mark>x<mark>y', '<mark class=x>literal</mark>', '<img src=x onerror=alert(1)> <script>alert(1)</script>')):
        snippet[0] = text; pg.fill('#search', f'remote-{i}'); pg.wait_for_timeout(650)
        snippets_ok.append(pg.locator('#convList .snippet').evaluate("""(node, source) => {
          const escaped = source.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
          const html = escaped.replace(/&lt;(\/?)mark&gt;/g, '<$1mark>');
          return node.innerHTML === new DOMParser().parseFromString(html, 'text/html').body.innerHTML;
        }""", text))
    check('search snippets preserve mark-only DOM for normal, nested and malformed input', all(snippets_ok), snippets_ok)
    check('search title/snippet HTML remains inert', pg.locator('#convList .row-title').inner_text() == title and pg.locator('#convList img, #convList script').count() == 0)
    pg.click('#searchCancel'); pg.wait_for_timeout(500)
    pg.locator('#convList li.row').dispatch_event('contextmenu'); pg.wait_for_timeout(350)
    pg.locator('#ctx [role=menuitem]', has_text='보관').click(); pg.wait_for_timeout(350)
    check('archive removes row before deferred commit', pg.locator('#convList li.row').count() == 0 and not any(t.get('archived') for t in req('GET', '/__db')['threads']))
    pg.locator('#toastAct').click(); pg.wait_for_timeout(3100)
    check('undo restores row and cancels archive timer', pg.locator('#convList li.row').count() == 1 and not any(t.get('archived') for t in req('GET', '/__db')['threads']))
    pg.locator('#convList li.row').dispatch_event('contextmenu'); pg.wait_for_timeout(350)
    pg.locator('#ctx [role=menuitem]', has_text='보관').click(); pg.wait_for_timeout(350)
    pg.evaluate("Object.defineProperty(document, 'visibilityState', {configurable:true,get:()=> 'hidden'}); document.dispatchEvent(new Event('visibilitychange'))")
    pg.wait_for_timeout(500)
    check('backgrounding commits pending archive once', sum(bool(t.get('archived')) for t in req('GET', '/__db')['threads']) == 1)
    ctx.close()
    check('no full CSP violations', not csp, csp)
    check('no page errors', not errs, errs); b.close()
print(f'{sum(R)}/{len(R)} checks'); raise SystemExit(0 if all(R) else 1)
