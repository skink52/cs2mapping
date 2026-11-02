// =====================================================================================
//  PUPPET BRAWL core - part 4: the game (seats, modes, rounds, hits, projectiles,
//  camera, HUD model) and the CPU brain.
// =====================================================================================

const MODES = ["duel", "teams", "ffa"];
const MODE_LABEL = { duel: "WINNER STAYS 1v1", teams: "TAG TEAM 2v2", ffa: "FREE-FOR-ALL" };
const MODE_SHORT = { duel: "1v1", teams: "TAG", ffa: "FFA" };

const DEFAULT_GAME_CFG = {
  mode: "duel",
  roundTime: { duel: 60, teams: 99, ffa: 80 },
  roundsToWin: 2,
  maxRounds: 5,
  hpScale: 1,
  cpuLevel: 1,              // 0 easy, 1 normal, 2 hard
  countdown: 3,
  needHuman: true,          // a match needs at least one human seated
  backBlocks: true,         // holding away from the opponent blocks (as well as the block button)
  perfectBlock: true,       // guarding just before a hit lands is a perfect block
  perfectWindow: 7,         // frames (64 per second) between pressing guard and the hit
  perfectHeal: 2,           // health a perfect block gives back
  guardRecovery: 14,        // frames a guard holds still after blocking before walking back resumes
  zoneLow: 0.3,             // hit zones by contact height (share of a standing fighter's height):
  zoneHigh: 0.62,           //   below zoneLow = LOW, above zoneHigh = HIGH, between = MID
  modes: ["duel", "teams"], // the modes the MODE button cycles through ("ffa" can be added back)
  tagTeam: true,            // teams mode: one fighter per team on stage, partners tag in and out
  tagCooldown: 3,           // seconds between tags for a team
  tagRecover: 0.5,          // share of the damage taken in a stint a benched partner heals back
  spawnX: { duel: [-110, 110], teams: [-150, -80, 80, 150], ffa: [-170, -58, 58, 170] },
  lobbyX: [-165, -55, 55, 165],
};

const SPARK_POOL = 6;

class Game {
  constructor(opts = {}) {
    this.cfg = Object.assign({}, DEFAULT_GAME_CFG, opts.cfg || {});
    this.rng = makeRng(opts.seed || 1234567);
    this.halfW = opts.halfWidth || 380;
    this.mode = this.cfg.mode;
    this.pendingMode = null;
    this.frame = 0;
    this.phase = "lobby"; this.phaseT = 0;
    this.seats = [0, 1, 2, 3].map((i) => ({ kind: null, uid: null, name: "", ready: false, joinSeq: 0, brain: null }));
    this.fighters = [0, 1, 2, 3].map((i) => new Fighter(this, i));
    this.joinSeq = 0;
    this.queue = [];
    this.active = [];
    this.roundNum = 0; this.roundTimer = 0;
    this.teamWins = [0, 0, 0, 0];
    this.bestCombo = [0, 0, 0, 0];
    for (const f of this.fighters) f.perfects = 0;
    this.roundWinner = -2; this.matchWinner = -2;
    this.streak = 0; this.champion = -1;
    this.slowmo = 0;
    this.countdown = 0;
    this.projectiles = [];
    this.sparks = [];
    for (let i = 0; i < SPARK_POOL; i++) this.sparks.push({ x: 0, y: 0, life: 0, max: 1, size: 8, color: { r: 255, g: 255, b: 255 } });
    this.sparkNext = 0;
    this.events = [];
    this.cam = { cx: 0, cy: 50, half: 240, shake: 0 };
    this.hud = this.makeHud();
    this.announceQueue = [];
    this.announceTimer = 0;
    this.announceGap = 0;
    this.comboTimers = [0, 0, 0, 0];
    this.comboKind = ["", "", "", ""];
    this.bestCombo = [0, 0, 0, 0];
    this.forceCpuMatch = false;
    this.point = [-1, -1];      // tag team: the seat each team has on stage
    this.tagCD = [0, 0];        // frames until that team can tag again
    if (!this.cfg.tagTeam) { MODE_LABEL.teams = "2v2 TEAMS"; MODE_SHORT.teams = "2v2"; }
    this.layoutLobby();
  }

  // ------------------------------------------------------------------ events / fx
  sound(id) { if (id) this.events.push({ t: "snd", id }); }
  say(text) { this.events.push({ t: "say", text }); }
  // visual effects for the renderer (stage flashes, rings, particles); the core never reads them back
  fx(kind, data) { this.events.push(Object.assign({ t: "fx", fx: kind, frame: this.frame }, data)); }
  shake(amount) { this.cam.shake = Math.max(this.cam.shake, amount * 4); }
  spark(x, y, color, size) {
    const s = this.sparks[this.sparkNext];
    this.sparkNext = (this.sparkNext + 1) % this.sparks.length;
    s.x = x; s.y = y; s.color = color; s.size = size; s.life = 7; s.max = 7;
  }
  announce(text, style = "", seconds = 1.2) {
    this.announceQueue.push({ text, style, seconds });
  }
  clearAnnounce() { this.announceQueue.length = 0; this.announceTimer = 0; this.hud.announce.show = false; }

  // ------------------------------------------------------------------ seats
  seated() { return [0, 1, 2, 3].filter((i) => this.seats[i].kind); }
  humans() { return this.seated().filter((i) => this.seats[i].kind === "human"); }
  freeSeat() { for (let i = 0; i < 4; i++) if (!this.seats[i].kind) return i; return -1; }
  hostSeat() {
    let best = -1, seq = Infinity;
    for (const i of this.humans()) if (this.seats[i].joinSeq < seq) { seq = this.seats[i].joinSeq; best = i; }
    return best;
  }

  seatHuman(seat, uid, name) {
    if (seat < 0 || seat > 3 || this.seats[seat].kind) return false;
    const s = this.seats[seat];
    Object.assign(s, { kind: "human", uid, name: String(name || "Player").slice(0, 18), ready: false, joinSeq: ++this.joinSeq, brain: null });
    this.fighters[seat].setCharacter(seat % CHARACTERS.length);
    this.fighters[seat].perfectOk = undefined;   // humans can always perfect-block
    this.onSeatJoined(seat);
    this.sound("select");
    return true;
  }

  addCpu(seat = -1) {
    if (seat < 0) seat = this.freeSeat();
    if (seat < 0 || this.seats[seat].kind) return -1;
    const s = this.seats[seat];
    Object.assign(s, { kind: "cpu", uid: null, name: "CPU", ready: true, joinSeq: ++this.joinSeq });
    this.fighters[seat].setCharacter(this.rng.int(0, CHARACTERS.length - 1));
    s.brain = new CpuBrain(this, this.fighters[seat], this.cfg.cpuLevel);
    this.onSeatJoined(seat);
    return seat;
  }

  // End any CPU game completely: every CPU leaves, CPU-only matches stop, back to the lobby.
  stopCpus() {
    const hadMatch = this.inMatch();
    this.forceCpuMatch = false;
    this.cfg.needHuman = true;
    if (hadMatch && !this.humans().length) this.toLobby();
    for (let i = 3; i >= 0; i--) if (this.seats[i].kind === "cpu") this.unseat(i, "removed");
    this.layoutLobby();
    return hadMatch;
  }

  removeCpu() {
    const cpus = this.seated().filter((i) => this.seats[i].kind === "cpu");
    if (!cpus.length) return -1;
    const seat = cpus[cpus.length - 1];
    this.unseat(seat, "removed");
    return seat;
  }

  onSeatJoined(seat) {
    const f = this.fighters[seat];
    if (this.phase === "lobby" || this.phase === "countdown") {
      this.layoutLobby();
    } else if (this.mode === "duel" && this.inMatch()) {
      if (!this.queue.includes(seat)) this.queue.push(seat);
      this.placeWaiting();
    } else {
      f.onStage = false; f.active = false;
    }
    this.cancelCountdown();
  }

