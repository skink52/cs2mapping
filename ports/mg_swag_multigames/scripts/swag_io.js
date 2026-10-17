import { Instance, Entity, BaseModelEntity, CSPlayerPawn, CSPlayerController, CSInputs, CSDamageFlags, CSGearSlot, CustomHudLayout, CSMoveType } from "cs_script/point_script";

// mg_swag_multigames: CS2 replacements for CS:GO entities and I/O tricks that no longer exist.
// Driven by `swag_io_script` -> RunScriptInput <input name>; the touching / pressing / picking-up player is the activator.
//
//   SetAlpha_<n>                  replaces  !activator Alpha <n> (+ AddOutput "rendermode 1")        (stealth / VIP knives)
//   SetColor_<r>_<g>_<b>          replaces  !activator Color / AddOutput "rendercolor r g b"           (VIP knives: team colour)
//   ColorAllPlayers_<r>_<g>_<b>   replaces  room_button -> player / weapon_* AddOutput "rendercolor"   (blue room)
//   SetOrigin_<x>_<y>_<z>         replaces  !activator AddOutput "origin x y z"                         (VIP knives: back to base)
//   Speed_<x>                     replaces  player_speedmod "speedmod" ModifySpeed <x>                 (VIP knives)
//   SetDest_<tele>__<dest>        replaces  spawn_CTport / spawn_Tport AddOutput "target <dest>"       (game picker buttons)
//   Teleport_<tele>               fired by those teleporters' OnStartTouch
//   Sweep_<tele>                  sends everyone already standing in that teleporter (it is switched on with them inside)
//   ZeroVelocity                  lobby trigger_teleports: stop the player after the teleport
//   MoveTo_<name>__<x>_<y>_<z>    replaces  AddOutput "origin x y z" on env_entity_maker / env_sprite / info_teleport_destination
//   Color_<prop>__<r>_<g>_<b>     replaces  <prop_physics_override> Color r g b                         (explosive / killer balls)
//   Show_/Hide_/Kill_<overlay>    replaces  env_screenoverlay StartOverlays / StopOverlays / Kill      (custom_hud_layout swag_overlay_layout)
//   Strip                         replaces  player_weaponstrip "stripdatguy" / "et_stripper" Strip
//   RefillPistolAmmo              replaces  game_player_equip "pistol_ammo" (ammo_50ae: CS2 has no ammo items)
//   SlayAll                       replaces  point_servercommand "sm_slay @all" (needed SourceMod)
//   (automatic)                   spawn strip: replaces the unnamed "Strip First" game_player_equip run on every spawn
//   (automatic)                   game_round_end "roundend" OnRoundEnded outputs
//   LobbyWinner                   spawn_tele (race winner): safety net that gets them into the game picker room
//   ConveyorSpeed_<name>__<speed> replaces  func_conveyor SetSpeed (slide): CS2 conveyors don't carry players, the script does
//   (automatic)                   ball physics: replaces phys_pushscale 900 / cs_enable_player_physics_box (knife / shoot / run into balls)
//   (automatic)                   spawn_overlay (map credits) only shows in the first two rounds
//
// The data block below is generated from the map by the port tooling.

