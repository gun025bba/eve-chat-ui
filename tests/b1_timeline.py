# 1.10.0 B1 하루 (DIRECTION-B-SPEC d196833): the conversation is a timeline, not bubbles. Structure, KST time, who, dots, day-sep, rail geometry, action row, proactive who, memory chips, confirm card, no forbidden elements.
import re
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright
from b1_common import *
R = []; errs = []
def check(n, ok, x=''): R.append(bool(ok)); print('PASS' if ok else 'FAIL', n, '' if ok else x)
reset()
Y = datetime.now(KST) - timedelta(days=1); WD = '월화수목금토일'
today = datetime.now(KST); WDT = '월화수목금토일'[today.weekday()]; WDY = '월화수목금토일'[Y.weekday()]
t = seed('하루 타임라인', [
  {'role': 'user', 'content': '내일 치과 몇 시였지?', 'created_at': at(7, 41, -1)},
  {'role': 'assistant', 'content': '내일 오후 3시예요.', 'created_at': at(7, 42, -1), 'sources': S2, 'memory_refs': MEM3},
  {'role': 'user', 'content': '고마워', 'created_at': at(8, 5)},
  {'role': 'assistant', 'content': '별말씀을요. 일정 하나 더 추가할까요?', 'created_at': at(8, 6), 'pending_actions': [ACT]},
  {'role': 'assistant', 'content': '비가 와요. 우산 챙기세요.', 'created_at': at(9, 0), 'origin': 'proactive', 'job_id': '01JJOB0000000000000000000A', 'template_kind': 'briefing', 'provenance': {'actor': 'scheduler', 'job_id': '01JJOB0000000000000000000A', 'job_name': '아침 브리핑'}},
  {'role': 'assistant', 'content': '조용한 시간 동안의 요약이에요.', 'created_at': at(9, 30), 'origin': 'proactive', 'kind': 'digest', 'read_at': at(9, 31)},
], actions=[ACT], memory=True)
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = new_ctx(b); pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
    open_thread(pg, '하루 타임라인'); pg.wait_for_timeout(800)
    ev = lambda js: pg.evaluate(js)
    check('list role + aria-label = the thread title (follow-up d)', ev("(()=>{const m=document.getElementById('messages'),t=document.getElementById('title').textContent.trim();return m.getAttribute('role')==='list'&&!!t&&m.getAttribute('aria-label')===t})()"))
    msgs = ev("[...document.querySelectorAll('#messages > .msg')].map(m=>({c:m.className,r:m.getAttribute('role'),a:m.getAttribute('aria-label'),tm:m.querySelector(':scope>.tm')?.textContent,who:m.querySelector(':scope>.who .who-n')?.textContent,dot:m.querySelector(':scope>.dot')?.getAttribute('aria-hidden')}))")
    check('6 events, all listitems with a dot aria-hidden', len(msgs) == 6 and all(m['r'] == 'listitem' and m['dot'] == 'true' for m in msgs), msgs)
    check('time column = KST HH:mm (24h)', [m['tm'] for m in msgs][:5] == ['07:41', '07:42', '08:05', '08:06', '09:00'], [m['tm'] for m in msgs])
    check('who: user → 나 (no hard-coded name), Eve → Eve', msgs[0]['who'] == '나' and msgs[1]['who'] == 'Eve' and msgs[2]['who'] == '나', [m['who'] for m in msgs])
    check('aria-label = "HH:mm who"', msgs[0]['a'] == '07:41 나' and msgs[1]['a'] == '07:42 Eve', [m['a'] for m in msgs])
    seps = ev("[...document.querySelectorAll('#messages > .day-sep')].map(s=>({t:s.textContent,dot:!!s.querySelector('.dot'),ml:getComputedStyle(s).fontWeight}))")
    check('day-sep: 어제 · 요일 above the first day, 오늘 · 요일 at the day change; dotless', [s['t'] for s in seps] == [f'어제 · {WDY}', f'오늘 · {WDT}'] and not any(s['dot'] for s in seps), seps)
    check('day-sep order: 어제 → 첫 메시지 … 오늘 → 08:05', ev("(()=>{const k=[...document.querySelectorAll('#messages > .day-sep, #messages > .msg')].map(x=>x.classList.contains('day-sep')?'S':'m').join('');return k.startsWith('Sm')&&k.includes('mSm')})()"))
    # no bubbles, no forbidden elements
    chk = ev("""(()=>{const u=document.querySelector('.msg.user .bubble'),e=document.querySelector('.msg.assistant .bubble'),us=getComputedStyle(u),es=getComputedStyle(e);
      return {ubg:us.backgroundColor,upad:us.paddingLeft,urad:us.borderTopLeftRadius,uw:us.fontWeight,efs:es.fontSize,elh:es.lineHeight,ufs:us.fontSize,ulh:us.lineHeight,
        forbid:document.querySelectorAll('.empty,.empty .mark,.chips .chip,.chip,.mark-tile').length,text:/무엇을 도와드릴까요|도와드릴/.test(document.body.innerText)}})()""")
    check('user text is plain: no background / padding / radius, weight 500, 16/24', chk['ubg'] in ('rgba(0, 0, 0, 0)', 'transparent') and chk['upad'] == '0px' and chk['urad'] == '0px' and chk['uw'] == '500' and chk['ufs'] == '16px' and chk['ulh'] == '24px', chk)
    check('Eve body 16/24', chk['efs'] == '16px' and chk['elh'] == '24px', chk)
    check('forbidden elements absent (centered logo, 무엇을 도와드릴까요?, suggestion cards)', chk['forbid'] == 0 and not chk['text'], chk)
    # geometry at 390: margin 16, dot left 47 / top 6 / 9px, body at +70, 288 wide
    g = ev("""(()=>{const m=document.querySelectorAll('#messages > .msg')[2],r=m.getBoundingClientRect(),d=m.querySelector('.dot').getBoundingClientRect(),b=m.querySelector('.bubble').getBoundingClientRect(),t=m.querySelector('.tm').getBoundingClientRect();
      return {dl:d.left-r.left,dt:d.top-r.top,dw:d.width,bl:b.left-r.left,bw:b.width,tw:t.width,tl:t.left-r.left,ml:r.left}})()""")
    check('geometry: dot left 47 / top 6 / 9px; body at +70 (288 wide @390); time col 44', abs(g['dl'] - 47) < 1 and abs(g['dt'] - 6) < 1 and g['dw'] == 9 and abs(g['bl'] - 70) < 1 and abs(g['bw'] - 288) < 1 and g['tw'] == 44 and g['tl'] == 0 and g['ml'] == 16, g)
    dots = ev("""(()=>{const c=s=>getComputedStyle(document.querySelector(s)+''?document.querySelector(s):document.body);const q=s=>getComputedStyle(document.querySelector(s));
      return {me:q('.msg.user .dot').backgroundColor,e:q('.msg.assistant .dot').backgroundColor,brand:getComputedStyle(document.documentElement).getPropertyValue('--brand').trim(),eglow:q('.msg.assistant .dot').boxShadow}})()""")
    check('dots: user = filled --label, Eve = --brand with halo + glow (dark)', dots['me'] == 'rgb(245, 245, 247)' and dots['brand'] == '#00D2BE' and dots['e'] == 'rgb(0, 210, 190)' and '12px' in dots['eglow'], dots)
    # who colours
    wc = ev("[...document.querySelectorAll('#messages > .msg')].slice(0,2).map(m=>getComputedStyle(m.querySelector('.who')).color)")
    check('who colours: Eve = --brand, user = --sub (.62)', wc[1] == 'rgb(0, 210, 190)' and wc[0].startswith('rgba(235, 235, 245, 0.62') , wc)
    # action row
    a = ev("""(()=>{const m=document.querySelectorAll('#messages > .msg.assistant')[0],r=m.querySelector('.actions');const bs=[...r.querySelectorAll('button')].filter(x=>x.offsetParent&&x.getBoundingClientRect().width).map(x=>x.getBoundingClientRect());const sv=r.querySelector('svg').getBoundingClientRect();
      return {h:r.getBoundingClientRect().height,n:bs.length,w:bs.map(x=>x.width),hh:bs.map(x=>x.height),sv:sv.width,order:[...r.querySelectorAll('button')].map(x=>x.getAttribute('aria-label')||x.className)}})()""")
    check('action row: 44px tall, 36x36 buttons, 18px icons', abs(a['h'] - 44) < 1 and all(w == 36 for w in a['w']) and all(h == 36 for h in a['hh']) and a['sv'] == 18 and a['n'] >= 3, a)
    order = ev("""(()=>{const m=document.querySelectorAll('#messages > .msg.assistant')[0],c=[...m.querySelector('.bubble').children].map(x=>x.className.split(' ')[0]).concat([...m.children].map(x=>x.className.split(' ')[0]));return c})()""")
    check('order: body → source chips → memory chips → action row', ev("""(()=>{const m=document.querySelectorAll('#messages > .msg.assistant')[0],q=s=>m.querySelector(s).getBoundingClientRect().top;return q('.md')<q('.sources')&&q('.sources')<q('.mchips')&&q('.mchips')<q('.actions')})()"""), order)
    # memory chips
    mc = ev("[...document.querySelectorAll('.msg.assistant .mchips .chp')].map(c=>({t:c.textContent,w:c.getBoundingClientRect().width,h:c.getBoundingClientRect().height,col:getComputedStyle(c).color}))")
    more = ev("document.querySelector('.mchips .chp-more')?.textContent")
    check('memory chip: max 2 + "+1"; label first 14 chars + …; ≤160px, 26px; --brand', len(mc) == 2 and more == '+1' and mc[0]['t'] == '아침 브리핑은 한국어로 짧…' and mc[1]['t'] == '다음 주 발표 준비 중' and all(c['w'] <= 160.5 and c['h'] == 26 and c['col'] == 'rgb(0, 210, 190)' for c in mc), [mc, more])
    # proactive who + icon
    pw = ev("[...document.querySelectorAll('#messages > .msg.proactive')].map(m=>({who:m.querySelector('.who-n').textContent,ic:!!m.querySelector('.who .who-ic'),a:m.getAttribute('aria-label'),origin:!!m.querySelector('.origin-line'),tm:m.querySelector('.tm').textContent}))")
    check('proactive: who = "Eve · {job_name}" + template icon, "조용한 시간 동안 요약" for digest', len(pw) == 2 and pw[0]['who'] == 'Eve · 아침 브리핑' and pw[0]['ic'] and pw[1]['who'] == 'Eve · 조용한 시간 동안 요약', pw)
    check('proactive: no origin-line, time = created KST, aria-label "HH:mm who" (+"읽지 않음, " prefix while unread)', not any(x['origin'] for x in pw) and pw[0]['tm'] == '09:00' and pw[0]['a'].endswith('09:00 Eve · 아침 브리핑') and pw[1]['a'] == '09:30 Eve · 조용한 시간 동안 요약', pw)
    # confirm card: in the timeline, 44pt targets via ::before, no behaviour change
    cc = ev("""(()=>{const c=document.querySelector('.confirm-card'),bs=[...c.querySelectorAll('.cc-actions button')],cs=getComputedStyle(c);const h=bs.map(x=>({h:x.getBoundingClientRect().height,tap:parseFloat(getComputedStyle(x,'::before').top)}));
      return {rad:cs.borderTopLeftRadius,left:c.getBoundingClientRect().left,n:bs.length,h}})()""")
    check('confirm card: radius 16, aligned to the body column (x=86), 32px buttons with a 6px-inset tap area (44pt)', cc['rad'] == '16px' and abs(cc['left'] - 86) < 1 and cc['n'] == 2 and all(abs(x['h'] - 32) < 1 and x['tap'] == -6 for x in cc['h']), cc)
    # tap on confirm still works (no behaviour change)
    pg.locator('.confirm-card .cc-primary').click(); pg.wait_for_timeout(900)
    check('confirm → confirmed state (behaviour unchanged)', pg.locator('.confirm-card').get_attribute('data-state') == 'confirmed', pg.locator('.confirm-card').get_attribute('data-state'))
    # rail: continuous background line at 51px through day-sep
    rl = ev("""(()=>{const r=s=>getComputedStyle(s).backgroundImage.includes('linear-gradient')&&getComputedStyle(s).backgroundPosition.startsWith('51px');return [...document.querySelectorAll('#messages > .msg, #messages > .day-sep, #messages > .cc-stack')].every(r)})()""")
    check('rail (1px at x=51) is drawn by events, day-seps and cards alike', rl)
    # motion: nothing transitions "all", no animation on thread open
    check('no entrance animation on thread open / re-render', ev("document.querySelectorAll('#messages .msg.enter').length") <= 1 and ev("[...document.querySelectorAll('#messages .msg')].every(m=>getComputedStyle(m).animationName==='none'||!m.classList.contains('enter'))"))
    check('no console errors', not errs, errs)
    # reduced motion: entrance is opacity only
    ctx2 = new_ctx(b, reduced_motion='reduce'); pg2 = ctx2.new_page(); open_thread(pg2, '하루 타임라인')
    pg2.fill('#input', 'x'); pg2.click('#sendBtn'); pg2.wait_for_timeout(120)
    rm = pg2.evaluate("(()=>{const m=document.querySelector('#messages > .msg.user.enter');if(!m)return 'none';return getComputedStyle(m).animationName})()")
    check('reduced motion: entrance animation is opacity-only (fadeIn)', rm in ('fadeIn', 'none'), rm)
    b.close()
print(f'{sum(R)}/{len(R)} checks'); raise SystemExit(0 if all(R) else 1)
