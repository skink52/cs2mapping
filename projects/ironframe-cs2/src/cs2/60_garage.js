// ===================================================================================================================
// IRONFRAME CS2 adapter, part 6: the garage (while the pawn is parked or between lives): an armory terminal.
// Layout (tools/hud.py, docs/HUD.md): tabs + item list on the left, the REAL mech in a hangar bay in the centre (the player's
// controlled camera looks at it), upgrade tracks of the equipped parts on the right.
// Keys: three focus columns, 0 tabs / 1 list / 2 upgrade tracks. W/S move inside the column, Space picks, Ctrl goes back, F upgrades.
// A/D: in the list A -> tabs, D -> tracks; in the tracks A -> list; in the tabs A/D (held) rotate the mech.
// The mech faces the camera when the garage opens and whenever the frame changes (10 Nov 2026 evening playtest: it used to start side-on and
// spin by itself). E / R held turn it in any column; so do the two buttons under its feet (ifr_grl / ifr_grr: 45 degrees a click, eased; it
// keeps turning while the mouse button stays down where the engine reports it); ifr_grf (FRONT) faces the camera again.
// Buying and upgrading ask first (a confirm bar: Space confirm / Ctrl cancel). The mouse works too (Button ids ifr_gc<i> tabs,
// ifr_gr<i> rows, ifr_ur<i> tracks, ifr_gup/ifr_gdn scroll, ifr_gcy/ifr_gcx confirm / cancel): a click on the selected row picks it.
// A draft loadout (9 ids) is edited; "Sortie" validates it and sends it to the server (save) or applies it stand-alone, then asks for a spawn.
// Buying and upgrading go to the server in server mode (the plugin owns credits); stand-alone everything is owned and upgrades are free and
// local (pe.localPilot; Nov 2026 playtest: the tracks did nothing offline): the core gets that pilot record (game.setPilot), so the next
// sortie's mech carries the upgraded stats; it lasts for the map (the core keeps it across round restarts).
// Drawing is ifrHudGarage(slot, state) from 50_hud.js (docs/HUD.md gives the state shape).
// ===================================================================================================================
const GARAGE_TABS = [
  { key: 'all', title: 'All' }, { key: 'pri', title: 'Primary' }, { key: 'sec', title: 'Shld' }, { key: 'spe', title: 'Special' }, { key: 'uti', title: 'Utility' },
  { key: 'frm', title: 'Frames' }, { key: 'pnt', title: 'Paint' }, { key: 'load', title: 'Slots' },
  { key: 'plt', title: 'Pilot' },      // callsign, title, badge, camera, hints, contracts, the server's top pilots (70_server.js srvCustom)
  { key: 'sortie', title: 'SORTIE' },  // stays last: W from the first tab, then Space, launches
];
const GARAGE_ROWS = (typeof HUD === 'object' && HUD && HUD.garage && HUD.garage.rows) || 8, GARAGE_VISIBLE = GARAGE_ROWS;   // the list rows the layout has (tools/hud.py GROWS)
const GARAGE_SLOTS = ['FRAME', 'R ARM', 'L ARM', 'R SHLD', 'L SHLD', 'GENERATOR', 'BOOSTER', 'FCS', 'PAINT'];
const GARAGE_KIND_SLOTS = { frame: [0], arm: [1, 2], shoulder: [3, 4], generator: [5], booster: [6], fcs: [7], paint: [8] };
const GARAGE_KIND_ORDER = ['frame', 'arm', 'shoulder', 'generator', 'booster', 'fcs', 'paint'];
const GARAGE_CLASS_ORDER = ['light', 'medium', 'heavy'];
// short forms of the server's refusal texts for the narrow garage boxes
const GARAGE_DENY = { 0: 'SERVER SAID NO', 1: 'PART NOT OWNED', 2: 'RANK TOO LOW', 3: 'NOT ENOUGH CREDITS', 4: 'OVER WEIGHT LIMIT', 5: 'OVER EN BUDGET', 6: 'AT MAX LEVEL', 7: 'LOADOUT NOT VALID', 8: 'TOO FAST, RETRY', 9: 'TEXT NOT ALLOWED', 10: 'NOT EARNED YET' };
const GARAGE_WTYPE = { proj: 'PROJECTILE', missile: 'MISSILE', hitscan: 'HITSCAN', lob: 'LOB', melee: 'MELEE', shield: 'SHIELD', ability: 'ABILITY' };
const PART_BY_ID = {};
for (const p of (PARTS.parts || [])) PART_BY_ID[p.id] = p;
const STARTER = PARTS.starter || { owned: [], loadouts: [] };
const garagePreviews = new Map();      // slot -> {sig, upper, legs, weapons[], bay}: the hangar props of a player's preview
let hangarOrigin = null;

const gfmt = (n) => (typeof ifrHudFmtNum === 'function' ? ifrHudFmtNum(n) : String(Math.round(n)));
function garageTab(g) { return GARAGE_TABS[g.tab]; }

function garageOpen(pe, why) {
  if (!pe.garage) pe.garage = { tab: 0, row: 0, col: 0, urow: 0, draft: null, slot: 1, msg: '', msgAt: 0, pending: false, rows: [], tracks: [], scroll: 0, confirm: null, yaw: 300, spinAt: -99, lastT: 0, drawAt: -99, dirty: true, bay: null };
  const g = pe.garage;
  g.open = true;
  const pilot = pe.pilot;
  g.slot = pilot ? pilot.active : (g.slot || 1);
  const src = pilot && pilot.loadouts[g.slot - 1] ? pilot.loadouts[g.slot - 1] : STARTER.loadouts[0] || '4,101,103,201,209,301,401,501,601';
  g.draft = garageParse(src);
  g.tab = 0; g.row = 0; g.scroll = 0; g.col = 0; g.urow = 0; g.confirm = null; g.msg = why || ''; g.msgAt = gameTime(); g.pending = false; g.nextSide = { arm: 0, shoulder: 0 };
  hangarOrigin = null;
  // stand-alone: the core gets the local pilot (its upgrades); in server mode a stale local one is dropped for the server's record
  if (game && !serverMode && pe.localPilot) guard('local pilot', () => game.setPilot(pe.slot, pe.localPilot));
  else if (game && serverMode && pe.localPilot) { pe.localPilot = null; guard('local pilot', () => game.setPilot(pe.slot, pe.pilot || null)); }
  g.bay = garageBay(pe.slot);
  g.yaw = g.yawT = garageFront(pe.slot); g.rotHold = 0; g.rotAt = -99;      // facing the camera
  pe.status = 'garage';
  if (pe.human) { revivePawn(pe); pe.camKind = ''; pe.camSent = null; }   // a live pawn (a dead one shows CS2's observer view) and a fresh CONTROLLED camera
  if (pe.human && typeof ifrHudCapture === 'function') ifrHudCapture(pe.slot, true);
  garageRows(pe); garageDraw(pe);
  if (game) game.events.push({ t: 'garage', slot: pe.slot, open: true });
}
function garageClose(pe) {
  if (!pe.garage || !pe.garage.open) return;
  pe.garage.open = false; pe.garage.confirm = null;
  garagePreviewDrop(pe.slot);
  if (pe.human && typeof ifrHudCapture === 'function') ifrHudCapture(pe.slot, false);
  if (game) game.events.push({ t: 'garage', slot: pe.slot, open: false });
  if (ifrHudSlate) ifrHudSlate(pe.slot, 'none', null);
}
function garageParse(s) { const ids = String(s).split(',').map((x) => parseInt(x, 10) || 0); while (ids.length < 9) ids.push(0); return ids.slice(0, 9); }
function garageStr(ids) { return ids.join(','); }
function garageOwned(pe, id) {
  if (!serverMode || !pe.pilot) return true;
  const p = PART_BY_ID[id]; if (!p) return false;
  if (p.kind === 'paint' && !p.cost) return true;
  return pe.pilot.owned.has(id);
}
// the pilot record the garage and the core work from: the server's (server mode) or the stand-alone one (upgrades only, every part owned)
function garageLocalPilot(pe) {
  if (!pe.localPilot) pe.localPilot = { local: true, rank: 0, xp: 0, credits: 0, active: 1, owned: new Set(Object.keys(PART_BY_ID).map(Number)), upgrades: {}, loadouts: [null, null, null, null, null, null], flags: 0 };
  return pe.localPilot;
}
function garagePilot(pe) { return serverMode ? pe.pilot || null : garageLocalPilot(pe); }
function garageLevel(pe, id) { const pl = garagePilot(pe); return pl && pl.upgrades ? (pl.upgrades[id] || 0) : 0; }
function garageRank(pe) { return pe.pilot ? pe.pilot.rank : 99; }
function garageCredits(pe) { return pe.pilot ? pe.pilot.credits : 0; }

