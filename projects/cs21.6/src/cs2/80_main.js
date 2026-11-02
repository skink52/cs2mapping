// ---------------------------------------------------------------- the main loop, CS2 events and chat commands

// ---- per player, every server tick (expensive reads are spread over ticks)
const weaponInfoCache = new WeakMap();
function weaponInfo(rec, w) {
  if (!w) return null;
  let info = weaponInfoCache.get(w);
  if (!info) {
    const id = weaponId(w);
    let type = CSWeaponType.UNKNOWN;
    try { type = w.GetData().GetType(); } catch (err) { /* ignore */ }
    info = { id, type, ammo: id && WEAPONS[id] ? WEAPONS[id].ammo || null : null, shown: { clip: 0, reserve: 0, ammo: null } };
    weaponInfoCache.set(w, info);
  }
  const t = info.type;
  if (t === CSWeaponType.KNIFE || t === CSWeaponType.C4 || t === CSWeaponType.TASER || t === CSWeaponType.EQUIPMENT || t === CSWeaponType.STACKABLEITEM) return null;
  const sh = info.shown;
  if (t === CSWeaponType.GRENADE) { sh.clip = -1; sh.reserve = info.id === 'flashbang' ? Math.max(1, rec.flashes) : 1; sh.ammo = info.id; return sh; }
  sh.clip = w.GetClipAmmo(); sh.reserve = w.GetReserveAmmo(); sh.ammo = info.ammo;
  return sh;
}

function sampleFast(rec, pawn, t) {
  const hp = pawn.GetHealth();
  if (hp !== rec.health) { rec.hpHot = t + 0.8; rec.health = hp; }
  const ap = pawn.GetArmor();
  if (ap !== rec.armor) { rec.apHot = t + 0.8; rec.armor = ap; }
  rec.weapon = weaponInfo(rec, pawn.GetActiveWeapon());
}
function sampleMoney(rec, c) {
  const m = c.GetMoneySpendableNow();
  if (!rec.moneyKnown) { rec.money = m; rec.moneyKnown = true; }
  else if (m !== rec.money) { showDelta(rec, m - rec.money); rec.money = m; }
}
function sampleSlow(rec, pawn, c) {
  sampleMoney(rec, c);
  const p = pawn.GetAbsOrigin();
  rec.pos = p;
  rec.hasC4 = rec.team === TEAM_T && !!pawn.GetC4();
  rec.hasDefuser = rec.team === TEAM_CT && pawn.HasDefuser();
  rec.helmet = pawn.HasHelmet();
  rec.inBuy = !!rec.map && inBuyZone(rec.map, rec.team, p);
  rec.inSite = rec.hasC4 && !!rec.map && inBombSite(rec.map, p);
  if (!pawn.IsAlive()) { rec.alive = false; return; }
  if (rec.cls && packWanted(rec) !== !!rec.packShown) applyModel(rec, pawn);
}

