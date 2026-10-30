"""Built artifact: full gateway CSP, bridge hooks, streaming, stop and offline boot."""
import json, os, urllib.request
from playwright.sync_api import sync_playwright
from version_common import VERSION

B = 'http://127.0.0.1:' + os.environ.get('EVE_PORT', '8765')
def put(path, body):
    request = urllib.request.Request(B + path, data=json.dumps(body).encode(), method='PUT', headers={'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(request))

with sync_playwright() as p:
    engines = [p.chromium] + ([p.webkit] if os.environ.get('EVE_WEBKIT') == '1' else [])
    for engine in engines:
        put('/reset', {})
        put('/auth/on', {}); put('/db/reset', {}); put('/persist/on', {}); put('/csp/full', {})
        browser = engine.launch()
        context = browser.new_context(viewport={'width': 390, 'height': 844})
        context.add_init_script("document.addEventListener('securitypolicyviolation', e => (window.__csp = window.__csp || []).push(e.violatedDirective));")
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' and 'Content Security Policy' in msg.text else None)
        page.goto(B + '/ui/')
        page.wait_for_function('() => window.__app && window.EveShell && window.__vv')
        assert page.evaluate('__app.version') == VERSION
        if engine.name == 'webkit':
            assert not errors and not page.evaluate('window.__csp || []'), errors
            print('PASS webkit artifact first screen, hooks, CSP, no page errors')
            browser.close()
            continue
        page.evaluate('__app.newChat()')
        page.locator('#input').fill('slow')
        page.locator('#sendBtn').click()
        page.wait_for_function("() => document.querySelector('.msg.assistant')?.textContent.includes('조각0')")
        page.locator('#sendBtn').click()
        page.wait_for_function("() => !document.querySelector('#sendBtn').classList.contains('stop')")
        page.evaluate('navigator.serviceWorker.ready')
        page.wait_for_function('() => navigator.serviceWorker.controller !== null')
        if engine.name == 'chromium':  # Playwright WebKit does not support SW offline navigation.
            context.set_offline(True)
            page.reload()
            page.wait_for_function('() => window.__app && window.EveShell')
            assert page.evaluate('__app.version') == VERSION
            context.set_offline(False)
            page.reload()
            page.wait_for_function('() => window.__app')
        assert not errors and not page.evaluate('window.__csp || []'), errors
        print('PASS', engine.name, 'artifact CSP, hooks, streaming/stop', 'offline/recovery' if engine.name == 'chromium' else 'online smoke')
        browser.close()
    put('/csp/off', {})
