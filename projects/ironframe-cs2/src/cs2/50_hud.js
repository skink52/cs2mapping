// ===================================================================================================================
// IRONFRAME CS2 adapter, part 5: the HUD driver for the custom_hud_layout `ifr_hud` (tools/hud.py writes the layout and
// the contract baked here as HUD = out/addon/_gen/hud.json; docs/HUD.md documents the API, the input shapes and the budget).
//
// Design (Space Racer 30_hud.js + Dogfight 60_hud.js, docs/creation/hud.md):
//  * per-slot MIRROR: what the layout entity shows for that player (classes on, dialog variable texts) and what the game
//    WANTS. A call only records a want; nothing is sent twice (change-only), and a want that returns to what the entity
//    already shows before the flush costs nothing.
//  * GOVERNOR: ifrHudTick() flushes at most IFR_HUD_BUDGET (900) engine writes per server tick, in priority bands
//    (0 warnings > 1 lock > 2 gauges > 3 text; a panel's band comes from the contract) and, inside a band, the odd or even
//    player half first (alternating per tick) so a burst never starves the same players twice. Leftovers wait.
//  * CONTRACT: a write to a panel id / class / text slot the layout does not have throws (a caller bug, found in the mock).
//  * RESET: ifrHudReset(slot) calls ResetForPlayer and marks every want dirty: the whole HUD is redrawn over the next ticks
//    (the caller does this on OnPlayerActivate, team change and spawn). A re-found layout entity redraws everyone.
//  * Ladders (gauges) are stL0..stL<n> on a fill panel; a new step clears the previous one (2 writes).
//  * PANEL IDS: CS2 keeps at most 1024 panel ids per custom_hud_layout. Every id named in SetHasClass* / SetDialogVariable* takes a place in a
//    table that never frees; past 1024 the console says "The maximum number of panel ids has been reached, no more can be referenced" and the
//    panel is never updated again (10 Nov 2026, 19:50: bars empty, weapons blank, the lock marker gone, because text was one id-carrying glyph
//    panel per character: 5 000 ids, and the garage, opened first, used the table up). Text is now ONE id per slot: a real Label whose dialog
//    variable `v` is set with SetDialogVariableStringForPlayer (1 engine call per changed text). The layout has 461 ids in all (hud.json `ids`,
//    budget 800); the driver counts the ids it has referenced (ifrHudStats().ids) and warns once in the console past IFR_HUD_ID_WARN.
//  * Quantised numbers: ifrHudNum rounds to `step` with hysteresis (0.6 step) so a steady value never flickers.
// Plain JS, no imports; top-level names ifr* / IFR_*. Without a HUD (HUD = {}) every call is a no-op.
// ===================================================================================================================

const IFR_HUD_BUDGET = (typeof CONFIG === 'object' && CONFIG && CONFIG.HUD_BUDGET) || 900;
const IFR_HUD_NAME = (typeof CONFIG === 'object' && CONFIG && CONFIG.HUD) || 'ifr_hud';
const IFR_HUD_ON = !!(typeof HUD === 'object' && HUD && HUD.panels);
const IFR_HUD_RADAR_RANGE = (typeof CONFIG === 'object' && CONFIG && CONFIG.RADAR_RANGE) || 6000;
const IFR_HUD_LINE_SECONDS = 4, IFR_HUD_KILL_SECONDS = 3, IFR_HUD_XP_SECONDS = 2.5;
// the message line: rows from the layout (3 since the evening playtest of 10 Nov 2026; an older hud.json has line / line2), the least time a message
// stays (MIN), the most an important one holds the line while others wait (KEEP), seconds per page of a long message, when queued news is stale
const IFR_HUD_LINE_SLOTS = (IFR_HUD_ON && HUD.line && HUD.line.slots) || ['line', 'line2'];
const IFR_HUD_LINE_MIN = 1.6, IFR_HUD_LINE_KEEP = 3.5, IFR_HUD_LINE_PAGE = 3, IFR_HUD_LINE_STALE = 10, IFR_HUD_LINE_QMAX = 8;
const IFR_HUD_FOCAL = (typeof CONFIG === 'object' && CONFIG && CONFIG.HUD_FOCAL) || 720;   // px per unit of view tangent at 1080 high (CS2: 90 degrees across 4:3)
const IFR_HUD_RADAR_CELLS = (IFR_HUD_ON && HUD.radar && HUD.radar.cells) || 24;
const IFR_HUD_RADAR_DOTS = (IFR_HUD_ON && HUD.radar && HUD.radar.dots) || 64;
const IFR_HUD_PRIOS = 4;

// ---------------------------------------------------------------- the contract
const IFR_HUD_PANELS = new Map();       // id -> { cls: Set, ranges: [[prefix, lo, hi]], vars: Set, prio }
if (IFR_HUD_ON) {
  for (const id in HUD.panels) {
    const p = HUD.panels[id];
    IFR_HUD_PANELS.set(id, { cls: new Set(p.classes || []), ranges: p.ranges || [], vars: new Set(p.vars || []), prio: Math.min(IFR_HUD_PRIOS - 1, p.prio == null ? 2 : p.prio) });
  }
}
const IFR_HUD_LADDERS = IFR_HUD_ON ? HUD.ladders || {} : {};
const IFR_HUD_TEXT = /** @type {any} */ (IFR_HUD_ON ? HUD.text_slots || {} : {});
const IFR_HUD_ROOT = (IFR_HUD_ON && HUD.root) || 'ifr_root';
const IFR_HUD_SCREENS = (IFR_HUD_ON && HUD.screens) || { fight: ['stFight'], spec: ['stSpec'], death: ['stDeath'], intro: ['stIntro'], podium: ['stPodium'], garage: ['stGarage'], off: [] };
const IFR_HUD_FAMILIES = new Set((IFR_HUD_ON && HUD.families) || []);
const IFR_HUD_PART_PICS = new Set((IFR_HUD_ON && HUD.garage && HUD.garage.parts) || []);
const IFR_HUD_GCATS = (IFR_HUD_ON && HUD.garage && HUD.garage.cats) || [];
const IFR_HUD_GROWS = (IFR_HUD_ON && HUD.garage && HUD.garage.rows) || 8;
const IFR_HUD_GSTATS = (IFR_HUD_ON && HUD.garage && HUD.garage.stats) || ['ap', 'weight', 'en', 'speed', 'boost', 'qb', 'lock'];

function ifrHudPanel(id) {
  const p = IFR_HUD_PANELS.get(id);
  if (!p) throw new Error('ifrHud: unknown panel ' + id);
  return p;
}
function ifrHudClassOk(p, cls) {
  if (p.cls.has(cls)) return true;
  for (const r of p.ranges) {
    if (cls.length > r[0].length && cls.slice(0, r[0].length) === r[0]) {
      const n = Number(cls.slice(r[0].length));
      if (Number.isInteger(n) && n >= r[1] && n <= r[2]) return true;
    }
  }
  return false;
}

// ---------------------------------------------------------------- per-slot state
const ifrHudSlots = new Map();
function ifrHudSlot(slot) {
  let s = ifrHudSlots.get(slot);
  if (!s) {
    s = { slot, want: new Map(), have: new Map(), wantVar: new Map(), haveVar: new Map(), dirty: [], ladder: new Map(), grid: new Map(),
      num: new Map(), pops: new Map(), memo: new Map(), lineUntil: 0, lineQ: [], lineCur: null, killUntil: 0, xpUntil: 0, deathAt: 0, deathWait: 0, screen: '', team: 0, points: null,
      pos: null, match: null, capture: false, mech: null, tgt: null, hints: new Set(), cards: {}, spawns: 0, deaths: 0 };
    for (let i = 0; i < IFR_HUD_PRIOS; i++) s.dirty.push(new Map());
    ifrHudSlots.set(slot, s);
  }
  return s;
}
function ifrHudNow() {
  if (typeof gameTime === 'function') return gameTime();
  try { return Instance.GetGameTime(); } catch (err) { return Date.now() / 1000; }
}
function ifrHudLog(msg) {
  if (typeof log === 'function') log(msg);
  else try { Instance.Msg('[ironframe] ' + msg); } catch (err) { /* no console */ }
}

// ---------------------------------------------------------------- the layout entity (re-found when it goes away)
let ifrHudEntity = null, ifrHudWarnedMissing = false;
function ifrHudEnt() {
  if (!IFR_HUD_ON) return null;
  if (ifrHudEntity) {
    try { if (ifrHudEntity.IsValid()) return ifrHudEntity; } catch (err) { /* fall through */ }
    ifrHudEntity = null;
  }
  let e = null;
  try { e = Instance.FindEntityByName(IFR_HUD_NAME); } catch (err) { e = null; }
  if (!e || typeof e.SetHasClassForPlayer !== 'function') {
    if (!ifrHudWarnedMissing) { ifrHudWarnedMissing = true; ifrHudLog('WARNING: no custom_hud_layout named ' + IFR_HUD_NAME + ' - no HUD'); }
    return null;
  }
  ifrHudEntity = e;
  for (const s of ifrHudSlots.values()) ifrHudMarkAll(s);     // a new entity shows its authored state: redraw every want
  return e;
}
/** map start / script reload: find the layout, reset it for everyone (the mirrors start empty) */
function ifrHudInit() {
  ifrHudEntity = null; ifrHudWarnedMissing = false;
  const e = ifrHudEnt();
  if (e) { try { e.Reset(); } catch (err) { /* ignore */ } }
  for (const s of ifrHudSlots.values()) ifrHudMarkAll(s);
  ifrHudLog('HUD ' + (e ? 'on: ' + IFR_HUD_PANELS.size + ' panel ids (CS2 allows 1024 per layout), budget ' + IFR_HUD_BUDGET + ' writes a tick' : IFR_HUD_ON ? 'MISSING (' + IFR_HUD_NAME + ')' : 'off (no hud.json baked)'));
  return !!e;
}

// ---------------------------------------------------------------- primitives
function ifrHudKey(id, cls) { return id + '|' + cls; }
function ifrHudHas(map, id, cls) { const m = map.get(id); return !!(m && m.get(cls)); }
function ifrHudPut(map, id, cls, on) { let m = map.get(id); if (!m) { m = new Map(); map.set(id, m); } m.set(cls, on); }

/** per-player class on / off: mirrored, change-only, governed */
function ifrHudSet(slot, id, cls, on) {
  if (!IFR_HUD_ON) return;
  const p = ifrHudPanel(id);
  if (!ifrHudClassOk(p, cls)) throw new Error('ifrHud: panel ' + id + ' has no class ' + cls);
  on = !!on;
  const s = ifrHudSlot(slot);
  if (ifrHudHas(s.want, id, cls) === on) return;
  ifrHudPut(s.want, id, cls, on);
  const key = ifrHudKey(id, cls), d = s.dirty[p.prio];
  if (ifrHudHas(s.have, id, cls) === on) d.delete(key); else d.set(key, { id, cls });
}
/** text for a Label: upper case, no control characters, cut at `max` characters. Anything printable stays (the Label's font, Noto Serif, has
 *  Latin, Greek and Cyrillic; CS2 falls back to its other Noto faces for the rest), so a pilot's name shows as it is. */
function ifrHudCleanText(t, max) {
  t = t === undefined || t === null ? '' : String(t);
  t = t.toUpperCase().replace(/[\x00-\x1f\x7f-\x9f]/g, ' ').replace(/\u00a0/g, ' ');
  if (max && t.length > max) t = t.slice(0, max);
  return t;
}
const IFR_HUD_GW = (IFR_HUD_ON && HUD.glyphs && HUD.glyphs.w) || {};      // size -> { code: advance px }: the Label font's real advance widths (tools/hud_font.py)
/** advance of one character at a size; a character outside the measured table counts as a W (the widest capital: never an underestimate) */
function ifrHudAdv(gw, code) { return gw[code] || gw[87] || 20; }
const IFR_HUD_SHORT = (IFR_HUD_ON && HUD.short) || {};       // weapon name -> short form for the narrow fight / equipped boxes
const ifrHudCuts = new Map();                                // slot name -> { text, shown }: strings that did not fit their box (the test asserts none for real strings)
/** a string did not fit its slot: remembered for the test, and said once per slot in the console (a cut in game is never silent: the 10 Nov 2026
 *  evening playtest found cut texts no offline list had covered) */
const ifrHudCutSaid = new Set();
function ifrHudCut(name, full, shown) {
  ifrHudCuts.set(name, { text: full, shown });
  if (ifrHudCutSaid.size < 40 && !ifrHudCutSaid.has(name)) { ifrHudCutSaid.add(name); ifrHudLog('HUD text cut in ' + name + ': "' + full + '" shown as "' + shown + '" (report it: test/hud_strings.cjs should have caught this)'); }
}
function ifrHudShort(name) { name = String(name || ''); return IFR_HUD_SHORT[name] || name; }
/** pixel width of `text` in text slot `name` (0 when the slot is unknown) */
function ifrHudWidth(name, text) {
  const ts = IFR_HUD_TEXT[name]; if (!ts) return 0;
  const gw = IFR_HUD_GW[ts.size] || {}; let w = 0;
  const t = ifrHudCleanText(text, 0);
  for (let i = 0; i < t.length; i++) w += ifrHudAdv(gw, t.charCodeAt(i));
  return w;
}
/** the tokens (joined by `sep`) that fit the box of slot `name`, in order: later tokens drop first */
function ifrHudFitTokens(name, tokens, sep) {
  const ts = IFR_HUD_TEXT[name]; let out = '';
  for (const t of tokens) { const c = out ? out + sep + t : t; if (ts && ifrHudWidth(name, c) > ts.w) break; out = c; }
  const all = tokens.join(sep);
  if (out !== all) ifrHudCut(name, all, out); else ifrHudCuts.delete(name);
  return out;
}
/** packs whole tokens (joined by `sep`) into the boxes of the given slots, first to last; a token that does not fit any remaining line is dropped, never cut */
function ifrHudWrapTokens(names, tokens, sep) {
  const out = []; let cur = '', i = 0, dropped = false;
  for (const t of tokens) {
    if (i >= names.length) { dropped = true; break; }
    const w = (IFR_HUD_TEXT[names[i]] || { w: 1e9 }).w, c = cur ? cur + sep + t : t;
    if (ifrHudWidth(names[i], c) <= w) { cur = c; continue; }
    if (cur) { out.push(cur); i++; cur = ''; if (i >= names.length) { dropped = true; break; } if (ifrHudWidth(names[i], t) <= (IFR_HUD_TEXT[names[i]] || { w: 1e9 }).w) { cur = t; continue; } }
    dropped = true;
  }
  if (cur && out.length < names.length) out.push(cur);
  if (dropped) ifrHudCut(names[0], tokens.join(sep), out.join(' / ')); else ifrHudCuts.delete(names[0]);
  return out;
}
/** does `text` fit the box (pixels) and the cells of slot `name`? (an unknown slot fits anything) */
function ifrHudFits(name, text) {
  const ts = IFR_HUD_TEXT[name]; if (!ts) return true;
  return String(text).length <= ts.max && ifrHudWidth(name, text) <= ts.w;
}
/** `text` word-wrapped into rows that each fit slot `name` (pixels and cells); a word wider than a row is broken; nothing is dropped */
function ifrHudWrapAll(name, text) {
  const out = []; let cur = '';
  for (let w of ifrHudCleanText(text, 0).split(/\s+/).filter(Boolean)) {
    for (;;) {
      const c = cur ? cur + ' ' + w : w;
      if (ifrHudFits(name, c)) { cur = c; break; }
      if (cur) { out.push(cur); cur = ''; continue; }
      let k = w.length - 1; while (k > 1 && !ifrHudFits(name, w.slice(0, k))) k--;     // a word wider than the row: break it
      out.push(w.slice(0, k)); w = w.slice(k);
    }
  }
  if (cur) out.push(cur);
  return out;
}
/** wraps `text` into the boxes of the given slots (word wrap by pixel width and cell count); words that need more rows than there are slots are
 *  dropped and the cut is recorded (callers that must not lose text use ifrHudWrapAll and page it, like the message line) */