  unseat(seat, reason = "left") {
    const s = this.seats[seat];
    if (!s.kind) return;
    const f = this.fighters[seat];
    // Only a fighter who leaves while the match is being fought forfeits. During matchEnd
    // the result already stands, and during nextUp the next pair simply gets re-picked.
    const paired = this.active.includes(seat);
    const fighting = paired && (this.phase === "intro" || this.phase === "fight" || this.phase === "roundEnd");
    Object.assign(s, { kind: null, uid: null, name: "", ready: false, brain: null });
    f.active = false; f.onStage = false; f.background = false;
    if (f.victim) { const v = f.victim; f.victim = null; v.thrower = null; v.throwPelvis = null; if (v.state === "thrown") { v.setState("launch"); v.vy = 200; v.y = Math.max(v.y, 0.5); v.kdOnLand = true; } }
    if (f.thrower) { f.thrower.victim = null; f.thrower = null; }
    this.projectiles = this.projectiles.filter((pr) => pr.owner !== f);
    f.projectile = null;
    this.queue = this.queue.filter((q) => q !== seat);
    this.active = this.active.filter((q) => q !== seat);
    if (seat === this.champion) { this.champion = -1; this.streak = 0; }
    if (this.inMatch() && this.cfg.needHuman && !this.forceCpuMatch && !this.humans().length) { this.toLobby(); return; }
    if (fighting) {
      if (this.mode === "duel") {
        const other = this.active[0];
        if (other !== undefined) { this.forfeit(other); return; }
        this.toLobby();
        return;
      }
      if (!this.matchViable()) { this.toLobby("Not enough fighters - back to the lobby"); return; }
    } else if (this.phase === "nextUp" && paired) {
      this.active = this.queue.slice(0, 2);
      if (this.active.length < 2) { this.toLobby(); return; }
      for (const i of this.active) { const g = this.fighters[i]; g.active = false; g.background = false; g.depthBase = 0; g.state = "lobby"; }
      this.clearAnnounce();
      this.announce(this.displayName(this.active[0]) + "  vs  " + this.displayName(this.active[1]), "small", 2.2);
    }
    if (this.phase === "lobby" || this.phase === "countdown") { this.cancelCountdown(); this.layoutLobby(); }
    if (this.mode === "duel" && this.inMatch()) this.placeWaiting();
    if (this.inMatch() && this.phase !== "matchEnd" && this.seated().length < 2) this.toLobby();
  }

  inMatch() { return this.phase !== "lobby" && this.phase !== "countdown"; }

  setMode(mode) {
    if (!MODES.includes(mode)) return;
    if (this.inMatch()) {
      this.pendingMode = mode;
      this.announce("NEXT MODE: " + MODE_LABEL[mode], "small", 1.6);
      return;
    }
    this.mode = mode; this.pendingMode = null;
    this.queue = [];
    this.cancelCountdown();
    this.layoutLobby();
    this.sound("select");
  }
  cycleMode() {
    const list = (this.cfg.modes || MODES).filter((m) => MODES.includes(m));
    const cur = this.pendingMode || this.mode;
    const i = list.indexOf(cur);
    this.setMode(list[(i + 1) % list.length]);
  }
  get tagMode() { return this.mode === "teams" && this.cfg.tagTeam !== false; }

  teamOfSeat(seat) {
    if (this.mode === "teams") return seat < 2 ? 0 : 1;
    return seat;
  }
  colorOfSeat(seat) {
    if (this.mode === "teams") return TEAM_COLORS[seat < 2 ? 0 : 1][seat % 2];
    return PLAYER_COLORS[seat];
  }
  seatLabel(seat) { return "P" + (seat + 1); }
  displayName(seat) {
    const s = this.seats[seat];
    return s.kind === "cpu" ? "CPU " + (seat + 1) : (s.name || this.seatLabel(seat));
  }

  // ------------------------------------------------------------------ lobby
  layoutLobby() {
    for (let i = 0; i < 4; i++) {
      const f = this.fighters[i], s = this.seats[i];
      f.team = this.teamOfSeat(i);
      f.color = this.colorOfSeat(i);
      f.active = false;
      f.background = false;
      f.depthBase = 0;
      if (!s.kind) { f.onStage = false; continue; }
      f.onStage = true;
      f.x = this.cfg.lobbyX[i] * Math.min(1, (this.halfW - 30) / 200);
      f.y = 0; f.vx = 0; f.vy = 0;
      f.facing = f.x < 0 ? 1 : -1;
      f.ko = false; f.hp = f.maxHp;
      f.state = "lobby"; f.move = null;
      f.lobbyReady = s.ready;
    }
  }

  canStart() {
    const seated = this.seated();
    if (this.cfg.needHuman && !this.humans().length && !this.forceCpuMatch) return false;
    if (this.mode === "teams") {
      return seated.some((i) => i < 2) && seated.some((i) => i >= 2);
    }
    return seated.length >= 2;
  }
  allReady() { return this.humans().every((i) => this.seats[i].ready); }
  cancelCountdown() { if (this.phase === "countdown") { this.phase = "lobby"; this.phaseT = 0; } }

  lobbyInput() {
    const host = this.hostSeat();
    for (const i of this.humans()) {
      const f = this.fighters[i], s = this.seats[i];
      const waitingInDuel = this.mode === "duel" && this.inMatch() && !this.active.includes(i);
      const inLobby = !this.inMatch();
      if (!inLobby && !waitingInDuel) continue;
      if (!s.ready) {
        if (f.hasPress(IN.LEFT, 0)) { f.consume(IN.LEFT); f.setCharacter(f.charIdx - 1); this.sound("tick"); }
        if (f.hasPress(IN.RIGHT, 0)) { f.consume(IN.RIGHT); f.setCharacter(f.charIdx + 1); this.sound("tick"); }
        if (f.hasPress(IN.PUNCH, 0)) { f.consume(IN.PUNCH); s.ready = true; f.lobbyReady = true; this.sound("select"); }
      } else if (f.hasPress(IN.KICK, 0)) {
        f.consume(IN.KICK); s.ready = false; f.lobbyReady = false; this.cancelCountdown(); this.sound("tick");
      }
      if (inLobby && i === host) {
        if (f.hasPress(IN.SPECIAL, 0)) { f.consume(IN.SPECIAL); this.cycleMode(); }
        if (f.hasPress(IN.THROW, 0)) {
          f.consume(IN.THROW);
          if (this.addCpu() < 0) { while (this.removeCpu() >= 0) { /* clear all CPUs */ } }
          this.sound("select");
        }
      }
    }
  }

  // ------------------------------------------------------------------ match flow
  startMatch() {
    if (this.pendingMode) { this.mode = this.pendingMode; this.pendingMode = null; }
    const seated = this.seated();
    if (this.mode === "duel") {
      this.queue = this.queue.filter((q) => this.seats[q].kind);
      for (const i of seated.sort((a, b) => this.seats[a].joinSeq - this.seats[b].joinSeq)) if (!this.queue.includes(i)) this.queue.push(i);
      this.active = this.queue.slice(0, 2);
    } else {
      this.active = seated.slice();
    }
    for (const i of seated) this.seats[i].ready = true;
    const teamCount = [0, 0, 0, 0];
    for (const i of this.active) teamCount[this.teamOfSeat(i)]++;
    const biggest = Math.max(...teamCount);
    for (let i = 0; i < 4; i++) {
      const f = this.fighters[i];
      f.team = this.teamOfSeat(i);
      f.color = this.colorOfSeat(i);
      const handicap = this.mode === "teams" && teamCount[f.team] ? biggest / teamCount[f.team] : 1;
      f.maxHp = Math.round(f.ch.stats.hp * this.cfg.hpScale * handicap);
      f.wins = 0;
    }
    this.teamWins = [0, 0, 0, 0];
    this.bestCombo = [0, 0, 0, 0];
    for (const f of this.fighters) f.perfects = 0;
    this.roundNum = 0;
    this.matchWinner = -2;
    this.startRound();
  }

  startRound() {
    this.roundNum++;
    this.roundTimer = this.cfg.roundTime[this.mode] || 60;
    this.projectiles = [];
    this.slowmo = 0;
    this.roundWinner = -2;
    this.clearAnnounce();
    const xs = this.mode === "duel" ? this.cfg.spawnX.duel : this.mode === "teams" ? this.cfg.spawnX.teams : this.cfg.spawnX.ffa;
    const k = Math.min(1, (this.halfW - 40) / 210);
    let order = this.active.slice();
    if (this.mode === "teams") order.sort((a, b) => a - b);
    for (let i = 0; i < 4; i++) { const f = this.fighters[i]; f.active = false; f.background = false; }
    if (this.tagMode) {
      // tag team: each team starts with one fighter (taking turns round by round)
      for (const team of [0, 1]) {
        const mem = order.filter((i) => this.teamOfSeat(i) === team);
        this.point[team] = mem.length ? mem[(this.roundNum - 1) % mem.length] : -1;
        this.tagCD[team] = Math.round(SIM_HZ * 1.5);
      }
      for (const seat of order) {
        const f = this.fighters[seat], team = this.teamOfSeat(seat);
        const x = this.cfg.spawnX.duel[team] * k;
        f.resetForRound(x, team === 0 ? 1 : -1);
        f.onStage = true; f.depthBase = 0; f.stintDmg = 0; f.benchHeal = 0;
        if (seat === this.point[team]) f.active = true;
        else this.bench(f, false);
      }
    } else order.forEach((seat, idx) => {
      const f = this.fighters[seat];
      let x;
      if (this.mode === "duel") x = xs[idx];
      else if (this.mode === "teams") x = xs[seat];
      else x = order.length > 1 ? lerp(xs[0], xs[3], idx / (order.length - 1)) : 0;
      f.onStage = true; f.active = true; f.depthBase = 0;
      f.resetForRound(x * k, x < 0 ? 1 : -1);
      f.depthBase = (idx % 2 ? -2.5 : 2.5);
    });
    this.placeWaiting();
    for (let i = 0; i < 4; i++) if (!this.seats[i].kind) { this.fighters[i].onStage = false; this.fighters[i].active = false; }
    this.phase = "intro"; this.phaseT = 0;
    const need = this.cfg.roundsToWin - 1;
    const finalRound = this.active.length >= 2 && this.activeTeams().every((t) => this.teamWins[t] === need) && need > 0;
    this.announce(finalRound ? "FINAL ROUND" : "ROUND " + this.roundNum, "big", 1.15);
    this.announce("FIGHT!", "fight", 0.75);
    this.sound("bell");
  }

