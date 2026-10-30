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
- ios_polish/native의 기존 로컬 실패와 b3_strip/stop_csp 실패는 변경 전 코드와 별도 비교 중이다. CI 통과로 보고하지 않는다.
- 새 의존성·shared 승격 없음. 확인 카드에 닿으므로 보안 리뷰 대상으로 유지한다.
