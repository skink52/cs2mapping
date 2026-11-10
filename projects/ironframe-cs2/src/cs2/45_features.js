// ===================================================================================================================
// IRONFRAME CS2 adapter: the fun features (core rules in src/core/86_features.js; docs/FEATURES.md).
//   Overdrive    input combo (JUMP + both shoulder buttons, or the chat command !od), charge and blast visuals, camera shake, HUD lines
//   Supply crates  the falling crate prop (models.json#fx.crate), a spark trail while it falls, thump on landing, HUD lines
//   Killstreaks  HUD lines and a tone; the radar ping flag (m.radarT) is read by featPinged() for the radar dots
//   Objectives   the zone / flag world markers and the plugin's ifr_obj state lines (objTick, from featTick; section at the end)
// Hooks from other files (one line each): 90_main.js handleEvent -> featEvent(ev); personTick input -> featInput(pe, input);
// the render loop -> featTick(); 30_render.js effects draw -> featCratePlace(p, o); hudFeed radar dots -> featPinged(me, o);
// 80_chat.js -> !od.
// ===================================================================================================================
const featTimers = [];        // {at, fn}
const featState = new Map();  // slot -> {full: bool}
const CRATE_TEXT = { repair: 'REPAIR: +40 % AP now', ammo: 'AMMO REFILLED on every weapon', damage: 'DAMAGE +25 % for 15 s', shield: 'SHIELD: -40 % damage taken for 15 s', overdrive: 'OVERDRIVE FULL: hold SPACE + R + E' };

