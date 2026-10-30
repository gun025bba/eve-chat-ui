import { APP_VERSION } from '../../lib/version.js';
export function Footer() {
  return (
    <>
      <p class="sec">
        동기화 <span class="sec-note" id="sSync"></span>
      </p>
      <div class="group">
        <button type="button" id="sSyncNow" class="row-link">
          지금 동기화
        </button>
        <div id="sMigrateRow" hidden>
          <button type="button" id="sMigrate" class="row-link">
            이 기기 대화 서버로 옮기기
          </button>
        </div>
      </div>
      <div class="group a2hs-row" id="a2hsRow">
        <button type="button" id="showA2hs" class="row-link">
          홈 화면에 추가 방법
          <svg class="i chev" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M9 6l6 6-6 6"></path>
          </svg>
        </button>
      </div>
      <p class="sec">정보</p>
      <div class="group info-group">
        <div class="info-row">
          <span>모델</span>
          <span id="sModelInfo" class="info-val">
            —
          </span>
        </div>
      </div>
      <small id="appVersion" class="app-version">
        v{APP_VERSION}
      </small>{' '}
    </>
  );
}
