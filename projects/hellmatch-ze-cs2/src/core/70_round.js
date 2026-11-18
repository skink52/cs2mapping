// ===================================================================================
// Part 7: round manager - splits players into arenas, picks modes and maps, scores,
// spectating, late joiners, leavers and AFK handling. Engine-agnostic.
// ===================================================================================

const MODES = {
  ffa: { name: 'FREE FOR ALL', teams: false, respawn: true, minPlayers: 2 },
  tdm: { name: 'TEAM DEATHMATCH', teams: true, respawn: true, minPlayers: 4 },
  elim: { name: 'TEAM ELIMINATION', teams: true, respawn: false, minPlayers: 4 },
  lms: { name: 'LAST MAN STANDING', teams: false, respawn: false, minPlayers: 2 },
  boss: { name: 'BOSS BATTLE', teams: false, respawn: true, coop: true, minPlayers: 1 },
};
const TEAM_NAMES = ['RED', 'BLUE'];

// arena sizes: one arena until there are enough people for two of at least arenaMin (8), then two, then four;
// people are spread evenly over the arenas in use. 15 -> [15], 16 -> [8,8], 31 -> [16,15], 32 -> [8,8,8,8]
function arenaSizes(n, cfg) {
  const max = cfg.arenaMax, min = cfg.arenaMin || 8, maxArenas = cfg.maxArenas;
  if (n <= 0) return [];
  let count = 1;
  while (count * 2 <= maxArenas && n >= count * 2 * min) count *= 2;
  while (count < maxArenas && n > count * max) count++;
  const m = Math.min(n, max * count);
  const base = Math.floor(m / count), extra = m % count;
  return Array.from({ length: count }, (_, i) => base + (i < extra ? 1 : 0));
}

function shuffle(a) {
  for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; }
  return a;
}

class RoundManager {
  constructor(levelData, cfg) {
    this.levels = levelData;      // array of converted level records
    this.cfg = cfg;
    this.arenas = [];
    this.pending = [];
    this.state = 'idle';          // idle | running | over
    this.time = 0;                // tics since round start
    this.modeKey = null;
    this.modeHistory = [];
    this.mapHistory = [];
    this.people = new Map();      // slot -> { slot, name, csTeam, bot, arena, player, status, lastActive, afk }
    this.events = [];
    this.roundNumber = 0;
  }

  // ------------------------------------------------------------------ people
  person(slot) { return this.people.get(slot); }

  addPerson(slot, name, csTeam, bot) {
    let pe = this.people.get(slot);
    if (!pe) {
      pe = { slot, name, csTeam, bot: !!bot, arena: null, player: null, status: 'none', lastActive: this.time, afk: false, spec: null };
      this.people.set(slot, pe);
    } else { pe.name = name; pe.csTeam = csTeam; pe.bot = !!bot; }
    return pe;
  }

  removePerson(slot) {
    const pe = this.people.get(slot);
    if (!pe) return;
    this.leaveArena(pe, 'left');
    this.people.delete(slot);
    this.checkAllEnds();
  }

  markActive(slot) {
    const pe = this.people.get(slot);
    if (!pe) return;
    pe.lastActive = this.time;
    if (pe.afk) { pe.afk = false; this.events.push({ type: 'afkClear', person: pe }); }
  }

  // ------------------------------------------------------------------ round start
  // one mode for the whole round, so every arena plays the same thing and finishes on a similar clock
  pickMode(arenaSizesList, excluded) {
    const w = Object.assign({}, this.cfg.modeWeights);
    const h = this.modeHistory;
    if (h.length >= 2 && h[h.length - 1] === h[h.length - 2]) w[h[h.length - 1]] = 0;
    const smallest = Math.min(...arenaSizesList);
    for (const k of Object.keys(w)) if (smallest < MODES[k].minPlayers || (excluded && excluded.has(k))) w[k] = 0;
    let total = 0; for (const k in w) total += w[k];
    if (total <= 0) return 'ffa';
    let r = Math.random() * total;
    for (const k in w) { r -= w[k]; if (r <= 0) return k; }
    return 'ffa';
  }

