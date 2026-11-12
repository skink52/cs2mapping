"""mg_trenchwarfare world checks on the user's vmap (adapted from projects/monsoon-cs2/tools/check_world.py). Reads only.

usage: python tools/check_world.py [map.vmap] [--json out.json] [--verbose]      (map default: the content addon's vmap)

1 script names: every name the script looks up (src/mg_trenchwarfare.js loadPoints / fire targets) is present with the class it needs,
  counts per family; mortar_<tg>_K (the fire animation target) must be a prop_dynamic whose model has a "fire" sequence
2 singletons: one info_map_parameters, light_environment, env_sky, skybox_reference, team_select, end_of_match, team intros, and one
  point_script / custom_hud_layout per name
3 bounds: every entity inside the sky shell (toolsskybox mesh) or the lobby room, except the script's pools parked under the lobby
4 overlaps: solid props whose physics hulls' boxes interpenetrate (by-design pairs in OK_PAIR are skipped) -> top model pairs
5 wiring: every output target resolves to a name in the map (the I/O graph)
6 counts per class; prop_static < 9000
7 models: every entity model exists: ours as .vmdl in the content addon and compiled .vmdl_c in the game addon (a .vmdl_c older than its
  .vmdl is listed as stale); stock ones as <path>_c in the game's pak01 VPK
7b archetypes: a prop_dynamic of ours must name a .vmdl with model_archetype "" or "animated_model" (a static_prop_model on a
  prop_dynamic is deleted by the map compile)
Each finding carries the entity's element id (mapdigest "i"), position and vis group (tw_user / ungrouped = the user's own objects).
Exit code 1 when a check fails.
"""
import os, sys, json, math, re, time, pickle
from collections import Counter, defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
REPO = os.path.normpath(os.path.join(PROJ, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'tools'))           # vmapedit
sys.path.insert(1, os.path.join(REPO, 'create'))          # check_play (vmdl / SMD readers), vpkdir
import vmapedit as V
import importlib.util
_spec = importlib.util.spec_from_file_location('check_play_neutral', os.path.join(REPO, 'create', 'check_play.py'))
CP = importlib.util.module_from_spec(_spec); sys.modules['check_play_neutral'] = CP; _spec.loader.exec_module(CP)   # create/check_play.py (this file shares its name)

LINKS = os.environ.get('TW_LINKS', r'C:\source1\links')
CONTENT = os.environ.get('TW_CONTENT', os.path.join(LINKS, 'content_addons', 'mg_trenchwarfare'))
GAME = os.environ.get('TW_GAME', os.path.join(LINKS, 'game_addons', 'mg_trenchwarfare'))
VPK = os.path.join(LINKS, 'cs2_root', 'game', 'csgo', 'pak01_dir.vpk')
VMAP = os.path.join(CONTENT, 'maps', 'mg_trenchwarfare.vmap')
REVIEW = os.path.join(PROJ, 'out', 'review')
OWN = ('models/tw/',)

# model pairs that touch by design (rows of revetment, stacked sandbags, dressing standing on another prop)
OK_PAIR = [('sandbag', 'sandbag'), ('revet_', 'revet_'), ('revet_', 'sandbag'), ('revet_', 'firestep'), ('firestep', 'firestep'), ('firestep', 'sandbag'),
           ('duckboard', ''), ('tunnel_set', ''), ('shelter', ''), ('hangar', 'plane_'), ('plane_', 'plane_'), ('plotting_table', 'sandbag'),
           ('ammo_box_mortar', 'sandbag'), ('tl_', ''), ('crate_', 'crate_'), ('shell_pile', ''), ('casings', ''), ('stretcher', ''),
           ('wreck_', 'sandbag'), ('log_fallen', 'stump'), ('tree_shattered', ''), ('stump', '')]
SINGLE = ('info_map_parameters', 'light_environment', 'env_sky', 'skybox_reference', 'team_select', 'end_of_match', 'terrorist_team_intro',
          'counterterrorist_team_intro')


