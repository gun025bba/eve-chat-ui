# AGENTS.md — eve-web (프런트엔드)

Eve 채팅 UI PWA예요. Vite + TypeScript로 빌드하며, 앱 진입점에서 API·feature 모듈을 조립하며 기존 UI 동작을 유지해요. 백엔드(eve-serving 게이트웨이)는 `dist/` 산출물을 `/ui/`로 서빙해야 해요. 런타임 의존성은 아직 없고 개발 도구는 정확한 버전과 락파일로 고정해요. 자세한 내용은 [README.md](README.md)를 보세요.

## 실행·테스트
```bash
npm ci --ignore-scripts && npm run check && npm run build
python3 -m http.server 8080 --directory dist  # 자산만 확인; /ui/ 앱은 tests/mock.py 사용
python -m pip install -r tests/requirements.txt && python -m playwright install chromium   # 처음 한 번
bash tests/run_all.sh                # 전체 스위트 (CI와 동일, mock.py 사용)
tests/run_e2e.sh <suite>.py          # 스위트 하나만, 예: tests/run_e2e.sh proactive.py
node tests/sw_push.js                # 빌드된 서비스 워커 푸시 테스트
```
레이아웃 테스트는 한글 폰트(NanumGothic)에 맞춰져 있어서 로컬에서 미세하게 다르면 CI 결과를 기준으로 봐요.

## 작업 방식
- 이슈 하나에 PR 하나. UI 변경에는 해당 `tests/*.py` 테스트를 추가하거나 고쳐요.
- CI(`test.yml`)가 통과해야 머지해요. force-push 금지.
- 서버 API 경로와 필드 이름은 `*-api.js`의 표에만 두어요. 계약은 eve-serving 문서가 기준이에요.
- 릴리스 버전의 정본은 `package.json`의 `version`이에요. 빌드가 `sw.js` 캐시 이름, 정적 파일의 `?v=`, `app.js`의 `APP_VERSION`에 주입해요. 루트 HTML/JS는 템플릿이므로 직접 배포하지 않아요.
- 메이저 변경(인증·확인 카드·보안 경계에 닿는 변경 포함)은 보안 리뷰가 필요해요.
- 비밀값, 실제 주소·호스트 이름, 서버 머신 이름을 커밋하지 않아요. 토큰은 저장하거나 로그에 남기지 않아요.
- 봇이 만든 커밋의 트레일러는 `Co-authored-by: Grok <grok-bot@noreply.invalid>` 하나만 써요. Codex 커밋에는 추가 트레일러를 넣지 않아요.

## Codex 범위 (코드 구현만)
할 일: 이슈에 적힌 범위의 UI·JS 구현, 테스트 추가, 리팩터링. 끝나면 PR을 열고 멈춰요.

하지 않는 일:
- 배포, 서버 설정 변경
- 비밀값 다루기
- 실제 DB 마이그레이션 실행
- `.github/workflows/` 등 CI/CD 수정
- 이슈 범위를 벗어난 변경
