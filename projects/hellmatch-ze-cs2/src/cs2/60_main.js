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
const allowDamage = new Set();
const specEdges = new Map();      // slot -> { next, prev, arena }
let realKillsBroken = false;
let respawnFailures = 0;          // in a row; three means CS2 isn't respawning and real kills are switched off
const centerMsgs = new Map();     // arena -> { text, until }

function buildCfg() {
  const c = JSON.parse(JSON.stringify(DEFAULT_CFG));
  const Z = CONFIG.ZE;
  c.minPlayersToStart = CONFIG.MIN_PLAYERS;
  c.afkWarnTics = CONFIG.AFK_WARN * TICRATE; c.afkKickTics = CONFIG.AFK_KICK * TICRATE;
  c.staggerArenas = true;
  c.arena.altdeath = CONFIG.ITEMS_RESPAWN;
  c.arena.freelookAim = CONFIG.FREELOOK_AIM;
  c.arena.botSkill = CONFIG.BOT_SKILL;
  c.arena.zeKnockback = Z.KNOCKBACK;
  Object.assign(c.ze, {
    map: Z.MAP, cap: Z.CAP, killDelayTics: Z.KILL_DELAY_TICS, drawWindowTics: Z.DRAW_WINDOW_TICS,
    zombieRespawnTics: Math.round(Z.ZOMBIE_RESPAWN * TICRATE), timeLimitTics: Z.TIME_LIMIT * TICRATE,
    aiBase: Z.AI_BASE, aiPerHuman: Z.AI_PER_HUMAN, classes: Z.CLASSES.slice(), holdScore: Z.HOLD_SCORE, escapeScore: Z.ESCAPE_SCORE,
    aiDamage: Z.AI_DAMAGE, zDamage: Z.ZOMBIE_DAMAGE, zHp: Z.ZOMBIE_HP, bossTakeover: Z.BOSS_TAKEOVER,
  });
  return c;
}

function cvars(list) { if (CONFIG.APPLY_CVARS) for (const c of list) Console.ServerCommand(c); }

function init() {
  rm = new ZeRound(LEVELS, buildCfg());
  findPropTemplate();
  hud();
  scanPeople(true);
  cvars(CONFIG.CVARS_ALWAYS);
  cvars(CONFIG.CVARS_ROUND);
  ready = true;
  lastTime = Instance.GetGameTime();
  startAt = lastTime + 1;
  log(`v${VERSION} ready: ${rm.zeLevels().length} ZE levels (${LEVELS.length} placements), ${Object.keys(SPRITE_MODELS).length} sprite models, HUD ${hud() ? "on" : "MISSING"}, prop template ${findPropTemplate() ? "on" : "MISSING"}${statsOn ? ", server stats on (mgstat)" : ""}`);
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
  for (const cmd of CONFIG.CLIENT_CVARS || []) guard("clientcvar", () => Console.ClientCommand(slot, cmd));
}

function dropPerson(slot) {
  statFlush(slot);   // before a newcomer can take the slot
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
}

