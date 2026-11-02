// ---------------------------------------------------------------- the HUD (custom_hud_layout)
// panorama/layout/custom_game/space_racer.xml has fixed panels; the script swaps CSS classes (pixel-font glyphs,
// colours, bar widths) and sets dialog variables (standings names) per player. Every change is cached so only real
// changes are sent, and a per-tick budget spreads big updates over a few ticks.
// Speed: each player has one HudSlot holding the class cache plus "memos" of what each part of the HUD was last
// drawn from (the text of a row, the standings list, a dot's cell...). A part whose inputs haven't changed is skipped
// without looking at its panels. A memo is only kept when every change of that part went out (HUD budget), and the
// whole HudSlot is thrown away whenever the HUD is reset, so a memo can never hide a missing change.

let hudEnt;
let hudBudget = Infinity;
let hudCheckedTick = -1;
const hudSlots = new Map();    // slot -> HudSlot

class HudSlot {
  constructor() {
    this.c = new Map();        // class slot key -> class (or dialog variable key -> text)
    this.rows = new Map();     // text row id -> { t, c, f } last drawn
    this.stand = null; this.standMe = -2;          // standings list object + the watched slot
    this.resMe = null; this.resRank = null; this.resKey = '';   // results board
    this.posKey = NaN; this.posOf = NaN; this.tallyT = NaN; this.tallyCT = NaN; this.lapKey = NaN; this.best = NaN;
    this.dots = new Int32Array(MAX_DOTS + 2).fill(-1);   // per dot: packed x / y / colour / shown (-1 = unknown)
    this.optCrt = null; this.optHelp = null;
    this.picker = null;
    this.vote = null; this.voteVer = -1; this.voteKey = '';   // the ballot on screen, its version, the voter's pick
  }
}

// once per server tick (and when it is found again): the custom_hud_layout entity
function hud() {
  if (hudEnt && hudCheckedTick === tickNo) return hudEnt;
  if (live(hudEnt)) { hudCheckedTick = tickNo; return hudEnt; }
  hudEnt = live(Instance.FindEntityByName(CONFIG.HUD));
  if (!hudEnt) { warnOnce('hud', 'no custom_hud_layout named ' + CONFIG.HUD + ' - no HUD'); return hudEnt; }
  hudCheckedTick = tickNo;
  for (const slot of hudSlots.keys()) { try { hudEnt.ResetForPlayer(slot); } catch (err) { /* ignore */ } }
  hudSlots.clear();
  return hudEnt;
}

function hslot(slot) {
  let s = hudSlots.get(slot);
  if (!s) { s = new HudSlot(); hudSlots.set(slot, s); }
  return s;
}
// animation flips and the minimap's quarter turn: kept per slot for as long as the map runs (not reset with the HUD)
const popKeep = new Map();
function pkeep(slot) {
  let k = popKeep.get(slot);
  if (!k) { k = { pop: new Map(), posCar: -1, pos: 99, posFlip: false, dotTurn: 0 }; popKeep.set(slot, k); }
  return k;
}

// class slot keys for (panel, group), made once per pair so the hot path never builds strings
const GKEYS = new Map();
function gkey(panel, group) {
  let m = GKEYS.get(group);
  if (!m) { m = new Map(); GKEYS.set(group, m); }
  let k = m.get(panel);
  if (k === undefined) { k = panel + '#' + group; m.set(panel, k); }
  return k;
}

// one class "slot" per panel: swapping replaces the previous class in that slot
function hudSwapK(hs, slot, panel, key, cls) {
  const c = hs.c;
  const old = c.get(key);
  if (old === cls) return true;
  if (old === undefined && cls === null) { c.set(key, null); return true; }    // nothing there yet: nothing to send
  if (hudBudget <= 0) return false;
  const h = hud();
  if (!h) return false;
  if (hudSlots.get(slot) !== hs) return false;    // the HUD was reset while drawing: the next update starts clean
  hudBudget -= old && cls ? 2 : 1;
  if (old) h.SetHasClassForPlayer(slot, panel, old, false);
  if (cls) h.SetHasClassForPlayer(slot, panel, cls, true);
  c.set(key, cls);
  return true;
}
function hudSwap(slot, panel, cls, group) {
  return hudSwapK(hslot(slot), slot, panel, group ? gkey(panel, group) : panel, cls);
}