function playerTick(rec, t) {
  const s = rec.slot;
  const phase = (tickNo + s) & 7;
  let c;
  if (phase === 0 || phase === 4) {
    c = controllerOf(s);
    if (!c || !c.IsConnected()) { dropPlayer(s); return; }
    const team = c.GetTeamNumber();
    if (team !== rec.team) { rec.team = team; rec.alive = false; rec.map = null; closeMenu(rec); }
  }
  let pawn = rec.alive ? live(rec.pawn) : undefined;
  if (rec.alive && !pawn) rec.alive = false;
  // alive but not known as alive (a missed reset): pick them up
  if (!rec.alive && phase === 0 && c && (rec.team === TEAM_T || rec.team === TEAM_CT)) {
    const p = live(c.GetPlayerPawn());
    if (p && p.IsAlive()) { adoptPawn(rec, p); pawn = p; }
  }
  if (pawn) {
    if (CONFIG.FALL_DAMAGE_16) rec.vz = pawn.GetAbsVelocity().z;
    // spawn: put back on the map's spawn if CS2 moved the player after the reset
    if (rec.placeUntil) {
      if (t < rec.placeUntil) {
        const p = pawn.GetAbsOrigin(), sp = rec.placePos;
        if (sp && (Math.abs(p.x - sp[0]) > 32 || Math.abs(p.y - sp[1]) > 32 || Math.abs(p.z - sp[2]) > 48)) place(rec, pawn);
        rec.pos = p;
      } else rec.placeUntil = 0;
    }
    if (rec.spawnFixAt && t >= rec.spawnFixAt) guard('spawnfix', () => spawnFix(rec, pawn));
    if (rec.botBuyAt && t >= rec.botBuyAt) guard('botbuy', () => botBuy(rec));
    if (rec.ammoFix.length) guard('ammofix', () => fixAmmo(rec, pawn));
    if ((phase & 1) === 0) sampleFast(rec, pawn, t);
    if (phase === 0) sampleSlow(rec, pawn, c);
    playerInput(rec, pawn, t);
  } else if (phase === 0 && c) sampleMoney(rec, c);
  // menus close themselves: the buy menu when buying is over, the class menu after a while (auto-select)
  if (rec.menu) {
    if (rec.menu.kind === 'buy' && canBuyNow(rec) !== null) closeMenu(rec);
    else if (rec.menu.kind === 'class' && t - rec.menu.opened > CONFIG.CLASS_MENU_SECONDS) chooseClass(rec, null);
  }
  drawHud(rec, t);
}

// the buy key: F (inspect) in a buy zone opens and closes the 1.6 buy menu; CS2's own buy key (B) opens it too if
// CS2 lets its menu open at all
function playerInput(rec, pawn, t) {
  if (rec.menu) menuKeys(rec, pawn);
  // (only read the keys while the player could buy: in a buy zone, in the buy time)
  if (!(rec.menu && rec.menu.kind === 'buy') && (!rec.inBuy || canBuyNow(rec) !== null)) { rec.cs2Buy = false; return; }
  let press = false;
  if (CONFIG.BUY_KEY_INSPECT && pawn.WasInputJustPressed(CSInputs.LOOK_AT_WEAPON)) press = true;
  if (CONFIG.BUY_KEY_CS2 && ((tickNo + rec.slot) & 3) === 0) {
    const open = !!guard('buymenu', () => pawn.IsBuyMenuOpen());
    if (open && !rec.cs2Buy) press = true;
    rec.cs2Buy = open;
  }
  if (!press) return;
  if (rec.menu && rec.menu.kind === 'buy') { closeMenu(rec); return; }
  const why = canBuyNow(rec);
  if (why === null) openMenu(rec, 'buy');
  else if (why) message(rec, why, 3);
}

function dropPlayer(slot) {
  const rec = recs.get(slot);
  if (rec && rec.capture) setCapture(rec, false);
  recs.delete(slot);
  hudCache.delete(slot);
  knifeSwings.delete(slot);
  pendingPay.delete(slot);
}

// ---- the think loop: every server tick
let lastTiming = 0, timeSum = 0, timeMax = 0, timeN = 0;
function think() {
  const t0 = Date.now();
  inThink = true;
  tickTime = Instance.GetGameTime();
  tickNo++;
  hudBudget = CONFIG.HUD_BUDGET;
  soundsThisTick = 0;
  try {
    guard('sounds', flushSounds);
    guard('round', () => roundThink(tickTime));
    for (const rec of [...recs.values()]) guard('player', () => playerTick(rec, tickTime));
    guard('say', flushSays);
  } finally { inThink = false; }
  Instance.SetNextThink(Instance.GetGameTime());
  // script time per tick, in the console once a minute
  const dt = Date.now() - t0;
  timeSum += dt; timeN++; if (dt > timeMax) timeMax = dt;
  if (tickTime - lastTiming > 60) {
    if (CONFIG.TIMING) log(`script time: avg ${(timeSum / Math.max(1, timeN)).toFixed(2)} ms, max ${timeMax} ms per tick, ${recs.size} players`);
    lastTiming = tickTime; timeSum = 0; timeMax = 0; timeN = 0;
  }
}