// ---------------------------------------------------------------- onboarding (10 Nov 2026 evening playtest: "not much is easy to understand or jump
// straight into"): the controls card at the first spawns and death screens (and on !help, or after holding Tab), the loadout card at every spawn,
// and hints: one important line the first time something happens to a pilot in a session (the HUD keeps what was shown: ifrHudHint).
// Every sentence is here so test/hud_strings.cjs can run each through the message line.
const ONB = { controlSpawns: 2, controlSecs: 14, controlDeaths: 3, loadoutSecs: 8, loadoutFirst: 12, tabHold: 0.8, tabSecs: 8, modeHintAfter: 7 };
const HINTS = {
  start: 'Keep an enemy inside the ring to lock on. Mouse 1 / 2 fire the arms, R / E the shoulders. !help: controls',
  stall: 'EN EMPTY: no hover or quick boost for 2.5 s. EN refills fast on the ground, slowly in the air',
  stagger: 'STAGGERED: heavy hits filled your stagger bar. Slow and +50 % damage taken for 2 s: quick boost (Ctrl) away',
  lock: 'SOFT LOCK: your guns track the bracketed mech. F = next target. Missiles want the red bracket',
  hard: 'HARD LOCK (red bracket): missiles fired now will track it',
  nolock: 'NO TARGET IN THE RING: the rockets flew straight. Aim at an enemy and HOLD the key: they launch guided',
  holdlock: 'KEEP HOLDING: the missiles launch guided when the lock is done. Let go early and they fly straight',
  multilock: 'MULTI-LOCK: hold the key to lock up to four mechs in the ring (a diamond on each), let go to fire',
  death: 'DESTROYED. Ctrl or F now opens the garage: change weapons or frame. Space drops you straight back in',
  zone: 'CAPTURING: stay inside the ring. More pilots capture faster; an enemy inside contests it',
  crate: 'SUPPLY CRATE LANDED (the glinting box): walk into it for a repair, ammo, a boost or a full overdrive',
  od: 'OVERDRIVE READY: press R + E together and hold (or !od). 1.2 s charge, then a blast: 2 500 damage and stagger within 600 u',
  odAgain: 'OVERDRIVE READY: hold R + E together',
  arty: 'ARTILLERY: aim at an enemy at least 700 u away. Six shells fall on it by themselves as soon as you lock',
  heat: 'OVERHEATED: this weapon cools before it fires again. Fire in bursts and watch its bar',
  shieldUp: 'Your arm shield blocks from the front only while you hold its key, and drains EN',
};
const STREAK_TEXT = {
  radar: ' KILL STREAK: RADAR PING. Every enemy within 6 000 u shows on your radar for 10 s',
  arty: ' KILL STREAK: ARTILLERY READY. Lock an enemy 700 u or more away and six shells fall on it',
  ace: ' KILL STREAK: ACE! +20 % speed and your overdrive refills by itself for 20 s',
};
// the event being handled: 80_chat.js reply() reads it to rank a message (news about other pilots never interrupts a prompt for this one)
let replyCtx = null;
// (a pilot who switched the hints off, a preference kept with the profile, gets none: 70_server.js srvProfileApply)
function onbHint(slot, key, secs) { if (typeof srvHintsOff === 'function' && srvHintsOff(slot)) return false; return typeof ifrHudHint === 'function' && HINTS[key] ? ifrHudHint(slot, key, HINTS[key], secs || 8) : false; }
function onbLater(secs, fn) { featTimers.push({ at: gameTime() + secs, fn }); }
function onbHuman(slot) { const pe = person(slot); return pe && pe.human ? pe : null; }
// a spawn: the loadout card every time (longer the first times), the controls card and the first hints at the start of a session
function onbSpawn(slot) {
  const pe = onbHuman(slot), m = game.mechs.get(slot); if (!pe || !m) return;
  const n = typeof ifrHudCount === 'function' ? ifrHudCount(slot, 'spawns') : 99;
  if (typeof ifrHudLoadout === 'function') ifrHudLoadout(slot, m, n <= ONB.controlSpawns ? ONB.loadoutFirst : ONB.loadoutSecs);
  if (n <= ONB.controlSpawns && typeof ifrHudCard === 'function') ifrHudCard(slot, 'controls', ONB.controlSecs);
  if (n === 1) onbLater(3.5, () => onbHint(slot, 'start', 9));
  // the mode's goal once per mode and session, a little after the drop
  const mode = game.matchFor(slot).mode;
  if (typeof ifrHudHinted === 'function' && !ifrHudHinted(slot, 'mode_' + mode)) onbLater(n === 1 ? ONB.modeHintAfter + 6 : ONB.modeHintAfter, () => {
    const M = game.matchFor(slot); if (!M || M.mode !== mode || typeof ifrHudObjective !== 'function') return;
    const title = String(IFR_HUD_MODE_NAMES[mode] || mode).replace(/\s+CO-OP$/, ''), goal = ifrHudObjective(mode, M);
    ifrHudHint(slot, 'mode_' + mode, title + ': ' + goal, 9);
  });
}
function onbDeath(slot) {
  const pe = onbHuman(slot); if (!pe) return;
  const n = typeof ifrHudCount === 'function' ? ifrHudCount(slot, 'deaths') : 99;
  if (typeof ifrHudCard === 'function') { ifrHudCard(slot, 'loadout', 0); if (n <= ONB.controlDeaths) ifrHudCard(slot, 'controls', ONB.controlSecs); }
  if (n === 1) onbHint(slot, 'death', 8);
}
// per tick for a piloting human (featInput): the first EN stall, the first press of a launcher with no lock, holding Tab for the controls card
function onbInput(pe, input) {
  const m = game.mechs.get(pe.slot); if (!m || !m.alive) return;
  const P = /** @type {any} */ (pe);
  if (m.enStalled > 0) onbHint(pe.slot, 'stall');
  for (let i = 0; i < 4; i++) {
    if (!input.fire[i]) continue;
    const w = m.weapons[i], spec = w && w.w; if (!spec) continue;
    if (spec.type === 'missile') {
      if (spec.multilock) onbHint(pe.slot, 'multilock', 9);
      else if (!(m.lock && m.lock.target >= 0)) onbHint(pe.slot, 'nolock', 9);                                           // nothing in the ring: it fired unguided
      else if (m.lock.stage < (spec.lock === 'hard' ? 2 : 1)) onbHint(pe.slot, 'holdlock', 8);                          // a lock is building: holding waits for it
    } else if (spec.type === 'shield') onbHint(pe.slot, 'shieldUp', 7);
    else if (w.overheat) onbHint(pe.slot, 'heat', 7);
  }
  // Tab held, then released: the controls card (the scoreboard hides the HUD while it is up)
  let tab = false; try { tab = !!pe.pawn.IsInputPressed(KEYS.scores); } catch (err) { tab = false; }
  if (tab) { if (!P.tabAt) P.tabAt = gameTime(); }
  else if (P.tabAt) { if (gameTime() - P.tabAt >= ONB.tabHold && typeof ifrHudCard === 'function') ifrHudCard(pe.slot, 'controls', ONB.tabSecs); P.tabAt = 0; }
}
// every 16th tick: standing in a capture zone for the first time
function onbZones() {
  for (const pe of people.values()) {
    if (!pe.human || pe.status !== 'mech') continue;
    const m = game.mechs.get(pe.slot); if (!m || !m.alive) continue;
    const M = game.matchFor(pe.slot); if (!M || !M.points || !(M.mode === 'cq' || M.mode === 'kh' || M.mode === 'so')) continue;
    for (const p of M.points) if (p && p.pos && Math.hypot(m.pos.x - p.pos.x, m.pos.y - p.pos.y) <= (p.radius || 700) && Math.abs(m.pos.z - p.pos.z) < 800 && p.owner !== m.team) { onbHint(pe.slot, 'zone', 7); break; }
  }
}
function onbEvent(ev) {
  switch (ev.t) {
    case 'spawn': onbSpawn(ev.slot); break;
    case 'death': onbDeath(ev.slot); break;
    case 'stagger': if (onbHuman(ev.slot)) onbHint(ev.slot, 'stagger', 8); break;
    case 'lock': {
      if (!onbHuman(ev.slot)) break;
      const m = game.mechs.get(ev.slot), msl = !!(m && m.weapons.some((w) => w.w && w.w.type === 'missile' && !w.w.multilock));
      if (ev.stage === 1) onbHint(ev.slot, 'lock', 8); else if (ev.stage === 2 && msl) onbHint(ev.slot, 'hard', 6);
      break;
    }
    default: break;
  }
}

