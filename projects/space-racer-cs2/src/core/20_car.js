// ===================================================================================
// Part 2: a car - state, driving physics, rails, falls, pads, boost, drift, spin attack, bumps.
// ===================================================================================

class Car {
  constructor(slot, name, clsKey, team) {
    this.slot = slot; this.name = name; this.cls = clsKey; this.spec = CARS[clsKey] || CARS.hornet; this.team = team;
    this.isBot = false; this.bot = null; this.person = null;
    this.x = 0; this.y = 0; this.z = 0; this.yaw = 0; this.vx = 0; this.vy = 0; this.vz = 0;
    this.speed = 0; this.vf = 0; this.vl = 0;
    this.shield = this.spec.shield; this.charge = RULES.startCharge;
    this.state = 'grid';          // grid | racing | falling | finished | gone | wrecked | withdrawn
    this.cmd = { throttle: 0, steer: 0, boost: false, drift: false, spin: false, ability: false, abilityDir: 0 };
    this.padTimer = 0; this.boosting = false; this.drifting = false; this.sliding = false; this.onCharge = false; this.slick = false;
    this.draft = null; this.spinTimer = 0; this.spinCd = 0; this.spinYaw = 0; this.hitCd = 0; this.ghost = 0;
    this.stagger = 0; this.knockCd = 0; this.lock = 0;   // lock: seconds left before spin / E work (the start)   // skidding after a spin hit; no second shove from the same spin
    // the E ability: cooldown; what fired this step (the arena does the part that touches other cars); timers
    this.abilCd = 0; this.fired = null; this.novaTimer = 0; this.novaLeft = 0; this.fireT = 0; this.aegis = 0; this.scorch = 0; this.burnCd = 0;
    this.driftDir = 0; this.driftStreak = 0;   // drift charge needs a held slide one way
    this.seg = 0; this.t = 0; this.d = 0; this.s = 0; this.prevS = 0; this.rawLap = 0; this.lapsDone = 0; this.nextCp = 1; this.total = 0;
    this.lapStart = 0; this.bestLap = 0; this.lastLap = 0;
    this.finishPos = 0; this.finishTime = 0; this.wreckTotal = 0; this.wreckTime = 0; this.stateTime = 0;
    this.lastHit = null;           // { slot, tic }
    this.wrongWay = 0; this.wrongWayFlag = false; this.offLine = false;
    this.out = false; this.exitS = 0;   // fell: over the rails out of the map (a bigger hit), and where it left the road
    this.fallTimer = 0; this.fx = 0;   // fx bits for the renderer: 1 hit, 2 rail, 4 pulsed, 8 pad, 16 fell
    this.pulsed = 0; this.noDamage = 0; this.calm = 0;   // seconds of no-damage after the start
    this.air = false; this.tz = 0; this.lift = 0; this.airTime = 0;   // jumps: airborne flag, track height, ramp height under the car
    this.fly = false;              // in a flight section (air is true too)
    this.creatureCd = 0; this.creatureWarned = -1;   // sea creatures: no second hit for a moment; the pass last warned about
    this.bank = 0;                 // tan of the road's lean under the car (banked bends)
    this.yawRate = 0;              // how fast the car is turning (radians per second, smoothed; + = left)
    this.gasAt = null; this.stall = 0;   // turbo start: when the gas went down on the grid; seconds of stalled engine
    this.gridPos = 0; this.pos = 0;      // grid slot; place in the race (set by the arena)
    this.koBy = null; this.koApplied = false;   // who wrecked it, and whether that kill was sent at once (CS2 side)
    // used by the CS2 side (sound edges, the HUD's turn arrow). Every field a car will ever have is made here: a field
    // added later gives some cars a different shape and makes the physics noticeably slower.
    this.wasBoost = false; this.wasCharge = false; this.turnTick = -1; this.turnCls = null;
    this.shade = 0;                // the driver's colour shade (index into their side's shades)
    this.glow = 0;                 // 1..3: placed that high in the driver's race last round (the car glows)
  }

