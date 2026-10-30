"""Migration component keeps skip, background import, retry, backup and literal failures."""
import json, os
from urllib.parse import quote
from playwright.sync_api import sync_playwright
from assets_common import full_csp, watch_csp
from b1_common import B, reset, put, req

local = [{'id': 'L' + str(i), 'title': ('importfail <img src=x>' if i == 2 else '로컬 ' + str(i)),
          'updated': 1793372400000 - i * 100000, 'archived': i == 1,
          'messages': [{'role': 'user', 'content': '질문'}, {'role': 'assistant', 'content': '<think>이유</think>\n답변'}]}
         for i in range(7)]
with full_csp(), sync_playwright() as p:
    for engine in (p.chromium, p.webkit):
        if engine.name == 'webkit' and os.environ.get('EVE_WEBKIT') != '1':
            continue
        reset()
        browser = engine.launch()
        context = browser.new_context(viewport={'width': 390, 'height': 844}, service_workers='block')
        watch_csp(context)
        context.add_init_script("if(!sessionStorage.getItem('fixture')){sessionStorage.setItem('fixture','1');localStorage.setItem('llmchat.convs'," + json.dumps(json.dumps(local)) + ")}")
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(B + '/ui/#/log')
        page.wait_for_function("() => window.__app && __app.route() === 'list' && __app.state().mode === 'server'")
        page.bring_to_front()
        page.wait_for_function("() => document.querySelector('#migrateSheet').classList.contains('show')")
        assert '대화 7개 · 메시지 14개' in page.text_content('#migStats')
        page.locator('#migLater').click()
        page.wait_for_function("() => document.querySelector('#migrateSheet').hidden")
        assert page.evaluate("(() => { const s = JSON.parse(localStorage.getItem('llmchat.migrateSnooze')); return s.n === 1 && s.until > Date.now() + 2 * 864e5; })()")
        print('PASS', engine.name, 'offer counts local data and later snoozes three days')
        def manual():
            if page.locator('#logBack').is_visible():
                page.locator('#logBack').click()
            page.locator('#openSettings:visible, #openSettings3:visible').first.click()
            page.locator('#sMigrate').click()
            page.wait_for_function("() => document.querySelector('#migrateSheet').classList.contains('show')")
        manual()
        page.locator('#migSkip').click()
        page.wait_for_function("() => document.querySelector('#migrateSheet').hidden")
        assert page.evaluate("localStorage.getItem('llmchat.migrated')") == 'skip'
        page.reload()
        page.wait_for_function('() => window.__app')
        page.wait_for_timeout(1400)
        assert page.locator('#migrateSheet').evaluate('e => e.hidden')
        print('PASS', engine.name, 'skip suppresses automatic offer after reload')
        manual()
        put('/delay/400?' + quote('POST /v1/threads/import', safe=''))
        page.locator('#migGo').click()
        page.wait_for_function("() => document.querySelector('#migrateSheet').dataset.view === 'progress'")
        assert page.locator('#migrateSheet').get_attribute('data-lock') == '1'
        assert '대화 옮기는 중' in page.text_content('#syncStatus')
        page.locator('.sheet-scrim').click(position={'x': 10, 'y': 10})
        assert page.locator('#migrateSheet').evaluate('e => !e.hidden')
        print('PASS', engine.name, 'progress owns sync status and locks outside dismissal')
        page.locator('#migBg').click()
        page.wait_for_function("() => document.querySelector('#migrateSheet').hidden")
        page.wait_for_function("() => document.querySelector('#migrateSheet').dataset.view === 'partial'")
        assert page.locator('#migFailList li').count() == 1
        assert page.text_content('#migFailList b') == 'importfail <img src=x>'
        assert not page.locator('#migFailList img').count()
        page.wait_for_function("() => document.querySelector('#toast').classList.contains('show')")
        print('PASS', engine.name, 'background failure renders literal title and retry toast')
        put('/delay/clear'); put('/importfix')
        page.locator('#toastAct').click()
        page.wait_for_function("() => document.querySelector('#migrateSheet').dataset.view === 'done'")
        assert page.text_content('#migDoneText') == '대화 7개를 옮겼어요'
        assert page.evaluate("localStorage.getItem('llmchat.convs') === null")
        assert page.evaluate("JSON.parse(localStorage.getItem('llmchat.convs.bak')).data") == local
        db = req('GET', '/__db')
        imported = [t for t in db['threads'] if t.get('client_id', '').startswith('local:')]
        assert len(imported) == 7
        assert any(m.get('reasoning') == '이유' and m['content'] == '답변' for m in db['messages'])
        print('PASS', engine.name, 'retry preserves counts, reasoning, backup and local removal')
        page.locator('#migDone').click()
        page.wait_for_function("() => document.querySelector('#migrateSheet').hidden")
        page.evaluate("localStorage.setItem('llmchat.convs.bak', JSON.stringify({at:Date.now()-8*864e5,data:[]}))")
        page.reload(); page.wait_for_function('() => window.__app')
        assert page.evaluate("localStorage.getItem('llmchat.convs.bak') === null")
        assert not errors, errors
        print('PASS', engine.name, 'old backup purges after seven days without page errors')
        assert not page.evaluate('window.__csp || []')
        browser.close()
