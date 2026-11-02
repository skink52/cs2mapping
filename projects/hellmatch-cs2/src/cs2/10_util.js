// ---------------------------------------------------------------- small helpers
function log(msg) { Instance.Msg("[hellmatch] " + msg); }
function dlog(msg) { if (CONFIG.DEBUG) log(msg); }
const warned = new Set();
function warnOnce(key, msg) { if (warned.has(key)) return; warned.add(key); log("WARNING: " + msg); }

function live(e) {
  try { return e && e.IsValid() ? e : undefined; } catch (err) { return undefined; }
}

function guard(what, fn) {
  try { return fn(); } catch (err) {
    const k = what + ":" + String(err);
    if (!warned.has(k)) { warned.add(k); log("error in " + what + ": " + err + (err && err.stack ? "\n" + err.stack : "")); }
    return undefined;
  }
}

function slotOfEntity(e) {
  if (!e) return undefined;
  try {
    const x = /** @type {any} */ (e);
    if (typeof x.GetPlayerController === "function") { const c = x.GetPlayerController(); return c ? c.GetPlayerSlot() : undefined; }
    if (typeof x.GetPlayerSlot === "function") return x.GetPlayerSlot();
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

function inputBit(name) { return CSInputs[name]; }

// chat lines are queued and sent one at a time from the think loop. On a listen server "say" speaks as the host,
// and CS2's chat flood limit drops a line sent right after another one (or right after the host typed something).
const sayQueue = [];
let sayNext = 0;
function sayAll(text) { sayQueue.push("say " + String(text).replace(/[;"]/g, "")); }
function sayHold() { sayNext = Math.max(sayNext, Instance.GetGameTime() + CONFIG.SAY_GAP); }
function flushSays() {
  const now = Instance.GetGameTime();
  if (!sayQueue.length || now < sayNext) return;
  Instance.ServerCommand(sayQueue.shift());
  sayNext = now + CONFIG.SAY_GAP;
}