// ---- chat commands (start with ! or /)
const HELP = [
  'CS 1.6: F in a buy zone = buy menu (or !buy, !ak47, !m4a1, !vesthelm, !rebuy)',
  '!dust2 !train !nuke = which map you want   !maps = who plays where',
  '!class = player model   !hud raised|classic|off',
].join('\n');

function onChat(ev) {
  const c = ev.player;
  if (!c) return;
  const s = c.GetPlayerSlot();
  const rec = recOf(s);
  if (!rec) return;
  const text = String(ev.text || '').trim();
  if (!/^[!/]/.test(text)) return;
  const parts = text.slice(1).toLowerCase().split(/\s+/);
  const cmd = parts[0], arg = parts[1] || '';
  dlog(`chat command from slot ${s}: ${text}`);
  const mapKey = (k) => (MAP_BY_KEY[k] ? k : MAP_BY_KEY[k.replace(/^de_/, '')] ? k.replace(/^de_/, '') : null);
  switch (cmd) {
    case 'buy': case 'b': case 'shop':
      if (arg) { if (!buyByName(rec, arg)) message(rec, 'Unknown item: ' + arg, 3); return; }
      { const why = canBuyNow(rec); if (why === null) openMenu(rec, 'buy'); else message(rec, why || 'You are not in a buy zone', 3); }
      return;
    case 'rebuy': rebuy(rec); return;
    case 'class': case 'model': case 'skin':
      if (rec.team === TEAM_T || rec.team === TEAM_CT) openMenu(rec, 'class');
      return;
    case 'close': closeMenu(rec); return;
    case 'help': case 'cs16': case 'commands': message(rec, HELP, 10); return;
    case 'hud':
      rec.hudMode = ['raised', 'classic', 'off'].includes(arg) ? arg : rec.hudMode === 'raised' ? 'classic' : rec.hudMode === 'classic' ? 'off' : 'raised';
      message(rec, 'HUD: ' + rec.hudMode, 2);
      return;
    case 'maps': {
      const lines = [...round.maps.keys()].map((k) => {
        const n = (team) => [...recs.values()].filter((r) => r.map === k && r.team === team).length;
        return `${MAP_BY_KEY[k].title}: ${n(TEAM_T)} T vs ${n(TEAM_CT)} CT`;
      });
      message(rec, (lines.join('\n') || 'No round running') + (rec.want ? `\nYou asked for ${MAP_BY_KEY[rec.want].title}` : ''), 6);
      return;
    }
    case 'map': {
      const k = mapKey(arg);
      if (k) { rec.want = k; message(rec, `You asked for ${MAP_BY_KEY[k].title}: from the next round when it runs`, 4); }
      else message(rec, 'Maps: ' + MAPS.map((m) => m.key).join(', '), 4);
      return;
    }
  }
  const k = mapKey(cmd);
  if (k) { rec.want = k; message(rec, `You asked for ${MAP_BY_KEY[k].title}: from the next round when it runs`, 4); return; }
  buyByName(rec, cmd);
}

