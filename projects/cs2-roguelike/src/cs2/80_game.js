// ===================================================================================
// CS2 adapter, part 4: the game loop. Round flow, the match's orders, exits, the showdown ring, effects, chat, init.
// ===================================================================================
const G = {
  match: null, rng: new Rng(1), roundStart: 0, started: false, ended: false, endAt: 0, ringR: 0,
  fx: null,
  sameSquad(a, b) { if (!a || !b) return false; if (!G.match) return a.ctrl && b.ctrl && sideOf(a.ctrl) === sideOf(b.ctrl); const sa = G.match.squadOf.get(a.slot), sb = G.match.squadOf.get(b.slot); return !!sa && sa === sb; },
  enemiesNear, hurtEnemy,
};

// ---------------------------------------------------------------- effects: pooled self-lit props, hard caps, dropped not spawned when the pool is dry
const FX = { live: [], cap: 48 };
G.fx = {
  trail(a, b, color) {
    const n = Math.min(6, Math.floor(V.dist(a, b) / 48));
    for (let i = 1; i <= n && FX.live.length < FX.cap; i++) {
      const t = i / (n + 1); const pos = V.add(a, V.mul(V.sub(b, a), t)); pos.z += 40;
      const p = poolTake(FXM.shard, pos, 0, 1, { r: color.r, g: color.g, b: color.b, a: 255 });
      if (p) FX.live.push({ p, until: E.now + 0.5, spin: 720 });
    }
  },
  tracer(a, b, color) {
    const n = Math.min(5, Math.floor(V.dist(a, b) / 160));
    for (let i = 1; i <= n && FX.live.length < FX.cap; i++) {
      const pos = V.add(a, V.mul(V.sub(b, a), i / (n + 1)));
      const p = poolTake(FXM.bolt, pos, V.yawTo(a, b), 0.6, { r: color.r, g: color.g, b: color.b, a: 255 });
      if (p) FX.live.push({ p, until: E.now + 0.12 });
    }
  },
  burst(pos, color) {
    for (let i = 0; i < 4 && FX.live.length < FX.cap; i++) {
      const a = (i / 4) * Math.PI * 2;
      const p = poolTake(FXM.spark, { x: pos.x + Math.cos(a) * 24, y: pos.y + Math.sin(a) * 24, z: pos.z + 40 }, 0, 1, { r: color.r, g: color.g, b: color.b, a: 255 });
      if (p) FX.live.push({ p, until: E.now + 0.35, vel: { x: Math.cos(a) * 120, y: Math.sin(a) * 120, z: 90 }, spin: 540 });
    }
  },
  tick() {
    for (let i = FX.live.length - 1; i >= 0; i--) {
      const f = FX.live[i];
      if (E.now > f.until) { poolGive(f.p); FX.live.splice(i, 1); continue; }
      if (f.vel || f.spin) poolMove(f.p, f.vel ? V.add(f.p.pos, V.mul(f.vel, E.dt)) : f.p.pos, f.spin ? (f.p.ang.yaw + f.spin * E.dt) % 360 : undefined);
    }
  },
};

