// ===================================================================================
// The match: squads, floors as chains of vault rooms drawn from the pool, staging, the breach and the showdown.
// Pure: it is given players (ids + side), time, and events (room cleared, player died); it emits orders the adapter carries out.
// ===================================================================================
const PHASE = { LOBBY: 'LOBBY', FLOORS: 'FLOORS', STAGING: 'STAGING', SHOWDOWN: 'SHOWDOWN', END: 'END' };

// how many squads of what size for n players: as many squads as possible up to SQUADS_MAX, sizes as even as possible
function squadPlan(n) {
  if (n < 1) return [];
  if (n === 1) return [1];   // solo: one squad, the showdown runs down the clock (checkWinner needs 2+ squads)
  // about five per squad: 10 -> 2x5, 20 -> 4x5, 32 -> 6, 48 -> 8x6, 64 -> 8x8; never fewer than 2 squads or more than SQUADS_MAX
  const k = clamp(Math.round(n / 5), 2, CONFIG.SQUADS_MAX);
  return Array.from({ length: k }, (_, i) => Math.floor(n / k) + (i < n % k ? 1 : 0));
}

class Squad {
  constructor(id, members) {
    this.id = id; this.members = members.slice();   // player ids
    this.floor = 0; this.room = -1; this.roomStart = 0; this.rooms = [];   // rooms visited (ids)
    this.cleared = 0; this.kills = 0; this.nanites = 0; this.staged = false; this.stagedAt = 0;
    this.alive = members.length; this.eliminated = false; this.place = 0;
  }
}

class Match {
  constructor(layout, seed, opts) {
    this.L = layout; this.rng = new Rng(seed); this.seed = seed;
    this.phase = PHASE.LOBBY; this.t = 0; this.phaseStart = 0;
    this.squads = []; this.squadOf = new Map();          // player id -> squad
    this.roomBusy = new Map();                            // room id -> squad id
    this.orders = [];                                     // what the adapter must do this tick
    this.ringStep = 0; this.winner = null; this.log = (opts && opts.log) || (() => {});
    this.floorEndsAt = 0; this.stagingEndsAt = 0; this.showdownEndsAt = 0;
  }
  order(o) { this.orders.push(o); }
  drain() { const o = this.orders; this.orders = []; return o; }

  // ---- lobby -> floors
  start(players, now) {
    // players: [{id, side}] ; squads are mixed-side so the CS2 round can be awarded to the winning squad's side
    const sizes = squadPlan(players.length);
    if (!sizes.length) return false;
    const ids = this.rng.shuffle(players.map((p) => p.id));
    this.squads = []; this.squadOf.clear(); this.roomBusy.clear();
    let at = 0;
    sizes.forEach((sz, i) => { const s = new Squad(i, ids.slice(at, at + sz)); at += sz; this.squads.push(s); s.members.forEach((m) => this.squadOf.set(m, s)); });
    this.phase = PHASE.FLOORS; this.phaseStart = now; this.t = now;
    this.floorEndsAt = now + CONFIG.FLOORS * CONFIG.FLOOR_TIME + 10;
    this.log(`run started: ${players.length} players, squads ${sizes.join('+')}, seed ${this.seed}`);
    for (const s of this.squads) this.sendToNextRoom(s, now);
    return true;
  }

  freeRoom(s) {
    // a room nobody is in, preferring kinds this squad hasn't seen; never the room it is in
    const cand = this.L.rooms.filter((r) => !this.roomBusy.has(r.id) && r.id !== s.room);
    if (!cand.length) return null;
    const seen = new Set(s.rooms.map((id) => this.L.rooms[id].kind));
    const fresh = cand.filter((r) => !seen.has(r.kind));
    return this.rng.pick(fresh.length ? fresh : cand);
  }

