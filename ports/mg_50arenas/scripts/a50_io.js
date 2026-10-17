import { Instance, Entity, BaseModelEntity, CSPlayerPawn, CSPlayerController, CSInputs, CustomHudLayout } from "cs_script/point_script";

// mg_50arenas: CS2 replacements for CS:GO entities and I/O tricks that no longer exist.
// Driven by `a50_io_script` -> RunScriptInput <input name>; the touching / picking-up player is the activator.
//
//   SetName_<name>               replaces  !activator AddOutput "targetname crowdt1 / crowdct1"
//   SetAlpha_<n> / SetColor_<r>_<g>_<b> / SetScale_<s>
//                                replaces  !activator Alpha / Color / AddOutput "modelscale"   (render1, asszone)
//   CrowdAlpha_<n> / CrowdColor_<r>_<g>_<b> / CrowdScale_<s>
//                                replaces  crowd* Alpha / Color / AddOutput "modelscale"       (the super powers)
//   Speed_<x>                    replaces  player_speedmod "speedfuck" ModifySpeed <x>
//   Strip                        replaces  player_weaponstrip "ladystrip" Strip               (VIP knives)
//   SetHP_<n> / ApplyHP          replaces  HP AddOutput "OnStartTouch !activator:AddOutput:health <n>"
//   Rename_<a>__<b>              replaces  <a> AddOutput "targetname <b>"                       (randomarena2 -> randomarena)
//   SetDest_<tele>__<dest>       replaces  spawn_Tport / spawn_CTport AddOutput "target <dest>" (the 50 arenas)
//   Teleport_<tele>              fired by those teleporters' OnStartTouch
//   Sweep_<tele> / SweepSkins    the teleporters / skin triggers are switched on with everyone already inside them
//   Model_<logic_script>         replaces  the 33 logic_script vscripts (activator.SetModel)    (random skins, the Power Ranger)
//   ShowIntro / HideIntro        replaces  env_screenoverlay "intro_overlay"                   (custom_hud_layout a50_overlay_layout)
//   SetEffect_<tint> / EffectOn / EffectOff
//                                replaces  env_screenoverlay "xx0s0e0" (screen tint effects -> post_processing_volume a50_effect_<tint>)
//   (automatic)                  spawn strip: replaces the unnamed "Strip First" game_player_equip run on every spawn
//   (automatic)                  game_round_end "efend" OnRoundEnded outputs
//
// The data block below is generated from the map by the port tooling.