  placeWaiting() {
    if (this.mode !== "duel") return;
    const waiting = this.queue.filter((q) => !this.active.includes(q) && this.seats[q].kind);
    waiting.forEach((seat, i) => {
      const f = this.fighters[seat];
      f.active = false; f.onStage = true; f.background = true;
      const side = i % 2 === 0 ? -1 : 1;
      f.x = side * (this.halfW - 40 - Math.floor(i / 2) * 34);
      f.y = 0; f.vx = 0; f.vy = 0;
      f.facing = -side;
      f.state = "waiting"; f.move = null; f.ko = false;
      f.depthBase = -70;
      f.team = this.teamOfSeat(seat); f.color = this.colorOfSeat(seat);
    });
  }

  // ------------------------------------------------------------------ tag team
  // A benched partner waits at the back of the stage on their team's side.
  bench(f, ko) {
    const side = f.team === 0 ? -1 : 1;
    f.active = false; f.onStage = true; f.background = true;
    f.x = side * (this.halfW - 40); f.y = 0; f.vx = 0; f.vy = 0;
    f.facing = -side; f.move = null; f.projectile = null;
    f.state = ko ? "defeat" : "waiting"; f.depthBase = -70;
    f.hitstop = 0; f.stun = 0; f.invuln = 0;
  }
  partnerOf(f) {
    for (const i of this.active) {
      const o = this.fighters[i];
      if (o !== f && o.team === f.team && !o.ko && this.seats[i].kind) return o;
    }
    return null;
  }
  canTag(f) {
    return this.tagMode && this.phase === "fight" && f.active && !f.ko && this.tagCD[f.team] <= 0 && NEUTRAL.has(f.state) && !f.airborne && !!this.partnerOf(f);
  }
  // swap the team's point fighter out for the partner, who comes in where they stood
  tagIn(team, inSeat, forced) {
    const inF = this.fighters[inSeat];
    const outSeat = this.point[team], outF = outSeat >= 0 ? this.fighters[outSeat] : null;
    const x = outF && outF.active ? outF.x : this.cfg.spawnX.duel[team] * Math.min(1, (this.halfW - 40) / 210);
    if (outF && outF !== inF) {
      outF.benchHeal = outF.ko ? 0 : Math.round((outF.stintDmg || 0) * (this.cfg.tagRecover || 0));
      outF.stintDmg = 0;
      this.projectiles = this.projectiles.filter((pr) => pr.owner !== outF);
      if (this.seats[outSeat].kind) this.bench(outF, outF.ko);
      else { outF.active = false; outF.onStage = false; }
    }
    this.point[team] = inSeat;
    inF.active = true; inF.onStage = true; inF.background = false; inF.depthBase = 0;
    inF.x = x; inF.y = 0; inF.vx = 0; inF.vy = 0; inF.move = null;
    inF.state = "idle"; inF.sf = 0; inF.invuln = 24; inF.throwInvuln = 30; inF.stintDmg = 0;
    inF.combo = 0; inF.comboDmg = 0; inF.juggle = 0; inF.clearInput();
    const foe = this.nearestEnemy(inF);
    if (foe) inF.facing = foe.x >= inF.x ? 1 : -1;
    this.tagCD[team] = Math.round(SIM_HZ * (this.cfg.tagCooldown || 3));
    this.spark(x, 50, { r: 255, g: 240, b: 160 }, 16);
    this.sound("select");
    this.announce(forced ? this.displayName(inSeat) + " STEPS IN" : "TAG!  " + this.displayName(inSeat), "small", 0.9);
    this.events.push({ t: "tag", team, seat: inSeat });
    this.fx("tag", { x, seat: inSeat, color: inF.ch.accent });
  }
  updateTag() {
    for (const team of [0, 1]) {
      if (this.tagCD[team] > 0) this.tagCD[team]--;
      const pSeat = this.point[team];
      const p = pSeat >= 0 ? this.fighters[pSeat] : null;
      // the point fighter left or was knocked out: the partner steps in
      const gone = !p || !this.seats[pSeat].kind || !this.active.includes(pSeat);
      const down = p && p.ko && !p.airborne && p.state !== "launch" && this.frame - (p.koFrame || 0) > SIM_HZ * 1.3;
      if (gone || down) {
        const mem = this.active.filter((i) => this.teamOfSeat(i) === team && i !== pSeat && !this.fighters[i].ko && this.seats[i].kind);
        if (mem.length) this.tagIn(team, mem[0], true);
      }
    }
    // benched partners get back part of the damage they took
    for (const i of this.active) {
      const f = this.fighters[i];
      if (f.background && !f.ko && f.benchHeal > 0 && this.frame % 6 === 0 && f.hp < f.maxHp) { f.hp++; f.benchHeal--; }
    }
  }

  activeTeams() {
    const t = new Set();
    for (const i of this.active) t.add(this.fighters[i].team);
    return [...t];
  }
  aliveTeams() {
    const t = new Set();
    for (const i of this.active) if (!this.fighters[i].ko) t.add(this.fighters[i].team);
    return [...t];
  }
  matchViable() {
    if (this.mode === "teams") { const t = this.activeTeams(); return t.includes(0) && t.includes(1); }
    return this.active.length >= 2;
  }
  isWinnerTeam(team) {
    if (this.phase === "matchEnd") return this.matchWinner === team;
    if (this.phase === "roundEnd") return this.roundWinner === team;
    return false;
  }

  endRound(winnerTeam, reason) {
    if (this.phase !== "fight") return;
    this.phase = "roundEnd"; this.phaseT = 0;
    this.roundWinner = winnerTeam;
    this.projectiles = [];
    for (const f of this.fighters) f.projectile = null;
    this.clearAnnounce();
    if (reason === "ko") { this.slowmo = Math.round(SIM_HZ * 1.1); this.announce("K.O.", "ko", 1.6); this.sound("ko"); }
    else if (reason === "time") { this.announce("TIME", "big", 1.2); this.sound("bell"); }
    if (winnerTeam >= 0) {
      this.teamWins[winnerTeam]++;
      const perfect = this.active.filter((i) => this.fighters[i].team === winnerTeam).every((i) => this.fighters[i].hp >= this.fighters[i].maxHp);
      this.announce(this.teamLabel(winnerTeam) + (perfect ? "  -  PERFECT" : ""), "sub", 1.6);
    } else {
      this.announce("DRAW", "big", 1.4);
    }
  }

  teamLabel(team) {
    if (this.mode === "teams") return TEAM_NAMES[team];
    return this.displayName(team);
  }

  forfeit(winnerSeat) {
    this.clearAnnounce();
    const team = this.fighters[winnerSeat].team;
    this.teamWins[team] = this.cfg.roundsToWin;
    this.phase = "roundEnd"; this.phaseT = 99;
    this.roundWinner = team;
    this.announce("FORFEIT", "big", 1.2);
    this.finishMatch();
  }

  finishMatch() {
    const teams = this.activeTeams();
    let best = -1, bestWins = -1, tie = false;
    for (const t of teams) {
      if (this.teamWins[t] > bestWins) { best = t; bestWins = this.teamWins[t]; tie = false; }
      else if (this.teamWins[t] === bestWins) tie = true;
    }
    this.matchWinner = tie ? -1 : best;
    this.phase = "matchEnd"; this.phaseT = 0;
    if (this.matchWinner >= 0) {
      const label = this.teamLabel(this.matchWinner);
      this.announce(label + " WINS", "win", 3.0);
      this.sound("win");
      this.fx("win", { team: this.matchWinner });
      let text = "[Puppet Brawl] " + label + " wins";
      if (this.mode === "duel") {
        const winSeat = this.active.find((i) => this.fighters[i].team === this.matchWinner);
        if (winSeat === this.champion) this.streak++; else { this.champion = winSeat; this.streak = 1; }
        if (this.streak > 1) text += " - " + this.streak + " in a row";
      }
      this.say(text);
    } else {
      this.announce("DRAW GAME", "win", 2.6);
    }
  }

