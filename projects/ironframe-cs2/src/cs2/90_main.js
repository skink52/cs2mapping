// ===================================================================================================================
// IRONFRAME CS2 adapter, part 9: the main loop, rounds and CS2 hooks.
// init finds the map's entities and builds the core game; think runs once a server tick: people, input, game.tick,
// events -> damage/kills/effects/HUD, drawing, cameras, perf. Rounds are the core's (mp_ignore_round_win_conditions 1);
// the adapter shows the podium, then fires FireWinCondition; if CS2 never ends the round, the next one starts anyway, and if
// CS2 ends it but never starts the next one (a match end, a plugin) the script starts it after RESTART_WAIT (Nov 2026 playtest:
// stuck on the round-won screen).
// ===================================================================================================================
let game = null;
let ready = false, phase = 'lobby';        // lobby | running | podium
let restartAskedAt = 0, podiumAt = 0, roundEndSeen = false, roundEndSeenAt = 0, roundEndWaitAt = 0, lastTime = 0, roundNo = 0;
let perfText = '';
let initAt = 0, navProbing = false;
const stagMark = new Map();   // victim slot -> tick of its stagger event (the damage event follows in the same tick)
const dmgFrom = new Map();   // slot -> {pos, until}: who hit this human last (damage direction arrow)
const DT = 1 / 64;
const missing = [];
const traceStats = { line: 0, sphere: 0, clip: 0 };
let introSlateShown = new Set();

// the world the core asks about: CS2 traces (mech hits come from the core's own spheres; players are ignored)
const world = {
  traceLine(a, b) {
    traceStats.line++;
    const tr = Instance.TraceLine({ start: a, end: b, ignorePlayers: true });
    return { hit: !!tr.didHit, pos: tr.end, normal: tr.normal, frac: tr.fraction, mech: -1 };
  },
  traceSphere(a, b, r) {
    traceStats.sphere++;
    const tr = Instance.TraceSphere({ start: a, end: b, radius: r, ignorePlayers: true });
    return { hit: !!tr.didHit, solid: !!tr.startedInSolid, pos: tr.end, normal: tr.normal, frac: tr.fraction, mech: -1 };
  },
  // player clips (core IF_clipStep): only a player-hull trace collides with clip brushes. Any pawn sets the hull (the mech's own pilot or
  // CS2 bot first, else any live pawn: the script's AI mechs have none); a hit on a pawn (another mech's rider) is not a clip
  traceClip(a, b, slot) {
    if (clipTraceOff) return null;
    const pawn = clipPawn(slot); if (!pawn) return null;
    traceStats.clip++;
    let tr;
    try { tr = Instance.TracePlayer({ start: a, end: b, player: pawn, isDucked: false }); }
    catch (err) { clipTraceOff = true; log('WARNING: Instance.TracePlayer failed (' + err + '): mechs ignore player clips'); return null; }
    if (!tr) return null;
    if (tr.didHit && tr.hitEntity && tr.hitEntity instanceof CSPlayerPawn) return null;
    return { hit: !!tr.didHit, solid: !!tr.startedInSolid, pos: tr.end, normal: tr.normal, frac: tr.fraction };
  },
  now() { return gameTime(); },
};
let clipTraceOff = false, clipAnyPawn, clipAnyAt = -1;
function clipPawn(slot) {
  const pe = person(slot), own = pe ? live(pe.pawn) : undefined;
  if (own && own.IsAlive()) return own;
  if (clipAnyAt !== ifrTickNo >> 6 || !live(clipAnyPawn) || !clipAnyPawn.IsAlive()) {
    clipAnyAt = ifrTickNo >> 6; clipAnyPawn = undefined;
    for (const q of people.values()) { const p = live(q.pawn); if (p && p.IsAlive()) { clipAnyPawn = p; break; } }
  }
  return clipAnyPawn;
}
// the sky shell's height over each arena copy (Dunes: 6 143 against the 5 000 arena ceiling): traces straight up at five points, the
// highest hit; projectiles and missiles cruise under it and vanish there without a blast (core IF_capZ / IF_atSky)
function measureSky() {
  for (const A of game.list) {
    const b = A.arena.bounds, cx = (b.min[0] + b.max[0]) / 2, cy = (b.min[1] + b.max[1]) / 2, qx = (b.max[0] - b.min[0]) / 4, qy = (b.max[1] - b.min[1]) / 4;
    let sky = -Infinity;
    for (const [x, y] of [[cx, cy], [cx - qx, cy - qy], [cx + qx, cy - qy], [cx - qx, cy + qy], [cx + qx, cy + qy]]) {
      const tr = guard('sky trace', () => Instance.TraceLine({ start: v3(x, y, b.max[2] - 50), end: v3(x, y, b.max[2] + 30000), ignorePlayers: true }));
      if (tr && tr.didHit && !tr.startedInSolid && tr.end && Number.isFinite(tr.end.z) && tr.end.z > sky) sky = tr.end.z;
    }
    if (Number.isFinite(sky)) A.g.skyZ = sky;
    log('arena ' + (A.k + 1) + ': sky ' + (Number.isFinite(sky) ? Math.round(sky) : 'not found (default ' + Math.round(b.max[2] + 1000) + ')') + ', arena ceiling ' + Math.round(b.max[2]));
  }
}

// CS2 re-creates every map entity at a round restart: cached handles (sounds, particles, mailboxes, HUD, booth, template) must be looked up again
function rebind() {
  for (const pe of people.values()) guard('preview drop', () => garagePreviewDrop(pe.slot));
  bayPool = null;
  for (const pe of people.values()) if (pe.garage && pe.garage.open) guard('rebay', () => { pe.garage.bay = garageBay(pe.slot); });
  renderReset(); boothEnt = undefined; boothOrigin = undefined;
  const fx = fxInit(); srvFindMail();
  if (typeof ifrHudInit === 'function') guard('hud init', () => ifrHudInit());
  for (const pe of people.values()) { pe.cam = undefined; pe.camKind = ''; pe.camSent = null; pe.hudReset = true; }
  dlog('rebound: particles ' + fx.pfx + ', sounds ' + fx.snd);
}
function hudOff(slot) { if (typeof ifrHudOff === 'function') guard('hudoff', () => ifrHudOff(slot)); else if (typeof ifrHudReset === 'function') guard('hudoff', () => ifrHudReset(slot)); }

