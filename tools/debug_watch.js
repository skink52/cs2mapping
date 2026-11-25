// debug_watch.js: console tools for checking a ported map in game. It does nothing until one of its commands is used.
//
// From Ninja-Chris's cs2-slop-porting scripts/debug_watch.js (2026-11-24, MIT, Ninja-Chris and skink52); calls moved to the current
// API (Entities.*, Console.*) by tools/jsapi.py. SETUP: stage D pass `debugwatch` copies it to <addon>/scripts/debug_watch.js and adds a
// point_script named debug_watch; delete that entity before publishing. Simulated only (api.py --strict, tscheck), not run in CS2 by us.
//
// Console (sv_cheats 1). <name> is an entity name; a name with * in it is passed to CS2's own name search as it is; a plain name
// that finds nothing is also tried as <name>* and *<name>*. class:<class> (e.g. class:prop_ragdoll) means every entity of that class,
// for unnamed ones.
//   dw_find <name>                  every entity by that name: class, place, angles, parent
//   dw_class <class> [near <name>] [radius]   every entity of that class (CS2 class name), or only those within radius (512) of <name>
//   dw_watch <name> [ticks]         a line every [ticks] ticks (default 8) per entity: place, angles, speed, velocity, parent; and a
//                                   JUMP line the tick its speed changes by more than 300 u/s or it moves more than 64 units
//                                   (an object shot off, teleported, or pushed out of a wall). Watches several names at once.
//   dw_watch off                    stops every watch
//   dw_rel <name> <reference>       where <name> is in <reference>'s own frame: forward / left / up and the angle difference
//                                   (reference = what it should line up with, e.g. a cannon's trigger)
//   dw_io <name> [output ...]       a line each time one of these outputs fires on an entity of that name, with the activator.
//                                   Default: the usual outputs of the entity's class (logic_relay OnTrigger, logic_timer OnTimer, ...)
//   dw_io off                       disconnects them all

import { Instance, Entities, Console } from "cs_script/point_script";
// CS2 now refuses a second SetThink ("Callback \"Think\" already registered"): the think is set once (a script reload re-runs
// this file, so it is set again then)
let thinkSetTo = null;
function setThinkOnce(fn) {
    if (thinkSetTo === fn) return;
    try {
        Instance.SetThink(fn);
    } catch (e) {
        if (!String(e).includes("already registered")) throw e;
    }
    thinkSetTo = fn;
}


const say = (s) => Console.Log(`[debug_watch] ${s}`);
const f0 = (v) => `${v.x.toFixed(0)} ${v.y.toFixed(0)} ${v.z.toFixed(0)}`;
const f1 = (v) => `${v.x.toFixed(1)} ${v.y.toFixed(1)} ${v.z.toFixed(1)}`;
const fa = (a) => `${a.pitch.toFixed(1)} ${a.yaw.toFixed(1)} ${a.roll.toFixed(1)}`;
const len = (v) => Math.hypot(v.x, v.y, v.z);
const time = () => Instance.GetGameTime().toFixed(2);

function find(name) {
    if (!name) return [];
    if (name.startsWith("class:")) {             // unnamed entities: every entity of that class (e.g. class:prop_ragdoll)
        try {
            return (Entities.FindByClass(name.slice(6)) || []).filter((e) => e && e.IsValid());
        } catch (e) {
            return [];
        }
    }
    const get = (n) => {
        try {
            return (Entities.FindByName(n) || []).filter((e) => e && e.IsValid());
        } catch (e) {
            return [];
        }
    };
    let r = get(name);
    if (!r.length && !name.includes("*")) r = get(`${name}*`);
    if (!r.length && !name.includes("*")) r = get(`*${name}*`);
    return r;
}
function label(e) {
    return `${e.GetClassName()} ${e.GetEntityName() || "(unnamed)"}`;
}
function parentOf(e) {
    const p = e.GetParent();
    return p && p.IsValid() ? ` parent ${label(p)}` : "";
}
function describe(e) {
    const v = e.GetAbsVelocity();
    return `${label(e)} at ${f1(e.GetAbsOrigin())} angles ${fa(e.GetAbsAngles())} speed ${len(v).toFixed(0)} (${f0(v)})${parentOf(e)}`;
}