  afterMatch() {
    if (this.mode === "duel" && !this.pendingMode) {
      const winSeat = this.matchWinner >= 0 ? this.active.find((i) => this.fighters[i].team === this.matchWinner) : undefined;
      const loseSeat = winSeat !== undefined ? this.active.find((i) => i !== winSeat) : undefined;
      let q = this.queue.filter((s) => this.seats[s].kind);
      if (winSeat !== undefined && loseSeat !== undefined) {
        q = q.filter((s) => s !== winSeat && s !== loseSeat);
        q = [winSeat, ...q, loseSeat];
      } else if (this.matchWinner === -1) {
        // draw game: nobody stays on, both go to the back of the queue
        const both = this.active.slice();
        q = [...q.filter((s) => !both.includes(s)), ...both];
        this.champion = -1; this.streak = 0;
      }
      this.queue = q;
      if (this.seated().length >= 2 && (this.humans().length || this.forceCpuMatch || !this.cfg.needHuman)) {
        this.active = this.queue.slice(0, 2);
        this.phase = "nextUp"; this.phaseT = 0;
        const [a, b] = this.active;
        this.announce(this.displayName(a) + "  vs  " + this.displayName(b), "small", 2.2);
        for (const i of this.seated()) {
          const f = this.fighters[i];
          if (!this.active.includes(i)) continue;
          f.active = false; f.state = "lobby";
        }
        this.placeWaiting();
        return;
      }
    }
    this.toLobby();
  }

  toLobby(msg) {
    this.phase = "lobby"; this.phaseT = 0;
    if (this.pendingMode) { this.mode = this.pendingMode; this.pendingMode = null; }
    this.active = [];
    this.projectiles = [];
    this.slowmo = 0;
    this.clearAnnounce();
    if (msg) this.announce(msg, "small", 2);
    for (const i of this.humans()) this.seats[i].ready = false;
    for (let i = 0; i < 4; i++) {
      const f = this.fighters[i];
      if (f.victim) f.victim = null;
      f.thrower = null;
    }
    this.layoutLobby();
  }

  reset() {
    this.toLobby();   // stop any match first, so emptying the seats can't award a forfeit
    for (let i = 0; i < 4; i++) if (this.seats[i].kind) this.unseat(i, "reset");
    this.queue = []; this.champion = -1; this.streak = 0;
    this.forceCpuMatch = false;
    this.layoutLobby();
  }

  // A human can take a CPU's seat whenever that CPU isn't fighting at the moment.
  canTakeOver(seat) {
    if (seat < 0 || seat > 3 || this.seats[seat].kind !== "cpu") return false;
    return !this.inMatch() || !this.active.includes(seat);
  }
  takeOver(seat, uid, name) {
    if (!this.canTakeOver(seat)) return false;
    const qi = this.queue.indexOf(seat);
    this.unseat(seat, "replaced");
    if (!this.seatHuman(seat, uid, name)) return false;
    if (qi >= 0) { this.queue = this.queue.filter((q) => q !== seat); this.queue.splice(Math.min(qi, this.queue.length), 0, seat); this.placeWaiting(); }
    return true;
  }

  forceStart() {
    if (this.inMatch()) return false;
    if (this.seated().length < 2 || (this.mode === "teams" && !this.canStartTeams())) return false;
    this.startMatch();
    return true;
  }
  canStartTeams() { const s = this.seated(); return s.some((i) => i < 2) && s.some((i) => i >= 2); }

  // ------------------------------------------------------------------ combat helpers
  enemies(f) {
    const out = [];
    for (const i of this.active) {
      const o = this.fighters[i];
      if (o !== f && o.team !== f.team && o.active) out.push(o);
    }
    return out;
  }
  nearestEnemy(f, aliveOnly = true) {
    let best = null, bd = Infinity;
    for (const o of this.enemies(f)) {
      if (aliveOnly && o.ko) continue;
      const d = Math.abs(o.x - f.x);
      if (d < bd) { bd = d; best = o; }
    }
    return best;
  }

  throwTarget(f) {
    const range = 40 * f.ch.legF;
    let best = null, bd = Infinity;
    for (const o of this.enemies(f)) {
      if (!o.throwable()) continue;
      const dx = (o.x - f.x) * f.facing;
      if (dx < -4 || dx > range) continue;
      if (dx < bd) { bd = dx; best = o; }
    }
    return best;
  }

  breakThrow(a, t) {
    a.victim = null; t.thrower = null; t.throwPelvis = null;
    a.move = null; a.state = "blockstun"; a.stun = 12; a.vx = -a.facing * 260;
    t.state = "blockstun"; t.stun = 12; t.vx = -t.facing * 260; t.facing = -a.facing;
    t.throwInvuln = 30;
    this.spark((a.x + t.x) / 2, 60, { r: 140, g: 220, b: 255 }, 12);
    this.sound("block");
    this.announce("BREAK", "small", 0.6);
  }

  releaseThrow(a, t) {
    const m = a.move;
    a.victim = null; t.thrower = null;
    t.throwPelvis = null;
    t.x = clamp(a.x - a.facing * 26 * a.ch.legF, -this.halfW + 14, this.halfW - 14);
    t.y = 40;
    const dmg = Math.round(m.def.dmg * a.ch.stats.dmg);
    this.applyDamage(t, dmg, a);
    t.setState("launch");
    t.vx = a.facing * m.def.toss.vx;
    t.vy = m.def.toss.vy;
    t.juggle = MAX_JUGGLE;
    t.facing = a.facing;
    this.sound("heavy");
    this.shake(1.5);
    this.spark(t.x, 30, { r: 255, g: 200, b: 120 }, 14);
  }

  applyDamage(d, dmg, attacker) {
    d.stintDmg = (d.stintDmg || 0) + Math.min(dmg, d.hp);
    d.hp = Math.max(0, d.hp - dmg);
    d.lastAttacker = attacker ? attacker.seat : -1;
    if (d.hp <= 0 && !d.ko) {
      d.ko = true; d.koFrame = this.frame;
      this.onKO(d, attacker);
    }
  }

  onKO(d, attacker) {
    this.shake(3);
    for (const i of this.queue) { const w = this.fighters[i]; if (w.background) w.cheering = 50; }
    if (this.tagMode) for (const i of this.active) { const w = this.fighters[i]; if (w.background && !w.ko) w.cheering = 50; }
  }

  // Strike resolution: attacker A (fighter) hits defender D with hit-def h at point tip.
  // LOW / MID / HIGH from where the hit lands on a standing body. "low" moves are always low,
  // "over" (overheads) and jump-in "air" attacks always high.
  zoneOf(h, tip, D) {
    if (h.level === "low") return "low";
    if (h.level === "over" || h.level === "air") return "high";
    const stand = D.ch.dims.thigh + D.ch.dims.shin + D.ch.dims.torso + D.ch.dims.neck + 2 * D.ch.dims.headR;
    const rel = (tip.y - D.y) / stand;
    return rel < this.cfg.zoneLow ? "low" : rel > this.cfg.zoneHigh ? "high" : "mid";
  }

