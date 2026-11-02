// ---------------------------------------------------------------- main loop and CS2 round flow

let rm = null;
const views = new Map();          // Arena -> ArenaView
let ready = false;
let lastTime = 0, acc = 0;
let phase = "lobby";              // lobby | running | ending
let startAt = 0;                  // game time when we may start the next Doom round
let lastPeopleScan = 0;
let nextPlaceCheck = 0;           // game time of the next check for people left standing in the lobby mid-round
const pendingKills = [];          // respawn modes: { at, victim, killer }
const elimKills = [];             // elimination modes: applied when the round ends
const allowDamage = new Set();
const specEdges = new Map();      // slot -> { next, prev, arena }
let realKillsBroken = false;
let respawnFailures = 0;          // in a row; three means CS2 isn't respawning and real kills are switched off
const centerMsgs = new Map();     // arena -> { text, until }

function buildCfg() {
  const c = JSON.parse(JSON.stringify(DEFAULT_CFG));
  c.modeWeights = Object.assign({}, CONFIG.MODE_WEIGHTS);
  c.ffaFrags = CONFIG.FFA_FRAGS; c.tdmFrags = CONFIG.TDM_FRAGS;
  c.arenaMax = CONFIG.ARENA_MAX; c.arenaMin = CONFIG.ARENA_MIN; c.maxArenas = CONFIG.MAX_ARENAS;
  c.minPlayersToStart = CONFIG.MIN_PLAYERS;
  c.friendlyFire = CONFIG.FRIENDLY_FIRE;
  c.mapBlacklist = CONFIG.MAP_BLACKLIST.slice(); c.bossMapBlacklist = (CONFIG.BOSS_MAP_BLACKLIST || []).slice();
  c.afkWarnTics = CONFIG.AFK_WARN * TICRATE; c.afkKickTics = CONFIG.AFK_KICK * TICRATE;
  c.elimTimeLimitTics = CONFIG.ELIM_SECONDS * TICRATE;
  c.finishGraceTics = CONFIG.FINISH_GRACE * TICRATE;
  c.loadoutChance = CONFIG.LOADOUT_CHANCE; c.loadouts = Object.assign({}, CONFIG.START_WEAPONS);
  c.monsterChance = CONFIG.MONSTER_CHANCE; c.monsters = Object.assign({}, CONFIG.MONSTERS);
  c.bossTimeLimitTics = CONFIG.BOSS_SECONDS * TICRATE;
  c.staggerArenas = true;
  c.replaceBots = CONFIG.REPLACE_BOTS;
  c.arenaMin = CONFIG.ARENA_MIN;
  c.arena.altdeath = CONFIG.ITEMS_RESPAWN;
  c.arena.freelookAim = CONFIG.FREELOOK_AIM;
  c.arena.botSkill = CONFIG.BOT_SKILL;
  // with real kills the CS2 respawn opens the gate; this is only the fallback
  c.autoRespawnTics = CONFIG.REAL_KILLS ? 8 * TICRATE : 3 * TICRATE;
  return c;
}

function cvars(list) { if (CONFIG.APPLY_CVARS) for (const c of list) Instance.ServerCommand(c); }

function init() {
  rm = new RoundManager(LEVELS, buildCfg());
  findPropTemplate();
  hud();
  scanPeople(true);
  cvars(CONFIG.CVARS_ALWAYS);
  ready = true;
  lastTime = Instance.GetGameTime();
  startAt = lastTime + 1;
  log(`v${VERSION} ready: ${LEVELS.length} levels, ${Object.keys(SPRITE_MODELS).length} sprite models, HUD ${hud() ? "on" : "MISSING"}, prop template ${findPropTemplate() ? "on" : "MISSING"}`);
}

function scanPeople(force) {
  const now = Instance.GetGameTime();
  if (!force && now - lastPeopleScan < 1) return;
  lastPeopleScan = now;
  const seen = new Set();
  for (const c of Instance.GetAllPlayerControllers()) {
    if (!c || !c.IsConnected()) continue;
    const slot = c.GetPlayerSlot();
    seen.add(slot);
    const bot = c.IsBot();
    if (bot && !CONFIG.CS2_BOTS_PLAY) continue;
    if (!bot && !rm.person(slot)) clientSettings(slot);
    rm.addPerson(slot, c.GetPlayerName(), c.GetTeamNumber(), bot);
  }
  for (const slot of Array.from(rm.people.keys())) if (!seen.has(slot)) dropPerson(slot);
}

// client settings asked of each player once when they arrive (CS2 only accepts the ones a server may set; others
// are ignored with a console note on the player's side)
function clientSettings(slot) {
  for (const cmd of CONFIG.CLIENT_CVARS || []) guard("clientcvar", () => Instance.ClientCommand(slot, cmd));
}

function dropPerson(slot) {
  voteDrop(slot);
  rm.removePerson(slot);
  parked.delete(slot);
  hudReset(slot);
  specEdges.delete(slot);
  forgetKills(slot);
}

// someone left or changed team: their pending deaths are dropped, and kills they made go to the world
// (a newcomer can take the same slot within a second and must not get the credit)
function forgetKills(slot) {
  for (let i = pendingKills.length - 1; i >= 0; i--) {
    const k = pendingKills[i];
    if (k.victim === slot) { if (k.player) k.player.respawnGate = true; pendingKills.splice(i, 1); }
    else if (k.killer === slot) k.killer = null;
  }
  for (let i = elimKills.length - 1; i >= 0; i--) {
    if (elimKills[i].victim === slot) elimKills.splice(i, 1);
    else if (elimKills[i].killer === slot) elimKills[i].killer = null;
  }
}

