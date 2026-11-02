// ---------------------------------------------------------------- players, maps and the 1.6 round on each map

class PlayerRec {
  constructor(slot) {
    this.slot = slot;
    this.team = 0; this.map = null; this.want = null;
    this.cls = null; this.clsTeam = 0;
    this.hudMode = CONFIG.HUD_MODE;
    this.pawn = undefined; this.alive = false;
    this.health = 100; this.armor = 0; this.helmet = false; this.weapon = null; this.money = 0;
    this.inBuy = false; this.inSite = false; this.hasC4 = false; this.hasDefuser = false;
    this.pos = null; this.vz = 0;
    this.menu = null; this.capture = false;
    this.msg = ''; this.msgUntil = 0; this.top = ''; this.topUntil = 0;
    this.hpHot = 0; this.apHot = 0; this.moneyHot = 0; this.delta = 0; this.deltaUntil = 0;
    this.flashes = 0; this.ammoFix = []; this.bought = []; this.lastBuys = [];
    this.placeUntil = 0; this.placePos = null; this.spawnFixAt = 0; this.cs2Buy = false; this.teamCheckAt = 0; this.fresh = false; this.survived = false;
    this.helpShown = false; this.helpPending = false; this.moneyKnown = false; this.botBuyAt = 0;
  }
}
const recs = new Map();          // slot -> PlayerRec
function recOf(slot) {
  if (slot === undefined || slot === null || slot < 0) return undefined;
  let r = recs.get(slot);
  if (!r) { r = new PlayerRec(slot); recs.set(slot, r); }
  return r;
}

// ---------------------------------------------------------------- which maps run, who plays where
let mapSet = [];                 // the maps in play (kept between rounds)
let roundsOnSet = 0;
let needPlan = true;
const round = {
  id: 0, live: false, frozen: true, freezeEnd: null, ended: false,
  maps: new Map(), plan: new Map(), spawnCount: new Map(), recent: [],
  c4Due: 0, firstDecided: null, startedAt: 0, emptySince: null,
};
const lossBonus = new Map();     // map key -> LossBonus (the losing streak bonus, kept per map as 1.6 kept it per server)
const pendingPay = new Map();    // slot -> round-end money, paid when the next round starts (as 1.6 did)

function teamPlayers() {
  const out = [];
  for (const rec of recs.values()) {
    const c = controllerOf(rec.slot);
    if (!c || !c.IsConnected()) continue;
    const team = c.GetTeamNumber();       // (the controller's team now: autobalance moves people just before a round)
    if (team !== rec.team) { rec.team = team; rec.map = null; }
    if (team !== TEAM_T && team !== TEAM_CT) continue;
    out.push(rec);
  }
  return out;
}

function chooseMaps(k) {
  const order = CONFIG.MAP_ORDER.filter((key) => MAP_BY_KEY[key]);
  if (!order.length) return [];
  k = Math.min(k, order.length);
  let due = CONFIG.ROUNDS_PER_MAP > 0 && roundsOnSet >= CONFIG.ROUNDS_PER_MAP;
  if (due && k >= order.length && mapSet.length === k) { roundsOnSet = 0; due = false; }   // every map runs: nothing to rotate
  if (mapSet.length === k && !due) return mapSet;
  const votes = {};
  for (const rec of recs.values()) if (rec.want && (rec.team === TEAM_T || rec.team === TEAM_CT)) votes[rec.want] = (votes[rec.want] || 0) + 1;
  // the rotation goes on from the last map played; maps just played go to the back when it is time to move on
  const start = mapSet.length ? (order.indexOf(mapSet[mapSet.length - 1]) + 1) % order.length : 0;
  let cand = order.map((_, i) => order[(start + i) % order.length]);
  if (due) cand = cand.filter((m) => !mapSet.includes(m)).concat(cand.filter((m) => mapSet.includes(m)));
  else cand = mapSet.filter((m) => cand.includes(m)).concat(cand.filter((m) => !mapSet.includes(m)));   // keep what runs
  cand = cand.map((m, i) => ({ m, i, v: votes[m] || 0 })).sort((a, b) => (due ? b.v - a.v : 0) || a.i - b.i).map((x) => x.m);
  const next = cand.slice(0, k);
  if (next.slice().sort().join() !== mapSet.slice().sort().join()) {
    roundsOnSet = 0;
    const names = next.map((m) => MAP_BY_KEY[m].title).join(' + ');
    log('maps: ' + names);
    if (mapSet.length && !isWarmup()) sayAll('Now playing: ' + names);
  }
  mapSet = next;
  return mapSet;
}

