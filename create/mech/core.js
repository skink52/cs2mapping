// mech core: shared by every mechanic module in create/mech/ (bundled into one cs_script by create/mechkit.py; cs_script has no imports).
// The bundle starts with the point_script import and `const CONFIG = {...}`; modules register tickers and inputs, mechStart() runs them.
// Ported in spirit from cs2-map-mcp's data/mechanics/core.js (Rmgs123, MIT): log, per-player state, HUD variables, one think loop.
// Fresh code for skink52's create/ toolkit.

const MECH = { tickers: [], now: 0, dt: 1 / 64, state: new Map(), hud: null, hudLooked: false, starters: [] };
const KEYS = { use: CSInputs.USE, attack: CSInputs.ATTACK, attack2: CSInputs.ATTACK2, reload: CSInputs.RELOAD, jump: CSInputs.JUMP,
  duck: CSInputs.DUCK, walk: CSInputs.WALK, forward: CSInputs.FORWARD, back: CSInputs.BACK, left: CSInputs.LEFT, right: CSInputs.RIGHT,
  inspect: CSInputs.LOOK_AT_WEAPON };

function mechLog(text) { Instance.Msg("[mech] " + text); }
function vec(x, y, z) { return { x: x, y: y, z: z }; }
function vAdd(a, b) { return vec(a.x + b.x, a.y + b.y, a.z + b.z); }
function vSub(a, b) { return vec(a.x - b.x, a.y - b.y, a.z - b.z); }
function vMul(a, s) { return vec(a.x * s, a.y * s, a.z * s); }
function vDot(a, b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
function vLen(a) { return Math.sqrt(vDot(a, a)); }
function vNorm(a) { const l = vLen(a); return l > 1e-6 ? vMul(a, 1 / l) : vec(0, 0, 0); }
function fwdOf(ang) {
  const p = ang.pitch * Math.PI / 180, y = ang.yaw * Math.PI / 180;
  return vec(Math.cos(p) * Math.cos(y), Math.cos(p) * Math.sin(y), -Math.sin(p));
}
function flatFwd(ang) { const y = ang.yaw * Math.PI / 180; return vec(Math.cos(y), Math.sin(y), 0); }
function clamp(v, lo, hi) { return v < lo ? lo : v > hi ? hi : v; }
function keyOf(name) { const k = KEYS[String(name || "").toLowerCase()]; if (k === undefined) throw new Error("unknown key " + name); return k; }

// live players: [{ ctrl, pawn, slot }]
function mechPlayers(team) {
  const out = [];
  for (const ctrl of Instance.GetAllPlayerControllers()) {
    if (!ctrl || !ctrl.IsConnected()) continue;
    const pawn = ctrl.GetPlayerPawn();
    if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) continue;
    if (team !== undefined && pawn.GetTeamNumber() !== team) continue;
    out.push({ ctrl: ctrl, pawn: pawn, slot: ctrl.GetPlayerSlot() });
  }
  return out;
}
function slotState(slot) { let s = MECH.state.get(slot); if (!s) { s = {}; MECH.state.set(slot, s); } return s; }
function pawnSlot(pawn) { const c = pawn && pawn.IsValid() ? pawn.GetPlayerController() : undefined; return c ? c.GetPlayerSlot() : -1; }

function mechHud() {
  if (!MECH.hudLooked && CONFIG.hud) { MECH.hudLooked = true; MECH.hud = Instance.FindEntityByName(CONFIG.hud.entity) || null; }
  return MECH.hud && MECH.hud.IsValid() ? MECH.hud : null;
}
const HUD_SEEN = new Map();          // only changed values go to the HUD (calls cost; most values repeat tick to tick)
function hudSet(slot, name, value) {
  const h = mechHud(), k = slot + "|" + name, s = String(value);
  if (!h || HUD_SEEN.get(k) === s) return;
  HUD_SEEN.set(k, s); h.SetDialogVariableStringForPlayer(slot, CONFIG.hud.panel, name, s);
}
function hudAll(name, value) {
  const h = mechHud(), k = "all|" + name, s = String(value);
  if (!h || HUD_SEEN.get(k) === s) return;
  HUD_SEEN.set(k, s); h.SetDialogVariableString(CONFIG.hud.panel, name, s);
}
function say(text) { hudAll("msg", text); mechLog(text); }
function every(fn) { MECH.tickers.push(fn); }
function onStart(fn) { MECH.starters.push(fn); }
function fire(name, input, value, delay) { Instance.EntFireAtName({ name: name, input: input, value: value, delay: delay || 0 }); }

function mechStart() {
  Instance.OnPlayerDisconnect((e) => { MECH.state.delete(e.playerSlot); for (const k of [...HUD_SEEN.keys()]) if (k.startsWith(e.playerSlot + "|")) HUD_SEEN.delete(k); });
  Instance.OnRoundStart(() => { MECH.hudLooked = false; HUD_SEEN.clear(); for (const f of MECH.starters) { try { f(); } catch (err) { mechLog("start: " + err); } } });
  Instance.SetThink(() => {
    MECH.now = Instance.GetGameTime();
    for (const t of MECH.tickers) { try { t(MECH.now); } catch (err) { mechLog("tick: " + err); } }
    Instance.SetNextThink(MECH.now + MECH.dt);
  });
  Instance.SetNextThink(Instance.GetGameTime() + MECH.dt);
  for (const f of MECH.starters) { try { f(); } catch (err) { mechLog("start: " + err); } }
}
