# 1.10.0 B2 shared helpers (DIRECTION-B-SPEC d196833): richer fixtures than b1_common — thread created/updated, archived, proactive messages
from b1_common import *
from datetime import datetime, timedelta
JOB = '01JJOB0000000000000000000A'
WD = '월화수목금토일'
def kst_now(): return datetime.now(KST)
def day_ymd(day=0): return (kst_now() + timedelta(days=day)).strftime('%Y-%m-%d')
def wd_of(day=0): return WD[(kst_now() + timedelta(days=day)).weekday()]
def label_of(day=0):
    d = kst_now() + timedelta(days=day)
    if day == 0: return f'오늘 · {wd_of(0)}'
    if day == -1: return f'어제 · {wd_of(-1)}'
    return f'{d.month}월 {d.day}일 · {wd_of(day)}'
def pro_msg(text, h, m, job='아침 브리핑', tkind=None, kind=None, read=False, day=0):
    t = at(h, m, day)
    return dict(role='assistant', content=text, created_at=t, origin='proactive', provenance={'actor': 'scheduler', 'job_id': JOB, 'job_name': job}, template_kind=tkind, kind=kind, read_at=(t if read else None))
def conv2(title, h, m, day=0, q=None, a=None, archived=False):
    """a thread whose first user message is at h:m of today+day and whose last activity is 1 minute later"""
    ms = [dict(role='user', content=q or title, created_at=at(h, m, day)), dict(role='assistant', content=a or f'{title} 에 대한 답이에요.', created_at=at(h, m + 1 if m < 59 else m, day))]
    return put('/b2/seed', dict(title=title, created=at(h, m, day), updated=at(h, m + 1 if m < 59 else m, day), archived=archived, messages=ms))['thread']
def pro_thread(title, msgs, h, m, day=0): return put('/b2/seed', dict(title=title, created=at(h, m, day), updated=at(h, m, day), messages=msgs))['thread']
def rich():
    """a full day: 3 선톡 (briefing unread, watch read, quiet-hours digest) + 7 conversations (→ latest 5 + "기록에서 더 보기") + 어제 + older days + 1 archived"""
    ids = {}
    ids['digest'] = pro_thread('조용한 시간 요약', [pro_msg('밤사이 알림 3건을 모았어요.', 6, 0, job=None, kind='digest', read=True)], 6, 0)
    ids['brief'] = pro_thread('아침 브리핑', [pro_msg('좋은 아침이에요. 오늘 일정과 날씨를 정리했어요.', 7, 30, tkind='briefing')], 7, 30)
    ids['watch'] = pro_thread('가격 알림', [pro_msg('찾던 키보드가 12% 내렸어요.', 10, 0, job='가격 알림', tkind='watch', read=True)], 10, 0)
    for t, h, m in [('점심 메뉴 추천', 8, 12), ('여행 일정 정리', 9, 5), ('SwiftUI 질문', 9, 40), ('회의록 요약', 10, 15), ('파이썬 코드 리뷰', 10, 50), ('운동 루틴 짜기', 11, 20), ('번역 부탁', 11, 45)]: ids[t] = conv2(t, h, m)
    return ids
def older():
    """yesterday (→ 이어서), 2 and 3 days ago, an old one, one archived"""
    ids = {}
    ids['cont'] = conv2('발표 자료 준비', 22, 10, day=-1, q='발표 자료 목차 잡아줘', a='1) 문제 2) 접근 3) 결과 순서로 가요.')
    ids['d2'] = conv2('주말 캠핑 장비', 15, 30, day=-2); ids['d3'] = conv2('영어 이메일 초안', 9, 15, day=-3); ids['old'] = conv2('지난달 영수증 정리', 14, 0, day=-8)
    ids['arch'] = conv2('보관한 대화', 12, 0, day=-5, archived=True)
    return ids
def goto_today(pg, hash_='#/', wait=1500, reload=True):
    pg.goto(B + '/ui/' + hash_)
    if reload and not hash_.startswith(('#/t/', '#/c/')): pg.reload()   # boot rewrites the hash to #/ and a deep link is opened after the list loads, so a reload right after goto would lose it
    pg.wait_for_timeout(wait)
def rt(pg): return pg.evaluate("document.getElementById('app').dataset.route")
