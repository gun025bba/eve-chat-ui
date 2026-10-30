import { render } from 'preact';
import { authCode, isAuthFail } from '../../api/client.js';
import type { createGatewayRequests } from '../../api/gateway.js';
import { fmtCode, LOCK_MS, MAXF, normCode, notice, PAIRED, PLOCK } from './model.js';
import { AuthNotice } from './view.js';

type Retry = (() => void) | null | undefined;
type Identity = { user?: unknown; login?: unknown; authenticated?: unknown } | null;
type Host = {
  gateway: ReturnType<typeof createGatewayRequests>;
  load: <T>(key: string, fallback: T) => T;
  save: (key: string, value: unknown) => void;
  clearCards: () => unknown;
  clearErrors: () => void;
  renderWho: () => void;
  buzz: (value: number) => void;
};
class Auth {
  private host!: Host;
  private identity: Identity = null;
  private authRetry: Retry = null;
  private lockTimer = 0;
  private element: HTMLElement;
  private card: HTMLElement;
  private form: HTMLFormElement;
  private input: HTMLInputElement;
  private error: HTMLElement;
  private button: HTMLButtonElement;
  private retryButton: HTMLButtonElement;
  private title: HTMLElement;
  private body: HTMLElement;
  constructor(root: Element) {
    render(<AuthNotice input={this.changeCode} submit={this.submit} retry={this.retry} />, root);
    const get = <T extends Element>(selector: string) => {
      const element = root.querySelector<T>(selector);
      if (!element) throw new Error('Missing auth element');
      return element;
    };
    this.element = get<HTMLElement>('#authNotice');
    this.card = get<HTMLElement>('.auth-card');
    this.form = get<HTMLFormElement>('#pairForm');
    this.input = get<HTMLInputElement>('#pairCode');
    this.error = get<HTMLElement>('#pairErr');
    this.button = get<HTMLButtonElement>('#pairSubmit');
    this.retryButton = get<HTMLButtonElement>('#authRetry');
    this.title = get<HTMLElement>('#authTitle');
    this.body = get<HTMLElement>('#authBody');
  }
  init(host: Host) {
    this.host = host;
  }
  user = () => this.identity && (this.identity.user || this.identity.login);
  private lockState() {
    const lock = this.host.load<{ fails?: number; until?: number } | null>(PLOCK, null) || {};
    return { fails: Number(lock.fails) | 0, until: Number(lock.until) || 0 };
  }
  private renderLock = () => {
    const { fails, until } = this.lockState(),
      left = until - Date.now();
    clearTimeout(this.lockTimer);
    if (left > 0) {
      const minutes = Math.ceil(left / 60e3);
      this.input.disabled = true;
      this.button.disabled = true;
      this.card.dataset.pair = 'locked';
      this.error.textContent = `시도가 너무 많아 잠겼어요. ${minutes}분 뒤에 새 코드를 받아 입력해 주세요.`;
      this.error.hidden = false;
      this.lockTimer = window.setTimeout(this.renderLock, Math.min(left, 30e3));
      return true;
    }
    if (until) {
      this.host.save(PLOCK, { fails: 0, until: 0 });
      this.error.hidden = true;
    }
    this.input.disabled = false;
    this.button.disabled = normCode(this.input.value).length !== 8;
    this.card.dataset.pair = fails ? 'failed' : 'entry';
    return false;
  };
  showAuthNotice = (retry?: Retry, code?: string) => {
    const { pair, title, body } = notice(code, localStorage.getItem(PAIRED) === '1');
    this.title.textContent = title;
    this.body.textContent = body;
    this.card.classList.toggle('pairing', pair);
    this.card.dataset.pair = pair ? 'entry' : '';
    this.form.hidden = !pair;
    this.retryButton.textContent = pair ? '이미 연결했어요' : '다시 시도';
    if (retry) this.authRetry = retry;
    if (!this.element.hidden) {
      if (pair) this.renderLock();
      return;
    }
    this.input.value = '';
    this.error.hidden = true;
    this.input.removeAttribute('aria-invalid');
    if (pair) this.renderLock();
    this.element.hidden = false;
    requestAnimationFrame(() => {
      this.element.classList.add('in');
      if (pair && !this.input.disabled && !matchMedia('(pointer:coarse)').matches) this.input.focus();
    });
  };
  private changeCode = () => {
    const code = normCode(this.input.value);
    this.input.value = fmtCode(code);
    this.button.disabled = code.length !== 8;
    if (!this.lockState().fails) this.error.hidden = true;
    this.input.removeAttribute('aria-invalid');
  };
  private submit = async (event: Event) => {
    event.preventDefault();
    const code = normCode(this.input.value);
    if (code.length !== 8 || this.renderLock()) return;
    this.button.disabled = true;
    this.button.textContent = '연결 중…';
    let response: Response;
    try {
      response = await this.host.gateway.pair(fmtCode(code));
    } catch {
      this.error.textContent = '서버에 연결할 수 없어요. 연결 상태를 확인해 주세요.';
      this.error.hidden = false;
      this.button.textContent = '연결';
      this.button.disabled = false;
      return;
    }
    this.button.textContent = '연결';
    if (!response.ok) {
      if (response.status !== 401) {
        this.error.textContent = '지금은 연결할 수 없어요. 잠시 뒤 다시 시도해 주세요.';
        this.error.hidden = false;
        this.button.disabled = false;
        return;
      }
      const fails = this.lockState().fails + 1;
      this.host.save(PLOCK, fails >= MAXF ? { fails: 0, until: Date.now() + LOCK_MS } : { fails, until: 0 });
      this.input.setAttribute('aria-invalid', 'true');
      this.host.buzz(20);
      if (this.renderLock()) return;
      this.error.textContent = `코드가 맞지 않거나, 이미 썼거나, 10분이 지났어요. 남은 시도 ${MAXF - fails}번`;
      this.error.hidden = false;
      this.button.disabled = false;
      return;
    }
    this.host.save(PLOCK, { fails: 0, until: 0 });
    localStorage.setItem(PAIRED, '1');
    if (await this.checkAuth()) {
      const fn = this.authRetry;
      this.authRetry = null;
      this.host.clearErrors();
      fn?.();
    }
  };
  private hide() {
    this.element.classList.remove('in');
    this.element.hidden = true;
  }
  checkAuth = async () => {
    try {
      const response = await this.host.gateway.identity();
      const value = await response.json().catch(() => null);
      if (isAuthFail(response.status, authCode(value)) || (response.ok && value && value.authenticated === false)) {
        this.identity = null;
        this.host.renderWho();
        this.host.clearCards();
        this.showAuthNotice(null, authCode(value));
        return false;
      }
      if (response.ok) {
        this.identity = value;
        this.host.renderWho();
        localStorage.setItem(PAIRED, '1');
      }
      this.hide();
      return true;
    } catch {
      return true;
    }
  };
  private retry = async () => {
    this.retryButton.disabled = true;
    this.retryButton.textContent = '확인 중…';
    const ok = await this.checkAuth();
    this.retryButton.disabled = false;
    this.retryButton.textContent = '다시 시도';
    if (ok && this.authRetry) {
      const fn = this.authRetry;
      this.authRetry = null;
      this.host.clearErrors();
      fn();
    }
  };
}
export function mountAuth(root: Element) {
  return new Auth(root);
}
