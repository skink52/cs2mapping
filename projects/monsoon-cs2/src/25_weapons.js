// ------------------------------------------------------------------ 25_weapons: requisition points, the armory, earned upgrades
// (playtest 1, finding 19; docs/WEAPONS.md). Kills, assists, captures and the support jobs earn REQ; REQ unlocks an optional upgrade
// for the rest of the round: a primary (an `unlock` kit: carbine, shotgun, sniper) or a perk (the frag pouch). Unlocks are side-neutral
// (the same unlock gives the other side's weapon), so they survive a team switch; deaths keep them; a new round clears them and keeps
// CARRY points; a disconnected player's points and unlocks wait KEEP s under his name; a script reload carries them (90_main).
const reqLedger = new Map();                     // player name -> { rq, unlocks: [ids], round, at }
const armoryHelpAt = new Map();                  // slot -> last time the !armory list went to chat

function unlockOf(word) {
  const w = String(word || "").toLowerCase().replace(/[^a-z0-9]/g, "");
  if (CONFIG.UNLOCKS[w]) return w;
  const a = CONFIG.UNLOCK_ALIAS[w]; return a && CONFIG.UNLOCKS[a] ? a : "";
}
// the unlock that opens a kit (kits without `unlock` are free)
function kitUnlockId(kit) { for (const id of CONFIG.UNLOCK_ORDER) { const U = CONFIG.UNLOCKS[id]; if (U && U.kit === kit) return id; } return ""; }
function kitOpen(p, kit) { const K = CONFIG.KITS[kit]; if (!K) return false; if (!K.unlock) return true; const id = kitUnlockId(kit); return !!id && p.unlocks.has(id); }
// what the upgrade is called for this player's side ("SNIPER - M21")
function unlockName(id, team) {
  const U = CONFIG.UNLOCKS[id]; if (!U) return id.toUpperCase();
  if (U.kit) { const K = CONFIG.KITS[U.kit]; return U.label + " - " + (K.name[team] || K.name[CT]); }
  return U.label + " - " + (U.name[team] || U.name[CT]);
}
// an upgrade carried this life (a man worth a bounty): an unlock kit in hand or the frag pouch
function carriesUpgrade(p) { return !!p && (!!(CONFIG.KITS[p.kit] && CONFIG.KITS[p.kit].unlock) || p.unlocks.has("grenades")); }

// ------------------------------------------------------------------ earning
// catch-up: the side well behind on tickets earns more (no runaway snowball: points do not multiply with a streak)
function reqMult(team) {
  const R = CONFIG.REQ, o = otherTeam(team);
  return game.tickets[o] - game.tickets[team] >= R.BEHIND ? R.BEHIND_MULT : 1;
}
function reqEarn(p, n, why) {
  const R = CONFIG.REQ;
  if (!R.ON || !p || (p.team !== T && p.team !== CT) || !(n > 0)) return 0;
  const before = p.rq;
  p.rq = Math.min(R.CAP, p.rq + Math.round(n * reqMult(p.team)));
  const got = p.rq - before;
  if (got <= 0) { stats.reqCapped++; return 0; }
  stats.reqEarned += got; stats.reqBy[why] = (stats.reqBy[why] || 0) + got;
  p.rqGain = got; p.rqGainUntil = TNOW + 2.5; p.rqDrawAt = 0;
  return got;
}
// damage taken from each enemy (OnPlayerDamage), for the assist share of a kill
function reqDamage(vp, as, dmg) {
  if (!vp || as < 0 || as === vp.slot || !(dmg > 0)) return;
  const e = vp.dmgBy.get(as);
  if (e && TNOW - e.at <= CONFIG.REQ.ASSIST_TIME) { e.d += dmg; e.at = TNOW; } else vp.dmgBy.set(as, { d: dmg, at: TNOW });
}
// a kill: the killer's points (+ the bounty on a man carrying an upgrade), the assists
function reqKill(vp, a) {
  const R = CONFIG.REQ;
  if (a) reqEarn(a, R.KILL + (carriesUpgrade(vp) ? R.BOUNTY : 0), "kill");
  if (vp) {
    for (const [s, e] of vp.dmgBy) {
      if ((a && s === a.slot) || TNOW - e.at > R.ASSIST_TIME || e.d < R.ASSIST_DMG) continue;
      const q = players.get(s);
      if (q && q.team && q.team !== vp.team) { if (reqEarn(q, R.ASSIST, "assist")) stats.assists++; }
    }
    vp.dmgBy.clear();
  }
}

