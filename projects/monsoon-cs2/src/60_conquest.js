// ------------------------------------------------------------------ 60_conquest: flags, tickets, bleed, round end (DESIGN 3.4)
const flags = [];
const game = { tickets: { 2: 0, 3: 0 }, bleed: { 2: 0, 3: 0 }, bleeding: { 2: false, 3: false }, held: { 2: 0, 3: 0 }, start: 0, over: false, overAt: 0, winner: 0,
               reason: 0, fallback: 0, flagAt: 0, rounds: 0, low: { 2: 0, 3: 0 } };
function loadFlags() {
  flags.length = 0;
  for (const f of LAYOUT.flags) {
    // the capture circle is centred on the flag's marker; without it on the pole (what a player walks to), the layout point last
    const e = need("mv_flag_" + f.id), pole = need("mv_flagpole_" + f.id);
    let pos = v3(f.x, f.y, f.z), from = "layout";
    try { if (e) { pos = e.GetAbsOrigin(); from = "mv_flag_" + f.id; } else if (pole) { pos = pole.GetAbsOrigin(); from = "pole"; } } catch (err) {}
    flags.push({ id: f.id, name: f.name, pos, r: f.r || 350, owner: 0, prog: 0, capTeam: 0, n: { 2: 0, 3: 0 }, contested: false, underAt: -99, changes: 0,
                 pole, pose: -1, poseF: 0, skin: -1, seen: false });
    log("flag " + f.id.toUpperCase() + " at " + Math.round(pos.x) + " " + Math.round(pos.y) + " " + Math.round(pos.z) + " (" + from + "), radius " + (f.r || 350));
  }
  for (const f of flags) drawPole(f, true);
}
// the flag on its pole: which team's cloth, and how high (pose 0 = at the foot, POSES-1 = at the top). The owner's flag comes down over
// the first half of an enemy capture and the taker's goes up over the second, so it reaches the top in the taker's colour at the flip;
// a neutral flag hangs at the foot in white until someone raises theirs. The cloth travels at most POSE_RATE poses a second.
function poleTarget(f) {
  const top = CONFIG.CONQUEST.POSES - 1, p = clampN(f.prog, 0, 1);
  if (!f.owner) return { skin: f.capTeam && p > 0 ? f.capTeam : 0, pose: Math.round(top * p) };
  if (!f.capTeam || f.capTeam === f.owner || p <= 0) return { skin: f.owner, pose: top };
  if (CONFIG.CONQUEST.NEUTRAL_FIRST) return { skin: f.owner, pose: Math.round(top * (1 - p)) };
  return p < 0.5 ? { skin: f.owner, pose: Math.round(top * (1 - 2 * p)) } : { skin: f.capTeam, pose: Math.round(top * (2 * p - 1)) };
}
function drawPole(f, snap, dt) {
  const C = CONFIG.CONQUEST, want = poleTarget(f);
  if (snap || f.pose < 0) f.poseF = want.pose;
  else {
    const step = C.POSE_RATE * (dt || C.TICK);
    // a colour change happens at the foot of the pole: the old cloth goes all the way down first
    const goal = want.skin !== f.skin && f.skin >= 0 ? 0 : want.pose;
    f.poseF += clampN(goal - f.poseF, -step, step);
  }
  let skin = f.skin;
  if (snap || f.skin < 0 || (want.skin !== f.skin && f.poseF <= 0.01)) skin = want.skin;
  const pose = Math.round(f.poseF);
  if (skin !== f.skin) { f.skin = skin; fire("mv_flagpole_" + f.id, "Skin", skin === T ? 1 : skin === CT ? 2 : 0); }
  if (pose !== f.pose) {
    f.pose = pose;
    const nm = "flag_" + (pose < 10 ? "0" : "") + pose;
    fire("mv_flagpole_" + f.id, C.POSE_ANIM, nm);
    fire("mv_flagpole_" + f.id, C.POSE_IDLE, nm);           // the prop returns to this pose whatever else plays
  }
}
function flagById(id) { for (const f of flags) if (f.id === id) return f; return undefined; }
function startGame() {
  const C = CONFIG.CONQUEST;
  game.tickets[T] = C.TICKETS; game.tickets[CT] = C.TICKETS; game.bleed[T] = 0; game.bleed[CT] = 0; game.bleeding[T] = false; game.bleeding[CT] = false;
  game.start = TNOW; game.over = false; game.overAt = 0; game.winner = 0; game.fallback = 0; game.flagAt = 0; game.low[T] = 0; game.low[CT] = 0;
  feedLines.length = 0;
  Console.ServerCommand("mp_ignore_round_win_conditions 1");
  try { GameRules.SetRoundRemainingTime(C.ROUND_SECONDS + 15); } catch (e) {}
}
// team = the side that filled the bar. With CONQUEST.NEUTRAL_FIRST an enemy flag only goes neutral and has to be filled again.
function captureFlag(f, team) {
  const prev = f.owner, label = f.id.toUpperCase() + " " + f.name.toUpperCase();
  const to = prev && prev !== team && CONFIG.CONQUEST.NEUTRAL_FIRST ? 0 : team;
  f.owner = to; f.prog = 0; f.capTeam = 0; f.changes++;
  fire("mv_flag_snd_" + f.id, "StartSound");                 // optional entity (not in CONTRACT): mv.capture at the pole
  if (CONFIG.CHAT.CAPTURES) sayLater("[mv] " + TEAM_NAME[team] + (to ? " took " : " neutralised ") + label + "   (" + TEAM_NAME[T] + " " + countHeld(T) + " / " + TEAM_NAME[CT] + " " + countHeld(CT) + " flags)");
  stats.captures++; stats.capturesBy[f.id] = (stats.capturesBy[f.id] || 0) + 1;
  if (to) { feed(team, "We took " + label, "good", true); feed(otherTeam(team), prev ? "We lost " + label : "The enemy took " + label, "bad", true); }
  else { feed(team, label + " neutralised", "good", true); feed(prev, "We lost " + label, "bad", true); }
  for (const p of players.values()) if (!p.bot && p.team === team && p.here === f.id) p.merit++;
  log(TEAM_NAME[team] + (to ? " took " : " neutralised ") + label);
}
function countHeld(team) { let n = 0; for (const q of flags) if (q.owner === team) n++; return n; }
function tickFlags(dt) {
  const C = CONFIG.CONQUEST;
  for (const f of flags) { f.n[T] = 0; f.n[CT] = 0; }
  for (const r of roster) {
    r.p.here = "";
    if (!r.alive || r.seated || !r.p.deployed || r.p.afk || (r.team !== T && r.team !== CT)) continue;
    for (const f of flags) {
      if (Math.abs(r.pos.z - f.pos.z) > C.CAP_HEIGHT || dist2(r.pos, f.pos) > f.r) continue;
      f.n[r.team]++; r.p.here = f.id;
      if (!f.seen && !r.bot) { f.seen = true; log("flag " + f.id.toUpperCase() + ": first human in the circle (slot " + r.slot + ", " + Math.round(dist2(r.pos, f.pos)) + " u from the pole)"); }
      break;
    }
  }
  if (game.over) { for (const f of flags) drawPole(f, false, dt); return; }
  for (const f of flags) {
    const a = Math.min(C.CAPTURE_MAX, f.n[T]), b = Math.min(C.CAPTURE_MAX, f.n[CT]);
    f.contested = a > 0 && b > 0;
    if (f.contested) continue;                               // frozen
    const team = a > 0 ? T : b > 0 ? CT : 0, cnt = Math.max(a, b);
    if (team && f.owner !== team) {
      if (f.capTeam && f.capTeam !== team && f.prog > 0) { f.prog -= cnt * dt / C.CAPTURE_SECONDS; if (f.prog <= 0) { f.prog = 0; f.capTeam = team; } }
      else {
        f.capTeam = team; f.prog += cnt * dt / C.CAPTURE_SECONDS;
        if (f.owner && TNOW - f.underAt > CONFIG.FEED.UNDER_ATTACK) { f.underAt = TNOW; feed(f.owner, f.id.toUpperCase() + " " + f.name.toUpperCase() + " is under attack", "bad", false); }
        if (f.prog >= 1) captureFlag(f, team);
      }
    } else if (f.prog > 0) {
      f.prog = Math.max(0, f.prog - (team ? 3 : 1) * C.DECAY * dt);
      if (f.prog <= 0) f.capTeam = 0;
    }
  }
  for (const f of flags) drawPole(f, false, dt);
}
function loseTicket(team, n) {
  if (game.over || (team !== T && team !== CT) || !(n > 0)) return;
  game.tickets[team] = Math.max(0, game.tickets[team] - n);
  const marks = CONFIG.FEED.TICKETS_LOW;
  while (game.low[team] < marks.length && game.tickets[team] <= marks[game.low[team]]) {
    const m = marks[game.low[team]++];
    if (game.tickets[team] > 0) { feed(team, "We are down to " + m + " tickets", "bad", false); feed(otherTeam(team), "The enemy is down to " + m + " tickets", "good", false); }
  }
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
    if (game.bleed[enemy] >= 1) { const k = Math.floor(game.bleed[enemy]); game.bleed[enemy] -= k; loseTicket(enemy, k); stats.bleedOn[enemy] += k; }
  }
  if (game.tickets[T] <= 0 || game.tickets[CT] <= 0 || TNOW - game.start >= C.ROUND_SECONDS) endGame();
}
function endGame() {
  const C = CONFIG.CONQUEST;
  let w = game.tickets[T] > game.tickets[CT] ? T : game.tickets[CT] > game.tickets[T] ? CT : 0;
  if (!w && game.held[T] !== game.held[CT]) w = game.held[T] > game.held[CT] ? T : CT;
  game.over = true; game.overAt = TNOW; game.winner = w; game.fallback = 0; game.rounds++;
  stats.results.push({ secs: Math.round(TNOW - game.start), winner: w, t: game.tickets[T], ct: game.tickets[CT], flags: flags.map((f) => f.changes).join("/") });
  if (stats.results.length > 50) stats.results.shift();
  game.reason = w === T ? CSRoundEndReason.TERRORISTS_WIN : w === CT ? CSRoundEndReason.CTS_WIN : CSRoundEndReason.DRAW;
  const text = w ? TEAM_NAME[w] + " HOLDS THE VALLEY" : "STALEMATE";
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
