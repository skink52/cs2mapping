import { Instance, CustomHudLayout } from "cs_script/point_script";

// CS2 replacement for the 25 CS:GO env_screenoverlay entities in mg_mario_party.
//
// Old I/O:  portrait_xxx  OnPressed -> <OverlayName>  StartOverlays         (delay 0)
//           portrait_xxx  OnPressed -> <OverlayName>  StopOverlays          (delay 3.5)
// New I/O:  portrait_xxx  OnPressed -> mario_overlay_script  RunScriptInput  Show_<OverlayName>
//           portrait_xxx  OnPressed -> mario_overlay_script  RunScriptInput  Hide_<OverlayName>
//
// Each overlay is a panel (id = the old entity name) in
// panorama/layout/custom_game/mario_overlays.xml, shown to every player like env_screenoverlay was.

const LAYOUT_NAME = "mario_overlay_layout";

const OVERLAYS = [
    "BlockfortOverlay",
    "BoxGameOverlay",
    "ChainChompOverlay",
    "ChompKnifeOverlay",
    "climb_race_Overlay",
    "FightYardOverlay",
    "gravity_revolvers_Overlay",
    "HexagonHeatOverlay",
    "HungerGamesOverlay",
    "KingOfTheHillOverlay",
    "KnifeArenaOverlay",
    "MarioSaysOverlay",
    "mvp_Overlay",
    "ObstacleOverlay",
    "PirateClimbOverlay",
    "PirateIslandOverlay",
    "PlatformPerilOverlay",
    "random_fight_yard_Overlay",
    "ScoutzKnivezOverlay",
    "shotgun_arena_Overlay",
    "SkippingOverlay",
    "SkyPlatformsOverlay",
    "SniperThwompsOverlay",
    "SpeedSMGsOverlay",
    "ThwompFallsOverlay"
];

/** @returns {CustomHudLayout | undefined} */
function getLayout() {
    const ent = Instance.FindEntityByName(LAYOUT_NAME);
    if (ent instanceof CustomHudLayout) return ent;
    Instance.Msg(`overlays.js: custom_hud_layout "${LAYOUT_NAME}" not found`);
    return undefined;
}

/**
 * @param {string} panelId
 * @param {boolean} visible
 */
function setOverlay(panelId, visible) {
    getLayout()?.SetHasClass(panelId, "Hidden", !visible);
}

for (const id of OVERLAYS) {
    Instance.OnScriptInput(`Show_${id}`, () => setOverlay(id, true));
    Instance.OnScriptInput(`Hide_${id}`, () => setOverlay(id, false));
}

Instance.OnScriptInput("HideAllOverlays", () => {
    for (const id of OVERLAYS) setOverlay(id, false);
});
