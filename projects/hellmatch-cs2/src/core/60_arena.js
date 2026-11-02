// ===================================================================================
// Part 6: Arena - one running Doom level with its own players, things and rules
// ===================================================================================

// player names as the HUD shows them: the HUD font has only A-Z, digits and some punctuation, so other characters
// are dropped; at most HUD_NAME_MAX characters (Steam names can be 32)
const HUD_NAME_MAX = 12;
function hudName(name) {
  const s = String(name || '').toUpperCase().replace(/[^\x20-\x5f]/g, '').replace(/\s+/g, ' ').trim().slice(0, HUD_NAME_MAX).trim();
  return s || 'PLAYER';
}

const OBITS = {
  fist: '%o was punched out by %k.', berserk: '%o was ripped apart by %k\'s fists.',
  chainsaw: '%o was mowed down by %k\'s ripsaw.', pistol: '%o was tickled by %k\'s pistol.',
  shotgun: '%o chewed on %k\'s shotgun.', ssg: '%o was splattered by %k\'s super shotgun.',
  chaingun: '%o was mowed down by %k\'s chaingun.', rocket: '%o rode %k\'s rocket.',
  rocketsplash: '%o almost dodged %k\'s rocket.', plasma: '%o was melted by %k\'s plasma rifle.',
  bfg: '%o was disintegrated by %k\'s SKAG 1337.', telefrag: '%o was telefragged by %k.', barrel: '%o was blown up by %k\'s barrel.',
  selfrocket: '%o should have stood back.', selfbfg: '%o got too close to their own SKAG 1337.', selfbarrel: '%o went boom.',
  slime: '%o melted.', crush: '%o was squished.', world: '%o died.', suicide: '%o suicides.',
};

class Arena {
  constructor(index, cfg) {
    this.index = index;
    this.cfg = cfg;
    this.level = null;
    this.players = new Map();   // slot -> player
    this.events = [];
    this.mobjs = new Set();
    this.removedMobjs = [];
    this.thinkers = [];
    this.activeplats = new Set();
    this.activeceilings = new Set();
    this.itemRespawnQueue = [];
    this.leveltime = 0;
    this.validcount = 1;
    this.dmstarts = [];
    this.teamsActive = false;
    this.friendlyFire = false;
    this.mode = null;            // set by the round manager
    this.teamScore = [0, 0];
    this.finished = false;
    this.result = null;
    this.damageCtx = null;
    this.modeKey = ''; this.mapId = ''; this.mapTitle = '';
    this.target = 0; this.startTime = 0; this.countdown = 0; this.time = 0; this.finishedAt = 0;
    this.bodyque = [];
    this.coopStarts = null;
    this.loadout = null;          // weapon start for this arena (key into LOADOUTS), or null
    this.lives = undefined;       // Boss Battle: lives per player
    this.coop = false;            // co-op (Boss Battle): players can't hurt each other, monsters are the enemy
    this.director = null;         // MonsterDirector when monsters are in play
    this.monsterCount = 0;        // monsters in the level (corpses included until they are cleaned up)
    this.playerMobjs = [];        // what monsters look for
    this.corpseQueue = [];
    this.monsterKills = 0; this.monsterFrags = false;
    this.ringCache = new Map();   // fitSpot: search points around a spot (map geometry only)
  }

  run(fn) { const prev = G; G = this; try { return fn(); } finally { G = prev; } }

