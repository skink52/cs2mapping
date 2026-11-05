// The title abilities on two cars at speed on a straight: what each one does to the other car, in numbers, so a change
// to RULES can be checked without a full sim. Prints, for the title the core module was built for:
//   NEON   Light Trail: a car cutting across the wall - bounced back, speed and shield lost. EMP: charge lost, fried
//          time. Overclock: charge spent over a boost. Firewall: an enemy and a teammate driving into it.
//   DEPTH  Ink Cloud: a car in it - steering and grip, shield lost. Depth Charge: a car tripping it - shove, lift,
//          shield. Hydrojet: speed, and a mine it rides over. Undertow: a teammate's and an enemy's speed in the wake.
//   SPACE  (nothing new: see spin_test.cjs; the Seeker Bolt and the others are measured in the sim)
// usage: SPR_CORE=<core module> node test/ability_test.cjs   (default build/core_test.cjs from tools/build.mjs)
const C = require(process.env.SPR_CORE || '../build/core_test.cjs');
const R = C.RULES;
const track = new C.Track(C.TRACKS.find((t) => t.id === 'oval') || C.TRACKS.find((t) => t.id === 'grid') || C.TRACKS.find((t) => t.id === 'coral') || C.TRACKS[0]);

// two (or three) cars on the start straight; returns the arena and the cars; every car racing at `speed`
function setup(specs, speed = 1200) {
  const a = new C.Arena(0, track, { countdownTics: 1, finishWindow: 30, raceCap: 300, endHold: 6, laps: 0 });
  const cars = specs.map((s, k) => a.addCar(k, s.name || 'car' + k, s.cls, s.team));
  for (const c of cars) c.isBot = false;
  a.placeGrid();
  a.step();                                                    // lights out
  const i = 20, tx = track.tx[i], ty = track.ty[i], lx = -ty, ly = tx, yaw = Math.atan2(ty, tx);
  specs.forEach((s, k) => {
    const car = cars[k];
    const along = s.along || 0, side = s.side || 0;
    car.placeAt(track.x[i] + tx * along + lx * side, track.y[i] + ty * along + ly * side, track.z[i], yaw, track);
    car.state = 'racing'; car.noDamage = 0; car.lock = 0; car.vx = tx * speed; car.vy = ty * speed; car.charge = 100;
    car.cmd.throttle = 1; car.cmd.steer = 0;
  });
  return { a, cars, tx, ty, lx, ly };
}
function run(a, secs, each) { for (let t = 0; t < secs * C.TICRATE; t++) { if (each) each(t / C.TICRATE); a.step(); } }
const f1 = (v) => (Math.round(v * 10) / 10).toString();
const theme = C.GAME_THEME;
console.log('title', theme, '- track', track.id);

if (theme === 'neon') {
  // LIGHT TRAIL: the Hornet lays it; an enemy 250 behind and 120 to the side steers across the line behind the Hornet
  {
    const { a, cars } = setup([{ cls: 'hornet', team: 0 }, { cls: 'meteor', team: 1, along: -250, side: 120 }]);
    const [h, m] = cars;
    h.cmd.ability = true;
    let hit = false, sBefore = 0, vBefore = 0, dBefore = 0;
    run(a, 2.5, (t) => {
      m.cmd.steer = t > 0.2 && t < 1.3 ? -0.6 : 0;                       // cut right, across the trail
      for (const e of a.events) if (e.type === 'hazard' && !hit) { hit = true; sBefore = m.shield; vBefore = m.speed; dBefore = m.d; }
      a.events.length = 0;
    });
    console.log(`LIGHT TRAIL: walls laid ${a.walls.length}, ${hit ? 'the Meteor hit one' : 'the Meteor missed'}; after: shield ${f1(m.shield)}/110, speed ${f1(m.speed)}, d ${f1(m.d)}`);
  }
  // EMP: a Meteor fires with a boosting Hornet 150 ahead
  {
    const { a, cars } = setup([{ cls: 'meteor', team: 0 }, { cls: 'hornet', team: 1, along: 150 }]);
    const [m, h] = cars;
    h.cmd.boost = true; h.charge = 80;
    run(a, 0.2);
    const c0 = h.charge, v0 = h.speed;
    m.cmd.ability = true;
    a.step(); a.step();
    console.log(`EMP: the Hornet's charge ${f1(c0)} -> ${f1(h.charge)}, fried ${f1(h.emp)} s, boosting ${h.boosting}, shield ${f1(h.shield)}/108`);
    run(a, 1.2);
    console.log(`     1.2 s later: fried ${f1(Math.max(0, h.emp))} s, speed ${f1(v0)} -> ${f1(h.speed)}`);
  }
  // OVERCLOCK: the Comet boosts for 3 s with and without it
  {
    for (const oc of [false, true]) {
      const { a, cars } = setup([{ cls: 'comet', team: 0 }]);
      const [c] = cars;
      c.charge = 130;
      if (oc) c.cmd.ability = true;
      run(a, 0.1);
      const c0 = c.charge;
      c.cmd.boost = true;
      run(a, 3.0);
      console.log(`OVERCLOCK ${oc ? 'on ' : 'off'}: 3 s of boost: charge ${f1(c0)} -> ${f1(c.charge)}, speed ${f1(c.speed)}`);
    }
  }
  // FIREWALL: a Bastion fires; an enemy 300 behind in its lane and a teammate 300 behind in the next lane drive on
  {
    const { a, cars } = setup([{ cls: 'bastion', team: 0 }, { cls: 'hornet', team: 1, along: -300 }, { cls: 'comet', team: 0, along: -300, side: 90 }], 1300);
    const [b, foe, mate] = cars;
    b.cmd.ability = true;
    foe.vx *= 1.15; foe.vy *= 1.15; mate.vx *= 1.15; mate.vy *= 1.15;
    const hits = [];
    run(a, 1.5, () => { for (const e of a.events) if (e.type === 'hazard') hits.push(e.car.name); a.events.length = 0; });
    const w = a.walls[0];
    console.log(`FIREWALL: ${w ? f1(Math.hypot(w.x1 - w.x0, w.y1 - w.y0)) + ' wide' : 'no wall'}; hit by [${hits.join(', ')}]; the enemy: speed ${f1(foe.speed)}, shield ${f1(foe.shield)}/108; the teammate: speed ${f1(mate.speed)}, shield ${f1(mate.shield)}/110`);
  }
}