// ---------------------------------------------------------------- the list
function garageTypeText(p) {
  const w = p.w;
  switch (p.kind) {
    case 'frame': return (p.class || '') + ' ' + (p.legs || '');
    case 'arm': return 'ARM / ' + (w ? (w.ability || GARAGE_WTYPE[w.type] || w.type) : '');
    case 'shoulder': return 'SHOULDER / ' + (w ? (w.ability || GARAGE_WTYPE[w.type] || w.type) : '');
    case 'fcs': return 'FCS';
    default: return p.kind;
  }
}
// which tab lists a part
function garageInTab(p, tab) {
  switch (tab.key) {
    case 'all': return true;
    case 'pri': return p.kind === 'arm';
    case 'sec': return p.kind === 'shoulder' && !(p.w && p.w.type === 'ability');
    case 'spe': return p.kind === 'shoulder' && !!(p.w && p.w.type === 'ability');
    case 'uti': return p.kind === 'generator' || p.kind === 'booster' || p.kind === 'fcs';
    case 'frm': return p.kind === 'frame';
    case 'pnt': return p.kind === 'paint';
    default: return false;
  }
}
function garageTagOf(g, p) {
  const sl = GARAGE_KIND_SLOTS[p.kind] || [], eq = sl.filter((i) => g.draft[i] === p.id);
  if (!eq.length || sl.length === 1) return '';
  return eq.length === 2 ? (p.kind === 'arm' ? 'R+L ARM' : 'R+L SHLD') : GARAGE_SLOTS[eq[0]];
}
function garagePartRow(pe, p) {
  const g = pe.garage, sl = GARAGE_KIND_SLOTS[p.kind] || [];
  const owned = garageOwned(pe, p.id), lvl = garageLevel(pe, p.id);
  const eq = sl.some((i) => g.draft[i] === p.id);
  const locked = !owned && p.rank > garageRank(pe);
  const afford = !serverMode || garageCredits(pe) >= p.cost;
  const state = eq ? 'equipped' : owned ? 'owned' : locked ? 'locked' : afford ? 'buy' : 'poor';
  const cost = p.cost || 0;
  const c = state === 'equipped' ? 'EQUIPPED' : state === 'owned' ? 'OWNED' : state === 'locked' ? 'R' + p.rank + ' NEEDED' : (cost ? gfmt(cost) + ' CR' : 'FREE');
  let r = state === 'equipped' ? garageTagOf(g, p) : state === 'locked' ? 'LOCKED' : state === 'poor' ? 'NEED CREDITS' : state === 'buy' && p.rank > 1 ? 'RANK ' + p.rank : '';
  if (lvl && (state === 'equipped' || state === 'owned')) r = r ? r + '  +' + lvl : IF_tierName(lvl);      // the upgrade level (MK I..V, +N beside a slot tag): on the small line, the name stays whole
  return { id: p.id, name: p.name, type: garageTypeText(p), c, r, state, cost, rank: p.rank, part: p, pic: p.key };
}
// all rows of the current tab
function garageRows(pe) {
  const g = pe.garage, tab = garageTab(g), rows = [];
  if (tab.key === 'load') {
    for (const x of garageSlotRows(pe)) rows.push(x);
  } else if (tab.key === 'plt') {
    for (const x of garagePilotRows(pe)) rows.push(x);
  } else if (tab.key === 'sortie') {
    const b = garageBudgets(pe), f = PART_BY_ID[g.draft[0]];
    rows.push({ id: 0, name: 'SORTIE', type: b.valid ? 'LAUNCH THIS LOADOUT' : (GARAGE_DENY[b.deny] || 'INVALID LOADOUT'), c: b.valid ? 'GO' : 'BLOCKED', r: '', state: b.valid ? 'owned' : 'locked', pic: f ? f.key : '' });
    rows.push({ id: -10, name: 'Save to slot ' + g.slot, type: 'KEEP THIS LOADOUT', c: 'SAVE', r: '', state: 'owned', pic: f ? f.key : '' });
  } else {
    if (tab.key === 'pri') for (const i of [1, 2]) rows.push({ id: -(20 + i), name: 'Empty ' + GARAGE_SLOTS[i], type: 'REMOVE EQUIPMENT', c: g.draft[i] === 0 ? 'ACTIVE' : '', r: '', state: g.draft[i] === 0 ? 'equipped' : 'owned', empty: i });
    if (tab.key === 'sec' || tab.key === 'spe') for (const i of [3, 4]) rows.push({ id: -(20 + i), name: 'Empty ' + GARAGE_SLOTS[i], type: 'REMOVE EQUIPMENT', c: g.draft[i] === 0 ? 'ACTIVE' : '', r: '', state: g.draft[i] === 0 ? 'equipped' : 'owned', empty: i });
    const list = (PARTS.parts || []).filter((p) => !p.pve && garageInTab(p, tab));
    // frames by class (light, medium, heavy), the newest models (the four Tripo frames) first in each class: they sat at rows 16-19 of the
    // FRAMES list, below the fold, where nobody found them (10 Nov 2026 evening). Array.sort is stable: everything else keeps its order.
    const fo = (p) => (p.kind === 'frame' ? GARAGE_CLASS_ORDER.indexOf(p.class) * 2 + (/^tripo_/.test(String(p.model || '')) ? 0 : 1) : 0);
    list.sort((a, b) => (tab.key === 'all' ? GARAGE_KIND_ORDER.indexOf(a.kind) - GARAGE_KIND_ORDER.indexOf(b.kind) : 0) || fo(a) - fo(b));
    for (const p of list) rows.push(garagePartRow(pe, p));
  }
  g.rows = rows;
  if (g.row >= rows.length) g.row = Math.max(0, rows.length - 1);
  garageScrollFix(g);
  g.tracks = garageTracks(pe);
  if (g.urow >= g.tracks.length) g.urow = Math.max(0, g.tracks.length - 1);
}
// the PILOT tab: who you are (callsign, title, badge), how you see (camera, hints), today's contracts and the server's top pilots.
// Every row reuses the list's four Labels: the value where the wide Label is (a callsign or a title is up to 12 wide letters), a caption of
// at most 20 letters under it, a short state on the right. The explanation goes to the ITEM INFORMATION plate (row.help, three rows of ~30
// letters). A pick cycles the setting (srvCustom: the session's profile stand-alone, an ifr_srv op on a server).
const gfit = (slot, text, pre) => (typeof ifrHudFitText === 'function' ? ifrHudFitText(slot, text, pre || '') : (pre || '') + text);
const gxp = (n) => (typeof ifrHudXpShort === 'function' ? ifrHudXpShort(n) : String(n));
function garageSlotRows(pe) {
  const g = pe.garage, pl = garagePilot(pe), pr = srvProfile(pe), rows = [];
  for (let k = 1; k <= IF_Career.slots; k++) {
    const l = (pl && pl.loadouts[k - 1]) || (k === g.slot ? garageStr(g.draft) : null);
    const f = l ? PART_BY_ID[garageParse(l)[0]] : null, ac = pr ? IF_Career.accent(pr.accents[k - 1]) : null, nm = pr ? pr.names[k - 1] : '';
    rows.push({ id: -k, name: nm ? gfit('gr0n', nm, k + '  ') : 'Loadout ' + k, type: l ? garageLoadoutName(l) : 'EMPTY', c: g.slot === k ? 'ACTIVE' : l ? 'SAVED' : 'EMPTY',
      r: ac ? ac.name : '', state: g.slot === k ? 'equipped' : (l ? 'owned' : 'locked'), pic: f ? f.key : '', help: 'Space picks this slot. SORTIE saves the build you fly into it.' });
  }
  const ac = pr ? IF_Career.accent(pr.accents[g.slot - 1]) : null, nm = pr ? pr.names[g.slot - 1] : '';
  rows.push({ id: -30, name: 'Accent colour', type: 'WEAPONS OF SLOT ' + g.slot, c: ac ? ac.name : 'NONE', r: '', state: 'owned', pic: '',
    help: 'Space: the next accent colour. The weapons of this loadout wear it.' });
  rows.push({ id: -31, name: nm ? gfit('gr0n', nm) : 'No name', type: 'SLOT ' + g.slot + ': !NAME <TEXT>', c: '', r: '', state: nm ? 'equipped' : 'owned', pic: '',
    help: 'Type !name and up to 10 letters in chat. !name alone clears it.' });
  return rows;
}
function garagePilotRows(pe) {
  const pr = srvProfile(pe), rows = [];
  if (!pr) return [{ id: -49, name: 'Pilot', type: 'WAITING', c: '', r: '', state: 'locked', pic: '', help: 'Your pilot record has not arrived from the server yet.' }];
  const H = IF_Career.data.honours, own = (kind) => H.filter((h) => h.kind === kind && pr.earned.has(h.id)), all = (kind) => H.filter((h) => h.kind === kind);
  const t = IF_Career.honour(pr.title), b = IF_Career.honour(pr.badge), cam = IF_Career.camera(pr.prefs & IF_Career.PREF_CAM), fav = PART_BY_ID[pr.fav];
  // a worn honour says how it was earned; an unworn row says what the next one takes
  const about = (kind, h) => { if (h) return h.how + '. Space: the next one.'; const n = all(kind).find((x) => !pr.earned.has(x.id)); return n ? 'Next: ' + n.name + ', ' + n.how + '.' : 'Every one earned. Space wears one.'; };
  rows.push({ id: -40, name: pr.callsign ? gfit('gr0n', pr.callsign) : 'No callsign', type: 'CALLSIGN', c: pr.callsign ? 'SET' : '', r: '', state: pr.callsign ? 'equipped' : 'owned', pic: '',
    help: 'Your name on the kill line and the podium. Chat: !callsign <text>' });
  rows.push({ id: -41, name: t ? t.name : 'No title', type: 'TITLE, ON THE PODIUM', c: t ? 'WORN' : '', r: own('title').length + '/' + all('title').length + ' EARNED', state: t ? 'equipped' : own('title').length ? 'owned' : 'locked', pic: '', help: about('title', t) });
  rows.push({ id: -42, name: b ? b.name : 'No badge', type: 'BADGE, ON KILL LINES', c: b ? '[' + b.tag + ']' : '', r: own('badge').length + '/' + all('badge').length + ' EARNED', state: b ? 'equipped' : own('badge').length ? 'owned' : 'locked', pic: '', help: about('badge', b) });
  rows.push({ id: -43, name: 'Camera', type: 'DISTANCE TO THE MECH', c: cam.name, r: 'X ' + cam.mult, state: 'owned', pic: '', help: 'Space steps the camera distance. Also !cam in chat.' });
  rows.push({ id: -44, name: 'Hints', type: 'TIPS FOR NEW PILOTS', c: (pr.prefs & IF_Career.PREF_HINTS_OFF) ? 'OFF' : 'ON', r: '', state: 'owned', pic: '', help: 'Tips on the message line. Space switches them. Also !hints in chat.' });
  rows.push({ id: -45, name: fav ? gfit('gr0n', fav.name) : 'No favourite', type: 'FAVOURITE FRAME', c: fav ? 'SET' : '', r: '', state: fav ? 'equipped' : 'owned', pic: fav ? fav.key : '',
    help: 'Space marks the frame in the bay as your favourite. Again clears it.' });
  pr.daily.forEach((d, i) => rows.push({ id: -50 - i, name: IF_Career.contractLabel(d.code), type: 'DAILY  ' + d.progress + ' / ' + d.goal, c: d.progress >= d.goal ? 'DONE' : Math.floor(100 * d.progress / d.goal) + ' %', r: '+' + gfmt(d.reward) + ' CR',
    state: d.progress >= d.goal ? 'equipped' : 'owned', pic: '', help: 'Pays its credits once, when the count is reached. New at 00:00 UTC.' }));
  if (!serverMode) rows.push({ id: -60, name: 'Top pilots', type: 'ON A SERVER', c: 'OFFLINE', r: '', state: 'locked', pic: '', help: 'Careers, contracts and the leaderboard need a server. All unlocked here.' });
  else {
    rows.push({ id: -60, name: 'Server place', type: srvBoard ? gxp(srvBoard.total) + ' PILOTS HERE' : 'NO LEADERBOARD YET', c: pr.place ? '#' + pr.place : '-', r: pe.pilot ? gxp(pe.pilot.xp) + ' XP' : '', state: 'owned', pic: '',
      help: 'Your place among the pilots of this server, by career XP.' });
    if (srvBoard) srvBoard.rows.forEach((x, i) => rows.push({ id: -61 - i, name: gfit('gr0n', x.name, (i + 1) + '  '), type: 'RANK ' + x.rank, c: gxp(x.xp) + ' XP', r: '', state: pr.place === i + 1 ? 'equipped' : 'owned', pic: '',
      help: 'Place ' + (i + 1) + ' on this server, by career XP.' }));
  }
  return rows;
}
// a pick on a PILOT / SLOTS setting row: the next value
function garagePilotPick(pe, id) {
  const g = pe.garage, pr = srvProfile(pe);
  if (!pr) { garageSay(pe, 'No pilot record from the server yet'); sndTone(pe.slot, 'ui_garage_deny'); return; }
  const cycle = (kind, cur) => { const ids = [0].concat(IF_Career.data.honours.filter((h) => h.kind === kind && pr.earned.has(h.id)).map((h) => h.id)); return ids[(ids.indexOf(cur) + 1) % ids.length]; };
  let code = 0, said = '';
  if (id === -30) { const ids = [0].concat(IF_Career.data.accents.map((a) => a.id)), nx = ids[(ids.indexOf(pr.accents[g.slot - 1]) + 1) % ids.length]; code = srvCustom(pe, 'accent', g.slot, nx); const a = IF_Career.accent(nx); said = 'Accent: ' + (a ? a.name : 'none'); }
  else if (id === -31) said = 'Type in chat: !name <text>';
  else if (id === -40) said = 'Type in chat: !callsign <text>';
  else if (id === -41 || id === -42) {
    const kind = id === -41 ? 'title' : 'badge', nx = cycle(kind, pr[kind]);
    if (nx === pr[kind]) { garageSay(pe, 'No ' + kind + ' earned yet'); sndTone(pe.slot, 'ui_garage_deny'); return; }
    code = srvCustom(pe, kind, nx); const h = IF_Career.honour(nx); said = (kind === 'title' ? 'Title: ' : 'Badge: ') + (h ? h.name : 'none');
  } else if (id === -43) { const n = IF_Career.data.camera.length, nx = ((pr.prefs & IF_Career.PREF_CAM) + 1) % n; code = srvCustom(pe, 'pref', (pr.prefs & ~IF_Career.PREF_CAM) | nx); said = 'Camera: ' + IF_Career.camera(nx).name; }
  else if (id === -44) { const nx = pr.prefs ^ IF_Career.PREF_HINTS_OFF; code = srvCustom(pe, 'pref', nx); said = 'Hints ' + ((nx & IF_Career.PREF_HINTS_OFF) ? 'off' : 'on'); }
  else if (id === -45) { const f = g.draft[0], nx = pr.fav === f ? 0 : f; code = srvCustom(pe, 'fav', nx); said = nx ? 'Favourite: ' + (PART_BY_ID[nx] || {}).name : 'Favourite cleared'; }
  else return;
  if (code) { garageSay(pe, DENY_TEXT[code] || 'denied'); sndTone(pe.slot, 'ui_garage_deny'); return; }
  garageRows(pe); garageSay(pe, said); sndTone(pe.slot, 'ui_garage_ok');
}
function garageScrollFix(g) {
  if (g.row < g.scroll) g.scroll = g.row;
  if (g.row >= g.scroll + GARAGE_VISIBLE) g.scroll = g.row - GARAGE_VISIBLE + 1;
  g.scroll = Math.max(0, Math.min(g.scroll, Math.max(0, g.rows.length - GARAGE_VISIBLE)));
}
function garageLoadoutName(l) { const ids = garageParse(l); const f = PART_BY_ID[ids[0]]; return f ? f.name : '?'; }
function garageBudgets(pe) {
  const g = pe.garage;
  const r = guard('budgets', () => game.garage.budgets(garageStr(g.draft), garagePilot(pe)));
  if (r) return r;
  // a fallback when the core is not there yet: weights only
  let weight = 0, en = 0, load = 0, output = 0;
  for (let i = 0; i < 9; i++) { const p = PART_BY_ID[g.draft[i]]; if (!p) continue; weight += p.weight || 0; en += p.en || 0; if (p.kind === 'frame') load = (PARTS.classes[p.class] || {}).load || 0; if (p.g) output = p.g.output; }
  return { weight, load, en, output, valid: weight <= load, deny: weight <= load ? 0 : 4 };
}

