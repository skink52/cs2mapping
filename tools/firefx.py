"""Stage C step / stage D pass `fire`: env_fire and env_spark.

CS2's env_fire draws nothing and does no damage (tested by skink52 on ttt_minecraft / ba_jail_keimusho and by cs2-slop-porting). The env_fire
stays (so its inputs still resolve) and gets companions driven by the same outputs:
- <name>_fx: info_particle_system playing the particle CS:GO's own client played, particles/burning_fx/env_fire_<tiny|small|medium|large>[_smoke]
  (picked by floor(firesize / 36); _smoke unless Smokeless), which CS2 ships. If the staged CS2 VPK lacks it, a generated
  particles/port_fire/fire_<size>.vpcf (vpcf66) is used instead.
- <name>_hurt: burn trigger_hurt (2/s, the lowest a CS2 trigger_hurt does; CS:GO did 1/s) over CS:GO's damage box (+-firesize/2, at least 16,
  from the origin up to firesize), unless damagescale is 0.
I/O follows CS:GO's fire.cpp: StartFire -> Start / Enable; a fire with fuel (not Infinite) is removed when it burns out, so Kill at
health s (+1 s for the flames); Extinguish <s> stops the flames after s s, the hurt at once; Disable puts it out at once; Kill -> Kill.
Unnamed fires that don't Start On are skipped (nothing can light them).
env_spark: kept for its sound, plus <name>_fx with a generated spark particle (particles/port_spark/, vpcf66 trails: about
Magnitude^2 x 3 streaks per burst every 0.1-MaxDelay s, 100-300 u/s, gravity 800; Directional fires along the entity's forward axis).
StartSpark / StopSpark -> Start / Stop, SparkOnce -> Start then Stop 0.15 s later, Kill -> Kill; ToggleSpark can't be mirrored (TO CHECK).
Rerun-safe. Method from github.com/Ninja-Chris/cs2-slop-porting 3.5 (MIT), 2 Nov 2026.
    firefx.run(m, c)
"""
import io, math
import dmx, vmapedit as V
import vpcf66 as P

SIZES = ('tiny', 'small', 'medium', 'large')
SIZE_STEP = 36.0
HURT_DAMAGE = 2.0


def _num(m, e, k, d):
    try: return float(m.P(e, k, '') or d)
    except ValueError: return float(d)


def _tex(c, rel, N, fn):
    from PIL import Image
    import radar
    im = Image.new('RGBA', (N, N))
    for y in range(N):
        for x in range(N): im.putpixel((x, y), (255, 255, 255, int(max(0.0, min(1.0, fn((x + .5) / N, (y + .5) / N))) * 255 + .5)))
    b = io.BytesIO(); im.save(b, 'PNG')
    c.write(rel + '.png', b.getvalue())
    c.write(rel + '.vtex', radar.VTEX.replace('panorama/images/overheadmaps/%(map)s_radar_psd.png', rel + '.png').replace('"int" "1024"', '"int" "%d"' % N).encode())
    return rel + '.vtex'


def fire_vpcf(size, tex):
    inits = P.sphere((size * 0.6, -12, -12), (size * 1.3, 12, 12), rmax=size * 0.3) + P.init_float(0.35, 0.8, P.LIFE) + \
        P.init_float(size * 0.15, size * 0.28, P.RADIUS) + P.init_float(0, 360, P.ROT, True) + P.init_float(0, 90, P.ROTSPEED, True)
    ops = P.op('C_OP_BasicMovement') + P.op('C_OP_SpinUpdate') + P.op('C_OP_ColorInterpolate', m_ColorFade='[ 190, 40, 8, 255 ]') + \
        P.op('C_OP_InterpolateRadius', m_flStartTime='0.0', m_flEndTime='1.0', m_flStartScale='1.0', m_flEndScale='0.35') + P.fade(0.15, 0.5) + P.op('C_OP_Decay')
    return P.system(int(size * 0.9) + 16, (255, 214, 120, 255), size * 0.2, P.renderer(tex, additive=True, selfillum=1.0), size * 0.9, inits, ops)


def spark_vpcf(mag, trail, delay, directional, tex):
    per = mag * mag * 3.0; rate = per / (0.1 + delay / 2.0); life = 0.35 + 0.15 * mag
    vmin, vmax = ((100, -120, -120), (300, 120, 120)) if directional else ((-120, -120, 50), (120, 120, 300))
    inits = P.sphere(vmin, vmax) + P.init_float(life * 0.6, life, P.LIFE) + P.init_float(0.5, 2.0, P.RADIUS)
    ops = P.op('C_OP_BasicMovement', m_Gravity='[ 0.0, 0.0, -800.0 ]') + P.op('C_OP_FadeOutSimple', m_flFadeOutTime='0.5') + P.op('C_OP_Decay')
    rend = P.renderer(tex, 'C_OP_RenderTrails', additive=True, extra=['m_flLengthScale = %s' % P.f(0.03 * trail)])
    return P.system(int(rate * life) + 16, (255, 255, 255, 255), 1.0, rend, rate, inits, ops)


