// mech minigames: CONFIG.minigames = [{ kind: "gallery" | "race" | "collect", name, ... }]
//   gallery: targets <name>_t0.._t<n-1> (func_breakable / func_button / prop with an output -> RunScriptInput "<name>_hit_<k>");
//            "<name>_start" (a button) starts a round of `seconds`; `up` targets show at a time (Enable / Disable inputs, or
//            `show` / `hide` input names); a hit scores and swaps the target; the best score is kept in the save data.
//   race:    checkpoint triggers -> RunScriptInput "<name>_cp_<k>" (k = 0 start .. n-1 finish), in order, per player; best time kept.
//   collect: pickups -> RunScriptInput "<name>_get_<k>"; each pickup counts once per player; all n -> "<name>_done" relay fired.
// HUD variables: <name>_score, <name>_time, <name>_best, msg. Ported from cs2-map-mcp's minigames.py + data/minigames/game.js (Rmgs123,
// MIT): shooting gallery, race and collect games; fresh code on create/mech/core.js.

function mgBest(key) { try { return JSON.parse(Instance.GetSaveData() || "{}")[key]; } catch (e) { return undefined; } }
function mgSaveBest(key, value) {
  let d = {};
  try { d = JSON.parse(Instance.GetSaveData() || "{}"); } catch (e) { d = {}; }
  d[key] = value; Instance.SetSaveData(JSON.stringify(d));
}

function minigamesInstall() {
  for (const g of CONFIG.minigames || []) {
    if (g.kind === "gallery") galleryInstall(g);
    else if (g.kind === "race") raceInstall(g);
    else if (g.kind === "collect") collectInstall(g);
    else throw new Error("unknown minigame " + g.kind);
  }
}

function galleryInstall(g) {
  const n = g.targets || 6, up = Math.min(g.up || 2, n), show = g.show || "Enable", hide = g.hide || "Disable";
  const S = { running: false, end: 0, score: 0, active: new Set(), player: -1 };
  const tname = (k) => g.name + "_t" + k;
  function pop() {
    const idle = [];
    for (let k = 0; k < n; k++) if (!S.active.has(k)) idle.push(k);
    if (!idle.length) return;
    const k = idle[Math.floor(Math.random() * idle.length)];
    S.active.add(k); fire(tname(k), show);
  }
  function stop() {
    S.running = false;
    for (const k of S.active) fire(tname(k), hide);
    S.active.clear();
    const best = mgBest(g.name) || 0;
    if (S.score > best) { mgSaveBest(g.name, S.score); hudAll(g.name + "_best", S.score); say("New record: " + S.score); }
    else say("Score " + S.score + " (best " + best + ")");
  }
  onStart(() => { S.running = false; S.active.clear(); for (let k = 0; k < n; k++) fire(tname(k), hide); hudAll(g.name + "_best", mgBest(g.name) || 0); });
  Instance.OnScriptInput(g.name + "_start", (d) => {
    if (S.running) return;
    S.running = true; S.end = MECH.now + (g.seconds || 30); S.score = 0;
    S.player = d.activator && d.activator.IsValid() ? pawnSlot(d.activator) : -1;
    for (let k = 0; k < up; k++) pop();
    say("Shoot the targets!");
  });
  for (let k = 0; k < n; k++) {
    Instance.OnScriptInput(g.name + "_hit_" + k, () => {
      if (!S.running || !S.active.has(k)) return;
      S.active.delete(k); fire(tname(k), hide); S.score++; pop();
    });
  }
  every((now) => {
    if (!S.running) return;
    hudAll(g.name + "_score", S.score);
    hudAll(g.name + "_time", Math.max(0, Math.ceil(S.end - now)));
    if (now >= S.end) stop();
  });
}

function raceInstall(g) {
  const n = g.checkpoints || 2;
  for (let k = 0; k < n; k++) {
    Instance.OnScriptInput(g.name + "_cp_" + k, (d) => {
      const pawn = d.activator;
      if (!pawn || !pawn.IsValid() || !pawn.GetPlayerController) return;
      const slot = pawnSlot(pawn); if (slot < 0) return;
      const st = slotState(slot), r = st[g.name] || (st[g.name] = { next: 0, start: 0 });
      if (k === 0) { r.next = 1; r.start = MECH.now; hudSet(slot, "msg", "Go!"); return; }
      if (k !== r.next) return;                                   // out of order: ignored
      r.next++;
      if (k === n - 1) {
        const t = MECH.now - r.start; r.next = 0;
        const best = mgBest(g.name);
        if (best === undefined || t < best) { mgSaveBest(g.name, t); hudAll(g.name + "_best", t.toFixed(2)); }
        hudSet(slot, "msg", "Finished in " + t.toFixed(2) + " s");
      } else hudSet(slot, "msg", "Checkpoint " + k + "/" + (n - 1));
    });
  }
  every((now) => {
    for (const pl of mechPlayers()) {
      const r = slotState(pl.slot)[g.name];
      if (r && r.next > 0) hudSet(pl.slot, g.name + "_time", (now - r.start).toFixed(1));
    }
  });
}

function collectInstall(g) {
  const n = g.items || 5;
  for (let k = 0; k < n; k++) {
    Instance.OnScriptInput(g.name + "_get_" + k, (d) => {
      const slot = d.activator && d.activator.IsValid() ? pawnSlot(d.activator) : -1; if (slot < 0) return;
      const st = slotState(slot), got = st[g.name] || (st[g.name] = new Set());
      if (got.has(k)) return;
      got.add(k); hudSet(slot, g.name + "_score", got.size + "/" + n);
      if (g.shared) fire(g.name + "_i" + k, "Disable");
      if (got.size === n) { hudSet(slot, "msg", "All " + n + " found!"); fire(g.name + "_done", "Trigger"); }
    });
  }
  onStart(() => { for (const st of MECH.state.values()) delete st[g.name]; });
}
