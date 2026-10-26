from playwright.sync_api import sync_playwright
BASE='http://127.0.0.1:8765/ui/'
IPHONE_UA='Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1'
SEED="""(()=>{ if(localStorage.getItem('seeded'))return; localStorage.setItem('seeded','1');
 localStorage.setItem('llmchat.settings',JSON.stringify({base:'',model:'mlx-community/Qwen3-30B-A3B-4bit',system:'',showThink:false,noThink:false}));
 const now=Date.now(); localStorage.setItem('llmchat.convs',JSON.stringify([
  {id:'c1',title:'SwiftUI 질문',updated:now,messages:[{role:'user',content:'안녕'},{role:'assistant',content:'<think>hi</think>안녕하세요! 무엇을 도와드릴까요?'}]},
  {id:'c2',title:'파이썬 코드 리뷰',updated:now-864e5,messages:[{role:'user',content:'리뷰해줘'},{role:'assistant',content:'좋아요.\\n\\n```py\\nprint(1)\\n```'}]},
  {id:'c3',title:'여행 계획',updated:now-3*864e5,messages:[{role:'user',content:'제주'},{role:'assistant',content:'3일 일정 추천'}]}]));
 localStorage.setItem('llmchat.current',JSON.stringify('c1')); })()"""

with sync_playwright() as p:
    b=p.chromium.launch()
    for scheme in ('dark','light'):
        c=b.new_context(viewport={'width':393,'height':852},device_scale_factor=3,is_mobile=True,has_touch=True,user_agent=IPHONE_UA,color_scheme=scheme)
        c.add_init_script(SEED); c.add_init_script("localStorage.setItem('visits','3');localStorage.setItem('a2hs.dismissed',String(Date.now()))")
        pg=c.new_page(); pg.goto(BASE+'#/'); pg.wait_for_timeout(900)
        pg.wait_for_timeout(300); pg.screenshot(path=f'shots/list-{scheme}.png')
        pg.locator('#convList li.row').nth(1).click(); pg.wait_for_timeout(800); pg.screenshot(path=f'shots/chat-{scheme}.png')
        pg.click('#backBtn'); pg.wait_for_timeout(600); pg.click('#openSettings'); pg.wait_for_timeout(800); pg.screenshot(path=f'shots/settings-{scheme}.png')
        pg.click('#cancelSettings'); pg.wait_for_timeout(500)
        pg.evaluate("localStorage.removeItem('a2hs.dismissed')"); pg.click('#openSettings'); pg.wait_for_timeout(600); pg.click('#showA2hs'); pg.wait_for_timeout(900)
        pg.screenshot(path=f'shots/install-{scheme}.png')
        c.close()
    b.close()
