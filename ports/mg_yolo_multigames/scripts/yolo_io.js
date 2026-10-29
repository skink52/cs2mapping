import { Instance, Entity, BaseModelEntity, CSPlayerPawn, CSPlayerController, CSInputs, CSDamageFlags, CSMoveType, CSGearSlot, CustomHudLayout, CustomCameraMode, CSGrenadeProjectileBase } from "cs_script/point_script";

// mg_yolo_multigames: CS2 replacements for CS:GO entities and I/O tricks that no longer exist.
// Driven by `yolo_io_script` -> RunScriptInput <input name>; the touching / pressing player is the activator.
//
//   SetAlpha_<n>                  replaces  !activator Alpha <n> / AddOutput "rendermode 6" (creeper: invisible)
//   Speed_<x>                     replaces  player_speedmod "speedmod" ModifySpeed <x>
//   Gravity_<x>                   replaces  trigger_gravity (player gravity scale <x>, kept after leaving, like CS:GO)
//   SetDest_<tele>__<dest>        replaces  spawn_CTport / spawn_Tport AddOutput "target <dest>" (game picker buttons)
//   Teleport_<tele>               fired by those teleporters' OnStartTouch
//   MakerOrigin_<maker>__x_y_z    replaces  <env_entity_maker> AddOutput "Origin x y z" (moves it before its ForceSpawn)
//   Color_<prop>__r_g_b           replaces  <prop_physics_override> Color r g b (volleyball balls)
//   Strip                         replaces  player_weaponstrip "aim_stripper" Strip
//   SlayAll                       replaces  point_servercommand "sm_slay @all" (5 minute timeout, needed SourceMod)
//   RefillPistolAmmo              replaces  game_player_equip "head_ammo" (ammo_50ae: CS2 has no ammo items)
//   Show_/Hide_spawn_overlay      replaces  env_screenoverlay "spawn_overlay" (custom_hud_layout yolo_overlay_layout)
//   GameUI_cube_gameui            replaces  game_ui "cube_gameui": remote-control cube (WASD thrusters, mouse1 shock,
//                                           mouse2 jump; use/jump exits) - the camera follows the cube (was a func_monitor)
//   GameUI_game_ui33              replaces  game_ui "game_ui33": the secret knife, mouse1 held = push_up33 enabled
//   (automatic)                   spawn strip: replaces the unnamed "Strip First" game_player_equip run on every spawn
//   (automatic)                   game_round_end "roundend" OnRoundEnded -> weed colour-correction volumes off
//   GiveNade                      replaces  game_player_equip "Givenade" (grenade holes supply rails; +use near a rail also works)
//   (automatic)                   grenade holes: a thrown grenade entering a hole fires that hole's logic_relay nade_holeN
//   (automatic)                   ball / block physics: replaces phys_pushscale 900 / 15 / -2000 and cs_enable_player_physics_box
//   NadeWin_T / NadeWin_CT        grenade holes: a team filled all 15 holes -> the other team is slain 60 s later (M4 time)
//   (automatic)                   volleyball: a ball landing on the other side's floor fires fb_tball_scored / fb_ctball_scored
//   (automatic)                   spawn_overlay (map credits) only shows in the first two rounds
//   Item_aim_deagle / Item_hacks_equip  item_assaultsuit from those game_player_equips (an item_* in an equip slot crashes CS2 on map load)
//   CreeperPickup                 creeper game: CS:GO parented the creeper body, its env_explosion and countdown sprites to the knife;
//                                           CS2 parenting to a weapon doesn't follow the carrier, so the script carries them
//   Weed_1 / Weed_2 / Weed_3      replaces  color_correction weed_co_1..3 (scouts "drugged" game): full-screen HUD overlay,
//   Weed_Off                                weed_random picks one every 10-25 s; cleared at round start/end (global, like CS:GO)
//
// The data block below is generated from the map by the port tooling.

