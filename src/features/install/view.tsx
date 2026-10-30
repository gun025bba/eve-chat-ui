export type InstallView = { hidden: boolean; shown: boolean; manual: boolean; bip: boolean; ipad: boolean };
function Steps({ ipad }: { ipad: boolean }) {
  return (
    <ol class="install-steps ios-only">
      <li>
        <span class="step-ic">
          <svg class="i" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 3v12M7 8l5-5 5 5" />
            <path d="M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7" />
          </svg>
        </span>
        <span class="step-share">
          {ipad ? (
            <>
              주소창 옆 <b>공유</b> 버튼(또는 ··· → 공유)을 누르고
            </>
          ) : (
            <>
              아래 <b>공유</b> 버튼을 누르고
            </>
          )}
        </span>
      </li>
      <li>
        <span class="step-ic">
          <svg class="i" viewBox="0 0 24 24" aria-hidden="true">
            <rect x="3" y="3" width="18" height="18" rx="4" />
            <path d="M12 8v8M8 12h8" />
          </svg>
        </span>
        <span>
          '<b>홈 화면에 추가</b>' 선택
        </span>
      </li>
      <li>
        <span class="step-ic">
          <svg class="i" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M5 12l5 5 9-10" />
          </svg>
        </span>
        <span>
          오른쪽 위 '<b>추가</b>'
        </span>
      </li>
    </ol>
  );
}
export function InstallSheet({
  state,
  later,
  install,
}: {
  state: InstallView;
  later: () => void;
  install: () => void;
}) {
  const classes = ['mini-sheet', state.bip && 'bip', state.ipad && 'ipad', state.shown && 'show']
    .filter(Boolean)
    .join(' ');
  return (
    <div
      id="installSheet"
      class={classes}
      hidden={state.hidden}
      role="dialog"
      aria-labelledby="installTitle"
      data-manual={state.manual ? '1' : ''}
    >
      <div class="grabber" />
      <img src="icons/apple-touch-icon.png" alt="" class="install-icon" />
      <h3 id="installTitle">홈 화면에 추가하기</h3>
      <p class="install-sub">전체 화면으로, 앱처럼 빠르게 열 수 있어요</p>
      <Steps ipad={state.ipad} />
      <p class="install-note ios-only">
        홈 화면 앱은 Safari와 저장소가 분리되지만, 서버에 저장된 대화는 그대로 보여요.
      </p>
      <button type="button" id="installBtn" class="primary bip-only" onClick={install}>
        설치
      </button>
      <button type="button" id="installLater" class="text-btn wide" onClick={later}>
        나중에
      </button>
      <div class="share-hint a2hs-arrow ios-only" aria-hidden="true">
        <svg class="i" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 5v14M6 13l6 6 6-6" />
        </svg>
      </div>
    </div>
  );
}