/** @type {{ alphas: number[], colors: string[], scales: string[], names: string[], speeds: string[], hps: number[], renames: [string, string][], models: Record<string, string>, teleporters: Record<string, { initial: string, dests: string[], team: number, box: number[][] }>, skinBoxes: Record<string, number[][]>, effects: string[], commands: string[], roundEnd: [string, string, string, number][] }} */
const DATA = {"alphas":[25,125,255],"colors":["0_0_255","0_255_0","0_255_255","128_0_128","255_0_0","255_128_0","255_255_0","255_255_255"],"scales":["1","1.5"],"names":["crowdct1","crowdt1"],"speeds":["1","1.1","1.5"],"hps":[1,50,100,150,200,500],"renames":[["randomarena2","randomarena"]],"models":{"script_ctm_st6_d":"characters/models/ctm_st6/ctm_st6_variantj.vmdl","script_ctm_fbi":"characters/models/ctm_fbi/ctm_fbi.vmdl","script_ctm_gig":"characters/models/ctm_gendarmerie/ctm_gendarmerie_varianta.vmdl","script_tm_pir_c":"characters/models/tm_jungle_raider/tm_jungle_raider_variantb.vmdl","script_tm_lee_b":"characters/models/tm_leet/tm_leet_variantb.vmdl","script_ctm_sas_c":"characters/models/ctm_sas/ctm_sas_variantf.vmdl","script_ctm_fbi_d":"characters/models/ctm_fbi/ctm_fbi_variantd.vmdl","script_tm_bal_a":"characters/models/tm_balkan/tm_balkan_variantf.vmdl","script_ctm_idf":"characters/models/ctm_st6/ctm_st6_variante.vmdl","script_tm_lee_e":"characters/models/tm_leet/tm_leet_variante.vmdl","script_all_green":"models/player/mapeadores/morell/powerranger/cs2/powerranger_green_cs2.vmdl","script_tm_ana_d":"characters/models/tm_jumpsuit/tm_jumpsuit_variantb.vmdl","script_tm_pir_b":"characters/models/tm_jungle_raider/tm_jungle_raider_varianta.vmdl","script_tm_lee_c":"characters/models/tm_leet/tm_leet_variantc.vmdl","script_ctm_swa_b":"characters/models/ctm_swat/ctm_swat_varianth.vmdl","script_ctm_swa_c":"characters/models/ctm_swat/ctm_swat_varianti.vmdl","script_tm_pho_c":"characters/models/tm_phoenix/tm_phoenix_variantc.vmdl","script_tm_bal_c":"characters/models/tm_balkan/tm_balkan_varianth.vmdl","script_tm_pro_3":"characters/models/tm_professional/tm_professional_varf.vmdl","script_tm_ana_a":"characters/models/tm_jumpsuit/tm_jumpsuit_varianta.vmdl","script_tm_pro_4":"characters/models/tm_professional/tm_professional_varg.vmdl","script_tm_sep":"characters/models/tm_jungle_raider/tm_jungle_raider_variantc.vmdl","script_tm_pho":"characters/models/tm_phoenix/tm_phoenix.vmdl","script_ctm_fbi_c":"characters/models/ctm_fbi/ctm_fbi_variantc.vmdl","script_tm_sep_d":"characters/models/tm_jungle_raider/tm_jungle_raider_variantd.vmdl","script_tm_bal_b":"characters/models/tm_balkan/tm_balkan_variantg.vmdl","script_ctm_gig_d":"characters/models/ctm_gendarmerie/ctm_gendarmerie_variantb.vmdl","script_ctm_gsg":"characters/models/ctm_swat/ctm_swat_variante.vmdl","script_ctm_st6_a":"characters/models/ctm_st6/ctm_st6_varianti.vmdl","script_ctm_gsg_d":"characters/models/ctm_swat/ctm_swat_variantf.vmdl","script_ctm_sas":"characters/models/ctm_sas/ctm_sas.vmdl","script_ctm_sas_e":"characters/models/ctm_sas/ctm_sas_variantg.vmdl","script_ctm_idf_d":"characters/models/ctm_st6/ctm_st6_variantg.vmdl"},"teleporters":{"spawn_CTport":{"initial":"","dests":["arena10_CTport","arena11_CTport","arena12_CTport","arena13_CTport","arena14_CTport","arena15_CTport","arena16_CTport","arena17_CTport","arena18_CTport","arena19_CTport","arena1_CTport","arena20_CTport","arena21_CTport","arena22_CTport","arena23_CTport","arena24_CTport","arena25_CTport","arena26_CTport","arena27_CTport","arena28_CTport","arena29_CTport","arena2_CTport","arena30_CTport","arena31_CTport","arena32_CTport","arena33_CTport","arena34_CTport","arena35_CTport","arena36_CTport","arena37_CTport","arena38_CTport","arena39_CTport","arena3_CTport","arena40_CTport","arena41_CTport","arena42_CTport","arena43_CTport","arena44_CTport","arena45_CTport","arena46_CTport","arena47_CTport","arena48_CTport","arena49_CTport","arena4_CTport","arena50_CTport","arena5_CTport","arena6_CTport","arena7_CTport","arena8_CTport","arena9_CTport"],"team":3,"box":[[-13392.0,-13392.0,-144.0],[-11184.0,-11184.0,1040.0]]},"spawn_Tport":{"initial":"","dests":["arena10_Tport","arena11_Tport","arena12_Tport","arena13_Tport","arena14_Tport","arena15_Tport","arena16_Tport","arena17_Tport","arena18_Tport","arena19_Tport","arena1_Tport","arena20_Tport","arena21_Tport","arena22_Tport","arena23_Tport","arena24_Tport","arena25_Tport","arena26_Tport","arena27_Tport","arena28_Tport","arena29_Tport","arena2_Tport","arena30_Tport","arena31_Tport","arena32_Tport","arena33_Tport","arena34_Tport","arena35_Tport","arena36_Tport","arena37_Tport","arena38_Tport","arena39_Tport","arena3_Tport","arena40_Tport","arena41_Tport","arena42_Tport","arena43_Tport","arena44_Tport","arena45_Tport","arena46_Tport","arena47_Tport","arena48_Tport","arena49_Tport","arena4_Tport","arena50_Tport","arena5_Tport","arena6_Tport","arena7_Tport","arena8_Tport","arena9_Tport"],"team":2,"box":[[-13384.0,-13384.0,-136.0],[-11192.0,-11192.0,1032.0]]}},"skinBoxes":{"skins_CT":[[-13336.0,-13336.0,-88.0],[-11240.0,-11240.0,984.0]],"skins_T":[[-13328.0,-13328.0,-80.0],[-11248.0,-11248.0,976.0]]},"commands":["say @ SIMON SAYS KNIFE","say @ SIMON SAYS AWP","say @ SIMON SAYS SSG08","say @ SIMON SAYS SCAR20","say @ SIMON SAYS G3SG1","say @ SIMON SAYS M4A1","say @ SIMON SAYS AK47","say @ SIMON SAYS M4A1S","say @ SIMON SAYS GALILAR","say @ SIMON SAYS FAMAS","say @ SIMON SAYS AUG","say @ SIMON SAYS SG556","say @ SIMON SAYS INCGRENADE","say @ SIMON SAYS MOLOTOV","say @ SIMON SAYS MP9","say @ SIMON SAYS MAC10","say @ SIMON SAYS MP7","say @ SIMON SAYS P90","say @ SIMON SAYS UMP45","say @ SIMON SAYS BIZON","say @ SIMON SAYS NOVA","say @ SIMON SAYS XM1014","say @ SIMON SAYS SAWEDOFF","say @ SIMON SAYS MAG7","say @ SIMON SAYS HEGRENADE","say @ SIMON SAYS SMOKEGRENADE","say @ SIMON SAYS FLASHBANG","say @ EFFECT [ OFF ]","say @ EFFECT [ T1 S1 E1 ]","say @ EFFECT [ T1 S1 E2 ]","say @ EFFECT [ T1 S1 E3 ]","say @ EFFECT [ T1 S1 E4 ]","say @ EFFECT [ T1 S1 E5 ]","say @ EFFECT [ T1 S1 E6 ]","say @ EFFECT [ T1 S2 E1 ]","say @ EFFECT [ T1 S2 E2 ]","say @ EFFECT [ T1 S2 E3 ]","say @ EFFECT [ T1 S2 E4 ]","say @ EFFECT [ T1 S2 E5 ]","say @ EFFECT [ T1 S2 E6 ]","say @ EFFECT [ T1 S2 E7 ]","say @ EFFECT [ T1 S3 E1 ]","say @ EFFECT [ T1 S3 E2 ]","say @ EFFECT [ T1 S3 E3 ]","say @ EFFECT [ T1 S3 E4 ]","say @ EFFECT [ T1 S3 E5 ]","say @ EFFECT [ T1 S3 E6 ]","say @ EFFECT [ T1 S3 E7 ]","say @ EFFECT [ T2 S1 E1 ]","say @ EFFECT [ T2 S1 E2 ]","say @ EFFECT [ T2 S1 E3 ]","say @ EFFECT [ T2 S1 E4 ]","say @ EFFECT [ T2 S1 E5 ]","say @ EFFECT [ T2 S1 E6 ]","say @ EFFECT [ T2 S1 E7 ]","say @ EFFECT [ T2 S2 E1 ]","say @ EFFECT [ T2 S2 E2 ]","say @ EFFECT [ T2 S2 E3 ]","say @ EFFECT [ T2 S2 E4 ]","say @ EFFECT [ T2 S2 E5 ]","say @ EFFECT [ T2 S2 E6 ]","say @ EFFECT [ T2 S2 E7 ]","say @ EFFECT [ T3 S1 E1 ]","say @ EFFECT [ T3 S1 E2 ]","say @ EFFECT [ T3 S1 E3 ]","say @ EFFECT [ T3 S1 E4 ]","say @ EFFECT [ T3 S1 E5 ]","say @ EFFECT [ T3 S1 E6 ]","say @ EFFECT [ T3 S1 E7 ]","say @ EFFECT [ T3 S2 E1 ]","say @ EFFECT [ T3 S2 E2 ]","say @ EFFECT [ T3 S2 E3 ]","say @ EFFECT [ T3 S2 E4 ]","say @ EFFECT [ T3 S2 E5 ]","say @ EFFECT [ T3 S2 E6 ]","say @ EFFECT [ T3 S2 E7 ]","say @ EFFECT [ T1 S1 E7 ]","say @ ARENA  [ 1 ]","say @ ARENA  [ 2 ]","say @ ARENA  [ 3 ]","say @ ARENA  [ 4 ]","say @ ARENA  [ 5 ]","say @ ARENA  [ 6 ]","say @ ARENA  [ 7 ]","say @ ARENA  [ 8 ]","say @ ARENA  [ 9 ]","say @ ARENA  [ 10 ]","say @ ARENA  [ 11 ]","say @ ARENA  [ 12 ]","say @ ARENA  [ 13 ]","say @ ARENA  [ 14 ]","say @ ARENA  [ 15 ]","say @ ARENA  [ 16 ]","say @ ARENA  [ 17 ]","say @ ARENA  [ 18 ]","say @ ARENA  [ 19 ]","say @ ARENA  [ 20 ]","say @ ARENA  [ 21 ]","say @ ARENA  [ 22 ]","say @ ARENA  [ 23 ]","say @ ARENA  [ 24 ]","say @ ARENA  [ 25 ]","say @ ARENA  [ 26 ]","say @ ARENA  [ 27 ]","say @ ARENA  [ 28 ]","say @ ARENA  [ 29 ]","say @ ARENA  [ 30 ]","say @ ARENA  [ 31 ]","say @ ARENA  [ 32 ]","say @ ARENA  [ 33 ]","say @ ARENA  [ 34 ]","say @ ARENA  [ 35 ]","say @ ARENA  [ 36 ]","say @ ARENA  [ 39 ]","say @ ARENA  [ 40 ]","say @ ARENA  [ 41 ]","say @ ARENA  [ 42 ]","say @ ARENA  [ 43 ]","say @ ARENA  [ 44 ]","say @ ARENA  [ 45 ]","say @ ARENA  [ 46 ]","say @ ARENA  [ 47 ]","say @ ARENA  [ 49 ]","say @ SUPER POWER [ INVISIBILITY ]","sv_accelerate -5.5","say @ SUPER POWER [ REVERSE MOTION ]","sv_airaccelerate -0.5","say @ SUPER POWER [ RAINBOW ]","say @ SUPER POWER [ BIG ASS ]","say @ SUPER POWER [ SPEED ]","say @ SUPER POWER [ INFINITE AMMO ]","sv_infinite_ammo 1","say @ SUPER POWER [ OFF ]","say @ SIMON SAYS M249","say @ SIMON SAYS NEGEV","say @ SIMON SAYS GLOCK","say @ SIMON SAYS USP","say @ SIMON SAYS P250","say @ SIMON SAYS HKP2000","say @ SIMON SAYS DEAGLE","say @ SIMON SAYS FIVESEVEN","say @ SIMON SAYS ELITE","say @ SIMON SAYS CZ75A","say @ SIMON SAYS TEC9","say @ SIMON SAYS REVOLVER","say @ SIMON SAYS ZEUS","sv_airaccelerate 150","mp_freezetime 0","sv_gravity 800","mp_solid_teammates 0","phys_timescale 0.65","sv_accelerate 5.5","sv_disable_immunity_alpha 1","mp_weapons_allow_map_placed 1","mp_autokick 0","sv_infinite_ammo 0","say @ LETS GO","say @ 50HP","say @ 100HP","say @ 150HP","say @ 200HP","say @ 100HP HEADSHOTZ!","say @ 1HP HOLYSHIT!","say @ 500HP","say @ GRAV [ 1 ]","say @ GRAV [ 0.9 ]","say @ GRAV [ 0.8 ]","say @ GRAV [ 0.7 ]","say @ GRAV [ 0.6 ]","say @ GRAV [ 0.5 ]","sv_gravity 720","sv_gravity 640","sv_gravity 560","sv_gravity 480","sv_gravity 400","sv_gravity 80","say @ GRAV [ 0.1 ]","say @ GRAV [ 2.0 ]","sv_gravity 1600","say @ ARENA  [ 37 ]","say @ ARENA  [ 38 ]","say @ ARENA  [ 48 ]","say @ ARENA  [ 50 ]"],"effects":["00x","0x0","0xx","x00","x0x","xx0","xxx","zzz"],"roundEnd":[["a50_io_script","RunScriptInput","EffectOff",0.029999999329447746],["a50_io_script","RunScriptInput","HideIntro",0.029999999329447746],["a50_io_script","RunScriptInput","EffectOff",0.019999999552965164],["a50_io_script","RunScriptInput","HideIntro",0.019999999552965164],["a50_io_script","RunScriptInput","HideIntro",0.009999999776482582],["a50_io_script","RunScriptInput","EffectOff",0.009999999776482582],["joinfix_timer","Disable","",0.0]]};

