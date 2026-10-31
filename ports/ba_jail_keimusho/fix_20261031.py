import sys, json, math, collections
sys.path.insert(0, '/home/claude/cs2mapping/tools')
import numpy as np, vmapedit as V, dmx, stage_c, lighting, probecover
from scipy import ndimage
SRC = '/mnt/user-data/uploads/ba_jail_keimusho/maps/ba_jail_keimusho.vmap'
m = V.Map(SRC)
c = stage_c.Ctx('ba_jail_keimusho', '/home/claude/root')
LOG = c.log
def ents_named(n): return [e for e in m.entities() if m.name(e).lower() == n.lower()]
def near(cls, o, r=48):
    cand = [e for e in m.by_class(cls) if sum((a - b) ** 2 for a, b in zip(m.origin(e), o)) < r * r]
    assert len(cand) >= 1, (cls, o)
    return cand
def del_conn(e, pred):
    a = dmx.geta(m.E[e], b'connectionsData'); before = len(a[2])
    a[2] = [ci for ci in a[2] if not pred(m.conn_tuple(m.E[ci]))]
    return before - len(a[2])

# ================= I/O =================
# 7. door pairs
pairs = [('func_button', (-1027, -1563, 266), 'outsidebigdoor2', 'outsidebigdoor1'),
         ('trigger_multiple', (-1004, -1741, 298), 'outsideoutsitedoorright', 'outsideoutsidedoorleft'),
         ('trigger_multiple', (-1083, -1361, 292), 'aboveoutsidedoorleft', 'aboveoutsidedoorright'),
         ('func_button', (-1027, -1533, 266), 'belowoutsidedoorright', 'belowoutsidedoorleft'),
         ('trigger_multiple', (-632, -346, 298), 'grdooright', 'grdoorleft'),
         ('filter_activator_team', (-765, -338, 320), 'grdooright', 'grdoorleft'),
         ('trigger_multiple', (-98, -89, 292), 'slepdoor', 'slepdoor2'),
         ('trigger_multiple', (-492, 220, 292), 'slepdoor4', 'slepdoor3'),
         ('trigger_multiple', (-674, 931, 292), 'slepdoor13', 'slepdoor12')]
for cls, o, have, add in pairs:
    for e in near(cls, o):
        cs = [m.conn_tuple(x) for x in m.conns(e) if m.conn_tuple(x)[1].lower() == have.lower()]
        if not cs: continue
        t = cs[0]
        if any(m.conn_tuple(x)[1].lower() == add.lower() for x in m.conns(e)): continue
        m.add_conn(e, t[0], add, t[2], t[3], t[4], t[5]); LOG.append('door pair: %s %s %s -> %s.%s' % (cls, [round(x) for x in o], t[0], add, t[2]))
for e in near('trigger_multiple', (-1081, 356, 292)):
    cs = [x for x in m.conns(e) if m.conn_tuple(x)[1] == 'slepdoor5']
    if len(cs) == 2:
        dmx.set_(cs[1], b'targetName', dmx.T_STR, b'slepdoor6'); LOG.append('door pair: duplicate slepdoor5 Open -> slepdoor6')
# 8. equips
stage_c.player_equip(m, c)
eq = set(m.name(e).lower() for e in m.by_class('game_player_equip') if m.name(e))
for e, cc in m.all_conns():
    t = m.conn_tuple(cc)
    if t[1].lower() in eq and t[2] == 'TriggerForActivatedPlayer' and t[3] == '!activator': dmx.set_(cc, b'overrideParam', dmx.T_STR, b'')
# 9. skipping case values -> float strings
for e in m.by_class('logic_case'):
    if m.name(e) != 'skippingcase': continue
    for i in range(1, 17):
        k = 'Case%02d' % i; v = m.P(e, k)
        if v not in (None, '') and '.' not in v: m.setp(e, k, '%d.000000' % int(float(v)))
    LOG.append('skippingcase: case values -> "N.000000" (math_counter OutValue arrives as a float string)')
# 10. tanktrain
pass  # func_tanktrain exists in CS2 (skink52): left as is