  load(data) {
    this.run(() => {
      this.level = new Level(data);
      const n = this.level.bmapwidth * this.level.bmapheight;
      this.blockThings = new Array(n);
      for (let i = 0; i < n; i++) this.blockThings[i] = [];
      for (const t of this.level.things) {
        const [x, y, angle, type, flags] = t;
        if (type === 11) { this.dmstarts.push({ x, y, angle }); continue; }
        if (type >= 1 && type <= 4) { this.coopStarts = this.coopStarts || []; this.coopStarts.push({ x, y, angle }); continue; }
        if (!(flags & 4)) continue; // not on the hard-skill set used for deathmatch
        const mt = DOOMEDNUM[type];
        if (mt === undefined) continue;
        const info = MOBJINFO[mt];
        if (info.kind === 'item' && info.pickup && info.pickup.startsWith('key')) continue;
        if (info.kind === 'monster') continue;   // monsters come from the director, never from the map
        const mo = spawnMobj(x, y, (info.flags & MF_SPAWNCEILING) ? ONCEILINGZ : ONFLOORZ, mt);
        mo.angle = angle; mo.pangle = angle;
        mo.spawnpoint = t;
        if (mo.tics > 0) mo.tics = 1 + (P_Random() % mo.tics);
      }
      if (!this.dmstarts.length && this.coopStarts) this.dmstarts = this.coopStarts.slice();
      // some starts sit exactly against a wall, which our collision counts as stuck: move them clear
      this.dmstarts = this.dmstarts.map((s) => { const f = this.fitSpot(s.x, s.y); return f ? { x: f.x, y: f.y, angle: s.angle } : s; });
    });
  }

  // nearest position (within maxR, same sector) where a player fits: no walls, no solid things or players
  fitSpot(x, y, maxR = 48, avoid, radius = 16, height = 56, info = null) {
    return this.run(() => {
      const sec = this.level.sectorAt(x, y);
      const fits = (px, py) => {
        if (avoid && avoid.some((t) => Math.abs(t.x - px) < 34 && Math.abs(t.y - py) < 34)) return false;
        // info: the monster this spot is for (monster-blocking lines then count as walls)
        const probe = { x: px, y: py, radius, height, flags: MF_SOLID | MF_SHOOTABLE | MF_PICKUP, z: 0, info, player: null };
        return checkPositionProbe(probe, px, py);
      };
      // every point searched is in this sector, and a thing never has more headroom there than the sector's own
      // floor-to-ceiling height: too tall for that = fits nowhere (the search below would only confirm it)
      if (sec.ceilingheight - sec.floorheight < height) return null;
      if (fits(x, y)) return { x, y };
      // rings of points around the spot, nearest first, that are in the same sector and inside the outline: that
      // only depends on the map, so it is worked out once per spot (monster spawn spots are searched every wave)
      const key = x + ',' + y + ',' + maxR;
      let ring = this.ringCache.get(key);
      if (!ring) {
        ring = [];
        for (let r = 4; r <= maxR; r += 4) {
          const steps = Math.max(8, Math.round(r / 3));
          for (let k = 0; k < steps; k++) {
            const nx = x + r * Math.cos(k * 2 * Math.PI / steps), ny = y + r * Math.sin(k * 2 * Math.PI / steps);
            if (this.level.sectorAt(nx, ny) === sec && this.inside(nx, ny)) ring.push(nx, ny);
          }
        }
        this.ringCache.set(key, ring);
      }
      for (let i = 0; i < ring.length; i += 2) {
        const nx = ring[i], ny = ring[i + 1];
        // the thing must fit there, and the point must be walkable in a straight line from the original spot: a point
        // just behind the outer wall is "in the same sector" as far as the map tree is concerned, but it is out in the
        // void (fits first: for a big monster that is what fails, and it saves the line trace)
        if (fits(nx, ny) && walkableLine(x, y, nx, ny)) return { x: nx, y: ny };
      }
      return null;
    });
  }

  // inside the level's outline (with a small margin)
  inside(x, y) {
    const bb = this.level.data && this.level.data.bb;   // [minx, miny, maxx, maxy]
    if (!bb) return true;
    return x >= bb[0] - 8 && y >= bb[1] - 8 && x <= bb[2] + 8 && y <= bb[3] + 8;
  }

  // safety net: anyone who ends up outside the level goes back to a spawn spot; a monster out there just goes away
  // (the director brings in another one)
  rescueOutside() {
    for (const p of this.players.values()) {
      if (!p.mo || p.mo.removed || p.playerstate !== 'live' || p.spectating) continue;
      if (this.inside(p.mo.x, p.mo.y)) continue;
      const s = this.pickSpawnSpot(p);
      this.run(() => { teleportMove(p.mo, s.x, s.y); p.mo.z = p.mo.floorz; p.mo.momx = p.mo.momy = p.mo.momz = 0; p.mo.angle = s.angle; });
      this.events.push({ type: 'teleport', player: p, angle: s.angle });
    }
    if (!this.monsterCount) return;
    this.run(() => {
      for (const m of Array.from(this.mobjs)) {
        if (m.info.kind !== 'monster' || m.health <= 0 || this.inside(m.x, m.y)) continue;
        if (this.director) this.director.onLost(m);
        removeMobj(m);
      }
    });
  }