// ---------------------------------------------------------------- upgrade tracks (the equipped parts, real numbers from parts.json)
// the value of a part's track at a level: the same formulas as the core (20_mech.js, 70_progress.js)
function garageTrackValue(p, L) {
  const caps = /** @type {any} */ (PARTS.caps || {}), up = p.upgrade, pc = up.pct * L, w = p.w || {};
  switch (up.stat) {
    case 'ap': { const c = (PARTS.classes || {})[p.class] || {}, m = p.mods || {}; return gfmt(c.ap * (m.ap || 1) * (1 + Math.min(caps.ap_pct || 15, pc) / 100)); }
    case 'damage': return gfmt((w.damage || 0) * (1 + Math.min(caps.dps_pct || 10, pc) / 100)) + (w.pellets ? ' x' + w.pellets : w.count ? ' x' + w.count : '');
    case 'capacity': return gfmt(p.g.capacity * (1 + pc / 100));
    case 'efficiency': return '-' + Math.round(Math.min(caps.mobility_pct || 8, pc) * 10) / 10 + ' %';
    case 'lock_time': return (p.f.hard * (1 + Math.max(-30, pc) / 100)).toFixed(2) + ' S';
    case 'charges': return String((w.charges || 0) + Math.floor(L / 3));
    case 'shield_hp': case 'heal': return gfmt((w[up.stat] || 0) * (1 + pc / 100));
    case 'block': return Math.round((w.block || 0) * (1 + pc / 100) * 100) + ' %';
    default: return (pc >= 0 ? '+' : '') + Math.round(pc * 10) / 10 + ' %';
  }
}
const GARAGE_STAT_NAME = { ap: 'AP', damage: 'DAMAGE', capacity: 'CAPACITY', efficiency: 'EFF', lock_time: 'LOCK TIME', shield_hp: 'BUBBLE', heal: 'HEAL', charges: 'CHARGES', block: 'BLOCK' };
function garageTrackOf(pe, idx, p) {
  const max = (PARTS.caps || {}).levels || 5, lvl = garageLevel(pe, p.id), up = p.upgrade;
  const cost = lvl >= max ? 0 : IF_upgradeCost(p, lvl, PARTS.caps);
  const stat = GARAGE_STAT_NAME[up.stat] || String(up.stat).toUpperCase().replace(/_/g, ' ');
  const state = lvl >= max ? 'max' : !serverMode ? 'up' : garageCredits(pe) < cost ? 'poor' : 'up';     // stand-alone: free
  const label = (idx === 0 ? 'FRAME' : idx === 5 ? 'GEN' : idx === 6 ? 'BOOST' : GARAGE_SLOTS[idx]) + ' ' + stat;
  // Mk V is a finish, not more power: a frame at Mk V tints its aura with the aura's accent colour (47_auras.js)
  const reward = lvl >= max ? (idx === 0 && PARTS.auras && PARTS.auras[p.key] ? 'AURA ' : '') + IF_tierName(lvl) : '';
  return { id: p.id, idx, part: p, n: label, s: p.name + '  ' + (reward || (up.pct > 0 ? '+' : '') + up.pct + ' % / LV'), lvl, max, cost, state,
    c: lvl >= max ? 'MAX' : cost && serverMode ? gfmt(cost) + ' CR' : 'FREE', l: lvl > 0 ? IF_tierName(lvl).slice(3) : '-', a: garageTrackValue(p, lvl), b: lvl >= max ? '' : garageTrackValue(p, lvl + 1), frac: lvl / max };
}
function garageTracks(pe) {
  const g = pe.garage, out = [];
  for (let idx = 0; idx < 8; idx++) { const p = PART_BY_ID[g.draft[idx]]; if (p && p.upgrade) out.push(garageTrackOf(pe, idx, p)); }
  return out;
}