function ifrHudWrap(names, text) {
  const out = []; let cur = '', i = 0, lost = false;
  for (const w of ifrHudCleanText(text, 0).split(/\s+/).filter(Boolean)) {
    if (i >= names.length) { lost = true; break; }
    const c = cur ? cur + ' ' + w : w;
    if (ifrHudFits(names[i], c)) { cur = c; continue; }
    if (cur) { out.push(cur); i++; cur = ''; if (i >= names.length) { lost = true; break; } }
    if (ifrHudFits(names[i], w)) cur = w; else lost = true;
  }
  if (cur && out.length < names.length) out.push(cur);
  if (lost) ifrHudCut(names[0], String(text), out.join(' / ')); else ifrHudCuts.delete(names[0]);
  return out;
}
/** `text` shortened to fit slot `name`, ending in '..' when it had to be cut (player names: up to 24 wide letters will not fit a name box).
 *  pre / post are kept whole: only `text` gives way */
function ifrHudFitText(name, text, pre, post) {
  pre = pre || ''; post = post || '';
  text = ifrHudCleanText(text, 0).trim();
  if (ifrHudFits(name, pre + text + post)) return pre + text + post;
  let k = text.length - 1;
  while (k > 1 && !ifrHudFits(name, pre + text.slice(0, k).trimEnd() + '..' + post)) k--;
  return pre + text.slice(0, k).trimEnd() + '..' + post;
}
/** text slot `name`: upper-cased and, if it is wider than the slot's box by the Label font's widths, cut (and the cut recorded: ifrHudCut).
 *  One engine call per changed text (the dialog variable `v` of the slot's Label); alignment is the Label's own css. */
function ifrHudVar(slot, name, text) {
  if (!IFR_HUD_ON) return;
  const ts = IFR_HUD_TEXT[name];
  if (!ts) throw new Error('ifrHud: unknown text slot ' + name);
  const p = ifrHudPanel(ts.panel);
  const full = ifrHudCleanText(text, 0).replace(/ +$/, '');
  const s = ifrHudSlot(slot);
  if (s.wantVar.get(ts.panel) === full) return;                 // the same text as last time (fitted or not): nothing to do
  const gw = IFR_HUD_GW[ts.size] || {};
  let used = 0, len = 0;
  for (; len < full.length && len < ts.max; len++) { const a = ifrHudAdv(gw, full.charCodeAt(len)); if (used + a > ts.w) break; used += a; }
  const shown = full.slice(0, len).replace(/ +$/, '');
  if (shown.length < full.length) ifrHudCut(name, full, shown); else ifrHudCuts.delete(name);
  s.wantVar.set(ts.panel, full);
  ifrHudText(s, p.prio, ts.panel, shown);
}
/** a Label's text for this player: mirrored, change-only, governed like a class write. Runs of spaces are kept with no-break spaces (a Label
 *  may fold them into one) */
function ifrHudText(s, prio, id, text) {
  text = text.replace(/ {2,}/g, (m) => ' ' + '\u00a0'.repeat(m.length - 1));
  const key = id + '|\u0001', d = s.dirty[prio];
  let m = s.want.get(id); if (!m) { m = new Map(); s.want.set(id, m); }
  if (m.get('\u0001') === text) return;
  m.set('\u0001', text);
  if ((s.haveVar.get(id) || '') === text) d.delete(key); else d.set(key, { id, txt: true });
}
function ifrHudFmtNum(n) {
  n = Math.round(Number(n) || 0);
  const neg = n < 0; let t = String(Math.abs(n));
  for (let i = t.length - 3; i > 0; i -= 3) t = t.slice(0, i) + ' ' + t.slice(i);
  return (neg ? '-' : '') + t;
}
/** a number text quantised to `step` with hysteresis: it only moves once the value is 0.6 step from what is shown */
function ifrHudNum(slot, name, n, step, prefix, suffix) {
  if (!IFR_HUD_ON) return;
  n = Number(n) || 0; step = step || 1;
  const s = ifrHudSlot(slot), last = s.num.get(name);
  if (last !== undefined && Math.abs(n - last) < step * 0.6) return;
  const shown = Math.round(n / step) * step;
  s.num.set(name, shown);
  ifrHudVar(slot, name, (prefix || '') + ifrHudFmtNum(shown) + (suffix || ''));
}
/** a gauge: frac 0..1 picks the step class on the ladder's fill panel and clears the previous one */
function ifrHudLadder(slot, name, frac) {
  if (!IFR_HUD_ON) return;
  const L = IFR_HUD_LADDERS[name];
  if (!L) throw new Error('ifrHud: unknown ladder ' + name);
  frac = Number(frac);
  if (!(frac >= 0)) frac = 0;
  if (frac > 1) frac = 1;
  const k = Math.round(frac * L.steps);
  const s = ifrHudSlot(slot), prev = s.ladder.get(name);
  if (prev === k) return;
  if (prev !== undefined) ifrHudSet(slot, L.panel, 'stL' + prev, false);
  ifrHudSet(slot, L.panel, 'stL' + k, true);
  s.ladder.set(name, k);
}
/** the message line (two rows, word-wrapped) for `seconds` (default 4); '' clears it. queue = true: shown after the current message
 *  instead of replacing it (multi-part replies such as !help) */
// 10 Nov 2026 evening playtest ("many in game messages get cut off"). Three causes, three rules:
//  * space: the text is wrapped by pixel width AND cell count into the line's rows; what does not fit becomes a second page (shown after the
//    first), and a word wider than a row is broken. Nothing is dropped, whatever the length (test/hud_strings.cjs fuzzes this).
//  * time: a message used to replace the one on screen at once, so "OVERDRIVE READY: hold ..." vanished the moment a bot took a crate. Now every
//    message stays at least IFR_HUD_LINE_MIN s; a newer one waits its turn in a queue (same-priority and lower ones), and only a more
//    important one cuts in, putting the interrupted one back at the head of the queue if it had less than that.
//  * noise: prio 0 (ambient: other pilots' news, trait procs) is shown only when the line is free and never waits; prio 2 (the pilot has to
//    do something: a reward, a prompt, a hint, a chat reply) is drawn in gold with a gold edge.
function ifrHudLineDraw(s, item) {
  const slot = s.slot, n = IFR_HUD_LINE_SLOTS.length;
  const rows = item ? item.pages[item.page] || [] : [];
  for (let k = 0; k < n; k++) ifrHudVar(slot, IFR_HUD_LINE_SLOTS[k], rows[k] || '');
  ifrHudSet(slot, 'ifr_line', 'stOn', !!item);
  if (ifrHudClassOk(ifrHudPanel('ifr_line'), 'stHi')) {
    ifrHudSet(slot, 'ifr_line', 'stHi', !!item && item.prio >= 2);
    for (let k = 1; k <= n; k++) ifrHudSet(slot, 'ifr_line', 'stR' + k, !!item && rows.length === k);
  }
}
function ifrHudLineStart(s, item, now) {
  if (!item.pages) {
    const rows = ifrHudWrapAll(IFR_HUD_LINE_SLOTS[0], item.text), n = IFR_HUD_LINE_SLOTS.length;
    item.pages = []; for (let i = 0; i < rows.length; i += n) item.pages.push(rows.slice(i, i + n));
    if (!item.pages.length) item.pages.push([]);
    item.page = 0;
  }
  item.since = now; item.pageSince = now;
  item.pageFor = Math.max(item.pages.length > 1 ? IFR_HUD_LINE_PAGE : 0, item.seconds / item.pages.length);
  s.lineCur = item; s.lineUntil = now + item.pageFor;
  ifrHudLineDraw(s, item);
}
function ifrHudLineNext(s, now) {
  let q = s.lineQ.shift();
  while (q && q.prio < 2 && now - q.at > IFR_HUD_LINE_STALE) q = s.lineQ.shift();      // old news is not worth showing late
  if (q) ifrHudLineStart(s, q, now); else { s.lineCur = null; s.lineUntil = 0; ifrHudLineDraw(s, null); }
}
/** the message line for `seconds` (default 4); '' clears it and the queue. queue = true: always after what is showing and waiting, in order
 *  (multi-part replies such as !help). prio: 0 ambient (only when the line is free), 1 normal (default), 2 important (gold; cuts in). */
function ifrHudLine(slot, text, seconds, queue, prio) {
  if (!IFR_HUD_ON) return;
  const s = ifrHudSlot(slot), now = ifrHudNow();
  text = ifrHudCleanText(text).replace(/\s+/g, ' ').trim();
  if (!text) { s.lineQ.length = 0; s.lineCur = null; s.lineUntil = 0; ifrHudLineDraw(s, null); return; }
  prio = prio === undefined || prio === null ? 1 : prio | 0;
  seconds = seconds > 0 ? seconds : IFR_HUD_LINE_SECONDS;
  const cur = s.lineCur, item = { text, seconds, prio, at: now, pages: null, page: 0, since: 0, pageSince: 0, pageFor: 0, bumped: false };
  if (cur && cur.text === text) { if (cur.page === cur.pages.length - 1) s.lineUntil = Math.max(s.lineUntil, now + Math.min(seconds, cur.pageFor)); return; }   // the same message again: keep it up
  if (s.lineQ.some((q) => q.text === text)) return;
  if (!cur) { ifrHudLineStart(s, item, now); return; }
  const shown = now - cur.since, waiting = s.lineQ.length;
  if (queue) { if (waiting < IFR_HUD_LINE_QMAX) s.lineQ.push(item); return; }
  if (prio > cur.prio) {                                   // more important: now; the interrupted message comes back if it was hardly read
    if (cur.prio >= 1 && !cur.bumped && shown < IFR_HUD_LINE_MIN && cur.page === 0) { cur.bumped = true; s.lineQ.unshift(cur); }
    ifrHudLineStart(s, item, now); return;
  }
  if (prio === 0) return;                                  // ambient news never waits and never interrupts
  if (!waiting && cur.page === cur.pages.length - 1 && shown >= (cur.prio > prio ? Math.min(cur.seconds, IFR_HUD_LINE_KEEP) : IFR_HUD_LINE_MIN)) { ifrHudLineStart(s, item, now); return; }
  if (waiting >= IFR_HUD_LINE_QMAX) { const i = s.lineQ.findIndex((q) => q.prio <= prio); if (i < 0) return; s.lineQ.splice(i, 1); }
  let at = s.lineQ.length; while (at > 0 && s.lineQ[at - 1].prio < prio) at--;      // important ones wait ahead of normal ones
  s.lineQ.splice(at, 0, item);
}
/** timed part of the line (ifrHudTick): the next page, the next waiting message, or off; a message others wait behind gives way sooner */
function ifrHudLineTick(s, now) {
  const cur = s.lineCur;
  if (!cur) return;
  let until = s.lineUntil;
  if (s.lineQ.length && cur.page === cur.pages.length - 1) until = Math.min(until, cur.pageSince + (cur.prio >= 2 ? IFR_HUD_LINE_KEEP : IFR_HUD_LINE_MIN + 0.6));
  if (now < until) return;
  if (cur.page < cur.pages.length - 1) { cur.page++; cur.pageSince = now; s.lineUntil = now + cur.pageFor; ifrHudLineDraw(s, cur); return; }
  ifrHudLineNext(s, now);
}
/** a one-time hint per pilot and session (key): an important line the first time, nothing after. Returns true when it was shown. */
function ifrHudHint(slot, key, text, seconds) {
  if (!IFR_HUD_ON) return false;
  const s = ifrHudSlot(slot);
  if (s.hints.has(key)) return false;
  s.hints.add(key);
  ifrHudLine(slot, text, seconds || 7, false, 2);
  return true;
}
function ifrHudHinted(slot, key) { const s = ifrHudSlots.get(slot); return !!(s && s.hints.has(key)); }
/** counts something per pilot and session ('spawns', 'deaths'): adds one and returns the new count (forgotten when the pilot leaves) */
function ifrHudCount(slot, key) { const s = ifrHudSlot(slot); s[key] = (s[key] | 0) + 1; return s[key]; }
/** one-shot animation replay: stPop / stPop2 alternate (Panorama replays only when the animation name changes) */
function ifrHudPop(slot, id) {
  if (!IFR_HUD_ON) return;
  const s = ifrHudSlot(slot), cur = s.pops.get(id) || 0, next = cur === 1 ? 2 : 1;
  if (cur) ifrHudSet(slot, id, cur === 1 ? 'stPop' : 'stPop2', false);
  ifrHudSet(slot, id, next === 1 ? 'stPop' : 'stPop2', true);
  s.pops.set(id, next);
}
/** hit marker on the reticle: kind 'hit' (light) | 'heavy' (stagger or impact >= 500) | 'kill'; one flash replay per call */
function ifrHudHit(slot, kind) {
  if (!IFR_HUD_ON) return;
  ifrHudPop(slot, kind === 'kill' ? 'ifr_hitK' : kind === 'heavy' ? 'ifr_hitH' : 'ifr_hit');
}
/** one class of a group on (others off), remembered under `memoKey` */
function ifrHudOne(slot, s, id, memoKey, cls) {
  const prev = s.memo.get(memoKey);
  if (prev === cls) return;
  if (prev) ifrHudSet(slot, id, prev, false);
  if (cls) ifrHudSet(slot, id, cls, true);
  s.memo.set(memoKey, cls || '');
}
function ifrHudMarkAll(s) {
  s.have.clear(); s.haveVar.clear();
  for (const d of s.dirty) d.clear();
  for (const [id, m] of s.want) {
    const p = IFR_HUD_PANELS.get(id); if (!p) continue;
    for (const [cls, on] of m) {
      if (cls === '\u0001') { if (on) s.dirty[p.prio].set(id + '|\u0001', { id, txt: true }); }      // a Label's text (a reset empties it)
      else if (on) s.dirty[p.prio].set(ifrHudKey(id, cls), { id, cls });
    }
  }
}
/** full redraw request: ResetForPlayer, then every wanted class and text goes out again (activate / team change / spawn / leave) */
function ifrHudReset(slot) {
  if (!IFR_HUD_ON) return;
  const s = ifrHudSlot(slot), e = ifrHudEnt();
  if (e) { try { e.ResetForPlayer(slot); } catch (err) { /* ignore */ } }
  ifrHudMarkAll(s);
  if (s.capture && e && typeof e.SetInputCaptureEnabled === 'function') { try { e.SetInputCaptureEnabled(slot, true); } catch (err) { /* ignore */ } }   // a reset may drop the garage's mouse
}
/** the player left: forget the slot */
function ifrHudOff(slot) {
  if (!IFR_HUD_ON) return;
  ifrHudSlots.delete(slot);
  if (typeof garagePreviewDrop === 'function') garagePreviewDrop(slot);     // the player's hangar preview props (60_garage.js)
  const e = ifrHudEnt();
  if (e) { try { e.ResetForPlayer(slot); } catch (err) { /* ignore */ } }
}

