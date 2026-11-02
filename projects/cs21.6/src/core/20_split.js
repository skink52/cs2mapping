// ---------------------------------------------------------------- which maps are played, and who plays where

// how many maps run at once for this many players on T + CT
function mapCountFor(nT, nCT, cfg) {
  const n = nT + nCT;
  let k = 1;
  for (const [min, maps] of cfg.MAPS_BY_PLAYERS) if (n >= min) k = maps;
  k = Math.min(k, cfg.MAP_ORDER.length, Math.max(1, Math.min(nT, nCT)));
  return Math.max(1, k);
}

// the k active maps, starting at the rotation index
function activeMaps(rotation, k, order) {
  const out = [];
  for (let i = 0; i < k; i++) out.push(order[(rotation + i) % order.length]);
  return out;
}

// split one team over the active maps. players: [{ slot, prev, want }]; returns Map slot -> map key.
// Targets differ by at most one; the maps listed first get the extra players (both teams use the same order, so
// a map that gets an extra T also tends to get the extra CT). Players stay where they were when they can,
// then go where they asked to, then fill whatever has room.
function splitTeam(players, maps) {
  const k = maps.length, n = players.length;
  const target = new Map(maps.map((m, i) => [m, Math.floor(n / k) + (i < n % k ? 1 : 0)]));
  const count = new Map(maps.map((m) => [m, 0]));
  const out = new Map();
  const place = (p, m) => { out.set(p.slot, m); count.set(m, count.get(m) + 1); };
  const rest = [];
  for (const p of players) {
    if (p.want && target.has(p.want) && count.get(p.want) < target.get(p.want)) place(p, p.want);
    else rest.push(p);
  }
  const rest2 = [];
  for (const p of rest) {
    if (p.prev && target.has(p.prev) && count.get(p.prev) < target.get(p.prev)) place(p, p.prev);
    else rest2.push(p);
  }
  for (const p of rest2) {
    let best = null;
    for (const m of maps) {
      const room = target.get(m) - count.get(m);
      if (room > 0 && (best === null || room > target.get(best) - count.get(best))) best = m;
    }
    place(p, best || maps[0]);
  }
  return out;
}

// everyone: [{ slot, team, prev, want }] -> Map slot -> map key
function assignMaps(everyone, maps) {
  const out = new Map();
  for (const team of [TEAM_T, TEAM_CT]) {
    const ps = everyone.filter((p) => p.team === team).sort((a, b) => a.slot - b.slot);
    for (const [s, m] of splitTeam(ps, maps)) out.set(s, m);
  }
  return out;
}

// a player joining mid-round (or in warmup): the active map with the fewest of their team
function lateMap(team, maps, counts) {
  let best = maps[0], bn = Infinity;
  for (const m of maps) {
    const c = (counts.get(m + ':' + team) || 0);
    if (c < bn) { bn = c; best = m; }
  }
  return best;
}