  placeAt(x, y, z, yaw, track) {
    this.x = x; this.y = y; this.z = z; this.yaw = yaw; this.vx = 0; this.vy = 0; this.vz = 0; this.speed = 0; this.vf = 0; this.vl = 0;
    this.air = false; this.fly = false; this.tz = z; this.lift = 0; this.yawRate = 0;
    const p = track.locateAll(x, y, z);
    this.seg = p.i; this.t = p.t; this.d = p.d; this.s = p.s; this.prevS = p.s;
  }

  get racing() { return this.state === 'racing' || this.state === 'falling'; }
  get solid() { return this.state === 'racing' && this.ghost <= 0; }
  get visible() { return this.state === 'racing' || this.state === 'falling' || this.state === 'grid' || this.state === 'finished' || (this.state === 'wrecked' && this.stateTime < RULES.wreckShow); }

  // ---------------------------------------------------------------- one physics step
  step(track, dt, tic) {
    const sp = this.spec, c = this.cmd;
    this.fx = 0;
    if (this.spinCd > 0) this.spinCd -= dt;
    if (this.hitCd > 0) this.hitCd -= dt;
    if (this.ghost > 0) this.ghost -= dt;
    if (this.noDamage > 0) this.noDamage -= dt;
    if (this.abilCd > 0) this.abilCd -= dt;
    if (this.aegis > 0) this.aegis -= dt;
    if (this.scorch > 0) this.scorch -= dt;
    if (this.creatureCd > 0) this.creatureCd -= dt;
    this.stateTime += dt;
    if (this.state !== 'racing' && this.state !== 'finished') this.yawRate *= 0.9;
    if (this.state === 'falling') { this.fallStep(track, dt, tic); return; }
    if (this.state !== 'racing' && this.state !== 'finished') return;
    const finished = this.state === 'finished';
    // finished cars coast on autopilot for a moment, then leave
    if (this.stall > 0) this.stall -= dt;
    const throttle = finished ? 0.4 : this.stall > 0 ? 0 : clamp(c.throttle, -1, 1);
    const steer = finished ? this.autoSteer(track) : (this.spinTimer > 0 ? 0 : clamp(c.steer, -1, 1));
    const flying = this.fly, air = this.air && !flying;    // flying: driven like the road (thrust, grip), height by W / S
    const wantBoost = !finished && !air && c.boost && this.charge > 0;
    this.drifting = !finished && !this.air && c.drift && this.speed > 250;
    // spin attack
    // the start: no spins, no Shockwave and no Seeker Bolt (the E abilities that hit others); Nova Burn and Aegis off
    // the line are fine
    if (this.lock > 0) { this.lock -= dt; c.spin = false; if (sp.ability === 'quake' || sp.ability === 'bolt') c.ability = false; }
    if (!finished && c.spin && this.spinCd <= 0 && this.charge >= sp.spinCost && this.spinTimer <= 0) {
      this.charge -= sp.spinCost; this.spinTimer = RULES.spinTime; this.spinCd = RULES.spinCooldown; this.fx |= 32;
    }
    c.spin = false;
    // the E ability (charge cost and cooldown per car)
    if (!finished && c.ability && this.abilCd <= 0 && this.charge >= sp.abilityCost && this.stall <= 0) this.useAbility(track, c);
    c.ability = false; c.abilityDir = 0;
    if (this.spinTimer > 0) { this.spinTimer -= dt; this.spinYaw += dt * (4 * Math.PI / RULES.spinTime); if (this.spinTimer <= 0) this.spinYaw = 0; }
    if (this.knockCd > 0) this.knockCd -= dt;
    if (this.stagger > 0) {
      // skidding after a spin hit: the tail swings from side to side, less and less
      this.stagger -= dt;
      const k = Math.max(0, this.stagger) / RULES.spinStagger;
      if (this.spinTimer <= 0) this.spinYaw = this.stagger > 0 ? Math.sin((RULES.spinStagger - this.stagger) * 22) * 0.4 * k : 0;
    }
    // heading
    let fx = Math.cos(this.yaw), fy = Math.sin(this.yaw);
    this.vf = this.vx * fx + this.vy * fy;
    const absv = Math.abs(this.vf);
    let turnRate = sp.turn * clamp(absv / 220, 0, 1) / (1 + Math.max(0, absv - 450) / RULES.turnFade);
    if (this.drifting) turnRate *= 1.45;
    if (this.slick) turnRate *= 0.8;
    if (this.spinTimer > 0) turnRate *= 0.3;
    if (this.stagger > 0) turnRate *= RULES.staggerSteer;
    if (this.scorch > 0) turnRate *= 0.8;
    if (!air) turnRate *= 1 + Math.abs(this.bank) * RULES.bankTurn;   // banked bends turn tighter
    if (air) turnRate *= RULES.airControl;
    const yawRate = turnRate * steer * (this.vf < 0 ? -1 : 1);       // radians per second, + = turning left
    this.yaw += yawRate * dt;
    this.yawRate += (yawRate - this.yawRate) * Math.min(1, dt * 8);   // smoothed, for the cars' and cameras' lean
    fx = Math.cos(this.yaw); fy = Math.sin(this.yaw);
    const lx = -fy, ly = fx;
    let vf = this.vx * fx + this.vy * fy, vl = this.vx * lx + this.vy * ly;
    // engine
    this.boosting = wantBoost;
    if (this.boosting) this.charge = Math.max(0, this.charge - RULES.boostDrain * dt);
    let mult = 1;
    if (this.boosting) mult = sp.boost;
    if (this.padTimer > 0) { this.padTimer -= dt; mult = Math.max(mult, RULES.padSpeed) + (this.boosting ? 0.1 : 0); }
    if (this.novaTimer > 0) { this.novaTimer -= dt; mult = Math.max(mult, RULES.novaSpeed); }
    if (this.draft) mult *= RULES.draftSpeed;
    const target = sp.maxSpeed * mult;
    let acc = sp.accel * (this.boosting ? 1.6 : 1) * (this.padTimer > 0 ? 1.5 : 1) * (this.novaTimer > 0 ? 2 : 1) * (this.draft ? 1.15 : 1);
    if (air) {
      vf -= vf * 0.05 * dt;            // no thrust or brakes in the air
    } else if (flying) {
      if (vf < target) vf = Math.min(target, vf + acc * dt);     // flight: always full thrust (W / S work the height)
    } else if (throttle > 0) {
      if (vf < target) vf = Math.min(target, vf + acc * throttle * dt);
    } else if (throttle < 0) {
      vf = Math.max(-RULES.reverseMax, vf + sp.brake * throttle * dt);
    } else {
      vf -= vf * RULES.coastDrag * dt;
    }
    if (vf > target && !air) vf -= (vf - target) * 3 * dt;
    // grip: bleed off sideways speed
    let grip = this.drifting ? sp.driftGrip : sp.grip;
    if (this.slick) grip *= RULES.slickGrip;
    if (this.spinTimer > 0) grip *= 0.5;
    if (this.stagger > 0) grip *= RULES.staggerGrip;
    if (this.scorch > 0) grip *= 0.6;                                   // driving through Nova fire
    if (!air) grip *= 1 + Math.abs(this.bank) * RULES.bankGrip;        // ... and hold the car better
    const g = Math.exp(-(air ? RULES.airGrip : grip) * dt);   // in the air the heading still pulls the car round a little
    this.sliding = Math.abs(vl) > 90 && absv > 300;
    // drift charge: only through a slide held one way, and not while boosting (flicking left-right while holding drift
    // and boost used to keep the boost going for ever)
    const dir = steer > 0.2 ? 1 : steer < -0.2 ? -1 : 0;
    if (this.drifting && this.sliding && dir !== 0 && dir === this.driftDir) this.driftStreak += dt;
    else this.driftStreak = 0;
    this.driftDir = this.drifting ? dir : 0;
    if (this.driftStreak > RULES.driftStreak && !this.boosting) this.charge = Math.min(sp.charge, this.charge + RULES.driftChargeRate * sp.driftCharge * dt);
    vl *= g;
    this.vx = vf * fx + vl * lx; this.vy = vf * fy + vl * ly;
    this.vf = vf; this.vl = vl;
    this.speed = Math.hypot(this.vx, this.vy);
    this.x += this.vx * dt; this.y += this.vy * dt;
    // where on the track are we now
    const p = track.locate(this.x, this.y, this.tz, this.seg);
    this.seg = p.i; this.t = p.t; this.d = p.d; this.tz = p.z; this.bank = p.bank;
    this.prevS = this.s; this.s = p.s;
    // height: ramps lift the car, the lip of a ramp throws it, an open gap drops it
    const lift = track.rampLift(p.i, p.t);
    const ground = p.z + lift;
    const road = track.road[p.i];
    if (track.fly[p.i] && (this.state === 'racing' || finished)) {
      this.flyStep(track, p, finished ? clamp((p.z - this.z) / 120, -1, 1) : clamp(-c.throttle, -1, 1), dt, tic, finished);   // like a plane: W noses down, S pulls up
    } else if (this.air) {
      if (this.fly) this.fly = false;   // out of the corridor: falls onto the landing road
      this.airTime += dt;
      this.vz -= RULES.gravity * dt;
      this.z += this.vz * dt;
      if (this.z <= ground && road && !finished) {
        this.air = false; this.z = ground; this.fx |= 1024;
        if (this.vz < -RULES.landSafe && this.noDamage <= 0) this.damage(Math.min(RULES.contactMax, (-this.vz - RULES.landSafe) * 0.03), null, tic);
        else if (this.airTime > RULES.bigAirTime) { this.charge = Math.min(sp.charge, this.charge + RULES.bigAirCharge); this.fx |= 4096; }   // big air, clean landing
        this.vz = 0;
      } else if (!road && this.z < ground - 40 && !finished) {
        this.startFall(false); this.air = false;
      } else if (finished && this.z <= ground) { this.air = false; this.z = ground; this.vz = 0; }
    } else if (this.lift > 0 && lift === 0 && (!road || track.rampLift((p.i - 1 + track.n) % track.n, 0.99) > 0)) {
      // off the lip: fly with the ramp's slope
      const along = this.vx * track.tx[p.i] + this.vy * track.ty[p.i];
      const f = track.rampAt(p.i - 1);
      const slope = f ? f.h / ((f.b - f.a + 1) * track.step) : 0.3;
      this.air = true; this.airTime = 0; this.z = p.z + this.lift; this.vz = Math.max(0, along) * slope * RULES.rampThrow + RULES.rampKick;
      if (f && f.maxD && along > 300) {
        // no further than the landing deck runs straight: solve the throw that comes down there at this speed
        const T = f.maxD / along, z0 = p.z + this.lift, zl = f.endZ;
        const vzMax = (zl - z0) / T + RULES.gravity * T / 2;
        if (vzMax < this.vz) this.vz = Math.max(RULES.rampKick, vzMax);
      } this.fx |= 512;
    } else if (!road && !finished) {
      this.startFall(false); this.vz = 0;
    } else {
      this.z = ground;
    }
    this.lift = this.air ? 0 : lift;
    if (this.state === 'falling') { this.speed = Math.hypot(this.vx, this.vy); return; }
    // rails and gaps
    const limit = p.hw - CAR_R * 0.7;
    // in the air higher than the rails: nothing holds the car in - past the edge it is out of the map
    const overRails = this.air && !finished && this.z - ground > RULES.railHeight;
    if (!this.fly && Math.abs(this.d) > limit) {
      const side = this.d > 0 ? 1 : -1;
      const nx = track.nx[p.i] * side, ny = track.ny[p.i] * side;   // points out of the track on this side
      if (overRails) {
        if (Math.abs(this.d) > p.hw + CAR_R * 0.4) this.startFall(true);
      } else if (p.rail || finished) {
        const over = Math.abs(this.d) - limit;
        this.x -= nx * over; this.y -= ny * over; this.d = side * limit;
        const vn = this.vx * nx + this.vy * ny;
        if (vn > 0) {
          this.vx -= (1 + RULES.railRestitution) * vn * nx; this.vy -= (1 + RULES.railRestitution) * vn * ny;
          const hard = Math.max(0, vn - RULES.railSoft);
          if (hard > 0 && !finished) {
            if (this.noDamage <= 0) this.damage(Math.min(RULES.contactMax, hard * RULES.railDamage), null, tic);
            const k = 1 - Math.min(0.45, vn / 1400);
            this.vx *= k; this.vy *= k;
            this.fx |= 2;
          } else this.fx |= 64;   // scrape
          // turn the nose a little away from the wall so the car doesn't grind along it
          const away = Math.atan2(-ny, -nx);
          this.yaw += normRad(away - this.yaw) * Math.min(1, vn / 600) * 0.15;
        }
      } else if (Math.abs(this.d) > p.hw + CAR_R * 0.4 && !finished) {
        this.startFall(false); this.vz = 0;
      }
    }
    this.speed = Math.hypot(this.vx, this.vy);
    // progress bookkeeping (laps and checkpoints)
    this.progress(track, tic);
    // features under the car
    this.onCharge = false; this.slick = false;
    const feats = this.fly ? this.ringsAt(track, p) : this.air ? null : track.featuresAt(this.seg, -this.d / Math.max(1, p.hw));
    if (feats && !finished) {
      for (const f of feats) {
        if (f.kind === 'boost' || f.kind === 'ring') {
          if (this.padTimer <= 0) { this.vx += fx * RULES.padKick; this.vy += fy * RULES.padKick; this.fx |= 8; }
          this.padTimer = Math.max(this.padTimer, RULES.padTime * sp.padMult);
        } else if (f.kind === 'charge' || f.kind === 'cring') {
          this.onCharge = true;
          this.charge = Math.min(sp.charge, this.charge + RULES.chargeRate * sp.chargeMult * dt);
          this.shield = Math.min(sp.shield, this.shield + RULES.chargeShield * dt);
        } else if (f.kind === 'slick') this.slick = true;
      }
    }
    // slow repair when nothing has hit us for a while
    this.calm += dt;
    if (this.calm > RULES.regenDelay && !finished) this.shield = Math.min(sp.shield, this.shield + RULES.regenRate * dt);
    // slipstream bonus (draft is set by the arena before the step)
    if (this.draft && !finished) {
      const team = this.draft.team >= 0 && this.draft.team === this.team;
      this.charge = Math.min(sp.charge, this.charge + RULES.draftCharge * sp.draftMult * (team ? 2 : 1) * dt);
      if (sp.draftRegen) this.shield = Math.min(sp.shield, this.shield + sp.draftRegen * dt);
    }
    // wrong way: moving against the track direction for a while
    const along = this.vx * track.tx[this.seg] + this.vy * track.ty[this.seg];
    if (along < -60) this.wrongWay += dt; else this.wrongWay = 0;
    this.wrongWayFlag = this.wrongWay > RULES.wrongWayTime;
  }