def expected():
    """name -> (class or tuple of classes, required): what src/mg_trenchwarfare.js finds by name"""
    T = 'info_teleport_destination'; I = 'info_target'; D = 'prop_dynamic'; Sn = 'point_soundevent'; Fx = 'info_particle_system'
    TP = (T, 'point_teleport', I)
    e = {'tw_hud': ('custom_hud_layout', True), 'tw_script': ('point_script', True)}
    for tg in ('t', 'ct'):
        for i in range(1, 21): e['trench_%s_%d' % (tg, i)] = (TP, True)
        for i in range(1, 4): e['heal_%s_%d' % (tg, i)] = ((I, T), True)
        for k in range(1, 6):
            e['mortarpit_%s_%d' % (tg, k)] = ((I, T), True)
            e['mortarcrew_%s_%d_a' % (tg, k)] = (TP, True); e['mortarcrew_%s_%d_b' % (tg, k)] = (TP, True)
            e['mortar_%s_%d' % (tg, k)] = (D, True)              # fire('mortar_' + tg, 'SetAnimation', 'fire') (src:921)
            e['tw_launch_snd_%s_%d' % (tg, k)] = (Sn, True); e['tw_launch_fx_%s_%d' % (tg, k)] = (Fx, True)
        for n in range(1, 6):
            e['plane_%s_%d' % (tg, n)] = (TP, True); e['tw_plane_%s_%d' % (tg, n)] = (D, True); e['tw_prop_%s_%d' % (tg, n)] = (D, True)
            for b in (1, 2): e['tw_bomb_%s_%d_%d' % (tg, n, b)] = (D, True)
            for t_ in range(1, 7): e['tw_tracer_%s_%d_%d' % (tg, n, t_)] = (D, True)
            e['tw_bombsight_%s_%d' % (tg, n)] = (D, True); e['tw_gunsight_%s_%d' % (tg, n)] = (D, True)
            for k in ('eng', 'gun', 'gun2', 'gun3'): e['tw_plane_%s_%s_%d' % (k, tg, n)] = (Sn, True)
            e['tw_plane_smoke_%s_%d' % (tg, n)] = (Fx, True)
    for i in range(1, 13):
        e['tw_boom_fx_%d' % i] = (Fx, True); e['tw_dirt_fx_%d' % i] = (Fx, True); e['tw_boom_snd_%d' % i] = (Sn, True)
        e['tw_whistle_snd_%d' % i] = (Sn, True); e['tw_shake_%d' % i] = ('env_shake', True)
    for i in range(1, 5): e['tw_uniform_%d' % i] = (D, True)
    return e


def vpk_index():
    os.makedirs(os.path.join(REVIEW, 'cache'), exist_ok=True)
    cp = os.path.join(REVIEW, 'cache', 'pak01_index.pkl')
    if os.path.exists(cp) and os.path.exists(VPK) and os.path.getmtime(cp) > os.path.getmtime(VPK): return pickle.load(open(cp, 'rb'))
    if not os.path.exists(VPK): return None
    import vpkdir
    idx = set(vpkdir.read_dir(VPK).keys())
    pickle.dump(idx, open(cp, 'wb'))
    return idx