// ---------------------------------------------------------------- the governor
let ifrHudTickNo = 0;
const ifrHudStat = { tick: 0, writes: 0, last: 0, max: 0, deferred: 0, deferredTicks: 0 };
// every panel id this script has named to the engine: CS2 stops updating panels past 1024 of them (see the header)
const ifrHudIds = new Set();
const IFR_HUD_ID_WARN = 950;
function ifrHudRef(id) {
  if (ifrHudIds.has(id)) return;
  ifrHudIds.add(id);
  if (ifrHudIds.size === IFR_HUD_ID_WARN + 1) ifrHudLog('WARNING: the HUD has referenced ' + ifrHudIds.size + ' panel ids; CS2 stops updating panels past 1024 (tools/hud.py budget, test/hud_ids.cjs)');
}
function ifrHudWrite(e, s, u) {
  ifrHudRef(u.id);
  if (u.txt) {
    const m = s.want.get(u.id), text = (m && m.get('\u0001')) || '';
    if ((s.haveVar.get(u.id) || '') === text) return 0;
    e.SetDialogVariableStringForPlayer(s.slot, u.id, 'v', text);
    s.haveVar.set(u.id, text);
    return 1;
  }
  const on = ifrHudHas(s.want, u.id, u.cls);
  if (ifrHudHas(s.have, u.id, u.cls) === on) return 0;
  e.SetHasClassForPlayer(s.slot, u.id, u.cls, on);
  ifrHudPut(s.have, u.id, u.cls, on);
  return 1;
}
/** flushes the dirty writes: priority bands, odd / even player half first (alternating), up to the budget. Call it last
 *  in the think. Returns the number of engine writes made. */
function ifrHudTick() {
  if (!IFR_HUD_ON) return 0;
  ifrHudTickNo++;
  ifrHudStat.tick = ifrHudTickNo;
  const now = ifrHudNow();
  for (const s of ifrHudSlots.values()) {            // timed one-shots and the death countdown
    ifrHudLineTick(s, now);
    ifrHudCardTick(s, now);
    if (s.killUntil && now >= s.killUntil) { s.killUntil = 0; ifrHudSet(s.slot, 'ifr_kill', 'stOn', false); }
    if (s.xpUntil && now >= s.xpUntil) { s.xpUntil = 0; ifrHudSet(s.slot, 'ifr_xp', 'stOn', false); }
    if (s.deathAt && s.screen === 'death') { const left = s.deathWait - (now - s.deathAt); ifrHudVar(s.slot, 'respawn', left > 0 ? 'RESPAWN IN ' + Math.ceil(left) : 'SPACE SORTIE   CTRL GARAGE'); }
  }
  const e = ifrHudEnt();
  if (!e) return 0;
  const first = ifrHudTickNo & 1, order = [];
  for (const s of ifrHudSlots.values()) if ((s.slot & 1) === first) order.push(s);
  for (const s of ifrHudSlots.values()) if ((s.slot & 1) !== first) order.push(s);
  let budget = IFR_HUD_BUDGET, writes = 0, left = 0;
  for (let prio = 0; prio < IFR_HUD_PRIOS; prio++) {
    for (const s of order) {
      const d = s.dirty[prio];
      if (!d.size) continue;
      if (budget <= 0) { left += d.size; continue; }
      for (const [key, u] of d) {
        if (budget <= 0) { left++; continue; }
        let n = 0;
        try { n = ifrHudWrite(e, s, u); } catch (err) { ifrHudLog('WARNING: HUD write ' + u.id + ' ' + (u.cls || 'text') + ': ' + err); }
        d.delete(key);
        budget -= n; writes += n;
      }
    }
  }
  ifrHudStat.writes += writes; ifrHudStat.last = writes;
  if (writes > ifrHudStat.max) ifrHudStat.max = writes;
  if (left) { ifrHudStat.deferred += left; ifrHudStat.deferredTicks++; }
  return writes;
}
function ifrHudCutList() { return Array.from(ifrHudCuts, ([k, v]) => k + ': ' + v.text + ' -> ' + v.shown); }
function ifrHudStats() { return { tick: ifrHudStat.tick, writes: ifrHudStat.writes, last: ifrHudStat.last, max: ifrHudStat.max, deferred: ifrHudStat.deferred, deferredTicks: ifrHudStat.deferredTicks, slots: ifrHudSlots.size, budget: IFR_HUD_BUDGET, ids: ifrHudIds.size, idsLayout: IFR_HUD_PANELS.size }; }
function ifrHudPending(slot) { const s = ifrHudSlots.get(slot); if (!s) return 0; let n = 0; for (const d of s.dirty) n += d.size; return n; }

// ---------------------------------------------------------------- screens and team accent
/** 'fight' | 'spec' | 'death' | 'intro' | 'podium' | 'garage' | 'off' */
function ifrHudScreen(slot, name) {
  if (!IFR_HUD_ON) return;
  const s = ifrHudSlot(slot);
  if (s.screen === name) return;
  s.screen = name;
  const on = IFR_HUD_SCREENS[name] || [];
  ifrHudSet(slot, IFR_HUD_ROOT, 'stOn', name !== 'off');
  for (const k in IFR_HUD_SCREENS) for (const c of IFR_HUD_SCREENS[k]) ifrHudSet(slot, IFR_HUD_ROOT, c, on.indexOf(c) >= 0);
}
function ifrHudTeam(slot, team) {
  if (!IFR_HUD_ON) return;
  ifrHudSlot(slot).team = team | 0;
  ifrHudSet(slot, IFR_HUD_ROOT, 'stTeamT', team === 2);
  ifrHudSet(slot, IFR_HUD_ROOT, 'stTeamCT', team === 3);
}

// ---------------------------------------------------------------- vitals (m = IF_Mech, INTERFACES 3.2 / core 20_mech.js)
const IFR_HUD_QB_CD = (typeof PARTS === 'object' && PARTS && PARTS.move && PARTS.move.qb_cd) || 0.45;
/** m: {ap, apMax, en, enMax, enStalled (s left), enOver?, stagger, staggerMax, staggered (s left), protect (s), landLag (s),
 *  boosting, assault, qbCd (s left)} */
function ifrHudVitals(slot, m) {
  if (!IFR_HUD_ON || !m) return;
  const apMax = m.apMax > 0 ? m.apMax : 1, enMax = m.enMax > 0 ? m.enMax : 1, sgMax = m.staggerMax > 0 ? m.staggerMax : 1;
  ifrHudLadder(slot, 'ap', m.ap / apMax);
  ifrHudNum(slot, 'ap', Math.max(0, m.ap), 10);
  ifrHudNum(slot, 'apmax', apMax, 1, '/ ');
  ifrHudLadder(slot, 'en', m.en / enMax);
  ifrHudNum(slot, 'en', Math.max(0, m.en), 20);
  const stalled = m.enStalled > 0;
  ifrHudSet(slot, 'ifr_enbar', 'stStall', stalled);
  ifrHudSet(slot, 'ifr_enbar', 'stOver', !!m.enOver && !stalled);
  ifrHudSet(slot, 'ifr_entag', 'stOn', stalled);
  ifrHudLadder(slot, 'stg', m.stagger / sgMax);
  ifrHudSet(slot, 'ifr_stg', 'stStaggered', m.staggered > 0);
  ifrHudSet(slot, 'ifr_stgring', 'stOn', m.staggered > 0);
  ifrHudLadder(slot, 'qb', m.qbCd > 0 ? 1 - m.qbCd / IFR_HUD_QB_CD : 1);
  ifrHudSet(slot, 'ifr_lag', 'stOn', m.landLag > 0);
  ifrHudSet(slot, 'ifr_boost', 'stOn', !!m.boosting && !m.assault);
  ifrHudSet(slot, 'ifr_boost', 'stAssault', !!m.boosting && !!m.assault);
  ifrHudSet(slot, 'ifr_shield', 'stOn', m.protect > 0 || m.dropT > 0);
  const s = ifrHudSlot(slot);
  s.mech = m;                                    // ifrHudWeapons (called next) reads the lock from it
  // Overdrive: the gauge, the percentage and one line that says what to do (10 Nov 2026 evening playtest: "no indication what overdrive does").
  // The core's odPhase is 0 | 1 (charging; an older HUD compared it with 'charge', so the charge state never showed); odT = seconds to the blast.
  const od = Math.max(0, Math.min(1, m.overdrive || 0)), charging = m.odPhase === 1 || m.odPhase === 'charge', ready = od >= 0.999 && !charging;
  ifrHudLadder(slot, 'od', charging ? 1 : od);
  ifrHudSet(slot, 'ifr_odbar', 'stCharge', charging);
  ifrHudSet(slot, 'ifr_odready', 'stOn', ready);
  if (IFR_HUD_TEXT.odl) {
    ifrHudSet(slot, 'ifr_odready', 'stCharge', charging);
    const pct = charging ? 100 : Math.floor(od * 20) * 5;     // 5 % steps: the text changes 20 times a fill, not every tick
    const odText = charging ? 'CHARGING: BLAST IN ' + Math.max(0, Number(m.odT) || 0).toFixed(1) + ' S' : ready ? IFR_HUD_TXT.odReady : m.aceT > 0 ? IFR_HUD_TXT.odAce : IFR_HUD_TXT.odFill;
    if (s.memo.get('odp') !== pct) { s.memo.set('odp', pct); ifrHudVar(slot, 'odp', pct + ' %'); }
    if (s.memo.get('odl') !== odText) { s.memo.set('odl', odText); ifrHudVar(slot, 'odl', odText); }
  }
  // buff badges: what it is (static), then the time left and what it does
  const wide = !!(IFR_HUD_TEXT.bfarty && IFR_HUD_TEXT.bfarty.w >= 200);
  const buffs = [['dmg', m.boostDmgT || 0, ' S LEFT'], ['shield', m.shieldT || 0, ' S LEFT'], ['ace', m.aceT || 0, ' S: OVERDRIVE REFILLS'], ['radar', m.radarT || 0, ' S: ENEMIES ON RADAR']];
  for (const b of buffs) {
    ifrHudSet(slot, 'ifr_bf_' + b[0], 'stOn', b[1] > 0);
    if (b[1] > 0) ifrHudNum(slot, 'bf' + b[0], Math.ceil(b[1]), 1, '', wide ? b[2] : ' S');
  }
  ifrHudSet(slot, 'ifr_bf_arty', 'stOn', !!m.artyReady);
  if (m.artyReady) ifrHudVar(slot, 'bfarty', wide ? IFR_HUD_TXT.artyReady : 'READY');
  // the pilot plate: kills / deaths / assists of this round, and the streak meter (per life; the rewards of src/core/86_features.js)
  if (IFR_HUD_TEXT.ptag && ((ifrHudTickNo + slot) & 63) === 0) ifrHudPilot(slot);
  if (IFR_HUD_TEXT.pk) {
    const sum = m.sum || {};
    ifrHudNum(slot, 'pk', (sum.kills | 0) + (sum.pveKills | 0) + (sum.bossKills | 0), 1); ifrHudNum(slot, 'pd', sum.deaths | 0, 1); ifrHudNum(slot, 'pa', sum.assists | 0, 1);
    const n = Math.max(0, (m.fkills !== undefined ? m.fkills : m.streak) | 0);
    if (s.memo.get('stk') !== n) {
      const was = s.memo.get('stk'); s.memo.set('stk', n);
      ifrHudVar(slot, 'stk', String(n));
      ifrHudLadder(slot, 'skp', Math.min(1, n / IFR_HUD_STREAK_PIPS));
      const nx = IFR_HUD_STREAKS.find((r) => n < r.at);
      ifrHudVar(slot, 'str', nx ? 'NEXT: ' + nx.at + ' KILLS = ' + nx.name : IFR_HUD_TXT.streakDone);
      ifrHudVar(slot, 'str2', nx ? nx.what : IFR_HUD_TXT.streakDone2);
      ifrHudSet(slot, 'ifr_streakp', 'stHot', n > 0);
      if (was !== undefined && n > was) ifrHudPop(slot, 'ifr_streakp');
    }
  }
}
// every sentence the HUD itself says (test/hud_strings.cjs measures each one against its slot)
const IFR_HUD_TXT = {
  odFill: 'DEAL OR TAKE DAMAGE TO FILL', odReady: 'READY: HOLD SPACE + R + E', odAce: 'ACE: REFILLING BY ITSELF',
  artyReady: 'READY: LOCK A TARGET', streakDone: 'ACE EARNED: TOP REWARD', streakDone2: 'A STREAK ENDS WHEN YOU DIE',
  wNoLock: 'NO LOCK: UNGUIDED', wLocked: 'LOCKED: FIRE', wRange: 'OUT OF RANGE', wHold: 'HOLD TO LOCK', wNoTarget: 'NO TARGET IN RING', wRelease: ' LOCKED: RELEASE', wNoAmmo: 'NO AMMO', wSalvo: 'FIRING',
  lAcq: 'ACQUIRING', lSoft: 'SOFT LOCK', lHard: 'LOCKED', loadFoot: 'DEAD: CTRL OR F OPENS THE GARAGE',
};
const IFR_HUD_STREAK_PIPS = (IFR_HUD_ON && HUD.streak_pips) || 8;
// killstreak rewards: when, the name, what it gives (numbers from the core's IF_FEAT.streak when it is in scope)
const IFR_HUD_STREAKS = (() => {
  const S = (typeof IF_FEAT === 'object' && IF_FEAT && IF_FEAT.streak) || { radar: 3, arty: 5, ace: 8, radarT: 10, shells: 6, aceT: 20, aceSpeed: 1.2 };
  return [
    { at: S.radar, key: 'radar', name: 'RADAR PING', what: 'ENEMIES ON RADAR FOR ' + S.radarT + ' S' },
    { at: S.arty, key: 'arty', name: 'ARTILLERY', what: S.shells + ' SHELLS ON YOUR NEXT LOCK' },
    { at: S.ace, key: 'ace', name: 'ACE', what: '+' + Math.round((S.aceSpeed - 1) * 100) + ' % SPEED, FAST OVERDRIVE' },
  ];
})();

