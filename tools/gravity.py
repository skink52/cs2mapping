"""trigger_gravity replacement (stage C `gravity` step / stage D `gravity` pass).

CS2's trigger_gravity does nothing to players. Each one becomes a trigger_multiple whose OnStartTouch fires
RunScriptInput Gravity_<scale> on the map's io script; the script then gives back (1 - scale) * sv_gravity of vertical
velocity every tick while the player is airborne, which is what CS:GO's per-player gravity scale looked like.
As in CS:GO the scale sticks until another gravity trigger (or a respawn) changes it, so there is no OnEndTouch.
"""
import json, re

HEAD_LINE = '//   Gravity_<scale> replaces trigger_gravity (activator only, 1 = back to normal; sticks until the next gravity trigger)'

THINK_JS = '''// ---------------------------------------------------------------- shared think loop
/** @type {(() => boolean)[]} each returns true while it still needs ticks */
const THINKERS = [];
let thinking = false;
function wakeThink() { if (!thinking) { thinking = true; Instance.SetNextThink(Instance.GetGameTime()); } }
Instance.SetThink(() => {
    let active = false;
    for (const t of THINKERS) if (t()) active = true;
    if (active) Instance.SetNextThink(Instance.GetGameTime()); else thinking = false;
});'''

GRAVITY_JS = r'''// ---------------------------------------------------------------- trigger_gravity replacement (does nothing to players in CS2)
// CS2 players have no gravity scale, so while a player is airborne the script gives back the part of sv_gravity the
// scale removes (0.2 -> 80% of 800 pushed back up every tick). The scale sticks until another gravity trigger or a respawn.
const SV_GRAVITY = 800;
/** @type {Map<number, number>} player slot -> gravity scale (only non-1 values are stored) */
const gravityBySlot = new Map();
let gravityLast = 0;
function gravityPawn(ent) {
    if (ent instanceof CSPlayerPawn) return ent;
    if (ent instanceof CSPlayerController) return ent.GetPlayerPawn();
    return undefined;
}
THINKERS.push(() => {
    const now = Instance.GetGameTime();
    const dt = Math.min(Math.max(now - gravityLast, 0), 0.1);
    gravityLast = now;
    for (const [slot, g] of gravityBySlot) {
        const pawn = Instance.GetPlayerController(slot)?.GetPlayerPawn();
        if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) { gravityBySlot.delete(slot); continue; }
        if (pawn.GetGroundEntity() || pawn.GetMoveType() !== CSMoveType.WALK) continue;
        const v = pawn.GetAbsVelocity();
        pawn.Move({ velocity: { x: v.x, y: v.y, z: v.z + (1 - g) * SV_GRAVITY * dt } });
    }
    return gravityBySlot.size > 0;
});
for (const g of __GRAVITIES__) {
    Instance.OnScriptInput("Gravity_" + g, ({ activator }) => {
        const ctrl = gravityPawn(activator)?.GetPlayerController();
        if (!ctrl) return;
        if (g === 1) gravityBySlot.delete(ctrl.GetPlayerSlot()); else gravityBySlot.set(ctrl.GetPlayerSlot(), g);
        if (gravityBySlot.size > 0) { gravityLast = Instance.GetGameTime(); wakeThink(); }
    });
}
// every life starts at normal gravity (CS:GO reset the scale on respawn too)
Instance.OnPlayerReset(({ player }) => {
    const slot = player.GetPlayerController()?.GetPlayerSlot();
    if (slot !== undefined) gravityBySlot.delete(slot);
});'''

def js_section(gravities):
    return GRAVITY_JS.replace('__GRAVITIES__', json.dumps(sorted(gravities)))

def run(m, c):
    """Convert the map's trigger_gravity entities; fills c.gravities with the scales used."""
    tg = m.by_class('trigger_gravity')
    if not tg: return
    if not hasattr(c, 'gravities'): c.gravities = set()
    for e in tg:
        try: g = float(m.P(e, 'gravity', '1') or 1)
        except ValueError: g = 1.0
        g = round(g, 4)
        c.gravities.add(g)
        m.setp(e, 'classname', 'trigger_multiple')
        m.delp(e, 'gravity')
        if m.P(e, 'wait') is None: m.setp(e, 'wait', '0')
        m.add_conn(e, 'OnStartTouch', c.script, 'RunScriptInput', 'Gravity_%g' % g)
    c.log.append('%d trigger_gravity (does nothing to players in CS2) -> trigger_multiple firing script Gravity_<scale> on touch (scales %s); names/filters/Enable/Disable kept' % (len(tg), sorted(c.gravities)))

def patch_script(js, gravities):
    """Add the gravity section to an existing <addon>_io.js (follow-up pass)."""
    if 'Instance.OnScriptInput("Gravity_"' in js:
        return re.sub(r'for \(const g of \[[^\]]*\]\) \{\n    Instance\.OnScriptInput\("Gravity_"', 'for (const g of %s) {\n    Instance.OnScriptInput("Gravity_"' % json.dumps(sorted(gravities)), js)
    m = re.match(r'import \{([^}]*)\} from "cs_script/point_script";', js)
    if m:
        names = [x.strip() for x in m.group(1).split(',') if x.strip()]
        for n in ('CSPlayerPawn', 'CSPlayerController', 'CSMoveType'):
            if n not in names: names.append(n)
        js = js[:m.start()] + 'import { %s } from "cs_script/point_script";' % ', '.join(names) + js[m.end():]
    else:
        js = 'import { Instance, CSPlayerPawn, CSPlayerController, CSMoveType } from "cs_script/point_script";\n\n' + js
    lines = js.rstrip('\n').split('\n')
    last_head = max((i for i, l in enumerate(lines[:40]) if l.startswith('//   ')), default=None)
    if last_head is not None: lines.insert(last_head + 1, HEAD_LINE)
    js = '\n'.join(lines) + '\n'
    if 'const THINKERS' not in js: js += '\n' + THINK_JS + '\n'
    return js + '\n' + js_section(gravities) + '\n'
