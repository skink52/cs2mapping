// ---------------------------------------------------------------- main loop and CS2 round flow

let rm = null;
const views = new Map();          // Arena -> ArenaView
let ready = false;
let lastTime = 0, acc = 0;
let phase = 'lobby';              // lobby | running | ending
let startAt = 0;
let lastPeopleScan = 0;
const pendingKills = [];          // { at, victim, killer }
const allowDamage = new Set();
const centerMsgs = new Map();     // slot -> { text, until, cls }
const subMsgs = new Map();        // slot -> { text, until }
const botMsgs = new Map();        // slot -> { text, until }  (bottom message line)
const soundCd = new Map();        // car slot + sfx -> next time
let standingsAt = 0;
const standingsCache = new Map(); // arena index -> rows
let lobbyNext = 0;

function buildCfg() {
  return {
    layout: CONFIG.ARENA_LAYOUT, arenaMin: CONFIG.ARENA_MIN, minPlayers: CONFIG.MIN_PLAYERS,
    afkWarnTics: CONFIG.AFK_WARN * TICRATE, afkKickTics: CONFIG.AFK_KICK * TICRATE, afkLobbyTics: CONFIG.AFK_LOBBY * TICRATE,
    countdownTics: CONFIG.COUNTDOWN * TICRATE, finishWindow: CONFIG.FINISH_WINDOW, raceCap: CONFIG.RACE_CAP, endHold: CONFIG.RESULTS_HOLD, laps: CONFIG.LAPS,
    botSkill: CONFIG.BOT_SKILL, podium: CONFIG.PODIUM, shares: CONFIG.SHARES.slice(), koCredit: CONFIG.KO_CREDIT_TO_ATTACKER, tiebreak: CONFIG.TIEBREAK,
    trackBlacklist: CONFIG.TRACK_BLACKLIST.slice(), staggerArenas: true, defaultCar: CONFIG.DEFAULT_CAR,
    votes: CONFIG.VOTES, voteWeights: CONFIG.VOTE_WEIGHTS.slice(), voteChoices: CONFIG.VOTE_CHOICES, botsVote: CONFIG.BOTS_VOTE,
    glowPlaces: CONFIG.WINNER_GLOW ? CONFIG.GLOW_PLACES : 0,
  };
}

function cvars(list) { if (CONFIG.APPLY_CVARS) for (const c of list) Instance.ServerCommand(c); }

function init() {
  seedRandom((Date.now() & 0x7fffffff) || 1);
  rm = new RoundManager(TRACKS, buildCfg());
  findPropTemplate();
  hud();
  scanPeople(true);
  cvars(CONFIG.CVARS_ALWAYS);
  if (CONFIG.AUTO_TEAM) cvars(['mp_force_assign_teams 1', 'sv_disable_teamselect_menu 1']);
  ready = true;
  lastTime = gameTime();
  startAt = lastTime + 1;
  log(`v${VERSION} ready: ${rm.tracks.length} tracks, HUD ${hud() ? 'on' : 'MISSING'}, prop template ${findPropTemplate() ? 'on' : 'MISSING'}`);
}

function scanPeople(force) {
  const now = gameTime();
  if (!force && now - lastPeopleScan < 1) return;
  lastPeopleScan = now;
  const seen = new Set();
  const unassigned = [];
  for (const c of Instance.GetAllPlayerControllers()) {
    if (!c || !c.IsConnected()) continue;
    const slot = c.GetPlayerSlot();
    seen.add(slot);
    const bot = c.IsBot();
    if (CONFIG.AUTO_TEAM && !bot && c.GetTeamNumber() === 0) unassigned.push(c);
    if (bot && !CONFIG.CS2_BOTS_PLAY) continue;
    const name = c.GetPlayerName();
    // the slot now holds someone else (a bot kicked for a joining player, a quick leave + join): start them fresh,
    // so the newcomer never inherits the old car, kill credit, HUD state or options
    const old = rm.person(slot);
    if (old && (old.bot !== bot || old.name !== name)) { log(`slot ${slot}: ${old.name} -> ${name}`); dropPerson(slot); }
    rm.addPerson(slot, name, c.GetTeamNumber(), bot);
  }
  for (const slot of Array.from(rm.people.keys())) if (!seen.has(slot)) dropPerson(slot);
  autoTeam(unassigned, now);
}

// players still on no team (CS2's team menu) after AUTO_TEAM_DELAY seconds go to the side with fewer players (then
// fewer humans; then the one with the worse score this map). Spectators (team 1) are left alone.
const unassignedSince = new Map();   // slot -> game time first seen without a team
function autoTeam(list, now) {
  for (const slot of Array.from(unassignedSince.keys())) if (!list.some((c) => c.GetPlayerSlot() === slot)) unassignedSince.delete(slot);
  if (!list.length) return;
  for (const c of list) {
    const slot = c.GetPlayerSlot();
    if (!unassignedSince.has(slot)) { unassignedSince.set(slot, now); if (CONFIG.AUTO_TEAM_DELAY > 0) continue; }
    if (now - unassignedSince.get(slot) < CONFIG.AUTO_TEAM_DELAY) continue;
    const n = { 2: 0, 3: 0 }, h = { 2: 0, 3: 0 };
    for (const pe of rm.people.values()) if (pe.csTeam === 2 || pe.csTeam === 3) { n[pe.csTeam]++; if (!pe.bot) h[pe.csTeam]++; }
    const team = n[2] !== n[3] ? (n[2] < n[3] ? 2 : 3) : h[2] !== h[3] ? (h[2] < h[3] ? 2 : 3) : (Math.random() < 0.5 ? 2 : 3);
    guard('autoteam', () => c.JoinTeam(team));
    unassignedSince.delete(slot);
    const pe = rm.person(slot);
    if (pe) pe.csTeam = team;
    log(`${c.GetPlayerName()} put on ${team === 2 ? 'T' : 'CT'} (auto team)`);
  }
}

function dropPerson(slot) {
  rm.removePerson(slot);
  parked.delete(slot); noPawnUntil.delete(slot);
  hudReset(slot);
  centerMsgs.delete(slot); subMsgs.delete(slot); botMsgs.delete(slot);
  awaitRespawn.delete(slot);
  for (let i = pendingKills.length - 1; i >= 0; i--) {
    const k = pendingKills[i];
    if (k.victim === slot) pendingKills.splice(i, 1);
    else if (k.killer === slot) { k.killer = null; k.kpe = null; }
  }
}

// ---------------------------------------------------------------- messages
function center(slot, text, secs, cls) { centerMsgs.set(slot, { text, until: gameTime() + secs, cls: cls || null }); }
function sub(slot, text, secs) { subMsgs.set(slot, { text, until: gameTime() + secs }); }
function bottom(slot, text, secs) { botMsgs.set(slot, { text, until: gameTime() + secs }); }
function timed(map, slot, now) { const m = map.get(slot); return m && now < m.until ? m : null; }

