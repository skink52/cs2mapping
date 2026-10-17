import { Instance, Entity, CSPlayerPawn, CSPlayerController, CSInputs, CSDamageFlags, CSMoveType, CSGearSlot } from "cs_script/point_script";

// mg_mario_party: CS2 replacements for CS:GO I/O tricks that no longer exist.
// Everything here is driven by `mario_io_script` -> RunScriptInput <input name>, with the touching player as activator.
//
//   SetName_<name>           replaces  !activator AddOutput "targetname <name>"   (feeds every filter_activator_name)
//   SetAlpha_<n>             replaces  !activator Alpha <n> (+ AddOutput rendermode 1)
//   SetColor_<r>_<g>_<b>     replaces  !activator Color <r g b>
//   Speed_<x>                replaces  player_speedmod SpeedMod ModifySpeed <x>  (0 = frozen, 1 = normal, 2/3 = faster)
//   SetDest_<tele>__<dest>   replaces  <tele> AddOutput "target <dest>"          (trigger_teleport Remote Destination)
//   Teleport_<tele>          fired by the teleporter trigger's OnStartTouch
//   EndRound_CTWin / _TWin   replaces  game_round_end EndRound_CounterTerroristsWin / EndRound_TerroristsWin
//   ResetAngles_boulder_maker replaces boulder_maker AddOutput "angles 0 0 0"
//   Gravity_<x>              replaces  trigger_gravity (player gravity scale <x>; 1 = normal)
//   BlockFortTele_t / _ct    replaces  block_fort_teleporter_t/_ct + sorter (random Block Fort spawn per player)
//   DogStart                 replaces  the chain chomp's 16 phys_thrusters (script glides Dog_box after "Dog_Chase")
//   (automatic)              spawn strip: replaces the map's spawn-time game_player_equip strip (no input needed)
//   Equip_<equip>            replaces  <game_player_equip> TriggerForActivatedPlayer (gives only weapons the player doesn't have)
//   BulletFire_<push trigger> replaces  bullet bill trigger_push Enable/Disable (flies the cannon's bullet straight out)
//
// The data block below is generated from the map by the port tooling.

/** @type {{ names: string[], speeds: number[], alphas: number[], colors: number[][], teleporters: Record<string, { initial: string, dests: string[] }> }} */
const DATA = {
    "names": [
        "0",
        "Dog_Chase",
        "HaveBox",
        "TeleReady",
        "Winner",
        "marine",
        "mushroom",
        "nothing",
        "p",
        "predator"
    ],
    "speeds": [
        0.0,
        1.0,
        2.0,
        3.0
    ],
    "alphas": [
        5,
        30,
        255
    ],
    "colors": [
        [
            96,
            96,
            96
        ],
        [
            255,
            255,
            255
        ]
    ],
    "teleporters": {
        "Pipe_islands_tele_1": {
            "initial": "",
            "dests": [
                "floating_islands_dest_1",
                "floating_islands_dest_2",
                "floating_islands_dest_3",
                "floating_islands_dest_4",
                "floating_islands_dest_5",
                "floating_islands_dest_6"
            ]
        },
        "Pipe_islands_tele_1_ct": {
            "initial": "",
            "dests": [
                "floating_islands_dest_1_ct",
                "floating_islands_dest_2_ct",
                "floating_islands_dest_3_ct",
                "floating_islands_dest_4_ct",
                "floating_islands_dest_5_ct",
                "floating_islands_dest_6_ct"
            ]
        },
        "Pipe_islands_tele_2": {
            "initial": "",
            "dests": [
                "floating_islands_dest_1",
                "floating_islands_dest_2",
                "floating_islands_dest_3",
                "floating_islands_dest_4",
                "floating_islands_dest_5",
                "floating_islands_dest_6"
            ]
        },
        "Pipe_islands_tele_2_ct": {
            "initial": "",
            "dests": [
                "floating_islands_dest_1_ct",
                "floating_islands_dest_2_ct",
                "floating_islands_dest_3_ct",
                "floating_islands_dest_4_ct",
                "floating_islands_dest_5_ct",
                "floating_islands_dest_6_ct"
            ]
        },
        "Pipe_islands_tele_3": {
            "initial": "",
            "dests": [
                "floating_islands_dest_1",
                "floating_islands_dest_2",
                "floating_islands_dest_3",
                "floating_islands_dest_4",
                "floating_islands_dest_5",
                "floating_islands_dest_6"
            ]
        },
        "Pipe_islands_tele_3_ct": {
            "initial": "",
            "dests": [
                "floating_islands_dest_1_ct",
                "floating_islands_dest_2_ct",
                "floating_islands_dest_3_ct",
                "floating_islands_dest_4_ct",
                "floating_islands_dest_5_ct",
                "floating_islands_dest_6_ct"
            ]
        },
        "Pipe_islands_tele_4": {
            "initial": "",
            "dests": [
                "floating_islands_dest_1",
                "floating_islands_dest_2",
                "floating_islands_dest_3",
                "floating_islands_dest_4",
                "floating_islands_dest_5",
                "floating_islands_dest_6"
            ]
        },
        "Pipe_islands_tele_4_ct": {
            "initial": "",
            "dests": [
                "floating_islands_dest_1_ct",
                "floating_islands_dest_2_ct",
                "floating_islands_dest_3_ct",
                "floating_islands_dest_4_ct",
                "floating_islands_dest_5_ct",
                "floating_islands_dest_6_ct"
            ]
        },
        "Pipe_islands_tele_5": {
            "initial": "",
            "dests": [
                "floating_islands_dest_1",
                "floating_islands_dest_2",
                "floating_islands_dest_3",
                "floating_islands_dest_4",
                "floating_islands_dest_5",
                "floating_islands_dest_6"
            ]
        },
        "Pipe_islands_tele_5_ct": {
            "initial": "",
            "dests": [
                "floating_islands_dest_1_ct",
                "floating_islands_dest_2_ct",
                "floating_islands_dest_3_ct",
                "floating_islands_dest_4_ct",
                "floating_islands_dest_5_ct",
                "floating_islands_dest_6_ct"
            ]
        },
        "Pipe_islands_tele_6": {
            "initial": "",
            "dests": [
                "floating_islands_dest_1",
                "floating_islands_dest_2",
                "floating_islands_dest_3",
                "floating_islands_dest_4",
                "floating_islands_dest_5",
                "floating_islands_dest_6"
            ]
        },
        "Pipe_islands_tele_6_ct": {
            "initial": "",
            "dests": [
                "floating_islands_dest_1_ct",
                "floating_islands_dest_2_ct",
                "floating_islands_dest_3_ct",
                "floating_islands_dest_4_ct",
                "floating_islands_dest_5_ct",
                "floating_islands_dest_6_ct"
            ]
        },
        "block_fort_teleporter_ct": {
            "initial": "",
            "dests": [
                "BlockFort_ct_dest_1",
                "BlockFort_ct_dest_10",
                "BlockFort_ct_dest_11",
                "BlockFort_ct_dest_12",
                "BlockFort_ct_dest_13",
                "BlockFort_ct_dest_14",
                "BlockFort_ct_dest_15",
                "BlockFort_ct_dest_16",
                "BlockFort_ct_dest_2",
                "BlockFort_ct_dest_3",
                "BlockFort_ct_dest_4",
                "BlockFort_ct_dest_5",
                "BlockFort_ct_dest_6",
                "BlockFort_ct_dest_7",
                "BlockFort_ct_dest_8",
                "BlockFort_ct_dest_9"
            ]
        },
        "block_fort_teleporter_t": {
            "initial": "",
            "dests": [
                "BlockFort_t_dest_1",
                "BlockFort_t_dest_10",
                "BlockFort_t_dest_11",
                "BlockFort_t_dest_12",
                "BlockFort_t_dest_13",
                "BlockFort_t_dest_14",
                "BlockFort_t_dest_15",
                "BlockFort_t_dest_16",
                "BlockFort_t_dest_2",
                "BlockFort_t_dest_3",
                "BlockFort_t_dest_4",
                "BlockFort_t_dest_5",
                "BlockFort_t_dest_6",
                "BlockFort_t_dest_7",
                "BlockFort_t_dest_8",
                "BlockFort_t_dest_9"
            ]
        },
        "floating_islands_tele": {
            "initial": "",
            "dests": [
                "floating_islands_dest_1",
                "floating_islands_dest_2",
                "floating_islands_dest_3",
                "floating_islands_dest_4",
                "floating_islands_dest_5",
                "floating_islands_dest_6"
            ]
        },
        "floating_islands_tele_ct": {
            "initial": "",
            "dests": [
                "floating_islands_dest_1_ct",
                "floating_islands_dest_2_ct",
                "floating_islands_dest_3_ct",
                "floating_islands_dest_4_ct",
                "floating_islands_dest_5_ct",
                "floating_islands_dest_6_ct"
            ]
        },
        "game_tele_CT": {
            "initial": "",
            "dests": [
                "CannonGameTeleDestCT",
                "Chomp_knife_dest_ct",
                "Tele_Dest_Climb_ct",
                "block_fort_tele_dest_ct",
                "chain_chomp_dest_ct",
                "ct_dest_random_gun_game_1",
                "ct_dest_random_gun_game_2",
                "ct_dest_random_gun_game_3",
                "ct_dest_thwomp_falls",
                "ct_spawn_dest",
                "ct_spawn_ka",
                "ct_thwomp_awp_dest",
                "fightyard_dest_ct",
                "floating_islands_dest_ct",
                "hexagon_heat_destCT",
                "hg_field_destCT",
                "mario_says_destCT",
                "mvp_ct_dest",
                "pirate_climb_destCT",
                "pirate_island_destCT",
                "platform_peril_destCT",
                "scoutzknivez_dest_ct",
                "skipping_tele_destCT",
                "speed_smg_ct",
                "summer_destCT"
            ]
        },
        "game_tele_T": {
            "initial": "",
            "dests": [
                "CannonGameTeleDestT",
                "Chomp_knife_dest_t",
                "Tele_Dest_Climb_t",
                "block_fort_tele_dest_t",
                "chain_chomp_dest_t",
                "fightyard_dest_t",
                "floating_islands_dest_t",
                "hexagon_heat_destT",
                "hg_field_destT",
                "mario_says_destT",
                "mvp_t_dest",
                "pirate_climb_destT",
                "pirate_island_destT",
                "platform_peril_destT",
                "scoutzknivez_dest_t",
                "skipping_tele_destT",
                "speed_smg_t",
                "summer_destT",
                "t_dest_random_gun_game_1",
                "t_dest_random_gun_game_2",
                "t_dest_random_gun_game_3",
                "t_dest_thwomp_falls",
                "t_spawn_dest",
                "t_spawn_ka",
                "t_thwomp_awp_dest"
            ]
        },
        "mushroom_tele_1": {
            "initial": "",
            "dests": [
                "box1_mushroom_dest",
                "box2_mushroom_dest",
                "box3_mushroom_dest",
                "box4_mushroom_dest"
            ]
        }
    }
};