// ---------------------------------------------------------------- drawing
function garageSay(pe, msg) { pe.garage.msg = msg; pe.garage.msgAt = gameTime(); pe.garage.dirty = true; }
// the draft with the highlighted list item swapped in: what the preview shows (an unowned item too: look before you buy)
function garagePreviewIds(pe) {
  const g = pe.garage, ids = g.draft.slice(), sel = g.col === 1 ? g.rows[g.row] : null;
  if (sel && sel.part && sel.state !== 'locked') { const t = garageTarget(g, sel.part, 0); if (t >= 0) ids[t] = sel.part.id; return { ids, swap: sel.part }; }
  return { ids, swap: null };
}
function garageWrap(text, n) {
  const out = []; let cur = '';
  for (const w of String(text).split(/\s+/)) { if (cur && (cur + ' ' + w).length > n) { out.push(cur); cur = w; } else cur = cur ? cur + ' ' + w : w; }
  if (cur) out.push(cur);
  return out;
}
const GARAGE_KEY_ROWS = { Type: 1, Damage: 1, Rate: 1, Cooldown: 1, Range: 1, Impact: 1, Weight: 1, 'EN load': 1, DPS: 1 };
// short labels for a weapon's third info line, in describe()'s row order (whatever fits is shown)
const GARAGE_ROW_SHORT = { Magazine: 'MAG', Ammo: 'AMMO', 'EN per shot': 'EN/SHOT', Lock: 'LOCK', Blocks: 'BLOCKS', 'Bubble HP': 'BUBBLE', Heal: 'HEAL', Charges: 'CHARGES', DPS: 'DPS', Weight: 'WT', 'EN load': 'EN' };
const GARAGE_KEY_SHORT = { Capacity: 'CAP', Output: 'OUT', 'Quick boost': 'QB', 'QB cost': 'QB COST', 'Soft lock': 'SOFT', 'Hard lock': 'HARD' };
function garageSlotW(name) { const ts = typeof IFR_HUD_TEXT === 'object' && IFR_HUD_TEXT ? IFR_HUD_TEXT[name] : null; return ts ? ts.w : 1e9; }
function garageInfo(pe, part) {
  const g = pe.garage;
  if (!part) return { name: '', type: '', lines: [], key: '', cmp: '' };
  const d = guard('describe', () => game.garage.describe(part.id, garagePilot(pe))), rows = (d && d.rows) || [], w = part.w;
  let lines = [], key = '', extraRow = '';
  if (part.kind === 'frame') {
    let tr = part.trait_name ? part.trait_name + ': ' + part.trait_desc : part.desc || '';
    const short = typeof IFR_HUD_TRAIT === 'object' ? IFR_HUD_TRAIT[part.trait || part.key] : null;
    if (short && part.trait_name && typeof ifrHudWrapAll === 'function' && ifrHudWrapAll('gpd', tr).length > 3) tr = part.trait_name + ' (' + short[0] + '): ' + short[1];
    lines = ifrHudWrap(['gpd', 'gpd2', 'gpd3'], tr);
    key = ifrHudFitTokens('gpk', rows.filter((r) => r[0] === 'Load' || r[0] === 'Stagger cap').map((r) => r[0].toUpperCase() + ' ' + r[1]), '  ');
  } else if (w) {
    const k = [];
    if (w.damage) k.push('DMG ' + gfmt(w.damage) + (w.pellets ? ' x' + w.pellets : w.count ? ' x' + w.count : ''));
    if (w.rate) k.push('ROF ' + w.rate); else if (w.cd) k.push('CD ' + w.cd + ' S');
    if (w.range) k.push('RNG ' + gfmt(w.range)); if (w.impact) k.push('IMP ' + gfmt(w.impact));
    // all four figures: without the thousands gaps when the row is too narrow for them (the sniper cannon's DMG 1 800 ... RNG 12 000 lost its IMP)
    if (typeof ifrHudFits === 'function' && !ifrHudFits('gpk', k.join('  '))) for (let i = 0; i < k.length; i++) k[i] = k[i].replace(/(\d) (?=\d)/g, '$1');
    key = ifrHudFitTokens('gpk', k, '  ');
    // the weapon's description (role and feel, parts.json desc) on two lines, then the most useful extra figures that fit the third
    if (part.desc) {
      // the description takes two rows, three when it needs them; the extra figures take the third row, or the comparison row when that is free
      lines = ifrHudWrap(['gpd', 'gpd2', 'gpd3'], part.desc);
      const extra = rows.filter((r) => GARAGE_ROW_SHORT[r[0]]).map((r) => GARAGE_ROW_SHORT[r[0]] + ' ' + r[1]);
      let x = ''; for (const t of extra) { const c = x ? x + '  ' + t : t; if (ifrHudWidth('gpd3', c) <= garageSlotW('gpd3')) x = c; }   // by priority, whatever fits
      if (lines.length <= 2) { while (lines.length < 2) lines.push(''); lines[2] = x; } else extraRow = x;
    } else lines = ifrHudWrapTokens(['gpd', 'gpd2', 'gpd3'], rows.filter((r) => !GARAGE_KEY_ROWS[r[0]]).map((r) => r[0] + ' ' + r[1]), '  ');
  } else {
    // generator / booster / FCS: the three key figures with short labels (CAPACITY 3400  REGEN 900/s  OUTPUT 1400 was wider than the row)
    key = ifrHudFitTokens('gpk', rows.slice(0, 3).map((r) => (GARAGE_KEY_SHORT[r[0]] || r[0].toUpperCase()) + ' ' + r[1]), '  ');
    lines = ifrHudWrapTokens(['gpd', 'gpd2', 'gpd3'], rows.slice(3).map((r) => r[0] + ' ' + r[1]), '  ');
  }
  // against the part that is in the slot now
  const sl = GARAGE_KIND_SLOTS[part.kind] || [], idx = sl.length ? garageTarget(g, part, 0) : -1, cur = idx >= 0 ? PART_BY_ID[g.draft[idx]] : null;
  let cmp = '';
  if (cur && cur.id !== part.id) { const dw = (part.weight || 0) - (cur.weight || 0), de = (part.en || 0) - (cur.en || 0); cmp = 'VS ' + GARAGE_SLOTS[idx] + ': WT ' + (dw >= 0 ? '+' : '') + dw + '  EN ' + (de >= 0 ? '+' : '') + de; }
  // type, rank and price on one row: SHOULDER is shortened when the full row is too wide (SHOULDER / PROJECTILE  RANK 5  3 500 CR was cut)
  if (!cmp && extraRow) cmp = extraRow;
  const tt = [garageTypeText(part), 'RANK ' + part.rank, part.cost ? gfmt(part.cost) + ' CR' : 'FREE'];
  if (typeof ifrHudFits === 'function' && !ifrHudFits('gpt', tt.join('  '))) tt[0] = tt[0].replace('SHOULDER', 'SHLD');
  return { name: part.name, type: ifrHudFitTokens('gpt', tt, '  '), lines, key, cmp };
}
// one EQUIPPED WEAPONS row: picture, short name (+ upgrade level) and the key figures that fit: damage as the upgraded weapon deals it (the core's
// Weapon.setup: a damage track adds pct x level, capped at caps.dps_pct) x pellets, rate or cooldown, magazine / ammo or EN per shot, ability figures
function garageWeaponLine(p, lvl) {
  if (!p) return null;
  const w = p.w || {};
  const up = p.upgrade || {}, caps = /** @type {any} */ (PARTS.caps || {});
  const mult = up.stat === 'damage' ? 1 + Math.min(caps.dps_pct || 10, (up.pct || 0) * (lvl || 0)) / 100 : 1;
  const t = [];
  if (w.damage) t.push('DMG ' + gfmt(w.damage * mult) + (w.pellets ? 'x' + w.pellets : w.count ? 'x' + w.count : ''));
  if (w.rate) t.push(w.rate + '/S'); else if (w.cd) t.push('CD ' + w.cd + 'S');
  if (w.mag && w.ammo) t.push(w.mag + '/' + w.ammo); else if (w.ammo) t.push('AMMO ' + w.ammo); else if (w.en_shot) t.push('EN ' + w.en_shot);
  if (w.block) t.push('BLOCKS ' + Math.round(w.block * 100) + ' %');
  if (w.shield_hp) t.push('BUBBLE ' + gfmt(w.shield_hp)); if (w.heal) t.push('HEAL ' + gfmt(w.heal));
  if (w.charges) t.push(w.charges + ' CHG');
  if (!t.length && w.ability) t.push(String(w.ability).toUpperCase());
  const name = typeof ifrHudShort === 'function' ? ifrHudShort(p.name) : p.name;
  let stats = typeof ifrHudFitTokens === 'function' ? ifrHudFitTokens('ge0s', t, '  ') : t.join('  ');
  if (lvl && (typeof ifrHudFits !== 'function' || ifrHudFits('ge0s', IF_tierName(lvl) + '  ' + stats))) stats = IF_tierName(lvl) + '  ' + stats;      // the upgrade level first, when the row has room
  return { pic: p.key, name, lvl: lvl || 0, stats };
}
function garageKda(pe) { const s = game && guard('summary', () => game.pilotSummary(pe.slot)); return s ? (s.kills | 0) + ' / ' + (s.deaths | 0) + ' / ' + (s.assists | 0) : '- / - / -'; }
function garageDraw(pe) {
  if (!ifrHudGarage) return;
  const g = pe.garage, tab = garageTab(g);
  const b = garageBudgets(pe), sel = g.rows[g.row], trk = g.tracks[g.urow];
  const frame = PART_BY_ID[g.draft[0]], fcs = PART_BY_ID[g.draft[7]];
  const pv = garagePreviewIds(pe);
  let focus = g.col === 2 && trk ? trk.part : sel && sel.part ? sel.part : frame;
  // a setting row (SLOTS / PILOT) explains itself on the ITEM INFORMATION plate; a part row shows the part
  const info = g.col !== 2 && sel && sel.help ? { name: sel.name, type: sel.type || '', lines: ifrHudWrap(['gpd', 'gpd2', 'gpd3'], sel.help), key: '', cmp: '' } : garageInfo(pe, focus);
  const arm = tab.key === 'pri' || tab.key === 'sec' || tab.key === 'spe' || tab.key === 'all', setup = tab.key === 'plt' || tab.key === 'load';
  const legend = g.confirm ? 'SPACE CONFIRM   CTRL CANCEL   OR CLICK' : g.col === 0 ? 'W/S TAB   SPACE OPEN   E/R TURN THE MECH   CTRL BACK'
    : g.col === 1 ? 'W/S ITEM   SPACE EQUIP   A TABS   D TRACKS   F UPGRADE   CTRL BACK' : 'W/S TRACK   SPACE OR CLICK UPGRADES   A LIST   CTRL BACK';
  const st = { tabs: GARAGE_TABS.map((t) => t.title), tab: g.tab, col: g.col, rows: g.rows.slice(g.scroll, g.scroll + GARAGE_VISIBLE), sel: g.row - g.scroll, scroll: g.scroll, total: g.rows.length,
    tracks: g.tracks, urow: g.urow, utitle: !g.tracks.length ? 'NO UPGRADES' : serverMode ? 'COST BASE X (LV+1)' : 'OFFLINE: FREE', budgets: b, lock: fcs && fcs.f ? fcs.f.range : undefined,
    frame: { name: frame ? frame.name : '', type: frame ? garageTypeText(frame) : '' },
    top: { map: String(ARENA.name || ARENA.id || '-'), credits: serverMode ? (pe.pilot ? gfmt(garageCredits(pe)) + ' CR' : 'NO PILOT YET') : 'UNLOCKED', kda: garageKda(pe),
      rank: (serverMode && pe.pilot ? 'R' + pe.pilot.rank : 'OPEN') + ' / SLOT ' + g.slot },
    bay: pv.swap ? pv.swap.name : frame ? frame.name : '', bay2: (pv.swap ? 'PREVIEW   ' : '') + 'BAY ' + (bayOf.has(pe.slot) ? bayOf.get(pe.slot) + 1 : '-') + '   E / R TURN',
    confirm: g.confirm, info, weapons: [1, 2, 3, 4].map((i) => garageWeaponLine(PART_BY_ID[g.draft[i]], garageLevel(pe, g.draft[i]))), legend, pending: g.pending,
    tips: setup ? [tab.key === 'plt' ? 'SPACE CHANGES A SETTING' : 'SPACE PICKS A SLOT   SORTIE SAVES IT', serverMode ? 'KEPT ON THIS SERVER' : 'OFFLINE: KEPT UNTIL THE MAP ENDS']
      : [arm ? 'SPACE EQUIPS R, THEN L IN TURN' : 'SPACE EQUIPS / BUYS (CONFIRMS FIRST)', 'F UPGRADES   D OPENS THE TRACKS'],
    hint: gameTime() - g.msgAt < 4 ? g.msg : '' };
  ifrHudGarage(pe.slot, st);
}

