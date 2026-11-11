"""mg_monsoon world checks on the generated vmap.

usage: check_world.py <map.vmap> [--plot out.png [x0,y0,x1,y1]]

1 every name in docs/CONTRACT.md is present with the right class and count
2 no prop origin more than 8 u below or 6 u above a surface under it (terrain, a platform top, the bridge deck, a tunnel floor,
  a karst crown), except the props mv_places listed as deliberately off the ground (out/world_sites.json "exceptions")
3 placer overlap audit of the solid props -> out/overlaps.json (top model pairs printed)
4 spawn / seat points: 80 u of clear headroom, standing on a surface, not inside a prop footprint
5 every flag reachable in principle: slope along the straight line from the nearest road stays under 40 degrees
6 counts per class
--plot draws a top-down picture (terrain shade, roads, prop footprints, spawns) of the whole map or a box, to look at.
Exit code 1 when a check fails.
"""
import os, sys, json, math, re
from collections import Counter
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dmx, vmapgen as G, placer
import layout as L
import mv_stock as S

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'out')
# model pairs that touch by design (stacked rows, things standing on / inside another prop)
OK_PAIR = [('sandbag', 'sandbag'), ('truss_span', ''), ('psp_pad', ''), ('camo_net', ''), ('fdc_bunker', 'plot_table'), ('camp_hut', 'plot_table_t'),
           ('m3_tripod', 'sandbag'), ('dshk_mount', 'sandbag'), ('quad50_mount', 'sandbag'), ('rocket_crate', 'rocket_crate'), ('ammo_crate', 'ammo_crate'),
           ('roots', ''), ('bridge_pier', ''), ('m2_gun', ''), ('dshk_gun', ''), ('quad50_gun', ''), ('howitzer_m102', 'howitzer_m102_gun'),
           ('rocket_tripod', 'rocket_rail'), ('rocket_122', ''), ('rotor_hip', 'rotor_hip'), ('heli_hip', 'rotor_hip'), ('heli_hip', 'tailrotor_hip'), ('heli_hip_gun', 'rotor_hip'),
           ('heli_hip_gun', 'tailrotor_hip'), ('flag_pole', 'sandbag'), ('khmer_tower', 'stone_stairs')]


def expected(n_mounts):
    T = 'info_teleport_destination'; D = 'prop_dynamic'; I = 'info_target'; Sn = 'point_soundevent'; Fx = 'info_particle_system'
    e = {'mv_script': 'point_script', 'mv_hud': 'custom_hud_layout', 'mv_params': 'info_map_parameters', 'mv_ambience': Sn}
    for tg, K in (('ct', 3), ('t', 4)):
        for i in range(1, 17): e['mv_spawn_%s_%d' % (tg, i)] = T
        e['mv_kit_' + tg] = I; e['mv_board_' + tg] = I
        for i in range(1, 4):
            e['mv_heli_%s_%d' % (tg, i)] = D; e['mv_pad_%s_%d' % (tg, i)] = I; e['mv_wreck_%s_%d' % (tg, i)] = D
            for nm in ('eng', 'gun', 'gun2', 'rkt'): e['mv_heli_%s_%s_%d' % (nm, tg, i)] = Sn
            e['mv_heli_smoke_%s_%d' % (tg, i)] = Fx; e['mv_heli_dust_%s_%d' % (tg, i)] = Fx
        for i in range(1, K + 1):
            e['mv_gun_%s_%d' % (tg, i)] = D; e['mv_tube_%s_%d' % (tg, i)] = D; e['mv_rack_%s_%d' % (tg, i)] = I
            e['mv_boardseat_%s_%d' % (tg, i)] = T; e['mv_gun_snd_%s_%d' % (tg, i)] = Sn; e['mv_gun_fx_%s_%d' % (tg, i)] = Fx
    for i in range(1, 4): e['mv_rotor_t_%d' % i] = D; e['mv_tail_t_%d' % i] = D; e['mv_tunnel_%d' % i] = T
    for i in range(1, 5): e['mv_round_t_%d' % i] = D
    for l in 'abcde':
        e['mv_flag_' + l] = I; e['mv_flagpole_' + l] = D; e['mv_kit_' + l] = I; e['mv_flag_snd_' + l] = Sn
        for i in range(1, 9): e['mv_flagspawn_%s_%d' % (l, i)] = T
    for i in range(1, n_mounts + 1):
        e['mv_mount_%d' % i] = D; e['mv_mountseat_%d' % i] = T; e['mv_mount_snd_%d' % i] = Sn; e['mv_mountinfo_%d' % i] = I
    for i in range(1, 17):
        e['mv_boom_fx_%d' % i] = Fx; e['mv_dirt_fx_%d' % i] = Fx; e['mv_boom_snd_%d' % i] = Sn; e['mv_whistle_snd_%d' % i] = Sn
        e['mv_shake_%d' % i] = 'env_shake'; e['mv_rocket_%d' % i] = D
    for i in range(1, 25): e['mv_tracer_%d' % i] = D
    for i in range(1, 11): e['mv_marker_%d' % i] = D
    for i in range(1, 7): e['mv_smoke_fx_%d' % i] = Fx
    for i in range(1, 13): e['mv_pip_%d' % i] = D; e['mv_shell_%d' % i] = D
    return e


