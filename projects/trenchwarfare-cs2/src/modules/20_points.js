// 20_points: named map points (CONTRACT.md "Entities"), read once per round

// named map points (cached per round, map entities are re-created every round)
let points = null;
let parkCarry = null;        // after a script reload: name -> where each aircraft (and its propeller) parks; the entities may be mid-air
function findList(prefix, max) {
  const out = [];
  for (let i = 1; i <= max; i++) { const e = byName(prefix + i); if (e) out.push(e); }
  return out;
}
function loadPoints() {
  points = { trench: {}, heal: {}, plane: {}, pit: {}, seatA: {}, seatB: {}, aircraft: {}, locks: {}, mortar: {} };
  for (const u of CONFIG.UNLOCKS) {
    points.locks[u.name] = [];
    for (const e of Entities.FindByName(u.name)) { try { if (e.IsValid()) points.locks[u.name].push(e.GetAbsOrigin()); } catch (err) {} }
  }
  for (const team of [T, CT]) {
    const tg = tagOf(team);
    points.trench[team] = findList("trench_" + tg + "_", 64).map(e => ({ pos: e.GetAbsOrigin(), ang: e.GetAbsAngles(), used: 0 }));
    points.heal[team] = findList("heal_" + tg + "_", 16).map(e => e.GetAbsOrigin());
    points.plane[team] = findList("plane_" + tg + "_", 16).map(e => ({ pos: e.GetAbsOrigin(), ang: e.GetAbsAngles() }));
    points.aircraft[team] = findList("tw_plane_" + tg + "_", 16).map(e => {
      const n = e.GetEntityName().slice("tw_plane_".length), park = e.GetAbsOrigin();
      const ent = (nm) => byName(nm);
      return { ent: e, park, parkAng: e.GetAbsAngles(), pilot: -1, void: v3(park.x, park.y, -3600), ti: 0, si: 0,
               bombEnts: [1, 2].map(k => ent("tw_bomb_" + n + "_" + k)).filter(x => x),
               tracerEnts: [1, 2, 3, 4, 5, 6].map(k => ent("tw_tracer_" + n + "_" + k)).filter(x => x),
               bsight: ent("tw_bombsight_" + n), gsight: ent("tw_gunsight_" + n), spin: 0,
               prop: ent("tw_prop_" + n), hub: undefined };
    });
    points.pit[team] = []; points.seatA[team] = []; points.seatB[team] = []; points.mortar[team] = [];
    for (let k = 1; k <= CONFIG.CREWS; k++) {
      const tube = byName("mortar_" + tg + "_" + k);   // the mortar prop_dynamic (fire animation); prop_static today (CONTRACT "Known missing")
      points.mortar[team].push(tube);
      const pit = byName("mortarpit_" + tg + "_" + k) || tube;
      const a = byName("mortarcrew_" + tg + "_" + k + "_a");
      const b = byName("mortarcrew_" + tg + "_" + k + "_b");
      points.pit[team].push(pit ? pit.GetAbsOrigin() : undefined);
      points.seatA[team].push(a ? { pos: a.GetAbsOrigin(), ang: a.GetAbsAngles() } : undefined);
      points.seatB[team].push(b ? { pos: b.GetAbsOrigin(), ang: b.GetAbsAngles() } : undefined);
    }
  }
  const n = (o) => o[T].length + "/" + o[CT].length;
  for (const team of [T, CT]) for (const a of points.aircraft[team]) {
    const c = parkCarry && parkCarry[a.ent.GetEntityName()];
    if (c) {                                   // reloaded mid-round: the old script's flights are gone, so every aircraft goes home
      a.park = c.park; a.parkAng = c.parkAng; a.void = v3(c.park.x, c.park.y, -3600);
      try { a.ent.Teleport({ position: a.park, angles: a.parkAng, velocity: v3(0, 0, 0) }); } catch (e) {}
      for (const e of [...a.bombEnts, ...a.tracerEnts, a.bsight, a.gsight]) park(a, e);
    }
    if (!a.prop) continue;
    if (c && c.hub) { a.hub = c.hub; a.propParkAng = c.propParkAng; placeProp(a); continue; }
    const w = a.prop.GetAbsOrigin(), y = a.parkAng.yaw * Math.PI / 180, dx = w.x - a.park.x, dy = w.y - a.park.y;
    a.hub = v3(dx * Math.cos(y) + dy * Math.sin(y), -dx * Math.sin(y) + dy * Math.cos(y), w.z - a.park.z);
    a.propParkAng = a.prop.GetAbsAngles();
  }
  parkCarry = null;
  Console.Log("[tw] points: trench " + n(points.trench) + ", heal " + n(points.heal) + ", plane spawns " + n(points.plane) + ", aircraft " + n(points.aircraft));
}
// what a script reload must carry: where each aircraft parks (read at round start, when they all stand on the field)
function parkMemo() {
  const out = {};
  if (points) for (const team of [T, CT]) for (const a of points.aircraft[team] || []) {
    try { out[a.ent.GetEntityName()] = { park: a.park, parkAng: a.parkAng, hub: a.hub, propParkAng: a.propParkAng }; } catch (e) {}
  }
  return out;
}
// the propeller on its parked aircraft
function placeProp(ac) {
  if (!ac.prop || !ac.hub) return;
  const y = ac.parkAng.yaw * Math.PI / 180, h = ac.hub;
  try { ac.prop.Teleport({ position: v3(ac.park.x + h.x * Math.cos(y) - h.y * Math.sin(y), ac.park.y + h.x * Math.sin(y) + h.y * Math.cos(y), ac.park.z + h.z),
                           angles: ac.propParkAng, velocity: v3(0, 0, 0) }); } catch (e) {}
}