const VAR_KEYS = new Map();
function hudVar(slot, panel, text) {
  const hs = hslot(slot), c = hs.c;
  let key = VAR_KEYS.get(panel);
  if (key === undefined) { key = panel + '$'; VAR_KEYS.set(panel, key); }
  text = String(text === undefined || text === null ? '' : text);
  if (c.get(key) === text) return true;
  if (hudBudget <= 0) return false;
  const h = hud();
  if (!h) return false;
  if (hudSlots.get(slot) !== hs) return false;
  hudBudget--;
  h.SetDialogVariableStringForPlayer(slot, panel, 'v', text);
  c.set(key, text);
  return true;
}

// pixel text: a row of glyph panels (<id>_0 .. <id>_n-1); each gets the class g<char code>, the row a colour class.
// Characters the font lacks show as '?'; only the characters that change are sent.
const GLYPH_OK = new Set(HUD_TEXT.charset.split(''));
const TEXT_COLOR = { gold: 'cY', red: 'cR', green: 'cG', cyan: 'cC', pink: 'cP', white: 'cW' };
const GLYPH_CLS = new Map();
function glyphClass(ch) {
  if (ch === undefined) return null;
  let g = GLYPH_CLS.get(ch);
  if (g === undefined) {
    const u = ch.toUpperCase();
    g = 'g' + (GLYPH_OK.has(u) ? u : '?').charCodeAt(0);
    GLYPH_CLS.set(ch, g);
  }
  return g;
}
const SLOT_IDS = {};
const ROWS = {};               // row id -> { ids, align, colKey, fxKey }
for (const id in HUD_TEXT.slots) {
  SLOT_IDS[id] = [];
  for (let k = 0; k < HUD_TEXT.slots[id]; k++) SLOT_IDS[id].push(id + '_' + k);
  ROWS[id] = { ids: SLOT_IDS[id], align: HUD_TEXT.align ? HUD_TEXT.align[id] : 'left', colKey: gkey(id, 'col'), fxKey: gkey(id, 'fx') };
}
const tooLong = new Set();
function hudText(slot, id, text, color, fx) {
  const R = ROWS[id];
  if (!R) return;
  text = String(text === undefined || text === null ? '' : text);
  const hs = hslot(slot);
  const cn = color || '', fn = fx || '';
  // the whole row is remembered: nothing to do when it shows this already
  let m = hs.rows.get(id);
  if (m && m.t === text && m.c === cn && m.f === fn) return;
  const ids = R.ids, n = ids.length;
  let t = text;
  if (t.length > n) {
    // (said once per line in the console: a line that doesn't fit is a bug to fix, e.g. the bottom line is 38 wide so
    // it stays clear of CS2's chat)
    if (!tooLong.has(id + t)) { tooLong.add(id + t); log(`WARNING: HUD text too long for ${id} (${n}): ${t}`); }
    t = t.slice(0, n);
  }
  // the row has a fixed number of cells: centre or right-align by padding
  let pad = 0;
  if (R.align === 'center') pad = Math.floor((n - t.length) / 2);
  else if (R.align === 'right') pad = n - t.length;
  let ok = true;
  for (let k = 0; k < n; k++) {
    const j = k - pad;
    const ch = j >= 0 && j < t.length ? t[j] : ' ';
    if (!hudSwapK(hs, slot, ids[k], ids[k], ch !== ' ' ? glyphClass(ch) : null)) ok = false;
  }
  if (color !== undefined && !hudSwapK(hs, slot, id, R.colKey, TEXT_COLOR[color] || color || null)) ok = false;
  if (!hudSwapK(hs, slot, id, R.fxKey, fx || null)) ok = false;
  if (!ok) { if (m) hs.rows.delete(id); return; }    // (a row cut short by the budget is finished on a later tick)
  if (!m) { m = { t: '', c: '', f: '' }; hs.rows.set(id, m); }
  m.t = text; m.c = cn; m.f = fn;
}
// a pop (scale-in) each time a row shows something new: the class alternates pop / pop2 (two copies of the same
// animation) because Panorama only replays an animation when its name changes
function popFx(slot, row, key) {
  const pop = pkeep(slot).pop;
  let st = pop.get(row);
  if (!st) { st = { key: null, flip: false }; pop.set(row, st); }
  if (st.key !== key) { st.key = key; st.flip = !st.flip; }
  return st.flip ? 'pop2' : 'pop';
}