/** @type {{ alphas: number[], speeds: number[], playerColors: string[], playerOrigins: string[], teleporters: Record<string, { initial: string, dests: string[] }>, moves: [string, string, string][], colors: [string, string][], overlays: string[], roundEnd: [string, string, string, number][] }} */
const DATA = {"alphas":[50,254,255],"speeds":[1.2],"playerColors":["0_0_255","255_0_0","255_255_255"],"playerOrigins":["-10568_-4824_-508","-12756_-4812_-507"],"teleporters":{"spawn_CTport":{"initial":"","dests":["CTSTARTDEST","balls_dest","et_dest","skeet_awpdest","skeet_m3dest"]},"spawn_Tport":{"initial":"","dests":["TSTARTDEST","balls_dest_t","et_dest_t","skeet_awpdest","skeet_m3dest"]}},"moves":[["name1","12448_-776_7392","env_particle_glow"],["name2","12448_-776_7356","env_particle_glow"],["TSTARTDEST","12448_-2288_6805","info_teleport_destination"],["CTSTARTDEST","12448_744_6805","info_teleport_destination"],["chickenmaker","12448_-776_6880","env_entity_maker"],["chickenmaker","12408_-736_6880","env_entity_maker"],["chickenmaker","12488_-816_6880","env_entity_maker"],["chickenmaker","12408_-816_6880","env_entity_maker"],["chickenmaker","12488_-736_6880","env_entity_maker"],["chickenmaker","4320_-5792_6471","env_entity_maker"],["chickenmaker","4192_-6400_6471","env_entity_maker"],["chickenmaker","4320_-6496_6471","env_entity_maker"],["chickenmaker","4320_-6208_6471","env_entity_maker"],["chickenmaker","4320_-5920_6471","env_entity_maker"],["chickenmaker","4192_-5312_6471","env_entity_maker"],["chickenmaker","4320_-5216_6471","env_entity_maker"],["chickenmaker","4320_-5504_6471","env_entity_maker"],["smoke_template_maker2","-6336_-1476_10735","env_entity_maker"],["smoke_template_maker2","-6336_-1360_10681","env_entity_maker"],["smoke_template_maker2","-6336_-1244_10627","env_entity_maker"],["smoke_template_maker2","-6336_-1128_10573","env_entity_maker"],["smoke_template_maker2","-6336_-1012_10519","env_entity_maker"],["smoke_template_maker2","-6336_-896_10465","env_entity_maker"],["smoke_template_maker2","-6336_-780_10411","env_entity_maker"],["smoke_template_maker2","-6336_-664_10357","env_entity_maker"],["smoke_template_maker2","-6336_-548_10303","env_entity_maker"],["smoke_template_maker2","-6336_-432_10249","env_entity_maker"],["smoke_template_maker2","-6336_-316_10195","env_entity_maker"],["smoke_template_maker2","-6336_-200_10141","env_entity_maker"],["smoke_template_maker","-6976_1220_10736","env_entity_maker"],["smoke_template_maker","-6976_1104_10682","env_entity_maker"],["smoke_template_maker","-6976_988_10628","env_entity_maker"],["smoke_template_maker","-6976_872_10574","env_entity_maker"],["smoke_template_maker","-6976_756_10520","env_entity_maker"],["smoke_template_maker","-6976_640_10466","env_entity_maker"],["smoke_template_maker","-6976_524_10412","env_entity_maker"],["smoke_template_maker","-6976_408_10358","env_entity_maker"],["smoke_template_maker","-6976_292_10304","env_entity_maker"],["smoke_template_maker","-6976_176_10250","env_entity_maker"],["smoke_template_maker","-6976_60_10196","env_entity_maker"],["smoke_template_maker","-6976_-56_10142","env_entity_maker"],["chickenmaker","-192_-192_-576","env_entity_maker"],["chickenmaker","192_-192_-576","env_entity_maker"],["chickenmaker","192_192_-576","env_entity_maker"],["chickenmaker","-192_192_-576","env_entity_maker"],["TSTARTDEST","-4480_5760_-588","info_teleport_destination"],["CTSTARTDEST","-2944_5760_-588","info_teleport_destination"],["TSTARTDEST","4320_-4848_5588","info_teleport_destination"],["CTSTARTDEST","4320_-6864_5588","info_teleport_destination"],["name2","4320_-5856_6976","env_particle_glow"],["name1","4320_-5856_7012","env_particle_glow"],["TSTARTDEST","14464_13120_12244","info_teleport_destination"],["CTSTARTDEST","8128_13120_12244","info_teleport_destination"],["name2","11296_13120_12520","env_particle_glow"],["name1","11296_13120_12556","env_particle_glow"],["TSTARTDEST","4736_7008_-5172","info_teleport_destination"],["CTSTARTDEST","6016_8288_-5172","info_teleport_destination"],["name2","5376_7648_-3404","env_particle_glow"],["name1","5376_7648_-3368","env_particle_glow"],["TSTARTDEST","12257_7814_-5339","info_teleport_destination"],["CTSTARTDEST","12256_5120_-5320","info_teleport_destination"],["CTSTARTDEST","8416_-10320_-8620","info_teleport_destination"],["TSTARTDEST","8416_-9312_-8620","info_teleport_destination"],["name1","8432_-9824_-8492","env_particle_glow"],["name2","8432_-9824_-8528","env_particle_glow"],["CTSTARTDEST","-4752_-9056_-6956","info_teleport_destination"],["TSTARTDEST","-4838_-9056_-6966","info_teleport_destination"],["name1","-4832_-8896_-7836","env_particle_glow"],["name2","-4832_-8896_-7872","env_particle_glow"],["name2","-2688_-14368_-13120","env_particle_glow"],["name1","-2688_-14368_-13084","env_particle_glow"],["CTSTARTDEST","-9960_-11992_-4203","info_teleport_destination"],["TSTARTDEST","-9888_-11992_-4203","info_teleport_destination"],["name1","-9920_-12032_-4000","env_particle_glow"],["name2","-9920_-12032_-4036","env_particle_glow"],["CTSTARTDEST","-12936_-4808_-500","info_teleport_destination"],["TSTARTDEST","-10392_-4824_-500","info_teleport_destination"],["name2","-11648_-4816_-4","env_particle_glow"],["name1","-11648_-4816_32","env_particle_glow"],["ad_maker","5760_7648_-5232","env_entity_maker"],["ad_maker","5504_7648_-5232","env_entity_maker"],["ad_maker","5248_7648_-5232","env_entity_maker"],["ad_maker","4992_7648_-5232","env_entity_maker"],["ad_maker","6016_7648_-5408","env_entity_maker"],["ad_maker","5760_7648_-5408","env_entity_maker"],["ad_maker","5504_7648_-5408","env_entity_maker"],["ad_maker","5248_7648_-5408","env_entity_maker"],["ad_maker","4992_7648_-5408","env_entity_maker"],["ad_maker","4736_7648_-5408","env_entity_maker"],["ad_maker","4736_7648_-5232","env_entity_maker"],["range_maker","8392_-8903_-8692","env_entity_maker"],["range_maker","8412_-8903_-8693","env_entity_maker"],["range_maker","8432_-8903_-8693","env_entity_maker"],["range_maker","8452_-8903_-8693","env_entity_maker"],["range_maker","8472_-8903_-8693","env_entity_maker"],["range_maker","8392_-10743_-8692","env_entity_maker"],["range_maker","8412_-10743_-8692","env_entity_maker"],["range_maker","8432_-10743_-8692","env_entity_maker"],["range_maker","8452_-10743_-8692","env_entity_maker"],["range_maker","8472_-10743_-8692","env_entity_maker"],["name2","-176_14512_12472","env_particle_glow"],["name1","-176_14512_12508","env_particle_glow"],["TSTARTDEST","-2136_-3648_6180","info_teleport_destination"],["CTSTARTDEST","-2400_-3648_6164","info_teleport_destination"],["name2","-2272_-3648_6660","env_particle_glow"],["name1","-2272_-3648_6696","env_particle_glow"],["TSTARTDEST","6128_-128_-6644","info_teleport_destination"],["CTSTARTDEST","4656_-128_-6644","info_teleport_destination"],["name2","5392_-128_-4812","env_particle_glow"],["name1","5392_-128_-4776","env_particle_glow"],["TSTARTDEST","-6656_-1600_10948","info_teleport_destination"],["CTSTARTDEST","-6656_1336_10948","info_teleport_destination"],["name2","-6656_-128_11168","env_particle_glow"],["name1","-6656_-128_11204","env_particle_glow"],["TSTARTDEST","3104_6304_1988","info_teleport_destination"],["CTSTARTDEST","160_3360_1988","info_teleport_destination"],["name2","1632_4832_2388","env_particle_glow"],["name1","1632_4832_2424","env_particle_glow"],["name2","12416_-13696_-1440","env_particle_glow"],["name1","12416_-13696_-1404","env_particle_glow"]],"colors":[["explosion_ball","0_200_0"],["explosion_ball","0_225_0"],["explosion_ball","0_255_0"],["explosion_ball","100_110_0"],["explosion_ball","10_200_0"],["explosion_ball","110_100_0"],["explosion_ball","120_90_0"],["explosion_ball","130_80_0"],["explosion_ball","150_60_0"],["explosion_ball","180_40_0"],["explosion_ball","20_190_0"],["explosion_ball","210_20_0"],["explosion_ball","240_10_0"],["explosion_ball","255_0_0"],["explosion_ball","30_180_0"],["explosion_ball","40_170_0"],["explosion_ball","50_160_0"],["explosion_ball","60_150_0"],["explosion_ball","70_140_0"],["explosion_ball","80_130_0"],["explosion_ball","90_120_0"],["explosion_ball1","0_200_0"],["explosion_ball1","0_225_0"],["explosion_ball1","0_255_0"],["explosion_ball1","100_110_0"],["explosion_ball1","10_200_0"],["explosion_ball1","110_100_0"],["explosion_ball1","120_90_0"],["explosion_ball1","130_80_0"],["explosion_ball1","150_60_0"],["explosion_ball1","180_40_0"],["explosion_ball1","20_190_0"],["explosion_ball1","210_20_0"],["explosion_ball1","240_10_0"],["explosion_ball1","255_0_0"],["explosion_ball1","30_180_0"],["explosion_ball1","40_170_0"],["explosion_ball1","50_160_0"],["explosion_ball1","60_150_0"],["explosion_ball1","70_140_0"],["explosion_ball1","80_130_0"],["explosion_ball1","90_120_0"],["explosion_ball2","0_200_0"],["explosion_ball2","0_225_0"],["explosion_ball2","0_255_0"],["explosion_ball2","100_110_0"],["explosion_ball2","10_200_0"],["explosion_ball2","110_100_0"],["explosion_ball2","120_90_0"],["explosion_ball2","130_80_0"],["explosion_ball2","150_60_0"],["explosion_ball2","180_40_0"],["explosion_ball2","20_190_0"],["explosion_ball2","210_20_0"],["explosion_ball2","240_10_0"],["explosion_ball2","255_0_0"],["explosion_ball2","30_180_0"],["explosion_ball2","40_170_0"],["explosion_ball2","50_160_0"],["explosion_ball2","60_150_0"],["explosion_ball2","70_140_0"],["explosion_ball2","80_130_0"],["explosion_ball2","90_120_0"]],"overlays":["ad_overlay","blindspot_overlay","doge_overlay","falldamageoverlay","spawn_overlay","sur_overlay_blue","sur_overlay_brown","sur_overlay_cyan","sur_overlay_green","sur_overlay_objective","sur_overlay_orange","sur_overlay_pink","sur_overlay_purple","sur_overlay_red","sur_overlay_white","sur_overlay_yellow","vip_overlay"],"roundEnd":[["swag_io_script","RunScriptInput","Hide_blindspot_overlay",0.0],["bs_timer","Kill","",0.0],["swag_io_script","RunScriptInput","Hide_blindspot_overlay",1.0],["swag_io_script","RunScriptInput","Hide_blindspot_overlay",2.0]]};
/** @type {Record<string, { team: number, boxes: number[][][] }>} */
const SWEEPS = {"spawn_CTport": {"team": 3, "boxes": [[[-352.0, 1088.0, 32.0], [352.0, 1440.0, 320.0]], [[-1088.0, -1088.0, -1728.0], [1088.0, 1088.0, 352.0]]]}, "spawn_Tport": {"team": 2, "boxes": [[[-352.0, 1088.0, 32.0], [352.0, 1440.0, 320.0]], [[-1088.0, -1088.0, -1728.0], [1088.0, 1088.0, 352.0]]]}};
/** @type {{ name: string, box: number[][], yaw: number, speed: number }[]} */
const CONVEYORS = [{"name": "slide_convey", "box": [[8672.0, 11264.0, 12176.0], [14432.0, 11776.0, 12177.0]], "yaw": 180.0, "speed": 600.0}, {"name": "slide_convey", "box": [[8160.0, 11264.0, 12176.0], [8672.0, 14464.0, 12177.0]], "yaw": 90.0, "speed": 600.0}, {"name": "slide_convey", "box": [[13920.0, 11776.0, 12176.0], [14432.0, 14976.0, 12177.0]], "yaw": 270.0, "speed": 600.0}, {"name": "slide_convey", "box": [[8160.0, 14464.0, 12176.0], [13920.0, 14976.0, 12177.0]], "yaw": 0.0, "speed": 600.0}];
/** @typedef {import("cs_script/point_script").Vector} Vector */
/** @typedef {import("cs_script/point_script").QAngle} QAngle */