  // one step in a flight section: height from W / S, the corridor's edge bounces like a rail
  flyStep(track, p, climb, dt, tic, finished) {
    if (!this.fly) { this.fly = true; this.air = true; this.airTime = 0; this.lift = 0; this.fx |= 8192; }
    this.airTime += dt;
    const want = climb > 0.1 ? climb * RULES.flyClimb : climb < -0.1 ? climb * RULES.flyDive : -RULES.flySink;
    this.vz += (want - this.vz) * Math.min(1, dt * RULES.flyResp);
    this.z += this.vz * dt;
    const R = Math.max(40, track.flyR[p.i] - CAR_R * 0.6);
    const dz = this.z - p.z, r = Math.hypot(this.d, dz);
    if (r <= R) return;
    const ud = this.d / r, uz = dz / r, nx = track.nx[p.i], ny = track.ny[p.i];
    // back onto the edge
    const dd = ud * R - this.d;
    this.x += nx * dd; this.y += ny * dd; this.d += dd; this.z = p.z + uz * R;
    // bounce off it
    const vlat = this.vx * nx + this.vy * ny, vr = vlat * ud + this.vz * uz;
    if (vr <= 0) return;
    const k = 1 + RULES.flyRest;
    this.vx -= nx * k * vr * ud; this.vy -= ny * k * vr * ud; this.vz -= k * vr * uz;
    const hard = Math.max(0, vr - RULES.railSoft);
    if (hard > 0 && !finished) {
      if (this.noDamage <= 0) this.damage(Math.min(RULES.contactMax, hard * RULES.railDamage), null, tic);
      this.fx |= 2;
    } else this.fx |= 64;
  }

