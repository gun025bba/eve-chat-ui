"""Mock gateway: OpenAI-compatible chat + threads/messages/feedback/search/import (backend contract v10)."""
import os
PORT = os.environ.get('EVE_PORT', '8765')   # tests may run on another port
import json, time, os, re, html, threading
from datetime import datetime, timezone, timedelta
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
CSP = "default-src 'self'; img-src 'self' data:; connect-src 'self'"
UI = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
STATE = {'n429': 0, 'authed': True, 'authHeader': False, 'persist': True, 'fail': {}, 'delay': {}, 'calls': []}
DB = {'threads': {}, 'messages': {}, 'seq': 0, 'imports': {}}
PRO = {}
def pro_reset(): PRO.clear(); PRO.update(supported=True, settings={'proactive': {'enabled': False, 'quiet_hours': {'start': '22:00', 'end': '08:00'}, 'memory_read': False}, 'memory': {'enabled': False}}, system={'proactive_available': True, 'tools_available': True, 'memory_read_only': False, 'memory_available': True}, actions={}, subs=[], reads=[], bodies=[], origins=[], issued=0, memDeletes=[], memWrites=[], memItems=[
    {'id': '01JMEM00000000000000000001', 'kind': 'profile', 'text': '이름은 건영', 'pinned': True, 'confidence': 'user', 'updated_at': '2026-10-01T00:00:00Z', 'expires_at': None},
    {'id': '01JMEM00000000000000000002', 'kind': 'preference', 'text': '아침 브리핑은 한국어로 짧게 받는 걸 선호', 'pinned': False, 'confidence': 'confirmed', 'updated_at': '2026-10-20T00:00:00Z', 'expires_at': None},
    {'id': '01JMEM00000000000000000003', 'kind': 'task', 'text': '다음 주 발표 준비 중', 'pinned': False, 'confidence': 'user', 'updated_at': '2026-10-10T00:00:00Z', 'expires_at': '2099-11-25T00:00:00Z'},
    {'id': '01JMEM00000000000000000004', 'kind': 'fact', 'text': '<img src=x onerror=alert(1)> 고양이 이름은 나비', 'pinned': False, 'confidence': 'user', 'updated_at': '2026-10-25T00:00:00Z', 'expires_at': None}])
pro_reset()
LOCK = threading.RLock()
def now(off=0): return (datetime.now(timezone.utc) + timedelta(seconds=off)).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
GEN = {}   # §3.8 detached generation: mid -> {'ev': [(seq, event, data)], 'done': bool}
def gen_run(mid, kind):
    import threading
    g = GEN[mid]
    def push(event, obj):
        with LOCK: g['ev'].append((len(g['ev']) + 1, event, obj))
    def body():
        m = DB['messages'][mid]; acc = []
        push(None, {"object": "chat.completion.chunk", "choices": [{"delta": {"role": "assistant"}}]})
        if kind in ('err', 'errra'):
            acc.append('partial '); m['content'] = ''.join(acc); push(None, {"choices": [{"delta": {"content": 'partial '}}]}); time.sleep(0.3)
            push(None, {"error": dict({"message": "upstream timed out", "type": "server_error", "code": "upstream_timeout"}, **({"retry_after": 2} if kind == 'errra' else {}))})
            m.update(status='failed', error_code='upstream_timeout')
            push(None, {"object": "chat.completion.persisted", "status": "failed", "thread_id": m['thread_id'], "message_id": mid})
        else:
            for k in range(10 if kind != 'slow' else 40):
                if g.get('cancel'):
                    m.update(status='failed', error_code='cancelled')
                    push(None, {"error": {"code": "cancelled", "message": "cancelled"}})
                    push(None, {"object": "chat.completion.persisted", "status": "failed", "thread_id": m['thread_id'], "message_id": mid})
                    push(None, '[DONE]'); g['done'] = True; return
                t = f'A{k} '; acc.append(t)
                with LOCK: m['content'] = ''.join(acc)
                push(None, {"choices": [{"delta": {"content": t}}]}); time.sleep(0.3)
            m['status'] = 'complete'
            push(None, {"object": "chat.completion.persisted", "status": "complete", "thread_id": m['thread_id'], "message_id": mid})
        push(None, '[DONE]'); g['done'] = True
    threading.Thread(target=body, daemon=True).start()
def nid(p):
    DB['seq'] += 1; return f'01JMQCK{p.upper()[:1]}{DB["seq"]:018d}'   # 26-char ULID-like
def preview(tid):
    ms = [m for m in DB['messages'].values() if m['thread_id'] == tid]
    return ms[-1]['content'][:80] if ms else ''
def tview(t):
    ms = [m for m in DB['messages'].values() if m['thread_id'] == t['id']]
    return dict(t, message_count=len(ms), last_message_preview=preview(t['id']), unread_count=sum(1 for m in ms if m.get('origin') == 'proactive' and not m.get('read_at')))
def new_thread(title, created=None, archived=False, client_id=None):
    t = {'id': nid('th'), 'title': title, 'created_at': created or now(), 'updated_at': created or now(), 'archived': archived}
    if client_id: t['client_id'] = client_id
    DB['threads'][t['id']] = t; return t
def add_msg(tid, role, content, **kw):
    m = {'id': nid('m'), 'thread_id': tid, 'role': role, 'content': content, 'created_at': kw.pop('created_at', None) or now(), 'status': 'complete'}
    m.update(kw); DB['messages'][m['id']] = m; DB['threads'][tid]['updated_at'] = now(); return m
