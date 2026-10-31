import { Instance } from "cs_script/point_script";

// ba_jail_keimusho: copy of ba_jail_seaside pushscale.js. Replaces "sm_cvar phys_pushscale 25" on rockbuttonon:
// while on, knifing or shooting a falling rock (rock6-9) pushes it. rockbuttonon -> push_on, rockbuttonoff -> push_off.

const NAME_RE = /^rock[6-9](?:&|$)/;   // ba_jail_keimusho rock dodgeball: rock6-9 (template-spawned)
const GUN_RANGE = 8192;
const KNIFE_RANGE = 65;
const GUN_PUSH = 1500;
const KNIFE_PUSH = 2000;
const LIFT = 200;
const DEBUG = false;

let enabled = false;

function forward(a) {
    const p = (a.pitch / 180) * Math.PI, y = (a.yaw / 180) * Math.PI, c = Math.cos(p);
    return { x: c * Math.cos(y), y: c * Math.sin(y), z: -Math.sin(p) };
}

function tryPush(pawn, range, strength) {
    if (!enabled || !pawn || !pawn.IsValid() || !pawn.IsAlive()) return;
    const eye = pawn.GetEyePosition();
    const d = forward(pawn.GetEyeAngles());
    const tr = Instance.TraceLine({
        start: eye,
        end: { x: eye.x + d.x * range, y: eye.y + d.y * range, z: eye.z + d.z * range },
        ignorePlayers: true,
    });
    const ent = tr.didHit ? tr.hitEntity : undefined;
    if (DEBUG) Instance.Msg(`[push] hit ${ent ? ent.GetEntityName() + " (" + ent.GetClassName() + ")" : "nothing"}`);
    if (!ent || !ent.IsValid() || !NAME_RE.test(ent.GetEntityName() || "")) return;

    Instance.EntFireAtTarget({ target: ent, input: "EnableMotion" });
    Instance.EntFireAtTarget({ target: ent, input: "Wake" });
    const v = ent.GetAbsVelocity();
    ent.Teleport({
        velocity: {
            x: v.x + d.x * strength,
            y: v.y + d.y * strength,
            z: v.z + d.z * strength + LIFT,
        },
    });
}

Instance.OnKnifeAttack((e) => tryPush(e.weapon.GetOwner(), KNIFE_RANGE, KNIFE_PUSH));
if (Instance.OnGunFire) Instance.OnGunFire((e) => tryPush(e.weapon.GetOwner(), GUN_RANGE, GUN_PUSH));

function setEnabled(on) {
    enabled = on;
    if (DEBUG) Instance.Msg(`[push] ${on ? "on" : "off"}`);
}

Instance.OnScriptInput("push_on", () => setEnabled(true));
Instance.OnScriptInput("push_off", () => setEnabled(false));
Instance.OnScriptInput("push_toggle", () => setEnabled(!enabled));