function makePlan() {
  needPlan = false;
  const players = teamPlayers();
  const nT = players.filter((r) => r.team === TEAM_T).length, nCT = players.length - nT;
  const keys = chooseMaps(mapCountFor(nT, nCT, CONFIG));
  const plan = assignMaps(players.map((r) => ({ slot: r.slot, team: r.team, prev: r.map, want: r.want })), keys);
  round.plan = new Map();
  round.maps = new Map();
  const counts = new Map();
  for (const r of players) {
    const m = plan.get(r.slot) || null;
    round.plan.set(r.slot, { map: m, team: r.team });
    r.map = m;
    if (m) counts.set(m + ':' + r.team, (counts.get(m + ':' + r.team) || 0) + 1);
  }
  for (const key of keys) {
    const mr = new MapRound(key);
    mr.start(counts.get(key + ':' + TEAM_T) || 0, counts.get(key + ':' + TEAM_CT) || 0);
    round.maps.set(key, mr);
    if (!lossBonus.has(key)) lossBonus.set(key, new LossBonus());
  }
  round.spawnCount = new Map();
  round.recent = [];
  dlog(`plan: ${nT} T, ${nCT} CT on ${keys.join(', ')}`);
}

// the map for a player who isn't in this round's plan (joined late, changed team, warmup respawn)
function mapForLate(rec) {
  const p = round.plan.get(rec.slot);
  if (p && p.team === rec.team && p.map && round.maps.has(p.map)) return p.map;
  let keys = [...round.maps.keys()];
  if (!keys.length || isWarmup()) {
    // warmup (no round yet): the maps the first round will use for this many players
    const ps = teamPlayers();
    const nT = ps.filter((r) => r.team === TEAM_T).length;
    keys = chooseMaps(mapCountFor(nT, ps.length - nT, CONFIG)).slice();
    if (!keys.length) return null;
  }
  if (rec.want && keys.includes(rec.want)) return rec.want;
  if (rec.map && keys.includes(rec.map)) return rec.map;
  const counts = new Map();
  for (const r of recs.values()) if (r.map && r.alive) counts.set(r.map + ':' + r.team, (counts.get(r.map + ':' + r.team) || 0) + 1);
  return lateMap(rec.team, keys, counts);
}

// ---------------------------------------------------------------- spawning
function spawnPoint(rec, fresh) {
  const m = MAP_BY_KEY[rec.map];
  const list = m.spawns[rec.team === TEAM_T ? 'T' : 'CT'];
  const key = rec.map + ':' + rec.team;
  const t = now();
  if (fresh) {
    const n = round.spawnCount.get(key) || 0;
    round.spawnCount.set(key, n + 1);
    if (n < list.length) return list[n];
  }
  // a spawn nobody stands on (or was just put on)
  round.recent = round.recent.filter((r) => t - r.t < 3);
  const busy = round.recent.map((r) => r.p);
  for (const r of recs.values()) if (r.alive && r.pos && r !== rec) busy.push([r.pos.x, r.pos.y, r.pos.z]);
  const start = Math.floor(Math.random() * list.length);
  for (let i = 0; i < list.length; i++) {
    const sp = list[(start + i) % list.length];
    if (busy.every((b) => Math.abs(b[0] - sp[0]) > 40 || Math.abs(b[1] - sp[1]) > 40 || Math.abs(b[2] - sp[2]) > 80)) return sp;
  }
  return list[start];
}

