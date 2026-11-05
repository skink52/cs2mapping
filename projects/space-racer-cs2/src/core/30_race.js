// ===================================================================================
// Part 3: an arena = one race on one track: grid, countdown, the field, slipstreams, bumps, the Pulse, wrecks,
// finishing order and the end of the race. Pushes events for the CS2 side (sounds, HUD, kills).
// ===================================================================================

const ARENA_DEFAULTS = {
  countdownTics: 10 * TICRATE,     // on the grid before the lights
  finishWindow: 30,                // seconds the rest get after the winner
  raceCap: 300,                    // seconds: a race never runs longer than this
  endHold: 6,                      // seconds the results stay up before the arena is over
  laps: 0,                         // 0 = the track's own setting
};

class Arena {
  constructor(index, track, cfg) {
    this.index = index; this.track = track; this.cfg = Object.assign({}, ARENA_DEFAULTS, cfg || {});
    this.laps = this.cfg.laps || track.laps;
    this.cars = new Map();          // slot -> Car
    this.order = [];                // cars in grid order
    this.events = [];
    this.tic = 0; this.time = 0;    // tics / seconds since the arena was built
    this.state = 'grid';            // grid | racing | over
    this.countdown = this.cfg.countdownTics;
    this.raceTic = 0;               // tics since the lights went green
    this.finishCount = 0; this.firstFinishTic = 0;
    this.pulse = { active: false, total: 0, prev: 0, lapsSeen: 0 };
    this.ranking = [];              // cars sorted by position (updated every few tics)
    this.result = null;
    this.finishedAt = 0;
    this.lastBeep = -1;
    this.bolts = []; this.boltIds = 0;                // Seeker Bolts in flight: { owner, s, d, z, x, y, yaw, speed, left, target }
    this.fires = [];                // Nova Burn fire on the road: { x, y, z, until, owner }
    // Neon Racer: walls of light on the road - Light Trail segments, Firewalls, and the short trail every boosting car
    // leaves: { id, x0, y0, x1, y1, z, until, owner, team, hard, kind: trail | firewall | boost }
    this.walls = []; this.wallIds = 0;
    // Depth Racer: Depth Charges { id, x, y, z, yaw, at, until, owner, team, armed } and ink clouds { id, x, y, z, until, owner, team }
    this.mines = []; this.mineIds = 0; this.clouds = []; this.cloudIds = 0;
    this.creatures = makeCreatures(track);   // sea creatures crossing the track (35_creatures.js)
    this.pairs = null;              // flat copies of positions for the pair loops in step()
    this.lanes = null;              // the bots' lane picture for this tic (laneCars)
    this.hudCache = null; this.newRecord = false;   // used by the CS2 side
    this.ballot = null;             // the track vote of this race's top places (RoundManager.closeRace)
  }

  addCar(slot, name, clsKey, team) {
    const car = new Car(slot, name, clsKey, team);
    this.cars.set(slot, car);
    this.order.push(car);
    return car;
  }

  // put every car on the grid (call once all cars are added); order = grid order
  placeGrid() {
    this.order.forEach((car, k) => {
      const g = this.track.gridSlot(k);
      car.placeAt(g.x, g.y, g.z, g.yaw, this.track);
      car.state = 'grid'; car.lapsDone = 0; car.nextCp = 1; car.total = -1000 + k;   // grid order until the start
      car.gridPos = k;
    });
    this.ranking = this.order.slice();
  }

  // the car picker on the grid: swap a car's class (keeps its grid slot)
  setClass(car, clsKey) {
    if (!CARS[clsKey] || car.state !== 'grid') return false;
    car.cls = clsKey; car.spec = CARS[clsKey]; car.shield = car.spec.shield; car.charge = RULES.startCharge;
    return true;
  }

  removeCar(slot, why) {
    const car = this.cars.get(slot);
    if (!car) return;
    if (car.racing || car.state === 'grid') { car.state = 'withdrawn'; car.wreckTotal = car.total; car.wreckTime = this.raceTic; car.stateTime = 0; }
    car.left = why === 'left';
    this.events.push({ type: 'withdraw', car, why });
  }