  // ---------------------------------------------------------------- players
  addPlayer(slot, name, team, color) {
    const p = newPlayer(slot, name);
    p.team = team; p.color = color;
    p.arena = this;
    this.players.set(slot, p);
    return p;
  }

  spawnPlayer(p, spot) {
    this.run(() => {
      if (p.mo && !p.mo.removed) {
        // Doom's body queue: keep the last 32 corpses
        this.bodyque = this.bodyque || [];
        this.bodyque.push(p.mo);
        if (this.bodyque.length > 32) { const old = this.bodyque.shift(); if (!old.removed) removeMobj(old); }
      }
      playerReborn(p);
      if (this.loadout) applyLoadout(p, this.loadout);
      if (!spot) spot = this.pickSpawnSpot(p);
      spawnPlayerAt(p, spot.x, spot.y, spot.angle);
      p.protectUntil = this.leveltime + (this.cfg.spawnProtectTics || 0);
      p.cmd.angle = spot.angle;
      this.events.push({ type: 'spawn', player: p, angle: spot.angle });
      if (!spot.silent) {
        const fog = spawnMobj(spot.x + 20 * Math.cos(spot.angle * DEG), spot.y + 20 * Math.sin(spot.angle * DEG), p.mo.z, MT.TFOG);
        startSound(fog, 'telept');
      }
    });
  }

  spotFree(spot, p) {
    for (const q of this.players.values()) {
      if (q === p || !q.mo || q.mo.removed || q.playerstate !== 'live' || q.spectating) continue;
      if (Math.abs(q.mo.x - spot.x) < 40 && Math.abs(q.mo.y - spot.y) < 40) return false;
    }
    return true;
  }

  pickSpawnSpot(p) {
    const starts = this.dmstarts;
    if (!starts.length) return { x: 0, y: 0, angle: 0 };
    // prefer free spots far from living enemies, with some randomness
    const monsters = this.monsterCount ? Array.from(this.mobjs).filter((m) => m.info.kind === 'monster' && m.health > 0) : [];
    const scored = starts.map((s) => {
      let near = 1e9;
      for (const q of this.players.values()) {
        if (q === p || !q.mo || q.playerstate !== 'live' || q.spectating) continue;
        if ((this.teamsActive && q.team === p.team) || this.coop) continue;
        near = Math.min(near, Math.hypot(q.mo.x - s.x, q.mo.y - s.y));
      }
      for (const m of monsters) near = Math.min(near, Math.hypot(m.x - s.x, m.y - s.y));
      return { s, free: this.spotFree(s, p), near };
    });
    const free = scored.filter((e) => e.free);
    const pool = free.length ? free : scored;
    pool.sort((a, b) => b.near - a.near);
    const top = pool.slice(0, Math.max(1, Math.ceil(pool.length / 2)));
    const s = top[(P_Random() * top.length) >> 8].s;
    // never spawn inside a wall or another player: step to the nearest clear spot
    const f = this.fitSpot(s.x, s.y, 64);
    return f ? { x: f.x, y: f.y, angle: s.angle } : s;
  }