const TEAM_T = 2, TEAM_CT = 3;
const BASE_SPEED = 250;       // knife run speed; boosted speeds are multiples of this
// CS:GO's player_speedmod scaled the player's max speed, which depends on the weapon in hand (an SMG runs at 220-240,
// not the knife's 250), so the boosted speed is weapon speed x multiplier.
const WEAPON_SPEED = {
    weapon_glock: 240, weapon_hkp2000: 240, weapon_usp_silencer: 240, weapon_p250: 240, weapon_elite: 240, weapon_fiveseven: 240,
    weapon_tec9: 240, weapon_cz75a: 240, weapon_deagle: 230, weapon_revolver: 220, weapon_taser: 220,
    weapon_mac10: 240, weapon_mp9: 240, weapon_bizon: 240, weapon_mp5sd: 235, weapon_ump45: 230, weapon_p90: 230, weapon_mp7: 220,
    weapon_ak47: 215, weapon_galilar: 215, weapon_m4a1: 225, weapon_m4a1_silencer: 225, weapon_famas: 220, weapon_aug: 220, weapon_sg556: 210,
    weapon_awp: 200, weapon_ssg08: 230, weapon_g3sg1: 215, weapon_scar20: 215,
    weapon_nova: 220, weapon_xm1014: 215, weapon_mag7: 225, weapon_sawedoff: 210, weapon_m249: 195, weapon_negev: 150,
    weapon_hegrenade: 245, weapon_flashbang: 245, weapon_smokegrenade: 245, weapon_molotov: 245, weapon_incgrenade: 245, weapon_decoy: 245,
    weapon_c4: 250, weapon_healthshot: 250,
};
// The script sets the ground velocity once per tick and the player's own movement then applies ground friction
// (sv_friction 5.2) to it before moving, so the speed actually travelled was ~8% under the target (the "slightly slow"
// speed SMGs). Pre-scale by the friction the movement code takes off.
const FRICTION_COMP = 1 / (1 - 5.2 / 64);
/** @param {CSPlayerPawn} pawn */
function weaponSpeed(pawn) {
    const w = pawn.GetActiveWeapon();
    if (!w || !w.IsValid()) return BASE_SPEED;
    return WEAPON_SPEED[w.GetClassName()] ?? BASE_SPEED;
}
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

// ---------------------------------------------------------------- names
for (const name of DATA.names) {
    Instance.OnScriptInput("SetName_" + name, ({ activator }) => {
        const target = toPawn(activator) ?? activator;
        if (target && target.IsValid()) target.SetEntityName(name);
        // "mushroom" = just grabbed the spawn-box mushroom; send them up like mushroom_grabber_tele did in CS:GO
        const pawn = toPawn(activator);
        if (name === "mushroom") mlog(`SetName_mushroom from the map, activator ${activator ? activator.GetClassName() : 'none'}`);
        if (name === "mushroom" && pawn && pawn.IsValid()) Instance.EntFireAtName({ name: "mario_io_script", input: "RunScriptInput", value: "MushroomWinner", activator: pawn });
    });
}