  // ---------------------------------------------------------------- the E abilities' effects on other cars
  abilities(cars, dt) {
    for (const c of cars) c.towed = 0;
    for (const c of cars) {
      if (c.fired) {
        const kind = c.fired;
        c.fired = null;
        let hits = 0;
        if (kind === 'emp') {
          // EMP: every enemy close by loses charge, its boost stops and it is fried for a moment
          for (const o of cars) {
            if (o === c || !o.solid || o.noDamage > 0 || o.aegis > 0 || Math.abs(o.z - c.z) > 120 || (o.team >= 0 && o.team === c.team)) continue;
            if (Math.hypot(o.x - c.x, o.y - c.y) > RULES.empRadius) continue;
            o.charge = Math.max(0, o.charge - RULES.empCharge);
            o.padTimer = 0; o.novaTimer = 0; o.overclock = 0; o.jet = 0; o.boosting = false; o.emp = RULES.empTime;
            o.damage(RULES.empDamage, c, this.raceTic); o.fx |= 1; hits++;
          }
        } else if (kind === 'firewall') {
          // FIREWALL: a wall across the road just behind the car, centred on its lane
          const T = this.track, i = c.seg, hw = T.hw[i], half = hw * RULES.firewallWidth;
          const d = clamp(c.d, -(hw - half), hw - half);
          const bx = c.x - Math.cos(c.yaw) * 110, by = c.y - Math.sin(c.yaw) * 110;
          const cx = bx + T.nx[i] * (d - c.d), cy = by + T.ny[i] * (d - c.d);
          this.addWall(c, cx - T.nx[i] * half, cy - T.ny[i] * half, cx + T.nx[i] * half, cy + T.ny[i] * half, c.z, RULES.firewallTime, true, 'firewall');
        } else if (kind === 'mine') {
          // DEPTH CHARGE: dropped just behind the car; a car can have minesMax out at once (the oldest goes)
          let mine = 0;
          for (let k = this.mines.length - 1; k >= 0; k--) if (this.mines[k].owner === c && ++mine >= RULES.minesMax) this.mines.splice(k, 1);
          const m = { id: ++this.mineIds, x: c.x - Math.cos(c.yaw) * 95, y: c.y - Math.sin(c.yaw) * 95, z: c.z, yaw: c.yaw, at: this.time, until: this.time + RULES.mineLife, owner: c, team: c.team, armed: false };
          this.mines.push(m);
          this.events.push({ type: 'mineDrop', mine: m });
        } else if (kind === 'quake') {
          // SHOCKWAVE: every car close by is shoved sideways away from the Meteor, harder the closer it is
          for (const o of cars) {
            if (o === c || !o.solid || o.noDamage > 0 || Math.abs(o.z - c.z) > 120) continue;
            const dx = o.x - c.x, dy = o.y - c.y, dist = Math.hypot(dx, dy);
            if (dist > RULES.quakeRadius) continue;
            const k = 1 - 0.5 * dist / RULES.quakeRadius;
            if (shove(c, o, dx / (dist || 1), dy / (dist || 1), RULES.quakeKnock * k, RULES.quakeStagger)) {
              o.damage(RULES.quakeDamage * k, c, this.raceTic); o.fx |= 1; hits++;
            }
          }
        } else if (kind === 'bolt') {
          this.launchBolt(c);
        } else if (kind === 'aegis') {
          // AEGIS: teammates close by get a share of the shell as shield
          for (const o of cars) {
            if (o === c || o.state !== 'racing' || o.team < 0 || o.team !== c.team) continue;
            if (Math.hypot(o.x - c.x, o.y - c.y) > RULES.aegisRange) continue;
            o.shield = Math.min(o.spec.shield, o.shield + RULES.aegisShare); o.fx |= 4; hits++;
          }
        }
        this.events.push({ type: 'ability', car: c, kind, hits });
      }
      // LIGHT TRAIL: a hard wall of light, segment by segment, behind the car while it lasts
      if (c.trailT > 0) {
        c.trailT -= dt; c.trailGap -= dt;
        if (c.state !== 'racing' || c.air) c.trailT = 0;
        else if (c.trailGap <= 0) {
          c.trailGap = RULES.trailGap;
          const tx = c.x - Math.cos(c.yaw) * CAR_LEN * 0.5, ty = c.y - Math.sin(c.yaw) * CAR_LEN * 0.5;
          if (Math.hypot(tx - c.trailX, ty - c.trailY) > 30) this.addWall(c, c.trailX, c.trailY, tx, ty, c.z, RULES.wallTime, true, 'trail');
          c.trailX = tx; c.trailY = ty;
        }
      }
      // the boost trail (Neon): a short, soft trail behind every car boosting on Mouse 1
      if (RULES.boostTrail > 0) {
        if (c.boosting && c.state === 'racing' && !c.air) {
          const tx = c.x - Math.cos(c.yaw) * CAR_LEN * 0.5, ty = c.y - Math.sin(c.yaw) * CAR_LEN * 0.5;
          if (!c.btOn) { c.btOn = true; c.btX = tx; c.btY = ty; c.btGap = 0.1; }
          else if ((c.btGap -= dt) <= 0) {
            c.btGap = 0.1;
            if (Math.hypot(tx - c.btX, ty - c.btY) > 30) this.addWall(c, c.btX, c.btY, tx, ty, c.z, RULES.boostTrail, false, 'boost');
            c.btX = tx; c.btY = ty;
          }
        } else c.btOn = false;
      }
      // INK CLOUD: clouds dropped behind the car while it lasts
      if (c.inkT > 0) {
        c.inkT -= dt; c.inkGap -= dt;
        if (c.state !== 'racing' || c.air) c.inkT = 0;
        else if (c.inkGap <= 0) {
          c.inkGap = RULES.inkGap;
          const cl = { id: ++this.cloudIds, x: c.x - Math.cos(c.yaw) * 120, y: c.y - Math.sin(c.yaw) * 120, z: c.z, until: this.time + RULES.inkTime, owner: c, team: c.team };
          this.clouds.push(cl);
          this.events.push({ type: 'ink', cloud: cl });
        }
      }
      // UNDERTOW: the current behind the car pulls teammates along and drags enemies back
      if (c.undertow > 0 && c.state === 'racing') {
        const fx = Math.cos(c.yaw), fy = Math.sin(c.yaw);
        for (const o of cars) {
          if (o === c || !o.solid || Math.abs(o.z - c.z) > 80) continue;
          const rx = o.x - c.x, ry = o.y - c.y;
          const along = rx * fx + ry * fy;
          if (along > -40 || along < -RULES.undertowRange || Math.abs(-rx * fy + ry * fx) > RULES.undertowSide) continue;
          if (o.team >= 0 && o.team === c.team) { o.towed = 1; o.charge = Math.min(o.spec.charge, o.charge + RULES.undertowCharge * dt); }
          else if (o.jet <= 0 && o.aegis <= 0) o.towed = -1;
        }
      }
      // NOVA BURN leaves fire on the road behind it
      if (c.novaTimer > 0 && c.novaLeft - c.novaTimer < RULES.fireFor && c.state === 'racing' && !c.air) {
        c.fireT -= dt;
        if (c.fireT <= 0) {
          c.fireT = RULES.fireGap;
          const f = { x: c.x - Math.cos(c.yaw) * 70, y: c.y - Math.sin(c.yaw) * 70, z: c.z, yaw: c.yaw, until: this.time + RULES.fireTime, owner: c };
          this.fires.push(f);
          this.events.push({ type: 'fire', fire: f });
        }
      }
    }
    if (this.bolts.length) this.moveBolts(cars, dt);
    if (this.walls.length) this.wallHits(cars);
    if (this.mines.length) this.mineStep(cars);
    if (this.clouds.length) this.cloudHits(cars);
    if (!this.fires.length) return;
    // fire burns anyone else driving through it: a little shield, less grip, credited to the Comet
    const R2 = RULES.fireRadius * RULES.fireRadius;
    this.fires = this.fires.filter((f) => f.until > this.time);
    for (const o of cars) {
      if (!o.solid || o.overHazards) continue;
      for (const f of this.fires) {
        if (f.owner === o || Math.abs(o.z - f.z) > 80) continue;
        const dx = o.x - f.x, dy = o.y - f.y;
        if (dx * dx + dy * dy > R2) continue;
        o.scorch = 0.25;
        if (o.burnCd <= this.time && o.noDamage <= 0) { o.damage(RULES.fireDamage, f.owner, this.raceTic); o.burnCd = this.time + RULES.fireEvery; o.fx |= 1; }
        break;
      }
    }
  }

