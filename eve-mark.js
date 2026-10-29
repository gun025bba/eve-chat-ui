/* Eve mark (icon F, ICON-SPEC §3): the 24x16 avatar that replaces the dot on Eve events, and the empty-Today hero. Decorative only; colours come from CSS variables (eve-mark.css).
   The large marks (empty state, settings, connection notice) are static inline SVG in index.html. */
(() => {
  const MARK_S = '<svg class="eve-mark" viewBox="0 0 24 16" width="24" height="16" aria-hidden="true" focusable="false"><path class="b" d="M.69 16A12 12 0 1 1 23.31 16Z"/><g class="eyes"><circle class="e" cx="8.1" cy="6.6" r="2.1"/><circle class="e" cx="15.9" cy="6.6" r="2.1"/></g></svg>';

  /* the avatar element for an Eve event (chat message or Today 선톡/브리핑 row) */
  function avatar() { const av = document.createElement('span'); av.className = 'av'; av.setAttribute('aria-hidden', 'true'); av.innerHTML = MARK_S; return av; }

  /* empty Today (§3.4): show the hero only while the timeline holds just "지금"; `enter` plays its one-time rise + blink */
  function syncHero(free, scroller, isEmpty, enter) {
    if (!free) return;
    const hero = free.firstElementChild;
    free.hidden = !isEmpty; if (scroller) scroller.classList.toggle('is-empty', isEmpty);
    if (!isEmpty) hero?.classList.remove('enter'); else if (enter) hero?.classList.add('enter');
  }

  self.EveMark = { avatar, syncHero };
})();