  // large: Boss Battle wants room for a horde and a boss, so it picks from the bigger half of the levels (by area),
  // the biggest quarter twice as often
  pickMap(players, used, large) {
    const want = Math.max(4, players) * this.cfg.areaPerPlayer;
    const recent = this.mapHistory.slice(-this.cfg.mapRepeatGap);
    const area = (L) => (L.bb[2] - L.bb[0]) * (L.bb[3] - L.bb[1]);
    const byArea = this.levels.slice().sort((a, b) => area(b) - area(a));
    const pool = large && byArea.length >= 4 ? byArea.slice(0, Math.ceil(byArea.length / 2)) : this.levels;
    const blacklist = (this.cfg.mapBlacklist || []).concat(large ? this.cfg.bossMapBlacklist || [] : []);
    let cands = pool.filter((L) => !used.has(L.id) && !recent.includes(L.id) && !blacklist.includes(L.id));
    if (!cands.length) cands = pool.filter((L) => !used.has(L.id) && !blacklist.includes(L.id));
    if (!cands.length) cands = pool.filter((L) => !used.has(L.id));
    if (!cands.length) cands = this.levels.slice();
    if (large) {
      const quarter = new Set(byArea.slice(0, Math.ceil(byArea.length / 4)).map((L) => L.id));
      const weights = cands.map((L) => [L, quarter.has(L.id) ? 2 : 1]);
      let r = Math.random() * weights.reduce((t, [, w]) => t + w, 0);
      for (const [L, w] of weights) { r -= w; if (r <= 0) return L; }
      return cands[cands.length - 1];
    }
    cands.sort((a, b) => Math.abs(Math.log(area(a) / want)) - Math.abs(Math.log(area(b) / want)));
    const top = cands.slice(0, Math.min(5, cands.length));
    return top[Math.floor(Math.random() * top.length)];
  }

  startRound(forceMode) {
    this.endRoundCleanup();
    const eligible = [];
    for (const pe of this.people.values()) {
      if (pe.csTeam !== 2 && pe.csTeam !== 3) continue;
      if (pe.afk && !pe.bot) { pe.status = 'none'; continue; }
      if (pe.notReady) continue;
      eligible.push(pe);
    }
    this.roundNumber++;
    this.time = 0;
    if (eligible.length < this.cfg.minPlayersToStart) {
      this.state = 'idle';
      this.events.push({ type: 'notEnough', count: eligible.length });
      return false;
    }
    const sizes = arenaSizes(eligible.length, this.cfg);
    // a team mode only if every arena gets players from both sides; otherwise pick again without team modes
    const excluded = new Set();
    let modeKey, groups;
    // a list = the vote's ranking, best first: the first one that can be played now (enough players, both sides for
    // a team mode, not a third round in a row) wins; none of them -> picked at random as usual
    if (Array.isArray(forceMode)) {
      const smallest = Math.min(...sizes), h = this.modeHistory;
      for (const k of forceMode) {
        if (!MODES[k] || smallest < MODES[k].minPlayers || (h.length >= 2 && h[h.length - 1] === k && h[h.length - 2] === k)) continue;
        const g = this.splitGroups(eligible, sizes, MODES[k].teams);
        if (MODES[k].teams && !g.every((x) => x.some((p) => p.csTeam === 2) && x.some((p) => p.csTeam === 3) && x.length >= MODES[k].minPlayers)) continue;
        modeKey = k; groups = g; break;
      }
      forceMode = undefined;
    }
    if (!modeKey) for (let tries = 0; tries < 3; tries++) {
      modeKey = (tries === 0 && forceMode) || this.pickMode(sizes, excluded);
      groups = this.splitGroups(eligible, sizes, MODES[modeKey].teams);
      if (!MODES[modeKey].teams || groups.every((g) => g.some((p) => p.csTeam === 2) && g.some((p) => p.csTeam === 3) && g.length >= MODES[modeKey].minPlayers)) break;
      for (const k of Object.keys(MODES)) if (MODES[k].teams) excluded.add(k);
    }
    this.modeKey = modeKey;
    this.modeHistory.push(modeKey); if (this.modeHistory.length > 10) this.modeHistory.shift();
    this.graceEnd = 0;
    this.arenas = [];
    const plan = this.planArenas(groups, modeKey);
    this.plan = plan;
    for (const item of plan) for (const pe of item.grp) pe.status = 'planned';
    this.pending = plan.slice();
    this.state = 'running';
    // building an arena (level, players, bots) is the heavy part: CS2 builds one per tic so the server doesn't hitch
    if (!this.cfg.staggerArenas) while (this.pending.length) this.buildNext();
    this.events.push({ type: 'roundStart', mode: modeKey, plan });
    return true;
  }

