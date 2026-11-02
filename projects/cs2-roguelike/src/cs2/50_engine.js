// ===================================================================================
// CS2 adapter, part 1: engine helpers, entity lookups, the prop pool, messages.
// ===================================================================================
const E = {
  now: 0, dt: 1 / 64, tick: 0,
  script: null, tpl: null, mapParams: null,
  tele: new Map(),       // name -> origin/angles of a teleport target (read once)
  pool: [], poolFree: [],
  msgs: [], msgAt: 0,
  ready: false, missing: [],
  perf: { ms: 0, max: 0, n: 0, calls: 0, lastLog: 0 },
};

function toPawn(ent) {
  if (ent instanceof CSPlayerPawn) return ent;
  if (ent instanceof CSPlayerController) return ent.GetPlayerPawn();
  return undefined;
}
function slotOf(pawn) { try { const c = pawn && pawn.GetPlayerController(); return c ? c.GetPlayerSlot() : -1; } catch (e) { return -1; } }
function sideOf(ctrl) { try { return ctrl.GetTeamNumber(); } catch (e) { return 0; } }   // 2 T, 3 CT

function findTele(name) {
  if (E.tele.has(name)) return E.tele.get(name);
  const e = Instance.FindEntityByName(name);
  if (!e) { if (!E.missing.includes(name)) E.missing.push(name); return undefined; }
  const o = e.GetAbsOrigin(); const a = e.GetAbsAngles();
  const v = { pos: { x: o.x, y: o.y, z: o.z }, yaw: a.yaw };
  E.tele.set(name, v); return v;
}

// spread a group around a point so nobody lands inside anybody (two pawns on one spot never move again)
function ringPositions(center, n, r = 56) {
  const out = [];
  if (n === 1) return [{ x: center.x, y: center.y, z: center.z }];
  for (let i = 0; i < n; i++) {
    const a = (i / n) * Math.PI * 2; const rr = n > 8 ? r * 1.8 : r;
    out.push({ x: center.x + Math.cos(a) * rr, y: center.y + Math.sin(a) * rr, z: center.z });
  }
  return out;
}

function teleportPawn(pawn, pos, yaw) {
  pawn.Teleport({ position: { x: pos.x, y: pos.y, z: pos.z + 4 }, angles: { pitch: 0, yaw, roll: 0 }, velocity: { x: 0, y: 0, z: 0 } });
  try { pawn.SetEyeAngles({ pitch: 0, yaw, roll: 0 }); } catch (e) { /* older API */ }
}

