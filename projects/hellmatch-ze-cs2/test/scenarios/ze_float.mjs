// Round 4 rows 4.1 and 4.3. 4 humans + 4 bots, 24 s, zemap=map01.
//   4.1: CT human 1 dies and rises as a lost soul in the T arena: its body has no gravity and hovers about 28 over the
//   floor under it (a gentle bob, under the ceiling), its eye 32 over the body; walking moves it and it stops again
//   (friction in the air); a dash aimed up flies up, and afterwards it sinks back to its hover height
//   4.3: T human 0 takes a big hit: the red screen goes no further than CONFIG.DAMAGE_TINT.MAX_STEP (red3) and is gone
//   within a second (Doom: red8 for about 3 s); the pickup gold and the berserk red are Doom's own
import { rm, pe, killDoom, liveZombie, timeline, invariants, checker, god, arenaOf } from './_lib.mjs';
const { probs, want } = checker();
const IN = { FORWARD: 1, ATTACK2: 512 };
const MF_NOGRAVITY = 512;
let push = null, samples = [], dashTop = -1e9, moved = null;
const flash = (api, slot) => { const c = api.dbg().hudCache.get(slot); return (c && c.get('fdm_flash')) || null; };
const soul = (api) => pe(api, 1).player;
const steps = timeline([
  [3, (api) => { killDoom(api, 1, null); pe(api, 1).zeClassPick = 'LOSTSOUL'; api.log('CT human 1 killed, picks the lost soul'); }],
  [10, (api) => {
    const z = soul(api);
    want(liveZombie(api, 1) && z.zclass === 'LOSTSOUL', 'slot 1 is a live lost soul: ' + (z && z.zclass));
    if (!z || !z.mo) return;
    want(!!(z.mo.flags & MF_NOGRAVITY), 'the lost soul body has no gravity');
    samples = [];
  }],
  [12, (api) => {
    const z = soul(api);
    if (!z || !z.mo || !samples.length) { probs.add('no hover samples'); return; }
    const hs = samples.map((s) => s.h), lo = Math.min(...hs), hi = Math.max(...hs);
    api.log(`hover over the floor ${lo.toFixed(1)}..${hi.toFixed(1)}, eye ${samples[0].eye.toFixed(1)} over the body`);
    want(samples.every((s) => s.h >= 28 - 3 - 2 && s.h <= 28 + 3 + 2 || s.capped), `hovers at 28 +- 3: ${lo.toFixed(1)}..${hi.toFixed(1)}`);
    want(hi - lo > 1.5, 'it bobs');
    want(samples.every((s) => Math.abs(s.eye - 32) < 1.5 || s.capped), "the eye sits 32 over the body (the view is set before the tic's move: within 1.5)");
    moved = { x: z.mo.x, y: z.mo.y };
    push = { buttons: IN.FORWARD, yaw: z.mo.angle, pitch: 0, until: api.time + 1 };
  }],
  [13.2, (api) => {
    const z = soul(api);
    const d = Math.hypot(z.mo.x - moved.x, z.mo.y - moved.y);
    want(d > 60, `walking moves the floating body: ${d.toFixed(0)} units in 1 s`);
  }],
  [14.5, (api) => {
    const z = soul(api);
    const v = Math.hypot(z.mo.momx, z.mo.momy);
    want(v < 1, `it comes to a stop without input: speed ${v.toFixed(2)}`);
    dashTop = -1e9;
    z.zcd = 0;
    push = { buttons: IN.ATTACK2, yaw: z.mo.angle, pitch: -35, until: api.time + 0.15 };   // look up and dash
  }],
  [15.2, (api) => {
    const z = soul(api);
    want(dashTop > 28 + 3 + 6, `the dash aimed up lifted it: ${dashTop.toFixed(1)} over the floor at most`);
  }],
  [18, (api) => {
    const z = soul(api);
    const h = z.mo.z - z.mo.floorz, cap = z.mo.ceilingz - z.mo.height - z.mo.floorz;
    want((h >= 23 && h <= 33) || Math.abs(h - cap) < 1, `back at its hover height after the dash: ${h.toFixed(1)}`);
    // 4.3: a big hit on T human 0
    const p = pe(api, 0).player;
    p.damagecount = 100; p.bonuscount = 0; p.powers[1] = 0;
  }],
  [18.1, (api) => { const f = flash(api, 0); want(f === 'red3', 'a big hit shows red3 at most: ' + f); }],
  [19.2, (api) => { const f = flash(api, 0); want(f === null || f === 'invul', `the red is gone within a second (the scenario's god mode shows the invulnerability tint) (Doom's count still ${pe(api, 0).player.damagecount}): ` + f); }],
  [19.5, (api) => { pe(api, 0).player.bonuscount = 10; }],
  [19.55, (api) => { const f = flash(api, 0); want(/^gold/.test(f || ''), 'a pickup still shows gold: ' + f); }],
  [20, (api) => { const p = pe(api, 0).player; p.bonuscount = 0; p.damagecount = 0; p.powers[1] = 1; }],
  [20.1, (api) => { const f = flash(api, 0); want(f === 'red2', 'berserk shows its own red (red2 at the start): ' + f); }],
]);
export default {
  setup(api) { for (const s of [0, 1, 2, 3]) api.manual.add(s); },
  tick(api) {
    god(api);
    const z = soul(api);
    if (z && z.mo && z.playerstate === 'live' && z.zclass === 'LOSTSOUL') {
      const cap = z.mo.ceilingz - z.mo.height - z.mo.floorz < 28 + 4;
      if (api.time >= 10.5 && api.time < 12) samples.push({ h: z.mo.z - z.mo.floorz, eye: z.viewz - z.mo.z, capped: cap });
      dashTop = Math.max(dashTop, z.mo.z - z.mo.floorz);
      z.powers[0] = 1 << 20;
    }
    if (push && api.time < push.until) { const c = api.ctrl(1); if (c && c.pawn) { c.pawn.buttons = push.buttons; c.pawn.eye = { pitch: push.pitch, yaw: push.yaw, roll: 0 }; } }
    steps(api); invariants(api, probs);
  },
  check: () => [...probs],
};
