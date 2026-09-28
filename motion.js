'use strict';
(() => {
  const toggle = document.getElementById('motionToggle');
  const label = document.getElementById('motionLabel');
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let pausedByUser = false;
  try { pausedByUser = localStorage.getItem('rs-motion-paused') === 'true'; } catch (_) { /* Motion still works without storage. */ }

  // Duplicate only the visual ribbon; screen readers encounter its content once.
  const track = document.querySelector('.focus-track');
  const group = track?.querySelector('.focus-group');
  if (group) {
    const copy = group.cloneNode(true);
    copy.setAttribute('aria-hidden', 'true');
    track.append(copy);
    track.classList.add('is-looping');
  }

  function updatePreference() {
    const paused = pausedByUser || reducedMotion.matches;
    document.body.classList.toggle('motion-paused', paused);
    if (toggle) {
      toggle.hidden = false;
      toggle.disabled = reducedMotion.matches;
      toggle.setAttribute('aria-pressed', String(paused));
      toggle.setAttribute('aria-label', reducedMotion.matches ? 'Animation off: reduced motion preference' : paused ? 'Play background animation' : 'Pause background animation');
      toggle.title = reducedMotion.matches ? 'Your device is set to reduced motion' : paused ? 'Play background animation' : 'Pause background animation';
      if (label) label.textContent = paused ? 'Motion off' : 'Motion on';
    }
  }
  toggle?.addEventListener('click', () => {
    pausedByUser = !pausedByUser;
    try { localStorage.setItem('rs-motion-paused', String(pausedByUser)); } catch (_) { /* Preference is optional. */ }
    updatePreference();
  });
  reducedMotion.addEventListener('change', updatePreference);

  // CSS handles motion; there is no perpetual canvas or JavaScript render loop.
  // Let scrolling use the rendering budget, then resume after the gesture ends.
  let scrollTimer = 0;
  window.addEventListener('scroll', () => {
    if (!scrollTimer) document.body.classList.add('is-scrolling');
    clearTimeout(scrollTimer);
    scrollTimer = setTimeout(() => {
      document.body.classList.remove('is-scrolling');
      scrollTimer = 0;
    }, 200);
  }, {passive: true});

  function updateVisibility() {
    document.body.classList.toggle('page-hidden', document.hidden);
  }
  document.addEventListener('visibilitychange', updateVisibility);

  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) {
        entry.target.classList.toggle('motion-offscreen', !entry.isIntersecting);
        if (entry.target.id === 'hero') {
          document.body.classList.toggle('hero-offscreen', !entry.isIntersecting);
        }
      }
    }, {rootMargin: '80px 0px'});
    document.querySelectorAll('.hero, .focus-strip, .project-visual').forEach(element => {
      element.classList.add('motion-offscreen');
      observer.observe(element);
    });
  }
  updateVisibility();
  updatePreference();
})();