// a centre message: short ones big, long ones in the smaller row; new messages pop in, warnings blink
const CTR_BIG = HUD_TEXT.slots.spr_ctr || 20;
function hudCenter(slot, text, cls) {
  text = text || '';
  const big = text.length <= CTR_BIG;
  const color = cls ? TEXT_COLOR[cls] || 'cW' : 'cW';
  const fx = cls === 'red' && /WRONG|MISSED/.test(text) ? 'blink' : text ? popFx(slot, 'c', text) : null;
  hudText(slot, 'spr_ctr', big ? text : '', color, big ? fx : null);
  hudText(slot, 'spr_ctr2', big ? '' : text, color, big ? null : fx);
}

function hudReset(slot) {
  hudSlots.delete(slot);
  const h = hud();
  if (h) { try { h.ResetForPlayer(slot); } catch (err) { /* ignore */ } }
}

// state classes on spr_root all start with "st" (stOn, stLobby, stPick, stHelp, stRes, stSpec, stBoost): a state
// class must never share its name with a panel's class, or the root picks up that panel's layout
const ROOT_GROUPS = ['on', 'lobby', 'pick', 'help', 'res', 'spec', 'boost', 'vote'];
const RK = {};
for (const g of ROOT_GROUPS) RK[g] = gkey('spr_root', g);
function rootSwap(hs, slot, group, cls) { return hudSwapK(hs, slot, 'spr_root', RK[group], cls); }
function hudOff(slot) {
  const hs = hslot(slot);
  for (const g of ROOT_GROUPS) rootSwap(hs, slot, g, null);
  hs.picker = null; hs.optHelp = null; hs.vote = null;     // their root classes are gone: redraw them next time
}

const W_CLS = [];
for (let k = 0; k <= 20; k++) W_CLS.push('w' + k);
function pct(v, max) { return W_CLS[clamp(Math.round(v / Math.max(1, max) * 20), 0, 20)]; }

// the car picker: four cards, the chosen one highlighted; pictures in the player's side colour.
// show: true / 'big' = the big cards (lobby, watching), 'mini' = the small row along the bottom (grid flyover),
// false = none
const CARD = CAR_KEYS.map((_, i) => ({ card: 'spr_card' + i, img: 'spr_cimg' + i, mcard: 'spr_mcard' + i, mimg: 'spr_mimg' + i }));
const PIC = {};
for (const k of CAR_KEYS) PIC[k] = { t: 'pic_' + k + '_t', ct: 'pic_' + k + '_ct', neutral: 'pic_' + k + '_neutral' };
function hudPicker(slot, pe, show) {
  const mini = show === 'mini';
  pe.pickShown = !!show;                 // A / D change the car only while the cards are up
  const hs = hslot(slot);
  const side = pe.csTeam === 2 ? 't' : pe.csTeam === 3 ? 'ct' : 'neutral';
  const key = show ? (mini ? 'm' : 'b') + side + pe.carChoice : '';
  if (hs.picker === key) return;
  let ok = rootSwap(hs, slot, 'pick', show ? (mini ? 'stPickMini' : 'stPick') : null);
  if (show) {
    for (let i = 0; i < CAR_KEYS.length; i++) {
      const k = CAR_KEYS[i], cd = CARD[i];
      if (!hudSwapK(hs, slot, mini ? cd.mcard : cd.card, mini ? cd.mcard : cd.card, pe.carChoice === k ? 'sel' : null)) ok = false;
      if (!hudSwapK(hs, slot, mini ? cd.mimg : cd.img, mini ? cd.mimg : cd.img, PIC[k][side])) ok = false;
    }
  }
  hs.picker = ok ? key : null;
}