// ---------------------------------------------------------------- weapons (m.weapons: IF_Weapon[4], order ra, la, rs, ls)
const IFR_HUD_WFLAGS = ['stReload', 'stEmpty', 'stHot', 'stCharge', 'stNo'];
const IFR_HUD_WSTATE = !!IFR_HUD_TEXT.w0s;       // the layout has the weapon state row (evening playtest 10 Nov 2026)
/** seconds for a countdown: whole above 3 s, halves below (few text changes) */
function ifrHudSecs(t) { t = Math.max(0, Number(t) || 0); return (t >= 3 ? String(Math.ceil(t)) : (Math.ceil(t * 2) / 2).toFixed(1)) + ' S'; }
const ifrHudPct5 = (f) => Math.floor(Math.max(0, Math.min(1, Number(f) || 0)) * 20) * 5 + ' %';
/** what a lock-type launcher will do if its key is pressed now: [text, state class]. Read from the core defensively (m.lock {target, stage, t},
 *  m.lockSoft / lockHard, wp.cd / salvo / mlock / mlDone / mlHold, spec.lock 'soft' | 'hard', spec.multilock, spec.range).
 *  10 Nov 2026 evening playtest: "i don't know how to target them, and there is no indication in game of what to do".
 *  The core's rules (40_combat.js case 'missile'): a press with no enemy in the FCS cone fires the salvo unguided at the reticle; a press on a
 *  target whose lock is still building waits while the key is held (wp.mslWait) and launches guided when the lock is done, releasing early
 *  fires unguided; a multi-lock launcher released with no finished lock fires unguided too. */
function ifrHudMissileState(me, w, spec, tgt) {
  const T = IFR_HUD_TXT;
  const left = spec.ammo !== undefined ? (w.magSize ? w.mag : w.ammo) : 1;
  if (w.salvo > 0) return [T.wSalvo, 'stLkOn'];
  if (!(left > 0)) return [T.wNoAmmo, 'stLkOut'];
  if (w.cd > 0.05) return ['READY IN ' + ifrHudSecs(w.cd), ''];
  if (spec.multilock) {
    const done = w.mlDone | 0, n = w.mlock ? w.mlock.length : 0;
    if (done > 0) return [done + T.wRelease, 'stLkOn'];
    if (w.mlHold > 0) return [n > 0 ? 'KEEP HOLDING: ' + n : T.wNoTarget, n > 0 ? 'stLkAcq' : 'stLkNo'];
    return [T.wHold, 'stLkNo'];
  }
  const lk = me && me.lock, need = spec.lock === 'hard' ? 2 : 1;
  if (!lk || !(lk.target >= 0)) return [T.wNoLock, 'stLkNo'];
  if ((lk.stage | 0) < need) {
    const soft = me.lockSoft > 0 ? me.lockSoft : 0.3, hard = me.lockHard > 0 ? me.lockHard : 0.9;
    return [(w.mslWait ? 'KEEP HOLDING ' : 'HOLD: LOCK ') + ifrHudPct5((lk.t || 0) / (need === 2 ? soft + hard : soft)), 'stLkAcq'];
  }
  if (tgt && tgt.pos && me.pos) { const dx = tgt.pos.x - me.pos.x, dy = tgt.pos.y - me.pos.y, dz = tgt.pos.z - me.pos.z; if (Math.sqrt(dx * dx + dy * dy + dz * dz) > (spec.range || 6000) * 1.05) return [T.wRange, 'stLkOut']; }
  return [T.wLocked, 'stLkOn'];
}
/** weapons[i]: {part (row or null), w (spec), ammo (reserve), mag, magSize, cd, heat (0..1), overheat, charge (0..1), charging,
 *  reloading, charges, firing, lastShot (game time of the last shot: a pulse when it changes)} */
function ifrHudWeapons(slot, weapons) {
  if (!IFR_HUD_ON || !weapons) return;
  const s = ifrHudSlot(slot);
  for (let i = 0; i < 4; i++) {
    const w = weapons[i], box = 'ifr_w' + i, part = w ? w.part : null, spec = w ? (w.w || (part && part.w)) : null;
    const fam = part ? part.key : '';
    if (s.memo.get(box + 'fam') !== fam) {
      ifrHudOne(slot, s, box + 'i', box + 'icon', fam && IFR_HUD_FAMILIES.has(fam) ? 'stW' + fam : '');
      s.memo.set(box + 'fam', fam);
      ifrHudVar(slot, 'w' + i + 'n', part ? ifrHudShort(String(part.name || fam)).toUpperCase() : '');
    }
    // text = the big figure (ammo, EN per shot); state = the row under it (what the weapon is doing / will do), lk = its colour class.
    // The big figure never carries a percentage any more: '100%  1200' and 'CHARGE 100%' were wider than the old box and got cut.
    let flag = '', text = '', mag = 0, cd = 0, state = '', lk = '';
    if (!part || !spec) flag = 'stNo';
    else if (spec.type === 'shield') { text = w.raised ? 'UP' : 'HOLD'; mag = 1; state = w.raised ? 'RAISED: BLOCKING' : 'HOLD KEY TO BLOCK'; lk = w.raised ? 'stLkOn' : ''; }
    else if (spec.heat_time) {
      const heat = Math.max(0, Math.min(1, w.heat || 0));
      mag = heat; text = spec.ammo !== undefined ? ifrHudFmtNum(w.ammo + w.mag) : IFR_HUD_WSTATE ? 'READY' : Math.round(heat * 100) + '%';
      if (w.overheat || heat >= 0.999) { flag = 'stHot'; state = 'OVERHEATED: WAIT'; lk = 'stLkOut'; }
      else if (heat >= 0.5) { state = 'HEAT ' + ifrHudPct5(heat); lk = heat >= 0.8 ? 'stLkNo' : ''; }
      if (spec.ammo !== undefined && w.ammo + w.mag <= 0) { flag = 'stEmpty'; state = IFR_HUD_TXT.wNoAmmo; lk = 'stLkOut'; }
    } else if (spec.charge && !spec.cd && spec.type !== 'missile') {
      const ch = Math.max(0, Math.min(1, w.charge || 0));
      mag = ch; text = !IFR_HUD_WSTATE && w.charging ? 'CHARGE ' + Math.round(ch * 100) + '%' : 'EN ' + (spec.en_shot || 0);
      if (w.charging) { flag = 'stCharge'; state = ch >= 0.999 ? 'CHARGED: RELEASE' : 'CHARGING ' + ifrHudPct5(ch); lk = ch >= 0.999 ? 'stLkOn' : 'stLkAcq'; } else state = 'HOLD TO CHARGE';
    } else if (spec.mag) {
      const magN = w.mag || 0, reserve = spec.ammo !== undefined ? w.ammo : -1;
      mag = w.magSize > 0 ? magN / w.magSize : magN / spec.mag;
      text = reserve >= 0 ? magN + ' / ' + reserve : String(magN);
      if (reserve >= 0 && !ifrHudFits('w' + i + 'a', text)) text = magN + '/' + reserve;
      if (w.reloading) { flag = 'stReload'; state = 'RELOAD ' + ifrHudSecs(w.reloadT); } else if (magN <= 0 && reserve === 0) { flag = 'stEmpty'; state = IFR_HUD_TXT.wNoAmmo; lk = 'stLkOut'; }
    } else {
      const left = spec.charges !== undefined ? w.charges : (spec.ammo !== undefined ? w.ammo + w.mag : -1);
      text = left >= 0 ? ifrHudFmtNum(left) : (spec.en_shot ? 'EN ' + spec.en_shot : 'READY');
      mag = 1;
      if (left === 0) { flag = 'stEmpty'; state = spec.charges !== undefined ? 'NO CHARGES' : IFR_HUD_TXT.wNoAmmo; lk = 'stLkOut'; }
      else if (spec.type !== 'missile' && w.cd > 0.05 && (spec.cd || 0) >= 2) state = 'READY IN ' + ifrHudSecs(w.cd);
      if (spec.charge && w.charging) { mag = Math.min(1, w.charge || 0); flag = 'stCharge'; state = mag >= 0.999 ? 'CHARGED: RELEASE' : 'CHARGING ' + ifrHudPct5(mag); lk = mag >= 0.999 ? 'stLkOn' : 'stLkAcq'; }
    }
    if (spec && spec.type === 'missile') { const ms = ifrHudMissileState(s.mech, w, spec, s.tgt); state = ms[0]; lk = ms[1]; }
    const cdMax = spec ? (spec.cd || spec.reload || (spec.rate ? 1 / spec.rate : 0)) : 0;
    if (cdMax > 0 && w && w.cd > 0) cd = Math.min(1, w.cd / cdMax);
    ifrHudLadder(slot, 'w' + i + 'm', mag);
    ifrHudLadder(slot, 'w' + i + 'c', cd);
    if (s.memo.get(box + 'txt') !== text) { s.memo.set(box + 'txt', text); ifrHudVar(slot, 'w' + i + 'a', text); }
    if (IFR_HUD_WSTATE) {
      if (s.memo.get(box + 'st') !== state) { s.memo.set(box + 'st', state); ifrHudVar(slot, 'w' + i + 's', state); }
      ifrHudOne(slot, s, box, box + 'lk', lk);
    }
    for (const f of IFR_HUD_WFLAGS) ifrHudSet(slot, box, f, f === flag);
    ifrHudSet(slot, box, 'stSel', !!(w && (w.firing || w.raised)));
    if (w && w.lastShot !== undefined && w.lastShot > -90 && s.memo.get(box + 'shot') !== w.lastShot) { s.memo.set(box + 'shot', w.lastShot); if (s.memo.has(box + 'shotSeen')) ifrHudPop(slot, box); s.memo.set(box + 'shotSeen', 1); }
  }
}

// ---------------------------------------------------------------- lock and threats
const IFR_HUD_THREAT_RANK = { launch: 3, lock: 2, close: 1 };
const IFR_HUD_THREAT_CLS = { launch: 'stLaunch', lock: 'stLock', close: 'stClose' };
function ifrHudDirOf(me, pos) {
  // direction 0..7 (0 ahead, clockwise) of a world point relative to the viewer's torso yaw
  const dx = pos.x - me.pos.x, dy = pos.y - me.pos.y;
  const ang = Math.atan2(dy, dx) * 180 / Math.PI - (me.torsoYaw || 0);     // CCW from ahead
  return Math.round((((-ang) % 360) + 360) % 360 / 45) % 8;
}
const IFR_HUD_LOCKGRID = (IFR_HUD_ON && HUD.lockgrid) || null;    // {step px, x, y (steps each side of the centre), marks}: the bracket can sit on the target
/** where a mech's centre is on the viewer's 1080-high screen, in px from the screen centre (x right, y down), from the camera the adapter sends
 *  the core each tick (me.input.camPos / camDir, 20_players.js cameraRay). null without a camera (bots, spectators). A point behind the camera
 *  is pushed to the nearer screen edge. CS2's default FOV is 90 degrees across a 4:3 screen and grows sideways on wider ones, so one focal length
 *  (IFR_HUD_FOCAL px per unit of tangent) holds for every aspect ratio. Unverified in CS2: the custom camera using that default FOV. */
function ifrHudProject(me, t) {
  const inp = me && me.input, cp = inp && inp.camPos, f = inp && inp.camDir;
  if (!cp || !f || !t || !t.pos) return null;
  const hl = Math.sqrt(f.x * f.x + f.y * f.y);
  if (!(hl > 1e-4)) return null;
  const rx = f.y / hl, ry = -f.x / hl;                                  // right (10_util.js rightOf)
  const ux = ry * f.z, uy = -rx * f.z, uz = rx * f.y - ry * f.x;        // up = right x forward
  const dx = t.pos.x - cp.x, dy = t.pos.y - cp.y, dz = t.pos.z + (t.height || 288) * 0.55 - cp.z;
  const z = dx * f.x + dy * f.y + dz * f.z, x = dx * rx + dy * ry, y = dx * ux + dy * uy + dz * uz;
  if (!(z > 1)) return { x: x >= 0 ? 1e5 : -1e5, y: 0 };
  return { x: IFR_HUD_FOCAL * x / z, y: -IFR_HUD_FOCAL * y / z };
}
/** moves the panel pair <id>x / <id>y (one translate class each) to p {x, y} px from the centre, snapped to the layout's grid; null = the centre */
function ifrHudGridTo(slot, s, id, p) {
  const g = IFR_HUD_LOCKGRID; if (!g) return;
  const kx = p ? Math.max(-g.x, Math.min(g.x, Math.round(p.x / g.step))) : 0, ky = p ? Math.max(-g.y, Math.min(g.y, Math.round(p.y / g.step))) : 0;
  ifrHudOne(slot, s, id + 'x', id + 'x', 'stX' + (kx + g.x));
  ifrHudOne(slot, s, id + 'y', id + 'y', 'stY' + (ky + g.y));
}
/** teammate marks: a green chevron over the head of up to grid.allies living teammates that are on the pilot's screen and within
 *  IFR_HUD_ALLY_RANGE (nearest first). A mark keeps its mech while that mech stays in the set, so marks do not swap places.
 *  ally(v) is the adapter's rule (90_main.js: nobody in Skirmish, every pilot and AI ally in Sortie, the own team elsewhere). */
