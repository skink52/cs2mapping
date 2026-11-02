// ---------------------------------------------------------------- small helpers
// the game time of the current server tick: read once per think (it doesn't change within a tick)
let tickTime = 0, inThink = false;
function gameTime() { return inThink ? tickTime : Instance.GetGameTime(); }

function log(msg) { Instance.Msg('[spr] ' + msg); }
function dlog(msg) { if (CONFIG.DEBUG) log(msg); }
const warned = new Set();
function warnOnce(key, msg) { if (warned.has(key)) return; warned.add(key); log('WARNING: ' + msg); }

function live(e) {
  try { return e && e.IsValid() ? e : undefined; } catch (err) { return undefined; }
}

function guard(what, fn) {
  try { return fn(); } catch (err) {
    const k = what + ':' + String(err);
    if (!warned.has(k)) { warned.add(k); log('error in ' + what + ': ' + err + (err && err.stack ? '\n' + err.stack : '')); }
    return undefined;
  }
}

function slotOfEntity(e) {
  if (!e) return undefined;
  try {
    const x = /** @type {any} */ (e);
    if (typeof x.GetPlayerController === 'function') { const c = x.GetPlayerController(); return c ? c.GetPlayerSlot() : undefined; }
    if (typeof x.GetPlayerSlot === 'function') return x.GetPlayerSlot();
  } catch (err) { /* ignore */ }
  return undefined;
}

function controllerOf(slot) {
  try { return Instance.GetPlayerController(slot); } catch (err) { return undefined; }
}
function pawnOf(slot) {
  const c = controllerOf(slot);
  if (!c) return undefined;
  try { const p = c.GetPlayerPawn(); return live(p); } catch (err) { return undefined; }
}

function normAngle(a) { a = a % 360; if (a > 180) a -= 360; if (a < -180) a += 360; return a; }
function angleDiff(a, b) { return normAngle(b - a); }

// chat lines are queued and sent one at a time (CS2 drops chat sent too fast)
const sayQueue = [];
let sayNext = 0;
function sayAll(text) { sayQueue.push('say ' + String(text).replace(/[;"]/g, '')); }
function sayHold() { sayNext = Math.max(sayNext, gameTime() + CONFIG.SAY_GAP); }
function flushSays() {
  const now = gameTime();
  if (!sayQueue.length || now < sayNext) return;
  Instance.ServerCommand(sayQueue.shift());
  sayNext = now + CONFIG.SAY_GAP;
}

// track titles by id (votes, chat)
const TRACK_TITLE = {};
for (const t of TRACKS) TRACK_TITLE[t.id] = t.title;
function trackTitle(id) { return TRACK_TITLE[id] || String(id).toUpperCase(); }

// the colour shades (!shade): per side, the car skin and the colour (for the glow), from tools/cars.py
const SHADES = CAR_MODELS.shades || { t: [{ skin: 't', name: 'ORANGE', rgb: [255, 150, 40] }], ct: [{ skin: 'ct', name: 'BLUE', rgb: [70, 150, 255] }] };

