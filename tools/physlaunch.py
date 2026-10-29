"""Stage C step `launch` / stage D pass `physlaunch`: CS:GO physics launchers (cannons) -> script launch.

CS:GO pattern (mg_pirates' cannons): a relay ForceSpawns a point_template holding a physics object (func_physbox / prop_physics),
a trigger_teleport (physics only) moves it to an info_teleport_destination at the muzzle, and the relay Enables a physics-only
trigger_push there for a moment (Disable a fraction of a second later). CS2's trigger_push doesn't throw physics objects (and stage C's
`push` step used to turn these into player pushes), so nothing left the barrel.

Found by the relay: an entity that sends ForceSpawn to a point_template with physics entities and Enable + Disable (within 1 s) to a
trigger_push, or to a trigger_multiple that the `push` step already made from one. The Enable becomes `RunScriptInput Launch_<pusher>`
0.05 s later (after the spawn), the Disable is dropped, and the pusher loses its PushIn/PushOut outputs. The script picks the newest
copy of the template's physics object near the cannon (still, within 400 u), puts it at the muzzle (the teleport destination
parented to the same thing as the pusher, if there is one) and gives it the push direction x LAUNCH_SPEED. The direction is from the
pusher's parent to that destination, or the pusher's pushdir turned by its current angles.
Physics-only trigger_push that don't fit the pattern are left as they are and listed in TO CHECK.
"""
import json, re, math
import dmx
import vmapedit as V

HEAD_LINE = '//   Launch_<pusher>               replaces physics-only trigger_push launchers (cannons): the spawned ball is fired from script'
PHYS_CLASSES = ('func_physbox', 'func_physbox_multiplayer', 'prop_physics', 'prop_physics_multiplayer', 'prop_physics_override')
MAX_SPEED = 2000          # CS:GO VPhysics capped object speed at 2000 u/s; the cannons' 35000 push reached the cap


def _del_conns(m, e, keep):
    arr = dmx.geta(m.E[e], b'connectionsData')
    if arr: arr[2] = [c for c in arr[2] if keep(m.conn_tuple(m.E[c]))]


def run(m, c):
    ents = m.entities()
    by_name = {}
    for e in ents: by_name.setdefault(m.name(e).lower(), []).append(e)
    pushers = {}
    for e in ents:
        if m.cls(e) == 'trigger_push':
            f = int(float(m.P(e, 'spawnflags', '0') or 0))
            if f & 8 and not f & 1: pushers[m.name(e).lower()] = e
        elif m.cls(e) == 'trigger_multiple' and any(t[2] == 'RunScriptInput' and t[3].startswith('PushIn_') for t in map(m.conn_tuple, m.conns(e))):
            pushers[m.name(e).lower()] = e
    data, done = {}, set()
    for r in ents:
        ts = [m.conn_tuple(cn) for cn in m.conns(r)]
        tmpls = [t[1] for t in ts if t[2].lower() == 'forcespawn' and any(m.cls(x) == 'point_template' for x in by_name.get(t[1].lower(), []))]
        if not tmpls: continue
        balls = []
        for tn in tmpls:
            for tp in by_name[tn.lower()]:
                for k in range(1, 17):
                    v = m.P(tp, 'Template%02d' % k, '')
                    if v and any(m.cls(x) in PHYS_CLASSES for x in by_name.get(v.lower(), [])): balls.append(v)
        if not balls: continue
        for t in ts:
            if t[2].lower() != 'enable' or t[1].lower() not in pushers: continue
            if not any(u[1].lower() == t[1].lower() and u[2].lower() == 'disable' and 0 <= u[4] - t[4] <= 1.0 for u in ts): continue
            p = pushers[t[1].lower()]; pn = m.name(p)
            parent = (m.P(p, 'parentname', '') or '').lower()
            dest = next((m.name(x) for x in ents if m.cls(x) == 'info_teleport_destination' and parent and (m.P(x, 'parentname', '') or '').lower() == parent), '')
            if m.cls(p) == 'trigger_push':
                pd = [float(x) for x in (m.P(p, 'pushdir', '0 0 0') or '0 0 0').split()[:3]]
                speed = float(m.P(p, 'speed', '0') or 0)
            else:   # already converted by the push step: direction / speed are in the io script's PUSH table, use the parent direction
                pd, speed = [0.0, 0.0, 0.0], MAX_SPEED
            loc = V.angle_fwd(pd)
            data[pn] = {'balls': sorted(set(balls)), 'dest': dest, 'pivot': m.P(p, 'parentname', '') or '', 'speed': min(speed, MAX_SPEED) or MAX_SPEED,
                        'dir': [round(x, 4) + 0.0 for x in loc]}
            _del_conns(m, r, lambda u, pn=pn: not (u[1].lower() == pn.lower() and u[2].lower() in ('enable', 'disable')))
            m.add_conn(r, t[0], c.script, 'RunScriptInput', 'Launch_' + pn, t[4] + 0.05, t[5])
            done.add(pn.lower())
    for pn in done:
        p = pushers[pn]
        _del_conns(m, p, lambda u: not (u[2] == 'RunScriptInput' and (u[3].startswith('PushIn_') or u[3].startswith('PushOut_'))))
        if m.cls(p) == 'trigger_push':
            m.setp(p, 'classname', 'trigger_multiple'); m.setp(p, 'spawnflags', '0'); m.setp(p, 'StartDisabled', '1')
            for k in ('pushdir', 'speed', 'alternateticksfix', 'triggeronstarttouch', 'FallingSpeedThreshold'): m.delp(p, k)
    left = [m.name(p) or '(unnamed)' for k, p in pushers.items() if k not in done and m.cls(p) == 'trigger_push']
    if left: c.todo.append('physics-only trigger_push not converted (CS2 pushes don\'t throw physics objects): %s' % ', '.join(sorted(left)))
    if data:
        c.log.append('%d physics launchers (cannons): trigger_push Enable/Disable -> script Launch_<pusher> (ball put at the muzzle, %g u/s along the barrel): %s'
                     % (len(data), MAX_SPEED, ', '.join(sorted(data))))
    c.launch = data
    return data