function init() {
  ready = false;
  const found = (name) => { const e = ifrFind(name); if (!e) missing.push(name); return e; };
  missing.length = 0;
  found(CONFIG.PROP_TEMPLATE); found(CONFIG.BOOTH); found(CONFIG.MAP_PARAMS); found(CONFIG.HUD);
  // every model the script may SetModel to is precached (experimental API; the map's cache room is the reliable path,
  // tools/patch_cache.py adds missing ones to a Hammer-saved map)
  guard('precache', () => {
    const res = [NULL_MODEL];
    for (const fr of Object.values(FRAMES)) { if (fr.legs) res.push(fr.legs); if (fr.upper) res.push(fr.upper); }
    for (const v of Object.values(WEAPON_MODELS)) if (typeof v === 'string') res.push(v);
    for (const v of Object.values(FX_MODELS)) if (typeof v === 'string') res.push(v);
    if (typeof Instance.Precache === 'function') { const pc = Instance.Precache({ resources: res }); dlog('precache ' + res.length + ' models ' + (pc ? 'requested' : 'refused')); }
  });
  renderReset();
  const fx = fxInit();
  if (typeof ifrHudInit === 'function') guard('hud init', () => ifrHudInit());
  const rng = ifrMakeRng(Math.floor(Instance.GetGameTime() * 1000) ^ 0x5eed);
  game = guard('core', () => new IfrArenas({ parts: PARTS, arena: ARENA, cfg: Object.assign({}, CONFIG.core), world, rng }));
  if (!game) { log('FATAL: the core did not start; nothing will run'); return; }
  srvInit();
  guard('sky', measureSky);
  ifrCvars(CONFIG.CVARS_ONCE); ifrCvars(CONFIG.CVARS_ALWAYS);
  people.clear(); scanPeople();
  phase = 'lobby'; roundEndSeen = false; roundEndWaitAt = 0; initAt = gameTime();
  game.probeStart(); navProbing = true;
  ready = true;
  log('v' + IFR_VERSION + ' ready: arena ' + (ARENA.name || ARENA.id) + ', ' + Object.keys(FRAMES).length + ' frame models, ' + Object.keys(WEAPON_MODELS).length + ' weapon models, particles ' + fx.pfx
    + ', sounds ' + fx.snd + ', HUD ' + (ifrFind(CONFIG.HUD) ? 'on' : 'MISSING') + ', prop template ' + (ifrFind(CONFIG.PROP_TEMPLATE) ? 'on' : 'MISSING')
    + ', mailboxes ' + mailEnts.filter((e) => !!e).length + '/64' + (missing.length ? ' | MISSING: ' + missing.join(', ') : ''));
}

// ---------------------------------------------------------------- rounds
function humansPlaying() { let n = 0; for (const pe of people.values()) if (pe.human && (pe.team === TEAM_T || pe.team === TEAM_CT)) n++; return n; }
function startRound() {
  if (!game) return;
  roundNo++;
  const humans = humansPlaying();
  const roster = []; for (const pe of people.values()) if (pe.human && (pe.team === TEAM_T || pe.team === TEAM_CT) && pe.status !== 'spec') roster.push({ slot: pe.slot, team: pe.team });
  const copies = game.planRound(roster);
  const mode = perfForce || guard('pickMode', () => game.pickMode(humans)) || 'tb';      // perfForce: the timing test (ifr_perf_64) wants Team Deathmatch
  guard('setMode', () => game.setMode(mode, humans));
  guard('startRound', () => { if (typeof game.startRound === 'function') game.startRound(gameTime()); });
  if (serverMode && humans >= 6 && typeof IF_balanceTeams === 'function') guard('balance', () => {
    const list = []; for (const pe of people.values()) if (pe.human && (pe.team === TEAM_T || pe.team === TEAM_CT)) list.push({ slot: pe.slot, rating: pe.pilot ? pe.pilot.rank : 1 });
    const b = IF_balanceTeams(list); let moved = 0;
    for (const t of [TEAM_T, TEAM_CT]) for (const slot of b[t]) { const pe = person(slot); if (pe && pe.team !== t) { const c = live(pe.ctrl); if (c) { c.JoinTeam(t); moved++; } } }
    if (moved) log('teams balanced by rank: ' + moved + ' moved');
  });
  phase = 'running'; roundEndSeen = false; roundEndSeenAt = 0; roundEndWaitAt = 0; restartAskedAt = 0;
  introSlateShown.clear();   // every round shows its intro slate (it also replaces the last round's podium on the HUD)
  music('music_battle');
  for (const pe of people.values()) {
    pe.hudReset = true;
    if (pe.team === TEAM_T || pe.team === TEAM_CT) {
      if (pe.human && pe.status !== 'spec') { pe.status = 'intro'; pe.joinedAt = gameTime(); }
      guard('addPlayer', () => game.addPlayer(pe.slot, { team: pe.team, human: pe.human, name: nameOf(pe.slot), pilot: pe.pilot }));
    }
  }
  log('round ' + roundNo + ': ' + humans + ' humans in ' + copies + ' arena' + (copies > 1 ? 's' : '') + ': ' + game.list.filter((a) => a.active).map((a) => (a.k + 1) + ' ' + a.g.match.mode + ' (' + a.humans + ')').join(', '));
}
function onCoreRoundEnd(ev) {
  if (phase !== 'running') return;
  const A = game.list[ev.arena || 0]; if (A) A.done = true;
  if (game.allDone()) { phase = 'podium'; podiumAt = gameTime() + CONFIG.PODIUM_SECONDS; }
  srvRoundEnd(ev.winner, ev.arena || 0);
  for (const pe of people.values()) {
    if (!pe.human || game.arenaIndexOf(pe.slot) !== (ev.arena || 0)) continue;
    garageClose(pe);
    const s = guard('summary', () => game.pilotSummary(pe.slot));
    if (typeof ifrHudSlate === 'function') guard('podium', () => ifrHudSlate(pe.slot, 'podium', { winner: ev.winner, podium: podiumCards(ev), me: s, team: pe.team }));
    sndTone(pe.slot, 'ui_podium');
  }
  log('round over: winner ' + ev.winner + ', podium ' + podiumCards(ev).map((c) => c.name + ' ' + c.kills).join(', '));
}
// the podium cards from the core's round_end (podiumInfo: the round's own scores, AI fill included); a pawn slot shows its CS2 name
function podiumCards(ev) {
  const info = ev.podiumInfo || (ev.podium || []).map((sl) => { const m = game.mechs.get(sl); return { slot: sl, name: m ? m.name : '', team: m ? m.team : 0, kills: m ? m.sum.kills : 0 }; });
  return info.map((c) => ({ slot: c.slot, name: c.slot < 64 && person(c.slot) ? nameOf(c.slot) : String(c.name || 'AI'), team: c.team, kills: c.kills | 0, score: c.score | 0 }));
}
function finishRound() {
  phase = 'lobby';
  const w = game.winner();
  const reason = w === TEAM_T ? CSRoundEndReason.TERRORISTS_WIN : w === TEAM_CT ? CSRoundEndReason.CTS_WIN : CSRoundEndReason.DRAW;
  ifrCvars(['mp_ignore_round_win_conditions 0']);
  guard('wincond', () => ifrFireName(CONFIG.MAP_PARAMS, 'FireWinCondition', reason));
  roundEndWaitAt = gameTime() + (GameRules.IsWarmupPeriod() ? 1 : CONFIG.ROUND_END_WAIT);   // warmup: CS2 ends no round, go on at once
  for (const pe of people.values()) { if (pe.status === 'mech') { pe.status = 'intro'; } garageClose(pe); }
  renderReset(); fxReset();
}
function cleanupRound(restart) {
  for (const pe of people.values()) { garageClose(pe); releaseCamera(pe); pe.status = pe.team === TEAM_T || pe.team === TEAM_CT ? 'intro' : 'none'; pe.camKind = ''; pe.camSent = null; }
  pendingKills.length = 0; awaitRespawn.clear();
  renderReset(); fxReset();
  if (restart && game) guard('reset core', () => game.reset && game.reset());
  phase = 'lobby';
}

