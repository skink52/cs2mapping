"""Stage C step / stage D pass `physpush` (opt-in): players push the map's physics props in proportion to the prop's mass, from the io script.

Every prop_physics / prop_physics_multiplayer / prop_physics_override / func_physbox gets a name (unnamed ones become port_phys_<n>) and a mass:
the CS:GO model's .phy mass (map files first, then CS:GO's VPK) x the entity's massScale, or 50 when there's no .phy. Each tick the
script sweeps every live player's box a few units along their movement; when it touches one of those props it gives the prop
speed along the touched face's normal: player speed into the face x pushMass / (pushMass + mass), pushMass = 85 (Source's player physics
mass) per player pushing the same way, at least 10 u/s, plus spin when the push is off-centre. Contact is kept 0.12 s through flicker and
while pressed flush. Props over 350 (the engine's push mass limit) and props already moving faster than 400 u/s are left to the engine.
Damage from a prop moving under 150 u/s is cancelled only for a player who pushed it in the last 0.3 s (squeezed against a wall).
From push_mass.js v7 in github.com/Ninja-Chris/cs2-slop-porting (MIT), 2 Nov 2026.
"""
import json, re, os

HEAD_LINE = '//   (automatic) players push physics props in proportion to the prop mass'

PHYS_JS = r'''// ---------------------------------------------------------------- physics prop pushing
// Props listed here are pushed by players in proportion to mass: speed into the face x pushMass / (pushMass + mass), pushMass = 85 per
// player (Source's player physics mass); players pushing the same prop the same way add their mass. Props over 350 (the engine's push
// mass limit) are left to the engine. A player isn't hurt by a slow prop they are pushing themselves; all other prop damage is normal.
/** @type {Record<string, number>} prop name (lower case) -> mass */
const PHYS = __PHYS__;
const PHYS_REF = 85, PHYS_LIMIT = 350, PHYS_MIN_SPEED = 10, PHYS_MIN_INTO = 20, PHYS_EXTERNAL = 400, PHYS_SAFE = 150;
const PHYS_REACH = 8, PHYS_KEEP = 3, PHYS_GRACE = 0.12, PHYS_SELF_WINDOW = 0.3, PHYS_SPIN_GAIN = 0.5, PHYS_SPIN_K = 400, PHYS_SPIN_MAX = 2;
const PHYS_STAND = { mins: { x: -16, y: -16, z: 4 }, maxs: { x: 16, y: 16, z: 72 } };
const PHYS_DUCK = { mins: { x: -16, y: -16, z: 4 }, maxs: { x: 16, y: 16, z: 54 } };
/** @type {Map<number, { vx: number, vy: number, px: number, py: number, t: number, prop: any }>} slot -> push memory */
const physBySlot = new Map();
/** @type {Map<string, Map<number, number>>} prop name -> slot -> last time that player pushed it */
const physPushers = new Map();
let physLast = 0;
function physMass(ent) {
    if (!ent || !ent.IsValid()) return undefined;
    if (ent.GetOwner() instanceof CSPlayerPawn) return undefined;        // held by a player (cs2mapTTT carry sets the owner)
    const cls = ent.GetClassName();
    if (cls !== "prop_physics" && cls !== "prop_physics_multiplayer" && cls !== "prop_physics_override" && cls !== "func_physbox") return undefined;
    return PHYS[ent.GetEntityName().toLowerCase()];
}
THINKERS.push(() => {
    const now = Instance.GetGameTime();
    const dt = Math.min(Math.max(now - physLast, 0.001), 0.1);
    physLast = now;
    const groups = new Map();
    for (let slot = 0; slot < 64; slot++) {
        const pawn = Instance.GetPlayerController(slot)?.GetPlayerPawn();
        if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) { physBySlot.delete(slot); continue; }
        const v = pawn.GetAbsVelocity();
        const sp = Math.hypot(v.x, v.y);
        const st = physBySlot.get(slot);
        let tx, ty, reach;
        if (st) { tx = st.px; ty = st.py; reach = PHYS_KEEP; }
        else if (sp >= PHYS_MIN_INTO) { tx = v.x / sp; ty = v.y / sp; reach = PHYS_REACH; }
        else continue;
        const o = pawn.GetAbsOrigin();
        const hull = pawn.IsCrouched() || pawn.IsCrouching() ? PHYS_DUCK : PHYS_STAND;
        const tr = Instance.TraceBox({ mins: hull.mins, maxs: hull.maxs, start: o, end: { x: o.x + tx * reach, y: o.y + ty * reach, z: o.z }, ignoreEntity: pawn, ignorePlayers: true });
        let prop = tr.hitEntity, inside = false;
        if (tr.startedInSolid && !tr.didHit && st && st.prop && st.prop.IsValid()) { prop = st.prop; inside = true; }   // pressed flush against it
        else if (!tr.didHit || tr.startedInSolid || !prop) { if (!(st && now - st.t < PHYS_GRACE)) physBySlot.delete(slot); continue; }
        const mass = physMass(prop);
        if (mass === undefined || mass > PHYS_LIMIT) { physBySlot.delete(slot); continue; }
        let nx = inside ? -st.px : tr.normal.x, ny = inside ? -st.py : tr.normal.y;
        const nl = Math.hypot(nx, ny);
        if (nl < 0.5) { physBySlot.delete(slot); continue; }          // standing on it, not pushing it
        nx /= nl; ny /= nl;
        if (nx * tx + ny * ty > 0) { nx = -nx; ny = -ny; }
        const px = -nx, py = -ny;                                       // into the prop
        // the engine stops the player against the prop, so keep the faster of the live and remembered approach speeds
        let vx = v.x, vy = v.y;
        if (st && st.vx * px + st.vy * py > vx * px + vy * py) { vx = st.vx; vy = st.vy; }
        const into = vx * px + vy * py;
        if (into < PHYS_MIN_INTO) { physBySlot.delete(slot); continue; }
        physBySlot.set(slot, { vx, vy, px, py, t: now, prop });
        const key = prop.GetEntityName().toLowerCase();
        let g = groups.get(key);
        if (!g) groups.set(key, g = { prop, mass, list: [] });
        g.list.push({ slot, o, px, py, into });
    }
    for (const [key, g] of groups) {
        let lead = g.list[0];
        for (const e of g.list) if (e.into > lead.into) lead = e;
        const team = g.list.filter((e) => e.px * lead.px + e.py * lead.py > 0.5);
        const pv = g.prop.GetAbsVelocity();
        if (Math.hypot(pv.x, pv.y) > PHYS_EXTERNAL) continue;
        const pm = PHYS_REF * team.length;
        const speed = Math.max(PHYS_MIN_SPEED, lead.into * pm / (pm + g.mass));
        const po = g.prop.GetAbsOrigin();
        let lever = 0;
        for (const e of team) lever += (e.o.x - po.x) * e.py - (e.o.y - po.y) * e.px;
        const spin = Math.max(-PHYS_SPIN_MAX, Math.min(PHYS_SPIN_MAX, PHYS_SPIN_GAIN * speed * lever / PHYS_SPIN_K));
        const a = g.prop.GetAbsAngles();
        g.prop.Teleport({ velocity: { x: lead.px * speed, y: lead.py * speed, z: pv.z }, angles: { pitch: a.pitch, yaw: a.yaw + spin * dt * 180 / Math.PI, roll: a.roll } });
        let ps = physPushers.get(key);
        if (!ps) physPushers.set(key, ps = new Map());
        for (const e of g.list) ps.set(e.slot, now);
    }
    return true;
});
Instance.OnActivate(() => { physLast = Instance.GetGameTime(); wakeThink(); });
Instance.OnModifyPlayerDamage(({ player, inflictor }) => {
    if (physMass(inflictor) === undefined) return;
    const slot = player?.GetPlayerController()?.GetPlayerSlot();
    const at = slot === undefined ? undefined : physPushers.get(inflictor.GetEntityName().toLowerCase())?.get(slot);
    if (at === undefined || Instance.GetGameTime() - at >= PHYS_SELF_WINDOW) return;
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

def _need_pawn_import(js):
    m = re.match(r'import \{([^}]*)\} from "cs_script/point_script";', js)
    if not m: return 'import { Instance, CSPlayerPawn } from "cs_script/point_script";\n\n' + js
    names = [x.strip() for x in m.group(1).split(',') if x.strip()]
    if 'CSPlayerPawn' in names: return js
    return js[:m.start()] + 'import { %s } from "cs_script/point_script";' % ', '.join(names + ['CSPlayerPawn']) + js[m.end():]

def patch_script(js, phys):
    """add (or replace) the physics-push section in an existing <addon>_io.js (stage D)"""
    js = _need_pawn_import(js)
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
