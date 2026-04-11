/* ============================================
   ORBI: TO THE MOON — Moondrop Game Engine
   Canvas-based falling minigame
   ============================================ */

// ── Canvas Setup ────────────────────────────────────────────────────
const canvas  = document.getElementById('moondrop-canvas');
const ctx     = canvas.getContext('2d');
const W       = canvas.width;
const H       = canvas.height;

// ── Game Config ─────────────────────────────────────────────────────
const CFG = {
  moonRadius:       22,
  moonSpeed:        5.5,
  baseObstacleSpeed: 2.8,
  speedIncrement:   0.0012,  // per frame
  obstacleInterval: 80,      // frames between spawns (decreases)
  starInterval:     55,
  maxLives:         3,
};

// ── State ────────────────────────────────────────────────────────────
let gameState  = 'idle'; // idle | playing | paused | dead
let score      = 0;
let strEarned  = 0;
let lives      = CFG.maxLives;
let frame      = 0;
let speed      = CFG.baseObstacleSpeed;
let spawnTimer = 0;
let starTimer  = 0;
let animId     = null;
let invincible = false;   // brief invincibility after hit
let invTimer   = 0;

// Player
const moon = {
  x: W / 2,
  y: H - 80,
  r: CFG.moonRadius,
  vx: 0,
  craters: [],   // extra craters added on hit
};

// Object pools
let obstacles = [];
let stars     = [];
let particles = [];

// Input
const keys = { left: false, right: false };

// ── Load / Save State ────────────────────────────────────────────────
function getMasterState() {
  const defaults = { str: 450, hunger: 4, maxHunger: 5, energy: 7, maxEnergy: 10, level: 4, xp: 230, xpNeeded: 500 };
  try { return Object.assign({}, defaults, JSON.parse(localStorage.getItem('orbi_state') || '{}')); }
  catch (e) { return defaults; }
}

function saveMasterState(s) {
  localStorage.setItem('orbi_state', JSON.stringify(s));
}

let masterState = getMasterState();

function syncHUD() {
  const s = masterState;
  const ep = Math.round((s.energy / s.maxEnergy) * 100);
  const hp = Math.round((s.hunger / s.maxHunger) * 100);
  const xp = Math.round((s.xp / s.xpNeeded) * 100);

  document.getElementById('hud-level').textContent        = s.level;
  document.getElementById('hud-str').textContent          = s.str.toLocaleString();
  document.getElementById('hud-energy-fill').style.width  = ep + '%';
  document.getElementById('hud-energy-text').textContent  = `${s.energy}/${s.maxEnergy}`;
  document.getElementById('hud-hunger-fill').style.width  = hp + '%';
  document.getElementById('hud-hunger-text').textContent  = `${s.hunger}/${s.maxHunger}`;
  document.getElementById('hud-xp-fill').style.width      = xp + '%';

  const hd  = document.getElementById('hunger-display');
  const hbf = document.getElementById('hunger-bar-fill');
  if (hd)  hd.textContent  = `${s.hunger} / ${s.maxHunger}`;
  if (hbf) hbf.style.width = hp + '%';
}

syncHUD();

// ── High Score ───────────────────────────────────────────────────────
function getHighScore() {
  return parseInt(localStorage.getItem('orbi_moondrop_hs') || '0', 10);
}
function setHighScore(s) {
  if (s > getHighScore()) localStorage.setItem('orbi_moondrop_hs', s);
}

document.getElementById('high-score-display').textContent = getHighScore();

// ── Toast ─────────────────────────────────────────────────────────────
function showToast(icon, msg) {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.innerHTML = `<span style="font-size:1.1rem;">${icon}</span> ${msg}`;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 3200);
}
window.showToast = showToast;

// ── Overlay helpers ──────────────────────────────────────────────────
function showOverlay(id) {
  ['overlay-start', 'overlay-gameover', 'overlay-pause'].forEach(o => {
    const el = document.getElementById(o);
    if (el) el.classList.toggle('hidden', o !== id);
  });
}