// ---------------------------------------------------------------- per person, per tick
const inputScratch = new Map();   // slot -> reusable input struct
function inputFor(slot) { let i = inputScratch.get(slot); if (!i) { i = { mx: 0, my: 0, yaw: 0, pitch: 0, boost: false, qb: false, jump: false, fire: [false, false, false, false], cycle: false, any: false, camPos: null, camDir: null }; inputScratch.set(slot, i); } return i; }

function personTick(pe, now) {
  if (!(pe.team === TEAM_T || pe.team === TEAM_CT)) return;
  const pawn = pe.pawn = pawnOf(pe.slot);
  if (!pawn) return;
  if (pe.hudReset && pe.human) { pe.hudReset = false; if (typeof ifrHudReset === 'function') guard('hudreset', () => ifrHudReset(pe.slot)); }
  const m = game.mechs.get(pe.slot);
  // bots: the core drives them; the pawn still rides the mech so the kill credit is real
  if (!pe.human) {
    if (m && m.alive) { if (pe.status !== 'mech') { pe.status = 'mech'; mountPawn(pe, m.pos); } ridePawn(pe, m); }
    else if (pe.status !== 'parked') { pe.status = 'parked'; parkPawn(pe); if (m && !m.alive && phase === 'running') guard('bot spawn', () => game.requestSpawn(pe.slot)); }
    return;
  }
  // AFK: no input for AFK_SPEC seconds (not in the garage: menus are slow)
  if (pe.status === 'mech' && now - pe.lastInput > CONFIG.AFK_WARN && !pe.afkWarned) { pe.afkWarned = true; reply(pe.slot, 'Are you there? You will be moved to spectators in ' + Math.round(CONFIG.AFK_SPEC - CONFIG.AFK_WARN) + ' s', 5); }
  if (pe.status === 'mech' && now - pe.lastInput > CONFIG.AFK_SPEC) { spectate(pe, 'AFK: moved to spectators. !back to return'); }
  switch (pe.status) {
    case 'intro': {
      if (pe.status !== 'parked') parkPawn(pe);
      if (phase === 'running' && !introSlateShown.has(pe.slot) && typeof ifrHudSlate === 'function') { introSlateShown.add(pe.slot); guard('intro', () => ifrHudSlate(pe.slot, 'intro', { title: ARENA.title || 'IRONFRAME', arena: (ARENA.name || '') + (game.count > 1 ? ' ' + (game.arenaIndexOf(pe.slot) + 1) : ''), mode: game.matchFor(pe.slot).mode })); }
      garageCamera(pe);
      if (phase === 'running') { const k = menuKeys(pe); if (k & (MK.back | MK.cycle)) garageOpen(pe, 'Pick a loadout and SORTIE'); else if (now - pe.joinedAt > CONFIG.INTRO_SECONDS || (k & MK.ok)) { pe.ready = true; guard('requestSpawn', () => game.requestSpawn(pe.slot)); } }
      break;
    }
    case 'garage': {
      garageCamera(pe); garageTick(pe);
      if (m && m.alive && pe.garage && pe.garage.open) { /* a spawn arrived while the garage was open (e.g. !back) */ garageClose(pe); }
      break;
    }
    case 'mech': {
      if (!m) { pe.status = 'intro'; break; }
      if (!m.alive) break;   // the death event switches the status
      const input = inputFor(pe.slot);
      sampleInput(pe, input);
      featInput(pe, input);
      guard('setInput', () => game.setInput(pe.slot, input));
      break;
    }
    case 'dead': {
      deathCamera(pe, m, now);
      // after the death camera the mech respawns by itself (the core's respawn timer); Ctrl or F opens the garage first
      if (pe.garage && pe.garage.open) garageTick(pe);
      else { const k = menuKeys(pe); if (k & (MK.back | MK.cycle)) garageOpen(pe, 'Change your loadout, then SORTIE'); else if (now - pe.deathAt > CONFIG.DEATH_CAM_SECONDS && !pe.garageSeenThisLife) { pe.garageSeenThisLife = true; pe.ready = true; guard('requestSpawn', () => game.requestSpawn(pe.slot)); } }
      break;
    }
    case 'spec': {
      specCamera(pe, now);
      if (menuKeys(pe) & MK.ok) specNext(pe);
      break;
    }
    default: break;
  }
}
// after game.tick: ride and look (humans in a mech)
function personAfterTick(pe) {
  if (!pe.human || pe.status !== 'mech') return;
  const m = game.mechs.get(pe.slot); if (!m || !m.alive || !live(pe.pawn)) return;
  ridePawn(pe, m);
  const cam = CONFIG.CAMERA[m.cls && m.cls.key] || CONFIG.CAMERA[(m.frame && m.frame.class) || 'medium'] || CONFIG.CAMERA.medium;
  const k = pe.camScale || 1;
  const kk = pe.kick || (pe.kick = { back: 0, up: 0, side: 0 }); const dec = Math.exp(-DT / 0.18);
  kk.back *= dec; kk.up *= dec; kk.side *= dec;
  // speed dolly (stands in for AC's boost FOV widening: the custom camera has no FOV control): pulls back with speed above walk,
  // CAM_BOOST_BACK at boost speed, up to x1.6 in a QB, + CAM_ASSAULT_BACK in assault boost; eased over CAM_SPEED_LAG s
  const lo = m.walkSpeed * 1.05, want = (m.speed > lo ? CONFIG.CAM_BOOST_BACK * Math.min(1.6, (m.speed - lo) / Math.max(1, m.boostSpeed - lo)) : 0) + (m.assault ? CONFIG.CAM_ASSAULT_BACK : 0);
  kk.spd = (kk.spd || 0) + (want - (kk.spd || 0)) * (1 - Math.exp(-DT / CONFIG.CAM_SPEED_LAG));
  let back = cam.back * k + kk.spd + kk.back, up = cam.up * k + kk.up, fast = false;
  // Looking up: CS2 turns the camera offset by the eye angles, so the camera swings down behind the mech, into the ground, and the clip
  // pull-in then parks it inside the mech's back (10 Nov 2026 playtest: "hard to shoot up ... the camera looking into the mech"). Past
  // CAM_UP_ORBIT degrees of up-look the camera stays where it is and only the view turns: the offset is counter-rotated by the excess
  // (in the eye frame: back' = back cos d - up sin d, up' = back sin d + up cos d), the mech sinks out of the bottom of the screen and
  // the reticle has clear sky. Looking down keeps the orbit (the camera rises over the mech; the higher CAMERA.up keeps the mech's head
  // ~10 deg under the reticle, so targets below the horizon are not behind the pilot's own mech).
  const over = -pe.eye.pitch - CONFIG.CAM_UP_ORBIT;
  if (over > 0) {
    const d = Math.min(89, over) * D2R, c = Math.cos(d), s = Math.sin(d), b0 = back, u0 = up;
    back = b0 * c - u0 * s; up = b0 * s + u0 * c; fast = true;
  }
  pe.camBack = back; pe.camUp = up;
  followCamera(pe, renderUpperEnt(pe.slot), back, up, renderHipZ(m), kk.side, fast || pe.camFast);
  pe.camFast = fast;
}
// cameras for people out of a mech
function garageCamera(pe) {
  const AR = game ? game.arenaFor(pe.slot) : ARENA;
  const drops = AR.drops && (AR.drops[pe.team === TEAM_T ? 't' : 'ct'] || AR.drops.ffa) || [];
  const d = drops[0] || [0, 0, 1500, 0];
  const t = gameTime() * 0.08;
  const pos = v3(d[0] + Math.cos(t) * 900, d[1] + Math.sin(t) * 900, d[2] - 900);
  controlledCamera(pe, pos, v3((AR.bounds.min[0] + AR.bounds.max[0]) / 2, (AR.bounds.min[1] + AR.bounds.max[1]) / 2, AR.bounds.min[2] + 600));
}
function killerFrameName(slot) { const k = slot >= 0 ? game.mechs.get(slot) : null; return k && k.frame ? String(k.frame.name || k.frame.model || '') : ''; }
function deathCamera(pe, m, now) {
  const c = pe.deathPos || (m ? m.pos : v3(0, 0, 500));
  // first 1.5 s: look at the killer from behind the wreck (opposite side from the killer), then the orbit
  const km = pe.deathKiller >= 0 && pe.deathKiller !== pe.slot ? game.mechs.get(pe.deathKiller) : null;
  if (km && km.alive && now - pe.deathAt < 1.5 && game.sameArena(km.slot, pe.slot)) {
    const dx = c.x - km.pos.x, dy = c.y - km.pos.y, l = Math.max(1, Math.sqrt(dx * dx + dy * dy));
    controlledCamera(pe, v3(c.x + dx / l * 650, c.y + dy / l * 650, c.z + 380), v3(km.pos.x, km.pos.y, km.pos.z + (km.cls ? km.cls.height : 288) * 0.6));
    return;
  }
  const t = (now - pe.deathAt) * 0.6 + pe.slot;
  const pos = v3(c.x + Math.cos(t) * CONFIG.DEATH_CAM_RADIUS, c.y + Math.sin(t) * CONFIG.DEATH_CAM_RADIUS, c.z + CONFIG.DEATH_CAM_UP);
  controlledCamera(pe, pos, v3(c.x, c.y, c.z + 120));
}
function specNext(pe) {
  const alive = Array.from(game.mechs.values()).filter((x) => x.alive && x.slot !== pe.slot && game.sameArena(x.slot, pe.slot)).map((x) => x.slot);
  if (!alive.length) { pe.specTarget = -1; return; }
  const i = alive.indexOf(pe.specTarget);
  pe.specTarget = alive[(i + 1) % alive.length];
  reply(pe.slot, 'Watching ' + nameOf(pe.specTarget), 3);
}
function specCamera(pe, now) {
  let m = game.mechs.get(pe.specTarget);
  if (!m || !m.alive) { specNext(pe); m = game.mechs.get(pe.specTarget); }
  if (!m) { garageCamera(pe); return; }
  const f = fwdOf(m.torsoYaw, 0);
  const pos = v3(m.pos.x - f.x * CONFIG.SPEC_BACK, m.pos.y - f.y * CONFIG.SPEC_BACK, m.pos.z + CONFIG.SPEC_UP + 120);
  controlledCamera(pe, pos, vadd(m.pos, v3(f.x * 400, f.y * 400, 160)));
  if (typeof ifrHudSlate === 'function' && ((ifrTickNo + pe.slot) & 31) === 0) guard('specbar', () => ifrHudSlate(pe.slot, 'spectator', { name: nameOf(m.slot), slot: m.slot }));
}

