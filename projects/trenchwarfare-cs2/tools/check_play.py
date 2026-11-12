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
  T2 fire steps every firestep prop: a standing spot on top (the highest support under a 32 x 32 player box free 72 u up, 16.5-40 u out
                from the wall, on the exact triangles), reached from the side's jump world (a node within 40 u and 54 u under it), and
                the eye 64 u over it clears the parapet (the highest solid 16-112 u in front, best of five lines)
  T3 ladders    climb volumes (toolsinvisibleladder): walkable ground at the bottom (in the world once open) and at the top; decorative
                ladder props without a volume are listed (the clips keep infantry in the trench by design)
  T4 dugouts    each shelter's dressing station is walked into from the trench on the exact triangles (a player box, 4-u steps,
                18-u step-ups; the 16-u grid cannot resolve the 30-u aisle between the stretchers) with >= 72 u over the floor there;
                check 1 then joins the station to its world at the shelter's mouth
  T5 no man's land  no walkable node of t / ct inside no man's land (|x| < 1450, |y| < 2750, above the galleries) in either state;
                wire props standing in a trench floor
  T6 mortar pits each pit's seats in one world, the pit closed off from both trench systems (crews are teleported), tube / table / box present
  T7 runways    air spawns (plane_<tg>_N + 1100): nothing within 300 u, a clear 3000-u lane on the spawn heading as wide as the side's
                aircraft (wing tips from the parked model) with 90 u over everything in it; stock trees by their real crowns (LOD0 render
                mesh read from the game's pak01 with create/s2/prop_mesh.mjs, cached), everything else from the visual grid; nothing
                over z 2900 in the flight box (the script's ground trace starts at 3000); parked planes on flat ground, clear of solid props
  T8 spawns     lobby: 64 spawns on the floor, >= 72 u headroom, >= 32 u apart; posts: headroom (a grid reading under 72 u is asked again
                of the exact triangles with a standing player box), >= 40 u apart, facing the enemy
  T9 sap mouths a player box walked through each sap mouth on the exact triangles (crouched / standing; planks in and out)
Owner: the user's objects (vis group tw_user, or ungrouped) are listed by checks 6 and 7, never counted (Adapter.user_owned).
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
    water_ok = ('duckboard', 'wire_', 'stump', 'log_fallen', 'tree_shattered', 'casings', 'helmet', 'tl_', 'debris_metal')   # debris: sunk in a crater pool, out of sight
    floors = {}

    def skip_entity(self, e):
        return e['o'][2] < -3000.0                     # script pools and precache props under the lobby

    def user_owned(self, p):
        """the user's own objects (vis group tw_user, or ungrouped): the remaster never changes them, so check 6 / 7 list them only"""
        return (p.get('vg') or '') in ('tw_user', '')

    def clip_tag(self, p):
        m = p['model']
        if any(k in m for k in ('revet_', 'firestep', 'tunnel_set', 'shelter', 'hangar')): return 'bury'      # set into the trench walls / the bank by design
        if any(k in m for k in ('stump_', 'helmet_', 'debris_metal', 'aztec_river_rock')): return 'bury'   # sunk into the churned mud as dressing
        # the generator's scatter dressing sunk in the shell-torn ground (make_map scatter(): zoff -2..-4, tilt 3-8 on the origin's ground,
        # blind to the crater it lands in): logs across flooded shell holes with their ends in the banks, shell piles, crates, a cart
        # wheel and wire in the mud of no man's land; and the pit breastworks' sandbag courses bedded into the mound where it dips
        # (renders out/review3/views/before_clip_*.png and their share of vertices under the ground: docs/REVIEW_WORLD_3.md "Clipping")
        if '/log_fallen' in m: return 'bury'
        if any(k in m for k in ('/shell_pile', '/casings')): return 'bury'          # a low heap: its box's corners stand in the slope it lies on
        if abs(p['o'][0]) < NML_X + 50 and any(k in m for k in ('/wreck_wheel', '/crate_shells', '/wire_coil', '/wire_fence')): return 'bury'
        if '/sandbag_' in m and abs(abs(p['o'][0]) - MORTAR_X) < 260 and abs(p['o'][1]) < 1900: return 'bury'
        if any(k in m for k in ('ladder', 'tl_lantern', '_prop.vmdl', 'tw_prop')): return 'float'   # leans on the wall / hangs from a frame / on the plane's nose
        return None

    def inplay(self, x, y, z):
        return abs(x) <= 7424 and abs(y) <= 6400

    # ---------------------------------------------------------------- points
    def worlds(self, ctx):
        sap_links(ctx)                                 # the sap mouths, proven on a fine grid, join the open walk graph (T9)
        w = {}
        for tg in ('t', 'ct'):
            # a dressing station inside a shelter whose walk-in the fine probe proves (T4) joins its world at the shelter's mouth:
            # the grid's 12-u widened blockers close the 30-u aisle between the two stretchers
            w[tg] = ctx.points(r'trench_%s_\d+' % tg) + [heal_point(ctx, h) for h in ctx.points(r'heal_%s_\d+' % tg)]
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
        """(side, prop, stand point (x, y, z) or None): where a player stands to fire: the highest support under a 32 x 32 player box
        that is free 72 u up, the box set 16.5 .. 40 u out from the wall face along the step's middle (the step's upper tier is only
        16 u deep: a player stands on it with the box overhanging the lower tier). Was: the 16-u grid at the prop's box centre, which
        on the CT side lands on the user's clip stair in front of the step 12 u under the tier (REVIEW_WORLD_1 M6, REVIEW_WORLD_3 T2)"""
        key = id(ctx)
        if _FS.get('key') == key: return _FS['out']
        out = []
        for p in ctx.props:
            if 'models/tw/firestep/' not in p['model']: continue
            tg = 't' if p['o'][0] < 0 else 'ct'
            yaw = math.radians(p['a'][1]); fx, fy = math.sin(yaw), -math.cos(yaw)     # local -y (toward the trench) in world space
            best = None
            for d in (16.5, 20.0, 24.0, 28.0, 32.0, 40.0):
                x, y = p['o'][0] + fx * d, p['o'][1] + fy * d
                z = exact_support(ctx, x, y, p['hi'][2] + 4.0)
                if not np.isfinite(z) or z < p['lo'][2] - 30: continue
                if not box_free(ctx, (x - 16.0, y - 16.0, z + 1.0), (x + 16.0, y + 16.0, z + 72.0)): continue
                if best is None or z > best[2] + 0.5: best = (x, y, z)
            out.append((tg, p, best))
        _FS.update(key=key, out=out)
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
                ('T5', "no man's land", t5_nml), ('T6', 'mortar pits', t6_pits), ('T7', 'runways and plane lanes', t7_air), ('T8', 'spawns', t8_spawns),
                ('T9', 'sap mouths (fine probe)', t9_saps)]


# ---------------------------------------------------------------- T9: the sap mouths on a fine grid
# The user's benches in each sap mouth (tw_user, 24 tl_bench) bridge the seam between the trench floor and the tunnel mesh: a low row of
# steps down from the trench floor (12 u above the tunnel floor at the portal) and an upper row that closes the ground over the mouth.
# The 16-u walk grid cannot resolve that seam (a 22-degree tunnel floor, bench tops 4-8 u apart, blockers widened 12 u), so it reported
# the galleries unreachable although players walk in (crouched: the upper benches hang 59-62 u over the trench floor). This probe walks a
# CS2 player box (32 x 32, 72 u standing / 54 u crouched, 18-u steps) over the exact triangles of the mouth on a 4-u grid, both ways,
# with the undergroundopen planks out (open) and in (closed). When the crouched box gets through both ways once open and not while
# closed, the coarse open walk graph gets a two-way link across the mouth (the closed graph is computed before the link is added).
SAP_XC, SAP_Y_TRENCH, SAP_Y_TUNNEL = 2144.0, -2776.0, -2888.0
SAP_REGION = (-2940.0, -2740.0, -220.0, 80.0)          # y0, y1, z0, z1 of the probe region (x: SAP_XC +- 96)
HULL_W, HULL_STAND, HULL_CROUCH, STEP_H = 16.0, 72.0, 54.0, 18.0
_SAP = {}


def _tri_box(T, lo, hi):
    """bool per triangle (N, 3, 3): does it intersect the box lo..hi (separating axis test, Akenine-Moller)"""
    if not len(T): return np.zeros(0, bool)
    c = (np.asarray(lo) + np.asarray(hi)) / 2.0; h = (np.asarray(hi) - np.asarray(lo)) / 2.0
    v = T - c
    e = np.stack([v[:, 1] - v[:, 0], v[:, 2] - v[:, 1], v[:, 0] - v[:, 2]], 1)
    ok = np.ones(len(T), bool)
    for a in range(3):                                    # box face normals
        ok &= ~((v[:, :, a].min(1) > h[a]) | (v[:, :, a].max(1) < -h[a]))
    n = np.cross(e[:, 0], e[:, 1])                        # triangle normal
    r = (np.abs(n) * h).sum(1); d = (n * v[:, 0]).sum(1)
    ok &= np.abs(d) <= r
    I = np.eye(3)
    for i in range(3):
        for j in range(3):
            ax = np.cross(e[:, j], I[i])
            p = (v * ax[:, None, :]).sum(2)
            rr = (np.abs(ax) * h).sum(1)
            ok &= ~((p.min(1) > rr) | (p.max(1) < -rr))
    return ok


def _sap_probe(sc, s, closed):
    """walk a player box through the sap mouth of side s (+1 CT, -1 T): {hull: (in, out)} for standing and crouched"""
    y0, y1, z0, z1 = SAP_REGION
    x0, x1 = s * SAP_XC - 96.0, s * SAP_XC + 96.0
    if x0 > x1: x0, x1 = x1, x0
    T = sc['tris']; src = sc['srcs']; kd = sc['kinds']
    lo = T.min(1); hi = T.max(1)
    rem = np.array([p['removable'] for p in sc['props']] + [False], bool)
    m = (hi[:, 0] >= x0 - 20) & (lo[:, 0] <= x1 + 20) & (hi[:, 1] >= y0 - 20) & (lo[:, 1] <= y1 + 20) & (hi[:, 2] >= z0) & (lo[:, 2] <= z1) & (kd != CP.K_WATER)
    if not closed: m &= ~((src >= 0) & rem[np.clip(src, 0, len(rem) - 1)])
    T = T[m]; lo = lo[m]; hi = hi[m]
    # columns on a 2-u lattice: every crossing z (any face) for the ground under the box
    gx = np.arange(x0 - 18, x1 + 19, 2.0); gy = np.arange(y0 - 18, y1 + 19, 2.0)
    cols = [[[] for _ in gy] for _ in gx]
    for t in T:
        a, b, c = t
        d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(d) < 1e-9: continue
        i0 = max(0, int(np.ceil((min(a[0], b[0], c[0]) - gx[0]) / 2.0))); i1 = min(len(gx) - 1, int(np.floor((max(a[0], b[0], c[0]) - gx[0]) / 2.0)))
        j0 = max(0, int(np.ceil((min(a[1], b[1], c[1]) - gy[0]) / 2.0))); j1 = min(len(gy) - 1, int(np.floor((max(a[1], b[1], c[1]) - gy[0]) / 2.0)))
        if i1 < i0 or j1 < j0: continue
        X, Y = np.meshgrid(gx[i0:i1 + 1], gy[j0:j1 + 1], indexing='ij')
        l1 = ((b[1] - c[1]) * (X - c[0]) + (c[0] - b[0]) * (Y - c[1])) / d
        l2 = ((c[1] - a[1]) * (X - c[0]) + (a[0] - c[0]) * (Y - c[1])) / d
        l3 = 1 - l1 - l2
        inn = (l1 >= -1e-6) & (l2 >= -1e-6) & (l3 >= -1e-6)
        Z = l1 * a[2] + l2 * b[2] + l3 * c[2]
        for ii, jj in zip(*np.nonzero(inn)): cols[i0 + ii][j0 + jj].append(float(Z[ii, jj]))
    kmax = max(1, max(len(cc) for row in cols for cc in row))
    CZ = np.full((len(gx), len(gy), kmax), np.inf)
    for i, row in enumerate(cols):
        for j, cc in enumerate(row):
            if cc: CZ[i, j, :len(cc)] = cc

    def ground(cx, cy, zfrom):
        """the highest face under the box footprint at or below zfrom (a box traced down from there)"""
        i0 = max(0, int(np.ceil((cx - HULL_W + 0.5 - gx[0]) / 2.0))); i1 = min(len(gx) - 1, int(np.floor((cx + HULL_W - 0.5 - gx[0]) / 2.0)))
        j0 = max(0, int(np.ceil((cy - HULL_W + 0.5 - gy[0]) / 2.0))); j1 = min(len(gy) - 1, int(np.floor((cy + HULL_W - 0.5 - gy[0]) / 2.0)))
        z = CZ[i0:i1 + 1, j0:j1 + 1]
        z = z[z <= zfrom + 0.01]
        return float(z.max()) if z.size else -np.inf

    def free(cx, cy, zb, H):
        blo = (cx - HULL_W + 0.5, cy - HULL_W + 0.5, zb + 1.0); bhi = (cx + HULL_W - 0.5, cy + HULL_W - 0.5, zb + H)
        mm = (hi[:, 0] >= blo[0]) & (lo[:, 0] <= bhi[0]) & (hi[:, 1] >= blo[1]) & (lo[:, 1] <= bhi[1]) & (hi[:, 2] >= blo[2]) & (lo[:, 2] <= bhi[2])
        return not _tri_box(T[mm], blo, bhi).any()

    def bfs(start, H):
        sx, sy, sz = start
        q = [(sx, sy, sz)]; seen = {(round(sx), round(sy), round(sz / 2.0))}; out = [(sx, sy, sz)]
        while q:
            cx, cy, cz = q.pop()
            for dx, dy in ((4, 0), (-4, 0), (0, 4), (0, -4), (4, 4), (4, -4), (-4, 4), (-4, -4)):
                nx, ny = cx + dx, cy + dy
                if not (x0 <= nx <= x1 and y0 <= ny <= y1): continue
                nz = ground(nx, ny, cz + STEP_H)
                if not np.isfinite(nz) or nz < z0 or nz < cz - 300: continue
                key = (round(nx), round(ny), round(nz / 2.0))
                if key in seen: continue
                # the 2-u lattice can miss a raised edge or the crest of a tilted bench by a unit or two: settle on the first free height
                # up to 4 u higher (the engine steps onto it)
                nz = next((nz + dz for dz in (0.0, 2.0, 4.0) if nz + dz <= cz + STEP_H and free(nx, ny, nz + dz, H)), None)
                if nz is None: continue
                if nz < cz and not free(nx, ny, cz, H): continue          # stepping off: the box moves over at its own height first
                key = (round(nx), round(ny), round(nz / 2.0))
                if key in seen: continue
                seen.add(key); q.append((nx, ny, nz)); out.append((nx, ny, nz))
        return out

    a = (s * SAP_XC, SAP_Y_TRENCH); b = (s * SAP_XC, SAP_Y_TUNNEL)
    za = ground(a[0], a[1], -30.0); zb = ground(b[0], b[1], -60.0)
    res = dict(trench=(a[0], a[1], za), tunnel=(b[0], b[1], zb))
    near = lambda pts, p: any(abs(x - p[0]) <= 8 and abs(y - p[1]) <= 8 and abs(z - p[2]) <= 20 for (x, y, z) in pts)
    for name, H in (('standing', HULL_STAND), ('crouched', HULL_CROUCH)):
        fwd = bfs((a[0], a[1], za), H); back = bfs((b[0], b[1], zb), H)
        res[name] = dict(walk_in=near(fwd, res['tunnel']), walk_out=near(back, res['trench']), states=len(fwd) + len(back))
        if _SAP.get('debug'): res[name].update(fwd=fwd, back=back, free=free, ground=ground)
    return res


def sap_links(ctx):
    """run the fine probe for both mouths (open and closed) once per grid; add the open-state links"""
    G = ctx.G
    if getattr(G, '_sap_done', False): return _SAP.get(id(G))
    G._sap_done = True
    G.closed()                                         # the closed graph first: a link must never bypass the planks
    out = {}
    from scipy import sparse
    add_r, add_c = [], []
    for s, tg in ((1, 'ct'), (-1, 't')):
        r_open = _sap_probe(ctx.sc, s, False); r_closed = _sap_probe(ctx.sc, s, True)
        ok = r_open['crouched']['walk_in'] and r_open['crouched']['walk_out'] and not (r_closed['crouched']['walk_in'] or r_closed['crouched']['walk_out'])
        link = None
        if ok:
            pa, pb = r_open['trench'], r_open['tunnel']
            na = G.nodes_near(pa[0], pa[1], pa[2] - 2.0, 12.0, 12.0); nb = G.nodes_near(pb[0], pb[1], pb[2] - 2.0, 12.0, 12.0)
            for u in na:
                for v in nb: add_r += [u, v]; add_c += [v, u]
            link = dict(trench_nodes=len(na), tunnel_nodes=len(nb))
        out[tg] = dict(open=r_open, closed=r_closed, link=link, ok=ok)
    if add_r:
        n = G.walk.shape[0]
        G.walk = (G.walk + sparse.csr_matrix((np.ones(len(add_r), np.int8), (add_r, add_c)), shape=(n, n))).tocsr()
        G.walk.data[:] = 1
    _SAP[id(G)] = out
    return out


def t9_saps(ctx):
    res = sap_links(ctx) or {}
    lines, fails, warn = [], [], []
    for tg, r in res.items():
        o, c = r['open'], r['closed']
        f = lambda d: '%s/%s' % ('in' if d['walk_in'] else '-', 'out' if d['walk_out'] else '-')
        lines.append('   %s sap (trench z %.1f -> tunnel z %.1f): open standing %s, crouched %s; closed standing %s, crouched %s; link %s'
                     % (tg, o['trench'][2], o['tunnel'][2], f(o['standing']), f(o['crouched']), f(c['standing']), f(c['crouched']),
                        'added (%d x %d nodes)' % (r['link']['trench_nodes'], r['link']['tunnel_nodes']) if r['link'] else 'NOT added'))
        if not r['ok']: fails.append('%s sap' % tg)
        if r['ok'] and not (o['standing']['walk_in'] and o['standing']['walk_out']): warn.append('%s sap: crouch to enter (standing box blocked)' % tg)
    out = {tg: dict(open={k: v for k, v in r['open'].items()}, closed={k: v for k, v in r['closed'].items()}, link=r['link'], ok=r['ok']) for tg, r in res.items()}
    return dict(result=out, lines=lines, fail=fails, warn=warn, summary=', '.join('%s %s' % (tg, 'crouch ok' if r['ok'] else 'FAIL') for tg, r in res.items()))


A = Trench()
_FS = {}
_EX = {}


def _exact(ctx):
    """the scene's solid triangles (water left out, the removable blockers in: the round start) with their boxes, once per scene"""
    if _EX.get('key') != id(ctx):
        sc = ctx.sc; T = sc['tris']; m = sc['kinds'] != CP.K_WATER
        T = T[m]
        _EX.clear(); _EX.update(key=id(ctx), T=T, lo=T.min(1), hi=T.max(1), src=sc['srcs'][m])
    return _EX


def box_free(ctx, lo, hi, ignore=()):
    """no solid triangle (and no stock tree trunk) intersects the box lo..hi"""
    E = _exact(ctx)
    mm = (E['hi'][:, 0] >= lo[0]) & (E['lo'][:, 0] <= hi[0]) & (E['hi'][:, 1] >= lo[1]) & (E['lo'][:, 1] <= hi[1]) & (E['hi'][:, 2] >= lo[2]) & (E['lo'][:, 2] <= hi[2])
    idx = np.nonzero(mm)[0]
    if len(ignore): idx = idx[~np.isin(E['src'][idx], list(ignore))]
    if len(idx) and _tri_box(E['T'][idx], lo, hi).any(): return False
    for (tx, ty, z0, z1, r, pi) in ctx.sc['trunks']:
        if z0 < hi[2] and z1 > lo[2] and math.hypot(max(lo[0] - tx, 0, tx - hi[0]), max(lo[1] - ty, 0, ty - hi[1])) < r: return False
    return True


def exact_support(ctx, x, y, zfrom, half=15.5, step=3.875):
    """the highest up-facing solid surface under a player footprint (x +- half, y +- half) at or below zfrom, from the exact triangles
    on a 9 x 9 lattice"""
    E = _exact(ctx)
    mm = (E['hi'][:, 0] >= x - half) & (E['lo'][:, 0] <= x + half) & (E['hi'][:, 1] >= y - half) & (E['lo'][:, 1] <= y + half) & (E['lo'][:, 2] <= zfrom)
    T = E['T'][mm]
    if not len(T): return -np.inf
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); T = T[n[:, 2] > 1e-6]
    if not len(T): return -np.inf
    g = np.arange(-half, half + 1e-6, step)
    X, Y = np.meshgrid(x + g, y + g, indexing='ij'); X = X.ravel(); Y = Y.ravel()
    a, b, c = T[:, 0], T[:, 1], T[:, 2]
    d = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1])
    d = np.where(np.abs(d) < 1e-9, 1e-9, d)
    l1 = ((b[:, 1] - c[:, 1])[:, None] * (X[None] - c[:, 0][:, None]) + (c[:, 0] - b[:, 0])[:, None] * (Y[None] - c[:, 1][:, None])) / d[:, None]
    l2 = ((c[:, 1] - a[:, 1])[:, None] * (X[None] - c[:, 0][:, None]) + (a[:, 0] - c[:, 0])[:, None] * (Y[None] - c[:, 1][:, None])) / d[:, None]
    l3 = 1 - l1 - l2
    Z = l1 * a[:, 2][:, None] + l2 * b[:, 2][:, None] + l3 * c[:, 2][:, None]
    ok = (l1 >= -1e-6) & (l2 >= -1e-6) & (l3 >= -1e-6) & (Z <= zfrom + 0.01)
    Z = np.where(ok, Z, -np.inf)
    return float(Z.max())


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
        # the tier is 16 u deep against the wall, too narrow for a 16-u grid node: the step counts as reached when a node of the side's
        # jump world lies within 40 u of the stand point and no more than a jump (54 u) under it
        ids = ctx.nodes(x, y, z, 40.0, 28.0, dz=-26.0, state='closed')
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
_SH = {}