const BASE_SPEED = 250;                                 // knife run speed
const WALK_FACTOR = 0.52, DUCK_FACTOR = 0.34;
const TEAM_T = 2, TEAM_CT = 3;

/**
 * @param {Entity | undefined} ent
 * @returns {CSPlayerPawn | undefined}
 */
function toPawn(ent) {
    if (ent instanceof CSPlayerPawn) return ent;
    if (ent instanceof CSPlayerController) return ent.GetPlayerPawn();
    return undefined;
}
/** @param {Entity | undefined} activator */
function slotOf(activator) {
    return toPawn(activator)?.GetPlayerController()?.GetPlayerSlot();
}
/** @returns {CSPlayerPawn[]} */
function livePawns() {
    const out = [];
    for (let slot = 0; slot < 64; slot++) {
        const pawn = Instance.GetPlayerController(slot)?.GetPlayerPawn();
        if (pawn && pawn.IsValid() && pawn.IsAlive()) out.push(pawn);
    }
    return out;
}
/** players a CS:GO "crowd*" target hit: everyone the spawn teleporters / crowd makers named crowdt1 / crowdct1 */
function crowd() { return livePawns().filter(p => p.GetEntityName().toLowerCase().startsWith("crowd")); }
/** @param {string} s  "r_g_b" -> numbers */
function nums(s) { return s.split("_").map(Number); }
/** @param {{x:number,y:number,z:number}} p @param {number[][]} box */
function inBox(p, box) {
    const [lo, hi] = box, pad = 16;
    return p.x >= lo[0] - pad && p.x <= hi[0] + pad && p.y >= lo[1] - pad && p.y <= hi[1] + pad && p.z >= lo[2] - pad && p.z <= hi[2] + pad;
}