// ---------------------------------------------------------------- the real mech in a hangar bay
// Bays: info_targets ifr_bay_1..ifr_bay_32 on the bay floors (their yaw points to the open side, where the camera goes).
// A player gets a free bay when the garage opens and gives it back when it closes; more garage users than bays share the
// fallback grid around ifr_hangar (or float above the booth when the map has neither).
let bayPool = null;
const bayOf = new Map();     // slot -> bay index
function bayList() {
  if (bayPool) return bayPool;
  bayPool = [];
  for (let i = 1; i <= 32; i++) { const e = ifrFind('ifr_bay_' + i); if (!e) continue; const o = e.GetAbsOrigin(), a = e.GetAbsAngles(); bayPool.push({ pos: v3(o.x, o.y, o.z), yaw: a.yaw, user: -1, n: i, clear: 1e9 }); }
  // the camera side per bay: of 8 directions (the entity's yaw first), the one with the most clear room out to 760 u
  // (a trace at camera height) whose camera spot isn't near another bay's mech; the mapper's yaw wins ties
  for (const b of bayPool) {
    const fixed = CONFIG.BAY_CAMERA_YAW && CONFIG.BAY_CAMERA_YAW[b.n];
    let best = b.yaw, bs = -1e9;
    for (let k = 0; k < 8; k++) {
      if (fixed !== undefined && k > 0) break;
      const yaw = fixed !== undefined ? fixed : b.yaw + k * 45, f = fwdOf(yaw, 0), z = b.pos.z + 220;
      let clear = 760;
      guard('bay trace', () => { const tr = Instance.TraceLine({ start: v3(b.pos.x + f.x * 200, b.pos.y + f.y * 200, z), end: v3(b.pos.x + f.x * 760, b.pos.y + f.y * 760, z), ignorePlayers: true }); if (tr && tr.didHit) clear = 200 + 560 * tr.fraction; });
      let near = 1e9; for (const o of bayPool) { if (o === b) continue; for (const dd of [350, 550, 700]) near = Math.min(near, Math.hypot(b.pos.x + f.x * dd - o.pos.x, b.pos.y + f.y * dd - o.pos.y)); }
      const score = clear - (near < 400 ? 2000 : near < 600 ? 600 : 0) - k * 0.5;
      if (score > bs) { bs = score; best = yaw; }
    }
    b.yaw = best; b.clear = bs;
  }
  if (bayPool.length) log('hangar: ' + bayPool.length + ' bays, camera sides ' + bayPool.map((b) => Math.round(normAngle(b.yaw))).join(' '));
  return bayPool;
}
function bayRelease(slot) { const i = bayOf.get(slot); if (i === undefined) return; bayOf.delete(slot); const b = bayList()[i]; if (b && b.user === slot) b.user = -1; }
function garageBay(slot) {
  const pool = bayList();
  let i = bayOf.get(slot);
  if (i === undefined) { i = pool.findIndex((b) => b.user < 0); if (i >= 0) { pool[i].user = slot; bayOf.set(slot, i); } }
  if (i !== undefined && i >= 0) { garageBayYaw.set(slot, pool[i].yaw); return v3(pool[i].pos.x, pool[i].pos.y, pool[i].pos.z); }
  garageBayYaw.set(slot, -90);  // the camera on the -Y side, as on the grid
  if (!hangarOrigin) { const e = ifrFind('ifr_hangar'); if (e) hangarOrigin = e.GetAbsOrigin(); }
  const col = slot % 8, row = Math.floor(slot / 8) % 8;
  if (hangarOrigin) return v3(hangarOrigin.x + (col - 3.5) * 800, hangarOrigin.y + (row - 3.5) * 1100, hangarOrigin.z);
  if (pool.length) warnOnce('bays full', 'all ' + pool.length + ' hangar bays are in use: extra garage users get a preview above the booth (add more ifr_bay_N)');
  else warnOnce('hangar', 'no ifr_bay_N or ifr_hangar info_targets: the garage preview floats 600 u above the booth');
  const b = boothPos(slot);
  return v3(b.x, b.y, b.z + 600);
}
const garageBayYaw = new Map();   // slot -> yaw of the bay's open side
// turning the preview: degrees per click of a turn button, deg/s while a key (or the mouse on a button) is held, how fast the mech eases to the
// yaw asked for, and where the feet sit on the 1080-high screen (px under the centre; the turn buttons are at y 686 in tools/hud.py)
const GARAGE_REBUILD = 0.12;
const GARAGE_TURN = { click: 45, rate: 140, ease: 10, max: 360, hold: 4, feetPx: 132 };
/** the yaw that faces the garage camera (the camera stands on the bay's open side, looking back at the bay) */
function garageFront(slot) { return garageBayYaw.has(slot) ? garageBayYaw.get(slot) : -90; }
/** the yaw nearest to `from` that is the same direction as `to` (no spin through a full turn when easing back to the front) */
function garageNear(from, to) { return from + normAngle(to - from); }
function garagePreviewDrop(slot) {
  bayRelease(slot);
  const pv = garagePreviews.get(slot); if (!pv) return;
  garagePreviews.delete(slot);
  for (const w of pv.weapons) if (w) releaseProp(w);
  if (pv.legs) releaseProp(pv.legs);
  if (pv.upper) releaseProp(pv.upper);
}
function garagePreviewBuild(pe, pv, fr, wm, paint, sig, key, wkeys, accent) {
  const g = pe.garage;
  for (const w of pv.weapons) if (w) releaseProp(w);
  if (pv.legs) releaseProp(pv.legs);
  if (pv.upper) releaseProp(pv.upper);
  pv.weapons = []; pv.legs = null; pv.upper = null;
  pv.upper = takeProp() || null;
  if (!pv.upper) return;                                       // no prop to spare this tick: try again next tick (sig unchanged)
  propModel(pv.upper, (fr && fr.upper) || FX_MODELS.placeholder || NULL_MODEL);
  if (fr && fr.legs) { pv.legs = takeProp() || null; if (pv.legs) propModel(pv.legs, fr.legs); }
  const ang = { pitch: 0, yaw: normAngle(g.yaw), roll: 0 };
  propPlace(pv.upper, g.bay, ang); if (pv.legs) propPlace(pv.legs, g.bay, ang);
  const hp = (fr && fr.hardpoints) || { ra: [40, -70, 60], la: [40, 70, 60], rs: [-20, -50, 120], ls: [-20, 50, 120] }, keys = ['ra', 'la', 'rs', 'ls'];
  for (let i = 0; i < 4; i++) {
    if (!wm[i]) continue;
    const wp = takeProp(); if (!wp) continue;
    propModel(wp, wm[i]);
    propParent(wp, pv.upper, localToWorld(g.bay, normAngle(g.yaw), 0, weaponMountPos(key, (wkeys && wkeys[i]) || '', i, hp[keys[i]])), ang);   // grip at the palm (models.json#mounts, tools/weapon_fit.py)
    if (accent) propColor(wp, accent);       // the loadout's accent colour: the weapons wear it (the frame wears the paint)
    pv.weapons.push(wp);
  }
  if (paint) { propColor(pv.upper, paint); if (pv.legs) propColor(pv.legs, paint); }
  pv.sig = sig;
}
// every tick the garage is open: keep the preview props in step with the draft, turn the mech, point the camera
function garagePreview(pe, dt) {
  const g = pe.garage; if (!pe.human || !g.bay) return;
  const now = gameTime(), pawn = live(pe.pawn);
  if (!Number.isFinite(g.yaw) || !Number.isFinite(g.yawT)) g.yaw = g.yawT = garageFront(pe.slot);
  if (pawn && !g.confirm) {
    // E / R (the shoulder keys) in any column, A / D in the tabs column; + is anticlockwise from above = the mech's front toward the viewer's right
    const l = pawn.IsInputPressed(KEYS.ls) || (g.col === 0 && pawn.IsInputPressed(KEYS.left)), r = pawn.IsInputPressed(KEYS.rs) || (g.col === 0 && pawn.IsInputPressed(KEYS.right));
    let dir = (r ? 1 : 0) - (l ? 1 : 0);
    // a turn button held down: keeps turning while the engine reports the mouse button (a click that only arrives on release just gives the step)
    if (g.rotHold) { let down = false; try { down = !!pawn.IsInputPressed(KEYS.ra); } catch (err) { down = false; } if (down && now - g.rotAt < GARAGE_TURN.hold) { if (!dir && now - g.rotAt > 0.25) dir = g.rotHold; } else g.rotHold = 0; }
    if (dir) g.yawT += dir * GARAGE_TURN.rate * dt;
  }
  const { ids } = garagePreviewIds(pe), frame = PART_BY_ID[ids[0]], key = frame && frame.model, fr = FRAMES[key];
  { const pv0 = garagePreviews.get(pe.slot); if (pv0 && pv0.frameKey !== undefined && pv0.frameKey !== key) g.yawT = garageNear(g.yaw, garageFront(pe.slot)); if (pv0) pv0.frameKey = key; }   // another frame: face the camera again
  { const d = g.yawT - g.yaw, st = GARAGE_TURN.max * dt; g.yaw += Math.max(-st, Math.min(st, d * (1 - Math.exp(-GARAGE_TURN.ease * dt)))); if (Math.abs(g.yawT - g.yaw) < 0.05) g.yaw = g.yawT; }
  const wm = [1, 2, 3, 4].map((i) => { const p = PART_BY_ID[ids[i]]; return (p && WEAPON_MODELS[p.key]) || ''; });
  const wkeys = [1, 2, 3, 4].map((i) => { const p = PART_BY_ID[ids[i]]; return (p && p.key) || ''; });
  const accent = (() => { const pr = srvProfile(pe), a = pr ? IF_Career.accent(pr.accents[g.slot - 1]) : null; return a ? a.tint : null; })();
  const sig = [key, wm.join('|'), ids[8], accent ? accent.join(',') : ''].join('#');
  let pv = garagePreviews.get(pe.slot);
  if (!pv) { pv = { sig: '', upper: null, legs: null, weapons: [], frameKey: key }; garagePreviews.set(pe.slot, pv); }
  // a rebuild re-parents (Teleports) the weapon props: at most one every GARAGE_REBUILD s, so scrolling the list never Teleports a prop on
  // consecutive ticks (CS2 does not draw a prop Teleported 3+ ticks in a row; the mock flagged it)
  if (pv.sig !== sig && now - (pv.builtAt || -9) >= GARAGE_REBUILD) { pv.builtAt = now; garagePreviewBuild(pe, pv, fr, wm, PAINTS[ids[8]] || null, sig, key, wkeys, accent); }
  const ang = { pitch: 0, yaw: normAngle(g.yaw), roll: 0 };
  if (pv.upper) propPlace(pv.upper, g.bay, ang);
  if (pv.legs) propPlace(pv.legs, g.bay, ang);
  const h = (frame && (PARTS.classes || {})[frame.class] || {}).height || 288; let d = Math.max(600, h * 2.2);
  const by = garageBayYaw.has(pe.slot) ? garageBayYaw.get(pe.slot) : -90, bf = fwdOf(by, 0);
  const bi = bayOf.get(pe.slot), bc = bi !== undefined && bayList()[bi] ? bayList()[bi].clear : 1e9;
  if (bc < d) d = Math.max(380, bc - 40);
  // the camera looks down just enough to put the feet GARAGE_TURN.feetPx under the screen centre, whatever the frame's height and the bay's depth:
  // the turn buttons sit right under them (IFR_HUD_FOCAL px per unit of view tangent, 50_hud.js)
  const camZ = g.bay.z + h * 0.55 + 40, focal = typeof IFR_HUD_FOCAL === 'number' ? IFR_HUD_FOCAL : 720;
  const pitch = Math.atan2(camZ - g.bay.z, d) - Math.atan2(GARAGE_TURN.feetPx, focal);
  controlledCamera(pe, v3(g.bay.x + bf.x * d, g.bay.y + bf.y * d, camZ), v3(g.bay.x, g.bay.y, camZ - d * Math.tan(pitch)));
}