// ---------------------------------------------------------------- render alpha / colour (players)
for (const a of DATA.alphas) {
    Instance.OnScriptInput("SetAlpha_" + a, ({ activator }) => {
        const pawn = toPawn(activator);
        if (!pawn || !pawn.IsValid()) return;
        const c = pawn.GetColor();
        pawn.SetColor({ r: c.r, g: c.g, b: c.b, a });
    });
}
for (const [r, g, b] of DATA.colors) {
    Instance.OnScriptInput(`SetColor_${r}_${g}_${b}`, ({ activator }) => {
        const pawn = toPawn(activator);
        if (!pawn || !pawn.IsValid()) return;
        pawn.SetColor({ r, g, b, a: pawn.GetColor().a });
    });
}

// ---------------------------------------------------------------- speed (player_speedmod) + gravity (trigger_gravity) replacements
// One think loop drives both, so a player who is boosted and in low gravity gets a single, combined velocity change.
/** @type {Map<number, number>} player slot -> speed multiplier (only non-1 values are stored) */
const speedBySlot = new Map();
/** @type {Map<number, number>} player slot -> gravity scale (only non-1 values are stored) */
const gravityBySlot = new Map();
const SV_GRAVITY = 800;                                 // CS2 default sv_gravity
let thinking = false;
let lastThink = 0;

function ensureThink() {
    if (thinking || (speedBySlot.size === 0 && gravityBySlot.size === 0 && !mushroom && !dog && flying.length === 0)) return;
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
        const v = pawn.GetAbsVelocity();
        let { x, y, z } = v;
        let changed = false;
        const onGround = !!pawn.GetGroundEntity();

        // trigger_gravity: CS2 players have no gravity scale, so while airborne give back the part of
        // gravity that the scale removes (0.25 gravity -> 75% of sv_gravity pushed back up every tick).
        const g = gravityBySlot.get(slot);
        if (g !== undefined && !onGround && pawn.GetMoveType() === CSMoveType.WALK) {
            z += (1 - g) * SV_GRAVITY * dt;
            changed = true;
        }

        const mult = speedBySlot.get(slot);
        if (mult === 0) {
            // frozen: no horizontal movement and no jumping
            x = 0; y = 0; z = Math.min(z, 0);
            changed = true;
        } else if (mult !== undefined && onGround) {    // keep air movement natural; boosted momentum carries into jumps
            const fwd = (pawn.IsInputPressed(CSInputs.FORWARD) ? 1 : 0) - (pawn.IsInputPressed(CSInputs.BACK) ? 1 : 0);
            const side = (pawn.IsInputPressed(CSInputs.RIGHT) ? 1 : 0) - (pawn.IsInputPressed(CSInputs.LEFT) ? 1 : 0);
            if (fwd !== 0 || side !== 0) {              // with no input, let normal friction stop the player
                const yaw = pawn.GetEyeAngles().yaw * Math.PI / 180;
                let dx = Math.cos(yaw) * fwd + Math.sin(yaw) * side;
                let dy = Math.sin(yaw) * fwd - Math.cos(yaw) * side;
                const len = Math.hypot(dx, dy); dx /= len; dy /= len;
                let speed = weaponSpeed(pawn) * mult * FRICTION_COMP;
                if (pawn.IsInputPressed(CSInputs.WALK)) speed *= WALK_FACTOR;
                if (pawn.IsDucking()) speed *= DUCK_FACTOR;
                x = dx * speed; y = dy * speed;
                changed = true;
            }
        }
        if (changed) pawn.Move({ velocity: { x, y, z } });
    }
    moveMushroom(now);
    moveDog(now);
    moveBullets(now, dt);
    if (speedBySlot.size > 0 || gravityBySlot.size > 0 || mushroom || dog || flying.length > 0) Instance.SetNextThink(now);
    else thinking = false;
});

/** @param {Entity | undefined} activator */
function slotOf(activator) {
    return toPawn(activator)?.GetPlayerController()?.GetPlayerSlot();
}

for (const s of DATA.speeds) {
    Instance.OnScriptInput("Speed_" + s, ({ activator }) => {
        const slot = slotOf(activator);
        if (slot === undefined) return;
        if (s === 1) speedBySlot.delete(slot); else speedBySlot.set(slot, s);
        ensureThink();
    });
}

// trigger_gravity replacements: Gravity_0.25 (gravity revolvers arena), Gravity_1 (lobby reset)
for (const g of [0.25, 1]) {
    Instance.OnScriptInput("Gravity_" + g, ({ activator }) => {
        const slot = slotOf(activator);
        if (slot === undefined) return;
        if (g === 1) gravityBySlot.delete(slot); else gravityBySlot.set(slot, g);
        ensureThink();
    });
}

// CS:GO reset speedmod on respawn; do the same, and start each life at normal gravity
// (respawned players pass back through the gravity triggers on the way into a game anyway).
Instance.OnPlayerReset(({ player }) => {
    const slot = player.GetPlayerController()?.GetPlayerSlot();
    if (slot !== undefined) { speedBySlot.delete(slot); gravityBySlot.delete(slot); }
    stripOnSpawn(player);
});

// ---------------------------------------------------------------- spawn strip (game_player_equip auto-equip replacement)
// CS:GO ran every game_player_equip without "Use Only" on each spawn, survivors of the last round included. In this map
// two of those strip the player ("gameequip" and an unnamed one, the last to run), so everyone spawned with nothing and
// the lobby's stripperTrigger then handed out armour. CS2 doesn't run them on spawn, so survivors kept their guns and
// everyone got the default knife + pistol. Recreate it: no default loadout, and strip every (re)spawning player.
const NO_DEFAULT_LOADOUT = ["mp_t_default_melee", "mp_ct_default_melee", "mp_t_default_secondary", "mp_ct_default_secondary",
                            "mp_t_default_primary", "mp_ct_default_primary", "mp_t_default_grenades", "mp_ct_default_grenades"];
function noDefaultLoadout() {
    for (const cvar of NO_DEFAULT_LOADOUT) Instance.ServerCommand(`${cvar} ""`);
}
/** @param {CSPlayerPawn} pawn */
function stripOnSpawn(pawn) {
    if (pawn && pawn.IsValid()) pawn.DestroyWeapons();
}