if (theme === 'depth') {
  // INK CLOUD: the Hornet lays it; an enemy 300 behind drives through
  {
    const { a, cars } = setup([{ cls: 'hornet', team: 0 }, { cls: 'meteor', team: 1, along: -300 }]);
    const [h, m] = cars;
    h.cmd.ability = true;
    m.vx *= 1.2; m.vy *= 1.2;
    let inked = 0;
    run(a, 2.5, () => { if (m.inked > 0) inked += C.DT; });
    console.log(`INK CLOUD: clouds ${a.clouds.length}; the Meteor was in ink ${f1(inked)} s, shield ${f1(m.shield)}/110`);
  }
  // DEPTH CHARGE: the Meteor drops one; an enemy 650 behind runs over it (a car closer than about 450 is past the spot
  // before the mine arms)
  {
    const { a, cars } = setup([{ cls: 'meteor', team: 0 }, { cls: 'hornet', team: 1, along: -650, side: 20 }]);
    const [m, h] = cars;
    m.cmd.ability = true;
    h.vx *= 1.2; h.vy *= 1.2;
    let boom = null, dMax = 0, zMax = 0;
    run(a, 2.5, () => { for (const e of a.events) if (e.type === 'mineBoom') boom = e; a.events.length = 0; if (boom) { dMax = Math.max(dMax, Math.abs(h.d)); zMax = Math.max(zMax, h.z - h.tz); } });
    console.log(`DEPTH CHARGE: ${boom ? 'went off, hit ' + boom.hits : 'did not go off'}; the Hornet: shoved to d ${f1(dMax)}, thrown ${f1(zMax)} up, shield ${f1(h.shield)}/108, speed ${f1(h.speed)}`);
  }
  // HYDROJET: the Comet surges over an armed enemy mine (dropped 700 ahead; the Comet jets at once and reaches it
  // after the mine has armed)
  {
    const { a, cars } = setup([{ cls: 'meteor', team: 1, along: 800 }, { cls: 'comet', team: 0 }]);
    const [m, c] = cars;
    m.cmd.ability = true;
    run(a, 0.1);
    const v0 = c.speed;
    c.cmd.ability = true;
    let boom = false;
    run(a, 1.5, () => { for (const e of a.events) if (e.type === 'mineBoom') boom = true; a.events.length = 0; });
    console.log(`HYDROJET: speed ${f1(v0)} -> ${f1(c.speed)} (jet left ${f1(Math.max(0, c.jet))} s); the mine ${boom ? 'went off' : 'stayed quiet under the Comet'}; mines left ${a.mines.length}`);
  }
  // UNDERTOW: a Bastion with a teammate and an enemy 250 behind
  {
    const { a, cars } = setup([{ cls: 'bastion', team: 0 }, { cls: 'hornet', team: 0, along: -250, side: 60 }, { cls: 'hornet', team: 1, along: -250, side: -60 }], 1300);
    const [b, mate, foe] = cars;
    const c0 = mate.charge;
    b.cmd.ability = true;
    run(a, 0.8);                                                           // (longer and the teammate, pulled along, runs into the Bastion)
    console.log(`UNDERTOW: the teammate: speed ${f1(mate.speed)}, charge ${f1(c0)} -> ${f1(mate.charge)}, towed ${mate.towed}; the enemy: speed ${f1(foe.speed)}, towed ${foe.towed}; the Bastion ${f1(b.speed)}`);
  }
  // PRESSURE: the track's height range and what a car feels at its top and bottom
  console.log(`PRESSURE: ${track.id} height range ${f1(track.zRange)} (${track.zRange >= R.pressureMinRange ? 'on' : 'off: under ' + R.pressureMinRange}): top speed -${R.pressureSpeed * 100}% / grip +${R.pressureGrip * 100}% / charge +${R.pressureCharge * 100}% at the bottom, the opposite at the top`);
}