function featHumansNear(pos, fn) {
  for (const pe of people.values()) {
    if (!pe.human) continue;
    const m = game.mechs.get(pe.slot); if (!m || vdist(m.pos, pos) > 14000) continue;
    fn(pe);
  }
}

// the keys: both shoulder buttons (RELOAD + USE, R + E) pressed TOGETHER and held; !od presses it for ~0.7 s. The core needs it held
// 0.6 s and a full meter. It used to need JUMP as well (11 Nov 2026, skink52: "difficult to position when forced to hold space
// (which is jump)"); that still works. Together = both went down within OD_CHORD ticks of each other, so a missile lock held on R
// with a shield raised on E later is not an overdrive. While the meter is full, a lone fresh shoulder press is held back for those
// ticks (0.12 s) so that the first key of the chord does not fire its weapon.
const OD_CHORD = 8;
function featInput(pe, input) {
  traitInput(pe, input);
  const st = /** @type {any} */ (pe).odc || ((/** @type {any} */ (pe)).odc = { p2: false, p3: false, d2: -99, d3: -99, chord: false });
  const f2 = !!input.fire[2], f3 = !!input.fire[3];
  if (f2 && !st.p2) st.d2 = ifrTickNo;
  if (f3 && !st.p3) st.d3 = ifrTickNo;
  st.p2 = f2; st.p3 = f3;
  if (!(f2 && f3)) st.chord = false; else if (!st.chord && Math.abs(st.d2 - st.d3) <= OD_CHORD) st.chord = true;
  const m = game ? game.mechs.get(pe.slot) : null, full = !!m && m.alive && m.overdrive >= 1 && !m.odPhase;
  if (full && !st.chord) {
    if (f2 && !f3 && ifrTickNo - st.d2 < OD_CHORD) input.fire[2] = false;
    if (f3 && !f2 && ifrTickNo - st.d3 < OD_CHORD) input.fire[3] = false;
  }
  input.od = !!((full && st.chord) || (input.jump && f2 && f3) || (/** @type {any} */ (pe).odChat > ifrTickNo));
  guard('onboarding', () => onbInput(pe, input));
}
function featChatOd(slot) {
  const pe = person(slot); if (!pe) return;
  const m = game.mechs.get(slot);
  if (!m || !m.alive) { reply(slot, 'No mech to overdrive'); return; }
  if (!(m.overdrive >= 1)) { reply(slot, 'OVERDRIVE ' + Math.round((m.overdrive || 0) * 100) + ' %: deal and take damage to fill the gold bar', 5); return; }
  /** @type {any} */ (pe).odChat = ifrTickNo + 48;
}

