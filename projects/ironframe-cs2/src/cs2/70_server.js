// ===================================================================================================================
// IRONFRAME CS2 adapter, part 7: the server plugin channel (docs/SERVER_CONTRACT.md). MAP CONTRACT: the SlimeMG
// IronFrame module depends on these names and formats (ifr_srv lines, mgstat keys, the ifr_* script inputs, the
// mailbox payload). Add, never rename.
// map -> server: `echo ifr_srv <slot> <op> [args]` and `echo mgstat <slot> <stat> [n]` (echo is on Valve's Workshop
// command allow list). server -> map: RunScriptInput ifr_server / ifr_pilot / ifr_deny on ifr_script with the player's
// pawn as the activator; the payload is the targetname of the slot's mailbox entity (ifr_mail_NN:<payload>), or the
// origins of ifr_mail_NN_0..3 in the origin-encoding fallback.
// Payload kinds (the first field of the string form / the page header's third int): p1 / 1 the pilot's career, d1 / 2 a refusal,
// q1 / 3 the pilot's profile (customisation, contracts, leaderboard place), o1 / 6 the owned parts (the origin form of p1 has no
// room for them); with ifr_server and NO activator, in mailbox 00: r1 / 4 the operator's match rules, t1 / 5 the leaderboard.
// ===================================================================================================================
let serverMode = false, statsOn = false;
let helloAt = 0, lastHelloAt = -1e9, serverSeen = false;
const mailEnts = [];        // slot -> info_target handle (or undefined)
const mailAlt = [];         // slot -> [ent0..ent3] for the origin fallback
const srvPending = new Map();   // slot -> {op, at}