const SCRIPT_NAME = "swag_io_script";
const BASE_SPEED = 250;                                 // knife run speed
const WALK_FACTOR = 0.52, DUCK_FACTOR = 0.34;

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
/** @param {string} s  "x_y_z" / "r_g_b" -> numbers */
function nums(s) { return s.split("_").map(Number); }

// ---------------------------------------------------------------- player render alpha / colour / position
for (const a of DATA.alphas) {
    Instance.OnScriptInput("SetAlpha_" + a, ({ activator }) => {
        const pawn = toPawn(activator);
        if (!pawn || !pawn.IsValid()) return;
        const c = pawn.GetColor();
        pawn.SetColor({ r: c.r, g: c.g, b: c.b, a });
    });
}
/** @param {BaseModelEntity} ent @param {number[]} rgb */
function tint(ent, [r, g, b]) {
    if (ent && ent.IsValid()) ent.SetColor({ r, g, b, a: ent.GetColor().a });
}
const WEAPON_SLOTS = [CSGearSlot.RIFLE, CSGearSlot.PISTOL, CSGearSlot.KNIFE, CSGearSlot.GRENADES, CSGearSlot.C4];
for (const c of DATA.playerColors) {
    const rgb = nums(c);
    Instance.OnScriptInput("SetColor_" + c, ({ activator }) => {
        const pawn = toPawn(activator);
        if (pawn) tint(pawn, rgb);
    });
    Instance.OnScriptInput("ColorAllPlayers_" + c, () => {
        for (const pawn of livePawns()) {
            tint(pawn, rgb);
            for (const slot of WEAPON_SLOTS) {
                const w = pawn.FindWeaponBySlot(slot);
                if (w) tint(w, rgb);
            }
        }
    });
}
for (const o of DATA.playerOrigins) {
    const [x, y, z] = nums(o);
    Instance.OnScriptInput("SetOrigin_" + o, ({ activator }) => {
        const pawn = toPawn(activator);
        if (pawn && pawn.IsValid()) pawn.Teleport({ position: { x, y, z } });
    });
}