const IFR_HUD_ALLY_RANGE = 9000, IFR_HUD_ALLY_FAR = 4500;
function ifrHudAllies(slot, me, mechs, ally) {
  if (!IFR_HUD_ON) return;
  const g = IFR_HUD_LOCKGRID, n = g ? g.allies | 0 : 0; if (!n) return;
  const s = ifrHudSlot(slot);
  let own = s.memo.get('frOwn'); if (!own) { own = new Array(n).fill(-1); s.memo.set('frOwn', own); }
  const found = [];
  if (me && me.alive && me.slot === slot && mechs) for (const v of mechs.values()) {
    if (!v || v === me || !v.alive || !v.pos || !ally(v)) continue;
    const dx = v.pos.x - me.pos.x, dy = v.pos.y - me.pos.y, dz = v.pos.z - me.pos.z, d2 = dx * dx + dy * dy + dz * dz;
    if (d2 > IFR_HUD_ALLY_RANGE * IFR_HUD_ALLY_RANGE) continue;
    const h = v.height || 288;
    const p = ifrHudProject(me, { pos: { x: v.pos.x, y: v.pos.y, z: v.pos.z + h * 0.7 }, height: h });     // 1.25 heights up: over the head
    if (!p || Math.abs(p.x) > g.x * g.step || Math.abs(p.y) > g.y * g.step) continue;                  // off the screen or behind
    found.push({ v, p, d2 });
  }
  found.sort((a, b) => a.d2 - b.d2); if (found.length > n) found.length = n;
  const want = new Map(); for (const f of found) want.set(f.v.slot, f);
  for (let i = 0; i < n; i++) if (own[i] >= 0 && !want.has(own[i])) { ifrHudOne(slot, s, 'ifr_fr' + i, 'fr' + i, ''); own[i] = -1; }
  for (const f of found) {
    let i = own.indexOf(f.v.slot);
    if (i < 0) { i = own.indexOf(-1); if (i < 0) continue; own[i] = f.v.slot; }
    ifrHudGridTo(slot, s, 'ifr_fr' + i, f.p);
    ifrHudOne(slot, s, 'ifr_fr' + i, 'fr' + i, f.d2 > IFR_HUD_ALLY_FAR * IFR_HUD_ALLY_FAR ? 'stFar' : 'stOn');
  }
}
/** lock = m.lock {target, stage (0 none, 1 soft, 2 hard), t (s in the stage)}; threats = m.threats [{kind: 'lock'|'launch'|'close',
 *  dir (0..7, 0 ahead, clockwise) | angle (deg, 0 ahead, clockwise) | pos {x,y,z} (needs `me`)}]; target = the locked IF_Mech or
 *  null; me = the viewer's IF_Mech (range, cone and threat directions need it; pass m as the 5th argument) */
function ifrHudLock(slot, lock, threats, target, me) {
  if (!IFR_HUD_ON) return;
  const s = ifrHudSlot(slot);
  const stage = lock ? lock.stage | 0 : 0;
  const softT = me && me.lockSoft > 0 ? me.lockSoft : 0.3, hardT = me && me.lockHard > 0 ? me.lockHard : 0.9;
  const grid = IFR_HUD_LOCKGRID, acq = !!grid && stage === 0 && !!lock && lock.target >= 0 && !!target;   // a target in the ring, not locked yet
  let cls = '', word = '';
  if (stage >= 2) { cls = 'stHard3'; word = IFR_HUD_TXT.lHard; }
  else if (stage === 1) { const b = Math.floor(3 * Math.max(0, (lock.t || 0) - softT) / hardT); cls = b <= 0 ? 'stSoft' : 'stHard' + Math.min(2, b); word = IFR_HUD_TXT.lSoft; }
  else if (acq) { cls = 'stAcq'; word = IFR_HUD_TXT.lAcq; }
  ifrHudOne(slot, s, 'ifr_lock', 'lock', cls);
  s.tgt = cls && target ? target : null;         // ifrHudWeapons: the range check of a locked launcher
  if (cls) {
    if (s.memo.get('tnameRaw') !== (target ? target.name : '')) { s.memo.set('tnameRaw', target ? target.name : ''); ifrHudVar(slot, 'tname', target ? ifrHudFitText('tname', String(target.name || '')) : ''); }
    if (target && me) { const dx = target.pos.x - me.pos.x, dy = target.pos.y - me.pos.y, dz = target.pos.z - me.pos.z; ifrHudNum(slot, 'rng', Math.sqrt(dx * dx + dy * dy + dz * dz), 10); }
    else ifrHudVar(slot, 'rng', '');
    ifrHudLadder(slot, 'tap', target && target.apMax > 0 ? target.ap / target.apMax : 1);
    if (grid) {
      if (s.memo.get('lstate') !== word) { s.memo.set('lstate', word); ifrHudVar(slot, 'lstate', word); }
      ifrHudLadder(slot, 'lkp', stage >= 2 ? 1 : Math.min(1, (lock.t || 0) / (softT + hardT)));
      // the bracket sits on the target: its place on the pilot's own screen (a spectator's camera is not the pilot's: centred there)
      const p = target && me && me.slot === slot ? ifrHudProject(me, target) : null;
      ifrHudGridTo(slot, s, 'ifr_lk', p);
    }
  }
  // multi-lock marks: one diamond per mech a held multi-lock launcher is locking (blinking) or has locked (red)
  if (grid) {
    let k = 0;
    const mechs = typeof game === 'object' && game && game.mechs ? game.mechs : null;
    if (me && me.slot === slot && me.weapons && mechs) for (const w of me.weapons) {
      if (!w || !w.mlock || !w.mlock.length) continue;
      for (const L of w.mlock) {
        if (k >= grid.marks) break;
        const v = mechs.get(L.slot), p = v && v.alive ? ifrHudProject(me, v) : null;
        if (!p) continue;
        const id = 'ifr_ml' + k++;
        ifrHudGridTo(slot, s, id, p);
        ifrHudSet(slot, id, 'stDone', !!L.done); ifrHudSet(slot, id, 'stOn', !L.done);
      }
    }
    const used = s.memo.get('mlN') || 0;
    for (let i = k; i < used; i++) { ifrHudSet(slot, 'ifr_ml' + i, 'stOn', false); ifrHudSet(slot, 'ifr_ml' + i, 'stDone', false); }
    s.memo.set('mlN', k);
  }
  ifrHudSet(slot, 'ifr_assist', 'stOn', stage > 0 && !!(me && me.fcs && me.fcs.f && me.fcs.f.gimbal > 0));
  if (me && me.fcs && me.fcs.f) { const c = me.fcs.f.cone; ifrHudOne(slot, s, 'ifr_cone', 'cone', 'stC' + (c <= 15 ? 0 : c <= 20 ? 1 : c <= 25 ? 2 : c <= 30 ? 3 : 4)); }
  const best = s.memo.get('thr') || new Array(8).fill(''), want = new Array(8).fill('');
  let launch = false;
  if (threats) for (const t of threats) {
    if (!t || !IFR_HUD_THREAT_CLS[t.kind]) continue;
    if (t.kind === 'launch') launch = true;
    let d = t.dir;
    if (d === undefined && t.angle !== undefined) d = Math.round(((t.angle % 360) + 360) % 360 / 45) % 8;
    if (d === undefined && t.pos && me) d = ifrHudDirOf(me, t.pos);
    if (d === undefined) continue;
    d = ((d | 0) % 8 + 8) % 8;
    if (!want[d] || IFR_HUD_THREAT_RANK[t.kind] > IFR_HUD_THREAT_RANK[want[d]]) want[d] = t.kind;
  }
  for (let d = 0; d < 8; d++) {
    if (best[d] === want[d]) continue;
    if (best[d]) ifrHudSet(slot, 'ifr_th' + d, IFR_HUD_THREAT_CLS[best[d]], false);
    if (want[d]) ifrHudSet(slot, 'ifr_th' + d, IFR_HUD_THREAT_CLS[want[d]], true);
    best[d] = want[d];
  }
  s.memo.set('thr', best);
  ifrHudSet(slot, 'ifr_mwarn', 'stOn', launch);
}

// ---------------------------------------------------------------- radar
function ifrHudGrid(slot, s, id, cellOrNull) {
  const prev = s.grid.get(id);
  if (prev === cellOrNull) return;
  if (prev !== undefined && prev !== null) ifrHudSet(slot, id, 'stG' + prev, false);
  if (cellOrNull !== null) ifrHudSet(slot, id, 'stG' + cellOrNull, true);
  s.grid.set(id, cellOrNull);
}
/** world offset (dx, dy) from the viewer, turned so the viewer's yaw points up, into a grid cell (clamped to the disc) */
function ifrHudCell(dx, dy, yaw) {
  const a = (yaw || 0) * Math.PI / 180, fx = Math.cos(a), fy = Math.sin(a);
  let x = (dx * fy - dy * fx) / IFR_HUD_RADAR_RANGE, y = (dx * fx + dy * fy) / IFR_HUD_RADAR_RANGE;   // x right, y forward
  const r = Math.sqrt(x * x + y * y);
  if (r > 0.9) { x *= 0.9 / r; y *= 0.9 / r; }   // beyond range: pinned just inside the drawn ring
  const n = IFR_HUD_RADAR_CELLS;
  return Math.max(0, Math.min(n - 1, Math.floor((1 - y) / 2 * n))) * n + Math.max(0, Math.min(n - 1, Math.floor((x + 1) / 2 * n)));
}
/** dots: [{x, y (world offsets from the viewer), team, kind: 'mech' | 'bounty' | 'target' | 'boss'}], myYaw (torso yaw),
 *  myPos (world position or null: no mech, the radar empties). Points A/B/C and the drop zones come from ARENA and the
 *  last ifrHudMode call. Call it about 8 times a second per player (90_main: every 8th tick). */
function ifrHudRadar(slot, dots, myYaw, myPos) {
  if (!IFR_HUD_ON) return;
  const s = ifrHudSlot(slot);
  s.pos = myPos ? { x: myPos.x, y: myPos.y, z: myPos.z } : null;     // ifrHudMode: which capture zone the viewer stands in
  let n = 0;
  if (myPos && dots) for (const d of dots) {
    if (!d || n >= IFR_HUD_RADAR_DOTS) continue;
    const id = 'ifr_rd' + n++, ally = s.team ? d.team === s.team : d.team === 3;
    ifrHudGrid(slot, s, id, ifrHudCell(d.x, d.y, myYaw));
    ifrHudSet(slot, id, 'stA', ally); ifrHudSet(slot, id, 'stE', !ally);
    ifrHudSet(slot, id, 'stBig', d.kind === 'bounty'); ifrHudSet(slot, id, 'stBoss', d.kind === 'boss'); ifrHudSet(slot, id, 'stTgt', d.kind === 'target');
  }
  const used = s.memo.get('dots') || 0;
  for (let i = n; i < used; i++) ifrHudGrid(slot, s, 'ifr_rd' + i, null);
  s.memo.set('dots', n);
  const arena = typeof ARENA === 'object' && ARENA ? ARENA : null;
  const pts = myPos && arena && arena.points ? arena.points : [];
  const seen = { A: false, B: false, C: false };
  for (const p of pts) {
    if (!seen.hasOwnProperty(p.id) || !p.pos) continue;
    seen[p.id] = true;
    const id = 'ifr_rd' + p.id, own = s.points && s.points[p.id] ? s.points[p.id] : { owner: 0, cap: false };
    ifrHudGrid(slot, s, id, ifrHudCell(p.pos[0] - myPos.x, p.pos[1] - myPos.y, myYaw));
    ifrHudSet(slot, id, 'stOwnT', own.owner === 2); ifrHudSet(slot, id, 'stOwnCT', own.owner === 3); ifrHudSet(slot, id, 'stCap', !!own.cap);
  }
  for (const L in seen) if (!seen[L]) ifrHudGrid(slot, s, 'ifr_rd' + L, null);
  const drops = myPos && arena && arena.drops ? arena.drops : null;
  for (const k of ['a', 'e']) {
    let cell = null;
    if (drops && s.team) {
      const list = drops[(k === 'a') === (s.team === 2) ? 't' : 'ct'];
      if (list && list.length) cell = ifrHudCell(list[0][0] - myPos.x, list[0][1] - myPos.y, myYaw);
    }
    ifrHudGrid(slot, s, 'ifr_rdD' + k, cell);
  }
  if (myPos) ifrHudNum(slot, 'rrange', IFR_HUD_RADAR_RANGE, 100);
}

