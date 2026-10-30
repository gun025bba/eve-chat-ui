"""Actual message think/source/template/memory/note components retain DOM and interaction contracts."""
import json, os, urllib.request
from playwright.sync_api import sync_playwright
from assets_common import full_csp, watch_csp
from b1_common import new_ctx
B = 'http://127.0.0.1:' + os.environ.get('EVE_PORT', '8765')
def put(path, body=None):
    request = urllib.request.Request(B + path, method='PUT', data=None if body is None else json.dumps(body).encode(), headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request) as response: return json.load(response)
SOURCES = [{'n':i, 'url':f'https://source{i}.example.com/p', 'title':f'출처 {i} <img> & 제목', 'domain':f'source{i}.example.com', **({'favicon':'/ui/favicon.svg'} if i==2 else {})} for i in range(1,9)]
REFS = [{'id':'ref-1','text':'🙂'*15}, {'id':'ref-2','text':'<img src=x> & 기억'}, {'id':'ref-3','text':'세 번째'}]
TOOLS = [{'tool':'web_search','query':'<script>질문</script> & 검색','selected_by':'model','status':'ok','count':8}]
with full_csp(), sync_playwright() as p:
    for engine in (p.chromium,p.webkit):
        if engine.name=='webkit' and os.environ.get('EVE_WEBKIT')!='1': continue
        for path in ('/auth/on','/reset','/db/reset','/persist/on','/pro/reset'): put(path)
        put('/b1/seed', {'title':'메시지 구성 요소','memory':True,'messages':[
            {'role':'assistant','reasoning':'생각 <img> & 과정','content':'답변[1]','sources':SOURCES,'memory_refs':REFS,'metadata':{'tools':TOOLS}},
            {'role':'assistant','content':'확인되지 않은 답변[1]','sources':SOURCES[:2],'metadata':{'fresh':'unverified','tools':[{'tool':'web_search','status':'timeout','error_code':'timeout'}]}},
            {'role':'assistant','content':'출처와 기억이 없는 답변'},
        ]})
        browser=engine.launch(); context=new_ctx(browser,service_workers='block'); watch_csp(context)
        page=context.new_page(); errors=[]; page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(B+'/ui/#/log'); page.bring_to_front(); page.wait_for_timeout(1200)
        page.locator('#convList li.row').first.click(); page.locator('.tnote .tb').wait_for()
        results=page.evaluate("""() => {
          const normalize = section => {
            const clone=section.cloneNode(true), list=clone.querySelector('.src-list'), id=list.id;
            list.id='SOURCE';
            clone.querySelectorAll('[aria-controls]').forEach(button=>{if(button.getAttribute('aria-controls')===id)button.setAttribute('aria-controls','SOURCE')});
            return clone.outerHTML;
          };
          return [...document.querySelectorAll('.msg.assistant')].slice(0,2).map((message,i)=>{
            const data=__app.msgs()[i], html=renderSources(data.sources,data.tools);
            const expected=new DOMParser().parseFromString(html,'text/html').body.firstElementChild;
            const actual=message.querySelector('.sources');
            return {same:normalize(actual)===normalize(expected),actual:normalize(actual),expected:normalize(expected)};
          });
        }""")
        assert all(result['same'] for result in results), (engine.name,results)
        print('PASS',engine.name,'source chips, queries, full template and items match legacy DOM')
        ids=page.locator('.sources .src-list').evaluate_all('nodes=>nodes.map(n=>n.id)')
        assert len(set(ids))==len(ids)==2 and page.locator('.msg.assistant').nth(2).locator('.sources,.mchips,.tnote').count()==0
        print('PASS',engine.name,'unique source IDs and absent optional sections')
        first=page.locator('.msg.assistant').first
        assert first.locator('.mchips .chp').count()==2 and first.locator('.chp-more').inner_text()=='+1'
        assert first.locator('.mchips .chp span').first.inner_text()=='🙂'*14+'…'
        assert first.locator('.mchips img, .mchips script').count()==0
        print('PASS',engine.name,'memory chips retain two-item limit and Unicode truncation without HTML')
        note=page.locator('.tnote')
        assert note.get_attribute('role')=='status' and note.get_attribute('aria-live')=='polite'
        assert note.locator('b').inner_text()=='검색 시간이 초과됐어요' and note.locator('button,a').count()==0
        print('PASS',engine.name,'tool failure note announces fixed text without actions')
        summary=first.locator('details.think summary'); summary.click()
        assert first.locator('details.think').evaluate("node=>node.open&&node.dataset.user==='1'")
        summary.click(); assert not first.locator('details.think').evaluate('node=>node.open')
        print('PASS',engine.name,'native think disclosure toggles and records user intent')
        first.locator('.sources .sc').first.click(); first.locator('.src-all').click()
        assert page.locator('#srcSheet').is_visible() and page.locator('#srcSheet .src-item').count()==8
        assert page.locator('#srcSheet .tq').inner_text().startswith('검색어') and page.locator('#srcSheet img, #srcSheet script').count()==0
        print('PASS',engine.name,'all-sources sheet clones actual component template content')
        page.locator('#srcSheet .src-close').click(); page.wait_for_function("()=>!document.querySelector('#srcSheet').open")
        assert not errors and not page.evaluate('window.__csp||[]'),errors
        print('PASS',engine.name,'no CSP violations or lifecycle errors')
        browser.close()
