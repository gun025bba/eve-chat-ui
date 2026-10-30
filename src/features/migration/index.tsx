import { render } from 'preact';
import { createImportBody, type ImportFailure, importOutcome, type LocalConversation } from '../../api/import.js';
import type { createThreadsAPI } from '../../api/threads.js';
import type { createMiniSheets } from '../../shared/mini-sheets.js';
import { MigrationContent, type MigrationView } from './view.js';

const KEYS = { migrated: 'llmchat.migrated', snooze: 'llmchat.migrateSnooze', backup: 'llmchat.convs.bak' };
type Progress = { done: number; total: number };
type Host = {
  localKey: string;
  load: <T>(key: string, fallback: T) => T;
  save: (key: string, value: unknown) => void;
  api: ReturnType<typeof createThreadsAPI>;
  model: () => string;
  isServer: () => boolean;
  isNet: (error: unknown) => boolean;
  route: () => string;
  wide: () => boolean;
  busy: () => boolean;
  app: HTMLElement;
  renderSync: () => void;
  initServer: () => unknown;
  showToast: (text: string, action: string, callback: () => void, ms: number) => void;
};
class Migration {
  private host!: Host;
  private asked = false;
  private failed: string[] = [];
  private currentProgress: Progress | null = null;
  private state: MigrationView = { sub: '', stats: '', progress: '', done: '', partial: '', fail: [] };
  constructor(
    private sheet: HTMLElement,
    private sheets: ReturnType<typeof createMiniSheets>,
  ) {
    this.draw();
  }
  get progress() {
    return this.currentProgress;
  }
  private draw() {
    render(
      <MigrationContent
        state={this.state}
        actions={{
          go: () => this.runMigration(),
          later: this.snooze,
          skip: () => {
            localStorage.setItem(KEYS.migrated, 'skip');
            this.close();
          },
          close: this.close,
          retry: () => this.runMigration(this.failed),
        }}
      />,
      this.sheet,
    );
  }
  init(host: Host) {
    this.host = host;
    const backup = host.load<{ at: number } | null>(KEYS.backup, null);
    if (backup && Date.now() - backup.at > 7 * 864e5) localStorage.removeItem(KEYS.backup);
  }
  private local() {
    return this.host.load<LocalConversation[]>(this.host.localKey, []).filter((c) => c.messages?.length);
  }
  canOffer() {
    const done = localStorage.getItem(KEYS.migrated);
    return this.host.isServer() && this.local().length > 0 && (!done || done === 'skip');
  }
  private eligible() {
    if (!this.host.isServer() || localStorage.getItem(KEYS.migrated)) return false;
    const snooze = this.host.load(KEYS.snooze, { until: 0, n: 0 });
    if (snooze.n >= 3 || Date.now() < snooze.until) return false;
    return this.local().length > 0;
  }
  maybeMigrate = () => {
    if (this.asked || !this.eligible()) return;
    const show = () => {
      if (this.asked || (this.host.route() !== 'list' && !this.host.wide()) || this.host.busy()) return;
      this.asked = true;
      setTimeout(() => this.open(), 1000);
    };
    if (this.host.route() === 'list' || this.host.wide()) show();
    else {
      const observer = new MutationObserver(() => {
        if (this.host.route() === 'list') {
          observer.disconnect();
          show();
        }
      });
      observer.observe(this.host.app, { attributes: true, attributeFilter: ['data-route'] });
    }
  };
  restart() {
    localStorage.removeItem(KEYS.migrated);
    this.host.save(KEYS.snooze, { until: 0, n: 0 });
    this.open();
  }
  private open() {
    const local = this.local(),
      messages = local.reduce((sum, c) => sum + c.messages.length, 0);
    const kb = new Blob([localStorage.getItem(this.host.localKey) || '']).size / 1024;
    this.sheet.dataset.view = 'ask';
    this.state.sub = `이 기기에 있는 대화 ${local.length}개를 서버로 옮기면 다른 기기에서도 이어서 볼 수 있어요.`;
    const size = kb >= 1024 ? `${(kb / 1024).toFixed(1)}MB` : `${Math.max(1, Math.round(kb))}KB`;
    this.state.stats = `대화 ${local.length}개 · 메시지 ${messages}개 · 약 ${size}`;
    this.draw();
    this.sheets.openMini(this.sheet, { onDismiss: this.snooze });
  }
  private close = () => this.sheets.closeMini(this.sheet);
  private snooze = () => {
    const snooze = this.host.load(KEYS.snooze, { until: 0, n: 0 });
    this.host.save(KEYS.snooze, { until: Date.now() + 3 * 864e5, n: snooze.n + 1 });
    this.close();
  };
  private progressView(done: number, total: number) {
    const ratio = done / Math.max(1, total);
    this.sheet.dataset.view = 'progress';
    this.state.progress = `${total}개 중 ${done}개 저장 중…`;
    this.draw();
    const ring = this.sheet.querySelector<SVGElement>('#migRing'),
      bar = this.sheet.querySelector<HTMLElement>('#migBar');
    if (ring) ring.style.strokeDashoffset = String(138 * (1 - ratio));
    if (bar) bar.style.width = `${ratio * 100}%`;
  }
  private outcomeView(ok: number, fail: ImportFailure[]) {
    this.sheet.dataset.view = fail.length ? 'partial' : 'done';
    if (fail.length) {
      this.state.partial = ok ? `${ok}개를 옮겼어요. ${fail.length}개는 실패했어요` : '지금은 옮길 수 없어요';
      this.state.fail = fail;
    } else this.state.done = `대화 ${ok}개를 옮겼어요`;
    this.draw();
  }
  private async send(items: LocalConversation[], ok: Set<string>, fail: ImportFailure[]): Promise<void> {
    const body = createImportBody(items, this.host.model);
    if (new Blob([body]).size > 4.5e6 && items.length > 1) {
      const half = Math.ceil(items.length / 2);
      await this.send(items.slice(0, half), ok, fail);
      return this.send(items.slice(half), ok, fail);
    }
    try {
      const result = importOutcome(await this.host.api.importThreads(body), items);
      for (const id of result.ok) ok.add(id);
      fail.push(...result.fail);
    } catch (error) {
      const e = error as { http?: number; message?: string };
      if ((e.http === 400 || e.http === 413) && items.length > 1) {
        const half = Math.ceil(items.length / 2);
        await this.send(items.slice(0, half), ok, fail);
        return this.send(items.slice(half), ok, fail);
      }
      for (const c of items) {
        fail.push({
          id: c.id,
          title: c.title,
          reason: this.host.isNet(error) ? '네트워크 연결 없음' : e.http === 413 ? '대화가 너무 커요' : e.message,
        });
      }
    }
  }
  private async runMigration(only?: string[]) {
    this.sheet.dataset.lock = '1';
    const all = this.local(),
      todo = only ? all.filter((c) => only.includes(c.id)) : all;
    this.currentProgress = { done: 0, total: todo.length };
    this.progressView(0, todo.length);
    this.host.renderSync();
    const ok = new Set<string>(),
      fail: ImportFailure[] = [];
    for (let i = 0; i < todo.length; i += 5) {
      const batch = todo.slice(i, i + 5);
      await this.send(batch, ok, fail);
      this.currentProgress.done = Math.min(todo.length, i + batch.length);
      this.progressView(this.currentProgress.done, todo.length);
      this.host.renderSync();
    }
    this.currentProgress = null;
    delete this.sheet.dataset.lock;
    this.host.renderSync();
    const previous = all.length - todo.length;
    this.failed = fail.map((f) => f.id);
    if (!fail.length) {
      localStorage.setItem(KEYS.migrated, String(Date.now()));
      this.host.save(KEYS.backup, { at: Date.now(), data: this.host.load(this.host.localKey, []) });
      localStorage.removeItem(this.host.localKey);
      this.outcomeView(ok.size + previous, []);
      this.host.initServer();
    } else this.outcomeView(ok.size + previous, fail);
    if (this.sheet.hidden && fail.length)
      this.host.showToast(
        `${fail.length}개 대화를 옮기지 못했어요`,
        '다시 시도',
        () => {
          this.sheets.openMini(this.sheet);
          this.runMigration(this.failed);
        },
        5000,
      );
  }
}
export function mountMigration(sheet: HTMLElement, sheets: ReturnType<typeof createMiniSheets>) {
  return new Migration(sheet, sheets);
}
