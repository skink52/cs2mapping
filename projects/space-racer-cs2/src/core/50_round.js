// ===================================================================================
// Part 5: round manager - who races where, car choices, locked rounds, spectating, AFK, the team result and
// the kill plan. Engine-agnostic: the CS2 side turns its events into cameras, HUD, sounds and CS2 kills.
// ===================================================================================

const DEFAULT_CFG = {
  arenaMax: 32, maxArenas: 2, minPlayers: 1, layout: '2x32', arenaMin: 8,
  afkWarnTics: 20 * TICRATE, afkKickTics: 30 * TICRATE, afkLobbyTics: 120 * TICRATE,
  countdownTics: 10 * TICRATE, finishWindow: 30, raceCap: 300, endHold: 6, laps: 0,
  botSkill: 0.5,
  podium: 3, shares: [50, 30, 20], koCredit: true, tiebreak: true,
  trackBlacklist: [], staggerArenas: true, defaultCar: 'hornet',
  // track votes: the top places of each finished race vote the next track, worth these many votes each (1st, 2nd, 3rd);
  // the choices on each ballot; whether CS2 bots in the top places vote (at random) too
  votes: true, voteWeights: [3, 2, 1], voteChoices: 4, botsVote: false,
  glowPlaces: 3,                   // the top N of each race glow in the next round
};

