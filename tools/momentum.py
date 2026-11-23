"""Stage C step / stage D pass `momentum`: Momentum Mod triggers (bhop / surf maps made for Momentum Mod) -> CS2 entities + the io script.

  trigger_momentum_teleport        stop + resetang (what CS2's trigger_teleport does without a landmark) -> trigger_teleport, kept as it
                                   is. Otherwise trigger_multiple, OnStartTouch -> RunScriptInput MomTele_<n>: the script moves the
                                   activator to the target, setting the view angles only with resetang, zeroing the velocity only with stop.
  trigger_momentum_speedthreshold  trigger_multiple; OnStartTouch / OnEndTouch -> MomSpeedIn_<n> / MomSpeedOut_<n>; its OnThreshold outputs
                                   become OnUser1, and the script fires FireUser1 on the trigger (activator = the player) when the
                                   horizontal / vertical speed is above (AboveOrBelow 0) or below (1) the limit: on entering, and every
                                   Interval s while inside when OnThink is set.
  trigger_momentum_slide           trigger_multiple; MomSlideIn / MomSlideOut: while inside and on the ground, the ground friction of the
                                   tick is given back and slopes pull the player down (surf-like sliding).
  trigger_momentum_push            trigger_multiple; on start and / or end touch (spawnflags 1<<21 / 1<<22) MomPush_<n> changes the
                                   activator's velocity once: increase 0 set, 1 add, 2 set if slower, 3 add if slower, 4 base velocity
                                   (added once), 5 variable push (spread over varpushduration with varpushbias / varpushincrease).
                                   pushdir is the direction (spawnflag 1<<19: pushdir is the force vector itself), force its speed.
Names, filters and the triggers' other outputs are kept. The script section is added to maps/scripts/<addon>_io.js (patch_script; stage C
writes the file through gen_script.build, see the integration note). Nothing here has run in game: simulated only.

Trigger semantics and the push modes from CS2-Porter momentum.py (MIT, copyright bcanusar), adapted to this pipeline's io-script model
(RunScriptInput <name> with the activator, like gravity.py / push zones). CS2-Porter's own script is not used.
    momentum.run(m, c)          fills c.momentum; momentum.patch_script(js, c.momentum) adds the section
"""
import json, math, re

TELEPORT, SPEED, SLIDE, PUSH = 'trigger_momentum_teleport', 'trigger_momentum_speedthreshold', 'trigger_momentum_slide', 'trigger_momentum_push'
CLASSES = (TELEPORT, SPEED, SLIDE, PUSH)
PUSH_DIR_AS_FORCE, PUSH_ON_START, PUSH_ON_END = 1 << 19, 1 << 21, 1 << 22
HEAD_LINE = '//   MomTele_<n> / MomSpeedIn_<n> / MomSpeedOut_<n> / MomSlideIn / MomSlideOut / MomPush_<n>   replace the Momentum Mod triggers'


def _on(v, d):
    try: return float(str(v if v not in (None, '') else d).strip()) != 0
    except ValueError: return d != '0'


def _num(v, d):
    try: return float(str(v).strip())
    except (ValueError, TypeError): return float(d)


def push_entry(kv):
    """CS2-Porter _push_entry: world velocity (pushdir angles x force), mode and when it applies"""
    try: ang = ([float(x) for x in str(kv.get('pushdir') or '0 0 0').split()[:3]] + [0.0, 0.0])[:3]
    except ValueError: ang = [0.0, 0.0, 0.0]
    p, y = math.radians(ang[0]), math.radians(ang[1])
    vec = [math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), -math.sin(p)]
    try: flags = int(float(str(kv.get('spawnflags') if kv.get('spawnflags') not in (None, '') else PUSH_ON_END)))
    except ValueError: flags = PUSH_ON_END
    if flags & PUSH_DIR_AS_FORCE: vec, force = ang, 1.0          # pushdir holds the force vector itself
    else: force = _num(kv.get('force'), 300.0)
    mode = int(_num(kv.get('increase'), 3))
    return {'vec': [round(v * force, 4) for v in vec], 'mode': mode if 0 <= mode <= 5 else 0, 'start': bool(flags & PUSH_ON_START),
            'end': bool(flags & PUSH_ON_END), 'duration': max(_num(kv.get('varpushduration'), 1.0), 0.0),
            'bias': min(max(_num(kv.get('varpushbias'), 0.5), 0.001), 0.999), 'increasing': _on(kv.get('varpushincrease'), '0')}