// crate prop: a pooled prop at the crate position (fall height raised), slow spin
function featCratePlace(p, o) {
  propModel(p, FX_MODELS.crate || FX_MODELS.placeholder || NULL_MODEL);
  propScale(p, 1);
  const z = o.pos.z + (o.state === 'fall' ? (o.fall || 0) : 0);
  propPlace(p, v3(o.pos.x, o.pos.y, z), { pitch: o.state === 'fall' ? Math.sin(ifrTickNo * 0.05) * 6 : 0, yaw: o.state === 'fall' ? (ifrTickNo * 3) % 360 : 20, roll: 0 });
}

// radar ping (killstreak 3): enemies within 6000 of a pinging mech show as bounty markers; so do enemies a Sandviper of my team
// marked (Spotter trait, m.markT / m.markTeam from src/core/87_traits.js), at any range
function featPinged(me, o) {
  if (me && o.markT > 0 && o.markTeam === me.team && o.team !== me.team) return true;
  return !!(me && me.radarT > 0 && o.team !== me.team && vdist(me.pos, o.pos) < 6000);
}

function featTick() {
  replyCtx = null;                // the tick's events are done: messages from here on are not part of one
  guard('objectives', objTick);   // the objective world markers (below)
  if ((ifrTickNo & 15) === 8) guard('onboarding zones', onbZones);
  const now = gameTime();
  for (let i = featTimers.length - 1; i >= 0; i--) if (now >= featTimers[i].at) { const t = featTimers.splice(i, 1)[0]; guard('feat timer', t.fn); }
  // the falling crate: a spark every few ticks along its fall
  for (const o of game.effects) {
    if (!o.alive || o.kind !== 'crate') continue;
    if (o.state === 'fall' && (ifrTickNo % 6) === 0) pfxBurst('spark', v3(o.pos.x, o.pos.y, o.pos.z + (o.fall || 0) + 60), 0.5);
    else if (o.state === 'ground' && (ifrTickNo % 96) === 0) pfxBurst('spark', v3(o.pos.x, o.pos.y, o.pos.z + 120), 0.6);   // a glint so it can be found
  }
  // overdrive ready line once per charge
  if ((ifrTickNo & 15) === 0) {
    for (const pe of people.values()) {
      if (!pe.human) continue;
      const m = game.mechs.get(pe.slot); if (!m) continue;
      let st = featState.get(pe.slot); if (!st) { st = { full: false }; featState.set(pe.slot, st); }
      const full = m.alive && m.overdrive >= 1 && !m.odPhase;
      if (full && !st.full) { if (!onbHint(pe.slot, 'od', 9)) reply(pe.slot, HINTS.odAgain, 5, false, 2); sndTone(pe.slot, 'ui_capture'); }
      st.full = full;
    }
  }
}

