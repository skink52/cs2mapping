import { Instance, Entity, CSPlayerPawn, CSPlayerController } from "cs_script/point_script";

// CS2 port of changemodel.nut (logic_script "ModelChangeScript").
// Triggered by: <trigger> -> ModelChangeScript -> RunScriptInput -> ChangeModel
//
// Original VScript:
//   activator.SetModel("models/player/custom_player/kuristaja/octodad/octodad_black.mdl");
//
// Because the ported Octodad model might not work as a CS2 player model, players who get
// it are also marked so they stay distinguishable:
//   * TINT  - always applied. Cosmetic only, no gameplay effect.
//   * GLOW  - outline. Likely visible THROUGH WALLS (like CS glows), so by default it is
//             only used as a fallback when the model fails to apply.
// Both are cleared when the player respawns / resets.

// CS2-ready Octodad: the CS:GO mesh rebound onto the CS2 agent skeleton with the stock agent animgraphs,
// hitboxes, ragdoll and first-person arms (the old octodad_black.vmdl is a plain prop, which made weapons huge).
const MODEL = "models/player/custom_player/kuristaja/octodad/cs2/octodad_cs2.vmdl";

/** Tint applied to every Octodad player, e.g. { r: 255, g: 140, b: 0 }. undefined = no tint. */
const TINT = undefined;   // was orange while the model could fail; the CS2 model applies properly, as in CS:GO

/** Glow colour for the outline. */
const GLOW_COLOR = { r: 255, g: 140, b: 0 };

/**
 * "off"      - never glow
 * "fallback" - glow only if SetModel didn't take (player still has their old model)
 * "always"   - always glow (careful: probably visible through walls in combat games)
 */
const GLOW_MODE = /** @type {"off" | "fallback" | "always"} */ ("fallback");

const WHITE = { r: 255, g: 255, b: 255 };

/** Player slots we've modified, so we only reset players this script touched. */
const marked = new Set();

/**
 * Triggers pass the player pawn as the activator; accept a controller too, just in case.
 * @param {Entity | undefined} ent
 * @returns {CSPlayerPawn | undefined}
 */
function toPawn(ent) {
    if (ent instanceof CSPlayerPawn) return ent;
    if (ent instanceof CSPlayerController) return ent.GetPlayerPawn();
    return undefined;
}

/** @param {CSPlayerPawn} pawn */
function modelApplied(pawn) {
    return pawn.GetModelName().toLowerCase().includes("octodad");
}

Instance.OnScriptInput("ChangeModel", ({ activator }) => {
    const pawn = toPawn(activator);
    if (!pawn || !pawn.IsValid()) return;

    pawn.SetModel(MODEL);

    if (TINT) pawn.SetColor(TINT);

    const applied = modelApplied(pawn);
    if (GLOW_MODE === "always" || (GLOW_MODE === "fallback" && !applied)) {
        pawn.Glow(GLOW_COLOR);
    }
    if (!applied) {
        Instance.Msg(`changemodel.js: Octodad model did not apply (still "${pawn.GetModelName()}")`);
    }

    const slot = pawn.GetPlayerController()?.GetPlayerSlot();
    if (slot !== undefined) marked.add(slot);
});

// Respawn, team change or round restart: remove the tint/glow so it doesn't carry over.
// (Spawn triggers re-apply it straight after if the player should still be Octodad.)
Instance.OnPlayerReset(({ player }) => {
    const slot = player.GetPlayerController()?.GetPlayerSlot();
    if (slot === undefined || !marked.has(slot)) return;
    marked.delete(slot);
    if (player.IsGlowing()) player.Unglow();
    player.SetColor(WHITE);
});