// ---- angles to axes (Source: forward x, left y, up z)
function axes(a) {
    const r = Math.PI / 180;
    const sp = Math.sin(a.pitch * r), cp = Math.cos(a.pitch * r), sy = Math.sin(a.yaw * r), cy = Math.cos(a.yaw * r);
    const sr = Math.sin(a.roll * r), cr = Math.cos(a.roll * r);
    const fwd = { x: cp * cy, y: cp * sy, z: -sp };
    const left = { x: sr * sp * cy - cr * sy, y: sr * sp * sy + cr * cy, z: sr * cp }; // Source's -right
    const up = { x: cr * sp * cy + sr * sy, y: cr * sp * sy - sr * cy, z: cr * cp };
    return { fwd, left, up };
}
const dot = (a, b) => a.x * b.x + a.y * b.y + a.z * b.z;
const angDiff = (a, b) => ((((a - b) % 360) + 540) % 360) - 180;

// ---- watch
const watches = new Map(); // name -> { every, last: Map<entity, {o, v}> }
let tick = 0, thinking = false;
function think() {
    Instance.SetNextThink(Instance.GetGameTime());
    if (!watches.size) {
        thinking = false;
        return;
    }
    tick++;
    for (const [name, W] of watches) {
        const ents = find(name);
        for (const e of ents) {
            const o = e.GetAbsOrigin(), v = e.GetAbsVelocity();
            const p = W.last.get(e);
            if (p) {
                const dv = len({ x: v.x - p.v.x, y: v.y - p.v.y, z: v.z - p.v.z });
                const dO = len({ x: o.x - p.o.x, y: o.y - p.o.y, z: o.z - p.o.z });
                if (dv > 300 || dO > 64) {
                    say(`t=${time()} JUMP ${label(e)}: speed ${len(p.v).toFixed(0)} -> ${len(v).toFixed(0)}, moved ${dO.toFixed(0)} ` +
                        `(${f0(p.o)} -> ${f0(o)}), velocity ${f0(p.v)} -> ${f0(v)}`);
                }
            } else {
                say(`t=${time()} new ${describe(e)}`);
            }
            W.last.set(e, { o, v });
            if (tick % W.every === 0) say(`t=${time()} ${describe(e)}`);
        }
        for (const e of [...W.last.keys()]) {
            if (!e.IsValid()) {
                W.last.delete(e);
                say(`t=${time()} ${name}: one is gone (killed / removed)`);
            }
        }
    }
}
function startThink() {
    if (thinking) return;
    thinking = true;
    setThinkOnce(think);
    Instance.SetNextThink(Instance.GetGameTime());
}

// ---- outputs: by class (CS2 prints an error for each output an entity doesn't have)
const USER = ["OnUser1", "OnUser2", "OnUser3", "OnUser4"];
const CASES = [];
for (let i = 1; i <= 16; i++) CASES.push(`OnCase${String(i).padStart(2, "0")}`);
function outputsFor(cls) {
    cls = (cls || "").toLowerCase();
    if (cls.startsWith("trigger_")) return ["OnTrigger", "OnStartTouch", "OnEndTouch", ...USER];
    if (cls === "logic_relay") return ["OnTrigger", "OnSpawn", ...USER];
    if (cls === "logic_timer") return ["OnTimer", "OnTimerHigh", "OnTimerLow", ...USER];
    if (cls === "logic_case") return [...CASES, "OnDefault", ...USER];
    if (cls === "math_counter") return ["OutValue", "OnHitMin", "OnHitMax", ...USER];
    if (cls === "env_entity_maker") return ["OnEntitySpawned", "OnEntityFailedSpawn", ...USER];
    if (cls === "point_template") return ["OnEntitySpawned", ...USER];
    if (cls === "logic_auto") return ["OnMapSpawn", ...USER];
    if (cls.includes("button")) return ["OnPressed", "OnDamaged", "OnIn", "OnOut", ...USER];
    if (cls.startsWith("prop_") || cls.startsWith("func_physbox") || cls.startsWith("func_breakable")) return ["OnBreak", "OnPlayerUse", "OnDamaged", ...USER];
    return USER;
}
let ioConns = [];

const words = (a) => String(a === undefined ? "" : a).trim().split(/\s+/).filter(Boolean);