// ---------------------------------------------------------------- round flow
function startDoomRound() {
  scanPeople(true);
  if (!rm.startRound()) {
    startAt = Instance.GetGameTime() + 5;
    if (!rm.zeLevels().length) warnOnce("nozelevels", "no ZE levels in the level data (records with a ze sidecar and side t/c)");
    return;
  }
  phase = "running";
  guard("music", () => musicStart("level", rm.base.id));
  cvars(["mp_ignore_round_win_conditions 1"]);
  // everyone respawns in CS2 after a scripted kill (a human comes back as a zombie, a zombie as a zombie); every kill
  // between players is across T and CT (a zombie keeps its CS2 team), so teammates are never enemies
  cvars(CONFIG.RESPAWN_CVARS_ON);
  cvars(["mp_teammates_are_enemies 0"]);
  guard("roundtime", () => GameRules.SetRoundRemainingTime(CONFIG.ROUND_SECONDS + CONFIG.ROUND_SLACK));
  pendingKills.length = 0;
  const n = { 2: 0, 3: 0 };
  for (const it of rm.plan) n[it.side] = it.grp.length;
  sayAll(`HELLMATCH ZE: ${rm.base.title} - T ${n[2]} vs CT ${n[3]}${rm.solo ? " (one side: survive the horde)" : ""}`);
  log(`round ${rm.roundNumber}: ze, ${rm.base.id} T ${n[2]} CT ${n[3]}${rm.solo ? " solo" : ""}`);
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
  guard("music", musicStop);
  statFlushAll();
  const r = rm.zeResult;
  sayAll("Round over - " + (r ? r.text : "no result"));
  cvars(["mp_ignore_round_win_conditions 0"]);
  const reason = r && r.winner === 2 ? CSRoundEndReason.TERRORISTS_WIN : r && r.winner === 3 ? CSRoundEndReason.CTS_WIN : CSRoundEndReason.DRAW;
  if (live(Entities.FindByName(CONFIG.MAP_PARAMS)[0])) {
    log(`FireWinCondition ${reason} (${r ? r.why + ": " + r.text : "no result"})`);
    guard("wincond", () => Entities.FireInput({ name: CONFIG.MAP_PARAMS, input: "FireWinCondition", value: reason }));
  } else {
    warnOnce("nomapparams", "no " + CONFIG.MAP_PARAMS + " entity: rounds end on the clock as draws");
    guard("endround", () => GameRules.SetRoundRemainingTime(1));
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
  pendingKills.length = 0;
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
// plugins; SERVER_STATS hands monster kills to a server plugin that can)
function monsterScore(arena, e) {
  const slot = e.killer.slot;
  const pts = e.boss ? CONFIG.MONSTER_SCORE_BOSS : CONFIG.MONSTER_SCORE;
  if (pts && !GameRules.IsWarmupPeriod()) {
    const c = controllerOf(slot);
    if (c) guard("monsterscore", () => c.AddScore(pts));
  }
}

// ---------------------------------------------------------------- stats for a server plugin (CONFIG.SERVER_STATS)
// "mgstat <slot> <stat> [n]": the plugin adds n (default 1) to that player's count for the server's current mode.
// pve_kills (every monster kill, Boss Battle or monsters loose in deathmatch), boss_kills (a boss, also a pve kill),
// lms_wins (the last man standing). Monster kills are added up per player and sent once a second (SERVER_STATS_EVERY),
// and before the player's slot is freed and at the end of the round. Bots and warmup don't count.
// PvP kills and deaths are real CS2 kills, so the plugin gets those from game events. Each goes out as "echo mgstat ...": a
// dedicated server drops any command a Workshop map sends that isn't on Valve's allow list, and echo is on it (the plugin reads echo lines).
let statsOn = !!CONFIG.SERVER_STATS;
const statPending = new Map();   // slot -> { pve, boss }
let statNext = 0;
function statSend(slot, stat, n) {
  const cmd = "echo mgstat " + Math.floor(slot) + " " + String(stat).replace(/[^a-z0-9_]/gi, "") + (n > 1 ? " " + Math.floor(n) : "");
  guard("mgstat", () => Console.ServerCommand(cmd));
}
function statHuman(slot) {
  if (!statsOn || slot === undefined || slot === null || slot < 0 || GameRules.IsWarmupPeriod()) return false;
  const c = controllerOf(slot);
  return !!c && !c.IsBot();
}
function statMonster(slot, boss) {
  if (!statHuman(slot)) return;
  let s = statPending.get(slot);
  if (!s) { s = { pve: 0, boss: 0 }; statPending.set(slot, s); }
  s.pve++;
  if (boss) s.boss++;
}
function statFlush(slot) {
  const s = statPending.get(slot);
  if (!s) return;
  statPending.delete(slot);
  if (s.pve) statSend(slot, "pve_kills", s.pve);
  if (s.boss) statSend(slot, "boss_kills", s.boss);
}
function statFlushAll() { for (const slot of Array.from(statPending.keys())) statFlush(slot); }
function statTick(now) {
  if (!statPending.size || now < statNext) return;
  statNext = now + (CONFIG.SERVER_STATS_EVERY || 1);
  statFlushAll();
}
function statsSwitch(on) {
  if (statsOn === on) return;
  if (!on) statFlushAll();
  statsOn = on;
  log(`server stats ${on ? "on" : "off"} (mgstat commands for a stats plugin)`);
}

// ZE kill credit (ZE_DESIGN.md 1.6): a human killed by a zombie player -> that player's CS2 kill (always across T/CT);
// by an AI zombie, the level or a teammate's telefrag -> a world kill. A zombie player killed by a human -> the human's
// kill; by the world -> a world kill. Every death is a CS2 kill after KILL_DELAY; CS2 then respawns the pawn, which
// opens the gate for the next Doom body (the human's zombie, or the zombie's next one).
function onDoomKill(arena, e) {
  const v = e.victim, k = e.killer;
  for (const p of [v, k]) if (p) { p.message = e.text; p.messageTime = arena.leveltime; }
  if (CONFIG.REAL_KILLS && GameRules.IsWarmupPeriod()) warnOnce("warmupkills", "warmup: kills are not sent to the CS2 scoreboard until warmup ends");
  if (!CONFIG.REAL_KILLS || realKillsBroken || GameRules.IsWarmupPeriod()) {
    if (CONFIG.ADD_SCORE && k && k !== v && !!k.zclass !== !!v.zclass) { const c = controllerOf(k.slot); if (c) guard("addscore", () => c.AddScore(1)); }
    return;
  }
  const credited = k && k !== v && e.kind !== "monster" && !!k.zclass !== !!v.zclass;   // only zombie <-> human kills
  v.respawnGate = false;
  pendingKills.push({ at: Instance.GetGameTime() + CONFIG.KILL_DELAY, victim: v.slot, killer: credited ? k.slot : null, player: v, since: Instance.GetGameTime() });
}

// the Doom player that a pending kill belongs to now (a dead human has become a zombie in the other arena meanwhile)
function killOwner(k) {
  const pe = rm.person(k.victim);
  if (!pe || !pe.player) return null;
  if (pe.player === k.player) return pe.player;
  return k.player.zclass ? null : (pe.zeRole === "zombie" && pe.player.zclass ? pe.player : null);
}

function processKills(now) {
  for (let i = pendingKills.length - 1; i >= 0; i--) {
    const k = pendingKills[i];
    if (k.done) {
      // waiting for CS2 to respawn the pawn
      if (now - k.at > 8) {
        const owner = killOwner(k);
        if (owner) owner.respawnGate = true;
        k.player.respawnGate = true;
        pendingKills.splice(i, 1);
        const pe = rm.person(k.victim), c = controllerOf(k.victim);
        const still = owner && pe && pe.status === "playing" && pe.arena && !pe.arena.finished && c && c.IsConnected();
        if (!still) continue;
        respawnFailures++;
        log(`CS2 did not respawn ${pe.name} within 8 s after a scripted kill (${respawnFailures} in a row)`);
        if (respawnFailures >= 3 && !realKillsBroken) { realKillsBroken = true; log("CS2 is not respawning killed players - check mp_respawn_on_death_t/ct. Real kills are off until the map changes."); }
      }
      continue;
    }
    if (now < k.at) continue;
    const owner = killOwner(k);
    if (!owner) { k.player.respawnGate = true; pendingKills.splice(i, 1); continue; }
    if (csKill(k.victim, k.killer)) { k.done = true; parked.delete(k.victim); }
    else { owner.respawnGate = true; k.player.respawnGate = true; pendingKills.splice(i, 1); }
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
      // zombie escape: stages, messages, the boss, score
      case "zeStage":
        if (e.phase === "start") centerMsgs.set(a, { text: e.name, until: Instance.GetGameTime() + 3 });
        else if (!e.escape) centerMsgs.set(a, { text: "STAGE CLEAR", until: Instance.GetGameTime() + 2 });
        log(`${a.mapId}: stage ${e.phase} ${e.name}${e.escape ? " (escaped " + e.escaped + ")" : ""}`);
        break;
      case "zeMsg":
        for (const p of a.players.values()) if (!p.zclass) { p.message = e.text; p.messageTime = a.leveltime; }
        break;
      case "zeBoss":
        centerMsgs.set(a, { text: "BOSS INCOMING", until: Instance.GetGameTime() + 4 });
        sayAll(`${ZE_SIDE_NAME[a.zeSide]}: the guardian is here - ${e.name.toLowerCase()}`);
        guard("music", () => musicBoss());
        break;
      case "zeMusic": guard("music", () => (e.id === "boss" ? musicBoss() : musicStart(e.id || "level", rm.base && rm.base.id))); break;
      // player bosses: the offer (zombie players see "PRESS E TO BECOME THE BOSS" while a.ze.offer is up), the takeover, the AI taking it back
      case "zeBossOptIn":
        e.player.message = "BOSS REQUESTED - MOST HUMAN KILLS WINS"; e.player.messageTime = a.leveltime;
        break;
      case "zeBossTaken": {
        const pe = e.player.person;
        if (pe) pe.zeBossUntil = Instance.GetGameTime() + 5;
        centerMsgs.set(a, { text: "THE BOSS IS A PLAYER!", until: Instance.GetGameTime() + 3 });
        sayAll(`${ZE_SIDE_NAME[a.zeSide]}: ${e.player.name} is the ${e.name.toLowerCase()}`);
        log(`${a.mapId}: ${e.player.name} took over the boss (${e.why})`);
        break;
      }
      case "zeBossBack":
        if (e.player) { e.player.message = "THE AI TOOK THE BOSS BACK"; e.player.messageTime = a.leveltime; }
        if (e.player && e.player.person) e.player.person.zeBossUntil = 0;
        log(`${a.mapId}: the AI took the boss back from ${e.player ? e.player.name : "?"} (${e.why})`);
        break;
      case "zeScore":
        if (!GameRules.IsWarmupPeriod()) for (const p of e.players) { const c = controllerOf(p.slot); if (c && e.points) guard("zescore", () => c.AddScore(e.points)); }
        break;
      case "monsterKill":
        if (e.boss && e.killer) { e.killer.message = `YOU KILLED THE ${String(e.name).toUpperCase()}`; e.killer.messageTime = a.leveltime; }
        if (e.killer) { monsterScore(a, e); statMonster(e.killer.slot, e.boss); }
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
      case "zeSwap":
        // the camera keeps looking at the corpse until the zombie body appears; the HUD says what happened
        if (e.person.player) { e.person.player.message = "YOU DIED - YOU RISE AS A ZOMBIE"; e.person.player.messageTime = e.to.leveltime; }
        dlog(`${e.person.name}: human of ${ZE_SIDE_NAME[e.person.zeSide]} -> zombie in ${e.to.mapId}`);
        break;
      case "zeZombie":
        if (e.first && e.person) e.person.zeBannerUntil = Instance.GetGameTime() + 4;
        if (e.person) e.person.zeClassUntil = Instance.GetGameTime() + 2.5;
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
function zeClock(sec) { sec = Math.max(0, sec); return Math.floor(sec / 60) + ":" + String(sec % 60).padStart(2, "0"); }
// a text bar for the HUD font: [=====-----] (width cells)
const ZE_BAR = 20;
function zeBar(frac) { const n = Math.max(0, Math.min(ZE_BAR, Math.round(frac * ZE_BAR))); return "[" + "=".repeat(n) + "-".repeat(ZE_BAR - n) + "]"; }

function arenaLines(a, now) {
  let m = arenaLinesMemo.get(a);
  if (m && m.serial === thinkSerial) return m;
  const ze = a.ze;
  let line1 = "", line2 = "", bar = "";
  if (ze) {
    const st = ze.stageInfo();
    line1 = st.name + (st.frac >= 0 && st.left > 0 ? " " + st.left + "S" : "");
    const left = Math.ceil((ze.timeLimitTics - Math.max(0, a.time - rm.cfg.countdownTics)) / TICRATE);
    line2 = (rm.solo ? `${ZE_SIDE_NAME[a.zeSide]} ${rm.humansAlive(a.zeSide)} ALIVE` : `T ${rm.humansAlive(2)} ALIVE  CT ${rm.humansAlive(3)} ALIVE`) + "  " + zeClock(left);
    if (st.boss) bar = (st.boss.name.length > 14 ? "BOSS" : st.boss.name) + " " + zeBar(st.boss.frac);
    else if (st.frac >= 0) bar = st.holding ? (st.escape ? "ESCAPE " : "HOLD ") + zeBar(st.frac) : "ZONE EMPTY - TIMER PAUSED";
  }
  let center = "";
  const cm = centerMsgs.get(a);
  if (a.countdown > 0) center = String(Math.ceil(a.countdown / TICRATE));
  else if (cm && now < cm.until) center = cm.text;
  else if (a.finished && a.result) center = hudResult(a.result);
  if (!m) { m = { serial: 0, line1: "", line2: "", center: "", bar: "" }; arenaLinesMemo.set(a, m); }
  m.serial = thinkSerial; m.line1 = line1; m.line2 = line2; m.center = center; m.bar = bar;
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
  // bottom line (spec) and the line above it (spec2): the stage / boss bar, a zombie's class and ability, spectators
  let spec = "", spec2 = al.bar, msg = "";
  const me = !spectating && pe.player && pe.player.arena === a ? pe.player : null;
  if (spectating) {
    const t = a.players.get(pe.spec.target);
    spec2 = t ? "SPECTATING " + hudName(t.name) : "SPECTATING";
    if (pe.afk) spec = "AFK - TYPE !BACK TO PLAY";
    else if (pe.csTeam !== 2 && pe.csTeam !== 3) spec = "JOIN T OR CT TO PLAY";
    else spec = rm.canJoin(pe) ? "TYPE !BACK TO PLAY" : "YOU PLAY NEXT ROUND";
  } else if (pe.afk) spec = "AFK - TYPE !BACK TO PLAY";
  else if (me && me.zclass) {
    const c = ZCLASS[me.zclass];
    const rising = me.playerstate !== "live" || !me.mo;
    const offer = a.ze && a.ze.offer && a.ze.bossEligible(me);
    const recent = me.message && a.leveltime - me.messageTime < 4 * TICRATE;   // who killed them stays readable
    // while dead / rising: the class of the next body, R (or right click) cycles it (F goes back)
    if (rising) { spec = "CLASS: " + c.name + "  [R] NEXT"; if (!recent) msg = "RISING AS A ZOMBIE..."; }
    else spec = c.name + "  " + c.ability + (me.zcd > 0 ? " " + (me.zcd / TICRATE).toFixed(1) + "S" : " READY");
    if (pe.zeBannerUntil > now) msg = "YOU ARE A ZOMBIE - HUNT THE " + ZE_SIDE_NAME[a.zeSide] + " HUMANS";
    else if (pe.zeClassUntil > now && !rising && !c.boss) msg = "YOU ARE " + (c.key === "IMP" ? "AN " : "A ") + c.name + " - MOUSE2 / R: " + c.ability;
    if (c.boss && pe.zeBossUntil > now) msg = c.melee ? "YOU ARE THE BOSS - MOUSE1 " + c.atkName + "  MOUSE2/R " + c.ability : "YOU ARE THE BOSS - MOUSE1/MOUSE2/R: " + c.ability;
    // a new boss is up for takeover: the first E near a zombie spawn takes it, else most human kills among who asked
    if (offer && !a.ze.offer.opted.has(me)) msg = "PRESS E TO BECOME THE BOSS";
  } else if (me && a.countdown > 0) spec = "HUMANS: HOLD THE ZONES, ESCAPE";
  // !help: controls on the message line and chat commands at the bottom, over whatever was there
  if (pe.helpUntil > now) {
    msg = me && me.zclass ? "MOUSE1 ATTACK  MOUSE2/R ABILITY  E USE" : "R NEXT  F PREV  E USE  SHIFT WALK";
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
    const rem = guard("remaining", () => GameRules.GetRoundRemainingTime());
    const left = rem === undefined ? 0 : Math.max(0, Math.ceil(rem - CONFIG.ROUND_SLACK));
    info.line1 = `ROUND ${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")} LEFT`;
    if (rm.base) info.line2 = (rm.solo ? rm.base.title : `${rm.base.title}: T ${rm.humansAlive(2)} CT ${rm.humansAlive(3)}`).slice(0, 32);
    if (pe.afk) info.spec = "AFK - TYPE !BACK TO PLAY";
    else if (pe.csTeam !== 2 && pe.csTeam !== 3) info.spec = "JOIN T OR CT TO PLAY";
    else info.spec = rm.canJoin(pe) ? "JOINING..." : "YOU PLAY NEXT ROUND";
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
      info.line1 = GameRules.IsFreezePeriod() ? "ROUND STARTS AFTER FREEZE TIME" : t > 0 ? `ROUND STARTS IN ${t}` : "ROUND STARTING...";
    }
    if (pe.afk) info.spec = "AFK - TYPE !BACK TO PLAY";
    else if (pe.csTeam !== 2 && pe.csTeam !== 3) info.spec = "JOIN T OR CT TO PLAY";
  }
  if (pe.helpUntil > now) { info.center = "R NEXT  F PREV  E USE"; info.spec = "SHIFT WALK !SPEC !AFK !BACK !HUD"; info.line2 = "MUSIC: MAIN MENU MUSIC SLIDER"; }
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
    if (pe.bot || parked.has(pe.slot)) continue;
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
  if (phase === "lobby") {
    if (now >= startAt && !GameRules.IsFreezePeriod()) startDoomRound();
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
  const remaining = guard("remaining", () => GameRules.GetRoundRemainingTime());
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
  // who looks at each arena (players in it, spectators watching it): things far from all of them aren't drawn
  for (const v of views.values()) v.viewers.length = 0;
  for (const pe of rm.people.values()) {
    if (pe.bot || !parked.has(pe.slot)) continue;
    let a = null, t = null;
    if (pe.status === "playing" && pe.arena && pe.player) { a = pe.arena; t = pe.player; }
    else if (pe.status === "spectating" && pe.spec) { a = rm.arenas[pe.spec.arena]; t = a && a.players.get(pe.spec.target); }
    const v = a && views.get(a);
    if (v && t && t.mo) v.viewers.push(t.mo);
  }
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
    if (ready) guard("stats", () => statTick(now));
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
  cvars(CONFIG.CVARS_ROUND);
}));
Instance.OnRoundEnd((ev) => guard("roundend", () => {
  if (phase === "running") endDoomRound();
  const w = ev && ev.winningTeam;
  log(`CS2 round ended: ${w === 2 ? "T win" : w === 3 ? "CT win" : "no winner (team " + w + ")"}, reason ${ev ? ev.reason : "?"}`);
}));
Instance.OnBeginRoundRestart(() => guard("restart", () => cleanupRound(true)));
Instance.OnPlayerDisconnect(({ playerSlot }) => guard("disconnect", () => dropPerson(playerSlot)));
// a stats plugin switches SERVER_STATS on (or off) for this map: RunScriptInput "mgstat_on" / "mgstat_off" on fdm_script
Instance.OnScriptInput("mgstat_on", () => guard("stats", () => statsSwitch(true)));
Instance.OnScriptInput("mgstat_off", () => guard("stats", () => statsSwitch(false)));
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
  // ZE: a human or zombie who changes CS2 team leaves (a human counts as lost for the old side) and comes back for the
  // new side by the late-join rules (in practice a zombie hunting the other side's humans)
  const wrongSide = pe.arena && pe.zeSide !== undefined && pe.zeSide !== pe.csTeam;
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