  resolveHit(A, D, h, tip, fromProjectile) {
    const away = Math.sign(D.x - A.x) || A.facing;
    const wall = Math.abs(D.x) >= this.halfW - D.ch.stats.pushW - 2;
    D.hitSerial++;
    const zone = this.zoneOf(h, tip, D);
    this.events.push({ t: "zone", zone, seat: D.seat });
    if (D.canBlock(zone)) {
      // perfect block: guard pressed just before the hit. No chip, a short blockstun, a little
      // health back, and the attacker is left hanging for a moment.
      const perfect = this.cfg.perfectBlock !== false && D.perfectOk !== false && this.frame - D.guardF <= this.cfg.perfectWindow;
      const chip = perfect ? 0 : (h.chip || 0);
      if (chip) D.hp = Math.max(1, D.hp - chip);
      D.move = null; D.strikeInvuln = false; D.armored = false;
      D.setState("blockstun"); D.sf = 0;
      D.stun = perfect ? Math.max(2, Math.round(h.blockstun * 0.35)) : h.blockstun; D.blockLow = !!(D.held & IN.DOWN);
      D.vx = away * h.push * (perfect ? 0.35 : 0.75);
      if (!fromProjectile) {
        A.moveBlocked = true; A.contactFrame = A.mf;
        if (wall) A.vx -= away * h.push * 0.5;
        const hs = Math.max(3, (h.hitstop || 4) - 2);
        A.hitstop = hs + (perfect ? 10 : 0);
        D.hitstop = hs;
      } else D.hitstop = 3;
      if (perfect) {
        D.hp = Math.min(D.maxHp, D.hp + (this.cfg.perfectHeal || 0));
        D.perfects++;
        D.guardF = -999;   // one perfect per press
        this.comboTimers[D.seat] = Math.round(SIM_HZ * 1.1); this.comboText[D.seat] = "PERFECT BLOCK"; this.comboKind[D.seat] = "perfect";
        this.spark(tip.x, tip.y, { r: 255, g: 255, b: 255 }, 15);
        this.sound("select");
        this.events.push({ t: "perfect", seat: D.seat });
      } else this.spark(tip.x, tip.y, { r: 120, g: 210, b: 255 }, 9);
      this.fx("block", { x: tip.x, y: tip.y, perfect, dir: away, seat: D.seat, heavy: h.snd === "heavy" });
      this.sound("block");
      return;
    }
    if (D.armored && D.armorHits < 1) {
      D.armorHits++;
      this.applyDamage(D, Math.round(h.dmg * 0.5), A);
      D.hitstop = 5; if (!fromProjectile) A.hitstop = 5;
      this.spark(tip.x, tip.y, { r: 255, g: 220, b: 120 }, 12);
      this.sound("block");
      if (!D.ko) return;
    }
    const scale = Math.max(0.45, 1 - 0.1 * D.combo);
    const dmg = Math.max(1, Math.round(h.dmg * scale));
    const wasAir = D.airborne;
    D.combo++; D.comboDmg += dmg;
    this.applyDamage(D, dmg, A);
    if (!fromProjectile) { A.moveHit = true; A.contactFrame = A.mf; }
    // cancel whatever the defender was doing
    if (D.victim) { const v = D.victim; D.victim = null; v.thrower = null; v.setState("launch"); v.vy = 180; v.kdOnLand = true; }
    D.move = null; D.strikeInvuln = false; D.armored = false;
    const hs = D.ko ? 14 : (h.hitstop || 5);
    D.hitstop = hs;
    if (!fromProjectile) A.hitstop = hs;
    if (D.ko) {
      D.setState("launch"); D.sf = 0;
      D.vx = away * 240; D.vy = Math.max(D.vy, 520); D.y = Math.max(D.y, 0.5);
    } else if (h.launch || h.kd || wasAir || (h.airKd && wasAir)) {
      const L = h.launch || { vx: 160, vy: 300 };
      D.setState("launch"); D.sf = 0;
      D.vx = away * Math.abs(L.vx);
      if (L.vx < 0) D.vx = -away * Math.abs(L.vx);
      D.vy = wasAir ? Math.max(260, L.vy * 0.6) : L.vy;
      D.y = Math.max(D.y, 0.5);
      D.juggle += wasAir ? 1 : 0;
      D.kdOnLand = true;
    } else {
      D.setState("hitstun"); D.sf = 0;
      D.stun = h.hitstun;
      D.hitLevel = zone === "high" ? "high" : "mid";
      D.crouchHit = !!(D.held & IN.DOWN) || D.state === "crouch";
      D.vx = away * h.push;
      if (wall && !fromProjectile) A.vx -= away * h.push * 0.6;
    }
    const heavy = h.snd === "heavy" || D.ko;
    this.spark(tip.x, tip.y, heavy ? { r: 255, g: 170, b: 60 } : { r: 255, g: 245, b: 200 }, heavy ? 13 : 9);
    this.fx("hit", { x: tip.x, y: tip.y, heavy, ko: !!D.ko, dir: away, seat: A.seat, victim: D.seat, dx: D.x,
      special: fromProjectile || !!(A.move && (A.move.special || A.move.combo)), color: A.ch.accent });
    this.sound(D.ko ? "heavy" : (h.snd || "hit"));
    if (heavy || h.shake) this.shake(h.shake ? 2 : 1);
    // combo tracker: hits in a row before the defender recovers, damage, and the match best
    if (D.combo >= 2) {
      const finisher = !fromProjectile && A.move && A.move.combo ? "  " + A.move.name.toUpperCase() : "";
      this.comboTimers[A.seat] = Math.round(SIM_HZ * 1.6);
      this.comboText[A.seat] = D.combo + " HIT COMBO  " + D.comboDmg + " DMG" + finisher;
      this.comboKind[A.seat] = "combo";
      if (D.combo > this.bestCombo[A.seat]) this.bestCombo[A.seat] = D.combo;
      if (D.combo === 5 || D.combo === 8) this.announce(D.combo + " HIT COMBO!", "small", 0.9);
    } else if (!fromProjectile && A.move && A.move.combo) {
      this.comboTimers[A.seat] = Math.round(SIM_HZ * 1.1); this.comboText[A.seat] = A.move.name.toUpperCase(); this.comboKind[A.seat] = "combo";
    }
  }

  // All contacts are found first and applied after, so two attacks that connect on the
  // same frame trade instead of the lower seat number always winning. Each attacker
  // lands at most one hit per frame (it then sits in hitstop).
  checkHits() {
    const found = [];
    for (const i of this.active) {
      const A = this.fighters[i];
      if (!A.active || A.ko || (A.state !== "attack") || !A.move || A.hitstop > 0) continue;
      const m = A.move, f = A.mf;
      let landed = false;
      for (let hi = 0; hi < m.hits.length && !landed; hi++) {
        const h = m.hits[hi];
        if (f < h.from || f > h.to) continue;
        if (A.hitWindow !== hi) { A.hitWindow = hi; A.hitIds.clear(); }
        const tip = A.tipFor(h);
        for (const D of this.enemies(A)) {
          if (A.hitIds.has(D.seat) || !D.strikeable()) continue;
          if (!D.overlaps(tip.x, tip.y, h.r)) continue;
          A.hitIds.add(D.seat);
          found.push({ A, D, h, tip });
          landed = true;
          break;
        }
      }
    }
    for (const c of found) this.resolveHit(c.A, c.D, c.h, c.tip, false);
  }

  // ------------------------------------------------------------------ projectiles
  spawnProjectile(f, pd) {
    if (f.projectile && this.projectiles.includes(f.projectile)) return;
    const tip = f.tips[pd.from] || { x: f.x, y: 60 };
    const pr = {
      owner: f, def: pd, x: tip.x + f.facing * 4, y: Math.max(pd.r, tip.y),
      vx: f.facing * pd.vx, vy: pd.vy, g: pd.g, r: pd.r, life: pd.life,
      color: mix(f.ch.accent, { r: 255, g: 255, b: 255 }, 0.25), spin: 0, kind: f.ch.id,
    };
    this.projectiles.push(pr);
    f.projectile = pr;
  }

  updateProjectiles() {
    const list = this.projectiles;
    for (const pr of list) {
      if (pr.owner.hitstop > 0 && pr.life > pr.def.life - 0.05) continue;
      pr.x += pr.vx * DT;
      pr.vy -= pr.g * DT;
      pr.y += pr.vy * DT;
      pr.life -= DT;
      pr.spin += 18;
      if (pr.def.ground && pr.y <= pr.r) { pr.y = pr.r; pr.dead = true; this.spark(pr.x, pr.r, pr.color, 10); this.sound("block"); this.fx("dust", { x: pr.x, small: true }); }
      if (pr.life <= 0 || Math.abs(pr.x) > this.halfW + 40) pr.dead = true;
    }
    // projectile vs projectile
    for (let a = 0; a < list.length; a++) for (let b = a + 1; b < list.length; b++) {
      const p = list[a], q = list[b];
      if (p.dead || q.dead || p.owner.team === q.owner.team) continue;
      if (Math.hypot(p.x - q.x, p.y - q.y) < p.r + q.r) {
        p.dead = q.dead = true;
        this.spark((p.x + q.x) / 2, (p.y + q.y) / 2, { r: 255, g: 255, b: 255 }, 14);
        this.sound("block");
      }
    }
    // projectile vs fighters
    for (const pr of list) {
      if (pr.dead) continue;
      for (const D of this.enemies(pr.owner)) {
        if (!D.strikeable()) continue;
        if (!D.overlaps(pr.x, pr.y, pr.r)) continue;
        const d = pr.def;
        const h = { dmg: d.dmg, level: d.level, hitstun: d.hitstun, blockstun: d.blockstun, push: d.push, hitstop: 6, snd: "heavy", chip: d.chip };
        this.resolveHit(pr.owner, D, h, { x: pr.x, y: pr.y }, true);
        pr.dead = true;
        break;
      }
    }
    for (const pr of list) if (pr.dead) {
      if (pr.owner.projectile === pr) pr.owner.projectile = null;
      this.fx("pop", { x: pr.x, y: pr.y, kind: pr.kind, color: pr.color });
    }
    this.projectiles = list.filter((pr) => !pr.dead);
  }

