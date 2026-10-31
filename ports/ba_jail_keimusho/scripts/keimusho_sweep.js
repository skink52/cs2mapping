import { Instance } from "cs_script/point_script";

// ba_jail_keimusho: CS2 doesn't re-check players already inside a trigger when it gets Enabled (CS:GO did), so the death
// roulette, fire game, parkour, spleef end teleport etc. missed everyone already standing in them. Each Enable on these
// triggers also fires sweepscript -> Sweep_<name> 0.1 s later, and each Disable fires Unsweep_<name>.
// trigger_teleport: everyone inside is sent to the destination once. trigger_hurt: everyone inside at the sweep takes the
// trigger's damage (per second, in 0.5 s steps) until they leave the box (the engine then handles them on re-entry) or
// the trigger is disabled.

/** @type {Record<string, { cls: string, boxes: number[][][], damage?: number, type?: number, dest?: number[], yaw?: number, team?: number, negated?: boolean }>} */
const TRIGGERS = {"losertelle": {"cls": "trigger_teleport", "boxes": [[[-3311.0, -5879.0, -411.21484375], [-3199.0, -5860.0, -20.0]]], "dest": [-2924.9599609375, -6329.8701171875, -235.0], "yaw": 91.99999237060547}, "parkourtpd": {"cls": "trigger_teleport", "boxes": [[[-1323.0, -1453.0, 420.0], [-860.0, 172.0, 715.0]], [[-1628.0, -1141.0, 703.0], [-388.0, 452.0, 1076.0]]], "dest": [-1058.0, 135.0, 475.0], "yaw": 270.0}, "parkourthurt": {"cls": "trigger_hurt", "boxes": [[[-1628.0, -1453.0, 420.0], [-388.0, 452.0, 1076.0]]], "damage": 20.0, "type": 0}, "skippinghurt": {"cls": "trigger_hurt", "boxes": [[[-1782.0, 1068.0, 516.0], [-1764.0, 1300.0, 525.0]]], "damage": 50.0, "type": 256}, "firehurt13": {"cls": "trigger_hurt", "boxes": [[[-1972.0, 2772.0, 24.0], [-1405.0, 3108.0, 239.0]]], "damage": 4.0, "type": 8}, "firehurt12": {"cls": "trigger_hurt", "boxes": [[[-1972.0, 2772.0, 24.0], [-1405.0, 3107.0, 239.0]]], "damage": 4.0, "type": 8}, "firehurt14": {"cls": "trigger_hurt", "boxes": [[[-1972.0, 2772.0, 24.0], [-1405.0, 3109.0, 239.0]]], "damage": 4.0, "type": 8}, "firehurt15": {"cls": "trigger_hurt", "boxes": [[[-1972.0, 2772.0, 24.0], [-1405.0, 3110.0, 239.0]]], "damage": 4.0, "type": 8}, "firehurt16": {"cls": "trigger_hurt", "boxes": [[[-1972.0, 2772.0, 24.0], [-1405.0, 3111.0, 239.0]]], "damage": 4.0, "type": 8}, "firehurt17": {"cls": "trigger_hurt", "boxes": [[[-1972.0, 2773.0, 24.0], [-1405.0, 3112.0, 239.0]]], "damage": 4.0, "type": 8}, "firehurt18": {"cls": "trigger_hurt", "boxes": [[[-1972.0, 2774.0, 24.0], [-1405.0, 3113.0, 239.0]]], "damage": 4.0, "type": 8}, "firehurt19": {"cls": "trigger_hurt", "boxes": [[[-1972.0, 2775.0, 24.0], [-1405.0, 3114.0, 239.0]]], "damage": 4.0, "type": 8}, "firehurt20": {"cls": "trigger_hurt", "boxes": [[[-1972.0, 2776.0, 24.0], [-1405.0, 3115.0, 239.0]]], "damage": 4.0, "type": 8}, "firehurt11": {"cls": "trigger_hurt", "boxes": [[[-1972.0, 2772.0, 24.0], [-1405.0, 3106.0, 239.0]]], "damage": 4.0, "type": 8}, "spleeftptrigger": {"cls": "trigger_teleport", "boxes": [[[-4292.0, -3415.0, -505.0], [-3450.0, -2339.0, -2.0]]], "dest": [-3589.0, -3418.0, -89.0], "yaw": 74.99999237060547}, "firehurt3": {"cls": "trigger_hurt", "boxes": [[[-1348.0, 2772.0, 24.0], [-781.0, 3111.0, 239.0]]], "damage": 4.0, "type": 8}, "firehurt2": {"cls": "trigger_hurt", "boxes": [[[-1348.0, 2772.0, 24.0], [-781.0, 3112.0, 239.0]]], "damage": 4.0, "type": 8}, "firehurt4": {"cls": "trigger_hurt", "boxes": [[[-1348.0, 2772.0, 24.0], [-781.0, 3112.0, 239.0]]], "damage": 4.0, "type": 8}, "firehurt5": {"cls": "trigger_hurt", "boxes": [[[-1348.0, 2772.0, 24.0], [-781.0, 3106.0, 239.0]]], "damage": 4.0, "type": 8}, "firehurt6": {"cls": "trigger_hurt", "boxes": [[[-1348.0, 2772.0, 24.0], [-781.0, 3107.0, 239.0]]], "damage": 4.0, "type": 8}, "firehurt7": {"cls": "trigger_hurt", "boxes": [[[-1348.0, 2772.0, 24.0], [-781.0, 3105.0, 239.0]]], "damage": 4.0, "type": 8}, "firehurt8": {"cls": "trigger_hurt", "boxes": [[[-1348.0, 2772.0, 24.0], [-781.0, 3104.0, 239.0]]], "damage": 4.0, "type": 8}, "firehurt9": {"cls": "trigger_hurt", "boxes": [[[-1348.0, 2772.0, 24.0], [-781.0, 3103.0, 239.0]]], "damage": 4.0, "type": 8}, "firehurt10": {"cls": "trigger_hurt", "boxes": [[[-1348.0, 2772.0, 24.0], [-781.0, 3102.0, 239.0]]], "damage": 4.0, "type": 8}, "firehurt1": {"cls": "trigger_hurt", "boxes": [[[-1348.0, 2772.0, 24.0], [-781.0, 3113.0, 239.0]]], "damage": 4.0, "type": 8}, "roulettehurt3": {"cls": "trigger_hurt", "boxes": [[[-1960.0, 1165.0, 30.75], [-1796.0, 1314.0, 212.0]]], "damage": 60.0, "type": 0}, "roulettehurt2": {"cls": "trigger_hurt", "boxes": [[[-1960.0, 1000.0, 30.75], [-1796.0, 1149.0, 212.0]]], "damage": 60.0, "type": 0}, "roulettehurt1": {"cls": "trigger_hurt", "boxes": [[[-1960.0, 835.0, 30.75], [-1796.0, 984.0, 212.0]]], "damage": 60.0, "type": 0}, "roulettehurt4": {"cls": "trigger_hurt", "boxes": [[[-1960.0, 1330.0, 30.75], [-1796.0, 1479.0, 212.0]]], "damage": 60.0, "type": 0}, "bumpminebrush": {"cls": "trigger_hurt", "boxes": [[[-2493.0, -4542.0, -116.0], [-1547.0, -3959.0, -114.0]]], "damage": 10000.0, "type": 0}};
const PLAYER_R = 16, PLAYER_H = 72, STEP = 0.5;

