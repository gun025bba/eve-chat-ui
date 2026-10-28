# 1.10.0 B3 shared helpers (DIRECTION-B-SPEC d196833 §5–§7 §8.1): status strip fixtures — memory, pending actions, today's briefing message
from b2_common import *
from datetime import datetime, timedelta, timezone
def isoz(mins=0, secs=0): return (datetime.now(timezone.utc) + timedelta(minutes=mins, seconds=secs)).strftime('%Y-%m-%dT%H:%M:%SZ')
def act(n, title=None, verb='add', exp=60 * 24, created=None, tool='calendar_add_event', display=None, scopes=None, **kw):
    pv = {'verb': verb}
    if title: pv['title'] = title
    if display: pv['display'] = display
    return dict(ACT, action_id='01JPEND%019d' % n, tool=tool, summary=kw.pop('summary', '일정 추가'), scopes=scopes or ['calendar.write'], payload_view=pv, expires_at=isoz(exp),
                created_at=created or isoz(-60 + n), **kw)
def seed_act(*acts, title='치과 예약', **kw):
    return put('/pro/seed', dict(title=title, user=['내일 치과 일정 추가해 줘'], proactive=['치과 예약 일정을 추가할까요?'], job_name='아침 브리핑', restore=list(acts), **kw))
def mem_items(n):
    return [{'id': '01JMEMB3%018d' % i, 'kind': 'fact', 'text': f'기억 {i + 1}번 항목', 'pinned': False, 'confidence': 'user', 'updated_at': isoz(-i - 1), 'expires_at': None} for i in range(n)]
def memory(n=3, enabled=True, mode=None, nokey=False):
    """server memory state: n items; enabled = memory.enabled; mode = memMode (off | availOff | e500 | drop | kill …); nokey = settings without the memory key"""
    put('/pro/set', {'settings': {'proactive': {'enabled': False, 'quiet_hours': {'start': '22:00', 'end': '08:00'}, 'memory_read': False}, 'memory': {'enabled': enabled}},
                     'memItems': mem_items(n), 'memMode': mode, 'memNoKey': nokey})
def ev(title, h, m, mins=60, cal='개인', all_day=False, day=0):
    s = datetime.now(KST).replace(hour=h, minute=m, second=0, microsecond=0) + timedelta(days=day)
    return {'title': title, 'start': s.isoformat(), 'end': (s + timedelta(minutes=mins)).isoformat(), 'all_day': all_day, 'calendar': cal}
def brief_thread(items, count=None, truncated=False, status='ok', date=None, h=7, m=42, sections=None, extra=None):
    """today's 아침 브리핑 thread: a proactive message with template_kind 'briefing' and a saved `briefing` (#66 §11.3)"""
    sec = [{'kind': 'events', 'status': status, 'count': len(items) if count is None else count, 'truncated': truncated, 'items': items}] if sections is None else sections
    b = {'schema': 1, 'status': 'ok', 'date': date or day_ymd(), 'text_source': 'template', 'sections': sec}
    if extra: b.update(extra)
    return pro_thread('아침 브리핑', [dict(pro_msg('좋은 아침이에요. 오늘 일정을 정리했어요.', h, m, tkind='briefing'), briefing=b)], h, m)
def strip(pg): return pg.evaluate("""() => { const w = document.getElementById('todayStrip'); return { hidden: w.hidden, n: getComputedStyle(w.firstElementChild).getPropertyValue('--n').trim(),
   cells: [...w.querySelectorAll('.stc')].map(c => ({ k: c.dataset.k, n: c.querySelector('.sn').textContent, label: c.querySelector('.sl span').textContent, aria: c.getAttribute('aria-label'), dis: c.getAttribute('aria-disabled') === 'true' })) } }""")
def keys(pg): return [c['k'] for c in strip(pg)['cells']]
def newpg(b, errs, scheme='dark', **kw):
    ctx = new_ctx(b, scheme=scheme, **kw); pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e))); return ctx, pg
def refresh(pg):   # what coming back to the app does
    pg.evaluate("document.dispatchEvent(new Event('visibilitychange'))"); pg.wait_for_timeout(600)