/** @type {{ alphas: number[], gravities: number[], speeds: number[], teleporters: Record<string, { initial: string, dests: string[] }>, makerOrigins: [string, number[]][], colors: [string, number[]][], roundEnd: [string, string, number][], holes: { name: string, mins: number[], maxs: number[] }[], rails: number[][][], volleyball: { ball: string, relay: string, dest: string, mins: number[], maxs: number[] }[], netClip: { name: string, mins: number[], maxs: number[] } }} */
const DATA = {"alphas":[0,255],"gravities":[0.25,0.85,1.0],"speeds":[1.2],"teleporters":{"spawn_CTport":{"initial":"","dests":["aim_ctdest","awp_ctdest","ele_dest","fb_ctdest","foot_ctdest","hacks_ctdest","head_ctdest","knife_ctdest","mc_backtoland","nade_ctdest","phys_ctdest","pistol_dest","weed_ctdest"]},"spawn_Tport":{"initial":"","dests":["aim_tdest","awp_tdest","ele_dest_t","fb_tdest","foot_tdest","hacks_tdest","head_tdest","knife_tdest","mc_dest_t","nade_tdest","phys_tdest","pistol_dest_t","weed_tdest"]}},"makerOrigins":[["foot_template_maker",[8712.0,11520.0,11152.0]],["foot_template_maker",[8856.0,11520.0,11152.0]],["foot_template_maker",[9000.0,11520.0,11152.0]],["foot_template_maker",[9144.0,11520.0,11152.0]],["foot_template_maker",[9344.0,11320.0,11152.0]],["foot_template_maker",[9344.0,11176.0,11152.0]],["foot_template_maker",[9344.0,11032.0,11152.0]],["foot_template_maker",[9344.0,10888.0,11152.0]],["foot_template_maker",[9144.0,10688.0,11152.0]],["foot_template_maker",[9000.0,10688.0,11152.0]],["foot_template_maker",[8856.0,10688.0,11152.0]],["foot_template_maker",[8712.0,10688.0,11152.0]],["foot_template_maker",[8512.0,10688.0,11152.0]],["foot_template_maker",[8512.0,11032.0,11152.0]],["foot_template_maker",[8512.0,11176.0,11152.0]],["foot_template_maker",[8512.0,11320.0,11152.0]],["physics_template_2_maker",[-12584.0,-5344.0,4160.0]],["physics_template_2_maker",[-12584.0,-4960.0,4160.0]],["physics_template_2_maker",[-12584.0,-4576.0,4160.0]],["physics_template_2_maker",[-12584.0,-4192.0,4160.0]],["physics_template_2_maker",[-12584.0,-3808.0,4160.0]],["physics_template_2_maker",[-11880.0,-4160.0,4160.0]],["physics_template_2_maker",[-11880.0,-4992.0,4160.0]],["physics_template_2_maker",[-12008.0,-4960.0,4544.0]],["physics_template_2_maker",[-12008.0,-4192.0,4544.0]],["physics_template_2_maker",[-12936.0,-4480.0,4544.0]],["physics_template_1_maker",[-13288.0,-5352.0,4160.0]],["physics_template_1_maker",[-13288.0,-4960.0,4160.0]],["physics_template_1_maker",[-13288.0,-4576.0,4160.0]],["physics_template_1_maker",[-13288.0,-4200.0,4160.0]],["physics_template_1_maker",[-13288.0,-3808.0,4160.0]],["physics_template_1_maker",[-13992.0,-4160.0,4160.0]],["physics_template_1_maker",[-13992.0,-4992.0,4160.0]],["physics_template_1_maker",[-13864.0,-4960.0,4544.0]],["physics_template_1_maker",[-13864.0,-4192.0,4544.0]],["physics_template_1_maker",[-12936.0,-4672.0,4544.0]],["knife_template_maker",[-3712.0,-9792.0,9416.0]],["knife_template_maker",[-3712.0,-9792.0,9928.0]],["knife_template_maker",[-3712.0,-8768.0,9416.0]],["knife_template_maker",[-3712.0,-8768.0,8904.0]],["knife_template_maker",[-3712.0,-9792.0,8904.0]],["knife_template_maker",[-3712.0,-9792.0,8392.0]],["knife_template_maker",[-3712.0,-8768.0,8392.0]],["knife_template_maker",[-3712.0,-8768.0,9928.0]]],"colors":[["fb_counterterroristball",[0,0,255]],["fb_terroristball",[255,0,0]]],"roundEnd":[["weed_co_1","Kill",0.10000000149011612],["weed_co_2","Kill",0.10000000149011612],["weed_co_3","Kill",0.10000000149011612],["weed_co_3","Disable",0.0],["weed_co_2","Disable",0.0],["weed_co_1","Disable",0.0]],"holes":[{"name":"nade_hole1","mins":[4288.0,-2880.0,832.0],"maxs":[4320.0,-2752.0,864.0]},{"name":"nade_hole10","mins":[4768.0,-2880.0,832.0],"maxs":[4800.0,-2752.0,864.0]},{"name":"nade_hole11","mins":[4768.0,-2880.0,576.0],"maxs":[4800.0,-2752.0,608.0]},{"name":"nade_hole12","mins":[4768.0,-2880.0,320.0],"maxs":[4800.0,-2752.0,352.0]},{"name":"nade_hole13","mins":[4928.0,-2880.0,832.0],"maxs":[4960.0,-2752.0,864.0]},{"name":"nade_hole14","mins":[4928.0,-2880.0,576.0],"maxs":[4960.0,-2752.0,608.0]},{"name":"nade_hole15","mins":[4928.0,-2880.0,320.0],"maxs":[4960.0,-2752.0,352.0]},{"name":"nade_hole16","mins":[5824.0,-2880.0,832.0],"maxs":[5856.0,-2752.0,864.0]},{"name":"nade_hole17","mins":[5824.0,-2880.0,576.0],"maxs":[5856.0,-2752.0,608.0]},{"name":"nade_hole18","mins":[5824.0,-2880.0,320.0],"maxs":[5856.0,-2752.0,352.0]},{"name":"nade_hole19","mins":[5184.0,-2880.0,832.0],"maxs":[5216.0,-2752.0,864.0]},{"name":"nade_hole2","mins":[4288.0,-2880.0,576.0],"maxs":[4320.0,-2752.0,608.0]},{"name":"nade_hole20","mins":[5184.0,-2880.0,576.0],"maxs":[5216.0,-2752.0,608.0]},{"name":"nade_hole21","mins":[5184.0,-2880.0,320.0],"maxs":[5216.0,-2752.0,352.0]},{"name":"nade_hole22","mins":[5664.0,-2880.0,832.0],"maxs":[5696.0,-2752.0,864.0]},{"name":"nade_hole23","mins":[5664.0,-2880.0,576.0],"maxs":[5696.0,-2752.0,608.0]},{"name":"nade_hole24","mins":[5504.0,-2880.0,832.0],"maxs":[5536.0,-2752.0,864.0]},{"name":"nade_hole25","mins":[5504.0,-2880.0,576.0],"maxs":[5536.0,-2752.0,608.0]},{"name":"nade_hole26","mins":[5504.0,-2880.0,320.0],"maxs":[5536.0,-2752.0,352.0]},{"name":"nade_hole27","mins":[5344.0,-2880.0,832.0],"maxs":[5376.0,-2752.0,864.0]},{"name":"nade_hole28","mins":[5344.0,-2880.0,576.0],"maxs":[5376.0,-2752.0,608.0]},{"name":"nade_hole29","mins":[5344.0,-2880.0,320.0],"maxs":[5376.0,-2752.0,352.0]},{"name":"nade_hole3","mins":[4288.0,-2880.0,320.0],"maxs":[4320.0,-2752.0,352.0]},{"name":"nade_hole30","mins":[5664.0,-2880.0,320.0],"maxs":[5696.0,-2752.0,352.0]},{"name":"nade_hole4","mins":[4448.0,-2880.0,832.0],"maxs":[4480.0,-2752.0,864.0]},{"name":"nade_hole5","mins":[4448.0,-2880.0,576.0],"maxs":[4480.0,-2752.0,608.0]},{"name":"nade_hole6","mins":[4448.0,-2880.0,320.0],"maxs":[4480.0,-2752.0,352.0]},{"name":"nade_hole7","mins":[4608.0,-2880.0,832.0],"maxs":[4640.0,-2752.0,864.0]},{"name":"nade_hole8","mins":[4608.0,-2880.0,576.0],"maxs":[4640.0,-2752.0,608.0]},{"name":"nade_hole9","mins":[4608.0,-2880.0,320.0],"maxs":[4640.0,-2752.0,352.0]}],"rails":[[[5216.0,-3536.0,96.0],[5920.0,-3520.0,144.0]],[[5216.0,-3536.0,352.0],[5920.0,-3520.0,400.0]],[[5216.0,-3536.0,608.0],[5920.0,-3520.0,656.0]],[[4224.0,-3536.0,608.0],[4928.0,-3520.0,656.0]],[[4224.0,-3536.0,352.0],[4928.0,-3520.0,400.0]],[[4224.0,-3536.0,96.0],[4928.0,-3520.0,144.0]]],"volleyball":[{"ball":"fb_terroristball","relay":"fb_tball_scored","dest":"fb_tball","mins":[-13536.0,11072.0,10688.0],"maxs":[-12512.0,12096.0,10692.0]},{"ball":"fb_counterterroristball","relay":"fb_ctball_scored","dest":"fb_ctball","mins":[-14816.0,11072.0,10688.0],"maxs":[-13792.0,12096.0,10692.0]}],"netClip":{"name":"fb_playerclip","mins":[-13792.0,11168.0,10784.0],"maxs":[-13536.0,12000.0,11456.0]}};
/** @typedef {import("cs_script/point_script").Vector} Vector */
/** @typedef {import("cs_script/point_script").QAngle} QAngle */