// ---------------------------------------------------------------- round flow
function startRace() {
  scanPeople(true);
  if (!rm.startRound()) { startAt = gameTime() + 5; return; }
  phase = 'running';
  cvars(['mp_ignore_round_win_conditions 1', 'mp_teammates_are_enemies 1']);
  guard('roundtime', () => Instance.SetRoundRemainingTime(CONFIG.COUNTDOWN + CONFIG.RACE_CAP + CONFIG.RESULTS_HOLD + CONFIG.ROUND_SLACK));
  pendingKills.length = 0;
  const desc = rm.plan.map((it) => `${it.track.title} (${it.grp.length}${it.voted ? ', VOTED' : ''})`).join(', ');
  sayAll(`RACE ${rm.roundNumber}: ${desc}`);
  log(`round ${rm.roundNumber}: ${rm.plan.map((it) => it.track.id + ':' + it.grp.length).join(' ')}`);
}

function onArenaBuilt(a) {
  views.set(a, new ArenaView(a));
  for (const car of a.order) {
    const pe = car.person;
    if (!pe || (pe.bot && !CONFIG.CS2_BOTS_PLAY)) continue;
    const pk = park(pe.slot, true);
    if (pk) pk.camYaw = null;
    if (!pe.bot) center(pe.slot, a.track.title, 4, 'gold');
  }
}

let endedAt = 0, roundEndSeen = false;
function endRace() {
  if (phase !== 'running') return;
  phase = 'ending'; endedAt = gameTime(); roundEndSeen = false;
  const pts = rm.teamPoints();
  const lines = pts.detail.map((d) => `${d.track}: T ${d.t} - CT ${d.ct}`);
  const who = pts.winner === 2 ? 'T WIN' : pts.winner === 3 ? 'CT WIN' : 'DRAW';
  sayAll(`RACE OVER - ${lines.join(' | ')} - ${who}`);
  cvars(['mp_ignore_round_win_conditions 0']);
  const reason = pts.winner === 2 ? CSRoundEndReason.TERRORISTS_WIN : pts.winner === 3 ? CSRoundEndReason.CTS_WIN : CSRoundEndReason.DRAW;
  if (live(Instance.FindEntityByName(CONFIG.MAP_PARAMS))) {
    log(`FireWinCondition ${reason} (top-8: T ${pts[2]}, CT ${pts[3]})`);
    guard('wincond', () => Instance.EntFireAtName({ name: CONFIG.MAP_PARAMS, input: 'FireWinCondition', value: reason }));
  } else {
    warnOnce('nomapparams', 'no ' + CONFIG.MAP_PARAMS + ' entity: rounds end on the clock as draws');
    guard('endround', () => Instance.SetRoundRemainingTime(1));
  }
}

function cleanupRound(entitiesGone) {
  for (const v of views.values()) {
    if (entitiesGone) { v.props.clear(); v.fx = []; v.pulseProp = null; v.anchors = null; }
    else v.destroy();
  }
  views.clear();
  for (const slot of Array.from(parked.keys())) unpark(slot);
  if (entitiesGone) { freeProps.length = 0; propTemplate = undefined; hudEnt = undefined; boothEnt = undefined; soundEnts.clear(); }
  rm.endRoundCleanup();
  rm.state = 'idle';
  pendingKills.length = 0;
  awaitRespawn.clear();
  standingsCache.clear();
  phase = 'lobby';
}

// ---------------------------------------------------------------- CS2 kills
function csKill(victimSlot, killerSlot) {
  const vp = pawnOf(victimSlot);
  if (!vp || !vp.IsAlive()) return false;
  let attacker = killerSlot === null || killerSlot === undefined ? undefined : killerSlot !== victimSlot ? pawnOf(killerSlot) : vp;
  if (attacker && !attacker.IsAlive()) attacker = controllerOf(killerSlot) || undefined;
  allowDamage.add(victimSlot);
  guard('cskill', () => vp.TakeDamage({
    damage: 1000, attacker, inflictor: attacker,
    damageTypes: CSDamageTypes.VEHICLE, damageFlags: CSDamageFlags.FORCE_DEATH | CSDamageFlags.IGNORE_ARMOR,
  }));
  allowDamage.delete(victimSlot);
  const died = !live(vp) || !vp.IsAlive();
  const vc = controllerOf(victimSlot), kc = killerSlot !== victimSlot ? controllerOf(killerSlot) : undefined;
  if ((vc && !vc.IsBot()) || (kc && !kc.IsBot())) guard('killlog', () => log(`CS2 kill: ${kc ? kc.GetPlayerName() : 'world'} -> ${vc ? vc.GetPlayerName() : victimSlot}${died ? '' : ' BLOCKED'}`));
  if (!died) warnOnce('killblocked', 'a scripted CS2 kill was blocked (plugin or damage settings?)');
  return died;
}

function queueKill(victimSlot, killerSlot, delay) {
  if (Instance.IsWarmupPeriod()) { warnOnce('warmupkills', 'warmup: race results are not sent to the CS2 scoreboard until warmup ends'); return; }
  if (!CONFIG.REAL_KILLS) {
    if (CONFIG.ADD_SCORE && killerSlot !== null && killerSlot !== undefined) { const c = controllerOf(killerSlot); if (c) guard('addscore', () => c.AddScore(1)); }
    return;
  }
  const kp = killerSlot === null || killerSlot === undefined ? null : rm.person(killerSlot);
  pendingKills.push({ at: gameTime() + delay, victim: victimSlot, killer: killerSlot, vpe: rm.person(victimSlot), kpe: kp });
}

function processKills(now) {
  for (let i = 0; i < pendingKills.length; i++) {
    const k = pendingKills[i];
    if (now < k.at) continue;
    pendingKills.splice(i, 1); i--;
    // only for the same people who raced: a slot can change hands between the race and the kill
    const pe = rm.person(k.victim);
    if (!pe || (k.vpe && pe !== k.vpe)) continue;
    let killer = k.killer;
    if (killer !== null && killer !== undefined && k.kpe && rm.person(killer) !== k.kpe) killer = null;
    if (csKill(k.victim, killer)) {
      parked.delete(k.victim);
      if (k.mid) awaitRespawn.set(k.victim, { at: now, pe });
    }
  }
  // knock-out kills during a race need CS2 to respawn the pawn (the player keeps watching through it);
  // if it doesn't, stop killing mid-race and credit knock-outs at the end of the race instead
  for (const [slot, w] of awaitRespawn) {
    if (now - w.at < 8) continue;
    awaitRespawn.delete(slot);
    const c = controllerOf(slot);
    if (rm.person(slot) !== w.pe || !c || !c.IsConnected()) continue;
    respawnFailures++;
    log(`CS2 did not respawn ${w.pe.name} within 8 s after a scripted kill (${respawnFailures} in a row)`);
    if (respawnFailures >= 2 && !koDeferred) { koDeferred = true; log('WARNING: CS2 is not respawning killed players (mp_respawn_on_death_t/ct?) - knock-out kills now wait for the end of each race'); }
  }
}
const awaitRespawn = new Map();   // slot -> { at, pe }: killed mid-race, waiting for CS2's respawn
let respawnFailures = 0, koDeferred = false;

// ---------------------------------------------------------------- events from the race
function sfxCar(view, sfx, car, gap) {
  const key = car.slot + sfx, now = gameTime();
  if (gap && (soundCd.get(key) || 0) > now) return;
  soundCd.set(key, now + (gap || 0));
  playSound(view, sfx, car);
}

const records = new Map();   // track id -> { time, name }: the best lap since the map loaded
function recordText(T) { const r = records.get(T.id); return r ? `  RECORD ${fmtTime(r.time)} ${r.name}` : ''; }

