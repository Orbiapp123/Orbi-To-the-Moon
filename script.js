/* ============================================
   ORBI: TO THE MOON — Shared JavaScript
   Stars animation + UI helpers
   ============================================ */

// ── Starfield Canvas ──────────────────────────
(function initStars() {
  const canvas = document.getElementById('stars-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  let W, H, stars = [], nebulae = [];

  // Star colour palette: purple · pink · teal · white
  const PALETTES = [
    [180, 155, 255],  // purple (×3 weight)
    [200, 175, 255],
    [165, 140, 255],
    [255, 110, 190],  // pink  (×2 weight)
    [240,  90, 170],
    [72,  230, 210],  // teal  (×2 weight)
    [100, 215, 235],
    [230, 225, 255],  // near-white (×1)
  ];

  function pickColor() {
    const r = Math.random();
    if (r < 0.42) return PALETTES[Math.floor(Math.random() * 3)];       // purple
    if (r < 0.67) return PALETTES[3 + Math.floor(Math.random() * 2)];   // pink
    if (r < 0.90) return PALETTES[5 + Math.floor(Math.random() * 2)];   // teal
    return PALETTES[7];                                                    // white
  }

  function resize() {
    W = canvas.width  = window.innerWidth;
    H = canvas.height = document.documentElement.scrollHeight;
  }

  function createStars(count = 240) {
    stars = [];
    for (let i = 0; i < count; i++) {
      stars.push({
        x: Math.random() * W,
        y: Math.random() * H,
        r: Math.random() * 1.6 + 0.2,
        alpha: Math.random() * 0.8 + 0.2,
        twinkleSpeed: Math.random() * 0.02 + 0.005,
        twinkleDir: Math.random() > 0.5 ? 1 : -1,
        color: pickColor(),
      });
    }
  }

  // Nebula flares: large soft radial blobs that slowly pulse
  function createNebulae() {
    const rBase = Math.max(W * 0.38, 300);
    nebulae = [
      { cx: W * 0.80, cy: H * 0.06, r: rBase * 1.1, rgb: [236, 72, 180],  peak: 0.055, phase: 0,            speed: 0.0022 }, // pink — top right
      { cx: W * 0.12, cy: H * 0.28, r: rBase * 0.95, rgb: [20, 200, 180], peak: 0.048, phase: Math.PI * 0.6, speed: 0.0031 }, // teal — mid left
      { cx: W * 0.62, cy: H * 0.55, r: rBase * 1.0,  rgb: [200, 60, 160],  peak: 0.040, phase: Math.PI * 1.2, speed: 0.0018 }, // pink — centre
      { cx: W * 0.20, cy: H * 0.78, r: rBase * 0.90, rgb: [30, 210, 200],  peak: 0.042, phase: Math.PI * 1.8, speed: 0.0027 }, // teal — bottom left
    ];
  }

  function drawNebulae() {
    nebulae.forEach(n => {
      n.phase += n.speed;
      const pulse = (Math.sin(n.phase) + 1) * 0.5;          // 0 → 1
      const a     = n.peak * (0.35 + pulse * 0.65);
      const [r, g, b] = n.rgb;

      const grad = ctx.createRadialGradient(n.cx, n.cy, 0, n.cx, n.cy, n.r);
      grad.addColorStop(0,   `rgba(${r},${g},${b},${a})`);
      grad.addColorStop(0.45,`rgba(${r},${g},${b},${(a * 0.35).toFixed(3)})`);
      grad.addColorStop(1,   `rgba(${r},${g},${b},0)`);

      ctx.beginPath();
      ctx.arc(n.cx, n.cy, n.r, 0, Math.PI * 2);
      ctx.fillStyle = grad;
      ctx.fill();
    });
  }

  function draw() {
    ctx.clearRect(0, 0, W, H);

    drawNebulae();

    stars.forEach(s => {
      s.alpha += s.twinkleSpeed * s.twinkleDir;
      if (s.alpha > 1 || s.alpha < 0.1) s.twinkleDir *= -1;

      const [r, g, b] = s.color;
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${r},${g},${b},${s.alpha})`;
      ctx.fill();
    });

    requestAnimationFrame(draw);
  }

  resize();
  createStars();
  createNebulae();
  draw();

  window.addEventListener('resize', () => { resize(); createStars(); createNebulae(); });
})();

// ── Navbar scroll effect ───────────────────────
(function navbarScroll() {
  const nav = document.querySelector('.navbar');
  if (!nav) return;
  window.addEventListener('scroll', () => {
    nav.style.background = window.scrollY > 40
      ? 'rgba(4, 4, 26, 0.97)'
      : 'rgba(4, 4, 26, 0.85)';
  });
})();

// ── Active nav link ────────────────────────────
(function setActiveNav() {
  const current = location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.nav-links a').forEach(a => {
    const href = a.getAttribute('href');
    if (href === current || (current === '' && href === 'index.html')) {
      a.classList.add('active');
    }
  });
})();

// ── Intersection Observer (fade-in on scroll) ──
(function fadeOnScroll() {
  const items = document.querySelectorAll('.fade-in');
  if (!items.length) return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });

  items.forEach(el => observer.observe(el));
})();

// ── Counter animation ──────────────────────────
function animateCounter(el, target, suffix = '') {
  const duration = 1800;
  const start = performance.now();
  const update = (now) => {
    const t = Math.min((now - start) / duration, 1);
    const ease = 1 - Math.pow(1 - t, 3);
    el.textContent = Math.round(ease * target).toLocaleString() + suffix;
    if (t < 1) requestAnimationFrame(update);
  };
  requestAnimationFrame(update);
}

(function initCounters() {
  const counters = document.querySelectorAll('[data-count]');
  if (!counters.length) return;
  const obs = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        const el = e.target;
        animateCounter(el, +el.dataset.count, el.dataset.suffix || '');
        obs.unobserve(el);
      }
    });
  }, { threshold: 0.5 });
  counters.forEach(el => obs.observe(el));
})();