// ---------------------------------------------------------------- retargetable teleporters
/** @type {Record<string, string>} teleporter -> current destination name ("" = none yet) */
const currentDest = {};
for (const [tele, info] of Object.entries(DATA.teleporters)) {
    currentDest[tele] = info.initial;
    for (const dest of info.dests) {
        Instance.OnScriptInput(`SetDest_${tele}__${dest}`, () => { currentDest[tele] = dest; });
    }
    Instance.OnScriptInput("Teleport_" + tele, ({ activator }) => {
        if (!activator || !activator.IsValid() || !currentDest[tele]) return;
        const dest = Instance.FindEntityByName(currentDest[tele]);
        if (!dest || !dest.IsValid()) return;
        // Same as trigger_teleport: move to the destination, take its facing, stop all movement.
        const angles = dest.GetAbsAngles();
        const pawn = toPawn(activator);
        if (pawn) {
            pawn.Teleport({ position: dest.GetAbsOrigin(), angles: { pitch: 0, yaw: angles.yaw, roll: 0 }, velocity: { x: 0, y: 0, z: 0 } });
            pawn.SetEyeAngles(angles);
        } else {
            activator.Teleport({ position: dest.GetAbsOrigin(), angles, velocity: { x: 0, y: 0, z: 0 }, angularVelocity: { x: 0, y: 0, z: 0 } });
            if (activator.GetEntityName() === MUSHROOM_NAME) startMushroom(activator);
        }
    });
}
// Each round starts with the destinations the map was built with (CS:GO respawned map entities each round).
Instance.OnBeginRoundRestart(() => {
    for (const [tele, info] of Object.entries(DATA.teleporters)) currentDest[tele] = info.initial;
    speedBySlot.clear();
    gravityBySlot.clear();
    mushroom = undefined;
    dog = undefined;
    for (const team of Object.keys(blockFortBag)) blockFortBag[team] = [];
});

// ---------------------------------------------------------------- Block Fort start teleporters
// CS:GO: players drop into a black box; block_fort_teleporter_sorter_* renames one of them "TeleReady" and picks a random
// spawn, and block_fort_teleporter_* (filter TeleReady) sends them there. In CS2 the rename lands after the player is
// already inside the teleporter, which only checks on entry, so everyone stayed in the box (noclipping out and back in
// worked). Now the teleporter takes everyone who enters and hands each player their own random spawn (no repeats until
// all 16 of that team's spawns are used), which is what the sorter was building.
/** @type {Record<string, string[]>} team -> remaining destination names */
const blockFortBag = { t: [], ct: [] };
for (const team of ["t", "ct"]) {
    Instance.OnScriptInput("BlockFortTele_" + team, ({ activator }) => {
        const pawn = toPawn(activator);
        if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) return;
        if (blockFortBag[team].length === 0) {
            blockFortBag[team] = Array.from({ length: 16 }, (_, i) => `BlockFort_${team}_dest_${i + 1}`);
        }
        const bag = blockFortBag[team];
        const name = bag.splice(Math.floor(Math.random() * bag.length), 1)[0];
        const dest = Instance.FindEntityByName(name);
        if (!dest || !dest.IsValid()) return;
        const a = dest.GetAbsAngles();
        pawn.Teleport({ position: dest.GetAbsOrigin(), angles: { pitch: 0, yaw: a.yaw, roll: 0 }, velocity: { x: 0, y: 0, z: 0 } });
        pawn.SetEyeAngles(a);
        pawn.SetEntityName("TeleReady");                   // what the CS:GO sorter named them
    });
}