function handleArenaEvents(a, now) {
  const view = views.get(a);
  const T = a.track;
  for (const e of a.events) {
    switch (e.type) {
      case 'beep': { const p = T.point(0); if (view) playSound(view, e.n === 1 ? 'beep2' : 'beep', null, p.x, p.y, p.z + 60); for (const c of a.order) if (c.person && !c.person.bot) center(c.person.slot, String(e.n), 1.1, 'red'); break; }
      case 'launch': { const pe = e.car.person; if (pe && !pe.bot) { bottom(pe.slot, 'TURBO START!', 2); hudFlash(pe.slot, 'pulse', 0.3); shake(pe.slot, 0.3, 8); } if (view) sfxCar(view, 'boost', e.car, 0.8); break; }
      case 'stall': { const pe = e.car.person; if (pe && !pe.bot) bottom(pe.slot, 'TOO EARLY - ENGINE STALLED', 2); break; }
      case 'ability': {
        // the E abilities: a sound for everyone near, an effect, a shake for the cars caught in a Shockwave
        const c = e.car, pe = c.person, human = pe && !pe.bot;
        if (view) sfxCar(view, e.kind === 'quake' ? 'quake' : e.kind === 'nova' ? 'nova' : e.kind === 'aegis' ? 'aegis' : 'dash', c);
        if (e.kind === 'quake') {
          if (view) view.effect(c.x, c.y, c.z, c.yaw, [CAR_MODELS.fx.quake0, CAR_MODELS.fx.quake1, CAR_MODELS.fx.quake2], 0.45, now);
          for (const o of a.order) {
            const op = o.person;
            if (!op || op.bot || Math.hypot(o.x - c.x, o.y - c.y) > RULES.quakeRadius * 1.5) continue;
            shake(op.slot, 0.5, o === c ? 10 : 18);
          }
          if (human && e.hits) bottom(pe.slot, 'SHOCKWAVE HIT ' + e.hits + (e.hits === 1 ? ' CAR' : ' CARS'), 2);
        } else if (e.kind === 'aegis') {
          if (human) bottom(pe.slot, e.hits ? 'AEGIS - ' + e.hits + ' TEAMMATE' + (e.hits === 1 ? '' : 'S') + ' +' + RULES.aegisShare + ' SHIELD' : 'AEGIS UP', 2);
          for (const o of a.order) if (o !== c && o.person && !o.person.bot && o.team === c.team && o.team >= 0 && Math.hypot(o.x - c.x, o.y - c.y) <= RULES.aegisRange && o.state === 'racing') bottom(o.person.slot, '+' + RULES.aegisShare + ' SHIELD FROM ' + c.name.slice(0, 16).toUpperCase(), 2);
        } else if (e.kind === 'nova') {
          if (human) { hudFlash(pe.slot, 'pulse', 0.3); shake(pe.slot, 0.35, 9); }
        }
        break;
      }
      case 'creaturePass': {
        // a sea creature starts a pass: its call, from where it sets off
        const s = e.cr.segs[0];
        if (view && CAR_MODELS.fx.cr_serpent_head) playSound(view, 'creature', null, s.x, s.y, s.z);
        break;
      }
      case 'creatureWarn': {
        const pe = e.car.person;
        if (pe && !pe.bot) { bottom(pe.slot, '!! ' + (CREATURE_NAMES[e.cr.kind] || 'CREATURE') + ' AHEAD !!', 2.5); hudFlash(pe.slot, 'pulse', 0.3); }
        break;
      }
      case 'creatureHit': {
        const pe = e.car.person;
        if (view) sfxCar(view, e.blocked ? 'aegis' : 'hit', e.car, 0.2);
        if (pe && !pe.bot) {
          if (e.blocked) bottom(pe.slot, 'AEGIS HELD OFF THE ' + (CREATURE_NAMES[e.cr.kind] || 'CREATURE'), 2);
          else { shake(pe.slot, 0.7, 22); hudFlash(pe.slot, 'hit', 0.5); bottom(pe.slot, 'HIT BY THE ' + (CREATURE_NAMES[e.cr.kind] || 'CREATURE') + '!', 2.5); }
        }
        break;
      }
      case 'boltHit': {
        // a Seeker Bolt landed: a burst, a hard shake for the car hit, a line for both drivers
        const b = e.bolt, vp = e.car.person, ap = b.owner.person;
        if (view) { view.effect(b.x, b.y, b.z - RULES.boltLift, b.yaw, [CAR_MODELS.fx.boom0, CAR_MODELS.fx.boom1], 0.3, now); sfxCar(view, e.blocked ? 'aegis' : 'hit', e.car, 0.2); }
        if (!e.blocked && vp && !vp.bot) { shake(vp.slot, 0.5, 18); hudFlash(vp.slot, 'hit', 0.4); bottom(vp.slot, 'HIT BY ' + b.owner.name.slice(0, 16).toUpperCase() + "'S SEEKER BOLT", 2); }
        if (ap && !ap.bot) bottom(ap.slot, e.blocked ? 'BOLT BLOCKED BY AEGIS' : 'BOLT HIT ' + e.car.name.slice(0, 20).toUpperCase(), 2);
        break;
      }
      case 'fire': {
        const f = e.fire;
        // Nova fire: two frames flickering for as long as it burns
        if (view) view.effect(f.x, f.y, f.z, f.yaw, FIRE_FRAMES, RULES.fireTime, now);
        break;
      }
      case 'spinHit': {
        // a spin attack landed: a hard shake for the car shoved across the road, a little one for the attacker
        const vp = e.car.person, ap = e.attacker.person;
        if (vp && !vp.bot) { shake(vp.slot, 0.45, 16); hudFlash(vp.slot, 'hit', 0.35); }
        if (ap && !ap.bot) shake(ap.slot, 0.2, 6);
        break;
      }
      case 'armed': { for (const c of a.order) if (c.racing && c.person && !c.person.bot) { bottom(c.person.slot, 'ATTACKS ON: SPINS ARE LIVE', 2); hudFlash(c.person.slot, 'pulse', 0.3); } break; }
      case 'go': { const p = T.point(0); if (view) playSound(view, 'go', null, p.x, p.y, p.z + 60); for (const c of a.order) if (c.person && !c.person.bot) center(c.person.slot, 'GO!', 1.2, 'green'); break; }
      case 'wreck': {
        if (view) { view.wreckEffect(e.car, now); sfxCar(view, 'wreck', e.car); }
        const pe = e.car.person;
        if (pe && !pe.bot) { center(pe.slot, 'WRECKED', 3, 'red'); shake(pe.slot, 0.6, 20); }
        if (e.attacker) {
          const ap = e.attacker.person;
          if (ap && !ap.bot) bottom(ap.slot, 'YOU WRECKED ' + e.car.name.slice(0, 20).toUpperCase(), 3);
          e.car.koBy = e.attacker;      // credited at the end of the race unless it goes out now
          if (CONFIG.KO_CREDIT_TO_ATTACKER && !koDeferred && pe && ap && !Instance.IsWarmupPeriod()) {
            e.car.koApplied = true; queueKill(pe.slot, ap.slot, 0.4);
            const k = pendingKills[pendingKills.length - 1]; if (k) k.mid = true;
          }
        }
        break;
      }
      case 'finish': {
        if (view) sfxCar(view, 'finish', e.car);
        const pe = e.car.person;
        if (pe && !pe.bot) center(pe.slot, 'FINISHED ' + ordinal(e.pos), 4, e.pos <= 3 ? 'gold' : 'green');
        break;
      }
      case 'gone': if (view) { view.warpEffect(e.car, now); sfxCar(view, 'warp', e.car); } break;
      case 'lap': {
        const best = e.car.bestLap && Math.abs(e.last - e.car.bestLap) < 1e-6 && e.lap > 1;
        // track records (kept while the map runs)
        const rec = records.get(T.id);
        if (e.last > 3 && (!rec || e.last < rec.time)) {
          records.set(T.id, { time: e.last, name: e.car.name.slice(0, 10).toUpperCase(), who: e.car.name, arena: a });
          a.newRecord = true;
          const rp = e.car.person;
          if (rec && rec.arena !== a && rp && !rp.bot) center(rp.slot, 'LAP RECORD!', 2, 'gold');
        }
        if (view) sfxCar(view, best ? 'best' : 'lap', e.car);
        const pe = e.car.person;
        if (pe && !pe.bot) {
          if (e.lap === a.laps - 1) center(pe.slot, 'FINAL LAP', 2, 'gold');
          bottom(pe.slot, (best ? 'BEST LAP ' : 'LAP ') + fmtTime(e.last), 2.5);
        }
        break;
      }
      case 'pulse': if (e.start && view) { const p = T.point(a.pulse.total); playSound(view, 'pulse', null, p.x, p.y, p.z + 40); } break;
      case 'pulsed': { const pe = e.car.person; if (pe && !pe.bot) bottom(pe.slot, '+' + RULES.pulseCharge + ' CHARGE FROM THE PULSE', 2); if (view) sfxCar(view, 'pulsed', e.car, 0.5); break; }
      case 'arenaEnd': onArenaEnd(a, e.result, now); break;
    }
  }
  a.events.length = 0;
  // per-car effect bits - once per race step: when an arena stops stepping (results), its cars keep their last bits
  if (!view || (a.state === 'over' && view.fxDone)) return;
  if (a.state === 'over') view.fxDone = true;
  for (const car of a.order) {
    const f = car.fx;
    if (!f && !car.boosting && !car.onCharge) { car.wasBoost = false; car.wasCharge = false; continue; }
    const pe = car.person, human = pe && !pe.bot;
    if (f & 1) { sfxCar(view, 'hit', car, 0.25); if (human) { hudFlash(pe.slot, 'hit', 0.25); shake(pe.slot, 0.25, 7); } }
    if (f & 2) { sfxCar(view, 'rail', car, 0.3); if (human) shake(pe.slot, 0.2, 5); }
    if (f & 64) sfxCar(view, 'scrape', car, 0.6);
    if (f & 8) sfxCar(view, 'pad', car, 0.5);
    if (f & 16) { sfxCar(view, 'fall', car); if (human) { center(pe.slot, car.out ? 'OUT OF BOUNDS' : 'FELL OFF', 2, 'red'); sub(pe.slot, '-' + (car.out ? RULES.outPenalty : RULES.fallPenalty) + ' SHIELD', 2); } }
    if (f & 32) sfxCar(view, 'spin', car);
    if (f & 128) { sfxCar(view, 'reset', car); const pk = pe ? parked.get(pe.slot) : null; if (pk) pk.camYaw = null; }
    if (f & 4 && human) hudFlash(pe.slot, 'pulse', 0.4);
    if (f & 512) sfxCar(view, 'jump', car, 0.3);
    if (f & 1024) { sfxCar(view, 'land', car, 0.3); if (human) shake(pe.slot, 0.3, 12); }
    if (f & 8192 && human) bottom(pe.slot, (GAME_THEME === 'depth' ? 'GLIDE' : 'FLIGHT') + ': W DOWN  S UP  HIT THE RINGS', 3);
    if (f & 4096) { sfxCar(view, 'pulsed', car, 0.4); if (human) bottom(pe.slot, 'BIG AIR! +' + RULES.bigAirCharge + ' CHARGE', 2); }
    if (car.boosting && !car.wasBoost) sfxCar(view, 'boost', car, 0.8);
    if (car.onCharge && !car.wasCharge) sfxCar(view, 'charge', car, 1.0);
    car.wasBoost = car.boosting; car.wasCharge = car.onCharge;
  }
}

