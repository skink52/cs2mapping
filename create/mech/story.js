// mech story: a state machine from JSON. CONFIG.story = { start: "intro", steps: { <step>: {
//     text: "shown on the HUD (msg)", seconds: 60 (a countdown: hud story_time; when it runs out go to `timeout`), timeout: "<step>",
//     on: { "<script input>": "<next step>", ... },   (map triggers / buttons -> RunScriptInput <input> on the point_script)
//     do: [ { fire: "name", input: "Open", value: "", delay: 0 }, { teleport: [x, y, z] }, { give: "weapon_knife" }, { hp: 100 },
//           { end: "win" | "lose" } ] } } }
// Entering a step runs its `do` list; inputs that don't belong to the current step are ignored. The step name goes to the HUD (story_step).
// end: fires "story_win" / "story_lose" relays (mechkit wires them to round-end conditions). Ported from cs2-map-mcp's story.py
// (Rmgs123, MIT): stories from JSON -> script + HUD + entities; fresh code on create/mech/core.js.

function storyInstall() {
  const ST = CONFIG.story; if (!ST) return;
  const S = { step: null, until: 0 };
  const inputs = new Set();
  for (const name of Object.keys(ST.steps)) for (const inp of Object.keys(ST.steps[name].on || {})) inputs.add(inp);
  function enter(name) {
    const step = ST.steps[name];
    if (!step) throw new Error("story: no step " + name);
    S.step = name; S.until = step.seconds ? MECH.now + step.seconds : 0;
    hudAll("story_step", name);
    if (step.text !== undefined) say(step.text);
    for (const a of step.do || []) {
      if (a.fire) fire(a.fire, a.input || "Trigger", a.value, a.delay);
      else if (a.teleport) for (const pl of mechPlayers()) pl.pawn.Teleport({ position: vec(a.teleport[0], a.teleport[1], a.teleport[2]), velocity: vec(0, 0, 0) });
      else if (a.give) for (const pl of mechPlayers()) { if (!pl.pawn.FindWeapon(a.give)) pl.pawn.GiveNamedItem(a.give); }
      else if (a.hp) for (const pl of mechPlayers()) pl.pawn.SetHealth(a.hp);
      else if (a.end) fire(a.end === "win" ? "story_win" : "story_lose", "Trigger");
    }
  }
  for (const inp of inputs) {
    Instance.OnScriptInput(inp, () => {
      const next = S.step && (ST.steps[S.step].on || {})[inp];
      if (next) enter(next);
    });
  }
  onStart(() => enter(ST.start));
  every((now) => {
    if (!S.step || !S.until) return;
    hudAll("story_time", Math.max(0, Math.ceil(S.until - now)));
    if (now >= S.until) { const t = ST.steps[S.step].timeout; S.until = 0; if (t) enter(t); }
  });
}
