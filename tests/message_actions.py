"""Message action ordering, clipboard flash ownership, fallback and Retry-After under full CSP."""
import json, os, urllib.request
from playwright.sync_api import sync_playwright
from assets_common import full_csp, watch_csp
B = 'http://127.0.0.1:' + os.environ.get('EVE_PORT', '8765')
def put(path, body=None):
    urllib.request.urlopen(urllib.request.Request(B + path, method='PUT', data=None if body is None else json.dumps(body).encode(), headers={'Content-Type':'application/json'})).read()
with full_csp(), sync_playwright() as p:
    for engine in (p.chromium, p.webkit):
        if engine.name == 'webkit' and os.environ.get('EVE_WEBKIT') != '1': continue
        for path in ('/auth/on', '/reset', '/db/reset', '/persist/on'): put(path)
        browser = engine.launch()
        context = browser.new_context(viewport={'width':390, 'height':844}, service_workers='block')
        watch_csp(context)
        context.add_init_script("Object.defineProperty(navigator, 'clipboard', {configurable:true,value:{writeText:async text => (window.__copies ||= []).push(text)}})")
        page = context.new_page(); errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(B + '/ui/'); page.bring_to_front()
        page.wait_for_function('() => window.__app'); page.wait_for_timeout(700)
        page.evaluate('__app.newChat()'); page.wait_for_timeout(300)
        page.fill('#input','hello actions'); page.click('#sendBtn')
        page.locator('.msg.assistant .actions .c').wait_for()
        assistant = page.locator('.msg.assistant').last
        assert assistant.locator('.actions').evaluate("row => [...row.children].map(n => n.className).join('|')") == 'c|r|fb up|fb down|fb-why|usage'
        print('PASS', engine.name, 'copy, regenerate, feedback and usage order')
        expected = page.evaluate('splitThink(__app.msgs().at(-1).content).answer.trim()')
        assistant.locator('.actions .c').click()
        page.wait_for_function("() => document.querySelector('.actions .c').classList.contains('done')")
        assert page.evaluate('window.__copies.at(-1)') == expected
        assert assistant.locator('.actions .c use').get_attribute('href') == '#i-check'
        assert assistant.locator('.actions .c').get_attribute('data-busy') == '1'
        print('PASS', engine.name, 'answer copies raw answer and shows check without label')
        page.wait_for_timeout(1600)
        assert assistant.locator('.actions .c use').get_attribute('href') == '#i-copy'
        assert assistant.locator('.actions .c').get_attribute('data-busy') is None
        print('PASS', engine.name, 'flash restores original copy icon and clears busy')
        code = assistant.locator('.code-head .copy')
        expected_code = assistant.locator('pre code').inner_text()
        code.click(); page.wait_for_timeout(450); code.click(); page.wait_for_timeout(1150)
        assert page.evaluate('window.__copies.at(-1)') == expected_code
        assert code.inner_text() == '복사' and code.get_attribute('data-busy') is None
        print('PASS', engine.name, 'code copies plain code and repeated click retains first flash deadline')
        page.evaluate("() => {navigator.clipboard.writeText = async () => {throw new Error('denied')}; document.execCommand = command => {window.__fallback = [command, document.querySelector('body > textarea').value]; return true};}")
        code.click(); page.wait_for_timeout(100)
        assert page.evaluate('window.__fallback') == ['copy', expected_code]
        assert page.locator('body > textarea').count() == 0 and code.inner_text() == '복사됨'
        print('PASS', engine.name, 'denied clipboard falls back and removes temporary textarea')
        page.evaluate('__app.newChat()'); page.wait_for_timeout(1700)
        assert page.locator('#messages .actions, #messages .code-head').count() == 0
        print('PASS', engine.name, 'navigation disposes pending copy flash')
        context.route('**/v1/chat/completions', lambda route: route.fulfill(status=429, headers={'Content-Type':'application/json','Retry-After':'1'}, body=json.dumps({'error':{'code':'queue_full'}})), times=1)
        page.fill('#input','retry action'); page.click('#sendBtn')
        retry = page.locator('.msg.error .retry'); retry.wait_for()
        assert retry.is_disabled() and page.locator('.msg.error .err-text').inner_text()
        page.wait_for_timeout(1200); assert retry.is_enabled()
        print('PASS', engine.name, 'error retry respects Retry-After')
        retry.click(); page.locator('.msg.assistant .actions .c').wait_for()
        assert page.locator('.msg.error').count() == 0
        print('PASS', engine.name, 'retry removes error and completes the same pending user turn')
        assert not page.evaluate('window.__csp || []')
        put('/b1/seed', {'title':'중지 상태 계약','messages':[
            {'role':'user','content':'계속 답해줘'},
            {'role':'assistant','content':'부분 답변','status':'incomplete','error_code':'cancelled'},
        ]})
        page.goto(B + '/ui/#/log'); page.reload(); page.wait_for_timeout(1200)
        page.locator('#convList li.row',has_text='중지 상태 계약').click()
        status=page.locator('.msg.assistant .stopped'); status.wait_for()
        assert status.get_attribute('role')=='note' and '답변을 멈췄어요' in status.inner_text()
        assert status.locator('.retry').count()==1
        print('PASS',engine.name,'stopped status keeps note role and retry control')
        message_id=page.evaluate('__app.msgs().at(-1).id'); requests=[]
        context.on('request',lambda request:requests.append(request.post_data_json) if request.method=='POST' and request.url.endswith('/v1/chat/completions') else None)
        status.locator('.retry').click(); page.locator('.msg.assistant .actions .c').wait_for()
        assert page.locator('.msg.assistant .stopped').count()==0 and requests[-1]['replace_message_id']==message_id
        print('PASS',engine.name,'status retry preserves server replacement ID and clears status')
        assert not page.locator('#messages [style], #messages style, #messages script').count()
        assert not errors and not page.evaluate('window.__csp || []'), errors
        print('PASS', engine.name, 'no inline content, CSP violations or lifecycle errors')
        browser.close()