// ---------------------------------------------------------------- round flow
function startDoomRound() {
  scanPeople(true);
  if (!rm.startRound(voteTake())) { startAt = Instance.GetGameTime() + 5; return; }
  phase = "running";
  const respawn = MODES[rm.modeKey].respawn;
  // Boss Battle has its own pool (the boss-level tracks), when the map has them
  const pool = MODES[rm.modeKey].coop && MUSIC_TRACKS.some((t) => t.pool === "boss") ? "boss" : respawn ? "long" : "short";
  guard("music", () => musicStart(pool));
  cvars(["mp_ignore_round_win_conditions 1"]);
  // one-life rounds keep CS2 respawning on when bots can be replaced: Doom deaths there only reach CS2 at the end
  // of the round, and it gives someone joining mid-round a body so they can take over a bot's marine
  cvars(respawn || CONFIG.REPLACE_BOTS ? CONFIG.RESPAWN_CVARS_ON : CONFIG.RESPAWN_CVARS_OFF);
  // any arena without teams: same-side kills there must not count as teamkills
  cvars([rm.plan.every((it) => MODES[it.mk].teams) ? "mp_teammates_are_enemies 0" : "mp_teammates_are_enemies 1"]);
  guard("roundtime", () => Instance.SetRoundRemainingTime(CONFIG.ROUND_SECONDS + CONFIG.ROUND_SLACK));
  pendingKills.length = 0; elimKills.length = 0;
  // the arenas themselves are built one per Doom tic (see arenaBuilt) so the server doesn't hitch
  const desc = rm.plan.map((it) => `${it.L.title} (${it.grp.length}${it.loadout ? ", " + LOADOUTS[it.loadout].name : ""}${it.monsters ? ", MONSTERS" : ""})`).join(", ");
  sayAll(`HELLMATCH: ${MODES[rm.modeKey].name} - ${desc}`);
  log(`round ${rm.roundNumber}: ${rm.modeKey}, arenas ${rm.plan.map((it) => it.mk + ":" + it.grp.length + (it.loadout ? "+" + it.loadout : "") + (it.monsters ? "+monsters" : "")).join(" ")}`);
}

function onArenaBuilt(a) {
  views.set(a, new ArenaView(a));
  centerMsgs.set(a, { text: MODES[a.modeKey].name, until: Instance.GetGameTime() + 3 });
  for (const p of a.players.values()) {
    const pe = p.person;
    if (!pe || pe.bot && !CONFIG.CS2_BOTS_PLAY) continue;
    if (park(pe.slot) && p.mo) faceView(pe.slot, p.mo.angle);
  }
}

function endDoomRound() {
  if (phase !== "running") return;
  phase = "ending";
  guard("vote", () => voteStart(Instance.GetGameTime()));
  guard("music", musicStop);
  // elimination kills go to CS2 now, in the order they happened
  if (CONFIG.REAL_KILLS && !Instance.IsWarmupPeriod()) for (const k of elimKills) csKill(k.victim, k.killer);
  elimKills.length = 0;
  guard("podium", monsterPodium);
  const lines = rm.arenas.map((a) => `${a.mapTitle}: ${a.result ? a.result.text : "-"}`);
  sayAll("Round over - " + lines.join(" | "));
  cvars(["mp_ignore_round_win_conditions 0"]);
  // the CS2 round winner: the side that won more arenas (a free-for-all arena goes to its winner's side)
  const wins = { 2: 0, 3: 0 };
  for (const a of rm.arenas) {
    const r = a.result;
    if (!r) continue;
    if (r.coop) { if (r.won && r.sides) { if (r.sides[2] > r.sides[3]) wins[2]++; else if (r.sides[3] > r.sides[2]) wins[3]++; } }   // Boss Battle: the side with more monster kills
    else if (r.team !== undefined) { if (r.team === 0) wins[2]++; else if (r.team === 1) wins[3]++; }
    else if (r.player && r.player.person && wins[r.player.person.csTeam] !== undefined) wins[r.player.person.csTeam]++;
  }
  const reason = wins[2] > wins[3] ? CSRoundEndReason.TERRORISTS_WIN : wins[3] > wins[2] ? CSRoundEndReason.CTS_WIN : CSRoundEndReason.DRAW;
  if (live(Instance.FindEntityByName(CONFIG.MAP_PARAMS))) {
    log(`FireWinCondition ${reason} (arenas won: T ${wins[2]}, CT ${wins[3]})`);
    guard("wincond", () => Instance.EntFireAtName({ name: CONFIG.MAP_PARAMS, input: "FireWinCondition", value: reason }));
  } else {
    warnOnce("nomapparams", "no " + CONFIG.MAP_PARAMS + " entity: rounds end on the clock as draws");
    guard("endround", () => Instance.SetRoundRemainingTime(1));
  }
}

// Boss Battle: monster frags decide a podium per arena. The top 3 (with at least one monster frag) get real CS2 kills:
// everyone else in the arena dies credited to them, shared 50 / 30 / 20 (Space Racer's rule)
function splitShares(total, shares) {
  const sum = shares.reduce((a, b) => a + b, 0) || 1;
  const raw = shares.map((s) => total * s / sum);
  const out = raw.map((r) => Math.floor(r));
  let left = total - out.reduce((a, b) => a + b, 0);
  const order = raw.map((r, i) => [r - Math.floor(r), i]).sort((a, b) => b[0] - a[0]);
  for (let k = 0; left > 0 && k < order.length; k++, left--) out[order[k][1]]++;
  while (left > 0) { out[0]++; left--; }
  return out;
}