def shelter_probe(ctx):
    """the walk into each shelter on the exact triangles: a player box (31 x 31, 72 u standing, 18-u steps) moved 4 u at a time along
    the shelter's axis, from 40 u outside the mouth (the support trench floor) to the dressing station inside, onto the highest support
    under it each step (the stretchers' edges are 7-8 u up). -> {heal name: dict(ok, mouth (x, y, z), headroom, ...)}"""
    if _SH.get('key') == id(ctx): return _SH['res']
    res = {}
    for p in ctx.props:
        if 'models/tw/shelter/' not in p['model']: continue
        tg = 't' if p['o'][0] < 0 else 'ct'
        heal = [e for e in ctx.ents if re.fullmatch(r'heal_%s_\d+' % tg, e['name']) and math.hypot(e['o'][0] - p['o'][0], e['o'][1] - p['o'][1]) < 160]
        if not heal: continue
        h = heal[0]
        yaw = math.radians(p['a'][1]); ux, uy = math.cos(yaw), math.sin(yaw)              # local +x: into the shelter (its mouth is at -48)
        lx_h = (h['o'][0] - p['o'][0]) * ux + (h['o'][1] - p['o'][1]) * uy
        ly_h = -(h['o'][0] - p['o'][0]) * uy + (h['o'][1] - p['o'][1]) * ux
        pt = lambda lx: (p['o'][0] + ux * lx - uy * ly_h, p['o'][1] + uy * lx + ux * ly_h)
        x, y = pt(-88.0); z = exact_support(ctx, x, y, p['o'][2] + 40.0)
        mouth = (x, y, z); ok = np.isfinite(z); worst = None; rise = 0.0
        for lx in np.arange(-84.0, lx_h + 0.01, 4.0):
            if not ok: break
            x, y = pt(lx)
            nz = exact_support(ctx, x, y, z + 18.0)
            if not np.isfinite(nz) or nz < z - 60: ok = False; worst = ('no floor', round(lx)); break
            if not box_free(ctx, (x - 15.5, y - 15.5, nz + 1.0), (x + 15.5, y + 15.5, nz + 72.0)): ok = False; worst = ('blocked', round(lx), round(nz, 1)); break
            rise = max(rise, nz - mouth[2]); z = nz
        head = None
        if ok:
            x, y = pt(lx_h); fz = z
            head = 72.0
            while head < 120 and box_free(ctx, (x - 15.5, y - 15.5, fz + 1.0), (x + 15.5, y + 15.5, fz + head + 1.0)): head += 1.0
        res[h['name']] = dict(ok=bool(ok), mouth=mouth, shelter=[round(v) for v in p['o']], side=tg, headroom=head, floor_rise=round(rise, 1), stop=worst)
    _SH.update(key=id(ctx), res=res)
    return res