  // distinct spots for a round start; teams get starts on opposite halves when possible
  roundStartSpots(list) {
    const starts = this.dmstarts.slice();
    for (let i = starts.length - 1; i > 0; i--) { const j = (P_Random() * (i + 1)) >> 8; [starts[i], starts[j]] = [starts[j], starts[i]]; }
    const out = new Map();
    if (this.teamsActive && starts.length >= 2) {
      // split starts along the axis of greatest spread
      const xs = starts.map((s) => s.x), ys = starts.map((s) => s.y);
      const useX = (Math.max(...xs) - Math.min(...xs)) >= (Math.max(...ys) - Math.min(...ys));
      const sorted = starts.slice().sort((a, b) => useX ? a.x - b.x : a.y - b.y);
      const half = Math.ceil(sorted.length / 2);
      const sides = [sorted.slice(0, half), sorted.slice(half)];
      const used = [0, 0];
      for (const p of list) {
        const t = p.team === 1 ? 1 : 0;
        const side = sides[t];
        const s = side[used[t]++ % side.length];
        out.set(p, { x: s.x, y: s.y, angle: s.angle, silent: true });
      }
    } else {
      list.forEach((p, i) => {
        const s = starts[i % starts.length];
        out.set(p, { x: s.x, y: s.y, angle: s.angle, silent: true });
      });
    }
    // more players than starts: put the extra ones at the nearest clear spot (checked against walls and the others)
    const taken = [];
    for (const [p, s] of out) {
      let f = this.fitSpot(s.x, s.y, 96, taken);
      // no room around this start (small ledge or platform): use the nearest other start with room
      if (!f) {
        const others = this.dmstarts.slice().sort((a, b) => Math.hypot(a.x - s.x, a.y - s.y) - Math.hypot(b.x - s.x, b.y - s.y));
        for (const o of others) { f = this.fitSpot(o.x, o.y, 96, taken); if (f) { s.angle = o.angle; break; } }
      }
      if (f) { s.x = f.x; s.y = f.y; }
      taken.push(s);
    }
    return out;
  }

  removePlayer(slot) {
    const p = this.players.get(slot);
    if (!p) return;
    this.run(() => {
      if (p.mo && !p.mo.removed) {
        p.mo.player = null;
        removeMobj(p.mo);
      }
    });
    p.mo = null;
    this.players.delete(slot);
  }

  makeSpectator(p) {
    this.run(() => {
      if (p.mo && !p.mo.removed) {
        // leave the corpse where it lies
        p.mo.player = null;
        p.mo.flags &= ~(MF_SOLID | MF_SHOOTABLE);
      }
    });
    p.spectating = true;
  }

  // ---------------------------------------------------------------- per-tic
  tic() {
    this.run(() => {
      this.leveltime++;
      this.removedMobjs.length = 0;
      this.playerMobjs.length = 0;
      for (const p of this.players.values()) {
        if (p.spectating) continue;
        p.pviewz = p.viewz;
        playerThink(p);
        if (p.mo && !p.mo.removed && p.playerstate === 'live') this.playerMobjs.push(p.mo);
      }
      const list = Array.from(this.mobjs);
      for (const mo of list) if (!mo.removed) mobjThinker(mo);
      runThinkers();
      respawnSpecials();
      if (this.director) this.director.tic();
      for (const s of this.level.sectors) { s.renderFloor = s.floorheight; s.renderCeil = s.ceilingheight; }
    });
  }

  // ---------------------------------------------------------------- hooks used by the playsim
  message(p, text) { this.events.push({ type: 'msg', player: p, text }); }
  isProtected(p) { return this.finished || this.leveltime < p.protectUntil; }
  onTeleport(p, angle) { this.events.push({ type: 'teleport', player: p, angle }); }
  onExitLine(p) {
    if (p) this.message(p, 'Exits are disabled in this game.');
    return false;
  }

  // ---------------------------------------------------------------- monsters
  onMonsterSpawned(mo, by) { /* bookkeeping hook; the director counts its own spawns */ }
  onMonsterRaised(mo) { if (this.director) this.director.spawned++; }
  onMonsterKilled(mo, source, inflictor) {
    this.monsterKills++;
    const killer = source && source.player && source !== mo ? source.player : null;
    if (killer) {
      killer.killcount++;
      if (this.monsterFrags) killer.frags += mo.boss ? 5 : 1;   // Boss Battle: the frag box counts monster kills
    }
    if (this.director) this.director.onKilled(mo, source);
    this.events.push({ type: 'monsterKill', mo, killer, boss: !!mo.boss, name: mo.info.name, time: this.leveltime });
  }