function monsterPodium() {
  if (!CONFIG.MONSTER_PODIUM || !CONFIG.REAL_KILLS || realKillsBroken || Instance.IsWarmupPeriod()) return;
  for (const a of rm.arenas) {
    if (!a.coop) continue;
    const ranked = Array.from(a.players.values()).filter((p) => p.person && rm.person(p.person.slot) === p.person).sort((x, y) => y.frags - x.frags);
    const podium = ranked.slice(0, 3).filter((p) => p.frags > 0);
    if (!podium.length) continue;
    const losers = ranked.filter((p) => !podium.includes(p));
    const counts = splitShares(losers.length, CONFIG.MONSTER_PODIUM_SHARES.slice(0, podium.length));
    let k = 0, done = 0;
    counts.forEach((n, i) => { for (let j = 0; j < n && k < losers.length; j++, k++) if (csKill(losers[k].person.slot, podium[i].person.slot)) done++; });
    log(`${a.mapTitle} podium (monster frags): ${podium.map((p) => p.name + " " + p.frags).join(", ")}; ${done} of ${losers.length} kills credited`);
    if (podium[0]) sayAll(`${a.mapTitle} top monster slayers: ${podium.map((p, i) => (i + 1) + ". " + p.name + " (" + p.frags + ")").join("  ")}`);
  }
}

function cleanupRound(entitiesGone) {
  guard("music", musicStop);
  for (const v of views.values()) {
    if (entitiesGone) { v.props.clear(); v.movers = []; v.anchors = null; }
    else { v.destroy(); if (v.anchors) v.anchors.release(); }
  }
  views.clear();
  for (const slot of Array.from(parked.keys())) unpark(slot);
  if (entitiesGone) { freeProps.length = 0; propTemplate = undefined; hudEnt = undefined; boothEnt = undefined; soundEnts.clear(); }
  rm.endRoundCleanup();
  rm.state = "idle";
  pendingKills.length = 0; elimKills.length = 0;
  phase = "lobby";
}

// ---------------------------------------------------------------- CS2 kills
function csKill(victimSlot, killerSlot) {
  const vp = pawnOf(victimSlot);
  if (!vp || !vp.IsAlive()) return false;
  // killer null = the killer left (world kill); killer = victim = Doom suicide
  let attacker = killerSlot === null ? undefined : killerSlot !== undefined && killerSlot !== victimSlot ? pawnOf(killerSlot) : vp;
  if (attacker && !attacker.IsAlive()) attacker = controllerOf(killerSlot) || undefined;
  allowDamage.add(victimSlot);
  guard("cskill", () => vp.TakeDamage({
    damage: 1000, attacker, inflictor: attacker,
    damageTypes: CSDamageTypes.BULLET, damageFlags: CSDamageFlags.FORCE_DEATH | CSDamageFlags.IGNORE_ARMOR,
  }));
  allowDamage.delete(victimSlot);
  const died = !live(vp) || !vp.IsAlive();
  const vc = controllerOf(victimSlot), kc = killerSlot != null && killerSlot !== victimSlot ? controllerOf(killerSlot) : undefined;
  if ((vc && !vc.IsBot()) || (kc && !kc.IsBot())) guard("killlog", () => log(`CS2 kill: ${kc ? kc.GetPlayerName() + " (team " + kc.GetTeamNumber() + ", score " + kc.GetScore() + ")" : "self/world"} -> ${vc ? vc.GetPlayerName() + " (team " + vc.GetTeamNumber() + ")" : victimSlot}${died ? "" : " BLOCKED"}`));
  if (!died) warnOnce("killblocked", "a scripted CS2 kill was blocked (plugin or damage settings?) - frags still count in the arena");
  return died;
}

// a monster kill on the CS2 scoreboard: score points with AddScore (a script can't touch the kills column or rank
// plugins; MONSTER_KILL_COMMAND hands each kill to a server plugin that can)
function monsterScore(arena, e) {
  if (!arena.coop && !CONFIG.MONSTER_SCORE_DEATHMATCH) return;
  const slot = e.killer.slot;
  const pts = e.boss ? CONFIG.MONSTER_SCORE_BOSS : CONFIG.MONSTER_SCORE;
  if (pts && !Instance.IsWarmupPeriod()) {
    const c = controllerOf(slot);
    if (c) guard("monsterscore", () => c.AddScore(pts));
  }
  if (CONFIG.MONSTER_KILL_COMMAND) {
    const cmd = CONFIG.MONSTER_KILL_COMMAND.replace("{slot}", String(slot)).replace("{boss}", e.boss ? "1" : "0").replace("{monster}", String(e.name).replace(/[^a-z ]/gi, "").replace(/ /g, "_"));
    guard("monstercmd", () => Instance.ServerCommand(cmd));
  }
}

function onDoomKill(arena, e) {
  const v = e.victim, k = e.killer;
  // obituary on the message line of the two players involved (the CS2 killfeed shows everyone)
  for (const p of [v, k]) if (p) { p.message = e.text; p.messageTime = arena.leveltime; }
  if (CONFIG.REAL_KILLS && Instance.IsWarmupPeriod()) warnOnce("warmupkills", "warmup: frags are not sent to the CS2 scoreboard until warmup ends");
  if (!CONFIG.REAL_KILLS || realKillsBroken || Instance.IsWarmupPeriod()) {
    if (CONFIG.ADD_SCORE) {
      const c = controllerOf(k ? k.slot : v.slot);
      if (c && e.kind !== "monster") guard("addscore", () => c.AddScore(k ? 1 : -1));
    }
    return;
  }
  // killed by a monster: a world kill in CS2 (no suicide penalty), as Doom counts it
  const killer = e.kind === "monster" ? null : k ? k.slot : v.slot;
  if (arena.mode.respawn) {
    v.respawnGate = false;
    pendingKills.push({ at: Instance.GetGameTime() + CONFIG.KILL_DELAY, victim: v.slot, killer, player: v, since: Instance.GetGameTime() });
  } else {
    elimKills.push({ victim: v.slot, killer });
  }
}