// ---------------------------------------------------------------- core events
function camKick(slot, back, up, side) { const pe = person(slot); if (!pe || !pe.human) return; const k = pe.kick || (pe.kick = { back: 0, up: 0, side: 0 }); k.back += back; k.up += up; k.side += side; }
function handleEvent(ev) {
  fxEvent(ev);
  featEvent(ev);
  traitEvent(ev);
  auraEvent(ev);
  if (ev.t === 'prop' || ev.t === 'props_reset') guard('props', () => propsEvent(ev));
  if (ev.t === 'qb') { const m = game.mechs.get(ev.slot); if (m) { const s = Math.sin((Math.atan2(m.vel.y, m.vel.x) * R2D - m.torsoYaw) * D2R); camKick(ev.slot, ev.chain ? 25 : 40, 0, -s * (ev.chain ? 110 : 90)); } }
  else if (ev.t === 'land') camKick(ev.slot, 0, ev.hard ? -70 : -25, 0);
  else if (ev.t === 'fire' && ev.hp >= 2) camKick(ev.slot, 25, 8, 0);
  else if (ev.t === 'damage' && ev.impact >= 500) camKick(ev.victim, 30, -20, (Math.random() - 0.5) * 40);
  else if (ev.t === 'stagger') { camKick(ev.slot, 60, -40, 0); stagMark.set(ev.slot, ifrTickNo); }
  switch (ev.t) {
    case 'spawn': {
      const pe = person(ev.slot); const m = game.mechs.get(ev.slot);
      if (pe && m) { garageClose(pe); pe.status = 'mech'; pe.garageSeenThisLife = false; pe.deathPos = null; mountPawn(pe, m.pos); renderClaimMech(m); pe.camSent = null; if (pe.human && typeof ifrHudSlate === 'function') ifrHudSlate(pe.slot, 'none', null); }
      break;
    }
    case 'damage': { applyDamageEvent(ev); const amech = ev.attacker >= 0 ? game.mechs.get(ev.attacker) : null; rigFlinch(ev.victim, ev.impact, amech ? amech.pos : null);
      if (ev.attacker >= 0 && ev.attacker !== ev.victim && typeof ifrHudHit === 'function') { const ap = person(ev.attacker); if (ap && ap.human) guard('hitmark', () => ifrHudHit(ev.attacker, (stagMark.get(ev.victim) === ifrTickNo || ev.impact >= 500 || ev.crit) ? 'heavy' : 'hit')); } const vp = person(ev.victim); const am = ev.attacker >= 0 ? game.mechs.get(ev.attacker) : null; if (vp && vp.human && am) dmgFrom.set(ev.victim, { pos: v3(am.pos.x, am.pos.y, am.pos.z), until: gameTime() + 1.2 }); break; }
    case 'kill': queueKill(ev); if (typeof ifrHudHit === 'function') { const hp = person(ev.killer); if (hp && hp.human && ev.killer !== ev.victim) guard('killmark', () => ifrHudHit(ev.killer, 'kill')); } if (typeof ifrHudFeed === 'function') { const kp = person(ev.killer); if (kp && kp.human) guard('feed', () => ifrHudFeed(ev.killer, { kill: typeof srvKillName === 'function' ? srvKillName(ev.victim) : nameOf(ev.victim), xp: ((PARTS.xp || {}).kill || 40), streak: (game.mechs.get(ev.killer) || {}).streak || 0 })); } break;
    case 'death': {
      const pe = person(ev.slot);
      if (pe) { pe.deathAt = gameTime(); pe.deathPos = ev.pos ? v3(ev.pos.x, ev.pos.y, ev.pos.z) : null; pe.deathKiller = ev.killer; if (pe.human) { pe.status = 'dead'; pe.camKind = ''; if (typeof ifrHudSlate === 'function') guard('deathslate', () => ifrHudSlate(pe.slot, 'death', { killer: ev.killer >= 0 ? nameOf(ev.killer) : 'the arena', weapon: ev.weapon || '', frame: killerFrameName(ev.killer), respawn: (PARTS.move && PARTS.move.respawn) || 6 })); } }
      break;
    }
    case 'round_end': onCoreRoundEnd(ev); break;
    case 'say': if (ev.slot === undefined || ev.slot < 0) { for (const pe of people.values()) if (pe.human) reply(pe.slot, ev.text, ev.secs || 4); } else reply(ev.slot, ev.text, ev.secs || 4); break;
    case 'bounty': for (const pe of people.values()) if (pe.human) reply(pe.slot, nameOf(ev.slot) + ' is on a ' + ev.streak + ' kill streak: BOUNTY', 5); break;
    case 'capture': { const pt = (ARENA.points || [])[ev.point]; for (const pe of people.values()) if (pe.human) reply(pe.slot, (ev.team === TEAM_T ? 'T' : 'CT') + ' took point ' + (pt ? pt.id : ev.point), 3); break; }
    case 'wave': for (const pe of people.values()) if (pe.human) reply(pe.slot, 'WAVE ' + ev.n, 4); break;
    case 'flag': if (ev.action === 'take' && ev.slot >= 0) reply(ev.slot, 'YOU HAVE THE FLAG: get it to your base', 5); else if (ev.action === 'capture') sndTone(ev.slot, 'ui_capture'); break;
    default: break;
  }
}

