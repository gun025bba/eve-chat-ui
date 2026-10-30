export function Header() {
  return (
    <>
      <div class="grabber"></div>
      <div class="sheet-head">
        <button type="button" id="cancelSettings" class="text-btn">
          취소
        </button>
        <h2>설정</h2>
        <button type="submit" id="saveSettings" class="text-btn done">
          완료
        </button>
      </div>
      <p id="sPriv" class="priv">
        <svg class="i" aria-hidden="true">
          <use href="#i-lock"></use>
        </svg>
        로컬 · 비공개
      </p>{' '}
    </>
  );
}
export function Connection() {
  return (
    <>
      <p class="sec">연결</p>
      <div class="group">
        <label>
          Base URL
          <input
            id="sBase"
            type="url"
            placeholder="같은 서버 (권장)"
            autoCapitalize="off"
            autoCorrect="off"
            spellcheck={false}
          />
        </label>
        <label class="model-row">
          모델<select id="sModel"></select>
          <button type="button" id="loadModels" class="mini-btn">
            불러오기
          </button>
        </label>
      </div>
      <p id="sBaseWarn" class="err-text base-warn" role="note" hidden>
        이 앱과 다른 서버를 쓰고 있어요. 대화·읽음·설정·알림이 모두 그 서버로 가고, 확인 카드는 승인할 수 없어요. 비워
        두면 이 앱의 서버를 써요.
      </p>
      <p id="sStatus" class="status"></p>
      <p id="sWho" class="status who" hidden></p>{' '}
    </>
  );
}
export function ConversationOptions() {
  return (
    <>
      <p class="sec">
        대화 <span class="sec-note">· 선택 사항</span>
      </p>
      <div class="group">
        <label class="col">
          시스템 프롬프트
          <textarea
            id="sSystem"
            rows={3}
            autoComplete="off"
            data-1p-ignore={true}
            data-lpignore="true"
            data-form-type="other"
            placeholder="예: 간결하게 한국어로 답해줘"
          ></textarea>
        </label>
      </div>
      <p class="sec">생각</p>
      <div class="group">
        <label class="sw">
          <span>생각 과정 기본 펼치기</span>
          <input id="sShowThink" type="checkbox" switch />
        </label>
        <label class="sw">
          <span>
            thinking 끄기 <small>/no_think</small>
          </span>
          <input id="sNoThink" type="checkbox" switch />
        </label>
      </div>{' '}
    </>
  );
}