// Nova fire flickers between its two frames (the effect steps through the list over its lifetime)
const CREATURE_NAMES = { serpent: 'SERPENT', manta: 'MANTA', whale: 'WHALE' };
const FIRE_FRAMES = Array.from({ length: Math.round(RULES.fireTime * 8) }, (_, k) => (k % 2 ? CAR_MODELS.fx.fire1 : CAR_MODELS.fx.fire0));

const flashes = new Map();   // slot -> { cls, until }
function hudFlash(slot, cls, secs) { flashes.set(slot, { cls, until: gameTime() + secs }); }

function onArenaEnd(a, result, now) {
  if (a.newRecord) { const r = records.get(a.track.id); if (r) sayAll(`LAP RECORD on ${a.track.title}: ${r.who} ${fmtTime(r.time)}`); a.newRecord = false; }
  // the results come up clear: a car picker still open from before the end closes (!car brings it back)
  // (pickShown too: an A / D tap before the next HUD update would otherwise count as browsing and reopen it)
  for (const pe of rm.people.values()) if (pe.arena === a || (pe.spec && pe.spec.arena === a.index)) { pe.pickUntil = 0; pe.pickShown = false; }
  const r = result.ranking;
  const top = r.slice(0, 3).map((c, i) => `${i + 1}. ${c.name}`).join('  ');
  sayAll(`${a.track.title}: ${top}`);
  // results: the board in the middle of everyone's screen (hudResults); your own placing on the bottom line
  for (const c of a.order) {
    const pe = c.person;
    if (!pe || pe.bot) continue;
    const pos = r.indexOf(c) + 1;
    // (38 characters at most, the bottom line's width: "WRECKED - 12TH OF 32 - BEST LAP 0:29.8")
    if (pos > 0) bottom(pe.slot, (c.state === 'wrecked' ? 'WRECKED - ' : c.state === 'dnf' ? 'DNF - ' : 'YOU: ') + ordinal(pos) + ' OF ' + r.length + (c.bestLap ? ' - BEST LAP ' + lapText(c.bestLap) : ''), CONFIG.RESULTS_HOLD + 2);
  }
  // the losers die, credited to the podium, one every few ticks
  const plan = rm.killPlan(a);
  plan.forEach((k, i) => {
    const vp = k.victim.person, kp = k.killer && k.killer.person;
    if (!vp || rm.person(vp.slot) !== vp) return;            // gone since the race
    const killerSlot = kp && rm.person(kp.slot) === kp ? kp.slot : null;
    queueKill(vp.slot, killerSlot, 1.0 + i * CONFIG.KILL_CASCADE_TICKS / 64);
  });
  log(`${a.track.id} over (${result.reason}): ${r.slice(0, 3).map((c) => c.name).join(', ')}; ${plan.length} deaths credited`);
}

