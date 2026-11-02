// ===================================================================================
// CS2 adapter, part 2: players, classes and abilities (dash, dome, surge), the damage gate.
// ===================================================================================
const PL = new Map();   // slot -> player record

function newPlayer(slot, ctrl) {
  return { slot, ctrl, pawn: undefined, name: '', cls: CONFIG.CLASS_DEFAULT, cdUntil: 0, activeUntil: 0,
           dome: null,                       // { pos, until, pawnSlot }
           chrono: null,                     // { pos, yaw, until, saved }
           prevUse: false, prevReload: false, prevF: false, exitSince: 0, lastRoom: -1, lastPos: { x: 0, y: 0, z: 0 },
           meleeKills: 0, alive: false, pendingSave: false, immuneUntil: 0, roomId: -1, hud: new Map(), msg: '', msgSub: '', msgUntil: 0 };
}

function playerFor(ctrl) {
  const slot = ctrl.GetPlayerSlot();
  let p = PL.get(slot);
  if (!p || p.ctrl !== ctrl) { p = newPlayer(slot, ctrl); PL.set(slot, p); }
  try { p.name = ctrl.GetPlayerName(); } catch (e) { /* bots mid-join */ }
  return p;
}

function refreshPawns() {
  for (const p of PL.values()) {
    try {
      p.pawn = p.ctrl.IsValid() ? p.ctrl.GetPlayerPawn() : undefined;
      p.alive = !!(p.pawn && p.pawn.IsValid() && p.pawn.IsAlive());
      if (p.alive) { const o = p.pawn.GetAbsOrigin(); p.lastPos.x = o.x; p.lastPos.y = o.y; p.lastPos.z = o.z; }
    } catch (e) { p.pawn = undefined; p.alive = false; }
  }
}

function setClass(p, key) {
  if (!CLASSES[key]) return false;
  p.cls = key; p.cdUntil = 0; p.activeUntil = 0; p.dome = null; p.chrono = null;
  return true;
}

// ---------------------------------------------------------------- abilities (edge detection every tick: 20 Hz polling missed taps)
function pressedEdge(p, input, field) {
  const now = p.pawn.IsInputPressed(input);
  const edge = now && !p[field]; p[field] = now; return edge;
}

function abilityTick(p, G) {
  if (!p.alive) return;
  const pawn = p.pawn;
  const useEdge = pressedEdge(p, CSInputs.USE, 'prevUse');
  const reloadEdge = pressedEdge(p, CSInputs.RELOAD, 'prevReload');
  const fEdge = pressedEdge(p, CSInputs.LOOK_AT_WEAPON, 'prevF');
  const ready = E.now >= p.cdUntil;
  if (p.cls === 'ninja' && useEdge && pawn.IsInputPressed(CSInputs.DUCK) && ready) ninjaDash(p, G);
  else if (p.cls === 'monk' && reloadEdge && ready) {
    const w = pawn.GetActiveWeapon();
    let clip = 1; try { clip = w ? w.GetClipAmmo() : 1; } catch (e) { clip = 1; }
    if (clip <= 0) monkDome(p);
  } else if (p.cls === 'chrono' && fEdge && ready) chronoSurge(p);
  // running effects
  if (p.chrono) {
    if (E.now > p.chrono.until) { p.chrono = null; }
    else chronoSpeed(p);
  }
  if (p.dome && E.now > p.dome.until) { if (p.dome.marker) poolGive(p.dome.marker); sfx('aegis_down', p.dome.pos); p.dome = null; }
}

function ninjaDash(p, G) {
  const pawn = p.pawn;
  const eye = pawn.GetEyePosition(); const dir = V.fromAngles(pawn.GetEyeAngles());
  const from = pawn.GetAbsOrigin();
  const want = V.add(from, V.mul(dir, CONFIG.NINJA_DASH));
  let end = want;
  try {
    const tr = Instance.TracePlayer({ start: from, end: want, player: pawn });
    end = tr.end;
    if (tr.didHit) end = V.add(end, V.mul(dir, -4));
  } catch (e) { /* TracePlayer missing: dash blind, clamped to the room */ }
  // strike everything the path crosses
  const a = eye, b = V.add(eye, V.sub(end, from));
  let hits = 0;
  for (const en of G.enemiesNear(from, CONFIG.NINJA_DASH + 64)) {
    if (V.segDist(en.pos, a, b) < en.kind.radius + 24) { G.hurtEnemy(en, CONFIG.NINJA_STRIKE, p, true); hits++; }
  }
  if (G.match && G.match.phase === PHASE.SHOWDOWN) {
    for (const q of PL.values()) {
      if (q === p || !q.alive || G.sameSquad(p, q)) continue;
      const o = q.pawn.GetAbsOrigin(); o.z += 40;
      if (V.segDist(o, a, b) < 48) { q.pawn.TakeDamage({ damage: CONFIG.NINJA_STRIKE, attacker: pawn, inflictor: pawn, damageTypes: CSDamageTypes.SLASH }); hits++; }
    }
  }
  pawn.Teleport({ position: end, velocity: V.mul(dir, 200) });
  p.cdUntil = E.now + CONFIG.NINJA_DASH_CD; p.activeUntil = E.now + 0.3;
  G.fx.trail(from, end, CLASSES.ninja.color); sfx('dash', from);
}