// ---------------------------------------------------------------- player_speedmod (think loop)
/** @type {Map<number, number>} player slot -> speed multiplier */
const speedBySlot = new Map();
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
    conveyorThink(dt);
    physThink(now, dt);
    winnerThink(now);
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

// ---------------------------------------------------------------- spawn strip (unnamed "Strip First" game_player_equip)
// CS:GO ran it on every spawn, so everyone started with nothing (the games hand out their own weapons).
// CS2 doesn't run non-"Use Only" equips on spawn: no default loadout, and strip every (re)spawning player.
const NO_DEFAULT_LOADOUT = ["mp_t_default_melee", "mp_ct_default_melee", "mp_t_default_secondary", "mp_ct_default_secondary",
                            "mp_t_default_primary", "mp_ct_default_primary", "mp_t_default_grenades", "mp_ct_default_grenades"];
Instance.OnPlayerReset(({ player }) => {
    const slot = player.GetPlayerController()?.GetPlayerSlot();
    if (slot !== undefined) speedBySlot.delete(slot);
    if (player && player.IsValid()) {
        player.DestroyWeapons();
        player.SetColor({ r: 255, g: 255, b: 255, a: 255 });           // CS:GO players respawned with default render colour
    }
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
        if (pawn && pawn.IsValid()) teleportTo(tele, pawn);
    });
}
/** @param {string} tele @param {CSPlayerPawn} pawn */
function teleportTo(tele, pawn) {
    if (!currentDest[tele]) return;
    const dest = Instance.FindEntityByName(currentDest[tele]);
    if (!dest || !dest.IsValid()) return;
    // like trigger_teleport: move to the destination (read now - the buttons move it), take its facing, stop all movement
    const angles = dest.GetAbsAngles();
    pawn.Teleport({ position: dest.GetAbsOrigin(), angles: { pitch: 0, yaw: angles.yaw, roll: 0 }, velocity: { x: 0, y: 0, z: 0 } });
    pawn.SetEyeAngles(angles);
}
// The lobby teleporters are switched on while everyone is standing in them; a CS2 trigger only reports players who walk in
// afterwards, so the map also sweeps them: everyone of the right team inside the teleporter's area goes now.
/** @param {{x:number,y:number,z:number}} p @param {number[][]} b */
function inBox(p, b) {
    return p.x >= b[0][0] - 16 && p.x <= b[1][0] + 16 && p.y >= b[0][1] - 16 && p.y <= b[1][1] + 16 && p.z >= b[0][2] - 16 && p.z <= b[1][2] + 16;
}
for (const [tele, info] of Object.entries(SWEEPS)) {
    Instance.OnScriptInput("Sweep_" + tele, () => {
        for (const pawn of livePawns()) {
            if (pawn.GetTeamNumber() !== info.team) continue;
            const p = pawn.GetAbsOrigin();
            if (info.boxes.some(b => inBox(p, b))) teleportTo(tele, pawn);
        }
    });
}
// lobby trigger_teleports: arrive standing still (the lobby trigger_pushes otherwise carry the speed through)
Instance.OnScriptInput("ZeroVelocity", ({ activator }) => {
    const pawn = toPawn(activator);
    if (pawn && pawn.IsValid()) pawn.Teleport({ velocity: { x: 0, y: 0, z: 0 } });
});

