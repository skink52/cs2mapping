// mech abilities: CONFIG.abilities = [{ kind, key, cooldown, strength, duration, team }]
//   double_jump (jump again in the air; strength = up speed, charges = extra jumps), dash (key: burst along the view, strength u/s),
//   jetpack (hold key: climb, fuel seconds = duration), blink (key: teleport up to strength u along the view, stops at walls),
//   flight (key toggles; fly where you look while forward is held), low_gravity (always: gravity scale = strength 0..1),
//   speed (always: ground speed cap x strength), shield (key: damage x strength for duration), invisibility (key: almost invisible
//   for duration), wallhack (key: enemies glow for duration), heal (key: +strength HP), jump_pad (map trigger -> script input
//   "jumppad_<i>": launches the activator; strength = up speed, push = forward speed along the trigger's yaw in `yaw`).
// HUD variable per ability: ab<i> ("ready" / seconds left). Ported from cs2-map-mcp's abilities.py + data/abilities/ability.js (Rmgs123,
// MIT): the same ability set; fresh code on create/mech/core.js.

const GRAVITY = 800;

function abilityReady(st, i, cd) { return !(st["cd" + i] > MECH.now); }
function abilityUse(st, i, cd) { st["cd" + i] = MECH.now + (cd || 0); }

function abilitiesInstall() {
  const list = CONFIG.abilities || [];
  list.forEach((ab, i) => {
    if (ab.kind === "jump_pad") {
      Instance.OnScriptInput("jumppad_" + i, (d) => {
        const pawn = d.activator;
        if (!pawn || !pawn.IsValid() || !pawn.IsAlive || !pawn.IsAlive()) return;
        const y = (ab.yaw || 0) * Math.PI / 180;
        const v = pawn.GetAbsVelocity();
        pawn.Teleport({ velocity: vec(v.x + Math.cos(y) * (ab.push || 0), v.y + Math.sin(y) * (ab.push || 0), ab.strength || 700) });
      });
    }
    if (ab.kind === "shield") {
      Instance.OnModifyPlayerDamage((e) => {
        const st = MECH.state.get(pawnSlot(e.player));
        if (st && st["on" + i] > MECH.now) return { damage: e.damage * (ab.strength !== undefined ? ab.strength : 0.3) };
      });
    }
  });
  every((now) => {
    const dt = MECH.dt;
    for (const pl of mechPlayers()) {
      const st = slotState(pl.slot), pawn = pl.pawn;
      list.forEach((ab, i) => {
        if (ab.team !== undefined && pawn.GetTeamNumber() !== ab.team) return;
        const key = ab.key ? keyOf(ab.key) : 0;
        const pressed = key && pawn.WasInputJustPressed(key);
        const held = key && pawn.IsInputPressed(key);
        const ready = abilityReady(st, i);
        const v = pawn.GetAbsVelocity();
        const air = !pawn.GetGroundEntity();
        switch (ab.kind) {
          case "double_jump":
            if (!air) st["j" + i] = ab.charges || 1;
            else if (pawn.WasInputJustPressed(CSInputs.JUMP) && st["j" + i] > 0 && ready) {
              st["j" + i]--; abilityUse(st, i, ab.cooldown); pawn.Teleport({ velocity: vec(v.x, v.y, ab.strength || 320) });
            }
            break;
          case "dash":
            if (pressed && ready) { abilityUse(st, i, ab.cooldown || 2); pawn.Teleport({ velocity: vAdd(v, vMul(flatFwd(pawn.GetEyeAngles()), ab.strength || 700)) }); }
            break;
          case "jetpack": {
            const max = ab.duration || 3;
            if (st["fuel" + i] === undefined) st["fuel" + i] = max;
            if (held && st["fuel" + i] > 0) { st["fuel" + i] -= dt; pawn.Teleport({ velocity: vec(v.x, v.y, Math.min(v.z + (GRAVITY + 900) * dt, ab.strength || 300)) }); }
            else if (!air) st["fuel" + i] = Math.min(max, st["fuel" + i] + dt * 0.5);
            hudSet(pl.slot, "ab" + i, Math.round(100 * st["fuel" + i] / max) + "%");
            return;
          }
          case "blink":
            if (pressed && ready) {
              abilityUse(st, i, ab.cooldown || 3);
              const eye = pawn.GetEyePosition(), f = fwdOf(pawn.GetEyeAngles());
              const tr = Instance.TraceLine({ start: eye, end: vAdd(eye, vMul(f, ab.strength || 600)), ignoreEntity: pawn, ignorePlayers: true });
              const to = vSub(tr.end, vMul(f, 32));
              pawn.Teleport({ position: vec(to.x, to.y, to.z - 64), velocity: vec(0, 0, 0) });
            }
            break;
          case "flight":
            if (pressed) st["fly" + i] = !st["fly" + i];
            if (st["fly" + i]) {
              const go = pawn.IsInputPressed(CSInputs.FORWARD) ? ab.strength || 400 : 0;
              pawn.Teleport({ velocity: vAdd(vMul(fwdOf(pawn.GetEyeAngles()), go), vec(0, 0, GRAVITY * dt)) });
            }
            break;
          case "low_gravity":
            if (air) pawn.Teleport({ velocity: vec(v.x, v.y, v.z + GRAVITY * (1 - (ab.strength !== undefined ? ab.strength : 0.4)) * dt) });
            return;
          case "speed": {
            const cap = 250 * (ab.strength || 1.4), h = Math.sqrt(v.x * v.x + v.y * v.y);
            if (!air && h > 1 && h < cap && (pawn.IsInputPressed(CSInputs.FORWARD) || pawn.IsInputPressed(CSInputs.BACK) ||
                pawn.IsInputPressed(CSInputs.LEFT) || pawn.IsInputPressed(CSInputs.RIGHT))) {
              const k = Math.min(cap / h, 1 + 4 * dt);
              pawn.Teleport({ velocity: vec(v.x * k, v.y * k, v.z) });
            }
            return;
          }
          case "shield":
            if (pressed && ready) { abilityUse(st, i, ab.cooldown || 10); st["on" + i] = now + (ab.duration || 4); }
            break;
          case "invisibility":
            if (pressed && ready) { abilityUse(st, i, ab.cooldown || 15); st["on" + i] = now + (ab.duration || 5); pawn.SetColor({ r: 255, g: 255, b: 255, a: 12 }); st["inv" + i] = true; }
            if (st["inv" + i] && !(st["on" + i] > now)) { pawn.SetColor({ r: 255, g: 255, b: 255, a: 255 }); st["inv" + i] = false; }
            break;
          case "wallhack":
            if (pressed && ready) {
              abilityUse(st, i, ab.cooldown || 20); st["on" + i] = now + (ab.duration || 4); st["wh" + i] = true;
              for (const o of mechPlayers()) if (o.pawn.GetTeamNumber() !== pawn.GetTeamNumber()) o.pawn.Glow({ r: 255, g: 60, b: 40 });
            }
            if (st["wh" + i] && !(st["on" + i] > now)) { st["wh" + i] = false; for (const o of mechPlayers()) o.pawn.Unglow(); }
            break;
          case "heal":
            if (pressed && ready) { abilityUse(st, i, ab.cooldown || 10); pawn.SetHealth(Math.min(pawn.GetMaxHealth(), pawn.GetHealth() + (ab.strength || 25))); }
            break;
          case "jump_pad":
            return;
          default:
            throw new Error("unknown ability " + ab.kind);
        }
        const left = (st["cd" + i] || 0) - now;
        hudSet(pl.slot, "ab" + i, left > 0 ? left.toFixed(1) + "s" : "ready");
      });
    }
  });
}