function monkDome(p) {
  const o = p.pawn.GetAbsOrigin();
  const marker = poolTake(FXM.dome, { x: o.x, y: o.y, z: o.z + 48 }, 0, 1, { r: 255, g: 200, b: 90, a: 255 });
  p.dome = { pos: { x: o.x, y: o.y, z: o.z + 48 }, until: E.now + CONFIG.MONK_DOME_T, marker };
  p.cdUntil = E.now + CONFIG.MONK_DOME_CD; sfx('aegis_up', o);
}
function insideDome(pos) {
  for (const q of PL.values()) if (q.dome && V.dist(pos, q.dome.pos) <= CONFIG.MONK_DOME_R) return q;
  return null;
}

function chronoSurge(p) {
  const o = p.pawn.GetAbsOrigin();
  p.chrono = { pos: { x: o.x, y: o.y, z: o.z }, yaw: p.pawn.GetEyeAngles().yaw, until: E.now + CONFIG.CHRONO_T, saved: false };
  p.cdUntil = E.now + CONFIG.CHRONO_CD; sfx('rewind_arm', o);
  try { const w = p.pawn.GetActiveWeapon(); if (w) w.SetClipAmmo(w.GetData().GetMaxClipAmmo()); } catch (e) { /* no weapon */ }
}
// +40% ground speed: the player's own movement applies friction 5.2/64 to what we set before it moves
const FRICTION_COMP = 1 / (1 - 5.2 / 64);
function chronoSpeed(p) {
  const pawn = p.pawn;
  if (!pawn.GetGroundEntity()) return;
  let fx = 0, fy = 0;
  if (pawn.IsInputPressed(CSInputs.FORWARD)) fx += 1;
  if (pawn.IsInputPressed(CSInputs.BACK)) fx -= 1;
  if (pawn.IsInputPressed(CSInputs.LEFT)) fy += 1;
  if (pawn.IsInputPressed(CSInputs.RIGHT)) fy -= 1;
  if (!fx && !fy) return;
  const yaw = pawn.GetEyeAngles().yaw * Math.PI / 180;
  const l = Math.hypot(fx, fy); fx /= l; fy /= l;
  const wx = Math.cos(yaw) * fx - Math.sin(yaw) * fy, wy = Math.sin(yaw) * fx + Math.cos(yaw) * fy;
  const speed = 250 * (pawn.IsInputPressed(CSInputs.WALK) ? 0.52 : 1) * CONFIG.CHRONO_SPEED * FRICTION_COMP;
  const v = pawn.GetAbsVelocity();
  pawn.Teleport({ velocity: { x: wx * speed, y: wy * speed, z: v.z } });
}

// ---------------------------------------------------------------- damage gate
function installDamageGate(G) {
  Instance.OnModifyPlayerDamage((ev) => {
    const victim = ev.player; const vs = slotOf(victim); let v = PL.get(vs);
    if (!v && vs >= 0) { try { const c = victim.GetPlayerController(); if (c) v = playerFor(c); } catch (e) { v = undefined; } }   // a slot that changed hands silently
    const apawn = toPawn(ev.attacker); const as = apawn ? slotOf(apawn) : -1; let a = as >= 0 ? PL.get(as) : undefined;
    if (!a && apawn && as >= 0) { try { const c = apawn.GetPlayerController(); if (c) a = playerFor(c); } catch (e) { a = undefined; } }
    let damage = ev.damage; let flags = ev.damageFlags;
    if (!G.match || G.match.phase === PHASE.LOBBY || G.match.phase === PHASE.END) {
      if (a && a !== v) return { abort: true };            // no fighting in the lobby
    } else if (a && a !== v) {
      if (G.sameSquad(a, v)) return { abort: true };
      if (G.match.phase !== PHASE.SHOWDOWN) return { abort: true };   // squads can't reach each other in the vaults; belt and braces
      damage *= CONFIG.PVP_DAMAGE_SCALE;
    }
    // the dome: hits on anyone inside from anyone outside are cut, and the monk's armor grows by what it stopped
    if (v) {
      const dome = insideDome(victim.GetAbsOrigin());
      if (dome) {
        const from = apawn ? apawn.GetAbsOrigin() : (ev.inflictor ? ev.inflictor.GetAbsOrigin() : null);
        if (!from || V.dist(from, dome.dome.pos) > CONFIG.MONK_DOME_R) {
          const cut = damage * CONFIG.MONK_DOME_CUT; damage -= cut;
          if (dome.alive) { try { dome.pawn.SetArmor(Math.min(100, Math.round(dome.pawn.GetArmor() + cut * CONFIG.MONK_ARMOR_GAIN))); } catch (e) { /* */ } }
        }
      }
      // chrono save: a lethal hit during the surge is held off; next tick the raider snaps back on 50 hp
      if (v.chrono && !v.chrono.saved && damage >= victim.GetHealth() - 1) {
        v.chrono.saved = true; v.pendingSave = true;
        return { damage: Math.max(1, Math.floor(damage)), damageFlags: flags | CSDamageFlags.PREVENT_DEATH };
      }
    }
    if (damage !== ev.damage) return { damage: Math.max(0.5, damage), damageFlags: flags };
    return undefined;
  });
}
function chronoSaveTick(p) {
  if (!p.pendingSave) return;
  p.pendingSave = false;
  if (!p.alive || !p.chrono) return;
  p.pawn.SetHealth(CONFIG.CHRONO_SAVE_HP);
  sfx('rewind_snap', p.lastPos);
  teleportPawn(p.pawn, p.chrono.pos, p.chrono.yaw); sfx('rewind_snap', p.chrono.pos);
  p.chrono = null;
}
