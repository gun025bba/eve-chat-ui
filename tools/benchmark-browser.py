"""python tools/benchmark-browser.py /tmp/eve-bench (Playwright Chromium + WebKit)."""
import functools, json, statistics, sys, threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path(sys.argv[1]) / 'dist'
class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; font-src 'self'; object-src 'none'")
        super().end_headers()
    def log_message(self, *args): pass

server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(root)))
threading.Thread(target=server.serve_forever, daemon=True).start()
replay = json.loads((root / 'replay.json').read_text())
results = json.loads((root / 'sizes.json').read_text())
with sync_playwright() as p:
    for engine in [p.chromium, p.webkit]:
        browser = engine.launch()
        for name in results:
            page = browser.new_page()
            page.add_init_script("window.violations=[];document.addEventListener('securitypolicyviolation',e=>violations.push(e.violatedDirective));")
            page.goto(f'http://127.0.0.1:{server.server_port}/{name}/')
            timings = []
            for _ in range(8):
                timings.append(page.evaluate("""chunks => {
                  const start=performance.now();
                  for(let round=0;round<20;round++) for(const chunk of chunks) {
                    window.apply(chunk.text);
                    if(document.getElementById('root').textContent!==chunk.text) throw Error('Uncommitted update');
                  }
                  return (performance.now()-start)/20;
                }""", replay))
            attack = '<img src=x onerror=alert(1)><script>alert(1)</script>'
            page.evaluate('text => window.apply(text)', attack)
            assert page.locator('#root').inner_text() == attack
            assert page.locator('#root img, #root script, style, [style]').count() == 0
            assert page.evaluate('violations') == []
            results[name][engine.name] = {'medianReplayMs': round(statistics.median(timings[1:]), 3),
                                        'updates': len(replay), 'browser': browser.version, 'cspViolations': 0}
            page.close()
        browser.close()
server.shutdown()
results['sharedHelperMs'] = round(sum(chunk['helperMs'] for chunk in replay), 3)
(root / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
print(json.dumps(results, indent=2))