// ---------------------------------------------------------------- AddOutput "origin": makers, sprites, teleport destinations
for (const [name, xyz, cls] of DATA.moves) {
    const [x, y, z] = nums(xyz);
    Instance.OnScriptInput(`MoveTo_${name}__${xyz}`, () => {
        for (const ent of Instance.FindEntitiesByName(name)) ent.Teleport({ position: { x, y, z } });
        if (cls === "env_particle_glow") {
            // restart the sprite so it is drawn at its new position (they are always on in this map)
            Instance.EntFireAtName({ name, input: "DestroyImmediately" });
            Instance.EntFireAtName({ name, input: "Start", delay: 0.05 });
        }
    });
}

// ---------------------------------------------------------------- prop colours
for (const [target, rgbs] of DATA.colors) {
    const rgb = nums(rgbs);
    Instance.OnScriptInput(`Color_${target}__${rgbs}`, () => {
        for (const ent of Instance.FindEntitiesByName(target)) if (ent instanceof BaseModelEntity) tint(ent, rgb);
    });
}

// ---------------------------------------------------------------- screen overlays (shown to everyone, like env_screenoverlay)
const LAYOUT_NAME = "swag_overlay_layout";
/** @type {Set<string>} overlays that were killed this round */
const killedOverlays = new Set();
/** @param {string} panelId @param {boolean} visible */
function setOverlay(panelId, visible) {
    const ent = Instance.FindEntityByName(LAYOUT_NAME);
    if (ent instanceof CustomHudLayout) ent.SetHasClass(panelId, "Hidden", !visible);
}
for (const o of DATA.overlays) {
    Instance.OnScriptInput("Show_" + o, () => {
        if (o === INTRO) { showIntro(); return; }
        if (!killedOverlays.has(o)) setOverlay(o, true);
    });
    Instance.OnScriptInput("Hide_" + o, () => setOverlay(o, false));
    Instance.OnScriptInput("Kill_" + o, () => { killedOverlays.add(o); setOverlay(o, false); });
}

