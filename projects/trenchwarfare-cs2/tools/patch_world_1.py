"""World patch 1 (remaster step 5): the auto-fixable findings of docs/REVIEW_WORLD_1.md as one guarded delta patch on the user's vmap.
Reads the input map (never writes it); writes the patched copy, the guard's target list and the deploy list under out/.

usage: python tools/patch_world_1.py [--in V] [--out V] [--stage DIR] [--user-h1 unlock|remove] [--user-m2] [--user-w5] [--render]
  defaults: --in <content addon>/maps/mg_trenchwarfare.vmap, --out out/mg_trenchwarfare_patched.vmap, --stage out/addon
  then:     python tools/patch_guard.py <in> <out> out/step5/patch_world_1.targets.json

Every target is matched on its element id (mapdigest "i") + class + model + origin within 2 u (meshes: id + parent class + bounds within
2 u). Any mismatch stops the patch before anything is written: ids hold only until the next Hammer save, so after one the table below
has to be re-read from the digest, never guessed.

Default (ours: tw_gen / tw_nav / the woodsopen vis group, plus the model key of the user's two undergroundopen blockers):
  H4  10 mortar tubes prop_static -> prop_dynamic mortar_<tg>_K on the animated *_dyn twins (tools/dyn_models.py: "idle" + "fire")
  H2  the 4 unlock blockers -> the dynamic-archetype twins (model key only; the undergroundopen pair is ungrouped, i.e. the user's,
      and gets nothing but the model key, so the geometry they placed stays exactly where it is)
  H3  the 4 woods WALKABLESEED meshes 100 u inward (centre |x| 1110, inside the clearing fence) and down so the box reaches 8 u under
      the lowest ground of its new footprint
  M3  tl_barrel 1727 +10 u along the bay (and the tins 1728 beside it, so they stay clear of it), tl_barrel 2811 -20.5 u: the minimum
      that keeps a 32 x 32 player box on trench_t_1 / trench_ct_13 2 u clear of the barrel's hull
  L5  three no man's land water sheets lowered 0.5-1.9 u so each overlapping pair is 2 u apart (no z-fight)
Opt-in, the user's objects (off by default, pending their answer):
  --user-h1 unlock  the 24 tl_bench in the two sap mouths -> prop_dynamic undergroundopen on tl_bench_dyn: the barricade stands until
                    the unlock, then goes with the planks (the script's effects() runs once per removed entity: 26 instead of 2)
  --user-h1 remove  the 24 benches are deleted
  --user-m2         deletes the duplicate info_map_parameters id 7 (ungrouped, buying 0; tw_params stays)
  --user-w5         deletes tl_bench 72, the exact copy of bench 71 1 u above it (same model, angles, scales and keys: z-fight;
                    REVIEW_WORLD_2 W5). Every other bench stays.
Decided 12 Nov 2026 (the user): the 24 sap benches are the user's seam bridges (steps from the trench floor down to the tunnel floor,
and the cover over the mouth); players get through them crouched. Do NOT use --user-h1 on this map: it would delete the bridges with the
unlock. tools/deploy_tw.py passes --user-m2 --user-w5 by default.
Left alone, with the reason, in docs/REVIEW_WORLD_1.md "Step 5 results".
--render: zoomed top-down renders of the changed areas (create/check_play.py) into out/review/after_*.png.
"""
import argparse, json, math, os, sys, time, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
REPO = os.path.normpath(os.path.join(PROJ, '..', '..'))
sys.path[:] = [os.path.join(REPO, 'tools')] + [p for p in sys.path if os.path.normcase(os.path.abspath(p or '.')) != os.path.normcase(HERE)]
import vmapedit as V      # noqa: E402
import dmx                # noqa: E402
import safepath           # noqa: E402

ADDON = r'C:\source1\links\content_addons\mg_trenchwarfare'
OUT = os.path.join(PROJ, 'out')
TOL = 2.0

MW, M58 = 'models/tw/minenwerfer/minenwerfer.vmdl', 'models/tw/ext/mortar_58mm/mortar_58mm.vmdl'
RPB, RPB128 = 'models/tw/revet_planks_broken/revet_planks_broken.vmdl', 'models/tw/revet_planks_broken_128/revet_planks_broken_128.vmdl'
BENCH = 'models/tw/tl_bench/tl_bench.vmdl'
dyn = lambda m: m[:-5] + '_dyn.vmdl'

