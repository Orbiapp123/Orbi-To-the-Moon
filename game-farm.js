/* ============================================
   ORBI: TO THE MOON — Farm Page Logic
   Manages plots, cow cycle, inventory & HUD
   ============================================ */

// ── Constants ──────────────────────────────────────────────────────
const PLOT_STAGES    = ['empty', 'seeded', 'growing', 'ready'];
const STAGE_DURATION = { seeded: 15, growing: 20 }; // seconds (demo speed)
const COW_MILK_TIME  = 25;  // seconds to produce milk (demo)
const COW_CHEESE_MILK = 2;  // milk needed per cheese

const PLOT_EMOJIS = {
  empty:   { emoji: '🟫', label: 'Empty Plot',      action: 'Tap to Plant' },
  seeded:  { emoji: '🌱', label: 'Seeds Planted',   action: 'Growing…'    },
  growing: { emoji: '🌿', label: 'Wheat Growing',   action: 'Almost ready!'},
  ready:   { emoji: '🌾', label: 'Ready to Harvest!', action: 'Tap to Harvest' },
};

// ── State ──────────────────────────────────────────────────────────
function loadState() {
  const defaults = {
    level: 4, xp: 230, xpNeeded: 500,
    str: 450, energy: 7, maxEnergy: 10,
    hunger: 4, maxHunger: 5,
    seeds: 8, wheat: 2, milk: 0, cheese: 1,
    harvestedToday: 0,
    plots: [
      { stage: 'ready',   timer: 0, progress: 100 },
      { stage: 'growing', timer: 10, progress: 50 },
      { stage: 'seeded',  timer: 8,  progress: 53 },
      { stage: 'empty',   timer: 0,  progress: 0  },
      { stage: 'empty',   timer: 0,  progress: 0  },
      { stage: 'empty',   timer: 0,  progress: 0  },
    ],
    cowState:    'idle',  // idle | milking | ready
    cowTimer:    0,
    cowProgress: 0,
  };
  try {
    const saved = JSON.parse(localStorage.getItem('orbi_farm') || '{}');
    return Object.assign({}, defaults, saved);
  } catch (e) { return defaults; }
}

function saveState() {
  localStorage.setItem('orbi_farm', JSON.stringify(state));
  // Sync master state too
  const master = getMasterState();
  master.str    = state.str;
  master.hunger = state.hunger;
  master.energy = state.energy;
  master.xp     = state.xp;
  master.level  = state.level;
  localStorage.setItem('orbi_state', JSON.stringify(master));
}

function getMasterState() {
  try { return JSON.parse(localStorage.getItem('orbi_state') || '{}'); }
  catch (e) { return {}; }
}

let state = loadState();

// ── Log ────────────────────────────────────────────────────────────
function logEntry(icon, msg) {
  const log = document.getElementById('farm-log');
  if (!log) return;
  const now = new Date();
  const time = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;
  const entry = document.createElement('div');
  entry.className = 'farm-log-entry';
  entry.innerHTML = `<span class="log-time">${time}</span><span class="log-icon">${icon}</span><span>${msg}</span>`;
  log.insertBefore(entry, log.firstChild);
  // Keep max 20 entries
  while (log.children.length > 20) log.removeChild(log.lastChild);
}

// ── Toast ──────────────────────────────────────────────────────────
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

// ── HUD Sync ───────────────────────────────────────────────────────
function syncHUD() {
  const ep = Math.round((state.energy / state.maxEnergy) * 100);
  const hp = Math.round((state.hunger / state.maxHunger) * 100);
  const xp = Math.round((state.xp    / state.xpNeeded)  * 100);

  document.getElementById('hud-level').textContent        = state.level;
  document.getElementById('hud-str').textContent          = state.str.toLocaleString();
  document.getElementById('hud-energy-fill').style.width  = ep + '%';
  document.getElementById('hud-energy-text').textContent  = `${state.energy}/${state.maxEnergy}`;
  document.getElementById('hud-hunger-fill').style.width  = hp + '%';
  document.getElementById('hud-hunger-text').textContent  = `${state.hunger}/${state.maxHunger}`;
  document.getElementById('hud-xp-fill').style.width      = xp + '%';
  document.getElementById('hud-xp-text').textContent      = `${state.xp} / ${state.xpNeeded} XP`;

  const cheeseTxt = document.getElementById('cheese-count-display');
  if (cheeseTxt) cheeseTxt.textContent = state.cheese + ' cheese ready';
}