  // each arena has its own small chance of a weapon start (weights in cfg.loadouts)
  pickLoadout(always) {
    const w = this.cfg.loadouts || {};
    const list = Array.isArray(w) ? w.map((k) => [k, 1]) : Object.entries(w);
    const keys = list.filter(([k, n]) => LOADOUTS[k] && n > 0);
    if (!keys.length || (!always && !(Math.random() < (this.cfg.loadoutChance || 0)))) return null;
    let r = Math.random() * keys.reduce((t, [, n]) => t + n, 0);
    for (const [k, n] of keys) { r -= n; if (r <= 0) return k; }
    return keys[0][0];
  }

  splitGroups(eligible, sizes, teams) {
    let groups;
    if (teams) {
      const ts = shuffle(eligible.filter((p) => p.csTeam === 2));
      const cts = shuffle(eligible.filter((p) => p.csTeam === 3));
      groups = sizes.map(() => []);
      // each arena gets the same share of Ts (worked out from the totals, cumulatively so rounding doesn't drift)
      const T = ts.length, N = eligible.length;
      let tLeft = ts.length, ctLeft = cts.length, cum = 0;
      sizes.forEach((sz, i) => {
        const before = Math.round(T * cum / N); cum += sz;
        let tq = i === sizes.length - 1 ? tLeft : Math.round(T * cum / N) - before;
        tq = Math.max(0, Math.min(tq, tLeft, sz));
        let cq = sz - tq;
        if (cq > ctLeft) { tq += cq - ctLeft; cq = ctLeft; }
        tq = Math.min(tq, tLeft);
        for (let k = 0; k < tq; k++) groups[i].push(ts.pop());
        for (let k = 0; k < cq; k++) groups[i].push(cts.pop());
        tLeft -= tq; ctLeft -= cq;
      });
      const rest = ts.concat(cts);
      for (const p of rest) { groups.sort((a, b) => a.length - b.length); groups[0].push(p); }
    } else {
      const all = shuffle(eligible.slice());
      groups = []; let k = 0;
      for (const sz of sizes) { groups.push(all.slice(k, k + sz)); k += sz; }
    }
    return groups;
  }

  planArenas(groups, modeKey) {
    const plan = [];
    const used = new Set();
    for (const grp of groups) {
      if (!grp.length) continue;
      let mk = modeKey;
      const tCount = grp.filter((p) => p.csTeam === 2).length, ctCount = grp.length - tCount;
      if (MODES[mk].teams && (grp.length < MODES[mk].minPlayers || !tCount || !ctCount)) mk = MODES[mk].respawn ? 'ffa' : 'lms';
      if (grp.length < 2 && mk !== 'boss') mk = 'ffa';
      const coop = !!MODES[mk].coop;
      const L = this.pickMap(grp.length, used, coop);
      used.add(L.id);
      this.mapHistory.push(L.id); if (this.mapHistory.length > 40) this.mapHistory.shift();
      // Boss Battle always starts everyone with a real weapon; the other modes roll for one and, separately, for monsters
      const loadout = coop ? (this.pickLoadout(true) || 'shotgun') : this.pickLoadout();
      const monsters = !coop && Math.random() < (this.cfg.monsterChance || 0);
      plan.push({ grp, mk, L, loadout, monsters });
    }
    return plan;
  }