// ---------------------------------------------------------------- orders from the match
function teleportSquad(members, toName) {
  const t = findTele(toName); if (!t) { Instance.Msg(`[${CONFIG.TAG}] MISSING teleport target ${toName}`); return; }
  const live = members.map((s) => PL.get(s)).filter((p) => p && p.alive);
  const spots = ringPositions(t.pos, live.length);
  live.forEach((p, i) => { teleportPawn(p.pawn, spots[i], t.yaw); p.exitSince = 0; p.immuneUntil = E.now + CONFIG.TELEPORT_IMMUNITY; });
  if (live.length) sfx('teleport', t.pos);
}
function runOrders() {
  for (const o of G.match.drain()) {
    switch (o.op) {
      case 'teleport': teleportSquad(o.members, o.to); for (const s of o.members) { const p = PL.get(s); if (p) p.roomId = o.to.startsWith('nt_room_') ? parseInt(o.to.slice(8), 10) : -1; } break;
      case 'wave': { const R = roomState(o.room); R.squad = o.squad; spawnWave(G, o.room, o.count, o.floor, o.boss); break; }
      case 'clearRoom': clearRoomEnemies(o.room); break;
      case 'openExit': { const R = roomState(o.room); R.exitOpen = true; const ex = LAYOUT.rooms[o.room].exit; R.beacon = poolTake(FXM.beacon, { x: ex[0], y: ex[1], z: 4 }, 0, 1); sfx('vault_clear', { x: ex[0], y: ex[1], z: 64 }); R.beaconSnd = sfx('beacon_loop', { x: ex[0], y: ex[1], z: 40 }, true); msgTo(G.match.squads[o.squad].members, 'VAULT CLEARED', 'stand on the amber plate to move on', 6); break; }
      case 'reward': for (const s of o.members) { const p = PL.get(s); if (p) { try { p.ctrl.AddMoneySpendableNow(o.amount); } catch (e) { /* */ } } } break;
      case 'msg': msgTo(G.match.squads[o.squad].members, o.text, '', 5); break;
      case 'msgAll': msgAll(o.text, '', 5); if (o.text.startsWith('THE BREACH')) ui('breach'); break;
      case 'ring': G.ringR = Math.max(360, 1500 - 300 * o.step); ui('ring_warn'); break;
      case 'end': endRound(o.winner, o.timeUp); break;
      default: break;
    }
  }
}

function exitTick(p) {
  if (!p.alive || p.roomId < 0 || !G.match) return;
  const R = ROOMS.get(p.roomId); if (!R || !R.exitOpen) { p.exitSince = 0; return; }
  const rm = LAYOUT.rooms[p.roomId]; const ex = rm.exit;
  const on = Math.abs(p.lastPos.x - ex[0]) < LAYOUT.pad && Math.abs(p.lastPos.y - ex[1]) < LAYOUT.pad && p.lastPos.z < 80;
  if (!on) { p.exitSince = 0; return; }
  if (!p.exitSince) p.exitSince = E.now;
  else if (E.now - p.exitSince > 1.2) { p.exitSince = 0; G.match.exitTouched(p.roomId, E.now); }
}

function ringTick() {
  if (!G.match || G.match.phase !== PHASE.SHOWDOWN || !G.ringR || E.tick % 64) return;
  const A = LAYOUT.arena;
  for (const p of PL.values()) {
    if (!p.alive || !G.match.squadOf.has(p.slot)) continue;
    if (V.dist2d(p.lastPos, { x: A.cx, y: A.cy }) > G.ringR) { try { p.pawn.TakeDamage({ damage: CONFIG.RING_DAMAGE, damageTypes: CSDamageTypes.SHOCK, damageFlags: CSDamageFlags.IGNORE_ARMOR }); } catch (e) { /* */ } }
  }
}

function endRound(winnerId, timeUp) {
  if (G.ended) return;
  G.ended = true; G.endAt = E.now + 6;
  if (winnerId === null || winnerId === undefined) { say('NO SQUAD SURVIVED THE TEMPLE.'); ui('lose'); return; }
  const s = G.match.squads[winnerId];
  let t = 0, ct = 0; for (const m of s.members) { const p = PL.get(m); if (p) { if (sideOf(p.ctrl) === 2) t++; else ct++; } }
  G.winSide = ct > t ? CSRoundEndReason.CTS_WIN : CSRoundEndReason.TERRORISTS_WIN; ui('win');
  const names = s.members.map((m) => (PL.get(m) || { name: '?' }).name).join(', ');
  say(`SQUAD ${winnerId + 1} WINS${timeUp ? ' ON TIME' : ''}: ${names}`);
}
function finishRound() {
  if (CONFIG.APPLY_CVARS) Instance.ServerCommand('mp_ignore_round_win_conditions 0');
  if (E.mapParams && G.winSide !== undefined) Instance.EntFireAtTarget({ target: E.mapParams, input: 'FireWinCondition', value: G.winSide });
  else Instance.SetRoundRemainingTime(1);
  G.finished = true;
}