  teleportBehind(f) {
    const t = this.nearestEnemy(f);
    const lim = this.halfW - f.ch.stats.pushW;
    let x;
    if (t) {
      x = t.x - t.facing * 48;
      if (Math.abs(x) > lim) x = t.x + t.facing * 48;
    } else x = -f.x;
    f.x = clamp(x, -lim, lim);
    if (t) f.facing = t.x >= f.x ? 1 : -1;
    this.spark(f.x, 50, f.ch.accent, 12);
    this.sound("special");
  }

  // ------------------------------------------------------------------ main step
  step() {
    this.frame++;
    const dtPhase = DT;
    this.phaseT += dtPhase;
    // CPU brains produce their inputs first
    for (const i of this.seated()) {
      const s = this.seats[i];
      if (s.kind === "cpu" && s.brain) {
        const [held, pressed] = s.brain.think();
        this.fighters[i].setInput(held, pressed);
      }
    }
    const slow = this.slowmo > 0 && (this.frame % 3 !== 0);
    if (this.slowmo > 0) this.slowmo--;
    if (!slow) {
      for (let i = 0; i < 4; i++) {
        const f = this.fighters[i];
        if (!this.seats[i].kind) { f.readInput(); continue; }
        f.step();
      }
      this.resolvePush();
      this.updateFacing();
    } else {
      for (let i = 0; i < 4; i++) this.fighters[i].readInput();
    }
    this.lobbyInput();
    for (let i = 0; i < 4; i++) if (this.fighters[i].onStage) this.fighters[i].animate();
    if (!slow) {
      if (this.phase === "fight") { this.checkHits(); this.updateProjectiles(); }
    }
    this.updatePhase();
    this.updateSparks();
    this.updateCamera();
    this.updateHud();
  }

  resolvePush() {
    const act = this.active.map((i) => this.fighters[i]).filter((f) => f.active);
    const solid = (f) => !f.ko && f.state !== "down" && f.state !== "thrown" && f.state !== "launch" && f.state !== "getup";
    for (let a = 0; a < act.length; a++) for (let b = a + 1; b < act.length; b++) {
      const A = act[a], B = act[b];
      if (!solid(A) || !solid(B)) continue;
      if (this.mode === "teams" && A.team === B.team) continue;
      if (Math.abs(A.y - B.y) > 46) continue;
      const w = A.ch.stats.pushW + B.ch.stats.pushW;
      let dx = B.x - A.x;
      if (Math.abs(dx) < 0.01) dx = A.facing > 0 ? 0.01 : -0.01;
      const overlap = w - Math.abs(dx);
      if (overlap <= 0) continue;
      const s = Math.sign(dx);
      const limA = this.halfW - A.ch.stats.pushW, limB = this.halfW - B.ch.stats.pushW;
      let ma = overlap / 2, mb = overlap / 2;
      if (Math.abs(A.x - s * ma) > limA) { mb += ma; ma = 0; }
      if (Math.abs(B.x + s * mb) > limB) { ma += mb; mb = 0; }
      A.x = clamp(A.x - s * ma, -limA, limA);
      B.x = clamp(B.x + s * mb, -limB, limB);
    }
  }

  updateFacing() {
    for (const i of this.active) {
      const f = this.fighters[i];
      if (!f.active || f.ko || !TURNABLE.has(f.state) || f.airborne) continue;
      const t = this.nearestEnemy(f);
      if (!t) continue;
      if (t.x > f.x + 1) f.facing = 1;
      else if (t.x < f.x - 1) f.facing = -1;
    }
  }

  updatePhase() {
    const t = this.phaseT;
    switch (this.phase) {
      case "lobby":
        if (this.canStart() && this.allReady() && this.humans().length + (this.forceCpuMatch ? 1 : 0) > 0) {
          this.phase = "countdown"; this.phaseT = 0; this.countdown = this.cfg.countdown; this.sound("tick");
        }
        break;
      case "countdown": {
        if (!this.canStart() || !this.allReady()) { this.cancelCountdown(); break; }
        const left = Math.ceil(this.cfg.countdown - t);
        if (left !== this.countdown) { this.countdown = left; if (left > 0) this.sound("tick"); }
        if (t >= this.cfg.countdown) this.startMatch();
        break;
      }
      case "intro":
        if (t >= 1.9) { this.phase = "fight"; this.phaseT = 0; }
        break;
      case "fight": {
        if (this.slowmo <= 0) this.roundTimer = Math.max(0, this.roundTimer - DT);
        if (this.tagMode) this.updateTag();
        const alive = this.aliveTeams();
        if (alive.length <= 1) { this.endRound(alive.length ? alive[0] : -1, "ko"); break; }
        if (this.roundTimer <= 0) {
          let best = -1, bestV = -1, tie = false;
          for (const team of alive) {
            let v = 0;
            for (const i of this.active) { const f = this.fighters[i]; if (f.team === team && !f.ko) v += f.hp / f.maxHp; }
            if (v > bestV + 1e-6) { best = team; bestV = v; tie = false; } else if (Math.abs(v - bestV) <= 1e-6) tie = true;
          }
          this.endRound(tie ? -1 : best, "time");
        }
        break;
      }
      case "roundEnd":
        if (t >= 3.2) {
          const need = this.cfg.roundsToWin;
          const decided = this.activeTeams().some((tm) => this.teamWins[tm] >= need) || this.roundNum >= this.cfg.maxRounds;
          if (decided) this.finishMatch(); else this.startRound();
        }
        break;
      case "matchEnd":
        if (t >= 3.6) this.afterMatch();
        break;
      case "nextUp":
        if (t >= 2.6) this.startMatch();
        break;
    }
  }

  updateSparks() {
    for (const s of this.sparks) if (s.life > 0) s.life--;
  }

  updateCamera() {
    const c = this.cam;
    let xs = [];
    if (this.inMatch() && this.phase !== "nextUp") {
      for (const i of this.active) { const f = this.fighters[i]; if (f.onStage && !f.background) xs.push(f.x); }
    } else {
      for (let i = 0; i < 4; i++) if (this.fighters[i].onStage) xs.push(this.fighters[i].x);
    }
    let cx = 0, half = Math.min(this.halfW, 240);
    if (xs.length) {
      const lo = Math.min(...xs), hi = Math.max(...xs);
      cx = (lo + hi) / 2;
      half = clamp((hi - lo) / 2 + 95, 160, this.halfW + 30);
    }
    if (half < this.halfW) cx = clamp(cx, -this.halfW + half * 0.92, this.halfW - half * 0.92);
    else cx = 0;
    c.cx = lerp(c.cx, cx, 0.12);
    c.half = lerp(c.half, half, 0.07);
    c.cy = 52;
    c.shake *= 0.84;
    if (c.shake < 0.05) c.shake = 0;
  }

  // ------------------------------------------------------------------ HUD model
  makeHud() {
    this.comboText = ["", "", "", ""];
    const card = () => ({ show: false, name: "", fighter: "", color: 0, hp: 100, wins: 0, need: 2, combo: "", comboKind: "", best: "", ko: false, bench: false, side: "L", you: -1 });
    return {
      inLobby: true, inMatch: false,
      mode: "", timer: "", round: "",
      cards: [card(), card(), card(), card()],
      announce: { text: "", style: "", show: false, id: 0 },
      lobby: { title: "PUPPET BRAWL", mode: "", lines: ["", "", "", ""], hint: "", count: "" },
      seat: [0, 1, 2, 3].map(() => ({ me: "", moves: "", motions: "", status: "" })),
      footer: "",
      queue: "",
    };
  }

  cardSeats() {
    // which seat shows on which of the 4 HUD cards (top-left, top-right, second row left/right)
    const out = [-1, -1, -1, -1];
    if (!this.inMatch()) return out;
    if (this.mode === "duel") {
      out[0] = this.active[0] ?? -1;
      out[1] = this.active[1] ?? -1;
      return out;
    }
    if (this.mode === "teams") {
      const t0 = this.active.filter((i) => i < 2).sort(), t1 = this.active.filter((i) => i >= 2).sort();
      out[0] = t0[0] ?? -1; out[2] = t0[1] ?? -1; out[1] = t1[0] ?? -1; out[3] = t1[1] ?? -1;
      return out;
    }
    const s = this.active.slice().sort((a, b) => a - b);
    out[0] = s[0] ?? -1; out[1] = s[1] ?? -1; out[2] = s[2] ?? -1; out[3] = s[3] ?? -1;
    return out;
  }

