"""Preact coexistence: toast text boundary, action replacement and timer ownership."""
import os
from playwright.sync_api import sync_playwright

B = 'http://127.0.0.1:' + os.environ.get('EVE_PORT', '8765')
with sync_playwright() as p:
    for engine in (p.chromium, p.webkit):
        if engine.name == 'webkit' and os.environ.get('EVE_WEBKIT') != '1':
            continue
        browser = engine.launch()
        context = browser.new_context(viewport={'width': 390, 'height': 844})
        context.add_init_script("document.addEventListener('securitypolicyviolation', e => (window.__csp = window.__csp || []).push(e.violatedDirective))")
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(B + '/ui/')
        page.bring_to_front()
        page.wait_for_function('() => window.__app')
        assert page.locator('#toast').count() == 1 and page.locator('#toast').get_attribute('role') == 'status'
        assert page.locator('#toast').evaluate('e => e.hidden && !e.classList.contains("show")')
        print('PASS', engine.name, 'one initially hidden status toast')
        page.evaluate("__app.showToast('<img src=x onerror=alert(1)> & 안녕', '실행', () => window.__toastCalls = (window.__toastCalls || 0) + 1)")
        page.wait_for_function("() => document.querySelector('#toast').classList.contains('show')")
        assert page.text_content('#toastText') == '<img src=x onerror=alert(1)> & 안녕'
        assert page.locator('#toast img').count() == 0 and page.is_visible('#toastAct')
        print('PASS', engine.name, 'untrusted text remains literal and action appears')
        page.locator('#toastAct').click()
        assert page.evaluate('window.__toastCalls') == 1
        page.wait_for_function("() => document.querySelector('#toast').hidden")
        print('PASS', engine.name, 'action executes once and fade finishes hidden')
        page.evaluate("__app.showToast('이전', '이전', () => window.__toastOld = true); __app.showToast('새 알림', '새 동작', () => window.__toastNew = true)")
        page.locator('#toastAct').click()
        assert page.evaluate('window.__toastNew === true && !window.__toastOld')
        print('PASS', engine.name, 'replacement action invokes latest callback')
        page.evaluate("__app.showToast('곧 닫힘', '', null, 100)")
        page.wait_for_function("() => document.querySelector('#toast').hidden")
        print('PASS', engine.name, 'automatic dismissal retains fade delay')
        page.evaluate("__app.showToast('타이머', '', null, 200); __app.showToast('유지')")
        page.wait_for_timeout(650)
        assert page.is_visible('#toast') and page.text_content('#toastText') == '유지'
        assert page.locator('#toastAct').evaluate('e => e.hidden')
        print('PASS', engine.name, 'replacement cancels stale timer and hides empty action')
        assert not page.locator('#toast [style], #toast style, #toast script').count()
        assert not errors and not page.evaluate('window.__csp || []'), errors
        print('PASS', engine.name, 'no inline content, CSP violations or page errors')
        browser.close()
