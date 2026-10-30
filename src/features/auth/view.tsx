type Actions = { input: () => void; submit: (event: Event) => void; retry: () => void };
export function AuthNotice({ input, submit, retry }: Actions) {
  return (
    <div
      id="authNotice"
      class="auth-notice"
      hidden
      role="alertdialog"
      aria-labelledby="authTitle"
      aria-describedby="authBody"
    >
      <div class="auth-card">
        <svg class="i auth-icon" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 3l7 3v5c0 4.5-3 8.3-7 10-4-1.7-7-5.5-7-10V6z" />
          <path d="M12 8v5M12 16h.01" />
        </svg>
        <h3 id="authTitle">서버에 연결할 수 없어요</h3>
        <p id="authBody">이 기기에서 Tailscale을 켜고 로그인하면 연결돼요.</p>
        <form id="pairForm" class="pair-form" hidden noValidate onSubmit={submit}>
          <label for="pairCode" class="sr-only">
            연결 코드
          </label>
          <input
            id="pairCode"
            name="eve-pair-code"
            class="pair-code"
            inputMode="text"
            autoComplete="one-time-code"
            autoCapitalize="characters"
            autoCorrect="off"
            spellcheck={false}
            maxLength={9}
            placeholder="XXXX-XXXX"
            aria-describedby="pairErr"
            onInput={input}
          />
          <p id="pairHint" class="pair-hint">
            코드는 10분 동안 한 번만 쓸 수 있어요
          </p>
          <p id="pairErr" class="pair-err" role="alert" hidden />
          <button type="submit" id="pairSubmit" class="btn primary" disabled>
            연결
          </button>
        </form>
        <button type="button" id="authRetry" class="btn primary" onClick={retry}>
          다시 시도
        </button>
      </div>
    </div>
  );
}