def main(path, plot=None, box=None):
    d = dmx.DMX.load(path)
    ents = G.entities(d)
    sites = json.load(open(os.path.join(OUT, 'world_sites.json'))) if os.path.exists(os.path.join(OUT, 'world_sites.json')) else {}
    fails = []
    rows = []
    for c in ents:
        ep = c.get('entity_properties')
        rows.append(dict(cls=ep.get('classname'), name=ep.get('targetname') or '', model=ep.get('model') or '', o=tuple(c.get('origin')), a=tuple(c.get('angles')),
                         s=tuple(c.get('scales') or (1, 1, 1)), solid=ep.get('solid') or '', msg=ep.get('message') or ''))
    # ---- 1 contract names
    names = Counter(r['name'] for r in rows if r['name'])
    cls_of = {r['name']: r['cls'] for r in rows if r['name']}
    nm = len([n for n in names if re.fullmatch(r'mv_mount_\d+', n)])
    exp = expected(nm)
    bad = [(n, c, names.get(n, 0), cls_of.get(n)) for n, c in exp.items() if names.get(n, 0) != 1 or cls_of.get(n) != c]
    for b in bad[:20]: print('CONTRACT  %s: want 1 x %s, have %d x %s' % b)
    if nm < 2 or nm != sites.get('mounts', nm): bad.append(('mv_mount count', nm))
    for r in rows:
        if r['name'].startswith('mv_mountinfo_') and not re.fullmatch(r'(m2|dshk|quad50):(t|ct|any)', r['msg']): bad.append((r['name'], r['msg']))
    ncache = len([n for n in names if n.startswith('mv_cache_')]); nnav = len([n for n in names if n.startswith('mv_nav_')])
    if ncache < 1: bad.append(('mv_cache_*', 0))
    if nnav < 8: bad.append(('mv_nav_*', nnav))
    print('1 contract: %d names expected, %d wrong; mounts %d, mv_cache_ %d, mv_nav_ %d' % (len(exp), len(bad), nm, ncache, nnav))
    if bad: fails.append('contract')
    # ---- 2 props on a surface
    exc = set()
    for e in sites.get('exceptions', []):          # float32 in the vmap: match on a 2-u grid, both neighbours
        for dx in (0, 1):
            for dy in (0, 1):
                for dz_ in (0, 1): exc.add((e[0], int(e[1] // 2) + dx, int(e[2] // 2) + dy, int(e[3] // 2) + dz_))
    surf = sites.get('surfaces', [])
    tun = sites.get('tunnel'); tp = np.array(tun['samples']) if tun else np.zeros((0, 2)); tf = np.array(tun['floor']) if tun else np.zeros(0)
    P = [r for r in rows if r['cls'] == 'prop_static' or (r['cls'] == 'prop_dynamic' and re.match(r'mv_(gun|heli|flagpole)_', r['name']) and 'heli_' not in r['name'][3:7] or
                                                         (r['cls'] == 'prop_dynamic' and re.fullmatch(r'mv_heli_(t|ct)_\d', r['name'])))]
    X = np.array([r['o'][0] for r in P]); Y = np.array([r['o'][1] for r in P]); Zp = np.array([r['o'][2] for r in P])
    Zg = L.height(X, Y)
    off = []
    for k, r in enumerate(P):
        dz = Zp[k] - Zg[k]
        if -8.0 <= dz <= 6.0: continue
        if (r['model'], int((r['o'][0] + 1) // 2), int((r['o'][1] + 1) // 2), int((r['o'][2] + 1) // 2)) in exc: continue
        cands = [zt for (x0, y0, x1, y1, zt) in surf if x0 - 1 <= r['o'][0] <= x1 + 1 and y0 - 1 <= r['o'][1] <= y1 + 1]
        if len(tp):
            dd = np.hypot(tp[:, 0] - r['o'][0], tp[:, 1] - r['o'][1]); i = int(dd.argmin())
            if dd[i] < 70: cands.append(tf[i])
        if any(-8.0 <= Zp[k] - zc <= 6.0 for zc in cands): continue
        off.append((round(float(dz), 1), r['model'].split('/')[-1], [round(v) for v in r['o']], r['name']))
    off.sort(key=lambda t: -abs(t[0]))
    print('2 ground: %d props checked, %d off the ground without being listed' % (len(P), len(off)))
    for o in off[:15]: print('   ', o)
    if off: fails.append('ground')
    # ---- 3 overlap audit
    table, built = S.bounds_table(os.path.join(OUT, 'props.json'))
    PLc = placer.Placer(bounds=placer.Bounds(props_json=os.path.join(OUT, 'props.json'), out=os.path.join(OUT, 'addon'), prefix='mv', table=table))
    for r in rows:
        if not r['model'].endswith('.vmdl') or r['cls'] not in ('prop_static', 'prop_dynamic') or r['o'][2] < L.LOBBY_Z + 1000: continue
        if r['solid'] == '0' and r['cls'] == 'prop_static': continue
        m = r['model']; nm_ = m.split('/')[-1][:-5]
        tr = S.TRUNK.get(m, S.TRUNK_MV.get(nm_, 344.0 if nm_ == 'rotor_hip' else None))       # trunks and the rotor disc are round
        if tr is not None:
            lo, hi = PLc.bounds(m)
            f = dict(c=(r['o'][0], r['o'][1]), h=(tr * r['s'][0], tr * r['s'][0]), a=0.0, z=(r['o'][2], r['o'][2] + hi[2] * r['s'][2]), model=m)
        else:
            f = PLc.footprint(m, r['o'][0], r['o'][1], r['o'][2], r['a'][1], r['s'])
            f['z'] = (f['z'][0] + 1.0, f['z'][1] - 1.0)
        f['name'] = r['name']
        PLc.add(f)
    short = lambda m: m.split('/')[-1][:-5]
    def allowed(a, b):
        for p, q in OK_PAIR:
            if (p in a and q in b) or (p in b and q in a): return True
        return False
    pairs = [(i, j) for i, j in PLc.audit() if not allowed(short(PLc.items[i]['model']), short(PLc.items[j]['model']))]
    cnt = Counter(tuple(sorted((short(PLc.items[i]['model']), short(PLc.items[j]['model'])))) for i, j in pairs)
    json.dump([dict(a=PLc.items[i]['model'], b=PLc.items[j]['model'], ca=[round(v) for v in PLc.items[i]['c']], cb=[round(v) for v in PLc.items[j]['c']]) for i, j in pairs],
              open(os.path.join(OUT, 'overlaps.json'), 'w'), indent=0)
    print('3 overlaps: %d solid props, %d interpenetrating pairs -> out/overlaps.json' % (len(PLc.items), len(pairs)))
    for (a, b), c_ in cnt.most_common(12): print('    %3d  %s + %s' % (c_, a, b))
    if pairs: fails.append('overlaps')
    # ---- 4 spawn / seat points
    sp = [r for r in rows if r['cls'] == 'info_teleport_destination' and r['name'].startswith('mv_')]
    bad_sp = []
    for r in sp:
        x, y, z = r['o']; feet = z - 8.0
        probe = dict(c=(x, y), h=(16.0, 16.0), a=0.0, z=(feet + 2.0, feet + 80.0), model='probe')
        hit = PLc.hits(probe)
        zs = [float(L.height(np.array([x]), np.array([y]))[0])] + [zt for (x0, y0, x1, y1, zt) in surf if x0 <= x <= x1 and y0 <= y <= y1]
        if len(tp) and r['name'].startswith('mv_tunnel'):
            zs.append(float(tf[int(np.hypot(tp[:, 0] - x, tp[:, 1] - y).argmin())]))
        on = any(-3.0 <= feet - zc <= 14.0 for zc in zs)
        if hit is not None: bad_sp.append((r['name'], 'inside ' + short(hit['model'])))
        elif not on: bad_sp.append((r['name'], 'feet %.0f, surfaces %s' % (feet, [round(v) for v in zs])))
    print('4 spawns: %d points, %d bad' % (len(sp), len(bad_sp)))
    for b in bad_sp[:15]: print('   ', b)
    if bad_sp: fails.append('spawns')
    # ---- 5 flags reachable from a road
    worst = {}
    for l, name, c in L.FLAGS:
        if l == 'b':
            g = L.gz(c[0], c[1] - L.BRIDGE_LEN / 2 - L.BRIDGE_RAMP); worst[l] = math.degrees(math.atan((L.BRIDGE_DECK_Z - g) / L.BRIDGE_RAMP)); continue
        best = None
        for hw, pts in L.ROADS:
            Pp = np.array(pts, float)
            for a, b in zip(Pp[:-1], Pp[1:]):
                t = np.clip(((c[0] - a[0]) * (b[0] - a[0]) + (c[1] - a[1]) * (b[1] - a[1])) / max(float((b - a) @ (b - a)), 1e-9), 0, 1)
                q = a + (b - a) * t; dq = math.hypot(q[0] - c[0], q[1] - c[1])
                if best is None or dq < best[0]: best = (dq, q)
        n = max(2, int(best[0] / 16)); xs = np.linspace(best[1][0], c[0], n + 1); ys = np.linspace(best[1][1], c[1], n + 1)
        z = L.height(xs, ys); step = max(best[0] / n, 1e-6)
        zz = np.convolve(np.pad(z, 1, mode='edge'), np.ones(3) / 3, mode='valid')
        worst[l] = float(np.degrees(np.arctan(np.abs(np.diff(zz)) / step)).max()) if n > 1 else 0.0
    print('5 flags: steepest slope from the nearest road: ' + ', '.join('%s %.0f deg' % (l.upper(), v) for l, v in worst.items()))
    if max(worst.values()) >= 40.0: fails.append('flags')
    # ---- 6 counts
    cc = Counter(r['cls'] for r in rows)
    print('6 classes: ' + ', '.join('%s %d' % kv for kv in cc.most_common()))
    ps = cc.get('prop_static', 0)
    print('  prop_static %d (target < 9000)%s' % (ps, '' if ps < 9000 else '  TOO MANY'))
    if ps >= 9000: fails.append('prop count')
    if plot: draw(rows, PLc, plot, box)
    print('RESULT: ' + ('clean' if not fails else 'FAILED: ' + ', '.join(fails)))
    return 1 if fails else 0


def draw(rows, PLc, dst, box=None):
    from PIL import Image, ImageDraw
    x0, y0, x1, y1 = box or (-L.MAP_X - 300, -L.MAP_Y - 300, L.MAP_X + 300, L.MAP_Y + 300)
    Wd = 1500; sc = Wd / (x1 - x0); Hd = int((y1 - y0) * sc)
    xs = np.linspace(x0, x1, Wd // 2); ys = np.linspace(y1, y0, Hd // 2)
    X, Y = np.meshgrid(xs, ys)
    Z = L.height(X, Y)
    gy_, gx_ = np.gradient(Z, (y1 - y0) / (Hd // 2), (x1 - x0) / (Wd // 2))
    shade = np.clip(0.75 + 0.9 * (gx_ * 0.5 + gy_ * 0.5), 0.35, 1.2)
    lo, hi = np.percentile(Z, 2), np.percentile(Z, 98)
    t = np.clip((Z - lo) / max(hi - lo, 1), 0, 1)
    rgb = np.stack([70 + 90 * t, 96 + 70 * t, 56 + 50 * t], -1) * shade[..., None]
    rgb[Z < L.WATER_Z] = (60, 96, 130)
    rd, hw = L.road_dist(X, Y); rgb[rd < hw] = rgb[rd < hw] * 0.5 + np.array([150, 120, 80]) * 0.5
    img = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).resize((Wd, Hd))
    dr = ImageDraw.Draw(img)
    px = lambda x, y: ((x - x0) * sc, (y1 - y) * sc)
    for (sx0, sy0, sx1, sy1, zt) in json.load(open(os.path.join(OUT, 'world_sites.json'))).get('surfaces', []):
        dr.rectangle([px(sx0, sy1), px(sx1, sy0)], outline=(200, 200, 200), fill=(128, 128, 120))
    big = box is not None
    for f in PLc.items:
        m = f['model'].split('/')[-1][:-5]
        if not (x0 <= f['c'][0] <= x1 and y0 <= f['c'][1] <= y1): continue
        c, s = math.cos(f['a']), math.sin(f['a']); hx, hy = f['h']
        poly = [px(f['c'][0] + c * a * hx - s * b * hy, f['c'][1] + s * a * hx + c * b * hy) for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        tree = any(k in m for k in ('banyan', 'palm', 'rubber', 'dead_tree', 'bamboo_clump'))
        col = (30, 90, 30) if tree else (230, 200, 120) if 'sandbag' in m else (255, 90, 60) if f.get('name') else (240, 240, 240)
        dr.polygon(poly, outline=col)
        if big and not tree and 'sandbag' not in m and max(hx, hy) * sc > 9: dr.text(poly[0], m[:14], fill=(255, 255, 0))
    for r in rows:
        if r['cls'] == 'info_teleport_destination' and x0 <= r['o'][0] <= x1 and y0 <= r['o'][1] <= y1:
            p = px(r['o'][0], r['o'][1]); dr.ellipse((p[0] - 2, p[1] - 2, p[0] + 2, p[1] + 2), fill=(80, 220, 255))
        if r['cls'] == 'prop_static' and r['solid'] == '0' and big and x0 <= r['o'][0] <= x1 and y0 <= r['o'][1] <= y1:
            p = px(r['o'][0], r['o'][1]); dr.point(p, fill=(120, 230, 120))
    for l, name, c in L.FLAGS:
        p = px(*c); dr.text((p[0] + 6, p[1] - 6), l.upper(), fill=(255, 255, 255))
    img.save(dst); print('plot ->', dst)


if __name__ == '__main__':
    if len(sys.argv) < 2: print(__doc__); sys.exit(2)
    plot = box = None
    if '--plot' in sys.argv:
        i = sys.argv.index('--plot'); plot = sys.argv[i + 1]
        if len(sys.argv) > i + 2: box = [float(v) for v in sys.argv[i + 2].split(',')]
    sys.exit(main(sys.argv[1], plot, box))
