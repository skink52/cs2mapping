// ---------------------------------------------------------------- Doom status bar HUD
// The layout (panorama/layout/custom_game/freedm.xml) has fixed panels; the script swaps one
// CSS class per panel per player. Every change is cached so only real changes are sent.

let hudEnt;
let hudBudget = Infinity;      // reset every think; when it runs out, the rest of the HUD changes go out next tick
const hudCache = new Map();   // slot -> Map(panelId -> class)
const hudLines = new Map();   // slot -> Map(line or number prefix -> what it last showed in full), so unchanged ones are skipped
const HUD_LINE_CHECK = false; // test only: still compare every skipped line panel by panel
let hudCheckMiss = 0;
let hudGen = 0;               // goes up whenever the HUD entity is found again (everything gets resent)

let hudValidThink = false;     // true once hudEnt has been checked during the current think (reset each think)
function hud() {
  if (hudValidThink && hudEnt) return hudEnt;
  if (live(hudEnt)) { hudValidThink = inThink; return hudEnt; }
  hudEnt = live(Instance.FindEntityByName(CONFIG.HUD));
  if (!hudEnt) { warnOnce("hud", "no custom_hud_layout named " + CONFIG.HUD + " - no game HUD"); return hudEnt; }
  // a (re)found HUD entity doesn't know what we sent before: clear it and resend everything
  for (const slot of hudCache.keys()) { try { hudEnt.ResetForPlayer(slot); } catch (err) { /* ignore */ } }
  hudCache.clear();
  hudLines.clear();
  hudGen++;
  return hudEnt;
}

// true when this line/number already shows `value` (then there is nothing to send)
function hudSame(slot, prefix, value) {
  const lines = hudLines.get(slot);
  return !!lines && lines.get(prefix) === value;
}

// remember what a line/number shows, but only if every change for it went out (the budget can cut a line short,
// and a HUD entity found again halfway through means the start of the line was wiped)
function hudDrawn(slot, prefix, value, gen) {
  let lines = hudLines.get(slot);
  if (!lines) { lines = new Map(); hudLines.set(slot, lines); }
  if (hudBudget > 0 && gen === hudGen && hudCache.has(slot)) lines.set(prefix, value); else lines.delete(prefix);
}

function hudSwap(slot, panel, cls) {
  let c = hudCache.get(slot);
  if (!c) { c = new Map(); hudCache.set(slot, c); }
  const old = c.get(panel);
  if (old === cls) return;
  if (hudBudget <= 0) return;
  const h = hud();
  if (!h) return;
  hudBudget -= old && cls ? 2 : 1;
  if (old) h.SetHasClassForPlayer(slot, panel, old, false);
  if (cls) h.SetHasClassForPlayer(slot, panel, cls, true);
  c.set(panel, cls);
}

function hudReset(slot) {
  hudCache.delete(slot);
  hudLines.delete(slot);
  const h = hud();
  if (h) { try { h.ResetForPlayer(slot); } catch (err) { /* ignore */ } }
}

// an arena result as the HUD shows it (short player name)
function hudResult(r) {
  if (r.coop) return r.won ? "VICTORY" : r.timeout ? "TIME UP" : "OVERRUN";
  return r.player && r.team === undefined ? hudName(r.player.name) + " WINS" : r.text;
}

// width of a text in the HUD font, in screen pixels of the 320-wide Doom screen
function hudWidth(text) {
  let w = 0;
  for (let i = 0; i < text.length; i++) { const c = text.charCodeAt(i); w += c === 32 ? 4 : (HUD_GLYPH_W[c] || 4); }
  return w;
}

// split a message into two lines at a space so each fits the screen width and the line's character slots
// (the same few messages are wrapped for everyone every tic: remembered)
const hudWrapMemo = new Map();
function hudWrap(text, maxPx, maxChars) {
  const k = maxPx + "|" + maxChars + "|" + text;
  let r = hudWrapMemo.get(k);
  if (!r) {
    if (hudWrapMemo.size > 256) hudWrapMemo.clear();
    r = hudWrapRaw(text, maxPx, maxChars);
    hudWrapMemo.set(k, r);
  }
  return r;
}
function hudWrapRaw(text, maxPx, maxChars) {
  text = String(text || "").toUpperCase();
  const fits = (s) => s.length <= maxChars && hudWidth(s) <= maxPx;
  if (fits(text)) return [text, ""];
  const words = text.split(" ");
  let a = "";
  while (words.length && fits(a ? a + " " + words[0] : words[0])) a = a ? a + " " + words.shift() : words.shift();
  let b = words.join(" ");
  while (b && !fits(b)) b = b.slice(0, -1);
  return [a, b];
}