function featEvent(ev) {
  replyCtx = ev;
  guard('onboarding', () => onbEvent(ev));
  if (ev.t === 'flag' || ev.t === 'capture') guard('obj event', () => objEvent(ev));
  switch (ev.t) {
    case 'overdrive': {
      if (!ev.pos) break;
      const c = v3(ev.pos.x, ev.pos.y, ev.pos.z + 120);
      if (ev.phase === 'charge') {
        pfxBurst('spark', c, 1.2); sndAt('boom_small', ev.pos, true);
        for (let k = 1; k <= 3; k++) featTimers.push({ at: gameTime() + 0.35 * k, fn: () => { const m = game.mechs.get(ev.slot); if (m && m.alive) pfxBurst('spark', v3(m.pos.x, m.pos.y, m.pos.z + 100 + 40 * k), 0.5); } });
        camKick(ev.slot, 10, 6, 0); reply(ev.slot, 'OVERDRIVE CHARGING: the blast comes in 1.2 s, stay close to them', 2);
      } else {
        for (const d of [[0, 0], [260, 0], [-260, 0], [0, 260], [0, -260]]) pfxBurst('gboom', v3(c.x + d[0], c.y + d[1], c.z), 3);
        pfxBurst('spark', c, 1.0); sndAt('boom_large', ev.pos, true);
        explodeShake(ev.pos, 1400); camKick(ev.slot, 120, -60, 0);
        featHumansNear(ev.pos, (pe) => { if (pe.slot !== ev.slot) reply(pe.slot, nameOf(ev.slot) + ' used OVERDRIVE', 2); });
      }
      break;
    }
    case 'crate': {
      const p = ev.pos; if (!p) break;
      if (ev.phase === 'drop') featHumansNear(p, (pe) => reply(pe.slot, 'SUPPLY DROP INBOUND', 4));
      else if (ev.phase === 'land') { pfxBurst('boom', p, 2); explodeShake(p, 120); featHumansNear(p, (pe) => { if (!onbHint(pe.slot, 'crate', 8)) reply(pe.slot, 'SUPPLY CRATE LANDED: walk into it', 4); }); }
      else if (ev.phase === 'take') {
        pfxBurst('spark', v3(p.x, p.y, p.z + 100), 0.8);
        reply(ev.slot, 'SUPPLY CRATE: ' + (CRATE_TEXT[ev.kind] || ev.kind), 5);
        featHumansNear(p, (pe) => { if (pe.slot !== ev.slot) reply(pe.slot, nameOf(ev.slot) + ' took the supply crate', 3); });
      }
      break;
    }
    case 'streak': {
      const s = ev.slot;
      // what was earned, what it does and how it is used, every time (10 Nov 2026 evening playtest: "what killstreaks do, or how to use any of them")
      if (ev.kind === 'radar') { reply(s, ev.streak + STREAK_TEXT.radar, 7); sndTone(s, 'ui_capture'); }
      else if (ev.kind === 'arty') { reply(s, ev.streak + STREAK_TEXT.arty, 8); sndTone(s, 'ui_capture'); }
      else if (ev.kind === 'ace') {
        reply(s, ev.streak + STREAK_TEXT.ace, 8); sndTone(s, 'ui_capture');
        for (const pe of people.values()) if (pe.human && pe.slot !== s && game.sameArena(pe.slot, s)) reply(pe.slot, nameOf(s) + ' is an ACE', 4);
      } else if (ev.kind === 'arty_fire') {
        reply(s, 'ARTILLERY INBOUND', 3);
        if (ev.pos) featHumansNear(ev.pos, (pe) => { if (pe.slot !== s) reply(pe.slot, 'INCOMING ARTILLERY', 3); });
      }
      break;
    }
    case 'shell': {
      if (!ev.pos) break;
      const at = gameTime() + Math.max(0, (ev.delay || 1) - 0.5), p = ev.pos;
      featTimers.push({ at, fn: () => pfxBurst('spark', v3(p.x, p.y, p.z + 900), 0.4) });
      break;
    }
    default: break;
  }
}

// ===================================================================================================================
// Objective world markers (10 Nov 2026 playtest: "not much indication of what mode is playing ... zones and capture progress
// more obvious"). The core keeps the state (src/core/85_objectives.js); this draws it with pooled self-lit props
// (tools/objective_fx.py models, cached in the map by tools/patch_cache.py; the stock fx models stand in until the map has them):
//   zone (Conquest points, the KOTH hill, the Sortie beacon): a ground ring at the radius in the owner colour (white flash
//     while contested), a progress arc inside it in the capturing team's colour (NN/20 of the circle), a light column whose
//     visible height is the progress (sunk into the ground), and the zone letter turning 1300 u up (above the map's
//     letter mast, tools/arenas/objectives.py). KOTH: the next hill shows its
//     letter, and its ring blinks in the last IF_OBJ.khWarn s before the move.
//   flag (CTF): the team-coloured flag on its stand / where it was dropped / over its carrier, a column over it (blinking white
//     while carried, so the carrier is seen from across the map) and the home ring (the capture spot).
// Server mode: the live state goes to the SlimeMG plugin as `echo ifr_obj <copy> ...` (SERVER_CONTRACT.md section 7); when the
// plugin answers RunScriptInput ifr_objdraw it draws beam rings / columns / arcs at the map's markers, and the script keeps only
// the letters and the flags (no doubled rings). Props: at most 4 per zone and 3 per flag (about 20 per arena copy).
// ===================================================================================================================
const OBJ_CFG = { on: true, colH: 3000, letterUp: 1300, flagColUp: 470, letterScale: 2, ringZ: 4, arcSteps: 20, flagRing: 2.6, echoGap: 0.25, refresh: 5, minCol: 0.08 };
const OBJ_KEYS = (() => {
  const k = [];
  for (const c of ['n', 't', 'ct', 'w']) k.push('obj_ring_' + c, 'obj_col_' + c);
  for (const c of ['t', 'ct']) { k.push('obj_flag_' + c); for (let i = 1; i <= 20; i++) k.push('obj_arc_' + c + '_' + (i < 10 ? '0' : '') + i); }
  for (const l of ['a', 'b', 'c', 'd', 'e']) for (const c of ['n', 't', 'ct']) k.push('obj_letter_' + l + '_' + c);
  return k;
})();
let objHave = /** @type {Set<string>|null} */ (null), objHaveKey = '';
let objPlugin = false;                 // the plugin draws the beams (RunScriptInput ifr_objdraw)
const objVis = new Map();              // visual key -> {p: Prop, pos, yaw, pitch, seen}
let objFrame = 0;
const objSent = new Map();             // echo key -> {s: last state string, at: time}
const objMode = new Map();             // arena copy -> mode last announced ('' after end)

