# LLM Chat UI (로컬 LLM 게이트웨이용)

빌드·의존성 없는 모바일 우선 채팅 PWA. OpenAI 호환 API(`/v1/models`, `/v1/chat/completions` stream)를 그대로 호출합니다.

## 배포 방법 A — 게이트웨이 내장 /ui (권장, CORS 불필요)
게이트웨이(gateway.py)는 `static_dir`(기본 `~/llm-serving/web`)이 존재하면 자동으로 `/ui`에 마운트합니다.
```bash
# 서버(배포 호스트)에서: 저장소 clone은 최초 1회
git clone https://github.com/gun025bba/llm-chat-ui.git ~/llm-chat-ui   # 최초 1회
cd ~/llm-chat-ui && git pull --ff-only
rsync -a --delete --exclude .git --exclude tests --exclude '.gitignore' ./ ~/llm-serving/web/
```
(폴더가 처음 생기는 경우에만 재시작 필요)

## 접속 주소와 인증 (v9 · Tailscale 신원 인증)
- 주소: **`https://<host>.<your-tailnet>.ts.net/ui/`** (`tailscale serve`로 HTTPS, 포트 없음). 예전 `http://…:8000` 주소는 닫혔습니다.
- 브라우저에는 API 키가 없습니다. `tailscale serve`가 넣어 주는 `Tailscale-User-Login` 헤더로 서버가 사용자를 확인합니다. API 키는 스크립트 전용입니다.
- 시작할 때 `GET /whoami`로 로그인 상태를 확인하고, 설정 화면 아래에 연결된 계정이 작게 표시됩니다.
- 401(`unauthenticated`)이면 "Tailscale 연결을 확인하세요", `identity_not_allowed`면 "허용되지 않은 Tailscale 계정" 안내와 **다시 시도** 버튼이 뜹니다. 이 기기에서 Tailscale 앱이 켜져 있고 로그인돼 있는지 확인하세요.
- 예전 버전에서 저장한 API 키와 `:8000`/IP를 가리키는 Base URL 설정은 첫 실행 때 자동으로 지워집니다.

## 홈 화면 앱 다시 추가하기 (주소가 바뀌어서 필요)
1. 홈 화면의 예전 아이콘을 길게 눌러 **앱 삭제**(또는 홈 화면에서 제거).
2. Safari에서 새 주소 `https://<host>.<your-tailnet>.ts.net/ui/`를 엽니다.
3. **공유** 버튼 → **홈 화면에 추가** → 추가.
4. 새 아이콘으로 실행합니다. 대화 기록은 주소(출처)별로 저장되므로 예전 대화는 넘어오지 않습니다.

## 사용법
- 키 입력 없이 바로 대화를 시작합니다. ⚙︎ 설정에서 모델 선택("불러오기"), 시스템 프롬프트, 생각 과정 옵션을 바꿀 수 있습니다.
- 대화 목록, 새 대화, 이름 변경, 삭제, 응답 중 ■ 버튼으로 중지. Qwen3의 `<think>` 내용은 접이식 "생각 과정"으로 표시
- 대화는 해당 브라우저에만 저장됩니다 (Safari 데이터 삭제 시 함께 삭제)

## 스트리밍 주의
리버스 프록시를 쓴다면 SSE 버퍼링을 끄세요(`X-Accel-Buffering: no`). 백엔드는 `text/event-stream`으로 `data: {...}\n\n` / `data: [DONE]`을 보내야 합니다. `delta.reasoning` / `reasoning_content` / `<think>` 모두 생각 과정으로 표시, 스트림 중 `data: {"error":...}`는 오류로 표시, 429(`queue_full`/`queue_timeout`/`rate_limited`)/502/503/504와 네트워크 오류는 "재시도" 버튼 제공, 마지막 청크의 `usage`(토큰 수)를 답변 아래 작게 표시합니다.
설정의 "thinking 끄기"를 켜면 보내는 마지막 사용자 메시지 끝에 ` /no_think`를 붙입니다. 기본 모델: `mlx-community/Qwen3-30B-A3B-4bit`.

## v6 · 네이티브 iOS 느낌 (NATIVE-SPEC v1)
- 구조: 대화 목록(라지 타이틀 + 검색) → 채팅 push. 설정은 시트(취소/완료). 761px 이상은 사이드바 유지.
- 제스처: 왼쪽 가장자리 스와이프로 뒤로(홈 화면 앱에서만), 목록 행 왼쪽 스와이프(이름 변경/삭제, 끝까지 밀면 삭제), 길게 누르기 메뉴, 시트는 아래로 끌어서 닫기.
- 상태 복원: 마지막 화면, 대화, 스크롤 위치, 입력 중인 초안.
- SW(현재 `llmchat-v13`, 정적 파일은 `?v=` 무시하고 캐시 조회): 앱 셸 precache, 정적 파일 SWR, `/v1/`은 네트워크만 사용. 오프라인 대체 화면, "새 버전" 토스트. HTTPS에서만 동작.

