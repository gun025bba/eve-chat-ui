# 1.10.2: a long answer is streaming, the device goes offline for ~5s and comes back → the live bubble must not stay on '답변 불러오는 중…':
# the app re-requests GET …/stream (Last-Event-ID) or re-polls, and the same bubble completes (one reply, no duplicate, no error)
import json, os, re, urllib.request
from playwright.sync_api import sync_playwright
M = 'http://127.0.0.1:' + os.environ.get('EVE_PORT', '8765'); BASE = M + '/ui/'
def req(method, path, body=None):
    r = urllib.request.Request(M + path, method=method, data=json.dumps(body).encode() if body is not None else None, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(r) as f: t = f.read(); return json.loads(t) if t else None
db = lambda: req('GET', '/__db')
R = []; errs = []
def check(name, ok, extra=''): R.append(bool(ok)); print('PASS' if ok else 'FAIL', name, '' if ok else extra)
SETTINGS = "localStorage.setItem('llmchat.settings',JSON.stringify({base:'',model:'mlx-community/Qwen3-30B-A3B-4bit',system:'',showThink:false,noThink:false}));localStorage.setItem('eve.mem.introSeen','1');"
for p in ('/auth/on', '/persist/on', '/db/reset', '/fail/clear'): req('PUT', p)
req('PUT', '/pro/set', {'snapOnly': False})
last_asst = lambda pg: pg.locator('.msg.assistant').last
def run(offline_s, label):
    req('PUT', '/db/reset'); req('PUT', '/pro/reset')
    with sync_playwright() as p:
        b = p.chromium.launch(); ctx = b.new_context(viewport={'width': 393, 'height': 852}, is_mobile=True, has_touch=True)
        ctx.add_init_script("if(!sessionStorage.getItem('s')){sessionStorage.setItem('s',1);" + SETTINGS + "}")
        pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto(BASE + '#/'); pg.wait_for_timeout(1200); pg.evaluate('__app.newChat()'); pg.wait_for_timeout(300)
        pg.fill('#input', 'detachslow 긴 답변'); pg.click('#sendBtn'); pg.wait_for_timeout(2200)
        t0 = last_asst(pg).inner_text(); check(f'{label}: answer is streaming before the cut', 'A0' in t0 and 'A39' not in t0, t0)
        n0 = len((db()['state'].get('resumes') or []))
        ctx.set_offline(True); pg.evaluate("window.dispatchEvent(new Event('offline'))"); pg.wait_for_timeout(int(offline_s * 1000))
        ctx.set_offline(False); pg.evaluate("window.dispatchEvent(new Event('online'))")
        pg.wait_for_timeout(2500)
        mid_t = last_asst(pg).inner_text()
        pg.wait_for_timeout(9000)
        t = last_asst(pg).inner_text(); rs = (db()['state'].get('resumes') or [])
        check(f'{label}: reply completes within ~12s of coming back online (no stuck "답변 불러오는 중…")', all(re.search(rf'\bA{k}\b', t) for k in range(40)) and '답변 불러오는 중' not in t, (mid_t[-60:], t[-80:]))
        check(f'{label}: exactly one assistant bubble, no error, no duplicate text', pg.locator('.msg.assistant').count() == 1 and pg.locator('.msg.error').count() == 0 and len(re.findall(r'\bA0\b', t)) == 1, (pg.locator('.msg.assistant').count(), pg.locator('.msg.error').count()))
        check(f'{label}: the stream was re-requested after the cut (GET …/stream with Last-Event-ID) or the message was re-read', len(rs) > n0 or bool(re.search(r'\bA39\b', t)), (n0, len(rs)))
        check(f'{label}: the bubble is the live one — message id set, no note left', bool(pg.evaluate("[...document.querySelectorAll('.msg.assistant')].pop().dataset.mid")) and last_asst(pg).locator('.msg-note').count() == 0)
        # reload shows the same single complete reply
        pg.reload(); pg.wait_for_timeout(1500); pg.evaluate("document.querySelector('#convList li.row .row-main')?.click()"); pg.wait_for_timeout(1200)
        t2 = pg.locator('.msg.assistant').last.inner_text() if pg.locator('.msg.assistant').count() else ''
        check(f'{label}: after reload the thread holds one complete reply', pg.locator('.msg.assistant').count() == 1 and bool(re.search(r'\bA39\b', t2)), t2[-60:])
        ctx.close(); b.close()
run(5, 'offline 5s')
run(2, 'offline 2s')
check('no page errors', not errs, errs)
print(f'{sum(R)}/{len(R)} passed')
raise SystemExit(0 if all(R) else 1)