// ---------------------------------------------------------------- HUD feed (humans in a mech or watching)
function hudFeed(pe, now) {
  if (!pe.human) return;
  const m = game.mechs.get(pe.status === 'spec' ? pe.specTarget : pe.slot);
  const half = ((ifrTickNo + pe.slot) & 1) === 0;
  if (m && (pe.status === 'mech' || pe.status === 'spec')) {
    if (typeof ifrHudVitals === 'function') guard('hud vitals', () => ifrHudVitals(pe.slot, m));
    if (half && typeof ifrHudWeapons === 'function') guard('hud weapons', () => ifrHudWeapons(pe.slot, m.weapons));
    // incoming fire shows as a red arrow toward the shooter for 1.2 s, beside the missile threats
    const df = dmgFrom.get(pe.slot); let threats = m.threats;
    if (df) { if (gameTime() > df.until) dmgFrom.delete(pe.slot); else threats = (m.threats || []).concat([{ kind: 'close', pos: df.pos }]); }
    if (typeof ifrHudLock === 'function') guard('hud lock', () => ifrHudLock(pe.slot, m.lock, threats, m.lock && m.lock.target >= 0 ? game.mechs.get(m.lock.target) : null, m));
    // teammate marks: nobody in Skirmish, every pilot and AI ally in Sortie (the wave is team 0), the own team elsewhere; same arena copy only
    if (half && typeof ifrHudAllies === 'function') guard('hud allies', () => {
      const mt = game.matchFor(m.slot), mode = mt ? mt.mode : 'tb';
      ifrHudAllies(pe.slot, m, game.mechs, (v) => mode !== 'sk' && game.matchFor(v.slot) === mt && (mode === 'so' ? v.team === TEAM_T || v.team === TEAM_CT : v.team === m.team));
    });
  }
  if (((ifrTickNo + pe.slot) & 7) === 0 && typeof ifrHudRadar === 'function') {
    const me = m || null; const dots = [];
    if (me) for (const o of game.mechs.values()) if (o.alive && o.slot !== me.slot && game.sameArena(o.slot, me.slot)) dots.push({ x: o.pos.x - me.pos.x, y: o.pos.y - me.pos.y, team: o.team, kind: (o.streak >= 5 || featPinged(me, o)) ? 'bounty' : (me.lock && me.lock.target === o.slot ? 'target' : 'mech') });
    guard('hud radar', () => ifrHudRadar(pe.slot, dots, me ? me.torsoYaw : 0, me ? me.pos : null));
  }
  if (((ifrTickNo + pe.slot) & 15) === 0 && typeof ifrHudMode === 'function') guard('hud mode', () => ifrHudMode(pe.slot, game.matchFor(pe.slot), pe.team));
}