  onPlayerKilled(victim, killer, inflictor, source) {
    let kind = 'world';
    const ctx = this.damageCtx;
    // killed by a monster: no frag lost (Doom's rule), the message names the creature
    const monster = source && source.info && source.info.kind === 'monster' ? source : null;
    if (monster) {
      victim.deaths++;
      if (victim.lives !== undefined) victim.lives--;
      const text = (MONSTER_OBITS[monster.info.key] || '%o was killed by a %m.').replace('%o', hudName(victim.name)).replace('%m', monster.info.name);
      this.events.push({ type: 'kill', victim, killer: null, kind: 'monster', text, time: this.leveltime, monster });
      return;
    }
    const self = !killer || killer === victim;
    if (ctx === 'telefrag') kind = 'telefrag';
    else if (ctx === 'crush') kind = 'crush';
    else if (ctx === 'slime') kind = 'slime';
    else if (inflictor && inflictor.type === MT.BARREL) kind = self ? 'selfbarrel' : 'barrel';
    else if (inflictor && inflictor.type === MT.ROCKET) kind = self ? 'selfrocket' : (ctx === 'direct' ? 'rocket' : 'rocketsplash');
    else if (inflictor && inflictor.type === MT.PLASMA) kind = 'plasma';
    else if (inflictor && (inflictor.type === MT.BFG || ctx === 'bfgspray')) kind = self ? 'selfbfg' : 'bfg';
    else if (killer && !self) {
      const w = killer.readyweapon;
      kind = ['fist', 'pistol', 'shotgun', 'chaingun', 'rocket', 'plasma', 'bfg', 'chainsaw', 'ssg'][w] || 'world';
      if (w === WP_FIST && killer.powers[PW_STRENGTH]) kind = 'berserk';
    } else if (self && source === victim.mo) kind = 'suicide';
    if (this.coop && !self) { kind = 'world'; }                     // co-op: no frags between players
    else if (self) victim.frags--; else killer.frags++;
    victim.deaths++;
    if (victim.lives !== undefined) victim.lives--;
    if (this.teamsActive) {
      if (self) { if (victim.team >= 0 && this.cfg.teamSuicidePenalty) this.teamScore[victim.team] = Math.max(0, this.teamScore[victim.team] - 1); }
      else if (killer.team !== victim.team && killer.team >= 0) this.teamScore[killer.team]++;
    }
    const text = (OBITS[kind] || OBITS.world).replace('%o', hudName(victim.name)).replace('%k', killer ? hudName(killer.name) : '');
    this.events.push({ type: 'kill', victim, killer: self || this.coop ? null : killer, kind, text, time: this.leveltime });
  }
}

function walkableLine(x1, y1, x2, y2) {
  return pathTraverse(x1, y1, x2, y2, PT_ADDLINES, (ic) => {
    const li = ic.line;
    if (!li.backsector || !(li.flags & ML_TWOSIDED) || (li.flags & ML_BLOCKING)) return false;
    const op = lineOpening(li);
    if (op.top - op.bottom < 56) return false;
    return Math.abs(li.frontsector.floorheight - li.backsector.floorheight) <= MAXSTEP;
  });
}

// a thing fits at (x, y) when nothing blocks it, it fits under the ceiling, and no step taller than MAXSTEP is within
// its radius (a spot right against a tall ledge passes the first two checks, but a thing placed there would be inside
// the ledge: it can't move at all, and a monster would stand at ledge height in the low room)
function checkPositionProbe(probe, x, y) {
  probe.sector = G.level.sectorAt(x, y);
  return checkPosition(probe, x, y) && TM.ceilingz - TM.floorz >= probe.height && TM.floorz - probe.sector.floorheight <= MAXSTEP;
}

// sound and message plumbing
function startSound(origin, sfx) {
  if (!G) return;
  if (!origin) { G.events.push({ type: 'sound', sfx, x: 0, y: 0, z: 0, mo: null, global: true }); return; }
  const isMo = origin.info !== undefined;
  G.events.push({ type: 'sound', sfx, x: origin.x, y: origin.y, z: isMo ? origin.z + origin.height / 2 : origin.z, mo: isMo ? origin : null });
}

function startLocalSound(player, sfx) {
  if (!G) return;
  G.events.push({ type: 'localsound', sfx, player });
}