// ---------------------------------------------------------------- map credits overlay: first two rounds only
// logic_auto shows spawn_overlay for 7 s; it now only shows in the first two rounds of the map and the script hides it itself.
const INTRO = "spawn_overlay", INTRO_ROUNDS = 2, INTRO_TIME = 7;
let introRounds = 0, lastRoundSignal = -100, introShownRound = 0;
function roundSignal() {
    const now = Instance.GetGameTime();
    if (now - lastRoundSignal > 3) introRounds++;
    lastRoundSignal = now;
}
function showIntro() {
    roundSignal();
    if (introRounds > INTRO_ROUNDS || introShownRound === introRounds) return;
    introShownRound = introRounds;
    setOverlay(INTRO, true);
    Instance.EntFireAtName({ name: SCRIPT_NAME, input: "RunScriptInput", value: "Hide_" + INTRO, delay: INTRO_TIME });
}
Instance.OnRoundStart(() => roundSignal());

// ---------------------------------------------------------------- conveyors (slide)
// CS:GO func_conveyor carried players standing on it; CS2's only drags physics objects. While a player is on the ground on
// one, their speed is set to the belt speed plus their own walking (like CS:GO's base velocity).
/** @type {Record<string, number>} conveyor name -> current speed */
const conveyorSpeed = {};
function resetConveyors() { for (const c of CONVEYORS) conveyorSpeed[c.name] = c.speed; }
resetConveyors();
for (const name of new Set(CONVEYORS.map(c => c.name))) {
    for (const s of [0]) Instance.OnScriptInput(`ConveyorSpeed_${name}__${s}`, () => { conveyorSpeed[name] = s; });
}
const BELTS = CONVEYORS.map(c => ({ name: c.name, mins: { x: c.box[0][0], y: c.box[0][1], z: c.box[0][2] }, maxs: { x: c.box[1][0], y: c.box[1][1], z: c.box[1][2] },
    dx: Math.cos(c.yaw * Math.PI / 180), dy: Math.sin(c.yaw * Math.PI / 180) }));