  updateHud() {
    const H = this.hud;
    H.inLobby = !this.inMatch();
    H.inMatch = this.inMatch();
    H.mode = MODE_LABEL[this.mode] + (this.pendingMode ? "  >  " + MODE_SHORT[this.pendingMode] : "");
    H.timer = (this.phase === "fight" || this.phase === "intro" || this.phase === "roundEnd") ? String(Math.ceil(this.roundTimer)) : "";
    H.round = this.inMatch() ? "ROUND " + Math.max(1, this.roundNum) : "";
    const cs = this.cardSeats();
    for (let c = 0; c < 4; c++) {
      const card = H.cards[c], seat = cs[c];
      if (seat < 0 || !this.seats[seat].kind) { card.show = false; continue; }
      const f = this.fighters[seat];
      card.show = true;
      card.name = this.displayName(seat);
      card.fighter = f.ch.name + (this.tagMode && f.background ? (f.ko ? "  \u00B7  OUT" : "  \u00B7  BENCH") : "");
      card.color = this.mode === "teams" ? (seat < 2 ? (seat === 0 ? 0 : 4) : (seat === 2 ? 1 : 5)) : seat;
      card.hp = Math.round(100 * clamp(f.hp / Math.max(1, f.maxHp), 0, 1));
      card.wins = this.teamWins[f.team] || 0;
      card.need = this.cfg.roundsToWin;
      card.ko = f.ko;
      card.bench = this.tagMode && f.background;
      card.side = c % 2 === 0 ? "L" : "R";
      card.seat = seat;
      if (this.comboTimers[seat] > 0) { this.comboTimers[seat]--; card.combo = this.comboText[seat]; card.comboKind = this.comboKind[seat]; }
      else { card.combo = ""; card.comboKind = ""; }
      const best = this.bestCombo[seat], pf = f.perfects;
      card.best = (best >= 2 ? "BEST " + best + " HITS" : "") + (pf ? (best >= 2 ? "   " : "") + pf + " PERFECT" + (pf > 1 ? "S" : "") : "");
    }
    // announcer queue
    const A = H.announce;
    if (this.announceTimer > 0) {
      this.announceTimer -= DT;
      if (this.announceTimer <= 0) { A.show = false; this.announceGap = 2; }
    } else if (this.announceGap > 0) {
      this.announceGap--;
    } else if (this.announceQueue.length) {
      const a = this.announceQueue.shift();
      A.text = a.text; A.style = a.style; A.show = true; A.id++;
      this.announceTimer = a.seconds;
    }
    // lobby panel
    const L = H.lobby;
    L.mode = "MODE:  " + MODE_LABEL[this.mode] + (this.pendingMode ? "  \u00B7  next: " + MODE_SHORT[this.pendingMode] : "");
    for (let i = 0; i < 4; i++) {
      const s = this.seats[i], f = this.fighters[i];
      let line = this.seatLabel(i) + "  ";
      if (this.mode === "teams") line += (i < 2 ? "RED  \u00B7  " : "BLUE  \u00B7  ");
      if (!s.kind) line += "open  \u00B7  stand on pad " + (i + 1) + " and press E";
      else {
        line += this.displayName(i) + "  \u00B7  " + f.ch.name + "  \u00B7  ";
        line += s.kind === "cpu" ? "CPU" : s.ready ? "READY" : "picking...";
        if (this.mode === "duel" && this.inMatch()) {
          const qi = this.queue.indexOf(i);
          if (this.active.includes(i)) line += "  \u00B7  fighting";
          else if (qi >= 0) line += "  \u00B7  queue #" + (qi - 1 > 0 ? qi - 1 : 1);
        }
      }
      L.lines[i] = line;
    }
    const host = this.hostSeat();
    if (this.phase === "countdown") L.count = "STARTING IN " + Math.max(1, this.countdown);
    else if (!this.canStart()) L.count = this.mode === "teams" ? "Need someone on each team (pads 1-2 RED vs 3-4 BLUE)" : "Need 2 fighters - get a friend or add a CPU";
    else if (!this.allReady()) L.count = "Waiting for everyone to press MOUSE1 (ready)";
    else L.count = "";
    L.hint = host >= 0 ? this.displayName(host) + " is host:  R change mode  \u00B7  F add / clear CPUs" : "";
    // per seat
    for (let i = 0; i < 4; i++) {
      const s = this.seats[i], f = this.fighters[i], out = H.seat[i];
      if (!s.kind) { out.me = ""; out.moves = ""; out.motions = ""; out.status = ""; continue; }
      const ch = f.ch;
      out.me = "YOU: " + this.seatLabel(i) + " " + (this.mode === "teams" ? TEAM_NAMES[i < 2 ? 0 : 1] : PLAYER_COLOR_NAMES[i]) + "  \u00B7  " + ch.name + "  \u00B7  " + ch.tag;
      out.moves = "R: " + MOVES[ch.specials[0]].name + "  \u00B7  FWD+R: " + MOVES[ch.specials[1]].name + "  \u00B7  DOWN+R: " + MOVES[ch.specials[2]].name;
      out.motions = "or motions:  " + ch.specials.map((id) => MOVES[id].motion.join(",") + "+" + MOVES[id].btn).join("  \u00B7  ") +
        (ch.combos ? "     COMBOS  P,P: " + MOVES[ch.combos.p].name + "  \u00B7  P,P,K  \u00B7  P,K: " + MOVES[ch.combos.mix].name + (MOVES[ch.combos.mix].hits[0].level === "low" ? " (LOW)" : " (OVERHEAD)") + "  \u00B7  K,K: " + MOVES[ch.combos.k].name : "");
      if (!this.inMatch() || (this.mode === "duel" && !this.active.includes(i))) {
        out.status = s.ready ? "Locked in  \u00B7  MOUSE2 to change" : "A / D pick a fighter  \u00B7  MOUSE1 ready";
      } else if (!this.active.includes(i)) out.status = "Match in progress - you're in the next one";
      else if (this.tagMode) {
        const partner = this.partnerOf(f);
        if (f.background) out.status = f.ko ? "Knocked out - cheer your partner on" : "On the bench - your partner can tag you in (SHIFT+R)" + (f.benchHeal > 0 ? "  \u00B7  recovering" : "");
        else if (!partner) out.status = "Last one standing!";
        else out.status = this.tagCD[f.team] > 0 ? "Tag ready in " + Math.ceil(this.tagCD[f.team] / SIM_HZ) : "SHIFT+R: tag in " + this.displayName(partner.seat);
      } else out.status = "";
    }
    if (this.mode === "duel" && this.inMatch()) {
      const waiting = this.queue.filter((q) => !this.active.includes(q));
      const streak = this.streak > 1 && this.champion >= 0 ? "STREAK: " + this.displayName(this.champion) + " x" + this.streak : "";
      H.queue = waiting.length ? "NEXT UP: " + this.displayName(waiting[0]) + (streak ? "  \u00B7  " + streak : "") : streak;
    } else H.queue = "";
    H.footer = "A/D move  \u00B7  W jump  \u00B7  S crouch  \u00B7  MOUSE1 punch  \u00B7  MOUSE2 kick  \u00B7  SHIFT block  \u00B7  R special  \u00B7  F throw  \u00B7  hold E to leave";
  }

  // ------------------------------------------------------------------ render export
  // Calls fn(partIndex, part) for each fighter part; projectiles and sparks separately.
  renderState() {
    return { fighters: this.fighters, projectiles: this.projectiles, sparks: this.sparks, cam: this.cam };
  }
}

// =====================================================================================
//  CPU brain - presses the same virtual buttons a player would.
// =====================================================================================
const AI_LEVELS = [
  { react: [20, 30], block: 0.2, aggro: 0.45, special: 0.12, antiAir: 0.2, punish: 0.25, throwP: 0.08, tech: 0.05, perfect: 0.04 },
  { react: [11, 18], block: 0.5, aggro: 0.6, special: 0.2, antiAir: 0.45, punish: 0.5, throwP: 0.12, tech: 0.2, perfect: 0.12 },
  { react: [6, 11], block: 0.72, aggro: 0.7, special: 0.24, antiAir: 0.7, punish: 0.8, throwP: 0.15, tech: 0.4, perfect: 0.25 },
];

class CpuBrain {
  constructor(game, fighter, level) {
    this.g = game; this.f = fighter;
    this.L = AI_LEVELS[clamp(level | 0, 0, 2)];
    this.plan = [];
    this.cool = 10;
    this.seenSerial = -1;
    this.lastHeld = 0;
    this.techAt = -2;        // -2: not grabbed, -1: decided not to break, n: break on state frame n
  }

  // steps: { dir: 1 toward | -1 away | 0, down, up, block, press: [bits], frames }
  push(...steps) { for (const s of steps) this.plan.push(Object.assign({ dir: 0, frames: 1, t: 0 }, s)); }