def heal_point(ctx, pt):
    """a dressing station's point for the walk graph: the shelter's mouth when the fine probe proves the walk in, else the station"""
    r = shelter_probe(ctx).get(pt[0])
    if r and r['ok']: return ('%s (mouth; walk-in proven by T4)' % pt[0], r['mouth'][0], r['mouth'][1], r['mouth'][2] + 8.0)
    return pt


def t4_dugouts(ctx):
    """each shelter's dressing station can be walked into from its trench (T4 fine probe) with >= 72 u over the floor there, and the
    shelter's mouth is in the side's walkable trench"""
    lines = []; fails = []; out = []
    for name, r in sorted(shelter_probe(ctx).items()):
        tg = r['side']
        W = ctx.world_mask(tg, 'closed')
        ids = ctx.nodes(r['mouth'][0], r['mouth'][1], r['mouth'][2] + 8.0, 40.0, 30.0, state='closed') if np.isfinite(r['mouth'][2]) else []
        inn = any(W[i] for i in ids)
        rec = dict(heal=name, at=r['shelter'], side=tg, walk_in=r['ok'], mouth_in_trench=inn, headroom=r['headroom'], floor_rise=r['floor_rise'], stop=r['stop'])
        out.append(rec)
        lines.append('shelter %s (%s): walk-in %s (floor rise %.0f u%s), mouth in the walkable trench %s; %s headroom %s u'
                     % (rec['at'], tg, 'ok' if r['ok'] else 'BLOCKED', r['floor_rise'], (', stopped: %s' % (r['stop'],)) if r['stop'] else '', inn, name, r['headroom']))
        if not r['ok'] or not inn or (r['headroom'] or 0) < 72: fails.append('shelter %s' % rec['at'][:2])
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
_TM = {}
_MESH_JS = r'''
import fs from "node:fs"; import { pathToFileURL } from "node:url";
const [repo, vpk, out, ...models] = process.argv.slice(2);
const { extractProp } = await import(pathToFileURL(repo + "/create/s2/prop_mesh.mjs").href);
const { readInput } = await import(pathToFileURL(repo + "/create/s2/vpk.mjs").href);
const res = {};
for (const m of models) {
  try { const r = await extractProp(readInput(m + "_c", vpk)); const P = []; for (const me of r.meshes) for (const v of me.P) P.push(+v.toFixed(2)); res[m] = P; }
  catch (e) { res[m] = { error: String(e && e.message || e).slice(0, 200) }; }
}
fs.writeFileSync(out, JSON.stringify(res));
'''


