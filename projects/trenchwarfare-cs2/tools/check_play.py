"""mg_trenchwarfare gameplay checks: the trench adapter for the neutral create/check_play.py (offline; "simulated").

usage: python tools/check_play.py [map.vmap] [--json out.json] [--only 1,6,T1] [--verbose] [--map out.png [x0,y0,x1,y1]] [--stage DIR]
       --stage DIR: a staging folder (e.g. out/addon) searched for models before the content addon
       (map default: the user's vmap in the content addon; read only)

The neutral checks (create/check_play.py docstring) run with this map's worlds and points:
  worlds     t / ct = the 20 infantry posts (trench_<tg>_N) + 3 dressing stations (heal_<tg>_N), one walkable trench system each at the
             round start; lobby = the 64 spawns in the briefing room; pit_<tg>_K = the two crew seats of each mortar pit
  separate   t and ct never meet while the blockers stand (woodsopen / undergroundopen); no pit is reached by the enemy
  targets    once the blockers are gone (the "open" state) both sides reach the woods clearing and the mine chamber (the nav seeds there)
  routes     t / ct walking distance to the woods clearing and the chamber (mirror pairs)
  sightlines enemy fire-step eyes -> deploy posts (a player arriving on the trench floor), -> mortar crews standing at their seats
  cover      the two halves of the woods clearing (the only open-ground fight)
Trench checks:
  T1 depth      trench floor below the cover around it: each walkable floor node of t / ct (every 3rd cell) against the highest solid
                ground within 128 u: a standing player's head (64 u eye) shows where that is < 60 u; plus enemy fire-step eyes -> eye
                at the node (head exposure across no man's land)
  T2 fire steps every firestep prop: a standing spot on top, in its side's walkable world, eye 64 u over it clears the parapet (a line to
                ground 500 u out into no man's land)
  T3 ladders    climb volumes (toolsinvisibleladder): walkable ground at the bottom (in the world once open) and at the top; decorative
                ladder props without a volume are listed (the clips keep infantry in the trench by design)
  T4 dugouts    each shelter has a walkable interior joined to its trench and >= 72 u headroom at the dressing station
  T5 no man's land  no walkable node of t / ct inside no man's land (|x| < 1450, |y| < 2750, above the galleries) in either state;
                wire props standing in a trench floor
  T6 mortar pits each pit's seats in one world, the pit closed off from both trench systems (crews are teleported), tube / table / box present
  T7 runways    air spawns (plane_<tg>_N + 1100): nothing within 300 u, a clear 3000-u lane on the spawn heading; nothing over z 2900 in
                the flight box (the script's ground trace starts at 3000); the flight box inside the sky shell; parked planes on flat ground,
                clear of other solid props
  T8 spawns     lobby: 64 spawns on the floor, >= 72 u headroom, >= 32 u apart; posts: headroom, >= 40 u apart, facing the enemy
"""
import os, sys, math, re
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
REPO = os.path.normpath(os.path.join(PROJ, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'create'))
import importlib.util
_spec = importlib.util.spec_from_file_location('check_play_neutral', os.path.join(REPO, 'create', 'check_play.py'))
CP = importlib.util.module_from_spec(_spec); sys.modules['check_play_neutral'] = CP; _spec.loader.exec_module(CP)   # create/check_play.py (this file shares its name)

LINKS = os.environ.get('TW_LINKS', r'C:\source1\links')
CONTENT = os.environ.get('TW_CONTENT', os.path.join(LINKS, 'content_addons', 'mg_trenchwarfare'))
VMAP = os.path.join(CONTENT, 'maps', 'mg_trenchwarfare.vmap')
REVIEW = os.path.join(PROJ, 'out', 'review')

# from tools/layout.py (generator constants) and the script's CONFIG (src/mg_trenchwarfare.js)
XF, XB, XS, HW, STEP_D = 1641.0, 1791.0, 2150.0, 36.0, 30.0
MORTAR_X, HANGAR_X = 3200.0, 6150.0
NML_X, NML_Y, NML_ZMIN = 1450.0, 2750.0, -150.0        # no man's land box (the woods track runs north of y 2750, the galleries under z -150)
SPAWN_ALT, NOSE, BOX_X, BOX_Y, ALT_MAX, HARD, HARD_Z = 1100.0, 90.0, 6500.0, 5500.0, 5000.0, 600.0, 400.0
GROUND_TRACE_Z = 3000.0
WOODS = {'t': (-1210.0, 3930.0), 'ct': (1210.0, 3930.0)}


