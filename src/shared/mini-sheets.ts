import { SHEET_EASE } from './sheet-gestures.js';

export function createMiniSheets() {
  const scrims = new Map<HTMLElement, HTMLElement>();
  function openMini(sheet: HTMLElement, options: { onDismiss?: () => void } = {}) {
    if (!sheet.hidden) return;
    const scrim = document.createElement('div');
    scrim.className = 'sheet-scrim';
    scrim.onclick = () => {
      if (!sheet.dataset.lock) (options.onDismiss || (() => closeMini(sheet)))();
    };
    document.body.appendChild(scrim);
    scrims.set(sheet, scrim);
    sheet.hidden = false;
    requestAnimationFrame(() =>
      requestAnimationFrame(() => {
        sheet.classList.add('show');
        scrim.classList.add('show');
      }),
    );
  }
  function closeMini(sheet: HTMLElement) {
    if (sheet.hidden) return;
    const scrim = scrims.get(sheet);
    scrims.delete(sheet);
    if (document.activeElement instanceof HTMLElement && sheet.contains(document.activeElement))
      document.activeElement.blur();
    sheet.classList.remove('show');
    scrim?.classList.remove('show');
    sheet.style.transition = `transform 300ms ${SHEET_EASE}`;
    sheet.style.transform = 'translateY(110%)';
    setTimeout(() => {
      sheet.hidden = true;
      sheet.style.transition = sheet.style.transform = '';
      scrim?.remove();
    }, 300);
  }
  return { openMini, closeMini };
}
