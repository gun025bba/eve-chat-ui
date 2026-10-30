# R0 결정 기록 — 툴체인과 가드레일

기준: main `2e7ede8`, 2026-10-30. [요구사항](https://app.notion.com/p/4088fc84110081f996c8f89acb8e388c).
목표: Vite + TypeScript + Preact + 네이티브 CSS. R0은 앱 동작을 보존하고, Preact 설치·화면 전환은 R3에서 한다.
R1 순수 로직 추출 → R2 모듈 경계 → R3/R4 feature별 컴포넌트 → R5 CSS → R6 정리 순서다.

## 프레임워크 선택

프로덕션 모드, Safari 16.4 타깃, 같은 article/div 텍스트 컴포넌트의 실제 빌드값이다.
macOS arm64, Chromium 148.0.7778.96 / WebKit 26.4, Playwright 1.60.0에서 측정했다.
268개 누적 텍스트(32자씩) 업데이트를 20회 반복, 워밍업 1회 제외 7회 중앙값을 1회 재생으로 환산했다.
매 업데이트마다 DOM textContent가 입력과 같은지 검증한다. 네트워크·레이아웃·전체 generate() 벤치마크는 아니다.
generate()/patchLive의 stableCut/renderMarkdown도 같은 입력으로 재생했다(공통 전처리 합계 2.626ms).

| 후보 | JS 원본 / gzip B | JS 요청 | Chromium / WebKit 재생 ms | npm 직접 의존성 | 판단 |
|---|---:|---:|---:|---:|---|
| Preact 11.1.0 | 10,837 / 4,619 | 1 | 0.380 / 0.150 | 0 | 선택: 가장 작고 명령형 DOM과 공존하기 쉬움 |
| React 19.3.1 + react-dom | 218,594 / 67,486 | 1 | 0.515 / 0.250 | react-dom에 react/scheduler 필요 | 현재 UI에 비해 전송 비용이 큼 |
| Svelte 5.57.3 | 24,992 / 9,944 | 1 | 0.430 / 0.150 | 16 (컴파일러 포함 패키지) | 컴파일 플러그인 추가 필요 |

세 후보 모두 CSP 위반 0, style 태그/속성 주입 0, 공격 문자열이 DOM 요소가 되지 않는 것을 확인했다.
예제에서 애니메이션·unsafe HTML API를 쓰지 않았다. 이는 프레임워크의 모든 기능이 안전하다는 뜻은 아니다.
R3에서도 텍스트 바인딩만 허용하고, raw HTML·CSS 주입 플러그인·외부 CDN은 도입하지 않는다.
WebKit 확인은 최신 자동화 엔진의 스모크이며 Safari 16.4·iOS 17 WKWebView 실기기 검증을 대체하지 않는다.
세 프로젝트의 npm 메타데이터 수정일은 각각 10/27, 10/29, 10/26로 확인했다(활동성 지표일 뿐 보안 승인 아님).
재현: tools/benchmark.mjs 주석의 임시 설치 → node tools/benchmark.mjs <임시경로> →
Playwright Python 환경에서 python tools/benchmark-browser.py <임시경로>.

## 빌드·캐시·배포 경계

- Vite 8.3.5(빌드), TypeScript 6.0.3(타입·공개 AST), Biome 2.6.4(린트·포맷)만 개발 의존성이다.
  TypeScript 7의 새 API는 불안정하므로 공개 AST를 제공하는 6을 쓴다. Node는 20.19+ 또는 22.12+다.
- 기존 9개 스크립트의 순서·URL을 보존한다. main.ts가 app.js를 IIFE로 번들하고 나머지는 그대로 출력한다.
  첫 로드 JS는 main 원본 310,306B/gzip 103,558B/9요청, R0 305,176B/gzip 95,399B/9요청이다.
  gzip은 파일별 로컬 압축 합계이며 실제 HTTP 전송량·SW 백그라운드 프리캐시 요청과 구분한다.
- package.json.version만 릴리스 버전 정본이다. 앱·HTML·SW와 테스트 기대값에 주입한다.
  오프라인 문서의 레거시 ?v=16도 같은 버전으로 출력한다. 매니페스트 바이트는 보존한다.
- sw.js는 루트·무해시다. precache는 산출물 51개 전체이며 SW 자신을 제외한다.
  ?v= 정확 URL cache-first, 비버전 network-first, HTML network-first, API 제외, activate 정리는 그대로다.
  빌드 검사가 SW 이벤트 처리 코드를 원본과 바이트 비교한다. 해시 파일·동적 import·지연 청크는 없다.
- 배포 목록은 tools/deploy-files.json의 52개뿐이다. 소스·테스트·도구·설정·락파일은 dist에 없다.
  설치 스크립트는 .npmrc와 npm ci --ignore-scripts로 차단한다. 락은 52개 패키지(플랫폼별 optional 포함),
  hasInstallScript 표시는 optional fsevents 1개이며 실행하지 않았다. 런타임 의존성은 0개다.
- 서명 릴리스는 아직 소스를 tar한다. 별도 보안 검토된 빌드→산출물 서명 전에는 태그·배포 금지다.
  CI/CD·서버 설정은 수정하지 않았다. 보안 리뷰·MAJOR 릴리스 판정·실기기·롤백 배포 리허설은 담당자 후속이다.
  현재 버전은 미발행 R0 검증 기준을 유지했다. 실제 릴리스는 기본 MAJOR이며 새 버전을 먼저 정해야 한다.

## 검증과 남은 경계

npm run check: 새 src/·도구의 린트/포맷, strict TS, AST 함수 크기, import 방향·순환·동적 import 금지,
Node 가드 테스트. 기존 JS/CSS는 포맷하지 않았다. ratchet은 파일/함수 초과 줄 합계와 긴 줄 개수,
innerHTML 대입·!important 발생 개수를 추적한다(IIFE 포함: 메모의 선언 함수만 세는 방식과 다름).
기존 !important는 18개 줄에 30회다. 새 innerHTML·!important는 0, 공유 승격 장부 변경은 없다.

산출물 게이트: 고정 52개, 개발 파일 미포함, 완전 precache, 버전 일치, inline/eval/dynamic import 없음.
Chromium: 엄격 CSP·스트리밍·정지·오프라인 시작·복구 통과. WebKit: 첫 화면·브리지 훅·CSP·페이지 오류 0.
Playwright의 SW 자동화는 Chromium만 지원하므로 WebKit 오프라인 검증은 실기기로 넘긴다.
원본→R0→원본 SW 전환: 각 1회 리로드와 오프라인 시작 통과(동일 버전 R0 비교, HTTP 조건부 304 배제).
빈 오늘 화면: 테마 2종 × 320/390/768px, 시계 고정·애니메이션 제거 후 원본과 PNG 바이트 동일.
실제 배포 환경의 캐시 헤더(P0)·버전 변경/서명·실기기 업그레이드 리허설은 별도다.
WebKit 스트림 정지 시 AbortError를 관찰했으나 원인 확정 전이며 R0 첫 화면 게이트와 분리했다.

저장소의 Playwright 1.64.1은 조회한 패키지 저장소에 없어 로컬 검증은 1.60.0으로 했다.
requirements.txt와 기존 스위트의 검증 기준은 유지했다. 필수 GitHub test 결과는 PR에서 확인해야 한다.
전체 스위트 실행 결과는 PR 설명에 기록한다. #43·#44는 확인 시 미머지 상태였다.

근거: [Vite 빌드](https://vite.dev/guide/build), [Preact API](https://preactjs.com/guide/v11/api-reference/),
[TypeScript 6 API](https://www.typescriptlang.org/docs/handbook/release-notes/typescript-6-0.html),
[Playwright SW 지원](https://playwright.dev/python/docs/service-workers).