// ---------------------------------------------------------------- Chain Chomp chase (phys_thruster replacement)
// CS:GO: Dog_box (a 256x256x128 physbox carrying Dog_rotator + the chain chomp model + its kill trigger) was pushed by
// 16 phys_thrusters (800, ignore mass), one per 22.5-degree sector, each switched on while the chased player ("Dog_Chase")
// was in that sector's trigger; with no target, random_thruster_timer fired a random one for 1 s.
// CS2's thrusters don't move the box, and pushing its physics velocity from script loses to floor friction, so here (like
// the spawn-box mushroom) the box's physics is frozen and the script glides it with Move: it accelerates toward the
// chased player, overshoots and turns wide like the thrusters did, and slides along the arena walls.
// The chased player is still whoever the map names "Dog_Chase"; if nobody in the arena has that name (the map's
// allocator trigger only reacts to players walking into it), the script names a random player in the arena itself.
const DOG_BOX = "Dog_box";
const DOG_CHASE_SPEED = 280;                             // a little faster than a knife run (250): dodge, don't outrun
const DOG_ACCEL = 600;                                   // units/s^2 - it turns wide and overshoots, like the thrusters
const DOG_WANDER_SPEED = 220;                            // no target: lunge in a random direction now and then
const DOG_FRICTION = 300;                                // units/s^2 slow-down when it isn't being pushed
const DOG_HALF = { x: 124, y: 124, z: 60 };              // Dog_box is 256x256x128; a little smaller so it can slide past walls
const DOG_ARENA = { min: { x: -9304, y: 7483, z: -260 }, max: { x: -7256, y: 9531, z: 40 } };  // Dog_target_allocator's area
const DOG_FIRST_TARGET_DELAY = 5;                        // the map enabled its target allocator 5 s after the start
const DOG_RETARGET_DELAY = 1.5;                          // after the chased player dies
/** @type {{ ent: Entity, vx: number, vy: number, lastT: number, pickAt: number, wanderDir: number[] | undefined, wanderUntil: number, nextWander: number, target: CSPlayerPawn | undefined } | undefined} */
let dog;
/** @param {string} t */
function dlog(t) { Instance.Msg(`[mario_io] chain chomp: ${t}`); }
/** @param {{x:number,y:number,z:number}} p */
function inDogArena(p) {
    return p.x >= DOG_ARENA.min.x && p.x <= DOG_ARENA.max.x && p.y >= DOG_ARENA.min.y && p.y <= DOG_ARENA.max.y &&
           p.z >= DOG_ARENA.min.z && p.z <= DOG_ARENA.max.z;
}
Instance.OnScriptInput("DogStart", () => {
    const ent = Instance.FindEntityByName(DOG_BOX);
    if (!ent || !ent.IsValid()) { dlog("DogStart, but Dog_box was not found"); return; }
    for (let n = 1; n <= 16; n++) {
        Instance.EntFireAtName({ name: `Thruster_${n}`, input: "Kill" });
        Instance.EntFireAtName({ name: `Thruster_${n}_timed`, input: "Kill" });
    }
    Instance.EntFireAtName({ name: "random_thruster_timer", input: "Disable" });
    Instance.EntFireAtName({ name: "testtimer", input: "Kill" });
    // the start trigger's own "Dog_box EnableMotion" fires at the same moment, so freeze it again after that
    for (const delay of [0, 0.1, 0.5]) Instance.EntFireAtName({ name: DOG_BOX, input: "DisableMotion", delay });
    const now = Instance.GetGameTime();
    dog = { ent, vx: 0, vy: 0, lastT: now, pickAt: now + DOG_FIRST_TARGET_DELAY, wanderDir: undefined, wanderUntil: 0,
            nextWander: now + 2, target: undefined };
    const p = ent.GetAbsOrigin();
    dlog(`started at ${p.x.toFixed(0)} ${p.y.toFixed(0)} ${p.z.toFixed(0)}`);
    ensureThink();
});
/** @param {number} now */
function findDogTarget(now) {
    const d = /** @type {NonNullable<typeof dog>} */ (dog);
    const pos = d.ent.GetAbsOrigin();
    /** @type {CSPlayerPawn[]} */
    const inArena = [];
    let target; let best = Infinity;
    for (let slot = 0; slot < 64; slot++) {
        const pawn = Instance.GetPlayerController(slot)?.GetPlayerPawn();
        if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) continue;
        const pp = pawn.GetAbsOrigin();
        if (!inDogArena(pp)) continue;
        inArena.push(pawn);
        if (pawn.GetEntityName() !== "Dog_Chase") continue;
        const dd = Math.hypot(pp.x - pos.x, pp.y - pos.y);
        if (dd < best) { best = dd; target = pawn; }
    }
    if (!target && inArena.length > 0 && now >= d.pickAt) {
        target = inArena[Math.floor(Math.random() * inArena.length)];
        target.SetEntityName("Dog_Chase");                 // the map's Dog_rotator face-the-target trigger filters on this
    }
    if (target !== d.target) {
        if (target) dlog(`chasing ${target.GetPlayerController()?.GetPlayerName() ?? "a player"}`);
        else d.pickAt = Math.max(d.pickAt, now + DOG_RETARGET_DELAY);
        d.target = target;
    }
    return target;
}
/** @param {number} now */
function moveDog(now) {
    if (!dog) return;
    const d = dog;
    if (!d.ent.IsValid()) { dog = undefined; return; }
    const dt = Math.min(Math.max(now - d.lastT, 0), 0.1);
    d.lastT = now;
    if (dt <= 0) return;
    const pos = d.ent.GetAbsOrigin();
    const target = findDogTarget(now);
    /** @type {{x:number,y:number} | undefined} */
    let want;
    if (target) {
        const pp = target.GetAbsOrigin(), dist = Math.hypot(pp.x - pos.x, pp.y - pos.y);
        if (dist > 1) want = { x: (pp.x - pos.x) / dist * DOG_CHASE_SPEED, y: (pp.y - pos.y) / dist * DOG_CHASE_SPEED };
    } else {
        if (now >= d.nextWander) {
            const a = Math.random() * Math.PI * 2;
            d.wanderDir = [Math.cos(a), Math.sin(a)]; d.wanderUntil = now + 1; d.nextWander = now + 5 + Math.random() * 5;
        }
        if (d.wanderDir && now < d.wanderUntil) want = { x: d.wanderDir[0] * DOG_WANDER_SPEED, y: d.wanderDir[1] * DOG_WANDER_SPEED };
    }
    if (want) {                                            // accelerate toward the wanted velocity
        let ax = want.x - d.vx, ay = want.y - d.vy;
        const need = Math.hypot(ax, ay), max = DOG_ACCEL * dt;
        if (need > max) { ax *= max / need; ay *= max / need; }
        d.vx += ax; d.vy += ay;
    } else {                                               // coast to a stop
        const sp = Math.hypot(d.vx, d.vy), drop = DOG_FRICTION * dt;
        const k = sp > drop ? (sp - drop) / sp : 0;
        d.vx *= k; d.vy *= k;
    }
    if (d.vx === 0 && d.vy === 0) return;
    // move, sliding along walls: try the full step, then each axis on its own; a blocked axis loses its speed
    const mins = { x: -DOG_HALF.x, y: -DOG_HALF.y, z: -DOG_HALF.z }, maxs = DOG_HALF;
    /** @param {number} x @param {number} y */
    const free = (x, y) => {
        const tr = Instance.TraceBox({ mins, maxs, start: pos, end: { x, y, z: pos.z }, ignoreEntity: d.ent, ignorePlayers: true });
        return !tr.didHit || tr.startedInSolid;
    };
    let nx = pos.x + d.vx * dt, ny = pos.y + d.vy * dt;
    if (!free(nx, ny)) {
        if (free(nx, pos.y)) { ny = pos.y; d.vy = 0; }
        else if (free(pos.x, ny)) { nx = pos.x; d.vx = 0; }
        else { d.vx = 0; d.vy = 0; return; }
    }
    // never leave the arena, whatever the traces say
    nx = Math.min(Math.max(nx, DOG_ARENA.min.x + 128), DOG_ARENA.max.x - 128);
    ny = Math.min(Math.max(ny, DOG_ARENA.min.y + 128), DOG_ARENA.max.y - 128);
    d.ent.Move({ position: { x: nx, y: ny, z: pos.z }, angles: { pitch: 0, yaw: 0, roll: 0 }, velocity: { x: d.vx, y: d.vy, z: 0 } });
}

// ---------------------------------------------------------------- spawn-box mushroom (phys_thruster replacement)
// CS:GO: once the hidden "correct" block is hit, mushroom_tele_1 drops mushroom_physbox1 under that block, then four
// phys_thrusters (1000, ignore mass) push it forward/back/left/right, switching every 1-3 s, with a phys_keepupright.
// CS2 physics doesn't damp that the way VPhysics did, so the mushroom accelerated without limit and tumbled.
// Here the thrusters/upright constraint are removed when it pops out and the script slides it instead:
// a steady pace, upright, a random new direction every 1-3 s (or straight away if it runs into something).
const MUSHROOM_NAME = "mushroom_physbox1";
const MUSHROOM_PARTS = ["mushroom_1_forward", "mushroom_1_back", "mushroom_1_left", "mushroom_1_right", "mushroom_1_keep"];
const MUSHROOM_SPEED = 120;                             // units/s - catchable at a run (250), like the Mario power-up
const MUSHROOM_DIRS = [[1, 0], [-1, 0], [0, 1], [0, -1]];
const MUSHROOM_MODEL = "mushroom1";                      // the visible prop, parented to the physbox
const MUSHROOM_GRAB_DELAY = 3;                          // CS:GO enabled mushroom1_button 3 s after it popped out
const MUSHROOM_GRAB_RADIUS = 36;                        // player half-width 16 + mushroom half-width 10 + reach
/** @type {{ ent: Entity, dir: number, startAt: number, nextTurn: number, yaw: number, grabAt: number, lastT: number } | undefined} */
let mushroom;
let mushroomLogAt = 0;
const MUSHROOM_DEBUG = false;                            // console trace while we chase the CS2 behaviour; set false when done
/** @param {string} t */
function mlog(t) { if (MUSHROOM_DEBUG) Instance.Msg(`[mario_io] ${t}`); }
/** @param {{x:number,y:number,z:number}} v */
function vstr(v) { return `${v.x.toFixed(0)} ${v.y.toFixed(0)} ${v.z.toFixed(0)}`; }

const MUSHROOM_CLEARANCE = 40;
const MUSHROOM_HALF = 10;                               // mushroom_physbox1 is a 20-unit cube