# (id, class, model, origin)  K = 1..5 from y -1600 .. 1600 (mortarpit_<tg>_K stands on the tube)
MORTARS = [(3651, MW, (-3200, -1600, -25.8), 't', 1), (3718, MW, (-3200, -800, -29.0), 't', 2), (3786, MW, (-3200, 0, -28.6), 't', 3),
           (3853, MW, (-3200, 800, -14.7), 't', 4), (3921, MW, (-3200, 1600, -28.0), 't', 5),
           (3989, M58, (3200, -1600, -13.2), 'ct', 1), (4056, M58, (3200, -800, -14.4), 'ct', 2), (4124, M58, (3200, 0, -23.4), 'ct', 3),
           (4191, M58, (3200, 800, -23.6), 'ct', 4), (4258, M58, (3200, 1600, -19.6), 'ct', 5)]
BLOCKERS = [(7979, RPB, (-2144, -2808, -96), 'undergroundopen', 'user'), (7980, RPB, (2145.5, -2806, -112), 'undergroundopen', 'user'),
            (7982, RPB128, (1784, 2792, -72), 'woodsopen', 'ours'), (7983, RPB128, (-1800, 2792, -88), 'woodsopen', 'ours')]
# (id, model, origin, (dx, dy, dz), why)
MOVES = [(1727, 'models/tw/tl_barrel/tl_barrel.vmdl', (-1660.85, -2733.02, -68.24), (0, 10.0, 0), 'M3 barrel off trench_t_1 (needs 9.7)'),
         (1728, 'models/tw/tl_tins/tl_tins.vmdl', (-1664.5, -2708.3, -68.2), (0, 10.0, 0), 'M3 tins moved with the barrel'),
         (2811, 'models/tw/tl_barrel/tl_barrel.vmdl', (1660.8, 1845.5, -73.7), (0, -20.5, 0), 'M3 barrel off trench_ct_13 (needs 20.1)')]
# mesh nodes: (mesh id, parent class, bounds lo+hi, (dx, dy, dz), why)
MESHES = [(8377, 'func_nav_markup', (-1226, 3684, -8, -1194, 3716, 26), (100, 0, -14), 'H3 woods seed T 1'),
          (8355, 'func_nav_markup', (-1226, 4134, 3, -1194, 4166, 37), (100, 0, -13), 'H3 woods seed T 2'),
          (8311, 'func_nav_markup', (1194, 3684, 5, 1226, 3716, 39), (-100, 0, -15), 'H3 woods seed CT 1'),
          (8289, 'func_nav_markup', (1194, 4134, -3, 1226, 4166, 31), (-100, 0, -14), 'H3 woods seed CT 2'),
          (3450, 'worldspawn', (869.31, -2004.28, -104.08, 1082.88, -1770.82, -74.08), (0, 0, -0.54), 'L5 z-fight with sheet 3502 (top -72.62)'),
          (3459, 'worldspawn', (1178.33, -1132.84, -79.12, 1375.48, -908.71, -49.12), (0, 0, -1.92), 'L5 z-fight with sheet 3473 (top -49.04)'),
          (3466, 'worldspawn', (1122.7, -3461.87, -86.79, 1310.33, -3299.81, -56.79), (0, 0, -0.59), 'L5 z-fight with sheet 3491 (top -55.38)')]
BENCHES = [(70, (2142.8, -2834, -17)), (71, (2164, -2834, -15)), (72, (2164, -2834, -14)), (73, (2142.8, -2834, -14)), (74, (2164, -2834, -14)),
           (75, (2142.8, -2834, -14)), (76, (-2156, -2834, -6)), (77, (-2134.8, -2834, -6)), (78, (-2134.8, -2834, 0)), (79, (-2156, -2834, 0)),
           (80, (-2156, -2834, 0)), (81, (-2134.8, -2834, 0)), (7933, (2136, -2816, -94)), (7934, (2136, -2814, -94)), (7935, (2176, -2814, -94)),
           (7936, (2170, -2816, -94)), (7937, (2176, -2818, -98)), (7938, (2136, -2818, -98)), (7939, (-2162, -2816, -82)), (7940, (-2128, -2816, -82)),
           (7941, (-2122, -2814, -82)), (7942, (-2162, -2814, -82)), (7943, (-2162, -2818, -86)), (7944, (-2122, -2818, -86))]