  // ---------------------------------------------------------------- walls of light (Neon Racer)
  addWall(owner, x0, y0, x1, y1, z, life, hard, kind) {
    const w = { id: ++this.wallIds, x0, y0, x1, y1, z, until: this.time + life, owner, team: owner.team, hard, kind, hit: null, dead: false };   // hit: the slots it has caught
    this.walls.push(w);
    return w;
  }
  // a car that crosses a wall this tick: a hard wall (Light Trail) bounces it back like a rail (a graze deflects, a
  // square hit hurts); a Firewall slows and hurts the car passing through; a boost trail makes it skid, and only when
  // it cuts across at an angle. Each wall catches a car once. The owner and its teammates pass.
  wallHits(cars) {
    const now = this.time, PX = this.pairs.x, PY = this.pairs.y;
    this.walls = this.walls.filter((w) => w.until > now);
    if (!this.walls.length) return;
    for (let i = 0; i < cars.length; i++) {
      const o = cars[i];
      if (!o.solid || o.overHazards || o.hazardCd > 0) continue;
      const px = PX[i], py = PY[i], qx = o.x, qy = o.y;
      for (const w of this.walls) {
        if (w.dead || w.owner === o || (w.team >= 0 && w.team === o.team) || Math.abs(w.z - o.z) > 80) continue;
        if (Math.min(px, qx) > Math.max(w.x0, w.x1) + CAR_R || Math.max(px, qx) < Math.min(w.x0, w.x1) - CAR_R ||
            Math.min(py, qy) > Math.max(w.y0, w.y1) + CAR_R || Math.max(py, qy) < Math.min(w.y0, w.y1) - CAR_R) continue;
        const wx = w.x1 - w.x0, wy = w.y1 - w.y0, wl = Math.hypot(wx, wy) || 1, ux = wx / wl, uy = wy / wl;
        // which side of the wall the car was on, and is on now (signed distance to the wall's line)
        const sp = (px - w.x0) * -uy + (py - w.y0) * ux, sq = (qx - w.x0) * -uy + (qy - w.y0) * ux;
        const crossed = (sp > 0) !== (sq > 0) || Math.abs(sq) < CAR_R * 0.5;
        if (!crossed) continue;
        const along = (qx - w.x0) * ux + (qy - w.y0) * uy;        // within the segment's length?
        if (along < -CAR_R * 0.5 || along > wl + CAR_R * 0.5) continue;
        if (w.hit && w.hit.indexOf(o.slot) >= 0) continue;              // this wall has had its go at this car
        const side = sp >= 0 ? 1 : -1, nx = -uy * side, ny = ux * side;   // the wall's normal towards where the car came from
        const vn = -(o.vx * nx + o.vy * ny);                               // speed into the wall
        let graze = false;
        if (w.kind === 'firewall') {
          // through it, slowed and hurt
          o.vx *= 1 - RULES.firewallSlow; o.vy *= 1 - RULES.firewallSlow;
          o.stagger = Math.max(o.stagger, RULES.firewallStagger);
          if (o.noDamage <= 0) { o.damage(RULES.firewallDamage, w.owner, this.raceTic); o.fx |= 1; }
        } else if (w.hard) {
          // back onto the side it came from and bounce, like a rail hit: a graze costs nothing, a square hit speed,
          // shield and a skid
          o.x = w.x0 + ux * clamp(along, 0, wl) + nx * CAR_R * 0.55; o.y = w.y0 + uy * clamp(along, 0, wl) + ny * CAR_R * 0.55;
          if (vn > 0) { o.vx += (1 + RULES.wallRest) * vn * nx; o.vy += (1 + RULES.wallRest) * vn * ny; }
          const hard = Math.max(0, vn - RULES.railSoft);
          if (hard > 0) {
            const k = 1 - Math.min(0.45, vn / 1400);
            o.vx *= k; o.vy *= k;
            o.stagger = Math.max(o.stagger, RULES.wallStagger); o.fx |= 2;
            if (o.noDamage <= 0) { o.damage(Math.min(RULES.contactMax, RULES.wallDamage + hard * RULES.railDamage), w.owner, this.raceTic); o.fx |= 1; }
          } else { graze = true; o.fx |= 64; }
        } else {
          // a soft trail: only a cut across it at an angle counts
          const sp2 = o.speed || 1;
          if (Math.abs((o.vx * -uy + o.vy * ux) / sp2) < RULES.boostTrailAngle) continue;
          o.stagger = Math.max(o.stagger, RULES.boostTrailStagger);
          if (o.noDamage <= 0) { o.damage(RULES.boostTrailDamage, w.owner, this.raceTic); o.fx |= 1; }
        }
        (w.hit || (w.hit = [])).push(o.slot);
        // burnt out: it catches nobody else and fades within a few ticks (not at once: a prop placed and hidden on
        // consecutive ticks is one CS2 stops drawing)
        if (w.kind === 'firewall' && w.hit.length >= RULES.firewallHits) { w.dead = true; w.until = Math.min(w.until, this.time + 0.15); }
        o.hazardCd = graze ? 0.15 : RULES.hazardCd;
        if (!graze) this.events.push({ type: 'hazard', kind: w.kind, car: o, owner: w.owner, wall: w });
        break;
      }
    }
  }