// ---------------------------------------------------------------- mode panel, objective chips, capture strip
// The mode tag (its own colour per mode) and the objective line say which mode is on at all times; Conquest / Sortie / KOTH / CTF also get
// the objective chips (who holds what, a progress bar each) and the capture strip while something is being taken (10 Nov 2026 playtest:
// "not much indication of which mode is playing"). Objective state is the core's (80_game.js captureStep, 85_objectives.js); the newer
// fields (points[].nT / nCT / scoring, match.hillLeft, flags[].returnMax / carrierTeam) are read defensively.
const IFR_HUD_MODE_TAG = { tb: 'TDM', cq: 'CONQUEST', sk: 'FFA', so: 'SORTIE', kh: 'KOTH', ctf: 'CTF' };
const IFR_HUD_MODE_NAMES = { tb: 'TEAM DEATHMATCH', cq: 'CONQUEST', sk: 'FREE FOR ALL', so: 'SORTIE  CO-OP', kh: 'KING OF THE HILL', ctf: 'CAPTURE THE FLAG' };
const IFR_HUD_TEAM = { 2: 'T', 3: 'CT' };
const IFR_HUD_AI = ['AI EASY', 'AI NORMAL', 'AI HARD'];
/** 'AI EASY' | 'AI NORMAL' | 'AI HARD' for the arena copy the viewer is in, '' when the core has no fill skill (or no AI fill is playing) */
function ifrHudAiLevel(slot) {
  try {
    if (typeof IF_Ai !== 'function' && typeof IF_Ai !== 'object') return '';
    if (typeof IF_Ai.fillSkill !== 'function' || typeof game !== 'object' || !game) return '';
    const g = game.list && typeof game.arenaIndexOf === 'function' ? (game.list[game.arenaIndexOf(slot)] || game.list[0]).g : game;
    if (!g || !g.mechs) return '';
    let fill = false; for (const m of g.mechs.values()) if (m.fill || m.npc || m.human === false) { fill = true; break; }
    if (!fill) return '';
    return IFR_HUD_AI[Math.max(0, Math.min(2, Math.round(IF_Ai.fillSkill(g))))] || '';
  } catch (err) { return ''; }
}
function ifrHudClock(sec) { sec = Math.max(0, Math.ceil(Number(sec) || 0)); const m = Math.floor(sec / 60), s = sec % 60; return m + ':' + (s < 10 ? '0' : '') + s; }
/** the mode's goal in a sentence (the intro slate); numbers from the last match the HUD saw, else the core's defaults */
function ifrHudObjective(mode, M) {
  M = M || {};
  switch (mode) {
    case 'tb': return 'MOST KILLS WINS. FIRST TEAM TO ' + (M.killTarget || 60) + ' KILLS TAKES THE ROUND.';
    case 'cq': return 'CAPTURE AND HOLD A, B AND C. HELD POINTS DRAIN ENEMY TICKETS; EVERY DEATH COSTS 2.';
    case 'sk': return 'EVERY PILOT FOR THEMSELVES. FIRST TO ' + (M.killTarget || 25) + ' KILLS WINS.';
    case 'so': return 'CO-OP: HOLD THE BEACON AGAINST WAVES OF AI MECHS. A BOSS EVERY THIRD WAVE.';
    case 'kh': return 'HOLD THE HILL WITH NO ENEMY ON IT TO SCORE 1 A SECOND. IT MOVES EVERY 2 MINUTES. FIRST TO ' + (M.khTarget || 150) + '.';
    case 'ctf': return 'TAKE THE ENEMY FLAG TO YOUR OWN FLAG WHILE YOURS IS HOME. ' + (M.ctfCaptures || 3) + ' CAPTURES WIN.';
    default: return '';
  }
}
/** one objective chip k (0 left, 1 middle, 2 right): letter, owner colour of the letter box, blink, the bar's team colour (-1 contested) and fill, a word */
function ifrHudChip(slot, k, on, letter, owner, blink, fill, frac, text) {
  const id = 'ifr_ob' + k;
  ifrHudSet(slot, id, 'stOn', !!on);
  if (!on) return;
  ifrHudVar(slot, 'ob' + k + 'k', letter); ifrHudVar(slot, 'ob' + k + 't', text);
  ifrHudSet(slot, 'ifr_obk' + k, 'stOwnT', owner === 2); ifrHudSet(slot, 'ifr_obk' + k, 'stOwnCT', owner === 3); ifrHudSet(slot, 'ifr_obk' + k, 'stCap', !!blink);
  ifrHudSet(slot, id, 'stT', fill === 2); ifrHudSet(slot, id, 'stCT', fill === 3); ifrHudSet(slot, id, 'stCont', fill === -1);
  ifrHudLadder(slot, 'ob' + k + 'p', frac);
}
/** the wide capture bar: team 2 / 3 colours it, -1 contested (red, flashing); warn = amber text (your flag is taken) */
function ifrHudCapStrip(slot, on, text, team, frac, warn) {
  ifrHudSet(slot, 'ifr_cap', 'stOn', !!on);
  if (!on) return;
  ifrHudVar(slot, 'capl', text);
  ifrHudSet(slot, 'ifr_cap', 'stT', team === 2); ifrHudSet(slot, 'ifr_cap', 'stCT', team === 3); ifrHudSet(slot, 'ifr_cap', 'stCont', team === -1);
  ifrHudSet(slot, 'ifr_cap', 'stWarn', !!warn);
  ifrHudLadder(slot, 'capbar', frac);
}
const ifrHudPct = (f) => Math.round(Math.max(0, Math.min(1, Number(f) || 0)) * 100) + ' %';
/** a capture point's state: who is taking it (from nT / nCT when the core sets them, else the side its value leans to), the chip word,
 *  whether it is changing hands now */
function ifrHudPointState(p) {
  const prog = Math.max(0, Math.min(1, Number(p.progress) || 0)), owner = p.owner | 0, lean = p.capTeam | 0;
  let taker = 0;
  if (p.nT !== undefined || p.nCT !== undefined) { const a = p.nT | 0, b = p.nCT | 0; taker = a > 0 && !b ? 2 : b > 0 && !a ? 3 : 0; }
  const held = owner && lean === owner && prog >= 0.999;
  let active = !!p.contested || (taker && !(held && taker === owner));
  if (p.nT === undefined && p.nCT === undefined) active = !!p.contested || (prog > 0 && prog < 0.999);   // an older core: changing = partway
  let word;
  if (p.contested) word = 'CONTESTED';
  else if (held) word = IFR_HUD_TEAM[owner] + (p.scoring ? ' SCORES' : ' HOLDS');
  else if (prog > 0.001 && lean) word = IFR_HUD_TEAM[lean] + ' ' + ifrHudPct(prog);
  else word = 'NEUTRAL';
  return { prog, owner, lean, taker, held, active, word };
}
/** match = game.match {mode, phase, timeLeft, scores:{2,3}, tickets:{2,3}?, points:[{id, owner, progress, capTeam, contested, nT?, nCT?, pos, radius}],
 *  killTarget, wave?, waves?, boss?:{ap, apMax}, flags?, hillLeft?, khTarget?, ctfCaptures?}; myTeam = the viewer's team (2 | 3): the accent colour and
 *  the radar's ally colours. Call it every 16th tick or so. */
function ifrHudMode(slot, match, myTeam) {
  if (!IFR_HUD_ON || !match) return;
  const s = ifrHudSlot(slot);
  s.match = match;
  if (myTeam !== undefined && myTeam !== s.team) ifrHudTeam(slot, myTeam);
  const mode = match.mode || 'tb';
  ifrHudVar(slot, 'mode', IFR_HUD_MODE_TAG[mode] || String(mode).toUpperCase());
  ifrHudOne(slot, s, 'ifr_mtag', 'mtag', IFR_HUD_MODE_TAG[mode] ? 'stM' + mode : '');
  ifrHudVar(slot, 'clock', match.phase === 'warmup' ? 'WARMUP' : match.phase === 'podium' || match.phase === 'over' ? 'END' : ifrHudClock(match.timeLeft));
  const sc = match.scores || {}, tk = match.tickets;
  let sub;
  if (mode === 'cq' && tk) { sub = 'TICKETS   HOLD A B C TO DRAIN THE ENEMY'; ifrHudNum(slot, 'scoreT', tk[2] || 0, 1); ifrHudNum(slot, 'scoreCT', tk[3] || 0, 1); }
  else if (mode === 'sk') { sub = 'FREE FOR ALL   FIRST TO ' + (match.killTarget || 25) + ' KILLS'; ifrHudNum(slot, 'scoreT', sc[2] || 0, 1); ifrHudVar(slot, 'scoreCT', ''); }
  else if (mode === 'kh') { const left = match.hillLeft; sub = 'KING OF THE HILL   FIRST TO ' + (match.khTarget || 150) + (left > 0 && match.allPoints && match.allPoints.length > 1 ? '   MOVES ' + ifrHudClock(left) : ''); ifrHudNum(slot, 'scoreT', sc[2] || 0, 1); ifrHudNum(slot, 'scoreCT', sc[3] || 0, 1); }
  else if (mode === 'ctf') { sub = 'CAPTURE THE FLAG   ' + (match.ctfCaptures || 3) + ' CAPTURES WIN'; ifrHudNum(slot, 'scoreT', sc[2] || 0, 1); ifrHudNum(slot, 'scoreCT', sc[3] || 0, 1); }
  else if (mode === 'so') { sub = 'CO-OP   ' + (match.wave ? 'WAVE ' + match.wave + (match.waves ? ' / ' + match.waves : '') + '   ' : '') + 'HOLD THE BEACON'; ifrHudNum(slot, 'scoreT', sc[2] || 0, 1); ifrHudNum(slot, 'scoreCT', sc[3] || 0, 1); }
  else { sub = 'TEAM DEATHMATCH   ' + (match.killTarget ? 'FIRST TO ' + match.killTarget + ' KILLS' : 'MOST KILLS WINS'); ifrHudNum(slot, 'scoreT', sc[2] || 0, 1); ifrHudNum(slot, 'scoreCT', sc[3] || 0, 1); }
  // the AI fill's level (easy / normal / hard: it follows how the humans fare, 50_ai.js fillSkill), when the line has room for it
  { const ai = ifrHudAiLevel(slot); if (ai && ifrHudFits('sub', sub + '   ' + ai)) sub += '   ' + ai; }
  ifrHudVar(slot, 'sub', sub);
  // the pilot plate: YOUR TEAM against ENEMY in the mode's own score (tickets in Conquest; in FFA your kills against the leader's)
  if (IFR_HUD_TEXT.pmy) {
    const my = s.team === 3 ? 3 : 2, en = my === 2 ? 3 : 2;
    let a = sc[my] || 0, b = sc[en] || 0;
    if (mode === 'cq' && tk) { a = tk[my] || 0; b = tk[en] || 0; }
    else if (mode === 'sk') { const sum = s.mech && s.mech.sum; a = sum ? sum.kills | 0 : 0; b = sc[2] || 0; }
    ifrHudNum(slot, 'pmy', a, 1); ifrHudNum(slot, 'pen', b, 1);
  }
  // objective chips and the capture strip
  const pts = (mode === 'cq' || mode === 'so' || mode === 'kh') && match.points && match.points.length ? match.points : null;
  const used = [false, false, false];
  let strip = null;
  s.points = null;
  if (pts) {
    s.points = {};
    const here = (p) => !!(s.pos && p.pos && Math.hypot(s.pos.x - p.pos.x, s.pos.y - p.pos.y) <= (p.radius || 700) && Math.abs(s.pos.z - p.pos.z) < 800);
    pts.forEach((p, i) => {
      const st = ifrHudPointState(p), k = mode === 'cq' ? i : 1;
      s.points[p.id] = { owner: st.owner, cap: st.active };
      if (k > 2 || used[k]) return;
      used[k] = true;
      const letter = String(p.id || 'ABC'[i] || '?');
      ifrHudChip(slot, k, true, letter, st.owner, st.active, p.contested ? -1 : st.lean, p.contested ? 1 : st.prog, st.word);
      if (!st.active) return;
      const name = mode === 'kh' ? 'HILL ' + letter : mode === 'so' ? 'BEACON' : letter;
      let text, team = st.lean, frac = st.prog;
      if (p.contested) { text = name + ' CONTESTED'; team = -1; frac = 1; }
      else if (st.taker && st.taker === st.lean) text = IFR_HUD_TEAM[st.taker] + (mode === 'kh' ? ' TAKING THE HILL  ' : ' CAPTURING ' + name + '  ') + ifrHudPct(frac);
      else if (st.taker) text = IFR_HUD_TEAM[st.taker] + ' NEUTRALISING ' + name + '  ' + ifrHudPct(1 - frac);
      else text = name + '  ' + (st.lean ? IFR_HUD_TEAM[st.lean] + ' ' : '') + ifrHudPct(frac);
      const cand = { text, team, frac, warn: false, mine: here(p) };
      if (!strip || (cand.mine && !strip.mine)) strip = cand;
    });
  } else if (mode === 'ctf' && match.flags) {
    const F = match.flags;
    for (const team of [2, 3]) {
      const f = F[team], k = team === 2 ? 0 : 2;
      if (!f) continue;
      used[k] = true;
      const enemy = f.carrierTeam || (team === 2 ? 3 : 2), base = F[enemy] && F[enemy].home;
      let frac = 1, fill = team, word = 'HOME';
      if (f.state === 'carried') {
        // the carrier's way home: 0 at this flag's base, 1 at the capture point (their own flag's base)
        const d0 = base && f.home ? Math.hypot(f.home.x - base.x, f.home.y - base.y) : 0, d = base && f.pos ? Math.hypot(f.pos.x - base.x, f.pos.y - base.y) : 0;
        frac = d0 > 1 ? Math.max(0, Math.min(1, 1 - d / d0)) : 0; fill = enemy; word = 'TAKEN ' + ifrHudPct(frac);
        const mine = f.carrier === slot, ownFlag = team === s.team;
        const cand = mine ? { text: 'FLAG IN HAND  ' + ifrHudPct(frac) + ' HOME', team: enemy, frac, warn: false, rank: 3 }
          : ownFlag ? { text: 'ENEMY HAS YOUR FLAG  ' + ifrHudPct(frac), team: enemy, frac, warn: true, rank: 2 }
            : { text: 'ALLY HAS THE FLAG  ' + ifrHudPct(frac), team: enemy, frac, warn: false, rank: 1 };
        if (!strip || cand.rank > strip.rank) strip = cand;
      } else if (f.state === 'dropped') {
        const max = f.returnMax > 0 ? f.returnMax : 20, left = Math.max(0, Number(f.returnT) || 0);
        frac = left / max; word = 'DROP ' + Math.ceil(left) + ' S';
        const cand = { text: IFR_HUD_TEAM[team] + ' FLAG DROPPED  ' + Math.ceil(left) + ' S', team, frac, warn: team === s.team, rank: 0 };
        if (!strip) strip = cand;
      }
      ifrHudChip(slot, k, true, IFR_HUD_TEAM[team], team, f.state !== 'home', fill, frac, word);
    }
  }
  for (let k = 0; k < 3; k++) if (!used[k]) ifrHudChip(slot, k, false);
  ifrHudSet(slot, 'ifr_obj', 'stOn', used[0] || used[1] || used[2]);
  if (strip) ifrHudCapStrip(slot, true, strip.text, strip.team, strip.frac, strip.warn); else ifrHudCapStrip(slot, false);
  const boss = match.boss && match.boss.apMax > 0 ? match.boss : null;
  ifrHudSet(slot, 'ifr_modebox', 'stBoss', !!boss);
  if (boss) ifrHudLadder(slot, 'bap', boss.ap / boss.apMax);
}