// ---------------------------------------------------------------- player render alpha / colour / scale / name
/** @param {BaseModelEntity} ent @param {number} a */
function setAlpha(ent, a) { const c = ent.GetColor(); ent.SetColor({ r: c.r, g: c.g, b: c.b, a }); }
/** @param {BaseModelEntity} ent @param {number[]} rgb */
function setRgb(ent, [r, g, b]) { ent.SetColor({ r, g, b, a: ent.GetColor().a }); }
for (const a of DATA.alphas) {
    Instance.OnScriptInput("SetAlpha_" + a, ({ activator }) => { const p = toPawn(activator); if (p && p.IsValid()) setAlpha(p, a); });
    Instance.OnScriptInput("CrowdAlpha_" + a, () => { for (const p of crowd()) setAlpha(p, a); });
}
for (const c of DATA.colors) {
    const rgb = nums(c);
    Instance.OnScriptInput("SetColor_" + c, ({ activator }) => { const p = toPawn(activator); if (p && p.IsValid()) setRgb(p, rgb); });
    Instance.OnScriptInput("CrowdColor_" + c, () => { for (const p of crowd()) setRgb(p, rgb); });
}
for (const s of DATA.scales) {
    const scale = Number(s);
    Instance.OnScriptInput("SetScale_" + s, ({ activator }) => { const p = toPawn(activator); if (p && p.IsValid()) p.SetModelScale(scale); });
    Instance.OnScriptInput("CrowdScale_" + s, () => { for (const p of crowd()) p.SetModelScale(scale); });
}
for (const n of DATA.names) {
    Instance.OnScriptInput("SetName_" + n, ({ activator }) => { const p = toPawn(activator); if (p && p.IsValid()) p.SetEntityName(n); });
}