function processKills(now) {
  for (let i = pendingKills.length - 1; i >= 0; i--) {
    const k = pendingKills[i];
    if (k.done) {
      // waiting for CS2 to respawn the pawn
      if (now - k.at > 8) {
        k.player.respawnGate = true; pendingKills.splice(i, 1);
        // only count it when the player is still here, still in that arena and still waiting for CS2
        const pe = rm.person(k.victim), c = controllerOf(k.victim);
        const still = pe && pe.player === k.player && pe.status === "playing" && pe.arena && pe.arena.mode.respawn && !pe.arena.finished && c && c.IsConnected();
        if (!still) continue;
        respawnFailures++;
        log(`CS2 did not respawn ${pe.name} within 8 s after a scripted kill (${respawnFailures} in a row)`);
        if (respawnFailures >= 3 && !realKillsBroken) { realKillsBroken = true; log("CS2 is not respawning killed players - check mp_respawn_on_death_t/ct. Real kills are off until the map changes."); }
      }
      continue;
    }
    if (now < k.at) continue;
    const pe = rm.person(k.victim);
    if (!pe || !pe.player || pe.player !== k.player) { pendingKills.splice(i, 1); continue; }
    if (csKill(k.victim, k.killer)) { k.done = true; parked.delete(k.victim); }
    else { k.player.respawnGate = true; pendingKills.splice(i, 1); }
  }
}

// ---------------------------------------------------------------- events from the playsim
function handleArenaEvents(a) {
  const view = views.get(a);
  for (const e of a.events) {
    switch (e.type) {
      case "sound": if (view) playSound(view, e); break;
      case "localsound": if (view && e.player.mo) playSound(view, { sfx: e.sfx, mo: e.player.mo, x: e.player.mo.x, y: e.player.mo.y, z: e.player.mo.z + 40 }); break;
      case "msg": e.player.message = e.text; e.player.messageTime = a.leveltime; break;
      case "kill": onDoomKill(a, e); break;
      case "teleport": case "spawn": faceView(e.player.slot, e.angle); break;
      case "fight": centerMsgs.set(a, { text: "FIGHT!", until: Instance.GetGameTime() + 1.2 }); break;
      // Boss Battle
      case "wave": centerMsgs.set(a, { text: `WAVE ${e.wave} OF ${e.of}`, until: Instance.GetGameTime() + 3 }); break;
      case "waveCleared": centerMsgs.set(a, { text: "WAVE CLEARED", until: Instance.GetGameTime() + 3 }); break;
      case "bossWave":
        centerMsgs.set(a, { text: "BOSS INCOMING", until: Instance.GetGameTime() + 4 });
        sayAll(`${a.mapTitle}: the boss is here - ${e.name.toLowerCase()}`);
        break;
      case "bossDown": centerMsgs.set(a, { text: e.noBoss ? "WAVE CLEARED" : "BOSS DOWN!", until: Instance.GetGameTime() + 3 }); break;
      case "monsterKill":
        if (e.boss && e.killer) { e.killer.message = `YOU KILLED THE ${String(e.name).toUpperCase()}`; e.killer.messageTime = a.leveltime; }
        if (e.killer) monsterScore(a, e);
        break;
    }
  }
  a.events.length = 0;
}

function handleRoundEvents() {
  for (const e of rm.events) {
    switch (e.type) {
      case "arenaEnd":
        centerMsgs.set(e.arena, { text: hudResult(e.result), until: Instance.GetGameTime() + 4 });
        sayAll(`${e.arena.mapTitle}: ${e.result.text}`);
        break;
      case "afkWarn":
        if (e.person.player) { e.person.player.message = "MOVE OR YOU WILL BE MARKED AFK"; e.person.player.messageTime = e.person.arena ? e.person.arena.leveltime : 0; }
        break;
      case "grace":
        for (const a of rm.arenas) if (!a.finished) centerMsgs.set(a, { text: `${Math.round(e.tics / TICRATE)} SECONDS LEFT`, until: Instance.GetGameTime() + 3 });
        break;
      case "arenaBuilt":
        onArenaBuilt(e.arena);
        break;
      case "replaced":
        forgetKills(e.bot.slot);
        log(`${e.person.name} took ${e.bot.name}'s place in ${e.arena.mapTitle}`);
        break;
      case "roundOver":
        endDoomRound();
        break;
    }
  }
  rm.events.length = 0;
}

// ---------------------------------------------------------------- per-tick work
// the arena's own lines (mode and clock, score, centre message) are the same for everyone looking at that arena:
// worked out once per arena per server tick
let thinkSerial = 0;
const arenaLinesMemo = new WeakMap();   // Arena -> { serial, line1, line2, center }
function arenaLines(a, now) {
  let m = arenaLinesMemo.get(a);
  if (m && m.serial === thinkSerial) return m;
  const mode = MODES[a.modeKey];
  let line1 = mode.name;
  // clock: the elimination limit and/or the time left once another arena has finished
  let left = Infinity;
  if (!mode.respawn && rm.cfg.elimTimeLimitTics) left = Math.ceil((rm.cfg.elimTimeLimitTics - a.time) / TICRATE);
  if (a.coop && rm.cfg.bossTimeLimitTics) left = Math.ceil((rm.cfg.bossTimeLimitTics - a.time) / TICRATE);
  if (rm.graceEnd && !a.finished) left = Math.min(left, Math.ceil((rm.graceEnd - rm.time) / TICRATE));
  const clock = left === Infinity ? "" : Math.floor(Math.max(0, left) / 60) + ":" + String(Math.max(0, left) % 60).padStart(2, "0");
  if (a.coop && a.director) {
    const d = a.director;
    line1 = (d.wave >= d.cfg.waves ? "BOSS" : d.wave > 0 ? `WAVE ${d.wave} OF ${d.cfg.waves}` : "BOSS BATTLE") + (clock ? " - " + clock : "");
  } else if (a.target && clock) line1 = "FIRST TO " + a.target + " - " + clock + " LEFT";
  else if (a.target) line1 += " - FIRST TO " + a.target;
  else if (clock) line1 += " " + clock;
  let line2 = "";
  if (a.coop && a.director) {
    const d = a.director;
    line2 = d.wave >= d.cfg.waves ? `${d.left()} TO KILL` : `${d.left()} MONSTERS`;   // + the viewer's lives, in infoFor
  } else if (a.teamsActive) {
    if (a.modeKey === "elim") {
      const alive = [0, 0];
      for (const p of a.players.values()) if (!p.spectating && p.playerstate === "live") alive[p.team]++;
      line2 = `RED ${alive[0]} ALIVE  BLUE ${alive[1]} ALIVE`;
    } else line2 = `RED ${a.teamScore[0]}  BLUE ${a.teamScore[1]}`;
  } else if (a.modeKey === "lms") {
    line2 = `${Array.from(a.players.values()).filter((p) => !p.spectating && p.playerstate === "live").length} LEFT`;
  } else {
    let best = null;
    for (const p of a.players.values()) if (!best || p.frags > best.frags) best = p;
    if (best) line2 = `LEADER ${hudName(best.name)} ${best.frags}`;
  }
  let center = "";
  const cm = centerMsgs.get(a);
  if (a.countdown > 0) center = String(Math.ceil(a.countdown / TICRATE));
  else if (cm && now < cm.until) center = cm.text;
  else if (a.finished && a.result) center = hudResult(a.result);
  if (!m) { m = { serial: 0, line1: "", line2: "", center: "" }; arenaLinesMemo.set(a, m); }
  m.serial = thinkSerial; m.line1 = line1; m.line2 = line2; m.center = center;
  return m;
}