// ---------------------------------------------------------------- input
function garageTick(pe) {
  const g = pe.garage; if (!g || !g.open) return;
  const now = gameTime(), dt = g.lastT ? Math.min(0.1, Math.max(0, now - g.lastT)) : 0.016; g.lastT = now;
  const k = menuKeys(pe);
  if (k) garageKeys(pe, k);
  guard('garage preview', () => garagePreview(pe, dt));
  if (k || g.dirty || now - g.drawAt > 0.5) {
    g.dirty = false; g.drawAt = now; garageDraw(pe);
    if (pe.human && typeof ifrHudKeepCapture === 'function') ifrHudKeepCapture(pe.slot);     // the mouse stays on while the garage is open
  }
}
function garageKeys(pe, k) {
  const g = pe.garage, tab = garageTab(g);
  if (g.pending) return;
  if (g.confirm) { if (k & MK.ok) garageConfirm(pe, true); else if (k & MK.back) garageConfirm(pe, false); return; }
  if (g.col === 0) {
    if (k & (MK.up | MK.down)) { garageSetTab(pe, (g.tab + GARAGE_TABS.length + ((k & MK.up) ? -1 : 1)) % GARAGE_TABS.length); sndTone(pe.slot, 'ui_garage_move'); }
    if (k & MK.ok) { if (tab.key === 'sortie') garagePick(pe); else g.col = 1; }
  } else if (g.col === 1) {
    if (k & MK.up) g.row = Math.max(0, g.row - 1);
    if (k & MK.down) g.row = Math.min(g.rows.length - 1, g.row + 1);
    garageScrollFix(g);
    if (k & (MK.up | MK.down)) sndTone(pe.slot, 'ui_garage_move');
    if (k & MK.left) g.col = 0; else if ((k & MK.right) && g.tracks.length) g.col = 2;
    if (k & MK.ok) garagePick(pe);
    if (k & MK.cycle) { const s = g.rows[g.row]; if (s && s.part) garageUpgradeAsk(pe, s.part); }
    if (k & MK.back) g.col = 0;
  } else {
    if (k & MK.up) g.urow = Math.max(0, g.urow - 1);
    if (k & MK.down) g.urow = Math.min(g.tracks.length - 1, g.urow + 1);
    if (k & (MK.up | MK.down)) sndTone(pe.slot, 'ui_garage_move');
    if (k & (MK.ok | MK.cycle)) { const t = g.tracks[g.urow]; if (t) garageUpgradeAsk(pe, t.part); }
    if (k & (MK.left | MK.back)) g.col = 1;
  }
  if ((k & MK.back) && g.col === 0 && pe.status === 'dead') garageClose(pe);   // back from the top level: watch the fight
}
function garageSetTab(pe, i) { const g = pe.garage; g.tab = i; g.row = 0; g.scroll = 0; garageRows(pe); g.dirty = true; }
// where a part goes: the slot of its kind; arms / shoulders: `explicit` (1..4); a part in one hand already goes to the other (a pair);
// else the hands take turns, R first (g.nextSide per kind; Nov 2026 playtest: every pick went to R, so the L weapon could never change)
function garageTarget(g, p, explicit) {
  const sl = GARAGE_KIND_SLOTS[p.kind] || []; if (!sl.length) return -1;
  if (sl.length === 1) return sl[0];
  if (explicit) return explicit;
  if (p.left_only) return sl[1];
  const inR = g.draft[sl[0]] === p.id, inL = g.draft[sl[1]] === p.id;
  if (inR && !inL) return sl[1];
  if (inL && !inR) return sl[0];
  return sl[(g.nextSide && g.nextSide[p.kind]) || 0];
}
function garagePick(pe) {
  const g = pe.garage, tab = garageTab(g), sel = g.rows[g.row];
  if (!sel) return;
  if (tab.key === 'sortie') {
    if (sel.id === -10) { garageSave(pe, false); return; }
    const b = garageBudgets(pe);
    if (!b.valid) { garageSay(pe, DENY_TEXT[b.deny] || 'invalid loadout'); sndTone(pe.slot, 'ui_garage_deny'); return; }
    garageSave(pe, true); return;
  }
  if (sel.id <= -30 && sel.id > -100) { garagePilotPick(pe, sel.id); return; }
  if (tab.key === 'load') {
    const k = -sel.id, pl = garagePilot(pe);
    const l = pl ? pl.loadouts[k - 1] : null;
    g.slot = k;
    if (l) g.draft = garageParse(l);
    garageSay(pe, 'Loadout ' + k + ' selected'); sndTone(pe.slot, 'ui_garage_ok'); garageRows(pe); return;
  }
  if (sel.empty) { g.draft[sel.empty] = 0; garageRows(pe); sndTone(pe.slot, 'ui_garage_ok'); return; }
  const p = sel.part; if (!p) return;
  if (sel.state === 'locked') { garageSay(pe, 'Rank ' + p.rank + ' needed'); sndTone(pe.slot, 'ui_garage_deny'); return; }
  if (sel.state === 'poor') { garageSay(pe, 'Need ' + gfmt(p.cost) + ' CR'); sndTone(pe.slot, 'ui_garage_deny'); return; }
  if (sel.state === 'buy') {
    g.confirm = { op: 'buy', id: p.id, q: 'Buy ' + p.name + ' for ' + gfmt(p.cost) + ' CR?', hint: 'Space confirm / Ctrl cancel' };
    sndTone(pe.slot, 'ui_garage_move'); return;
  }
  const t = garageTarget(g, p, 0);
  if (t < 0) return;
  g.draft[t] = p.id;
  const sl = GARAGE_KIND_SLOTS[p.kind] || [];
  if (sl.length === 2) { g.nextSide = g.nextSide || {}; g.nextSide[p.kind] = t === sl[0] ? 1 : 0; garageSay(pe, GARAGE_SLOTS[t] + ': ' + p.name); }
  garageRows(pe); sndTone(pe.slot, 'ui_garage_ok');
}
// ask before an upgrade (a part of the list or a track)
function garageUpgradeAsk(pe, part) {
  const g = pe.garage;
  if (!part || !part.upgrade) { garageSay(pe, 'No upgrade track'); return; }
  if (!garageOwned(pe, part.id)) { garageSay(pe, 'Buy it first'); sndTone(pe.slot, 'ui_garage_deny'); return; }
  if (serverMode && !pe.pilot) { garageSay(pe, 'No pilot record from the server yet'); sndTone(pe.slot, 'ui_garage_deny'); return; }   // credits unknown: not 'Need N CR'
  const idx = GARAGE_KIND_SLOTS[part.kind][0], t = garageTrackOf(pe, idx, part);
  if (t.state === 'max') { garageSay(pe, 'Already at ' + IF_tierName(t.max)); sndTone(pe.slot, 'ui_garage_deny'); return; }
  if (t.state === 'poor') { garageSay(pe, 'Need ' + gfmt(t.cost) + ' CR'); sndTone(pe.slot, 'ui_garage_deny'); return; }
  g.confirm = { op: 'upg', id: part.id, q: 'Upgrade ' + part.name + ' to ' + IF_tierName(t.lvl + 1) + (serverMode && t.cost ? ' for ' + gfmt(t.cost) + ' CR?' : '? (free offline)'), hint: 'Space confirm / Ctrl cancel' };
  sndTone(pe.slot, 'ui_garage_move');
}
function garageConfirm(pe, yes) {
  const g = pe.garage, c = g.confirm; g.confirm = null; g.dirty = true;
  if (!c) return;
  if (!yes) { garageSay(pe, 'Cancelled'); return; }
  const p = PART_BY_ID[c.id]; if (!p) return;
  if (!serverMode) {      // stand-alone: no credits, no server; the upgrade goes on the local pilot and to the core at once
    if (c.op !== 'upg') return;
    const lp = garageLocalPilot(pe), max = (PARTS.caps || {}).levels || 5, lvl = Math.min(max, (lp.upgrades[p.id] || 0) + 1);
    lp.upgrades[p.id] = lvl;
    if (game) guard('local pilot', () => game.setPilot(pe.slot, lp));
    garageRows(pe); garageSay(pe, p.name + ' ' + IF_tierName(lvl) + ': next sortie'); sndTone(pe.slot, 'ui_garage_ok');
    return;
  }
  g.pending = true;
  if (c.op === 'buy') { srvPending.set(pe.slot, { op: 'buy', at: gameTime() }); srvSend(pe.slot, 'buy', [p.id]); garageSay(pe, 'Buying ' + p.name + '...'); }
  else { srvPending.set(pe.slot, { op: 'upg', at: gameTime() }); srvSend(pe.slot, 'upg', [p.id]); garageSay(pe, 'Upgrading ' + p.name + '...'); }
}
function garageSave(pe, thenSortie) {
  const g = pe.garage; const l = garageStr(g.draft);
  if (serverMode) {
    g.pending = true; g.sortieAfter = !!thenSortie;
    srvPending.set(pe.slot, { op: 'save', at: gameTime() });
    srvSend(pe.slot, 'save', [g.slot, l]);
    garageSay(pe, 'Saving loadout ' + g.slot + '...');
  } else {
    const code = guard('setLoadout', () => game.setLoadout(pe.slot, l));
    if (code) { garageSay(pe, DENY_TEXT[code] || 'invalid loadout'); sndTone(pe.slot, 'ui_garage_deny'); return; }
    const lp = garageLocalPilot(pe); lp.loadouts[g.slot - 1] = l; lp.active = g.slot;      // the session keeps all six slots
    if (thenSortie) garageSortie(pe); else { garageSay(pe, 'Loadout set'); sndTone(pe.slot, 'ui_garage_ok'); }
  }
}
function garageSortie(pe) {
  garageClose(pe);
  pe.ready = true;
  guard('requestSpawn', () => game.requestSpawn(pe.slot));
  sndTone(pe.slot, 'ui_garage_ok');
}
// the server answered with a fresh pilot state
function garagePilotUpdated(pe) {
  if (game && pe.pilot) guard('setLoadout srv', () => { const l = pe.pilot.loadouts[pe.pilot.active - 1]; if (l) game.setLoadout(pe.slot, l); });
  const g = pe.garage; if (!g) return;
  const was = g.pending; g.pending = false;
  if (!g.open) return;
  if (was) { garageSay(pe, 'OK'); sndTone(pe.slot, 'ui_garage_ok'); }
  garageRows(pe);
  if (g.sortieAfter) { g.sortieAfter = false; garageSortie(pe); return; }
  garageDraw(pe);
}
function garageDenied(pe, code, text) {
  const g = pe.garage; if (!g) return;
  g.pending = false; g.sortieAfter = false; g.confirm = null;
  garageSay(pe, text || DENY_TEXT[code] || 'denied'); sndTone(pe.slot, 'ui_garage_deny');
  if (g.open) garageDraw(pe);
}

