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
