// ------------------------------------------------------------------ 70_hud: role cards, objective bar, instruments, board (ids: docs/SCRIPT.md "HUD contract")
const NEEDLE = (deg) => "a" + (((Math.round(deg / 5) % 72) + 72) % 72);
function roleCard(p, role) {
  const team = p.team === T || p.team === CT ? p.team : CT;
  // (the card's lines are 320 px of 19 px text: about 34 characters; playtest 1 found pass 1's 70-character lines would not fit)
  if (role === "infantry") return info(p, "INFANTRY", ["Stand at a flag pole to take it", "Hold 3 flags: their tickets bleed",
    "E at a rack or held crate: kit", "Hold E on far ground: fire mission", "E: board a helicopter / man a gun"], "!spawn picks where you deploy");
  if (role === "artillery") return info(p, team === T ? "ROCKET BATTERY" : "HOWITZER BATTERY", ["Two to a gun. E at the rack: round",
    "E at the gun: load. E at the board", "WASD aims, MOUSE1 locks, R: mission", team === T ? "SPACE: salvo (up to 4 rockets)" : "SPACE fires. MOUSE2 at rack: shell",
    "Hold E on a hit gun: repair"], "You join a crew when a seat is free");
  if (role === "air") return info(p, "AIRCREW", ["SPACE climbs, CTRL descends", "Mouse turns, WASD moves", "Land slow and level. E: out",
    "MOUSE1: rockets or the nose gun", "Your pad repairs and re-arms"], "!controls in the seat: every key");
}
// G = the gun's config (belt, reload). The belt read-out has its own label when the HUD has one (mv_gun_ammo, "HUD additions");
// until then it rides on the name line, in steps of 5 rounds so the text is not re-sent for every shot.
function drawGun(p, name, st, G) {
  hClass(p, "mv_gun", "show", true);
  hClass(p, "mv_gun", "hot", st.locked);
  let ammo = "";
  if (G && G.belt) ammo = st.reloadAt ? "RELOADING " + Math.max(1, Math.ceil(st.reloadAt - TNOW)) + " s" : "BELT " + (st.ammo === undefined ? G.belt : st.ammo);
  if (hudHas("mv_gun_ammo")) { hText(p, "mv_gun_name", name); if ((tickNo + p.slot) % 4 === 0 || st.reloadAt) hText(p, "mv_gun_ammo", ammo); }
  else hText(p, "mv_gun_name", ammo ? name + "   " + (st.reloadAt ? ammo : "BELT " + Math.ceil((st.ammo === undefined ? G.belt : st.ammo) / 5) * 5) : name);
  hSwap(p, "mv_gun_heat", "heat", "ht" + clampN(Math.round(st.heat * 10), 0, 10));
}
function drawObjective(p) {
  const C = CONFIG.CONQUEST;
  hClass(p, "mv_obj", "show", true);
  for (const f of flags) {
    const id = "mv_flag_" + f.id;
    hSwap(p, id, "own", f.owner === T ? "own_t" : f.owner === CT ? "own_ct" : "own_n");
    hSwap(p, id, "cap", "cap" + clampN(Math.round(f.prog * 10), 0, 10));
    if (f.capTeam) hSwap(p, id, "capt", f.capTeam === T ? "capt_t" : "capt_ct");
    hClass(p, id, "contest", f.contested);
    hClass(p, id, "here", p.here === f.id);
  }
  for (const team of TEAMS) {
    const tg = tagOf(team);
    hText(p, "mv_tk_" + tg, String(game.tickets[team]));
    hClass(p, "mv_tk_" + tg, "bleed", game.bleeding[team]);
    hSwap(p, "mv_tkbar_" + tg, "w", "w" + clampN(Math.round(20 * game.tickets[team] / Math.max(1, C.TICKETS)), 0, 20));
  }
  const left = game.over ? 0 : Math.max(0, C.ROUND_SECONDS - (TNOW - game.start));
  hText(p, "mv_clock", Math.floor(left / 60) + ":" + ("0" + Math.floor(left % 60)).slice(-2));
}
// instruments for everyone aboard: needles every other tick, texts and the seat list a few times a second
function drawFlight(p, h, seat) {
  const H = CONFIG.HELI;
  hClass(p, "mv_fly", "show", true);
  hClass(p, "mv_status", "show", false);
  hSwap(p, "mv_fly", "seat", "seat_" + seat.kind);
  const pg = seat.kind === "pilot" ? pilotGun(h) : null;
  if (seat.kind === "gunner") drawGun(p, h.M.GUN.name, h.gun, h.M.GUN); else if (pg) drawGun(p, pg.name, pg.st, pg.G); else hClass(p, "mv_gun", "show", false);
  const phase = h.tick + p.slot;
  if (phase % 2 === 0) {
    const kmh = Math.hypot(h.speed, h.vel.z) * 0.0254 * 3.6, altm = h.alt * 0.0254, vs = h.vel.z * 0.0254;
    hSwap(p, "mv_n_asi", "rot", NEEDLE(300 * Math.min(1, kmh / CONFIG.HUDCFG.ASI_MAX_KMH)));
    hSwap(p, "mv_n_alt", "rot", NEEDLE((altm % 100) / 100 * 360));
    hSwap(p, "mv_n_vsi", "rot", NEEDLE(clampN(vs / 10, -1, 1) * 135));
    hSwap(p, "mv_ai_roll", "rot", NEEDLE(-h.roll));
    hSwap(p, "mv_ai_pitch", "pit", "pit" + clampN(Math.round(10 - h.pitch / 2), 0, 20));
    hSwap(p, "mv_hdg", "hdg", "h" + (((Math.round((90 - h.yaw) / 5) % 72) + 72) % 72));
  }
  if (phase % 8 !== 0) return;
  const hdg = ((90 - h.yaw) % 360 + 360) % 360;
  hText(p, "mv_hdg_txt", ("00" + (Math.round(hdg) % 360)).slice(-3));
  hText(p, "mv_alt_txt", String(Math.round(h.alt * 0.0254)));
  hText(p, "mv_spd_txt", String(Math.round(h.speed * 0.0254 * 3.6)));
  hSwap(p, "mv_heli_hp", "hp", "hp" + clampN(Math.round(h.hp / h.maxHp * 20), 0, 20));
  hClass(p, "mv_rtb", "on", h.hp < H.SMOKE_HP);
  hText(p, "mv_rkt_txt", h.M.ROCKETS ? (h.rockets < 2 ? "RE-ARM" : "RKT " + h.rockets) : "");
  for (let i = 0; i < 6; i++) {
    const s = h.seats[i], id = "mv_seat_" + (i + 1);
    hText(p, id, s ? s.kind.toUpperCase() + "  " + (s.slot >= 0 ? nameOf(s.slot) : "-") : "");
    hClass(p, id, "me", !!s && s.slot === p.slot);
  }
  hText(p, "mv_fly_info", h.state === "crashing" ? "GOING DOWN" : h.warn || seatHint(h, seat.kind));
}
function stepOf(t) { return clampN(Math.floor(t * BOARD_STEPS), 0, BOARD_STEPS - 1); }
function placeMarkerUV(p, id, u, v, on) {
  hClass(p, id, "on", on);
  if (!on) return;
  hSwap(p, id, "x", "x" + stepOf(u));
  hSwap(p, id + "y", "y", "y" + stepOf(v));
}
function placeMarker(p, id, pos) {
  if (!pos) { hClass(p, id, "on", false); return; }
  const s = worldToBoard(pos.x, pos.y);
  placeMarkerUV(p, id, s.u, s.v, true);
}
function drawBoard(p, g) {
  const A = CONFIG.ARTY, C = CONFIG.BOARD, team = p.team;
  hClass(p, "mv_board", "show", true);
  hClass(p, "mv_status", "show", false);
  hSwap(p, "mv_board", "lay", gunDisabled(g) ? "lay_disabled" : "lay_" + g.lay);
  placeMarkerUV(p, "mv_ret", p.u, p.v, true);
  placeMarker(p, "mv_lock", g.target);
  placeMarker(p, "mv_gpos", g.pos);
  hClass(p, "mv_cep", "on", !!g.target);
  if (g.target) hSwap(p, "mv_cep", "size", "cep" + clampN(Math.round(1.1774 * sigmaOf(g, g.target.range) / C.CEP_STEP) - 1, 0, C.CEP_MAX));
  for (let i = 0; i < A.IMPACTS_SHOWN; i++) placeMarker(p, "mv_imp" + i, g.impacts[i]);
  const marks = boardMarks(team), sel = p.msnSel >= 0 && p.msnSel < marks.length ? marks[p.msnSel] : null;
  for (let i = 0; i < A.MISSION.PER_TEAM; i++) {
    const m = missions[team].find((q) => q.idx === i);
    placeMarker(p, "mv_msn" + i, m);
    hClass(p, "mv_msn" + i, "sel", !!m && !!sel && sel.m === m);
  }
  let fi = 0;
  for (const f of flashes[team]) { if (TNOW < f.from || fi >= A.FLASH_MAX) continue; placeMarker(p, "mv_fl" + fi, f); hClass(p, "mv_fl" + fi, "sel", !!sel && sel.kind === "flash" && sel.x === f.x && sel.y === f.y); fi++; }
  for (; fi < A.FLASH_MAX; fi++) { placeMarker(p, "mv_fl" + fi, null); hClass(p, "mv_fl" + fi, "sel", false); }
  const w = boardToWorld(p.u, p.v), range = dist2(g.pos, w);
  hText(p, "mv_b_range", "RANGE  " + Math.round(range * 0.0254) + " m");
  hText(p, "mv_b_grid", "GRID  " + gridRef(w.x, w.y) + (g.target ? "   LOCKED " + gridRef(g.target.x, g.target.y) : ""));
  hText(p, "mv_b_gun", "GUN " + (g.k + 1) + "  " + (gunDisabled(g) ? "DISABLED " + Math.ceil(g.disabledUntil - TNOW) + " s" : g.lay === "laying" ? "LAYING " + Math.max(0, g.layEnd - TNOW).toFixed(1) + " s" : g.lay === "laid" ? "LAID" : "NO TARGET"));
  hText(p, "mv_b_shell", g.loaded.length ? (team === T ? "LOADED: " + g.loaded.length + " ROCKET" + (g.loaded.length > 1 ? "S" : "") : "LOADED: " + A.SHELL_NAME[g.loaded[g.loaded.length - 1]]) : "EMPTY");
  const why = fireBlock(g);
  hText(p, "mv_b_state", why ? why.toUpperCase() : "READY - SPACE TO FIRE");
  hText(p, "mv_b_msn", sel ? (sel.kind === "msn" ? "MISSION " + (p.msnSel + 1) + "/" + marks.length + "  " + nameOf(sel.m.owner) + "  " + gridRef(sel.x, sel.y) + "  " + Math.max(0, Math.ceil(sel.m.until - TNOW)) + " s"
                                                   : "ENEMY GUN FLASH  " + gridRef(sel.x, sel.y)) : marks.length ? marks.length + " MARK" + (marks.length > 1 ? "S" : "") + " WAITING - R TO CYCLE" : "NO FIRE MISSIONS");
  hText(p, "mv_b_stats", "ROUNDS " + p.fired + "   HITS " + p.hits + "   MISSIONS " + p.missions);
}
function drawStatus(p, team) {
  hClass(p, "mv_status", "show", true);
  if (p.role === "infantry") {
    const K = CONFIG.KITS[p.kit] || CONFIG.KITS.rifle;
    hText(p, "mv_st_role", "INFANTRY - " + K.label);
    hText(p, "mv_st_l1", K.name[team] + (p.kit === "at" && TNOW < p.atReadyAt ? "  (reloading " + Math.ceil(p.atReadyAt - TNOW) + " s)" : "") + (p.kitNext ? "  (next: " + CONFIG.KITS[p.kitNext].label + ")" : ""));
    const m = missions[team].find((q) => q.owner === p.slot);
    hText(p, "mv_st_l2", m ? "Fire mission " + gridRef(m.x, m.y) + (m.shot ? "  SHOT" : "  waiting") + "  " + Math.max(0, Math.ceil(m.until - TNOW)) + " s" : "Hold E on far ground: fire mission");
    hText(p, "mv_st_l3", TNOW < p.protectUntil ? "Deploy cover " + Math.ceil(p.protectUntil - TNOW) + " s" : "Kills " + p.kills + "   Merit " + p.merit);
  } else if (p.role === "artillery") {
    const g = guns[team][p.crew];
    hText(p, "mv_st_role", (team === T ? "ROCKET BATTERY" : "HOWITZER BATTERY") + (g ? " - GUN " + (g.k + 1) : ""));
    const mate = g ? g.crew.find((s) => s !== p.slot) : undefined;
    hText(p, "mv_st_l1", g ? "Mate: " + (mate !== undefined ? nameOf(mate) : "none") + "   " + (gunDisabled(g) ? "DISABLED" : g.lay.toUpperCase()) : "");
    hText(p, "mv_st_l2", g ? (g.loaded.length ? "Loaded " + g.loaded.length : "Empty") + "   Target " + (g.target ? gridRef(g.target.x, g.target.y) : "none") + "   Missions " + missions[team].length : "");
    hText(p, "mv_st_l3", "Rounds " + p.fired + "   Hits " + p.hits + (p.carrying ? "   (" + CONFIG.ARTY.SHELL_NAME[p.carrying] + " in hand)" : ""));
  } else {
    const h = ownHeli(p);
    hText(p, "mv_st_role", "AIRCREW" + (h ? " - " + h.M.label + " " + h.n : ""));
    hText(p, "mv_st_l1", h ? (h.state === "dead" ? "New helicopter in " + Math.max(0, Math.ceil(h.respawnAt - TNOW)) + " s" : "Your helicopter is " + (h.landed ? "on the ground" : "airborne")) : "No helicopter");
    hText(p, "mv_st_l2", h && h.state !== "dead" ? "Airframe " + Math.round(100 * h.hp / h.maxHp) + " %" + (h.M.ROCKETS ? "   Rockets " + h.rockets : "") : "");
    hText(p, "mv_st_l3", "Kills " + p.kills);
  }
}
function drawHold(p, text, frac) {
  const on = frac > 0;
  hClass(p, "mv_hold", "show", on);
  if (!on) return;
  hText(p, "mv_hold_text", text);
  hSwap(p, "mv_hold_bar", "p", "p" + clampN(Math.round(frac * 20), 0, 20));
}
function drawBrief(p, team) {
  hClass(p, "mv_brief", "show", true);
  hText(p, "mv_brief_role", (ROLE_NAME[p.role] || "") + (p.role === "infantry" ? " - " + CONFIG.KITS[p.kit].label : ""));
  let lines;
  if (p.role === "artillery") { const g = guns[team][p.crew]; lines = ["Gun " + (g ? g.k + 1 : "?") + " of " + guns[team].length + ". Answer the fire missions on the board.", "Rounds from the rack, load at the gun, plot, fire.", "Enemy shells can silence your gun: hold E to repair."]; }
  else if (p.role === "air") { const h = ownHeli(p); lines = [(h ? h.M.label + " on pad " + h.n : "Helicopter") + ". Carry the infantry, support the flags.", "SPACE up, CTRL down, mouse turns, WASD tilts.", "The pad repairs and re-arms. Riders board with E."]; }
  else lines = [CONFIG.KITS[p.kit].name[team] + ". Hold 3 of the 5 flags to bleed their tickets.", "Hold E on far ground to call the battery. E boards a helicopter.", "Kits: !rifle !mg !at, or E at an arms rack or flag crate."];
  hText(p, "mv_brief_l1", lines[0]); hText(p, "mv_brief_l2", lines[1]); hText(p, "mv_brief_l3", lines[2]);
  const open = p.role === "infantry" && spawnChoices(p).includes(p.spawnSel);
  hText(p, "mv_brief_spawn", p.role === "infantry" ? "DEPLOY: " + (open ? spawnLabel(p.spawnSel) : "BASE  (" + (p.spawnSel === "heli" ? "no helicopter waiting" : spawnLabel(p.spawnSel) + ((flagById(p.spawnSel) || {}).owner === p.team ? " is under attack" : " is not ours")) + ")") + "   [R] next"
                                                   : p.role === "air" ? "DEPLOY: HELIPAD" : "DEPLOY: BATTERY");
  hText(p, "mv_brief_count", "Moving out in " + Math.max(0, p.deployAt - TNOW).toFixed(0) + " s    chat: !help  !infantry  !artillery  !air");
}