// Doom font text: one panel per character, classes c<ascii code>
function hudText(slot, prefix, len, text) {
  // already showing exactly this (what is remembered is upper case, so an equal string needs no conversion)
  if (typeof text === "string" && !HUD_LINE_CHECK && hudSame(slot, prefix, text)) return;
  text = String(text || "").toUpperCase();
  const same = hudSame(slot, prefix, text);
  if (same && !HUD_LINE_CHECK) return;
  const full = text, gen = hudGen;
  const pre = HUD_STRING_INDEX.get(text);
  const set = (panel, cls) => { if (!same) hudSwap(slot, panel, cls); else { const c = hudCache.get(slot); if (((c && c.get(panel)) || null) !== cls) hudCheckMiss++; } };
  set(prefix + "img", pre === undefined ? null : "t" + pre);
  if (pre !== undefined) text = "";
  for (let i = 0; i < len; i++) {
    const ch = i < text.length ? text.charCodeAt(i) : 0;
    let cls = null;
    if (ch === 32) cls = "csp";
    else if (ch >= 33 && ch <= 95) cls = "c" + ch;
    else if (ch) cls = "csp";
    set(prefix + i, cls);
  }
  if (!same) hudDrawn(slot, prefix, full, gen);
}

function hudNumber(slot, prefix, digits, value, kind, showZero) {
  // right-aligned digits; kind: "b" big red, "y" small yellow, "g" small grey. The remembered key is the number
  // itself (each number panel always has the same kind), so nothing is built for a number that hasn't changed
  let key;
  if (value === null) key = "-";
  else { key = Math.floor(value); if (key !== key) key = "NaN"; }
  const same = hudSame(slot, prefix, key);
  if (same && !HUD_LINE_CHECK) return;
  const gen = hudGen;
  const set = (panel, cls) => { if (!same) hudSwap(slot, panel, cls); else { const c = hudCache.get(slot); if (((c && c.get(panel)) || null) !== cls) hudCheckMiss++; } };
  let v = Math.max(-99, Math.min(Math.pow(10, digits) - 1, Math.floor(value)));
  const neg = v < 0; if (neg) v = -v;
  const s = String(v);
  for (let i = 0; i < digits; i++) {
    const di = s.length - digits + i;
    let cls = null;
    if (di >= 0) cls = kind + "n" + s[di];
    else if (neg && di === -1) cls = kind + "nm";
    if (value === null) cls = null;
    set(prefix + i, cls);
  }
  if (!same) hudDrawn(slot, prefix, key, gen);
}

// ---------------------------------------------------------------- face (ST_updateFaceWidget)
const ST_FACESTRIDE = 8, ST_NUMPAINFACES = 5, ST_TURNOFFSET = 3, ST_OUCHOFFSET = 5, ST_EVILGRINOFFSET = 6, ST_RAMPAGEOFFSET = 7;
const ST_GODFACE = ST_NUMPAINFACES * ST_FACESTRIDE, ST_DEADFACE = ST_GODFACE + 1;

function faceState(p) {
  if (!p.face) p.face = { priority: 0, count: 0, index: 0, lastattackdown: -1, oldhealth: -1, oldweapons: p.weaponowned.slice(), rnd: 0 };
  return p.face;
}

function calcPainOffset(p) {
  const health = Math.min(100, p.health);
  return ST_FACESTRIDE * Math.floor(((100 - health) * ST_NUMPAINFACES) / 101);
}

