# LLM Chat UI (Mac Studio 로컬 LLM용)

빌드·의존성 없는 모바일 우선 채팅 PWA. OpenAI 호환 API(`/v1/models`, `/v1/chat/completions` stream)를 그대로 호출합니다.

## 배포 방법 A — 게이트웨이 내장 /ui (권장, CORS 불필요)
게이트웨이(gateway.py)는 `static_dir`(기본 `~/llm-serving/web`)이 존재하면 자동으로 `/ui`에 마운트합니다.
```bash
rsync -a --delete llm-chat-ui/ mac-studio:~/llm-serving/web/
ssh mac-studio 'launchctl kickstart -k gui/$(id -u)/com.llmserving.gateway; launchctl kickstart -k gui/$(id -u)/com.llmserving.gateway-ts'
```
(폴더가 처음 생기는 경우에만 재시작 필요) → 아이폰에서 `http://<mac-name>.<your-tailnet>.ts.net:8000/ui/` 접속.
Base URL은 비워두면 같은 서버의 `/v1/...`를 상대경로로 호출합니다. API 키(`~/llm-serving/.api_key`)만 입력하세요.

## 배포 방법 B — 별도 정적 서버 (manifest/sw 스코프가 /ui/ 이므로 ui 하위경로로 서빙)
```bash
mkdir -p ~/llm-static && cp -r llm-chat-ui ~/llm-static/ui && cd ~/llm-static && python3 -m http.server 8080
```
`http://<mac-name>.<your-tailnet>.ts.net:8080/ui/` 접속 → 설정 Base URL에 `http://<mac-name>.<your-tailnet>.ts.net:8000` 입력.
게이트웨이 CORS 필요: config.yaml `cors_origins: ["http://<mac-name>.<your-tailnet>.ts.net:8080"]` (또는 `GW_CORS_ORIGINS=...`) 후 재시작.

## HTTPS (선택, 오프라인 캐시/서비스워커용)
서비스워커는 HTTPS(또는 localhost)에서만 동작합니다. HTTP에서도 채팅·홈 화면 추가는 정상 동작합니다.
HTTPS가 필요하면: `tailscale serve --bg 8000` → `https://<mac-name>.<your-tailnet>.ts.net/ui/`

## 사용법
- 첫 실행 시 설정 창: API 키 입력 → "불러오기"로 모델 선택 → 저장 (localStorage에 저장)
- ☰ 메뉴: 대화 목록, 새 대화, ✎ 이름 변경, 🗑 삭제, ⚙︎ 설정(시스템 프롬프트 등)
- 응답 중 ■ 버튼으로 중지. Qwen3의 `<think>` 내용은 접이식 "생각 과정"으로 표시
- 아이폰 Safari: 공유 → "홈 화면에 추가"로 앱처럼 사용
- 키/대화는 해당 브라우저에만 저장됩니다 (Safari 데이터 삭제 시 함께 삭제)

## 스트리밍 주의
리버스 프록시를 쓴다면 SSE 버퍼링을 끄세요(`X-Accel-Buffering: no`). 백엔드는 `text/event-stream`으로 `data: {...}\n\n` / `data: [DONE]`을 보내야 합니다. `delta.reasoning` / `reasoning_content` / `<think>` 모두 생각 과정으로 표시, 스트림 중 `data: {"error":...}`는 오류로 표시, 429/502/503/504와 네트워크 오류는 "재시도" 버튼 제공, 마지막 청크의 `usage`(토큰 수)를 답변 아래 작게 표시합니다.
설정의 "thinking 끄기"를 켜면 보내는 마지막 사용자 메시지 끝에 ` /no_think`를 붙입니다. 기본 모델: `mlx-community/Qwen3-30B-A3B-4bit`.

## v6 · 네이티브 iOS 느낌 (NATIVE-SPEC v1)
- 구조: 대화 목록(라지 타이틀 + 검색) → 채팅 push. 설정은 시트(취소/완료). 761px 이상은 사이드바 유지.
- 제스처: 왼쪽 가장자리 스와이프로 뒤로(홈 화면 앱에서만), 목록 행 왼쪽 스와이프(이름 변경/삭제, 끝까지 밀면 삭제), 길게 누르기 메뉴, 시트는 아래로 끌어서 닫기.
- 상태 복원: 마지막 화면, 대화, 스크롤 위치, 입력 중인 초안.
- SW `llmchat-v6`: 앱 셸 precache, 정적 파일 SWR, `/v1/`은 네트워크만 사용. 오프라인 대체 화면, "새 버전" 토스트. **HTTPS에서만 동작** (`tailscale serve --bg 8000` → `https://<mac-name>.<your-tailnet>.ts.net/ui/`). HTTP여도 앱은 정상 동작.

### iPhone에서 테스트
1. 배포: `rsync -a --delete llm-chat-ui/ mac-studio:~/llm-serving/web/` 후 게이트웨이 kickstart.
2. Safari에서 `https://<mac-name>.<your-tailnet>.ts.net/ui/` 열기 → 두 번째 방문(또는 첫 답변 후)에 설치 안내 시트가 뜸. 공유 → 홈 화면에 추가.
3. 홈 화면 앱은 Safari와 저장소가 분리되므로 API 키를 다시 입력.
4. 확인할 것: 스플래시 → 앱, 상태바 아래 블러 바, 가장자리 스와이프 뒤로, 행 스와이프/길게 누르기, 키보드가 열려도 컴포저가 위에 붙는지, 비행기 모드에서 실행 → 오프라인 배너, 앱 종료 후 재실행 시 같은 대화/초안 복원.
5. 로컬 테스트: `cd tests && ./run_e2e.sh` (기존 e2e), `./run_e2e.sh native.py` (42개 네이티브 검사), `./run_e2e.sh shots_native.py` (스크린샷).

## Tests

End-to-end tests (Playwright, against a local mock API) live in `tests/`.

```bash
cd tests
python3 -m venv v && v/bin/pip install playwright && v/bin/playwright install chromium   # first time only
./run_e2e.sh            # runs e2e.py; pass another script name to run it instead
```

`mock.py` serves this app at `http://127.0.0.1:8765/ui/` with a fake OpenAI-compatible API.
