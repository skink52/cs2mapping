import { Instance } from "cs_script/point_script";

// ba_jail_keimusho: climb game balls (func_physbox ball1-7, spawned by climbtemp1-7 and rolled down the climb).
// In CS:GO players pushed them by walking into them; CS2 players don't move physics props, so this script does it:
// a player touching a ball (sphere RADIUS, player hull 32x72) while moving into it gives the ball their speed along
// the contact direction (x PUSH_GAIN, at least PUSH_MIN), keeping the ball's own vertical speed.

const NAME_RE = /^ball[1-7](?:&|$)/;
const RADIUS = 32;
const PLAYER_R = 16, PLAYER_H = 72;
const PUSH_GAIN = 1.15, PUSH_MIN = 60, MIN_INTO = 10;
const SCAN_EVERY = 0.5, IDLE_THINK = 0.5;

/** @type {any[]} */
let balls = [];
let nextScan = 0;

function scan(now) {
    nextScan = now + SCAN_EVERY;
    balls = Instance.FindEntitiesByClass("func_physbox").filter((e) => e.IsValid() && NAME_RE.test(e.GetEntityName() || ""));
}

Instance.SetThink(() => {
    const now = Instance.GetGameTime();
    if (now >= nextScan) scan(now);
    if (balls.length === 0) { Instance.SetNextThink(now + IDLE_THINK); return; }
    const pawns = [];
    for (const c of Instance.GetAllPlayerControllers()) {
        const p = c.GetPlayerPawn();
        if (p && p.IsValid() && p.IsAlive()) pawns.push(p);
    }
    for (const b of balls) {
        if (!b.IsValid()) continue;
        const bo = b.GetAbsOrigin();
        for (const p of pawns) {
            const o = p.GetAbsOrigin();
            if (bo.z < o.z - RADIUS || bo.z > o.z + PLAYER_H + RADIUS) continue;
            const dx = bo.x - o.x, dy = bo.y - o.y, d = Math.hypot(dx, dy);
            if (d > RADIUS + PLAYER_R + 2 || d < 0.01) continue;
            const nx = dx / d, ny = dy / d;
            const v = p.GetAbsVelocity();
            const into = v.x * nx + v.y * ny;
            if (into < MIN_INTO) continue;
            const bv = b.GetAbsVelocity();
            const along = bv.x * nx + bv.y * ny;
            const want = Math.max(PUSH_MIN, into * PUSH_GAIN);
            if (along >= want) continue;
            Instance.EntFireAtTarget({ target: b, input: "Wake" });
            b.Teleport({ velocity: { x: bv.x + nx * (want - along), y: bv.y + ny * (want - along), z: bv.z } });
        }
    }
    Instance.SetNextThink(now);
});

Instance.OnActivate(() => { nextScan = 0; Instance.SetNextThink(Instance.GetGameTime()); });
Instance.OnRoundStart(() => { balls = []; nextScan = 0; Instance.SetNextThink(Instance.GetGameTime()); });