def _kv(m, e): return {a[0].decode().lower(): a[2].decode('utf-8', 'replace') for a in m.props(e)['attrs'] if isinstance(a[2], bytes)}


def run(m, c):
    import dmx
    ents = m.by_class(*CLASSES)
    if not ents: return 0
    data = getattr(c, 'momentum', None) or {'teleport': [], 'speed': [], 'slide': False, 'push': []}
    counts = {k: 0 for k in CLASSES}; kept_tp = 0
    for e in ents:
        cls = m.cls(e); kv = _kv(m, e); counts[cls] += 1
        drop = ()
        if cls == TELEPORT:
            stop, resetang = _on(kv.get('stop'), '1'), _on(kv.get('resetang'), '1')
            drop = ('stop', 'resetang')
            if stop and resetang:
                m.setp(e, 'classname', 'trigger_teleport'); kept_tp += 1
            else:
                i = len(data['teleport']); data['teleport'].append({'target': kv.get('target', ''), 'stop': stop, 'resetang': resetang})
                m.setp(e, 'classname', 'trigger_multiple'); drop += ('target',)
                m.add_conn(e, 'OnStartTouch', c.script, 'RunScriptInput', 'MomTele_%d' % i)
        elif cls == SPEED:
            i = len(data['speed'])
            data['speed'].append({'above': (kv.get('aboveorbelow') or '0').strip() != '1', 'horizontal': _on(kv.get('horizontal'), '0'),
                                  'hspeed': _num(kv.get('horizontalspeed'), 0), 'vertical': _on(kv.get('vertical'), '0'),
                                  'vspeed': _num(kv.get('verticalspeed'), 0), 'think': _on(kv.get('onthink'), '0'),
                                  'interval': max(_num(kv.get('interval'), 0.1), 0.0)})
            m.setp(e, 'classname', 'trigger_multiple')
            drop = ('aboveorbelow', 'horizontal', 'horizontalspeed', 'vertical', 'verticalspeed', 'onthink', 'interval')
            for cc in m.conns(e):
                if (dmx.get(cc, b'outputName') or b'').lower() == b'onthreshold': dmx.set_(cc, b'outputName', dmx.T_STR, b'OnUser1')
            m.add_conn(e, 'OnStartTouch', c.script, 'RunScriptInput', 'MomSpeedIn_%d' % i)
            m.add_conn(e, 'OnEndTouch', c.script, 'RunScriptInput', 'MomSpeedOut_%d' % i)
        elif cls == SLIDE:
            data['slide'] = True
            m.setp(e, 'classname', 'trigger_multiple')
            m.add_conn(e, 'OnStartTouch', c.script, 'RunScriptInput', 'MomSlideIn')
            m.add_conn(e, 'OnEndTouch', c.script, 'RunScriptInput', 'MomSlideOut')
        else:
            p = push_entry(kv); i = len(data['push']); data['push'].append(p)
            m.setp(e, 'classname', 'trigger_multiple')
            drop = ('pushdir', 'force', 'increase', 'varpushduration', 'varpushbias', 'varpushincrease')
            if p['start']: m.add_conn(e, 'OnStartTouch', c.script, 'RunScriptInput', 'MomPush_%d' % i)
            if p['end']: m.add_conn(e, 'OnEndTouch', c.script, 'RunScriptInput', 'MomPush_%d' % i)
        if m.P(e, 'wait') is None and cls != TELEPORT: m.setp(e, 'wait', '0')
        if drop: m.props(e)['attrs'] = [a for a in m.props(e)['attrs'] if a[0].decode().lower() not in drop]
    c.momentum = data
    c.log.append('momentum: %s -> trigger_teleport (%d kept as such) / trigger_multiple + io script MomTele/MomSpeed/MomSlide/MomPush (names, filters, outputs kept; OnThreshold -> OnUser1)'
                 % (', '.join('%d %s' % (v, k) for k, v in counts.items() if v), kept_tp))
    c.todo.append('momentum: the Momentum Mod triggers are script-driven and only simulated: try each kind in game (teleports keep speed, speed gates, slides, pushes)')
    return len(ents)