# ================= scripts =================
SCRIPTS = {'samuraiscript': 'maps/scripts/keimusho_samurai.vjs', 'gravityscript': 'maps/scripts/keimusho_gravity.vjs', 'pushscale': 'maps/scripts/keimusho_pushscale.vjs'}
# 11. samurai mask trigger
tr = m.by_class('trigger_once')[0]
anchor = m.origin(tr)
dead = lambda t: (t[1] == 'value' and t[2].lower() == 'modifyspeed') or (t[1] == '!activator' and (t[2] in ('Alpha',) or (t[2] == 'AddOutput' and t[3].split()[0] in ('gravity', 'rendermode', 'health'))))
n = del_conn(tr, dead)
m.add_conn(tr, 'OnStartTouch', 'samuraiscript', 'RunScriptInput', 'samurai_on', 0.0, -1)
for e in m.by_class('player_speedmod'): m.remove_node(e)
LOG.append('samurai mask trigger_once: %d dead outputs (speedmod 3, gravity 0.5, Alpha, rendermode, health 200) -> samuraiscript samurai_on; player_speedmod removed' % n)
m.new_entity('point_script', [anchor[0] + 64, anchor[1], anchor[2] + 64], {'targetname': 'samuraiscript', 'cs_script': SCRIPTS['samuraiscript']})
# 13. water race gravity
for e, cc in list(m.all_conns()):
    t = m.conn_tuple(cc)
    if t[1] == '!activator' and t[2] == 'AddOutput' and t[3].startswith('gravity '):
        g = t[3].split()[1]
        dmx.set_(cc, b'targetName', dmx.T_STR, b'gravityscript'); dmx.set_(cc, b'inputName', dmx.T_STR, b'RunScriptInput')
        dmx.set_(cc, b'overrideParam', dmx.T_STR, ('Gravity_%s' % g).encode()); wr = m.origin(e)
        LOG.append('water race trigger %s: AddOutput gravity %s -> gravityscript Gravity_%s' % (t[0], g, g))
m.new_entity('point_script', [wr[0], wr[1], wr[2] + 96], {'targetname': 'gravityscript', 'cs_script': SCRIPTS['gravityscript']})
# rock dodgeball push (replaces sm_cvar phys_pushscale 25 / 1)
on = m.by_class('func_button'); on_ = [e for e in on if m.name(e) == 'rockbuttonon'][0]; off_ = [e for e in on if m.name(e) == 'rockbuttonoff'][0]
m.add_conn(on_, 'OnPressed', 'pushscale', 'RunScriptInput', 'push_on', 0.5, -1)
m.add_conn(off_, 'OnPressed', 'pushscale', 'RunScriptInput', 'push_off', 0.0, -1)
o = m.origin(on_); m.new_entity('point_script', [o[0], o[1] + 32, o[2] + 32], {'targetname': 'pushscale', 'cs_script': SCRIPTS['pushscale']})
LOG.append('rock dodgeball: rockbuttonon/off also fire pushscale push_on/push_off (script push of rock6-9 by guns/knife; sm_cvar outputs left in place)')

# trigger_push -> trigger_multiple + push zones (separate script)
c.script = 'pushscript'
stage_c.trigger_push(m, c)
pp = m.by_class('trigger_multiple'); o = [x for x in m.entities() if m.cls(x)=='trigger_multiple' and any(m.conn_tuple(k)[1]=='pushscript' for k in m.conns(x))]
if o:
    b = m.origin(o[0]); m.new_entity('point_script', [b[0], b[1], b[2] + 96], {'targetname': 'pushscript', 'cs_script': 'maps/scripts/keimusho_push.vjs'})
    import gen_script
    open('/home/claude/work/out/keimusho_push.js', 'w').write(gen_script.build('ba_jail_keimusho', 'pushscript', push=c.push))
# ================= lighting =================
OMNI_K = lighting.OMNI_RANGE_K
# 5. brightness from v2 BSP _light
E = json.load(open('/home/claude/work/v2ents.json'))
vmf = []
for e in E:
    d = dict(e)
    if d['classname'] in ('light', 'light_spot', 'light_environment'):
        vmf.append('entity\n{\n' + ''.join('\t"%s" "%s"\n' % (k, v) for k, v in e if '\x1b' not in v) + '}\n')