// ---- events
Instance.OnActivate(() => {
  if (CONFIG.APPLY_CVARS) {
    const extra = [
      `mp_roundtime ${(CONFIG.ROUND_TIME / 60).toFixed(2)}`, `mp_roundtime_defuse ${(CONFIG.ROUND_TIME / 60).toFixed(2)}`,
      `mp_freezetime ${CONFIG.FREEZE_TIME}`, `mp_c4timer ${CONFIG.C4_TIMER}`, `mp_startmoney ${CONFIG.START_MONEY}`,
      `mp_maxmoney ${CONFIG.MAX_MONEY}`, `mp_round_restart_delay ${CONFIG.RESTART_DELAY}`,
    ];
    if (CONFIG.JUMP_16) extra.push('sv_jump_impulse 268.33');
    for (const cv of CONFIG.CVARS.concat(extra)) guard('cvar', () => Instance.ServerCommand(cv));
  }
  for (const c of Instance.GetAllPlayerControllers()) {
    if (!c || !c.IsConnected()) continue;
    const rec = recOf(c.GetPlayerSlot());
    rec.team = c.GetTeamNumber();
    const p = live(c.GetPlayerPawn());
    if (p && p.IsAlive()) { rec.pawn = p; rec.alive = true; guard('name', () => p.SetEntityName(pawnName(rec.slot))); }
  }
  log(`v${VERSION} ready: ${MAPS.map((m) => m.title).join(', ')}; ${recs.size} players`);
  Instance.SetThink(think);
  Instance.SetNextThink(Instance.GetGameTime());
});
Instance.OnPlayerActivate((ev) => guard('activate', () => {
  const s = ev.player.GetPlayerSlot();
  const rec = recOf(s);
  hudReset(s);
  // (cursor mode left over from a previous player in this slot)
  const h = hud();
  if (h) guard('capture', () => h.SetInputCaptureEnabled(s, false));
  rec.capture = false;
  rec.moneyKnown = false;
}));
Instance.OnPlayerDisconnect((ev) => guard('disconnect', () => dropPlayer(ev.playerSlot)));
Instance.OnPlayerReset((ev) => guard('reset', () => onReset(ev.player)));
Instance.OnPlayerTeamChanged((ev) => guard('team', () => onTeamChanged(ev.player)));
Instance.OnBeginRoundRestart(() => guard('restart', () => { needPlan = true; }));
Instance.OnRoundStart(() => guard('roundstart', onRoundStart));
Instance.OnRoundEnd((ev) => guard('roundend', () => {
  // the first test should show whether CS2 read our result the way it was meant (see TESTING.md)
  const want = round.endRes;
  if (want && round.ended && round.endSent) {
    const ok = want.winner ? ev.winningTeam === want.winner : ev.winningTeam !== TEAM_T && ev.winningTeam !== TEAM_CT;
    log(`CS2 round end: team ${ev.winningTeam}, reason ${ev.reason}` + (ok ? '' : ` - WARNING: expected ${want.winner ? teamName(want.winner) : 'a draw'}`));
  }
  round.endRes = null;
  onRoundEnd();
}));
Instance.OnBombPlant((ev) => guard('plant', () => onBombPlant(ev)));
Instance.OnBombDefuse((ev) => guard('defuse', () => onBombDefuse(ev)));
Instance.OnBombExplode((ev) => guard('explode', () => onBombExplode(ev)));
Instance.OnPlayerKill((ev) => guard('kill', () => onKill(ev)));
Instance.OnModifyPlayerDamage((ev) => guard('damage', () => onModifyDamage(ev)));
Instance.OnPlayerLand((ev) => guard('land', () => onLand(ev.player)));
Instance.OnKnifeAttack((ev) => guard('knife', () => onKnifeAttack(ev)));
Instance.OnPlayerChat((ev) => guard('chat', () => onChat(ev)));
Instance.OnCustomHudClicked((ev) => guard('click', () => { const rec = recs.get(ev.player.GetPlayerSlot()); if (rec) menuClick(rec, ev.buttonId); }));
Instance.OnGrenadeThrow((ev) => guard('nade', () => {
  const owner = ev.weapon ? ev.weapon.GetOwner() : undefined;
  const rec = recs.get(slotOf(owner));
  if (!rec) return;
  if (weaponId(ev.weapon) === 'flashbang') rec.flashes = Math.max(0, rec.flashes - 1);
  // 1.6: "Fire in the hole!" on the thrower's team radio
  if (CONFIG.FIRE_IN_THE_HOLE && rec.map) playToMany([...recs.values()].filter((r) => r.map === rec.map && r.team === rec.team), 'ct_fireinhole');
}));
