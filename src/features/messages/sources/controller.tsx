import { render } from 'preact';
import { animateOut } from '../../../shared/sheet-gestures.js';

const reduceMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
function SheetContents({ count }: { count: number }) {
  return (
    <>
      <div class="grabber" aria-hidden="true" />
      <div class="src-sheet-head">
        <h3 id="srcSheetTitle">{`출처 ${count}개`}</h3>
        <button type="button" class="text-btn src-close">
          닫기
        </button>
      </div>
      <div class="src-sheet-body" />
    </>
  );
}
class SourceSheet {
  private close(dialog: HTMLDialogElement) {
    if (dialog.open && !dialog.classList.contains('closing')) animateOut(dialog, () => dialog.close());
  }
  private ensure() {
    const previous = document.getElementById('srcSheet') as HTMLDialogElement | null;
    if (previous) return previous;
    const dialog = document.createElement('dialog');
    dialog.id = 'srcSheet';
    dialog.className = 'src-sheet';
    dialog.setAttribute('aria-labelledby', 'srcSheetTitle');
    document.body.appendChild(dialog);
    dialog.addEventListener('click', (event) => {
      if (event.target === dialog || (event.target instanceof Element && event.target.closest('.src-close')))
        this.close(dialog);
    });
    dialog.addEventListener('cancel', (event) => {
      event.preventDefault();
      this.close(dialog);
    });
    dialog.addEventListener('close', () => document.body.classList.remove('sheet-open'));
    return dialog;
  }
  open(section: HTMLElement) {
    const template = section.querySelector<HTMLTemplateElement>('.src-all-tpl');
    if (!template) return;
    const count = template.content.querySelectorAll('.src-item').length;
    const dialog = this.ensure();
    render(null, dialog);
    dialog.replaceChildren();
    render(<SheetContents count={count} />, dialog);
    dialog.querySelector('.src-sheet-body')?.appendChild(template.content.cloneNode(true));
    document.body.classList.add('sheet-open');
    dialog.showModal();
  }
}
function toggle(section: HTMLElement, open: boolean) {
  const chips = section.querySelectorAll('.sc'),
    list = section.querySelector<HTMLElement>('.src-list');
  if (!chips.length || !list) return;
  for (const chip of chips) chip.setAttribute('aria-expanded', String(open));
  section.classList.toggle('open', open);
  if (open) {
    list.hidden = false;
    list.classList.remove('in');
    void list.offsetWidth;
    list.classList.add('in');
  } else if (reduceMotion()) list.hidden = true;
  else {
    list.classList.remove('in');
    const finish = (event: TransitionEvent) => {
      if (event.target !== list || event.propertyName !== 'opacity') return;
      list.removeEventListener('transitionend', finish);
      if (!section.classList.contains('open')) list.hidden = true;
    };
    list.addEventListener('transitionend', finish);
  }
  if (open && section.closest('.msg') === [...document.querySelectorAll('#messages .msg')].pop()) {
    const scroll = () => list.scrollIntoView({ block: 'nearest', behavior: reduceMotion() ? 'auto' : 'smooth' });
    if (reduceMotion()) scroll();
    else {
      const finish = (event: TransitionEvent) => {
        if (event.target !== list || event.propertyName !== 'transform') return;
        list.removeEventListener('transitionend', finish);
        scroll();
      };
      list.addEventListener('transitionend', finish);
    }
  }
}
class SourceInteractions {
  private sheet = new SourceSheet();
  constructor() {
    document.addEventListener('click', this.click);
    document.addEventListener('error', this.favicon, true);
  }
  private click = (event: MouseEvent) => {
    if (!(event.target instanceof Element)) return;
    const chip = event.target.closest<HTMLElement>('.sources .sc');
    if (chip) {
      const section = chip.closest<HTMLElement>('.sources');
      if (section) toggle(section, chip.getAttribute('aria-expanded') !== 'true');
      return;
    }
    const all = event.target.closest('.sources .src-all');
    if (all) {
      const section = all.closest<HTMLElement>('.sources');
      if (section) this.sheet.open(section);
      return;
    }
    const citation = event.target.closest<HTMLAnchorElement>('sup.cite a[data-n]');
    if (citation) this.citation(event, citation);
  };
  private citation(event: MouseEvent, citation: HTMLAnchorElement) {
    const section = citation.closest('.bubble')?.querySelector<HTMLElement>('.sources');
    if (!section) return;
    event.preventDefault();
    const number = citation.dataset.n?.split(',')[0] || '';
    toggle(section, true);
    const selector = `.src-item[data-n="${CSS.escape(number)}"]`;
    let item = section.querySelector<HTMLElement>(`.src-list ${selector}`);
    if (!item) {
      this.sheet.open(section);
      item = document.querySelector<HTMLElement>(`#srcSheet ${selector}`);
    }
    if (!item) return;
    item.scrollIntoView({ block: 'nearest', behavior: reduceMotion() ? 'auto' : 'smooth' });
    item.classList.remove('hl');
    void item.offsetWidth;
    item.classList.add('hl');
    const highlighted = item;
    setTimeout(() => highlighted.classList.remove('hl'), 600);
  }
  private favicon = (event: Event) => {
    const image = event.target;
    if (image instanceof HTMLImageElement && image.dataset.mono && image.parentElement?.classList.contains('fav')) {
      image.parentElement.classList.add('mono');
      image.parentElement.textContent = image.dataset.mono;
    }
  };
}
export function mountSourceInteractions() {
  return new SourceInteractions();
}