open('/home/claude/work/v2_lights.vmf', 'w').write(''.join(vmf))
L = m.by_class('light_omni2', 'light_barn')
before = {e: (m.P(e, 'brightness_legacy'), m.P(e, 'color')) for e in L}
# own match (same rule as fix_brightness) to know which were matched
src = [(('light_omni2' if dict(x)['classname'] == 'light' else 'light_barn'), [float(v) for v in dict(x)['origin'].split()]) for x in E if dict(x)['classname'] in ('light', 'light_spot')]
used = set()
for want, o in src:
    cand = [(sum((a - b) ** 2 for a, b in zip(m.origin(e), o)), e) for e in L if m.cls(e) == want and e not in used]
    if cand:
        d2, e = min(cand, key=lambda x: x[0])
        if d2 <= 64 ** 2: used.add(e)
lighting.fix_brightness(m, c, '/home/claude/work/v2_lights.vmf')
KEYS = ['brightness_legacy', 'brightness', 'brightness_lumens', 'brightness_candelas', 'brightness_nits', 'color', 'colormode']
for e in used:
    if m.cls(e) == 'light_omni2':
        leg = float(m.P(e, 'brightness_legacy')); m.setp(e, 'range', '%.0f' % math.sqrt(leg * OMNI_K))
nc = 0
for e in L:
    if e in used: continue
    pool = [x for x in used if m.cls(x) == m.cls(e)]
    if not pool: continue
    s = min(pool, key=lambda x: sum((a - b) ** 2 for a, b in zip(m.origin(x), m.origin(e))))
    for k in KEYS + (['range'] if m.cls(e) == 'light_omni2' else []):
        v = m.P(s, k)
        if v is not None: m.setp(e, k, v)
    nc += 1
LOG.append('brightness: %d lights matched to v2 _light (omni range = sqrt(legacy x %g)); %d v3-moved/new lights copied from the nearest matched light' % (len(used), OMNI_K, nc))

# 1-4 stationary
for env in m.by_class('light_environment'): m.setp(env, 'directlight', '3')
LOG.append('light_environment -> Stationary')
vs = 32.0
polys = lighting.world_polys(m)
for e in m.by_class('func_door', 'func_door_rotating', 'func_movelinear', 'func_brush', 'func_breakable'):
    for ch in m.children(e):
        if m.type(ch) == b'CMapMesh': polys.extend(lighting.mesh_polys(m, ch))
solid, lo = lighting.voxelise(polys, vs); S = np.array(solid.shape)
above = np.zeros(solid.shape, np.uint8); cur = np.zeros(solid.shape[:2], np.uint8)
for z in range(solid.shape[2] - 1, -1, -1):
    above[:, :, z] = cur; nz = solid[:, :, z]; cur = np.where(nz > 0, nz, cur)
walk = np.zeros(solid.shape, bool); band = np.zeros(solid.shape, bool); dist = np.full(solid.shape[:2], 999)
for z in range(solid.shape[2]):
    dist = np.where(solid[:, :, z] == 1, 0, dist + 1); walk[:, :, z] = (dist >= 1) & (dist <= 3); band[:, :, z] = dist <= 6
empty = solid == 0
li, ni = ndimage.label(empty & (above == 1)); lo_, no = ndimage.label(empty & (above != 1) & band)
wall = solid == 1
def vox(p): return tuple(np.clip(np.floor((np.array(p) - lo) / vs).astype(int), 0, S - 1))
def reg(p):
    i = vox(p)
    for dz in (0, 1, -1, 2, 3, -2):
        j = (i[0], i[1], int(np.clip(i[2] + dz, 0, S[2] - 1)))
        if li[j]: return ('in', int(li[j]))
        if lo_[j]: return ('out', int(lo_[j]))
    return None