function infoFor(pe, now) {
  const spectating = pe.status === "spectating" && pe.spec;
  // a spectator sees the arena they are watching (after E / jump that can be another one than their own)
  const a = (spectating && rm.arenas[pe.spec.arena]) || pe.arena;
  if (!a) return { line1: "", line2: "", center: "", spec: "", spec2: "" };
  const al = arenaLines(a, now);
  const line1 = al.line1, center = al.center;
  let line2 = al.line2;
  if (a.coop && a.director) {
    const me = pe.player && pe.player.arena === a ? pe.player : null;
    if (me && me.lives !== undefined) line2 += `  LIVES ${Math.max(0, me.lives)}`;
  }
  // bottom line (spec) and the line above it (spec2): spectators see who they watch and how to get back in
  let spec = "", spec2 = "", msg = "";
  if (spectating) {
    const t = a.players.get(pe.spec.target);
    spec2 = t ? "SPECTATING " + hudName(t.name) : "SPECTATING";
    if (pe.afk) spec = "AFK - TYPE !BACK TO PLAY";
    else if (pe.csTeam !== 2 && pe.csTeam !== 3) spec = "JOIN T OR CT TO PLAY";
    else spec = rm.canJoin(pe) ? "TYPE !BACK TO PLAY" : "YOU PLAY NEXT ROUND";
  } else if (pe.afk) spec = "AFK - TYPE !BACK TO PLAY";
  else if (pe.player && pe.player.playerstate === "dead" && a.mode.respawn) spec = pe.player.lives !== undefined && pe.player.lives <= 0 ? "OUT OF LIVES" : "RESPAWNING...";
  else if (a.countdown > 0 && a.loadout) spec = LOADOUTS[a.loadout].name;
  // !help: controls on the message line and chat commands at the bottom, over whatever was there
  if (pe.helpUntil > now) {
    msg = "R NEXT  F PREV  E USE  SHIFT WALK";
    spec = "CHAT: !SPEC  !AFK  !BACK  !HUD";
    line2 = "MUSIC: MAIN MENU MUSIC SLIDER";
    if (spectating) spec2 = "MOUSE1/2 SWITCH PLAYER" + (rm.arenas.length > 1 ? "  E NEXT ARENA" : "");
  }
  return { line1, line2, center, spec, spec2, msg, sbar: pe.hudPos, text: pe.textSize };
}

let lobbyNext = 0, lobbyCycle = 0, lobbyWaiting = 0;   // lobbyCycle: which arena the lobby status shows (changes every 3 s)
function lobbyInfo(pe, now) {
  const info = { line1: "", line2: "", center: "", spec: "", text: pe.textSize };
  if (phase === "running") {
    const rem = guard("remaining", () => Instance.GetRoundRemainingTime());
    const left = rem === undefined ? 0 : Math.max(0, Math.ceil(rem - CONFIG.ROUND_SLACK));
    info.line1 = `ROUND ${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")} LEFT`;
    const open = rm.arenas.filter((a) => !a.finished);
    const a = rm.arenas[lobbyCycle % Math.max(1, rm.arenas.length)];
    if (a) {
      let s;
      if (a.finished) s = a.result ? hudResult(a.result) : "FINISHED";
      else if (a.teamsActive && a.modeKey !== "elim") s = `RED ${a.teamScore[0]} BLUE ${a.teamScore[1]}`;
      else s = `${Array.from(a.players.values()).filter((p) => !p.spectating).length} PLAYING`;
      info.line2 = `${a.mapTitle}: ${s}`.slice(0, 32);
    }
    if (pe.afk) info.spec = "AFK - TYPE !BACK TO PLAY";
    else if (pe.csTeam !== 2 && pe.csTeam !== 3) info.spec = "JOIN T OR CT TO PLAY";
    else info.spec = open.some((x) => x.mode.respawn) ? "JOINING..." : "YOU PLAY NEXT ROUND";
  } else if (phase === "ending") {
    info.line1 = "ROUND OVER";
    info.center = "NEXT ROUND SOON";
  } else {
    const need = CONFIG.MIN_PLAYERS - lobbyWaiting;
    if (need > 0) {
      info.line1 = `WAITING FOR PLAYERS ${lobbyWaiting}/${CONFIG.MIN_PLAYERS}`;
      info.line2 = `NEED ${need} MORE ON T OR CT`;
    } else {
      const t = Math.max(0, Math.ceil(startAt - now));
      info.line1 = Instance.IsFreezePeriod() ? "ROUND STARTS AFTER FREEZE TIME" : t > 0 ? `ROUND STARTS IN ${t}` : "ROUND STARTING...";
    }
    if (pe.afk) info.spec = "AFK - TYPE !BACK TO PLAY";
    else if (pe.csTeam !== 2 && pe.csTeam !== 3) info.spec = "JOIN T OR CT TO PLAY";
  }
  if (pe.helpUntil > now) { info.center = "R NEXT  F PREV  E USE"; info.spec = "SHIFT WALK !SPEC !AFK !BACK !HUD"; info.line2 = "MUSIC: MAIN MENU MUSIC SLIDER"; }
  if (vote && phase !== "running") voteLines(pe, now, info);   // the ballot wins over !help while it is up
  return info;
}