// ── Render Plots ───────────────────────────────────────────────────
function renderPlots() {
  const grid = document.getElementById('plots-grid');
  if (!grid) return;
  grid.innerHTML = '';

  state.plots.forEach((plot, i) => {
    const info = PLOT_EMOJIS[plot.stage];
    const div  = document.createElement('div');
    div.className = `farm-plot ${plot.stage}`;
    div.dataset.index = i;
    div.onclick = () => clickPlot(i);

    const progressBar = plot.stage === 'seeded' || plot.stage === 'growing'
      ? `<div class="plot-progress"><div class="plot-progress-fill" style="width:${plot.progress}%;"></div></div>
         <div class="plot-timer">${formatTimer(plot.timer)}</div>`
      : '';

    div.innerHTML = `
      <div class="plot-emoji">${info.emoji}</div>
      <div class="plot-label">${info.label}</div>
      <div class="plot-action-label">${info.action}</div>
      ${progressBar}
    `;
    grid.appendChild(div);
  });
}

// ── Render Inventory ───────────────────────────────────────────────
function renderInventory() {
  const grid = document.getElementById('inventory-grid');
  if (!grid) return;

  const items = [
    { emoji: '🌱', name: 'Seeds',  count: state.seeds  },
    { emoji: '🌾', name: 'Wheat',  count: state.wheat  },
    { emoji: '🥛', name: 'Milk',   count: state.milk   },
    { emoji: '🧀', name: 'Cheese', count: state.cheese },
    { emoji: '💊', name: 'Potions', count: 0           },
    { emoji: '🎒', name: 'Extras',  count: 0           },
  ];

  grid.innerHTML = items.map(it => `
    <div class="inv-slot ${it.count > 0 ? 'has-item' : ''}">
      ${it.count > 0 ? `<span class="inv-count">x${it.count}</span>` : ''}
      <span class="inv-emoji">${it.emoji}</span>
      <span class="inv-name">${it.name}</span>
    </div>
  `).join('');
}

// ── Button States ──────────────────────────────────────────────────
function updateButtons() {
  const hasWheat    = state.wheat >= 1;
  const hasMilk     = state.milk  >= COW_CHEESE_MILK;
  const hasCheese   = state.cheese >= 1;
  const cowIdle     = state.cowState === 'idle';
  const cowReady    = state.cowState === 'ready';
  const hungerFull  = state.hunger >= state.maxHunger;

  const feedBtn     = document.getElementById('feed-cow-btn');
  const milkBtn     = document.getElementById('milk-cow-btn');
  const cheeseBtn   = document.getElementById('make-cheese-btn');
  const useCheeseBtn = document.getElementById('use-cheese-btn');

  if (feedBtn)      feedBtn.disabled    = !hasWheat || !cowIdle;
  if (milkBtn)      milkBtn.disabled    = !cowReady;
  if (cheeseBtn)    cheeseBtn.disabled  = !hasMilk;
  if (useCheeseBtn) useCheeseBtn.disabled = !hasCheese || hungerFull;

  // Cow status text
  const cowText = document.getElementById('cow-status-text');
  if (cowText) {
    if (state.cowState === 'milking') cowText.textContent = '🥛 Producing milk…';
    else if (state.cowState === 'ready') cowText.textContent = '✅ Milk ready to collect!';
    else cowText.textContent = hasWheat ? 'Idle — feed wheat to produce milk' : 'Idle — waiting for wheat';
  }
}

// ── Cow Progress ───────────────────────────────────────────────────
function updateCowUI() {
  const wrap    = document.getElementById('cow-progress-wrap');
  const fill    = document.getElementById('cow-progress-fill');
  const timerEl = document.getElementById('cow-timer-text');
  const labelEl = document.getElementById('cow-progress-label');

  if (state.cowState === 'milking') {
    if (wrap) wrap.style.display = 'block';
    const pct = Math.round(state.cowProgress);
    if (fill)    fill.style.width = pct + '%';
    if (timerEl) timerEl.textContent = formatTimer(state.cowTimer);
    if (labelEl) labelEl.textContent = '🥛 Producing Milk…';
  } else if (state.cowState === 'ready') {
    if (wrap) wrap.style.display = 'block';
    if (fill)    fill.style.width = '100%';
    if (timerEl) timerEl.textContent = 'Ready!';
    if (labelEl) labelEl.textContent = '✅ Milk is ready!';
  } else {
    if (wrap) wrap.style.display = 'none';
  }
}

