import { render } from 'preact';
import type { createMiniSheets } from '../../shared/mini-sheets.js';
import { sheetDrag } from '../../shared/sheet-gestures.js';

type Bindings = { save: () => void; close: () => void };
function RenameSheet({ save, close }: Bindings) {
  return (
    <div id="renameSheet" class="mini-sheet small" hidden role="dialog" aria-labelledby="renameTitle">
      <div class="grabber" />
      <h3 id="renameTitle">대화 이름</h3>
      <input
        id="titleEdit"
        class="sheet-input"
        type="text"
        enterKeyHint="done"
        aria-label="대화 제목"
        autoCorrect="on"
        autoCapitalize="sentences"
        autoComplete="off"
        data-1p-ignore
        data-lpignore="true"
        data-form-type="other"
        onKeyDown={(event) => {
          if (event.key === 'Enter' && !event.isComposing) {
            event.preventDefault();
            save();
          }
          if (event.key === 'Escape') close();
        }}
      />
      <div class="sheet-btns">
        <button type="button" id="renameCancel" class="text-btn" onClick={close}>
          취소
        </button>
        <button type="button" id="renameSave" class="primary" onClick={save}>
          저장
        </button>
      </div>
    </div>
  );
}
export function mountRename(root: Element, sheets: ReturnType<typeof createMiniSheets>) {
  let conversation: { title: string } | null = null;
  let update: (title: string) => void = () => {};
  render(<RenameSheet save={() => save()} close={() => close()} />, root);
  const sheet = root.querySelector<HTMLElement>('#renameSheet');
  const input = root.querySelector<HTMLInputElement>('#titleEdit');
  if (!sheet || !input) throw new Error('Missing rename sheet');
  const close = () => sheets.closeMini(sheet);
  const save = () => {
    const value = input.value.trim();
    close();
    if (value && value !== conversation?.title) update(value);
  };
  sheetDrag(sheet, null, close);
  return {
    open(current: { title: string }, onSave: (title: string) => void) {
      conversation = current;
      update = onSave;
      input.value = current.title;
      sheets.openMini(sheet);
      setTimeout(() => {
        input.focus();
        input.select();
      }, 60);
    },
  };
}