/** @param {CSPlayerPawn} pawn @returns {{ x: number, y: number }} the player's own walking velocity from their keys */
function walkVelocity(pawn) {
    const fwd = (pawn.IsInputPressed(CSInputs.FORWARD) ? 1 : 0) - (pawn.IsInputPressed(CSInputs.BACK) ? 1 : 0);
    const side = (pawn.IsInputPressed(CSInputs.RIGHT) ? 1 : 0) - (pawn.IsInputPressed(CSInputs.LEFT) ? 1 : 0);
    if (fwd === 0 && side === 0) return { x: 0, y: 0 };
    const yaw = pawn.GetEyeAngles().yaw * Math.PI / 180;
    let dx = Math.cos(yaw) * fwd + Math.sin(yaw) * side, dy = Math.sin(yaw) * fwd - Math.cos(yaw) * side;
    const len = Math.hypot(dx, dy);
    let speed = BASE_SPEED;
    if (pawn.IsInputPressed(CSInputs.WALK)) speed *= WALK_FACTOR;
    if (pawn.IsDucking()) speed *= DUCK_FACTOR;
    return { x: dx / len * speed, y: dy / len * speed };
}
/** @param {number} dt */
function conveyorThink(dt) {
    for (const pawn of livePawns()) {
        if (!pawn.GetGroundEntity() || pawn.GetMoveType() !== CSMoveType.WALK) continue;
        const p = pawn.GetAbsOrigin();
        const belt = BELTS.find(b => p.x >= b.mins.x && p.x <= b.maxs.x && p.y >= b.mins.y && p.y <= b.maxs.y && p.z >= b.mins.z - 4 && p.z <= b.maxs.z + 8);
        if (!belt) continue;
        const speed = conveyorSpeed[belt.name] ?? 0;
        if (speed <= 0) continue;
        const w = walkVelocity(pawn);
        pawn.Move({ velocity: { x: belt.dx * speed + w.x, y: belt.dy * speed + w.y, z: pawn.GetAbsVelocity().z } });
    }
}

// ---------------------------------------------------------------- lobby race winner -> game picker room
// The race winner (spawn_tele) drops down a shaft to spawn_telewinner, which sends them to the picker room (spawn_winnerdest2).
// Safety net: if 3 s later they're neither in the picker room nor still falling down the shaft, put them in the picker room.
const PICKER_ROOM = { mins: { x: -480, y: -480, z: -820 }, maxs: { x: 480, y: 480, z: -660 } };
const WINNER_SHAFT = { mins: { x: 330, y: -54, z: 400 }, maxs: { x: 406, y: 22, z: 2200 } };
/** @type {CSPlayerPawn | undefined} */
let lobbyWinner = undefined;
let winnerCheckAt = 0, winnerGiveUpAt = 0;
Instance.OnScriptInput("LobbyWinner", ({ activator }) => {
    const pawn = toPawn(activator);
    if (!pawn || !pawn.IsValid()) return;
    lobbyWinner = pawn;
    winnerCheckAt = Instance.GetGameTime() + 3;
    winnerGiveUpAt = Instance.GetGameTime() + 10;
});
/** @param {Vector} p @param {{ mins: Vector, maxs: Vector }} b */
function inRegion(p, b) { return p.x >= b.mins.x && p.x <= b.maxs.x && p.y >= b.mins.y && p.y <= b.maxs.y && p.z >= b.mins.z && p.z <= b.maxs.z; }
/** @param {number} now */
function winnerThink(now) {
    if (!lobbyWinner || now < winnerCheckAt) return;
    const pawn = lobbyWinner;
    if (!pawn.IsValid() || !pawn.IsAlive() || now > winnerGiveUpAt) { lobbyWinner = undefined; return; }
    const p = pawn.GetAbsOrigin();
    if (inRegion(p, PICKER_ROOM)) { lobbyWinner = undefined; return; }
    if (inRegion(p, WINNER_SHAFT)) { winnerCheckAt = now + 0.5; return; }
    const dest = Instance.FindEntityByName("spawn_winnerdest2");
    if (dest && dest.IsValid()) pawn.Teleport({ position: dest.GetAbsOrigin(), velocity: { x: 0, y: 0, z: 0 } });
    lobbyWinner = undefined;
}