// ── Actions ────────────────────────────────────────────────────────
function clickPlot(i) {
  const plot = state.plots[i];
  if (plot.stage === 'empty') {
    if (state.seeds <= 0) { showToast('❌', 'No seeds! Buy a Seed Chest.'); return; }
    state.seeds--;
    plot.stage    = 'seeded';
    plot.timer    = STAGE_DURATION.seeded;
    plot.progress = 0;
    logEntry('🌱', `Plot ${i + 1}: Seeds planted.`);
    addXP(5);
    saveState(); renderAll();
    showToast('🌱', `Plot ${i + 1} planted!`);
  } else if (plot.stage === 'ready') {
    state.wheat++;
    plot.stage    = 'empty';
    plot.timer    = 0;
    plot.progress = 0;
    state.harvestedToday++;
    logEntry('🌾', `Plot ${i + 1}: Wheat harvested! (+1 wheat)`);
    addXP(10);
    saveState(); renderAll();
    showToast('🌾', 'Wheat harvested! +1 🌾');
  } else {
    showToast('⏳', 'Still growing — check back soon!');
  }
}

window.farmAction = function(action) {
  switch (action) {

    case 'plantAll': {
      let planted = 0;
      state.plots.forEach((p, i) => {
        if (p.stage === 'empty' && state.seeds > 0) {
          state.seeds--;
          p.stage = 'seeded'; p.timer = STAGE_DURATION.seeded; p.progress = 0;
          planted++;
        }
      });
      if (planted > 0) {
        logEntry('🌱', `Planted ${planted} plot(s).`);
        addXP(planted * 5);
        showToast('🌱', `Planted ${planted} plot${planted > 1 ? 's' : ''}!`);
      } else {
        showToast('❌', state.seeds <= 0 ? 'No seeds left!' : 'No empty plots to plant!');
      }
      saveState(); renderAll();
      break;
    }

    case 'harvestAll': {
      let harvested = 0;
      state.plots.forEach(p => {
        if (p.stage === 'ready') {
          state.wheat++;
          p.stage = 'empty'; p.timer = 0; p.progress = 0;
          harvested++;
        }
      });
      if (harvested > 0) {
        state.harvestedToday += harvested;
        logEntry('🌾', `Harvested ${harvested} plot(s). +${harvested} wheat.`);
        addXP(harvested * 10);
        showToast('🌾', `Harvested ${harvested} plot${harvested > 1 ? 's' : ''}! +${harvested} 🌾`);
      } else {
        showToast('⏳', 'No plots ready to harvest yet!');
      }
      saveState(); renderAll();
      break;
    }

    case 'waterAll': {
      const growing = state.plots.filter(p => p.stage === 'growing' || p.stage === 'seeded');
      growing.forEach(p => { p.timer = Math.max(0, p.timer - 5); });
      if (growing.length > 0) {
        logEntry('💧', `Watered ${growing.length} plot(s). Growth time -5s each.`);
        showToast('💧', `Watered ${growing.length} plot${growing.length > 1 ? 's' : ''}! Growth boosted.`);
      } else {
        showToast('💧', 'No growing plots to water!');
      }
      saveState(); renderAll();
      break;
    }

    case 'feedCow': {
      if (state.wheat < 1) { showToast('❌', 'Need at least 1 wheat to feed Bessie!'); return; }
      if (state.cowState !== 'idle') { showToast('⏳', 'Bessie is busy!'); return; }
      state.wheat--;
      state.cowState    = 'milking';
      state.cowTimer    = COW_MILK_TIME;
      state.cowProgress = 0;
      logEntry('🐄', 'Fed Bessie 1 wheat. Milk production started!');
      addXP(8);
      showToast('🐄', 'Bessie is making milk! 🥛');
      saveState(); renderAll();
      break;
    }

    case 'collectMilk': {
      if (state.cowState !== 'ready') { showToast('⏳', 'Milk not ready yet!'); return; }
      state.milk++;
      state.milk++;          // common cow yields 2 milk
      state.cowState = 'idle';
      state.cowTimer = 0; state.cowProgress = 0;
      logEntry('🥛', 'Collected 2 milk from Bessie!');
      addXP(5);
      showToast('🥛', 'Collected 2 milk! 🥛🥛');
      saveState(); renderAll();
      break;
    }

    case 'makeCheese': {
      if (state.milk < COW_CHEESE_MILK) { showToast('❌', `Need ${COW_CHEESE_MILK} milk to make cheese!`); return; }
      state.milk -= COW_CHEESE_MILK;
      state.cheese++;
      logEntry('🧀', '2 milk → 1 cheese crafted!');
      addXP(12);
      showToast('🧀', 'Cheese crafted! +1 🧀');
      saveState(); renderAll();
      break;
    }

    case 'useCheese': {
      if (state.cheese < 1) { showToast('❌', 'No cheese available!'); return; }
      if (state.hunger >= state.maxHunger) { showToast('😋', 'Hunger bar is already full!'); return; }
      state.cheese--;
      state.hunger = Math.min(state.hunger + 1, state.maxHunger);
      logEntry('🍖', `Ate cheese! Hunger restored to ${state.hunger}/${state.maxHunger}.`);
      addXP(3);
      showToast('🍖', `+1 Hunger! (${state.hunger}/${state.maxHunger})`);
      saveState(); renderAll();
      break;
    }
  }
};