function place(rec, pawn) {
  const sp = rec.placePos;
  if (!sp) return;
  pawn.Teleport({ position: { x: sp[0], y: sp[1], z: sp[2] + 1 }, angles: { pitch: 0, yaw: sp[3], roll: 0 }, velocity: { x: 0, y: 0, z: 0 } });
  guard('eyes', () => pawn.SetEyeAngles({ pitch: 0, yaw: sp[3], roll: 0 }));
}

function onReset(pawn) {
  const s = slotOf(pawn);
  const rec = recOf(s);
  if (!rec) return;
  const c = controllerOf(s);
  const team = c ? c.GetTeamNumber() : pawn.GetTeamNumber();
  if (team !== rec.team) { rec.team = team; rec.map = null; }
  if (team !== TEAM_T && team !== TEAM_CT) { rec.alive = false; return; }
  rec.pawn = pawn;
  // (a team change resets a dead player too: nothing to place until they spawn)
  if (!pawn.IsAlive()) { rec.alive = false; closeMenu(rec); return; }
  rec.alive = true;
  rec.vz = 0;
  guard('name', () => pawn.SetEntityName(pawnName(s)));
  if (needPlan && !isWarmup()) makePlan();
  const planned = round.plan.get(s);
  const fresh = !!planned && planned.team === team && !!planned.map && round.live === false;
  rec.map = planned && planned.team === team && planned.map ? planned.map : mapForLate(rec);
  if (!rec.map) return;
  rec.placePos = spawnPoint(rec, fresh || (planned && planned.team === team && round.freezeEnd === null));
  round.recent.push({ t: now(), p: rec.placePos });
  rec.placeUntil = now() + 0.6;
  place(rec, pawn);
  // a player who didn't live through last round starts like a 1.6 spawn: pistol + 2 magazines, no armour
  rec.fresh = !rec.survived;
  rec.survived = false;
  rec.flashes = rec.fresh ? 0 : rec.flashes;
  rec.spawnFixAt = now() + 0.1;
  if (c && c.IsBot() && CONFIG.BOT_BUY) rec.botBuyAt = now() + 0.4 + Math.random() * 0.8;
  rec.health = pawn.GetHealth();
  rec.hpHot = rec.apHot = 0;
  rec.hasC4 = false;
  rec.hasDefuser = guard('defuser', () => team === TEAM_CT && pawn.HasDefuser()) || false;
  closeMenu(rec);
  applyModel(rec, pawn);
  const m = MAP_BY_KEY[rec.map];
  topLine(rec, m.title.toUpperCase(), 6);
  if (CONFIG.CLASS_MENU && (!rec.cls || rec.clsTeam !== team) && !(c && c.IsBot())) openMenu(rec, 'class');
  else if (c && c.IsBot() && (!rec.cls || rec.clsTeam !== team)) chooseClass(rec, null);
  if (!rec.helpShown && !(c && c.IsBot())) {
    rec.helpShown = true;
    if (rec.menu) rec.helpPending = true; else message(rec, CONFIG.HELP_LINE, 8);
  }
}

// a living pawn the script lost track of (missed reset): keep it where it is, on the map it stands on
function adoptPawn(rec, pawn) {
  rec.pawn = pawn;
  rec.alive = true;
  guard('name', () => pawn.SetEntityName(pawnName(rec.slot)));
  const p = pawn.GetAbsOrigin();
  rec.pos = p;
  rec.map = mapAt(p) || rec.map || mapForLate(rec);
  dlog(`slot ${rec.slot} picked up alive on ${rec.map}`);
}