  // flight rings under the car: a ring counts when the car passes through it (centre d / height dz, radius rr)
  ringsAt(track, p) {
    const list = track.featAt[this.seg];
    if (!list) return null;
    let out = null;
    const dz = this.z - p.z;
    for (const k of list) {
      const f = track.feats[k];
      if (f.kind !== 'ring' && f.kind !== 'cring') continue;
      if (Math.hypot(this.d - f.rd, dz - f.rz) < f.rr) (out || (out = [])).push(f);
    }
    return out;
  }

  autoSteer(track) {
    const p = track.point(this.s + 260);
    const want = Math.atan2(p.y - this.y, p.x - this.x);
    return clamp(normRad(want - this.yaw) * 2, -1, 1);
  }

  // off the track: falls for a moment (keeping its speed, so a car that flew out sails on out of the map)
  startFall(out) {
    this.state = 'falling'; this.stateTime = 0; this.fallTimer = RULES.fallTime; this.fx |= 16;
    this.out = out; this.exitS = this.s;
  }

  fallStep(track, dt, tic) {
    this.fallTimer -= dt;
    this.vz -= 900 * dt;
    this.x += this.vx * dt; this.y += this.vy * dt; this.z += this.vz * dt;
    this.vx *= 0.98; this.vy *= 0.98;
    if (this.fallTimer <= 0) {
      // back on the track's centreline where it left it (or just past, if that was a gap, a ramp or a flight), facing
      // forward, with no speed and a hit to the shield
      const s = safeSpot(track, this.exitS);
      const p = track.point(s);
      this.x = p.x; this.y = p.y; this.z = p.z; this.yaw = Math.atan2(p.ty, p.tx);
      this.vx = 0; this.vy = 0; this.vz = 0; this.speed = 0; this.vf = 0; this.vl = 0;
      this.seg = p.i; this.prevS = this.exitS; this.s = s; this.d = 0; this.air = false; this.fly = false; this.tz = p.z; this.lift = 0;
      this.state = 'racing'; this.stateTime = 0; this.ghost = 1.5; this.padTimer = 0;
      this.progress(track, tic);          // count any checkpoint between where it left and where it comes back
      this.prevS = s;
      this.shield -= this.out ? RULES.outPenalty : RULES.fallPenalty;
      this.out = false;
      this.fx |= 128;
    }
  }

