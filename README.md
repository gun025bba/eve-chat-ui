# Eve — 채팅 UI

OpenAI 호환 백엔드용 모바일 우선 채팅 PWA예요. 순수 HTML/JS로 만들었고 빌드 단계와 의존성이 없어요.

## 실행
빌드 없이 저장소 파일을 그대로 정적 서빙하면 돼요. 서비스 워커는 HTTPS(또는 localhost)에서만 동작해요.

```bash
python3 -m http.server 8080   # 로컬 확인용 예시
```

운영에서는 백엔드 게이트웨이가 이 파일들을 `/ui/` 경로로 서빙해요(같은 출처라 CORS가 필요 없어요). `.git`과 `tests/`는 배포하지 않아요.

## 백엔드 연결
- 기본값은 **같은 출처**예요. UI는 상대 경로 `/v1/...`(`/v1/models`, `/v1/chat/completions`, `/v1/threads` 등)와 `/whoami`를 호출해요.
- 설정의 Base URL(`localStorage` `llmchat.settings`의 `base`)로 다른 주소를 지정할 수 있어요. 끝의 `/`와 `/v1`은 자동으로 잘라요. 예: `https://<gateway-host>`
- 브라우저는 API 키를 보내지 않아요. 인증은 게이트웨이 앞단의 신원 헤더로 처리해요.
- 스트리밍은 SSE(`text/event-stream`)를 써요. 리버스 프록시를 쓴다면 버퍼링을 꺼 주세요.

## 버전
- SemVer를 따르고, 현재 버전은 **2.1.0**이에요.
- 서비스 워커 캐시 이름은 `llmchat-<버전>`이에요(`sw.js`). 정적 파일의 `?v=<버전>`과 `app.js`의 `APP_VERSION`도 같이 올려요.
- 실행 중인 버전은 설정 화면 아래에 `v<버전> · SW <버전>`으로 표시돼요.

## 선톡 API 상태 (1.1.0)
선톡 UI의 서버 호출은 모두 `proactive-api.js`의 `ENDPOINTS` 표에 모여 있어요. 백엔드가 정해지면 이 표만 고치면 돼요.
서버가 404/405/501을 돌려주면 해당 기능은 숨겨지거나 "아직 지원하지 않아요"로 표시돼요. 앱에는 클라이언트 mock이 없고, 테스트용 mock은 `tests/mock.py`에 있어요.
서버 필드 이름은 `proactive-api.js`의 `FIELDS`에만 있어요(eve-serving `ui-api-contract.md` §3, PR #16 기준). 계약이 바뀌면 여기만 고쳐요.

| 엔드포인트 | 상태 |
|---|---|
| `GET/PATCH /v1/settings`, `POST /v1/threads/{id}/read`, `POST /v1/messages/{id}/read`, `POST /v1/proposals/{id}/revise`, `GET /v1/actions`, `POST /v1/actions/{id}/reissue·approve·reject` | 계약 있음 |
| `GET /v1/threads?unread=true` (미읽음, `/v1/notifications` 없음) | 계약 있음 §3.5.2 |
| `GET /v1/push/vapid-public-key` `{key,key_id}`, `POST /v1/push/subscriptions` → 201, `DELETE` `{endpoint}` → 204 | 계약 있음 §3.5.3 |
| `GET /v1/actions/{id}` (승인 응답 유실 시 결과 확인) | UI 가정, 없으면 `GET /v1/actions`로 대체 |

보안 규칙:
- 확인 토큰은 승인 버튼을 누를 때만 `POST /v1/actions/{id}/reissue`로 받아 바로 `approve`에 써요(§3.5.4). 지역 변수에만 두고 저장·로그하지 않아요. SSE의 토큰은 무시해요.
- 토큰·결정·`/v1/actions` 호출은 같은 origin에서만 해요(CORS 헤더 없음). 서버 주소 설정이 다른 origin이면 승인 버튼이 꺼지고 안내 문구가 나와요.
- 모든 POST/PUT/PATCH/DELETE는 `X-Eve-Request: 1`을 보내고, 본문이 있으면 `Content-Type: application/json`이에요.
- 오류는 HTTP 상태가 아니라 본문 `error_code`로 판단해요.

테스트: `tests/run_e2e.sh proactive.py`, `tests/run_e2e.sh csrf_all.py`, `node tests/sw_push.js`. 포트는 `EVE_PORT`로 바꿀 수 있어요(기본 8765).

## 메모리 (Part B, 플래그 뒤)

- 기본값은 꺼짐이에요. `localStorage['eve.flag.memory'] = '1'`일 때만 설정에 메모리 영역이 보여요.
- API 경로와 필드 이름은 `memory-api.js`에만 있어요. 스키마는 eve-serving ui-api-contract §3.9를 따라요.
- 사용자 `memory.enabled`는 `/v1/settings`에 있고, 키가 없으면 꺼짐이에요. 읽기 전용 `system.memory_available`이 서버 킬스위치예요(없으면 true). 둘 다 true일 때만 메모리가 동작해요. 읽기 전용 상태는 쓰기 응답 503 `memory_read_only`로만 알아요.
- `/v1/memory*`가 `{"detail":"Not Found"}` 404를 주면 서버 메모리가 꺼진 것으로 보고 메모리 영역을 숨겨요. `{"error_code":"not_found"}` 404는 이미 지워진 항목이에요.
- 500·503 응답은 예전 `{error:{code}}` 형식이고, 4xx 응답은 `{error_code}` 형식이에요. 둘 다 읽어요.