// ---------------------------------------------------------------- the stuck-player watchdog (once a second)
// unassigned humans are put on the smaller team; a human stuck in the intro or dead without a respawn is spawned; a piloting
// human's camera and move type are put back if anything changed them
// CS2 bots as the AI fill (scoreboard names, real kills credited like Hellmatch): bot_quota follows the fill target; the
// core counts them as pilots and drops its own AI mechs as they arrive. A map without a nav mesh never gets bots (CS2
// ignores bot_quota there): after 20 s with none, the script's own AI mechs stay the fill and bot_quota goes back to 0.
let botQuota = -1, botsAskedAt = 0, botsUnavailable = false;
function manageBots(now) {
  if (!CONFIG.CS2_BOTS || botsUnavailable || phase !== 'running') return;
  const humans = humansPlaying();
  const mode = game.matchFor(-1) ? game.matchFor(-1).mode : 'tb';
  const A = (game.list[0].g.cfg && game.list[0].g.cfg.ai) || { floor: 24, fillTotal: 16, sortieAllies: 8, skirmishFill: 8 };
  const target = humans >= A.floor ? 0 : mode === 'so' ? A.sortieAllies : mode === 'sk' ? A.skirmishFill : A.fillTotal;
  let want = Math.max(0, Math.min(64 - humans - 2, target - humans));
  // a Sortie's enemies are the script's own AI: keep two CS2 bots even with a full flight of humans, as stand-ins for the kill credit
  if (CONFIG.STANDIN_KILLS && mode === 'so' && humans > 0) want = Math.max(want, Math.min(2, 64 - humans - 2));
  let bots = 0; for (const pe of people.values()) if (!pe.human) bots++;
  if (want !== botQuota) { botQuota = want; ifrCvars(['bot_quota_mode normal', 'bot_quota ' + want, 'bot_join_after_player 0', 'bot_stop 1']); if (want > bots) botsAskedAt = now; }
  if (want > 0 && bots === 0 && botsAskedAt && now - botsAskedAt > 20) { botsUnavailable = true; ifrCvars(['bot_quota 0']); log('no CS2 bots joined (the map needs a nav mesh): the script own AI mechs fill instead'); }
}
function watchdog(now) {
  manageBots(now);
  let t = 0, ct = 0;
  for (const pe of people.values()) { if (pe.team === TEAM_T) t++; else if (pe.team === TEAM_CT) ct++; }
  for (const pe of people.values()) {
    if (!pe.human) continue;
    if (pe.team === 0 && now - pe.joinedAt > 1) { const c = live(pe.ctrl); if (c) { const team = t <= ct ? TEAM_T : TEAM_CT; guard('jointeam', () => c.JoinTeam(team)); if (team === TEAM_T) t++; else ct++; } continue; }
    if (!(pe.team === TEAM_T || pe.team === TEAM_CT) || phase !== 'running') continue;
    const m = game.mechs.get(pe.slot);
    if (pe.status === 'intro' && now - pe.joinedAt > CONFIG.INTRO_SECONDS + 4) { pe.ready = true; guard('wd spawn', () => game.requestSpawn(pe.slot)); }
    if (pe.status === 'dead' && !(pe.garage && pe.garage.open) && now - pe.deathAt > 12) { pe.deathAt = now; guard('wd respawn', () => game.requestSpawn(pe.slot)); }
    if (pe.status === 'mech' && m && m.alive) {
      const pawn = live(pe.pawn);
      if (pawn && pawn.IsAlive() && pawn.GetMoveType() !== pe.wantMt) pawn.SetMoveType(pe.wantMt);
      const cam = live(pe.cam);
      if (cam && cam.GetMode() !== CustomCameraMode.FOLLOW_POSITION) { pe.camKind = ''; pe.camSent = null; }
    }
  }
}

// ---------------------------------------------------------------- the tick
function think() {
  const t0 = perfOn ? clockMs() : 0;
  perfBegin();
  ifrTickNo++;
  const now = Instance.GetGameTime();
  ifrTickTime = now; ifrInThink = true;
  flushSays();
  let dt = now - lastTime; lastTime = now;
  if (!(dt > 0) || dt > 0.25) dt = DT;
  if (ready) guard('frame', () => frame(dt, now));
  ifrInThink = false;
  if (perfOn) { const ms = clockMs() - t0; perfTick(ms, now); perfDeepTick(ms, now); }
  Instance.SetNextThink(now);
}
function frame(dt, now) {
  if ((ifrTickNo & 63) === 0) scanPeople();
  fxTick(now);
  propsTick(now);
  srvTick(now);
  flushKills(); respawnWatch(now);
  perfMark('fx+props+server');
  if (navProbing) { const done = guard('nav probe', () => game.probeStep(world, 90)); if (done !== false) { navProbing = false; log('world survey done: ' + game.probeSummary()); } }
  if (phase === 'lobby' && roundNo === 0 && initAt && now - initAt > 1.5) { log('starting the first round'); startRound(); }
  if ((ifrTickNo & 63) === 32) guard('watchdog', () => watchdog(now));
  if (phase === 'lobby' && roundEndWaitAt && now > roundEndWaitAt && !roundEndSeen) { log('CS2 did not end the round: starting the next one myself'); roundEndWaitAt = 0; ifrCvars(CONFIG.CVARS_ALWAYS); startRound(); }
  // CS2 ended the round but no new round came (end of match, a plugin): start it ourselves rather than sit on the round-won screen
  // first ask CS2 for a real restart (clears its win panel; OnRoundStart then starts our round); if that brings no round either,
  // RESTART_WAIT later start it ourselves on top
  if (phase === 'lobby' && roundEndSeen && roundEndSeenAt && now > roundEndSeenAt + CONFIG.RESTART_WAIT) {
    if (!restartAskedAt) {
      log('CS2 ended the round ' + Math.round(now - roundEndSeenAt) + ' s ago but started no new one: mp_restartgame 1');
      restartAskedAt = now; ifrCvars(CONFIG.CVARS_ALWAYS); ifrCmd('mp_restartgame 1');
    } else if (now > restartAskedAt + CONFIG.RESTART_WAIT) {
      log('mp_restartgame brought no round either: starting it myself'); roundEndSeen = false; roundEndSeenAt = 0; roundEndWaitAt = 0; restartAskedAt = 0;
      cleanupRound(true); if (ready) rebind(); ifrCvars(CONFIG.CVARS_ALWAYS); startRound();
    }
  }
  if (phase === 'podium' && now > podiumAt) finishRound();
  for (const pe of people.values()) guard('person', () => personTick(pe, now));
  perfMark('players in');
  if (phase === 'running' || phase === 'podium') {
    guard('core tick', () => game.tick(dt, now));
    perfMark('core rest');
    const evs = game.events;
    for (let i = 0; i < evs.length; i++) guard('event ' + evs[i].t, () => handleEvent(evs[i]));
    evs.length = 0;
    perfMark('events');
    for (const pe of people.values()) guard('after', () => personAfterTick(pe));
    perfMark('players out');
    guard('render', renderAll);
    perfMark('render');
    guard('features', featTick);
    perfMark('features');
    for (const m of game.mechs.values()) guard('loops', () => fxMechLoops(m));
    perfMark('loops');
    guard('auras', auraTick);
    perfMark('auras');
    for (const pe of people.values()) guard('hudfeed', () => hudFeed(pe, now));
    perfMark('hud feed');
  }
  if (typeof ifrHudTick === 'function') guard('hudtick', ifrHudTick);
  perfMark('hud write');
}

