// How hard a spin attack shoves: two cars side by side at speed on a straight, one spins into the other. Prints how
// far across the road the victim is pushed, the speed it loses and the shield it loses (rail hits included), for
// every attacker / victim pair.
// usage: node test/spin_test.cjs [tune.json]   (needs build/core_test.cjs from tools/build.mjs)
const C = require('../build/core_test.cjs');
if (process.argv[2]) {                                         // a tuning file, as for sim.cjs tune=
  const t = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
  Object.assign(C.RULES, t.RULES || {});
  for (const [k, v] of Object.entries(t.CARS || {})) Object.assign(C.CARS[k], v);
}
const track = new C.Track(C.TRACKS.find((t) => t.id === 'oval') || C.TRACKS.find((t) => t.id === 'grid') || C.TRACKS[0]);   // (Space Racer's oval, Neon Racer's Grid Circuit, or the first track)

function trial(attKey, vicKey, speed = 900, gap = 70) {
  const a = new C.Arena(0, track, { countdownTics: 1, finishWindow: 30, raceCap: 300, endHold: 6, laps: 0 });
  const att = a.addCar(0, 'att', attKey, 0), vic = a.addCar(1, 'vic', vicKey, 1);
  att.isBot = vic.isBot = false;
  a.placeGrid();
  a.step();                                                    // lights out
  // side by side on the start straight, the attacker on the victim's right
  const i = 20, tx = track.tx[i], ty = track.ty[i], lx = -ty, ly = tx;
  const yaw = Math.atan2(ty, tx);
  for (const [car, off] of [[att, -gap / 2], [vic, gap / 2]]) {
    car.placeAt(track.x[i] + lx * off, track.y[i] + ly * off, track.z[i], yaw, track);
    car.state = 'racing'; car.noDamage = 0; car.lock = 0; car.vx = tx * speed;   // (lock: the start's no-attack seconds)
    car.vy = ty * speed; car.charge = 100;
    car.cmd.throttle = 1; car.cmd.steer = 0;
  }
  const d0 = vic.d, v0 = speed, s0 = vic.shield;
  att.cmd.spin = true;
  let dMax = 0, hit = false, rail = false;
  for (let t = 0; t < 1.5 * C.TICRATE; t++) {
    att.cmd.throttle = vic.cmd.throttle = 1; att.cmd.steer = vic.cmd.steer = 0;
    a.step();
    for (const e of a.events) if (e.type === 'spinHit') hit = true;
    a.events.length = 0;
    dMax = Math.max(dMax, Math.abs(vic.d - d0));
    if (Math.abs(vic.d) > track.hw[vic.seg] - 45) rail = true;
  }
  return { hit, push: dMax, rail, lost: s0 - vic.shield, wrecked: vic.state === 'wrecked' };
}

console.log('spin hit at 900 u/s, cars 70 apart; push = furthest the victim slides across the road in 1.5 s (half-width',
  track.hw[20] + ')');
const keys = C.CAR_KEYS;
for (const ak of keys) {
  const row = keys.map((vk) => {
    const r = trial(ak, vk);
    return `${vk.slice(0, 7).padEnd(7)} ${r.hit ? '' : '(miss) '}${r.push.toFixed(0).padStart(4)}${r.rail ? ' rail' : '     '} -${r.lost.toFixed(0).padStart(2)}`;
  });
  console.log(`${ak.padEnd(8)} hits: ${row.join(' | ')}`);
}