// a moment after spawning: the 1.6 starting pistol (USP for CTs) with 1.6 spare ammo
function spawnFix(rec, pawn) {
  rec.spawnFixAt = 0;
  if (CONFIG.SWAP_P2000_FOR_USP && rec.team === TEAM_CT) {
    const p2k = pawn.FindWeapon('weapon_hkp2000');
    if (p2k && !pawn.FindWeapon('weapon_usp_silencer')) {
      let isP2k = true;
      try { isP2k = p2k.GetData().GetName() === 'weapon_hkp2000'; } catch (err) { /* ignore */ }
      if (isP2k) { pawn.DestroyWeapon(p2k); pawn.GiveNamedItem('weapon_usp_silencer', false); }
    }
  }
  if (!rec.fresh) return;
  for (const id of ['glock18', 'usp']) {
    const W = WEAPONS[id];
    const w = pawn.FindWeapon(W.cls) || (id === 'usp' ? pawn.FindWeapon('weapon_hkp2000') : undefined);
    if (w) rec.ammoFix.push({ cls: W.cls, reserve: W.clip * (W.spawnMags || 0), until: now() + 1 });
  }
  // CS2 can start players with armour (game mode settings); 1.6 never does
  if (CONFIG.NO_SPAWN_ARMOR && pawn.GetArmor() > 0) { pawn.SetArmor(0); pawn.SetHasHelmet(false); }
}

// CS2 bots can't use the 1.6 buy menu: they buy here, a moment after spawning, roughly like 1.6 bots did
function botBuy(rec) {
  rec.botBuyAt = 0;
  const c = controllerOf(rec.slot);
  if (!c || !c.IsBot() || !rec.alive || !rec.map || !rec.placePos) return;
  rec.inBuy = true;                       // (they stand on their spawn)
  rec.money = c.GetMoneySpendableNow();
  const T = rec.team === TEAM_T;
  const m = rec.money;
  // gun, its ammo, then armour (1.6 bots bought ammo too)
  const list = [];
  if (m >= 6000 && Math.random() < 0.2) list.push('awp', 'ammo_primary', 'vesthelm');
  else if (m >= (T ? 3800 : 4400)) list.push(T ? 'ak47' : 'm4a1', 'ammo_primary', 'vesthelm');
  else if (m >= (T ? 2900 : 3150)) list.push(T ? 'galil' : 'famas', 'ammo_primary', 'kevlar');
  else if (m >= 2300) list.push('mp5navy', 'ammo_primary', 'kevlar');
  else if (m >= 1400 && Math.random() < 0.5) list.push('deagle', 'ammo_secondary', 'kevlar');
  else if (m >= 650) list.push('kevlar');
  list.push('ammo_secondary');
  if (!T) list.push('defuser');
  list.push('hegrenade', 'flashbang');
  for (const it of list) buy(rec, it, true);
}

// ---------------------------------------------------------------- the round
function timerLeft(t) {
  if (isWarmup() || !round.live) return null;
  if (round.frozen || round.freezeEnd === null) return CONFIG.ROUND_TIME;
  return round.timeLeft;
}

function onRoundStart() {
  const warm = isWarmup();
  // a new match (warmup over, mp_restartgame): CS2 resets money and weapons, so 1.6's carry-overs go too
  if (!warm && guard('rounds', () => Instance.GetRoundsPlayed()) === 0) {
    pendingPay.clear();
    lossBonus.clear();
    for (const rec of recs.values()) { rec.survived = false; rec.lastBuys = []; }
  }
  if (needPlan && !warm) {
    // planned only now (the resets came first, or during warmup): put everyone on their planned map
    makePlan();
    for (const rec of recs.values()) {
      const pawn = rec.alive ? live(rec.pawn) : undefined;
      if (!pawn || !rec.map) continue;
      rec.placePos = spawnPoint(rec, true);
      rec.placeUntil = now() + 0.6;
      place(rec, pawn);
      topLine(rec, MAP_BY_KEY[rec.map].title.toUpperCase(), 6);
    }
  }
  round.id++;
  round.live = !warm;
  round.ended = false;
  round.frozen = isFrozen();
  round.freezeEnd = round.frozen ? null : now();
  round.c4Due = now() + 0.5;
  round.firstDecided = null;
  round.startedAt = now();
  round.timeLeft = CONFIG.ROUND_TIME;
  round.emptySince = null;
  if (!round.frozen && !warm) onFreezeEnd();
  // last round's money (1.6 paid the round bonus when the next round started)
  for (const [slot, amount] of pendingPay) {
    const rec = recs.get(slot), c = controllerOf(slot);
    if (!rec || !c || !amount) continue;
    const have = c.GetMoneySpendableNow();
    const add = Math.min(amount, CONFIG.MAX_MONEY - have);
    if (add > 0) { c.AddMoneySpendableNow(add); rec.money = have + add; showDelta(rec, add); }
  }
  pendingPay.clear();
}

