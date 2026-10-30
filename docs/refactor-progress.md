# 리팩터링 진행 기록

이슈: https://app.notion.com/p/4088fc84110081f996c8f89acb8e388c
사용자 지시에 따라 앞 PR의 머지를 기다리지 않고 후속 PR을 그 브랜치 위에 쌓는다. 배포·태그·머지는 하지 않는다.

## R1a — legacy 이동, SSE·think 파서

- 기반: R0 #46. 스크립트 9개를 내용 동일 이동 커밋으로 src/legacy/에 격리했다.
- SSE와 think/중지 표식을 strict TypeScript로 추출했다. SSE는 모든 문자 경계에서 CRLF·다중 data·event/id·flush를 검증한다.
- 기존 Node 테스트는 Vite가 만든 개발 전용 CJS 헬퍼 번들을 읽는다. 브라우저 전역 헬퍼는 유지한다.
- 테스트 source_path는 사라진 루트 JS 경로만 legacy로 해석한다. 기존 동작·보안·레이아웃 단언은 유지한다.
- 산출물은 동일한 52개·기존 URL·SW 규칙이다. 새 의존성·innerHTML·!important·shared 승격은 없다.
- ratchet 파일 초과 3,204→3,181줄, 긴 줄 1,266→1,264줄, 함수 초과 3,817줄 유지. 루트 파일 초과 15→6개.
- npm run check/build와 기존 마크다운·출처·CSP/오프라인·브리지·스트림 재개 검증을 수행한다.
- 나머지 마크다운·출처·도구 순수 로직 추출은 R1b에서 이어간다. 실기기·서명 파이프라인·보안 리뷰는 별도다.

## R1b — 출처·도구 데이터 모델

- 기반: R1a #47. URL 검증·출처 날짜/도메인·HTML escape와 도구 상태/실패 사유를 strict TS로 분리한다.
- citeMap의 기존 필드·순서·날짜 동작을 보존한다. 서버 문구 대신 고정 실패 문구를 쓰는 경계도 유지한다.
- 이전 헬퍼 번들과 153개 입력의 출력·도구 상태를 비교해 동일함을 확인했다. 누적 DOM 전역과 API 호출은 그대로다.
- 새 의존성·innerHTML·!important·shared 승격 없음. 마크다운/출처 HTML 렌더러 추출은 다음 R1c로 이어간다.

## R1c — 마크다운·출처 렌더러

- 기반: R1b #48. 마크다운 inline/block/list/stream과 출처 HTML을 strict TS로 분리한다.
- 인용 맵을 호출 인자로 전달해 렌더 간 공유 가변 상태를 제거한다. 출처 ID 카운터는 legacy 어댑터가 소유한다.
- 이전 번들과 2,620개 잘린 스트림·목록·인용·HTML 입력의 결과를 비교해 동일함을 확인했다.
- 스트리밍 srcDomain 누락을 복구했고, 같은 추출 오류를 막는 미정의 이름 가드를 추가했다.
- legacy app 파일 초과 1,953→1,829줄, 긴 줄 479→463. 신규 innerHTML/!important·shared 승격·의존성 없음.

## R2a — API·feature 모듈과 DOM 공통화

- 기반: R1c #49. API/feature/shell 8개 파일을 내용 동일 이동 후 ES 모듈로 연결한다.
- main.ts가 API·PIM·브리핑·선톡·메모리 의존성을 주입한다. feature 간 직접 import와 순환이 없다.
- el() 다섯 구현을 shared/dom.ts로 동시에 교체했다. 승격 장부: el — briefing, memory, pim, proactive, legacy/app.
- self.EveShell과 __app/__vv는 유지한다. 외부 브라우저 테스트가 쓰는 EvePim/EveProactiveAPI만 호환 별칭으로 남겼다.
- 클래식 진입점은 app.js 하나이고 산출물은 52→44개다. 제거한 8개 보조 스크립트는 app.js에 포함된다.
- SW fetch/lifecycle 코드는 유지하고 43개 산출물 프리캐시를 자동 생성한다. 새 의존성·innerHTML·!important 없음.
- 남은 R2는 threads/outbox API·상태 분리와 큰 proactive 모듈 분해다. 프레임워크·화면 전환은 아직 하지 않는다.

## R2b — HTTP·thread 모델과 outbox 상태

