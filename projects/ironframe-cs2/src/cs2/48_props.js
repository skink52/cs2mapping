// =====================================================================================================================
// IRONFRAME CS2 adapter: destructible street props (core 88_props.js).
//
// The map holds one prop_dynamic_override named `ifr_car` per entry of arena.cars (the generator / patch writes both; the
// copies of an arena have their own entities under the same name). Each entity is matched to its entry by position, in
// every arena copy, the first time it is needed. arena.cars entry: [x, y, z, radius, big, yaw, pitch, roll, 'r g b'].
//   {t:'prop', how:'boom'}   the body turns to a burnt wreck (dark, slumped to one side); the explosion itself (flash, sound,
//                            shake) is the core's own 'explode' event a tick later; smoke stands over it while it burns,
//                            with sparks now and then
//   {t:'prop', how:'crush'}  a crunch, the body pressed into the ground, dark
//   {t:'prop_out'}           the smoke stops by itself (it was started for the burn time)
//   {t:'props_reset'}        every body back to its place and colour (round start)
// A map without ifr_car entities: nothing happens here (the core still counts the props; they are just not drawn changed).
// =====================================================================================================================
/** @type {Map<string, {ent:any, pos:any, ang:any, tint:string, dead:boolean, sparkAt:number, until:number}>|null} */
let carEnts = null;
const carKey = (x, y, z) => Math.round(x / 16) + '_' + Math.round(y / 16) + '_' + Math.round(z / 32);
function carsBind() {
  carEnts = new Map();
  const ents = ifrFindAll('ifr_car'); if (!ents.length) return;
  const at = new Map();
  for (const e of ents) { const o = e.GetAbsOrigin(); at.set(carKey(o.x, o.y, o.z), e); }
  let n = 0, total = 0;
  for (const A of game.list) {
    for (const c of (A.arena && A.arena.cars) || []) {
      total++;
      let e = at.get(carKey(c[0], c[1], c[2]));
      if (!e) for (let dx = -16; dx <= 16 && !e; dx += 16) for (let dy = -16; dy <= 16 && !e; dy += 16) for (let dz = -32; dz <= 32 && !e; dz += 32) e = at.get(carKey(c[0] + dx, c[1] + dy, c[2] + dz));
      if (!e) continue;
      carEnts.set(carKey(c[0], c[1], c[2]), { ent: e, pos: v3(c[0], c[1], c[2]), ang: { pitch: c[6] || 0, yaw: c[5] || 0, roll: c[7] || 0 }, tint: c[8] || '255 255 255', dead: false, sparkAt: 0, until: 0 });
      n++;
    }
  }
  log('destructible props: ' + n + ' of ' + total + ' entries have their ifr_car entity (' + ents.length + ' in the map)');
}
function carOf(pos) { if (!carEnts) carsBind(); return carEnts ? carEnts.get(carKey(pos.x, pos.y, pos.z)) : undefined; }
function propsEvent(ev) {
  if (ev.t === 'prop') {
    const c = carOf(ev.pos);
    if (ev.how === 'crush') { if (nearHuman(ev.pos, 3500)) { sndAt('hit_metal', ev.pos, true); pfxBurst('spark', ev.pos, 0.5); } }
    if (!c || !live(c.ent)) return;
    c.dead = true;
    guard('prop wreck', () => {
      const s = ((ev.id * 2654435761) >>> 0) / 4294967296;          // a steady pseudo-random per prop: which way it slumps
      if (ev.how === 'crush') {
        ifrFire(c.ent, 'Color', '74 70 66');
        c.ent.Teleport({ position: v3(c.pos.x, c.pos.y, c.pos.z - (ev.big ? 30 : 17)), angles: { pitch: c.ang.pitch + (s - 0.5) * 8, yaw: c.ang.yaw, roll: c.ang.roll + (s > 0.5 ? 7 : -7) } });
      } else {
        ifrFire(c.ent, 'Color', '36 33 31');
        c.ent.Teleport({ position: v3(c.pos.x, c.pos.y, c.pos.z - 5), angles: { pitch: c.ang.pitch + (s - 0.5) * 10, yaw: c.ang.yaw + (s - 0.5) * 24, roll: c.ang.roll + (s > 0.5 ? 9 : -9) } });
        c.until = gameTime() + 14; c.sparkAt = gameTime() + 2.5;
        pfxBurst('trail', v3(c.pos.x, c.pos.y, c.pos.z + (ev.big ? 70 : 34)), 14);       // the smoke column of the burning wreck
      }
    });
  } else if (ev.t === 'props_reset') {
    if (!carEnts) return;
    for (const c of carEnts.values()) {
      if (!c.dead || !live(c.ent)) continue;
      c.dead = false; c.until = 0;
      guard('prop reset', () => { ifrFire(c.ent, 'Color', c.tint); c.ent.Teleport({ position: c.pos, angles: c.ang }); });
    }
  }
}
// sparks off the burning wrecks, a few a second at most over the whole map
function propsTick(now) {
  if (!carEnts || (ifrTickNo & 15) !== 0) return;
  for (const c of carEnts.values()) {
    if (!c.dead || now >= c.until || now < c.sparkAt) continue;
    c.sparkAt = now + 2 + Math.random() * 3;
    pfxBurst('spark', v3(c.pos.x, c.pos.y, c.pos.z + 30), 0.4);
  }
}
