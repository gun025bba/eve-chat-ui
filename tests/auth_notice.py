"""Auth component: classification, ephemeral code and five-failure lock in both engines."""
import json, os, re
from playwright.sync_api import sync_playwright
from b1_common import B, reset

with sync_playwright() as p:
    for engine in (p.chromium, p.webkit):
        if engine.name == 'webkit' and os.environ.get('EVE_WEBKIT') != '1':
            continue
        reset()
        browser = engine.launch()
        context = browser.new_context(viewport={'width': 390, 'height': 844}, service_workers='block')
        context.add_init_script("document.addEventListener('securitypolicyviolation', e => (window.__csp = window.__csp || []).push(e.violatedDirective))")
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        response = {'status': 403, 'body': {'error_code': 'identity_not_allowed'}}
        page.route(re.compile(r'/whoami$'), lambda route: route.fulfill(status=response['status'], content_type='application/json', body=json.dumps(response['body'])))
        page.route(re.compile(r'/v1/pair$'), lambda route: route.fulfill(status=401, content_type='application/json', body='{"error_code":"pair_failed"}'))
        page.goto(B + '/ui/')
        page.bring_to_front()
        page.wait_for_function("() => document.querySelector('#authNotice').classList.contains('in')")
        assert page.text_content('#authTitle') == '이 계정은 쓸 수 없어요'
        assert page.locator('#pairForm').evaluate('e => e.hidden')
        print('PASS', engine.name, 'identity rejection keeps code entry hidden')
        response.update(status=401, body={'error_code': 'unauthenticated'})
        page.locator('#authRetry').click()
        page.wait_for_function("() => !document.querySelector('#pairForm').hidden")
        assert page.text_content('#authTitle') == '이 기기를 연결해 주세요'
        page.locator('#pairCode').fill('oilu2abc')
        assert page.locator('#pairCode').input_value() == '011V-2ABC'
        assert page.locator('#pairCode').get_attribute('autocomplete') == 'one-time-code'
        print('PASS', engine.name, '401 enables entry and Crockford normalization')
        for attempt in range(1, 6):
            page.locator('#pairSubmit').click()
            page.wait_for_function('n => { const s = JSON.parse(localStorage.getItem("eve.pairLock")); return s && (n === 5 ? s.until > Date.now() : s.fails === n); }', arg=attempt)
        assert page.locator('.auth-card').get_attribute('data-pair') == 'locked'
        assert page.locator('#pairCode').is_disabled() and page.locator('#pairSubmit').is_disabled()
        assert '10분' in page.text_content('#pairErr')
        print('PASS', engine.name, 'fifth failed code locks input and submit for ten minutes')
        stored = page.evaluate('Object.values(localStorage).join(" ")')
        assert '011V-2ABC' not in stored and 'oilu2abc' not in stored
        print('PASS', engine.name, 'code stays out of storage')
        response.update(status=200, body={'authenticated': True, 'user': '테스트'})
        page.locator('#authRetry').click()
        page.wait_for_function("() => document.querySelector('#authNotice').hidden")
        assert page.evaluate("localStorage.getItem('eve.paired')") == '1'
        assert page.text_content('#sWho') == '테스트 계정으로 연결됨'
        print('PASS', engine.name, 'identity retry hides notice and updates settings projection')
        assert not errors and not page.evaluate('window.__csp || []'), errors
        assert not page.locator('#authNotice style, #authNotice script, #authNotice [style]').count()
        print('PASS', engine.name, 'no page errors, CSP violations or inline styles')
        browser.close()
