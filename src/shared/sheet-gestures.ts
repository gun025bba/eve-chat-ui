export const SHEET_EASE = 'cubic-bezier(.32,.72,0,1)';
type Drag = {
  y0: number;
  yl: number;
  tl: number;
  v: number;
  dy: number;
  h: number;
  lock: 'y' | 'n' | null;
  x0: number;
  head: boolean;
};
function start(sheet: HTMLElement, scroll: HTMLElement | null, event: TouchEvent): Drag | null {
  const touch = event.touches[0],
    target = event.target as Element;
  const onHead = touch.clientY - sheet.getBoundingClientRect().top < 56 || target.closest('.grabber,.sheet-head');
  if (!onHead && (scroll ? scroll.scrollTop > 0 : true)) return null;
  if (target.closest('input,textarea,select') && !onHead) return null;
  return {
    y0: touch.clientY,
    yl: touch.clientY,
    tl: performance.now(),
    v: 0,
    dy: 0,
    h: sheet.offsetHeight,
    lock: null,
    x0: touch.clientX,
    head: !!onHead,
  };
}
function move(sheet: HTMLElement, state: Drag, event: TouchEvent) {
  const touch = event.touches[0],
    dy = touch.clientY - state.y0;
  if (!state.lock) {
    if (Math.hypot(dy, touch.clientX - state.x0) < 6) return;
    state.lock = Math.abs(dy) > Math.abs(touch.clientX - state.x0) && (dy > 0 || state.head) ? 'y' : 'n';
    if (state.lock === 'y') sheet.style.transition = 'none';
  }
  if (state.lock !== 'y') return;
  event.preventDefault();
  const now = performance.now();
  state.v = (touch.clientY - state.yl) / Math.max(1, now - state.tl);
  state.yl = touch.clientY;
  state.tl = now;
  state.dy = dy;
  sheet.style.transform = `translateY(${dy < 0 ? dy * 0.2 : dy}px)`;
  document.body.style.setProperty('--sheet-p', String(1 - Math.max(0, dy) / state.h));
}
function finish(sheet: HTMLElement, state: Drag, close: (dragged: true) => void) {
  if (state.lock !== 'y') return;
  const velocity = performance.now() - state.tl > 100 ? 0 : state.v;
  document.body.style.removeProperty('--sheet-p');
  if (state.dy > state.h * 0.3 || velocity > 0.6) close(true);
  else {
    sheet.style.transition = 'transform 300ms cubic-bezier(.34,1.36,.64,1)';
    sheet.style.transform = '';
  }
}
export function sheetDrag(sheet: HTMLElement, scroll: HTMLElement | null, close: (dragged: true) => void) {
  let state: Drag | null = null;
  sheet.addEventListener(
    'touchstart',
    (event) => {
      const next = start(sheet, scroll, event);
      if (next) state = next;
    },
    { passive: true },
  );
  sheet.addEventListener(
    'touchmove',
    (event) => {
      if (state) move(sheet, state, event);
    },
    { passive: false },
  );
  const end = () => {
    const previous = state;
    state = null;
    if (previous) finish(sheet, previous, close);
  };
  sheet.addEventListener('touchend', end);
  sheet.addEventListener('touchcancel', end);
}
export function animateOut(sheet: HTMLElement, done: () => void) {
  sheet.style.transition = `transform 300ms ${SHEET_EASE}`;
  sheet.style.transform = 'translateY(100%)';
  sheet.classList.add('closing');
  setTimeout(() => {
    sheet.classList.remove('closing');
    sheet.style.transition = sheet.style.transform = '';
    done();
  }, 300);
}