  // ---------------------------------------------------------------- Depth Charges and ink (Depth Racer)
  mineStep(cars) {
    const now = this.time;
    for (let k = this.mines.length - 1; k >= 0; k--) {
      const m = this.mines[k];
      if (m.until <= now || m.owner.state === 'withdrawn') { this.mines.splice(k, 1); this.events.push({ type: 'mineEnd', mine: m }); continue; }
      if (!m.armed) { if (now >= m.at + RULES.mineArm) m.armed = true; else continue; }
      let trip = false;
      for (const o of cars) {
        if (o === m.owner || !o.solid || o.overHazards || (o.team >= 0 && o.team === m.team) || Math.abs(o.z - m.z) > 80) continue;
        if (Math.hypot(o.x - m.x, o.y - m.y) < RULES.mineTrigger) { trip = true; break; }
      }
      if (!trip) continue;
      // the blast: everyone not on the Meteor's side within reach is shoved away, thrown up a little and hurt
      let hits = 0;
      for (const o of cars) {
        if (o === m.owner || !o.solid || o.noDamage > 0 || o.aegis > 0 || (o.team >= 0 && o.team === m.team) || Math.abs(o.z - m.z) > 120) continue;
        const dx = o.x - m.x, dy = o.y - m.y, dist = Math.hypot(dx, dy);
        if (dist > RULES.mineRadius) continue;
        const kk = 1 - 0.5 * dist / RULES.mineRadius;
        o.knockCd = 0;
        shove(m.owner, o, dx / (dist || 1), dy / (dist || 1), RULES.mineKnock * kk, RULES.mineStagger);
        if (!o.air && !o.fly && o.jet <= 0) { o.air = true; o.airTime = 0; o.vz = Math.max(o.vz, RULES.mineLift * kk); o.z += 1; }
        o.damage(RULES.mineDamage * kk, m.owner, this.raceTic); o.fx |= 1; hits++;
      }
      this.mines.splice(k, 1);
      this.events.push({ type: 'mineBoom', mine: m, hits });
    }
  }
  cloudHits(cars) {
    const now = this.time, R2 = RULES.inkRadius * RULES.inkRadius;
    this.clouds = this.clouds.filter((cl) => cl.until > now);
    if (!this.clouds.length) return;
    for (const o of cars) {
      if (!o.solid || o.overHazards) continue;
      for (const cl of this.clouds) {
        if (cl.owner === o || (cl.team >= 0 && cl.team === o.team) || Math.abs(o.z - cl.z) > 80) continue;
        const dx = o.x - cl.x, dy = o.y - cl.y;
        if (dx * dx + dy * dy > R2) continue;
        if (o.inked <= 0) this.events.push({ type: 'hazard', kind: 'ink', car: o, owner: cl.owner });
        o.inked = 0.3;
        if (o.burnCd <= now && o.noDamage <= 0) { o.damage(RULES.inkDamage, cl.owner, this.raceTic); o.burnCd = now + RULES.inkEvery; o.fx |= 1; }
        break;
      }
    }
  }