// ---------------------------------------------------------------- perf
const perfClock = typeof performance !== 'undefined' && performance && typeof performance.now === 'function' ? performance : null;
const perfOn = CONFIG.PERF_LOG && (!!perfClock || typeof Date !== 'undefined');
function clockMs() { return perfClock ? perfClock.now() : Date.now(); }
let perfSum = 0, perfMax = 0, perfN = 0, perfAt = 0, perfTraces = 0, perfClip = 0;
function perfTick(ms, now) {
  if (phase !== 'running') { perfN = 0; perfSum = 0; perfMax = 0; perfAt = now + 60; perfTraces = traceStats.line + traceStats.sphere + traceStats.clip; perfClip = traceStats.clip; return; }
  perfSum += ms; perfN++; if (ms > perfMax) perfMax = ms;
  if (now < perfAt) return;
  const all = traceStats.line + traceStats.sphere + traceStats.clip, tr = all - perfTraces; perfTraces = all;
  perfText = 'script time: avg ' + (perfSum / Math.max(1, perfN)).toFixed(2) + ' ms, max ' + perfMax.toFixed(1) + ' ms per server tick (' + humansPlaying() + ' humans, ' + game.mechs.size + ' mechs, ' + (tr / Math.max(1, perfN)).toFixed(1) + ' traces/tick (' + ((traceStats.clip - perfClip) / Math.max(1, perfN)).toFixed(1) + ' hull), ' + propCount + ' props)' + (perfClock ? '' : ' (1 ms clock)');
  log(perfText); perfClip = traceStats.clip;
  perfN = 0; perfSum = 0; perfMax = 0; perfAt = now + 60;
}

