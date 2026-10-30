import type { ImportFailure } from '../../api/import.js';
export type MigrationView = {
  sub: string;
  stats: string;
  progress: string;
  done: string;
  partial: string;
  fail: ImportFailure[];
};
type Actions = { go: () => void; later: () => void; skip: () => void; close: () => void; retry: () => void };
function Ask({ state, actions }: { state: MigrationView; actions: Actions }) {
  return (
    <div class="mig v-ask">
      <svg class="i mig-icon" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M7 18a5 5 0 1 1 1-9.9A6 6 0 0 1 19.5 10 4 4 0 0 1 18 18M12 12v8M9 15l3-3 3 3" />
      </svg>
      <h3 id="migTitle">대화를 서버에 저장할까요?</h3>
      <p id="migSub" class="mig-sub">
        {state.sub}
      </p>
      <div id="migStats" class="mig-stats">
        {state.stats}
      </div>
      <button type="button" id="migGo" class="primary" onClick={actions.go}>
        서버로 옮기기
      </button>
      <button type="button" id="migLater" class="text-btn wide" onClick={actions.later}>
        나중에
      </button>
      <p class="mig-note">
        이 기기 데이터는 옮긴 뒤에도 7일 동안 보관돼요.{' '}
        <button type="button" id="migSkip" class="link-btn" onClick={actions.skip}>
          이 기기에만 보관
        </button>
      </p>
    </div>
  );
}
function Progress({ state, close }: { state: MigrationView; close: () => void }) {
  return (
    <div class="mig v-progress">
      <svg class="mig-ring" viewBox="0 0 48 48" aria-hidden="true">
        <circle cx="24" cy="24" r="22" class="trk" />
        <circle id="migRing" cx="24" cy="24" r="22" class="val" />
      </svg>
      <p id="migProgText" class="mig-sub" role="status">
        {state.progress}
      </p>
      <div class="mig-track">
        <i id="migBar" />
      </div>
      <button type="button" id="migBg" class="text-btn wide" onClick={close}>
        백그라운드에서 계속
      </button>
    </div>
  );
}
function Outcome({ state, actions }: { state: MigrationView; actions: Actions }) {
  return (
    <>
      <div class="mig v-done">
        <svg class="i mig-icon ok" viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="12" r="10" />
          <path d="M7 12l3.5 3.5L17 9" />
        </svg>
        <h3 id="migDoneText">{state.done}</h3>
        <button type="button" id="migDone" class="primary" onClick={actions.close}>
          완료
        </button>
      </div>
      <div class="mig v-partial">
        <svg class="i mig-icon warn" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 3l10 18H2zM12 10v5M12 18h.01" />
        </svg>
        <h3 id="migPartText">{state.partial}</h3>
        <ul id="migFailList" class="mig-fails">
          {state.fail.slice(0, 3).map((failure) => (
            <li key={failure.id}>
              <b>{String(failure.title ?? '')}</b>
              <small>{String(failure.reason ?? '')}</small>
            </li>
          ))}
          {state.fail.length > 3 && <li class="more">+{state.fail.length - 3}</li>}
        </ul>
        <button type="button" id="migRetry" class="primary" onClick={actions.retry}>
          실패한 항목 다시 시도
        </button>
        <button type="button" id="migLater2" class="text-btn wide" onClick={actions.close}>
          나중에
        </button>
      </div>
    </>
  );
}
export function MigrationContent({ state, actions }: { state: MigrationView; actions: Actions }) {
  return (
    <>
      <div class="grabber" />
      <Ask state={state} actions={actions} />
      <Progress state={state} close={actions.close} />
      <Outcome state={state} actions={actions} />
    </>
  );
}
