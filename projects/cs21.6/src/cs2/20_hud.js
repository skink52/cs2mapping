// ---------------------------------------------------------------- the 1.6 HUD (custom_hud_layout cs16_hud)
// panorama/layout/custom_game/cs16.xml (made by tools/hud.py from the 1.6 HUD sprites) has fixed panels. The script
// switches CSS classes (digits, icons, colours) and sets a few text variables per player. Every change is cached, so only
// real changes are sent, and a per-tick budget spreads big updates (a menu opening for 30 players) over a few ticks.

let hudEnt;
let hudBudget = Infinity;
let hudCheckedTick = -1;
const hudCache = new Map();     // slot -> Map(key -> class or text)

function hud() {
  if (hudCheckedTick === tickNo) return hudEnt;
  if (live(hudEnt)) { hudCheckedTick = tickNo; return hudEnt; }
  hudEnt = live(Instance.FindEntityByName(CONFIG.HUD));
  hudCheckedTick = tickNo;
  if (!hudEnt) { warnOnce('hud', 'no custom_hud_layout named ' + CONFIG.HUD + ' - no 1.6 HUD'); return hudEnt; }
  hudCheckedTick = tickNo;
  // a new HUD entity (map reload, round restart re-created it): everyone's cache is stale
  for (const slot of hudCache.keys()) { try { hudEnt.ResetForPlayer(slot); } catch (err) { /* ignore */ } }
  hudCache.clear();
  // cursor mode belonged to the old entity: switch it on again for open menus
  for (const rec of recs.values()) { rec.capture = false; if (rec.menu) setCapture(rec, true); }
  return hudEnt;
}
// colour classes the layout starts with (so switching away from them removes them)
/** @type {[string, string][]} */
const HUD_INIT = [['cs_hpb#c', 'cO'], ['cs_tmb#c', 'cO'], ['cs_amb#c', 'cO'], ['cs_mdb#c', 'cG']];
function hcache(slot) {
  let c = hudCache.get(slot);
  if (!c) { c = new Map(HUD_INIT); hudCache.set(slot, c); }
  return c;
}
// one class "slot" per (panel, group): setting a class replaces the previous class in that slot (null = none)
function hudCls(slot, panel, group, cls) {
  const c = hcache(slot);
  const key = panel + '#' + group;
  const old = c.get(key);
  if (old === cls) return true;
  if (old === undefined && cls === null) { c.set(key, null); return true; }
  if (hudBudget <= 0) return false;
  const h = hud();
  if (!h) return false;
  hudBudget -= old && cls ? 2 : 1;
  if (old) h.SetHasClassForPlayer(slot, panel, old, false);
  if (cls) h.SetHasClassForPlayer(slot, panel, cls, true);
  c.set(key, cls);
  return true;
}
function hudFlag(slot, panel, cls, on) { return hudCls(slot, panel, cls, on ? cls : null); }
function hudVar(slot, panel, text) {
  const c = hcache(slot);
  const key = panel + '$';
  text = String(text === undefined || text === null ? '' : text);
  if (c.get(key) === text) return true;
  if (hudBudget <= 0) return false;
  const h = hud();
  if (!h) return false;
  hudBudget--;
  h.SetDialogVariableStringForPlayer(slot, panel, 'v', text);
  c.set(key, text);
  return true;
}
function hudReset(slot) {
  hudCache.delete(slot);
  const h = hud();
  if (h) { try { h.ResetForPlayer(slot); } catch (err) { /* ignore */ } }
}

// a number in a row of digit cells (<row>_0 .. <row>_n-1), right-aligned, leading cells blank (1.6 style)
const DIGIT = ['d0', 'd1', 'd2', 'd3', 'd4', 'd5', 'd6', 'd7', 'd8', 'd9'];
function hudNum(slot, row, n, cells, zeroPad) {
  let s = String(Math.max(0, Math.floor(n)));
  if (zeroPad) while (s.length < zeroPad) s = '0' + s;
  if (s.length > cells) s = s.slice(s.length - cells);
  for (let k = 0; k < cells; k++) {
    const j = k - (cells - s.length);
    hudCls(slot, row + '_' + k, 'd', j >= 0 ? DIGIT[s.charCodeAt(j) - 48] : null);
  }
}

// ---------------------------------------------------------------- what each player's HUD shows (drawn from PlayerRec)
const AMMO_ICON = {};
for (const t in AMMO) AMMO_ICON[t] = 'am_' + t;
for (const t of ['hegrenade', 'flashbang', 'smokegrenade']) AMMO_ICON[t] = 'am_' + t;