// minimap: the track picture is 48 x 48 big pixels; dots snap to them. x / y position classes for a track-local point
const MM_CELLS = HUD_TEXT.mm_cells || 48;
const MAX_DOTS = HUD_TEXT.max_dots || 32;
const X_CLS = [], Y_CLS = [];
for (let k = 0; k < MM_CELLS; k++) { X_CLS.push('x' + k); Y_CLS.push('y' + k); }
const DOT_COL = [null, 'Out', 'T', 'CT'];          // index 0 = no colour class
const DOTS = [];                                  // panel names and class slot keys per dot
for (let k = 0; k < MAX_DOTS; k++) DOTS.push(dotPanels('spr_md' + k, 'spr_mdy' + k));
const DOT_LEAD = dotPanels('spr_ldot', 'spr_ldoty'), DOT_ME = dotPanels('spr_dot', 'spr_doty');
function dotPanels(outer, inner) { return { outer, inner, xk: gkey(outer, 'x'), yk: gkey(inner, 'y'), ck: gkey(inner, 'col'), ok: gkey(outer, 'on') }; }
function dotCell(track, v, isY) {
  const mm = track.mm, half = mm.size / 2;
  const p = isY ? half - v * mm.scale : half + v * mm.scale;
  return clamp(Math.floor(p / mm.size * MM_CELLS), 0, MM_CELLS - 1);
}
function dotCells(track, x, y) { return [dotCell(track, x, false), dotCell(track, y, true)]; }
// col: 0..3 = DOT_COL index, -1 = leave the colour alone. Remembered per dot as one number.
function hudDot(hs, slot, idx, P, car, track, col, step) {
  let packed;
  if (!car) packed = 0;
  else {
    let cx = dotCell(track, car.x, false), cy = dotCell(track, car.y, true);
    if (step > 1) { cx -= cx % step; cy -= cy % step; }
    packed = 1 + cx * 4 + cy * 256 + (col + 1) * 65536;
    if (hs.dots[idx] === packed) return;
    let ok = hudSwapK(hs, slot, P.outer, P.xk, X_CLS[cx]);
    if (!hudSwapK(hs, slot, P.inner, P.yk, Y_CLS[cy])) ok = false;
    if (col >= 0 && !hudSwapK(hs, slot, P.inner, P.ck, DOT_COL[col])) ok = false;
    if (!hudSwapK(hs, slot, P.outer, P.ok, 'On')) ok = false;
    hs.dots[idx] = ok ? packed : -1;
    return;
  }
  if (hs.dots[idx] === packed) return;
  hs.dots[idx] = hudSwapK(hs, slot, P.outer, P.ok, null) ? packed : -1;
}
// every car in the race on the minimap (grid order = dot number), the leader in gold and the watched car blinking
// white on top. To keep the class traffic down the other cars move in 2-pixel steps and a quarter of them is
// refreshed on each HUD update.
// (CONFIG.MINIMAP_DOT_HZ: how often each of those dots is refreshed - the HUD updates 32 times a second, so 8 = a
// quarter of the dots per update, 4 = an eighth)
const DOT_PARTS = Math.max(1, Math.round(32 / Math.max(1, CONFIG.MINIMAP_DOT_HZ || 8)));
const DOT_PER = Math.ceil(MAX_DOTS / DOT_PARTS);
function hudDots(hs, slot, arena, me) {
  const T = arena.track;
  const n = ++pkeep(slot).dotTurn;
  const from = (n % DOT_PARTS) * DOT_PER, to = Math.min(MAX_DOTS, from + DOT_PER), order = arena.order;
  for (let k = from; k < to; k++) {
    const car = order[k];
    const show = car && car !== me && car.visible && !car.left;
    hudDot(hs, slot, k, DOTS[k], show ? car : null, T,
      show ? (car.state === 'wrecked' || car.state === 'finished' ? 1 : car.team === 0 ? 2 : car.team === 1 ? 3 : 0) : -1, 2);
  }
  const lead = arena.ranking[0];
  hudDot(hs, slot, MAX_DOTS, DOT_LEAD, lead && lead !== me && lead.racing ? lead : null, T, -1, 1);
  hudDot(hs, slot, MAX_DOTS + 1, DOT_ME, me && me.visible ? me : null, T, -1, 1);
}