JS = r'''// ---------------------------------------------------------------- physics launchers (CS:GO cannons: physics-only trigger_push)
// Launch_<pusher>: the relay just ForceSpawned the ball. Take the newest still copy near the cannon, put it at the muzzle and fire it
// along the barrel (pivot -> muzzle destination), or along the pusher's pushdir turned by its angles when there's no destination.
/** @type {Record<string, { balls: string[], dest: string, pivot: string, speed: number, dir: number[] }>} */
const LAUNCH = __LAUNCH__;
/** @param {{ pitch: number, yaw: number, roll: number }} a @param {number[]} v local x forward, y left, z up */
function launchRotate(a, v) {
    const p = a.pitch * Math.PI / 180, y = a.yaw * Math.PI / 180, r = a.roll * Math.PI / 180;
    const sp = Math.sin(p), cp = Math.cos(p), sy = Math.sin(y), cy = Math.cos(y), sr = Math.sin(r), cr = Math.cos(r);
    const f = [cp * cy, cp * sy, -sp];
    const rt = [-sr * sp * cy + cr * sy, -sr * sp * sy - cr * cy, -sr * cp];
    const u = [cr * sp * cy + sr * sy, cr * sp * sy - sr * cy, cr * cp];
    return [0, 1, 2].map(k => f[k] * v[0] - rt[k] * v[1] + u[k] * v[2]);
}
for (const [pusher, L] of Object.entries(LAUNCH)) {
    Instance.OnScriptInput("Launch_" + pusher, () => {
        const pe = Instance.FindEntityByName(pusher);
        const de = L.dest ? Instance.FindEntityByName(L.dest) : undefined;
        const pv = L.pivot ? Instance.FindEntityByName(L.pivot) : undefined;
        /** @type {number[]} */ let dir;
        let from;
        if (de && pv) {
            const a = pv.GetAbsOrigin(); from = de.GetAbsOrigin();
            dir = [from.x - a.x, from.y - a.y, from.z - a.z];
        } else if (pe) {
            from = pe.GetAbsOrigin(); dir = launchRotate(pe.GetAbsAngles(), L.dir);
        } else return;
        const len = Math.hypot(dir[0], dir[1], dir[2]) || 1;
        dir = dir.map(x => x / len);
        const near = pv ? pv.GetAbsOrigin() : from;
        let best, bestD = 400;
        for (const name of L.balls) {
            for (const ent of Instance.FindEntitiesByName(name)) {
                const o = ent.GetAbsOrigin(), v = ent.GetAbsVelocity();
                const d = Math.hypot(o.x - near.x, o.y - near.y, o.z - near.z);
                if (Math.hypot(v.x, v.y, v.z) < 100 && d <= bestD) { best = ent; bestD = d; }
            }
        }
        if (!best) return;
        const velocity = { x: dir[0] * L.speed, y: dir[1] * L.speed, z: dir[2] * L.speed };
        if (de) best.Teleport({ position: from, velocity }); else best.Teleport({ velocity });
    });
}'''


def patch_script(js, data):
    sec = JS.replace('__LAUNCH__', json.dumps(data, indent=1))
    if 'const LAUNCH = ' in js:
        return re.sub(r'// -{10,} physics launchers.*?\n}\n?(?=\n// -{10,}|\Z)', lambda _: sec + '\n', js, flags=re.S)
    mm = re.match(r'import \{([^}]*)\} from "cs_script/point_script";', js)
    if mm:
        names = [x.strip() for x in mm.group(1).split(',') if x.strip()]
        if 'Instance' not in names: names.append('Instance')
        js = js[:mm.start()] + 'import { %s } from "cs_script/point_script";' % ', '.join(names) + js[mm.end():]
    else:
        js = 'import { Instance } from "cs_script/point_script";\n\n' + js
    lines = js.rstrip('\n').split('\n')
    last_head = max((i for i, l in enumerate(lines[:60]) if l.startswith('//   ')), default=None)
    if last_head is not None: lines.insert(last_head + 1, HEAD_LINE)
    return '\n'.join(lines) + '\n\n' + sec + '\n'