function hideAllOverlays() {
  ['overlay-start', 'overlay-gameover', 'overlay-pause'].forEach(o => {
    const el = document.getElementById(o);
    if (el) el.classList.add('hidden');
  });
}

// ── Moon craters for initial display ─────────────────────────────────
moon.craters = [
  { ox: -8,  oy: -6,  r: 5  },
  { ox:  9,  oy:  5,  r: 4  },
  { ox: -4,  oy:  10, r: 3  },
];

// ── Draw Functions ───────────────────────────────────────────────────

function drawBackground() {
  // Deep space gradient
  const grad = ctx.createLinearGradient(0, 0, 0, H);
  grad.addColorStop(0,   '#04041a');
  grad.addColorStop(0.5, '#06063a');
  grad.addColorStop(1,   '#04041a');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, W, H);
}

function drawMoon() {
  const { x, y, r } = moon;

  // Flicker when invincible
  if (invincible && Math.floor(invTimer / 4) % 2 === 0) return;

  // Glow
  const glow = ctx.createRadialGradient(x, y, r * 0.5, x, y, r * 2.5);
  glow.addColorStop(0,   'rgba(251,191,36,0.18)');
  glow.addColorStop(1,   'rgba(251,191,36,0)');
  ctx.beginPath();
  ctx.arc(x, y, r * 2.5, 0, Math.PI * 2);
  ctx.fillStyle = glow;
  ctx.fill();

  // Moon body
  const bodyGrad = ctx.createRadialGradient(x - r * 0.25, y - r * 0.25, r * 0.05, x, y, r);
  bodyGrad.addColorStop(0,   '#fffde7');
  bodyGrad.addColorStop(0.35,'#fff9c4');
  bodyGrad.addColorStop(0.7, '#e8e0b0');
  bodyGrad.addColorStop(1,   '#b0a060');
  ctx.beginPath();
  ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.fillStyle = bodyGrad;
  ctx.fill();

  // Shadow side
  const shadow = ctx.createRadialGradient(x + r * 0.4, y + r * 0.3, 0, x, y, r);
  shadow.addColorStop(0.6, 'rgba(0,0,0,0)');
  shadow.addColorStop(1,   'rgba(0,0,0,0.38)');
  ctx.beginPath();
  ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.fillStyle = shadow;
  ctx.fill();

  // Craters
  moon.craters.forEach(c => {
    ctx.beginPath();
    ctx.arc(x + c.ox, y + c.oy, c.r, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(0,0,0,0.18)';
    ctx.fill();
    ctx.strokeStyle = 'rgba(0,0,0,0.1)';
    ctx.lineWidth = 0.5;
    ctx.stroke();
  });
}

function drawLives() {
  for (let i = 0; i < CFG.maxLives; i++) {
    const alpha = i < lives ? 1 : 0.2;
    ctx.globalAlpha = alpha;
    ctx.font = '18px serif';
    ctx.fillText('🌕', 12 + i * 26, 30);
  }
  ctx.globalAlpha = 1;
}

function drawScore() {
  ctx.font = 'bold 22px Inter, sans-serif';
  ctx.fillStyle = '#ffffff';
  ctx.textAlign = 'right';
  ctx.fillText(score, W - 14, 30);
  ctx.font = '11px Inter, sans-serif';
  ctx.fillStyle = 'rgba(255,255,255,0.45)';
  ctx.fillText('SCORE', W - 14, 44);
  ctx.textAlign = 'left';
}

function drawSTRCount() {
  ctx.font = 'bold 14px Inter, sans-serif';
  ctx.fillStyle = '#fbbf24';
  ctx.textAlign = 'right';
  ctx.fillText(`⭐ ${strEarned} STR`, W - 14, 62);
  ctx.textAlign = 'left';
}

function drawObstacles() {
  obstacles.forEach(ob => {
    // Glow
    const g = ctx.createRadialGradient(ob.x, ob.y, ob.r * 0.3, ob.x, ob.y, ob.r * 1.8);
    g.addColorStop(0, 'rgba(239,68,68,0.2)');
    g.addColorStop(1, 'rgba(239,68,68,0)');
    ctx.beginPath();
    ctx.arc(ob.x, ob.y, ob.r * 1.8, 0, Math.PI * 2);
    ctx.fillStyle = g;
    ctx.fill();

    // Body - irregular rocky shape
    ctx.save();
    ctx.translate(ob.x, ob.y);
    ctx.rotate(ob.rot);
    ctx.beginPath();
    const pts = ob.shape;
    ctx.moveTo(pts[0].x, pts[0].y);
    for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i].x, pts[i].y);
    ctx.closePath();

    const bodyG = ctx.createRadialGradient(0, 0, 0, 0, 0, ob.r);
    bodyG.addColorStop(0, '#6b4c2a');
    bodyG.addColorStop(0.6,'#4a3218');
    bodyG.addColorStop(1, '#2d1e0e');
    ctx.fillStyle = bodyG;
    ctx.fill();
    ctx.strokeStyle = 'rgba(239,68,68,0.5)';
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.restore();

    // Trail
    ob.trail.forEach((t, ti) => {
      const alpha = (ti / ob.trail.length) * 0.3;
      ctx.beginPath();
      ctx.arc(t.x, t.y, ob.r * 0.4 * (ti / ob.trail.length), 0, Math.PI * 2);
      ctx.fillStyle = `rgba(239,68,68,${alpha})`;
      ctx.fill();
    });
  });
}