// ------------------------------------------------------------------ spending
// buy (or pick again) an upgrade. atRack: the player stands at a kit station (or is in the briefing room): a primary is issued now.
function reqBuy(p, id, pawn, atRack) {
  const U = CONFIG.UNLOCKS[id];
  if (!U || (p.team !== T && p.team !== CT)) { toast(p, "!armory lists the upgrades", 3); return false; }
  if (!CONFIG.REQ.ON) { toast(p, "The armory is closed on this server", 3); return false; }
  const owned = p.unlocks.has(id);
  if (!owned) {
    if (p.rq < U.cost) { stats.reqDenied++; toast(p, U.label + ": " + U.cost + " REQ (you have " + p.rq + ")", 3); return false; }
    if (U.kit && !kitFree(p, U.kit)) { stats.reqDenied++; toast(p, U.label + ": all " + kitLimit(p.team, U.kit) + " issued on your side", 3); return false; }
    p.rq -= U.cost; p.unlocks.add(id); p.rqDrawAt = 0;
    stats.unlocks++; stats.unlockBy[id] = (stats.unlockBy[id] || 0) + 1;
    if (!p.bot) log("requisition: " + nameOf(p.slot) + " " + id + " for " + U.cost + " (left " + p.rq + ")");
  }
  let alive = false; try { alive = !!pawn && pawn.IsAlive(); } catch (e) {}
  const onFoot = alive && p.deployed && p.role === "infantry" && !p.heli && p.mount < 0 && !p.board;
  if (U.kit) {
    if (p.role !== "infantry") { p.kitNext = U.kit; toast(p, unlockName(id, p.team) + (owned ? "" : " unlocked") + ": yours as infantry (!infantry)", 4); return true; }
    if (onFoot && !atRack) { p.kitNext = p.kit === U.kit ? "" : U.kit; toast(p, unlockName(id, p.team) + (owned ? "" : " unlocked") + ": issued at a rack or your next deploy", 4); return true; }
    if (!setKit(p, onFoot ? pawn : undefined, U.kit, true)) p.kitNext = U.kit;
    if (!owned) banner(p, "REQUISITIONED", unlockName(id, p.team) + "  -  yours until the round ends", 4);
    return true;
  }
  // a perk: the pouch is filled now at a rack, else at the next deploy
  if (owned) { toast(p, unlockName(id, p.team) + ": yours this round, filled at every deploy", 3); return true; }
  if (onFoot && atRack) givePerks(p, pawn);
  banner(p, "REQUISITIONED", unlockName(id, p.team) + (onFoot && atRack ? "" : "  -  from your next deploy"), 4);
  return true;
}
// the frag pouch: a frag and a smoke (CS2's default grenade limit is one of each)
function givePerks(p, pawn) {
  if (p.role !== "infantry" || !p.unlocks.has("grenades")) return;
  for (const c of CONFIG.UNLOCKS.grenades.give) give(pawn, c, false);
}
// bots: one upgrade at deploy when they can pay for it (WEAPONS.md "Bots"); AI pilots / gunners / crews and the MG / AT bots keep theirs
function botBuy(p, pawn) {
  const B = CONFIG.BOT_BUY;
  if (!B.ON || !CONFIG.REQ.ON || !p.bot || p.aiRole || p.role !== "infantry") return;
  const picks = B.PICKS;
  for (let k = 0; k < picks.length; k++) {
    const id = picks[((p.slot >> 1) + k) % picks.length], U = CONFIG.UNLOCKS[id];
    if (!U) continue;
    if (p.unlocks.has(id)) { if (U.kit && p.kit === "rifle" && kitFree(p, U.kit)) p.kit = U.kit; return; }
    if (p.rq < U.cost) return;                                          // saves up for its pick (no hopping to a cheaper one)
    if (U.kit && (p.kit !== "rifle" || !kitFree(p, U.kit))) continue;
    if (id === "sniper" && teamCount(p.team, (q) => q.bot && q !== p && q.unlocks.has("sniper")) >= B.SNIPERS) continue;
    p.rq -= U.cost; p.unlocks.add(id); stats.unlocks++; stats.unlockBy[id] = (stats.unlockBy[id] || 0) + 1; stats.botBuys++;
    if (U.kit) p.kit = U.kit;
    return;
  }
}