/** @type {Map<string, Set<number>>} active hurt -> player slots still to hurt */
const active = new Map();
let thinking = false, nextHurt = 0;

function inside(t, o) {
    return t.boxes.some(([lo, hi]) => o.x + PLAYER_R >= lo[0] && o.x - PLAYER_R <= hi[0] && o.y + PLAYER_R >= lo[1] && o.y - PLAYER_R <= hi[1]
        && o.z + PLAYER_H >= lo[2] && o.z <= hi[2]);
}
function passes(t, pawn) {
    if (t.team === undefined || !t.team) return true;
    const team = pawn.GetTeamNumber();
    return t.negated ? team !== t.team : team === t.team;
}
function playersIn(t) {
    const out = [];
    for (const c of Instance.GetAllPlayerControllers()) {
        const p = c.GetPlayerPawn();
        if (p && p.IsValid() && p.IsAlive() && passes(t, p) && inside(t, p.GetAbsOrigin())) out.push(p);
    }
    return out;
}

for (const [name, t] of Object.entries(TRIGGERS)) {
    Instance.OnScriptInput("Sweep_" + name, () => {
        const ps = playersIn(t);
        if (t.cls === "trigger_teleport") {
            for (const p of ps) p.Teleport({ position: { x: t.dest[0], y: t.dest[1], z: t.dest[2] }, angles: { pitch: 0, yaw: t.yaw ?? 0, roll: 0 }, velocity: { x: 0, y: 0, z: 0 } });
            return;
        }
        active.set(name, new Set(ps.map((p) => p.GetPlayerController().GetPlayerSlot())));
        if (!thinking) { thinking = true; nextHurt = Instance.GetGameTime(); Instance.SetNextThink(nextHurt); }
    });
    Instance.OnScriptInput("Unsweep_" + name, () => { active.delete(name); });
}

Instance.SetThink(() => {
    const now = Instance.GetGameTime();
    if (now >= nextHurt) {
        nextHurt = now + STEP;
        for (const [name, slots] of active) {
            const t = TRIGGERS[name];
            for (const slot of [...slots]) {
                const p = Instance.GetPlayerController(slot)?.GetPlayerPawn();
                if (!p || !p.IsValid() || !p.IsAlive() || !inside(t, p.GetAbsOrigin())) { slots.delete(slot); continue; }
                p.TakeDamage({ damage: (t.damage ?? 10) * STEP, damageTypes: t.type ?? 0 });
            }
        }
    }
    if (active.size > 0) Instance.SetNextThink(now + 0.05); else thinking = false;
});

Instance.OnRoundStart(() => { active.clear(); });