// ---------------------------------------------------------------- player_speedmod (think loop)
/** @type {Map<number, number>} player slot -> speed multiplier */
const speedBySlot = new Map();
let thinking = false;
function ensureThink() {
    if (thinking || speedBySlot.size === 0) return;
    thinking = true;
    Instance.SetNextThink(Instance.GetGameTime());
}
Instance.SetThink(() => {
    for (const [slot, mult] of speedBySlot) {
        const pawn = Instance.GetPlayerController(slot)?.GetPlayerPawn();
        if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) { speedBySlot.delete(slot); continue; }
        if (!pawn.GetGroundEntity()) continue;
        const fwd = (pawn.IsInputPressed(CSInputs.FORWARD) ? 1 : 0) - (pawn.IsInputPressed(CSInputs.BACK) ? 1 : 0);
        const side = (pawn.IsInputPressed(CSInputs.RIGHT) ? 1 : 0) - (pawn.IsInputPressed(CSInputs.LEFT) ? 1 : 0);
        if (fwd === 0 && side === 0) continue;
        const yaw = pawn.GetEyeAngles().yaw * Math.PI / 180;
        let dx = Math.cos(yaw) * fwd + Math.sin(yaw) * side;
        let dy = Math.sin(yaw) * fwd - Math.cos(yaw) * side;
        const len = Math.hypot(dx, dy); dx /= len; dy /= len;
        let speed = BASE_SPEED * mult;
        if (pawn.IsInputPressed(CSInputs.WALK)) speed *= WALK_FACTOR;
        if (pawn.IsDucking()) speed *= DUCK_FACTOR;
        pawn.Move({ velocity: { x: dx * speed, y: dy * speed, z: pawn.GetAbsVelocity().z } });
    }
    if (speedBySlot.size > 0) Instance.SetNextThink(Instance.GetGameTime());
    else thinking = false;
});
for (const s of DATA.speeds) {
    const mult = Number(s);
    Instance.OnScriptInput("Speed_" + s, ({ activator }) => {
        const slot = slotOf(activator);
        if (slot === undefined) return;
        if (mult === 1) speedBySlot.delete(slot); else speedBySlot.set(slot, mult);
        ensureThink();
    });
}