const SCRIPT_NAME = "yolo_io_script";
const TEAM_T = 2, TEAM_CT = 3;
const BASE_SPEED = 250;                                 // knife run speed
const WALK_FACTOR = 0.52, DUCK_FACTOR = 0.34;
const SV_GRAVITY = 800;

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

// ---------------------------------------------------------------- render alpha (players)
for (const a of DATA.alphas) {
    Instance.OnScriptInput("SetAlpha_" + a, ({ activator }) => {
        const pawn = toPawn(activator);
        if (!pawn || !pawn.IsValid()) return;
        const c = pawn.GetColor();
        pawn.SetColor({ r: c.r, g: c.g, b: c.b, a });
    });
}

// ---------------------------------------------------------------- think loop: speed, gravity, game_ui
/** @type {Map<number, number>} player slot -> speed multiplier */
const speedBySlot = new Map();
/** @type {Map<number, number>} player slot -> gravity scale */
const gravityBySlot = new Map();
let thinking = false;
let lastThink = 0;

function ensureThink() {
    if (thinking) return;
    thinking = true;
    lastThink = Instance.GetGameTime();
    Instance.SetNextThink(lastThink);
}

Instance.SetThink(() => {
    const now = Instance.GetGameTime();
    const dt = Math.min(Math.max(now - lastThink, 0), 0.1);
    lastThink = now;
    for (const slot of new Set([...speedBySlot.keys(), ...gravityBySlot.keys()])) {
        const pawn = Instance.GetPlayerController(slot)?.GetPlayerPawn();
        if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) { speedBySlot.delete(slot); gravityBySlot.delete(slot); continue; }
        let { x, y, z } = pawn.GetAbsVelocity();
        let changed = false;
        const onGround = !!pawn.GetGroundEntity();
        // trigger_gravity: CS2 players have no gravity scale, so while airborne give back the part of gravity the scale removes
        const g = gravityBySlot.get(slot);
        if (g !== undefined && !onGround && pawn.GetMoveType() === CSMoveType.WALK) { z += (1 - g) * SV_GRAVITY * dt; changed = true; }
        const mult = speedBySlot.get(slot);
        if (mult !== undefined && onGround) {
            const fwd = (pawn.IsInputPressed(CSInputs.FORWARD) ? 1 : 0) - (pawn.IsInputPressed(CSInputs.BACK) ? 1 : 0);
            const side = (pawn.IsInputPressed(CSInputs.RIGHT) ? 1 : 0) - (pawn.IsInputPressed(CSInputs.LEFT) ? 1 : 0);
            if (fwd !== 0 || side !== 0) {
                const yaw = pawn.GetEyeAngles().yaw * Math.PI / 180;
                let dx = Math.cos(yaw) * fwd + Math.sin(yaw) * side;
                let dy = Math.sin(yaw) * fwd - Math.cos(yaw) * side;
                const len = Math.hypot(dx, dy); dx /= len; dy /= len;
                let speed = BASE_SPEED * mult;
                if (pawn.IsInputPressed(CSInputs.WALK)) speed *= WALK_FACTOR;
                if (pawn.IsDucking()) speed *= DUCK_FACTOR;
                x = dx * speed; y = dy * speed; changed = true;
            }
        }
        if (changed) pawn.Move({ velocity: { x, y, z } });
    }
    cubeThink(now);
    creeperThink();
    knife33Think();
    nadeThink(now);
    physThink(now, dt);
    netThink();
    Instance.SetNextThink(now);
});

for (const s of DATA.speeds) {
    Instance.OnScriptInput("Speed_" + s, ({ activator }) => {
        const slot = slotOf(activator);
        if (slot === undefined) return;
        if (s === 1) speedBySlot.delete(slot); else speedBySlot.set(slot, s);
        ensureThink();
    });
}
for (const g of DATA.gravities) {
    Instance.OnScriptInput("Gravity_" + g, ({ activator }) => {
        const slot = slotOf(activator);
        if (slot === undefined) return;
        if (g === 1) gravityBySlot.delete(slot); else gravityBySlot.set(slot, g);
        ensureThink();
    });
}

// ---------------------------------------------------------------- spawn strip (unnamed "Strip First" game_player_equip)
// CS:GO ran it on every spawn, so everyone started with nothing (the games hand out their own weapons).
// CS2 doesn't run non-"Use Only" equips on spawn: no default loadout, and strip every (re)spawning player.
const NO_DEFAULT_LOADOUT = ["mp_t_default_melee", "mp_ct_default_melee", "mp_t_default_secondary", "mp_ct_default_secondary",
                            "mp_t_default_primary", "mp_ct_default_primary", "mp_t_default_grenades", "mp_ct_default_grenades"];
