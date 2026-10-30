"""Settings component preserves native dialog and persisted form semantics."""
import os
from playwright.sync_api import sync_playwright
from assets_common import full_csp, watch_csp
from b1_common import B, reset
from version_common import VERSION

with full_csp(), sync_playwright() as p:
    for engine in (p.chromium, p.webkit):
        if engine.name == 'webkit' and os.environ.get('EVE_WEBKIT') != '1':
            continue
        reset()
        browser = engine.launch()
        context = browser.new_context(viewport={'width': 390, 'height': 844}, service_workers='block')
        watch_csp(context)
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(B + '/ui/')
        page.bring_to_front()
        page.wait_for_function('() => window.__app')
        assert page.locator('#settings').count() == 1
        assert page.text_content('#appVersion') == 'v' + VERSION
        print('PASS', engine.name, 'single settings dialog has injected version without service worker')
        def open_settings():
            page.locator('#openSettings').click()
            page.wait_for_function("() => document.querySelector('#settings').open")
        open_settings()
        assert page.locator('#settingsForm').get_attribute('method') == 'dialog'
        assert page.locator('#sShowThink').get_attribute('switch') is not None
        assert page.locator('#sBase').get_attribute('spellcheck') == 'false'
        print('PASS', engine.name, 'native dialog form and input attributes retained')
        page.locator('#sSystem').fill('<img src=x> & 간결하게')
        page.locator('label:has(#sShowThink)').click()
        page.locator('#saveSettings').click()
        page.wait_for_function("() => !document.querySelector('#settings').open")
        saved = page.evaluate("JSON.parse(localStorage.getItem('llmchat.settings'))")
        assert saved['system'] == '<img src=x> & 간결하게' and saved['showThink'] is True
        assert set(saved) == {'noThink', 'base', 'model', 'system', 'showThink'}
        print('PASS', engine.name, 'save keeps exact settings storage shape and literal prompt')
        open_settings()
        assert page.locator('#sSystem').input_value() == '<img src=x> & 간결하게'
        assert page.locator('#sShowThink').is_checked()
        page.locator('#sSystem').fill('취소한 변경')
        page.locator('#cancelSettings').click()
        page.wait_for_function("() => !document.querySelector('#settings').open")
        open_settings()
        assert page.locator('#sSystem').input_value() == '<img src=x> & 간결하게'
        print('PASS', engine.name, 'cancel discards unsaved prompt and reopen restores saved values')
        page.keyboard.press('Escape')
        page.wait_for_function("() => !document.querySelector('#settings').open")
        assert not page.locator('#settings img, #settings style, #settings script').count()
        assert not errors, errors
        print('PASS', engine.name, 'Escape closes without markup injection or page errors')
        assert not page.evaluate('window.__csp || []')
        browser.close()