// ---------------------------------------------------------------- the mouse (custom_hud_layout Buttons)
function garageClick(pe, id) {
  const g = pe.garage; if (!g || !g.open || g.pending) return;
  let m;
  if (g.confirm) {
    if (id === 'ifr_gcy') garageConfirm(pe, true); else if (id === 'ifr_gcx') garageConfirm(pe, false);
  } else if ((m = /^ifr_gc(\d+)$/.exec(id))) {
    const i = +m[1]; if (i < GARAGE_TABS.length) { g.col = 1; garageSetTab(pe, i); sndTone(pe.slot, 'ui_garage_move'); }
  } else if ((m = /^ifr_gr(\d+)$/.exec(id))) {
    const r = g.scroll + (+m[1]); if (r >= g.rows.length) return;
    if (g.col === 1 && g.row === r) garagePick(pe); else { g.col = 1; g.row = r; sndTone(pe.slot, 'ui_garage_move'); }
  } else if ((m = /^ifr_ur(\d+)$/.exec(id))) {
    const i = +m[1]; if (i >= g.tracks.length) return;
    g.col = 2; g.urow = i; garageUpgradeAsk(pe, g.tracks[i].part);      // one click asks (the confirm bar is the safety); it used to need a second click
  } else if (id === 'ifr_grl' || id === 'ifr_grr') {       // the turn buttons under the mech's feet
    const dir = id === 'ifr_grr' ? 1 : -1;
    g.yawT += dir * GARAGE_TURN.click; g.rotHold = dir; g.rotAt = gameTime(); sndTone(pe.slot, 'ui_garage_move');
  } else if (id === 'ifr_grf') { g.yawT = garageNear(g.yaw, garageFront(pe.slot)); g.rotHold = 0; sndTone(pe.slot, 'ui_garage_move');
  } else if (id === 'ifr_gup' || id === 'ifr_gdn') {
    const d = id === 'ifr_gup' ? -GARAGE_VISIBLE : GARAGE_VISIBLE;
    g.scroll = Math.max(0, Math.min(Math.max(0, g.rows.length - GARAGE_VISIBLE), g.scroll + d));
    g.row = Math.max(g.scroll, Math.min(g.scroll + GARAGE_VISIBLE - 1, g.row)); g.col = 1; sndTone(pe.slot, 'ui_garage_move');
  } else return;
  g.dirty = true;
  garageDraw(pe);
}
// every button id is logged the first time it is clicked (in-game check that clicks arrive: the 10 Nov 2026 playtest saw no response from the tracks)
const garageClickSeen = new Set();
if (typeof Instance.OnCustomHudClicked === 'function') {
  Instance.OnCustomHudClicked(({ player, buttonId }) => guard('hud click', () => {
    const s = slotOfEntity(player), pe = s !== undefined ? person(s) : undefined;
    if (!garageClickSeen.has(buttonId)) { garageClickSeen.add(buttonId); log('HUD click ' + buttonId + ' (slot ' + s + (pe && pe.garage && pe.garage.open ? ', garage open' : ', garage closed') + ')'); }
    if (pe) garageClick(pe, buttonId);
  }));
}