Instance.OnPlayerReset(({ player }) => {
    const slot = player.GetPlayerController()?.GetPlayerSlot();
    if (slot !== undefined) { speedBySlot.delete(slot); gravityBySlot.delete(slot); knife33.delete(slot); }
    if (cube.driver === player) exitCube();
    if (player && player.IsValid()) player.DestroyWeapons();
});

// ---------------------------------------------------------------- weapon strip / ammo / slay
Instance.OnScriptInput("Strip", ({ activator }) => {
    const pawn = toPawn(activator);
    if (pawn && pawn.IsValid()) pawn.DestroyWeapons();
});
Instance.OnScriptInput("RefillPistolAmmo", ({ activator }) => {
    const pawn = toPawn(activator);
    if (!pawn || !pawn.IsValid()) return;
    const w = pawn.FindWeaponBySlot(CSGearSlot.PISTOL);
    if (w && w.IsValid()) w.SetReserveAmmo(w.GetData().GetMaxReserveAmmo());
});
Instance.OnScriptInput("SlayAll", () => {
    for (const pawn of livePawns()) pawn.TakeDamage({ damage: 100000, damageFlags: CSDamageFlags.FORCE_DEATH | CSDamageFlags.IGNORE_ARMOR });
});

// ---------------------------------------------------------------- game picker teleporters
/** @type {Record<string, string>} teleporter -> current destination ("" = none yet) */
const currentDest = {};
for (const [tele, info] of Object.entries(DATA.teleporters)) {
    currentDest[tele] = info.initial;
    for (const dest of info.dests) Instance.OnScriptInput(`SetDest_${tele}__${dest}`, () => { currentDest[tele] = dest; });
    Instance.OnScriptInput("Teleport_" + tele, ({ activator }) => {
        const pawn = toPawn(activator);
        if (!pawn || !pawn.IsValid() || !currentDest[tele]) return;
        const dest = Instance.FindEntityByName(currentDest[tele]);
        if (!dest || !dest.IsValid()) return;
        // like trigger_teleport: move to the destination, take its facing, stop all movement
        const angles = dest.GetAbsAngles();
        pawn.Teleport({ position: dest.GetAbsOrigin(), angles: { pitch: 0, yaw: angles.yaw, roll: 0 }, velocity: { x: 0, y: 0, z: 0 } });
        pawn.SetEyeAngles(angles);
    });
}

// ---------------------------------------------------------------- env_entity_maker origins
for (const [maker, xyz] of DATA.makerOrigins) {
    const key = `MakerOrigin_${maker}__${xyz.map(v => String(v)).join("_")}`;
    Instance.OnScriptInput(key, () => {
        for (const ent of Instance.FindEntitiesByName(maker)) ent.Teleport({ position: { x: xyz[0], y: xyz[1], z: xyz[2] } });
    });
}

// ---------------------------------------------------------------- prop colours
for (const [target, [r, g, b]] of DATA.colors) {
    Instance.OnScriptInput(`Color_${target}__${r}_${g}_${b}`, () => {
        for (const ent of Instance.FindEntitiesByName(target)) {
            if (ent instanceof BaseModelEntity) ent.SetColor({ r, g, b, a: ent.GetColor().a });
            // volleyball start (fb_relay colours the balls): the balls start asleep in the air - drop them
            if (VOLLEY.some(v => v.ball === target)) wake(ent);
        }
    });
}

// ---------------------------------------------------------------- screen overlay
const LAYOUT_NAME = "yolo_overlay_layout";
/** @param {string} panelId @param {boolean} visible */
function setOverlay(panelId, visible) {
    const ent = Instance.FindEntityByName(LAYOUT_NAME);
    if (ent instanceof CustomHudLayout) ent.SetHasClass(panelId, "Hidden", !visible);
}
// map credits: only in the first two rounds of the map, and the script hides it itself after 5 s
const INTRO_ROUNDS = 2, INTRO_TIME = 5;
let introRounds = 0, lastRoundSignal = -100, introShownRound = 0;
function roundSignal() {
    const now = Instance.GetGameTime();
    if (now - lastRoundSignal > 3) introRounds++;
    lastRoundSignal = now;
}
Instance.OnScriptInput("Show_spawn_overlay", () => {
    roundSignal();
    if (introRounds > INTRO_ROUNDS || introShownRound === introRounds) return;
    introShownRound = introRounds;
    setOverlay("spawn_overlay", true);
    Instance.EntFireAtName({ name: SCRIPT_NAME, input: "RunScriptInput", value: "Hide_spawn_overlay", delay: INTRO_TIME });
});
Instance.OnScriptInput("Hide_spawn_overlay", () => setOverlay("spawn_overlay", false));

// scouts "drugged" game: CS:GO cycled three global color_corrections (weed_co_1..3); the post_processing_volume copies showed nothing in CS2
const WEED = ["weed_1", "weed_2", "weed_3"];
/** @param {number} n 0 = off */
function weed(n) { WEED.forEach((id, i) => setOverlay(id, i === n - 1)); }
Instance.OnScriptInput("Weed_1", () => weed(1));
Instance.OnScriptInput("Weed_2", () => weed(2));
Instance.OnScriptInput("Weed_3", () => weed(3));
Instance.OnScriptInput("Weed_Off", () => weed(0));

// ---------------------------------------------------------------- equip items (item_* in a game_player_equip slot crashes the server on map load)
for (const equip of ["aim_deagle", "hacks_equip"]) {
    Instance.OnScriptInput("Item_" + equip, ({ activator }) => { toPawn(activator)?.GiveNamedItem("item_assaultsuit", false); });
}