  // SEEKER BOLT: launched from the Hornet's nose along the road; it locks on to the first car ahead (by road distance)
  launchBolt(c) {
    const T = this.track, L = T.len;
    let target = null, best = RULES.boltRange;
    for (const o of this.order) {
      if (o === c || !o.solid || Math.abs(o.z - c.z) > 150) continue;
      const ahead = (((o.s - c.s) % L) + L) % L;
      if (ahead > 20 && ahead < best) { best = ahead; target = o; }
    }
    const b = { owner: c, s: c.s + CAR_LEN * 0.6, d: c.d, z: c.z, x: c.x, y: c.y, yaw: c.yaw, speed: Math.max(0, c.speed) + RULES.boltSpeed, left: RULES.boltRange, target, id: ++this.boltIds, h: c.fly ? c.z - this.track.zAtS(c.s) : 0 };
    this.placeBolt(b);
    this.bolts.push(b);
    this.events.push({ type: 'bolt', bolt: b });
  }
  placeBolt(b) {
    const T = this.track, p = T.point(b.s);
    b.d = clamp(b.d, -p.hw, p.hw);
    b.x = p.x + p.nx * b.d; b.y = p.y + p.ny * b.d;
    b.z = p.z - b.d * T.bankAt(p.i, 0) + RULES.boltLift + (b.h || 0);
    b.yaw = Math.atan2(p.ty, p.tx);
  }
  moveBolts(cars, dt) {
    const L = this.track.len, R = RULES.boltRadius + CAR_R;
    for (let k = this.bolts.length - 1; k >= 0; k--) {
      const b = this.bolts[k], c = b.owner;
      const step = b.speed * dt;
      b.s += step; b.left -= step;
      const t = b.target;
      if (t && t.solid) {
        const ahead = (((t.s - b.s) % L) + L) % L;
        if (ahead < L / 2) {
          b.d += clamp(t.d - b.d, -RULES.boltTurn * dt, RULES.boltTurn * dt);
          const th = t.fly ? t.z - this.track.zAtS(t.s) : 0;           // in a flight section it climbs / dives after the target
          b.h += clamp(th - b.h, -RULES.boltTurn * dt, RULES.boltTurn * dt);
        }
      }
      this.placeBolt(b);
      let hit = null;
      for (const o of cars) {
        if (o === c || !o.solid || o.noDamage > 0) continue;
        const dx = o.x - b.x, dy = o.y - b.y, dz = o.z + RULES.boltLift - b.z;
        if (dx * dx + dy * dy + dz * dz < R * R) { hit = o; break; }
      }
      if (hit) {
        const blocked = hit.aegis > 0;
        if (!blocked) {
          const dx = hit.x - b.x, dy = hit.y - b.y, dist = Math.hypot(dx, dy) || 1;
          hit.knockCd = 0;
          shove(c, hit, dx / dist, dy / dist, RULES.boltKnock, RULES.boltStagger);
          hit.vx *= 1 - RULES.boltSlow; hit.vy *= 1 - RULES.boltSlow;
          hit.damage(RULES.boltDamage, c, this.raceTic); hit.fx |= 1; hit.hitCd = 0.25;
        }
        this.events.push({ type: 'boltHit', bolt: b, car: hit, blocked });
        this.bolts.splice(k, 1);
      } else if (b.left <= 0 || c.state === 'withdrawn') {
        this.events.push({ type: 'boltEnd', bolt: b });
        this.bolts.splice(k, 1);
      }
    }
  }