Console.RegisterCheatCommand("dw_find", (a) => {
    const [name] = words(a);
    const ents = find(name);
    if (!ents.length) return say(`dw_find ${name || "<name>"}: nothing by that name`);
    for (const e of ents) say(describe(e));
});
Console.RegisterCheatCommand("dw_class", (a) => {
    const w = words(a).filter((x) => x.toLowerCase() !== "near");
    const [cls, ref, rad] = w;
    if (!cls) return say("dw_class <classname> [near <name>] [radius, default 512]");
    let ents = [];
    try {
        ents = (Entities.FindByClass(cls) || []).filter((e) => e && e.IsValid());
    } catch (e) {
        ents = [];
    }
    let centre;
    if (ref) {
        const r = find(ref);
        if (!r.length) return say(`dw_class: nothing named ${ref}`);
        centre = r[0].GetAbsOrigin();
        const R = Number(rad) || 512;
        ents = ents.filter((e) => {
            const o = e.GetAbsOrigin();
            return Math.hypot(o.x - centre.x, o.y - centre.y, o.z - centre.z) <= R;
        });
    }
    if (!ents.length) return say(`dw_class ${cls}: none${ref ? " near " + ref : ""}`);
    for (const e of ents.slice(0, 40)) say(describe(e));
    if (ents.length > 40) say(`... ${ents.length - 40} more`);
});
Console.RegisterCheatCommand("dw_watch", (a) => {
    const [name, n] = words(a);
    if (!name) return say("dw_watch <name> [ticks] | dw_watch off");
    if (name === "off") {
        watches.clear();
        return say("every watch stopped");
    }
    const every = Math.max(1, Math.floor(Number(n) || 8));
    watches.set(name, { every, last: new Map() });
    say(`watching ${name} (${find(name).length} now), a line every ${every} tick(s), JUMP lines at once`);
    startThink();
});
Console.RegisterCheatCommand("dw_rel", (a) => {
    const [name, ref] = words(a);
    if (!name || !ref) return say("dw_rel <name> <reference>");
    const A = find(name), B = find(ref);
    if (!A.length || !B.length) return say(`dw_rel: ${A.length ? "" : "no " + name + " "}${B.length ? "" : "no " + ref}`);
    for (const b of B) {
        const bo = b.GetAbsOrigin(), ba = b.GetAbsAngles(), ax = axes(ba);
        for (const e of A) {
            const o = e.GetAbsOrigin(), d = { x: o.x - bo.x, y: o.y - bo.y, z: o.z - bo.z }, ea = e.GetAbsAngles();
            say(`${label(e)} from ${label(b)}: forward ${dot(d, ax.fwd).toFixed(1)} left ${dot(d, ax.left).toFixed(1)} up ${dot(d, ax.up).toFixed(1)}` +
                ` (world ${f1(o)} vs ${f1(bo)}; reference angles ${fa(ba)}), angles differ ${angDiff(ea.pitch, ba.pitch).toFixed(1)} ` +
                `${angDiff(ea.yaw, ba.yaw).toFixed(1)} ${angDiff(ea.roll, ba.roll).toFixed(1)}`);
        }
    }
});
Console.RegisterCheatCommand("dw_io", (a) => {
    const w = words(a);
    if (!w.length) return say("dw_io <name> [output ...] | dw_io off");
    if (w[0] === "off") {
        for (const id of ioConns) Entities.DisconnectOutput(id);
        say(`${ioConns.length} output hook(s) removed`);
        ioConns = [];
        return;
    }
    const ents = find(w[0]);
    if (!ents.length) return say(`dw_io: nothing named ${w[0]}`);
    let n = 0;
    for (const e of ents) {
        const nm = label(e);
        for (const out of w.length > 1 ? w.slice(1) : outputsFor(e.GetClassName())) {
            let id;
            try {
                id = Entities.ConnectOutput({ target: e, output: out, callback: ({ activator, value }) => {
                    const act = activator && activator.IsValid() ? label(activator) : "none";
                    say(`t=${time()} ${nm} ${out}${value !== undefined ? " (" + value + ")" : ""}, activator ${act}`);
                } });
            } catch (ex) {
                id = undefined;
            }
            if (id !== undefined) {
                ioConns.push(id);
                n++;
            }
        }
    }
    say(`${n} output hook(s) on ${ents.length} entit(ies) named ${w[0]}`);
});

Instance.OnActivate(() => say("ready (dw_find, dw_class, dw_watch, dw_rel, dw_io)"));
// a round restart makes new entities: watches find them again by name; output hooks were on the old ones
Instance.OnRoundStart(() => {
    for (const W of watches.values()) W.last.clear();
    if (watches.size) {
        thinking = false;
        startThink();
    }
    if (ioConns.length) say("round restarted: run dw_io again (the hooks were on the old entities)");
    ioConns = [];
});