// ---------------------------------------------------------------- creeper (mc_creeper_knife OnPlayerPickup -> CreeperPickup)
const CREEPER_PARTS = ["mc_creeper", "mc_creeper_explosive", "mc_sprite_1", "mc_sprite_2", "mc_sprite_3", "mc_sprite_4", "mc_sprite_5", "mc_sprite_boom"];
const CREEPER_KNIFE_SPAWN = { x: -11620, y: -10272, z: 6963 };   // the parts keep their offset from the knife, now from the carrier's feet
/** @type {{ pawn: CSPlayerPawn | undefined, parts: { ent: Entity, ofs: { x: number, y: number, z: number } }[] }} */
const creeper = { pawn: undefined, parts: [] };
Instance.OnScriptInput("CreeperPickup", ({ activator }) => {
    const pawn = toPawn(activator);
    if (!pawn) return;
    creeper.pawn = pawn; creeper.parts = [];
    for (const name of CREEPER_PARTS) {
        for (const ent of Instance.FindEntitiesByName(name)) {
            const o = ent.GetAbsOrigin();
            Instance.EntFireAtTarget({ target: ent, input: "ClearParent" });
            creeper.parts.push({ ent, ofs: { x: o.x - CREEPER_KNIFE_SPAWN.x, y: o.y - CREEPER_KNIFE_SPAWN.y, z: o.z - CREEPER_KNIFE_SPAWN.z } });
        }
    }
});
function creeperThink() {
    const pawn = creeper.pawn;
    if (!pawn) return;
    if (!pawn.IsValid() || !pawn.IsAlive()) { creeper.pawn = undefined; creeper.parts = []; return; }
    const p = pawn.GetAbsOrigin();
    for (const part of creeper.parts) {
        if (part.ent.IsValid()) part.ent.Teleport({ position: { x: p.x + part.ofs.x, y: p.y + part.ofs.y, z: p.z + part.ofs.z } });
    }
}

// ---------------------------------------------------------------- game_ui "cube_gameui": remote-control cube
// CS:GO: ent_fire_me (+use) switches the hover thrusters "up" on and activates the game_ui (freeze player,
// +use / jump exits). XAxis -> left/right thrusters, YAxis -> front/backward, mouse2 -> "up2" (0.2 s boost),
// mouse1 -> cube_hurttrig Toggle. A func_monitor showed the camera on the cube; here the driver's view follows it.
const cube = {
    /** @type {CSPlayerPawn | undefined} */ driver: undefined,
    since: 0,
    /** @type {Record<string, boolean>} */ on: {},
};
/** @param {string} name @param {boolean} active */
function thruster(name, active) {
    if (cube.on[name] === active) return;
    cube.on[name] = active;
    Instance.EntFireAtName({ name, input: active ? "Activate" : "Deactivate" });
}
function exitCube() {
    const pawn = cube.driver;
    cube.driver = undefined;
    for (const n of ["front", "backward", "left", "right"]) thruster(n, false);
    cube.on = {};
    if (pawn && pawn.IsValid()) {
        if (pawn.GetMoveType() === CSMoveType.NONE) pawn.SetMoveType(CSMoveType.WALK);
        try { pawn.GetCustomCamera().SetMode(CustomCameraMode.DISABLED); } catch (e) { }
    }
}
Instance.OnScriptInput("GameUI_cube_gameui", ({ activator }) => {
    const pawn = toPawn(activator);
    if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) return;
    if (cube.driver && cube.driver !== pawn) exitCube();
    cube.driver = pawn; cube.since = Instance.GetGameTime(); cube.on = {};
    pawn.SetMoveType(CSMoveType.NONE);                                  // "Freeze Player"
    const body = Instance.FindEntityByName("cube");
    if (body && body.IsValid()) {
        try {
            const cam = pawn.GetCustomCamera();
            cam.SetFollowConfig({ followEntity: body, followOffset: { x: 0, y: 0, z: 24 }, cameraOffset: { x: -160, y: 0, z: 48 }, clipCameraOffset: true });
            cam.SetMode(CustomCameraMode.FOLLOW_POSITION);
        } catch (e) { }
    }
    ensureThink();
});
/** @param {number} now */
function cubeThink(now) {
    const p = cube.driver;
    if (!p) return;
    if (!p.IsValid() || !p.IsAlive()) { exitCube(); return; }
    // "+use deactivates" / "jump deactivates" (ignore the +use that started it)
    if (now - cube.since > 0.5 && (p.WasInputJustPressed(CSInputs.USE) || p.WasInputJustPressed(CSInputs.JUMP))) { exitCube(); return; }
    const y = (p.IsInputPressed(CSInputs.FORWARD) ? 1 : 0) - (p.IsInputPressed(CSInputs.BACK) ? 1 : 0);
    const x = (p.IsInputPressed(CSInputs.RIGHT) ? 1 : 0) - (p.IsInputPressed(CSInputs.LEFT) ? 1 : 0);
    thruster("front", y > 0); thruster("backward", y < 0);              // compare_y_axis
    thruster("right", x > 0); thruster("left", x < 0);                  // compare_x_axis
    if (p.WasInputJustPressed(CSInputs.ATTACK2)) Instance.EntFireAtName({ name: "up2", input: "Activate" });
    if (p.WasInputJustPressed(CSInputs.ATTACK)) Instance.EntFireAtName({ name: "cube_hurttrig", input: "Toggle" });
}

// ---------------------------------------------------------------- game_ui "game_ui33": secret knife (spawned by aim_spawn)
// CS:GO: picking up knife33 activates game_ui33; AttackAxis -> compare_up33: mouse1 held -> push_up33 Enable, else Disable.
/** @type {Map<number, boolean>} player slot -> push_up33 currently enabled */
const knife33 = new Map();
Instance.OnScriptInput("GameUI_game_ui33", ({ activator }) => {
    const slot = slotOf(activator);
    if (slot === undefined) return;
    knife33.set(slot, false);
    ensureThink();
});
function knife33Think() {
    for (const [slot, enabled] of knife33) {
        const pawn = Instance.GetPlayerController(slot)?.GetPlayerPawn();
        if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) {
            if (enabled) Instance.EntFireAtName({ name: "push_up33", input: "Disable" });
            knife33.delete(slot); continue;
        }
        const want = pawn.IsInputPressed(CSInputs.ATTACK) && !pawn.IsInputPressed(CSInputs.ATTACK2);
        if (want !== enabled) {
            Instance.EntFireAtName({ name: "push_up33", input: want ? "Enable" : "Disable" });
            knife33.set(slot, want);
        }
    }
}