  // ---------------------------------------------------------------- per tic
  step() {
    this.tic++; this.time = this.tic / TICRATE;
    if (this.creatures.length) {
      placeCreatures(this, this.time);
      for (const cr of this.creatures) if (cr.active && cr.cycle !== cr.warned) { cr.warned = cr.cycle; this.events.push({ type: 'creaturePass', cr }); }
    }
    if (this.state === 'grid') {
      this.countdown--;
      const secs = Math.ceil(this.countdown / TICRATE);
      if (secs <= 3 && secs !== this.lastBeep && this.countdown > 0) { this.lastBeep = secs; this.events.push({ type: 'beep', n: secs }); }
      // turbo start: remember when each driver last pressed the gas during the final beeps
      if (secs <= 3) for (const car of this.order) {
        if (car.state !== 'grid' || car.isBot) continue;
        if (car.cmd.throttle > 0) { if (car.gasAt === null) car.gasAt = this.countdown; } else car.gasAt = null;
      }
      if (this.countdown <= 0) {
        this.state = 'racing'; this.raceTic = 0;
        for (const car of this.order) if (car.state === 'grid') {
          car.state = 'racing'; car.stateTime = 0; car.lapStart = 0; car.noDamage = RULES.startProtect; car.lock = RULES.attackLock;
          // gas pressed in the last moment before the lights: a turbo start; held down since long before: a stall
          const g = car.isBot ? (rnd() < car.bot.skill * RULES.botLaunch ? 1 : null) : car.gasAt;
          if (g !== null && g <= RULES.launchWindow * TICRATE) {
            const fx = Math.cos(car.yaw), fy = Math.sin(car.yaw);
            car.vx += fx * RULES.launchKick; car.vy += fy * RULES.launchKick; car.padTimer = RULES.launchTime; car.fx |= 8;
            this.events.push({ type: 'launch', car });
          } else if (g !== null && g > RULES.stallAfter * TICRATE) {
            car.stall = RULES.stallTime;
            this.events.push({ type: 'stall', car });
          }
          car.gasAt = null;
        }
        this.events.push({ type: 'go' });
      }
      return;
    }
    if (this.state !== 'racing') { this.finishedAt++; return; }
    this.raceTic++;
    if (this.raceTic === Math.round(RULES.attackLock * TICRATE)) this.events.push({ type: 'armed' });   // spins and E unlock
    const dt = DT;
    const cars = this.order, n = cars.length;
    // the pair loops below (every car against every other, 64 times a second) read positions from flat arrays that
    // mirror the cars: the same numbers, much faster to scan than the car objects
    let A = this.pairs;
    if (!A || A.n !== n) A = this.pairs = { n, x: new Float64Array(n), y: new Float64Array(n), z: new Float64Array(n), v: new Float64Array(n), solid: new Uint8Array(n), spin: new Uint8Array(n) };
    const X = A.x, Y = A.y, Z = A.z, V = A.v, SOL = A.solid, SPIN = A.spin;
    for (let i = 0; i < n; i++) {
      const c = cars[i];
      c.draft = null;
      X[i] = c.x; Y[i] = c.y; Z[i] = c.z; V[i] = c.speed; SOL[i] = c.state === 'racing' && c.ghost <= 0 ? 1 : 0;
    }
    // slipstreams: who is directly behind whom
    for (let i = 0; i < n; i++) {
      if (!SOL[i] || V[i] < 300) continue;
      const c = cars[i];
      const fx = Math.cos(c.yaw), fy = Math.sin(c.yaw), cx = X[i], cy = Y[i], cz = Z[i];
      let best = -1, bestAlong = 1e9;
      for (let j = 0; j < n; j++) {
        if (j === i || !SOL[j] || V[j] < 350) continue;
        const rx = X[j] - cx, ry = Y[j] - cy;
        const along = rx * fx + ry * fy;
        if (along < 60 || along > 360) continue;
        const side = Math.abs(-rx * fy + ry * fx);
        if (side > 70 || Math.abs(Z[j] - cz) > 60) continue;
        if (along < bestAlong) { best = j; bestAlong = along; }
      }
      c.draft = best >= 0 ? cars[best] : null;
    }
    // drive
    for (const c of cars) c.step(this.track, dt, this.raceTic);
    this.abilities(cars, dt);
    if (this.creatures.length) {
      creatureHits(this, cars);
      // the drivers coming up to a crossing are warned (a few times a second; once per creature pass)
      if ((this.tic & 7) === 0) for (const c of cars) {
        if (c.isBot || c.state !== 'racing') continue;
        const a = creatureAhead(this, c, RULES.creatureWarn);
        const key = a ? a.cr.id * 100000 + a.cr.cycle : -1;
        if (a && key !== c.creatureWarned) this.events.push({ type: 'creatureWarn', car: c, cr: a.cr });
        c.creatureWarned = key;
      }
    }
    // bumps
    for (let i = 0; i < n; i++) {
      const c = cars[i];
      X[i] = c.x; Y[i] = c.y; SOL[i] = c.state === 'racing' && c.ghost <= 0 ? 1 : 0; SPIN[i] = c.spinTimer > 0 ? 1 : 0;
    }
    const R2 = CAR_R * 2;
    for (let i = 0; i < n; i++) {
      if (!SOL[i]) continue;
      const a = cars[i];
      for (let j = i + 1; j < n; j++) {
        if (!SOL[j]) continue;
        const near = R2 + (SPIN[i] || SPIN[j] ? RULES.spinReach : 0);
        if (Math.abs(X[i] - X[j]) > near || Math.abs(Y[i] - Y[j]) > near) continue;
        const b = cars[j];
        const hit = collideCars(a, b, this.raceTic);
        X[i] = a.x; Y[i] = a.y; X[j] = b.x; Y[j] = b.y;      // a bump pushes the two apart
        if (hit) this.events.push({ type: 'spinHit', attacker: hit[0], car: hit[1] });
      }
    }
    // wrecks, finishes, departures
    for (const c of cars) {
      if (c.state === 'racing' || c.state === 'falling') {
        if (c.shield <= 0) {
          c.state = 'wrecked'; c.stateTime = 0; c.wreckTotal = c.total; c.wreckTime = this.raceTic; c.shield = 0;
          const attacker = c.lastHit && this.raceTic - c.lastHit.tic <= RULES.koCreditWindow * TICRATE ? this.cars.get(c.lastHit.slot) : null;
          this.events.push({ type: 'wreck', car: c, attacker: attacker && attacker !== c ? attacker : null });
        } else if (c.state === 'racing' && c.lapsDone >= this.laps) {
          c.state = 'finished'; c.stateTime = 0; c.finishPos = ++this.finishCount; c.finishTime = this.raceTic / TICRATE; c.ghost = 99;
          c.total = 1e9 - c.finishPos;
          if (this.finishCount === 1) this.firstFinishTic = this.raceTic;
          this.events.push({ type: 'finish', car: c, pos: c.finishPos });
        } else if (c.fx & 256) this.events.push({ type: 'lap', car: c, lap: c.lapsDone, last: c.lastLap });
      } else if (c.state === 'finished' && c.stateTime > 1.0) { c.state = 'gone'; this.events.push({ type: 'gone', car: c }); }
    }
    // the Pulse: once per lap of the leader, a ring sweeps from the back and tops up everyone it passes
    if (RULES.pulseEnabled) this.pulseStep(dt);
    if ((this.raceTic & 7) === 0) this.rank();
    // end of the race
    let active = false;
    for (const c of cars) if (c.state === 'racing' || c.state === 'falling') { active = true; break; }
    const cap = this.raceTic >= this.cfg.raceCap * TICRATE;
    const window = this.firstFinishTic && this.raceTic - this.firstFinishTic >= this.cfg.finishWindow * TICRATE;
    if (!active || cap || window) this.end(cap ? 'time' : window ? 'window' : 'all');
  }