MOMENTUM_JS = r'''// ---------------------------------------------------------------- Momentum Mod triggers (trigger_momentum_*; CS2 has none)
// Semantics from CS2-Porter momentum.py (MIT, copyright bcanusar). Every trigger fires RunScriptInput Mom*_<n> with the player as activator.
/** @type {{ teleport: { target: string, stop: boolean, resetang: boolean }[], speed: { above: boolean, horizontal: boolean, hspeed: number, vertical: boolean, vspeed: number, think: boolean, interval: number }[], slide: boolean, push: { vec: number[], mode: number, start: boolean, end: boolean, duration: number, bias: number, increasing: boolean }[] }} */
const MOM = __DATA__;
const MOM_GRAVITY = 800, MOM_MIN_SLOPE_Z = 0.7;
function momPawn(ent) {
    if (ent instanceof CSPlayerPawn) return ent;
    if (ent instanceof CSPlayerController) return ent.GetPlayerPawn();
    return undefined;
}
function momSlot(pawn) { const ctrl = pawn.GetPlayerController(); return ctrl ? ctrl.GetPlayerSlot() : undefined; }
const momHoriz = (v) => Math.sqrt(v.x * v.x + v.y * v.y);
const momAdd = (a, b) => ({ x: a.x + b.x, y: a.y + b.y, z: a.z + b.z });
const momLenSq = (v) => v.x * v.x + v.y * v.y + v.z * v.z;
// teleport: CS2's trigger_teleport always stops the player and sets the view; these keep one or both
MOM.teleport.forEach((t, i) => {
    Instance.OnScriptInput("MomTele_" + i, ({ activator }) => {
        const pawn = momPawn(activator);
        if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) return;
        const dest = Entities.FindByName(t.target)[0];
        if (!dest || !dest.IsValid()) return;
        /** @type {{ position: import("cs_script/point_script").Vector, angles?: import("cs_script/point_script").QAngle, velocity?: import("cs_script/point_script").Vector }} */
        const values = { position: dest.GetAbsOrigin() };
        if (t.resetang) values.angles = dest.GetAbsAngles();
        if (t.stop) values.velocity = { x: 0, y: 0, z: 0 };
        pawn.Teleport(values);
    });
});
// speed threshold: OnThreshold became the trigger's OnUser1
/** @type {Map<string, { e: (typeof MOM.speed)[number], trigger: import("cs_script/point_script").Entity, pawn: CSPlayerPawn, next: number }>} */
const momSpeedIn = new Map();
function momSpeedCheck(st) {
    const v = st.pawn.GetAbsVelocity(), e = st.e;
    const pass = (s, lim) => e.above ? s > lim : s < lim;
    if (e.horizontal && pass(momHoriz(v), e.hspeed)) st.trigger.FireInput({ input: "FireUser1", activator: st.pawn, caller: st.trigger });
    if (e.vertical && pass(Math.abs(v.z), e.vspeed)) st.trigger.FireInput({ input: "FireUser1", activator: st.pawn, caller: st.trigger });
}
MOM.speed.forEach((e, i) => {
    Instance.OnScriptInput("MomSpeedIn_" + i, ({ activator, caller }) => {
        const pawn = momPawn(activator);
        if (!pawn || !pawn.IsValid() || !caller) return;
        const slot = momSlot(pawn);
        if (slot === undefined) return;
        const st = { e, trigger: caller, pawn, next: Instance.GetGameTime() + Math.max(e.interval, 0.01) };
        momSpeedCheck(st);
        if (e.think) { momSpeedIn.set(i + "|" + slot, st); wakeThink(); }
    });
    Instance.OnScriptInput("MomSpeedOut_" + i, ({ activator }) => {
        const pawn = momPawn(activator);
        const slot = pawn ? momSlot(pawn) : undefined;
        if (slot !== undefined) momSpeedIn.delete(i + "|" + slot);
    });
});
// slide: no ground friction inside, slopes pull the player down
/** @type {Map<number, { pawn: CSPlayerPawn, count: number, speed: number }>} */
const momSlide = new Map();
let momLast = 0;
Instance.OnScriptInput("MomSlideIn", ({ activator }) => {
    const pawn = momPawn(activator);
    const slot = pawn ? momSlot(pawn) : undefined;
    if (slot === undefined) return;
    const st = momSlide.get(slot);
    if (st) { st.count++; return; }
    momSlide.set(slot, { pawn, count: 1, speed: momHoriz(pawn.GetAbsVelocity()) });
    momLast = Instance.GetGameTime(); wakeThink();
});
Instance.OnScriptInput("MomSlideOut", ({ activator }) => {
    const pawn = momPawn(activator);
    const slot = pawn ? momSlot(pawn) : undefined;
    const st = slot === undefined ? undefined : momSlide.get(slot);
    if (st && --st.count <= 0) momSlide.delete(slot);
});
function momSlideTick(st, dt) {
    const pawn = st.pawn, v = pawn.GetAbsVelocity();
    const speed = momHoriz(v);
    if (!pawn.GetGroundEntity()) { st.speed = speed; return; }
    let vx = v.x, vy = v.y;
    const friction = (Console.GetConvarNumber("sv_friction") ?? 5.2) * dt * Math.max(st.speed, Console.GetConvarNumber("sv_stopspeed") ?? 80);
    if (speed > 1 && st.speed > speed && st.speed - speed <= friction * 1.5 + 1) { const k = st.speed / speed; vx *= k; vy *= k; }   // a bigger loss is a hit: kept
    const pos = pawn.GetAbsOrigin();
    const tr = Instance.TraceLine({ start: { x: pos.x, y: pos.y, z: pos.z + 2 }, end: { x: pos.x, y: pos.y, z: pos.z - 16 }, ignorePlayers: true });
    if (tr.didHit && tr.normal.z < 0.999 && tr.normal.z >= MOM_MIN_SLOPE_Z) {
        const pull = MOM_GRAVITY * dt * tr.normal.z;
        vx += tr.normal.x * pull; vy += tr.normal.y * pull;
    }
    st.speed = Math.sqrt(vx * vx + vy * vy);
    if (vx !== v.x || vy !== v.y) pawn.Teleport({ velocity: { x: vx, y: vy, z: v.z } });
}
// push: the velocity changes once (mode 5 spreads it over a duration)
/** @type {{ pawn: CSPlayerPawn, vec: import("cs_script/point_script").Vector, until: number, start: number, duration: number, bias: number, increasing: boolean }[]} */
let momVarPush = [];
const momBias = (x, b) => Math.pow(Math.max(x, 0), Math.log(b) / Math.log(0.5));
MOM.push.forEach((p, i) => {
    Instance.OnScriptInput("MomPush_" + i, ({ activator }) => {
        const pawn = momPawn(activator);
        if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) return;
        const cur = pawn.GetAbsVelocity();
        let vel = { x: p.vec[0], y: p.vec[1], z: p.vec[2] };
        if (p.mode === 1 || p.mode === 4) vel = momAdd(vel, cur);                     // add / base velocity (added once)
        else if (p.mode === 2) { if (momLenSq(vel) < momLenSq(cur)) vel = cur; }       // set if slower
        else if (p.mode === 3) { if (momLenSq(vel) < momLenSq(cur)) vel = momAdd(vel, cur); }   // add if slower
        else if (p.mode === 5) {                                                       // variable push
            const now = Instance.GetGameTime();
            momVarPush.push({ pawn, vec: vel, start: now, until: now + Math.max(p.duration, 0.01), duration: Math.max(p.duration, 0.01), bias: p.bias, increasing: p.increasing });
            wakeThink(); return;
        }
        pawn.Teleport({ velocity: vel });
    });
});
THINKERS.push(() => {
    const now = Instance.GetGameTime();
    const dt = Math.min(Math.max(now - momLast, 0), 0.1); momLast = now;
    for (const [slot, st] of momSlide) {
        if (!st.pawn.IsValid() || !st.pawn.IsAlive()) { momSlide.delete(slot); continue; }
        momSlideTick(st, dt);
    }
    for (const [key, st] of momSpeedIn) {
        if (!st.pawn.IsValid() || !st.pawn.IsAlive() || !st.trigger.IsValid()) { momSpeedIn.delete(key); continue; }
        if (now >= st.next) { st.next = now + Math.max(st.e.interval, 0.01); momSpeedCheck(st); }
    }
    momVarPush = momVarPush.filter((st) => {
        if (!st.pawn.IsValid() || !st.pawn.IsAlive()) return false;
        let f = Math.min((now - st.start) / st.duration, 1);
        if (!st.increasing) f = 1 - f;
        const k = momBias(f, st.bias);                               // added every tick, as CS2-Porter's script does (one push a tick)
        if (k > 0) st.pawn.Teleport({ velocity: momAdd(st.pawn.GetAbsVelocity(), { x: st.vec.x * k, y: st.vec.y * k, z: st.vec.z * k }) });
        return now < st.until;
    });
    return momSlide.size > 0 || momSpeedIn.size > 0 || momVarPush.length > 0;
});
Instance.OnPlayerReset(({ player }) => {
    const slot = player ? momSlot(player) : undefined;
    if (slot === undefined) return;
    momSlide.delete(slot);
    for (const key of [...momSpeedIn.keys()]) if (key.endsWith("|" + slot)) momSpeedIn.delete(key);
    momVarPush = momVarPush.filter((st) => st.pawn !== player);
});'''