// per-arena values every player's HUD needs, worked out once per server tick
function arenaHud(a) {
  let h = a.hudCache;
  if (!h) { h = a.hudCache = { tick: -1, clock: '', field: 0, mm: 'mm_' + a.track.id }; }
  if (h.tick === tickNo) return h;
  h.tick = tickNo;
  h.clock = a.state === 'grid' ? 'GRID' : a.state === 'over' ? 'RESULTS' : fmtTime(a.raceTic / TICRATE).slice(0, -3);
  let n = 0;
  for (const c of a.order) if (!c.left) n++;
  h.field = n;
  return h;
}

const STAND = [];
for (let i = 0; i < 8; i++) { const p = 'spr_st' + i; STAND.push({ name: 'spr_stn' + i, row: p, side: gkey(p, 'side'), me: gkey(p, 'me') }); }
const MM_KEY = gkey('spr_mmimg', 'map');
function hudRaceCommon(hs, slot, arena, info, car) {
  const ah = arenaHud(arena);
  rootSwap(hs, slot, 'on', 'stOn');
  rootSwap(hs, slot, 'res', arena.state === 'over' ? 'stRes' : null);
  hudSwapK(hs, slot, 'spr_mmimg', MM_KEY, ah.mm);
  hudText(slot, 'spr_clock', info.clock || '', info.clock === 'GRID' || info.clock === 'RESULTS' ? 'cY' : 'cW');
  hudCenter(slot, info.center, info.centerCls);
  hudText(slot, 'spr_sub', info.sub || '', 'cW');
  hudText(slot, 'spr_msg', info.msg || '', 'cC');
  hudSwapK(hs, slot, 'spr_flash', 'spr_flash', info.flash || null);
  // standings (8 rows): the names, their side, and which row is the watched car (the list is shared by everyone in
  // the arena and only rebuilt every STANDINGS_PERIOD)
  const rows = info.rows || [], me = info.me === undefined ? -1 : info.me;
  if (hs.stand !== rows || hs.standMe !== me) {
    let ok = true;
    for (let i = 0; i < 8; i++) {
      const r = rows[i], S = STAND[i];
      if (!hudVar(slot, S.name, r ? r.text : '')) ok = false;
      if (!hudSwapK(hs, slot, S.row, S.side, r ? (r.team === 0 ? 'T' : r.team === 1 ? 'CT' : 'N') : null)) ok = false;
      if (!hudSwapK(hs, slot, S.row, S.me, r && r.slot === me ? 'me' : null)) ok = false;
    }
    hs.stand = ok ? rows : null; hs.standMe = me;
  }
  if (arena.state === 'over') hudResults(hs, slot, arena, car);
}

// the results board: the top 8 (your own line instead of the 8th if you placed lower), with finish times and gaps
const RB = [];
for (let i = 0; i < 8; i++) { const p = 'spr_rb' + i; RB.push({ p: 'spr_rbp' + i, n: 'spr_rbn' + i, t: 'spr_rbt' + i, row: p, side: gkey(p, 'side'), me: gkey(p, 'me'), pod: gkey(p, 'pod') }); }
function hudResults(hs, slot, arena, me) {
  const r = (arena.result && arena.result.ranking) || arena.ranking;
  // redrawn only when the ranking, the watched car or the state of a car on the board changes
  const mine = me ? r.indexOf(me) : -1;
  let key = r.length + '|' + mine + '|' + (me ? me.state + (me.left ? 'L' : '') + (me.finishPos ? 'f' : '') : '') + '|';
  for (let i = 0; i < r.length && i < 8; i++) { const c = r[i]; key += c.slot + c.state + (c.finishPos ? 'f' : '') + (c.left ? 'L' : '') + ','; }
  if (hs.resRank === r && hs.resMe === me && hs.resKey === key) return;
  const rows = r.slice(0, 8);
  if (mine >= 8) rows[7] = me;
  const win = r[0];
  let ok = true;
  for (let i = 0; i < 8; i++) {
    const c = rows[i], B = RB[i];
    const pos = c ? r.indexOf(c) + 1 : 0;
    let time = '';
    if (c) {
      if (c.finishPos) time = c === win || !win || !win.finishPos ? fmtTime(c.finishTime) : '+' + fmtTime(c.finishTime - win.finishTime);
      else time = c.state === 'wrecked' ? 'WRECKED' : c.state === 'withdrawn' || c.left ? 'OUT' : 'DNF';
    }
    if (!hudVar(slot, B.p, c ? ordinal(pos) : '')) ok = false;
    if (!hudVar(slot, B.n, c ? c.name.slice(0, 20).toUpperCase() : '')) ok = false;
    if (!hudVar(slot, B.t, time)) ok = false;
    if (!hudSwapK(hs, slot, B.row, B.side, c ? (c.team === 0 ? 'T' : c.team === 1 ? 'CT' : null) : null)) ok = false;
    if (!hudSwapK(hs, slot, B.row, B.me, c && c === me ? 'me' : null)) ok = false;
    if (!hudSwapK(hs, slot, B.row, B.pod, pos >= 1 && pos <= 3 ? 'p' + pos : null)) ok = false;
  }
  hs.resRank = ok ? r : null; hs.resMe = me; hs.resKey = key;
}