  buildNext() {
    const item = this.pending.shift();
    if (!item) return null;
    const { mk, L } = item;
    // people who left (or went AFK) since the plan was made are skipped
    const grp = item.grp.filter((pe) => this.people.get(pe.slot) === pe && pe.status === 'planned');
    const arena = new Arena(this.arenas.length, Object.assign({}, this.cfg.arena));
    arena.load(L);
    arena.modeKey = mk; arena.mode = MODES[mk];
    arena.loadout = item.loadout;
    arena.teamsActive = MODES[mk].teams;
    arena.coop = !!MODES[mk].coop;
    arena.friendlyFire = this.cfg.friendlyFire;
    arena.mapId = L.id; arena.mapTitle = L.title;
    const n = item.grp.length;
    arena.target = mk === 'ffa' ? Math.min(this.cfg.ffaFrags, 6 + 2 * n) : mk === 'tdm' ? Math.min(this.cfg.tdmFrags, 4 * n) : 0;
    const mc = this.cfg.monsters || {};
    if (arena.coop) {
      arena.monsterFrags = true;
      arena.director = new MonsterDirector(arena, 'boss', { waves: mc.waves || 5, maxAlive: mc.maxAlive || 36, difficulty: mc.difficulty || 1 });
      arena.lives = mc.lives !== undefined ? mc.lives : 3;
    } else if (item.monsters) {
      // a few monsters loose in the level, sized to it
      const bb = L.bb, area = (bb[2] - bb[0]) * (bb[3] - bb[1]);
      const count = Math.max(2, Math.min(mc.roamMax || 8, 2 + Math.round(area / 300000) + (n > 8 ? 2 : 0)));
      arena.director = new MonsterDirector(arena, 'roam', { roamCount: count, maxAlive: mc.maxAlive || 36 });
    }
    arena.startTime = this.time;
    arena.countdown = this.cfg.countdownTics;
    arena.index = this.arenas.length;
    this.arenas.push(arena);
    grp.forEach((pe) => this.joinArena(pe, arena, true));
    const spots = arena.roundStartSpots(grp.map((pe) => pe.player));
    for (const pe of grp) arena.spawnPlayer(pe.player, spots.get(pe.player));
    // the round starts frozen until the countdown ends
    for (const pe of grp) pe.player.frozen = true;
    this.events.push({ type: 'arenaBuilt', arena });
    return arena;
  }

  joinArena(pe, arena, atStart) {
    const team = arena.teamsActive ? (pe.csTeam === 3 ? 1 : 0) : -1;
    const color = arena.teamsActive ? (team === 0 ? 3 : 1) : this.colorFor(arena);
    const p = arena.addPlayer(pe.slot, pe.name, team, color);
    p.person = pe; p.isBot = pe.bot;
    if (arena.coop && arena.lives !== undefined) p.lives = arena.lives;
    pe.arena = arena; pe.player = p; pe.status = 'playing'; pe.spec = null;
    pe.lastActive = this.time;
    if (!atStart) {
      arena.spawnPlayer(p);
      this.events.push({ type: 'join', person: pe, arena });
    }
    return p;
  }

  colorFor(arena) {
    const used = new Set(Array.from(arena.players.values()).map((p) => p.color));
    for (let c = 0; c < 16; c++) if (!used.has(c)) return c;
    return 0;
  }