PARAMS_DUP = (7, (512, 328, 32))
BENCH_DUP = (72, (2164, -2834, -14), 71, (2164, -2834, -15))      # (drop, origin, the copy that stays, its origin): W5
TEMPLATE_DYN = 7979      # the user's own Hammer-made prop_dynamic: Hammer's full prop_dynamic key set
STATIC_ONLY = ('bakelighting', 'lodlevel', 'baketoworld', 'emissive', 'emissive_lighting_boost', 'lightmapscalebias', 'bakelightdoublesided',
               'visoccluder', 'disablemerging', 'collision_override', 'materialoverride')


class Mismatch(Exception): pass


def near(a, b, tol=TOL): return all(abs(float(x) - float(y)) <= tol for x, y in zip(a, b))


def node_parent(m):
    return {n: p for n, p in m.walk()}


def expect_entity(m, i, cls, model, origin, vg=None):
    if i >= len(m.E) or m.type(i) != b'CMapEntity': raise Mismatch('id %d is not an entity' % i)
    c, mm, o = m.cls(i), m.P(i, 'model', '') or '', m.origin(i)
    if c != cls or (model is not None and mm != model) or not near(o, origin):
        raise Mismatch('id %d: want %s %s at %s, found %s %s at %s' % (i, cls, model, origin, c, mm, [round(v, 2) for v in o]))
    if vg is not None:
        g = (m.g(i, b'customVisGroup') or b'').decode()
        if g != vg: raise Mismatch('id %d: want vis group %r, found %r' % (i, vg, g))


def set_props(m, i, pairs):
    """replace the whole keyvalue list of entity i (same element, so the node keeps its id and nodeID)"""
    m.props(i)['attrs'] = [[k.encode(), dmx.T_STR, str(v).encode()] for k, v in pairs]


def dyn_keys(m, i, model, name, anim):
    """prop_dynamic keys from the template entity, with this entity's look carried over from its prop_static keys"""
    old = {a[0].decode(): a[2].decode() for a in m.props(i)['attrs']}
    keys = [(a[0].decode(), a[2].decode()) for a in m.props(TEMPLATE_DYN)['attrs']]
    want = dict(classname='prop_dynamic', model=model, targetname=name, solid=old.get('solid', '6'), rendercolor=old.get('rendercolor', '255 255 255'),
                skin=old.get('skin', 'default'), disableshadows=old.get('disableshadows', '0'), rendertocubemaps=old.get('rendertocubemaps', '0'),
                lightingorigin=old.get('lightingorigin', ''), steamaudio_geometry_mode=old.get('steamaudio_geometry_mode', '0'))
    if anim:
        want.update(use_animgraph='0', StartingAnim='idle', StartingAnimationLoopMode='ANIM_LOOP_MODE_LOOPING', IdleAnim='idle',
                    IdleAnimationLoopMode='ANIM_LOOP_MODE_LOOPING')
    out = [(k, want.pop(k, v)) for k, v in keys]
    out = [kv for kv in out if kv[0] != 'classname']
    return [('classname', 'prop_dynamic')] + out + sorted(want.items())