// ---------------------------------------------------------------- weapon strip, health
Instance.OnScriptInput("Strip", ({ activator }) => {
    const pawn = toPawn(activator);
    if (pawn && pawn.IsValid()) pawn.DestroyWeapons();
});
/** health the round's "randomhp" picked for the HP trigger (undefined = none yet) @type {number | undefined} */
let roundHP;
for (const hp of DATA.hps) Instance.OnScriptInput("SetHP_" + hp, () => { roundHP = hp; });
Instance.OnScriptInput("ApplyHP", ({ activator }) => {
    const pawn = toPawn(activator);
    if (!pawn || !pawn.IsValid() || !pawn.IsAlive() || roundHP === undefined) return;
    if (roundHP > pawn.GetMaxHealth()) pawn.SetMaxHealth(roundHP);
    pawn.SetHealth(roundHP);
});

// ---------------------------------------------------------------- entity renames
for (const [from, to] of DATA.renames) {
    Instance.OnScriptInput(`Rename_${from}__${to}`, () => {
        for (const ent of Instance.FindEntitiesByName(from)) ent.SetEntityName(to);
    });
}

// ---------------------------------------------------------------- arena teleporters
/** @type {Record<string, string>} teleporter -> current destination ("" = none yet) */
const currentDest = {};
/** @type {Set<number>} slots the arena teleporters already sent this round */
const teleported = new Set();
const SWEEP_NAME = { spawn_Tport: "crowdt1", spawn_CTport: "crowdct1" };   // the teleporters' own OnStartTouch rename
/** @param {string} tele @param {CSPlayerPawn} pawn */
function teleport(tele, pawn) {
    if (!currentDest[tele]) return false;
    const dest = Instance.FindEntityByName(currentDest[tele]);
    if (!dest || !dest.IsValid()) return false;
    // like trigger_teleport: move to the destination, take its facing, stop all movement
    const angles = dest.GetAbsAngles();
    pawn.Teleport({ position: dest.GetAbsOrigin(), angles: { pitch: 0, yaw: angles.yaw, roll: 0 }, velocity: { x: 0, y: 0, z: 0 } });
    pawn.SetEyeAngles(angles);
    const slot = pawn.GetPlayerController()?.GetPlayerSlot();
    if (slot !== undefined) teleported.add(slot);
    return true;
}
for (const [tele, info] of Object.entries(DATA.teleporters)) {
    currentDest[tele] = info.initial;
    for (const dest of info.dests) Instance.OnScriptInput(`SetDest_${tele}__${dest}`, () => { currentDest[tele] = dest; });
    Instance.OnScriptInput("Teleport_" + tele, ({ activator }) => {
        const pawn = toPawn(activator);
        if (pawn && pawn.IsValid() && pawn.IsAlive()) teleport(tele, pawn);
    });
    Instance.OnScriptInput("Sweep_" + tele, () => {
        for (const pawn of livePawns()) {
            const slot = pawn.GetPlayerController()?.GetPlayerSlot();
            if (slot === undefined || teleported.has(slot) || pawn.GetTeamNumber() !== info.team || !inBox(pawn.GetAbsOrigin(), info.box)) continue;
            if (teleport(tele, pawn)) {
                const n = /** @type {Record<string, string>} */ (SWEEP_NAME)[tele];
                if (n) pawn.SetEntityName(n);
            }
        }
    });
}