class Trench(CP.Adapter):
    name = 'mg_trenchwarfare'
    extent = (-7424.0, -6400.0, 7424.0, 6400.0)
    model_roots = [CONTENT]
    vpk_dir = os.path.join(LINKS, 'cs2_root', 'game', 'csgo')
    cache_dir = os.path.join(REVIEW, 'cache')
    out_json = os.path.join(REVIEW, 'check_play.json')
    terrain_mats = ('hr_ancient_blend_groundgrass01-grounddirt01', 'hr_ancient_blend_groundmud03-groundgrass')
    water_mats = ('water',)
    water_edge_tol = 3.0        # trench pools end at the wall foot under the revetments: a 1-3 u lip there is hidden
    removable = ('woodsopen', 'undergroundopen')
    foliage = ('foliage', 'weeds', 'grass', 'leaves', 'bush', 'shrub', 'dogwood', 'viburnum')
    trees = ('tree_poplar', 'maple_tree', 'tree_small_beech', 'tree_shattered')
    buildings = ('hangar', 'shelter')
    water_ok = ('duckboard', 'wire_', 'stump', 'log_fallen', 'tree_shattered', 'casings', 'helmet', 'tl_')
    floors = {}

    def skip_entity(self, e):
        return e['o'][2] < -3000.0                     # script pools and precache props under the lobby

    def clip_tag(self, p):
        m = p['model']
        if any(k in m for k in ('revet_', 'firestep', 'tunnel_set', 'shelter', 'hangar')): return 'bury'      # set into the trench walls / the bank by design
        if any(k in m for k in ('stump_', 'helmet_', 'debris_metal', 'aztec_river_rock')): return 'bury'   # sunk into the churned mud as dressing
        if any(k in m for k in ('ladder', 'tl_lantern', '_prop.vmdl', 'tw_prop')): return 'float'   # leans on the wall / hangs from a frame / on the plane's nose
        return None

    def inplay(self, x, y, z):
        return abs(x) <= 7424 and abs(y) <= 6400

    # ---------------------------------------------------------------- points
    def worlds(self, ctx):
        w = {}
        for tg in ('t', 'ct'):
            w[tg] = ctx.points(r'trench_%s_\d+' % tg) + ctx.points(r'heal_%s_\d+' % tg)
            for k in range(1, 6): w['pit_%s_%d' % (tg, k)] = ctx.points(r'mortarcrew_%s_%d_[ab]' % (tg, k))
        w['lobby'] = [(e['cls'], e['o'][0], e['o'][1], e['o'][2]) for e in ctx.ents if e['cls'] in ('info_player_terrorist', 'info_player_counterterrorist')]
        # the two areas the unlocks open: the woods clearing (a point well inside each half) and the mine galleries (their nav seeds)
        w['woods'] = [('woods %s' % tg, x * 0.5, y, ctx.G.ground(x * 0.5, y, 1e4) + 8) for tg, (x, y) in WOODS.items()]
        w['mines'] = [('mines seed %d' % k, x, y, z + 8) for k, (n, x, y, z) in enumerate(self.seeds(ctx)) if -1000 < z < -150]
        return w

    def separate(self, ctx):
        s = [('t', 'ct'), ('t', 'woods'), ('ct', 'woods'), ('t', 'mines'), ('ct', 'mines')]
        for k in range(1, 6): s += [('t', 'pit_ct_%d' % k), ('ct', 'pit_t_%d' % k)]
        return s

    def seeds(self, ctx):
        return [(n, (b[0] + b[3]) / 2, (b[1] + b[4]) / 2, b[2]) for (p, n, b) in ctx.sc['navboxes'] if p == 'WALKABLESEED']

    def targets(self, ctx):
        """once the blockers are gone both sides walk into the woods clearing and the mine galleries"""
        out = []
        for (n, x, y, z) in ctx.points(r'.*') if False else []: pass
        for w in ('woods', 'mines'):
            for (n, x, y, z) in self.worlds(ctx)[w]:
                for tg in ('t', 'ct'): out.append(dict(name='%s from %s' % (n, tg), x=x, y=y, z=z, state='open', world=tg))
        return out

    def routes(self, ctx):
        r = []
        ch = [s for s in self.seeds(ctx) if -1000 < s[3] < -150 and abs(s[1]) < 400]
        for tg in ('t', 'ct'):
            wx, wy = WOODS[tg]; wx *= 0.5                # well inside the fenced clearing (the nav seeds at x +-1210 are outside it)
            r.append(('%s->woods' % tg, tg, 'open', (wx, wy, ctx.G.ground(wx, wy, 1e4) + 8)))
            r.append(('%s->enemy woods' % tg, tg, 'open', (-wx, wy, ctx.G.ground(-wx, wy, 1e4) + 8)))
            if ch: r.append(('%s->chamber' % tg, tg, 'open', (ch[0][1], ch[0][2], ch[0][3] + 8)))
        return r

    def mirror_pairs(self, ctx):
        return [('t->woods', 'ct->woods'), ('t->enemy woods', 'ct->enemy woods'), ('t->chamber', 'ct->chamber')]

    def firesteps(self, ctx):
        """(side, prop, stand point (x, y, z) or None): the top of each firestep prop's hull at its centre"""
        out = []
        for p in ctx.props:
            if 'models/tw/firestep/' not in p['model']: continue
            tg = 't' if p['o'][0] < 0 else 'ct'
            cx, cy = (p['lo'][0] + p['hi'][0]) / 2, (p['lo'][1] + p['hi'][1]) / 2
            z = ctx.G.ground(cx, cy, p['hi'][2] + 4)
            out.append((tg, p, (cx, cy, z) if np.isfinite(z) and z > p['lo'][2] - 30 else None))
        return out

    def no_sight(self, ctx):
        eyes = {tg: [(x, y, z + 64.0) for (s, p, q) in self.firesteps(ctx) if s == tg and q for (x, y, z) in [q]][::2] for tg in ('t', 'ct')}
        ns = []
        for tg, en in (('t', 'ct'), ('ct', 't')):
            posts = [(x, y, ctx.G.ground(x, y, z) + 64.0) for (n, x, y, z) in ctx.points(r'trench_%s_\d+' % tg)]
            ns.append(dict(label='%s fire steps -> %s posts (eye)' % (en, tg), A=eyes[en], B=posts))
            crew = [(x, y, ctx.G.ground(x, y, z) + 64.0) for (n, x, y, z) in ctx.points(r'mortarcrew_%s_\d_[ab]' % tg)]
            ns.append(dict(label='%s fire steps -> %s mortar crews (eye)' % (en, tg), A=eyes[en], B=crew))
        return ns

    def cover_sites(self, ctx):
        return [('woods %s half' % tg, x, y, ctx.G.ground(x, y, 1e4), 600.0, 4) for tg, (x, y) in WOODS.items()]

    def paths(self, ctx):
        try:
            import layout as L                        # tools/layout.py: the generator's trench centre lines
        except Exception:
            return []
        out = []
        for (a, b, kind) in L.segments():
            if kind == 'niche': continue                 # the shelter fills its niche (T4)
            for s in (1, -1):
                out.append(('%s %s' % ('ct' if s > 0 else 't', kind), 0.0, [(s * a[0], a[1]), (s * b[0], b[1])]))
        return out

    def nav_protect(self, ctx):
        return [(n, x, y, z) for tg in ('t', 'ct') for (n, x, y, z) in ctx.points(r'(trench|heal)_%s_\d+' % tg)]

    def extra_checks(self, ctx):
        return [('T1', 'trench depth', t1_depth), ('T2', 'fire steps', t2_firesteps), ('T3', 'ladders', t3_ladders), ('T4', 'dugouts', t4_dugouts),
                ('T5', "no man's land", t5_nml), ('T6', 'mortar pits', t6_pits), ('T7', 'runways and plane lanes', t7_air), ('T8', 'spawns', t8_spawns)]