- 기반: R2a #50의 PIM 별칭 충돌 수정 포함. HTTP/인증 분류·요청 헤더·메시지/스레드 매핑·쓰기 경로를 api/로 옮긴다.
- conversations/outbox가 재시도 큐·타이머·실패 수를 소유한다. app은 mode getter·렌더/오류 콜백을 주입한다.
- llmchat.outbox 키와 {op,key,payload,tries,nextAt} 저장 형식, 2~60초 백오프·429/5xx·피드백 보정 동작을 유지한다.
- Node 계약 테스트로 헤더·204·신원 상실·outcome_unknown·토큰 scrub·쓰기 본문·중복 병합·동시 재생 금지를 검증한다.
- legacy app 파일 초과 1,829→1,766줄, 긴 줄 462→444, 함수 초과 2,275→2,208. 새 innerHTML/!important·shared 승격·의존성 없음.

## R2c — 선톡 모델·확인 카드·흐름 분리

- 기반: R2b #51. proactive 모듈을 model, confirm-card, index 세 파일로 분리한다.
- 카드 맵·ID·시스템 설정·접근성 알림은 한 인스턴스가 소유하고 의존성으로 전달한다. API·본문·토큰 처리·DOM 순서를 유지한다.
- 547줄 초과 파일을 없애고 파일 초과 합계 247줄, 함수 초과 합계 474줄을 줄였다. 긴 줄·innerHTML·!important 증가는 없다.
- source_text가 분리된 선톡 소스 전체를 읽도록 테스트를 보완했다. 아이콘 정적 검사는 R1에서 이동한 실제 TS 구현과 import를 확인한다.
- 정적 검사와 Node 10개 통과. 선톡 98개, PIM 확인 카드 19개, 메모리 58개, 후속 동작 47개, 모션·아이콘 16개 및 Chromium/WebKit 스모크를 검증한다.
- R2a 전체 회귀는 53개 Python+SW 중 5개 스위트 실패였다. motion_icons의 오래된 소스 위치 단언은 여기서 수정한다.
- ios_polish/native는 기존 로컬 실패다. b3_strip 59·stop_csp 38개는 변경 전 코드와 R2c 단독 실행 모두 통과했다. 전체 실행을 CI 통과로 보고하지 않는다.
- 새 의존성·shared 승격 없음. 확인 카드에 닿으므로 보안 리뷰 대상으로 유지한다.

## R2d — 대화 상태 소유권

- 기반: R2c #52. 대화 모드·목록·보관함·커서·로딩·저장 비활성·현재 ID를 conversations/state.ts가 소유한다.
- llmchat.mode → 선택한 캐시 → llmchat.current의 읽기 순서와 기본값을 유지한다. mode·currentId 등 테스트 훅의 외부 필드도 동일하다.
- 심볼을 기준으로 루트 변수 참조만 바꿨다. 같은 이름의 지역 변수·문자열·API 필드·저장 키는 바꾸지 않는다.
- Node 계약 테스트로 서버/로컬 캐시 선택, 유효하지 않은 모드의 기본값, 인스턴스 간 상태 격리를 검증한다.
- legacy 파일 초과 1,766→1,764줄, 함수 초과 2,208→2,205줄. 긴 줄·innerHTML·!important·shared 장부·의존성 변화 없음.

## R2e — gateway·thread 요청 경계

- 기반: R2d #53. 남은 앱 직접 api/fetch 호출을 threads.ts와 gateway.ts로 옮긴다.
- 대화·검색·이전 메시지·보관함·취소·이전(import) 경로와 페어링·신원·모델·스트림 재개·채팅 요청을 API 모듈이 정의한다.
- GET에도 붙던 X-Eve-Request, 쿠키 옵션·Last-Event-ID·AbortSignal, persistence_disabled 재전송 때 thread/replace 생략을 그대로 유지한다.
- Node 13개가 요청 경로·인코딩·메서드·헤더·본문을 검증한다. SW 프리캐시·CSP 산출물 게이트도 통과한다.
- ratchet 긴 줄 합계 1,206→1,198, 함수 초과 3,268→3,265줄. 파일 초과·innerHTML·!important 증가 없음. 신규 의존성·shared 승격 없음.

## R3a — Preact 공존과 토스트