// ---------------------------------------------------------------- the lobby -> run
function lobbyTick() {
  if (G.started || Instance.IsWarmupPeriod()) return;
  if (E.now - G.roundStart < CONFIG.LOBBY_WAIT) return;
  const players = [];
  for (const p of PL.values()) { const side = sideOf(p.ctrl); if (p.alive && (side === 2 || side === 3)) players.push({ id: p.slot, side }); }
  if (players.length < CONFIG.MIN_PLAYERS) { if (E.tick % 640 === 0) say(`Waiting for players: ${players.length}/${CONFIG.MIN_PLAYERS}`); return; }
  const seed = (Date.now() ^ (players.length * 7919)) >>> 0;
  G.rng = new Rng(seed); G.match = new Match(LAYOUT, seed, { log: (s) => Instance.Msg(`[${CONFIG.TAG}] ${s}`) });
  if (!G.match.start(players, E.now)) { G.match = null; return; }
  G.started = true; G.ended = false; G.finished = false; G.ringR = 0;
  Instance.SetRoundRemainingTime(CONFIG.FLOORS * CONFIG.FLOOR_TIME + CONFIG.STAGING_TIME + CONFIG.SHOWDOWN_TIME + CONFIG.ROUND_PAD + 30);
  say(`THE TEMPLE OPENS. ${G.match.squads.length} squads. Clear ${CONFIG.FLOORS} vaults, buy up, then the breach.`);
  ui('temple_open'); msgAll('THE TEMPLE OPENS', `${G.match.squads.length} squads. Clear ${CONFIG.FLOORS} vaults, buy up, then the breach.`, 6);
}

// ---------------------------------------------------------------- think
let lastValidate = 0;
function think() {
  const t0 = Date.now();
  E.now = Instance.GetGameTime(); E.tick++;
  try {
    if (E.now - lastValidate > 1) { lastValidate = E.now; refreshPawns(); validateSlots(); }
    else refreshPawns();
    if (!G.match) { lobbyTick(); for (const p of PL.values()) kioskTick(p); }
    if (G.match && !G.finished) {
      if (!G.ended) {
        G.match.tick(E.now);
        for (const p of PL.values()) { if (!G.match.squadOf.has(p.slot)) { kioskTick(p); continue; } abilityTick(p, G); chronoSaveTick(p); exitTick(p); if (G.match.phase === PHASE.STAGING) kioskTick(p); }
        // enemies per occupied room
        for (const R of ROOMS.values()) {
          if (R.squad < 0) continue;
          const s = G.match.squads[R.squad]; if (!s) continue;
          enemyTick(G, R, s.members.map((m) => PL.get(m)).filter(Boolean));
        }
        ringTick(); beaconTick();
        if (G.match.phase === PHASE.SHOWDOWN && CONFIG.APPLY_CVARS && !G.noRespawnSet) { G.noRespawnSet = true; Instance.ServerCommand('mp_respawn_on_death_t 0'); Instance.ServerCommand('mp_respawn_on_death_ct 0'); }
      } else if (E.now >= G.endAt) finishRound();
      runOrders();
    }
    G.fx.tick();
    sndTick();
    hudTick();
    flushMsgs();
  } catch (e) {
    Instance.Msg(`[${CONFIG.TAG}] think error: ${e && e.stack ? e.stack : e}`);
  } finally {
    Instance.SetNextThink(E.now + E.dt);
    const ms = Date.now() - t0; E.perf.ms += ms; E.perf.max = Math.max(E.perf.max, ms); E.perf.n++;
    if (E.now - E.perf.lastLog > 60) { if (E.perf.n) Instance.Msg(`[${CONFIG.TAG}] script time: avg ${(E.perf.ms / E.perf.n).toFixed(2)} ms, max ${E.perf.max} ms per server tick`); E.perf.lastLog = E.now; E.perf.ms = 0; E.perf.max = 0; E.perf.n = 0; }
  }
}

function beaconTick() {
  for (const R of ROOMS.values()) {
    if (R.beacon && !R.exitOpen) { poolGive(R.beacon); R.beacon = null; if (R.beaconSnd) { sfxStop(R.beaconSnd); R.beaconSnd = null; } }
    else if (R.beacon) poolMove(R.beacon, R.beacon.pos, (R.beacon.ang.yaw + 90 * E.dt) % 360);
  }
}