def js_section(data):
    d = {'teleport': data.get('teleport', []), 'speed': data.get('speed', []), 'slide': bool(data.get('slide')), 'push': data.get('push', [])}
    return MOMENTUM_JS.replace('__DATA__', json.dumps(d))


def patch_script(js, data):
    """Add (or replace) the Momentum section in an existing or freshly built <addon>_io.js."""
    import gravity
    marker = '// ---------------------------------------------------------------- Momentum Mod triggers'
    if marker in js:
        i = js.index(marker); j = js.find('\n// ----------------------------------------------------------------', i + 10)
        return js[:i] + js_section(data) + (js[j:] if j >= 0 else '\n')
    mm = re.match(r'import \{([^}]*)\} from "cs_script/point_script";', js)
    if mm:
        names = [x.strip() for x in mm.group(1).split(',') if x.strip()]
        for n in ('Instance', 'CSPlayerPawn', 'CSPlayerController', 'Entities', 'Console'):
            if n not in names: names.append(n)
        js = js[:mm.start()] + 'import { %s } from "cs_script/point_script";' % ', '.join(names) + js[mm.end():]
    else:
        js = 'import { Instance, CSPlayerPawn, CSPlayerController, Entities, Console } from "cs_script/point_script";\n\n' + js
    lines = js.rstrip('\n').split('\n')
    last_head = max((i for i, l in enumerate(lines[:40]) if l.startswith('//   ')), default=None)
    if last_head is not None: lines.insert(last_head + 1, HEAD_LINE)
    js = '\n'.join(lines) + '\n'
    if 'const THINKERS' not in js: js += '\n' + gravity.THINK_JS + '\n'
    return js + '\n' + js_section(data) + '\n'
