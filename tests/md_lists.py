"""v16: ordered lists keep numbering (tight, loose, start, interrupted, nested) and streaming == final render."""
import json, os, subprocess, sys
APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app.js')
JS = r'''
const {renderMarkdown:r, stableCut:c} = require(process.argv[1]);
const cases = JSON.parse(process.argv[2]);
const out = {};
for (const [k, src] of Object.entries(cases)) {
  // simulate patchLive: freeze stable blocks, re-render tail per token
  let stable = '', prev = 0, frozenOk = true;
  for (let n = 1; n <= src.length; n++) {
    const a = src.slice(0, n), cut = c(a);
    if (cut > prev) stable += r(a.slice(prev, cut)); else if (cut < prev) { stable = r(a.slice(0, cut)); frozenOk = false; }
    prev = cut;
  }
  out[k] = { full: r(src), streamed: stable + r(src.slice(prev)), frozenOk };
}
console.log(JSON.stringify(out));
'''
CASES = {
 'tight': '1. a\n2. b\n3. c',
 'loose': '답변:\n\n1. **첫째** 설명 [1]\n\n2. 둘째\n\n3. 셋째\n\n끝.',
 'start': '3. x\n4. y',
 'interrupted': '1. a\n\n중간 문단\n\n2. b\n3. c',
 'nested': '1. a\n   - n1\n   - n2\n2. b\n   - n3',
 'continuation': '1. a\n\n   이어지는 문단\n\n2. b',
 'code_between': '1. a\n\n```\ncode\n```\n\n2. b',
}
fails = 0
def check(name, ok, info=''):
    global fails
    print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else '  ' + str(info))); fails += (not ok)
res = json.loads(subprocess.check_output(['node', '-e', JS, APP, json.dumps(CASES)]).decode())
f = {k: v['full'] for k, v in res.items()}
check('tight: one <ol>, 3 items', f['tight'].count('<ol') == 1 and f['tight'].count('<li>') == 3, f['tight'])
check('loose: one <ol>, 3 items', f['loose'].count('<ol') == 1 and f['loose'].count('<li>') == 3, f['loose'])
check('loose: no start attr', '<ol>' in f['loose'], f['loose'])
check('start=3 preserved', '<ol start="3">' in f['start'], f['start'])
check('interrupted resumes start=2', '<ol start="2"><li>b</li><li>c</li></ol>' in f['interrupted'], f['interrupted'])
check('nested bullets inside one ol', f['nested'].count('<ol') == 1 and f['nested'].count('<ul>') == 2 and '<li>b<ul>' in f['nested'], f['nested'])
check('indented continuation stays in item', f['continuation'].count('<ol') == 1 and '<p>이어지는 문단</p></li>' in f['continuation'], f['continuation'])
check('code between items resumes start=2', '<ol start="2">' in f['code_between'], f['code_between'])
for k, v in res.items():
    check(f'streamed == final ({k})', v['streamed'] == v['full'], v)
    check(f'frozen blocks never retracted ({k})', v['frozenOk'])
print(f'\n{len(CASES)*2+8-fails}/{len(CASES)*2+8} passed'); sys.exit(1 if fails else 0)