function objModel(key) { return 'models/ifr/fx/obj/' + key + '.vmdl'; }
function objHas(key) { return !!(objHave && objHave.has(key)); }
// which objective models the map caches (a prop named ifr_cache_<key> in the cache room); re-read every round (entities are recreated)
function objCheckModels() {
  objHave = new Set(); for (const k of OBJ_KEYS) if (ifrFind('ifr_cache_' + k)) objHave.add(k);
  if (!objHave.size) warnOnce('objfx', 'no objective marker models cached in the map (tools/patch_cache.py): zones drawn with the stock fx models');
}
const objTeam = (t) => (t === TEAM_T ? 't' : t === TEAM_CT ? 'ct' : 'n');
const objOff = () => objPlugin && serverMode;

// one prop per visual key, change-only updates
function objShow(key, model, pos, yaw, scale, pitch) {
  if (!model) return;
  let v = objVis.get(key);
  if (v && !live(v.p.ent)) { objVis.delete(key); v = undefined; }
  if (!v) { const p = takeProp(); if (!p) return; v = { p, pos: null, yaw: 0, pitch: 0, seen: 0 }; objVis.set(key, v); }
  v.seen = objFrame;
  propModel(v.p, model);
  propScale(v.p, scale);
  const pt = pitch || 0;
  if (!v.pos || Math.abs(v.pos.x - pos.x) + Math.abs(v.pos.y - pos.y) + Math.abs(v.pos.z - pos.z) > 1 || Math.abs(v.yaw - yaw) > 0.5 || v.pitch !== pt) {
    propPlace(v.p, pos, { pitch: pt, yaw, roll: 0 }); v.pos = v3(pos.x, pos.y, pos.z); v.yaw = yaw; v.pitch = pt;
  }
}
function objSweep() { for (const [k, v] of objVis) if (v.seen !== objFrame) { releaseProp(v.p); objVis.delete(k); } }

// the column: a 3000 u light sunk so `frac` of it shows (fallback: the laser beam model pointed up, scaled to the height)
function objColumn(key, c, pos, frac, flash) {
  const cc = flash ? 'w' : c, f = Math.max(OBJ_CFG.minCol, Math.min(1, frac));
  if (objHas('obj_col_' + cc)) { objShow(key, objModel('obj_col_' + cc), v3(pos.x, pos.y, pos.z - OBJ_CFG.colH * (1 - f)), 0, 1); return; }
  const m = c === 'ct' ? FX_MODELS.beam : c === 't' ? (FX_MODELS.beam_red || FX_MODELS.beam) : (FX_MODELS.tracer || FX_MODELS.beam);
  objShow(key, m, pos, 0, Math.max(1, OBJ_CFG.colH * 0.6 * f / 100), -90);
}
function objRing(key, c, pos, radius) {
  if (objHas('obj_ring_' + c)) objShow(key, objModel('obj_ring_' + c), v3(pos.x, pos.y, pos.z + OBJ_CFG.ringZ), 0, Math.max(0.3, radius / 100));
  else if (FX_MODELS.landing) objShow(key, FX_MODELS.landing, v3(pos.x, pos.y, pos.z + OBJ_CFG.ringZ), 0, Math.max(0.3, radius / 118));
}
function objLetter(key, id, c, pos, scale) {
  const k = 'obj_letter_' + String(id || 'a').toLowerCase() + '_' + c;
  const yaw = (ifrTickNo * 1.2) % 360, z = pos.z + OBJ_CFG.letterUp + Math.sin(ifrTickNo * 0.04) * 20;
  if ((ifrTickNo & 1) && objVis.has(key)) { objVis.get(key).seen = objFrame; return; }   // turn every 2nd tick
  if (objHas(k)) objShow(key, objModel(k), v3(pos.x, pos.y, z), yaw, scale);
  else { const m = c === 'ct' ? FX_MODELS.iff_ct : c === 't' ? FX_MODELS.iff_t : FX_MODELS.iff; objShow(key, m || FX_MODELS.iff, v3(pos.x, pos.y, z), yaw, scale * 2.5); }
}

