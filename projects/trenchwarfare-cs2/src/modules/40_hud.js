// 40_hud: HUD: per-player cache (only changes are sent), toast, info card, role cards, banner, front headlines (docs/HUD.md)

// ------------------------------------------------------------------ HUD (per-player cache, only changes are sent)
let hudEnt;
function hud() {
  if (live(hudEnt)) return hudEnt;
  hudEnt = byName(CONFIG.HUD);
  return hudEnt;
}
// one record per panel id and player ({ t: text, c: class -> on, s: group -> class }): no key strings are built per call (they were
// 40 % of the script's time at 64 players, as monsoon found)
function hrec(p, id) { let r = p.hud.get(id); if (!r) { r = { t: undefined, c: {}, s: {} }; p.hud.set(id, r); } return r; }
function hText(p, id, text) {
  if (p.bot) return;                  // bots have no screen (and it costs script time)
  text = String(text === undefined || text === null ? "" : text);
  const r = hrec(p, id);
  if (r.t === text) return;
  const h = hud(); if (!h) return;
  h.SetDialogVariableStringForPlayer(p.slot, id, "v", text);
  r.t = text;
}
function hClass(p, id, cls, on) {
  if (p.bot) return;
  const r = hrec(p, id);
  if (r.c[cls] === on) return;
  const h = hud(); if (!h) return;
  h.SetHasClassForPlayer(p.slot, id, cls, on);
  r.c[cls] = on;
}
function hSwap(p, id, group, cls) {   // one class per group (marker positions, map picture)
  if (p.bot) return;
  const r = hrec(p, id);
  const old = r.s[group];
  if (old === cls) return;
  const h = hud(); if (!h) return;
  if (old) h.SetHasClassForPlayer(p.slot, id, old, false);
  if (cls) h.SetHasClassForPlayer(p.slot, id, cls, true);
  r.s[group] = cls;
}
function hudReset(p) { const h = hud(); if (h) { try { h.ResetForPlayer(p.slot); } catch (e) {} } p.hud.clear(); }
function toast(p, text, secs) { hText(p, "tw_toast_text", text); p.toastUntil = now() + (secs || 3); }
function info(p, title, lines, foot, secs) {
  hText(p, "tw_info_title", title);
  for (let k = 0; k < 5; k++) hText(p, "tw_info_l" + (k + 1), lines[k] || "");
  hText(p, "tw_info_foot", foot || "");
  p.infoUntil = now() + (secs || 9);
}
function roleCard(p, role) {
  const team = p.team === T || p.team === CT ? p.team : CT;
  if (role === "infantry") return info(p, "RIFLEMAN", [CONFIG.RIFLE_NAME[team], "Hold the fire trench.", "Kill streaks earn better weapons.",
    "[SHIFT+E] or !swap: change weapon."], "Assigned from your next deployment.");
  if (role === "mortar") return info(p, "MORTAR CREW", ["Two to a tube.", "[E] at the plotting table, [WASD] to aim.", "[MOUSE 1] set target, [SPACE] fire.", "[E] at the ammo box for a round."],
    "Assigned from your next deployment, if a post is free.");
  if (role === "air") return info(p, "PILOT", ["!air to volunteer.", "[MOUSE] steer, [W/S] throttle, [A/D] roll.", "[MOUSE 1] guns, [MOUSE 2] bomb.", "Two sorties, then back to the line."],
    CONFIG.AIR_ENABLED ? "Volunteered. You're first in line for the next aircraft." : "No aircraft on this front yet.");
}
function banner(p, title, sub, secs) { hText(p, "tw_banner_title", title); hText(p, "tw_banner_sub", sub); p.bannerUntil = now() + (secs || 5); }
// a front-wide headline ("THE WAY TO THE WOOD IS OPEN - ladder at the north end..."): the part before " - " is the title, the rest
// (first letter raised) the line under it; bots are skipped by hText
function headline(p, msg, secs) {
  const i = String(msg).indexOf(" - ");
  const sub = i < 0 ? "" : msg.slice(i + 3);
  banner(p, i < 0 ? msg : msg.slice(0, i), sub.charAt(0).toUpperCase() + sub.slice(1), secs);
}