function onFreezeEnd() {
  round.frozen = false;
  round.freezeEnd = now();
  round.lastClock = now();
  if (isWarmup()) return;
  if (CONFIG.SET_ROUND_TIME) guard('roundtime', () => Instance.SetRoundRemainingTime(CONFIG.ROUND_TIME));
  round.timeLeft = CONFIG.ROUND_TIME;
  // the 1.6 round start radio: one random line per team on each map
  for (const key of round.maps.keys()) {
    for (const team of [TEAM_T, TEAM_CT]) {
      const list = [...recs.values()].filter((r) => r.map === key && r.team === team && r.alive);
      if (list.length) playToMany(list, pick(['moveout', 'letsgo', 'locknload', 'com_go']));
    }
  }
}

function onRoundEnd() {
  round.live = false;
  round.ended = true;
  needPlan = true;
  round.endSent = 0;
  if (!isWarmup()) roundsOnSet++;
  for (const rec of recs.values()) {
    rec.survived = rec.alive;
    if (rec.bought.length) rec.lastBuys = rec.bought;
    rec.bought = [];
    if (rec.menu && rec.menu.kind === 'buy') closeMenu(rec);
  }
}

// one map's result: money for its players (paid next round), the 1.6 centre text and radio line
function mapDecided(key) {
  const mr = round.maps.get(key);
  if (!mr || !mr.result) return;
  const res = mr.result;
  const players = [...recs.values()].filter((r) => r.map === key && (r.team === TEAM_T || r.team === TEAM_CT));
  if (CONFIG.ROUND_MONEY) {
    const pay = teamRewards(res);
    if (!lossBonus.has(key)) lossBonus.set(key, new LossBonus());
    const bonus = lossBonus.get(key).apply(res.winner);
    if (res.winner) pay[otherTeam(res.winner)] += bonus;
    for (const r of players) pendingPay.set(r.slot, (pendingPay.get(r.slot) || 0) + (pay[r.team] || 0));
  }
  const rt = resultText(res);
  for (const r of players) message(r, rt.text, 6);
  playToMany(players, rt.sound);
  const m = MAP_BY_KEY[key];
  log(`${m.title}: ${rt.text}`);
  if (round.maps.size > 1) sayAll(`${m.title}: ${rt.text}`);
  if (round.firstDecided === null) {
    round.firstDecided = now();
    // the other maps get at most FINISH_GRACE seconds more (planted bombs still play out)
    const open = [...round.maps.values()].some((x) => x.active && !x.result);
    if (open && CONFIG.FINISH_GRACE > 0 && round.timeLeft > CONFIG.FINISH_GRACE) {
      round.timeLeft = CONFIG.FINISH_GRACE;
      if (CONFIG.SET_ROUND_TIME) guard('roundtime', () => Instance.SetRoundRemainingTime(CONFIG.FINISH_GRACE));
    }
  }
}