  leaveArena(pe, why) {
    const a = pe.arena;
    if (a && pe.player) {
      const p = pe.player;
      if (p.playerstate === 'live' && !p.spectating && a.mode && !a.mode.respawn && !a.finished) {
        // leaving an elimination arena counts as eliminated
        a.events.push({ type: 'eliminated', victim: p, why });
      }
      // one life per round: whoever leaves a one-life arena can't take a bot's place until the next round
      // one life per round; Boss Battle: one entry per round (leaving and rejoining would hand out fresh lives)
      if (a.mode && (!a.mode.respawn || a.coop)) pe.outRound = this.roundNumber;
      a.removePlayer(pe.slot);
      this.events.push({ type: 'leave', person: pe, arena: a, why });
    }
    pe.arena = null; pe.player = null; pe.status = 'none'; pe.spec = null;
  }

  // arenas someone can walk into mid-round: respawn rounds with room (team arenas only for T/CT players)
  joinCandidates(pe) {
    return this.arenas.filter((a) => !a.finished && a.mode.respawn && a.players.size < this.cfg.arenaMax && !(a.coop && pe.outRound === this.roundNumber) &&
      (!a.teamsActive || pe.csTeam === 2 || pe.csTeam === 3));
  }

  // would lateJoin put this person into a game right now? (not while they are still in an arena: knocked out of a
  // one-life round, or their arena is over)
  canJoin(pe) {
    if (this.state !== 'running' || pe.arena) return false;
    return this.joinCandidates(pe).length > 0 || (!pe.bot && this.cfg.replaceBots !== false && !!this.botToReplace(pe));
  }

  lateJoin(pe) {
    if (this.state !== 'running') return false;
    if (pe.arena) return true;
    const cands = this.joinCandidates(pe);
    if (cands.length) {
      cands.sort((a, b) => a.players.size - b.players.size);
      this.joinArena(pe, cands[0], false);
      return true;
    }
    // no room (arenas full, or one-life rounds): a human takes a bot's place instead of waiting
    if (!pe.bot && this.cfg.replaceBots !== false && this.replaceBot(pe)) return true;
    this.spectate(pe);
    return false;
  }

  // the bot whose place this human would take, or null
  botToReplace(pe) {
    if (pe.csTeam !== 2 && pe.csTeam !== 3) return null;
    const team = pe.csTeam === 3 ? 1 : 0;
    const out = pe.outRound === this.roundNumber;
    let best = null, bestScore = Infinity;
    for (const a of this.arenas) {
      if (a.finished || a.countdown > 0) continue;
      if ((!a.mode.respawn || a.coop) && out) continue;               // already had their one life / entry this round
      for (const p of a.players.values()) {
        const pb = p.person;
        if (!pb || !pb.bot || p.spectating) continue;
        if (a.teamsActive && p.team !== team) continue;             // keep the teams even
        if (!a.mode.respawn && p.playerstate !== 'live') continue;  // one-life rounds: take over a living bot
        // respawn rounds: prefer a bot that is dead right now, then the one with the fewest frags
        const score = (a.mode.respawn && p.playerstate === 'dead' ? 0 : 1000) + p.frags;
        if (score < bestScore) { bestScore = score; best = { a, p, pb }; }
      }
    }
    return best;
  }

  replaceBot(pe) {
    const best = this.botToReplace(pe);
    if (!best) return false;
    const { a, p, pb } = best;
    if (a.mode.respawn) {
      a.removePlayer(pb.slot);
      pb.arena = null; pb.player = null; pb.status = 'none';
      this.spectate(pb, a);
      this.joinArena(pe, a, false);
    } else {
      // hand the bot's living marine (health, weapons, position) to the human
      a.players.delete(pb.slot);
      p.slot = pe.slot; p.name = pe.name; p.person = pe; p.isBot = false; p.bot = null;
      p.cmd.forwardmove = 0; p.cmd.sidemove = 0; p.cmd.buttons = 0;
      a.players.set(pe.slot, p);
      pe.arena = a; pe.player = p; pe.status = 'playing'; pe.spec = null; pe.lastActive = this.time;
      pb.arena = null; pb.player = null;
      this.spectate(pb, a);
    }
    pe.player.message = 'YOU TOOK ' + hudName(pb.name) + "'S PLACE";
    pe.player.messageTime = a.leveltime;
    this.events.push({ type: 'replaced', person: pe, bot: pb, arena: a });
    return true;
  }

