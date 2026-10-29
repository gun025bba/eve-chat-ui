# B5 memory first-run intro sheet #memIntro (design 824725d) e2e against mock.py — flag 'eve.flag.memory'
import json, os, urllib.request
from playwright.sync_api import sync_playwright
M = 'http://127.0.0.1:' + os.environ.get('EVE_PORT', '8765'); B = M
def req(method, path, body=None):
    r = urllib.request.Request(M + path, method=method, data=json.dumps(body).encode() if body is not None else None, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(r) as f: t = f.read(); return json.loads(t) if t else None
put = lambda p, body=None: req('PUT', p, body)
pro = lambda: req('PUT', '/__pro')
R = []
def check(name, ok, extra=''): R.append(bool(ok)); print(('PASS' if ok else 'FAIL'), name, extra)
SET = "localStorage.setItem('llmchat.settings',JSON.stringify({base:'',model:'mlx-community/Qwen3-30B-A3B-4bit',system:'',showThink:false,noThink:false}));"
SYS = {'proactive_available': True, 'tools_available': True, 'memory_read_only': False, 'memory_available': True}
PS = lambda mem=True, ui=None: dict({'proactive': {'enabled': False, 'quiet_hours': {'start': '22:00', 'end': '08:00'}, 'memory_read': False}, 'memory': {'enabled': mem}}, **({'ui': ui} if ui is not None else {}))
TITLE, SUB = '이제 Eve가 기억해요', '대화에 도움이 되는 걸 기억해 다음 대화에 참고해요'
BUL = ['이름·선호·할 일처럼 대화에 도움이 되는 것만 기억해요', '저장하기 전에 항상 먼저 물어봐요', '설정 › 메모리에서 보고, 지우고, 내보낼 수 있어요']
errs = []
def setup(**kw):
    put('/auth/on'); put('/persist/on'); put('/db/reset'); put('/fail/clear'); put('/pro/reset')
    put('/pro/set', dict({'settings': PS(), 'system': SYS}, **kw))
uiPatches = lambda: [x['b'] for x in pro()['bodies'] if x['p'] == '/v1/settings' and x['m'] == 'PATCH' and 'ui' in (x['b'] or {})]
memPatches = lambda: [x['b'] for x in pro()['bodies'] if x['p'] == '/v1/settings' and x['m'] == 'PATCH' and 'memory' in (x['b'] or {})]
with sync_playwright() as p:
    b = p.chromium.launch()
    def launch(flag=True, local_seen=False, wait=2200, extra='', motion='no-preference'):
        ctx = b.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark', reduced_motion=motion)
        init = "if(!sessionStorage.getItem('s')){sessionStorage.setItem('s',1);" + SET + ("localStorage.setItem('eve.flag.memory','1');" if flag else '') + ("localStorage.setItem('eve.mem.introSeen','1');" if local_seen else '') + "}" + extra
        ctx.add_init_script(init)
        pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto(B + '/ui/#/'); pg.wait_for_timeout(wait)
        return ctx, pg
    shown = lambda pg: pg.is_visible('#memIntro')
    seenLocal = lambda pg: pg.evaluate("localStorage.getItem('eve.mem.introSeen')")

    # 1) flag off → nothing
    setup(); ctx, pg = launch(flag=False)
    check('version 1.10.2', pg.evaluate('__app.version') == '1.10.2' and 'v1.10.2' in pg.text_content('#appVersion'))
    check('flag off → no sheet, no seen', not shown(pg) and seenLocal(pg) is None and not uiPatches()); ctx.close()

    # 2) memory.enabled false → no sheet, no seen
    setup(settings=PS(False)); ctx, pg = launch()
    check('memory.enabled=false → no sheet, no seen', not shown(pg) and seenLocal(pg) is None and not uiPatches()); ctx.close()
    setup(memNoKey=True); ctx, pg = launch()
    check('memory key missing (off) → no sheet', not shown(pg) and seenLocal(pg) is None); ctx.close()

    # 3) memory_available=false → no sheet AND no seen (local or server)
    setup(system=dict(SYS, memory_available=False)); ctx, pg = launch()
    check('memory_available=false → no sheet, no seen saved', not shown(pg) and seenLocal(pg) is None and not uiPatches()); ctx.close()

    # 4) settings unreadable → deferred, no seen; next launch shows
    setup(settingsDrop=True); ctx, pg = launch()
    check('settings unreadable → no sheet, no seen', not shown(pg) and seenLocal(pg) is None and not uiPatches())
    put('/pro/set', {'settingsDrop': False}); pg.evaluate("history.pushState({route:'chat'},'','#/c/x')"); pg.evaluate('history.back()'); pg.wait_for_timeout(1200)
    check('… still deferred for the rest of this launch', not shown(pg))
    pg.reload(); pg.wait_for_timeout(2200)
    check('… next launch shows it', shown(pg)); ctx.close()

    # 5) not connected (local mode: persistence off) → no sheet
    setup(); put('/persist/off'); ctx, pg = launch()
    check('not connected to server → no sheet, no seen', pg.evaluate('__app.state().mode') != 'server' and not shown(pg) and seenLocal(pg) is None); ctx.close()

    # 6) another sheet open → no sheet, no seen
    setup(); ctx, pg = launch(extra="addEventListener('DOMContentLoaded',()=>{document.getElementById('renameSheet').hidden=false});")
    check('other sheet open → no sheet, no seen', pg.is_visible('#renameSheet') and not shown(pg) and seenLocal(pg) is None); ctx.close()
    setup(); ctx, pg = launch(wait=0); pg.wait_for_function("window.__app && __app.state().mode==='server'"); pg.evaluate("document.getElementById('openSettings').click()"); pg.wait_for_timeout(1500)
    check('settings dialog open → no sheet', not shown(pg) and seenLocal(pg) is None); ctx.close()

    # 7) already seen: local OR server
    setup(); ctx, pg = launch(local_seen=True)
    check('local eve.mem.introSeen=1 → no sheet', not shown(pg)); ctx.close()
    setup(settings=PS(True, {'memory_intro_seen': True})); ctx, pg = launch()
    check('server ui.memory_intro_seen=true → no sheet (local unset)', not shown(pg) and seenLocal(pg) is None); ctx.close()

    # 8) happy path: memory_available missing (→ true) + enabled, 600ms after the list
    setup(uiKey=True, system={k: v for k, v in SYS.items() if k != 'memory_available'}); ctx, pg = launch(wait=0)
    pg.wait_for_function("window.__app && __app.state().mode==='server'"); t0 = pg.evaluate('performance.now()')
    pg.wait_for_selector('#memIntro', state='visible', timeout=4000); dt = pg.evaluate('performance.now()') - t0
    check('appears ≥600ms after the thread list (server) renders, on Today (the home route)', dt >= 550 and pg.evaluate("document.getElementById('app').dataset.route") == 'today', round(dt))
    pg.wait_for_timeout(500)
    check('copy verbatim', pg.text_content('#memIntroTitle') == TITLE and pg.text_content('#memIntroBody') == SUB and [pg.locator('.mem-intro-list li').nth(i).inner_text().strip() for i in range(3)] == BUL and pg.text_content('#memIntroOk') == '좋아요' and pg.text_content('#memIntroSettings') == '설정에서 끄기')
    a = pg.evaluate("(()=>{const e=document.getElementById('memIntro');return [e.getAttribute('role'),e.getAttribute('aria-modal'),e.getAttribute('aria-labelledby'),e.getAttribute('aria-describedby'),document.querySelector('.mem-intro-list').getAttribute('role'),[...e.querySelectorAll('svg')].every(s=>s.getAttribute('aria-hidden')==='true')]})()")
    check('role=dialog aria-modal labelled/described, list role, icons aria-hidden', a == ['dialog', 'true', 'memIntroTitle', 'memIntroBody', 'list', True], a)
    check('focus on title', pg.evaluate("document.activeElement.id") == 'memIntroTitle')
    check('seen saved on show: localStorage', seenLocal(pg) == '1')
    check('seen saved on show: PATCH /v1/settings {ui:{memory_intro_seen:true}} accepted (200) → server flag set (CSRF gate passed)', pro()['settings'].get('ui') == {'memory_intro_seen': True}, pro()['settings'].get('ui'))
    check('… sheet stays, no toast, no error', shown(pg) and pg.evaluate("!document.getElementById('toast').classList.contains('show')") and not errs)
    g = pg.evaluate("(()=>{const r=id=>document.getElementById(id).getBoundingClientRect();const s=getComputedStyle(document.getElementById('memIntro'));return [r('memIntroOk').height,r('memIntroSettings').height,Math.round(r('memIntro').height),s.paddingBottom,getComputedStyle(document.getElementById('memIntroOk')).backgroundColor]})()")
    check('buttons ≥44pt (좋아요 50), medium height, bottom padding ≥16, filled --accent-fill', g[0] >= 50 and g[1] >= 44 and 0.5 * 844 <= g[2] <= 0.9 * 844 and float(g[3][:-2]) >= 16 and g[4] == 'rgb(10, 111, 232)', g)
    ids = []
    for _ in range(4): pg.keyboard.press('Tab'); ids.append(pg.evaluate('document.activeElement.id'))
    pg.keyboard.press('Shift+Tab'); ids.append(pg.evaluate('document.activeElement.id'))
    check('focus trapped inside', set(ids) <= {'memIntroOk', 'memIntroSettings'}, ids)
    pg.click('#memIntroOk'); pg.wait_for_timeout(600)
    check('좋아요 → closes only (no memory PATCH)', not shown(pg) and not memPatches() and pg.is_hidden('#memIntroScrim'))
    check('focus restored (not stuck on hidden sheet)', pg.evaluate("!document.getElementById('memIntro').contains(document.activeElement)"))
    pg.reload(); pg.wait_for_timeout(2200)
    check('never shown again after seen', not shown(pg)); ctx.close()

    # 9) Escape closes + restores previous focus; server-side seen respected with server key accepted
    setup(uiKey=True); ctx, pg = launch(wait=0); pg.wait_for_function("window.__app && __app.state().mode==='server'")
    pg.focus('#openLog'); pg.wait_for_selector('#memIntro', state='visible', timeout=4000); pg.wait_for_timeout(400)
    pg.keyboard.press('Escape'); pg.wait_for_timeout(600)
    check('Escape → closes, focus back to previous element', not shown(pg) and pg.evaluate('document.activeElement.id') == 'openLog' and not memPatches())
    check('server key stored when accepted', pro()['settings'].get('ui') == {'memory_intro_seen': True})
    ctx.close(); ctx, pg = launch()
    check('other device (fresh localStorage) + server seen → not shown', not shown(pg) and seenLocal(pg) is None); ctx.close()

    # 10) swipe down closes
    setup(); ctx, pg = launch(); pg.wait_for_timeout(300)
    bx = pg.locator('#memIntroTitle').bounding_box(); x, y = bx['x'] + 20, bx['y'] + 5
    pg.mouse.move(x, y); pg.mouse.down(); pg.mouse.move(x, y + 60, steps=4); pg.mouse.move(x, y + 200, steps=4); pg.mouse.up(); pg.wait_for_timeout(600)
    check('swipe down → closes only', not shown(pg) and not memPatches()); ctx.close()

    # 11) 설정에서 끄기 → Settings › 메모리, focus toggle, memory NOT turned off
    setup(); ctx, pg = launch(); pg.wait_for_timeout(300)
    pg.click('#memIntroSettings'); pg.wait_for_timeout(1800)
    check('설정에서 끄기 → settings open, focus on 메모리 toggle', not shown(pg) and pg.evaluate("document.getElementById('settings').open") and pg.evaluate('document.activeElement.id') == 'sMemory')
    check('… memory not turned off (still checked, no memory PATCH)', pg.is_checked('#sMemory') and not memPatches() and pro()['settings']['memory'] == {'enabled': True}); ctx.close()

    # 12) reduced motion → opacity only
    setup(); ctx, pg = launch(motion='reduce'); pg.wait_for_timeout(300)
    rm = pg.evaluate("(()=>{const s=getComputedStyle(document.getElementById('memIntro'));return [s.transform,s.transitionProperty,s.opacity]})()")
    check('reduced motion → no transform, opacity transition only', shown(pg) and rm[0] == 'none' and rm[1] == 'opacity' and rm[2] == '1', rm); ctx.close()


    # 13) 1.10.2: localStorage is written ONLY after the server answered 200 to PATCH {ui:{memory_intro_seen:true}}
    attempts = lambda: len(uiPatches())
    toast_vis = lambda pg: pg.evaluate("(() => { const t = document.getElementById('toast'); return t && t.classList.contains('show') ? { text: t.innerText } : null })()")
    err_vis = lambda pg: pg.evaluate("(() => { const t = document.getElementById('memIntroErr'); if (!t.classList.contains('on') || getComputedStyle(t).opacity !== '1') return null; const r = t.getBoundingClientRect(), s = document.getElementById('memIntro').getBoundingClientRect(); const e = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2); return { text: t.innerText, role: t.getAttribute('role'), inSheet: r.top >= s.top && r.bottom <= s.bottom, onTop: !!e && t.contains(e) } })()")
    setup(); ctx, pg = launch(wait=0); pg.wait_for_function("window.__app && __app.state().mode==='server'"); pg.wait_for_selector('#memIntro', state='visible', timeout=4000); pg.wait_for_timeout(500)
    check('PATCH 400 at show: sheet stays, localStorage NOT written, no error shown yet', shown(pg) and seenLocal(pg) is None and attempts() == 1 and err_vis(pg) is None, (seenLocal(pg), attempts()))
    pg.evaluate("window.__g = () => { const e = document.getElementById('memIntroErr'), r = e.getBoundingClientRect(), cs = getComputedStyle(e); return { sheetTop: document.getElementById('memIntro').getBoundingClientRect().top, okTop: document.getElementById('memIntroOk').getBoundingClientRect().top, h: r.height, lh: parseFloat(cs.lineHeight), mb: parseFloat(cs.marginBottom), op: cs.opacity } }")
    g0 = pg.evaluate("__g()")
    check('1.10.2: error line reserves its space while invisible (one 1.25rem line ≈ 20px + 10px margin), opacity 0', abs(g0['h'] - g0['lh']) < .01 and 20 <= g0['h'] <= 22 and g0['mb'] == 10 and g0['op'] == '0', g0)
    pg.click('#memIntroOk'); pg.wait_for_timeout(900); tv = err_vis(pg)
    check('좋아요 retries the PATCH; still 400 → sheet kept, error line (role=alert) inside the sheet, visible, localStorage still unset, button usable', shown(pg) and attempts() == 2 and seenLocal(pg) is None and tv and '저장하지 못했어요' in tv['text'] and tv['role'] == 'alert' and tv['inSheet'] and tv['onTop'] and not pg.is_disabled('#memIntroOk'), (attempts(), seenLocal(pg), tv))
    g1 = pg.evaluate("__g()")
    check('1.10.2: showing the error does not move the sheet top or the 좋아요 button (no jump), opacity 1', g1['sheetTop'] == g0['sheetTop'] and g1['okTop'] == g0['okTop'] and g1['h'] == g0['h'] and g1['op'] == '1', (g0, g1))
    pg.evaluate("window.__ops = []; (function f() { window.__ops.push(parseFloat(getComputedStyle(document.getElementById('memIntroErr')).opacity)); window.__raf = requestAnimationFrame(f); })()")
    pg.click('#memIntroOk'); pg.wait_for_timeout(900); ops = pg.evaluate("cancelAnimationFrame(window.__raf), window.__ops")
    check('1.10.2: retry that fails again keeps the error line fully visible throughout (no flicker), sheet top unchanged', attempts() == 3 and len(ops) > 5 and min(ops) == 1 and pg.evaluate("__g().sheetTop") == g0['sheetTop'], (attempts(), min(ops), len(ops)))
    put('/pro/set', {'uiKey': True}); pg.click('#memIntroOk'); pg.wait_for_timeout(900)
    check('server now accepts → 좋아요 closes, localStorage written only now, server flag set, error line gone', not shown(pg) and pg.evaluate("!document.getElementById('memIntroErr').classList.contains('on')") and seenLocal(pg) == '1' and pro()['settings'].get('ui') == {'memory_intro_seen': True}, (seenLocal(pg), pro()['settings'].get('ui')))
    pg.reload(); pg.wait_for_timeout(2200); check('… and never shown again', not shown(pg)); ctx.close()
    # 1.10.2: 200 + non-JSON body on the PATCH does not count as saved (same as a failure: sheet stays, localStorage unset, error line)
    setup(); put('/pro/set', {'uiKey': True, 'patchNonJson': True}); ctx, pg = launch(wait=0); pg.wait_for_function("window.__app && __app.state().mode==='server'"); pg.wait_for_selector('#memIntro', state='visible', timeout=4000); pg.wait_for_timeout(500)
    check('PATCH 200 text/html at show: sheet stays, localStorage NOT written', shown(pg) and seenLocal(pg) is None and attempts() == 1 and err_vis(pg) is None, (seenLocal(pg), attempts()))
    pg.click('#memIntroOk'); pg.wait_for_timeout(900); tv = err_vis(pg)
    check('좋아요 → retry also 200 non-JSON: sheet kept, error line visible, localStorage unset, no server flag', shown(pg) and attempts() == 2 and seenLocal(pg) is None and bool(tv) and not pro()['settings'].get('ui'), (attempts(), seenLocal(pg), tv))
    put('/pro/set', {'patchNonJson': False}); pg.click('#memIntroOk'); pg.wait_for_timeout(900)
    check('real JSON 200 afterwards → saved, closes', not shown(pg) and seenLocal(pg) == '1' and pro()['settings'].get('ui') == {'memory_intro_seen': True}, (seenLocal(pg), pro()['settings'].get('ui')))
    ctx.close()
    setup(); ctx, pg = launch(); pg.wait_for_timeout(400); pg.keyboard.press('Escape'); pg.wait_for_timeout(700)
    check('failed PATCH + Escape: closes, localStorage unset → next launch asks again', not shown(pg) and seenLocal(pg) is None)
    pg.reload(); pg.wait_for_timeout(2400); check('… next launch shows the sheet again', shown(pg)); ctx.close()
    # silent retry on load: local says seen, server flag empty
    setup(uiKey=True); ctx, pg = launch(local_seen=True, wait=2600)
    check('local seen + server flag empty: no sheet, PATCH retried silently → server flag set, localStorage stays 1, no toast', not shown(pg) and seenLocal(pg) == '1' and pro()['settings'].get('ui') == {'memory_intro_seen': True} and toast_vis(pg) is None, (pro()['settings'].get('ui'), seenLocal(pg))); ctx.close()
    setup(); ctx, pg = launch(local_seen=True, wait=2600)
    check('retry rejected (400): silent — no sheet, no toast, localStorage kept, exactly 1 attempt', not shown(pg) and seenLocal(pg) == '1' and attempts() == 1 and toast_vis(pg) is None, attempts())
    pg.evaluate("location.hash = '#/log'"); pg.wait_for_timeout(700); pg.evaluate("location.hash = '#/'"); pg.wait_for_timeout(1500)
    pg.evaluate("document.dispatchEvent(new Event('visibilitychange'))"); pg.wait_for_timeout(1200)
    check('… still once per load after Today is shown again / app comes back', attempts() == 1, attempts())
    pg.reload(); pg.wait_for_timeout(2600); check('… a new load tries once more (2 in total)', attempts() == 2 and not shown(pg), attempts()); ctx.close()
    setup(settings=PS(True, {'memory_intro_seen': True})); ctx, pg = launch(local_seen=True, wait=2400)
    check('local seen + server seen: no PATCH at all', attempts() == 0 and not shown(pg)); ctx.close()
    setup(system=dict(SYS, memory_available=False)); ctx, pg = launch(local_seen=True, wait=2400)
    check('local seen but memory_available=false: no PATCH', attempts() == 0 and not shown(pg)); ctx.close()
    setup(settings=PS(False)); ctx, pg = launch(local_seen=True, wait=2400)
    check('local seen but memory.enabled=false: no PATCH', attempts() == 0 and not shown(pg)); ctx.close()
    check('no page errors', not errs, errs)
    b.close()
print(f'{sum(R)}/{len(R)} passed'); raise SystemExit(0 if all(R) else 1)