// ---------------------------------------------------------------- player models (the logic_script vscripts)
/** @type {Set<number>} slots that got a model this round */
const skinned = new Set();
for (const [script, model] of Object.entries(DATA.models)) {
    Instance.OnScriptInput("Model_" + script, ({ activator }) => {
        const pawn = toPawn(activator);
        if (!pawn || !pawn.IsValid()) return;
        pawn.SetModel(model);
        const slot = pawn.GetPlayerController()?.GetPlayerSlot();
        if (slot !== undefined) skinned.add(slot);
    });
}
// skins_T / skins_CT (OnStartTouch -> randomskin_<team> PickRandom) are enabled with everyone already inside
Instance.OnScriptInput("SweepSkins", () => {
    for (const pawn of livePawns()) {
        const slot = pawn.GetPlayerController()?.GetPlayerSlot();
        if (slot === undefined || skinned.has(slot)) continue;
        const team = pawn.GetTeamNumber(), key = team === TEAM_T ? "skins_T" : team === TEAM_CT ? "skins_CT" : undefined;
        if (!key || !DATA.skinBoxes[key] || !inBox(pawn.GetAbsOrigin(), DATA.skinBoxes[key])) continue;
        Instance.EntFireAtName({ name: team === TEAM_T ? "randomskin_T" : "randomskin_CT", input: "PickRandom", activator: pawn });
    }
});

