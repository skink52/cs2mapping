// helpers for the ZE mock scenarios (node test/mock_cs2.mjs <humans> <bots> <seconds> seed=N,scenario=test/scenarios/<x>.mjs)
export const rm = (api) => api.dbg().rm;
export const pe = (api, slot) => rm(api).person(slot);
export const MF_PICKUP = 0x800;

// kill a person's Doom player now; killerSlot: a player in the same arena credited with it (null = the world)
export function killDoom(api, slot, killerSlot) {
  const p = pe(api, slot).player, a = p.arena;
  const k = killerSlot === undefined || killerSlot === null ? null : pe(api, killerSlot).player;
  a.run(() => api.ctx.damageMobj(p.mo, k ? k.mo : null, k ? k.mo : null, 10000));
}
export const liveZombie = (api, slot) => { const x = pe(api, slot); return !!x && x.zeRole === 'zombie' && !!x.player && x.player.playerstate === 'live' && !!x.player.mo; };

// steps: [[time, fn], ...]: each fn runs once, on the first tick at or after its time
export function timeline(steps) {
  const done = new Set();
  return (api) => { for (const [t, fn] of steps) if (!done.has(t) && api.time >= t) { done.add(t); fn(api); } };
}

// every tick: monsters never target zombie players, zombie bodies never pick things up
export function invariants(api, probs) {
  for (const a of rm(api).arenas) {
    for (const p of a.players.values()) if (p.zclass && p.mo && !p.mo.removed && (p.mo.flags & MF_PICKUP)) probs.add('zombie body with MF_PICKUP: ' + p.name);
    for (const m of a.mobjs) if (m.info.kind === 'monster' && m.health > 0 && m.target && m.target.player && m.target.player.zclass) probs.add(`a ${m.info.key} targets zombie player ${m.target.player.name}`);
  }
}

export function checker() {
  const probs = new Set();
  return { probs, want: (ok, m) => { if (!ok) probs.add(m); } };
}

// the scripted players only die when a scenario kills them (killDoom uses 10000 damage, which invulnerability lets through)
export function god(api) {
  for (const s of api.manual) { const x = pe(api, s); if (x && x.player) x.player.powers[0] = 1 << 20; }
}

// Round 4: the round without the finale level record (an escape wins at once, as before): call in setup
export function noFinale(api) {
  const L = api.ctx.__LEVELS;
  for (let i = L.length - 1; i >= 0; i--) if (L[i].finale) L.splice(i, 1);
}

// a side's own ZE arena (2 T, 3 CT) and the finale arena (Round 4)
export const arenaOf = (api, side) => rm(api).arenas.find((a) => a.zeSide === side && !a.zeFinale);
export const finaleArena = (api) => rm(api).arenas.find((a) => a.zeFinale);
// put a live player at (x, y) in their arena, or the nearest free spot around it
export function tpInto(api, a, p, x, y) {
  for (const [dx, dy] of [[0, 0], [40, 0], [-40, 0], [0, 40], [0, -40], [64, 64], [-64, -64], [96, 0], [0, 96], [-96, 0], [0, -96]]) {
    let ok = false;
    a.run(() => { ok = api.ctx.teleportMove(p.mo, x + dx, y + dy); });
    if (ok) { p.mo.z = p.mo.floorz; p.mo.momx = p.mo.momy = p.mo.momz = 0; return true; }
  }
  return false;
}
// a side escapes now: every stage before the escape done, the escape started, the human in slot `slot` put in its zone,
// before(arena) runs just before the escape completes; the escape completed. Returns a problem string or null.
export function forceEscape(api, side, slot, before) {
  const a = arenaOf(api, side);
  if (!a) return 'no arena for side ' + side;
  const ze = a.ze, e = ze.stages.find((s) => s.d.escape);
  if (!e) return 'no escape stage in ' + a.mapId;
  a.run(() => { for (const x of ze.stages) if (x.i < e.i && x.state !== 'done') { if (x.state === 'pending') ze.startStage(x); ze.finishStage(x); } if (e.state === 'pending') ze.startStage(e); });
  const c = ze.zoneCentre(e.d.zone), p = pe(api, slot).player;
  if (!c || !p || p.playerstate !== 'live' || p.arena !== a || !tpInto(api, a, p, c.x, c.y)) return 'could not put slot ' + slot + ' into the escape zone';
  if (before) before(a);
  a.run(() => ze.finishStage(e));
  return ze.escaped > 0 ? null : 'nobody escaped';
}
// the HUD's centre line and both message lines of a player
export const hudCentre = (api, slot) => api.hudLine(slot, 'fdm_ctr', 24);
export const hudMsg = (api, slot) => (api.hudLine(slot, 'fdm_msg', 56) + ' ' + api.hudLine(slot, 'fdm_msgb', 56)).trim();
// the stats a slot got: sent plus what still waits in the script's one-second batch
export function statsOf(api, slot) {
  const o = Object.assign({}, api.mg.bySlot.get(String(slot)) || {});
  const p = api.ctx.__stats().statPending.get(slot) || {};
  for (const [k, n] of Object.entries(p)) o[k] = k.startsWith('best_') ? Math.max(o[k] || 0, n) : (o[k] || 0) + n;
  return o;
}
