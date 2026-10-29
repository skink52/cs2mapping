"""Stage C step / stage D pass `physpush` (opt-in): players push the map's physics props in proportion to the prop's mass, from the io script.

Every prop_physics / prop_physics_multiplayer / prop_physics_override / func_physbox gets a name (unnamed ones become port_phys_<n>) and a mass:
the CS:GO model's .phy mass (map files first, then CS:GO's VPK) x the entity's massScale, or 50 when there's no .phy. Each tick the
script sweeps every live player's box a few units along their movement; when it touches one of those props it gives the prop
speed along the touched face's normal: player speed into the face x 20 / (20 + mass), at least 10 u/s, plus a little spin when the
push is off-centre. Props already moving faster than 400 u/s (blasts, shots) are left to the engine, and damage from a listed prop
moving under 150 u/s is cancelled (bumping a crate shouldn't hurt).
Idea from push_mass.js in github.com/Ninja-Chris/cs2-slop-porting, written fresh for the generated io script.
"""
import json, re, os

HEAD_LINE = '//   (automatic) players push physics props in proportion to the prop mass'

PHYS_JS = r'''// ---------------------------------------------------------------- physics prop pushing
// Props listed here are pushed by players in proportion to mass: speed into the face x REF / (REF + mass).
/** @type {Record<string, number>} prop name (lower case) -> mass */
const PHYS = __PHYS__;
const PHYS_REF = 20, PHYS_MIN_SPEED = 10, PHYS_MIN_INTO = 20, PHYS_EXTERNAL = 400, PHYS_SAFE = 150;
const PHYS_REACH = 8, PHYS_KEEP = 3, PHYS_SPIN_GAIN = 0.5, PHYS_SPIN_K = 400, PHYS_SPIN_MAX = 2;
const PHYS_STAND = { mins: { x: -16, y: -16, z: 4 }, maxs: { x: 16, y: 16, z: 72 } };
const PHYS_DUCK = { mins: { x: -16, y: -16, z: 4 }, maxs: { x: 16, y: 16, z: 54 } };
/** @type {Map<number, { vx: number, vy: number, nx: number, ny: number }>} slot -> last push (approach velocity, push direction) */
const physBySlot = new Map();
let physLast = 0;
function physMass(ent) {
    if (!ent || !ent.IsValid()) return undefined;
    const cls = ent.GetClassName();
    if (cls !== "prop_physics" && cls !== "prop_physics_multiplayer" && cls !== "prop_physics_override" && cls !== "func_physbox") return undefined;
    return PHYS[ent.GetEntityName().toLowerCase()];
}
THINKERS.push(() => {
    const now = Instance.GetGameTime();
    const dt = Math.min(Math.max(now - physLast, 0.001), 0.1);
    physLast = now;
    for (let slot = 0; slot < 64; slot++) {
        const pawn = Instance.GetPlayerController(slot)?.GetPlayerPawn();
        if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) { physBySlot.delete(slot); continue; }
        const v = pawn.GetAbsVelocity();
        const sp = Math.hypot(v.x, v.y);
        const last = physBySlot.get(slot);
        let dx, dy, reach;
        if (last) { dx = last.nx; dy = last.ny; reach = PHYS_KEEP; }
        else if (sp >= PHYS_MIN_INTO) { dx = v.x / sp; dy = v.y / sp; reach = PHYS_REACH; }
        else continue;
        const o = pawn.GetAbsOrigin();
        const hull = pawn.IsCrouched() || pawn.IsCrouching() ? PHYS_DUCK : PHYS_STAND;
        const tr = Instance.TraceBox({ mins: hull.mins, maxs: hull.maxs, start: o, end: { x: o.x + dx * reach, y: o.y + dy * reach, z: o.z }, ignoreEntity: pawn, ignorePlayers: true });
        const prop = tr.didHit && !tr.startedInSolid ? tr.hitEntity : undefined;
        const mass = physMass(prop);
        if (mass === undefined) { physBySlot.delete(slot); continue; }
        let nx = tr.normal.x, ny = tr.normal.y;
        const nl = Math.hypot(nx, ny);
        if (nl < 0.5) { physBySlot.delete(slot); continue; }          // standing on it, not pushing it
        nx = -nx / nl; ny = -ny / nl;                                   // into the prop
        if (nx * dx + ny * dy < 0) { nx = -nx; ny = -ny; }
        // the engine stops the player against the prop, so keep the faster of the live and remembered approach speeds
        let vx = v.x, vy = v.y;
        if (last && last.vx * nx + last.vy * ny > vx * nx + vy * ny) { vx = last.vx; vy = last.vy; }
        const into = vx * nx + vy * ny;
        if (into < PHYS_MIN_INTO) { physBySlot.delete(slot); continue; }
        physBySlot.set(slot, { vx, vy, nx, ny });
        const pv = prop.GetAbsVelocity();
        if (Math.hypot(pv.x, pv.y) > PHYS_EXTERNAL) continue;
        const speed = Math.max(PHYS_MIN_SPEED, into * PHYS_REF / (PHYS_REF + mass));
        const po = prop.GetAbsOrigin();
        const lever = (o.x - po.x) * ny - (o.y - po.y) * nx;
        const spin = Math.max(-PHYS_SPIN_MAX, Math.min(PHYS_SPIN_MAX, PHYS_SPIN_GAIN * speed * lever / PHYS_SPIN_K));
        const a = prop.GetAbsAngles();
        prop.Teleport({ velocity: { x: nx * speed, y: ny * speed, z: pv.z }, angles: { pitch: a.pitch, yaw: a.yaw + spin * dt * 180 / Math.PI, roll: a.roll } });
    }
    return true;
});
Instance.OnActivate(() => { physLast = Instance.GetGameTime(); wakeThink(); });
Instance.OnModifyPlayerDamage(({ inflictor }) => {
    if (physMass(inflictor) === undefined) return;
    const pv = inflictor.GetAbsVelocity();
    if (Math.hypot(pv.x, pv.y, pv.z) < PHYS_SAFE) return { abort: true };
});'''