// the track vote box (left): four tracks with their votes, a voter's pick in gold. Redrawn only when a vote changes.
const VOTE_ROWS = 4;
function hudVote(hs, slot, ballot) {
  if (!ballot) {
    if (hs.vote !== false) hs.vote = rootSwap(hs, slot, 'vote', null) ? false : null;
    return;
  }
  const v = ballot.voters.get(slot);
  const mine = v && rm.person(slot) === v.pe ? v : null;
  const key = mine ? (mine.choice || '-') + mine.weight : '';
  if (hs.vote === ballot && hs.voteVer === ballot.ver && hs.voteKey === key) return;
  const tally = rm.tally(ballot);
  let ok = rootSwap(hs, slot, 'vote', 'stVote');
  for (let i = 0; i < VOTE_ROWS; i++) {
    const id = ballot.tracks[i];
    const picked = !!(mine && id && mine.choice === id);
    hudText(slot, 'spr_vn' + i, id ? trackTitle(id) : '', picked ? 'cY' : 'cW', picked ? 'pulse' : null);
    const n = id ? tally.get(id) || 0 : 0;
    hudText(slot, 'spr_vc' + i, n ? String(Math.min(9, n)) : '', 'cC');
    if (!hs.rows.has('spr_vn' + i) || !hs.rows.has('spr_vc' + i)) ok = false;
  }
  hudText(slot, 'spr_vf', mine ? (mine.choice ? 'YOUR VOTE X' + mine.weight + '  W/S' : 'W/S TO VOTE  X' + mine.weight) : 'TOP 3 ARE VOTING', mine && !mine.choice ? 'cY' : 'cP', mine && !mine.choice ? 'blink' : null);
  if (!hs.rows.has('spr_vf')) ok = false;
  hs.vote = ok ? ballot : null; hs.voteVer = ballot.ver; hs.voteKey = key;
}

// lap timer and best lap (tenths), under the race clock
function lapText(sec) { return sec > 0 ? fmtTime(sec).slice(0, -1) : '-'; }

// fixed class slot keys used every update
const K = {
  shfill: 'spr_shfill', shLow: gkey('spr_shield', 'low'), chfill: 'spr_chfill', chSt: gkey('spr_charge', 'st'),
  abfill: 'spr_abfill', abSt: gkey('spr_abil', 'st'), spfill: 'spr_spfill', spPad: gkey('spr_speed', 'pad'), turn: gkey('spr_turn', 'dir'),
};
const ABIL_TEXT = {};
for (const k of CAR_KEYS) ABIL_TEXT[k] = 'E ' + CARS[k].abilityName;