// lobby kiosks: stand within 110 units of one and press E to take its class (the picker panel names them)
const KIOSK = [{ dx: 1, dy: 0, cls: 'ninja' }, { dx: -1, dy: 0, cls: 'monk' }, { dx: 0, dy: 1, cls: 'chrono' }];
function kioskTick(p) {
  if (!p.alive || (G.match && G.match.squadOf.has(p.slot) && G.match.phase !== PHASE.STAGING)) return;
  const edge = pressedEdge(p, CSInputs.USE, 'prevUse'); if (!edge) return;
  const L = LAYOUT.lobby;
  for (const k of KIOSK) {
    const kx = L.cx + k.dx * 260, ky = L.cy + k.dy * 260;
    if (Math.hypot(p.lastPos.x - kx, p.lastPos.y - ky) < 110 && p.cls !== k.cls) { setClass(p, k.cls); sfx('kiosk', p.lastPos); msgTo([p.slot], CLASSES[k.cls].name, CLASSES[k.cls].blurb, 5); return; }
  }
}

function validateSlots() {
  for (const [slot, p] of PL) {
    let c; try { c = Instance.GetPlayerController(slot); } catch (e) { c = undefined; }
    if (!c || c !== p.ctrl || !c.IsValid()) {
      if (G.match) G.match.playerLeft(slot);
      PL.delete(slot);
      if (c && c.IsValid()) playerFor(c);
    }
  }
}

function resetAll() {
  // the pooled entities are gone with the old round: forget them without touching them
  for (const R of ROOMS.values()) { R.enemies = []; R.bolts = []; R.spawnQueue = []; R.beacon = null; R.beaconSnd = null; }
  sndReset();
  ROOMS.clear();
  FX.live.length = 0;
  for (const p of PL.values()) if (p.dome) p.dome.marker = null;
  for (const p of PL.values()) { p.cdUntil = 0; p.activeUntil = 0; if (p.dome && p.dome.marker) poolGive(p.dome.marker); p.dome = null; p.chrono = null; p.roomId = -1; p.exitSince = 0; p.pendingSave = false; }
  G.match = null; G.started = false; G.ended = false; G.finished = false; G.ringR = 0; G.noRespawnSet = false; G.winSide = undefined;
}

// ---------------------------------------------------------------- init
function init() {
  E.script = Instance.FindEntityByName(`${CONFIG.TAG.slice(0, 0)}nt_script`);
  const tpl = Instance.FindEntityByName('nt_tpl_prop'); E.tpl = tpl instanceof PointTemplate ? tpl : null;
  E.mapParams = Instance.FindEntityByName('nt_map_params') || null;
  E.missing = [];
  for (const r of LAYOUT.rooms) findTele(r.name + '_in');
  for (const s of LAYOUT.stagings) findTele(s.name);
  for (const b of LAYOUT.arena.balconies) findTele(b.name);
  findTele('nt_lobby');
  if (!E.tpl) E.missing.push('nt_tpl_prop'); if (!E.mapParams) E.missing.push('nt_map_params');
  E.pool.length = 0; E.poolFree.length = 0;
  poolInit(256);
  anchorsInit(48);
  sndInit();
  applyCvars();
  if (CONFIG.APPLY_CVARS) { Instance.ServerCommand('mp_respawn_on_death_t 1'); Instance.ServerCommand('mp_respawn_on_death_ct 1'); }
  E.ready = true;
  Instance.Msg(`[${CONFIG.TAG}] v${VERSION} ready: ${LAYOUT.rooms.length} vaults, ${LAYOUT.stagings.length} staging rooms, ${LAYOUT.arena.balconies.length} balconies, pool ${E.pool.length}` +
               (E.missing.length ? `, MISSING: ${E.missing.join(' ')}` : ''));
  E.now = Instance.GetGameTime(); G.roundStart = E.now;
  Instance.SetThink(think); Instance.SetNextThink(E.now + E.dt);
}