def main(argv=None):
    ap = argparse.ArgumentParser(description='world patch 1 (step 5)')
    ap.add_argument('--in', dest='inp', default=os.path.join(ADDON, 'maps', 'mg_trenchwarfare.vmap'))
    ap.add_argument('--out', default=os.path.join(OUT, 'mg_trenchwarfare_patched.vmap'))
    ap.add_argument('--stage', default=os.path.join(OUT, 'addon'))
    ap.add_argument('--user-h1', choices=('unlock', 'remove'))
    ap.add_argument('--user-m2', action='store_true')
    ap.add_argument('--user-w5', action='store_true', help='drop tl_bench 72, the exact duplicate of 71 (REVIEW_WORLD_2 W5)')
    ap.add_argument('--render', action='store_true')
    ap.add_argument('--targets', default=None, help='where the guard target list goes (default out/step5/patch_world_1.targets.json)')
    a = ap.parse_args(argv)
    outp = os.path.abspath(a.out)
    if not safepath.inside(OUT, outp) or os.path.normcase(outp) == os.path.normcase(os.path.abspath(a.inp)):
        sys.exit('patch_world_1: --out must be under %s and not the input' % OUT)
    t0 = time.time()
    raw = open(a.inp, 'rb').read()
    m = V.Map(a.inp, data=raw)
    V.random.seed('patch_world_1:%08x:%d' % (zlib.crc32(raw) & 0xffffffff, len(raw)))   # new guids / referenceIDs / randomSeeds (vmapedit's global random) follow from the input: same input, same bytes
    m.path = a.inp
    nid = lambda i: m.g(i, b'nodeID')
    T = dict(input=os.path.abspath(a.inp), input_bytes=len(raw), input_crc32='%08x' % (zlib.crc32(raw) & 0xffffffff), modify={}, remove={}, add=[],
             prefix=['map_asset_references', 'map_subasset_reference_types', 'map_subasset_reference_names', 'map_subasset_reference_counts'], root=False)
    def declare(i, fields, why): T['modify'][str(nid(i))] = dict(i=i, fields=fields, why=why)
    log = []
    try:
        # ---- verify every target first: nothing is changed unless all match
        for i, mdl, o, tg, k in MORTARS: expect_entity(m, i, 'prop_static', mdl, o, 'tw_gen')
        pits = {m.name(e): m.origin(e) for e in m.entities() if m.name(e).startswith('mortarpit_')}
        for i, mdl, o, tg, k in MORTARS:
            p = pits.get('mortarpit_%s_%d' % (tg, k))
            if p is None or math.hypot(p[0] - o[0], p[1] - o[1]) > 40: raise Mismatch('mortarpit_%s_%d is not on tube %d' % (tg, k, i))
            if any(m.name(e) == 'mortar_%s_%d' % (tg, k) for e in m.entities()): raise Mismatch('mortar_%s_%d already exists' % (tg, k))
        for i, mdl, o, name, own in BLOCKERS:
            expect_entity(m, i, 'prop_dynamic', mdl, o)
            if m.name(i) != name: raise Mismatch('id %d: want targetname %s, found %r' % (i, name, m.name(i)))
        for i, mdl, o, d, why in MOVES: expect_entity(m, i, 'prop_static', mdl, o, 'tw_gen')
        par = node_parent(m)
        for i, pcls, b, d, why in MESHES:
            if i >= len(m.E) or m.type(i) != b'CMapMesh': raise Mismatch('id %d is not a mesh' % i)
            pc = m.cls(par[i]) if m.type(par[i]) == b'CMapEntity' else 'worldspawn'
            bb = m.bounds(i)
            if pc != pcls or not near(bb[0] + bb[1], b): raise Mismatch('mesh %d: want %s %s, found %s %s' % (i, pcls, b, pc, [round(v, 2) for v in bb[0] + bb[1]]))
            if list(m.g(i, b'origin')) != [0.0, 0.0, 0.0]: raise Mismatch('mesh %d: origin not 0 0 0' % i)
        if a.user_h1:
            for i, o in BENCHES: expect_entity(m, i, 'prop_static', BENCH, o, 'tw_user')
        if a.user_m2:
            expect_entity(m, PARAMS_DUP[0], 'info_map_parameters', None, PARAMS_DUP[1], '')
            if not [e for e in m.entities() if m.name(e) == 'tw_params' and m.cls(e) == 'info_map_parameters']: raise Mismatch('tw_params missing')
        if a.user_w5:
            d, do, k, ko = BENCH_DUP
            expect_entity(m, d, 'prop_static', BENCH, do, 'tw_user'); expect_entity(m, k, 'prop_static', BENCH, ko, 'tw_user')
            kv = lambda i: sorted((x[0], x[2]) for x in m.props(i)['attrs'])
            if (list(m.g(d, b'angles')) != list(m.g(k, b'angles')) or list(m.g(d, b'scales') or []) != list(m.g(k, b'scales') or [])
                    or kv(d) != kv(k) or abs(m.origin(d)[2] - m.origin(k)[2]) > 1.01 or m.origin(d)[:2] != m.origin(k)[:2]):
                raise Mismatch('bench %d is not an exact copy of %d (angles / scales / keys / origin)' % (d, k))
    except Mismatch as ex:
        sys.exit('patch_world_1: TARGET MISMATCH, nothing written: %s' % ex)
    # ---- the staged models must exist
    need = [dyn(MW), dyn(M58), dyn(RPB), dyn(RPB128)] + ([dyn(BENCH)] if a.user_h1 == 'unlock' else [])
    miss = [x for x in need if not os.path.isfile(os.path.join(a.stage, x.replace('/', os.sep)))]
    if miss: sys.exit('patch_world_1: staged models missing (run tools/dyn_models.py first): %s' % miss)

    # ---- apply
    for i, mdl, o, tg, k in MORTARS:
        set_props(m, i, dyn_keys(m, i, dyn(mdl), 'mortar_%s_%d' % (tg, k), anim=True))
        declare(i, ['class', 'kv:*'], 'H4 mortar_%s_%d: prop_dynamic on the animated twin' % (tg, k)); log.append('H4 %d -> mortar_%s_%d' % (i, tg, k))
    for i, mdl, o, name, own in BLOCKERS:
        m.setp(i, 'model', dyn(mdl)); declare(i, ['kv:model'], 'H2 %s blocker (%s) -> dynamic archetype twin' % (name, own))
        log.append('H2 %d %s model -> %s' % (i, name, dyn(mdl)))
    for i, mdl, o, d, why in MOVES:
        oo = m.origin(i); dmx.set_(m.E[i], b'origin', dmx.T_V3, [oo[0] + d[0], oo[1] + d[1], oo[2] + d[2]])
        declare(i, ['origin'], why); log.append('%s: %d by %s' % (why, i, d))
    for i, pcls, b, d, why in MESHES:
        dmx.set_(m.E[i], b'origin', dmx.T_V3, [float(d[0]), float(d[1]), float(d[2])])
        declare(i, ['origin'], why); bb = m.bounds(i); log.append('%s: mesh %d now %s' % (why, i, [round(v, 1) for v in bb[0] + bb[1]]))
    removed = []
    if a.user_h1 == 'unlock':
        for i, o in BENCHES:
            set_props(m, i, dyn_keys(m, i, dyn(BENCH), 'undergroundopen', anim=False))
            declare(i, ['class', 'kv:*'], 'H1 (opt-in) sap bench -> prop_dynamic undergroundopen')
        log.append('H1 opt-in: 24 benches -> prop_dynamic undergroundopen')
    elif a.user_h1 == 'remove':
        removed += [i for i, o in BENCHES]; log.append('H1 opt-in: 24 benches deleted')
    if a.user_m2:
        removed.append(PARAMS_DUP[0]); log.append('M2 opt-in: info_map_parameters 7 deleted')
    if a.user_w5:
        removed.append(BENCH_DUP[0]); log.append('W5 opt-in: tl_bench 72 deleted (exact copy of 71, 1 u above it)')
    for i in removed:
        T['remove'][str(nid(i))] = dict(i=i, why='opt-in removal')
        if not m.remove_node(i): sys.exit('patch_world_1: could not remove %d' % i)
    if removed: log.append('pruned %d unreachable elements' % m.prune())

    # ---- prefix: asset references and per-class entity counts
    ents = m.entities()
    used = {m.P(e, 'model', '') for e in ents}
    counts = {}
    for e in ents: counts[m.cls(e)] = counts.get(m.cls(e), 0) + 1
    for attrs in m.doc.prefix:
        pre = {x[0]: x for x in attrs}
        if b'map_asset_references' in pre:
            ar = pre[b'map_asset_references'][2]
            for x in need:
                if x.encode() not in ar: ar.append(x.encode())
            for x in (MW, M58):
                if x not in used and x.encode() in ar: ar.remove(x.encode())
        if b'map_subasset_reference_names' in pre:
            names = sorted(counts)
            pre[b'map_subasset_reference_types'][2] = [b'entity'] * len(names)
            pre[b'map_subasset_reference_names'][2] = [n.encode() for n in names]
            pre[b'map_subasset_reference_counts'][2] = [counts[n] for n in names]
    n = m.save(outp)
    for l in log: print('  ' + l)
    os.makedirs(os.path.join(OUT, 'step5'), exist_ok=True)
    tp = a.targets or os.path.join(OUT, 'step5', 'patch_world_1.targets.json')
    T['output'] = outp; T['flags'] = dict(user_h1=a.user_h1, user_m2=a.user_m2, user_w5=a.user_w5)
    json.dump(T, open(tp, 'w'), indent=1)
    # ---- deploy list: the map and every staged file the patched map's models need
    staged = [l.strip() for l in open(os.path.join(OUT, 'step5_models.txt')) if l.strip()]
    dep = ['maps/mg_trenchwarfare.vmap   <- %s' % os.path.relpath(outp, PROJ)]
    for f in staged:
        fd, fb = f.rsplit('/', 1)
        for x in need:
            xd, xb = x.rsplit('/', 1)
            if fd in (xd, xd + '/anims') and fb.startswith(xb[:-len('_dyn.vmdl')]):
                dep.append(f); break
    open(os.path.join(OUT, 'step5', 'deploy_files%s.txt' % ('_optin' if (a.user_h1 or a.user_m2 or a.user_w5) else '')), 'w', newline='\n').write(
        '# remaster step 5: files to copy into content\\csgo_addons\\mg_trenchwarfare\\ (addon-relative), from out/addon unless noted.\n'
        '# Back up the vmap first, close Hammer, then compile the new models (they are not compiled yet).\n' + '\n'.join(dep) + '\n')
    print('patched map: %s (%d bytes); targets %s; %d changes, %d removals; %.1f s' % (outp, n, tp, len(T['modify']), len(T['remove']), time.time() - t0))
    if a.render: render_after(outp, a.stage, 'after_optin_' if (a.user_h1 or a.user_m2 or a.user_w5) else 'after_')