// a racing player's own HUD (or a spectator looking through `car`)
function hudRace(slot, car, arena, info) {
  const hs = hslot(slot);
  hudRaceCommon(hs, slot, arena, info, car);
  // position: big digits (gold when leading), the suffix, and the field size
  // the big number pops when you gain a place (or start watching another car)
  const pk = pkeep(slot), pos = car.pos || 99;
  if (pk.posCar !== car.slot || pos < pk.pos) pk.posFlip = !pk.posFlip;
  pk.posCar = car.slot; pk.pos = pos;
  const posKey = (car.pos || 0) * 2 + (pk.posFlip ? 1 : 0);
  if (hs.posKey !== posKey) {
    const ord = car.pos ? ordinal(car.pos) : '-';
    const num = car.pos ? String(car.pos) : '-';
    const posCol = car.pos === 1 ? 'cY' : car.pos && car.pos <= 3 ? 'cG' : 'cW';
    hudText(slot, 'spr_pos', num, posCol, pk.posFlip ? 'pop2' : 'pop');
    hudText(slot, 'spr_suf', ord.slice(num.length), posCol);
    hs.posKey = hs.rows.has('spr_pos') && hs.rows.has('spr_suf') ? posKey : NaN;
  }
  const ah = arenaHud(arena);
  if (hs.posOf !== ah.field) { hudText(slot, 'spr_posof', '/' + ah.field, 'cP'); hs.posOf = hs.rows.has('spr_posof') ? ah.field : NaN; }
  const tl = info.tally || { t: 0, ct: 0 };
  if (hs.tallyT !== tl.t || hs.tallyCT !== tl.ct) {
    hudText(slot, 'spr_tt', 'T ' + tl.t, 'cY');
    hudText(slot, 'spr_tct', tl.ct + ' CT', 'cC');
    const ok = hs.rows.has('spr_tt') && hs.rows.has('spr_tct');
    hs.tallyT = ok ? tl.t : NaN; hs.tallyCT = ok ? tl.ct : NaN;
  }
  const lap = Math.min(arena.laps, car.lapsDone + 1);
  const final = lap === arena.laps && arena.laps > 1 && car.state === 'racing';
  const lapKey = final ? -1 - arena.laps : lap * 64 + arena.laps;
  if (hs.lapKey !== lapKey) {
    if (final) hudText(slot, 'spr_lap', 'FINAL LAP', 'cR', 'blink');
    else hudText(slot, 'spr_lap', 'LAP ' + lap + '/' + arena.laps, 'cY');
    hs.lapKey = hs.rows.has('spr_lap') ? lapKey : NaN;
  }
  // the running lap time ticks about 5 times a second (fewer class changes than every tenth)
  if (car.state !== 'racing' || arena.tic % 12 < 2) hudText(slot, 'spr_laptime', arena.state === 'grid' ? '-' : car.state === 'racing' ? lapText(arena.raceTic / TICRATE - car.lapStart) : lapText(car.lastLap), 'cW');
  if (hs.best !== car.bestLap) { hudText(slot, 'spr_best', lapText(car.bestLap), 'cY'); hs.best = hs.rows.has('spr_best') ? car.bestLap : NaN; }
  hudSwapK(hs, slot, 'spr_shfill', K.shfill, pct(car.shield, car.spec.shield));
  hudSwapK(hs, slot, 'spr_shield', K.shLow, car.shield < car.spec.shield * 0.3 ? 'low' : null);
  hudSwapK(hs, slot, 'spr_chfill', K.chfill, pct(car.charge, car.spec.charge));
  hudSwapK(hs, slot, 'spr_charge', K.chSt, car.boosting ? 'boosting' : car.onCharge ? 'charging' : null);
  // the E ability: name, and a bar that refills over the cooldown; gold when ready, red when short of charge
  const sp = car.spec, ready = car.abilCd <= 0;
  const short = ready && car.charge < sp.abilityCost;
  if (car.lock > 0 && (sp.ability === 'quake' || sp.ability === 'bolt')) {   // the first seconds of a race: no Shockwave yet, count down to it
    hudText(slot, 'spr_abtxt', 'ATTACKS IN ' + Math.ceil(car.lock), 'cW', null);
    hudSwapK(hs, slot, 'spr_abfill', K.abfill, pct(RULES.attackLock - car.lock, RULES.attackLock));
    hudSwapK(hs, slot, 'spr_abil', K.abSt, null);
  } else {
    hudText(slot, 'spr_abtxt', ABIL_TEXT[sp.key] || 'E ' + sp.abilityName, ready && !short ? 'cY' : short ? 'cR' : 'cW', ready && !short && !info.spectating ? 'pulse' : null);
    hudSwapK(hs, slot, 'spr_abfill', K.abfill, pct(ready ? sp.abilityCd : sp.abilityCd - car.abilCd, sp.abilityCd));
    hudSwapK(hs, slot, 'spr_abil', K.abSt, short ? 'low' : ready ? 'ready' : null);
  }
  // "km/h" for the dial (units/s x 0.36 reads like a racing speedo), 8 updates a second in steps of 2
  if ((arena.tic & 7) < 2 || car.speed < 10) hudText(slot, 'spr_spd', String(Math.round(car.speed * 0.18) * 2).padStart(4, ' '), car.boosting || car.padTimer > 0 ? 'cY' : 'cW');
  hudSwapK(hs, slot, 'spr_spfill', K.spfill, pct(car.speed, car.spec.maxSpeed * 1.5));
  hudSwapK(hs, slot, 'spr_speed', K.spPad, car.padTimer > 0 ? 'pad' : null);
  // the bend ahead: an arrow (two blinking ones for a hairpin), looking further ahead the faster the car goes
  if (car.state === 'racing' && (arena.tic & 3) < 2) hudSwapK(hs, slot, 'spr_turn', K.turn, turnClass(car, arena));
  else if (car.state !== 'racing') hudSwapK(hs, slot, 'spr_turn', K.turn, null);
  // speed lines: white for the car's own boost (Mouse 1, Nova Burn), gold for a boost pad or a turbo start
  const fast = car.state === 'racing' && !info.spectating;
  rootSwap(hs, slot, 'boost', fast && car.padTimer > 0 ? 'stPadb' : fast && (car.boosting || car.novaTimer > 0) ? 'stBoost' : null);
  hudDots(hs, slot, arena, car);
  rootSwap(hs, slot, 'spec', info.spectating ? 'stSpec' : null);
  rootSwap(hs, slot, 'lobby', null);
  hudVote(hs, slot, info.vote || null);
}
// the turn arrow for a car, worked out once per tick however many players look through that car
function turnClass(car, arena) {
  if (car.turnTick === tickNo) return car.turnCls;
  const look = 500 + car.speed * 0.9;
  const turn = arena.track.turnAhead(car.s, look * 0.3, look + 900);
  const a = Math.abs(turn);
  car.turnTick = tickNo;
  car.turnCls = a > 0.75 ? (turn > 0 ? 'l' : 'r') + (a > 1.9 ? '2' : '1') : null;
  return car.turnCls;
}

