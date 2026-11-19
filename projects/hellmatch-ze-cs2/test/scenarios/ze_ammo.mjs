// ammo and upgrades, surges (Round 3). 4 humans + 4 bots, 40 s, zemap=map01 (any level works).
//   AMMO_FLOOR: a human out of bullets on the fist gets bullets back (1 a second) and the pistol up again
//   a completed hold: the stage's give (or the default ladder) and its resupply (or HOLD_RESUPPLY): new weapons, more
//   ammo, health back up, bottom HUD line "UPGRADE: ..." then "RESUPPLY"
//   the next hold's start: an automatic surge, centre "HERE THEY COME", more AI at once
//   AI deaths drop ammo (Doom dropped items, MF_DROPPED, the kinds the humans use); a drop is picked up by walking over it
//   and goes after DROP_SECONDS when nobody does
import { rm, pe, timeline, checker, god } from './_lib.mjs';
const { probs, want } = checker();
const MF_DROPPED = 0x20000;
const arenaT = (api) => rm(api).arenas.find((a) => a.zeSide === 2);
const live = (a) => [...a.mobjs].filter((m) => m.info.kind === 'monster' && m.health > 0 && !m.boss);
let before = null, ladder = null, sawUpgrade = '', sawResupply = false, sawSurge = false, aiAtStart = 0, aiPeak = 0, surgeFrom = 0;
let drops = [], expired = null, picked = null, pickAmmo = 0;
const steps = timeline([
  [5, (api) => {
    const p = pe(api, 0).player;
    p.ammo[0] = 0; p.readyweapon = 0; p.pendingweapon = 10;   // AM_CLIP, WP_FIST, WP_NOCHANGE
    api.log('human 0: no bullets, on the fist');
  }],
  [7.5, (api) => {
    const p = pe(api, 0).player;
    want(p.ammo[0] >= 1, 'AMMO_FLOOR: bullets back within 2.5 s: ' + p.ammo[0]);
    want(p.readyweapon === 1 || p.pendingweapon === 1, `AMMO_FLOOR: the pistol comes back up (ready ${p.readyweapon} pending ${p.pendingweapon})`);
  }],
  [8, (api) => {
    const a = arenaT(api), ze = a.ze, s = ze.active(), p = pe(api, 0).player;
    want(!!s && s.total > 0 && !s.d.escape, 'T arena in a hold at 8 s');
    if (!s) return;
    p.health = 40; p.mo.health = 40;
    before = { ammo: p.ammo.slice(), owned: p.weaponowned.slice(), health: p.health };
    const give = (s.d.on_done || []).find((x) => x && x.give);
    ladder = give ? give.give : ze.ladder ? ((ze.ladder.find((e) => e.on === 'done:' + (s.i + 1)) || {}).give || []) : [];
    a.run(() => ze.finishStage(s));
    api.log(`T arena hold "${s.name}" completed; expected weapons ${JSON.stringify(ladder)}`);
    aiAtStart = live(a).length; surgeFrom = api.time;
  }],
  [8.3, (api) => {
    const p = pe(api, 0).player;
    const W = { pistol: 1, shotgun: 2, chaingun: 3, rocket: 4, plasma: 5, bfg: 6, chainsaw: 7, ssg: 8 };
    for (const id of ladder) want(p.weaponowned[W[id]], 'given ' + id);
    want(p.health > before.health, `resupply health ${before.health} -> ${p.health}`);
    want(p.ammo[1] > before.ammo[1] || p.ammo[1] === p.maxammo[1], `resupply shells ${before.ammo[1]} -> ${p.ammo[1]}`);
  }],
  [20, (api) => {
    // drops: AI killed by human 0 until a few items fell
    const a = arenaT(api), k = pe(api, 0).player;
    let n = 0;
    for (const m of live(a)) {
      if (n++ > 40 || drops.length >= 3) break;
      const had = a.ze.drops.length;
      a.run(() => api.ctx.damageMobj(m, k.mo, k.mo, 10000));
      if (a.ze.drops.length > had) drops.push(a.ze.drops[a.ze.drops.length - 1]);
    }
    want(drops.length >= 1, `AI deaths drop ammo: ${drops.length} drops from ${n} kills`);
    for (const d of drops) {
      want((d.mo.flags & MF_DROPPED) !== 0, 'a drop is a Doom dropped item');
      want(['CLIP', 'SHELL', 'CELL', 'ROCKETAMMO'].includes(d.mo.info.key), 'a drop is ammo: ' + d.mo.info.key);
    }
    if (drops.length) { expired = drops[0]; expired.until = a.leveltime + 5; }
    if (drops.length > 1) {
      picked = drops[1];
      const p = pe(api, 0).player;
      const am = { CLIP: 0, SHELL: 1, CELL: 2, ROCKETAMMO: 3 }[picked.mo.info.key];
      p.ammo[am] = 0; pickAmmo = am;
      a.run(() => { api.ctx.teleportMove(p.mo, picked.mo.x, picked.mo.y); p.mo.z = p.mo.floorz; });
    }
  }],
  [22.5, (api) => {
    if (expired) want(expired.mo.removed, 'a drop nobody took goes after its time');
    if (picked) { const p = pe(api, 0).player; want(picked.mo.removed && p.ammo[pickAmmo] > 0, `drop picked up: removed ${picked.mo.removed}, ammo ${p.ammo[pickAmmo]}`); }
  }],
]);
export default {
  setup(api) { for (const s of [0, 1, 2, 3]) api.manual.add(s); },
  tick(api) {
    god(api); steps(api);
    if (before && api.time < 16) {
      const bottom = api.hudLine(0, 'fdm_spec', 32), centre = api.hudLine(0, 'fdm_ctr', 24);
      if (bottom.startsWith('UPGRADE: ')) sawUpgrade = bottom;
      if (bottom === 'RESUPPLY') sawResupply = true;
      if (centre === 'HERE THEY COME') sawSurge = true;
      const a = arenaT(api);
      if (a) aiPeak = Math.max(aiPeak, live(a).length);
    }
  },
  check(api) {
    if (ladder && ladder.length) want(sawUpgrade === 'UPGRADE: ' + ladder.join(' + ').toUpperCase(), `HUD upgrade line "${sawUpgrade}" (want "UPGRADE: ${ladder.join(' + ').toUpperCase()}")`);
    want(sawResupply, 'HUD line RESUPPLY shown after the hold');
    want(sawSurge, 'HERE THEY COME shown after the next hold started');
    const d = arenaT(api).director, full = aiPeak + d.zombiePlayers() >= d.capN - 2;
    want(aiPeak > aiAtStart || full, `the surge brought AI in at once (or the horde was at the cap ${d.capN}): ${aiAtStart} -> ${aiPeak}`);
    api.log(`upgrade "${sawUpgrade}", AI ${aiAtStart} -> ${aiPeak} after the surge, ${drops.length} drops`);
    return [...probs];
  },
};