// ------------------------------------------------------------------ the armory card (the info card) and the REQ row
// at a rack: F opens the card and steps through it, E requisitions (or takes) the highlighted line; walking off closes it
function armoryLines(p) {
  return CONFIG.UNLOCK_ORDER.map((id, i) => {
    const U = CONFIG.UNLOCKS[id], mark = p.armory && i === p.armSel ? "> " : "   ";
    const K = U.kit ? CONFIG.KITS[U.kit] : null, nm = K ? K.name[p.team] : U.name[p.team];
    return mark + U.label + "  " + nm + "  " + (p.unlocks.has(id) ? "OWNED" : U.cost);
  });
}
function drawArmory(p, atRack) {
  info(p, "ARMORY   REQ " + p.rq, armoryLines(p), atRack ? "[F] next   [E] requisition" : "At a rack: F opens this.  !armory <name>", atRack ? 3 : 12);
}
function armoryChat(p) {
  if (p.bot || TNOW - (armoryHelpAt.get(p.slot) || -99) < 20) return;
  armoryHelpAt.set(p.slot, TNOW);
  sayLater("[mv] armory (" + nameOf(p.slot) + ", REQ " + p.rq + "): " + CONFIG.UNLOCK_ORDER.map((id) => id + " " + CONFIG.UNLOCKS[id].cost).join(", ") +
           ".  !armory <name> buys; kills, assists and captures earn REQ");
}
// on foot at a kit station: returns the prompt, or "" to leave the kit prompt as it is. pressed = new keys this tick.
function tickArmory(p, pawn, pressed) {
  const order = CONFIG.UNLOCK_ORDER;
  // F is a tap (the inspect key): the edge from the per-tick key read, or CS2's own "pressed during this tick" for a tap shorter than a tick
  let f = (pressed & CSInputs.LOOK_AT_WEAPON) !== 0;
  if (!f) { try { f = pawn.WasInputJustPressed(CSInputs.LOOK_AT_WEAPON); } catch (e) {} }
  if (f) {
    if (!p.armory) { p.armory = true; stats.armoryOpens++; const i = order.findIndex((id) => !p.unlocks.has(id) && CONFIG.UNLOCKS[id].cost <= p.rq); p.armSel = i >= 0 ? i : 0; }
    else p.armSel = (p.armSel + 1) % order.length;
  }
  if (!p.armory) return "";
  drawArmory(p, true);
  const id = order[p.armSel], U = CONFIG.UNLOCKS[id];
  if (pressed & CSInputs.USE) { reqBuy(p, id, pawn, true); drawArmory(p, true); }
  if (p.unlocks.has(id)) return U.kit ? (p.kit === U.kit ? U.label + ": in your hands" : "[E] Take the " + CONFIG.KITS[U.kit].name[p.team]) : U.label + ": filled at every deploy";
  return p.rq >= U.cost ? "[E] Requisition " + U.label + " (" + U.cost + ")" : U.label + ": " + U.cost + " REQ (you have " + p.rq + ")";
}
function closeArmory(p) { if (!p.armory) return; p.armory = false; p.infoUntil = 0; }
// the REQ row under the status box: points (+ the last gain for a moment), and what they buy next
function drawReq(p) {
  if (p.bot || !hudHas("mv_req")) return;
  if (TNOW < p.rqDrawAt) return;
  p.rqDrawAt = TNOW + CONFIG.REQ.SHOW_EVERY / 64;
  const on = CONFIG.REQ.ON && (p.team === T || p.team === CT);
  hClass(p, "mv_req", "show", on);
  if (!on) return;
  hText(p, "mv_req_pts", "REQ " + p.rq + (TNOW < p.rqGainUntil ? "  +" + p.rqGain : ""));
  let next = "", ready = false;
  for (const id of CONFIG.UNLOCK_ORDER) {
    const U = CONFIG.UNLOCKS[id]; if (p.unlocks.has(id)) continue;
    if (U.cost <= p.rq) { ready = true; next = U.label + " READY  -  F at a rack"; break; }
    if (!next) next = U.label + " IN " + (U.cost - p.rq);
  }
  if (!next) next = "ALL UPGRADES YOURS";
  hText(p, "mv_req_next", next);
  hClass(p, "mv_req", "ready", ready);
}

// ------------------------------------------------------------------ keeping it: rounds, disconnects (reload: 90_main)
function reqNewRound(p) {
  p.unlocks.clear(); p.rq = Math.min(p.rq, CONFIG.REQ.CARRY); p.dmgBy.clear(); p.armory = false; p.rqDrawAt = 0;
  if (CONFIG.KITS[p.kit] && CONFIG.KITS[p.kit].unlock) p.kit = "rifle";
  if (p.kitNext && CONFIG.KITS[p.kitNext] && CONFIG.KITS[p.kitNext].unlock) p.kitNext = "";
}
function reqRemember(p) {
  if (p.bot || !p.name || (!p.rq && !p.unlocks.size)) return;
  reqLedger.set(p.name, { rq: p.rq, unlocks: [...p.unlocks], round: stats.rounds, at: TNOW });
  for (const [k, v] of reqLedger) if (TNOW - v.at > CONFIG.REQ.KEEP) reqLedger.delete(k);
}
function reqRestore(p) {
  if (p.bot || !p.name) return;
  const e = reqLedger.get(p.name); if (!e) return;
  reqLedger.delete(p.name);
  if (TNOW - e.at > CONFIG.REQ.KEEP) return;
  const same = e.round === stats.rounds;
  p.rq = Math.min(CONFIG.REQ.CAP, same ? e.rq : Math.min(e.rq, CONFIG.REQ.CARRY));
  if (same) for (const id of e.unlocks) if (CONFIG.UNLOCKS[id]) p.unlocks.add(id);
  stats.ledgerRestores++;
  log("requisition: " + p.name + " back: " + p.rq + " REQ, " + p.unlocks.size + " unlocks");
}
