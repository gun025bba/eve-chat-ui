# 390px review shots for 1.5.0 compact sources: python sources_shots.py <outdir>
import os, sys
from playwright.sync_api import sync_playwright
B = 'http://127.0.0.1:' + os.environ.get('EVE_PORT', '8765'); out = sys.argv[1]; os.makedirs(out, exist_ok=True)
SRC = [{'n': i, 'title': t, 'url': f'https://www.{d}/a/{i}', 'domain': d} for i, (t, d) in enumerate([
  ('서울 주간 날씨 예보: 화요일부터 기온 뚝, 수요일 비 소식', 'weather.go.kr'), ('기상청 중기예보 해설 — 이번 주 대기 정체와 미세먼지 전망까지 길게 정리', 'kma.go.kr'),
  ('Seoul weekly forecast', 'accuweather.com'), ('서울 날씨 10일', 'weather.naver.com'), ('Korea weather news', 'koreaherald.com'),
  ('주간 날씨 정리', 'news.kbs.co.kr'), ('대기질 예보', 'airkorea.or.kr')], 1)]
MD = '이번 주 서울은 화요일부터 기온이 크게 떨어져요[1][2]. 수요일에는 비 소식이 있어요[3].\n\n- 미세먼지: 보통~나쁨[7]\n- 주말: 맑음[4, 5]'
with sync_playwright() as p:
    b = p.chromium.launch()
    for scheme in ['dark', 'light']:
        ctx = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=scheme); pg = ctx.new_page()
        pg.add_init_script("localStorage.setItem('eve.mem.introSeen','1')")
        pg.goto(B + '/ui/#/'); pg.wait_for_timeout(1000); pg.click('#newChat'); pg.wait_for_timeout(600)
        pg.evaluate("""([md,src])=>{const m=document.getElementById('messages');m.querySelector('.empty')?.remove();
          const u=document.createElement('div');u.className='msg user';u.innerHTML='<div class="bubble">이번 주 서울 날씨 정리해 줘</div>';m.appendChild(u);
          const d=document.createElement('div');d.className='msg assistant';d.id='shot';d.innerHTML='<div class="bubble"><div class="md">'+renderMarkdown(md,src)+'</div>'+renderSources(src)+'</div>';m.appendChild(d)}""", [MD, SRC])
        pg.wait_for_timeout(300); pg.screenshot(path=f'{out}/collapsed-{scheme}.png')
        pg.locator('#shot sup.cite a').nth(1).click(); pg.wait_for_timeout(200); pg.screenshot(path=f'{out}/cite-tap-highlight-{scheme}.png')
        pg.wait_for_timeout(700); pg.screenshot(path=f'{out}/expanded-{scheme}.png')
        pg.click('#shot .src-all'); pg.wait_for_timeout(700); pg.screenshot(path=f'{out}/sheet-{scheme}.png')
        ctx.close()
    b.close()
