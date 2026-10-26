import json,time
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import os
UI=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE={'n429':0}
class H(SimpleHTTPRequestHandler):
    def __init__(s,*a,**k): super().__init__(*a,directory=UI,**k)
    def log_message(s,*a): pass
    def j(s,code,obj):
        b=json.dumps(obj).encode(); s.send_response(code);s.send_header('Content-Type','application/json');s.end_headers();s.wfile.write(b)
    def auth(s):
        if s.headers.get('Authorization')!='Bearer testkey':
            s.j(401,{"error":{"message":"Invalid API key","type":"authentication_error","code":"invalid_api_key"}});return False
        return True
    def do_GET(s):
        if s.path=='/v1/models':
            if s.auth(): s.j(200,{"data":[{"id":"mlx-community/Qwen3-30B-A3B-4bit"}]})
            return
        if s.path.startswith('/ui'): s.path=s.path[3:] or '/'
        else: s.send_response(404); s.end_headers(); return
        super().do_GET()
    def ev(s,o): s.wfile.write(f'data: {json.dumps(o)}\n\n'.encode()); s.wfile.flush(); time.sleep(0.08)
    def do_POST(s):
        body=json.loads(s.rfile.read(int(s.headers['Content-Length'])))
        if not s.auth():return
        last=body['messages'][-1]['content']; STATE['last']=last; STATE['so']=body.get('stream_options')
        if last.startswith('q429') and STATE['n429']==0:
            STATE['n429']=1; return s.j(429,{"error":{"message":"queue full","type":"rate_limit_error","code":"queue_full"}})
        s.send_response(200);s.send_header('Content-Type','text/event-stream');s.end_headers()
        if last.startswith('long'):
            for k in range(12): s.ev({"choices":[{"delta":{"reasoning":f"think line {k}\n"}}]})
            for k in range(8): s.ev({"choices":[{"delta":{"content":f"Para {k} 한국어 문장입니다 `a*b*c`.\n\n"}}]})
            s.ev({"choices":[{"delta":{"content":"```py\nx=1\n\ny=2\n```"}}]})
        elif last.startswith('midErr'):
            s.ev({"choices":[{"delta":{"content":"partial"}}]})
            s.ev({"error":{"message":"upstream died","type":"server_error","code":"upstream_error"}})
        else:
            time.sleep(0.4)
            for r in ['Let me ','think.']: s.ev({"choices":[{"delta":{"reasoning":r}}]})
            for t in ['Hello **world**','\n```py\nprint(1<2)\n```']: s.ev({"choices":[{"delta":{"content":t}}]})
            s.ev({"choices":[],"usage":{"prompt_tokens":12,"completion_tokens":34,"total_tokens":46}})
        s.wfile.write(b'data: [DONE]\n\n')
    def do_PUT(s): s.j(200,STATE)
ThreadingHTTPServer(('127.0.0.1',8765),H).serve_forever()