// ---------------------------------------------------------------- grenade holes
// CS:GO: the supply rails gave an HE grenade (game_player_equip "Givenade"); a grenade landing in a hole touched
// hole_trigger (toggle that hole's wall, open a climbing step, count it). CS2 triggers don't see grenades, so the
// script follows every thrown grenade and fires the hole's logic_relay (nade_holeN, same outputs) when it goes in.
/** @param {CSPlayerPawn} pawn */
function giveNade(pawn) {
    if (!pawn.IsValid() || !pawn.IsAlive() || pawn.FindWeapon("weapon_hegrenade")) return;
    pawn.GiveNamedItem("weapon_hegrenade", false);
}
Instance.OnScriptInput("GiveNade", ({ activator }) => {
    const pawn = toPawn(activator);
    if (pawn) giveNade(pawn);
});
const RAIL_REACH = 80;
/** @type {Map<CSGrenadeProjectileBase, { last: Vector, born: number }>} */
const nades = new Map();
/** @type {Set<string>} holes already filled this round */
const holesDone = new Set();
let nadeWinner = 0, nadeSlayAt = 0;
const NADE_SLAY_DELAY = 60;
const NADE_AREA = { mins: { x: 3900, y: -3800, z: -600 }, maxs: { x: 6300, y: -2500, z: 2300 } };
/** @param {Vector} p @param {{ x: number, y: number, z: number }} mins @param {{ x: number, y: number, z: number }} maxs @param {number} pad */
function inside(p, mins, maxs, pad) {
    return p.x >= mins.x - pad && p.x <= maxs.x + pad && p.y >= mins.y - pad && p.y <= maxs.y + pad && p.z >= mins.z - pad && p.z <= maxs.z + pad;
}
const HOLES = DATA.holes.map(h => ({ name: h.name, mins: { x: h.mins[0], y: h.mins[1], z: h.mins[2] }, maxs: { x: h.maxs[0], y: h.maxs[1], z: h.maxs[2] } }));
const RAILS = DATA.rails.map(r => ({ mins: { x: r[0][0], y: r[0][1], z: r[0][2] }, maxs: { x: r[1][0], y: r[1][1], z: r[1][2] } }));
/** segment a->b touches box? (checked at a few points along the way, grenades move < 30u per tick) */
function segmentHits(/** @type {Vector} */ a, /** @type {Vector} */ b, /** @type {{ mins: any, maxs: any }} */ box) {
    const steps = Math.max(1, Math.ceil(Math.hypot(b.x - a.x, b.y - a.y, b.z - a.z) / 8));
    for (let i = 1; i <= steps; i++) {
        const f = i / steps;
        if (inside({ x: a.x + (b.x - a.x) * f, y: a.y + (b.y - a.y) * f, z: a.z + (b.z - a.z) * f }, box.mins, box.maxs, 0)) return true;
    }
    return false;
}
Instance.OnGrenadeThrow(({ projectile }) => {
    if (!projectile || !projectile.IsValid()) return;
    const p = projectile.GetAbsOrigin();
    if (!inside(p, NADE_AREA.mins, NADE_AREA.maxs, 0)) return;
    nades.set(projectile, { last: p, born: Instance.GetGameTime() });
});
/** @param {number} now */
function nadeThink(now) {
    if (nadeSlayAt && now >= nadeSlayAt) nadeSlay();
    for (const [nade, st] of nades) {
        if (!nade.IsValid() || now - st.born > 10) { nades.delete(nade); continue; }
        const p = nade.GetAbsOrigin();
        for (const h of HOLES) {
            if (holesDone.has(h.name) || !segmentHits(st.last, p, h)) continue;
            holesDone.add(h.name);
            Instance.EntFireAtName({ name: h.name, input: "Trigger", activator: nade.GetThrower() });
        }
        st.last = p;
    }
    // +use at a supply rail also hands out a grenade (in case the func_button doesn't register the press)
    for (const pawn of livePawns()) {
        if (!pawn.WasInputJustPressed(CSInputs.USE)) continue;
        const eye = pawn.GetEyePosition();
        if (!inside(eye, NADE_AREA.mins, NADE_AREA.maxs, 0)) continue;
        if (RAILS.some(r => inside(eye, r.mins, r.maxs, RAIL_REACH))) giveNade(pawn);
    }
}

/** @param {number} winner team that filled its holes */
function nadeWin(winner) {
    if (nadeWinner) return;
    nadeWinner = winner;
    nadeSlayAt = Instance.GetGameTime() + NADE_SLAY_DELAY;
}
function nadeSlay() {
    nadeSlayAt = 0;
    for (const pawn of livePawns()) {
        if (pawn.GetTeamNumber() === nadeWinner || pawn.GetTeamNumber() < TEAM_T) continue;
        pawn.TakeDamage({ damage: 100000, damageFlags: CSDamageFlags.FORCE_DEATH | CSDamageFlags.IGNORE_ARMOR });
    }
}
Instance.OnScriptInput("NadeWin_T", () => nadeWin(TEAM_T));
Instance.OnScriptInput("NadeWin_CT", () => nadeWin(TEAM_CT));
// every round starts with empty holes (also puts the hole walls / steps / counters back in case they kept their state)
function resetNadeGame() {
    holesDone.clear();
    nades.clear();
    nadeWinner = 0;
    nadeSlayAt = 0;
    for (const h of HOLES) {
        const n = h.name.slice("nade_hole".length);
        Instance.EntFireAtName({ name: "hole_wall" + n, input: "Disable" });
        Instance.EntFireAtName({ name: "nade_climb" + n, input: "Close" });
    }
    for (const c of ["nade_counter", "nade_counter1"]) Instance.EntFireAtName({ name: c, input: "SetValueNoFire", value: 0 });
    Instance.EntFireAtName({ name: "nade_heal", input: "Enable" });
}