function handleRoundEvents() {
  for (const e of rm.events) {
    switch (e.type) {
      case 'arenaBuilt': onArenaBuilt(e.arena); break;
      case 'afkWarn': if (!e.person.bot) sub(e.person.slot, 'MOVE OR YOU WILL BE MARKED AFK', 5); break;
      case 'afk': if (!e.person.bot) { center(e.person.slot, 'AFK', 3, 'red'); log(`${e.person.name} marked AFK`); } break;
      case 'roundOver': endRace(); break;
      case 'ballot': {
        // the top places of a race that just ended vote the next track
        for (const v of e.ballot.voters.values()) if (!v.pe.bot) sub(v.pe.slot, 'VOTE THE NEXT TRACK: W / S  (YOUR VOTE COUNTS X' + v.weight + ')', 8);
        break;
      }
    }
  }
  rm.events.length = 0;
}

// ---------------------------------------------------------------- HUD text
function standingsFor(a, now) {
  let rows = standingsCache.get(a.index);
  if (rows && now < rows.at + CONFIG.STANDINGS_PERIOD) return rows.list;
  const list = a.ranking.slice(0, 8).map((c, i) => ({
    slot: c.slot, team: c.team,
    text: `${i + 1}  ${c.name.slice(0, 13).toUpperCase()}${c.state === 'gone' || c.state === 'finished' ? '  FIN' : c.state === 'wrecked' ? '  OUT' : c.state === 'withdrawn' || c.state === 'dnf' ? '  DNF' : ''}`,
  }));
  standingsCache.set(a.index, { at: now, list });
  return list;
}

// the live team score (all arenas): refreshed with the standings
let tallyAt = -1, tally = { t: 0, ct: 0 };
function liveTally(now) {
  if (now >= tallyAt) { const p = rm.teamPoints(true); tally = { t: p[2], ct: p[3] }; tallyAt = now + CONFIG.STANDINGS_PERIOD; }
  return tally;
}

function raceInfo(pe, car, a, now, spectating) {
  // (rows = the arena's shared standings list; the HUD marks the row whose slot is info.me)
  const info = { rows: standingsFor(a, now), me: car.slot, spectating, tally: liveTally(now), clock: arenaHud(a).clock, vote: voteFor(pe, a) };
  const cm = timed(centerMsgs, pe.slot, now);
  if (cm) { info.center = cm.text; info.centerCls = cm.cls; }
  else if (a.state === 'grid' && a.countdown > 3 * TICRATE) info.center = '';
  else if (car.wrongWayFlag && car.state === 'racing') { info.center = 'WRONG WAY'; info.centerCls = 'red'; }
  else if (car.offLine && car.state === 'racing') { info.center = 'MISSED CHECKPOINT'; info.centerCls = 'red'; }
  const sm = timed(subMsgs, pe.slot, now);
  if (sm) info.sub = sm.text;
  else if (spectating) info.sub = 'WATCHING ' + car.name.slice(0, 12).toUpperCase() + '  M1/M2 NEXT  E ARENA  R CAR';
  // (the turbo start - gas on the third beep - is a secret: nothing on screen gives it away)
  else if (a.state === 'grid') info.sub = 'YOU START ' + ordinal((car.gridPos || 0) + 1) + ' OF ' + a.order.length + (a.countdown > 3 * TICRATE ? '  -  LIGHTS IN ' + Math.ceil(a.countdown / TICRATE - 3) : '  -  NO ATTACKS FOR ' + Math.round(RULES.attackLock) + ' SECONDS');
  else if (pe.afk) info.sub = 'AFK - TYPE !BACK TO RACE NEXT ROUND';
  const bm = timed(botMsgs, pe.slot, now);
  info.msg = bm ? bm.text : '';
  const fl = flashes.get(pe.slot);
  info.flash = fl && now < fl.until ? fl.cls : null;
  return info;
}

let lobbyCycle = 0;
// the CS2 round clock, read once per tick however many lobby screens show it
let remTick = -1, remValue;
function roundRemaining() {
  if (remTick !== tickNo || !inThink) { remValue = guard('remaining', () => Instance.GetRoundRemainingTime()); remTick = inThink ? tickNo : -1; }
  return remValue;
}
// the ballot a player sees: their own (top places of a finished race), else the one of the race they are looking at
function voteFor(pe, a) {
  const own = rm.ballotOf(pe);
  if (own) return own;
  const b = a && a.ballot;
  return b && b.voters.size ? b : null;
}

function lobbyInfo(pe, now) {
  const info = { line1: '', line2: '', line3: '', vote: voteFor(pe, null) };
  const car = CARS[pe.carChoice] || CARS.hornet;
  info.line2 = 'YOUR CAR: ' + car.name + ' - ' + car.perk + (pe.pickShown ? '  (A / D, E TO CONFIRM)' : '  (R TO CHANGE)');
  const nextT = rm.upcoming[0];
  if (phase === 'running') {
    const rem = roundRemaining();
    const left = rem === undefined ? 0 : Math.max(0, Math.ceil(rem - CONFIG.ROUND_SLACK));
    info.line1 = `RACE ON - YOU ARE IN THE NEXT ONE  (${Math.floor(left / 60)}:${String(left % 60).padStart(2, '0')} AT MOST)`;
    const a = rm.arenas[lobbyCycle % Math.max(1, rm.arenas.length)];
    if (a && a.ranking[0]) info.line3 = `${a.track.title}: ${a.state === 'over' ? 'RESULTS' : 'LEADER ' + a.ranking[0].name.slice(0, 16).toUpperCase()}`;
  } else if (phase === 'ending') {
    info.line1 = 'RACE OVER - NEXT ONE SOON';
    const vt = rm.voteLeader();
    if (vt) info.line3 = `VOTES SO FAR: ${vt.title}${recordText(vt)}`;
    else if (nextT) info.line3 = `NEXT: ${nextT.title}${recordText(nextT)}`;
  } else {
    let waiting = 0;
    for (const p of rm.people.values()) if ((p.csTeam === 2 || p.csTeam === 3) && !(p.afk && !p.bot)) waiting++;
    const need = CONFIG.MIN_PLAYERS - waiting;
    if (need > 0) { info.line1 = `WAITING FOR PLAYERS ${waiting}/${CONFIG.MIN_PLAYERS}`; info.blink1 = true; }
    else {
      const t = Math.max(0, Math.ceil(startAt - now));
      info.line1 = Instance.IsFreezePeriod() ? 'THE RACE STARTS AFTER FREEZE TIME' : t > 0 ? `THE RACE STARTS IN ${t}` : 'STARTING...';
    }
    const vt = rm.voteLeader();
    if (vt) info.line3 = `VOTED: ${vt.title} - ${vt.laps} LAPS${recordText(vt)}`;
    else if (nextT) info.line3 = `NEXT: ${nextT.title} - ${nextT.laps} LAPS${recordText(nextT)}`;
  }
  if (pe.afk) info.line3 = 'AFK - TYPE !BACK OR PRESS A KEY TO RACE';
  else if (pe.csTeam !== 2 && pe.csTeam !== 3) info.line3 = 'JOIN T OR CT TO RACE';
  // (!help shows the help panel itself; the answers to chat commands like !cam go on the bottom line here too)
  const bm = timed(botMsgs, pe.slot, now);
  info.msg = bm ? bm.text : '';
  return info;
}