def los(a, b):
    d = b - a; n = int(np.linalg.norm(d, axis=1).max() / 16) + 2; ok = np.ones(len(b), bool)
    for t in np.linspace(0.05, 0.95, n):
        q = a + d * t; idx = np.clip(np.floor((q - lo) / vs).astype(int), 0, S - 1); ok &= ~wall[idx[:, 0], idx[:, 1], idx[:, 2]]
    return ok
PLAYCLS = ('info_player_terrorist', 'info_player_counterterrorist', 'info_teleport_destination')
INTER = PLAYCLS + ('func_button', 'trigger_teleport', 'trigger_multiple', 'trigger_hurt', 'game_player_equip')
play = collections.Counter(reg(m.origin(e)) for e in m.by_class(*PLAYCLS))
inter_pts = np.array([m.origin(e) for e in m.by_class(*INTER)] + [m.origin(e) for e in m.entities() if m.cls(e).startswith('weapon_')])
lights = m.by_class(*lighting.LIGHT_CLASSES)
byreg = collections.defaultdict(list)
for e in lights: byreg[reg(m.origin(e))].append(e)
CAP = 640.0; MAXOV = 4
tmpl = next(e for e in m.by_class('light_omni2') if e in used)
def new_light(p, rg, leg, color='255 255 214', shadows='0'):
    props = {a[0].decode(): a[2].decode() for a in m.props(tmpl)['attrs'] if a[0] not in (b'classname',)}
    props.update({'targetname': '', 'directlight': '3', 'range': '%.0f' % rg, 'enabled': '1', 'color': color, 'colormode': '0', 'castshadows': shadows,
                  'brightness_legacy': '%g' % leg, 'brightness': '%g' % round(math.log2(leg), 6), 'brightness_lumens': '%d' % round(1000 * leg),
                  'brightness_candelas': '%d' % round(1000 * leg / (4 * math.pi)), 'brightness_nits': '%d' % round(9816 * leg)})
    return m.new_entity('light_omni2', p, props)
med_leg = float(np.median([float(m.P(e, 'brightness_legacy')) for e in used if m.cls(e) == 'light_omni2']))
added = 0; switched = 0; rep = []
sz_i = ndimage.sum(np.ones_like(li), li, index=np.arange(ni + 1))
for key in [k for k in set(byreg) | set(play) if k and k[0] == 'in' and sz_i[k[1]] >= 64]:
    mask = (li == key[1]) & walk
    pts = lo + (np.argwhere(mask) + .5) * vs
    if not len(pts): continue
    if len(pts) > 8000: pts = pts[np.random.RandomState(1).choice(len(pts), 8000, replace=False)]
    Ls = byreg.get(key, []); P = np.array([m.origin(e) for e in Ls]).reshape(-1, 3)
    D = np.linalg.norm(pts[:, None, :] - P[None, :, :], axis=2) if len(Ls) else np.zeros((len(pts), 0))
    Vv = np.zeros_like(D, bool)
    for j in range(len(Ls)):
        nr = D[:, j] < CAP
        if nr.any(): Vv[nr, j] = los(P[j], pts[nr])
    cov = np.zeros(len(pts), bool); ov = np.zeros(len(pts), int); chosen = []
    while cov.mean() < 0.9:
        best = None
        for j in range(len(Ls)):
            if j in [x[0] for x in chosen]: continue
            rg = CAP
            while rg >= 192 and (ov[(D[:, j] < rg) & Vv[:, j]] >= MAXOV).any(): rg *= 0.85
            if rg < 192: continue
            h = (D[:, j] < rg) & Vv[:, j]; g = (h & ~cov).sum()
            if best is None or g > best[0]: best = (g, j, rg, h)
        if not best or best[0] < 0.004 * len(pts): break
        g, j, rg, h = best; chosen.append((j, rg)); cov |= h; ov += h
    for j, rg in chosen:
        e = Ls[j]; m.setp(e, 'directlight', '3'); switched += 1
        if rg < float(m.P(e, 'range', '0') or 0) - 1: m.setp(e, 'range', '%.0f' % rg)
    # uncovered play-relevant pockets -> new stationary lights
    unc = pts[~cov]; newn = 0
    if len(unc) >= 15:
        g = np.zeros(solid.shape, bool); ii = np.clip(np.floor((unc - lo) / vs).astype(int), 0, S - 1); g[ii[:, 0], ii[:, 1], ii[:, 2]] = 1
        lab, nn = ndimage.label(ndimage.binary_dilation(g, iterations=2) & (li == key[1]))
        for k in range(1, nn + 1):
            cell = np.argwhere(lab == k); cnt = int(g[lab == k].sum())
            if cnt < 15: continue
            cp = lo + (cell + .5) * vs; ctr = cp.mean(0)
            if not len(inter_pts) or np.min(np.linalg.norm(inter_pts - ctr, axis=1)) > max(256, float(np.ptp(cp, axis=0).max()) / 2 + 128): continue
            # light near the top of the pocket above its centre
            col = cell[np.argmin(np.linalg.norm(cp[:, :2] - ctr[:2], axis=1))]
            top = col.copy()
            while top[2] + 1 < S[2] and (li[top[0], top[1], top[2] + 1] == key[1]): top[2] += 1
            bot = col.copy()
            while bot[2] - 1 >= 0 and (li[bot[0], bot[1], bot[2] - 1] == key[1]): bot[2] -= 1
            p = lo + (top + .5) * vs - np.array([0, 0, 16])
            p[2] = min(p[2], lo[2] + bot[2] * vs + 320)
            rg = min(CAP, float(np.linalg.norm(cp - p, axis=1).max()) + 64)
            hit = (np.linalg.norm(pts - p, axis=1) < rg)
            while rg > 192 and (ov[hit] >= MAXOV).any(): rg *= 0.85; hit = (np.linalg.norm(pts - p, axis=1) < rg)
            LOG.append('  new light %s %s r%.0f' % (key[1], [round(x) for x in p], rg)); new_light(p, rg, med_leg); ov += hit; cov |= hit & los(p, pts) ; added += 1; newn += 1
    rep.append((key, len(Ls), len(chosen), newn, round(float(cov.mean()), 2)))