def _flame(x, y):
    w = 0.32 * max(0.15, min(1.0, 1 - (0.62 - y) * 1.1))
    d = math.sqrt(((x - .5) / max(w, 1e-3)) ** 2 + ((y - .62) / 0.45) ** 2)
    return max(0.0, 1 - d) ** 1.4


def _streak(x, y):
    return max(0.0, 1 - abs(x - .5) * 6) * max(0.0, 1 - abs(y - .5) * 2.2)


def _box(m, mn, mx):
    import watervol
    tm = V.Map(watervol.TEMPLATE)
    return watervol.box(m, tm, tm.children(tm.world)[0], mn, mx, b'materials/tools/toolstrigger.vmat')


def run(m, c):
    fires, sparks = m.by_class('env_fire'), m.by_class('env_spark')
    if not fires and not sparks: return 0
    names = {m.name(e).lower() for e in m.entities() if m.name(e)}
    made = {}                                   # fire name -> ([(companion, on, off)], burn time, infinite)
    nfx = nhurt = nstock = 0; skipped = []; gen_sizes = set(); floating = []
    for e in fires:
        nm = m.name(e); sf = int(_num(m, e, 'spawnflags', 0)); size = _num(m, e, 'firesize', 64); dur = _num(m, e, 'health', 30)
        if not nm and not sf & 4: skipped.append(' '.join(str(round(x)) for x in m.origin(e))); continue
        o = m.origin(e); par = m.P(e, 'parentname', '')
        comp = []
        fx = (nm + '_fx') if nm else ''
        if not nm or fx.lower() not in names:
            eff = 'particles/burning_fx/env_fire_%s%s.vpcf' % (SIZES[min(3, int(size // SIZE_STEP))], '' if sf & 2 else '_smoke')
            if c.cs2v and not c.cs2v.has(eff + '_c'):
                gs = max(16, int(round(size / 16.0) * 16)); gen_sizes.add(gs); eff = 'particles/port_fire/fire_%d.vpcf' % gs
            else: nstock += 1
            props = {'targetname': fx, 'effect_name': eff, 'start_active': '1' if sf & 4 else '0'}
            if par: props['parentname'] = par
            m.new_entity('info_particle_system', o, props, angles=m.g(e, b'angles', [0, 0, 0]))
            nfx += 1
        if nm: comp.append((fx, 'Start', 'Stop'))
        hurt = (nm + '_hurt') if nm else ''
        if _num(m, e, 'damagescale', 1) > 0:
            if not nm or hurt.lower() not in names:
                half = max(16.0, size / 2.0)
                mn, mx = [o[0] - half, o[1] - half, o[2]], [o[0] + half, o[1] + half, o[2] + size]
                props = {'targetname': hurt, 'damage': '%g' % HURT_DAMAGE, 'damagecap': '%g' % HURT_DAMAGE, 'damagetype': '8', 'spawnflags': '1',
                         'StartDisabled': '0' if sf & 4 else '1'}
                if par: props['parentname'] = par
                h = m.new_entity('trigger_hurt', [(mn[k] + mx[k]) / 2 for k in range(3)], props)
                dmx.geta(m.E[h], b'children')[2].append(_box(m, mn, mx))
                nhurt += 1
            if nm: comp.append((hurt, 'Enable', 'Disable'))
        if nm:
            names.update(x[0].lower() for x in comp)
            made[nm.lower()] = (comp, dur, bool(sf & 1))
        if sf & 4 and not sf & 1: c.todo.append('env_fire %s starts on and burned %g s in CS:GO: its flames / hurt now stay on' % (nm or 'unnamed', dur))
        if not sf & 16: floating.append(nm or 'unnamed')
    have = {(src,) + tuple(x.lower() if isinstance(x, str) else x for x in m.conn_tuple(cc)) for src, cc in m.all_conns()}

    def add(src, o_, ent, inp, d, n):
        k = (src, o_.lower(), ent.lower(), inp.lower(), '', d, n)
        if k in have: return 0
        have.add(k); m.add_conn(src, o_, ent, inp, '', d, n); return 1
    nio = 0; enable = set()
    for src, cc in list(m.all_conns()):
        o_, t, i, p, d, n = m.conn_tuple(cc)
        f = made.get(t.lower())
        if not f: continue
        comp, dur, inf = f; il = i.lower()
        try: secs = max(0.0, float(p or 0))
        except ValueError: secs = 0.0
        for ent, on, off in comp:
            isfx = ent.lower().endswith('_fx')
            if il == 'startfire':
                nio += add(src, o_, ent, on, d, n)
                if not inf: nio += add(src, o_, ent, 'Kill', d + dur + (1.0 if isfx else 0.0), n)
            elif il in ('extinguish', 'extinguishtemporary'): nio += add(src, o_, ent, off, d + (secs if isfx else 0.0), n)
            elif il == 'disable': nio += add(src, o_, ent, off, d, n)
            elif il in ('kill', 'killhierarchy'): nio += add(src, o_, ent, 'Kill', d, n)
        if il == 'enable': enable.add(t)
    if gen_sizes:
        tex = _tex(c, 'materials/port_fire/flame', 64, _flame)
        for s in gen_sizes: c.write('particles/port_fire/fire_%d.vpcf' % s, fire_vpcf(s, tex).encode())
    sp = {}; nsp = 0; spfiles = set(); lost = 0
    for e in sparks:
        nm = m.name(e); sf = int(_num(m, e, 'spawnflags', 0))
        mag = max(1, int(_num(m, e, 'Magnitude', 1))); trail = max(1, int(_num(m, e, 'TrailLength', 1))); delay = max(0.0, _num(m, e, 'MaxDelay', 0))
        dirn = bool(sf & 512)
        rel = 'particles/port_spark/spark_m%d_t%d_d%s%s.vpcf' % (mag, trail, ('%g' % delay).replace('.', 'd'), '_dir' if dirn else '')
        fx = (nm + '_fx') if nm else ''
        if nm and fx.lower() in names: sp[nm.lower()] = fx; continue
        if not nm and not sf & 64: continue
        spfiles.add((rel, mag, trail, delay, dirn))
        props = {'targetname': fx, 'effect_name': rel, 'start_active': '1' if sf & 64 else '0'}
        if m.P(e, 'parentname', ''): props['parentname'] = m.P(e, 'parentname', '')
        m.new_entity('info_particle_system', m.origin(e), props, angles=m.g(e, b'angles', [0, 0, 0]))
        nsp += 1
        if nm: names.add(fx.lower()); sp[nm.lower()] = fx
    if spfiles:
        tex = _tex(c, 'materials/port_spark/streak', 32, _streak)
        for rel, mag, trail, delay, dirn in spfiles: c.write(rel, spark_vpcf(mag, trail, delay, dirn, tex).encode())
    for src, cc in list(m.all_conns()):
        o_, t, i, p, d, n = m.conn_tuple(cc)
        fx = sp.get(t.lower())
        if not fx: continue
        il = i.lower()
        if il in ('startspark', 'stopspark'): nio += add(src, o_, fx, 'Start' if il == 'startspark' else 'Stop', d, n)
        elif il == 'sparkonce': nio += add(src, o_, fx, 'Start', d, n) + add(src, o_, fx, 'Stop', d + 0.15, n)
        elif il in ('kill', 'killhierarchy'): nio += add(src, o_, fx, 'Kill', d, n)
        elif il == 'togglespark': lost += 1
    if fires:
        c.log.append('fire: %d env_fire -> %d _fx particles (%d stock burning_fx, generated sizes %s), %d burn trigger_hurts (%g/s); %d skipped (unnamed, not Start On)'
                     % (len(fires), nfx, nstock, sorted(gen_sizes) or '-', nhurt, HURT_DAMAGE, len(skipped)))
        if floating: c.todo.append('env_fire without Don\'t Drop (CS:GO dropped it onto the floor below; CS2 flames/hurt stay where placed): %s' % ', '.join(floating[:20]))
        if enable: c.todo.append('env_fire Enable inputs (CS:GO ignored StartFire while disabled; the particle/hurt start on every StartFire): %s' % ', '.join(sorted(enable)))
    if sparks: c.log.append('fire: %d env_spark -> %d _fx spark particles (particles/port_spark/, vpcf66); env_sparks kept for their sound' % (len(sparks), nsp))
    if nio: c.log.append('fire: %d outputs added so the companions follow StartFire / Extinguish / Disable / Kill / spark inputs' % nio)
    if lost: c.todo.append('env_spark ToggleSpark x%d: particles have no toggle input' % lost)
    return len(fires) + len(sparks)
