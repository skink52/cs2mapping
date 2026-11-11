// ------------------------------------------------------------------ 60_conquest: flags, tickets, bleed, round end (DESIGN 3.4)
const flags = [];
const game = { tickets: { 2: 0, 3: 0 }, bleed: { 2: 0, 3: 0 }, bleeding: { 2: false, 3: false }, held: { 2: 0, 3: 0 }, start: 0, over: false, overAt: 0, winner: 0,
               reason: 0, fallback: 0, flagAt: 0, rounds: 0 };
function loadFlags() {
  flags.length = 0;
  for (const f of LAYOUT.flags) {
    const e = need("mv_flag_" + f.id);
    need("mv_flagpole_" + f.id);
    flags.push({ id: f.id, name: f.name, pos: e ? e.GetAbsOrigin() : v3(f.x, f.y, f.z), r: f.r || 350, owner: 0, prog: 0, capTeam: 0, n: { 2: 0, 3: 0 }, contested: false });
    fire("mv_flagpole_" + f.id, "Skin", 0);
  }
}
function flagById(id) { for (const f of flags) if (f.id === id) return f; return undefined; }
function startGame() {
  const C = CONFIG.CONQUEST;
  game.tickets[T] = C.TICKETS; game.tickets[CT] = C.TICKETS; game.bleed[T] = 0; game.bleed[CT] = 0; game.bleeding[T] = false; game.bleeding[CT] = false;
  game.start = TNOW; game.over = false; game.overAt = 0; game.winner = 0; game.fallback = 0; game.flagAt = 0;
  Console.ServerCommand("mp_ignore_round_win_conditions 1");
  try { GameRules.SetRoundRemainingTime(C.ROUND_SECONDS + 15); } catch (e) {}
}
function captureFlag(f, team) {
  const prev = f.owner;
  f.owner = team; f.prog = 0; f.capTeam = 0;
  fire("mv_flagpole_" + f.id, "Skin", team === T ? 1 : 2);
  fire("mv_flag_snd_" + f.id, "StartSound");                 // optional entity (not in CONTRACT): mv.capture at the pole
  stats.captures++;
  const text = TEAM_NAME[team] + " took " + f.id.toUpperCase() + " " + f.name.toUpperCase();
  for (const p of players.values()) {
    if (p.bot) continue;
    toast(p, p.team === team ? text : prev === p.team ? "We lost " + f.id.toUpperCase() + " " + f.name.toUpperCase() : text, 4);
    if (p.team === team && p.here === f.id) p.merit++;
  }
  log(text);
}
function tickFlags(dt) {
  const C = CONFIG.CONQUEST;
  for (const f of flags) { f.n[T] = 0; f.n[CT] = 0; }
  for (const r of roster) {
    r.p.here = "";
    if (!r.alive || r.seated || !r.p.deployed || (r.team !== T && r.team !== CT)) continue;
    for (const f of flags) {
      if (Math.abs(r.pos.z - f.pos.z) > C.CAP_HEIGHT || dist2(r.pos, f.pos) > f.r) continue;
      f.n[r.team]++; r.p.here = f.id; break;
    }
  }
  if (game.over) return;
  for (const f of flags) {
    const a = Math.min(C.CAPTURE_MAX, f.n[T]), b = Math.min(C.CAPTURE_MAX, f.n[CT]);
    f.contested = a > 0 && b > 0;
    if (f.contested) continue;                               // frozen
    const team = a > 0 ? T : b > 0 ? CT : 0, cnt = Math.max(a, b);
    if (team && f.owner !== team) {
      if (f.capTeam && f.capTeam !== team && f.prog > 0) { f.prog -= cnt * dt / C.CAPTURE_SECONDS; if (f.prog <= 0) { f.prog = 0; f.capTeam = team; } }
      else { f.capTeam = team; f.prog += cnt * dt / C.CAPTURE_SECONDS; if (f.prog >= 1) captureFlag(f, team); }
    } else if (f.prog > 0) {
      f.prog = Math.max(0, f.prog - (team ? 3 : 1) * C.DECAY * dt);
      if (f.prog <= 0) f.capTeam = 0;
    }
  }
}
function loseTicket(team, n) {
  if (game.over || (team !== T && team !== CT)) return;
  game.tickets[team] = Math.max(0, game.tickets[team] - n);
}
function tickTickets(dt) {
  const C = CONFIG.CONQUEST;
  if (game.over) { tickRoundEnd(); return; }
  game.held[T] = 0; game.held[CT] = 0;
  for (const f of flags) if (f.owner) game.held[f.owner]++;
  for (const team of TEAMS) {
    const enemy = otherTeam(team), n = game.held[team];
    game.bleeding[enemy] = n >= C.BLEED_FLAGS;
    if (n < C.BLEED_FLAGS) continue;
    game.bleed[enemy] += (n - (C.BLEED_FLAGS - 1)) * dt / C.BLEED_SECONDS;
    if (game.bleed[enemy] >= 1) { const k = Math.floor(game.bleed[enemy]); game.bleed[enemy] -= k; loseTicket(enemy, k); }
  }
  if (game.tickets[T] <= 0 || game.tickets[CT] <= 0 || TNOW - game.start >= C.ROUND_SECONDS) endGame();
}
function endGame() {
  const C = CONFIG.CONQUEST;
  let w = game.tickets[T] > game.tickets[CT] ? T : game.tickets[CT] > game.tickets[T] ? CT : 0;
  if (!w && game.held[T] !== game.held[CT]) w = game.held[T] > game.held[CT] ? T : CT;
  game.over = true; game.overAt = TNOW; game.winner = w; game.fallback = 0; game.rounds++;
  game.reason = w === T ? CSRoundEndReason.TERRORISTS_WIN : w === CT ? CSRoundEndReason.CTS_WIN : CSRoundEndReason.DRAW;
  const text = w ? TEAM_NAME[w] + " HOLD THE VALLEY" : "STALEMATE";
  const sub = TEAM_NAME[T] + " " + game.tickets[T] + "  -  " + TEAM_NAME[CT] + " " + game.tickets[CT] + " tickets";
  for (const p of players.values()) if (!p.bot) banner(p, text, sub, 12);
  log("round over: " + text + " (" + sub + ")");
  Console.ServerCommand("mp_ignore_round_win_conditions 0");
  try { if (w) GameRules.AddTeamScore(w, 1); } catch (e) {}
  try { GameRules.TerminateRound(game.reason, C.END_DELAY); } catch (e) { log("TerminateRound failed: " + e); }
}
// CS2 did not start a new round (warmup, a plugin): ask the map parameters entity, then restart the script's own round
function tickRoundEnd() {
  const C = CONFIG.CONQUEST, dtEnd = TNOW - game.overAt;
  if (game.fallback === 0 && dtEnd > C.RESTART_FALLBACK) {
    game.fallback = 1;
    log("no new round " + C.RESTART_FALLBACK + " s after TerminateRound: firing FireWinCondition at " + CONFIG.PARAMS);
    fire(CONFIG.PARAMS, "FireWinCondition", game.reason);
    try { GameRules.SetRoundRemainingTime(1); } catch (e) {}
  }
  if (game.fallback === 1 && dtEnd > C.SELF_RESET) {
    game.fallback = 2;
    log("still no new round: the script restarts its own");
    resetRound(true);
  }
}