  spectate(pe, arena) {
    pe.status = 'spectating';
    if (!pe.spec) pe.spec = { arena: arena ? arena.index : (pe.arena ? pe.arena.index : 0), target: null };
    this.fixSpectate(pe, 0);
  }

  // pick a living player to watch: dir 0 = keep if valid, 1/-1 = cycle, 'arena' = next running arena
  fixSpectate(pe, dir) {
    if (!pe.spec) pe.spec = { arena: 0, target: null };
    const running = this.arenas.filter((a) => !a.finished);
    const pool = running.length ? running : this.arenas;
    if (!pool.length) { pe.spec.target = null; return; }
    let ai = pool.findIndex((a) => a.index === pe.spec.arena);
    if (ai < 0) ai = 0;
    if (dir === 'arena') { ai = (ai + 1) % pool.length; pe.spec.target = null; dir = 0; }
    const arena = pool[ai];
    pe.spec.arena = arena.index;
    const alive = Array.from(arena.players.values()).filter((p) => !p.spectating && p.mo && !p.mo.removed);
    if (!alive.length) { pe.spec.target = null; return; }
    let i = alive.findIndex((p) => p.slot === pe.spec.target);
    if (i < 0) i = 0;
    else if (dir) i = (i + dir + alive.length) % alive.length;
    pe.spec.target = alive[i].slot;
  }

  // ------------------------------------------------------------------ per tic (35 Hz)
  tic(remainingSeconds) {
    if (this.state !== 'running') return;
    this.time++;
    if (this.pending && this.pending.length) this.buildNext();
    for (const a of this.arenas) {
      if (a.finished && a.time >= a.finishedAt + this.cfg.arenaEndHoldTics) continue;
      a.time = (a.time || 0) + 1;
      if (a.countdown > 0) {
        a.countdown--;
        if (a.countdown === 0) {
          for (const p of a.players.values()) { p.frozen = false; p.protectUntil = a.leveltime + this.cfg.arena.spawnProtectTics; }
          a.events.push({ type: 'fight' });
        }
      }
      for (const p of a.players.values()) {
        if (p.isBot) botThink(a, p);
        if (p.frozen || a.finished) { p.cmd.forwardmove = 0; p.cmd.sidemove = 0; p.cmd.buttons = 0; }
      }
      a.tic();
      if ((a.leveltime & 31) === 0) a.rescueOutside();
      this.arenaRules(a);
    }
    this.checkAfk();
    // once the first arena is done, the others get a limited time so nobody waits long
    if (this.cfg.finishGraceTics && !this.graceEnd && !this.pending.length && this.arenas.some((a) => a.finished) && this.arenas.some((a) => !a.finished)) {
      this.graceEnd = this.time + this.cfg.finishGraceTics;
      this.events.push({ type: 'grace', tics: this.cfg.finishGraceTics });
    }
    if (this.graceEnd && this.time >= this.graceEnd) this.timeUp();
    if (remainingSeconds !== undefined && remainingSeconds <= 0) this.timeUp();
    this.checkAllEnds();
  }