### iPhone에서 테스트
1. 배포: 위 "배포 방법 A" (서버에서 `git pull` + rsync). `web/` 폴더가 이미 있으면 재시작 불필요.
2. Safari에서 `https://<host>.<your-tailnet>.ts.net/ui/` 열기 → 두 번째 방문(또는 첫 답변 후)에 설치 안내 시트가 뜸. 공유 → 홈 화면에 추가.
3. 키 입력은 필요 없습니다. 홈 화면 앱에서 설정을 열어 연결된 계정이 보이는지 확인.
4. 확인할 것: 스플래시 → 앱, 상태바 아래 블러 바, 가장자리 스와이프 뒤로, 행 스와이프/길게 누르기, 키보드가 열려도 컴포저가 위에 붙는지, 비행기 모드에서 실행 → 오프라인 배너, 앱 종료 후 재실행 시 같은 대화/초안 복원.
5. 로컬 테스트: `cd tests && ./run_e2e.sh` (기존 e2e), `./run_e2e.sh native.py` (52개 네이티브 검사), `./run_e2e.sh threads.py` (서버 대화 저장), `./run_e2e.sh header_crisp.py` (헤더 글자 선명도), `./run_e2e.sh shots_native.py` (스크린샷).

## v10 · 서버에 대화 저장 (threads API)
게이트웨이에 DB가 연결되어 있으면 대화가 서버에 저장되어 여러 기기에서 이어서 볼 수 있습니다. 계약은 llm-serving `docs/threads-api.md`를 따릅니다.
- 시작할 때 `GET /v1/threads`가 성공하면 **서버 모드**가 됩니다. `503 persistence_disabled`(또는 API 없음)이면 **이 기기 전용 모드**로 바뀌고, 상단에 "서버 저장이 꺼져 있어 이 기기에만 저장돼요"가 작게 표시됩니다. 채팅은 그대로 됩니다.
- 대화 목록: 날짜별 묶음, 아래로 스크롤하면 더 불러오기, 이름 변경(목록에서 바로 수정하거나 제목을 눌러 시트에서), 밀어서 또는 메뉴로 **보관**(2.8초 동안 되돌리기 가능, 그 뒤 서버에 반영). 보관함(`#/archive`)에서 복원할 수 있습니다. 서버에는 완전 삭제가 없어서 서버 모드에서는 보관만 됩니다.
- 검색: 기기에 있는 대화를 먼저 보여 주고, 250ms 뒤 서버 검색 결과를 `<mark>` 강조와 함께 붙입니다. 결과를 누르면 해당 메시지로 이동합니다.
- 메시지: 위로 스크롤하면 이전 메시지를 불러오며 스크롤 위치를 유지합니다. 답변 아래 버튼 순서는 복사 · 다시 생성 · 👍 · 👎 · 토큰입니다. 👎를 누르면 이유를 고르는 시트가 뜨고(건너뛰기 가능) 내용은 `comment`로 저장됩니다. 다시 생성하면 같은 메시지가 바뀌고 피드백은 초기화됩니다.
- 저장 실패(네트워크, 5xx, 429)는 대기열에 넣어 최대 60초 간격으로 다시 시도합니다. 상태는 목록 상단(`#syncStatus`)과 설정 > 동기화에 표시됩니다.
- **기존 기기 대화 옮기기**: 서버 모드에서 이 기기에 저장된 대화가 있으면 한 번 물어봅니다. 5개씩 `POST /v1/threads/import`로 올리고, 실패한 항목만 다시 시도할 수 있습니다. 옮긴 뒤에도 기기 사본은 7일 동안 보관됩니다. "나중에"는 3일 뒤 다시 묻습니다(최대 3번).

## Tests

End-to-end tests (Playwright, against a local mock API) live in `tests/`.

```bash
cd tests
python3 -m venv v && v/bin/pip install playwright && v/bin/playwright install chromium   # first time only
./run_e2e.sh            # runs e2e.py; pass another script name to run it instead
```

`mock.py` serves this app at `http://127.0.0.1:8765/ui/` with a fake OpenAI-compatible API.

## Workflow
- GitHub(`gun025bba/llm-chat-ui`)가 단일 진실의 원천(source of truth)입니다.
- 수정은 clone에서 → commit → push. 배포 서버의 `~/llm-serving/web/`을 직접 수정하지 마세요 (배포 사본).
- 개발 환경/서버에서는 `git pull --ff-only`로 동기화. force-push 금지. 실제 호스트명·IP·키는 커밋하지 마세요 (`<host>`, `<tailscale-ip>` 사용).

## CSP (v13)
게이트웨이의 `/ui` 정책 `default-src 'self'; img-src 'self' data:; connect-src 'self'`에서 그대로 동작해요. 인라인 `<script>`/`<style>`/`style=` 속성/`on*=` 핸들러, eval, blob:, 외부 폰트·이미지를 쓰지 않아요(동적 스타일은 CSSOM `el.style.x`만 사용). 모델 출력의 마크다운 링크는 `target="_blank" rel="noopener noreferrer"`, 마크다운 이미지는 링크로만 표시해요. 회귀 테스트: `tests/stop_csp.py`.