function lobbyHud(now) {
  if (now < lobbyNext) return;
  lobbyNext = now + 0.25;
  lobbyCycle = Math.floor(now / 3);
  lobbyWaiting = 0;
  for (const pe of rm.people.values()) if ((pe.csTeam === 2 || pe.csTeam === 3) && !(pe.afk && !pe.bot)) lobbyWaiting++;
  // when the HUD changes per tick run out (everyone redrawn after a restart, a busy ballot) the next pass carries on
  // next tick from where this one stopped, so the people late in the list aren't left with a blank screen
  const list = lobbyList; list.length = 0;
  for (const pe of rm.people.values()) list.push(pe);
  const n = list.length;
  for (let i = 0; i < n; i++) {
    const k = (lobbyResume + i) % n;
    const pe = list[k];
    if (pe.bot || (parked.has(pe.slot) && !vote)) continue;   // the ballot also goes to players still looking at their arena
    if (phase === "running" && pe.status !== "none") continue;
    if (hudBudget <= 0) { lobbyResume = k; lobbyNext = now; list.length = 0; return; }
    guard("lobbyhud", () => hudLobby(pe.slot, lobbyInfo(pe, now)));
  }
  lobbyResume = 0;
  list.length = 0;
}
const lobbyList = [];
let lobbyResume = 0;

function spectatorInput(pe, pk) {
  const pawn = pk.pawn;   // checked by the caller this tick
  let ed = specEdges.get(pe.slot);
  if (!ed) { ed = { next: false, prev: false, arena: false }; specEdges.set(pe.slot, ed); }
  if (pawn.WasInputJustPressed(CSInputs.ATTACK)) ed.next = true;
  if (pawn.WasInputJustPressed(CSInputs.ATTACK2)) ed.prev = true;
  if (pawn.WasInputJustPressed(CSInputs.USE) || pawn.WasInputJustPressed(CSInputs.JUMP)) ed.arena = true;
  if (ed.next) { rm.fixSpectate(pe, 1); ed.next = false; }
  if (ed.prev) { rm.fixSpectate(pe, -1); ed.prev = false; }
  if (ed.arena) { rm.fixSpectate(pe, "arena"); ed.arena = false; }
  const ang = pawn.GetEyeAngles();
  if (Math.abs(angleDiff(pk.lastYaw, ang.yaw)) > 2) rm.markActive(pe.slot);
  pk.lastYaw = normAngle(ang.yaw);
}

function frame(dt, now) {
  soundsThisTick = 0;
  spawnBudget = CONFIG.SPAWN_BUDGET;
  scanPeople(false);
  lobbyHud(now);
  if (vote) voteTick(now);
  if (phase === "lobby") {
    if (now >= startAt && !voteBusy(now) && !Instance.IsFreezePeriod()) startDoomRound();
    return;
  }
  if (phase !== "running") return;
  // safety net: anyone on T/CT standing in the lobby with a live pawn goes in (or watches) within a second
  if (now >= nextPlaceCheck) {
    nextPlaceCheck = now + 1;
    for (const pe of rm.people.values()) if (pe.status === "none") placeLateJoiner(pe, true);
  }
  // input for everyone in an arena. Button edges (weapon switch, spectator keys) are read every server tick so short
  // presses are never missed; held buttons, movement and view angles only on ticks where a Doom tic runs (what a
  // tic sees is the last sample before it, so the in-between reads changed nothing)
  const ticDue = acc + dt >= 1 / TICRATE;
  for (const pe of rm.people.values()) {
    if (pe.status === "playing" && pe.player && !pe.player.isBot) {
      let pk = parked.get(pe.slot);
      if (!pk || !live(pk.pawn)) pk = pe.player.respawnGate === false ? undefined : park(pe.slot);
      if (pk && sampleInput(pe.slot, pe.player, pk, ticDue, now)) rm.markActive(pe.slot);
      if (pk) applyEdges(pe.player, pk);
    } else if (pe.status === "spectating") {
      let pk = parked.get(pe.slot);
      if (!pk || !live(pk.pawn)) pk = park(pe.slot);
      if (pk) spectatorInput(pe, pk);
    } else if (pe.bot && pe.status === "playing") {
      if (!parked.has(pe.slot) && pe.player.respawnGate !== false) park(pe.slot);
    }
  }
  // Doom tics at 35 Hz
  acc += dt;
  let ran = 0;
  const remaining = guard("remaining", () => Instance.GetRoundRemainingTime());
  while (acc >= 1 / TICRATE && ran < 4) {
    acc -= 1 / TICRATE; ran++;
    rm.tic(remaining === undefined ? undefined : remaining - CONFIG.ROUND_SLACK);
    for (const a of rm.arenas) handleArenaEvents(a);
    handleRoundEvents();
    if (phase !== "running") return;
  }
  if (acc > 4 / TICRATE) acc = 0;
  const alpha = CONFIG.TICK_INTERP ? Math.min(1, acc * TICRATE) : 1;
  processKills(now);
  // world
  for (const v of views.values()) guard("render", () => v.update(alpha));
  // cameras and HUD
  for (const pe of rm.people.values()) {
    const pk = parked.get(pe.slot);
    if (!pk) continue;
    guard("view", () => {
      if (pe.status === "playing" && pe.player && pe.arena) {
        const view = { player: pe.player, self: pe.player, arenaView: views.get(pe.arena) };
        if (view.arenaView) placeCamera(pk, view, alpha, pe.player.playerstate === "dead");
        if (ran) hudPlayer(pe.slot, pe.player, pe.arena, infoFor(pe, now));
      } else if (pe.status === "spectating" && pe.spec) {
        const a = rm.arenas[pe.spec.arena];
        const t = a && a.players.get(pe.spec.target);
        if (!t || !t.mo || t.spectating) { rm.fixSpectate(pe, 0); return; }
        placeCamera(pk, { player: t, self: null, arenaView: views.get(a) }, alpha, true);
        if (ran) hudPlayer(pe.slot, t, a, infoFor(pe, now));
      }
    });
  }
}

