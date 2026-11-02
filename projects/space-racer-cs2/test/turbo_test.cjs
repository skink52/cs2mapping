// The secret turbo start. Gas down on the third beep (1 s before GO) or after it, and held to GO: a launch (speed
// kick + a pad boost). Gas held since before the second beep: a stall. Gas only after GO: neither. A player hears the
// beep late and reacts late, so the presses are also tried 0.1-0.4 s after the beep.
// usage: node test/turbo_test.cjs   (needs build/core_test.cjs from tools/build.mjs)
const C = require('../build/core_test.cjs');
const track = new C.Track(C.TRACKS[0]);

function start(pressAt, release) {
  const a = new C.Arena(0, track, { countdownTics: 10 * C.TICRATE, finishWindow: 30, raceCap: 300, endHold: 6, laps: 0 });
  const car = a.addCar(0, 'driver', 'hornet', 0);
  car.isBot = false;
  a.placeGrid();
  const beeps = [], got = [];
  let speedAtGo = null;
  for (let t = 0; t < 12 * C.TICRATE && a.state === 'grid'; t++) {
    const left = (a.countdown - 1) / C.TICRATE;           // seconds to GO at the tic about to run
    const down = pressAt !== null && left <= pressAt + 1e-9 && !(release !== undefined && left <= release);
    car.cmd.throttle = down ? 1 : 0;
    a.step();
    for (const e of a.events) {
      if (e.type === 'beep') beeps.push(+(a.countdown / C.TICRATE).toFixed(2));
      if (e.type === 'launch' || e.type === 'stall') got.push(e.type);
    }
    a.events.length = 0;
    if (a.state === 'racing') speedAtGo = Math.hypot(car.vx, car.vy);
  }
  return { beeps, got: got.join(',') || 'none', speedAtGo, pad: car.padTimer };
}

const cases = [
  ['on the third beep', 1.0, 'launch'],
  ['third beep, heard and pressed 0.25 s late', 0.75, 'launch'],
  ['third beep, 0.4 s late', 0.6, 'launch'],
  ['a moment before the third beep', 1.2, 'launch'],
  ['just before GO', 0.1, 'launch'],
  ['between the second and third beep', 1.6, 'none'],
  ['on the second beep', 2.0, 'stall'],
  ['held all through the countdown', 9.0, 'stall'],
  ['not at all', null, 'none'],
  ['on the third beep but let go before GO', 1.0, 'none', 0.3],
];
let bad = 0;
const r0 = start(null);
console.log('beeps at', r0.beeps.join(' / '), 's before GO; launch window', C.RULES.launchWindow, 's, stall if held since', C.RULES.stallAfter, 's');
for (const [name, at, want, rel] of cases) {
  const r = start(at, rel);
  const ok = r.got === want;
  if (!ok) bad++;
  console.log(`${ok ? 'ok  ' : 'FAIL'} ${name.padEnd(44)} -> ${r.got.padEnd(7)} (want ${want})${r.got === 'launch' ? `, speed at GO ${r.speedAtGo.toFixed(0)}, pad boost ${r.pad.toFixed(2)} s` : ''}`);
}
if (r0.beeps.join() !== '3,2,1') { console.log('FAIL beeps are not 3 / 2 / 1 s before GO'); bad++; }
console.log(bad ? `${bad} FAILED` : 'turbo start OK');
process.exit(bad ? 1 : 0);