  // laps and checkpoints from the change of progress this tick
  progress(track, tic) {
    const L = track.len;
    let ds = this.s - this.prevS;
    if (ds < -L / 2) { ds += L; this.rawLap++; this.crossStart(track, 1, tic); }
    else if (ds > L / 2) { ds -= L; this.rawLap--; this.crossStart(track, -1, tic); }
    // checkpoints 1..7: passed forward when progress crosses them
    if (ds > 0) {
      const k = this.nextCp;
      if (k < track.cp.length) {
        const cs = track.cpS[k];
        if (this.crossed(this.prevS, this.s, cs, L)) this.nextCp = k + 1;
      }
    } else if (ds < 0) {
      const k = this.nextCp - 1;
      if (k >= 1 && this.crossed(this.s, this.prevS, track.cpS[k], L)) this.nextCp = k;
    }
    // ranking progress: clamp to the next checkpoint so a missed one (or a crossing cut) doesn't count
    let s = this.s;
    const nextS = this.nextCp < track.cp.length ? track.cpS[this.nextCp] : L;
    this.offLine = s > nextS + track.step * 3;
    if (this.offLine) s = nextS;
    this.total = this.lapsDone * L + s;
  }

  crossed(a, b, c, L) {
    // did progress going forward from a to b pass c (a < b; a and b are not wrapped here)
    if (a <= b) return a < c && c <= b;
    return false;
  }