  sendToNextRoom(s, now) {
    if (s.room >= 0) this.roomBusy.delete(s.room);
    if (s.floor >= CONFIG.FLOORS) return this.sendToStaging(s, now);
    const r = this.freeRoom(s);
    if (!r) { this.log(`squad ${s.id}: no free room, straight to staging`); return this.sendToStaging(s, now); }
    s.floor += 1; s.room = r.id; s.rooms.push(r.id); s.roomStart = now; this.roomBusy.set(r.id, s.id);
    const n = Math.round((CONFIG.WAVE_BASE + CONFIG.WAVE_PER_PLAYER * s.members.length) * CONFIG.WAVE_FLOOR_SCALE[s.floor - 1]);
    this.order({ op: 'teleport', squad: s.id, to: r.name + '_in', members: s.members });
    this.order({ op: 'wave', squad: s.id, room: r.id, floor: s.floor, count: n, boss: s.floor === CONFIG.FLOORS });
    this.order({ op: 'msg', squad: s.id, text: `FLOOR ${s.floor} / ${CONFIG.FLOORS}: ${r.kind.toUpperCase()} VAULT` });
  }

  sendToStaging(s, now) {
    if (s.room >= 0) { this.order({ op: 'clearRoom', room: s.room }); this.roomBusy.delete(s.room); }
    s.room = -1; s.staged = true; s.stagedAt = now;
    this.order({ op: 'teleport', squad: s.id, to: 'nt_stage_' + (s.id % this.L.stagings.length), members: s.members });
    this.order({ op: 'msg', squad: s.id, text: 'STAGING: BUY UP. THE BREACH IS COMING.' });
    if (this.squads.every((q) => q.staged || q.eliminated)) {
      this.phase = PHASE.STAGING; this.phaseStart = now; this.stagingEndsAt = now + CONFIG.STAGING_TIME;
      this.order({ op: 'msgAll', text: `ALL SQUADS THROUGH. BREACH IN ${CONFIG.STAGING_TIME} S.` });
    }
  }

  // ---- events from the adapter
  roomCleared(roomId, now) {
    const sid = this.roomBusy.get(roomId); if (sid === undefined) return;
    const s = this.squads[sid]; s.cleared += 1; s.nanites += CONFIG.NANITES_ROOM_CLEAR;
    this.order({ op: 'reward', squad: s.id, members: s.members, amount: CONFIG.NANITES_ROOM_CLEAR, why: 'room clear' });
    this.order({ op: 'openExit', room: roomId, squad: s.id });
  }
  exitTouched(roomId, now) {
    const sid = this.roomBusy.get(roomId); if (sid === undefined) return;
    this.sendToNextRoom(this.squads[sid], now);
  }
  enemyKilled(playerId, kind) {
    const s = this.squadOf.get(playerId); if (!s) return;
    s.kills += 1; const amt = (ENEMIES[kind] || { nanites: 100 }).nanites; s.nanites += amt;
    this.order({ op: 'reward', squad: s.id, members: [playerId], amount: amt, why: kind });
  }
  playerDied(playerId, killerId) {
    const s = this.squadOf.get(playerId); if (!s) return;
    s.alive = Math.max(0, s.alive - 1);
    if (killerId !== undefined && killerId !== null) {
      const k = this.squadOf.get(killerId);
      if (k && k !== s) { k.nanites += CONFIG.NANITES_PVP_KILL; this.order({ op: 'reward', squad: k.id, members: [killerId], amount: CONFIG.NANITES_PVP_KILL, why: 'squad kill' }); }
    }
    if (this.phase === PHASE.SHOWDOWN && s.alive === 0 && !s.eliminated) {
      s.eliminated = true; s.place = this.squads.filter((q) => !q.eliminated).length + 1;
      this.order({ op: 'msgAll', text: `SQUAD ${s.id + 1} ELIMINATED` });
      this.checkWinner();
    } else if (this.phase === PHASE.FLOORS && s.alive === 0 && !s.eliminated) {
      // a squad wiped in the vaults waits in staging as spectators of its own fate; it still gets a place
      s.eliminated = true; s.place = this.squads.length;
      this.order({ op: 'msgAll', text: `SQUAD ${s.id + 1} FELL IN THE VAULTS` });
      if (s.room >= 0) { this.order({ op: 'clearRoom', room: s.room }); this.roomBusy.delete(s.room); s.room = -1; }
      s.staged = true;
      if (this.squads.every((q) => q.staged || q.eliminated) && this.phase === PHASE.FLOORS) {
        this.phase = PHASE.STAGING; this.phaseStart = this.t; this.stagingEndsAt = this.t + CONFIG.STAGING_TIME;
      }
      this.checkWinner();
    }
  }
  playerLeft(playerId) {
    const s = this.squadOf.get(playerId); if (!s) return;
    s.members = s.members.filter((m) => m !== playerId); this.squadOf.delete(playerId);
    s.alive = Math.min(s.alive, s.members.length);
    if (!s.members.length && !s.eliminated) { s.eliminated = true; s.place = this.squads.length; if (s.room >= 0) { this.order({ op: 'clearRoom', room: s.room }); this.roomBusy.delete(s.room); s.room = -1; } this.checkWinner(); }
  }
  respawned(playerId) { const s = this.squadOf.get(playerId); if (s && !s.eliminated) s.alive = Math.min(s.members.length, s.alive + 1); }