  bitsFor(step) {
    const f = this.f;
    let held = 0;
    if (step.dir > 0) held |= f.towardBit();
    if (step.dir < 0) held |= f.awayBit();
    if (step.down) held |= IN.DOWN;
    if (step.up) held |= IN.UP;
    if (step.block) held |= IN.BLOCK;
    let pressed = 0;
    if (step.t === 0 && step.press) for (const b of step.press) pressed |= b;
    return [held | pressed, pressed];
  }

  think() {
    const g = this.g, f = this.f, L = this.L, R = g.rng;
    if (!f.active || f.ko || g.phase !== "fight") { this.plan.length = 0; return [0, 0]; }
    // grabbed: one roll per throw to break it a few frames in, like a person reacting
    if (f.state === "thrown") {
      this.plan.length = 0;
      if (this.techAt === -2) this.techAt = R.chance(L.tech) ? f.sf + R.int(1, 4) : -1;
      return this.techAt >= 0 && f.sf >= this.techAt ? [IN.THROW, IN.THROW] : [0, 0];
    }
    this.techAt = -2;
    const t = g.nearestEnemy(f);
    if (!t) return [0, 0];
    const dist = Math.abs(t.x - f.x);
    // defence: notice new enemy attacks (one roll per move)
    if (t.state === "attack" && t.move && t.moveSerial !== this.seenSerial && NEUTRAL.has(f.state)) {
      this.seenSerial = t.moveSerial;
      const reach = 70 * t.ch.legF + (t.move.def.vel ? 70 : 0);
      if (dist < reach && R.chance(L.block)) {
        const low = t.move.hits.some((h) => h.level === "low");
        const air = t.move.hits.some((h) => h.level === "air" || h.level === "over");
        const left = Math.max(6, t.move.total - t.mf);
        this.plan.length = 0;
        // a CPU reacts on the attack's first frame, which would make every block perfect:
        // only some of them count, more often on harder levels
        f.perfectOk = R.chance(L.perfect || 0);
        this.push({ block: 1, down: low && !air ? 1 : 0, frames: Math.min(left, 40) });
      }
    }
    // incoming projectile
    if (!this.plan.length && NEUTRAL.has(f.state)) {
      for (const pr of g.projectiles) {
        if (pr.owner.team === f.team) continue;
        const dx = pr.x - f.x;
        if (Math.sign(pr.vx) !== -Math.sign(dx) || Math.abs(dx) > 160) continue;
        if (R.chance(0.08 + L.block * 0.08)) {
          if (R.chance(0.5)) this.push({ block: 1, frames: 24 });
          else this.push({ dir: 1, up: 1, press: [IN.UP], frames: 2 }, { dir: 1, frames: 14 }, { press: [IN.KICK], frames: 10 });
          break;
        }
      }
    }
    if (this.plan.length) {
      const step = this.plan[0];
      const out = this.bitsFor(step);
      step.t++;
      if (step.t >= step.frames) this.plan.shift();
      return out;
    }
    if (this.cool > 0) { this.cool--; return [this.idleHold(t, dist), 0]; }
    if (!NEUTRAL.has(f.state) && f.state !== "land") return [0, 0];
    this.decide(t, dist);
    this.cool = R.int(L.react[0], L.react[1]);
    return [0, 0];
  }

  idleHold(t, dist) {
    const f = this.f;
    if (dist > 120) return f.towardBit();
    if (dist < 34 && this.g.rng.chance(0.02)) return f.awayBit();
    return this.lastHeld;
  }

  hasProjectile() {
    const m = MOVES[this.f.ch.specials[0]];
    return !!m.projectile;
  }

  decide(t, dist) {
    const f = this.f, L = this.L, R = this.g.rng;
    const P = IN.PUNCH, K = IN.KICK, S = IN.SPECIAL;
    this.lastHeld = 0;
    // tag team: swap out when hurt and the partner is in better shape
    if (this.g.canTag(f)) {
      const mate = this.g.partnerOf(f);
      if (mate && f.hp / f.maxHp < 0.45 && mate.hp / mate.maxHp > f.hp / f.maxHp + 0.2 && R.chance(0.35)) { this.push({ block: 1, frames: 2 }, { block: 1, press: [S], frames: 2 }); return; }
    }
    // anti-air
    if (t.airborne && t.state !== "launch" && dist < 110 && R.chance(L.antiAir)) {
      if (dist < 60) {
        if (R.chance(0.5)) this.push({ down: 1, press: [S], frames: 2 });
        else this.push({ down: 1, frames: 3 }, { down: 1, press: [P], frames: 2 });
      } else this.push({ dir: -1, frames: 8 }, { block: 1, frames: 10 });
      return;
    }
    // punish recovery
    if (t.state === "attack" && t.move && t.mf > (t.move.hits[t.move.hits.length - 1]?.to ?? 0) + 2 && dist < 70 && R.chance(L.punish)) {
      const pick = R.int(0, 2);
      if (pick === 0) this.push({ down: 1, press: [P], frames: 2 });
      else if (pick === 1) this.push({ down: 1, press: [K], frames: 2 });
      else this.push({ press: [P], frames: 3 }, { press: [P], frames: 4 }, { dir: 1, press: [P], frames: 2 });
      return;
    }
    // knocked-down opponent: wait at a safe distance
    if (t.state === "down" || t.state === "getup") {
      if (dist > 70) this.push({ dir: 1, frames: 10 }); else this.push({ block: 1, frames: 12 });
      return;
    }
    if (dist > 175) {
      const r = R();
      if (r < 0.22 && this.hasProjectile() && !f.projectile) this.push({ press: [S], frames: 2 });
      else if (r < 0.34) this.push({ dir: 1, press: [f.towardBit()], frames: 1 }, { frames: 2 }, { dir: 1, press: [f.towardBit()], frames: 2 });
      else if (r < 0.42) this.push({ dir: 1, up: 1, press: [IN.UP], frames: 2 }, { dir: 1, frames: 12 }, { press: [K], frames: 8 });
      else this.push({ dir: 1, frames: R.int(18, 34) });
      return;
    }
    if (dist > 85) {
      const r = R();
      if (r < 0.2) this.push({ dir: 1, press: [K], frames: 2 });
      else if (r < 0.2 + L.special * 0.6) this.push({ dir: 1, press: [S], frames: 2 });
      else if (r < 0.5) this.push({ dir: 1, up: 1, press: [IN.UP], frames: 2 }, { dir: 1, frames: R.int(10, 16) }, { press: [R.chance(0.6) ? K : P], frames: 8 });
      else if (r < 0.62 && this.hasProjectile() && !f.projectile) this.push({ press: [S], frames: 2 });
      else if (r < 0.7) this.push({ block: 1, frames: 14 });
      else this.push({ dir: 1, frames: R.int(10, 22) });
      return;
    }
    // close range
    const r = R();
    if (dist < 42 && r < L.throwP) { this.push({ press: [IN.THROW], frames: 2 }); return; }
    if (r < 0.26 * L.aggro / 0.6) {
      // combo strings: P,P / P,P,K / P,K (the mix-up ender) / jab into straight
      const pick = R.int(0, 3);
      if (pick === 0) this.push({ press: [P], frames: 4 }, { frames: 2 }, { press: [P], frames: 3 });
      else if (pick === 1) this.push({ press: [P], frames: 4 }, { frames: 2 }, { press: [P], frames: 3 }, { frames: 14 }, { press: [K], frames: 3 });
      else if (pick === 2) this.push({ press: [P], frames: 4 }, { frames: 2 }, { press: [K], frames: 3 });
      else this.push({ press: [P], frames: 3 }, { press: [P], frames: 4 }, { dir: 1, press: [P], frames: 3 });
    }
    else if (r < 0.4) { if (R.chance(0.5)) this.push({ press: [K], frames: 4 }, { frames: 4 }, { press: [K], frames: 3 }); else this.push({ press: [K], frames: 2 }); }
    else if (r < 0.5) this.push({ down: 1, frames: 2 }, { down: 1, press: [K], frames: 2 });
    else if (r < 0.56) this.push({ down: 1, frames: 2 }, { down: 1, press: [P], frames: 2 });
    else if (r < 0.56 + L.special * 0.5) this.push({ dir: R.chance(0.5) ? 1 : 0, press: [S], frames: 2 });
    else if (r < 0.74) this.push({ block: 1, frames: R.int(10, 22) });
    else if (r < 0.82) this.push({ dir: -1, press: [f.awayBit()], frames: 1 }, { frames: 2 }, { dir: -1, press: [f.awayBit()], frames: 2 });
    else this.push({ dir: -1, frames: R.int(8, 16) });
  }
}