// ---------------------------------------------------------------- the prop pool (enemies, bolts, markers)
const PARK = { x: 0, y: 0, z: -4000 };   // under the lobby, in the void: never seen (pool props are non-solid and invisible when parked)
function poolInit(n) {
  if (!E.tpl || E.pool.length) return;
  let made = 0;
  for (let i = 0; i < n; i++) {
    const ents = E.tpl.ForceSpawn({ x: PARK.x + (i % 16) * 40, y: PARK.y + Math.floor(i / 16) * 40, z: PARK.z }, { pitch: 0, yaw: 0, roll: 0 });
    const ent = ents && ents.find((x) => x instanceof BaseModelEntity);
    if (!ent) break;
    try { ent.SetEntityName(`${CONFIG.TAG}_pool_${i}`); } catch (e) { /* optional */ }
    const p = { id: i, ent, used: false, model: '', pos: { x: PARK.x, y: PARK.y, z: PARK.z }, ang: { pitch: 0, yaw: 0, roll: 0 }, scale: 1, lastMove: -1, lastTele: -9 };
    E.pool.push(p); E.poolFree.push(p); made++;
  }
  Instance.Msg(`[${CONFIG.TAG}] prop pool: ${made} props`);
}
// map entities (the template's spawn group included) are re-made every CS2 round: the pool is rebuilt from scratch then
function poolRebuild(n) {
  E.pool.length = 0; E.poolFree.length = 0;
  const tpl = Instance.FindEntityByName('nt_tpl_prop'); E.tpl = tpl instanceof PointTemplate ? tpl : null;
  poolInit(n);
}
// sound anchors: their own ring of invisible props (not the pool), used round-robin; 48 anchors at 16 sounds a tick means an anchor
// is moved at most every third tick, so a short sound's source never gets the 3-Teleports-in-a-row treatment
const ANCH = { list: [], next: 0 };
function anchorsInit(n) {
  ANCH.list.length = 0; ANCH.next = 0;
  if (!E.tpl) return;
  for (let i = 0; i < n; i++) {
    const ents = E.tpl.ForceSpawn({ x: PARK.x + 800 + (i % 8) * 40, y: PARK.y + Math.floor(i / 8) * 40, z: PARK.z }, { pitch: 0, yaw: 0, roll: 0 });
    const ent = ents && ents.find((x) => x instanceof BaseModelEntity);
    if (!ent) break;
    try { ent.SetEntityName(`${CONFIG.TAG}_anchor_${i}`); } catch (e) { /* */ }
    ANCH.list.push({ id: i, ent, name: `${CONFIG.TAG}_anchor_${i}` });
  }
}
function anchorAt(pos) {
  if (!ANCH.list.length) return null;
  const a = ANCH.list[ANCH.next]; ANCH.next = (ANCH.next + 1) % ANCH.list.length;
  try { a.ent.Teleport({ position: { x: pos.x, y: pos.y, z: pos.z } }); } catch (e) { return null; }
  return a;
}
// never two Teleports on one prop in consecutive ticks (CS2 stops drawing a prop Teleported 3 ticks running): the second becomes a Move
function placeProp(p, nv) {
  if (E.tick - p.lastTele <= 1) { p.ent.Move(nv); return; }
  p.ent.Teleport(nv); p.lastTele = E.tick;
}
function poolTake(model, pos, yaw = 0, scale = 1, color) {
  const p = E.poolFree.shift();     // FIFO: a prop just parked isn't Teleported again next tick (CS2 stops drawing props Teleported 3 ticks running)
  if (!p) return null;
  p.used = true;
  try {
    if (p.model !== model) { p.ent.SetModel(model); p.model = model; }
    if (p.scale !== scale) { p.ent.SetModelScale(scale); p.scale = scale; }
    placeProp(p, { position: pos, angles: { pitch: 0, yaw, roll: 0 } });
    if (color) p.ent.SetColor(color);
  } catch (e) { Instance.Msg(`[${CONFIG.TAG}] pool take failed: ${e}`); p.used = false; E.poolFree.push(p); return null; }
  p.pos = { x: pos.x, y: pos.y, z: pos.z }; p.ang.yaw = yaw; p.lastMove = E.tick;
  return p;
}
function poolMove(p, pos, yaw) {
  if (Math.abs(pos.x - p.pos.x) + Math.abs(pos.y - p.pos.y) + Math.abs(pos.z - p.pos.z) < 0.01 && (yaw === undefined || yaw === p.ang.yaw)) return;
  if (yaw !== undefined) p.ang.yaw = yaw;
  const far = V.dist(pos, p.pos) > 400;
  p.pos = { x: pos.x, y: pos.y, z: pos.z };
  const nv = { position: p.pos, angles: { pitch: 0, yaw: p.ang.yaw, roll: 0 } };
  if (far) placeProp(p, nv); else p.ent.Move(nv);
}
function poolGive(p, park = true) {
  if (!p || !p.used) return;
  p.used = false;
  try {
    if (p.model !== NULL_MODEL) p.ent.SetColor({ r: 255, g: 255, b: 255, a: 255 });
    // an invisible anchor (null model) needs no parking: skipping the Teleport keeps the 3-Teleports-in-a-row rule safe when the pool cycles fast
    if (park && p.model !== NULL_MODEL) placeProp(p, { position: { x: PARK.x + (p.id % 16) * 40, y: PARK.y + Math.floor(p.id / 16) * 40, z: PARK.z } });
    if (p.model !== NULL_MODEL) { p.ent.SetModel(NULL_MODEL); p.model = NULL_MODEL; }
    if (p.scale !== 1) { p.ent.SetModelScale(1); p.scale = 1; }
  } catch (e) { /* entity gone after a round restart: it is re-made in init */ }
  p.pos = { x: PARK.x, y: PARK.y, z: PARK.z };
  E.poolFree.push(p);
}
const NULL_MODEL = 'models/nt/null.vmdl';

// ---------------------------------------------------------------- messages (chat until the HUD lands; paced 1 s apart, host flood limit)
function say(text) { E.msgs.push(text.replace(/[;"]/g, '')); }
function flushMsgs() {
  if (!E.msgs.length || E.now - E.msgAt < 1.0) return;
  E.msgAt = E.now;
  Instance.ServerCommand(`say [${CONFIG.TAG.toUpperCase()}] ${E.msgs.shift()}`);
}

function applyCvars() {
  if (!CONFIG.APPLY_CVARS) return;
  for (const c of ['mp_ignore_round_win_conditions 1', 'mp_teammates_are_enemies 1', 'mp_friendlyfire 1', 'mp_respawn_immunitytime 0',
                   'mp_respawn_on_death_t 1', 'mp_respawn_on_death_ct 1', 'mp_roundtime 60', 'mp_roundtime_defuse 60', 'mp_roundtime_hostage 60',
                   'mp_freezetime 3', 'mp_buy_anywhere 0', 'mp_buytime 36000', 'mp_startmoney ' + CONFIG.NANITES_START, 'mp_maxmoney 16000',
                   'mp_playercashawards 0', 'mp_teamcashawards 0', 'mp_afterroundmoney 0', 'mp_death_drop_gun 1', 'mp_force_assign_teams 1',
                   'sv_disable_teamselect_menu 1', 'mp_solid_teammates 1', 'bot_quota 0', 'mp_autokick 0', 'mp_limitteams 0', 'mp_autoteambalance 0'])
    Instance.ServerCommand(c);
}