function endRound(res) {
  if (round.ended) return;
  round.ended = true;
  // several maps: everyone sees how the round went overall
  if (round.maps.size > 1 && res.reason === 'maps' || res.reason === 'draw' && round.maps.size > 1) {
    let t = 0, ct = 0;
    for (const mr of round.maps.values()) if (mr.result) { if (mr.result.winner === TEAM_T) t++; else if (mr.result.winner === TEAM_CT) ct++; }
    const text = (res.winner === TEAM_T ? 'Terrorists win the round' : res.winner === TEAM_CT ? 'Counter-Terrorists win the round' : 'Round Draw') + `  (maps ${t} - ${ct})`;
    for (const r of recs.values()) if (r.team === TEAM_T || r.team === TEAM_CT) topLine(r, text, 6);
  }
  log(`round over: ${res.winner === TEAM_T ? 'Terrorists' : res.winner === TEAM_CT ? 'Counter-Terrorists' : 'nobody'} (${res.reason})`);
  round.endRes = res;
  round.endTries = 0;
  sendWin();
}
// FireWinCondition with the round's result. Wins use 9 / 8 (Terrorists / CTs win, the same in every numbering CS2 might
// use); a draw tries CONFIG.DRAW_REASONS in turn. If CS2 hasn't ended the round 3 seconds later, the next value is tried.
function sendWin() {
  const res = round.endRes;
  const list = res.winner === TEAM_T ? [9] : res.winner === TEAM_CT ? [8] : CONFIG.DRAW_REASONS;
  const reason = CONFIG.EXACT_END_REASONS && res.winner ? endReasonFor(res) : list[Math.min(round.endTries, list.length - 1)];
  round.endTries++;
  round.endSent = now();
  if (live(Instance.FindEntityByName(CONFIG.MAP_PARAMS))) {
    dlog(`FireWinCondition ${reason}`);
    guard('wincond', () => Instance.EntFireAtName({ name: CONFIG.MAP_PARAMS, input: 'FireWinCondition', value: reason }));
  } else warnOnce('nomapparams', 'no ' + CONFIG.MAP_PARAMS + ' entity: the script cannot end rounds');
}

function roundThink(t) {
  if (isWarmup() || !round.live) return;
  if (round.ended) {
    // CS2 didn't take the result yet: try again
    if (round.endSent && t - round.endSent > 3 && round.endTries < 4) { warnOnce('winretry', 'FireWinCondition did not end the round; trying again'); sendWin(); }
    return;
  }
  // C4 for one random terrorist on each map, once everyone has spawned
  if (round.c4Due && t >= round.c4Due) { round.c4Due = 0; giveBombs(); }
  if (round.frozen) {
    if (!isFrozen()) onFreezeEnd();
    else return;
  }
  // the clock: CS2's round clock when it is set from here, otherwise our own count
  let left = round.timeLeft - (t - (round.lastClock || t));
  round.lastClock = t;
  if (CONFIG.SET_ROUND_TIME) { const cs = guard('clock', () => Instance.GetRoundRemainingTime()); if (typeof cs === 'number') left = Math.min(left, cs + 0.05); }
  round.timeLeft = Math.max(0, left);
  const timeUp = round.timeLeft <= 0;
  // bombs that should have gone off (if CS2's explode event was missed)
  for (const mr of round.maps.values()) if (mr.bomb && !mr.bomb.exploded && !mr.bomb.defused && t > mr.bomb.explodes + 3) { if (mr.explode()) mapDecided(mr.key); }
  // who is still alive on each map
  const alive = new Map();
  for (const r of recs.values()) if (r.alive && r.map) alive.set(r.map + ':' + r.team, (alive.get(r.map + ':' + r.team) || 0) + 1);
  let anyActive = false;
  for (const mr of round.maps.values()) {
    if (!mr.active) continue;
    anyActive = true;
    if (mr.check(alive.get(mr.key + ':' + TEAM_T) || 0, alive.get(mr.key + ':' + TEAM_CT) || 0, timeUp)) mapDecided(mr.key);
  }
  if (anyActive) {
    if ([...round.maps.values()].every((x) => !x.active || x.result)) endRound(overallResult([...round.maps.values()]));
    return;
  }
  // nothing to play (only one team has players): end at the clock; restart as soon as both teams have someone
  let t2 = 0, ct2 = 0;
  for (const r of recs.values()) if (r.alive) { if (r.team === TEAM_T) t2++; else if (r.team === TEAM_CT) ct2++; }
  if (t2 && ct2) {
    if (round.emptySince === null) round.emptySince = t;
    if (t - round.emptySince > 2) endRound({ winner: 0, reason: 'draw' });
  } else round.emptySince = null;
  if (timeUp) endRound({ winner: 0, reason: 'draw' });
}

