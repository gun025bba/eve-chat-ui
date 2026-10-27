"""v15: web search toggle, live search status, [n] citations, sources list, persisted sources, CSP."""
from playwright.sync_api import sync_playwright
import urllib.request, json
B = 'http://127.0.0.1:'+__import__('os').environ.get('EVE_PORT','8765')+''
def put(path, body=None):
    r = urllib.request.Request(B + path, method='PUT', data=json.dumps(body).encode() if body else None, headers={'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(r))
def db(): return json.load(urllib.request.urlopen(B + '/__db'))
FAIL = []
def check(name, ok, info=''):
    print(('PASS ' if ok else 'FAIL ') + name + (' ' + str(info) if info and not ok else ''))
    if not ok: FAIL.append(name)

with sync_playwright() as p:
    b = p.chromium.launch()
    put('/auth/on'); put('/reset'); put('/db/reset'); put('/csp/on'); put('/persist/on'); put('/webdisabled/off')
    ctx = b.new_context(viewport={'width': 390, 'height': 844})
    ctx.add_init_script("document.addEventListener('securitypolicyviolation', e => { (window.__csp = window.__csp || []).push(e.violatedDirective + ' ' + e.blockedURI); });")
    pg = ctx.new_page(); errs = []; reqs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('request', lambda r: reqs.append(r.url))
    pg.goto(B + '/ui/'); pg.wait_for_timeout(800)
    pg.evaluate("location.hash='#/c/new'"); pg.wait_for_timeout(300)
    if pg.is_visible('#newChat'): pg.click('#newChat'); pg.wait_for_timeout(400)
    btn = pg.locator('#webBtn')
    af = pg.evaluate(r"""(()=>{const bad=/name|address|contact|e-?mail|phone|tel|street|city|zip|postal|이름|주소|연락|전화/i;
      const out={}; for (const sel of ['#input','#search','#titleEdit','#sSystem']) { const e=document.querySelector(sel);
        const words=[e.id,e.name,e.placeholder,e.getAttribute('aria-label'),e.className].join(' ');
        out[sel]={ok:e.getAttribute('autocomplete')===(sel==='#input'?'eve-composer':'off')&&e.hasAttribute('data-1p-ignore')&&e.dataset.lpignore==='true'&&e.dataset.formType==='other'&&!bad.test(words),words}; }
      const t=document.querySelector('#input'), f=document.querySelector('#composer');
      out.composer={ok:t.tagName==='TEXTAREA'&&t.getAttribute('enterkeyhint')==='send'&&t.getAttribute('autocapitalize')==='off'&&t.getAttribute('autocorrect')==='off'&&t.spellcheck===false&&!t.form&&!t.closest('form')&&f.tagName!=='FORM'};
      return out;})()""")
    for k, v in af.items(): check('no contact AutoFill hints: ' + k, v['ok'], v)
    check('toggle visible in composer', pg.evaluate("!!document.querySelector('#composer .field #webBtn')") and btn.is_visible())
    check('toggle default off (aria-pressed=false)', btn.get_attribute('aria-pressed') == 'false')
    hit = pg.evaluate("(()=>{const b=document.querySelector('#webBtn'),r=b.getBoundingClientRect(),s=getComputedStyle(b,'::before');return {w:r.width-2*parseFloat(s.left),h:r.height-2*parseFloat(s.top)}})()")
    check('toggle hit area >= 44', hit['w'] >= 44 and hit['h'] >= 44, hit)
    # off -> request has no web_search
    pg.fill('#input', 'hello off'); pg.click('#sendBtn'); pg.wait_for_timeout(2000)
    check('off: web_search omitted', 'web_search' not in db()['state']['lastBody'], db()['state']['lastBody'])
    btn.click(); pg.wait_for_timeout(200)
    check('toggle on: aria-pressed=true + .on', btn.get_attribute('aria-pressed') == 'true' and 'on' in btn.get_attribute('class'))
    check('persisted in localStorage', pg.evaluate("localStorage.getItem('llmchat.webSearch')") == '1')
    pg.reload(); pg.wait_for_timeout(800)
    if not pg.is_visible('#input'): pg.evaluate("document.querySelector('#convList li.row .row-main').click()"); pg.wait_for_timeout(600)
    check('toggle survives reload', pg.locator('#webBtn').get_attribute('aria-pressed') == 'true')
    # streaming auto
    pg.fill('#input', 'ws 질문'); pg.click('#sendBtn'); pg.wait_for_timeout(500)
    st = pg.locator('.msg.assistant .ws-status').last
    check('searching status on tool_call', st.is_visible() and '웹 검색 중: eve 속도' in st.inner_text(), st.inner_text() if st.count() else None)
    pg.wait_for_timeout(1000)
    st2 = pg.evaluate("(document.querySelector('.msg.assistant:last-of-type .ws-status')||{}).textContent||''")
    check('fetch status shows domain', '읽는 중: example.com' in st2 or '답변' in st2, st2)
    check('request sent web_search=auto', db()['state']['lastBody'].get('web_search') == 'auto')
    pg.wait_for_timeout(2200)
    last = pg.locator('.msg.assistant').last
    cites = last.locator('.md sup.cite a')
    check('citation capsules rendered (1.7.0: [1,2] merged)', cites.count() >= 3, cites.count())
    check('cite [1] -> source url', cites.first.get_attribute('href') == 'https://example.com/notes?a=1&b=2', cites.first.get_attribute('href'))
    check('cite rel/target', all(cites.nth(i).get_attribute('rel') == 'noopener noreferrer' and cites.nth(i).get_attribute('target') == '_blank' for i in range(cites.count())))
    md = last.locator('.md').inner_html()
    check('unknown [9] left as text', '[9]' in md)
    check('[1] inside code untouched', '<code>코드 [1]</code>' in md, md)
    check('[1, 2] in list -> one merged capsule 1·2', last.locator('.md li sup.cite').count() == 1 and last.locator('.md li sup.cite').inner_text() == '1·2')
    srcs = last.locator('.sources li a')
    check('sources list: 2 safe items (javascript: dropped)', srcs.count() == 2, srcs.count())
    check('source title escaped', '<b>' not in last.locator('.sources').inner_html().replace('&lt;b&gt;', ''))
    check('source domain shown', 'docs.example.org' in last.locator('.sources .src-list').text_content())
    check('no ws-status after answer', last.locator('.ws-status').count() == 0)
    check('no external requests', all(u.startswith(B) or u.startswith('data:') for u in reqs), [u for u in reqs if not u.startswith(B)])
    # persisted reload
    pg.evaluate("localStorage.removeItem('llmchat.convs')"); pg.reload(); pg.wait_for_timeout(1200)
    if not pg.is_visible('#input'): pg.evaluate("document.querySelector('#convList li.row .row-main').click()"); pg.wait_for_timeout(1200)
    pg.screenshot(path='/workspace/llm-chat-ui-shots/v15-websearch.png')
    m = [x for x in db()['messages'].values() if x.get('sources')] if isinstance(db()['messages'], dict) else [x for x in db()['messages'] if x.get('sources')]
    check('server stored sources', len(m) >= 1)
    check('thread reload renders sources from API', pg.locator('.msg.assistant .sources li').count() >= 2 and pg.locator('.msg.assistant sup.cite').count() >= 2)
    # non-stream
    pg.fill('#input', 'wsnostream q'); pg.click('#sendBtn'); pg.wait_for_timeout(1500)
    last = pg.locator('.msg.assistant').last
    check('non-stream message.sources rendered', last.locator('.sources li').count() == 2 and last.locator('sup.cite').count() >= 2)
    # disabled on server -> auto-off + retry
    put('/webdisabled/on')
    pg.fill('#input', 'hello disabled'); pg.click('#sendBtn'); pg.wait_for_timeout(2500)
    check('web_search_disabled: toggle turned off', pg.locator('#webBtn').get_attribute('aria-pressed') == 'false')
    check('web_search_disabled: retried without field', 'web_search' not in db()['state']['lastBody'] and 'Hello' in pg.locator('.msg.assistant').last.inner_text())
    put('/webdisabled/off')
    # local (no persistence) mode also renders
    put('/persist/off'); pg.locator('#webBtn').click()
    check('CSP: no violations', not (pg.evaluate("window.__csp || []")), pg.evaluate("window.__csp || []"))
    check('no page errors', not errs, errs)
    b.close()
put('/persist/on'); put('/csp/off')
print('FAILED:', FAIL) if FAIL else print('ALL PASS')