/** @param {Entity} ent */
function startMushroom(ent) {
    for (const name of MUSHROOM_PARTS) Instance.EntFireAtName({ name, input: "Kill" });
    // It pops out right under the block the player just headbutted, i.e. inside that player. CS:GO's physics shoved it
    // out of the player; CS2's doesn't (the player gets stuck and the mushroom is hidden inside them). So pop it out on
    // the open side away from the nearest player, already heading that way.
    const pos = ent.GetAbsOrigin();
    let away = { x: 0, y: 0 }, best = Infinity;
    for (let slot = 0; slot < 64; slot++) {
        const pawn = Instance.GetPlayerController(slot)?.GetPlayerPawn();
        if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) continue;
        const pp = pawn.GetAbsOrigin(), d = Math.hypot(pos.x - pp.x, pos.y - pp.y);
        if (d < best) { best = d; away = { x: pos.x - pp.x, y: pos.y - pp.y }; }
    }
    let dir = 0, score = -Infinity;
    for (let k = 0; k < 4; k++) {
        const [dx, dy] = MUSHROOM_DIRS[k];
        const tr = Instance.TraceLine({ start: pos, end: { x: pos.x + dx * (MUSHROOM_CLEARANCE + 12), y: pos.y + dy * (MUSHROOM_CLEARANCE + 12), z: pos.z },
                                        ignoreEntity: ent, ignorePlayers: true });
        const s = (tr.didHit ? -1000 : 0) + dx * away.x + dy * away.y;
        if (s > score) { score = s; dir = k; }
    }
    if (best < MUSHROOM_CLEARANCE * 2) {
        const [dx, dy] = MUSHROOM_DIRS[dir];
        ent.Teleport({ position: { x: pos.x + dx * MUSHROOM_CLEARANCE, y: pos.y + dy * MUSHROOM_CLEARANCE, z: pos.z },
                       velocity: { x: 0, y: 0, z: 0 }, angularVelocity: { x: 0, y: 0, z: 0 } });
    }
    const now = Instance.GetGameTime();
    // CS:GO switched the forward thruster on 0.5 s after it popped out
    mushroom = { ent, dir, startAt: now + 0.5, nextTurn: now + 0.5 + 1 + Math.random() * 2, yaw: ent.GetAbsAngles().yaw,
                 grabAt: now + MUSHROOM_GRAB_DELAY, lastT: now };
    // freeze its physics (the map's own EnableMotion outputs fire around now too, so repeat once they're done)
    for (const delay of [0, 0.2, 0.5]) Instance.EntFireAtName({ name: MUSHROOM_NAME, input: "DisableMotion", delay });
    const model = Instance.FindEntityByName(MUSHROOM_MODEL);
    const f = (/** @type {{x:number,y:number,z:number}} */ v) => `${v.x.toFixed(0)} ${v.y.toFixed(0)} ${v.z.toFixed(0)}`;
    Instance.Msg(`[mario_io] mushroom out: popped at ${f(pos)}, physbox now ${f(ent.GetAbsOrigin())}` +
                 (model && model.IsValid() ? `, model at ${f(model.GetAbsOrigin())}` : ", model not found"));
    ensureThink();
}

/**
 * Grabbing it. CS:GO: touching mushroom1_button (a thin trigger under the physbox) named the player "mushroom" and
 * removed the mushroom; mushroom_grabber_tele (covers the whole lobby, filter "mushroom") then sent them to
 * winner_dest_1 and renamed them "p". In CS2 the solid physbox stops you before you can reach that thin trigger,
 * and a teleport trigger you are already standing in may not re-check you, so the script does the whole grab.
 * @param {CSPlayerPawn} pawn
 */
function grabMushroom(pawn) {
    mlog(`script grab by slot ${pawn.GetPlayerController()?.GetPlayerSlot()} at ${vstr(pawn.GetAbsOrigin())}`);
    for (const name of ["mushroom1_button", MUSHROOM_MODEL, MUSHROOM_NAME]) Instance.EntFireAtName({ name, input: "Kill" });
    Instance.EntFireAtName({ name: "mushroom_tele_1", input: "Disable" });
    mushroom = undefined;
    sendMushroomWinner(pawn);
}

/**
 * mushroom_grabber_tele: the mushroom holder goes to winner_dest_1 and is renamed "p".
 * Reached from the script's own grab check and from the map's mushroom1_button (SetName_mushroom).
 * @param {CSPlayerPawn} pawn
 */
function sendMushroomWinner(pawn) {
    const dest = Instance.FindEntityByName("winner_dest_1");
    mlog(`sending mushroom winner to ${dest && dest.IsValid() ? vstr(dest.GetAbsOrigin()) : 'winner_dest_1 (NOT FOUND)'}`);
    if (dest && dest.IsValid()) {
        const a = dest.GetAbsAngles();
        pawn.Teleport({ position: dest.GetAbsOrigin(), angles: { pitch: 0, yaw: a.yaw, roll: 0 }, velocity: { x: 0, y: 0, z: 0 } });
        pawn.SetEyeAngles(a);
    }
    pawn.SetEntityName("p");
    mushroom = undefined;
}
Instance.OnScriptInput("MushroomWinner", ({ activator }) => {
    const pawn = toPawn(activator);
    mlog(`MushroomWinner input, activator ${activator ? activator.GetClassName() : 'none'}`);
    if (pawn && pawn.IsValid() && pawn.IsAlive()) sendMushroomWinner(pawn);
});

/** @param {number} now */
function moveMushroom(now) {
    if (!mushroom) return;
    const m = mushroom;
    if (!m.ent.IsValid()) { mlog(`mushroom physbox removed (t+${(now - m.grabAt + MUSHROOM_GRAB_DELAY).toFixed(1)}s)`); mushroom = undefined; return; }
    if (now >= mushroomLogAt) {
        mushroomLogAt = now + 1;
        const model = Instance.FindEntityByName(MUSHROOM_MODEL);
        mlog(`mushroom t+${(now - m.grabAt + MUSHROOM_GRAB_DELAY).toFixed(1)}s physbox ${vstr(m.ent.GetAbsOrigin())} dir ${m.dir}` +
             (model && model.IsValid() ? ` model ${vstr(model.GetAbsOrigin())}` : ' model GONE') + (now >= m.grabAt ? ' (grabbable)' : ''));
    }
    if (now >= m.grabAt) {
        const model = Instance.FindEntityByName(MUSHROOM_MODEL);
        const at = model && model.IsValid() ? model.GetAbsOrigin() : m.ent.GetAbsOrigin();
        for (let slot = 0; slot < 64; slot++) {
            const pawn = Instance.GetPlayerController(slot)?.GetPlayerPawn();
            if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) continue;
            const pp = pawn.GetAbsOrigin();
            if (Math.hypot(pp.x - at.x, pp.y - at.y) <= MUSHROOM_GRAB_RADIUS && at.z - pp.z > -40 && at.z - pp.z < 80) {
                grabMushroom(pawn);
                return;
            }
        }
    }
    // Kinematic: physics is frozen (see startMushroom) and the box is glided with Move, which keeps the client's
    // interpolation (a Teleport every tick made the model render stale/invisible). Traces keep it on the floor and
    // turn it at walls and ledges.
    const pos = m.ent.GetAbsOrigin();
    const dt = Math.min(Math.max(now - m.lastT, 0), 0.1);
    m.lastT = now;
    const upright = { pitch: 0, yaw: m.yaw, roll: 0 };
    /** @param {number} x @param {number} y @param {number} fromZ */
    const floorAt = (x, y, fromZ) => {
        const tr = Instance.TraceLine({ start: { x, y, z: fromZ }, end: { x, y, z: fromZ - 160 }, ignoreEntity: m.ent, ignorePlayers: true });
        return tr.didHit && !tr.startedInSolid ? tr.end.z : undefined;
    };
    if (now < m.startAt) {                                 // settle onto the floor where it popped out
        const fz = floorAt(pos.x, pos.y, pos.z);
        const z = fz === undefined ? pos.z : Math.max(fz + MUSHROOM_HALF, pos.z - 400 * dt);
        m.ent.Move({ position: { x: pos.x, y: pos.y, z }, angles: upright });
        return;
    }
    const turn = () => {
        m.dir = (m.dir + 1 + Math.floor(Math.random() * 3)) % 4;   // always a different direction
        m.nextTurn = now + 1 + Math.random() * 2;
    };
    if (now >= m.nextTurn) turn();
    const [dx, dy] = MUSHROOM_DIRS[m.dir];
    const step = MUSHROOM_SPEED * dt;
    const wall = Instance.TraceLine({ start: pos, end: { x: pos.x + dx * (step + MUSHROOM_HALF + 2), y: pos.y + dy * (step + MUSHROOM_HALF + 2), z: pos.z },
                                      ignoreEntity: m.ent, ignorePlayers: true });
    if (wall.didHit) { turn(); return; }
    const nx = pos.x + dx * step, ny = pos.y + dy * step;
    const fz = floorAt(nx, ny, pos.z + 18);                // 18 = step-up height
    if (fz === undefined || fz < pos.z - MUSHROOM_HALF - 24) { turn(); return; }   // ledge: don't walk off
    m.ent.Move({ position: { x: nx, y: ny, z: fz + MUSHROOM_HALF }, angles: upright });
}

