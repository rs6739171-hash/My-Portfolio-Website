'use strict';
(() => {
  const canvas = document.getElementById('ambientCanvas');
  const toggle = document.getElementById('motionToggle');
  const label = document.getElementById('motionLabel');
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const finePointer = window.matchMedia('(pointer: fine)');
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

  // The CSS aurora remains available if the browser cannot create a canvas.
  const context = canvas?.getContext('2d');
  let width = 0;
  let height = 0;
  let raf = 0;
  let lastFrame = 0;
  let elapsed = 0;
  let targetX = .65;
  let targetY = .4;
  let pointerX = targetX;
  let pointerY = targetY;
  const isPaused = () => pausedByUser || reducedMotion.matches;
  const particles = Array.from({length: 42}, (_, index) => ({
    x: ((index * 73 + 19) % 101) / 101,
    y: ((index * 43 + 31) % 97) / 97,
    radius: index % 5 === 0 ? 1.7 : .85,
    speed: .4 + (index % 7) * .09,
    phase: index * 1.7,
  }));

  function draw(time) {
    if (!context || !width || !height) return;
    context.clearRect(0, 0, width, height);
    const compact = width < 700;
    const strands = compact ? 10 : 18;
    const segments = compact ? 36 : 60;
    const offsetX = (pointerX - .5) * (compact ? 0 : 24);
    const offsetY = (pointerY - .5) * (compact ? 0 : 20);
    // Fine, slowly moving contour lines form an abstract data field.
    for (let strand = 0; strand < strands; strand++) {
      context.beginPath();
      for (let segment = 0; segment <= segments; segment++) {
        const u = segment / segments;
        const x = width * (.27 + u * .89) + offsetX;
        const y = height * .43 + strand * 12 + Math.sin(u * 5.6 + time * .17 + strand * .095) * height * .18
          + Math.cos(u * 3.2 - time * .11) * 24 + (u - .5) * height * .22 + offsetY;
        if (segment === 0) context.moveTo(x, y); else context.lineTo(x, y);
      }
      context.strokeStyle = `rgba(${94 + strand * 3}, ${157 + strand * 2}, 234, ${.055 + strand / strands * .05})`;
      context.lineWidth = .75;
      context.stroke();
    }
    const count = compact ? 20 : particles.length;
    for (let index = 0; index < count; index++) {
      const point = particles[index];
      const x = point.x * width + Math.sin(time * .1 * point.speed + point.phase) * 24 + offsetX * .5;
      const y = (point.y * height - time * 3 * point.speed % (height + 40) + height + 40) % (height + 40) - 20;
      const alpha = .2 + .2 * (.5 + Math.sin(time * .4 + point.phase) * .5);
      context.fillStyle = `rgba(155, 202, 247, ${alpha})`;
      context.beginPath();
      context.arc(x, y, point.radius, 0, Math.PI * 2);
      context.fill();
    }
  }

  function frame(now) {
    raf = 0;
    if (isPaused() || document.hidden) return;
    if (!lastFrame) lastFrame = now;
    const delta = now - lastFrame;
    // Decorative work is capped at 30 fps and at 2x device resolution.
    if (delta >= 1000 / 30) {
      elapsed += Math.min(delta, 100) / 1000;
      pointerX += (targetX - pointerX) * .045;
      pointerY += (targetY - pointerY) * .045;
      draw(elapsed);
      lastFrame = now;
    }
    raf = requestAnimationFrame(frame);
  }

  function start() {
    if (context && !raf && !isPaused() && !document.hidden) {
      lastFrame = 0;
      raf = requestAnimationFrame(frame);
    }
  }
  function stop() {
    cancelAnimationFrame(raf);
    raf = 0;
    lastFrame = 0;
  }
  function resize() {
    if (!context) return;
    width = window.innerWidth;
    height = window.innerHeight;
    const ratio = Math.min(window.devicePixelRatio || 1, width < 700 ? 1.5 : 2);
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    draw(elapsed);
  }
  function updatePreference() {
    const paused = isPaused();
    document.body.classList.toggle('motion-paused', paused);
    if (toggle) {
      toggle.hidden = false;
      toggle.disabled = reducedMotion.matches;
      toggle.setAttribute('aria-pressed', String(paused));
      toggle.setAttribute('aria-label', reducedMotion.matches ? 'Animation off: reduced motion preference' : paused ? 'Play background animation' : 'Pause background animation');
      toggle.title = reducedMotion.matches ? 'Your device is set to reduced motion' : paused ? 'Play background animation' : 'Pause background animation';
      label.textContent = paused ? 'Motion off' : 'Motion on';
    }
    if (paused) stop(); else start();
  }
  toggle?.addEventListener('click', () => {
    pausedByUser = !pausedByUser;
    try { localStorage.setItem('rs-motion-paused', String(pausedByUser)); } catch (_) { /* Preference is optional. */ }
    updatePreference();
  });
  reducedMotion.addEventListener('change', updatePreference);
  document.addEventListener('visibilitychange', () => {
    document.body.classList.toggle('page-hidden', document.hidden);
    if (document.hidden) stop(); else start();
  });
  window.addEventListener('resize', resize, {passive: true});
  window.addEventListener('pointermove', event => {
    if (!finePointer.matches || isPaused()) return;
    targetX = event.clientX / width;
    targetY = event.clientY / height;
  }, {passive: true});
  document.addEventListener('pointerleave', () => { targetX = .65; targetY = .4; });
  resize();
  updatePreference();
})();