# ---------------------------------------------------------------- after-renders (the review's views, same tool)
VIEWS = [('after_01_sap_t.png', (-2350, -3000, -1950, -2650), [(-2145, -2825, 'sap T')]),
         ('after_02_sap_ct.png', (1950, -3000, 2350, -2650), [(2150, -2825, 'sap CT')]),
         ('after_03_woods_seeds_t.png', (-1500, 3500, -900, 4350), [(-1110, 3700, 'seed'), (-1110, 4150, 'seed')]),
         ('after_04_woods_seeds_ct.png', (900, 3500, 1500, 4350), [(1110, 3700, 'seed'), (1110, 4150, 'seed')]),
         ('after_06_post_t_1_barrel.png', (-1760, -2860, -1540, -2640), [(-1649, -2752, 'trench_t_1')]),
         ('after_07_post_ct_13_barrel.png', (1540, 1750, 1760, 1970), [(1649, 1856, 'trench_ct_13')]),
         ('after_08_pit_t_2.png', (-3450, -1000, -2950, -600), [(-3200, -800, 'mortar_t_2')]),
         ('after_08b_pit_ct_3.png', (2950, -200, 3450, 200), [(3200, 0, 'mortar_ct_3')]),
         ('after_11_nml_zfight.png', (700, -2150, 1450, -750), [(920, -1944, 'zf'), (1264, -928, 'zf')]),
         ('after_11b_nml_zfight_s.png', (950, -3550, 1400, -3200), [(1136, -3368, 'zf')])]


def render_after(vmap, stage, prefix='after_'):
    sys.path.insert(0, HERE)
    import check_play as TP
    TP.A.model_roots = [os.path.abspath(stage)] + list(TP.A.model_roots)
    TP.A.out_json = os.path.join(OUT, 'review', 'check_play_render_tmp.json')
    ctx = TP.CP.run(vmap, TP.A, only={'1'})
    for name, box, marks in VIEWS:
        TP.CP.render(ctx, os.path.join(OUT, 'review', prefix + name[len('after_'):]), box, marks)


if __name__ == '__main__':
    main()