def main(path, out_json=None, verbose=False):
    t0 = time.time()
    m = V.Map(path)
    fails = []; warn = []; res = {}
    rows = []
    for e in m.entities():
        vg = m.g(e, b'customVisGroup', b''); vg = vg.decode() if isinstance(vg, bytes) else (vg or '')
        rows.append(dict(i=e, cls=m.cls(e), name=m.name(e), model=m.P(e, 'model', '') or '', o=tuple(round(float(v), 1) for v in m.origin(e)),
                         a=tuple(float(v) for v in m.g(e, b'angles', [0, 0, 0])), s=tuple(float(v) for v in (m.g(e, b'scales', None) or (1, 1, 1))),
                         solid=str(m.P(e, 'solid', '') or ''), vg=vg or 'ungrouped'))
    who = lambda r: dict(i=r['i'], cls=r['cls'], name=r['name'], model=r['model'].split('/')[-1], o=list(r['o']), vg=r['vg'])
    named = defaultdict(list)
    for r in rows:
        if r['name']: named[r['name']].append(r)
    # ---- 1 script names
    exp = expected(); bad = []
    for n, (cls, req) in exp.items():
        cs = cls if isinstance(cls, tuple) else (cls,)
        have = named.get(n, [])
        if not have: bad.append(dict(name=n, want=cs[0], have='missing'))
        elif len(have) > 1: bad.append(dict(name=n, want=cs[0], have='%d entities' % len(have)))
        elif have[0]['cls'] not in cs: bad.append(dict(name=n, want=cs[0], have=have[0]['cls'], i=have[0]['i'], o=list(have[0]['o'])))
    fam = Counter(re.sub(r'\d+', 'N', b['name']) for b in bad)
    mortars = []
    for tg in ('t', 'ct'):
        for k in range(1, 6):
            pit = named.get('mortarpit_%s_%d' % (tg, k))
            if not pit: continue
            px_, py_ = pit[0]['o'][:2]
            tube = [r for r in rows if r['cls'].startswith('prop_') and ('mortar' in r['model'] or 'minenwerfer' in r['model']) and math.hypot(r['o'][0] - px_, r['o'][1] - py_) < 40]
            for r in tube:
                vf = CP.vmdl_files(type('A', (), {'model_roots': [CONTENT]})(), r['model'])
                txt = open(os.path.join(CONTENT, r['model'].replace('/', os.sep)), errors='ignore').read() if os.path.exists(os.path.join(CONTENT, r['model'].replace('/', os.sep))) else ''
                fire = bool(re.search(r'"fire"', txt)) or bool(re.search(r'AnimFile|AnimationList', txt) and 'fire' in txt)
                mortars.append(dict(who(r), pit='mortarpit_%s_%d' % (tg, k), want_name='mortar_%s_%d' % (tg, k), archetype=vf[2] if vf else None, fire_anim=fire))
    res['1'] = dict(expected=len(exp), wrong=bad, families=dict(fam), mortars=mortars)
    print('1 script names: %d expected, %d wrong: %s' % (len(exp), len(bad), ', '.join('%s x%d' % kv for kv in fam.most_common()) or 'none'))
    for b in bad[:12 if not verbose else 200]: print('    ', b)
    for r in mortars[:10]: print('    tube at %s: %s %s (%s), name %r (script wants %s), archetype %r, fire animation %s' % (r['pit'], r['cls'], r['model'], r['vg'], r['name'], r['want_name'], r['archetype'], r['fire_anim']))
    if bad: fails.append('script names')
    # ---- 2 singletons
    cc = Counter(r['cls'] for r in rows)
    dup = {c: [who(r) for r in rows if r['cls'] == c] for c in SINGLE if cc.get(c, 0) > 1}
    for c in ('point_script', 'custom_hud_layout'):
        byn = Counter(r['name'] for r in rows if r['cls'] == c)
        for n, k in byn.items():
            if k > 1: dup['%s %s' % (c, n)] = [who(r) for r in rows if r['cls'] == c and r['name'] == n]
    miss = [c for c in ('info_map_parameters', 'light_environment', 'env_sky', 'skybox_reference', 'team_select') if cc.get(c, 0) == 0]
    res['2'] = dict(duplicates=dup, missing=miss)
    print('2 singletons: %d duplicated, %d missing %s' % (len(dup), len(miss), miss))
    for c, lst in dup.items():
        for w in lst: print('    %s: %s' % (c, w))
    if dup or miss: fails.append('singletons')
    # ---- 3 bounds: the sky shell and the lobby room (meshes)
    sky = None; lobby = None
    for n_, _ in m.walk():
        if m.type(n_) != b'CMapMesh': continue
        md = m.g(n_, b'meshData')
        mats = ' '.join(x.decode().lower() for x in m.g(md, b'materials') or [])
        if 'toolsskybox' in mats or 'briefing' in mats or 'wood_boards_worn' in mats:
            b = m.bounds(n_)
            if 'toolsskybox' in mats: sky = b
            elif lobby is None or b[0][2] < lobby[0][2]: lobby = b if 'wood_boards_worn' in mats else lobby
    def inbox(o, b, pad=0.0): return b is not None and all(b[0][k] - pad <= o[k] <= b[1][k] + pad for k in range(3))
    out_b = []
    for r in rows:
        if inbox(r['o'], sky) or inbox(r['o'], lobby, 2.0): continue
        if r['o'][2] < -3000 and (r['name'].startswith('tw_') or r['cls'] in ('prop_dynamic', 'info_particle_system', 'point_soundevent', 'env_shake')): continue     # script pools
        if r['cls'] in ('func_nav_markup',) and r['o'] == (0.0, 0.0, 0.0): continue
        out_b.append(who(r))
    res['3'] = dict(sky=[list(map(round, sky[0])), list(map(round, sky[1]))] if sky else None, lobby=[list(map(round, lobby[0])), list(map(round, lobby[1]))] if lobby else None, outside=out_b)
    print('3 bounds: sky shell %s, lobby %s; %d entities outside both (pools under the lobby excepted)' % (res['3']['sky'], res['3']['lobby'], len(out_b)))
    for w in out_b[:12]: print('    ', w)
    if out_b: fails.append('bounds')
    # ---- 4 overlaps (hull boxes)
    A_ = type('A', (), {'model_roots': [CONTENT]})()
    hb = {}
    def hull_box(model):
        if model in hb: return hb[model]
        vf = CP.vmdl_files(A_, model); r = None
        if vf and vf[1]:
            import numpy as np
            P = np.concatenate([CP.phys_tris(*f).reshape(-1, 3) for f in vf[1]])
            if len(P): r = (tuple(P.min(0)), tuple(P.max(0)))
        hb[model] = r
        return r
    sys.path.insert(0, HERE)
    import placer
    table = {}
    items = []
    for r in rows:
        if r['cls'] not in ('prop_static', 'prop_dynamic') or not r['model'].startswith(OWN) or r['solid'] == '0' or r['o'][2] < -1500: continue
        b = hull_box(r['model'])
        if b is None: continue
        table[r['model']] = b
        items.append(r)
    PL = placer.Placer(bounds=placer.Bounds(props_json=None, table=table))
    for r in items:
        f = PL.footprint(r['model'], r['o'][0], r['o'][1], r['o'][2], r['a'][1], r['s'], pad=-2.0)
        f['z'] = (f['z'][0] + 1.0, f['z'][1] - 1.0); f['r'] = r
        PL.add(f)
    short = lambda mm: mm.split('/')[-1][:-5]
    def allowed(a, b):
        for p, q in OK_PAIR:
            if (p in a and q in b) or (p in b and q in a): return True
        return False
    pairs = [(i, j) for i, j in PL.audit() if not allowed(short(PL.items[i]['model']), short(PL.items[j]['model']))]
    cnt = Counter(tuple(sorted((short(PL.items[i]['model']), short(PL.items[j]['model'])))) for i, j in pairs)
    plist = [dict(a=who(PL.items[i]['r']), b=who(PL.items[j]['r'])) for i, j in pairs]
    user_pairs = [p for p in plist if p['a']['vg'] != 'tw_gen' or p['b']['vg'] != 'tw_gen']
    res['4'] = dict(solid_props=len(items), pairs=len(pairs), top=[(a, b, c) for (a, b), c in cnt.most_common(30)], list=plist[:300], user_pairs=user_pairs)
    print('4 overlaps: %d solid props of ours with hulls, %d interpenetrating pairs outside OK_PAIR (%d involve a user object)' % (len(items), len(pairs), len(user_pairs)))
    for (a, b), c_ in cnt.most_common(12): print('    %3d  %s + %s' % (c_, a, b))
    if pairs: warn.append('%d overlapping solid prop pairs' % len(pairs))
    # ---- 5 wiring
    names = set(named)
    dang = []
    for r in rows:
        for c in m.conns(r['i']):
            t = m.conn_tuple(c)
            tgt = t[1] if len(t) > 1 else ''
            if tgt and not tgt.startswith('!') and tgt not in names and not any(re.fullmatch(tgt.replace('*', '.*'), n) for n in names): dang.append((r['name'] or r['cls'], t[0], tgt))
    res['5'] = dict(dangling=dang)
    print('5 wiring: %d outputs to a name that is not in the map' % len(dang))
    for d in dang[:10]: print('    ', d)
    if dang: fails.append('wiring')
    # ---- 6 counts
    ps = cc.get('prop_static', 0)
    res['6'] = dict(classes=dict(cc.most_common()), prop_static=ps)
    print('6 classes: ' + ', '.join('%s %d' % kv for kv in cc.most_common(14)) + ' ...; prop_static %d (target < 9000)' % ps)
    if ps >= 9000: fails.append('prop count')
    # ---- 7 models
    idx = vpk_index()
    missing = Counter(); notcompiled = Counter(); stale = Counter(); n_own = n_stock = 0; seen = set(); who_m = defaultdict(list)
    for r in rows:
        mm = r['model']
        if not mm.endswith('.vmdl'): continue
        who_m[mm].append(r)
        if mm in seen: continue
        seen.add(mm)
        if mm.startswith(OWN):
            n_own += 1
            src = os.path.join(CONTENT, mm.replace('/', os.sep)); cmp_ = os.path.join(GAME, mm.replace('/', os.sep) + '_c')
            if not os.path.isfile(src): missing[mm] += 1
            if not os.path.isfile(cmp_): notcompiled[mm] += 1
            elif os.path.isfile(src) and os.path.getmtime(src) > os.path.getmtime(cmp_) + 2: stale[mm] += 1
        elif idx is not None:
            n_stock += 1
            if mm + '_c' not in idx and not os.path.isfile(os.path.join(GAME, mm.replace('/', os.sep) + '_c')): missing[mm] += 1
    res['7'] = dict(own=n_own, stock=n_stock, missing={k: [who(r) for r in who_m[k]][:6] for k in missing}, not_compiled=list(notcompiled), stale=list(stale))
    print('7 models: %d of ours, %d stock (%s); %d missing, %d of ours not compiled in the game addon, %d compiled before their last .vmdl edit'
          % (n_own, n_stock, 'pak01 index' if idx is not None else 'NO VPK: stock not checked', len(missing), len(notcompiled), len(stale)))
    for mm in list(missing)[:12]: print('    missing %s x%d' % (mm, len(who_m[mm])))
    for mm in list(notcompiled)[:12]: print('    not compiled %s x%d' % (mm, len(who_m[mm])))
    for mm in list(stale)[:12]: print('    stale %s' % mm)
    if missing or notcompiled: fails.append('models')
    # 7b archetypes
    arch_bad = []
    arch = {}
    for r in rows:
        mm = r['model']
        if r['cls'] != 'prop_dynamic' or not mm.startswith(OWN): continue
        if mm not in arch:
            vf = CP.vmdl_files(A_, mm); arch[mm] = vf[2] if vf else None
        if arch[mm] not in (None, '', 'animated_model'): arch_bad.append(dict(who(r), archetype=arch[mm]))
    res['7b'] = dict(dynamic_models=len(arch), wrong=arch_bad)
    print('7b archetypes: %d prop_dynamic models of ours, %d entities on a static_prop_model' % (len(arch), len(arch_bad)))
    for b in arch_bad[:10]: print('    ', b)
    if arch_bad: fails.append('archetypes')
    res['fails'] = fails; res['warnings'] = warn; res['seconds'] = round(time.time() - t0, 1)
    for w in warn: print('WARNING ' + w)
    oj = out_json or os.path.join(REVIEW, 'check_world.json')
    os.makedirs(os.path.dirname(oj), exist_ok=True)
    json.dump(res, open(oj, 'w'), indent=1, default=str)
    print('RESULT: %s  (%.1f s)' % ('clean' if not fails else 'FAILED: ' + ', '.join(fails), time.time() - t0))
    return 1 if fails else 0


if __name__ == '__main__':
    argv = sys.argv[1:]
    if argv and argv[0] in ('-h', '--help'): print(__doc__); sys.exit(2)
    path = argv[0] if argv and not argv[0].startswith('--') else VMAP
    oj = argv[argv.index('--json') + 1] if '--json' in argv else None
    sys.exit(main(path, oj, '--verbose' in argv))