def tree_mesh(q):
    """world-space vertices of a stock tree's LOD0 render mesh (create/s2/prop_mesh.mjs on the game's pak01, cached per model in the
    cache folder), or None when it cannot be read"""
    import json, subprocess, tempfile
    mdl = q['model']
    if mdl not in _TM:
        cp = os.path.join(A.cache_dir, 'stock_mesh_%s.npy' % re.sub(r'[^A-Za-z0-9_]+', '_', mdl))
        if not os.path.exists(cp):
            try:
                os.makedirs(A.cache_dir, exist_ok=True)
                js = os.path.join(tempfile.gettempdir(), 'tw_tree_mesh.mjs'); open(js, 'w').write(_MESH_JS)
                tmp = cp + '.json'
                subprocess.run(['node', js, REPO.replace('\\', '/'), A.vpk_dir.replace('\\', '/'), tmp, mdl], capture_output=True, timeout=120,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                v = json.load(open(tmp))[mdl]; os.remove(tmp)
                if isinstance(v, dict): raise RuntimeError(v.get('error'))
                np.save(cp, np.array(v, np.float32).reshape(-1, 3))
            except Exception as ex:
                print('    T7: no mesh for %s (%s): its bounds stand in' % (mdl, str(ex)[:120]))
                _TM[mdl] = None
        if mdl not in _TM: _TM[mdl] = np.load(cp).astype(float)
    P = _TM[mdl]
    if P is None or not len(P): return None
    return (P * np.array(q['s'])) @ CP.rot_matrix(q['a']).T + np.array(q['o'])


def vis_without_trees(ctx):
    """Sight.vis (the highest visual thing per cell) without the stock trees: their crowns are measured from their meshes"""
    G = ctx.G
    hs = np.where(G.terr > -1e8, G.terr, G.Z[0]); hs = np.where(np.isfinite(hs), hs, -1e5)
    solid = hs.copy()
    m = (G.s_kind == CP.K_WORLD) | (G.s_kind == CP.K_HULL); np.maximum.at(solid, G.s_cell[m], G.s_z[m])
    m = (G.b_kind == CP.K_WORLD) | (G.b_kind == CP.K_HULL); np.maximum.at(solid, G.b_cell[m], G.b_hi[m])
    vis = solid.copy()
    for p in ctx.props:
        if p['removable'] or (CP.has(p['model'], A.trees) and not p['ours']): continue
        ex = max(p['hi'][0] - p['lo'][0], p['hi'][1] - p['lo'][1])
        r = ex * (0.30 if CP.has(p['model'], A.trees) else 0.42)
        cx, cy = (p['lo'][0] + p['hi'][0]) / 2, (p['lo'][1] + p['hi'][1]) / 2
        c, _, _ = G.disc(cx, cy, max(r, CP.CELL * 0.6))
        if len(c): np.maximum.at(vis, c, p['hi'][2])
    return vis.reshape(CP.NX, CP.NY)


def t7_air(ctx):
    G = ctx.G; SG = ctx.SG; lines = []; fails = []; warn = []; out = []
    NX, NY, X0, Y0, CELL = CP.NX, CP.NY, CP.X0, CP.Y0, CP.CELL
    V = SG.vis
    def vis_at(x, y):
        i = int((x - X0) // CELL); j = int((y - Y0) // CELL)
        return float(V[i, j]) if 0 <= i < NX and 0 <= j < NY else -1e9
    # the lane: the spawn's 3000 u straight ahead, as wide as the side's aircraft (wing tip to wing tip, from the parked model's bounds),
    # NOSE u of clearance over everything in it. Stock trees count with their real crowns (LOD0 render mesh from the game's pak01,
    # tree_mesh()); the grid's stand-in for them (a disc of 0.3 x the bounds at the full height) put the whole box width at the crown
    # top (REVIEW_WORLD_3 T7). Everything else is the visual grid (the highest surface or prop top per 16-u cell).
    span = {}
    for p in ctx.props:
        mm = re.fullmatch(r'tw_plane_(t|ct)_\d+', p['name'] or '')
        if mm: span[mm.group(1)] = max(span.get(mm.group(1), 0.0), abs(p['mhi'][1] - p['mlo'][1]) / 2.0 * p['s'][1])
    VN = vis_without_trees(ctx)
    def vn_at(x, y):
        i = int((x - X0) // CELL); j = int((y - Y0) // CELL)
        return float(VN[i, j]) if 0 <= i < NX and 0 <= j < NY else -1e9
    stock_trees = [q for q in ctx.props if CP.has(q['model'], A.trees) and not q['ours']]
    for tg in ('t', 'ct'):
        hw = span.get(tg, 160.0)
        for (n, x, y, z) in ctx.points(r'plane_%s_\d+' % tg):
            sz = z + SPAWN_ALT
            near = max(vis_at(x + dx, y + dy) for dx in np.arange(-300, 301, 32) for dy in np.arange(-300, 301, 32) if dx * dx + dy * dy <= 300 * 300)
            f = -1.0 if tg == 'ct' else 1.0
            ax0, ax1 = (x, x + 3000.0) if f > 0 else (x - 3000.0, x)
            lane, lx, ly, who = -1e9, x, y, []
            for d in np.arange(0, 3000, 16):
                for o in np.arange(-hw, hw + 1, 16):
                    v = vn_at(x + f * d, y + o)
                    if v > lane: lane, lx, ly, who = v, x + f * d, y + o, None
            for q in stock_trees:
                if q['hi'][2] < lane or q['hi'][0] < ax0 or q['lo'][0] > ax1 or q['hi'][1] < y - hw or q['lo'][1] > y + hw: continue
                W = tree_mesh(q)
                if W is None:                                        # no mesh: the grid's disc stands in
                    W = np.array([[q['o'][0], q['o'][1], q['hi'][2]]])
                sel = (W[:, 0] >= ax0) & (W[:, 0] <= ax1) & (np.abs(W[:, 1] - y) <= hw)
                if sel.any():
                    k = np.argmax(np.where(sel, W[:, 2], -1e9))
                    if W[k, 2] > lane: lane, lx, ly, who = float(W[k, 2]), float(W[k, 0]), float(W[k, 1]), [CP.short(q['model']) + ' %d' % q['i']]
            if who is None:
                who = [CP.short(q['model']) for q in ctx.props if q['hi'][2] >= lane - 1 and q['lo'][0] - 64 <= lx <= q['hi'][0] + 64 and q['lo'][1] - 64 <= ly <= q['hi'][1] + 64][:3]
            rec = dict(name=n, spawn_z=round(sz), clear_r300=round(sz - near), lane_clear=round(sz - lane - NOSE), lane_top=[round(lx), round(ly), round(lane)], lane_by=who,
                       lane_half_width=round(hw))
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
    lines.append('air spawns: ' + ', '.join('%s z %d (r300 clear by %d, lane +-%d u clear by %d; highest under the lane %s %s)' % (r['name'], r['spawn_z'], r['clear_r300'], r['lane_half_width'], r['lane_clear'], r['lane_top'], r['lane_by']) for r in out))
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
        h = (min(cand) - fz) if cand else 999.0
        # the grid's blockers are widened 12 u (a barrel beside the post reads as over it): ask the exact triangles whether a standing
        # player box (32 x 32, from step height to 72 u over the floor) fits on the post
        if h < 72 and np.isfinite(fz) and box_free(ctx, (x - 16.0, y - 16.0, fz + CP.BODY0), (x + 16.0, y + 16.0, fz + 72.0)): h = 72.0
        return fz, h
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
    if any(a in ('-h', '--help') for a in argv): print(__doc__); sys.exit(2)      # (was: ran the whole check on the user's map)
    if '--stage' in argv:
        k = argv.index('--stage'); A.model_roots = [os.path.abspath(argv[k + 1])] + list(A.model_roots); del argv[k:k + 2]
    if not argv or argv[0].startswith('--'): argv = [VMAP] + argv
    sys.exit(CP.cli(A, argv))