CLASSES = ('prop_physics', 'prop_physics_multiplayer', 'prop_physics_override', 'func_physbox')

def phy_mass(data):
    """total of the "mass" values in a .phy file's text section, or None"""
    vals = [float(x) for x in re.findall(rb'"mass"\s+"([0-9.]+)"', data or b'')]
    return sum(vals) if vals else None

def js_section(phys):
    return PHYS_JS.replace('__PHYS__', json.dumps(phys, indent=4, sort_keys=True))

def run(m, c):
    props = m.by_class(*CLASSES)
    if not props: return
    c.phys = getattr(c, 'phys', {})
    k = 0; guessed = []
    taken = set(m.name(e).lower() for e in m.entities() if m.name(e))
    for e in props:
        name = m.name(e)
        if not name:
            while 'port_phys_%d' % k in taken: k += 1
            name = 'port_phys_%d' % k; taken.add(name); m.setp(e, 'targetname', name)
        mdl = (m.P(e, 'model') or '').lower().replace('\\', '/')
        phy = mdl[:-5] + '.phy' if mdl.endswith('.vmdl') else None
        mass = None
        if m.cls(e) == 'func_physbox':
            # brush physbox: mass from its size (~ a 40x40x20 minecart = 64), there's no .phy
            b = m.bounds(e)
            if b: mass = min(max((b[1][0] - b[0][0]) * (b[1][1] - b[0][1]) * (b[1][2] - b[0][2]) / 500.0, 2.0), 400.0)
        elif phy and c.src and c.src.has(phy): mass = phy_mass(c.src.read(phy))
        if mass is None: mass = 50.0; guessed.append(os.path.basename(mdl) or name)
        try: ms = float(m.P(e, 'massScale', m.P(e, 'massscale', '0')) or 0)
        except ValueError: ms = 0
        mass *= ms if ms > 0 else 1
        key = name.lower()
        c.phys[key] = round(max(c.phys.get(key, 0), mass), 1)
    c.log.append('physpush: %d physics props pushed by mass from the io script (masses %s)' % (len(props), ', '.join('%s %g' % kv for kv in sorted(c.phys.items()))[:500]))
    if guessed: c.todo.append('physpush: no CS:GO .phy mass for %s - used 50' % ', '.join(sorted(set(guessed)))[:400])

def patch_script(js, phys):
    """add (or replace) the physics-push section in an existing <addon>_io.js (stage D)"""
    sec = js_section(phys)
    mark = '// ---------------------------------------------------------------- physics prop pushing'
    if mark in js:
        i = js.index(mark); j = js.find('\n// ----------------------------------------------------------------', i + 10)
        return js[:i] + sec + (js[j:] if j >= 0 else '\n')
    import gravity
    lines = js.rstrip('\n').split('\n')
    last_head = max((i for i, l in enumerate(lines[:40]) if l.startswith('//   ')), default=None)
    if last_head is not None: lines.insert(last_head + 1, HEAD_LINE)
    js = '\n'.join(lines) + '\n'
    if 'const THINKERS' not in js: js += '\n' + gravity.THINK_JS + '\n'
    return js + '\n' + sec + '\n'
