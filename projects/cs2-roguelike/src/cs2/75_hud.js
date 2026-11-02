// ===================================================================================
// CS2 adapter, part 3b: the HUD (custom_hud_layout nt_hud). Per-player caches, only changes are sent, a budget per tick.
// Panels: Nt (root states stOn stTop stRun stMsg stPick stVig stStage stBreach), TopT{t}, Cls{c}, Abil{a}, Tile (stReady stActive stMonk stChrono),
// Info{i}, Msg{m}, Sub{u}, Row0..2 (stSel).
// ===================================================================================
const HUD = { ent: undefined, budget: 0, fails: 0, tried: 0 };

function findHud() {
  if (HUD.ent && HUD.ent.IsValid()) return HUD.ent;
  HUD.ent = undefined;
  const e = Instance.FindEntityByName('nt_hud');
  if (e instanceof CustomHudLayout) HUD.ent = e;
  else for (const x of Instance.FindEntitiesByClass('custom_hud_layout')) if (x instanceof CustomHudLayout) { HUD.ent = x; break; }
  if (HUD.ent) for (const p of PL.values()) p.hud.clear();
  return HUD.ent;
}
function hudVar(p, panel, v, value) {
  const k = panel + '$' + v;
  if (p.hud.get(k) === value || HUD.budget <= 0 || HUD.fails > 50) return;
  try { HUD.ent.SetDialogVariableStringForPlayer(p.slot, panel, v, value); p.hud.set(k, value); HUD.budget--; }
  catch (e) { HUD.fails++; if (HUD.fails < 4) Instance.Msg(`[${CONFIG.TAG}] hud var failed: ${e}`); }
}
function hudClass(p, panel, cls, on) {
  const k = panel + '#' + cls;
  if (p.hud.get(k) === on || HUD.budget <= 0 || HUD.fails > 50) return;
  try { HUD.ent.SetHasClassForPlayer(p.slot, panel, cls, on); p.hud.set(k, on); HUD.budget--; }
  catch (e) { HUD.fails++; if (HUD.fails < 4) Instance.Msg(`[${CONFIG.TAG}] hud class failed: ${e}`); }
}
function hudReset(slot) {
  const p = PL.get(slot); if (p) p.hud.clear();
  if (findHud()) { try { HUD.ent.ResetForPlayer(slot); } catch (e) { /* */ } }
}

function msgTo(members, text, sub, seconds) {
  for (const s of members) { const p = PL.get(s); if (p) { p.msg = text; p.msgSub = sub || ''; p.msgUntil = E.now + (seconds || 4); } }
}
function msgAll(text, sub, seconds) { msgTo([...PL.keys()], text, sub, seconds); }

function areaName(p) {
  if (!G.match) return 'ENTRANCE HALL';
  const s = G.match.squadOf.get(p.slot); if (!s) return 'ENTRANCE HALL';
  if (G.match.phase === PHASE.SHOWDOWN) return 'THE ARENA';
  if (s.room >= 0) { const r = LAYOUT.rooms[s.room]; return `VAULT ${String(r.id + 1).padStart(2, '0')}  ${r.kind.toUpperCase()}`; }
  if (s.staged) return 'STAGING';
  return 'ENTRANCE HALL';
}