// ---------------------------------------------------------------- CS2 hooks
Instance.SetThink(think);
Instance.OnActivate(() => { guard('init', init); Instance.SetNextThink(gameTime()); });
Instance.OnScriptReload({
  before: () => { guard('reload', () => cleanupRound(false)); return null; },
  after: () => { guard('init', init); Instance.SetNextThink(gameTime()); },
});
Instance.OnRoundStart(() => guard('roundstart', () => {
  if (phase !== 'lobby') cleanupRound(true);
  if (ready) rebind();
  ifrCvars(CONFIG.CVARS_ALWAYS);
  startRound();
}));
Instance.OnRoundEnd((ev) => guard('roundend', () => {
  roundEndSeen = true; roundEndSeenAt = gameTime();
  if (phase === 'running' && game) { guard('force end', () => game.endRound && game.endRound()); }
  const w = ev && ev.winningTeam;
  log('CS2 round ended: ' + (w === TEAM_T ? 'T win' : w === TEAM_CT ? 'CT win' : 'draw') + ', reason ' + (ev ? ev.reason : '?'));
}));
Instance.OnBeginRoundRestart(() => guard('restart', () => cleanupRound(true)));
Instance.OnPlayerDisconnect(({ playerSlot }) => guard('disconnect', () => dropPerson(playerSlot, 'disconnect')));
Instance.OnPlayerActivate(({ player }) => guard('activate', () => { scanPeople(); const s = slotOfEntity(player); const pe = s !== undefined ? person(s) : undefined; if (pe) pe.hudReset = true; }));
Instance.OnPlayerTeamChanged(({ player }) => guard('team', () => { scanPeople(); }));
Instance.OnPlayerReset(({ player }) => guard('reset', () => {
  const slot = slotOfEntity(player); if (slot === undefined) return;
  if (awaitRespawn.delete(slot)) respawnFailures = 0;
  scanPeople();
  const pe = person(slot); if (!pe) return;
  pe.pawn = pawnOf(slot); pe.camKind = ''; pe.camSent = null;
  // a fresh pawn: back into the booth (dead or in the garage) or straight onto the mech it pilots
  const m = game ? game.mechs.get(slot) : null;
  if (m && m.alive && pe.status === 'mech') mountPawn(pe, m.pos); else parkPawn(pe);
}));
Instance.OnPlayerKill(({ player }) => guard('cskilled', () => {
  const slot = slotOfEntity(player); if (slot === undefined) return;
  const pe = person(slot); if (!pe || allowDamage.has(slot)) return;
  // killed by something outside the game (admin slay): the mech dies too
  if (game) guard('outside kill', () => game.killMech && game.killMech(slot, -1));
}));
Instance.OnModifyPlayerDamage((event) => {
  const slot = slotOfEntity(event && event.player);
  if (slot !== undefined && allowDamage.has(slot) && damageDepth > 0) return undefined;
  return { abort: true };
});
Instance.OnPlayerChat(({ player, text }) => guard('chat', () => onChat(player, text)));
// the server plugin (docs/SERVER_CONTRACT.md)
Instance.OnScriptInput('ifr_server', () => guard('ifr_server', onServerInput));
Instance.OnScriptInput('ifr_pilot', (ev) => guard('ifr_pilot', () => onPilotInput(ev)));
Instance.OnScriptInput('ifr_deny', (ev) => guard('ifr_deny', () => onDenyInput(ev)));
// test only (CONFIG.DEBUG; test/mock_flows.mjs): the first piloting human destroys an AI mech, as far as the kill credit goes
// The timing test (11 Nov 2026: 10-12 ms ticks with 16 mechs, never measured with 64). Server only: the plugin's console command
// `slime_ifr_test input ifr_perf_64` (or ent_fire with cheats). It restarts the round as Team Deathmatch filled to 64 mechs (CS2 bots take
// the player slots, the script's AI the rest) and logs, every 20 s: the tick time, how many ticks took 8 ms or more, the average time of
// each part of the tick, and for the slow ticks which part was the biggest and where they fall in the 64-tick cycle (the once-a-second jobs).
// ifr_perf_32: the same with 32. ifr_perf_off: back to normal. The clock is 1 ms coarse here, so the parts are averages over ~1280 ticks.
let perfDeep = false, perfForce = '', perfSecT = 0, perfDeepAt = 0, perfDeepN = 0, perfDeepSum = 0, perfDeepMax = 0, perfSlow = 0;
/** @type {Record<string, number>} */ const perfSecs = {};
/** @type {Record<string, number>} */ const perfTickSecs = {};
/** @type {Record<string, number>} */ const perfSlowBy = {};
const perfSlowPhase = new Int32Array(64);
function perfBegin() { if (perfDeep) { perfSecT = clockMs(); for (const k in perfTickSecs) perfTickSecs[k] = 0; } }
function perfMark(name) { if (!perfDeep) return; const t = clockMs(), d = t - perfSecT; perfSecT = t; perfSecs[name] = (perfSecs[name] || 0) + d; perfTickSecs[name] = (perfTickSecs[name] || 0) + d; }
function perfDeepTick(ms, now) {
  if (!perfDeep || phase !== 'running') return;
  perfDeepN++; perfDeepSum += ms; if (ms > perfDeepMax) perfDeepMax = ms;
  if (ms >= 8) {
    perfSlow++; perfSlowPhase[ifrTickNo & 63]++;
    let top = 'other', tv = 0; for (const k in perfTickSecs) if (perfTickSecs[k] > tv) { tv = perfTickSecs[k]; top = k; }
    perfSlowBy[top] = (perfSlowBy[top] || 0) + 1;
  }
  if (now < perfDeepAt) return;
  if (!perfBenchDone) { perfBenchDone = true; guard('perf bench', perfBench); }
  const n = Math.max(1, perfDeepN);
  const secs = Object.keys(perfSecs).sort((a, b) => perfSecs[b] - perfSecs[a]).map((k) => k + ' ' + (perfSecs[k] / n).toFixed(2)).join(', ');
  const by = Object.keys(perfSlowBy).sort((a, b) => perfSlowBy[b] - perfSlowBy[a]).map((k) => k + ' x' + perfSlowBy[k]).join(', ');
  const ph = []; for (let i = 0; i < 64; i++) if (perfSlowPhase[i]) ph.push([i, perfSlowPhase[i]]);
  ph.sort((a, b) => b[1] - a[1]);
  let bots = 0; for (const pe of people.values()) if (!pe.human) bots++;
  log('perf: ' + game.mechs.size + ' mechs (' + humansPlaying() + ' humans, ' + bots + ' CS2 bots), ' + propCount + ' props: avg ' + (perfDeepSum / n).toFixed(2) + ' ms, max ' + perfDeepMax.toFixed(0) +
    ' ms a tick, ' + perfSlow + ' of ' + perfDeepN + ' ticks took 8 ms or more');
  log('perf parts, avg ms a tick: ' + secs);
  if (perfSlow) log('perf slow ticks: biggest part ' + by + '; tick mod 64: ' + ph.slice(0, 6).map((x) => x[0] + ' x' + x[1]).join(', '));
  perfDeepN = 0; perfDeepSum = 0; perfDeepMax = 0; perfSlow = 0; perfSlowPhase.fill(0);
  for (const k in perfSecs) perfSecs[k] = 0;
  for (const k in perfSlowBy) delete perfSlowBy[k];
  perfDeepAt = now + 20;
}
// what one unit of each kind of work costs in this engine (once, at the first report): plain arithmetic, small objects and closures,
// a line / sphere / hull trace, one Teleport. Node on the same PC (cold): 58 / 10 / 18 ms. Measured in CS2 11 Nov 2026: 278 / 42 / 74 ms,
// line trace 21 us, sphere 16, hull 17, teleport 3: the script engine is about 5 x slower than Node, a trace costs as much as ~200 plain operations.
let perfBenchDone = false;
function perfBench() {
  let t = clockMs(), x = 0;
  for (let i = 0; i < 3000000; i++) x += Math.sqrt(i * 1.0001) * 0.5 - (x > 1e6 ? x * 0.5 : 0);
  const js = clockMs() - t; t = clockMs();
  let y = 0; for (let i = 0; i < 300000; i++) { const o = { x: i, y: i + 1, z: i + 2 }; y += o.x + o.z; }
  const obj = clockMs() - t; t = clockMs();
  let z = 0; for (let i = 0; i < 300000; i++) { const f = () => i + 1; z += f(); }
  const clo = clockMs() - t;
  let m0 = null; for (const m of game.mechs.values()) if (m.alive) { m0 = m; break; }
  let line = -1, sph = -1, clip = -1, tp = -1;
  if (m0) {
    const a = v3(m0.pos.x, m0.pos.y, m0.pos.z + 150), b = v3(m0.pos.x + 2000, m0.pos.y + 500, m0.pos.z + 100);
    t = clockMs(); for (let i = 0; i < 3000; i++) world.traceLine(a, b); line = (clockMs() - t) / 3;
    t = clockMs(); for (let i = 0; i < 1000; i++) world.traceSphere(a, b, 60); sph = clockMs() - t;
    t = clockMs(); for (let i = 0; i < 1000; i++) world.traceClip(a, b, m0.slot); clip = clockMs() - t;
  }
  const pp = pfx.spark && pfx.spark.find((q) => !q.busy && live(q.ent));
  if (pp) { t = clockMs(); for (let i = 0; i < 2000; i++) pp.ent.Teleport({ position: HIDE_POS }); tp = (clockMs() - t) / 2; }
  log('perf bench: 3 M arithmetic ' + js + ' ms, 300 k objects ' + obj + ' ms, 300 k closures ' + clo + ' ms; microseconds each: line trace ' + line.toFixed(1) + ', sphere trace ' + sph.toFixed(1) +
    ', hull trace ' + clip.toFixed(1) + ', teleport ' + tp.toFixed(1) + ' (' + (x + y + z > 0 ? 'ok' : '?') + ')');
}
function perfSet(n) {
  if (!game) return;
  perfDeep = n > 0; perfForce = n > 0 ? 'tb' : '';
  for (const a of game.list) {
    /** @type {any} */ (a.g).perfHook = n > 0 ? (/** @type {string} */ name) => perfMark('core ' + name) : undefined;      // the stages of the core tick (80_game.js)
    const A = /** @type {any} */ (a.g.cfg.ai);
    if (n > 0) { if (!A.perfKeep) A.perfKeep = [A.fillTotal, A.floor]; A.fillTotal = n; A.floor = 999; }
    else if (A.perfKeep) { A.fillTotal = A.perfKeep[0]; A.floor = A.perfKeep[1]; A.perfKeep = null; }
  }
  log(n > 0 ? 'perf test ON: Team Deathmatch filled to ' + n + ' mechs, a timing report every 20 s (ifr_perf_off ends it)' : 'perf test off: the next round is a normal one');
  perfDeepAt = gameTime() + 20; perfDeepN = 0; perfDeepSum = 0; perfDeepMax = 0; perfSlow = 0;
  cleanupRound(true); if (ready) rebind(); ifrCvars(CONFIG.CVARS_ALWAYS); startRound();
}
Instance.OnScriptInput('ifr_perf_64', () => guard('perf', () => perfSet(64)));
Instance.OnScriptInput('ifr_perf_32', () => guard('perf', () => perfSet(32)));
Instance.OnScriptInput('ifr_perf_off', () => guard('perf', () => perfSet(0)));
Instance.OnScriptInput('ifr_test_npckill', () => guard('test npckill', () => {
  if (!CONFIG.DEBUG) return;
  for (const pe of people.values()) if (pe.human && pe.status === 'mech') { queueKill({ victim: 9999, killer: pe.slot, weapon: 'test' }); return; }
}));
for (const name of CHAT_FROM_SERVER) Instance.OnScriptInput('ifr_cmd_' + name, (ev) => guard('ifr_cmd', () => onServerCommand(name, ev)));
Instance.OnScriptInput('mgstat_on', () => guard('stats', () => { if (!statsOn) log('server stats on'); statsOn = true; }));
Instance.OnScriptInput('mgstat_off', () => guard('stats', () => { statsOn = false; }));