  crossStart(track, dir, tic) {
    if (dir > 0) {
      if (this.nextCp >= track.cp.length) {
        this.lapsDone++; this.nextCp = 1;
        const now = tic / TICRATE;
        this.lastLap = now - this.lapStart; this.lapStart = now;
        if (!this.bestLap || this.lastLap < this.bestLap) this.bestLap = this.lastLap;
        this.fx |= 256;
      }
    } else {
      // reversing back over the line: undo a lap if it was complete
      if (this.nextCp === 1 && this.lapsDone > 0) { this.lapsDone--; this.nextCp = track.cp.length; }
    }
  }

  // the E ability. The car's own part happens here; whatever touches other cars (the Shockwave, the Aegis share, Nova
  // fire) is done by the arena, which sees `fired`.
  useAbility(track, c) {
    const sp = this.spec;
    this.abilCd = sp.abilityCd; this.fired = sp.ability; this.fx |= 2048;
    const fx = Math.cos(this.yaw), fy = Math.sin(this.yaw), lx = -fy, ly = fx;
    if (sp.ability === 'bolt') {
      this.charge -= sp.abilityCost;                // the arena launches the bolt
    } else if (sp.ability === 'nova') {
      const all = this.charge;
      this.charge = 0;
      this.novaTimer = this.novaLeft = RULES.novaTime + all * RULES.novaTimePerCharge;
      this.vx += fx * RULES.novaKick; this.vy += fy * RULES.novaKick; this.fireT = 0;
    } else if (sp.ability === 'quake') {
      this.charge -= sp.abilityCost;
      this.vx *= 0.92; this.vy *= 0.92;          // the slam costs the Meteor a little speed
    } else if (sp.ability === 'aegis') {
      this.charge -= sp.abilityCost;
      this.aegis = RULES.aegisTime; this.stagger = 0;
    }
  }