// ── XP Helper ──────────────────────────────────────────────────────
function addXP(amount) {
  state.xp += amount;
  if (state.xp >= state.xpNeeded) {
    state.xp -= state.xpNeeded;
    state.level++;
    state.maxHunger = Math.min(state.maxHunger + 1, 10);
    logEntry('✨', `Level up! Now Level ${state.level}!`);
    showToast('🎉', `Level Up! Now Level ${state.level}! 🎉`);
  }
}

// ── Utility ────────────────────────────────────────────────────────
function formatTimer(seconds) {
  const s = Math.ceil(seconds);
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return m > 0 ? `${m}:${String(rem).padStart(2,'0')}` : `${s}s`;
}

function renderAll() {
  syncHUD();
  renderPlots();
  renderInventory();
  updateButtons();
  updateCowUI();
}

// ── Game Loop (tick every second) ──────────────────────────────────
function gameTick() {
  let changed = false;

  // Advance plot timers
  state.plots.forEach(plot => {
    if (plot.stage === 'seeded' || plot.stage === 'growing') {
      if (plot.timer > 0) {
        plot.timer -= 1;
        const maxTime = plot.stage === 'seeded' ? STAGE_DURATION.seeded : STAGE_DURATION.growing;
        plot.progress = Math.round(((maxTime - plot.timer) / maxTime) * 100);
        changed = true;

        if (plot.timer <= 0) {
          plot.progress = 100;
          if (plot.stage === 'seeded') {
            plot.stage = 'growing';
            plot.timer = STAGE_DURATION.growing;
            plot.progress = 0;
          } else if (plot.stage === 'growing') {
            plot.stage = 'ready';
            plot.timer = 0;
            logEntry('🌾', 'A wheat plot is ready to harvest!');
            showToast('🌾', 'Wheat is ready to harvest!');
          }
        }
      }
    }
  });

  // Advance cow timer
  if (state.cowState === 'milking') {
    if (state.cowTimer > 0) {
      state.cowTimer -= 1;
      state.cowProgress = Math.round(((COW_MILK_TIME - state.cowTimer) / COW_MILK_TIME) * 100);
      changed = true;
    }
    if (state.cowTimer <= 0) {
      state.cowState    = 'ready';
      state.cowProgress = 100;
      state.cowTimer    = 0;
      logEntry('✅', 'Bessie has milk ready to collect!');
      showToast('✅', 'Bessie\'s milk is ready! 🥛');
      changed = true;
    }
  }

  if (changed) {
    saveState();
    renderAll();
  }
}

// ── Init ───────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  renderAll();
  setInterval(gameTick, 1000);
  logEntry('🌾', 'Welcome back to the Moon Farm!');
});