- 기반: R2e #54. Preact 11.1.0 하나를 정확히 고정하고 설치 스크립트 없이 추가했다. Preact의 전이 런타임 의존성과 install/postinstall 스크립트는 없다.
- main의 독립 마운트에 토스트만 올린다. 기존 DOM ID·클래스·role·콜백·rAF 표시·300ms 숨김·자동 종료 타이머를 유지한다.
- 모델/사용자 문구는 JSX 텍스트로만 렌더하고 CSS는 기존 외부 파일을 그대로 쓴다. shared 컴포넌트 사전 승격은 없다.
- TSX의 .js import도 타입 소스로 해석하도록 import 게이트와 순환 검사 fixture를 보완하고 마지막 ambient EvePim 예외를 없앴다.
- Node 14개, Chromium/WebKit 토스트 14개, 대화 35·피드백 62·스모크 2·셸 브리지 21 단언 통과. WebKit은 테스트 탭을 전경으로 가져와 검증한다.
- 이전 산출물과 dark/light × 320/390/768 토스트 PNG 6개가 바이트 단위로 일치했다.
- app.js 293.85→309.58 kB, gzip 84.67→90.48 kB. 요청 수·배포 목록·프리캐시 정책은 유지한다.
- ratchet 파일 초과 2,679→2,672, 긴 줄 1,198→1,195, 함수 초과 3,265→3,258. 신규 innerHTML/!important 0.
- 새 런타임 의존성·텍스트 경계이므로 보안 리뷰 대상이다. npm audit은 취약점 0이었으며 보안 승인을 대신하지 않는다.

## R3b — 이름 변경 시트와 기존 시트 동작 추출

- 기반: R3a #55. 이름 변경 UI를 conversations/rename.tsx로 옮기고 callback으로 updateThread를 주입한다.
- 기존 sheetDrag/animateOut/openMini/closeMini를 shared로 이동한다. 설정·설치·이름 변경·오늘 띠·이전 시트 호출처를 동시에 바꿨다. 새 불리언 모드 인자는 없다.
- 새 승격 장부: 기존 시트 제스처(설정·설치·이름 변경·오늘 띠)와 미니 시트 수명(이름 변경·오늘 띠·이전). CSS·임계 거리/속도·지연·스크림·lock 처리는 유지한다.
- 제목은 입력 값과 텍스트로만 취급한다. IME Enter·일반 Enter·취소·Escape·바깥 탭·선택 포커스의 Chromium/WebKit 12개 단언 통과.
- Node 14개와 산출물 게이트 통과. 기존 대화 35·오늘 시트 25·오버플로 19개도 통과했다. 이름 시트의 dark/light × 320/390/768 PNG 6개가 기존 산출물과 바이트 단위로 같았다.
- ratchet 파일 초과 2,672→2,615, 긴 줄 1,195→1,186, 함수 초과 3,258→3,204줄. 신규 innerHTML/!important·의존성 없음.

## R3c — 설정 화면 컴포넌트

- 기반: R3b #56. 설정의 기본 입력·선톡·메모리 프레임·정보 표시를 Preact 컴포넌트로 나누고 기존 컨트롤러에 연결한다.
- feature 간 import 없이 main이 먼저 DOM 마운트를 만든다. 설정/메모리/선톡 컨트롤러가 현재 쓰는 ID·필드·네이티브 dialog 동작을 유지한다.
- 기존 checkbox의 네이티브 checked 상태와 group 레이아웃을 보존하기 위해 해당 JSX의 a11y 정적 규칙 다섯 곳에만 사유를 적었다. iOS switch 속성도 타입을 보완했다.
- 버전 정본은 package.json이며 lib/version.ts의 단일 주입값을 화면과 앱/SW 표시가 같이 쓴다. TS 따옴표·선언 변환에 대한 단위 검증과 미치환 토큰 거부를 추가했다.
- Node 15개·설정 저장/취소/입력 속성/SW 없는 버전 표시 Chromium/WebKit 10개 통과. 메모리 58·선톡 98·브리핑 53·산출물 스모크 2개 통과.
- dark/light × 320/390/768 설정 시트 PNG 6개가 기존 산출물과 바이트 단위로 같다.
- ratchet 파일 초과 2,615→2,614, 긴 줄 1,186→1,160. 함수 초과·innerHTML·!important·승격 장부·의존성 증가는 없다.

## R3d — 홈 화면 추가 안내