  checkWinner() {
    const live = this.squads.filter((q) => !q.eliminated);
    if (live.length <= 1 && this.phase !== PHASE.END && this.squads.length > 1) {
      this.winner = live[0] || null; this.phase = PHASE.END; this.phaseStart = this.t;
      this.order({ op: 'end', winner: this.winner ? this.winner.id : null });
    }
  }

  // ---- clock
  tick(now) {
    this.t = now;
    if (this.phase === PHASE.FLOORS) {
      for (const s of this.squads) {
        if (s.room >= 0 && now - s.roomStart > CONFIG.FLOOR_TIME) { this.order({ op: 'msg', squad: s.id, text: 'THE VAULT SEALS. MOVING ON.' }); this.order({ op: 'clearRoom', room: s.room }); this.sendToNextRoom(s, now); }
      }
      if (now > this.floorEndsAt) { for (const s of this.squads) if (!s.staged && !s.eliminated) this.sendToStaging(s, now); if (this.phase === PHASE.FLOORS) { this.phase = PHASE.STAGING; this.phaseStart = now; this.stagingEndsAt = now + CONFIG.STAGING_TIME; } }
    } else if (this.phase === PHASE.STAGING) {
      if (now >= this.stagingEndsAt) this.breach(now);
    } else if (this.phase === PHASE.SHOWDOWN) {
      const step = Math.floor((now - this.phaseStart) / CONFIG.RING_EVERY);
      if (step > this.ringStep) { this.ringStep = step; this.order({ op: 'ring', step }); this.order({ op: 'msgAll', text: 'THE BARRIERS CLOSE IN' }); }
      if (now >= this.showdownEndsAt) this.timeUp();
    }
  }
  breach(now) {
    this.phase = PHASE.SHOWDOWN; this.phaseStart = now; this.ringStep = 0; this.showdownEndsAt = now + CONFIG.SHOWDOWN_TIME;
    const live = this.squads.filter((q) => !q.eliminated);
    live.forEach((s, i) => { s.alive = s.members.length; this.order({ op: 'teleport', squad: s.id, to: 'nt_arena_' + (i % this.L.arena.balconies.length), members: s.members }); });
    this.order({ op: 'msgAll', text: 'THE BREACH. LAST SQUAD STANDING.' });
    if (live.length <= 1) this.checkWinner();
  }
  timeUp() {
    // most alive, then most nanites
    const live = this.squads.filter((q) => !q.eliminated).sort((a, b) => b.alive - a.alive || b.nanites - a.nanites);
    this.winner = live[0] || null; this.phase = PHASE.END; this.phaseStart = this.t;
    this.order({ op: 'end', winner: this.winner ? this.winner.id : null, timeUp: true });
  }
  status(now) {
    if (this.phase === PHASE.FLOORS) return `VAULTS ${fmtTime(this.floorEndsAt - now)}`;
    if (this.phase === PHASE.STAGING) return `BREACH IN ${fmtTime(this.stagingEndsAt - now)}`;
    if (this.phase === PHASE.SHOWDOWN) return `SHOWDOWN ${fmtTime(this.showdownEndsAt - now)}`;
    return this.phase;
  }
}