// a zone: p = core point {id, pos, radius, owner, value, progress, capTeam, contested}
function objZone(key, p, opts) {
  const pos = p.pos, own = objTeam(p.owner), cap = objTeam(p.capTeam), prog = Math.max(0, Math.min(1, p.progress || 0));
  const flash = !!p.contested && ((ifrTickNo >> 3) & 1) === 1;
  const lc = own !== 'n' ? own : (prog > 0.02 ? cap : 'n');
  objLetter(key + 'L', p.id, lc, pos, OBJ_CFG.letterScale * (opts.big ? 1.25 : 1));
  if (opts.letterOnly) { if (opts.blink && ((ifrTickNo >> 4) & 1) && !objOff()) objRing(key + 'R', 'n', pos, p.radius); return; }
  if (objOff()) return;                          // the plugin's beams draw ring, arc and column
  objRing(key + 'R', flash ? 'w' : own, pos, p.radius * (flash ? 1.03 : 1));
  if (prog > 0.02 && cap !== 'n') {
    const n = Math.max(1, Math.min(OBJ_CFG.arcSteps, Math.ceil(prog * OBJ_CFG.arcSteps - 1e-6))), k = 'obj_arc_' + cap + '_' + (n < 10 ? '0' : '') + n;
    if (objHas(k)) objShow(key + 'A', objModel(k), v3(pos.x, pos.y, pos.z + OBJ_CFG.ringZ + 2), 0, Math.max(0.3, p.radius / 100));
  }
  objColumn(key + 'C', own !== 'n' ? own : (prog > 0.02 ? cap : 'n'), pos, own !== 'n' ? prog : (prog > 0.02 ? prog : 1), flash);
}

// a flag: f = core flag {team, home, pos, state, carrier}
function objFlag(key, f) {
  const c = objTeam(f.team), real = objHas('obj_flag_' + c);
  const mdl = real ? objModel('obj_flag_' + c) : (c === 'ct' ? FX_MODELS.iff_ct : FX_MODELS.iff_t), scale = real ? 1 : 3;
  if (f.state === 'carried') {
    const m = game.mechs.get(f.carrier);
    const pos = m ? v3(m.pos.x, m.pos.y, m.pos.z + (m.height || 288) + 20) : f.pos;
    objShow(key + 'F', mdl, pos, m ? m.legYaw + 180 : 0, scale * 0.8);
    if (!objOff()) objColumn(key + 'C', c, v3(pos.x, pos.y, pos.z + OBJ_CFG.flagColUp), 1, ((ifrTickNo >> 4) & 1) === 1);
  } else {
    const pos = v3(f.pos.x, f.pos.y, f.pos.z + (f.state === 'dropped' ? 20 + Math.sin(ifrTickNo * 0.08) * 20 : 0));
    const home = f.state !== 'dropped', yaw = home ? Math.atan2(-f.home.y, -f.home.x) * 180 / Math.PI + 90 : (ifrTickNo * 3) % 360;   // on the stand: banner across the line to the centre; dropped: spins
    objShow(key + 'F', mdl, pos, yaw, scale);
    if (!objOff()) objColumn(key + 'C', c, v3(f.pos.x, f.pos.y, f.pos.z + OBJ_CFG.flagColUp), 1, f.state === 'dropped' && ((ifrTickNo >> 3) & 1) === 1);   // starts over the flag
  }
  if (!objOff()) objRing(key + 'H', c, f.home, 100 * OBJ_CFG.flagRing);
}

