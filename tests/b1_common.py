# 1.10.0 B1 shared helpers: mock REST helpers, fixtures, thread opener (DIRECTION-B-SPEC d196833)
import json, os, urllib.request
from datetime import datetime, timedelta, timezone
M = 'http://127.0.0.1:' + os.environ.get('EVE_PORT', '8765'); B = M
KST = timezone(timedelta(hours=9))
SETTINGS = "localStorage.setItem('llmchat.settings',JSON.stringify({base:'',model:'mlx-community/Qwen3-30B-A3B-4bit',system:'',showThink:false,noThink:false}));localStorage.setItem('eve.mem.introSeen','1');localStorage.setItem('eve.flag.memory','1');"
def req(method, path, body=None):
    r = urllib.request.Request(M + path, method=method, data=json.dumps(body).encode() if body is not None else None, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(r) as f: t = f.read(); return json.loads(t) if t else None
put = lambda p, body=None: req('PUT', p, body)
def iso(dt): return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
def reset(): put('/auth/on'); put('/persist/on'); put('/db/reset'); put('/fail/clear'); put('/pro/reset')
def src(specs): return [{'n': i, 'title': f'제목 {i}', 'url': f'https://{d}/p/{i}', 'domain': d} for i, d in enumerate(specs, 1)]
S1 = src(['a.example.com']); S2 = src(['a.example.com', 'b.example.com']); S5 = src(['a.example.com', 'b.example.com', 'c.example.com', 'd.example.com', 'e.example.com'])
MEM1 = [{'id': '01JMEM00000000000000000002', 'text': '아침 브리핑은 한국어로 짧게 받는 걸 선호'}]
MEM2 = MEM1 + [{'id': '01JMEM00000000000000000003', 'text': '다음 주 발표 준비 중'}]
MEM3 = MEM2 + [{'id': '01JMEM00000000000000000001', 'text': '이름은 건영'}]
def at(h, m, day=0): return iso(datetime.now(KST).replace(hour=h, minute=m, second=0, microsecond=0) + timedelta(days=day))
ACT = {'action_id': '01JACT00000000000000000001', 'tool': 'calendar_add_event', 'tool_version': '1', 'summary': '일정 추가', 'scopes': ['calendar.write'], 'payload_hash': 'sha256:pim', 'expires_at': '2099-01-01T00:00:00Z', 'tainted': False,
       'provenance': {'actor': 'user', 'job_id': None, 'job_name': None},
       'payload_view': {'verb': 'add', 'title': '치과', 'start': '2026-10-29T15:00:00+09:00', 'end': '2026-10-29T16:00:00+09:00', 'all_day': False, 'display': '10/29 (목) 15:00–16:00', 'location': '역삼동 치과', 'notes': None, 'calendar_id': 'cal_1', 'calendar': '개인'}}
def open_thread(pg, title):
    pg.goto(B + '/ui/#/log'); pg.reload(); pg.wait_for_timeout(1300)   # 1.10.0 B2: the root is Today; the thread list is the log
    if pg.evaluate("document.getElementById('app').dataset.route") == 'chat': pg.evaluate('history.back()'); pg.wait_for_timeout(400)
    pg.locator('#convList li.row', has_text=title).first.click(); pg.wait_for_timeout(1200)
def seed(title, messages, **kw): return put('/b1/seed', dict(title=title, messages=messages, **kw))
def new_ctx(b, w=390, h=844, scheme='dark', **kw):
    ctx = b.new_context(viewport={'width': w, 'height': h}, has_touch=True, is_mobile=True, device_scale_factor=kw.pop('dsf', 1), color_scheme=scheme, **kw)
    ctx.add_init_script("if(!sessionStorage.getItem('s')){sessionStorage.setItem('s',1);" + SETTINGS + "}")
    return ctx
