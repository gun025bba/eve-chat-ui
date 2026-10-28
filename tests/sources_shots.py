# 390px review shots for 1.9.0 source chips: python sources_shots.py <outdir>
# {1,2,5} sources × {collapsed,expanded} × {dark,light} → sources-<n>-<state>-<scheme>.png
import os, sys
from playwright.sync_api import sync_playwright
B = 'http://127.0.0.1:' + os.environ.get('EVE_PORT', '8765'); out = sys.argv[1]; os.makedirs(out, exist_ok=True)
ALL = [('서울 주간 날씨 예보: 화요일부터 기온 뚝, 수요일 비 소식', 'weather.go.kr'), ('기상청 중기예보 해설 — 이번 주 대기 정체와 미세먼지 전망까지 길게 정리', 'kma.go.kr'),
  ('Seoul weekly forecast', 'accuweather.com'), ('서울 날씨 10일', 'weather.naver.com'), ('Korea weather news', 'koreaherald.com')]
FAV = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAIAAAD8GO2jAAAAKklEQVR4nGNgWDGNtmjUglELRi0YtWDUglELRi0YtWDUglELRi0YKhYAAPfi+D1bzCJ8AAAAAElFTkSuQmCC'  # synthetic teal square: stands in for a server-provided favicon on source 1 (others fall back to monogram)
SRC = lambda n: [dict({'n': i, 'title': t, 'url': f'https://www.{d}/a/{i}', 'domain': d}, **({'favicon': FAV} if i == 1 else {})) for i, (t, d) in enumerate(ALL[:n], 1)]
MD = {1: '이번 주 서울은 화요일부터 기온이 크게 떨어져요[1].', 2: '이번 주 서울은 화요일부터 기온이 크게 떨어져요[1]. 수요일에는 비 소식이 있어요[2].',
      5: '이번 주 서울은 화요일부터 기온이 크게 떨어져요[1][2]. 수요일에는 비 소식이 있어요[3].\n\n- 기온: 아침 4도[4]\n- 주말: 맑음[5]'}
with sync_playwright() as p:
    b = p.chromium.launch()
    for scheme in ['dark', 'light']:
        ctx = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=scheme); pg = ctx.new_page()
        pg.add_init_script("localStorage.setItem('eve.mem.introSeen','1')")
        pg.goto(B + '/ui/#/'); pg.wait_for_timeout(1000); pg.evaluate("__app.newChat()"); pg.wait_for_timeout(600)
        for n in [1, 2, 5]:
            pg.evaluate("""([md,src])=>{const m=document.getElementById('messages');m.innerHTML='';
              const u=document.createElement('div');u.className='msg user';u.innerHTML='<div class="bubble">이번 주 서울 날씨 정리해 줘</div>';m.appendChild(u);
              const d=document.createElement('div');d.className='msg assistant';d.id='shot';d.innerHTML='<div class="bubble"><div class="md">'+renderMarkdown(md,src)+'</div>'+renderSources(src)+'</div>';m.appendChild(d)}""", [MD[n], SRC(n)])
            pg.wait_for_timeout(300); pg.screenshot(path=f'{out}/sources-{n}-collapsed-{scheme}.png')
            pg.locator('#shot .sc').first.click(); pg.wait_for_timeout(700); pg.screenshot(path=f'{out}/sources-{n}-expanded-{scheme}.png')
        ctx.close()
    b.close()