function giveBombs() {
  if (!CONFIG.GIVE_C4) return;
  for (const mr of round.maps.values()) {
    if (!mr.active) continue;
    const ts = [...recs.values()].filter((r) => r.map === mr.key && r.team === TEAM_T && r.alive && live(r.pawn));
    if (!ts.length || ts.some((r) => guard('c4', () => !!r.pawn.GetC4()))) continue;
    const r = pick(ts);
    guard('givec4', () => r.pawn.GiveNamedItem('weapon_c4', false));
    r.hasC4 = true;
    dlog(`C4 on ${mr.key} -> slot ${r.slot}`);
  }
}

// ---------------------------------------------------------------- bomb events
function bombMap(c4) { const p = guard('c4pos', () => c4.GetAbsOrigin()); return p ? mapAt(p) : undefined; }

function onBombPlant(ev) {
  const c4 = ev.plantedC4;
  const key = bombMap(c4);
  const mr = key ? round.maps.get(key) : undefined;
  if (!mr) return;
  const site = guard('site', () => (c4.IsBombsiteA() ? 'A' : 'B')) || '?';
  let explodes = now() + CONFIG.C4_TIMER;
  const et = guard('c4time', () => c4.GetExplodeTime());
  if (typeof et === 'number' && et > now()) explodes = et;
  mr.plant(site, now(), explodes - now());
  const players = [...recs.values()].filter((r) => r.map === key);
  for (const r of players) message(r, 'The bomb has been planted!', 4);
  playToMany(players, 'bombpl');
  for (const r of players) r.hasC4 = false;
}
function onBombDefuse(ev) {
  const key = bombMap(ev.plantedC4);
  const mr = key ? round.maps.get(key) : undefined;
  if (mr && mr.defuse()) mapDecided(key);
}
function onBombExplode(ev) {
  const key = bombMap(ev.plantedC4);
  const mr = key ? round.maps.get(key) : undefined;
  if (mr && mr.explode()) mapDecided(key);
  else if (mr && mr.bomb) mr.bomb.exploded = true;
}

// ---------------------------------------------------------------- kills (1.6: +300 for an enemy, -3300 for a teammate)
function onKill(ev) {
  const vs = slotOf(ev.player);
  const vrec = recs.get(vs);
  if (vrec) { vrec.alive = false; vrec.survived = false; vrec.hasC4 = false; closeMenu(vrec); }
  if (!CONFIG.KILL_MONEY || isWarmup() || !round.live) return;
  const att = ev.attacker;
  if (!isPawn(att)) return;
  const as = slotOf(att);
  if (as === undefined || as === vs) return;
  const arec = recs.get(as), c = controllerOf(as);
  if (!arec || !c || !vrec) return;
  const amount = arec.team === vrec.team ? REWARD.TEAMKILL : REWARD.KILL;
  const have = c.GetMoneySpendableNow();
  const add = amount > 0 ? Math.min(amount, CONFIG.MAX_MONEY - have) : Math.max(amount, -have);
  if (add) { c.AddMoneySpendableNow(add); arec.money = have + add; showDelta(arec, add); }
}

function onTeamChanged(pawnOrCtrl) {
  const s = slotOf(pawnOrCtrl);
  const rec = recOf(s);
  if (!rec) return;
  const pawn = pawnOf(s);
  // (CS2 may reset a living pawn first and report the team change after: keep that player)
  if (pawn && pawn.IsAlive() && pawn === rec.pawn && rec.alive) return;
  rec.alive = false;
  rec.map = null;
  closeMenu(rec);
}