// ---------------------------------------------------------------- ball / block physics
// CS:GO ran phys_pushscale 900 (knife and bullet hits sent props flying), phys_pushscale -2000 in BLOCKS (shot blocks
// fly at the shooter), phys_pushscale 15 in AIM and cs_enable_player_physics_box 1 (players shove props by running
// into them). Those cvars are gone or blocked in CS2, so hits and running into props set the prop's velocity here.
// BLOCKS: shot blocks are pushed away from the shooter.
// Volleyball balls fall at 1/4 gravity (CS:GO's fb_gravity trigger_gravity 0.25 also applied to physics objects).
/** @type {{ prefix: string, hit: number, lift: number, run: boolean, gravity: number }[]} hit < 0 = towards the shooter */
const PHYS = [
    { prefix: "foot_ball", hit: 900, lift: 200, run: true, gravity: 1 },
    { prefix: "fb_terroristball", hit: 650, lift: 300, run: true, gravity: 0.25 },
    { prefix: "fb_counterterroristball", hit: 650, lift: 300, run: true, gravity: 0.25 },
    { prefix: "physics_block", hit: 1100, lift: 100, run: false, gravity: 1 },
    { prefix: "aim_boxes", hit: 300, lift: 60, run: false, gravity: 1 },
];
const PHYS_CLASSES = ["prop_physics", "prop_physics_override", "prop_physics_multiplayer", "func_physbox", "func_physbox_multiplayer"];
const KNIFE_RANGE = 72, RUN_REACH = 30, RUN_MIN_SPEED = 60, RUN_BOOST = 1.4;
/** @param {Entity | undefined} ent */
function physRule(ent) {
    if (!ent || !ent.IsValid()) return undefined;
    const n = ent.GetEntityName();
    return n ? PHYS.find(r => n.startsWith(r.prefix)) : undefined;
}
/** @param {Entity} ent @param {Vector} dir unit vector @param {number} speed @param {number} lift */
function launch(ent, dir, speed, lift) {
    const v = { x: dir.x * speed, y: dir.y * speed, z: dir.z * speed };
    if (v.z < lift) v.z = lift;
    ent.Teleport({ velocity: v });
}
/** @param {Vector} from @param {Vector} to */
function unit(from, to) {
    const x = to.x - from.x, y = to.y - from.y, z = to.z - from.z, l = Math.hypot(x, y, z) || 1;
    return { x: x / l, y: y / l, z: z / l };
}
/** @param {QAngle} a */
function forward(a) {
    const p = a.pitch * Math.PI / 180, y = a.yaw * Math.PI / 180;
    return { x: Math.cos(p) * Math.cos(y), y: Math.cos(p) * Math.sin(y), z: -Math.sin(p) };
}
Instance.OnBulletImpact(({ weapon, position, hitEntity }) => {
    const rule = physRule(hitEntity);
    if (!rule || !hitEntity) return;
    const shooter = weapon?.GetOwner();
    if (!shooter || !shooter.IsValid()) return;
    const dir = unit(shooter.GetEyePosition(), position);
    if (rule.hit < 0) launch(hitEntity, { x: -dir.x, y: -dir.y, z: -dir.z }, -rule.hit, rule.lift);
    else launch(hitEntity, dir, rule.hit, rule.lift);
});
Instance.OnKnifeAttack(({ weapon }) => {
    const pawn = weapon?.GetOwner();
    if (!pawn || !pawn.IsValid()) return;
    const eye = pawn.GetEyePosition(), dir = forward(pawn.GetEyeAngles());
    const end = { x: eye.x + dir.x * KNIFE_RANGE, y: eye.y + dir.y * KNIFE_RANGE, z: eye.z + dir.z * KNIFE_RANGE };
    const tr = Instance.TraceSphere({ radius: 8, start: eye, end, ignoreEntity: pawn, ignorePlayers: true });
    const rule = physRule(tr.hitEntity);
    if (!rule || !tr.hitEntity || rule.hit <= 0) return;
    launch(tr.hitEntity, dir, rule.hit, rule.lift);
});
// volleyball: CS:GO's floor trigger_teleports (ball on the other side's floor -> point, ball back to its server spot)
const VOLLEY = DATA.volleyball.map(v => ({ ...v, lo: { x: v.mins[0], y: v.mins[1], z: v.mins[2] - 8 }, hi: { x: v.maxs[0], y: v.maxs[1], z: v.maxs[2] + 24 } }));
/** @type {Map<Entity, number>} */
const lastScore = new Map();
/** @type {Map<Entity, number>} balls to wake (start falling) at a game time */
const wakeAt = new Map();
/** @param {Entity} ball */
function wake(ball) { const v = ball.GetAbsVelocity(); ball.Teleport({ velocity: { x: v.x, y: v.y, z: Math.min(v.z, -20) } }); }
/** @param {Entity} ball @param {Vector} p @param {number} now */
function volleyScore(ball, p, now) {
    const name = ball.GetEntityName();
    const v = VOLLEY.find(x => x.ball === name);
    if (!v || !inside(p, v.lo, v.hi, 0) || now - (lastScore.get(ball) ?? -10) < 1) return false;
    lastScore.set(ball, now);
    const dest = Instance.FindEntityByName(v.dest);
    if (dest && dest.IsValid()) ball.Teleport({ position: dest.GetAbsOrigin(), velocity: { x: 0, y: 0, z: 0 }, angularVelocity: { x: 0, y: 0, z: 0 } });
    Instance.EntFireAtName({ name: v.relay, input: "Trigger" });
    wakeAt.set(ball, now + 0.15);                                      // after the relay's DisableMotion / EnableMotion
    return true;
}
/** @type {{ ent: Entity, rule: { prefix: string, hit: number, lift: number, run: boolean, gravity: number } }[]} */
let physBodies = [];
let nextBodyScan = 0;
/** @type {Map<Entity, number>} */
const lastShove = new Map();
/** @type {Map<Entity, number>} vertical velocity the script set last tick (low-gravity balls) */
const lastSetVz = new Map();
let physGravity = SV_GRAVITY;                                         // measured from the balls, starts at sv_gravity
/** @param {number} now @param {number} dt */
function physThink(now, dt) {
    if (now >= nextBodyScan) {
        nextBodyScan = now + 0.5;
        physBodies = [];
        // by class and by name (whichever finds them), each prop once
        const found = new Set();
        for (const cls of PHYS_CLASSES) for (const ent of Instance.FindEntitiesByClass(cls)) found.add(ent);
        for (const r of PHYS) for (const n of [r.prefix, r.prefix + "*"]) for (const ent of Instance.FindEntitiesByName(n)) found.add(ent);
        for (const ent of found) {
            const rule = physRule(ent);
            if (rule && (rule.run || rule.gravity !== 1 || VOLLEY.some(v => v.ball === ent.GetEntityName()))) physBodies.push({ ent, rule });
        }
    }
    for (const [ball, at] of wakeAt) {
        if (now < at) continue;
        wakeAt.delete(ball);
        if (ball.IsValid()) wake(ball);
    }
    if (physBodies.length === 0) return;
    const pawns = livePawns();
    for (const { ent, rule } of physBodies) {
        if (!ent.IsValid()) continue;
        const bp = ent.GetAbsOrigin();
        if (volleyScore(ent, bp, now)) continue;
        let v = ent.GetAbsVelocity();
        let changed = false;
        if (rule.gravity !== 1 && dt > 0 && (Math.abs(v.z) > 1 || Math.hypot(v.x, v.y) > 1)) {
            // measure the engine's gravity on this ball in free flight (vz drop since the velocity we set last tick)
            const last = lastSetVz.get(ent);
            if (last !== undefined) {
                const accel = (v.z - last) / dt;
                if (accel < -100 && accel > -2000) physGravity += (-accel - physGravity) * 0.2;
            }
            v = { x: v.x, y: v.y, z: v.z + (1 - rule.gravity) * physGravity * dt }; changed = true;
            lastSetVz.set(ent, v.z);
        } else lastSetVz.delete(ent);
        if (rule.run && now - (lastShove.get(ent) ?? 0) > 0.08) {
            for (const pawn of pawns) {
                const pp = pawn.GetAbsOrigin();
                const dz = bp.z - pp.z;
                if (dz < -16 || dz > 80) continue;
                const dx = bp.x - pp.x, dy = bp.y - pp.y, d = Math.hypot(dx, dy);
                if (d > RUN_REACH || d < 0.01) continue;
                const pv = pawn.GetAbsVelocity();
                const ax = dx / d, ay = dy / d;
                const toward = pv.x * ax + pv.y * ay;                    // player speed towards the prop
                if (toward < RUN_MIN_SPEED) continue;
                const want = toward * RUN_BOOST, have = v.x * ax + v.y * ay;
                if (have >= want) continue;
                v = { x: v.x + ax * (want - have), y: v.y + ay * (want - have), z: Math.max(v.z, 60) };
                changed = true;
                lastShove.set(ent, now);
                break;
            }
        }
        if (changed) ent.Teleport({ velocity: v });
    }
}