function srvSend(slot, op, args) {
  const line = 'echo ifr_srv ' + slot + ' ' + op + (args && args.length ? ' ' + args.map((a) => String(a).replace(/[;"\s]/g, '')).join(' ') : '');
  guard('ifr_srv', () => ifrCmd(line));
}
function ifrStat(slot, key, n) {
  if (!statsOn || Instance.IsWarmupPeriod()) return;
  const pe = person(slot); if (!pe || !pe.human) return;
  const k = String(key).toLowerCase().replace(/[^a-z0-9_]/g, '').slice(0, 32);
  if (!k) return;
  guard('mgstat', () => ifrCmd('echo mgstat ' + slot + ' ' + k + (n !== undefined && n !== 1 ? ' ' + Math.round(n) : '')));
}
function srvInit() { srvFindMail(); helloAt = gameTime(); srvHello(); }
// map entities are re-created at every round restart: look the mailboxes up again
function srvFindMail() {
  mailEnts.length = 0; mailAlt.length = 0; mailPages.clear();
  for (let s = 0; s < 64; s++) {
    mailEnts[s] = ifrFind(CONFIG.MAIL_PREFIX + pad2(s));
    const alt = []; for (let k = 0; k < 4; k++) { const e = ifrFind(CONFIG.MAIL_PREFIX + pad2(s) + '_' + k); if (e) alt.push(e); }
    mailAlt[s] = alt;
  }
}
function srvHello() { lastHelloAt = gameTime(); srvSend(-1, 'hello', [CONFIG.PROTOCOL, IFR_VERSION]); }
function srvOnJoin(slot) { if (serverMode) srvWant(slot); }
// `want` at most once every 2 s a pilot: one round start fires ifr_server several times (rules, leaderboard pages), and the plugin
// drops ops past 10 in 10 s
const srvWantAt = new Map();
function srvWant(slot) { const now = gameTime(); if (now - (srvWantAt.get(slot) || -99) < 2) return; srvWantAt.set(slot, now); srvSend(slot, 'want', []); }
// extended round statistics are queued and sent a few a tick: 64 pilots x ~30 lines in one tick would be ~2 000 console commands at once
const statQueue = [];
function ifrStatLater(slot, key, n) { if (statsOn && n > 0 && statQueue.length < 6000) statQueue.push([slot, key, n]); }
function srvStatDrain() {
  for (let k = 0; k < (CONFIG.SRV_STATS_PER_TICK || 24) && statQueue.length; k++) { const q = statQueue.shift(); ifrStat(q[0], q[1], q[2]); }
}
function srvTick(now) {
  if (statQueue.length) srvStatDrain();
  if (!serverMode && !serverSeen && now - lastHelloAt > CONFIG.HELLO_EVERY) srvHello();
  for (const [slot, p] of srvPending) if (now - p.at > 5) { srvPending.delete(slot); const pe = person(slot); if (pe) garageDenied(pe, 0, 'no answer from the server'); }
}
// the payload for a slot: after the first ':' of the mailbox name (MailboxMode "name"), else the origin encoding
// (MailboxMode "origin": the plugin Teleports ifr_mail_NN_0..3, 3 ints 0..8191 each = 12 ints per page: [page, pages, kind,
// 9 values...]; one RunScriptInput per page; pilot values [rank, active, flags, xp lo13, xp hi13, credits lo13, credits hi13,
// n, (id, lvl) x n, L1[9], L2[9], L3[9]], deny values [code, ref]). Returns the string form, or null while pages are missing.
const mailPages = new Map();   // slot -> {pages, kind, got: Map(page -> ints[9])}
// `kinds`: the page kinds / string prefixes the caller takes (the ifr_server reader takes only rules and the leaderboard, so slot 0's own
// pilot pages are never mistaken for them)
const MAIL_PREFIX_KIND = { p1: 1, d1: 2, q1: 3, r1: 4, t1: 5, o1: 6 };
function mailRead(slot, kinds) {
  const e = live(mailEnts[slot]);
  if (e) {
    const name = String(e.GetEntityName() || ''); const i = name.indexOf(':');
    if (i >= 0 && i < name.length - 1) { const s = name.slice(i + 1); return !kinds || kinds.indexOf(MAIL_PREFIX_KIND[s.slice(0, 2)]) >= 0 ? s : null; }
  }
  const alt = mailAlt[slot] || [];
  if (alt.length < 4) return null;
  const ints = [];
  for (const a of alt) { if (!live(a)) return null; const o = a.GetAbsOrigin(); ints.push(Math.round(o.x), Math.round(o.y), Math.round(o.z)); }
  const page = ints[0], pages = Math.max(1, ints[1]), kind = ints[2];
  if (kinds && kinds.indexOf(kind) < 0) return null;
  let st = mailPages.get(slot);
  if (!st || st.pages !== pages || st.kind !== kind || page === 0 && st.got.size >= pages) { st = { pages, kind, got: new Map() }; mailPages.set(slot, st); }
  st.got.set(page, ints.slice(3));
  if (st.got.size < pages) return null;
  const vals = []; for (let k = 0; k < pages; k++) { const pg = st.got.get(k); if (!pg) return null; for (const x of pg) vals.push(x); }
  mailPages.delete(slot);
  return srvDecodeInts(kind, vals, slot);
}
// the owned parts in the origin form (kind 6): [1, blocks, (lo13, hi13) x blocks]: block b carries ids 100 b + 0..25
function srvOwnedFromInts(v) {
  if ((v[0] | 0) < 1) return null;
  const out = [];
  for (let b = 0; b < Math.min(10, v[1] | 0); b++) { const bits = (v[2 + 2 * b] | 0) + (v[3 + 2 * b] | 0) * 8192; for (let k = 0; k < 26; k++) if (Math.floor(bits / Math.pow(2, k)) % 2 === 1) out.push(b * 100 + k); }
  return 'o1.' + (out.length ? out.join(',') : '0');
}
function srvDecodeInts(kind, v, slot) {
  let i = 0; const next = () => (i < v.length ? v[i++] : 0);
  if (kind === 2) return 'd1.' + next() + '.' + next();
  if (kind === 3) return IF_Career.profileFromInts(v);
  if (kind === 4) return IF_Career.rulesFromInts(v);
  if (kind === 5) return IF_Career.boardFromInts(v);
  if (kind === 6) return srvOwnedFromInts(v);
  if (kind !== 1) return null;
  const rank = next(), active = next(), flags = next(), xp = next() + next() * 8192, credits = next() + next() * 8192;
  const n = next(); const ups = []; for (let k = 0; k < n; k++) { const id = next(), lvl = next(); if (id) ups.push(id + '-' + lvl); }
  const lds = []; for (let l = 0; l < 3; l++) { const ids = []; for (let k = 0; k < 9; k++) ids.push(next()); lds.push(ids.every((x) => x === 0) ? '0' : ids.join(',')); }
  // the origin form carries no owned bitset: the o1 payload brings it (sent at load and after a purchase); until it arrives every part
  // in the loadouts and the starter kit counts as owned. The server still validates every save and buy.
  const pe0 = srvAny(person(slot));
  const owned = new Set((pe0 && pe0.ownedSrv) || (PARTS.starter && PARTS.starter.owned) || []);
  for (const l of lds) if (l !== '0') for (const id of l.split(',')) owned.add(parseInt(id, 10));
  const nib = []; for (const id of owned) if (id > 0) { const k = id >> 2; while (nib.length <= k) nib.push(0); nib[k] |= 1 << (id & 3); }
  let hex = ''; for (let k = nib.length - 1; k >= 0; k--) hex += nib[k].toString(16);
  return ['p1', rank, xp, credits, active, hex.replace(/^0+/, '') || '0', ups.length ? ups.join(',') : '0', lds[0], lds[1], lds[2], flags].join('.');
}
// "p1.<rank>.<xp>.<credits>.<active>.<owned hex>.<upgrades>.<L1>.<L2>.<L3>.<flags>" -> pilot object (INTERFACES 3)
function parsePilot(s) {
  const f = String(s).split('.');
  if (f[0] !== 'p1' || f.length < 11) return null;
  const owned = new Set();
  const hex = f[5] || '0';
  for (let i = 0; i < hex.length; i++) {
    const nib = parseInt(hex[hex.length - 1 - i], 16); if (!Number.isFinite(nib)) continue;
    for (let b = 0; b < 4; b++) if (nib & (1 << b)) owned.add(i * 4 + b);
  }
  const upgrades = {};
  if (f[6] && f[6] !== '0') for (const pair of f[6].split(',')) { const [id, lvl] = pair.split('-').map(Number); if (Number.isFinite(id) && Number.isFinite(lvl)) upgrades[id] = lvl; }
  const loadouts = [f[7] || '0', f[8] || '0', f[9] || '0'].map((l) => (l === '0' ? null : l));
  return { rank: Math.max(1, parseInt(f[1], 10) || 1), xp: parseInt(f[2], 10) || 0, credits: parseInt(f[3], 10) || 0, active: Math.min(IF_Career.slots, Math.max(1, parseInt(f[4], 10) || 1)),
    owned, upgrades, loadouts, flags: parseInt(f[10], 10) || 0 };
}
function onServerInput() {
  if (!serverMode) log('server mode: the SlimeMG IronFrame module is here (progression on)');
  serverMode = true; serverSeen = true;
  // the operator's match rules (r1) or the leaderboard (t1) ride in mailbox 00 with this input (no activator); a plugin that sends neither
  // leaves the map's own rules
  const payload = guard('srv mail', () => mailRead(0, [4, 5]));
  if (payload && payload.slice(0, 2) === 'r1') srvRulesIn(payload);
  else if (payload && payload.slice(0, 2) === 't1') { srvBoardIn(payload); return; }
  for (const pe of people.values()) if (pe.human && (pe.team === TEAM_T || pe.team === TEAM_CT) && !pe.pilot) srvWant(pe.slot);
}
let srvRulesText = '';
function srvRulesIn(payload) {
  const r = IF_Career.parseRules(payload); if (!r) { warnOnce('rules bad', 'ifr_server rules not readable (' + payload.slice(0, 40) + ')'); return; }
  IF_Career.setRules(r);
  if (payload !== srvRulesText) { srvRulesText = payload; log('server rules: ' + (IF_Career.rules() ? 'rotation ' + (r.rotation.join(' ') || 'map') + ', round ' + (r.roundS || 'map') + ' s, AI ' + r.aiMin + '-' + r.aiMax + ', XP x' + r.xpRate + ', flags ' + r.flags : "the map's own")); }
}
// the server's leaderboard: {total, rows: [{name, rank, xp}]} (null stand-alone / before the first one)
let srvBoard = null;
function srvBoardIn(payload) {
  const b = IF_Career.parseBoard(payload); if (!b) return;
  srvBoard = b;
  for (const pe of people.values()) if (pe.human && pe.garage && pe.garage.open) { garageRows(pe); pe.garage.dirty = true; }
}
function onPilotInput(ev) {
  const slot = slotOfEntity(ev && ev.activator);
  if (slot === undefined) { warnOnce('pilot noact', 'ifr_pilot without a player activator'); return; }
  const pe = person(slot); if (!pe) return;
  const payload = mailRead(slot);
  if (!payload) return;                                   // a page of a longer payload: the rest follows
  const kind = payload.slice(0, 2);
  if (kind === 'q1') { srvProfileIn(pe, payload); return; }
  if (kind === 'o1') { srvOwnedIn(pe, payload); return; }
  const pilot = parsePilot(payload);
  if (!pilot) { warnOnce('pilot bad ' + slot, 'ifr_pilot for slot ' + slot + ' with no readable payload (' + payload.slice(0, 40) + ')'); return; }
  const was = pe.pilot;
  if (srvAny(pe).ownedSrv) for (const id of srvAny(pe).ownedSrv) pilot.owned.add(id);
  pe.pilot = pilot;
  srvMergeLoadouts(pe);
  srvAccentCheck(pe);
  srvPending.delete(slot);
  // rank up: say it, and list what the new rank unlocks to buy
  if (was && pilot.rank > was.rank) {
    const unlocked = (PARTS.parts || []).filter((p) => !p.pve && p.rank > was.rank && p.rank <= pilot.rank).map((p) => p.name);
    reply(slot, 'RANK ' + pilot.rank + '!' + (unlocked.length ? ' Unlocked: ' + unlocked.slice(0, 4).join(', ') + (unlocked.length > 4 ? ' +' + (unlocked.length - 4) + ' more' : '') : ''), 8);
    sndTone(slot, 'ui_podium');
  }
  if (game) guard('pilot', () => game.setPilot && game.setPilot(slot, pilot));
  garagePilotUpdated(pe);
}
// the career payload carries loadouts 1-3, the profile 4-6: the pilot record the garage and the core use has all six
function srvMergeLoadouts(pe) {
  if (!pe.pilot) return;
  const pr = pe.profile, l = pe.pilot.loadouts;
  for (let k = 0; k < 3; k++) l[3 + k] = pr ? pr.loadouts[k] : (l[3 + k] || null);
}
function srvOwnedIn(pe, payload) {
  const set = new Set(payload === 'o1.0' ? [] : payload.slice(3).split(',').map((x) => parseInt(x, 10)).filter((x) => x > 0));
  srvAny(pe).ownedSrv = set;
  if (pe.pilot) { for (const id of set) pe.pilot.owned.add(id); if (pe.garage && pe.garage.open) { garageRows(pe); pe.garage.dirty = true; } }
}
function srvProfileIn(pe, payload) {
  const pr = IF_Career.parseProfile(payload);
  if (!pr) { warnOnce('profile bad ' + pe.slot, 'profile for slot ' + pe.slot + ' not readable (' + payload.slice(0, 40) + ')'); return; }
  const was = pe.profile;
  pe.profile = pr;
  srvMergeLoadouts(pe);
  // a contract finished since the last profile: say it once
  if (was) for (const d of pr.daily) { const o = was.daily.find((x) => x.code === d.code && x.goal === d.goal); if (o && o.progress < o.goal && d.progress >= d.goal) { reply(pe.slot, 'CONTRACT COMPLETE: ' + IF_Career.contractLabel(d.code) + '  +' + d.reward + ' CR', 6); sndTone(pe.slot, 'ui_podium'); } }
  const waited = srvPending.get(pe.slot);
  if (waited && waited.profile) { srvPending.delete(pe.slot); if (pe.garage) { pe.garage.pending = false; if (pe.garage.open) { garageSay(pe, 'OK'); sndTone(pe.slot, 'ui_garage_ok'); } } }
  srvProfileApply(pe);
}
// ---------------------------------------------------------------- customisation that follows the pilot (SERVER_CONTRACT.md section 8)
// The profile: the server's (server mode) or the session's own (stand-alone: nothing is saved, every title and badge can be worn).
function srvProfile(pe) {
  if (serverMode) return pe.profile || null;
  if (!pe.localProfile) { pe.localProfile = IF_Career.blank(); for (const h of IF_Career.data.honours) pe.localProfile.earned.add(h.id); }
  return pe.localProfile;
}
// (fields this file keeps on a person: profile, localProfile, ownedSrv, hintsOff)
function srvAny(pe) { return /** @type {any} */ (pe); }
function srvHintsOff(slot) { const pe = srvAny(person(slot)); return !!(pe && pe.hintsOff); }
function srvProfileOf(slot) { const pe = slot < 64 ? person(slot) : null; return pe && pe.human ? srvProfile(pe) : null; }
// what the HUD calls a pilot: the callsign when one is set (10_util.js nameOf), the badge's tag on the kill line, the title on the podium
function srvCallsign(slot) { const pr = srvProfileOf(slot); return pr && pr.callsign ? pr.callsign : ''; }
function srvIdentity(slot) { return IF_Career.identity(srvProfileOf(slot), nameOf(slot)); }
function srvKillName(slot) { const id = srvIdentity(slot); return (id.tag ? '[' + id.tag + '] ' : '') + id.name; }
// the accent colour of the loadout a pilot flies (the weapon props take it; null = none)
function srvAccentOf(slot) {
  const pe = slot < 64 ? person(slot) : null, pr = pe && pe.human ? srvProfile(pe) : null; if (!pr) return null;
  const k = serverMode ? (pe.pilot ? pe.pilot.active : 1) : ((pe.garage && pe.garage.slot) || 1);
  const a = IF_Career.accent(pr.accents[k - 1]);
  return a ? a.tint : null;
}
// a new accent (another colour, another active slot): the mech's rig is dropped, and the next draw takes fresh weapon props in the new
// colour (30_render.js renderMech claims a rig every tick; the colour is given when a weapon prop is taken)
function srvAccentCheck(pe) {
  const x = srvAny(pe), sig = String(srvAccentOf(pe.slot) || '');
  if (x.accentSig !== undefined && x.accentSig !== sig && typeof renderDropMech === 'function') guard('accent rig', () => renderDropMech(pe.slot));
  x.accentSig = sig;
}
// the preferences and the pilot plate follow the profile
function srvProfileApply(pe) {
  const pr = srvProfile(pe); if (!pr) return;
  srvAccentCheck(pe);
  pe.camScale = IF_Career.camera(pr.prefs & IF_Career.PREF_CAM).mult || 1;
  srvAny(pe).hintsOff = !!(pr.prefs & IF_Career.PREF_HINTS_OFF);
  if (typeof ifrHudPilot === 'function') guard('hud pilot', () => ifrHudPilot(pe.slot));
  if (pe.garage && pe.garage.open) { garageRows(pe); pe.garage.dirty = true; }
}
/** One customisation change. what: 'callsign' (text) | 'name' (k, text) | 'accent' (k, id) | 'title' (id) | 'badge' (id) | 'pref' (prefs) | 'fav' (frame id).
 *  Stand-alone it is applied to the session's profile at once; in server mode the op goes to the plugin, which answers with the profile (q1)
 *  or a refusal. Returns 0 or a deny code (the same checks as the plugin's, so a refusal rarely needs the round trip). */
function srvCustom(pe, what, a, b) {
  const pr = srvProfile(pe), D = IF_Career.data;
  if (!pr) return IF_DENY.BAD;
  const k = a | 0;
  let args, apply;
  if (what === 'callsign' || what === 'name') {
    const raw = String((what === 'name' ? b : a) || ''), text = IF_Career.clean(raw, what === 'name' ? D.name_len : D.callsign_len);
    if (raw.trim() && !text) return IF_DENY.TEXT;
    if (what === 'name') { if (!(k >= 1 && k <= IF_Career.slots)) return IF_DENY.BAD; args = [k, IF_Career.wire(text)]; apply = () => { pr.names[k - 1] = text; }; }
    else { args = [IF_Career.wire(text)]; apply = () => { pr.callsign = text; }; }
  } else if (what === 'accent') {
    const id = b | 0;
    if (!(k >= 1 && k <= IF_Career.slots) || (id && !IF_Career.accent(id))) return IF_DENY.BAD;
    args = [k, id]; apply = () => { pr.accents[k - 1] = id; };
  } else if (what === 'title' || what === 'badge') {
    const h = IF_Career.honour(k);
    if (k && (!h || h.kind !== what)) return IF_DENY.BAD;
    if (k && !pr.earned.has(k)) return IF_DENY.NOT_EARNED;
    args = [k]; apply = () => { pr[what] = k; };
  } else if (what === 'pref') {
    const v = (k & IF_Career.PREF_HINTS_OFF) | Math.min(k & IF_Career.PREF_CAM, D.camera.length - 1);
    args = [v]; apply = () => { pr.prefs = v; };
  } else if (what === 'fav') {
    const p = k ? (PARTS.parts || []).find((x) => x.id === k) : null;
    if (k && (!p || p.kind !== 'frame' || p.pve)) return IF_DENY.BAD;
    args = [k]; apply = () => { pr.fav = k; };
  } else return IF_DENY.BAD;
  if (serverMode) {
    // shown at once (the plugin's answer replaces it; a refusal brings the old profile back with the next q1)
    apply();
    srvPending.set(pe.slot, { op: what, at: gameTime(), profile: true });
    srvSend(pe.slot, what, args.filter((x) => x !== ''));
  } else apply();
  srvProfileApply(pe);
  return 0;
}
function onDenyInput(ev) {
  const slot = slotOfEntity(ev && ev.activator);
  if (slot === undefined) return;
  const pe = person(slot); if (!pe) return;
  const payload = mailRead(slot) || '';
  const f = payload.split('.');
  const code = f[0] === 'd1' ? parseInt(f[1], 10) || 0 : 0;
  const waited = srvPending.get(slot);
  srvPending.delete(slot);
  if (waited && waited.profile) { srvSend(slot, 'want', []); if (!pe.garage || !pe.garage.open) reply(slot, DENY_TEXT[code] || DENY_TEXT[0], 4); }   // the shown change was refused: fetch the real profile
  garageDenied(pe, code, '');
}
const DENY_TEXT = { 0: 'the server said no', 1: 'you do not own that part', 2: 'your rank is too low', 3: 'not enough credits', 4: 'over the weight limit', 5: 'over the EN budget', 6: 'already at the maximum level', 7: 'that loadout is not valid', 8: 'too fast: try again in a moment', 9: 'that text is not allowed', 10: 'not earned yet' };
// The extended statistics of a round (core pilotStats), as mgstat lines the plugin stores per pilot and mode without knowing their names
// (docs/SERVER_CONTRACT.md section 2b; slime-mg-gm docs/stats.md). Names are [a-z0-9_], at most 32. No name ends in `_wins` or starts
// with `wins_` except mech_wins: those also mark the round as won on the server.
function srvRoundStats(slot, won) {
  const t = game.pilotStats(slot); if (!t) return;
  const S = (k, n) => ifrStatLater(slot, k, Math.round(n));
  S('mech_shots', t.shots); S('mech_hits', t.hits); S('mech_qb', t.qb); S('mech_msl_fired', t.mslFired); S('mech_msl_dodged', t.dodges);
  S('mech_staggers', t.staggers); S('mech_overdrives', t.od); S('mech_crates', t.crates); S('mech_flag_returns', t.flagReturns);
  S('mech_dmg_taken', t.dmgTaken / 1000);
  S('best_round_damage', t.damage); S('best_round_kills', t.kills); S('best_life_s', t.lifeBest);
  const mode = String(t.mode || '').replace(/[^a-z0-9]/g, '');
  if (mode) { S('mech_' + mode + '_rounds', 1); if (won) S('mech_won_' + mode, 1); }
  const fk = String(t.frame || '').toLowerCase().replace(/[^a-z0-9]/g, '').slice(0, 12);
  if (fk) { S('mech_f_' + fk + '_rounds', 1); S('mech_f_' + fk + '_kills', t.kills); if (won) S('mech_f_' + fk + '_won', 1); }
  for (const k in t.weapons) {
    const wk = String(k).toLowerCase().replace(/[^a-z0-9]/g, '').slice(0, 14); if (!wk) continue;
    S('mech_w_' + wk + '_kills', t.weapons[k].kills); S('mech_w_' + wk + '_dmg', t.weapons[k].damage / 1000);
  }
}
// the round summary for every human: mgstat lines + the ifr_srv round op
function srvRoundEnd(winner, arena) {
  if (!serverMode) return;
  for (const pe of people.values()) {
    if (!pe.human || !(pe.team === TEAM_T || pe.team === TEAM_CT)) continue;
    if (arena !== undefined && game.arenaIndexOf(pe.slot) !== arena) continue;
    const s = guard('summary', () => game.pilotSummary(pe.slot));
    if (!s) continue;
    const won = s.won !== undefined ? !!s.won : winner === pe.team;
    ifrStat(pe.slot, 'mech_rounds', 1);
    if (s.xp) ifrStat(pe.slot, 'mech_xp', s.xp);
    if (s.credits) ifrStat(pe.slot, 'mech_credits', s.credits);
    if (s.assists) ifrStat(pe.slot, 'mech_assists', s.assists);
    if (s.captures) ifrStat(pe.slot, 'mech_captures', s.captures);
    if (s.damage) ifrStat(pe.slot, 'mech_damage', Math.round(s.damage / 1000));
    if (s.pveKills) ifrStat(pe.slot, 'mech_pve_kills', s.pveKills);
    if (s.bossKills) ifrStat(pe.slot, 'mech_boss_kills', s.bossKills);
    if (s.streakBest) ifrStat(pe.slot, 'best_streak', s.streakBest);
    if (won) ifrStat(pe.slot, 'mech_wins', 1);
    srvSend(pe.slot, 'round', [game.matchFor(pe.slot).mode, pe.team, won ? 1 : 0, s.kills || 0, s.deaths || 0, s.assists || 0, s.xp || 0, s.credits || 0]);
    guard('round stats', () => srvRoundStats(pe.slot, won));
  }
}