  arenaRules(a) {
    if (a.finished) return;
    // drain kill events for elimination bookkeeping
    for (const p of a.players.values()) {
      if (p.spectating) continue;
      if (p.playerstate === 'dead') {
        const deadFor = a.leveltime - p.deathTime;
        if (a.mode.respawn && !(p.lives !== undefined && p.lives <= 0)) {
          const gateOk = p.respawnGate !== false;
          const wantEarly = (p.respawnNow || (p.cmd.buttons & (BT_USE | BT_ATTACK))) && deadFor > this.cfg.minRespawnTics;
          if (gateOk && (wantEarly || deadFor > this.cfg.autoRespawnTics)) {
            p.respawnNow = false;
            a.spawnPlayer(p);
            this.events.push({ type: 'respawn', player: p, arena: a });
          }
        } else if (deadFor > this.cfg.elimSpectateTics) {
          a.makeSpectator(p);
          const pe = p.person;
          if (pe) { pe.status = 'spectating'; pe.spec = { arena: a.index, target: p.attacker && p.attacker.player ? p.attacker.player.slot : null }; this.fixSpectate(pe, 0); }
        }
      }
    }
    const players = Array.from(a.players.values());
    const active = players.filter((p) => !p.spectating);
    let winner = null;
    switch (a.modeKey) {
      case 'ffa': {
        const top = players.reduce((b, p) => (!b || p.frags > b.frags ? p : b), null);
        if (top && top.frags >= a.target) winner = { player: top };
        else if (active.length < 2 && this.time > this.cfg.countdownTics) winner = { player: active[0] || top, forfeit: true };
        break;
      }
      case 'tdm': {
        if (a.teamScore[0] >= a.target) winner = { team: 0 };
        else if (a.teamScore[1] >= a.target) winner = { team: 1 };
        else {
          const has = [active.some((p) => p.team === 0), active.some((p) => p.team === 1)];
          if (!has[0] || !has[1]) winner = { team: has[0] ? 0 : has[1] ? 1 : -1, forfeit: true };
        }
        break;
      }
      case 'elim': {
        const alive = [0, 0];
        for (const p of active) if (p.playerstate === 'live') alive[p.team]++;
        const pendingDead = active.some((p) => p.playerstate === 'dead');
        if (!alive[0] || !alive[1]) {
          if (!pendingDead || (!alive[0] && !alive[1])) winner = { team: alive[0] ? 0 : alive[1] ? 1 : -1 };
          else if (a.leveltime > 0) winner = { team: alive[0] ? 0 : 1 };
        }
        break;
      }
      case 'lms': {
        const alive = active.filter((p) => p.playerstate === 'live');
        if (alive.length <= 1 && this.time > this.cfg.countdownTics) winner = { player: alive[0] || null };
        break;
      }
      case 'boss': {
        const d = a.director;
        const standing = active.filter((p) => p.playerstate === 'live' || (p.lives !== undefined && p.lives > 0));
        if (d && d.won) winner = this.coopResult(a, true);
        else if (!standing.length && this.time > this.cfg.countdownTics) winner = this.coopResult(a, false);
        else if (this.cfg.bossTimeLimitTics && a.time > this.cfg.bossTimeLimitTics) winner = this.coopResult(a, false, true);
        break;
      }
    }
    // elimination rounds have their own clock so a hiding last player can't stall the round
    if (!winner && !a.mode.respawn && this.cfg.elimTimeLimitTics && a.time > this.cfg.elimTimeLimitTics) {
      if (a.teamsActive) {
        const alive = [0, 0], hp = [0, 0];
        for (const p of active) if (p.playerstate === 'live') { alive[p.team]++; hp[p.team] += p.health; }
        winner = { team: alive[0] !== alive[1] ? (alive[0] > alive[1] ? 0 : 1) : hp[0] !== hp[1] ? (hp[0] > hp[1] ? 0 : 1) : -1, timeout: true };
      } else {
        const alive = active.filter((p) => p.playerstate === 'live').sort((x, y) => y.health - x.health);
        winner = { player: alive.length && (alive.length === 1 || alive[0].health > alive[1].health) ? alive[0] : null, timeout: true };
      }
    }
    if (winner) this.finishArena(a, winner);
  }

  // Boss Battle result: the best monster hunter is named, each CS2 side's share of the kills is kept for the round credit
  coopResult(a, won, timeout) {
    const players = Array.from(a.players.values());
    const top = players.slice().sort((x, y) => y.frags - x.frags || y.stats.damage - x.stats.damage)[0] || null;
    const sides = { 2: 0, 3: 0 };
    for (const p of players) if (p.person && sides[p.person.csTeam] !== undefined) sides[p.person.csTeam] += p.frags;
    const wave = a.director ? a.director.wave : 0;
    return { coop: true, won, player: top, sides, wave, timeout: !!timeout };
  }