- 기반: R3c #57. 설치 안내 UI·방문 수·프롬프트 이벤트·타이머·스크림을 install feature가 소유한다. busy/대화 유무/환경은 앱이 주입한다.
- visits, a2hs.installed, a2hs.dismissed와 30일 숨김·1200ms 노출·300ms 닫기·수동 안내 예외를 유지한다.
- iPad 문구의 innerHTML 대입을 JSX 텍스트/강조로 대체했다. 설정·생성 완료·초기 인증의 안내 호출은 주입된 메서드를 쓴다.
- Node 15개·산출물 게이트·Chromium/WebKit의 iPhone/iPad/desktop 설치 계약 16개 통과. 기존 native 54/55이며 원본에서도 실패한 offline fallback 하나만 남았다.
- 스모크 2·설정 10·이름 시트 12개도 통과. 두 기기 × 두 테마 × 세 너비 PNG 12개는 반복 화살표 애니메이션 위상을 고정하면 바이트 단위로 일치했다.
- ratchet 파일 초과 2,614→2,587, 긴 줄 1,160→1,150, 함수 초과 3,204→3,177, innerHTML 38→37. 신규 !important·shared 승격·의존성 없음.

### R3a 고정 소스 전체 회귀 결과

- 54개 Python + sw_push.js 실행 완료: PASS 단언 1,709개, 실패 스위트 ios_polish/native 두 개.
- 두 실패는 변경 전 main에서도 재현했다. 긴 제목의 overflow computed 값 단언과 uncached HTML의 offline fallback 단언이다.
- 나머지 52개 Python과 SW 통과. 앞 실행에서 실패했던 b3_strip·stop_csp·stream_resume·motion_icons도 통과했다.
- 전체 통과나 CI 성공으로 표현하지 않는다. 이후 feature 전환은 별도 대상으로 검증한다.

## R3e — 인증·페어링 안내

- 기반: R3d #58. 인증 안내 UI·신원·재시도·실패 횟수·잠금 타이머를 auth feature로 옮긴다. 앱이 gateway·카드 삭제·오류 정리·계정 표시·haptic을 주입한다.
- eve.paired/eve.pairLock와 8자리 Crockford 정규화·5회 실패/10분 잠금·기존 401/403 분류·쿠키 요청을 유지한다. 코드/토큰은 저장하지 않는다.
- Node 16개와 기존 pairing 30·identity_403 24·CSRF 24·선톡 98·설정 10·스모크 2개 통과. Chromium/WebKit 새 인증 계약 12개, 전체 소스 헤더 검사 12·셸 브리지 21개도 검증했다.
- 공개 파일 보안 검사는 실제 dist 전체 JS/HTML/manifest로, 전송 정적 검사는 분리된 src 전체로 넓혔다. 옵션 없는 API fetch forwarder 두 곳은 인접 메서드를 오인하지 않게 구분하고 Node 요청 계약으로 확인한다.
- 연결/재연결/거절 × 두 테마 × 세 너비 PNG 18개가 기존 산출물과 바이트 단위로 같다.
- ratchet 파일 초과 2,587→2,513, 긴 줄 1,150→1,135, 함수 초과 3,177→3,103. 신규 innerHTML/!important·shared 승격·의존성 없음. 인증 경계로 보안 리뷰 대상이다.

## R3f — 로컬 대화 이전

- 기반: R3e #59. 이전 상태·노출/건너뛰기·스크림·재시도·백업을 migration feature가 소유하고 API import.ts가 요청/응답 필드 매핑을 소유한다.
- 5개 단위·4.5MB 사전 분할·400/413 이분할·부분 실패 재시도·3일 숨김/3회 제한·7일 백업을 유지한다. 기존 저장 키·본문 순서·모델/추론 분리·ID를 보존한다.
- 실패 목록을 JSX 텍스트로 바꿔 innerHTML을 한 곳 줄였다. 시트 프레임의 열림/닫힘은 기존 shared mini-sheet가, 내용만 컴포넌트가 소유한다.
- Node 18개·기존 대화 35·CSRF 24·산출물 스모크 2·설정 10개 통과. Chromium/WebKit 이전 계약 12개는 백그라운드 실패·재시도·백업·잠금·텍스트 경계를 확인한다.
- 초기 WebKit 대기는 한 번 시간 초과했지만 단독 재실행과 전환 전 산출물의 동일 테스트가 모두 12개 통과했다.
- 안내/부분 실패/완료 × 두 테마 × 세 너비 PNG 18개가 기존 산출물과 바이트 단위로 같다.
- 새 feature 계약 6개에 full CSP와 위반 수집/초기화 하네스를 적용했고 Chromium/WebKit 합계 76개 단언이 통과했다.
- ratchet 파일 초과 2,513→2,434, 긴 줄 1,135→1,110, 함수 초과 3,103→3,024, innerHTML 37→36. 신규 !important·shared 승격·의존성 없음.

## R4a — 메시지 피드백