// ---------------------------------------------------------------- the pilot's identity, the daily contract, the server's top pilots (S2 / S3)
// Server data arrives through 70_server.js (the profile q1, the leaderboard t1); stand-alone the session's own profile is shown and the
// contract row and the leaderboard stay hidden. Layouts without these slots (an older hud.json) are left alone.
const ifrHudXpShort = (n) => { n = Math.max(0, Number(n) || 0); return n >= 1e6 ? (Math.floor(n / 1e4) / 100) + 'M' : n >= 1e5 ? Math.floor(n / 1000) + 'K' : ifrHudFmtNum(n); };
/** the daily contract row: the open contract nearest to done, or that all are done; '' with none */
function ifrHudDaily(daily) {
  if (!daily || !daily.length) return '';
  const open = daily.filter((d) => d.progress < d.goal), done = daily.length - open.length;
  if (!open.length) return 'DAILY CONTRACTS DONE  ' + done + '/' + daily.length;
  open.sort((a, b) => b.progress / b.goal - a.progress / a.goal);
  const d = open[0], core = (typeof IF_Career === 'object' ? IF_Career.contractLabel(d.code) : 'CONTRACT') + ' ' + d.progress + ' / ' + d.goal;
  // as much context as the row holds: "DAILY 1/3  WIN ROUNDS 1 / 2", then without the count, then the contract alone
  for (const t of ['DAILY ' + done + '/' + daily.length + '  ' + core, 'DAILY  ' + core, core]) if (ifrHudFits('dly', t)) return t;
  return core;
}
/** the strip under the streak meter: [BADGE] CALLSIGN   TITLE, and the daily contract. Called when the profile changes and now and then. */
function ifrHudPilot(slot) {
  if (!IFR_HUD_ON || !IFR_HUD_TEXT.ptag || typeof srvIdentity !== 'function') return;
  const pe = person(slot), pr = pe ? srvProfile(pe) : null, id = srvIdentity(slot);
  let tag = ifrHudFitText('ptag', (id.tag ? '[' + id.tag + '] ' : '') + id.name);
  if (id.title && ifrHudFits('ptag', tag + '   ' + id.title)) tag += '   ' + id.title;
  const dly = pr ? ifrHudDaily(pr.daily) : '';
  const show = !!(pr && (id.tag || id.title || pr.callsign || dly));
  ifrHudSet(slot, 'ifr_ident', 'stOn', show);
  if (show) { ifrHudVar(slot, 'ptag', tag); ifrHudVar(slot, 'dly', dly); }
}
/** the top pilots beside the podium: board {total, rows: [{name, rank, xp}]} (null hides it), me {place, rank, xp} */
function ifrHudBoard(slot, board, me) {
  if (!IFR_HUD_ON || !IFR_HUD_TEXT.lbme) return;
  const on = !!(board && board.rows && board.rows.length);
  ifrHudSet(slot, 'ifr_lb', 'stOn', on);
  if (!on) return;
  ifrHudVar(slot, 'lbh', ifrHudXpShort(board.total) + ' PILOT' + (board.total === 1 ? '' : 'S'));
  for (let i = 0; i < 5; i++) {
    const x = board.rows[i];
    ifrHudVar(slot, 'lb' + i + 'n', x ? ifrHudFitText('lb' + i + 'n', x.name, (i + 1) + '  ') : '');
    ifrHudVar(slot, 'lb' + i + 'v', x ? 'R' + x.rank + '  ' + ifrHudXpShort(x.xp) : '');
  }
  ifrHudVar(slot, 'lbme', me && me.place ? ifrHudFitText('lbme', 'YOU  # ' + ifrHudFmtNum(me.place) + '   R' + me.rank + '   ' + ifrHudXpShort(me.xp) + ' XP') : me ? 'YOU: NOT PLACED YET' : '');
}

// ---------------------------------------------------------------- feed: kill confirm, XP ticker, badges
/** f: {kill?: text (3 s pop), xp?: number (+N XP, 2.5 s pop), streak?: n (shown from 2), bounty?: bool, rookie?: bool}; only
 *  the keys given are touched */
function ifrHudFeed(slot, f) {
  if (!IFR_HUD_ON || !f) return;
  const s = ifrHudSlot(slot);
  if (f.kill !== undefined) {
    if (f.kill) { ifrHudVar(slot, 'kill', ifrHudFitText('kill', f.kill, 'DESTROYED  ')); ifrHudSet(slot, 'ifr_kill', 'stOn', true); ifrHudPop(slot, 'ifr_kill'); s.killUntil = ifrHudNow() + IFR_HUD_KILL_SECONDS; }
    else { ifrHudSet(slot, 'ifr_kill', 'stOn', false); s.killUntil = 0; }
  }
  if (f.xp !== undefined) {
    if (f.xp) { ifrHudVar(slot, 'xp', (f.xp > 0 ? '+' : '') + ifrHudFmtNum(f.xp) + ' XP'); ifrHudSet(slot, 'ifr_xp', 'stOn', true); ifrHudPop(slot, 'ifr_xp'); s.xpUntil = ifrHudNow() + IFR_HUD_XP_SECONDS; }
    else { ifrHudSet(slot, 'ifr_xp', 'stOn', false); s.xpUntil = 0; }
  }
  if (f.streak !== undefined && IFR_HUD_PANELS.has('ifr_streakb')) { ifrHudSet(slot, 'ifr_streakb', 'stOn', f.streak >= 2); if (f.streak >= 2) ifrHudVar(slot, 'streak', 'x' + f.streak); }   // an older layout's badge
  if (f.bounty !== undefined) ifrHudSet(slot, 'ifr_bounty', 'stOn', !!f.bounty);
  if (f.rookie !== undefined) ifrHudSet(slot, 'ifr_rookie', 'stOn', !!f.rookie);
}

// ---------------------------------------------------------------- slates (90_main.js shapes)
const IFR_HUD_PODIUM_ROWS = 6;
/** kind 'intro' {title, arena, mode (key)} | 'death' {killer (name), weapon (key or name), respawn (seconds)} |
 *  'podium' {winner (team), podium: [{slot, name, kills}], me: pilotSummary {xp, credits, kills, assists, captures, damage,
 *  pveKills, bossKills, won, streakBest}, team} | 'spectator' {name, slot} | 'none' (back to the fight HUD) | 'off' */
function ifrHudSlate(slot, kind, data) {
  if (!IFR_HUD_ON) return;
  data = data || {};
  const s = ifrHudSlot(slot);
  if (kind !== 'death') s.deathAt = 0;
  if (kind === 'intro') {
    ifrHudScreen(slot, 'intro');
    ifrHudVar(slot, 'arena', ifrHudFitText('arena', String(data.arena || '')));
    ifrHudVar(slot, 'imode', IFR_HUD_MODE_NAMES[data.mode] || String(data.mode || '').toUpperCase());
    ifrHudOne(slot, s, 'ifr_imbar', 'imbar', IFR_HUD_MODE_TAG[data.mode] ? 'stM' + data.mode : '');
    let M = s.match && s.match.mode === data.mode ? s.match : null;
    if (!M && typeof game === 'object' && game && typeof game.matchFor === 'function') { try { M = game.matchFor(slot); } catch (err) { M = null; } }
    const ob = ifrHudWrap(['iobj', 'iobj2'], data.objective || ifrHudObjective(data.mode, M));
    ifrHudVar(slot, 'iobj', ob[0] || ''); ifrHudVar(slot, 'iobj2', ob[1] || '');
    ifrHudVar(slot, 'ihint', data.hint || 'ANY MENU KEY: GARAGE');
  } else if (kind === 'death') {
    ifrHudScreen(slot, 'death');
    ifrHudVar(slot, 'killer', ifrHudFitText('killer', String(data.killer || '')));
    ifrHudVar(slot, 'kframe', ifrHudFitText('kframe', String(data.frame || '')));
    ifrHudVar(slot, 'kweapon', ifrHudFitText('kweapon', ifrHudWeaponName(data.weapon)));
    s.deathAt = ifrHudNow(); s.deathWait = Number(data.respawn) > 0 ? Number(data.respawn) : 6;
    ifrHudVar(slot, 'respawn', 'RESPAWN IN ' + Math.ceil(s.deathWait));
  } else if (kind === 'podium') {
    ifrHudScreen(slot, 'podium');
    const w = data.winner, mine = data.team;
    ifrHudVar(slot, 'phead', w === 2 || w === 3 ? (w === mine ? 'VICTORY' : 'DEFEAT') : 'ROUND OVER');
    ifrHudVar(slot, 'psub', data.sub || '');
    const top = data.podium || [];
    for (let i = 0; i < 3; i++) {
      const t = top[i];
      // a pilot's title (the profile that follows the pilot) beside the kills, when the row has room for both
      let ps = t ? (t.kills | 0) + ' KILLS' : '';
      if (t && t.slot < 64 && typeof srvIdentity === 'function') { const idt = srvIdentity(t.slot); if (idt.title && ifrHudFits('ps' + i, ps + '   ' + idt.title)) ps += '   ' + idt.title; }
      ifrHudVar(slot, 'pn' + i, t ? ifrHudFitText('pn' + i, t.name) : ''); ifrHudVar(slot, 'ps' + i, ps);
      ifrHudSet(slot, 'ifr_pc' + i, 'stT', !!t && t.team === 2); ifrHudSet(slot, 'ifr_pc' + i, 'stCT', !!t && t.team === 3); ifrHudSet(slot, 'ifr_pc' + i, 'stMe', !!t && t.slot === slot);
    }
    const me = data.me, rows = [];
    if (me) {
      rows.push({ label: 'KILLS ' + (me.kills | 0), value: 'ASSISTS ' + (me.assists | 0) });
      if (me.captures) rows.push({ label: 'CAPTURES', value: String(me.captures) });
      if (me.pveKills || me.bossKills) rows.push({ label: 'PVE KILLS', value: (me.pveKills | 0) + (me.bossKills ? '   BOSS ' + me.bossKills : '') });
      rows.push({ label: 'DAMAGE', value: ifrHudFmtNum(me.damage || 0) });
      rows.push({ label: 'BEST STREAK', value: String(me.streakBest | 0) });
      rows.push({ label: 'TOTAL   +' + ifrHudFmtNum(me.xp || 0) + ' XP', value: '+' + ifrHudFmtNum(me.credits || 0) + ' CR' });     // XP left, credits right: both in one cell were cut at six figures
    }
    for (let i = 0; i < IFR_HUD_PODIUM_ROWS; i++) { const r = rows[i]; ifrHudVar(slot, 'pt' + i + 'l', r ? r.label : ''); ifrHudVar(slot, 'pt' + i + 'v', r ? r.value : ''); }
    ifrHudVar(slot, 'pfoot', data.foot || 'NEXT ROUND SOON');
    // the server's top pilots and this pilot's place among them (hidden stand-alone and before the first leaderboard)
    if (typeof srvBoard !== 'undefined') {
      const pe = person(slot), pr = pe ? srvProfile(pe) : null;
      ifrHudBoard(slot, serverMode ? srvBoard : null, pe && pe.pilot ? { place: pr ? pr.place : 0, rank: pe.pilot.rank, xp: pe.pilot.xp } : null);
    }
  } else if (kind === 'spectator' || kind === 'spec') {
    ifrHudScreen(slot, 'spec');
    ifrHudVar(slot, 'spec', ifrHudFitText('spec', String(data.name || ''), 'WATCHING ', '   SPACE: NEXT PILOT'));
  } else if (kind === 'garage') ifrHudScreen(slot, 'garage');
  else if (kind === 'off') ifrHudScreen(slot, 'off');
  else ifrHudScreen(slot, 'fight');
}

// ---------------------------------------------------------------- cards: controls and loadout (evening playtest 10 Nov 2026)
const IFR_HUD_CARDS = { controls: 'ifr_ctrl', loadout: 'ifr_load' };
/** shows card `name` ('controls' | 'loadout') for `seconds` (0 hides it now) */
function ifrHudCard(slot, name, seconds) {
  const id = IFR_HUD_CARDS[name];
  if (!IFR_HUD_ON || !id || !IFR_HUD_PANELS.has(id)) return;
  const s = ifrHudSlot(slot);
  s.cards[name] = seconds > 0 ? ifrHudNow() + seconds : 0;
  ifrHudSet(slot, id, 'stOn', seconds > 0);
}
function ifrHudCardOn(slot, name) { const s = ifrHudSlots.get(slot); return !!(s && s.cards[name] > ifrHudNow()); }
function ifrHudCardTick(s, now) {
  for (const k in s.cards) if (s.cards[k] && now >= s.cards[k]) { s.cards[k] = 0; ifrHudSet(s.slot, IFR_HUD_CARDS[k], 'stOn', false); }
}
// a weapon's job in a word or two (the loadout card), by part key; the fallback is by type
const IFR_HUD_ROLE = { rifle: 'MID RANGE', gatling: 'SUSTAINED FIRE', shotgun: 'CLOSE RANGE', laser: 'CHARGE BEAM', bazooka: 'SPLASH, STAGGER', grenade: 'LOBBED SPLASH', blade: 'MELEE LUNGE',
  plasma: 'SPLASH BOLTS', rail: 'LONG RANGE', handmsl: 'LOCK-ON ROCKETS', shield: 'HOLD TO BLOCK', smg: 'CLOSE RANGE', pilebunker: 'MELEE STAGGER', sniper: 'EXTREME RANGE', burstrifle: 'LONG RANGE',
  flamer: 'CLOSE, BURNS', eshotgun: 'CLOSE, USES EN', heavyblade: 'MELEE SWEEP', vm6: 'LOCK-ON MISSILES', dualmsl: 'LOCK-ON MISSILES', lasercannon: 'CHARGE BEAM', grenadecannon: 'BIG BLAST',
  autocannon: 'HEAVY ROUNDS', flak: 'ANTI-AIR BURST', pulseshield: 'BUBBLE SHIELD', repair: 'REPAIRS AP', decoy: 'BREAKS LOCKS', vm12: 'LOCK-ON MISSILES', minelayer: 'DROPS MINES',
  orbitdrones: 'ATTACK DRONES', multimsl: 'HOLD: MULTI-LOCK', clusterart: 'AREA BARRAGE' };
const IFR_HUD_ROLE_TYPE = { proj: 'GUN', hitscan: 'BEAM', lob: 'LOBBED SHELL', melee: 'MELEE', missile: 'LOCK-ON MISSILES', shield: 'HOLD TO BLOCK', ability: 'ABILITY' };
function ifrHudRole(part) { if (!part) return ''; const w = part.w || {}; return IFR_HUD_ROLE[part.key] || IFR_HUD_ROLE_TYPE[w.type] || ''; }
// a frame's trait on the loadout card: how it is used (the key), then what it does, each a row (the long form is in the garage)
const IFR_HUD_TRAIT = {
  krasnaya: ['PASSIVE', 'FIRST HIT AFTER A QUICK BOOST +20 %'], stryder: ['PASSIVE', 'QUICK BOOSTS CHEAPER AND FASTER'], lisa: ['SPACE AGAIN IN THE AIR', 'A SECOND JUMP FOR 250 EN'],
  whiteglint: ['PASSIVE', 'EN REFILLS FASTER AFTER A QUICK BOOST'], atlas: ['PASSIVE', 'SLOW REPAIR AFTER 5 S UNHIT'], supplice: ['PASSIVE', 'ASSAULT BOOST 25 % CHEAPER'],
  rx78: ['PASSIVE', 'SHIELDS BLOCK 30 % MORE'], ogre: ['PASSIVE', '-15 % DAMAGE FROM THE FRONT'], noblesse: ['PASSIVE', 'SHOULDER RELOAD 20 % FASTER'],
  legion: ['HOLD F', '3 S: -25 % FRONT DAMAGE, HALF SPEED'], barbatos: ['PASSIVE', 'MELEE HEALS 15 % OF ITS DAMAGE'], mule: ['STAND STILL 1 S', '-30 % DAMAGE, TIGHTER SPREAD'],
  ronin: ['DOUBLE-TAP CTRL', 'A SHORT UNTOUCHABLE DASH (600 EN)'], unicorn: ['PASSIVE', 'OVERDRIVE FILLS 30 % FASTER'], me3atlas: ['PASSIVE', 'NO STAGGER RIGHT AFTER A STAGGER'],
  sandviper: ['HOLD A LOCK 1.5 S', 'MARKS IT: +10 % DAMAGE, ON RADAR'], kestrel: ['PASSIVE', '-35 % DAMAGE IN A QUICK BOOST'], warden: ['HOLD F', 'BARRIER FOR YOU AND NEAR ALLIES'],
  bastion: ['HOLD F ON THE GROUND', 'ROOTED 4 S, +20 % DAMAGE'],
};
/** the loadout card for mech m: the four weapons by the key that fires them (M1 / M2 / R / E), each with its role, the frame and its trait
 *  (how to use it, what it does). Shown for `seconds` (default 9). m: IF_Mech (frame part, weapons[4]). */