A = Trench()


def _xyz(ctx, n): return ctx.node_xyz(n)


# ---------------------------------------------------------------- T1 depth
def t1_depth(ctx):
    G = ctx.G; SG = ctx.SG; NX, NY, NC, CELL, X0, Y0 = CP.NX, CP.NY, CP.NC, CP.CELL, CP.X0, CP.Y0
    fs_cells = set()
    for (tg, p, q) in A.firesteps(ctx):
        c, _, _ = G.disc((p['lo'][0] + p['hi'][0]) / 2, (p['lo'][1] + p['hi'][1]) / 2, 40.0)
        fs_cells.update(c.tolist())
    res = {}; lines = []; warn = []; fails = []
    H = SG.hard
    offs = [(int(round(r * math.cos(a) / CELL)), int(round(r * math.sin(a) / CELL))) for r in (48, 80, 112, 128) for a in np.linspace(0, 2 * math.pi, 16, endpoint=False)]
    fs = {tg: [(x, y, z + 64.0) for (s, p, q) in A.firesteps(ctx) if s == tg and q for (x, y, z) in [q]][::3] for tg in ('t', 'ct')}
    for tg, en in (('t', 'ct'), ('ct', 't')):
        W = ctx.world_mask(tg, 'closed').reshape(G.K, NC)
        k_, c_ = np.nonzero(W)
        sel = ((c_ // NY) % 3 == 0) & ((c_ % NY) % 3 == 0)
        k_, c_ = k_[sel], c_[sel]
        xs = X0 + (c_ // NY + 0.5) * CELL; ys = Y0 + (c_ % NY + 0.5) * CELL; zs = G.Z[k_, c_]
        trench = (np.abs(np.abs(xs) - 1900) < 700) & (np.abs(ys) < 3300) & (zs > -150) & np.array([c not in fs_cells for c in c_.tolist()])
        xs, ys, zs, cc = xs[trench], ys[trench], zs[trench], c_[trench]
        depth = np.full(len(xs), np.inf)
        ii = cc // NY; jj = cc % NY
        cov = np.full(len(xs), -np.inf)
        for (di, dj) in offs:
            a = np.clip(ii + di, 0, NX - 1); b = np.clip(jj + dj, 0, NY - 1)
            cov = np.maximum(cov, H[a, b])
        depth = cov - zs
        shallow = depth < 60.0
        # head exposure: enemy fire-step eyes -> the eye of a player standing on the node
        E = np.array(fs[en]); P = np.stack([xs, ys, zs + 64.0], 1)
        seen = np.zeros(len(P), int)
        if len(E) and len(P):
            for e in E:
                d = np.hypot(P[:, 0] - e[0], P[:, 1] - e[1])
                m = d < 6000
                v = np.zeros(len(P), bool)
                if m.any(): v[m] = SG.los(np.repeat(e[None], m.sum(), 0), P[m], skip=40.0)
                seen += v
        cl_sh = CP.cluster([(x, y) for x, y in zip(xs[shallow], ys[shallow])], 160.0)
        cl_ex = CP.cluster([(x, y) for x, y, s in zip(xs, ys, seen) if s > 0], 160.0)
        res[tg] = dict(nodes=len(xs), depth_median=round(float(np.median(depth)), 1) if len(xs) else None, depth_min=round(float(depth.min()), 1) if len(xs) else None,
                       shallow=int(shallow.sum()), exposed=int((seen > 0).sum()), shallow_places=[dict(x=round(a), y=round(b), n=n) for a, b, n in cl_sh[:20]],
                       exposed_places=[dict(x=round(a), y=round(b), n=n, z=round(float(zs[np.argmin(np.hypot(xs - a, ys - b))]))) for a, b, n in cl_ex[:20]])
        lines.append('%s: %d floor samples, cover above the floor median %.0f u, min %.0f u; %d samples under 60 u in %d places; %d samples where an enemy fire-step eye sees a standing eye, in %d places'
                     % (tg, len(xs), res[tg]['depth_median'] or 0, res[tg]['depth_min'] or 0, int(shallow.sum()), len(cl_sh), int((seen > 0).sum()), len(cl_ex)))
        for a, b, n in cl_ex[:6]: lines.append('   exposed near (%d, %d): %d samples' % (a, b, n))
        for a, b, n in cl_sh[:6]: lines.append('   shallow near (%d, %d): %d samples' % (a, b, n))
        if cl_ex: warn.append('%s trench: %d places where a standing player is seen from the enemy fire step' % (tg, len(cl_ex)))
    return dict(result=res, lines=lines, warn=warn, fail=fails, summary='t %s / ct %s exposed places' % (len(res['t']['exposed_places']), len(res['ct']['exposed_places'])))


# ---------------------------------------------------------------- T2 fire steps
_JW = {}


def jump_world(ctx, tg):
    """nodes a side reaches and comes back from when jumps (54 u) are allowed (closed state): a fire step is a jump up from the floor;
    the user's func_brush clip stair in front of it is finer than the 16-u grid"""
    if tg in _JW: return _JW[tg]
    G = ctx.G
    if G.jump is None:
        wb = G.blocked; G.blocked = G.blocked_jump; G.jump = G.graph(CP.JUMP); G.blocked = wb
    from scipy import sparse
    keep = (~G.extra_blocked.ravel()).astype(np.int8) if getattr(G, 'extra_blocked', None) is not None else None
    J = G.jump
    if keep is not None:
        D = sparse.diags(keep, dtype=np.int8); J = (D @ J @ D).tocsr()
    _JW[tg] = CP.reach(J, ctx.home[tg]) & CP.reach(J, ctx.home[tg], reverse=True)
    return _JW[tg]
def t2_firesteps(ctx):
    G = ctx.G; SG = ctx.SG
    out = {'t': dict(n=0, no_spot=[], off_world=[], blind=[]), 'ct': dict(n=0, no_spot=[], off_world=[], blind=[])}
    for (tg, p, q) in A.firesteps(ctx):
        r = out[tg]; r['n'] += 1
        tag = (round(p['o'][0]), round(p['o'][1]))
        if q is None: r['no_spot'].append(tag); continue
        x, y, z = q
        ids = ctx.nodes(x, y, z, 24.0, 12.0, dz=0.0, state='closed')
        W = ctx.world_mask(tg, 'closed'); J = jump_world(ctx, tg)
        if any(W[i] for i in ids): r['walk'] = r.get('walk', 0) + 1
        if not any(J[i] for i in ids): r['off_world'].append(tag + (round(z),))
        s = -1.0 if tg == 'ct' else 1.0                     # toward the enemy
        # parapet clearance: the best of five lines straight forward from the step (+-24 u along it): eye (64 u over the step) minus
        # the highest solid thing 16..112 u in front on that line
        H = SG.hard; tops = []
        for o in (-24, -12, 0, 12, 24):
            t_ = -1e9
            for d in range(16, 113, 16):
                i = int((x + s * d - CP.X0) // CP.CELL); j = int((y + o - CP.Y0) // CP.CELL)
                t_ = max(t_, float(H[i, j]))
            tops.append(t_)
        clear = z + 64.0 - min(tops)
        r.setdefault('clearance', []).append(round(clear, 1))
        if clear < 4.0: r['blind'].append(tag + (round(z), round(clear, 1)))
    lines = []; fails = []; warn = []
    for tg, r in out.items():
        cl = r.get('clearance', [0])
        lines.append('%s: %d fire steps, %d without a standing spot, %d not reached from the trench floor with a jump (%d by walking on the 16-u grid), %d whose eye clears the parapet by < 4 u (clearance min %.0f, median %.0f u)'
                     % (tg, r['n'], len(r['no_spot']), len(r['off_world']), r.get('walk', 0), len(r['blind']), min(cl), float(np.median(cl))))
        for k in ('no_spot', 'off_world', 'blind'):
            if r[k]: lines.append('   %s: %s' % (k, r[k][:10]))
        if r['off_world'] or r['blind']: fails.append('%s fire steps' % tg)
    return dict(result=out, lines=lines, fail=fails, warn=warn, summary='%d / %d fire steps checked' % (out['t']['n'], out['ct']['n']))


# ---------------------------------------------------------------- T3 ladders
def t3_ladders(ctx):
    G = ctx.G
    vols = []; lines = []; fails = []
    for L_, ids in zip(ctx.sc['ladders'], G.ladder_nodes):
        b = L_['box']; tg = 't' if b[0] < 0 else 'ct'
        zs = [ctx.node_xyz(n)[2] for n in ids]
        bot = [n for n, z in zip(ids, zs) if z <= b[2] + 24]; top = [n for n, z in zip(ids, zs) if z >= b[5] - 40]
        Wo = ctx.world_mask(tg, 'open'); Wc = ctx.world_mask(tg, 'closed')
        rec = dict(box=[round(v) for v in b], vg=L_['vg'] or 'ungrouped', side=tg, bottom=len(bot), top=len(top),
                   bottom_open=any(Wo[n] for n in bot), bottom_closed=any(Wc[n] for n in bot), top_open=any(Wo[n] for n in top),
                   floor=round(max(ctx.node_xyz(n)[2] for n in bot)) if bot else None, top_floor=round(min(ctx.node_xyz(n)[2] for n in top)) if top else None)
        # how far is the nearest walkable floor node below the volume's bottom face (the nav generator joins a ladder bottom within reach)
        near = ctx.nodes((b[0] + b[3]) / 2, (b[1] + b[4]) / 2, b[2], 64.0, 48.0, dz=0.0, state='open')
        rec['floor_within_64'] = len(near)
        vols.append(rec)
        lines.append('volume %s (%s, %s side): bottom nodes %d (floor z %s; in the world: open %s, closed %s), top nodes %d (z %s; in the world open %s)'
                     % (rec['box'], rec['vg'], tg, rec['bottom'], rec['floor'], rec['bottom_open'], rec['bottom_closed'], rec['top'], rec['top_floor'], rec['top_open']))
        if not (rec['bottom_open'] and rec['top_open']): fails.append('ladder %s' % rec['box'][:3])
    deco = [p for p in ctx.props if 'models/tw/ladder/' in p['model']]
    lone = []
    for p in deco:
        if not any(abs(p['o'][0] - (v['box'][0] + v['box'][3]) / 2) < 80 and abs(p['o'][1] - (v['box'][1] + v['box'][4]) / 2) < 80 for v in vols):
            lone.append((round(p['o'][0]), round(p['o'][1]), round(p['o'][2]), p['vg'] or 'ungrouped'))
    lines.append('%d ladder props, %d without a climb volume (decorative: the trench clips keep infantry in by design): %s' % (len(deco), len(lone), lone[:14]))
    return dict(result=dict(volumes=vols, decorative=lone), lines=lines, fail=fails, summary='%d climb volumes, %d decorative ladder props' % (len(vols), len(lone)))


# ---------------------------------------------------------------- T4 dugouts
def t4_dugouts(ctx):
    G = ctx.G; lines = []; fails = []; out = []
    for p in ctx.props:
        if 'models/tw/shelter/' not in p['model']: continue
        tg = 't' if p['o'][0] < 0 else 'ct'
        W = ctx.world_mask(tg, 'closed')
        cx, cy = (p['lo'][0] + p['hi'][0]) / 2, (p['lo'][1] + p['hi'][1]) / 2
        ids = ctx.nodes(cx, cy, p['o'][2] + 8, 60.0, 30.0, state='closed')
        inn = [i for i in ids if W[i]]
        heal = [e for e in ctx.ents if re.fullmatch(r'heal_%s_\d+' % tg, e['name']) and math.hypot(e['o'][0] - p['o'][0], e['o'][1] - p['o'][1]) < 160]
        head = None
        if heal:
            h = heal[0]; c = CP.cell_of(h['o'][0], h['o'][1]); fz = G.ground(h['o'][0], h['o'][1], h['o'][2])
            above = G.Z[:, c][np.isfinite(G.Z[:, c]) & (G.Z[:, c] > fz + 1)]
            bl = G.b_lo[(G.b_cell == c) & (G.b_lo > fz + 1)]
            cand = list(above) + list(bl)
            head = round(float(min(cand) - fz), 1) if cand else 999.0
        rec = dict(at=[round(p['o'][0]), round(p['o'][1]), round(p['o'][2])], side=tg, interior_nodes=len(ids), in_world=len(inn), heal=heal[0]['name'] if heal else None, headroom=head, vg=p['vg'])
        out.append(rec)
        lines.append('shelter %s (%s): %d interior nodes, %d in the walkable trench; %s headroom %s u' % (rec['at'], tg, len(ids), len(inn), rec['heal'], head))
        if not inn or (head is not None and head < 72): fails.append('shelter %s' % rec['at'][:2])
    return dict(result=out, lines=lines, fail=fails, summary='%d shelters' % len(out))


# ---------------------------------------------------------------- T5 no man's land
def t5_nml(ctx):
    G = ctx.G; NC = CP.NC; lines = []; fails = []; warn = []
    leak = {}
    for tg in ('t', 'ct'):
        for st in ('closed', 'open'):
            Wm = ctx.reach_of(tg, st).reshape(G.K, NC)
            k_, c_ = np.nonzero(Wm)
            xs = CP.X0 + (c_ // CP.NY + 0.5) * CP.CELL; ys = CP.Y0 + (c_ % CP.NY + 0.5) * CP.CELL; zs = G.Z[k_, c_]
            m = (np.abs(xs) < NML_X) & (np.abs(ys) < NML_Y) & (zs > NML_ZMIN)
            cl = CP.cluster(list(zip(xs[m], ys[m])), 200.0)
            leak['%s %s' % (tg, st)] = dict(cells=int(m.sum()), places=[dict(x=round(a), y=round(b), n=n) for a, b, n in cl[:10]])
            if m.sum(): fails.append('%s walks into no man\'s land (%s)' % (tg, st))
    lines.append('walkable cells inside no man\'s land: ' + ', '.join('%s %d' % (k, v['cells']) for k, v in leak.items()))
    for k, v in leak.items():
        for pl in v['places'][:4]: lines.append('   %s: near (%d, %d), %d cells' % (k, pl['x'], pl['y'], pl['n']))
    wire = [p for p in ctx.props if '/wire_' in p['model'] or 'cheval' in p['model']]
    in_trench = []
    for p in wire:
        x, y, z = p['o']
        g = max(G.terr[CP.cell_of(x + dx, y + dy)] for dx in (-96, 96) for dy in (-96, 96) if CP.cell_of(x + dx, y + dy) >= 0)
        if z < g - 40 and abs(x) > 1500: in_trench.append((CP.short(p['model']), round(x), round(y), round(z), p['vg'] or 'ungrouped'))
    nml_wire = sum(1 for p in wire if abs(p['o'][0]) < NML_X)
    lines.append('%d wire / cheval props, %d in no man\'s land, %d standing on a trench floor: %s' % (len(wire), nml_wire, len(in_trench), in_trench[:8]))
    if in_trench: warn.append('%d wire props on a trench floor' % len(in_trench))
    return dict(result=dict(leak=leak, wire=len(wire), nml_wire=nml_wire, wire_in_trench=in_trench), lines=lines, fail=fails, warn=warn,
                summary='leaks %s' % (', '.join(k for k, v in leak.items() if v['cells']) or 'none'))


# ---------------------------------------------------------------- T6 mortar pits
def t6_pits(ctx):
    G = ctx.G; lines = []; fails = []; out = []
    for tg in ('t', 'ct'):
        for k in range(1, 6):
            pit = ctx.by.get('mortarpit_%s_%d' % (tg, k))
            w = 'pit_%s_%d' % (tg, k)
            if pit is None: fails.append('mortarpit_%s_%d missing' % (tg, k)); continue
            near = lambda frag, r=140.0: [p for p in ctx.props if frag in p['model'] and math.hypot(p['o'][0] - pit['o'][0], p['o'][1] - pit['o'][1]) < r]
            tube = near('mortar_58mm', 40) + near('minenwerfer', 40)
            Wp = ctx.world_mask(w, 'closed'); Wt = ctx.world_mask(tg, 'closed')
            joined = bool((Wp & Wt).any())
            cells = int(Wp.sum())
            rec = dict(pit=w, seats_split=ctx.res.get('1', {}).get('worlds', {}).get(w, {}).get('split'), cells=cells, joined_to_trench=joined,
                       tube=[(CP.short(p['model']), p['cls'], p['name']) for p in tube], table=len(near('plotting_table')), ammo=len(near('ammo_box_mortar')))
            out.append(rec)
            lines.append('%s: %d walkable cells, joined to the %s trench: %s; tube %s, table %d, ammo box %d' % (w, cells, tg, joined, rec['tube'], rec['table'], rec['ammo']))
            if not tube or not rec['table'] or not rec['ammo']: fails.append('%s station missing' % w)
    return dict(result=out, lines=lines, fail=fails, summary='%d pits' % len(out))


# ---------------------------------------------------------------- T7 air
def t7_air(ctx):
    G = ctx.G; SG = ctx.SG; lines = []; fails = []; warn = []; out = []
    NX, NY, X0, Y0, CELL = CP.NX, CP.NY, CP.X0, CP.Y0, CP.CELL
    V = SG.vis
    def vis_at(x, y):
        i = int((x - X0) // CELL); j = int((y - Y0) // CELL)
        return float(V[i, j]) if 0 <= i < NX and 0 <= j < NY else -1e9
    for tg in ('t', 'ct'):
        for (n, x, y, z) in ctx.points(r'plane_%s_\d+' % tg):
            sz = z + SPAWN_ALT
            near = max(vis_at(x + dx, y + dy) for dx in np.arange(-300, 301, 32) for dy in np.arange(-300, 301, 32) if dx * dx + dy * dy <= 300 * 300)
            f = -1.0 if tg == 'ct' else 1.0
            lv = [(vis_at(x + f * d, y), x + f * d) for d in np.arange(0, 3000, 16)]
            lane, lx = max(lv)
            who = [CP.short(q['model']) for q in ctx.props if q['hi'][2] >= lane - 1 and q['lo'][0] - 64 <= lx <= q['hi'][0] + 64 and q['lo'][1] - 64 <= y <= q['hi'][1] + 64][:3]
            rec = dict(name=n, spawn_z=round(sz), clear_r300=round(sz - near), lane_clear=round(sz - lane - NOSE), lane_top=[round(lx), round(y), round(lane)], lane_by=who)
            out.append(rec)
            if rec['clear_r300'] < 0 or rec['lane_clear'] < 0: fails.append('%s air spawn blocked' % n)
    hi = V.max()
    i, j = np.unravel_index(np.argmax(V), V.shape)
    bx = (np.abs(X0 + (np.arange(NX) + 0.5) * CELL) <= BOX_X + HARD)[:, None] & (np.abs(Y0 + (np.arange(NY) + 0.5) * CELL) <= BOX_Y + HARD)[None, :]
    over = int(((V > GROUND_TRACE_Z - 100) & bx).sum())
    sky = [m for m in ctx.sc['meshes'] if 'toolsskybox' in m['mat'] or 'skybox' in m['mat']]
    sky_box = None
    for m in ctx.sc['meshes']:
        pass
    lines.append('air spawns: ' + ', '.join('%s z %d (r300 clear by %d, lane clear by %d; highest under the lane %s %s)' % (r['name'], r['spawn_z'], r['clear_r300'], r['lane_clear'], r['lane_top'], r['lane_by']) for r in out))
    lines.append('tallest thing in the flight box: %.0f at (%.0f, %.0f); %d cells over z %d (the script\'s ground trace starts at %d)'
                 % (hi, X0 + (i + 0.5) * CELL, Y0 + (j + 0.5) * CELL, over, GROUND_TRACE_Z - 100, GROUND_TRACE_Z))
    if over: fails.append('geometry over the ground-trace start')
    # parked planes: ground under the footprint, other solid props inside it
    for p in ctx.props:
        if not re.fullmatch(r'tw_plane_(t|ct)_\d+', p['name'] or ''): continue
        zs = [G.ground(px_, py_, p['o'][2] + 40) for px_, py_ in p['poly']]
        rel = max(zs) - min(zs)
        def box_of(q):
            if q['hull'] == 'trunk':
                r_ = A.trunk_radius(q['model']) * q['s'][0]; return (q['o'][0] - r_, q['o'][1] - r_, q['o'][0] + r_, q['o'][1] + r_)
            return (q['lo'][0], q['lo'][1], q['hi'][0], q['hi'][1])
        hits = []
        for q in ctx.props:
            if q is p or not q['solid'] or not q['hull'] or (q['name'] or '').startswith('tw_'): continue
            b = box_of(q)
            if b[0] < p['hi'][0] and b[2] > p['lo'][0] and b[1] < p['hi'][1] and b[3] > p['lo'][1] and q['hi'][2] > p['lo'][2] + 10 and q['lo'][2] < p['hi'][2]:
                hits.append(CP.short(q['model']))
        rec = dict(name=p['name'], relief=round(rel, 1), overlaps=hits[:6])
        out.append(rec)
        lines.append('parked %s: ground relief under the footprint %.0f u; solid props inside its box: %s' % (p['name'], rel, hits[:6] or 'none'))
        if hits: warn.append('%s overlaps %s' % (p['name'], hits[:3]))
    # the flight box inside the sky shell
    sk = [m for m in ctx.sc['meshes']]
    return dict(result=dict(spawns=out, tallest=round(float(hi)), over_trace=over), lines=lines, fail=fails, warn=warn, summary='%d air spawns' % len([r for r in out if 'spawn_z' in r]))


# ---------------------------------------------------------------- T8 spawns
def t8_spawns(ctx):
    G = ctx.G; lines = []; fails = []; warn = []
    def headroom(x, y, z):
        """free height over the floor at a point: the lowest surface above the knee (18 u), or the lowest blocker (walls widened 12 u)
        reaching above the knee"""
        c = CP.cell_of(x, y); fz = G.ground(x, y, z)
        above = G.Z[:, c][np.isfinite(G.Z[:, c]) & (G.Z[:, c] > fz + CP.BODY0)]
        bl = G.b_lo[(G.b_cell == c) & (G.b_hi > fz + CP.BODY0) & (G.b_lo < fz + 200)]
        cand = list(above) + [max(b, fz + CP.BODY0) for b in bl]
        return fz, (min(cand) - fz) if cand else 999.0
    out = {}
    for label, pts, gap, yaw in (('lobby', [(e['cls'], e['o'][0], e['o'][1], e['o'][2], e['a'][1]) for e in ctx.ents if e['cls'] in ('info_player_terrorist', 'info_player_counterterrorist')], 32.0, None),
                                 ('t posts', [(e['name'], e['o'][0], e['o'][1], e['o'][2], e['a'][1]) for e in ctx.ents if re.fullmatch(r'trench_t_\d+', e['name'])], 40.0, 0.0),
                                 ('ct posts', [(e['name'], e['o'][0], e['o'][1], e['o'][2], e['a'][1]) for e in ctx.ents if re.fullmatch(r'trench_ct_\d+', e['name'])], 40.0, 180.0)):
        low = []; close = []; off = []; face = []
        for k, (n, x, y, z, a) in enumerate(pts):
            fz, h = headroom(x, y, z)
            if not np.isfinite(fz) or z - fz > 24 or z - fz < -2: off.append((n, round(x), round(y), round(z), round(fz) if np.isfinite(fz) else None))
            elif h < 72: low.append((n, round(x), round(y), round(h)))
            for (n2, x2, y2, z2, a2) in pts[k + 1:]:
                if math.hypot(x - x2, y - y2) < gap and abs(z - z2) < 72: close.append((n, n2, round(math.hypot(x - x2, y - y2))))
            if yaw is not None and abs((a - yaw + 180) % 360 - 180) > 30: face.append((n, round(a)))
        out[label] = dict(n=len(pts), off_floor=off, low=low, close=close, facing=face)
        lines.append('%s: %d points, %d off the floor, %d with < 72 u headroom, %d pairs closer than %d u, %d not facing the enemy' % (label, len(pts), len(off), len(low), len(close), gap, len(face)))
        for kk in ('off_floor', 'low', 'close', 'facing'):
            if out[label][kk]: lines.append('   %s: %s' % (kk, out[label][kk][:8]))
        if off or low: fails.append('%s spawns' % label)
        if close or face: warn.append('%s: %d close pairs, %d facing' % (label, len(close), len(face)))
    return dict(result=out, lines=lines, fail=fails, warn=warn, summary=', '.join('%s %d' % (k, v['n']) for k, v in out.items()))


if __name__ == '__main__':
    argv = sys.argv[1:]
    if '--stage' in argv:
        k = argv.index('--stage'); A.model_roots = [os.path.abspath(argv[k + 1])] + list(A.model_roots); del argv[k:k + 2]
    if not argv or argv[0].startswith('--'): argv = [VMAP] + argv
    sys.exit(CP.cli(A, argv))