// a small seeded random for the ballots, so votes never touch the race's own random sequence
function ballotRandom(seed) {
  let st = (seed >>> 0) || 1;
  return () => { st = (st + 0x6D2B79F5) >>> 0; let t = st; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

// layouts: '2x32' (up to 2 arenas of 32), '4x16' (up to 4 arenas of 16), 'alternate' (switches every round)
const LAYOUTS = { '2x32': { arenaMax: 32, maxArenas: 2 }, '4x16': { arenaMax: 16, maxArenas: 4 } };
function layoutFor(cfg, round) {
  const k = cfg.layout === 'alternate' ? (round % 2 ? '2x32' : '4x16') : cfg.layout;
  return Object.assign({ key: LAYOUTS[k] ? k : '2x32' }, LAYOUTS[k] || LAYOUTS['2x32']);
}

// 2x32: 1..32 players race together, more are split into equal arenas (33 -> 17 + 16).
// 4x16: one arena up to 16, then as many as needed (each at least arenaMin when there is more than one).
function arenaSizes(n, cfg) {
  if (n <= 0) return [];
  let count = Math.max(1, Math.min(cfg.maxArenas, Math.ceil(n / cfg.arenaMax)));
  while (count > 1 && n < count * (cfg.arenaMin || 1) && Math.ceil(n / (count - 1)) <= cfg.arenaMax) count--;
  const m = Math.min(n, cfg.arenaMax * count);
  const base = Math.floor(m / count), extra = m % count;
  return Array.from({ length: count }, (_, i) => base + (i < extra ? 1 : 0));
}

// split `total` kills among the podium by percentage shares (largest remainder), e.g. 29 -> 15 / 9 / 5
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

class RoundManager {
  constructor(tracks, cfg) {
    this.tracks = tracks.map((d) => new Track(d));
    this.cfg = Object.assign({}, DEFAULT_CFG, cfg || {});
    this.people = new Map();       // slot -> person
    this.arenas = []; this.pending = []; this.plan = [];
    this.state = 'idle';           // idle | running | over
    this.clock = 0;                // tics, never reset
    this.time = 0;                 // tics since the round started
    this.roundNumber = 0;
    this.lastTracks = [];
    this.upcoming = [];
    this.events = [];
    this.ballots = [];             // this round's finished races: { arena, tracks, voters: Map(slot -> voter), ver }
    this.glow = new Map();         // person -> place (1..glowPlaces) in last round's race: their car glows this round
    this.glowNext = new Map();
    this.pickUpcoming();
  }

  // the tracks the next round will use (shown in the lobby): shuffled, none from the last round if possible
  pickUpcoming() {
    let cands = this.tracks.filter((t) => !this.lastTracks.includes(t.id) && !this.cfg.trackBlacklist.includes(t.id));
    if (cands.length < 4) cands = this.tracks.filter((t) => !this.cfg.trackBlacklist.includes(t.id));
    if (!cands.length) cands = this.tracks.slice();
    this.upcoming = shuffle(cands.slice());
  }

  // ------------------------------------------------------------------ people
  person(slot) { return this.people.get(slot); }
  addPerson(slot, name, csTeam, bot) {
    let pe = this.people.get(slot);
    if (!pe) {
      pe = { slot, name, csTeam, bot: !!bot, arena: null, car: null, status: 'none', lastActive: this.clock, afk: false, spec: null,
             carChoice: bot ? CAR_KEYS[Math.floor(rnd() * CAR_KEYS.length)] : this.cfg.defaultCar, wins: 0, races: 0, shade: 0 };
      this.people.set(slot, pe);
    } else { pe.name = name; pe.csTeam = csTeam; pe.bot = !!bot; }
    return pe;
  }
  removePerson(slot) {
    const pe = this.people.get(slot);
    if (!pe) return;
    this.leaveArena(pe, 'left');
    this.people.delete(slot);
  }
  markActive(slot) {
    const pe = this.people.get(slot);
    if (!pe) return;
    pe.lastActive = this.clock;
    if (pe.afk) { pe.afk = false; this.events.push({ type: 'afkClear', person: pe }); }
  }
  // the car picker: any time outside a race, and on the grid until the last 3 seconds
  setCar(pe, key) {
    if (!CARS[key]) return false;
    pe.carChoice = key;
    if (pe.car && pe.arena && pe.arena.state === 'grid' && pe.arena.countdown > 3 * TICRATE) pe.arena.setClass(pe.car, key);
    else if (pe.car && pe.arena && pe.arena.state === 'grid') return false;
    this.events.push({ type: 'carPick', person: pe, key });
    return true;
  }
  cycleCar(pe, dir) {
    const i = CAR_KEYS.indexOf(pe.carChoice);
    return this.setCar(pe, CAR_KEYS[((i < 0 ? 0 : i) + dir + CAR_KEYS.length) % CAR_KEYS.length]);
  }

  // ------------------------------------------------------------------ round start
  startRound() {
    this.endRoundCleanup();
    const eligible = [];
    for (const pe of this.people.values()) {
      if (pe.csTeam !== 2 && pe.csTeam !== 3) continue;
      // idle through the whole lobby and the race before it (watching counts as idle only for this long)
      if (!pe.bot && this.clock - pe.lastActive > this.cfg.afkLobbyTics) { pe.afk = true; }
      if (pe.afk && !pe.bot) { pe.status = 'none'; continue; }
      eligible.push(pe);
    }
    this.roundNumber++; this.time = 0;
    if (eligible.length < this.cfg.minPlayers) { this.state = 'idle'; this.events.push({ type: 'notEnough', count: eligible.length }); return false; }
    this.layout = layoutFor(this.cfg, this.roundNumber);
    const sizes = arenaSizes(eligible.length, Object.assign({}, this.cfg, this.layout));
    const groups = this.splitGroups(eligible, sizes);
    // tracks: what each arena's own voters chose (votes from last round's top places who race in that arena), else
    // the ones the lobby showed (different per arena, none from the last round)
    if (this.upcoming.length < groups.length) this.pickUpcoming();
    this.plan = this.assignTracks(groups);
    this.lastTracks = this.plan.map((p) => p.track.id);
    this.ballots = [];
    this.glow = this.glowNext; this.glowNext = new Map();
    this.pickUpcoming();
    for (const item of this.plan) for (const pe of item.grp) pe.status = 'planned';
    // anyone eligible but not placed (over 64) spectates
    for (const pe of eligible) if (pe.status !== 'planned') pe.status = 'none';
    this.pending = this.plan.slice();
    this.arenas = [];
    this.state = 'running';
    if (!this.cfg.staggerArenas) while (this.pending.length) this.buildNext();
    this.events.push({ type: 'roundStart', plan: this.plan });
    return true;
  }

  // each arena gets the same share of Ts and CTs (so the top-8 count is a fair fight), random within that
  splitGroups(eligible, sizes) {
    const ts = shuffle(eligible.filter((p) => p.csTeam === 2));
    const cts = shuffle(eligible.filter((p) => p.csTeam === 3));
    const groups = sizes.map(() => []);
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
    for (const g of groups) shuffle(g);     // random grid order
    return groups;
  }

  buildNext() {
    const item = this.pending.shift();
    if (!item) return null;
    const grp = item.grp.filter((pe) => this.people.get(pe.slot) === pe && pe.status === 'planned');
    const arena = new Arena(this.arenas.length, item.track, {
      countdownTics: this.cfg.countdownTics, finishWindow: this.cfg.finishWindow, raceCap: this.cfg.raceCap, endHold: this.cfg.endHold, laps: this.cfg.laps,
    });
    this.arenas.push(arena);
    for (const pe of grp) {
      const car = arena.addCar(pe.slot, pe.name, pe.carChoice, pe.csTeam === 3 ? 1 : 0);
      car.person = pe; car.isBot = pe.bot; car.shade = pe.shade || 0; car.glow = this.glow.get(pe) || 0;
      if (pe.bot) car.bot = makeBot(this.cfg.botSkill);
      pe.arena = arena; pe.car = car; pe.status = 'racing'; pe.spec = null; pe.lastActive = this.clock; pe.races++;
    }
    arena.placeGrid();
    this.events.push({ type: 'arenaBuilt', arena });
    return arena;
  }

  leaveArena(pe, why) {
    const a = pe.arena;
    if (a && pe.car) { a.removeCar(pe.slot, why); this.events.push({ type: 'leave', person: pe, arena: a, why }); }
    pe.arena = null; pe.car = null; pe.status = 'none'; pe.spec = null;
  }

  // rounds are locked: anyone arriving mid-round watches until the next one
  lateJoin(pe) {
    if (this.state !== 'running') return false;
    if (pe.arena) return true;
    this.spectate(pe);
    return false;
  }

  spectate(pe, arena) {
    pe.status = 'spectating';
    if (!pe.spec) pe.spec = { arena: arena ? arena.index : (pe.arena ? pe.arena.index : 0), target: null };
    this.fixSpectate(pe, 0);
  }
  // a car to watch: dir 0 = keep if still valid, 1/-1 = next/previous in the standings, 'arena' = next arena
  fixSpectate(pe, dir) {
    if (!pe.spec) pe.spec = { arena: 0, target: null };
    const live = this.arenas.filter((a) => a.state !== 'over' || a.finishedAt < a.cfg.endHold * TICRATE);
    const pool = live.length ? live : this.arenas;
    if (!pool.length) { pe.spec.target = null; return; }
    let ai = pool.findIndex((a) => a.index === pe.spec.arena);
    if (ai < 0) ai = 0;
    if (dir === 'arena') { ai = (ai + 1) % pool.length; pe.spec.target = null; dir = 0; }
    const arena = pool[ai];
    pe.spec.arena = arena.index;
    const vis = arena.ranking.filter((c) => c.visible && c.state !== 'withdrawn');
    if (!vis.length) { pe.spec.target = null; return; }
    let i = vis.findIndex((c) => c.slot === pe.spec.target);
    if (i < 0) i = 0;
    else if (dir) i = (i + dir + vis.length) % vis.length;
    pe.spec.target = vis[i].slot;
  }

  // ------------------------------------------------------------------ per tic
  tic() {
    this.clock++;
    if (this.state !== 'running') return;
    this.time++;
    if (this.pending.length) this.buildNext();
    for (const a of this.arenas) {
      if (a.state === 'over' && a.finishedAt >= a.cfg.endHold * TICRATE) continue;
      for (const c of a.order) if (c.isBot) botThink(a, c);
      a.step();
      if (a.result && !a.ballot) this.closeRace(a);
    }
    this.checkAfk();
    this.checkEnds();
  }

  checkAfk() {
    for (const pe of this.people.values()) {
      // people waiting for the next race (finished, wrecked, joined mid-race and watching) aren't idle: only an idle
      // driver, or someone idle through a whole lobby, sits out. (!afk and an AFK verdict while driving still stick.)
      if (!pe.bot && !pe.afk && (!pe.car || (!pe.car.racing && pe.car.state !== 'grid'))) pe.lastActive = this.clock;
      if (pe.bot || pe.status !== 'racing' || !pe.arena || pe.arena.state !== 'racing' || !pe.car || !pe.car.racing) continue;
      const idle = this.clock - pe.lastActive;
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

  checkEnds() {
    for (const a of this.arenas) {
      if (a.state !== 'over' || a.finishedAt < a.cfg.endHold * TICRATE) continue;
      for (const c of a.order) {
        const pe = c.person;
        if (pe && pe.status === 'racing') { pe.status = 'spectating'; pe.spec = { arena: a.index, target: null }; this.fixSpectate(pe, 'arena'); }
      }
    }
    if (this.arenas.length && !this.pending.length && this.arenas.every((a) => a.over)) {
      this.state = 'over';
      this.events.push({ type: 'roundOver', arenas: this.arenas, points: this.teamPoints() });
    }
  }

  // ------------------------------------------------------------------ results
  // per arena: with 8+ cars, how many of the top 8 are T / CT; with fewer, 1 point to the winner's side.
  // live = true counts the running order of arenas still racing too (the HUD's team score)
  teamPoints(live) {
    const pts = { 2: 0, 3: 0, best: { 2: 99, 3: 99 }, detail: [] };
    for (const a of this.arenas) {
      if (!a.result && !live) continue;
      const r = a.result ? a.result.ranking : a.ranking.filter((c) => !c.left);
      const d = { track: a.track.title, t: 0, ct: 0 };
      if (r.length >= 8) {
        r.slice(0, 8).forEach((c) => { if (c.team === 0) d.t++; else if (c.team === 1) d.ct++; });
      } else if (r.length) {
        if (r[0].team === 0) d.t = 1; else if (r[0].team === 1) d.ct = 1;
      }
      r.forEach((c, i) => { const cs = c.team === 0 ? 2 : c.team === 1 ? 3 : 0; if (cs) pts.best[cs] = Math.min(pts.best[cs], i + 1); });
      pts[2] += d.t; pts[3] += d.ct; pts.detail.push(d);
    }
    let winner = pts[2] > pts[3] ? 2 : pts[3] > pts[2] ? 3 : 0;
    if (!winner && this.cfg.tiebreak) winner = pts.best[2] < pts.best[3] ? 2 : pts.best[3] < pts.best[2] ? 3 : 0;
    pts.winner = winner;
    return pts;
  }

  // who dies and who gets the credit when an arena's results are in
  killPlan(a) {
    const r = a.result ? a.result.ranking : [];
    const podium = r.slice(0, this.cfg.podium).filter((c) => c);
    const plan = [];
    // wrecked by someone's attack but not credited yet: the attacker gets that kill now (if still in the race's result)
    const deferred = r.slice(this.cfg.podium).filter((c) => !c.koApplied && !c.left && c.koBy && r.includes(c.koBy));
    for (const c of deferred) plan.push({ victim: c, killer: c.koBy });
    const losers = r.slice(this.cfg.podium).filter((c) => !c.koApplied && !c.left && !deferred.includes(c));
    const counts = splitShares(losers.length, this.cfg.shares.slice(0, Math.max(1, podium.length)));
    let k = 0;
    counts.forEach((n, i) => { for (let j = 0; j < n && k < losers.length; j++, k++) plan.push({ victim: losers[k], killer: podium[i] || null }); });
    while (k < losers.length) plan.push({ victim: losers[k++], killer: podium[0] || null });
    return plan;
  }

  // ------------------------------------------------------------------ track votes and the winners' glow
  // a race is over: its top places get a ballot of tracks for the next round, and glow next round
  closeRace(a) {
    const r = a.result.ranking, cfg = this.cfg;
    r.slice(0, cfg.glowPlaces).forEach((c, i) => { if (c.person && !c.left) this.glowNext.set(c.person, i + 1); });
    const rand = ballotRandom(this.roundNumber * 7919 + a.index * 104729 + this.clock);
    const raced = new Set(this.arenas.map((x) => x.track.id));
    const usable = this.tracks.filter((t) => !cfg.trackBlacklist.includes(t.id));
    const fresh = usable.filter((t) => !raced.has(t.id)), rest = usable.filter((t) => raced.has(t.id));
    const mix = (list) => { for (let i = list.length - 1; i > 0; i--) { const j = Math.floor(rand() * (i + 1)); [list[i], list[j]] = [list[j], list[i]]; } return list; };
    const tracks = mix(fresh).concat(mix(rest)).slice(0, Math.max(2, cfg.voteChoices)).map((t) => t.id);
    const voters = new Map();
    if (cfg.votes && tracks.length > 1) {
      r.slice(0, cfg.voteWeights.length).forEach((c, i) => {
        const pe = c.person;
        if (!pe || c.left || (pe.bot && !cfg.botsVote)) return;
        voters.set(pe.slot, { pe, weight: cfg.voteWeights[i], place: i + 1, choice: pe.bot ? tracks[Math.floor(rand() * tracks.length)] : null });
      });
    }
    a.ballot = { arena: a.index, track: a.track.id, tracks, voters, ver: 0 };
    this.ballots.push(a.ballot);
    if (voters.size) this.events.push({ type: 'ballot', arena: a, ballot: a.ballot });
  }

  // the ballot `pe` votes on (the person must still be the one who raced), or null
  ballotOf(pe) {
    if (!pe) return null;
    for (const b of this.ballots) { const v = b.voters.get(pe.slot); if (v && v.pe === pe) return b; }
    return null;
  }
  // vote for a track (id) or move the vote up / down the ballot (dir 1 / -1); returns the track voted for, or null
  vote(pe, idOrDir) {
    const b = this.ballotOf(pe);
    if (!b) return null;
    const v = b.voters.get(pe.slot);
    let id = idOrDir;
    if (typeof idOrDir === 'number') {
      const i = v.choice ? b.tracks.indexOf(v.choice) : (idOrDir > 0 ? -1 : 0);
      id = b.tracks[((i + idOrDir) % b.tracks.length + b.tracks.length) % b.tracks.length];
    }
    if (!b.tracks.includes(id)) return null;
    if (v.choice !== id) { v.choice = id; b.ver++; }
    return id;
  }
  // votes per track on one ballot
  tally(b) {
    const t = new Map();
    for (const id of b.tracks) t.set(id, 0);
    for (const v of b.voters.values()) if (v.choice && this.people.get(v.pe.slot) === v.pe) t.set(v.choice, (t.get(v.choice) || 0) + v.weight);
    return t;
  }
  // the track leading all the votes so far (shown in the lobby), or null
  voteLeader() {
    const all = new Map();
    for (const b of this.ballots) for (const [id, n] of this.tally(b)) if (n) all.set(id, (all.get(id) || 0) + n);
    let best = null, bn = 0;
    for (const [id, n] of all) if (n > bn) { best = id; bn = n; }
    return best ? this.tracks.find((t) => t.id === best) || null : null;
  }

  // the next round's tracks: each arena counts the votes of its own racers (wherever they voted); the arena with the
  // most votes behind its pick chooses first, so two arenas never get the same track; arenas without votes take the
  // lobby's upcoming tracks
  assignTracks(groups) {
    const byId = new Map(this.tracks.map((t) => [t.id, t]));
    const counts = groups.map((grp) => {
      const inGrp = new Set(grp);
      const c = new Map();
      for (const b of this.ballots) for (const v of b.voters.values()) {
        if (!v.choice || !inGrp.has(v.pe) || this.people.get(v.pe.slot) !== v.pe) continue;
        c.set(v.choice, (c.get(v.choice) || 0) + v.weight);
      }
      // highest first; ties go to the track first seen on the ballots (stable)
      return [...c].sort((x, y) => y[1] - x[1]);
    });
    const order = groups.map((_, i) => i).sort((i, j) => ((counts[j][0] || [0, 0])[1] - (counts[i][0] || [0, 0])[1]) || i - j);
    const taken = new Set(), picks = new Array(groups.length).fill(null), voted = new Array(groups.length).fill(false);
    for (const i of order) {
      for (const [id] of counts[i]) {
        const t = byId.get(id);
        if (t && !taken.has(id) && !this.cfg.trackBlacklist.includes(id)) { picks[i] = t; voted[i] = true; taken.add(id); break; }
      }
    }
    const cands = this.upcoming;
    let k = 0;
    for (let i = 0; i < groups.length; i++) {
      if (picks[i]) continue;
      // the lobby's next tracks in order, skipping any an arena voted for
      let t = null;
      for (let n = 0; n < cands.length * 2 && !t; n++) { const c = cands[(k + n) % cands.length]; if (!taken.has(c.id)) { t = c; k = (k + n + 1) % cands.length; } }
      if (!t) t = cands[i % cands.length];
      picks[i] = t; taken.add(t.id);
    }
    return groups.map((grp, i) => ({ grp, track: picks[i], voted: voted[i] }));
  }

  endRoundCleanup() {
    for (const pe of this.people.values()) { pe.arena = null; pe.car = null; pe.status = 'none'; pe.spec = null; }
    this.arenas = []; this.pending = []; this.plan = [];
  }
}