function drawStars() {
  stars.forEach(s => {
    const t = Date.now() / 400 + s.phase;
    const pulse = 1 + Math.sin(t) * 0.18;

    // Outer glow
    const g = ctx.createRadialGradient(s.x, s.y, 0, s.x, s.y, s.r * 3 * pulse);
    const col = s.rainbow ? `hsla(${(Date.now()/12 + s.phase * 40) % 360},100%,70%,` : 'rgba(251,191,36,';
    g.addColorStop(0, col + '0.35)');
    g.addColorStop(1, col + '0)');
    ctx.beginPath();
    ctx.arc(s.x, s.y, s.r * 3 * pulse, 0, Math.PI * 2);
    ctx.fillStyle = g;
    ctx.fill();

    // Star body
    ctx.save();
    ctx.translate(s.x, s.y);
    ctx.rotate(Date.now() / 600 + s.phase);
    drawStar5(ctx, s.r * pulse, s.rainbow ? `hsl(${(Date.now()/12 + s.phase*40) % 360},100%,70%)` : '#fbbf24');
    ctx.restore();
  });
}

function drawStar5(ctx, r, color) {
  const pts = 5;
  const inner = r * 0.45;
  ctx.beginPath();
  for (let i = 0; i < pts * 2; i++) {
    const angle = (i * Math.PI) / pts - Math.PI / 2;
    const rad   = i % 2 === 0 ? r : inner;
    i === 0
      ? ctx.moveTo(Math.cos(angle) * rad, Math.sin(angle) * rad)
      : ctx.lineTo(Math.cos(angle) * rad, Math.sin(angle) * rad);
  }
  ctx.closePath();
  ctx.fillStyle = color;
  ctx.fill();
  ctx.strokeStyle = 'rgba(255,255,255,0.4)';
  ctx.lineWidth = 0.8;
  ctx.stroke();
}

function drawParticles() {
  particles = particles.filter(p => p.life > 0);
  particles.forEach(p => {
    p.x   += p.vx;
    p.y   += p.vy;
    p.vy  += 0.08;
    p.life -= 1;
    const alpha = p.life / p.maxLife;
    ctx.globalAlpha = alpha;
    ctx.beginPath();
    ctx.arc(p.x, p.y, p.r * alpha, 0, Math.PI * 2);
    ctx.fillStyle = p.color;
    ctx.fill();
  });
  ctx.globalAlpha = 1;
}