- 기반: R3f #60. 평가 버튼·사유·메모·패널 수명·스크롤 감시·오류 복구를 feedback feature로 분리했다. API 모듈은 전체 교체 본문을 복사해 재전송 중 선택 변경과 격리한다.
- Preact의 native portal로 기존 액션 행에 버튼만 마운트하고, 복사/재생성/사용량과 기존 DOM 순서를 유지한다. 메시지 재렌더 시 컴포넌트·패널·observer를 정리한다.
- 즉시 평가 저장·사유 순서·140자/IME·Escape·스크롤 자동 저장·낙관적 롤백·오프라인 outbox·기존 요청/저장 키를 유지한다.
- Node 19개와 산출물 게이트 통과. 기존 피드백 62개 단언을 full CSP에서 Chromium/WebKit 각각 통과했다.
- ratchet 파일 초과 2,434→2,332, 긴 줄 1,110→1,085, 함수 초과 3,024→2,922, innerHTML 36→30. 신규 !important·shared 승격·의존성 없음.
- 대화 35·산출물 스모크 2개도 통과했고, 평가/메모/저장/좋아요 × 두 테마 × 세 너비 PNG 24개가 이전 산출물과 바이트 단위로 같다.

## R4b — 대화 행·보관 상태

- 기반: R4a #61. 목록/보관함 행을 JSX로 바꾸고 보관·복원·로컬 삭제·지연 커밋·되돌리기 상태를 conversations/archive.ts로 분리했다.
- 2.8초 되돌리기·현재 대화/초안 선택·생성 중단·백그라운드 커밋·쓰기 실패 롤백과 기존 API/outbox 키를 유지한다. 선톡 dot/pill/마크의 DOM 순서와 장식 콜백도 유지한다.
- Node 19개·빌드 게이트·기존 대화 35·선톡 98개 통과. 두 테마 × 세 너비의 목록/보관함 PNG 12개가 이전 산출물과 바이트 단위로 같다.
- 목록 계약을 full CSP와 Chromium/WebKit으로 확장하고, 악성 형태의 제목·미리보기와 반복 갱신의 중복 액션을 확인한다.
- ratchet 파일 초과 2,332→2,301, 긴 줄 1,085→1,073, 함수 초과 2,922→2,889, innerHTML 30→28. 신규 !important·shared 승격·의존성 없음.
- 확장 목록 계약 35개 단언을 Chromium/WebKit 각각 통과했다. 되돌리기 후 타이머 취소와 백그라운드 지연 커밋도 실제 API 상태로 확인한다.

### R3f 고정 소스 전체 회귀 결과

- Python 59개 + sw_push.js 실행 완료: PASS 단언 1,771개, 실패 스위트 ios_polish/native 두 개.
- 두 실패는 변경 전 main에서도 재현한 computed overflow 값/uncached HTML fallback 단언이다. 나머지 57개 Python과 SW 검사는 통과했다.
- R3a 이후 추가한 auth/install/migration/rename/settings 계약도 포함한다. 전체 통과나 CI 성공으로 표현하지 않는다.

## R4c — 목록·검색 결과·보관함 컴포넌트

- 기반: R4b #62. 날짜 그룹·고정 정렬·검색 결과·스켈레톤·보관함을 Preact가 소유하며, 편집 중 갱신 금지·그룹 모서리·기존 행 재생성 동작을 유지한다.
- 검색 타이머·순번·결과는 ConversationSearch가 소유한다. 250ms debounce·이전 응답 무시·중복 결과 분류·진행 표시를 유지한다.
- 검색 snippet은 정확한 mark 토큰만 JSX로 구성하고 다른 HTML 형태 입력은 텍스트로 남긴다. 정상/중첩/잘못 닫힌 태그와 악성 HTML의 DOM을 이전 escape+mark 처리와 비교한다.
- Node 19개·빌드·대화 35·가로 넘침 19개 통과. 목록/보관함/검색 × 두 테마 × 세 너비 PNG 18개가 이전 산출물과 바이트 단위로 같다.
- WebKit의 SW 활성 컨텍스트에서 page route 검색 응답 가로채기가 시간 초과했고, UI 테스트의 service_workers=block 격리 후 full CSP 확장 목록 37개가 통과했다. 서비스 워커 검증은 별도 원본 계약을 유지한다.
- ratchet 파일 초과 2,301→2,272, 긴 줄 1,073→1,061, 함수 초과 2,889→2,858, innerHTML 28→20. 신규 !important·shared 승격·의존성 없음.
- 최종 UI 격리 설정에서 Chromium/WebKit 각각 37개 단언 통과. CSP 위반·페이지 오류가 없으며 기존 SW 소스/회귀 테스트는 변경하지 않았다.