function updateFace(p) {
  const f = faceState(p);
  if (f.oldhealth < 0) f.oldhealth = p.health;
  if (f.priority < 10 && !p.health) { f.priority = 9; f.index = ST_DEADFACE; f.count = 1; }
  if (f.priority < 9 && p.bonuscount) {
    let doevil = false;
    for (let i = 0; i < NUMWEAPONS; i++) if (f.oldweapons[i] !== p.weaponowned[i]) { doevil = true; f.oldweapons[i] = p.weaponowned[i]; }
    if (doevil) { f.priority = 8; f.count = 2 * TICRATE; f.index = calcPainOffset(p) + ST_EVILGRINOFFSET; }
  }
  if (f.priority < 8 && p.damagecount && p.attacker && p.attacker !== p.mo && !p.attacker.removed && p.mo) {
    f.priority = 7;
    if (p.health - f.oldhealth > 20 || f.oldhealth - p.health > 20) { f.count = TICRATE; f.index = calcPainOffset(p) + ST_OUCHOFFSET; }
    else {
      const bad = pointToAngle(p.mo.x, p.mo.y, p.attacker.x, p.attacker.y);
      const d = angleDiff(p.mo.angle, bad);
      f.count = TICRATE; f.index = calcPainOffset(p);
      if (Math.abs(d) < 45) f.index += ST_RAMPAGEOFFSET;
      else if (d > 0) f.index += ST_TURNOFFSET + 1;     // attacker on the left
      else f.index += ST_TURNOFFSET;
    }
  }
  if (f.priority < 7 && p.damagecount) {
    if (f.oldhealth - p.health > 20) { f.priority = 7; f.count = TICRATE; f.index = calcPainOffset(p) + ST_OUCHOFFSET; }
    else { f.priority = 6; f.count = TICRATE; f.index = calcPainOffset(p) + ST_RAMPAGEOFFSET; }
  }
  if (f.priority < 6) {
    if (p.attackdown) {
      if (f.lastattackdown === -1) f.lastattackdown = 2 * TICRATE;
      else if (!--f.lastattackdown) { f.priority = 5; f.index = calcPainOffset(p) + ST_RAMPAGEOFFSET; f.count = 1; f.lastattackdown = 1; }
    } else f.lastattackdown = -1;
  }
  if (f.priority < 5 && p.powers[PW_INVULN]) { f.priority = 4; f.index = ST_GODFACE; f.count = 1; }
  if (!f.count) { f.index = calcPainOffset(p) + (P_Random() % 3); f.count = TICRATE / 2; f.priority = 0; }
  f.count--;
  f.oldhealth = p.health;
  return f.index;
}

// !text sizes (tools/hud.py TEXT_SIZES; "normal" has no class)
const TEXT_SCALE = { tiny: 0.6, small: 0.8, normal: 1, large: 1.25, huge: 1.5 };

// ---------------------------------------------------------------- per player HUD refresh
const weaponClassMemo = [];
function weaponClass(psp) {
  if (!psp || psp.state === S_NULL) return null;
  let c = weaponClassMemo[psp.state];
  if (c === undefined) {
    const st = STATES[psp.state];
    c = weaponClassMemo[psp.state] = "w_" + st.sprite.toLowerCase() + "_" + String.fromCharCode(97 + st.frame);
  }
  return c;
}
// class names built once
const HUD_SY = Array.from({ length: 25 }, (_, i) => "sy" + i);
const HUD_FB = Array.from({ length: 16 }, (_, i) => "fb" + i);
const HUD_RED = Array.from({ length: 9 }, (_, i) => "red" + i);
const HUD_GOLD = Array.from({ length: 5 }, (_, i) => "gold" + i);
const HUD_FACE = [];
const HUD_AMC = ["fdm_am0c", "fdm_am1c", "fdm_am2c", "fdm_am3c"], HUD_AMM = ["fdm_am0m", "fdm_am1m", "fdm_am2m", "fdm_am3m"];

function hudOptions(slot) {
  const pe = rm && rm.person(slot);
  const hide = pe && pe.hideOnScores !== undefined ? pe.hideOnScores : CONFIG.HIDE_HUD_ON_SCOREBOARD;
  hudSwap(slot, "fdm_opts", hide ? "hidescores" : null);
}

