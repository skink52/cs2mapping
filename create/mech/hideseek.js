// mech hide and seek: CONFIG.hideseek = { hiders: 2, seekers: 3, hide_seconds: 30, models: ["models/...vmdl", ...], seek_seconds: 180,
//   hiders_win: "hs_hiders_win", seekers_win: "hs_seekers_win", miss_damage: 5 }
// Round start: hiders get a random prop model (USE swaps it for the next one in the list); seekers are held where they stand for
// hide_seconds; then they hunt. A seeker shooting and hitting no player loses miss_damage HP (prop hunt's rule). When every hider is
// dead the seekers_win relay fires; when the seek time runs out the hiders_win relay fires (mechkit wires both to an
// info_map_parameters FireWinCondition). HUD: hs_phase, hs_time, hs_left. Ported from cs2-map-mcp's hideseek.py + data/hideseek/hideseek.js
// (Rmgs123, MIT); fresh code on create/mech/core.js.

function hideseekInstall() {
  const H = CONFIG.hideseek; if (!H) return;
  const models = H.models || [];
  const S = { phase: "idle", until: 0, hold: new Map(), done: false };
  function begin() {
    S.phase = "hide"; S.until = MECH.now + (H.hide_seconds || 30); S.hold.clear(); S.done = false;
    for (const pl of mechPlayers(H.hiders !== undefined ? H.hiders : 2)) {
      const st = slotState(pl.slot); st.hsModel = Math.floor(Math.random() * Math.max(1, models.length));
      if (models.length) pl.pawn.SetModel(models[st.hsModel]);
    }
    for (const pl of mechPlayers(H.seekers !== undefined ? H.seekers : 3)) S.hold.set(pl.slot, pl.pawn.GetAbsOrigin());
    say("Hide! Seekers are released in " + (H.hide_seconds || 30) + " s");
  }
  onStart(begin);
  Instance.OnGunFire((e) => {
    if (S.phase !== "seek" || !H.miss_damage) return;
    const owner = e.weapon.GetOwner();
    if (!owner || !owner.IsValid() || owner.GetTeamNumber() !== (H.seekers !== undefined ? H.seekers : 3)) return;
    slotState(pawnSlot(owner)).hsShot = MECH.now;
  });
  Instance.OnPlayerDamage((e) => {
    const a = e.attacker;
    if (a && a.IsValid && a.IsValid() && a.GetPlayerController) slotState(pawnSlot(a)).hsHit = MECH.now;
  });
  every((now) => {
    if (S.phase === "idle") return;
    const hiders = mechPlayers(H.hiders !== undefined ? H.hiders : 2);
    hudAll("hs_left", hiders.length);
    hudAll("hs_phase", S.phase === "hide" ? "Hide" : "Seek");
    hudAll("hs_time", Math.max(0, Math.ceil(S.until - now)));
    for (const pl of hiders) {
      if (models.length > 1 && pl.pawn.WasInputJustPressed(CSInputs.USE)) {
        const st = slotState(pl.slot); st.hsModel = (st.hsModel + 1) % models.length; pl.pawn.SetModel(models[st.hsModel]);
      }
    }
    if (S.phase === "hide") {
      for (const pl of mechPlayers(H.seekers !== undefined ? H.seekers : 3)) {
        const at = S.hold.get(pl.slot);
        if (at) pl.pawn.Teleport({ position: at, velocity: vec(0, 0, 0) });
      }
      if (now >= S.until) { S.phase = "seek"; S.until = now + (H.seek_seconds || 180); say("Seekers released!"); }
      return;
    }
    for (const pl of mechPlayers(H.seekers !== undefined ? H.seekers : 3)) {        // a shot that hit no player costs HP
      const st = slotState(pl.slot);
      if (st.hsShot && now - st.hsShot > 0.1) {
        if (!(st.hsHit >= st.hsShot)) pl.pawn.TakeDamage({ damage: H.miss_damage });
        st.hsShot = 0;
      }
    }
    if (!S.done && hiders.length === 0) { S.done = true; S.phase = "idle"; fire(H.seekers_win || "hs_seekers_win", "Trigger"); say("Seekers win"); }
    else if (!S.done && now >= S.until) { S.done = true; S.phase = "idle"; fire(H.hiders_win || "hs_hiders_win", "Trigger"); say("Hiders win"); }
  });
}