// ---------------------------------------------------------------- screen overlays
const LAYOUT_NAME = "a50_overlay_layout";
/** @param {string} panelId @param {boolean} visible */
function setOverlay(panelId, visible) {
    const ent = Instance.FindEntityByName(LAYOUT_NAME);
    if (ent instanceof CustomHudLayout) ent.SetHasClass(panelId, "Hidden", !visible);
}
Instance.OnScriptInput("ShowIntro", () => setOverlay("intro_overlay", true));
Instance.OnScriptInput("HideIntro", () => setOverlay("intro_overlay", false));
// screen tint effects: SetEffect_ picks the tint (xx0s0e0 AddOutput OverlayName1), joinfix_timer re-sends EffectOn every 0.1 s
/** @type {string | undefined} */ let effect;
/** @type {string | undefined} */ let effectOn;
/** @param {string | undefined} key */
function showEffect(key) {
    if (key === effectOn) return;
    if (effectOn && effectOn !== "xxx") Instance.EntFireAtName({ name: "a50_effect_" + effectOn, input: "Disable" });
    if (key && key !== "xxx") Instance.EntFireAtName({ name: "a50_effect_" + key, input: "Enable" });   // xxx = white tint: no change
    effectOn = key;
}
for (const key of DATA.effects) Instance.OnScriptInput("SetEffect_" + key, () => { effect = key; if (effectOn) showEffect(key); });
Instance.OnScriptInput("EffectOn", () => showEffect(effect));
Instance.OnScriptInput("EffectOff", () => showEffect(undefined));

// ---------------------------------------------------------------- server commands (point_servercommand startcms / msg_psc)
DATA.commands.forEach((cmd, i) => Instance.OnScriptInput("Cmd_" + i, () => Instance.ServerCommand(cmd)));

// ---------------------------------------------------------------- spawn strip (unnamed "Strip First" game_player_equip)
// CS:GO ran it on every spawn, so everyone started with nothing (the round hands out its own weapons).
// CS2 doesn't run non-"Use Only" equips on spawn: no default loadout, and strip every (re)spawning player.
const NO_DEFAULT_LOADOUT = ["mp_t_default_melee", "mp_ct_default_melee", "mp_t_default_secondary", "mp_ct_default_secondary",
                            "mp_t_default_primary", "mp_ct_default_primary", "mp_t_default_grenades", "mp_ct_default_grenades"];
Instance.OnActivate(() => {
    for (const cvar of NO_DEFAULT_LOADOUT) Instance.ServerCommand(`${cvar} ""`);
});
Instance.OnPlayerReset(({ player }) => {
    const slot = player.GetPlayerController()?.GetPlayerSlot();
    if (slot !== undefined) speedBySlot.delete(slot);
    if (player && player.IsValid()) {
        player.DestroyWeapons();
        player.SetColor({ r: 255, g: 255, b: 255, a: 255 });           // CS:GO players respawned with default render colour / scale
        player.SetModelScale(1);
    }
});

// ---------------------------------------------------------------- round flow
// game_round_end "efend" OnRoundEnded
Instance.OnRoundEnd(() => {
    for (const [name, input, value, delay] of DATA.roundEnd) Instance.EntFireAtName({ name, input, value, delay });
});
// Each round starts like the map was built (CS:GO respawned map entities each round).
Instance.OnBeginRoundRestart(() => {
    for (const [tele, info] of Object.entries(DATA.teleporters)) currentDest[tele] = info.initial;
    speedBySlot.clear();
    teleported.clear();
    skinned.clear();
    roundHP = undefined;
    effect = undefined; effectOn = undefined;      // the tint volumes respawn disabled
    setOverlay("intro_overlay", false);
});