  damage(amount, attacker, tic) {
    if (amount <= 0 || this.state !== 'racing' || this.aegis > 0) return;
    this.shield -= amount;
    this.fx |= 1;
    if (attacker && attacker !== this) this.lastHit = { slot: attacker.slot, tic };
    this.calm = 0;
  }
}

// where a car that fell off at s goes back on: the first stretch of solid, flat road (no gap, ramp or flight) from s on
function safeSpot(track, s) {
  const n = track.n, i0 = Math.floor((((s % track.len) + track.len) % track.len) / track.step);
  const ok = (i) => track.road[i % n] && !track.rampOf[i % n] && !track.fly[i % n];
  for (let k = 0; k < n; k++) {
    const i = i0 + k;
    if (ok(i) && ok(i + 1) && ok(i + 2) && ok(i + 3)) return ((i % n) + 0.5) * track.step;
  }
  return i0 * track.step;
}

// ---------------------------------------------------------------- pairs
// a spin attack landing: the other car is shoved sideways, away from the attacker (harder by a heavier car, less
// into a heavier one), loses a little speed and skids for a moment, so the shove carries it across the road - often
// into the rail. A car just spun can't be spun again for a moment (RULES.spinImmune).
function spinHit(att, vic, nx, ny) {
  if (!shove(att, vic, nx, ny, RULES.spinKnock, RULES.spinStagger)) return false;
  vic.knockCd = RULES.spinImmune;
  return true;
}
// a sideways shove away from `att` (the Shockwave uses it too); an Aegis shell can't be shoved
function shove(att, vic, nx, ny, knock, stagger) {
  if (vic.knockCd > 0 || vic.aegis > 0) return false;
  const lx = -Math.sin(vic.yaw), ly = Math.cos(vic.yaw);            // the victim's left
  const side = nx * lx + ny * ly >= 0 ? 1 : -1;                      // the attacker is on the other side
  const k = knock * att.spec.mass / vic.spec.mass;
  vic.vx = vic.vx * (1 - RULES.spinSlow) + lx * side * k;
  vic.vy = vic.vy * (1 - RULES.spinSlow) + ly * side * k;
  vic.stagger = stagger; vic.knockCd = 0.4;
  return true;
}

