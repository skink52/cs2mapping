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