// engine sound: short overlapping hum grains on every human-driven car, the band (pitch) following its speed
const humNext = new Map();
function engineHum(now) {
  for (const [a, view] of views) {
    if (a.state !== 'racing' && a.state !== 'grid') continue;
    for (const car of a.order) {
      if (car.isBot || !car.visible || car.state === 'wrecked') continue;
      const due = humNext.get(car.slot) || 0;
      if (now < due) continue;
      const k = car.speed / Math.max(1, car.spec.maxSpeed);
      const band = car.boosting || car.padTimer > 0 ? 3 : k < 0.15 ? 0 : k < 0.55 ? 1 : 2;
      humNext.set(car.slot, now + 0.38);
      playSound(view, 'hum' + band, car);
    }
  }
}

// ---------------------------------------------------------------- per tick
function lobbyFrame(now, dt) {
  // keys and the camera every tick (a tap of A / D lasts a tick or two), the HUD 20 times a second
  const hudNow = now >= lobbyNext;
  if (hudNow) { lobbyNext = now + 0.05; lobbyCycle = Math.floor(now / 3); }
  const a0 = rm.arenas[0];
  for (const pe of rm.people.values()) {
    if (pe.bot) { if (!parked.has(pe.slot) && verifyTurn(pe.slot)) park(pe.slot); continue; }   // bots stand frozen in the booth too
    const pk = park(pe.slot, verifyTurn(pe.slot));
    if (!pk) { if (hudNow) guard('nopawnhud', () => { hudOptions(pe.slot, pe); hudLobby(pe.slot, lobbyInfo(pe, now)); hudPicker(pe.slot, pe, false); }); continue; }
    if (!playerCall('lobbyinput', pe.slot, () => { const a = pickerInput(pe, pk), b = voteInput(pe, pk); if (a || b) rm.markActive(pe.slot); })) continue;   // pawn gone
    if (hudNow) guard('lobbyhud', () => { hudOptions(pe.slot, pe); hudLobby(pe.slot, lobbyInfo(pe, now)); hudPicker(pe.slot, pe, pickerAuto(pe) || pickerOpen(pe, now)); });
    // nothing to look at yet: a slow look around the first track from above
    if (!a0) playerCall('lobbycam', pe.slot, () => {
      if (!pk.cam) return;
      // the track of the next race, the whole of it in view: a slow circle high above its edge, looking in
      const T = rm.upcoming[0] || rm.tracks[0];
      const off = T.off || [0, 0, 0];
      const ang = now * 0.06;
      const r = T.ext * 0.95, h = T.ext * 0.6;
      const zc = (T.zmin + T.zmax) / 2;
      const pitch = deg(Math.atan2(h + T.zmax - zc, r));
      if (pk.camMode !== CustomCameraMode.CONTROLLED) { pk.cam.SetMode(CustomCameraMode.CONTROLLED); pk.camMode = CustomCameraMode.CONTROLLED; }
      pk.cam.Move({ position: { x: off[0] + Math.cos(ang) * r, y: off[1] + Math.sin(ang) * r, z: off[2] + T.zmax + h }, angles: { pitch, yaw: deg(ang + Math.PI), roll: 0 } });
    });
  }
}

// music: one piece at a time for everyone (lobby loop, race loop, results fanfare), retriggered at the end of each loop
let musCur = null, musAt = 0;
function musicFrame(now) {
  if (!CONFIG.MUSIC) { if (musCur) { musicStop(musCur); musCur = null; } return; }
  const race = rm.roundNumber % 2 === 0 && MUSIC_LEN.mus_race2 ? 'mus_race2' : 'mus_race';   // the two race loops take turns
  const want = phase === 'lobby' ? 'mus_lobby' : phase === 'running' ? race : 'mus_results';
  if (want !== musCur) {
    if (musCur) musicStop(musCur);
    musCur = want; musAt = now + (MUSIC_LEN[want] || 20);
    musicStart(want);
  } else if (now >= musAt - 0.008 && want !== 'mus_results') {
    musAt += MUSIC_LEN[want] || 20;
    if (musAt < now) musAt = now + (MUSIC_LEN[want] || 20);
    musicStart(want);
  }
}
function musicStart(name) { const e = soundEnt(name); if (e) Instance.EntFireAtTarget({ target: e, input: 'StartSound' }); }
function musicStop(name) { const e = soundEnt(name); if (e) Instance.EntFireAtTarget({ target: e, input: 'StopSound' }); }

function frame(dt) {
  const now = gameTime();
  guard('music', () => musicFrame(now));
  soundsThisTick = 0;
  spawnBudget = CONFIG.SPAWN_BUDGET;
  scanPeople(false);
  if (phase === 'lobby') {
    lobbyFrame(now, dt);
    if (now >= startAt && !Instance.IsFreezePeriod()) startRace();
    return;
  }
  if (phase === 'ending' && !roundEndSeen && now - endedAt > CONFIG.ROUND_END_WAIT) {
    // CS2 didn't end the round (warmup, or something blocked FireWinCondition): carry on with the next race
    log(Instance.IsWarmupPeriod() ? 'warmup: next race without a CS2 round change' : 'WARNING: the CS2 round did not end after the race - starting the next race anyway');
    cleanupRound(false);
    startAt = now + 3;
    return;
  }
  if (phase !== 'running' && phase !== 'ending') return;
  // input
  for (const pe of rm.people.values()) {
    if (pe.bot) { if (!parked.has(pe.slot) && verifyTurn(pe.slot)) park(pe.slot); continue; }
    const pk = park(pe.slot, verifyTurn(pe.slot));
    if (!pk) continue;
    playerCall('input', pe.slot, () => playerInput(pe, pk));
  }
  // the race, one step per server tick
  acc += dt;
  let ran = 0;
  while (acc >= DT && ran < 3) {
    acc -= DT; ran++;
    rm.tic();
    for (const a of rm.arenas) handleArenaEvents(a, now);
    handleRoundEvents();
  }
  if (acc > 3 * DT) acc = 0;
  processKills(now);
  for (const v of views.values()) guard('render', () => v.update(now));
  if (CONFIG.ENGINE_HUM) guard('hum', () => engineHum(now));
  // cameras and HUD
  for (const pe of rm.people.values()) {
    if (pe.bot) continue;
    const pk = parked.get(pe.slot);
    if (!pk) {
      // no pawn (CS2 spectator team, not joined yet, or dead): no camera of ours, but the HUD still shows - the race
      // HUD (results board included) for someone who raced and is waiting for CS2's respawn, else the status lines
      guard('nopawnhud', () => {
        hudOptions(pe.slot, pe);
        if (pe.car && pe.arena && views.has(pe.arena)) { if (hudTurn(pe.slot)) hudRace(pe.slot, pe.car, pe.arena, raceInfo(pe, pe.car, pe.arena, now, false)); }
        else hudLobby(pe.slot, lobbyInfo(pe, now));
        hudPicker(pe.slot, pe, false);
      });
      continue;
    }
    hudOptions(pe.slot, pe);
    playerCall('view', pe.slot, () => {
      if (pe.status === 'racing' && pe.car && pe.arena) {
        const a = pe.arena, v = views.get(a);
        if (!v) return;
        if (a.state === 'over') placeOverviewCamera(pk, a, v);
        else if (a.state === 'grid' && CONFIG.FLYOVER && a.countdown > CONFIG.FLYOVER_CUT * TICRATE) placeFlyover(pk, a, v, now);
        else placeCamera(pk, pe.car, v, dt, pe.cam, pe.tilt);
        if (!hudTurn(pe.slot)) return;
        hudRace(pe.slot, pe.car, a, raceInfo(pe, pe.car, a, now, false));
        // the small cards on the grid (first race, or after !car); the big ones only after !car once the car is done
        if (a.state === 'grid') hudPicker(pe.slot, pe, a.countdown > 3 * TICRATE && (pickerAuto(pe) || pickerOpen(pe, now)) ? 'mini' : false);
        else hudPicker(pe.slot, pe, !pe.car.racing && pickerOpen(pe, now));
      } else {
        // placed in an arena that is still being built (one arena per tic): wait for it - turning them into
        // spectators here used to leave them out of their race (the second arena came up empty of humans)
        if (pe.status === 'planned') { hudLobby(pe.slot, lobbyInfo(pe, now)); return; }
        // spectators and people waiting for the next race
        if (!pe.spec) rm.spectate(pe);
        const a = rm.arenas[pe.spec ? pe.spec.arena : 0], v = a && views.get(a);
        const t = a && pe.spec && pe.spec.target !== null ? a.cars.get(pe.spec.target) : null;
        if (!a || !v) { hudLobby(pe.slot, lobbyInfo(pe, now)); hudPicker(pe.slot, pe, pickerAuto(pe) || pickerOpen(pe, now)); return; }
        if (t && t.visible && a.state !== 'over') { placeCamera(pk, t, v, dt, pe.cam, pe.tilt); if (hudTurn(pe.slot)) hudRace(pe.slot, t, a, raceInfo(pe, t, a, now, true)); }
        else { placeOverviewCamera(pk, a, v); if (pe.car && pe.arena === a) hudRace(pe.slot, pe.car, a, raceInfo(pe, pe.car, a, now, false)); else { hudLobby(pe.slot, lobbyInfo(pe, now)); } rm.fixSpectate(pe, 0); }
        // watchers (results included) see the cards only after asking for them with !car
        hudPicker(pe.slot, pe, pe.status !== 'racing' && pickerOpen(pe, now));
      }
    });
  }
}