def ec(code): return {'error_code': code}   # 선톡/actions API error body
def err(code, typ='invalid_request_error', msg=None): return {"error": {"code": code, "message": msg or code, "type": typ, "request_id": "req_mock"}}
class H(SimpleHTTPRequestHandler):
    protocol_version = 'HTTP/1.0'
    def __init__(s, *a, **k): super().__init__(*a, directory=UI, **k)
    def log_message(s, *a): pass
    def end_headers(s):
        if getattr(s, '_csp', False): s.send_header('Content-Security-Policy', STATE.get('csp_value') or CSP)
        super().end_headers()
    def j(s, code, obj, hdr=None):
        b = json.dumps(obj).encode() if obj is not None else b''
        s.send_response(code); s.send_header('Content-Type', 'application/json')
        for k, v in (hdr or {}).items(): s.send_header(k, v)
        s.end_headers(); s.wfile.write(b)
    def auth(s):
        if s.headers.get('Authorization'): STATE['authHeader'] = True
        if STATE.get('denied'): s.j(401, err('identity_not_allowed', 'authentication_error', 'not allowed')); return False
        if STATE.get('invalidSession'): s.j(401, err('invalid_session', 'authentication_error', 'Session expired or revoked: pair this browser again.')); return False
        if not STATE['authed']: s.j(401, {"error_code": "unauthenticated"} if STATE.get('auth4') else err('unauthenticated', 'authentication_error', 'Tailscale identity required')); return False
        if STATE.get('scope403') and urlparse(s.path).path.startswith('/v1/chat'): s.j(403, {"error_code": "scope_denied"}); return False
        return True
    def body(s):
        n = int(s.headers.get('Content-Length') or 0); return json.loads(s.rfile.read(n)) if n else {}
    def pro_api(s, method, path):
        """선톡 P1 mock (planned/mock endpoints, see proactive-api.js ENDPOINTS)."""
        import re as _re
        m_read = _re.fullmatch(r'/v1/messages/([^/]+)/read', path); m_tread = _re.fullmatch(r'/v1/threads/([^/]+)/read', path); m_rev = _re.fullmatch(r'/v1/proposals/([^/]+)/revise', path); m_act = _re.fullmatch(r'/v1/actions/([^/]+)/(reissue|approve|reject)', path)
        if not ((_re.fullmatch(r'/v1/actions/[^/]+', path) and method == 'GET') or path in ('/v1/settings', '/v1/actions', '/v1/push/vapid-public-key', '/v1/push/subscriptions', '/v1/briefing/preview') or m_read or m_act or m_tread or m_rev or path in ('/v1/memory', '/v1/memory/export', '/v1/memory/items') or _re.fullmatch(r'/v1/memory/items/[^/]+', path)): return False
        if not s.auth(): return True
        if not PRO['supported']: s.j(404, ec('not_found')); return True
        if method != 'GET': PRO['origins'].append(s.headers.get('Origin'))
        b = s.body() if method in ('POST', 'PATCH', 'DELETE') else {}
        PRO['bodies'].append({'m': method, 'p': path, 'b': b})
        with LOCK:
            _ac = PRO.get('actCode') or {}; _kind = m_act.group(2) if m_act else ('revise' if m_rev else None)
            if _kind in _ac: st_, code_ = _ac.pop(_kind); s.j(st_, ec(code_)); return True   # e.g. backend #38: 403 scope_denied for non-browser sessions
            m_one = _re.fullmatch(r'/v1/actions/([^/]+)', path)
            if m_one and method == 'GET':
                if PRO.get('getDelay'): __import__('time').sleep(PRO['getDelay'])
                a = PRO['actions'].get(m_one.group(1))
                if not a or PRO.get('noSingleGet'): s.j(404, ec('not_found')); return True
                s.j(200, {k: v for k, v in a.items() if k != 'token'}); return True
            if m_read:
                m = DB['messages'].get(m_read.group(1))
                if not m or m.get('origin') != 'proactive': s.j(404, ec('not_found')); return True
                m['read_at'] = now(); PRO['reads'].append(m['id']); s.j(204, None); return True
            if m_tread:
                PRO['threadReads'] = PRO.get('threadReads', []) + [m_tread.group(1)]
                for m in DB['messages'].values():
                    if m['thread_id'] == m_tread.group(1) and m.get('origin') == 'proactive' and not m.get('read_at'): m['read_at'] = now()
                s.j(200, {'unread_count': 0}); return True
            if m_rev:
                a = PRO['actions'].get(m_rev.group(1))
                if PRO.get('revise410'): s.j(410, ec('expired')); return True
                if not a or a['status'] not in ('pending', 'expired'): s.j(409, ec('conflict')); return True
                ids = b.get('item_ids'); items = (a.get('payload_view') or {}).get('items', [])
                if ids is not None and (not ids or not set(ids) <= {i.get('id') for i in items}): s.j(409, ec('item_gone')); return True
                PRO['revisions'] = PRO.get('revisions', 0) + 1; nid = a['action_id'][:-2] + 'V%d' % PRO['revisions']
                pv = dict(a.get('payload_view') or {}); 
                if ids is not None: pv['items'] = [i for i in items if i.get('id') in ids]
                a['status'] = 'superseded'
                na = dict(a, action_id=nid, payload_view=pv, payload_hash='sha256:rev%d' % PRO['revisions'], status='pending', token='revtok%d' % PRO['revisions'], expires_at=now(600))
                PRO['actions'][nid] = na
                if set(b) - {'item_ids'}: s.j(400, ec('invalid')); return True
                out = {k: v for k, v in na.items() if k not in ('token', 'status', 'thread_id')}
                if PRO.get('reviseNoToken'): na['token'] = None
                else: out.update(confirm_token=na['token'], token_expires_at=now(PRO.get('tokenTtl', 120)))
                s.j(200, out); return True
            # Part B memory mock — ui-api-contract §3.9 (eve-serving PR #32).
            # memMode: None (on) | 'off' (server off: system.memory_available=false + {"detail":"Not Found"} 404) | 'gone' (available but routes 404 detail)
            #          | 'kill' (403 kill_switch, approve-only in reality) | 'e429' (429 {error:{code:rate_limited}})
            #          | 'ro' (503 legacy {error:{code:memory_read_only}} on writes) | 'e500' (500 legacy internal_error on writes) | 'drop' (network failure)
            m_mi = _re.fullmatch(r'/v1/memory/items/([^/]+)', path)
            if path in ('/v1/memory', '/v1/memory/export', '/v1/memory/items') or m_mi:
                mode = PRO.get('memMode')
                if mode == 'drop': s.close_connection = True; s.connection.shutdown(2); return True
                if mode in ('off', 'gone'): s.j(404, {'detail': 'Not Found'}); return True
                def raw(st, obj, extra=()):
                    s.send_response(st); s.send_header('Content-Type', 'application/json'); s.send_header('Cache-Control', 'no-store')
                    for k, v in extra: s.send_header(k, v)
                    b2 = json.dumps(obj).encode(); s.send_header('Content-Length', str(len(b2))); s.end_headers(); s.wfile.write(b2)
                ups = max([i['updated_at'] for i in PRO['memItems']] or [None])
                if method == 'GET' and path in ('/v1/memory', '/v1/memory/export'):
                    raw(200, {'object': 'memory', 'updated_at': ups, 'items': PRO['memItems']}, [('Content-Disposition', 'attachment; filename="memory.json"')] if 'export' in path else []); return True
                if method == 'GET': s.j(405, ec('invalid')); return True
                PRO['memWrites'].append({'method': method, 'path': path, 'body': b, 'xer': s.headers.get('X-Eve-Request'), 'ct': s.headers.get('Content-Type')})
                if m_mi and method == 'DELETE': PRO['memDeletes'].append({'id': m_mi.group(1), 'xer': s.headers.get('X-Eve-Request'), 'ct': s.headers.get('Content-Type'), 'origin': s.headers.get('Origin')})
                if s.headers.get('X-Eve-Request') != '1': s.j(403, ec('invalid')); return True
                if mode == 'kill': s.j(403, ec('kill_switch')); return True
                if mode == 'ro' or PRO.get('memDelRO'): s.j(503, err('memory_read_only', 'server_error', 'memory is read-only')); return True
                if mode == 'e429': s.j(429, err('rate_limited', 'rate_limit_error', 'slow down')); return True
                if mode == 'e500': s.j(500, err('internal_error', 'server_error', 'audit write failed')); return True
                if PRO.get('memDelDrop') and method == 'DELETE': PRO['memDelDrop'] = False; s.close_connection = True; s.connection.shutdown(2); return True
                ts = '2026-10-27T05:00:%02dZ' % (len(PRO['memWrites']) % 60)
                if path == '/v1/memory' and method == 'DELETE': PRO['memItems'] = []; s.j(204, None); return True
                if path == '/v1/memory/items' and method == 'POST':
                    if not isinstance(b, dict) or set(b) - {'kind', 'text', 'pinned', 'expires_at'} or b.get('kind') not in ('profile', 'preference', 'fact', 'task') or not isinstance(b.get('text'), str) or not b['text'] or len(b['text']) > 300: s.j(400, ec('invalid')); return True
                    if _re.search(r'(?i)password|sk-[a-z0-9]{8}|\d{4}-\d{4}-\d{4}-\d{4}', b['text']): s.j(422, ec('secret_detected')); return True
                    if len(PRO['memItems']) >= PRO.get('memCap', 200): s.j(422, ec('cap_exceeded')); return True
                    it = {'id': '01JMEMNEW%017d' % len(PRO['memWrites']), 'kind': b['kind'], 'text': b['text'], 'pinned': b.get('pinned', b['kind'] == 'profile'), 'confidence': 'user', 'created_at': ts, 'updated_at': ts, 'expires_at': b.get('expires_at')}
                    PRO['memItems'].append(it); s.j(201, it); return True
                cur = next((i for i in PRO['memItems'] if m_mi and i['id'] == m_mi.group(1)), None)
                if m_mi and method == 'DELETE':
                    if not cur: s.j(404, ec('not_found')); return True
                    PRO['memItems'].remove(cur); s.j(204, None); return True
                if m_mi and method == 'PATCH':
                    if not isinstance(b, dict) or set(b) - {'text', 'pinned', 'expires_at', 'if_updated_at'}: s.j(400, ec('invalid')); return True
                    if not cur: s.j(404, ec('not_found')); return True
                    if b.get('if_updated_at') and b['if_updated_at'] != cur['updated_at']: s.j(409, ec('conflict')); return True
                    if 'text' in b and (not isinstance(b['text'], str) or not b['text'] or len(b['text']) > 300): s.j(400, ec('invalid')); return True
                    cur.update({k: v for k, v in b.items() if k != 'if_updated_at'}, updated_at=ts); s.j(200, cur); return True
                s.j(405, ec('invalid')); return True
            if path == '/v1/briefing/preview':   # eve-serving #77: 200 {status,text,sections} | 502 {status,sections} | 404 off | 403 scope_denied
                PRO['previews'] = PRO.get('previews', 0) + 1
                if PRO.get('briefingDelay'): time.sleep(PRO['briefingDelay'])
                if PRO.get('briefingDrop'): s.close_connection = True; s.connection.shutdown(2); return True
                st_, body_ = PRO.get('briefing') or (200, {'status': 'ok', 'text': '오늘 2026-10-27(화) 브리핑\n일정 2건\n- 09:30 팀 스탠드업\n- 종일 출장\n리마인더 1건\n- (기한 지남) 10/25 세금 납부', 'sections': [{'name': 'events', 'count': 2}, {'name': 'reminders', 'count': 1}]})
                s.j(st_, body_); return True
            if path == '/v1/settings':
                if PRO.get('settingsDrop'): s.close_connection = True; s.connection.shutdown(2); return True
                if method == 'PATCH':
                    if 'ui' in b and PRO.get('uiKey'): PRO.setdefault('settings', {}).setdefault('ui', {}); PRO['settings']['ui'].update(b.pop('ui'))
                    if not b: s.j(200, dict(PRO['settings'], system=PRO['system'])); return True
                    if PRO.get('failSettings'): s.j(500, ec('invalid')); return True
                    if 'memory' in b and PRO.get('memMode') == 'off': s.j(400, ec('invalid')); return True
                    if 'memory' in b and PRO.get('memMode') == 'ro': s.j(503, err('memory_read_only', 'server_error', 'memory is read-only')); return True
                    ok = set(b) <= {'proactive', 'memory'}   # system.* is read-only → 400 and set(b.get('proactive') or {}) <= {'enabled', 'quiet_hours', 'memory_read'} and set(b.get('memory') or {}) <= {'enabled'}
                    q = (b.get('proactive') or {}).get('quiet_hours')
                    if q is not None and (set(q) != {'start', 'end'} or not all(_re.fullmatch(r'\d{2}:\d{2}', q[k]) for k in q)): ok = False
                    if not ok: s.j(400, ec('invalid')); return True
                    for k, v in b.items(): PRO['settings'][k].update(v)
                out = dict(PRO['settings'], system=PRO['system'])
                if PRO.get('memMode') in ('off', 'availOff'): out['system'] = dict(out['system'], memory_available=False)
                if PRO.get('memNoKey'): out.pop('memory', None)   # missing memory key → off
                s.j(200, out); return True
            if path == '/v1/actions':
                s.j(200, {'data': [{k: v for k, v in a.items() if k not in ('token',)} for a in PRO['actions'].values() if a['status'] == 'pending' and a.get('thread_id')]}); return True
            if path == '/v1/push/vapid-public-key':
                s.j(200, {'key': 'BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkrxZJjSgSnfckjBJuBkr3qBUYIHBQFLXYp5Nksh8U', 'key_id': PRO.get('kid', 'k1')}); return True
            if path == '/v1/push/subscriptions':
                if method == 'POST': PRO['subs'].append(b); s.j(201, {'ok': True})
                else: PRO['subs'] = [x for x in PRO['subs'] if x.get('endpoint') != b.get('endpoint')]; s.j(204, None)
                return True
            aid, op = m_act.groups(); a = PRO['actions'].get(aid)
            if not a: s.j(404, ec('not_found')); return True
            if op == 'reissue':
                if a['status'] != 'pending': s.j(409, ec('conflict')); return True
                a['_re'] = a.get('_re', 0) + 1
                if a['_re'] > 3: s.j(422, ec('cap_exceeded')); return True
                PRO['issued'] += 1; a['token'] = f'tok{PRO["issued"]}'; s.j(200, {'confirm_token': a['token'], 'token_expires_at': now(PRO.get('tokenTtl', 120))}); return True
            if op == 'reject':
                a['status'] = 'rejected'; s.j(200, {'status': 'rejected'}); return True
            if PRO.get('approveRaw'): st, body_ = PRO.pop('approveRaw'); s.j(st, body_); return True   # 1.10.0: #78 502 bodies {status, action_id, error_code, outcome_unknown}
            if PRO.get('approveCode'): st, code = PRO.pop('approveCode'); s.j(st, ec(code)); return True
            if PRO.get('approveLegacy'): st, code = PRO.pop('approveLegacy'); s.j(st, err(code, 'server_error', code)); return True   # 500/503: legacy {error:{code}} body (§3.9.8)
            if not b.get('confirm_token'): s.j(400, ec('invalid')); return True
            if a['status'] != 'pending': s.j(409, ec('conflict')); return True
            if b.get('payload_hash') != a['payload_hash']: s.j(422, ec('payload_mismatch')); return True
            if b['confirm_token'] != a.get('token'): s.j(404, ec('not_found')); return True
            a['status'] = 'executed'; a['token'] = None
            if PRO.get('approveDrop'): PRO['approveDrop'] = False; s.close_connection = True; s.connection.shutdown(2); return True   # executed, response lost
            s.j(200, {'status': 'executed', 'result': {}}); return True
    def threads_api(s, method):
        u = urlparse(s.path); q = {k: v[0] for k, v in parse_qs(u.query).items()}; path = u.path
        if s.pro_api(method, path): return True
        if not path.startswith('/v1/threads') and not path.startswith('/v1/messages') and not path.startswith('/v1/search'): return False
        if not s.auth(): return True
        STATE['calls'].append(f'{method} {s.path}')
        if not STATE['persist']: s.j(503, err('persistence_disabled', 'server_error', 'conversation storage is disabled')); return True
        for pat, ms in STATE['delay'].items():   # 1.10.0 B2: /delay/<ms>?<regex> holds matching calls (skeleton tests)
            if re.search(pat, f'{method} {path}'): time.sleep(ms / 1000)
        for pat, code in STATE['fail'].items():
            if re.search(pat, f'{method} {path}'): s.j(code, err('mock_failure', 'server_error')); return True
        with LOCK:
            if path == '/v1/threads' and method == 'GET':
                arch = q.get('archived', 'false') == 'true'; lim = int(q.get('limit', 20)); off = int(q.get('cursor') or 0)
                ts = sorted([t for t in DB['threads'].values() if t['archived'] == arch], key=lambda t: t['updated_at'], reverse=True)
                if q.get('unread') == 'true': ts = [t for t in ts if tview(t)['unread_count'] > 0]
                page = ts[off:off + lim]
                return s.j(200, {'data': [tview(t) for t in page], 'next_cursor': str(off + lim) if off + lim < len(ts) else None}) or True
            if path == '/v1/threads' and method == 'POST':
                return s.j(201, tview(new_thread(s.body().get('title') or '새 대화'))) or True
            if path == '/v1/threads/import' and method == 'POST':
                if int(s.headers.get('Content-Length') or 0) > 5 * 1024 * 1024: return s.j(413, err('payload_too_large')) or True
                b = s.body(); res = []; ts = b.get('threads', [])
                bad = lambda t: not t.get('client_id') or not t.get('created_at') or any(m.get('role') not in ('user', 'assistant', 'system', 'tool') or not m.get('created_at') for m in t.get('messages', []))
                # contract: validation is per request -> whole batch 400 (importfail simulates a server-rejected thread)
                if any(bad(t) or ('importfail' in t.get('title', '') and not STATE.get('importfix')) for t in ts): return s.j(400, err('bad_request', msg='invalid thread in import')) or True
                for t in ts:
                    cid = t['client_id']
                    if cid in DB['imports']: res.append({'client_id': cid, 'thread_id': DB['imports'][cid], 'status': 'exists'}); continue
                    th = new_thread(t.get('title') or '대화', t.get('created_at'), t.get('archived', False), cid)
                    for m in t.get('messages', []):
                        add_msg(th['id'], m['role'], m.get('content', ''), created_at=m.get('created_at'), client_id=m['client_id'], **({'reasoning': m['reasoning']} if m.get('reasoning') else {}))
                    th['updated_at'] = max([x.get('created_at') or '' for x in t.get('messages', [])] + [t['created_at']])
                    DB['imports'][cid] = th['id']; res.append({'client_id': cid, 'thread_id': th['id'], 'status': 'created'})
                return s.j(200, {'results': res}) or True
            m = re.match(r'^/v1/threads/([^/]+)(/messages)?$', path)
            if m:
                t = DB['threads'].get(m.group(1))
                if not t: return s.j(404, err('not_found')) or True
                if m.group(2):
                    ms = [x for x in DB['messages'].values() if x['thread_id'] == t['id']]
                    if q.get('before'): ms = ms[:[x['id'] for x in ms].index(q['before'])] if q['before'] in [x['id'] for x in ms] else []
                    lim = int(q.get('limit', 50)); page = ms[-lim:]
                    return s.j(200, {'data': page, 'has_more': len(ms) > len(page)}) or True
                if method == 'GET': return s.j(200, tview(t)) or True
                if method == 'PATCH':
                    b = s.body()
                    if 'title' in b: t['title'] = b['title']
                    if 'archived' in b: t['archived'] = bool(b['archived'])
                    t['updated_at'] = now(); return s.j(200, tview(t)) or True
                if method == 'DELETE': t['archived'] = True; return s.j(204, None) or True
            m = re.match(r'^/v1/messages/([^/]+)/feedback$', path)
            if m:
                msg = DB['messages'].get(m.group(1))
                if not msg: return s.j(404, err('not_found')) or True
                if method == 'PUT':
                    b = s.body()
                    if b.get('rating') not in ('up', 'down'): return s.j(400, err('bad_request')) or True
                    STATE.setdefault('fbBodies', []).append(b)
                    allowed = {'down': ['wrong_info', 'too_long', 'misunderstood', 'over_refusal', 'bad_source', 'other'], 'up': ['accurate', 'concise', 'helpful', 'good_source']}[b['rating']]
                    rs = b.get('reasons', [])
                    if not isinstance(rs, list) or any(r not in allowed for r in rs) or STATE.get('rejectReasons') and rs: return s.j(400, err('invalid_feedback_reason')) or True
                    cm = b.get('comment')
                    if cm is not None and not isinstance(cm, str): return s.j(400, err('bad_request')) or True
                    if len((cm or '').strip()) > (139 if STATE.get('rejectComment') else 140): return s.j(400, err('feedback_comment_too_long')) or True
                    cm = (cm or '').strip() or None
                    old = msg.get('feedback') or {}; msg['feedback'] = {'message_id': msg['id'], 'rating': b['rating'], 'reasons': list(dict.fromkeys(rs)), 'comment': cm, 'created_at': old.get('created_at') or now(), 'updated_at': now()}; return s.j(200, msg['feedback']) or True
                if method == 'DELETE': msg.pop('feedback', None); return s.j(204, None) or True
            if path == '/v1/search':
                term = q.get('q', ''); out = []
                for t in sorted(DB['threads'].values(), key=lambda t: t['updated_at'], reverse=True):
                    if term.lower() in t['title'].lower(): out.append({'thread_id': t['id'], 'thread_title': t['title'], 'message_id': None, 'role': None, 'snippet': mark(t['title'], term), 'created_at': t['created_at'], 'match': 'title'})
                    for x in DB['messages'].values():
                        if x['thread_id'] == t['id'] and term.lower() in x['content'].lower():
                            out.append({'thread_id': t['id'], 'thread_title': t['title'], 'message_id': x['id'], 'role': x['role'], 'snippet': mark(x['content'], term), 'created_at': x['created_at'], 'match': 'content'})
                return s.j(200, {'data': out[:int(q.get('limit', 20))], 'next_cursor': None}) or True
        s.j(404, err('not_found')); return True
    def do_GET(s):
        if s.path == '/whoami':
            if STATE.get('whoamiFalse'): return s.j(200, {"authenticated": False})
            if s.auth(): s.j(200, {"authenticated": True, "user": "user@example.com", "provider": "tailscale-identity"})
            return
        if s.path == '/__db': return s.j(200, {'threads': list(DB['threads'].values()), 'messages': list(DB['messages'].values()), 'state': {k: v for k, v in STATE.items()}})
        if s.path == '/v1/models':
            if s.auth(): s.j(200, {"data": [{"id": "mlx-community/Qwen3-30B-A3B-4bit"}]})
            return
        mres = re.fullmatch(r'/v1/threads/([^/]+)/messages/([^/]+)/stream', urlparse(s.path).path)
        if mres:
            if not s.auth(): return
            tid, mid = mres.groups(); m = DB['messages'].get(mid); q = parse_qs(urlparse(s.path).query)
            STATE.setdefault('resumes', []).append({'mid': mid, 'lei': s.headers.get('Last-Event-ID'), 'xer': s.headers.get('X-Eve-Request')})
            if PRO.get('resume404') or not m or m['thread_id'] != tid or m['role'] != 'assistant': return s.j(404, err('not_found'))
            after = int(s.headers.get('Last-Event-ID') or (q.get('after') or ['0'])[0])
            if PRO.get('subs429', 0) > 0:
                PRO['subs429'] -= 1; return s.j(429, err('too_many_subscribers', 'rate_limit_error', 'too many subscribers'), {'Retry-After': '1'})
            s.send_response(200); s.send_header('Content-Type', 'text/event-stream'); s.send_header('Cache-Control', 'no-store'); s.end_headers()
            try:
                if PRO.get('snapLive') and mid in GEN:   # log overflow: snapshot (current content + last_event_id) then live
                    with LOCK: last = GEN[mid]['ev'][-1][0]; snap = dict(m, last_event_id=last)
                    s.wfile.write(('event: eve.snapshot\ndata: ' + json.dumps(snap) + '\n\n').encode()); s.wfile.flush()
                    return s.gen_stream(mid, last)
                if PRO.get('resumeCut', 0) > 0:   # 30s write deadline: server drops a slow reader
                    PRO['resumeCut'] -= 1; return s.gen_stream(mid, after, cut=3)
                if PRO.get('snapOnly') or mid not in GEN:
                    while m['status'] == 'generating': time.sleep(0.1)   # (test simplification: snapshot of the final row)
                    s.wfile.write(('event: eve.snapshot\ndata: ' + json.dumps(m) + '\n\ndata: [DONE]\n\n').encode()); return
                s.gen_stream(mid, after)
            except OSError: pass
            return
        if s.threads_api('GET'): return
        if s.path.startswith('/ui'): s.path = s.path[3:] or '/'; s._csp = bool(STATE.get('csp'))
        else: s.send_response(404); s.end_headers(); return
        super().do_GET()
    ORIGIN = 'http://127.0.0.1:' + PORT
    def gate(s, method):
        """Server rule: every POST/PUT/PATCH/DELETE on the API needs X-Eve-Request: 1 + exact allow-listed Origin,
        + Sec-Fetch-Site: same-origin, and a JSON Content-Type when it has a body → else 403 {error_code:'invalid'}. Test-control routes are exempt."""
        p = urlparse(s.path).path
        if not (p.startswith('/v1/') or p == '/whoami'): return True
        h = s.headers; has_body = int(h.get('Content-Length') or 0) > 0
        ok = h.get('X-Eve-Request') == '1' and h.get('Origin') == s.ORIGIN and h.get('Sec-Fetch-Site') == 'same-origin' and (not has_body or (h.get('Content-Type') or '').split(';')[0].strip() == 'application/json')
        STATE.setdefault('mut', []).append({'m': method, 'p': p, 'ok': ok, 'xer': h.get('X-Eve-Request'), 'origin': h.get('Origin'), 'ct': h.get('Content-Type'), 'sfs': h.get('Sec-Fetch-Site'), 'body': has_body})
        if not ok:
            if has_body: s.rfile.read(int(h.get('Content-Length')))
            s.j(403, ec('invalid'))
        return ok
    def do_PATCH(s): s.gate('PATCH') and (s.threads_api('PATCH') or s.j(404, err('not_found')))
    def do_DELETE(s):
        if not s.gate('DELETE'): return
        if urlparse(s.path).path == '/v1/session':   # 4.0.0 logout (eve-serving #65): revoke own session, clear cookie, 204
            STATE.setdefault('logouts', []).append({'t': time.time(), 'xer': s.headers.get('X-Eve-Request')}); STATE['authed'] = False
            return s.j(204, None, {'Set-Cookie': 'eve_session=; Max-Age=0; Path=/'})
        s.threads_api('DELETE') or s.j(404, err('not_found'))
    def ev(s, o): s.wfile.write(f'data: {json.dumps(o)}\n\n'.encode()); s.wfile.flush(); time.sleep(0.08)
    def do_POST(s):
        if not s.gate('POST'): return
        mc = re.fullmatch(r'/v1/threads/([^/]+)/messages/([^/]+)/cancel', urlparse(s.path).path)
        if mc:
            tid, mid = mc.groups(); m = DB['messages'].get(mid)
            STATE.setdefault('cancels', []).append({'mid': mid, 'len': int(s.headers.get('Content-Length') or 0)})
            if not m or m['thread_id'] != tid: return s.j(404, err('not_found'))
            if mid in GEN: GEN[mid]['cancel'] = True
            s.send_response(204); s.end_headers(); return
        if urlparse(s.path).path == '/v1/pair':   # 4.0.0 identity-transport §4: unauthenticated, 5 fails → code invalidated; success/failure only
            b = s.body(); STATE.setdefault('pairBodies', []).append(b)
            code = STATE.get('pairCode')
            if code and str(b.get('code', '')) == code:
                STATE.update(authed=True, pairCode=None, pairFails=0, invalidSession=False)
                return s.j(204, None, {'Set-Cookie': 'eve_session=mock; HttpOnly; SameSite=Strict; Path=/'})
            STATE['pairFails'] = STATE.get('pairFails', 0) + 1
            if STATE['pairFails'] >= 5: STATE['pairCode'] = None   # lock: outstanding codes voided
            return s.j(401, err('pair_failed', 'authentication_error', 'Pairing failed'))
        if s.threads_api('POST'): return
        body = s.body()
        if not s.auth(): return
        last = body['messages'][-1]['content']; STATE['last'] = last; STATE['so'] = body.get('stream_options'); STATE['lastBody'] = {k: v for k, v in body.items() if k != 'messages'}
        if last.startswith('q429') and STATE['n429'] == 0:
            STATE['n429'] = 1; return s.j(429, err('queue_full', 'rate_limit_error', 'queue full'))
        tid = body.get('thread_id'); th = None; um = None; rep = body.get('replace_message_id')
        if (tid or rep) and not STATE['persist']: return s.j(503, err('persistence_disabled', 'server_error', 'conversation storage is disabled'))
        if tid and tid != 'new' and tid not in DB['threads']: return s.j(404, err('not_found'))
        if rep and (tid in (None, 'new') or DB['messages'].get(rep, {}).get('thread_id') != tid): return s.j(404, err('not_found'))
        if rep and DB['messages'][rep]['role'] != 'assistant': return s.j(400, err('bad_request'))
        if last.startswith('dup409') and tid in DB['threads'] and not rep:   # eve-serving #62: same-turn resend while generating
            g = STATE.setdefault('dupGen', {}).get(tid)
            if g and g in GEN and not GEN[g]['done']:
                STATE['dup409n'] = STATE.get('dup409n', 0) + 1; shape = STATE.get('dupShape', 'nested')
                e = err('generation_in_progress', 'invalid_request_error', 'generation in progress')
                if shape == 'nested': e['error']['message_id'] = g
                elif shape == 'top': e['message_id'] = g
                elif shape == 'details': e['error']['details'] = {'message_id': g}
                return s.j(409, e)
            th = DB['threads'][tid]; add_msg(tid, 'user', last)
            am = s.save_asst(th, None, '', '', 'generating'); am.pop('error_code', None); mid = am['id']
            GEN[mid] = {'ev': [(1, 'eve.meta', {"thread_id": tid, "message_id": mid})], 'done': False}
            gen_run(mid, 'slow'); STATE['dupGen'][tid] = mid
            return s.j(503, err('server_busy', 'server_error', 'busy'))   # the client never saw this turn start
        with LOCK:
            if tid:
                th = new_thread(last[:40]) if tid == 'new' else DB['threads'].get(tid)
                if th and not rep: um = add_msg(th['id'], 'user', last)
        WS = body.get('web_search') in ('auto', 'force', True)
        if WS and STATE.get('webdisabled'): return s.j(400, err('web_search_disabled', 'invalid_request_error', 'web search is disabled'))
        SRCS = [{"n": 1, "title": "Eve 릴리스 노트", "url": "https://example.com/notes?a=1&b=2", "domain": "example.com", "fetched": True},
                {"n": 2, "title": "두 번째 출처 <b>bold</b>", "url": "https://docs.example.org/page", "domain": "docs.example.org", "fetched": False},
                {"n": 3, "title": "bad scheme", "url": "javascript:alert(1)", "domain": "evil", "fetched": False}]
        WSTEXT = "검색 결과에 따르면 Eve는 빠릅니다[1]. 자세한 내용은 문서를 보세요[2]. 없는 번호[9]와 `코드 [1]`.\n\n- 목록 항목[1, 2]"
        if WS and last.startswith('wsnostream'):
            out = {"id": "x", "object": "chat.completion", "choices": [{"message": {"role": "assistant", "content": WSTEXT, "sources": SRCS[:2]}}]}
            if th: am = s.save_asst(th, rep, WSTEXT, ''); am['sources'] = SRCS[:2]; out.update(thread_id=th['id'], message_id=am['id'])
            return s.j(200, out)
        if WS and last.startswith('ws'):
            s.send_response(200); s.send_header('Content-Type', 'text/event-stream'); s.end_headers()
            try:
                if th: s.ev({"object": "chat.completion.chunk", "choices": [], "thread_id": th['id'], "user_message_id": um['id'] if um else None})
                s.ev({"object": "chat.completion.tool_call", "id": "tc_1", "tool": "web_search", "args": {"query": "eve 속도"}, "round": 1}); time.sleep(0.8)
                s.ev({"object": "chat.completion.tool_result", "id": "tc_1", "tool": "web_search", "status": "ok", "sources": SRCS[:2]}); time.sleep(0.3)
                s.ev({"object": "chat.completion.tool_call", "id": "tc_2", "tool": "web_fetch", "args": {"url": "https://www.example.com/notes"}, "round": 2}); time.sleep(0.8)
                s.ev({"object": "chat.completion.tool_result", "id": "tc_2", "tool": "web_fetch", "status": "ok", "sources": SRCS[:1]}); time.sleep(0.6)
                s.ev({"id": "web-1", "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {"role": "assistant", "content": WSTEXT}, "finish_reason": "stop"}]})
                s.ev({"object": "chat.completion.sources", "sources": SRCS, "cited": [1, 2]})
                if th:
                    am = s.save_asst(th, rep, WSTEXT, ''); am['sources'] = SRCS[:2]
                    s.ev({"object": "chat.completion.persisted", "status": "complete", "thread_id": th['id'], "message_id": am['id'], "user_message_id": um['id'] if um else None})
                s.wfile.write(b'data: [DONE]\n\n')
            except (BrokenPipeError, ConnectionResetError): pass
            return
        if last.startswith('pim'):   # eve-serving #66 §11: PIM tool events (stream-only cards) — 'pim<scenario> …'
            import datetime as _dt
            KST = _dt.timezone(_dt.timedelta(hours=9)); n0 = _dt.datetime.now(KST); Y = n0.year
            iso = lambda y, mo, d, h=0, mi=0: _dt.datetime(y, mo, d, h, mi, tzinfo=KST).isoformat()
            scen = last.split()[0]; PRO['pimPrompts'] = PRO.get('pimPrompts', 0) + 1
            def tr(tool, **k): return dict({"object": "chat.completion.tool_result", "id": "pc_1", "tool": tool}, **k)
            def tc(tool, args): return {"object": "chat.completion.tool_call", "id": "pc_1", "tool": tool, "args": args, "round": 1}
            evs = []; text = "확인했어요."
            EV = [{"id": "evt_a1", "title": "팀 스탠드업 <img src=x onerror=alert(1)>", "start": iso(Y, 10, 28, 9, 30), "end": iso(Y, 10, 28, 10, 0), "all_day": False, "calendar": "회사", "calendar_id": "cal_1"},
                  {"id": "evt_a2", "title": "기념일", "start": iso(Y, 10, 28), "end": iso(Y, 10, 29), "all_day": True, "calendar": "개인", "calendar_id": "cal_2"},
                  {"id": "evt_a3", "title": "야간 배포", "start": iso(Y, 10, 28, 23, 0), "end": iso(Y, 10, 29, 1, 0), "all_day": False, "calendar": "회사", "calendar_id": "cal_1"},
                  {"id": "evt_a4", "title": "제주 여행", "start": iso(Y, 10, 30), "end": iso(Y, 11, 2), "all_day": True, "calendar": "개인", "calendar_id": "cal_2"},
                  {"id": "evt_a5", "title": "내년 일정", "start": iso(Y + 1, 1, 5, 9, 0), "end": iso(Y + 1, 1, 5, 10, 0), "all_day": False, "calendar": "개인", "calendar_id": "cal_2"}]
            RNG = {"from": iso(Y, 10, 28), "to": iso(Y, 10, 29)}
            if scen == 'pimcal':
                evs = [tc("calendar_list_events", {"from": RNG['from'], "to": RNG['to']}), tr("calendar_list_events", status="ok", count=5, truncated=False, card={"kind": "calendar_events", "v": 1, "range": {"from": iso(Y, 10, 28), "to": iso(Y, 11, 3)}, "items": EV})]
            elif scen == 'pimcal0':
                evs = [tc("calendar_list_events", {}), tr("calendar_list_events", status="ok", count=0, truncated=False, card={"kind": "calendar_events", "v": 1, "range": RNG, "items": []})]
            elif scen == 'pimrem':
                items = [{"id": f"rem_{i}", "title": f"할 일 {i}", "due": iso(Y, 10, 28, 18, 0) if i % 3 else None, "list": "장보기", "done": i == 2} for i in range(12)]
                evs = [tc("reminders_list", {"due_before": RNG['to'], "include_done": True}), tr("reminders_list", status="ok", count=100, truncated=True, card={"kind": "reminders", "v": 1, "due_before": RNG['to'], "items": items})]
            elif scen == 'pimerr':
                evs = [tc("calendar_list_events", {}), tr("calendar_list_events", status="denied", error_code="permission_denied", card={"kind": "error", "v": 1, "error_code": "permission_denied"})]; text = "캘린더를 확인하지 못했어요."
            elif scen == 'pimerrto':
                evs = [tc("reminders_list", {}), tr("reminders_list", status="timeout", error_code="timeout", card={"kind": "error", "v": 1, "error_code": "timeout"})]; text = "리마인더를 확인하지 못했어요."
            elif scen == 'pimerrunk':
                evs = [tc("reminders_list", {}), tr("reminders_list", status="error", error_code="brand_new_code", card={"kind": "error", "v": 1, "error_code": "brand_new_code"})]
            elif scen == 'pimkind':
                evs = [tc("calendar_list_events", {}), tr("calendar_list_events", status="ok", count=1, truncated=False, card={"kind": "heatmap", "v": 1, "items": [{"title": "x"}]})]
            elif scen == 'pimv2':
                evs = [tc("calendar_list_events", {}), tr("calendar_list_events", status="ok", count=1, truncated=False, card={"kind": "calendar_events", "v": 2, "range": RNG, "items": EV[:1]})]
            elif scen in ('pimadd', 'pimremadd', 'pimremdone', 'pimaddall', 'pimaddnull'):
                tool = 'calendar_add_event' if scen.startswith('pimadd') else ('reminders_complete' if scen == 'pimremdone' else 'reminders_add')
                aid = '01JBX0000000000000000000' + {'pimadd': 'C1', 'pimaddall': 'C2', 'pimaddnull': 'C3', 'pimremadd': 'A1', 'pimremdone': 'D1'}[scen]
                if tool == 'calendar_add_event':
                    pv = {"verb": "add", "title": "치과", "start": iso(Y, 10, 28, 15, 0), "end": iso(Y, 10, 28, 16, 0), "all_day": False, "display": f"10/28 ({'월화수목금토일'[_dt.date(Y, 10, 28).weekday()]}) 15:00–16:00", "location": "역삼동 치과", "notes": None, "calendar_id": "cal_1", "calendar": "개인"}
                    if scen == 'pimaddall': pv = dict(pv, title="가족 모임", all_day=True, display="10/30 (금) – 11/1 (일) 종일", location=None, notes="케이크 챙기기", start=iso(Y, 10, 30), end=iso(Y, 11, 2))
                    if scen == 'pimaddnull': pv = dict(pv, calendar_id=None, calendar="기본 캘린더", location=None)
                    summ, scopes = "일정 추가", ["calendar.write"]
                elif tool == 'reminders_add':
                    pv = {"verb": "add", "title": "우유 사기", "due": iso(Y, 10, 28, 18, 0), "display": f"10/28 ({'월화수목금토일'[_dt.date(Y, 10, 28).weekday()]}) 18:00", "list": None}; summ, scopes = "리마인더 추가", ["reminders.write"]
                else:
                    pv = {"verb": "update", "id": "rem_b1", "title": "우유 사기", "display": f"10/28 ({'월화수목금토일'[_dt.date(Y, 10, 28).weekday()]}) 18:00", "list": "장보기"}; summ, scopes = "리마인더 완료 처리", ["reminders.write"]
                act = {"action_id": aid, "thread_id": th['id'] if th else None, "message_id": None, "tool": tool, "tool_version": "1", "scopes": scopes, "payload_hash": "sha256:pim", "provenance": {"actor": "user", "job_id": None, "job_name": None},
                       "tainted": False, "status": "pending", "expires_at": now(900), "created_at": now(0), "summary": summ, "payload_view": pv}
                PRO['actions'][aid] = dict(act, status='pending', token=None)
                evs = [tc(tool, {}), tr(tool, status="pending_confirmation", action_id=aid), dict(act, object="chat.completion.confirmation")]; text = "추가할까요?"
            elif scen == 'pimwritedeny':
                evs = [tc("calendar_add_event", {}), tr("calendar_add_event", status="denied", error_code="secret_detected", card={"kind": "error", "v": 1, "error_code": "secret_detected"})]; text = "추가하지 못했어요."
            s.send_response(200); s.send_header('Content-Type', 'text/event-stream'); s.end_headers()
            try:
                if th: s.ev({"object": "chat.completion.chunk", "choices": [], "thread_id": th['id'], "user_message_id": um['id'] if um else None})
                for e in evs:
                    if e.get('object') == 'chat.completion.tool_result': time.sleep(PRO.get('pimGap', 0.7))
                    s.ev(e)
                time.sleep(PRO.get('pimGap', 0.7))
                s.ev({"id": "p-1", "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {"role": "assistant", "content": text}, "finish_reason": "stop"}]})
                if th:
                    am = s.save_asst(th, rep, text, '')
                    s.ev({"object": "chat.completion.persisted", "status": "complete", "thread_id": th['id'], "message_id": am['id'], "user_message_id": um['id'] if um else None})
                s.wfile.write(b'data: [DONE]\n\n')
            except (BrokenPipeError, ConnectionResetError): pass
            return
        if last.startswith('confirm'):
            act = {"action_id": "01JACT0000000000000000000S", "tool": "calendar_create_event", "tool_version": "1.0.0", "summary": "10/28 15:00 치과 일정 추가",
                   "payload_view": {"제목": "치과", "시각": "2026-10-28 15:00"}, "payload_hash": "sha256:abc", "expires_at": now(3600), "tainted": False, "scopes": ["calendar.write"], "provenance": {"actor": "user", "job_id": None, "job_name": None}}
            if last.startswith('confirmreminder') or last.startswith('confirmcomplete'):   # eve-serving #78 reminders_add / reminders_complete, exact Confirmation fields
                base = {"tool_version": "1.0.0", "scopes": ["reminders.write"], "payload_hash": "sha256:rem", "provenance": {"actor": "user"}, "tainted": False, "status": "pending",
                        "expires_at": now(900), "created_at": now(0)}
                if last.startswith('confirmcomplete'):
                    act = dict(base, action_id="01JACT0000000000000000000C", tool="reminders_complete", summary="리마인더 완료 처리", payload_view={"verb": "update", "method": "reminders.complete", "title": "세금 납부", "list": "개인"})
                elif last.startswith('confirmreminder0'):
                    act = dict(base, action_id="01JACT0000000000000000000Z", tool="reminders_add", summary="리마인더 추가", payload_view={"verb": "add", "method": "reminders.add", "title": "우유 사기"})
                else:
                    act = dict(base, action_id="01JACT0000000000000000000R", tool="reminders_add", summary="리마인더 추가", payload_view={"verb": "add", "method": "reminders.add", "title": "엄마께 전화 <b>드리기</b>", "due": "2026-10-28T18:00:00+09:00", "list": "개인"})
            if last.startswith('confirmdeny'):
                act = {"action_id": "01JACT0000000000000000000D", "tool": "memory.propose", "status": "denied", "error_code": "secret_detected", "scopes": ["memory.write"], "provenance": {"actor": "user", "job_id": None, "job_name": None}}
            if last.startswith('confirmremember'):
                act = {"action_id": "01JACT0000000000000000000M", "tool": "memory.propose", "tool_version": "1.0.0", "summary": "메모리 저장", "payload_view": {"op": "add", "items": [{"text": "커피는 디카페인", "kind": "preference"}], "ambiguous": False},
                       "payload_hash": "sha256:mem", "expires_at": now(3600), "tainted": False, "scopes": ["memory.write"], "provenance": {"actor": "user", "job_id": None, "job_name": None}}
            PRO['actions'][act['action_id']] = dict(act, status='pending', token=None)
            if PRO.get('sseToken'): act = dict(act, confirm_token='ssetok-must-be-ignored')   # contract forbids this; client must ignore it
            s.send_response(200); s.send_header('Content-Type', 'text/event-stream'); s.end_headers()
            try:
                s.ev({"id": "c-1", "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {"role": "assistant", "content": "일정을 추가할까요?"}, "finish_reason": None}]})
                s.ev(dict(act, object="chat.completion.confirmation"))
                s.ev({"id": "c-1", "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]})
                s.wfile.write(b'data: [DONE]\n\n')
            except (BrokenPipeError, ConnectionResetError): pass
            return
        if last.startswith('busy429'):
            return s.j(429, err('too_many_generations', 'rate_limit_error', 'too many generations'), {'Retry-After': '2'})
        if last.startswith('regen409') and rep:
            return s.j(409, err('generation_in_progress', 'invalid_request_error', 'generation in progress'))
        if last.startswith('detach') and th:   # new server (gateway 3.1.0): row first, eve.meta, id: seq, survives disconnect
            am = s.save_asst(th, rep, '', '', 'generating'); am.pop('error_code', None); mid = am['id']
            GEN[mid] = {'ev': [(1, 'eve.meta', {"thread_id": th['id'], "message_id": mid})], 'done': False}
            STATE['genStarts'] = STATE.get('genStarts', 0) + 1
            gen_run(mid, 'errra' if last.startswith('detacherrra') else 'err' if last.startswith('detacherr') else 'slow' if last.startswith('detachslow') else 'ok')
            s.send_response(200); s.send_header('Content-Type', 'text/event-stream'); s.send_header('X-Thread-Id', th['id']); s.send_header('X-Message-Id', mid)
            if um: s.send_header('X-User-Message-Id', um['id'])
            s.end_headers()
            try: s.gen_stream(mid, 0, cut=4 if last.startswith('detachcut') else None)
            except (BrokenPipeError, ConnectionResetError, OSError): pass
            return
        if last.startswith('oldcut') and th:   # old server: no eve.meta; reply saved, connection dies mid-stream
            s.send_response(200); s.send_header('Content-Type', 'text/event-stream'); s.end_headers()
            try:
                s.ev({"object": "chat.completion.chunk", "choices": [], "thread_id": th['id'], "user_message_id": um['id'] if um else None})
                s.ev({"choices": [{"delta": {"content": "old "}}]}); time.sleep(0.6)
                s.save_asst(th, rep, 'old server full reply', '')
                s.close_connection = True; s.connection.shutdown(2)
            except OSError: pass
            return
        if last.startswith('slownostream'):
            for _ in range(60):
                time.sleep(0.1)
            text = 'late non-stream'
            try: return s.j(200, {"id": "x", "object": "chat.completion", "choices": [{"message": {"role": "assistant", "content": text}}]})
            except (BrokenPipeError, ConnectionResetError): STATE['nsAborted'] = True; return
        if last.startswith('nostream'):
            text = 'non-stream reply'; hdr = {}
            out = {"id": "x", "object": "chat.completion", "choices": [{"message": {"role": "assistant", "content": text}}], "usage": {"prompt_tokens": 3, "completion_tokens": 4}}
            if th:
                am = s.save_asst(th, rep, text, '')
                out.update(thread_id=th['id'], message_id=am['id'], user_message_id=um['id'] if um else None); hdr = {'X-Thread-Id': th['id'], 'X-Message-Id': am['id']}
                if um: hdr['X-User-Message-Id'] = um['id']
                if rep: out['replaced_message_id'] = rep
            return s.j(200, out, hdr)
        s.send_response(200); s.send_header('Content-Type', 'text/event-stream')
        if th: s.send_header('X-Thread-Id', th['id']); um and s.send_header('X-User-Message-Id', um['id'])
        s.end_headers()
        acc = []; rs = []
        def ev(o):
            d = o.get('choices', [{}])[0].get('delta', {}) if o.get('choices') else {}
            if d.get('content'): acc.append(d['content'])
            if d.get('reasoning'): rs.append(d['reasoning'])
            s.ev(o)
        try:
            if th: s.ev({"id": "persist-req_mock", "object": "chat.completion.chunk", "created": int(time.time()), "model": "mlx-community/Qwen3-30B-A3B-4bit", "choices": [], "thread_id": th['id'], "user_message_id": um['id'] if um else None})
            ev({"choices": [{"delta": {"role": "assistant"}}]})
            status = 'complete'
            if last.startswith('long'):
                for k in range(12): ev({"choices": [{"delta": {"reasoning": f"think line {k}\n"}}]})
                for k in range(8): ev({"choices": [{"delta": {"content": f"Para {k} 한국어 문장입니다 `a*b*c`.\n\n"}}]})
                ev({"choices": [{"delta": {"content": "```py\nx=1\n\ny=2\n```"}}]})
            elif last.startswith('slow'):
                for k in range(3): ev({"choices": [{"delta": {"reasoning": f"생각 {k} "}}]})
                for k in range(200): ev({"choices": [{"delta": {"content": f"조각{k} "}}]})
            elif last.startswith('mdlinks'):
                ev({"choices": [{"delta": {"content": "출처: [예시](https://example.com/a) 그리고 ![고양이](https://example.com/cat.png) 끝 <img src=x onerror=alert(1)>"}}]})
            elif last.startswith('midErr'):
                ev({"choices": [{"delta": {"content": "partial"}}]})
                ev({"error": {"message": "upstream died", "type": "server_error", "code": "upstream_error"}}); status = 'incomplete'
            else:
                time.sleep(0.4)
                for r in ['Let me ', 'think.']: ev({"choices": [{"delta": {"reasoning": r}}]})
                for t in ['Hello **world**', '\n```py\nprint(1<2)\n```']: ev({"choices": [{"delta": {"content": t}}]})
                ev({"choices": [], "usage": {"prompt_tokens": 12, "completion_tokens": 34, "total_tokens": 46}})
            if th:
                am = s.save_asst(th, rep, ''.join(acc), ''.join(rs), status, 'upstream_error')
                s.ev({"object": "chat.completion.persisted", "created": int(time.time()), "status": status, "thread_id": th['id'], "message_id": am['id'], "user_message_id": um['id'] if um else None})
            s.wfile.write(b'data: [DONE]\n\n')
        except (BrokenPipeError, ConnectionResetError):
            if th: s.save_asst(th, rep, ''.join(acc), ''.join(rs), 'incomplete', 'client_disconnected')
    def gen_stream(s, mid, after, cut=None):
        g = GEN[mid]; i = after; sent = 0
        while True:
            with LOCK: evs = [e for e in g['ev'] if e[0] > i]
            for seq, event, obj in evs:
                data = obj if obj == '[DONE]' else json.dumps(obj)
                s.wfile.write(((f'id: {seq}\n') + (f'event: {event}\n' if event else '') + f'data: {data}\n\n').encode()); s.wfile.flush(); i = seq; sent += 1
                if obj == '[DONE]': return
                if cut and sent >= cut: time.sleep(0.6); s.close_connection = True; s.connection.shutdown(2); return
            s.wfile.write(b': keepalive\n\n'); s.wfile.flush(); time.sleep(0.1)
    def save_asst(s, th, rep, text, reasoning, status='complete', reason=None):
        extra = {'metadata': {'incomplete': True, 'reason': reason}} if status == 'incomplete' else {}
        with LOCK:
            if rep and rep in DB['messages']:
                m = DB['messages'][rep]; m.pop('metadata', None); m.update(content=text, reasoning=reasoning, status=status, updated_at=now(), **extra); m.pop('feedback', None); th['updated_at'] = now(); return m
            return add_msg(th['id'], 'assistant', text, reasoning=reasoning, status=status, model='mlx-community/Qwen3-30B-A3B-4bit', usage={'prompt_tokens': 12, 'completion_tokens': 34}, latency_ms=900, **extra)
    def do_PUT(s):
        if not s.gate('PUT'): return
        if s.threads_api('PUT'): return
        p = s.path
        if p.startswith('/auth/'): STATE['authed'] = p.endswith('/on')
        if p.startswith('/deny/'): STATE['denied'] = p.endswith('/on')
        if p.startswith('/auth4/'): STATE['auth4'] = p.endswith('/on')
        if p.startswith('/dupshape/'): STATE.update(dupShape=p[10:], dupGen={}, dup409n=0)
        if p.startswith('/invalidsession/'): STATE['invalidSession'] = p.endswith('/on')
        if p.startswith('/scope403/'): STATE['scope403'] = p.endswith('/on')
        if p.startswith('/paircode/'): STATE.update(pairCode=p[10:] or None, pairFails=0, pairBodies=[])
        if p.startswith('/csp/'): STATE['csp'] = p.endswith('/on')
        if p.startswith('/rejectcomment/'): STATE['rejectComment'] = p.endswith('/on')
        if p.startswith('/rejectreasons/'): STATE['rejectReasons'] = p.endswith('/on')
        if p.startswith('/persist/'): STATE['persist'] = p.endswith('/on')
        if p.startswith('/webdisabled/'): STATE['webdisabled'] = p.endswith('/on')
        if p == '/reset': STATE['authHeader'] = False; STATE['n429'] = 0  # one-shot q429 must re-arm per run
        if p == '/db/reset':
            DB.update(threads={}, messages={}, seq=0, imports={}); STATE.update(mut=[], fail={}, delay={}, calls=[], importfix=False, rejectReasons=False, rejectComment=False, fbBodies=[])
        if p.startswith('/fail/'):   # /fail/<code>?<regex>
            code, _, pat = p[6:].partition('?'); 
            if code == 'clear': STATE['fail'] = {}
            else: STATE['fail'][__import__('urllib.parse').parse.unquote(pat)] = int(code)
        if p.startswith('/delay/'):
            ms, _, pat = p[7:].partition('?')
            if ms == 'clear': STATE['delay'] = {}
            else: STATE['delay'][__import__('urllib.parse').parse.unquote(pat)] = int(ms)
        if p == '/importfix': STATE['importfix'] = True
        if p.startswith('/whoamifalse/'): STATE['whoamiFalse'] = p.endswith('/on')
        if p == '/pro/reset': pro_reset()
        if p.startswith('/pro/set'):
            b = s.body(); so = b.pop('statusOf', {}); mp = b.pop('msgPatch', {}); PRO.update(b)
            for k, v in mp.items(): DB['messages'][k].update(v)
            dr = b.pop('dropMsgs', []) if False else PRO.pop('dropMsgs', [])
            for k in dr: DB['messages'].pop(k, None)
            for k, v in so.items(): PRO['actions'][k]['status'] = v
            return s.j(200, {})
        if p.startswith('/pro/supported/'): PRO['supported'] = p.endswith('/on')
        if p == '/__mut': return s.j(200, STATE.get('mut', []))
        if p == '/mut/reset': STATE['mut'] = []
        if p == '/__pro': return s.j(200, {k: v for k, v in PRO.items()})
        if p == '/pro/seed':   # {thread, proactive:[text], actions:[{...}], scheduler_action:{...}}
            b = s.body(); out = {}
            with LOCK:
                th = new_thread(b.get('title', '대화'))
                out['thread'] = th['id']
                for t in b.get('user', []): add_msg(th['id'], 'user', t)
                out['msgs'] = [add_msg(th['id'], 'assistant', t, origin='proactive', job_id='01JJOB0000000000000000000A', provenance={'actor': 'scheduler', 'job_id': '01JJOB0000000000000000000A', 'job_name': b.get('job_name')}, kind=b.get('kind'), template_kind=b.get('template_kind'), read_at=None)['id'] for t in b.get('proactive', [])]
                for a in b.get('restore', []):
                    a = dict(a); mi = a.pop('_mi', None)   # _mi: index into the proactive messages just created → message_id
                    if mi is not None: a['message_id'] = out['msgs'][mi]
                    PRO['actions'][a['action_id']] = dict(a, status='pending', token=None, thread_id=th['id'])
                for a in b.get('actions', []):
                    a = dict(a); PRO['actions'][a['action_id']] = dict(a, status='pending', token=None)
                    m = add_msg(th['id'], 'assistant', a.pop('_text', '이 작업을 할까요?'))
                    m['pending_actions'] = [a]; out.setdefault('amsgs', []).append(m['id'])
            return s.j(200, out)
        if p == '/b1/seed':   # 1.10.0 B1 fixtures: {title, messages:[{role, content, created_at?, ...any server field (sources, memory_refs, pending_actions…)}], actions:[{...}], memory:bool}
            b = s.body(); out = {}
            with LOCK:
                th = new_thread(b.get('title', '대화')); out['thread'] = th['id']; out['msgs'] = []
                for a in b.get('actions', []): PRO['actions'][a['action_id']] = dict(a, status=a.get('status', 'pending'), token=None, thread_id=th['id'])
                for m in b.get('messages', []):
                    m = dict(m); role = m.pop('role'); c = m.pop('content', ''); out['msgs'].append(add_msg(th['id'], role, c, **m)['id'])
                if b.get('memory'): PRO['settings']['memory'] = {'enabled': True}
                th['updated_at'] = now()
            return s.j(200, out)
        if p == '/b2/seed':   # 1.10.0 B2 fixtures: {title, created?, updated?, archived?, messages:[{role, content, created_at?, origin?, provenance?, kind?, template_kind?, read_at?, …}]}
            b = s.body(); out = {}
            with LOCK:
                th = new_thread(b.get('title', '대화'), b.get('created'), archived=bool(b.get('archived'))); out['thread'] = th['id']; out['msgs'] = []
                for m in b.get('messages', []):
                    m = dict(m); role = m.pop('role'); c = m.pop('content', ''); out['msgs'].append(add_msg(th['id'], role, c, **m)['id'])
                th['updated_at'] = b.get('updated') or b.get('created') or now()
            return s.j(200, out)
        if p == '/seed':
            b = s.body(); out = []
            with LOCK:
                for i, t in enumerate(b.get('threads', [])):
                    th = new_thread(t['title'], now(-i * 3600 * t.get('hours', 1)))
                    for k, (role, c) in enumerate(t.get('messages', [])): add_msg(th['id'], role, c, created_at=now(-i * 3600 - 100 + k))
                    th['updated_at'] = now(-i * 3600 * t.get('hours', 1)); out.append(th['id'])
            return s.j(200, {'ids': out})
        s.j(200, {k: v for k, v in STATE.items() if k != 'calls'})
def mark(text, term):
    i = text.lower().find(term.lower()); a = max(0, i - 20)
    seg = text[a:i + len(term) + 40]; j = i - a
    return html.escape(seg[:j]) + '<mark>' + html.escape(seg[j:j + len(term)]) + '</mark>' + html.escape(seg[j + len(term):])
ThreadingHTTPServer(('127.0.0.1', int(PORT)), H).serve_forever()