// lobby: status lines, the picker and the bottom line (answers to chat commands). The centre lines stay empty: the
// picker sits where they are.
function hudLobby(slot, info) {
  const hs = hslot(slot);
  rootSwap(hs, slot, 'lobby', 'stLobby');
  rootSwap(hs, slot, 'on', null);
  rootSwap(hs, slot, 'res', null);
  rootSwap(hs, slot, 'boost', null);
  rootSwap(hs, slot, 'spec', null);
  hudText(slot, 'spr_lob1', info.line1 || '', 'cW', info.blink1 ? 'blink' : null);
  hudText(slot, 'spr_lob2', info.line2 || '', 'cY');
  hudText(slot, 'spr_lob3', info.line3 || '', 'cC');
  hudCenter(slot, '');
  hudText(slot, 'spr_sub', '');
  hudText(slot, 'spr_msg', info.msg || '', 'cC');
  hudSwapK(hs, slot, 'spr_flash', 'spr_flash', null);
  hudVote(hs, slot, info.vote || null);
}

function hudHelp(slot, on) { const hs = hslot(slot); rootSwap(hs, slot, 'help', on ? 'stHelp' : null); hs.optHelp = null; }
// per-player switches, refreshed with every HUD update: scanlines (!crt), and the help panel while !help asked for it
const OPT_CRT = gkey('spr_opts', 'crt');
function hudOptions(slot, pe) {
  const hs = hslot(slot);
  const crt = pe.crt === false, help = (pe.helpUntil || 0) > gameTime();
  if (hs.optCrt === crt && hs.optHelp === help) return;
  const ok = hudSwapK(hs, slot, 'spr_opts', OPT_CRT, crt ? 'nocrt' : null) && rootSwap(hs, slot, 'help', help ? 'stHelp' : null);
  hs.optCrt = ok ? crt : null; hs.optHelp = ok ? help : null;
}
