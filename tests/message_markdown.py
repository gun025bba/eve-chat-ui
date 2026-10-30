"""Final message Markdown VDOM matches the existing escaped renderer's browser-normalized DOM."""
import json, os, urllib.request
from playwright.sync_api import sync_playwright
from assets_common import full_csp, watch_csp
B = 'http://127.0.0.1:' + os.environ.get('EVE_PORT', '8765')
def put(path, body=None):
    request = urllib.request.Request(B + path, method='PUT', data=None if body is None else json.dumps(body).encode(), headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request) as response: return json.load(response)
CASES = [
    'plain & <img src=x onerror=alert(1)> <script>alert(1)</script>',
    '# 제목\n\n**굵게** *기울임* `x < y & z`\n한 줄 더',
    '1. 첫 항목\n2. 두 번째\n   - 안쪽\n   - 다음\n\n뒤 문단',
    '3) 시작 번호\n4) 다음\n\n- 서로 다른 목록\n\n  이어진 줄',
    '```py\nprint(1<2)\n```\n\n끝',
    '```<img src=x>\n<script> & "code"\n```',
    '닫히지 않은 코드\n```txt\n<svg onload=alert(1)>',
    '[링크](https://example.com/a?q=1&b=2) ![그림](https://example.com/p.png)',
    '[위험](javascript:alert(1)) [속성](https://example.com/"onclick="alert(1))',
    '[바깥 [안쪽](https://example.com/a)](https://example.com/b)',
    '인용[1]. 긴단어가열세글자를넘어갑니다[1, 2]! 없는 번호[3]와 `코드 [1]`.',
    '**굵게 *기울임** 교차* &lt;mark&gt; &#39; &#0;',
    '- 항목\n\n  이어지는 문단\n\n  4. 내부 번호\n  5. 다음\n\n마무리',
    '여러 줄\r\n탭\t과 줄바꿈\n\n끝',
]
SOURCES = [{'n':1,'url':'https://example.com/a','title':'<img> & 출처','domain':'example.com'}, {'n':2,'url':'https://docs.example.org/b','title':'문서'}, {'n':3,'url':'javascript:alert(1)','title':'위험'}]
with full_csp(), sync_playwright() as p:
    for engine in (p.chromium, p.webkit):
        if engine.name == 'webkit' and os.environ.get('EVE_WEBKIT') != '1': continue
        for path in ('/auth/on','/reset','/db/reset','/persist/on'): put(path)
        messages = [{'role':'assistant','content':text,'sources':SOURCES} for text in CASES]
        put('/b1/seed', {'title':'Markdown 경계','messages':messages})
        browser = engine.launch(); context = browser.new_context(viewport={'width':390,'height':844}, service_workers='block')
        watch_csp(context); page = context.new_page(); errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(B + '/ui/#/log'); page.bring_to_front(); page.wait_for_timeout(1200)
        page.locator('#convList li.row').first.click()
        page.wait_for_function('n => document.querySelectorAll(".msg.assistant .md").length === n', arg=len(CASES))
        comparisons = page.evaluate("""() => [...document.querySelectorAll('.msg.assistant .md')].map((element, i) => {
          const message = __app.msgs()[i];
          const expected = new DOMParser().parseFromString(renderMarkdown(message.content, message.sources), 'text/html').body.innerHTML;
          return {same:element.innerHTML === expected, actual:element.innerHTML, expected};
        })""")
        for i, result in enumerate(comparisons):
            assert result['same'], (engine.name, i, result)
            print('PASS', engine.name, 'normalized Markdown DOM', i)
        assert page.locator('.md img, .md script, .md style, .md [style], .md [onclick], .md [onerror]').count() == 0
        assert page.locator('.md a[href^="javascript:"]').count() == 0
        print('PASS', engine.name, 'untrusted markup has no executable DOM or unsafe links')
        assert not errors and not page.evaluate('window.__csp || []'), errors
        print('PASS', engine.name, 'no CSP violations or page errors')
        browser.close()
