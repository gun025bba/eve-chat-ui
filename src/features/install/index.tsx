import { render } from 'preact';
import { SHEET_EASE, sheetDrag } from '../../shared/sheet-gestures.js';
import { InstallSheet, type InstallView } from './view.js';

type PromptEvent = Event & { prompt: () => void; userChoice: Promise<{ outcome: string }> };
type Host = { isStandalone: () => boolean; isIOS: boolean; busy: () => boolean; hasAssistant: () => boolean };

class Install {
  private state: InstallView = { hidden: true, shown: false, manual: false, bip: false, ipad: false };
  private host: Host | null = null;
  private bip: PromptEvent | null = null;
  private scrim: HTMLElement | null = null;
  private timer = 0;
  private visits = 0;
  private sheet: HTMLElement;
  constructor(private root: Element) {
    this.draw();
    const sheet = root.querySelector<HTMLElement>('#installSheet');
    if (!sheet) throw new Error('Missing install sheet');
    this.sheet = sheet;
    sheetDrag(sheet, null, () => this.closeA2HS(true));
  }
  private draw() {
    render(<InstallSheet state={this.state} later={() => this.closeA2HS(true)} install={this.install} />, this.root);
  }
  init(host: Host) {
    this.host = host;
    window.addEventListener('beforeinstallprompt', (event) => {
      event.preventDefault();
      this.bip = event as PromptEvent;
      this.maybeA2HS();
    });
    window.addEventListener('appinstalled', () => {
      localStorage.setItem('a2hs.installed', '1');
      this.closeA2HS();
    });
    if (host.isStandalone()) localStorage.setItem('a2hs.installed', '1');
    this.visits = (Number(localStorage.getItem('visits')) || 0) + 1;
    localStorage.setItem('visits', String(this.visits));
  }
  private eligible() {
    const host = this.host;
    if (!host || host.isStandalone() || localStorage.getItem('a2hs.installed')) return false;
    if (Date.now() - (Number(localStorage.getItem('a2hs.dismissed')) || 0) < 30 * 864e5) return false;
    if (!(host.isIOS || this.bip)) return false;
    return this.visits >= 2 || host.hasAssistant();
  }
  maybeA2HS = () => {
    clearTimeout(this.timer);
    this.timer = window.setTimeout(() => {
      if (this.eligible() && !this.host?.busy() && this.state.hidden) this.openA2HS();
    }, 1200);
  };
  openA2HS = (manual = false) => {
    this.state.bip = !!this.bip && !this.host?.isIOS;
    this.state.ipad = !!this.host?.isIOS && !/iPhone|iPod/.test(navigator.userAgent);
    this.state.hidden = false;
    this.state.manual = !!manual;
    this.draw();
    this.scrim = document.createElement('div');
    this.scrim.className = 'sheet-scrim';
    this.scrim.onclick = () => this.closeA2HS(true);
    document.body.appendChild(this.scrim);
    requestAnimationFrame(() =>
      requestAnimationFrame(() => {
        this.state.shown = true;
        this.draw();
        this.scrim?.classList.add('show');
      }),
    );
  };
  closeA2HS = (dismissed = false) => {
    if (this.state.hidden) return;
    if (dismissed && !this.state.manual) localStorage.setItem('a2hs.dismissed', String(Date.now()));
    this.state.shown = false;
    this.draw();
    this.scrim?.classList.remove('show');
    this.sheet.style.transition = `transform 300ms ${SHEET_EASE}`;
    this.sheet.style.transform = 'translateY(110%)';
    setTimeout(() => {
      this.state.hidden = true;
      this.draw();
      this.sheet.style.transition = this.sheet.style.transform = '';
      this.scrim?.remove();
      this.scrim = null;
    }, 300);
  };
  private install = async () => {
    if (!this.bip) return;
    this.bip.prompt();
    const result = await this.bip.userChoice.catch(() => null);
    this.bip = null;
    if (result?.outcome === 'accepted') localStorage.setItem('a2hs.installed', '1');
    this.closeA2HS(result?.outcome !== 'accepted');
  };
}
export function mountInstall(root: Element) {
  return new Install(root);
}