function topLine(p) {
  if (!G.match) {
    let n = 0; for (const q of PL.values()) if (q.alive) n++;
    const left = Math.max(0, CONFIG.LOBBY_WAIT - (E.now - G.roundStart));
    return n >= CONFIG.MIN_PLAYERS ? `NANITE TEMPLE    ${n} PLAYERS    STARTING IN ${fmtTime(left)}` : `NANITE TEMPLE    WAITING FOR PLAYERS  ${n} / ${CONFIG.MIN_PLAYERS}`;
  }
  const M = G.match; const s = M.squadOf.get(p.slot);
  if (M.phase === PHASE.FLOORS) {
    if (s && s.room >= 0) return `VAULT ${s.floor} / ${CONFIG.FLOORS}    ${fmtTime(CONFIG.FLOOR_TIME - (E.now - s.roomStart))}`;
    return `VAULTS    ${fmtTime(M.floorEndsAt - E.now)}`;
  }
  if (M.phase === PHASE.STAGING) return `STAGING    BREACH IN ${fmtTime(M.stagingEndsAt - E.now)}`;
  if (M.phase === PHASE.SHOWDOWN) { const live = M.squads.filter((q) => !q.eliminated).length; return `SHOWDOWN ${fmtTime(M.showdownEndsAt - E.now)}    ${live} SQUAD${live === 1 ? '' : 'S'} LEFT`; }
  if (M.phase === PHASE.END) return M.winner ? `SQUAD ${M.winner.id + 1} TAKES THE TEMPLE` : 'THE TEMPLE KEEPS ITS SECRETS';
  return 'NANITE TEMPLE';
}

function abilityLine(p) {
  const c = CLASSES[p.cls]; const name = c.active;
  if (p.cls === 'chrono' && p.chrono) return [`REWIND ARMED ${Math.max(0, p.chrono.until - E.now).toFixed(1)} s`, 'active'];
  if (p.cls === 'monk' && p.dome) return [`AEGIS ${Math.max(0, p.dome.until - E.now).toFixed(1)} s`, 'active'];
  if (E.now >= p.cdUntil) return [`${name} READY`, 'ready'];
  return [`${name} ${(p.cdUntil - E.now).toFixed(1)} s`, 'cool'];
}

function drawHud(p) {
  const inRun = !!(G.match && G.match.squadOf.has(p.slot) && G.match.phase !== PHASE.END);
  hudClass(p, 'Nt', 'stOn', true);
  hudClass(p, 'Nt', 'stTop', true);
  hudVar(p, 'TopT', 't', topLine(p));
  hudClass(p, 'Nt', 'stRun', inRun);
  hudClass(p, 'Nt', 'stPick', !G.match || G.match.phase === PHASE.STAGING || (G.match.phase === PHASE.FLOORS && !inRun));
  hudClass(p, 'Nt', 'stStage', !!(G.match && G.match.phase === PHASE.STAGING));
  hudClass(p, 'Nt', 'stBreach', !!(G.match && G.match.phase === PHASE.SHOWDOWN));
  hudClass(p, 'Nt', 'stVig', !!(p.chrono && p.alive));
  for (let i = 0; i < 3; i++) hudClass(p, 'Row' + i, 'stSel', CLASS_KEYS[i] === p.cls);
  if (inRun) {
    hudVar(p, 'Cls', 'c', CLASSES[p.cls].name);
    const [a, st] = abilityLine(p);
    hudVar(p, 'Abil', 'a', a);
    hudClass(p, 'Tile', 'stReady', st === 'ready'); hudClass(p, 'Tile', 'stActive', st === 'active');
    hudClass(p, 'Tile', 'stMonk', p.cls === 'monk'); hudClass(p, 'Tile', 'stChrono', p.cls === 'chrono');
    const s = G.match.squadOf.get(p.slot);
    hudVar(p, 'Info', 'i', `SQUAD ${s.id + 1}    ${s.alive} / ${s.members.length} ALIVE    AREA  ${areaName(p)}`);
  }
  const show = !!(p.msg && E.now < p.msgUntil);
  hudClass(p, 'Nt', 'stMsg', show);
  if (show) { hudVar(p, 'Msg', 'm', p.msg); hudVar(p, 'Sub', 'u', p.msgSub || ' '); }
}

function hudTick() {
  if (!findHud()) return;
  HUD.budget = CONFIG.HUD_BUDGET;
  for (const p of PL.values()) {
    if ((p.slot & 7) !== (E.tick & 7)) continue;      // each player refreshed every 8 ticks
    if (!p.alive && !p.ctrl.IsValid()) continue;
    try { drawHud(p); } catch (e) { HUD.fails++; }
  }
}