// once a minute during a round the console shows how long the script takes per server tick (a 64-tick server has
// 15.6 ms per tick for everything)
const scriptTime = { n: 0, ms: 0, max: 0, next: 0 };
const clockMs = typeof Date !== "undefined" && typeof Date.now === "function" ? () => Date.now() : null;

let inThink = false;
function think() {
  const t0 = clockMs ? clockMs() : 0;
  inThink = true; hudValidThink = false; thinkSerial++;
  hudBudget = CONFIG.HUD_BUDGET;
  const now = Instance.GetGameTime();
  try {
    guard("say", flushSays);
    let dt = now - lastTime;
    lastTime = now;
    if (!(dt > 0) || dt > 0.25) dt = 1 / 64;
    if (ready) guard("frame", () => frame(dt, now));
    if (ready) guard("music", () => musicTick(now));
  } finally { inThink = false; hudValidThink = false; }
  if (clockMs && phase === "running") {
    const d = clockMs() - t0;
    scriptTime.n++; scriptTime.ms += d; if (d > scriptTime.max) scriptTime.max = d;
    if (!scriptTime.next) scriptTime.next = now + 60;
    else if (now >= scriptTime.next) {
      log(`script time: avg ${(scriptTime.ms / scriptTime.n).toFixed(1)} ms, max ${scriptTime.max} ms per server tick (${rm.people.size} players, ${rm.arenas.length} arenas)`);
      scriptTime.n = 0; scriptTime.ms = 0; scriptTime.max = 0; scriptTime.next = now + 60;
    }
  }
  Instance.SetNextThink(now);
}

// ---------------------------------------------------------------- CS2 hooks
Instance.SetThink(think);
Instance.OnActivate(() => { guard("init", init); Instance.SetNextThink(Instance.GetGameTime()); });
Instance.OnScriptReload({
  before: () => { guard("reload", () => cleanupRound(false)); return null; },
  after: () => { guard("init", init); Instance.SetNextThink(Instance.GetGameTime()); },
});
Instance.OnRoundStart(() => guard("roundstart", () => {
  if (phase !== "lobby") cleanupRound(true);
  startAt = Instance.GetGameTime() + 0.5;
  cvars(["mp_ignore_round_win_conditions 1"]);
}));
Instance.OnRoundEnd((ev) => guard("roundend", () => {
  if (phase === "running") endDoomRound();
  const w = ev && ev.winningTeam;
  log(`CS2 round ended: ${w === 2 ? "T win" : w === 3 ? "CT win" : "no winner (team " + w + ")"}, reason ${ev ? ev.reason : "?"}`);
}));
Instance.OnBeginRoundRestart(() => guard("restart", () => cleanupRound(true)));
Instance.OnPlayerDisconnect(({ playerSlot }) => guard("disconnect", () => dropPerson(playerSlot)));
// someone not in a game during a running round goes into one (or watches, if there's no place): their pawn is parked
function placeLateJoiner(pe, needAlive) {
  if (phase !== "running" || pe.status !== "none" || pe.afk || (pe.csTeam !== 2 && pe.csTeam !== 3)) return;
  const pawn = pawnOf(pe.slot);
  if (!pawn || (needAlive && !guard("alive", () => pawn.IsAlive()))) return;
  if (rm.lateJoin(pe)) { park(pe.slot); if (pe.player && pe.player.mo) faceView(pe.slot, pe.player.mo.angle); }
  else if (pe.status === "spectating") park(pe.slot);
}