## R4d — 메시지 타임라인 프레임

- 기반: R4c #63. 메시지 프레임·시각/이름·날짜 구분·빈 화면·로딩/이전 메시지 표시를 JSX로 옮겼다. 프레임 수명은 Timeline이 관리하며 화면 초기화·삭제·재생성 시 피드백 컴포넌트와 패널도 정리한다.
- 기존 KST 포맷·DOM/ARIA·사용자 텍스트·입장 애니메이션·선톡 장식·날짜 구분·현재 시각 갱신·스크롤을 유지한다. 공통 time/shared 승격은 하지 않고 호스트가 기존 formatter를 주입한다.
- 생성 도중 반복 새 대화에서 WebKit의 AbortError를 전환 전 산출물에서도 재현했다. 기존 reader.cancel()의 동기 catch가 놓친 비동기 거절을 API stream helper에서 처리하고 Node 회귀 검사를 추가했다. API 요청·취소 시점·전송 본문은 유지한다.
- Node 20개·빌드 게이트 통과. full CSP 타임라인 28개를 Chromium/WebKit 각각 통과했고, 빈 화면 11·피드백 62·중지/CSP 38개도 통과했다.
- 이벤트/빈 화면 × 두 테마 × 세 너비 PNG 12개가 이전 산출물과 바이트 단위로 같다.
- ratchet 파일 초과 2,272→2,256, 긴 줄 1,061→1,051, 함수 초과 2,858→2,840, innerHTML 20→19. 신규 !important·shared 승격·의존성 없음.
- reader 취소 수정 후 기존 스트림 재연결 36개도 통과했다. 전환 전 WebKit의 27/28 결과는 수정 후 28/28로 바뀌었다.

## R4e — 메시지 액션·복사·오류

- 기반: R4d #64. 복사/재생성 버튼과 오류/재시도 내용은 JSX로, 복사 완료 표시·클립보드 폴백·Retry-After 타이머는 message parts가 소유한다.
- 1.5초 완료 표시·반복 클릭의 기존 마감 시점·원문/코드 복사·textarea 폴백·기존 액션/피드백/사용량 순서를 유지한다. 복사 표시 후 원래 노드를 복원하며 메시지 제거 시 타이머와 컴포넌트를 정리한다.
- Node 20개·빌드 게이트 통과. full CSP의 새 액션 계약은 Chromium/WebKit 합계 18개 단언 통과. 기존 피드백 62·중지/CSP 38·기본 E2E 17개도 통과했다.
- 답변/코드 복사 완료/오류 × 두 테마 × 세 너비 PNG 18개가 이전 산출물과 바이트 단위로 같다.
- ratchet 파일 초과 2,256→2,247, 긴 줄 1,051→1,046, 함수 초과 2,840→2,830, innerHTML 19→15. 신규 !important·shared 승격·의존성 없음.

## R4f — 완료 답변 Markdown 컴포넌트

- 기반: R4e #65. 완료 답변의 Markdown 내용을 기존 pure parser → 브라우저 정규화 → 허용 태그/속성 VDOM의 비공개 경로로 전환한다. 임의 HTML을 받는 공개 컴포넌트/unsafe HTML prop은 추가하지 않는다.
- 기존 escape·링크·인용·코드·목록 파서와 browserHelpers 계약은 유지한다. 스크립트/스타일/이벤트 속성은 허용하지 않으며 HTTP(S)/sprite 링크만 구성한다. 스트리밍 경로는 다음 단계에서 전환한다.
- Node 20개·빌드 통과. full CSP에서 정상/중첩/잘못된 Markdown·HTML 형태 입력·코드·인용 14종의 실제 DOM이 기존 렌더러와 Chromium/WebKit 모두 일치했다(보안/오류 포함 32개 단언).
- 액션 18·출처 47·목록 22개 통과. 두 테마 × 세 너비 PNG 6개가 이전 산출물과 바이트 단위로 같다.
- 사용처가 없는 두 과거 token-fade 함수를 제거했다. ratchet 파일 초과 2,247→2,243, 긴 줄 1,046→1,045, 함수 초과 2,830→2,825. innerHTML 15·!important 30 유지, 신규 shared 승격·의존성 없음. 렌더링 경계 보안 리뷰 대상이다.