function drawHud(rec, t) {
  const s = rec.slot;
  if (!hud()) return;
  const onTeam = rec.team === TEAM_T || rec.team === TEAM_CT;
  hudFlag(s, 'cs_root', 'stOn', onTeam && rec.hudMode !== 'off');      // (menus show even with the HUD off)
  hudFlag(s, 'cs_root', 'stRaised', rec.hudMode === 'raised');
  if (!onTeam) { drawMenu(rec); drawMessage(rec, t); return; }
  const alive = rec.alive;
  hudFlag(s, 'cs_root', 'stAlive', alive);
  // health and armour: brighter for a moment after they change; health red below 25 (1.6)
  if (alive) {
    hudNum(s, 'cs_hp', rec.health, 3);
    hudCls(s, 'cs_hpb', 'c', rec.health < 25 ? 'cR' : 'cO');
    hudFlag(s, 'cs_hpb', 'hot', t < rec.hpHot);
    hudNum(s, 'cs_ap', rec.armor, 3);
    hudCls(s, 'cs_api', 'i', rec.armor > 0 ? (rec.helmet ? 'suith' : 'suit') : 'suite');
    hudFlag(s, 'cs_apb', 'hot', t < rec.apHot);
    // ammo of the weapon in hand (knife, C4 and grenades: no counter, grenades show their count)
    const w = rec.weapon;
    const showAmmo = !!w && (w.clip >= 0 || w.reserve >= 0);
    hudFlag(s, 'cs_amb', 'on', showAmmo);
    if (showAmmo) {
      hudFlag(s, 'cs_amb', 'noclip', w.clip < 0);
      if (w.clip >= 0) hudNum(s, 'cs_ac', w.clip, 3);
      hudNum(s, 'cs_ar', Math.max(0, w.reserve), 3);
      hudCls(s, 'cs_ami', 'i', w.ammo ? AMMO_ICON[w.ammo] || null : null);
      hudCls(s, 'cs_amb', 'c', w.clip === 0 && w.reserve <= 0 ? 'cR' : 'cO');
    }
    // status icons on the left: buy zone, C4 (blinks inside a bomb site), defuse kit
    hudFlag(s, 'cs_ibuy', 'on', rec.inBuy && canBuyNow(rec) === null);
    hudFlag(s, 'cs_ic4', 'on', rec.hasC4);
    hudFlag(s, 'cs_ic4', 'blink', rec.hasC4 && rec.inSite);
    hudFlag(s, 'cs_idef', 'on', rec.hasDefuser);
  }
  // round timer (1.6 hides it once the bomb on your map is planted); red under 30 seconds
  const mr = rec.map ? round.maps.get(rec.map) : undefined;
  const planted = !!(mr && mr.bomb && !mr.bomb.defused && !mr.bomb.exploded);
  const left = timerLeft(t);
  const showTimer = left !== null && !planted && !(mr && mr.decided);
  hudFlag(s, 'cs_root', 'stTimer', showTimer);
  if (showTimer) {
    const sec = Math.max(0, Math.ceil(left));
    const m = Math.floor(sec / 60), ss = sec % 60;
    hudNum(s, 'cs_tm', m * 100 + ss, 4, 3);
    hudCls(s, 'cs_tmb', 'c', sec <= 30 && !round.frozen ? 'cR' : 'cO');
  }
  // money, with the last change (+300 green, -2500 red) under it for a few seconds
  hudNum(s, 'cs_mn', rec.money, 5);
  hudFlag(s, 'cs_mnb', 'hot', t < rec.moneyHot);
  const showDelta = t < rec.deltaUntil && rec.delta !== 0;
  hudFlag(s, 'cs_mdb', 'on', showDelta);
  if (showDelta) {
    hudNum(s, 'cs_md', Math.abs(rec.delta), 5);
    hudCls(s, 'cs_mdb', 'c', rec.delta > 0 ? 'cG' : 'cR');
    hudCls(s, 'cs_mds', 'i', rec.delta > 0 ? 'plus' : 'minus');
  }
  drawTop(rec, t);
  drawMenu(rec);
  drawMessage(rec, t);
}

// the centre message (1.6's centre print): one at a time, newest wins
function message(rec, text, seconds) {
  rec.msg = text;
  rec.msgUntil = now() + (seconds || 4);
}
function drawMessage(rec, t) {
  const show = !!rec.msg && t < rec.msgUntil;
  if (show) hudVar(rec.slot, 'cs_msg', rec.msg);
  hudFlag(rec.slot, 'cs_msgb', 'on', show);
}
// the small line at the top: which map you play on (a few seconds after spawning), or what you are watching
function drawTop(rec, t) {
  const show = !!rec.top && t < rec.topUntil;
  if (show) hudVar(rec.slot, 'cs_top', rec.top);
  hudFlag(rec.slot, 'cs_topb', 'on', show);
}
function topLine(rec, text, seconds) { rec.top = text; rec.topUntil = now() + (seconds || 6); }