// two solid cars. A spinning car hits anything within its reach (a car swinging round sweeps further than its body),
// touching or not, moving closer or not. Bodies that touch are separated and swap momentum by mass, with shield
// damage from the closing speed. Returns [attacker, victim] when a spin attack landed.
function collideCars(a, b, tic) {
  if (Math.abs(a.z - b.z) > 60) return null;
  const dx = b.x - a.x, dy = b.y - a.y;
  const dist2 = dx * dx + dy * dy;
  const R = CAR_R * 2;
  const aSpin = a.spinTimer > 0, bSpin = b.spinTimer > 0;
  const reach = aSpin !== bSpin ? R + RULES.spinReach : R;
  if (dist2 >= reach * reach) return null;
  const dist = Math.sqrt(dist2) || 0.01;
  const nx = dx / dist, ny = dy / dist;
  let hit = null;
  if (aSpin && !bSpin && b.noDamage <= 0 && spinHit(a, b, nx, ny)) { b.damage(RULES.spinDamage, a, tic); b.hitCd = 0.25; hit = [a, b]; }
  else if (bSpin && !aSpin && a.noDamage <= 0 && spinHit(b, a, -nx, -ny)) { a.damage(RULES.spinDamage, b, tic); a.hitCd = 0.25; hit = [b, a]; }
  if (hit) { a.fx |= 1; b.fx |= 1; }
  if (dist >= R) return hit;
  // an Aegis shell is as good as a wall: four times the mass, so the other car bounces off
  const ma = a.spec.mass * (a.aegis > 0 ? RULES.aegisMass : 1), mb = b.spec.mass * (b.aegis > 0 ? RULES.aegisMass : 1), msum = ma + mb;
  const over = R - dist;
  a.x -= nx * over * (mb / msum); a.y -= ny * over * (mb / msum);
  b.x += nx * over * (ma / msum); b.y += ny * over * (ma / msum);
  const vrel = (a.vx - b.vx) * nx + (a.vy - b.vy) * ny;   // > 0: closing
  if (vrel > 0) {
    const j = (1 + RULES.contactRestitution) * vrel / (1 / ma + 1 / mb);
    a.vx -= j / ma * nx; a.vy -= j / ma * ny;
    b.vx += j / mb * nx; b.vy += j / mb * ny;
    let base = Math.min(RULES.contactMax, Math.max(0, vrel - RULES.contactSoft) * RULES.contactDamage);
    if (a.noDamage > 0 || b.noDamage > 0) base = 0;
    let da = base, db = base;
    if (a.spec.ram > 1) { db *= a.spec.ram; da /= a.spec.ram; }
    if (b.spec.ram > 1) { da *= b.spec.ram; db /= b.spec.ram; }
    if (a.aegis > 0 && b.aegis <= 0 && b.noDamage <= 0) db = Math.max(db, RULES.aegisBump);   // bouncing off an Aegis hurts
    if (b.aegis > 0 && a.aegis <= 0 && a.noDamage <= 0) da = Math.max(da, RULES.aegisBump);
    if (aSpin && !bSpin) da = 0;                 // the spinner takes no bump damage (its hit was dealt above)
    else if (bSpin && !aSpin) db = 0;
    else if (aSpin && bSpin && a.noDamage <= 0 && b.noDamage <= 0) { da = db = RULES.spinDamage; }   // two spins meet
    if (a.hitCd <= 0 && da > 0) { a.damage(da, b, tic); a.hitCd = 0.25; }
    if (b.hitCd <= 0 && db > 0) { b.damage(db, a, tic); b.hitCd = 0.25; }
    if (da > 0 || db > 0) { a.fx |= 1; b.fx |= 1; }
  }
  return hit;
}