// one player's keys for this tick (racing, on the grid, watching)
function playerInput(pe, pk) {
  if (pe.status === 'racing' && pe.car && pe.arena) {
    if (pe.car.state === 'grid') { if (pe.arena.countdown > 3 * TICRATE ? pickerInput(pe, pk) : sampleInput(pe.slot, pe.car, pk)) rm.markActive(pe.slot); }
    else if (pe.car.racing) { pe.raced = true; if (sampleInput(pe.slot, pe.car, pk)) rm.markActive(pe.slot); }
    else {
      // wrecked / finished / withdrawn: watch the others after a moment (!car works from here on); W / S vote
      pickerInput(pe, pk);
      voteInput(pe, pk);
      if (pe.car.stateTime > RULES.wreckShow || pe.car.state === 'gone' || pe.car.state === 'withdrawn') {
        pe.status = 'spectating'; pe.spec = { arena: pe.arena.index, target: null }; rm.fixSpectate(pe, 0);
      }
    }
  } else if (pe.status === 'spectating' || pe.status === 'none') {
    const a = spectatorInput(pe, pk), b = voteInput(pe, pk);
    if (a || b) rm.markActive(pe.slot);
  }
}

// something failed for one player: if their pawn or camera went away between checks, forget the parked entry so the
// next tick looks the pawn up again (returns false: skip the rest of this player's tick); any other error is said
// once per kind and the player carries on
function playerCall(what, slot, fn) {
  try { fn(); return true; } catch (err) {
    const pk = parked.get(slot);
    if (pk && (!live(pk.pawn) || (pk.cam && !live(pk.cam)))) { parked.delete(slot); return false; }   // expected: no message
    const k = what + ':' + String(err);
    if (!warned.has(k)) { warned.add(k); log('error in ' + what + ' (slot ' + slot + '): ' + err + (err && err.stack ? '\n' + err.stack : '')); }
    return true;
  }
}

// HUDs refresh at half the tick rate, half the players on even ticks and half on odd (cameras still move every tick)
let tickNo = 0;
function hudTurn(slot) { return ((slot + tickNo) & 1) === 0; }

function think() {
  const t0 = perfOn ? clockMs() : 0;
  tickNo++;
  hudBudget = CONFIG.HUD_BUDGET;
  const now = Instance.GetGameTime();
  tickTime = now; inThink = true;
  flushSays();
  let dt = now - lastTime;
  lastTime = now;
  if (!(dt > 0) || dt > 0.25) dt = DT;
  if (ready) guard('frame', () => frame(dt));
  inThink = false;
  if (perfOn) perfTick(clockMs() - t0, now);
  Instance.SetNextThink(now);
}