function drawSpeedStripes() {
  if (speed < CFG.baseObstacleSpeed + 1) return;
  const intensity = Math.min((speed - CFG.baseObstacleSpeed) / 3, 1);
  ctx.globalAlpha = intensity * 0.06;
  for (let i = 0; i < 8; i++) {
    const x = (i / 8) * W + (frame * 0.5 % (W / 8));
    ctx.strokeStyle = 'rgba(124,58,237,1)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x - 20, H);
    ctx.stroke();
  }
  ctx.globalAlpha = 1;
}

// ── Spawn Functions ──────────────────────────────────────────────────
function spawnObstacle() {
  const r = 14 + Math.random() * 16;
  const x = r + Math.random() * (W - r * 2);
  const numPts = 7 + Math.floor(Math.random() * 4);
  const shape  = [];
  for (let i = 0; i < numPts; i++) {
    const a  = (i / numPts) * Math.PI * 2;
    const rd = r * (0.7 + Math.random() * 0.55);
    shape.push({ x: Math.cos(a) * rd, y: Math.sin(a) * rd });
  }
  obstacles.push({ x, y: -r - 10, r, vy: speed, rot: 0, rotV: (Math.random() - 0.5) * 0.06, shape, trail: [] });
}

function spawnStar() {
  const r       = 8 + Math.random() * 5;
  const x       = r + Math.random() * (W - r * 2);
  const rainbow = Math.random() < 0.12;
  stars.push({ x, y: -r - 10, r, vy: speed * 0.75, phase: Math.random() * Math.PI * 2, rainbow, value: rainbow ? 25 : 10 });
}

// ── Collision ────────────────────────────────────────────────────────
function dist(ax, ay, bx, by) {
  return Math.hypot(ax - bx, ay - by);
}

function checkCollisions() {
  // Stars
  stars = stars.filter(s => {
    if (dist(moon.x, moon.y, s.x, s.y) < moon.r + s.r) {
      collectStar(s);
      return false;
    }
    return true;
  });

  // Obstacles
  if (invincible) return;
  obstacles = obstacles.filter(ob => {
    // Simple circle vs circle (approximate for rocky shape)
    if (dist(moon.x, moon.y, ob.x, ob.y) < moon.r + ob.r * 0.75) {
      hitMoon(ob);
      return false;
    }
    return true;
  });
}

function collectStar(s) {
  strEarned += s.value;
  score     += s.value * 2;
  document.getElementById('live-str').textContent  = strEarned;
  document.getElementById('live-score').textContent = score;

  // Burst particles
  for (let i = 0; i < 10; i++) {
    const a = Math.random() * Math.PI * 2;
    const v = 1.5 + Math.random() * 3;
    particles.push({ x: s.x, y: s.y, vx: Math.cos(a) * v, vy: Math.sin(a) * v - 1,
      r: 3 + Math.random() * 3, color: s.rainbow ? `hsl(${Math.random()*360},100%,70%)` : '#fbbf24',
      life: 30, maxLife: 30 });
  }
  showToast(s.rainbow ? '🌈' : '⭐', `+${s.value} STR!`);
}

function hitMoon(ob) {
  lives--;
  invincible = true;
  invTimer   = 90; // frames

  // Add a crater
  const angle = Math.atan2(ob.y - moon.y, ob.x - moon.x);
  moon.craters.push({
    ox: Math.cos(angle) * (moon.r * 0.5),
    oy: Math.sin(angle) * (moon.r * 0.5),
    r: 4 + Math.random() * 3,
  });

  // Explosion particles
  for (let i = 0; i < 20; i++) {
    const a = Math.random() * Math.PI * 2;
    const v = 2 + Math.random() * 5;
    particles.push({ x: moon.x, y: moon.y, vx: Math.cos(a) * v, vy: Math.sin(a) * v - 1,
      r: 4 + Math.random() * 4, color: i % 2 === 0 ? '#ef4444' : '#f97316',
      life: 40, maxLife: 40 });
  }

  if (lives <= 0) endGame();
}