function ifrHudLoadout(slot, m, seconds) {
  if (!IFR_HUD_ON || !m || !IFR_HUD_PANELS.has('ifr_load')) return;
  const s = ifrHudSlot(slot), fr = m.frame || {};
  ifrHudVar(slot, 'lcf', ifrHudFitText('lcf', String(fr.name || '')));
  for (let i = 0; i < 4; i++) {
    const w = m.weapons && m.weapons[i], part = w ? w.part : null, fam = part ? part.key : '';
    ifrHudOne(slot, s, 'ifr_lci' + i, 'lci' + i, fam && IFR_HUD_FAMILIES.has(fam) ? 'stW' + fam : '');
    ifrHudVar(slot, 'lc' + i + 'n', part ? ifrHudShort(String(part.name || fam)) : 'EMPTY');
    ifrHudVar(slot, 'lc' + i + 'r', ifrHudRole(part));
  }
  const tk = fr.trait || fr.key, tr = IFR_HUD_TRAIT[tk];
  if (fr.trait_name) {
    ifrHudVar(slot, 'lct', ifrHudFitText('lct', String(fr.trait_name) + ': ' + (tr ? tr[0] : 'SEE THE GARAGE')));
    ifrHudVar(slot, 'lct2', tr ? tr[1] : (ifrHudWrapAll('lct2', String(fr.trait_desc || ''))[0] || ''));
  } else { ifrHudVar(slot, 'lct', IFR_HUD_TXT.loadFoot); ifrHudVar(slot, 'lct2', ''); }
  ifrHudCard(slot, 'loadout', seconds > 0 ? seconds : 9);
}
/** a weapon's display name from a part key ('vm6'), a model name or a name; underscores become spaces */
function ifrHudWeaponName(w) {
  w = String(w || '');
  const p = IFR_HUD_PART_BY_KEY.get(w);
  return p ? String(p.name) : w.replace(/_/g, ' ');
}

// ---------------------------------------------------------------- garage (60_garage.js state)
const IFR_HUD_GROW_STATES = { owned: 'stOwned', locked: 'stLocked', equipped: 'stEquip', buy: 'stBuy', poor: 'stPoor' };
const IFR_HUD_GROW_CLS = ['stSel', 'stOwned', 'stLocked', 'stEquip', 'stBuy', 'stPoor', 'stOff'];
const IFR_HUD_GTRACKS = (IFR_HUD_ON && HUD.garage && HUD.garage.tracks) || 8;
const IFR_HUD_GSCALE = { ap: 15000, speed: 600, boost: 1800, qb: 3200, lock: 10000 };
const IFR_HUD_PART_BY_KEY = new Map(), IFR_HUD_PART_BY_MODEL = new Map(), IFR_HUD_PART_BY_ID = new Map();
if (typeof PARTS === 'object' && PARTS && PARTS.parts) for (const p of PARTS.parts) { IFR_HUD_PART_BY_KEY.set(p.key, p); IFR_HUD_PART_BY_ID.set(p.id, p); if (p.model) IFR_HUD_PART_BY_MODEL.set(p.model, p); }
/** mouse capture for the garage (the layout entity's SetInputCaptureEnabled): on while the garage is open, off when it closes; remembered per
 *  slot so a HUD reset (ResetForPlayer) or a re-found layout entity turns it back on (ifrHudReset, ifrHudKeepCapture) */
function ifrHudCapture(slot, on) {
  if (!IFR_HUD_ON) return;
  ifrHudSlot(slot).capture = !!on;
  const e = ifrHudEnt();
  if (e && typeof e.SetInputCaptureEnabled === 'function') { try { e.SetInputCaptureEnabled(slot, !!on); } catch (err) { /* ignore */ } }
}
/** while the garage is open: puts the mouse capture back if the engine dropped it (cheap: one query) */
function ifrHudKeepCapture(slot) {
  if (!IFR_HUD_ON) return;
  const s = ifrHudSlots.get(slot), e = ifrHudEnt();
  if (!s || !s.capture || !e || typeof e.IsInputCaptureEnabled !== 'function') return;
  try { if (!e.IsInputCaptureEnabled(slot)) { e.SetInputCaptureEnabled(slot, true); ifrHudLog('garage: mouse capture was off for slot ' + slot + ', turned it back on'); } } catch (err) { /* ignore */ }
}
function ifrHudPicKey(pic) {
  if (pic && !IFR_HUD_PART_PICS.has(pic)) { const p = IFR_HUD_PART_BY_MODEL.get(pic); pic = p && IFR_HUD_PART_PICS.has(p.key) ? p.key : ''; }
  return pic || '';
}
const ifrHudGarageErr = new Set();
/** one garage section, guarded: a throw in one part never blanks the rest; logged once per section */
function ifrHudGSection(name, fn) {
  try { fn(); } catch (err) { if (!ifrHudGarageErr.has(name)) { ifrHudGarageErr.add(name); ifrHudLog('WARNING: garage HUD section ' + name + ': ' + err); } }
}
/** state (everything pre-formatted by 60_garage.js garageDraw):
 *  {tabs: [titles], tab, col (0 tabs, 1 list, 2 upgrades), rows: [{name, type, c, r, state:'owned'|'locked'|'equipped'|'buy'|'poor', pic}] (the visible rows), sel (visible index),
 *   scroll, total, tracks: [{n, s, c, l, a, b, frac, state:'up'|'max'|'poor'|'dis'}], urow, utitle, frame: {name, type},
 *   budgets: {weight, load, en, output, valid, deny, ap, walk, boost, qb}, lock, top: {map, credits, kda, rank}, bay, bay2, confirm: {q, hint} | null,
 *   info: {name, type, lines: [a, b, c], key, cmp}, weapons: [{pic, name, stats} x4], legend, tips: [a, b], hint, pending} */
function ifrHudGarage(slot, g) {
  if (!IFR_HUD_ON || !g) return;
  const s = ifrHudSlot(slot), V = (n, t) => ifrHudVar(slot, n, t);
  ifrHudScreen(slot, 'garage');
  // equipped weapons first (10 Nov 2026 playtest: the section looked blank; it now also never waits behind a section that throws)
  ifrHudGSection('weapons', () => {
    const ws = g.weapons || [];
    for (let i = 0; i < 4; i++) {
      const w = ws[i];
      ifrHudSet(slot, 'ifr_ge' + i, 'stEmpty', !w || !w.name);
      V('ge' + i + 'n', w && w.name ? ifrHudShort(w.name).toUpperCase() : 'EMPTY'); V('ge' + i + 's', w && w.stats ? String(w.stats).toUpperCase() : '');
      const key = w && w.pic && IFR_HUD_PART_PICS.has(w.pic) && ifrHudClassOk(ifrHudPanel('ifr_gep' + i), 'stP' + w.pic) ? w.pic : '';
      ifrHudOne(slot, s, 'ifr_gep' + i, 'gep' + i, key ? 'stP' + key : '');
    }
  });
  ifrHudGSection('tabs', () => {
    const tabs = g.tabs || IFR_HUD_GCATS, top = g.top || {};
    for (let i = 0; i < IFR_HUD_GCATS.length; i++) {
      const t = tabs[i];
      V('gcn' + i, t ? String(t).toUpperCase() : '');
      ifrHudSet(slot, 'ifr_gc' + i, 'stOff', !t);
      ifrHudSet(slot, 'ifr_gc' + i, 'stSel', !!t && i === (g.tab | 0));
    }
    for (let c = 0; c < 3; c++) ifrHudSet(slot, 'ifr_gpage', 'stCol' + c, c === (g.col | 0));
    V('gmap', top.map || ''); V('gcred', top.credits || ''); V('gkda', top.kda || ''); V('grank', top.rank || '');
  });
  ifrHudGSection('list', () => {
    const rows = g.rows || [];
    for (let i = 0; i < IFR_HUD_GROWS; i++) {
      const r = rows[i], id = 'ifr_gr' + i;
      V('gr' + i + 'n', r ? String(r.name || '').toUpperCase() : ''); V('gr' + i + 't', r ? String(r.type || '').toUpperCase() : '');
      V('gr' + i + 'c', r ? String(r.c || '').toUpperCase() : ''); V('gr' + i + 'r', r ? String(r.r || '').toUpperCase() : '');
      const st = r ? IFR_HUD_GROW_STATES[r.state] || '' : '';
      for (const c of IFR_HUD_GROW_CLS) ifrHudSet(slot, id, c, c === 'stSel' ? !!r && i === g.sel : c === 'stOff' ? !r : c === st);
      const pic = r ? ifrHudPicKey(r.pic) : '';
      ifrHudOne(slot, s, 'ifr_grp' + i, 'grp' + i, pic ? 'stP' + pic : '');
    }
    const total = g.total !== undefined ? g.total : rows.length, first = g.scroll || 0;
    V('glist', total > IFR_HUD_GROWS ? 'ROWS ' + (first + 1) + ' - ' + Math.min(total, first + IFR_HUD_GROWS) + ' OF ' + total : total + ' ITEMS');
    ifrHudSet(slot, 'ifr_gthumb', 'stOn', total > IFR_HUD_GROWS);
    const span = Math.max(1, total - IFR_HUD_GROWS), pos = total > IFR_HUD_GROWS ? Math.round(10 * first / span) : 0;
    ifrHudOne(slot, s, 'ifr_gthumb', 'gthumb', 'stS' + Math.max(0, Math.min(10, pos)));
    V('gtip', (g.tips && g.tips[0]) || ''); V('gtip2', (g.tips && g.tips[1]) || '');
  });
  ifrHudGSection('tracks', () => {
    const tr = g.tracks || [];
    for (let i = 0; i < IFR_HUD_GTRACKS; i++) {
      const t = tr[i], id = 'ifr_ur' + i;
      V('ur' + i + 'n', t ? String(t.n).toUpperCase() : ''); V('ur' + i + 's', t ? String(t.s || '').toUpperCase() : ''); V('ur' + i + 'c', t ? String(t.c || '').toUpperCase() : '');
      V('ur' + i + 'l', t ? String(t.l || '') : ''); V('ur' + i + 'a', t ? String(t.a || '').toUpperCase() : ''); V('ur' + i + 'b', t ? String(t.b || '').toUpperCase() : '');
      ifrHudLadder(slot, 'u' + i, t ? t.frac : 0);
      ifrHudSet(slot, id, 'stOff', !t); ifrHudSet(slot, id, 'stSel', !!t && i === (g.urow | 0));
      ifrHudSet(slot, id, 'stMax', !!t && t.state === 'max'); ifrHudSet(slot, id, 'stPoor', !!t && t.state === 'poor'); ifrHudSet(slot, id, 'stDis', !!t && t.state === 'dis');
    }
    V('gutitle', g.utitle || '');
  });
  ifrHudGSection('frame', () => {
    const fr = g.frame || {}, b = g.budgets || {};
    V('gfn', String(fr.name || '').toUpperCase()); V('gft', String(fr.type || '').toUpperCase());
    const vals = { ap: b.ap, speed: b.walk, boost: b.boost, qb: b.qb, lock: g.lock };
    for (let i = 0; i < IFR_HUD_GSTATS.length; i++) {
      const k = IFR_HUD_GSTATS[i];
      let frac = 0, text = '';
      if (k === 'weight') { frac = b.load > 0 ? b.weight / b.load : 0; text = ifrHudFmtNum(b.weight || 0) + ' / ' + ifrHudFmtNum(b.load || 0); ifrHudSet(slot, 'ifr_gsb1', 'stOver', b.weight > b.load); }
      else if (k === 'en') { frac = b.output > 0 ? b.en / b.output : 0; text = ifrHudFmtNum(b.en || 0) + ' / ' + ifrHudFmtNum(b.output || 0); ifrHudSet(slot, 'ifr_gsb2', 'stOver', b.en > b.output); }
      else if (vals[k] !== undefined && vals[k] !== null) { frac = Number(vals[k]) / (IFR_HUD_GSCALE[k] || 1); text = ifrHudFmtNum(Number(vals[k])); }
      ifrHudLadder(slot, 'gs' + i, frac);
      V('gs' + i + 'v', text);
    }
    V('gwarn', b.valid === false ? (b.weight > b.load ? 'OVERWEIGHT' : b.en > b.output ? 'EN OVER' : 'INVALID LOADOUT') : b.en > b.output ? 'EN OVER x' + (b.output / b.en).toFixed(2) : '');
  });
  ifrHudGSection('info', () => {
    const info = g.info || {}, il = info.lines || [];
    V('gpn', String(info.name || '').toUpperCase()); V('gpt', String(info.type || '').toUpperCase()); V('gpd', il[0] || ''); V('gpd2', il[1] || ''); V('gpd3', il[2] || '');
    V('gpk', String(info.key || '').toUpperCase()); V('gcmp', String(info.cmp || '').toUpperCase());
    const gh = IFR_HUD_TEXT.ghint2 ? ifrHudWrap(['ghint', 'ghint2'], String(g.pending ? 'WAITING FOR THE SERVER...' : g.hint || '')) : [String(g.pending ? 'WAITING FOR THE SERVER...' : g.hint || '').toUpperCase()];
    V('ghint', gh[0] || ''); if (IFR_HUD_TEXT.ghint2) V('ghint2', gh[1] || '');
  });
  ifrHudGSection('centre', () => {
    V('gbay', String(g.bay || '').toUpperCase()); V('gbay2', String(g.bay2 || '').toUpperCase());
    const cf = g.confirm;
    ifrHudSet(slot, 'ifr_gcbar', 'stOn', !!cf);
    if (IFR_HUD_PANELS.has('ifr_grot')) ifrHudSet(slot, 'ifr_grot', 'stOff', !!cf);     // the turn buttons hide under the confirm bar
    const q = cf ? ifrHudWrap(['gconf', 'gconfb'], String(cf.q).toUpperCase()) : [];
    V('gconf', q[0] || ''); V('gconfb', q[1] || ''); V('gconf2', cf ? String(cf.hint || '').toUpperCase() : '');
    const lg = ifrHudWrap(['glegend', 'glegend2'], String(g.legend || '').toUpperCase());
    V('glegend', lg[0] || ''); V('glegend2', lg[1] || '');
  });
}