// ---------------------------------------------------------------- KOTH round end
// CS:GO used game_round_end, which ends the round for a team no matter who is alive. CS2 has no such entity,
// so: 1) kill the losing team so the winners take the round by elimination (the normal multiplayer case);
//     2) if the round still hasn't ended a moment later - nobody on the losing team, e.g. testing alone, or they are
//        all dead already - make the winners the team that wins when the round clock runs out, and run it out.
const DEFAULT_WINNER_NO_OBJECTIVE = -1;               // CS2 default for mp_default_team_winner_no_objective
let roundOver = false;
let winnerCvarChanged = false;

/** @param {number} team */
function killTeam(team) {
    for (let slot = 0; slot < 64; slot++) {
        const pawn = Instance.GetPlayerController(slot)?.GetPlayerPawn();
        if (pawn && pawn.IsValid() && pawn.IsAlive() && pawn.GetTeamNumber() === team) {
            pawn.TakeDamage({ damage: 100000, damageFlags: CSDamageFlags.FORCE_DEATH | CSDamageFlags.IGNORE_ARMOR });
        }
    }
}

/** @param {number} winner */
async function endRound(winner) {
    await Instance.Delay(0.1);                          // let mp_ignore_round_win_conditions 0 apply first
    if (roundOver) return;
    killTeam(winner === TEAM_T ? TEAM_CT : TEAM_T);
    await Instance.Delay(1.0);
    if (roundOver) return;
    Instance.ServerCommand(`mp_default_team_winner_no_objective ${winner}`);
    winnerCvarChanged = true;
    Instance.SetRoundRemainingTime(0);
}
Instance.OnScriptInput("EndRound_CTWin", () => { endRound(TEAM_CT); });
Instance.OnScriptInput("EndRound_TWin", () => { endRound(TEAM_T); });

Instance.OnRoundEnd(() => {
    roundOver = true;
    if (winnerCvarChanged) {                            // put the server back how it was for the other games
        Instance.ServerCommand(`mp_default_team_winner_no_objective ${DEFAULT_WINNER_NO_OBJECTIVE}`);
        winnerCvarChanged = false;
    }
});

// ---------------------------------------------------------------- math_counter -> logic_case
// CS:GO: math_counter OutValue / OnGetValue -> logic_case InValue, with whole-number cases ("1", "5", "20" ...).
// CS2 passes the counter's value on as a float ("5.000000"), which never equals those cases, so nothing fired
// (KOTH countdown/win, MVP, Hexagon Heat, Mario Says, wipeout, boulders). Forward the value as a whole number instead.
// The map's direct counter -> case links were removed so nothing fires twice.
/** @type {[string, string, string][]} counter, output, logic_case */
const COUNTER_TO_CASE = [
    ["koth_point_counter_t", "OutValue", "t_case_timer"],
    ["koth_point_counter_ct", "OutValue", "ct_case_timer"],
    ["mvp_counter_1", "OnGetValue", "mvp_math_case"],
    ["mvp_counter_1", "OnGetValue", "mvp_math_case2"],
    ["hexagonheat_counter", "OutValue", "hexagonheat_case"],
    ["mario_pressed_counter", "OnGetValue", "mario_pressed_case"],
    ["wipcounter", "OutValue", "wipcase"],
    ["boulder_counter_pg", "OutValue", "boulder_case_pg"],
];
/** @type {number[]} */
let counterHooks = [];
function hookCounters() {
    for (const id of counterHooks) Instance.DisconnectOutput(id);
    counterHooks = [];
    for (const [counter, output, kase] of COUNTER_TO_CASE) {
        for (const ent of Instance.FindEntitiesByName(counter)) {
            const id = Instance.ConnectOutput(ent, output, ({ value }) => {
                const n = Math.round(Number(value));
                if (Number.isFinite(n)) Instance.EntFireAtName({ name: kase, input: "InValue", value: String(n) });
            });
            if (id !== undefined) counterHooks.push(id);
        }
    }
}
Instance.OnActivate(() => {
    noDefaultLoadout();
    hookCounters();
});
Instance.OnRoundStart(() => {
    roundOver = false;
    hookCounters();                               // map entities are respawned each round, so hook the new ones
});

// ---------------------------------------------------------------- cannon boulder maker
Instance.OnScriptInput("ResetAngles_boulder_maker", () => {
    const maker = Instance.FindEntityByName("boulder_maker");
    if (maker && maker.IsValid()) maker.Teleport({ angles: { pitch: 0, yaw: 0, roll: 0 } });
});

