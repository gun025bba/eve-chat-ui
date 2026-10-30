"""Install component retains platform copy, manual snooze and prompt ownership."""
import os
from playwright.sync_api import sync_playwright
from assets_common import full_csp, watch_csp
from b1_common import B, reset

with full_csp(), sync_playwright() as p:
    for engine in (p.chromium, p.webkit):
        if engine.name == 'webkit' and os.environ.get('EVE_WEBKIT') != '1':
            continue
        for platform in ('iPhone', 'iPad', 'desktop'):
            reset()
            browser = engine.launch()
            options = {'viewport': {'width': 390, 'height': 844}, 'service_workers': 'block'}
            if platform != 'desktop':
                options['user_agent'] = 'Mozilla/5.0 (' + platform + '; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Safari/604.1'
            context = browser.new_context(**options)
            watch_csp(context)
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(B + '/ui/')
            page.bring_to_front()
            page.wait_for_function('() => window.__app')
            assert page.evaluate("localStorage.getItem('visits')") == '1'
            assert page.locator('#installSheet').evaluate('e => e.hidden')
            if platform == 'desktop':
                page.evaluate("""() => {
                  const e = new Event('beforeinstallprompt', {cancelable:true});
                  e.prompt = () => window.__prompted = (window.__prompted || 0) + 1;
                  e.userChoice = Promise.resolve({outcome:'accepted'});
                  window.dispatchEvent(e);
                }""")
            page.locator('#openSettings').click()
            page.locator('#showA2hs').click()
            page.wait_for_function("() => document.querySelector('#installSheet').classList.contains('show')")
            assert page.locator('#installSheet').get_attribute('data-manual') == '1'
            assert page.locator('#installSheet').get_attribute('role') == 'dialog'
            if platform == 'desktop':
                assert page.locator('#installSheet').evaluate("e => e.classList.contains('bip')")
                page.locator('#installBtn').click()
                page.wait_for_function("() => document.querySelector('#installSheet').hidden")
                assert page.evaluate("window.__prompted === 1 && localStorage.getItem('a2hs.installed') === '1'")
                print('PASS', engine.name, 'accepted browser prompt runs once and remembers installation')
            else:
                copy = page.text_content('.step-share')
                assert ('주소창 옆' in copy) == (platform == 'iPad'), copy
                assert '공유' in copy and page.locator('.step-share b').text_content() == '공유'
                print('PASS', engine.name, platform, 'platform instructions preserve bold share label')
                page.locator('#installLater').click()
                page.wait_for_function("() => document.querySelector('#installSheet').hidden")
                assert page.evaluate("localStorage.getItem('a2hs.dismissed') === null")
                print('PASS', engine.name, platform, 'manual dismissal does not create thirty-day snooze')
            assert not page.locator('.sheet-scrim').count()
            assert not errors, errors
            print('PASS', engine.name, platform, 'closing removes scrim without page errors')
            assert not page.evaluate('window.__csp || []')
            browser.close()