// ── Game Loop ─────────────────────────────────────────────────────────
function gameLoop() {
  if (gameState !== 'playing') return;

  frame++;
  speed += CFG.speedIncrement;

  // Input → velocity
  if (keys.left)  moon.vx = Math.max(moon.vx - 1.2, -CFG.moonSpeed);
  if (keys.right) moon.vx = Math.min(moon.vx + 1.2,  CFG.moonSpeed);
  if (!keys.left && !keys.right) moon.vx *= 0.82;

  // Move moon (horizontal only)
  moon.x = Math.max(moon.r, Math.min(W - moon.r, moon.x + moon.vx));

  // Invincibility timer
  if (invincible) {
    invTimer--;
    if (invTimer <= 0) invincible = false;
  }

  // Spawn objects
  const spawnRate = Math.max(40, CFG.obstacleInterval - frame * 0.04);
  spawnTimer++;
  if (spawnTimer >= spawnRate) { spawnObstacle(); spawnTimer = 0; }

  starTimer++;
  const starRate = Math.max(35, CFG.starInterval - frame * 0.02);
  if (starTimer >= starRate) { spawnStar(); starTimer = 0; }

  // Update obstacles
  obstacles.forEach(ob => {
    ob.trail.unshift({ x: ob.x, y: ob.y });
    if (ob.trail.length > 8) ob.trail.pop();
    ob.y   += ob.vy;
    ob.rot += ob.rotV;
    ob.vy   = speed;           // always track current speed
  });
  obstacles = obstacles.filter(ob => ob.y - ob.r < H + 30);

  // Update stars
  stars.forEach(s => { s.y += s.vy; });
  stars = stars.filter(s => s.y - s.r < H + 20);

  // Score ticks up with time
  if (frame % 6 === 0) {
    score++;
    document.getElementById('live-score').textContent = score;
  }

  // Collisions
  checkCollisions();

  // ── Draw ──
  drawBackground();
  drawSpeedStripes();
  drawStars();
  drawObstacles();
  drawParticles();
  drawMoon();
  drawLives();
  drawScore();
  drawSTRCount();

  animId = requestAnimationFrame(gameLoop);
}

// ── Game Flow ────────────────────────────────────────────────────────
window.startGame = function() {
  // Check hunger
  masterState = getMasterState();
  if (masterState.hunger <= 0) {
    showToast('🍖', 'No hunger left! Go to the Farm and make cheese.');
    return;
  }

  // Deduct 1 hunger
  masterState.hunger = Math.max(0, masterState.hunger - 1);
  saveMasterState(masterState);
  syncHUD();

  // Reset game state
  score     = 0;
  strEarned = 0;
  lives     = CFG.maxLives;
  frame     = 0;
  speed     = CFG.baseObstacleSpeed;
  spawnTimer = 0;
  starTimer  = 0;
  obstacles  = [];
  stars      = [];
  particles  = [];
  invincible = false;
  invTimer   = 0;

  moon.x = W / 2;
  moon.y = H - 80;
  moon.vx = 0;
  moon.craters = [
    { ox: -8,  oy: -6,  r: 5 },
    { ox:  9,  oy:  5,  r: 4 },
    { ox: -4,  oy:  10, r: 3 },
  ];

  document.getElementById('live-score').textContent = 0;
  document.getElementById('live-str').textContent   = 0;

  hideAllOverlays();
  gameState = 'playing';

  if (animId) cancelAnimationFrame(animId);
  gameLoop();
};