LOG.append('stationary: %d existing lights -> Stationary (line-of-sight cover of the walkable floor per roofed compartment, cap %d u, <= %d overlapping); %d new unshadowed stationary light_omni2 in uncovered play pockets; per compartment (lights, switched, new, cover): %s'
           % (switched, CAP, MAXOV, added, [(k[1], a, b, d, cv) for k, a, b, d, cv in rep]))
# outdoor fills: one per cluster of spawns/teleport dests in each open-to-sky area with no stationary light
env = m.by_class('light_environment')[0]; suncol = m.P(env, 'color') or '255 255 255'
fills = 0
for key in [k for k in play if k and k[0] == 'out']:
    ps = np.array([m.origin(e) for e in m.by_class(*PLAYCLS) if reg(m.origin(e)) == key])
    groups = []
    for p in ps:
        for gp in groups:
            if np.linalg.norm(np.mean(gp, 0)[:2] - p[:2]) < 1500: gp.append(p); break
        else: groups.append([p])
    for gp in groups:
        p = np.mean(gp, 0) + np.array([0, 0, 192])
        new_light(p, 1024, max(med_leg, 0.5), color=suncol); fills += 1; LOG.append('  fill %s %s' % (key[1], [round(x) for x in p]))
LOG.append('outdoor: %d unshadowed stationary fill lights over the open-to-sky play areas (on top of the stationary sun)' % fills)
# 6. probe volume
probecover.run(m, c, fix=True)
for e in m.by_class('env_combined_light_probe_volume'):
    if m.P(e, 'moveable') is not None and m.P(e, 'indoor_outdoor_level') == '0' and m.P(e, 'edge_fade_dists') == '0 32 0': m.setp(e, 'indoor_outdoor_level', '1')
m.save('/home/claude/work/out/ba_jail_keimusho.vmap')
open('/home/claude/work/out/edit_log.txt', 'w').write('\n'.join(LOG) + '\n\nTODO\n' + '\n'.join(c.todo) + '\n')
print('\n'.join(LOG)); print('TODO', c.todo)