// ---------------------------------------------------------------- weapon equips without duplicates
// CS:GO's game_player_equip never handed a player a second copy of a weapon they already owned. CS2 does, so walking in and out
// of the weapon triggers stacked guns on the floor. Equips that strip first are left on the map entity (re-touching can't stack).
/** @type {Record<string, string[]>} */
const EQUIPS = {"GunGameM249": ["weapon_knife", "weapon_m249"], "GunGameAug": ["weapon_aug", "weapon_knife"], "GunGameAWP": ["weapon_awp", "weapon_knife"], "GunGamedeagle": ["weapon_knife", "weapon_deagle"], "thwomp_knifes": ["weapon_knife"], "knife_tamp_boulder_over": ["weapon_knife"], "HG_M4_Equip": ["weapon_m4a1"], "HG_deagle_Equip": ["weapon_deagle"], "HG_ssg08_Equip": ["weapon_ssg08"], "HG_Nova_Equip": ["weapon_nova"], "GunGameSSG08": ["weapon_knife", "weapon_ssg08"], "GunGameArenaNova": ["weapon_nova", "weapon_knife"], "GunGameNegev": ["weapon_knife", "weapon_negev"], "scout_equip_sk": ["weapon_knife", "weapon_ssg08"], "awp_equip": ["weapon_awp", "weapon_knife"], "ssg08_equip": ["weapon_knife", "weapon_ssg08"], "speed_smg_p90": ["weapon_knife", "weapon_p90"], "speed_smg_mac10": ["weapon_knife", "weapon_mac10"], "speed_smg_mp7": ["weapon_knife", "weapon_mp7"], "m4a1_spawner": ["weapon_knife", "weapon_m4a1"], "ak47_spawner": ["weapon_ak47", "weapon_knife"], "deagle_spawner": ["weapon_deagle", "weapon_knife"], "negev_spawner": ["weapon_knife", "weapon_negev"], "knifegiver": ["weapon_knife"], "knifespawner": ["weapon_knife"]};
for (const [equip, weapons] of Object.entries(EQUIPS)) {
    Instance.OnScriptInput("Equip_" + equip, ({ activator }) => {
        const pawn = toPawn(activator);
        if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) return;
        for (const w of weapons) {
            if (w.startsWith("weapon_knife")) { if (pawn.FindWeaponBySlot(CSGearSlot.KNIFE)) continue; }
            else if (w.startsWith("weapon_") && pawn.FindWeapon(w)) continue;
            pawn.GiveNamedItem(w);
        }
    });
}

// ---------------------------------------------------------------- bullet bill cannons
// CS:GO spawned the bullet (a motion-disabled prop_physics with a trigger_hurt child), enabled its motion and switched on a
// trigger_push for half a second to fire it. CS2's trigger_push doesn't throw it, so it fell out of the cannon (into the water in
// the knife arena). The cannon outputs now fire BulletFire_<push trigger> instead, and the bullet is flown straight out along the
// push direction - CS:GO stored that direction relative to the trigger, so it turns with a rotating cannon - until it hits a wall.
/** @type {Record<string, { bullet: string, pushdir: number[] }>} */
const BULLETS = {"bullet_push_trigger_climb": {"bullet": "bullet_climb", "pushdir": [0.0, 90.0, 0.0]}, "bullet_push_trigger_ka5": {"bullet": "bullet_ka5", "pushdir": [0.0, 0.0, 10.0]}, "bullet_push_trigger_ka4": {"bullet": "bullet_ka4", "pushdir": [0.0, 0.0, 10.0]}, "bullet_push_trigger_ka3": {"bullet": "bullet_ka3", "pushdir": [0.0, 0.0, 10.0]}, "bullet_push_trigger_ka2": {"bullet": "bullet_ka2", "pushdir": [0.0, 0.0, 10.0]}, "bullet_push_trigger_ka1": {"bullet": "bullet_ka1", "pushdir": [0.0, 0.0, 10.0]}, "bullet_push_trigger_ka": {"bullet": "bullet_ka", "pushdir": [0.0, 0.0, 10.0]}};
const BULLET_SPEED = 1500;          // units/s
const BULLET_LIFE = 6;              // seconds, in case it never hits anything
const BULLET_ARM = 0.25;            // ignore hits this soon after firing (the cannon barrel)
const BULLET_REACH = 48;            // trace this far ahead of the bullet's centre
/** @type {{ ent: Entity, dir: { x: number, y: number, z: number }, t0: number }[]} */
let flying = [];

/** forward vector of a QAngle rotated by another QAngle (Source pitch/yaw/roll) */
function angleVec(a) {
    const p = a.pitch * Math.PI / 180, y = a.yaw * Math.PI / 180;
    return { x: Math.cos(p) * Math.cos(y), y: Math.cos(p) * Math.sin(y), z: -Math.sin(p) };
}
function rotateBy(ang, v) {
    const p = ang.pitch * Math.PI / 180, y = ang.yaw * Math.PI / 180, r = ang.roll * Math.PI / 180;
    const sp = Math.sin(p), cp = Math.cos(p), sy = Math.sin(y), cy = Math.cos(y), sr = Math.sin(r), cr = Math.cos(r);
    const M = [[cp * cy, sr * sp * cy - cr * sy, cr * sp * cy + sr * sy],
               [cp * sy, sr * sp * sy + cr * cy, cr * sp * sy - sr * cy],
               [-sp, sr * cp, cr * cp]];
    return { x: M[0][0] * v.x + M[0][1] * v.y + M[0][2] * v.z, y: M[1][0] * v.x + M[1][1] * v.y + M[1][2] * v.z, z: M[2][0] * v.x + M[2][1] * v.y + M[2][2] * v.z };
}

for (const [trig, info] of Object.entries(BULLETS)) {
    Instance.OnScriptInput("BulletFire_" + trig, () => {
        const base = angleVec({ pitch: info.pushdir[0], yaw: info.pushdir[1], roll: 0 });
        const t = Instance.FindEntityByName(trig);
        const dir = t && t.IsValid() ? rotateBy(t.GetAbsAngles(), base) : base;
        const now = Instance.GetGameTime();
        for (const ent of Instance.FindEntitiesByName(info.bullet)) {
            if (!ent.IsValid() || flying.some(f => f.ent === ent)) continue;
            flying.push({ ent, dir, t0: now });
        }
        ensureThink();
    });
}

/** @param {number} now @param {number} dt */
function moveBullets(now, dt) {
    if (flying.length === 0) return;
    flying = flying.filter(f => {
        if (!f.ent.IsValid()) return false;
        if (now - f.t0 > BULLET_LIFE) { Instance.EntFireAtTarget({ target: f.ent, input: "KillHierarchy" }); return false; }
        const pos = f.ent.GetAbsOrigin();
        const step = BULLET_SPEED * dt;
        const next = { x: pos.x + f.dir.x * step, y: pos.y + f.dir.y * step, z: pos.z + f.dir.z * step };
        if (now - f.t0 > BULLET_ARM) {
            const tr = Instance.TraceLine({ start: pos, end: { x: next.x + f.dir.x * BULLET_REACH, y: next.y + f.dir.y * BULLET_REACH, z: next.z + f.dir.z * BULLET_REACH },
                                            ignoreEntity: f.ent, ignorePlayers: true });
            if (tr.didHit && !tr.startedInSolid) { Instance.EntFireAtTarget({ target: f.ent, input: "KillHierarchy" }); return false; }
        }
        f.ent.Teleport({ position: next, velocity: { x: 0, y: 0, z: 0 } });
        return true;
    });
}