  pulseStep(dt) {
    const p = this.pulse;
    let leader = -Infinity, back = Infinity, any = false;
    for (const c of this.order) if (c.state === 'racing') { any = true; if (c.total > leader) leader = c.total; if (c.total < back) back = c.total; }
    if (!any) { p.active = false; return; }
    const leaderLaps = Math.floor(leader / this.track.len);
    if (!p.active && leaderLaps > p.lapsSeen && leaderLaps < this.laps) {
      p.lapsSeen = leaderLaps; p.active = true; p.total = back - 400; p.prev = p.total;
      this.events.push({ type: 'pulse', start: true });
    }
    if (!p.active) return;
    p.prev = p.total; p.total += RULES.pulseSpeed * dt;
    for (const c of this.order) {
      if (c.state !== 'racing') continue;
      if (c.total > p.prev && c.total <= p.total) { c.charge = Math.min(c.spec.charge, c.charge + RULES.pulseCharge); c.fx |= 4; c.pulsed = 0.6; this.events.push({ type: 'pulsed', car: c }); }
    }
    if (p.total > leader + 300) { p.active = false; this.events.push({ type: 'pulse', start: false }); }
  }

  // position order: finished by finish order, then racing by progress, then wrecked/withdrawn by progress at the time
  rank() {
    const key = (c) => {
      if (c.state === 'finished' || c.state === 'gone') return 3e9 - c.finishPos;
      if (c.racing) return 1e9 + c.total;
      if (c.left) return -2e9 + c.wreckTotal;
      return c.wreckTotal;
    };
    this.ranking = this.order.slice().sort((a, b) => key(b) - key(a));
    this.ranking.forEach((c, i) => { c.pos = i + 1; });
    return this.ranking;
  }

  end(reason) {
    if (this.state !== 'racing') return;
    this.state = 'over'; this.finishedAt = 0;
    for (const c of this.order) {
      if (c.racing) { c.state = 'dnf'; c.wreckTotal = c.total; c.wreckTime = this.raceTic; }
    }
    this.rank();
    const racers = this.ranking.filter((c) => !c.left);
    this.result = { reason, ranking: racers, winner: racers[0] || null, count: racers.length };
    this.events.push({ type: 'arenaEnd', arena: this, result: this.result });
  }

  get over() { return this.state === 'over' && this.finishedAt >= this.cfg.endHold * TICRATE; }
}