function objTick() {
  if (!OBJ_CFG.on || !game) return;
  const list = game.list || [{ g: game, k: 0, active: true }];
  const rk = list.map((a) => (a.active ? a.g.match.mode + a.g.match.phase : '')).join('|');
  if (!objHave || objHaveKey !== rk) { objCheckModels(); objHaveKey = rk; }
  objFrame++;
  for (const a of list) {
    const M = a.g.match; if (!a.active || !M) continue;
    const on = M.phase === 'running' || M.phase === 'warmup';
    if (serverMode) guard('obj echo', () => objEcho(a.k, M, on));
    if (!on) continue;
    const pre = 'o' + a.k + '_';
    if (M.mode === 'cq') M.points.forEach((p, i) => objZone(pre + 'p' + i, p, {}));
    else if (M.mode === 'so' && M.points.length) objZone(pre + 'p0', M.points[0], {});
    else if (M.mode === 'kh' && M.points.length) {
      objZone(pre + 'hill', M.points[0], { big: true });
      const nx = (M.allPoints || [])[M.hillNext];
      if (nx && nx !== M.points[0]) objZone(pre + 'next', nx, { letterOnly: true, blink: (M.hillLeft === undefined ? 99 : M.hillLeft) <= IF_OBJ.khWarn });
    } else if (M.mode === 'ctf' && M.flags) for (const t of [2, 3]) objFlag(pre + 'f' + t, M.flags[t]);
  }
  objSweep();
}

// ---- the plugin channel (server mode only): `echo ifr_obj <copy> mode|pt|flag|end ...`, change-only, at most 4 a second per item,
// every item again after OBJ_CFG.refresh s
function objSend(key, state, line) {
  const now = gameTime(), s = objSent.get(key);
  if (s && ((s.s === state && now - s.at < OBJ_CFG.refresh) || now - s.at < OBJ_CFG.echoGap)) return;
  objSent.set(key, { s: state, at: now });
  ifrCmd('echo ifr_obj ' + line);
}
function objForget(copy) { for (const key of Array.from(objSent.keys())) if (key.startsWith(copy + ':')) objSent.delete(key); }
function objEcho(k, M, on) {
  const copy = k + 1, prev = objMode.get(k) || '';
  if (!on) { if (prev) { objMode.set(k, ''); ifrCmd('echo ifr_obj ' + copy + ' end'); objForget(copy); } return; }
  if (prev !== M.mode) { objMode.set(k, M.mode); ifrCmd('echo ifr_obj ' + copy + ' mode ' + M.mode); objForget(copy); }
  const pt = (p, active) => {
    const st = (active ? 1 : 0) + ' ' + (p.owner | 0) + ' ' + (p.capTeam | 0) + ' ' + Math.round((p.progress || 0) * 20) * 5 + ' ' + (p.contested ? 1 : 0) + ' ' + (p.nT | 0) + ' ' + (p.nCT | 0);
    objSend(copy + ':pt' + p.id, st, copy + ' pt ' + p.id + ' ' + st);
  };
  if (M.mode === 'cq') for (const p of M.points) pt(p, true);
  else if (M.mode === 'so' && M.points.length) pt(M.points[0], true);
  else if (M.mode === 'kh') for (const p of (M.allPoints || [])) pt(p, M.points[0] === p);
  else if (M.mode === 'ctf' && M.flags) for (const t of [2, 3]) {
    const f = M.flags[t], q = (v) => Math.round(v / 150);
    const st = f.state + ' ' + (f.state === 'home' ? '' : q(f.pos.x) + ',' + q(f.pos.y) + ',' + q(f.pos.z)) + ' ' + f.carrier;
    objSend(copy + ':flag' + t, st, copy + ' flag ' + (t === TEAM_T ? 't' : 'ct') + ' ' + f.state + ' ' + Math.round(f.pos.x) + ' ' + Math.round(f.pos.y) + ' ' + Math.round(f.pos.z) + ' ' + f.carrier);
  }
}
function onObjDrawInput() {
  if (!objPlugin) log('objective zones: the server plugin draws them (script rings and columns off)');
  objPlugin = true; objSent.clear(); objMode.clear();      // resend everything
}
Instance.OnScriptInput('ifr_objdraw', () => guard('ifr_objdraw', onObjDrawInput));

// objective events: a burst where it happened
function objEvent(ev) {
  const g = game.list ? (game.list[ev.arena | 0] || game.list[0]).g : game, M = g.match;
  if (ev.t === 'flag' && M.flags) { const f = M.flags[ev.team]; if (f) pfxBurst(ev.action === 'capture' ? 'gboom' : 'spark', v3(f.pos.x, f.pos.y, f.pos.z + 120), ev.action === 'capture' ? 2 : 0.8); }
  else if (ev.t === 'capture') { const p = (M.allPoints && M.allPoints.length ? M.allPoints : M.points).find((q) => q.id === ev.id) || M.points[0]; if (p) pfxBurst('spark', v3(p.pos.x, p.pos.y, p.pos.z + 300), 1.2); }
}
