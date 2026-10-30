# Eve — 채팅 UI

OpenAI 호환 백엔드용 모바일 우선 채팅 PWA예요. Vite + TypeScript 툴체인을 사용해요. ES 모듈로 나눈 기존 UI와 동작을 유지하며, 런타임 의존성은 아직 없어요.

## 실행
Node 20.19+ 또는 22.12+에서 `npm ci --ignore-scripts && npm run check && npm run build`를 실행해요. 개발 의존성은 락파일로 고정하고 설치 스크립트는 실행하지 않아요. 배포 대상은 `dist/` 44개 파일뿐이에요. 서비스 워커는 HTTPS(또는 localhost)에서만 동작해요.

```bash
npm run build
EVE_PORT=8080 python3 tests/mock.py  # http://127.0.0.1:8080/ui/ (로컬 mock)
```

운영에서는 백엔드 게이트웨이가 `dist/` 내용을 `/ui/` 경로로 서빙해요(같은 출처라 CORS가 필요 없어요). `.git`과 `tests/`는 배포하지 않아요.

## 백엔드 연결
- 기본값은 **같은 출처**예요. UI는 상대 경로 `/v1/...`(`/v1/models`, `/v1/chat/completions`, `/v1/threads` 등)와 `/whoami`를 호출해요.
- 설정의 Base URL(`localStorage` `llmchat.settings`의 `base`)로 다른 주소를 지정할 수 있어요. 끝의 `/`와 `/v1`은 자동으로 잘라요. 예: `https://<gateway-host>`
- 브라우저는 API 키를 보내지 않아요. 인증은 게이트웨이 앞단의 신원 헤더로 처리해요.
- 스트리밍은 SSE(`text/event-stream`)를 써요. 리버스 프록시를 쓴다면 버퍼링을 꺼 주세요.

## 버전
- SemVer를 따르고, 현재 버전의 정본은 `package.json`의 `version`이에요.
- 빌드가 한 버전을 SW 캐시 이름 `llmchat-<버전>`, 정적 파일 `?v=<버전>`, `APP_VERSION`에 주입해요. 루트 HTML/JS의 `__EVE_VERSION__`은 빌드 템플릿이에요.
- 실행 중인 버전은 설정 화면 아래에 `v<버전> · SW <버전>`으로 표시돼요.

## R0 개발·배포 경계

`npm run check`는 Biome, TypeScript, 크기 ratchet, import 방향·순환 검사와 Node 단위 테스트를 실행해요.
`bash tests/run_all.sh`는 `npm ci`·검사·빌드 후 `dist/`를 서빙해 기존 브라우저 스위트를 실행해요.
`EVE_WEBKIT=1`을 주면 추가 스모크에서 WebKit도 확인해요(브라우저 설치 필요).
`tools/deploy-files.json`이 산출물 고정 목록이고, 빌드는 CSP·프리캐시 완전성도 검사해요.
레거시 파일은 R1 이후 단계적으로 타입 검사·포맷 범위를 넓혀요. 새 `src/`·도구는 지금부터 검사해요.

**현재 서명 릴리스는 소스 파일을 패키징하므로 이 브랜치를 태그·배포하면 안 돼요.**
별도 보안 검토된 빌드→산출물 서명 파이프라인이 선행돼야 해요. CI/CD는 이 PR에서 수정하지 않아요.
프레임워크 선택과 이행 제약은 [R0 결정 기록](docs/refactor-r0.md)을 보세요.

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