function hudPlayer(slot, p, arena, info) {
  hudSwap(slot, "fdm_root", "On");
  hudOptions(slot);
  hudSwap(slot, "fdm_sbarbox", info && info.sbar && info.sbar !== "centre" ? info.sbar : null);
  hudSwap(slot, "fdm_screen", info && info.text && info.text !== "normal" ? info.text : null);
  // weapon sprite + flash
  const wp = p.psprites[0], fp = p.psprites[1];
  const alive = p.playerstate === "live";
  hudSwap(slot, "fdm_wspr", alive || wp.state !== S_NULL ? weaponClass(wp) : null);
  hudSwap(slot, "fdm_wflash", weaponClass(fp));
  // raising/lowering moves the gun in steps; the walking bob is a CSS animation on the client
  const ready = wp.state !== S_NULL && STATES[wp.state].action === "A_WeaponReady";
  const sy = ready ? 0 : Math.max(0, Math.min(24, Math.round((wp.sy - WEAPONTOP) / 4)));
  hudSwap(slot, "fdm_wpn", HUD_SY[sy]);
  const moving = p.mo && p.bob > 4 && p.mo.z <= p.mo.floorz;
  hudSwap(slot, "fdm_wbob", ready && moving ? (p.bob > 10 ? "bob2" : "bob1") : null);
  // numbers
  const ammoType = WEAPONINFO[p.readyweapon].ammo;
  hudNumber(slot, "fdm_ammo", 3, ammoType === AM_NOAMMO ? null : p.ammo[ammoType], "b");
  hudNumber(slot, "fdm_hp", 3, p.health, "b");
  hudNumber(slot, "fdm_ar", 3, p.armorpoints, "b");
  const fragVal = arena && arena.teamsActive && p.team >= 0 ? arena.teamScore[p.team] : p.frags;
  hudNumber(slot, "fdm_frag", 3, fragVal, "b");
  for (let i = 0; i < 4; i++) {
    hudNumber(slot, HUD_AMC[i], 3, p.ammo[i], "y");
    hudNumber(slot, HUD_AMM[i], 3, p.maxammo[i], "y");
  }
  if (p.faceTic !== (arena ? arena.leveltime : 0)) { p.faceIdx = updateFace(p); p.faceTic = arena ? arena.leveltime : 0; }
  hudSwap(slot, "fdm_face", HUD_FACE[p.faceIdx] || (HUD_FACE[p.faceIdx] = "f" + p.faceIdx));
  hudSwap(slot, "fdm_faceb", HUD_FB[p.color & 15]);
  // screen tint (Doom's palette shifts)
  let tint = null;
  let cnt = p.damagecount;
  if (p.powers[PW_STRENGTH]) { const bzc = 12 - (p.powers[PW_STRENGTH] >> 6); if (bzc > cnt) cnt = bzc; }
  if (cnt) tint = HUD_RED[Math.min(8, (cnt + 7) >> 3)];
  else if (p.bonuscount) tint = HUD_GOLD[Math.min(4, (p.bonuscount + 7) >> 3)];
  else if (p.powers[PW_INVULN] > 4 * 32 || (p.powers[PW_INVULN] & 8)) tint = "invul";
  hudSwap(slot, "fdm_flash", tint);
  hudSwap(slot, "fdm_team", arena && arena.teamsActive && p.team >= 0 ? (p.team === 0 ? "teamred" : "teamblue") : null);
  // message line (4 seconds, like Doom); !help puts the controls there instead
  const msg = info && info.msg ? info.msg : p.message && arena && arena.leveltime - p.messageTime < 4 * TICRATE ? p.message : "";
  const [m1, m2] = hudWrap(msg, Math.floor(316 / TEXT_SCALE[(info && info.text) || "normal"]), 56);
  hudText(slot, "fdm_msg", 56, m1);
  hudText(slot, "fdm_msgb", 56, m2);
  if (info) {
    hudText(slot, "fdm_inf1_", 32, info.line1 || "");
    hudText(slot, "fdm_inf2_", 32, info.line2 || "");
    hudText(slot, "fdm_ctr", 24, info.center || "");
    hudText(slot, "fdm_spec", 32, info.spec || "");
    hudText(slot, "fdm_spec2_", 40, info.spec2 || "");
  }
}

function hudOff(slot) {
  hudSwap(slot, "fdm_root", null);
}

// lobby: only the text lines (top right, centre, bottom)
function hudLobby(slot, info) {
  hudSwap(slot, "fdm_root", "Lobby");
  hudSwap(slot, "fdm_screen", info.text && info.text !== "normal" ? info.text : null);
  hudOptions(slot);
  hudText(slot, "fdm_inf1_", 32, info.line1 || "");
  hudText(slot, "fdm_inf2_", 32, info.line2 || "");
  hudText(slot, "fdm_ctr", 24, info.center || "");
  hudText(slot, "fdm_spec", 32, info.spec || "");
  hudText(slot, "fdm_spec2_", 40, info.spec2 || "");
}
