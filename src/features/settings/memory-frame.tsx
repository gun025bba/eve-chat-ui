function MemoryEditor() {
  return (
    <>
      {/* biome-ignore lint/a11y/useSemanticElements: Preserve the existing group layout and role. */}
      <div id="memForm" class="mem-form" role="group" aria-label="메모리 편집" hidden>
        <select id="memKind" aria-label="종류">
          <option value="preference">선호</option>
          <option value="profile">프로필</option>
          <option value="fact">사실</option>
          <option value="task">할 일</option>
        </select>
        <textarea
          id="memText"
          class="sheet-input"
          rows={2}
          maxLength={300}
          aria-label="메모리 내용"
          aria-describedby="memFormErr"
        ></textarea>
        <p id="memFormErr" class="status hint warn" role="alert" hidden></p>
        <div class="mem-form-btns">
          <button type="button" id="memFormCancel" class="btn">
            취소
          </button>
          <button type="button" id="memFormSave" class="btn primary">
            저장
          </button>
        </div>
      </div>{' '}
    </>
  );
}
function MemoryContents() {
  return (
    <>
      <div id="memoryView" hidden>
        <div id="memBanner" class="mem-banner" role="status" hidden>
          <p class="mem-banner-t">지금은 메모리를 바꿀 수 없어요</p>
          <p class="mem-banner-s">저장된 메모리는 그대로 있고, 곧 다시 쓸 수 있어요</p>
        </div>
        <div class="mem-tools">
          <button type="button" id="memAdd" class="mem-add" aria-label="메모리 추가">
            +
          </button>
        </div>
        <MemoryEditor />
        <p id="memState" class="status hint" role="status" hidden></p>
        <button type="button" id="memRetry" class="btn" hidden>
          다시 시도
        </button>
        <ul id="memList" class="mem-list group" aria-label="저장된 메모리"></ul>
        <p id="memTotal" class="mem-total status hint" hidden></p>
        <div class="group mem-group" id="memExportGroup" hidden>
          <button type="button" id="memExport" class="row-link mem-row-btn accent">
            메모리 내보내기
          </button>
        </div>
        <div class="group mem-group">
          <button type="button" id="memWipe" class="row-link mem-row-btn danger-text">
            모든 메모리 지우기
          </button>
        </div>
        <div id="memToast" class="mem-toast" role="status" aria-live="polite" hidden>
          <span id="memToastText"></span>
          <button type="button" id="memToastAct" class="btn"></button>
        </div>
        <div id="memWipeSheet" class="mem-sheet" role="alertdialog" aria-labelledby="memWipeQ" hidden>
          <p id="memWipeQ">모든 메모리를 지울까요? 백업 사본도 복구할 수 없게 돼요.</p>
          <button type="button" id="memWipeYes" class="btn danger">
            모두 지우기
          </button>
          <button type="button" id="memWipeNo" class="btn">
            취소
          </button>
        </div>
      </div>{' '}
    </>
  );
}
export function MemorySettings() {
  return (
    <>
      <div id="memSection" hidden>
        <p class="sec">메모리</p>
        <div class="group">
          <label class="sw">
            <span>메모리 사용</span>
            {/* biome-ignore lint/a11y/useAriaPropsForRole: Existing native checkbox exposes its checked state. */}
            <input id="sMemory" type="checkbox" switch role="switch" aria-describedby="sMemNote" />
          </label>
          <button type="button" id="memOpen" class="row-link" aria-expanded="false" aria-controls="memoryView">
            <span>저장된 메모리</span>
            <span id="memCount" class="row-value"></span>
          </button>
        </div>
        <p id="sMemNote" class="status hint"></p>
        <MemoryContents />
      </div>{' '}
    </>
  );
}
