function QuietHours() {
  return (
    <>
      <div id="proMore" hidden>
        <p class="sec">조용한 시간</p>
        <div class="group">
          <button type="button" id="qStartRow" class="row-static">
            <span>시작</span>
            <span id="qStartVal" class="row-value"></span>
          </button>
          <div id="qStartWrap" class="time-wrap" hidden>
            <input
              id="qStart"
              type="time"
              step="900"
              aria-label="조용한 시간 시작"
              autoComplete="off"
              data-1p-ignore={true}
              data-lpignore="true"
              data-form-type="other"
            />
          </div>
          <button type="button" id="qEndRow" class="row-static">
            <span>종료</span>
            <span id="qEndVal" class="row-value"></span>
          </button>
          <div id="qEndWrap" class="time-wrap" hidden>
            <input
              id="qEnd"
              type="time"
              step="900"
              aria-label="조용한 시간 종료"
              autoComplete="off"
              data-1p-ignore={true}
              data-lpignore="true"
              data-form-type="other"
            />
          </div>
        </div>
        <p id="qErr" class="status err-text" hidden>
          시작과 종료가 같을 수 없어요
        </p>
        <p id="qTz" class="status hint">
          한국 시간 기준
        </p>
        <p class="status hint">이 시간에 온 메시지는 알림 없이 보관했다가 끝날 때 한 번에 알려 드려요.</p>
        <div id="proMemRow" hidden>
          <div class="group">
            <label class="sw">
              <span>선톡에서 메모리 사용</span>
              {/* biome-ignore lint/a11y/useAriaPropsForRole: Existing native checkbox exposes its checked state. */}
              <input id="sProMem" type="checkbox" switch role="switch" />
            </label>
          </div>
          <p class="status hint">켜면 이름·선호·진행 중인 일만 참고해요.</p>
        </div>
      </div>{' '}
    </>
  );
}
export function ProactiveOptions() {
  return (
    <>
      <p class="sec">선톡</p>
      <div class="group">
        <label class="sw">
          <span>Eve가 먼저 말하기</span>
          {/* biome-ignore lint/a11y/useAriaPropsForRole: Existing native checkbox exposes its checked state. */}
          <input id="sProactive" type="checkbox" switch role="switch" />
        </label>
      </div>
      <div id="pushRow" hidden>
        <div class="group">
          <label class="sw">
            <span>알림 받기</span>
            {/* biome-ignore lint/a11y/useAriaPropsForRole: Existing native checkbox exposes its checked state. */}
            <input id="sPush" type="checkbox" switch role="switch" />
          </label>
        </div>
        <p id="sPushNote" class="status hint">
          알림에는 내용 없이 “Eve에게서 새 메시지가 있어요”만 표시돼요.
        </p>
      </div>
      <p id="sProNote" class="status hint">
        Eve가 브리핑이나 알림을 먼저 보낼 수 있어요. 하루 최대 3번.
      </p>
      <QuietHours />
      <div id="briefSection" hidden>
        <p class="sec">아침 브리핑</p>
        <div class="group">
          <button type="button" id="briefRun" class="row-link">
            <span>지금 미리보기</span>
          </button>
        </div>
        <div id="briefOut" role="status" aria-live="polite"></div>
      </div>{' '}
    </>
  );
}