  finishArena(a, winner) {
    if (a.finished) return;
    a.finished = true;
    a.finishedAt = a.time;
    let text;
    if (winner.coop) text = winner.won ? 'VICTORY' + (winner.player ? ' - ' + winner.player.name + ' ' + winner.player.frags + ' KILLS' : '') : (winner.timeout ? 'TIME UP' : 'OVERRUN') + ' AT WAVE ' + winner.wave;
    else if (winner.team !== undefined) text = winner.team >= 0 ? TEAM_NAMES[winner.team] + ' TEAM WINS' : 'DRAW';
    else text = winner.player ? winner.player.name + ' WINS' : 'DRAW';
    a.result = Object.assign({ text }, winner);
    for (const p of a.players.values()) { p.frozenEnd = true; }
    this.events.push({ type: 'arenaEnd', arena: a, result: a.result });
  }

  timeUp() {
    for (const a of this.arenas) {
      if (a.finished) continue;
      const players = Array.from(a.players.values());
      if (a.coop) { this.finishArena(a, this.coopResult(a, !!(a.director && a.director.won), true)); continue; }
      if (a.mode.teams) {
        let s0, s1;
        if (a.modeKey === 'elim') {
          s0 = players.filter((p) => p.team === 0 && p.playerstate === 'live' && !p.spectating).length;
          s1 = players.filter((p) => p.team === 1 && p.playerstate === 'live' && !p.spectating).length;
        } else { s0 = a.teamScore[0]; s1 = a.teamScore[1]; }
        this.finishArena(a, { team: s0 > s1 ? 0 : s1 > s0 ? 1 : -1, timeout: true });
      } else {
        const pool = a.modeKey === 'lms' ? players.filter((p) => p.playerstate === 'live' && !p.spectating) : players;
        const top = pool.slice().sort((x, y) => y.frags - x.frags);
        const tie = top.length > 1 && top[0].frags === top[1].frags && a.modeKey === 'ffa';
        this.finishArena(a, { player: tie ? null : top[0] || null, timeout: true });
      }
    }
  }

  checkAllEnds() {
    if (this.state !== 'running') return;
    // move players of finished arenas to spectating once the hold time has passed
    for (const a of this.arenas) {
      if (!a.finished || a.time < a.finishedAt + this.cfg.arenaEndHoldTics) continue;
      for (const p of a.players.values()) {
        const pe = p.person;
        if (pe && pe.status === 'playing') { pe.status = 'spectating'; pe.spec = { arena: a.index, target: null }; this.fixSpectate(pe, 'arena'); }
      }
    }
    if (this.arenas.length && !this.pending.length && this.arenas.every((a) => a.finished)) {
      if (this.arenas.every((a) => a.time >= a.finishedAt + this.cfg.arenaEndHoldTics)) {
        this.state = 'over';
        this.events.push({ type: 'roundOver', arenas: this.arenas });
      }
    }
  }

  checkAfk() {
    if (!this.cfg.afkKickTics) return;
    for (const pe of this.people.values()) {
      if (pe.bot || pe.status !== 'playing') continue;
      const idle = this.time - pe.lastActive;
      if (idle === this.cfg.afkWarnTics) this.events.push({ type: 'afkWarn', person: pe });
      if (idle >= this.cfg.afkKickTics) {
        pe.afk = true;
        const a = pe.arena;
        this.leaveArena(pe, 'afk');
        this.events.push({ type: 'afk', person: pe });
        this.spectate(pe, a);
      }
    }
  }

  endRoundCleanup() {
    for (const pe of this.people.values()) { pe.arena = null; pe.player = null; pe.status = 'none'; pe.spec = null; }
    this.arenas = [];
    this.pending = [];
  }
}