// ---------------------------------------------------------------- volleyball net player clip
// fb_playerclip kept players out of the space above the net. In CS2 its playerclip faces blocked the balls as well, so it is
// a never-solid func_brush now and the script keeps players out of that box until it is killed (a team won).
const NET = { name: DATA.netClip.name, mins: { x: DATA.netClip.mins[0], y: DATA.netClip.mins[1], z: DATA.netClip.mins[2] }, maxs: { x: DATA.netClip.maxs[0], y: DATA.netClip.maxs[1], z: DATA.netClip.maxs[2] } };
const PLAYER_HALF = 16, PLAYER_HEIGHT = 72;
let netAlive = true, nextNetCheck = 0;
function netThink() {
    const now = Instance.GetGameTime();
    if (now >= nextNetCheck) {
        nextNetCheck = now + 0.25;
        const ent = Instance.FindEntityByName(NET.name);
        netAlive = !!ent && ent.IsValid();
    }
    if (!netAlive) return;
    const midX = (NET.mins.x + NET.maxs.x) / 2;
    for (const pawn of livePawns()) {
        const p = pawn.GetAbsOrigin();
        if (p.x + PLAYER_HALF <= NET.mins.x || p.x - PLAYER_HALF >= NET.maxs.x) continue;
        if (p.y + PLAYER_HALF <= NET.mins.y || p.y - PLAYER_HALF >= NET.maxs.y) continue;
        if (p.z + PLAYER_HEIGHT <= NET.mins.z || p.z >= NET.maxs.z) continue;
        const v = pawn.GetAbsVelocity();
        const left = p.x < midX;
        const x = left ? NET.mins.x - PLAYER_HALF - 0.5 : NET.maxs.x + PLAYER_HALF + 0.5;
        const vx = left ? Math.min(v.x, 0) : Math.max(v.x, 0);
        pawn.Teleport({ position: { x, y: p.y, z: p.z }, velocity: { x: vx, y: v.y, z: v.z } });
    }
}

// ---------------------------------------------------------------- round flow
Instance.OnActivate(() => {
    for (const cvar of NO_DEFAULT_LOADOUT) Instance.ServerCommand(`${cvar} ""`);
    ensureThink();
});
// game_round_end "roundend" OnRoundEnded: switch the scouts game's colour correction off
Instance.OnRoundStart(() => { roundSignal(); resetNadeGame(); weed(0); creeper.pawn = undefined; creeper.parts = []; });
Instance.OnRoundEnd(() => {
    weed(0);
    for (const [name, input, delay] of DATA.roundEnd) Instance.EntFireAtName({ name, input, delay });
});
// Each round starts with the teleport targets the map was built with (CS:GO respawned map entities each round).
Instance.OnBeginRoundRestart(() => {
    for (const [tele, info] of Object.entries(DATA.teleporters)) currentDest[tele] = info.initial;
    speedBySlot.clear();
    gravityBySlot.clear();
    knife33.clear();
    exitCube();
    resetNadeGame();
    lastScore.clear();
    wakeAt.clear();
    lastSetVz.clear();
    netAlive = true;
    nextNetCheck = 0;
    physBodies = [];
    nextBodyScan = 0;
    lastShove.clear();
});