// joining or switching team can clear the player's HUD on their screen: draw all of it again
Instance.OnPlayerActivate(({ player }) => guard("activate", () => { scanPeople(true); const s = slotOfEntity(player); if (s !== undefined) hudReset(s); }));
// CS2 sends OnPlayerReset (spawn) and OnPlayerTeamChanged for one team change in either order, so both use the
// team the player has now and only undo a place that no longer fits
Instance.OnPlayerTeamChanged(({ player }) => guard("team", () => {
  const slot = slotOfEntity(player);
  if (slot === undefined) return;
  scanPeople(true);
  hudReset(slot);
  forgetKills(slot);
  const pe = rm.person(slot);
  if (!pe) return;
  const onSide = pe.csTeam === 2 || pe.csTeam === 3;
  const wrongSide = pe.arena && pe.arena.teamsActive && pe.player && pe.player.team !== (pe.csTeam === 3 ? 1 : 0);
  if (pe.status !== "none" && (!onSide || wrongSide)) { rm.leaveArena(pe, "team change"); unpark(slot); }
  // watching only because there was no place with the old team: try again with the new one
  if (pe.status === "spectating" && !pe.arena && !pe.afk && phase === "running" && rm.canJoin(pe)) pe.status = "none";
  placeLateJoiner(pe, false);
}));
Instance.OnPlayerReset(({ player }) => guard("reset", () => {
  const slot = slotOfEntity(player);
  if (slot === undefined || phase !== "running") return;
  scanPeople(true);
  const pe = rm.person(slot);
  if (!pe) return;
  if (pe.status === "playing" && pe.player) {
    park(slot);
    const k = pendingKills.findIndex((x) => x.victim === slot && x.done);
    if (k >= 0) { pendingKills.splice(k, 1); respawnFailures = 0; }
    pe.player.respawnGate = true; pe.player.respawnNow = true;
  } else if (pe.status === "none") {
    hudReset(slot);
    placeLateJoiner(pe, false);
  }
}));
Instance.OnPlayerKill(({ player }) => guard("cskilled", () => {
  const slot = slotOfEntity(player);
  if (slot === undefined) return;
  parked.delete(slot);
  const pe = rm.person(slot);
  if (!pe || pe.status !== "playing" || !pe.player || allowDamage.has(slot)) return;
  // killed by something outside Doom (admin slay, world): kill the Doom player too
  const p = pe.player;
  if (p.playerstate === "live" && pe.arena) {
    p.respawnGate = false;
    pe.arena.run(() => damageMobj(p.mo, null, null, 10000));
  }
}));
Instance.OnModifyPlayerDamage((event) => {
  const slot = slotOfEntity(event.player);
  if (slot !== undefined && allowDamage.has(slot)) return;
  if (phase === "running" || parked.has(slot)) return { abort: true };
});
Instance.OnPlayerChat(({ player, text }) => guard("chat", () => {
  if (!CONFIG.CHAT_COMMANDS || !player) return;
  const slot = player.GetPlayerSlot();
  const pe = rm.person(slot);
  let t = text.trim().toLowerCase();
  if (t.startsWith("/")) t = "!" + t.slice(1);   // /help works the same as !help
  if (!player.IsBot()) sayHold();
  if (t.startsWith("!")) log(`chat command "${t}" from slot ${slot}`);
  if (t === "!spec" || t === "!spectate") {
    if (pe && pe.status === "playing") { const a = pe.arena; rm.leaveArena(pe, "spectate"); rm.spectate(pe, a); }
  } else if (t === "!afk") {
    if (pe) { pe.afk = true; if (pe.status === "playing") { const a = pe.arena; rm.leaveArena(pe, "afk"); rm.spectate(pe, a); } }
  } else if (t === "!back") {
    // back into a game only when there is a place now; someone knocked out of a one-life round waits for the next
    if (pe) {
      pe.afk = false; rm.markActive(slot);
      if (pe.status === "spectating" && phase === "running" && rm.canJoin(pe)) {
        pe.status = "none";
        if (rm.lateJoin(pe) && pe.player && pe.player.mo) faceView(slot, pe.player.mo.angle);
      } else if (pe.status === "none") placeLateJoiner(pe, true);   // standing in the lobby (back from AFK)
    }
  } else if (vote && vote.open && (VOTE_SHORT[t.slice(1)] || t.startsWith("!vote "))) {
    // !ffa !tdm !elim !lms !boss, or !vote <mode> (the mode's short or full name)
    const want = t.startsWith("!vote ") ? t.slice(6).trim() : t.slice(1);
    const k = VOTE_ORDER.find((m) => m === want || VOTE_SHORT[m].toLowerCase() === want || MODES[m].name.toLowerCase() === want);
    if (k) voteCast(slot, k);
  } else if (t === "!hud scores" || t === "!hud scoreboard") {
    // per player: hide the Doom HUD while the scoreboard is open
    if (pe) {
      pe.hideOnScores = !(pe.hideOnScores !== undefined ? pe.hideOnScores : CONFIG.HIDE_HUD_ON_SCOREBOARD);
      if (pe.player) { pe.player.message = "HUD UNDER SCOREBOARD: " + (pe.hideOnScores ? "HIDDEN" : "SHOWN"); pe.player.messageTime = pe.arena ? pe.arena.leveltime : 0; }
    }
  } else if (t === "!hud" || t.startsWith("!hud ")) {
    // status bar size for this player: 85% (default) -> classic (full size) -> small (65%)
    const order = ["centre", "classic", "small"];
    const alias = { center: "centre", middle: "centre", normal: "centre", full: "classic", big: "classic" };
    const want = alias[t.slice(5).trim()] || t.slice(5).trim();
    if (pe) {
      pe.hudPos = order.includes(want) ? want : order[(order.indexOf(pe.hudPos || "centre") + 1) % order.length];
      if (pe.player) { pe.player.message = "STATUS BAR: " + ({ centre: "NORMAL", classic: "CLASSIC", small: "SMALL" })[pe.hudPos] + "  (!HUD TO CHANGE)"; pe.player.messageTime = pe.arena ? pe.arena.leveltime : 0; }
    }
  } else if (t === "!text" || t.startsWith("!text ")) {
    // size of the Doom font text lines for this player: normal -> large -> huge -> small -> tiny -> normal
    const order = ["normal", "large", "huge", "small", "tiny"];
    const alias = { big: "large", bigger: "huge", default: "normal", medium: "normal", little: "small" };
    const want = alias[t.slice(6).trim()] || t.slice(6).trim();
    if (pe) {
      pe.textSize = order.includes(want) ? want : order[(order.indexOf(pe.textSize || "normal") + 1) % order.length];
      if (pe.player) { pe.player.message = "TEXT SIZE: " + pe.textSize.toUpperCase() + "  (!TEXT TO CHANGE)"; pe.player.messageTime = pe.arena ? pe.arena.leveltime : 0; }
    }
  } else if (["!help", "!controls", "!hm", "!doom", "!fdm"].includes(t)) {   // !doom / !fdm: old names, still work
    // shown only on the HUD of whoever typed it (CS2 scripts can't send a private chat line); see infoFor / lobbyInfo
    if (pe) pe.helpUntil = Instance.GetGameTime() + CONFIG.HELP_SECONDS;
  }
}));