// script time per server tick, said in the console once a minute while a race runs (to judge a server's load)
const perfClock = typeof performance !== 'undefined' && performance && typeof performance.now === 'function' ? performance : null;
const perfOn = CONFIG.PERF_LOG && (!!perfClock || typeof Date !== 'undefined');
function clockMs() { return perfClock ? perfClock.now() : Date.now(); }
let perfSum = 0, perfMax = 0, perfN = 0, perfAt = 0;
function perfTick(ms, now) {
  if (phase !== 'running') { perfN = 0; perfSum = 0; perfMax = 0; perfAt = now + 60; return; }
  perfSum += ms; perfN++; if (ms > perfMax) perfMax = ms;
  if (now < perfAt) return;
  let humans = 0, cars = 0;
  for (const pe of rm.people.values()) if (!pe.bot) humans++;
  for (const a of rm.arenas) cars += a.order.length;
  log(`script time: avg ${(perfSum / Math.max(1, perfN)).toFixed(2)} ms, max ${perfMax.toFixed(1)} ms per server tick (${humans} players, ${cars} cars, ${rm.arenas.length} arenas)${perfClock ? '' : ' (1 ms clock)'}`);
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
  startAt = gameTime() + CONFIG.START_DELAY;
  cvars(['mp_ignore_round_win_conditions 1']);
}));
Instance.OnRoundEnd((ev) => guard('roundend', () => {
  if (phase === 'running') endRace();
  roundEndSeen = true;
  const w = ev && ev.winningTeam;
  log(`CS2 round ended: ${w === 2 ? 'T win' : w === 3 ? 'CT win' : 'no winner (team ' + w + ')'}, reason ${ev ? ev.reason : '?'}`);
}));
Instance.OnBeginRoundRestart(() => guard('restart', () => cleanupRound(true)));
Instance.OnPlayerDisconnect(({ playerSlot }) => guard('disconnect', () => dropPerson(playerSlot)));
Instance.OnPlayerActivate(() => guard('activate', () => scanPeople(true)));
Instance.OnPlayerTeamChanged(({ player }) => guard('team', () => {
  const slot = slotOfEntity(player);
  if (slot === undefined) return;
  const pe = rm.person(slot);
  if (pe && pe.status === 'racing') { rm.leaveArena(pe, 'team change'); unpark(slot); }
  for (let i = pendingKills.length - 1; i >= 0; i--) if (pendingKills[i].victim === slot) pendingKills.splice(i, 1);
  scanPeople(true);
}));
Instance.OnPlayerReset(({ player }) => guard('reset', () => {
  const slot = slotOfEntity(player);
  if (slot === undefined) return;
  if (awaitRespawn.delete(slot)) respawnFailures = 0;
  const pe = rm.person(slot);
  if (!pe) return;
  // a fresh pawn (spawn, or the respawn after a scripted kill): park it again and keep the camera
  parked.delete(slot); noPawnUntil.delete(slot);
  park(slot, true);
  if (phase === 'running' && pe.status === 'none') rm.lateJoin(pe);
}));
Instance.OnPlayerKill(({ player }) => guard('cskilled', () => {
  const slot = slotOfEntity(player);
  if (slot === undefined) return;
  parked.delete(slot);
  const pe = rm.person(slot);
  if (!pe || allowDamage.has(slot)) return;
  // killed by something outside the race (admin slay): the car withdraws
  if (pe.status === 'racing' && pe.car && pe.car.racing && pe.arena) { rm.leaveArena(pe, 'slain'); rm.spectate(pe, pe.arena); }
}));
Instance.OnModifyPlayerDamage((event) => {
  const slot = slotOfEntity(event.player);
  if (slot !== undefined && allowDamage.has(slot)) return;
  return { abort: true };
});
Instance.OnPlayerChat(({ player, text }) => guard('chat', () => {
  if (!CONFIG.CHAT_COMMANDS || !player) return;
  const slot = player.GetPlayerSlot();
  const pe = rm.person(slot);
  let t = text.trim().toLowerCase();
  if (t.startsWith('/')) t = '!' + t.slice(1);
  if (!player.IsBot()) sayHold();
  if (!t.startsWith('!') || !pe) return;
  log(`chat command "${t}" from slot ${slot}`);
  const word = t.split(/\s+/)[0];
  if (word === '!car' || word === '!cars' || word === '!pick') {
    // !car 1-4 (or a name) picks straight away; !car on its own brings the picker up for a few seconds
    const arg = t.slice(word.length).trim();
    const n = parseInt(arg, 10);
    const key = arg ? CAR_KEYS[n - 1] || CAR_KEYS.find((k) => k === arg || CARS[k].name.toLowerCase() === arg) : undefined;
    const driving = pe.car && pe.arena && (pe.car.racing || (pe.car.state === 'grid' && pe.arena.countdown <= 3 * TICRATE));
    if (key) {
      pe.picked = true; pe.pickUntil = 0;
      const car = CARS[key];
      if (!rm.setCar(pe, key)) bottom(slot, 'TOO LATE TO SWAP - ' + car.name + ' NEXT RACE', 3);
      else bottom(slot, (driving ? 'NEXT RACE: ' : 'YOUR CAR: ') + car.name + ' - ' + car.perk, 3);
    } else if (arg || driving) {
      // a name we don't know, or the hands are on the wheel (A / D steer): the numbers instead
      bottom(slot, '1 HORNET  2 METEOR  3 COMET  4 BASTION', 5);
    } else {
      pe.pickUntil = gameTime() + CONFIG.PICK_SHOW;
    }
  } else if (t === '!cam' || t.startsWith('!cam ')) {
    const names = Object.keys(CONFIG.CAMERAS);
    const want = t.slice(4).trim();
    const cur = pe.cam || CONFIG.CAM_DEFAULT;
    pe.cam = names.includes(want) ? want : names[(names.indexOf(cur) + 1) % names.length];
    bottom(slot, 'CAMERA: ' + pe.cam.toUpperCase() + '  (!CAM ' + names.join('/').toUpperCase() + ')', 3);
  } else if (t === '!tilt') {
    pe.tilt = pe.tilt === false;
    bottom(slot, 'CAMERA TILT ' + (pe.tilt === false ? 'OFF' : 'ON') + '   (!TILT)', 3);
  } else if (t === '!crt') {
    pe.crt = pe.crt === false;
    bottom(slot, 'SCANLINES ' + (pe.crt ? 'ON' : 'OFF') + '   (!CRT)', 3);
  } else if (t === '!music') {
    bottom(slot, CONFIG.MUSIC ? 'MUSIC: ON FOR THE WHOLE SERVER' : 'MUSIC IS OFF ON THIS SERVER', 4);
  } else if (t === '!spec' || t === '!spectate') {
    if (pe.status === 'racing' && pe.arena) { const a = pe.arena; rm.leaveArena(pe, 'spectate'); rm.spectate(pe, a); }
  } else if (t === '!afk') {
    pe.afk = true;
    if (pe.status === 'racing' && pe.arena) { const a = pe.arena; rm.leaveArena(pe, 'afk'); rm.spectate(pe, a); }
  } else if (t === '!back') {
    pe.afk = false; rm.markActive(slot);
  } else if (word === '!vote' || word === '!v') {
    // !vote 1-4 (or a track name) for the top places of a finished race; !vote alone says how
    const b = rm.ballotOf(pe);
    const arg = t.slice(word.length).trim();
    if (!b) bottom(slot, CONFIG.VOTES ? 'ONLY THE TOP 3 OF A RACE VOTE' : 'TRACK VOTES ARE OFF ON THIS SERVER', 3);
    else if (!arg) bottom(slot, 'W / S OR !VOTE 1-' + b.tracks.length + ' (THE BOX ON THE LEFT)', 4);
    else {
      const n = parseInt(arg, 10);
      const id = n >= 1 && n <= b.tracks.length ? b.tracks[n - 1]
        : b.tracks.find((tid) => tid.startsWith(arg) || trackTitle(tid).toLowerCase().startsWith(arg));
      const got = id ? rm.vote(pe, id) : null;
      bottom(slot, got ? 'YOUR VOTE: ' + trackTitle(got) : 'NOT ON THE BALLOT - !VOTE 1-' + b.tracks.length, 3);
    }
  } else if (word === '!shade' || word === '!color' || word === '!colour') {
    // !shade cycles your colour (reds on T, blues on CT); !shade 1-6 or a name picks one
    const side = pe.csTeam === 3 ? 'ct' : 't';
    const list = SHADES[side];
    const arg = t.slice(word.length).trim();
    const n = parseInt(arg, 10);
    let k = (pe.shade || 0);
    if (!arg) k = (k + 1) % list.length;
    else if (n >= 1 && n <= list.length) k = n - 1;
    else { const f = list.findIndex((sh) => sh.name.toLowerCase().startsWith(arg)); if (f >= 0) k = f; else { bottom(slot, '!SHADE 1-' + list.length + ': ' + list.map((sh) => sh.name).join(' ').slice(0, 26), 5); return; } }
    pe.shade = k;
    if (pe.car) pe.car.shade = k;                 // the car changes colour straight away
    bottom(slot, 'SHADE: ' + list[k].name + ' (' + (k + 1) + '/' + list.length + ')  !SHADE 1-' + list.length, 3);
  } else if (t === '!race' || t === '!help' || t === '!spr') {
    pe.helpUntil = gameTime() + CONFIG.HELP_SECONDS;      // hudOptions takes it down again
    hudHelp(slot, true);
  }
}));