Instance.OnPlayerConnect(({ player }) => { if (player) playerFor(player); });
Instance.OnPlayerActivate(({ player }) => { if (player) { const p = playerFor(player); hudReset(p.slot); } });
Instance.OnPlayerTeamChanged(({ player }) => { const slot = slotOf(player); if (slot >= 0) hudReset(slot); });
Instance.OnPlayerDisconnect(({ playerSlot }) => { if (G.match) G.match.playerLeft(playerSlot); PL.delete(playerSlot); });
Instance.OnPlayerReset(({ player }) => {
  const slot = slotOf(player); const p = PL.get(slot); if (!p) return;
  p.cdUntil = 0; p.chrono = null; p.pendingSave = false; p.exitSince = 0;
  if (!G.match || G.match.phase === PHASE.END) return;
  const s = G.match.squadOf.get(slot); if (!s || s.eliminated) return;
  // a respawn in the vaults rejoins the squad in its room; in staging, the staging room; nobody respawns in the showdown
  const to = s.room >= 0 ? LAYOUT.rooms[s.room].name + '_in' : (s.staged ? 'nt_stage_' + (s.id % LAYOUT.stagings.length) : null);
  if (to) { G.match.respawned(slot); Instance.Delay(0.2).then(() => { refreshPawns(); const q = PL.get(slot); if (q && q.alive) teleportSquad([slot], to); }); }
});
Instance.OnPlayerKill(({ player, attacker }) => {
  const vs = slotOf(player); const ap = toPawn(attacker); const as = ap ? slotOf(ap) : undefined;
  if (G.match) G.match.playerDied(vs, as !== undefined && as >= 0 && as !== vs ? as : undefined);
});
Instance.OnBulletImpact(({ weapon, position }) => {
  if (!G.match) return;
  let shooter; try { shooter = weapon.GetOwner ? weapon.GetOwner() : undefined; } catch (e) { shooter = undefined; }
  if (!shooter) { try { shooter = weapon.GetOriginalOwner(); } catch (e) { /* */ } }
  if (shooter) bulletHit(G, shooter, weapon, position);
});
Instance.OnKnifeAttack(({ weapon, attackType }) => { if (G.match) knifeHit(G, weapon, attackType); });
Instance.OnPlayerChat(({ player, text }) => {
  if (!player) return;
  const p = playerFor(player); const t = text.trim().toLowerCase();
  if (CONFIG.DEV_COMMANDS && /^[!\/](skip|nt skip)\b/.test(t)) {
    // testing: kill every guardian in the room you stand in (counts as your kills)
    const R = p.roomId >= 0 ? roomState(p.roomId) : null; let n = 0;
    if (R) { R.spawnQueue.length = 0; for (const en of R.enemies.slice()) if (en.alive) { hurtEnemy(G, en, 1e6, p, false); n++; } }
    msgTo([p.slot], n ? `SKIPPED ${n} GUARDIANS` : 'NOTHING TO SKIP HERE', 'dev command', 3); return;
  }
  const m = t.match(/^[!\/](class|vector|warden|echo|ninja|monk|chrono|nt|help)\s*(\w*)/); if (!m) return;
  const word = m[1] === 'class' ? m[2] : m[1];
  const key = CLASS_BY_CHAT[word];
  if (!key) { msgTo([p.slot], `YOU ARE ${CLASSES[p.cls].name}`, 'chat !vector !warden !echo, or press E at a lobby kiosk', 6); return; }
  if (setClass(p, key)) msgTo([p.slot], CLASSES[key].name, CLASSES[key].blurb, 5);
});
Instance.OnRoundStart(() => { resetAll(); poolRebuild(256); anchorsInit(48); sndInit(); E.mapParams = Instance.FindEntityByName('nt_map_params') || null; E.now = Instance.GetGameTime(); G.roundStart = E.now; if (CONFIG.APPLY_CVARS) { Instance.ServerCommand('mp_ignore_round_win_conditions 1'); Instance.ServerCommand('mp_respawn_on_death_t 1'); Instance.ServerCommand('mp_respawn_on_death_ct 1'); } });
Instance.OnBeginRoundRestart(() => { resetAll(); });
Instance.OnScriptReload({ before: () => null, after: () => init() });
installDamageGate(G);
init();
