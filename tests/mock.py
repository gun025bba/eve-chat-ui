"""Mock gateway: OpenAI-compatible chat + threads/messages/feedback/search/import (backend contract v10)."""
import json, time, os, re, html, threading
from datetime import datetime, timezone, timedelta
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
UI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = {'n429': 0, 'authed': True, 'authHeader': False, 'persist': True, 'fail': {}, 'calls': []}
DB = {'threads': {}, 'messages': {}, 'seq': 0, 'imports': {}}
LOCK = threading.RLock()
def now(off=0): return (datetime.now(timezone.utc) + timedelta(seconds=off)).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
def nid(p):
    DB['seq'] += 1; return f'01JMOCK{p.upper()[:1]}{DB["seq"]:018d}'   # 26-char ULID-like
def preview(tid):
    ms = [m for m in DB['messages'].values() if m['thread_id'] == tid]
    return ms[-1]['content'][:80] if ms else ''
def tview(t):
    ms = [m for m in DB['messages'].values() if m['thread_id'] == t['id']]
    return dict(t, message_count=len(ms), last_message_preview=preview(t['id']))
def new_thread(title, created=None, archived=False, client_id=None):
    t = {'id': nid('th'), 'title': title, 'created_at': created or now(), 'updated_at': created or now(), 'archived': archived}
    if client_id: t['client_id'] = client_id
    DB['threads'][t['id']] = t; return t
def add_msg(tid, role, content, **kw):
    m = {'id': nid('m'), 'thread_id': tid, 'role': role, 'content': content, 'created_at': kw.pop('created_at', None) or now(), 'status': 'complete'}
    m.update(kw); DB['messages'][m['id']] = m; DB['threads'][tid]['updated_at'] = now(); return m
def err(code, typ='invalid_request_error', msg=None): return {"error": {"code": code, "message": msg or code, "type": typ, "request_id": "req_mock"}}
class H(SimpleHTTPRequestHandler):
    protocol_version = 'HTTP/1.0'
    def __init__(s, *a, **k): super().__init__(*a, directory=UI, **k)
    def log_message(s, *a): pass
    def j(s, code, obj, hdr=None):
        b = json.dumps(obj).encode() if obj is not None else b''
        s.send_response(code); s.send_header('Content-Type', 'application/json')
        for k, v in (hdr or {}).items(): s.send_header(k, v)
        s.end_headers(); s.wfile.write(b)
    def auth(s):
        if s.headers.get('Authorization'): STATE['authHeader'] = True
        if STATE.get('denied'): s.j(401, err('identity_not_allowed', 'authentication_error', 'not allowed')); return False
        if not STATE['authed']: s.j(401, err('unauthenticated', 'authentication_error', 'Tailscale identity required')); return False
        return True
    def body(s):
        n = int(s.headers.get('Content-Length') or 0); return json.loads(s.rfile.read(n)) if n else {}
    def threads_api(s, method):
        u = urlparse(s.path); q = {k: v[0] for k, v in parse_qs(u.query).items()}; path = u.path
        if not path.startswith('/v1/threads') and not path.startswith('/v1/messages') and not path.startswith('/v1/search'): return False
        if not s.auth(): return True
        STATE['calls'].append(f'{method} {s.path}')
        if not STATE['persist']: s.j(503, err('persistence_disabled', 'server_error', 'conversation storage is disabled')); return True
        for pat, code in STATE['fail'].items():
            if re.search(pat, f'{method} {path}'): s.j(code, err('mock_failure', 'server_error')); return True
        with LOCK:
            if path == '/v1/threads' and method == 'GET':
                arch = q.get('archived', 'false') == 'true'; lim = int(q.get('limit', 20)); off = int(q.get('cursor') or 0)
                ts = sorted([t for t in DB['threads'].values() if t['archived'] == arch], key=lambda t: t['updated_at'], reverse=True)
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
                    old = msg.get('feedback') or {}; msg['feedback'] = {'message_id': msg['id'], 'rating': b['rating'], 'comment': b.get('comment'), 'created_at': old.get('created_at') or now(), 'updated_at': now()}; return s.j(200, msg['feedback']) or True
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
            if s.auth(): s.j(200, {"authenticated": True, "user": "user@example.com", "provider": "tailscale-identity"})
            return
        if s.path == '/__db': return s.j(200, {'threads': list(DB['threads'].values()), 'messages': list(DB['messages'].values()), 'state': {k: v for k, v in STATE.items()}})
        if s.path == '/v1/models':
            if s.auth(): s.j(200, {"data": [{"id": "mlx-community/Qwen3-30B-A3B-4bit"}]})
            return
        if s.threads_api('GET'): return
        if s.path.startswith('/ui'): s.path = s.path[3:] or '/'
        else: s.send_response(404); s.end_headers(); return
        super().do_GET()
    def do_PATCH(s): s.threads_api('PATCH') or s.j(404, err('not_found'))
    def do_DELETE(s): s.threads_api('DELETE') or s.j(404, err('not_found'))
    def ev(s, o): s.wfile.write(f'data: {json.dumps(o)}\n\n'.encode()); s.wfile.flush(); time.sleep(0.08)
    def do_POST(s):
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
        with LOCK:
            if tid:
                th = new_thread(last[:40]) if tid == 'new' else DB['threads'].get(tid)
                if th and not rep: um = add_msg(th['id'], 'user', last)
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
    def save_asst(s, th, rep, text, reasoning, status='complete', reason=None):
        extra = {'metadata': {'incomplete': True, 'reason': reason}} if status == 'incomplete' else {}
        with LOCK:
            if rep and rep in DB['messages']:
                m = DB['messages'][rep]; m.pop('metadata', None); m.update(content=text, reasoning=reasoning, status=status, updated_at=now(), **extra); m.pop('feedback', None); th['updated_at'] = now(); return m
            return add_msg(th['id'], 'assistant', text, reasoning=reasoning, status=status, model='mlx-community/Qwen3-30B-A3B-4bit', usage={'prompt_tokens': 12, 'completion_tokens': 34}, latency_ms=900, **extra)
    def do_PUT(s):
        if s.threads_api('PUT'): return
        p = s.path
        if p.startswith('/auth/'): STATE['authed'] = p.endswith('/on')
        if p.startswith('/deny/'): STATE['denied'] = p.endswith('/on')
        if p.startswith('/persist/'): STATE['persist'] = p.endswith('/on')
        if p == '/reset': STATE['authHeader'] = False
        if p == '/db/reset':
            DB.update(threads={}, messages={}, seq=0, imports={}); STATE.update(fail={}, calls=[], importfix=False)
        if p.startswith('/fail/'):   # /fail/<code>?<regex>
            code, _, pat = p[6:].partition('?'); 
            if code == 'clear': STATE['fail'] = {}
            else: STATE['fail'][__import__('urllib.parse').parse.unquote(pat)] = int(code)
        if p == '/importfix': STATE['importfix'] = True
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
ThreadingHTTPServer(('127.0.0.1', 8765), H).serve_forever()