function endGame() {
  if (animId) cancelAnimationFrame(animId);
  gameState = 'dead';

  // Final draw frame
  drawBackground();
  drawStars();
  drawObstacles();
  drawParticles();
  drawMoon();
  drawLives();
  drawScore();
  drawSTRCount();

  // Award STR to master state
  masterState.str += strEarned;
  masterState.xp  += Math.floor(score / 10);
  if (masterState.xp >= masterState.xpNeeded) {
    masterState.xp -= masterState.xpNeeded;
    masterState.level++;
    masterState.maxHunger = Math.min((masterState.maxHunger || 5) + 1, 10);
    showToast('🎉', `Level Up! Now Level ${masterState.level}!`);
  }
  saveMasterState(masterState);
  syncHUD();

  setHighScore(score);
  document.getElementById('high-score-display').textContent = getHighScore();

  // Rank estimate
  let rank = 'Bottom third — earn minimum STR payout';
  if (score >= 800)      rank = '🥇 Top 10% — maximum STR payout!';
  else if (score >= 500) rank = '🥈 Top third — above average payout';
  else if (score >= 200) rank = '🥉 Middle third — standard payout';

  document.getElementById('final-score').textContent    = score + ' pts';
  document.getElementById('final-str').textContent      = `+${strEarned} STR earned`;
  document.getElementById('final-rank').textContent     = rank;
  showOverlay('overlay-gameover');

  if (strEarned > 0) showToast('⭐', `+${strEarned} STR added to your wallet!`);
}

window.resumeGame = function() {
  if (gameState !== 'paused') return;
  hideAllOverlays();
  gameState = 'playing';
  gameLoop();
};

// ── Input Handlers ────────────────────────────────────────────────────
document.addEventListener('keydown', e => {
  if (e.key === 'ArrowLeft'  || e.key === 'a' || e.key === 'A') keys.left  = true;
  if (e.key === 'ArrowRight' || e.key === 'd' || e.key === 'D') keys.right = true;
  if ((e.key === 'p' || e.key === 'P') && gameState === 'playing') {
    if (animId) cancelAnimationFrame(animId);
    gameState = 'paused';
    showOverlay('overlay-pause');
  }
  if ((e.key === 'p' || e.key === 'P' || e.key === 'Escape') && gameState === 'paused') {
    window.resumeGame();
  }
});

document.addEventListener('keyup', e => {
  if (e.key === 'ArrowLeft'  || e.key === 'a' || e.key === 'A') keys.left  = false;
  if (e.key === 'ArrowRight' || e.key === 'd' || e.key === 'D') keys.right = false;
});

// Touch controls (tap left half = move left, right half = move right)
canvas.addEventListener('touchstart', e => {
  e.preventDefault();
  const rect   = canvas.getBoundingClientRect();
  const scaleX = W / rect.width;
  Array.from(e.touches).forEach(t => {
    const tx = (t.clientX - rect.left) * scaleX;
    if (tx < W / 2) keys.left  = true;
    else             keys.right = true;
  });
}, { passive: false });

canvas.addEventListener('touchend', e => {
  e.preventDefault();
  if (e.touches.length === 0) { keys.left = false; keys.right = false; }
}, { passive: false });

// Click to start if idle
canvas.addEventListener('click', () => {
  if (gameState === 'idle') window.startGame();
});

// ── Idle draw (before game starts) ───────────────────────────────────
function drawIdle() {
  if (gameState !== 'idle') return;
  drawBackground();
  // Drift the moon gently
  moon.x = W / 2 + Math.sin(Date.now() / 1200) * 30;
  moon.y = H / 2 + Math.cos(Date.now() / 1600) * 20;
  drawMoon();
  requestAnimationFrame(drawIdle);
}

drawIdle();

// ── Responsive canvas ─────────────────────────────────────────────────
function resizeCanvas() {
  const maxW  = Math.min(window.innerWidth - 48, 420);
  canvas.style.width  = maxW + 'px';
  canvas.style.height = (maxW * H / W) + 'px';
}

resizeCanvas();
window.addEventListener('resize', resizeCanvas);