// ---------------------------------------------------------------- ball physics
// CS:GO ran phys_pushscale 900 (knife and bullet hits sent balls flying) and cs_enable_player_physics_box 1 (players shove
// balls by running into them). Both are gone or blocked in CS2, so hits and running into a ball set its velocity here.
/** @type {{ prefix: string, hit: number, lift: number, run: boolean }[]} */
const PHYS = [
    { prefix: "foot_ball", hit: 900, lift: 200, run: true },
    { prefix: "explosion_ball", hit: 800, lift: 200, run: true },
    { prefix: "balls_ball", hit: 800, lift: 200, run: true },
];
const PHYS_CLASSES = ["prop_physics", "prop_physics_override", "prop_physics_multiplayer"];
const KNIFE_RANGE = 72, RUN_REACH = 30, RUN_MIN_SPEED = 60, RUN_BOOST = 1.4;
/** @param {Entity | undefined} ent */
function physRule(ent) {
    if (!ent || !ent.IsValid()) return undefined;
    const n = ent.GetEntityName();
    return n ? PHYS.find(r => n.startsWith(r.prefix)) : undefined;
}
/** @param {Entity} ent @param {Vector} dir @param {number} speed @param {number} lift */
function launch(ent, dir, speed, lift) {
    const v = { x: dir.x * speed, y: dir.y * speed, z: dir.z * speed };
    if (v.z < lift) v.z = lift;
    ent.Teleport({ velocity: v });
}
/** @param {QAngle} a */
function forward(a) {
    const p = a.pitch * Math.PI / 180, y = a.yaw * Math.PI / 180;
    return { x: Math.cos(p) * Math.cos(y), y: Math.cos(p) * Math.sin(y), z: -Math.sin(p) };
}
Instance.OnBulletImpact(({ weapon, position, hitEntity }) => {
    const rule = physRule(hitEntity);
    const shooter = weapon?.GetOwner();
    if (!rule || !hitEntity || !shooter || !shooter.IsValid()) return;
    const e = shooter.GetEyePosition();
    const x = position.x - e.x, y = position.y - e.y, z = position.z - e.z, l = Math.hypot(x, y, z) || 1;
    launch(hitEntity, { x: x / l, y: y / l, z: z / l }, rule.hit, rule.lift);
});
Instance.OnKnifeAttack(({ weapon }) => {
    const pawn = weapon?.GetOwner();
    if (!pawn || !pawn.IsValid()) return;
    const eye = pawn.GetEyePosition(), dir = forward(pawn.GetEyeAngles());
    const end = { x: eye.x + dir.x * KNIFE_RANGE, y: eye.y + dir.y * KNIFE_RANGE, z: eye.z + dir.z * KNIFE_RANGE };
    const tr = Instance.TraceSphere({ radius: 8, start: eye, end, ignoreEntity: pawn, ignorePlayers: true });
    const rule = physRule(tr.hitEntity);
    if (rule && tr.hitEntity) launch(tr.hitEntity, dir, rule.hit, rule.lift);
});
/** @type {Entity[]} */
let balls = [];
let nextBallScan = 0;
/** @type {Map<Entity, number>} */
const lastShove = new Map();
/** @param {number} now @param {number} dt */
function physThink(now, dt) {
    if (now >= nextBallScan) {
        nextBallScan = now + 0.5;
        balls = [];
        for (const cls of PHYS_CLASSES) for (const ent of Instance.FindEntitiesByClass(cls)) if (physRule(ent)?.run) balls.push(ent);
    }
    if (balls.length === 0) return;
    const pawns = livePawns();
    for (const ball of balls) {
        if (!ball.IsValid() || now - (lastShove.get(ball) ?? 0) < 0.08) continue;
        const bp = ball.GetAbsOrigin();
        let v = ball.GetAbsVelocity();
        for (const pawn of pawns) {
            const pp = pawn.GetAbsOrigin();
            const dz = bp.z - pp.z;
            if (dz < -16 || dz > 80) continue;
            const dx = bp.x - pp.x, dy = bp.y - pp.y, d = Math.hypot(dx, dy);
            if (d > RUN_REACH || d < 0.01) continue;
            const pv = pawn.GetAbsVelocity();
            const ax = dx / d, ay = dy / d;
            const toward = pv.x * ax + pv.y * ay;
            if (toward < RUN_MIN_SPEED) continue;
            const want = toward * RUN_BOOST, have = v.x * ax + v.y * ay;
            if (have >= want) continue;
            v = { x: v.x + ax * (want - have), y: v.y + ay * (want - have), z: Math.max(v.z, 60) };
            ball.Teleport({ velocity: v });
            lastShove.set(ball, now);
            break;
        }
    }
}

// ---------------------------------------------------------------- round flow
Instance.OnActivate(() => {
    for (const cvar of NO_DEFAULT_LOADOUT) Instance.ServerCommand(`${cvar} ""`);
    ensureThink();
});
// game_round_end "roundend" OnRoundEnded
Instance.OnRoundEnd(() => {
    for (const [name, input, value, delay] of DATA.roundEnd) Instance.EntFireAtName({ name, input, value, delay });
});
// Each round starts like the map was built (CS:GO respawned map entities each round).
Instance.OnBeginRoundRestart(() => {
    for (const [tele, info] of Object.entries(DATA.teleporters)) currentDest[tele] = info.initial;
    speedBySlot.clear();
    killedOverlays.clear();
    for (const o of DATA.overlays) setOverlay(o, false);
    resetConveyors();
    lobbyWinner = undefined;
    balls = [];
    nextBallScan = 0;
    lastShove.clear();
});
