"""Rename component keeps composition, save/cancel and shared sheet dismissal."""
import os
from playwright.sync_api import sync_playwright
from b2_common import reset, conv2, B

with sync_playwright() as p:
    for engine in (p.chromium, p.webkit):
        if engine.name == 'webkit' and os.environ.get('EVE_WEBKIT') != '1':
            continue
        reset()
        thread = conv2('기존 제목', 10, 0)
        browser = engine.launch()
        page = browser.new_page(viewport={'width': 390, 'height': 844})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(B + '/ui/#/c/' + thread)
        page.bring_to_front()
        page.wait_for_function("() => document.querySelector('#title').textContent === '기존 제목'")
        def open_sheet():
            page.locator('#titleWrap').click()
            page.wait_for_function("() => document.querySelector('#renameSheet').classList.contains('show')")
        open_sheet()
        page.wait_for_function("() => document.activeElement.id === 'titleEdit'")
        assert page.locator('#titleEdit').input_value() == '기존 제목'
        assert page.locator('#titleEdit').evaluate('e => e.selectionStart === 0 && e.selectionEnd === e.value.length')
        print('PASS', engine.name, 'rename opens with selected current title')
        page.locator('#titleEdit').fill('  <img src=x> & 새 제목  ')
        page.locator('#titleEdit').dispatch_event('keydown', {'key': 'Enter', 'isComposing': True})
        assert page.locator('#renameSheet').evaluate('e => !e.hidden')
        print('PASS', engine.name, 'composition Enter keeps editing')
        page.locator('#titleEdit').press('Enter')
        page.wait_for_function("() => document.querySelector('#renameSheet').hidden")
        assert page.text_content('#title') == '<img src=x> & 새 제목'
        assert not page.locator('#title img').count()
        print('PASS', engine.name, 'Enter trims and saves title as literal text')
        open_sheet()
        page.locator('#titleEdit').fill('취소한 제목')
        page.locator('#renameCancel').click()
        page.wait_for_function("() => document.querySelector('#renameSheet').hidden")
        assert page.text_content('#title') == '<img src=x> & 새 제목'
        print('PASS', engine.name, 'cancel leaves original title intact')
        open_sheet()
        page.locator('#titleEdit').press('Escape')
        page.wait_for_function("() => document.querySelector('#renameSheet').hidden")
        assert not page.locator('.sheet-scrim').count()
        print('PASS', engine.name, 'Escape closes sheet and removes scrim')
        open_sheet()
        page.locator('.sheet-scrim').click(position={'x': 10, 'y': 10})
        page.wait_for_function("() => document.querySelector('#renameSheet').hidden")
        assert not errors, errors
        print('PASS', engine.name, 'outside tap dismisses without page errors')
        browser.close()
