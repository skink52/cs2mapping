"""World patch 3 (13 Nov 2026, docs/REVIEW_WORLD_3.md): the real problems check_play still found in the generated content of the chained
map, as one guarded delta patch. Reads the input map (never writes it); writes the patched copy, the guard's target list and a report.

usage: python tools/patch_world_3.py [--in V] [--out V] [--targets T] [--report R] [--no-guard]
  defaults: --in out/step9/chain/4_seams.vmap, --out out/mg_trenchwarfare_world3.vmap, --targets <out>.targets.json, --report <out>.report.json
  then (here unless --no-guard): python tools/patch_guard.py <in> <out> <targets> --strict
Chain: patch_world_1 -> patch_models -> patch_terrain -> patch_seams -> patch_world_3 -> patch_sounds -> patch_nav.

What it changes (generated objects only, vis group tw_gen; every target matched on nodeID + class + model + origin within 2 u + vis group,
or a mismatch stops the patch before anything is written; the user's objects, tw_user or ungrouped, are never touched):
  T7  air lanes   four tree_poplar_mature_02 by the CT aerodrome (scale 1.08-1.13, the tallest trees by either airfield; the T side
                  has none over 0.94-1.0 mature_01) stand with their crowns in the take-off lanes of plane_ct_2 / _3 / _5 (the spawn
                  1100 u over plane_ct_N, flying -x, wing tips +-169 u). Each is scaled down by the minimum that leaves 100 u (the
                  checker's 90-u nose margin + 10) between every CT spawn and its crown (measured on the tree's LOD0 render mesh):
                  -1.6 .. -7.6 %. Nothing moves; the T lanes are untouched.
  W2b pit_t_2     the stock shell rack (ammo_artillery_small_01) stood across the walk between crew seats a and b with its long side
                  into the pit (15 u between it and the plotting table: a 32-u player cannot pass; seat a was walled in). Turned 90
                  deg to lie along the breastwork, 8 u further out (its outer end stays bedded in the sandbags as before): 41 u to the
                  table, 3 u clear of seat a's player box.
  L4  poplar      a living tree_poplar_mature_02 (-637, -3582) stood in the middle of a generated crater pool (8.7 u of water round
                  the trunk, the pool centred on it): moved straight out of the pool by the minimum that puts its trunk 8 u past the
                  water's edge, set on the ground there (the scatter's own -6 u).
  W8  pool edges  generated no man's land crater pools (12-gon water prisms, tw_gen; the generator sized them from the crater, step 7
                  then roughened the ground) whose rim stands over lower ground (lips of 3-22 u: the sheet's edge hangs in the air):
                  every rim vertex (and the bottom vertex under it) moves along its own ray from the pool's centre, in or out, to the
                  nearest spot where the ground is no more than 1 u under the water line, with both rim edges (every 4 u) meeting it
                  too, the rim kept convex (the 12-gon top face is fan-triangulated); only when no such rim exists at the pool's
                  level is the level lowered, 1 u at a time (at most 25), never to within 2 u of another sheet over the same ground
                  (z-fight). A pool that
                  would keep under 30 % of its area, or cannot be closed, is reported and left as it was. Nothing is added. The
                  user's own pools (tw_user) are not touched (check_play lists them).
Every new value follows from the input map alone (same input, same bytes: vmapedit's random is seeded from the input CRC, as in the
other stages). Level: "simulated" (check_play, patch_guard --strict). AI-generated (Claude) for skink52.
"""
import argparse, json, math, os, subprocess, sys, time, zlib
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
OUT = os.path.join(PROJ, 'out')
_spec = importlib.util.spec_from_file_location('tw_patch_seams', os.path.join(HERE, 'patch_seams.py'))
PS = importlib.util.module_from_spec(_spec); sys.modules['tw_patch_seams'] = PS; _spec.loader.exec_module(PS)   # mesh helpers, exact terrain
CS = PS.CS
import vmapedit as V      # noqa: E402  (the repo's, set up by check_seams)
import dmx                # noqa: E402
import safepath           # noqa: E402
import numpy as np        # noqa: E402

GROUP = 'tw_gen'
TOL = 2.0
POPLAR = 'models/foliage/trees/poplar/tree_poplar_mature_02.vmdl'
RACK = 'models/generic/ammo_artillery_01/ammo_artillery_small_01.vmdl'
# (nodeID, model, origin, old uniform scale, new scale, why): the new scale is the largest that keeps every CT lane 100 u over the
# crown (bisection on the LOD0 render mesh, docs/REVIEW_WORLD_3.md T7)
TREES = [(126436, POPLAR, (4127.5, -224.4, -5.8), 1.1313, 1.0449, 'T7 plane_ct_2 lane (was 74 u short of the margin)'),
         (126348, POPLAR, (3894.0, -490.3, 0.0), 1.0987, 1.0389, 'T7 plane_ct_2 lane (48 u short)'),
         (126353, POPLAR, (3888.6, -15.3, -12.4), 1.0807, 1.0551, 'T7 plane_ct_3 lane (15 u short)'),
         (126442, POPLAR, (4277.5, 572.8, -22.6), 1.0854, 1.0686, 'T7 plane_ct_5 lane (6 u short with the wing span)')]
# (nodeID, model, origin, yaw, yaw +, move): pit_t_2's rack, turned along the breastwork
RACK_T = (123716, RACK, (-3360.78, -789.26, -30.24), 262.0, 90.0, (-8.0, 0.0, 0.0))
# the poplar in the pool and the pool (nodeIDs)
POOL_TREE = (125694, POPLAR, (-637.2, -3582.27, -55.36), 123494)
TRUNK_R = 12.0                       # check_play's stock poplar trunk radius
LIP_MAX, LIP_FAIL = 1.0, 3.0         # the rim after the patch / a lip that check_play counts (water_edge_tol)
NML_X = 1450.0                       # crater pools are generated in no man's land only (make_map: |cx| <= 1380)


class Mismatch(Exception): pass


def near(a, b, tol=TOL): return all(abs(float(x) - float(y)) <= tol for x, y in zip(a, b))


def by_node(m):
    out = {}
    for n, _ in m.walk():
        out[m.g(n, b'nodeID')] = n
    return out


def expect(m, nodes, nid, cls, model, origin):
    i = nodes.get(nid)
    if i is None or m.type(i) != b'CMapEntity': raise Mismatch('nodeID %d is not an entity' % nid)
    c, mm, o, vg = m.cls(i), m.P(i, 'model', '') or '', m.origin(i), (m.g(i, b'customVisGroup') or b'').decode()
    if c != cls or mm != model or not near(o, origin) or vg != GROUP:
        raise Mismatch('nodeID %d (id %d): want %s %s at %s in %s, found %s %s at %s in %r' % (nid, i, cls, model, origin, GROUP, c, mm, [round(v, 2) for v in o], vg))
    return i


# ================================================================ water rims
def pool_rings(m, n):
    """a generated pool's top and bottom rings: (mesh info, top ids, bottom id per top id, z top) or None when it is not a prism"""
    mi = PS.mesh_info(m, n)
    P = mi['P']
    zs = np.round(P[:, 2], 3)
    lv = sorted(set(zs.tolist()))
    if len(lv) != 2 or len(P) % 2: return None
    top = [k for k in range(len(P)) if zs[k] == lv[1]]; bot = [k for k in range(len(P)) if zs[k] == lv[0]]
    pair = {}
    for k in top:
        d = [np.hypot(*(P[b_, :2] - P[k, :2])) for b_ in bot]
        j = int(np.argmin(d))
        if d[j] > 0.01: return None
        pair[k] = bot[j]
    # the top face's loop order (the 12-gon), from the face whose vertices are all on top
    loop = None
    for he in mi['fei']:
        hs, h = [], he
        for _ in range(64):
            hs.append(h); h = mi['nxt'][h]
            if h == he: break
        vids = [mi['vdi'][mi['evi'][x]] for x in hs]
        if len(vids) == len(top) and all(v in pair for v in vids): loop = vids; break
    if loop is None: return None
    return mi, loop, pair, float(lv[1])


def lip_at(S, x, y, z):
    g = S.z(x, y)
    return (z - g) if np.isfinite(g) else 0.0


def rim_lips(S, Q, z, step=4.0):
    """worst lip of each rim vertex (its own spot and the two rim edges out of it, sampled every `step` u)"""
    n = len(Q); edge = np.zeros(n)
    for k in range(n):
        a, b = Q[k], Q[(k + 1) % n]
        L = np.hypot(*(b - a)); m_ = max(1, int(L // step))
        edge[k] = max(lip_at(S, a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, z) for t in np.linspace(0, 1, m_ + 1))
    v = np.array([max(lip_at(S, Q[k][0], Q[k][1], z), edge[k - 1], edge[k]) for k in range(n)])
    return v, edge


def trim_pool(S, Q0, z, step=2.0, lo=0.35, hi=1.6, max_drop=25, min_area=0.3, iters=300, forbid=None):
    """a rim for the pool that meets the ground: every rim vertex moves along its own ray from the pool's centre (in or out) to the
    nearest spot where the ground is no more than LIP_MAX under the water line, the rim edges between them (every 4 u) as well; when no
    such rim exists at the pool's level, the level drops 1 u at a time (at most max_drop) -> (rim, level, ok)"""
    c = Q0.mean(0); n = len(Q0)
    U = (Q0 - c) / np.hypot(*(Q0 - c).T)[:, None]; r0 = np.hypot(*(Q0 - c).T)
    area = lambda Q: 0.5 * abs(np.dot(Q[:, 0], np.roll(Q[:, 1], 1)) - np.dot(Q[:, 1], np.roll(Q[:, 0], 1)))
    a0 = area(Q0)
    def edge_lip(p, q, zl):
        L = np.hypot(*(q - p)); m_ = max(1, int(L // 4.0))
        return max(lip_at(S, p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t, zl) for t in np.linspace(0, 1, m_ + 1))
    for drop in range(0, max_drop + 1):
        zl = z - drop
        cand = []
        for k in range(n):
            rs = np.arange(lo * r0[k], hi * r0[k] + 1e-6, step)
            ok = [r for r in rs if lip_at(S, c[0] + U[k, 0] * r, c[1] + U[k, 1] * r, zl) <= LIP_MAX]
            cand.append(sorted(ok, key=lambda r: abs(r - r0[k])))
        if any(not cc for cc in cand): continue
        pick = [0] * n
        Q = np.array([c + U[k] * cand[k][0] for k in range(n)])
        for _ in range(iters):
            bad = [k for k in range(n) if edge_lip(Q[k], Q[(k + 1) % n], zl) > LIP_MAX]
            if not bad: break
            k = bad[0]; j = (k + 1) % n
            best = None
            for dk in range(0, 6):
                for dj in range(0, 6):
                    if dk == dj == 0: continue
                    ik, ij = pick[k] + dk, pick[j] + dj
                    if ik >= len(cand[k]) or ij >= len(cand[j]): continue
                    pk, pj = c + U[k] * cand[k][ik], c + U[j] * cand[j][ij]
                    if edge_lip(pk, pj, zl) <= LIP_MAX:
                        cost = abs(cand[k][ik] - r0[k]) + abs(cand[j][ij] - r0[j])
                        if best is None or cost < best[0]: best = (cost, ik, ij)
            if best is None: break
            pick[k], pick[j] = best[1], best[2]
            Q[k] = c + U[k] * cand[k][pick[k]]; Q[j] = c + U[j] * cand[j][pick[j]]
        else:
            continue
        # the rim must stay convex: the engine and the checks fan-triangulate the 12-gon top face, and a reflex corner folds a triangle
        sgn = np.sign(np.cross(Q0[1] - Q0[0], Q0[2] - Q0[1])) or 1.0
        turn = lambda Q, k: sgn * np.cross(Q[k] - Q[k - 1], Q[(k + 1) % n] - Q[k])
        for _ in range(iters):
            bad = [k for k in range(n) if turn(Q, k) <= 1e-6]
            if not bad: break
            fixed = False
            for k in bad:
                for ik in sorted(range(len(cand[k])), key=lambda i: abs(cand[k][i] - r0[k])):
                    q = c + U[k] * cand[k][ik]; Qt = Q.copy(); Qt[k] = q
                    if (edge_lip(Qt[k - 1], Qt[k], zl) <= LIP_MAX and edge_lip(Qt[k], Qt[(k + 1) % n], zl) <= LIP_MAX
                            and all(turn(Qt, j % n) > 1e-6 for j in (k - 1, k, k + 1))):
                        Q, pick[k], fixed = Qt, ik, True; break
                if fixed: break
            if not fixed: break
        if (any(edge_lip(Q[k], Q[(k + 1) % n], zl) > LIP_MAX for k in range(n)) or any(turn(Q, k) <= 1e-6 for k in range(n))
                or area(Q) < min_area * a0): continue
        if forbid is not None and forbid(zl, Q): continue          # another sheet over the same ground at this height: z-fight
        return Q, zl, True
    return Q0, z, False


def main(argv=None):
    ap = argparse.ArgumentParser(description='world patch 3: air lanes, pit_t_2 rack, the pool poplar, crater pool rims')
    ap.add_argument('--in', dest='inp', default=os.path.join(OUT, 'step9', 'chain', '4_seams.vmap'))
    ap.add_argument('--out', default=os.path.join(OUT, 'mg_trenchwarfare_world3.vmap'))
    ap.add_argument('--targets', default=None)
    ap.add_argument('--report', default=None)
    ap.add_argument('--no-guard', action='store_true')
    a = ap.parse_args(argv)
    for st_ in (sys.stdout, sys.stderr):
        if hasattr(st_, 'reconfigure'): st_.reconfigure(encoding='utf-8', errors='replace')
    inp, outp = os.path.abspath(a.inp), os.path.abspath(a.out)
    if not safepath.inside(OUT, outp) or os.path.normcase(outp) == os.path.normcase(inp):
        sys.exit('patch_world_3: --out must be under %s and not the input' % OUT)
    tp = a.targets or os.path.splitext(outp)[0] + '.targets.json'
    rp = a.report or os.path.splitext(outp)[0] + '.report.json'
    t0 = time.time()
    raw = open(inp, 'rb').read()
    m = V.Map(inp, data=raw); m.path = inp
    V.random.seed('patch_world_3:%08x:%d' % (zlib.crc32(raw) & 0xffffffff, len(raw)))   # nothing here draws from it today; kept like the other stages
    T = dict(input=inp, input_bytes=len(raw), input_crc32='%08x' % (zlib.crc32(raw) & 0xffffffff), modify={}, remove={}, add=[], prefix=[], root=False)
    rep = dict(trees=[], rack=None, pool_tree=None, pools=[], pools_left=[])
    nodes = by_node(m)
    def declare(nid, i, fields, why): T['modify'][str(nid)] = dict(i=i, fields=fields, why=why)
    try:
        # ---- verify every entity target first
        ti = [(expect(m, nodes, nid, 'prop_static', mdl, o), nid, s0, s1, why) for (nid, mdl, o, s0, s1, why) in TREES]
        for (i, nid, s0, s1, why) in ti:
            sc_ = m.g(i, b'scales') or [1, 1, 1]
            if not all(abs(v - s0) < 5e-4 for v in sc_): raise Mismatch('nodeID %d: want uniform scale %.4f, found %s' % (nid, s0, sc_))
        rnid, rmdl, ro, yaw0, dyaw, mv = RACK_T
        ri = expect(m, nodes, rnid, 'prop_static', rmdl, ro)
        if abs(((m.g(ri, b'angles') or [0, 0, 0])[1] - yaw0 + 180) % 360 - 180) > 0.5: raise Mismatch('rack %d: yaw is not %.1f' % (rnid, yaw0))
        pnid, pmdl, po, pool_nid = POOL_TREE
        pi = expect(m, nodes, pnid, 'prop_static', pmdl, po)
        pn = nodes.get(pool_nid)
        if pn is None or m.type(pn) != b'CMapMesh' or (m.g(pn, b'customVisGroup') or b'').decode() != GROUP: raise Mismatch('pool %d is not a generated mesh' % pool_nid)
    except Mismatch as ex:
        sys.exit('patch_world_3: TARGET MISMATCH, nothing written: %s' % ex)

    sc = CS.load_scene(inp)
    S = PS.Surface(sc, kinds=('terrain', 'parapet'))

    # ---- T7: the four poplars, scaled about their own origin
    for (i, nid, s0, s1, why) in ti:
        dmx.set_(m.E[i], b'scales', dmx.T_V3, [float(s1)] * 3)
        declare(nid, i, ['scales'], why + ': scale %.4f -> %.4f' % (s0, s1))
        rep['trees'].append(dict(nodeID=nid, id=i, origin=[round(v, 1) for v in m.origin(i)], scale=[s0, s1], why=why))

    # ---- pit_t_2: the rack along the breastwork
    ang = list(m.g(ri, b'angles') or [0, 0, 0]); oo = m.origin(ri)
    dmx.set_(m.E[ri], b'angles', dmx.T_V3, [float(ang[0]), float((ang[1] + dyaw) % 360.0), float(ang[2])])
    dmx.set_(m.E[ri], b'origin', dmx.T_V3, [oo[0] + mv[0], oo[1] + mv[1], oo[2] + mv[2]])
    declare(rnid, ri, ['angles', 'origin'], 'W2b pit_t_2: shell rack turned along the breastwork (yaw +90, 8 u out): seats a and b joined')
    rep['rack'] = dict(nodeID=rnid, id=ri, yaw=[round(ang[1], 3), round((ang[1] + dyaw) % 360.0, 3)], origin=[[round(v, 2) for v in oo], [round(oo[k] + mv[k], 2) for k in range(3)]])

    # ---- the poplar in the pool: straight out of it, onto the ground
    rings = pool_rings(m, pn)
    if rings is None: sys.exit('patch_world_3: pool %d is not a 12-gon prism' % pool_nid)
    mi_, loop, pair, zt = rings
    R = mi_['P'][loop][:, :2]; c = R.mean(0)
    to = np.array(m.origin(pi)[:2]); d = to - c; d = d / np.hypot(*d)
    s = (m.g(pi, b'scales') or [1, 1, 1])[0]
    # the rim's distance from the centre along d (ray / polygon), then the trunk 8 u past it
    best = 0.0
    for k in range(len(R)):
        p, q = R[k], R[(k + 1) % len(R)]
        M_ = np.array([d, p - q]).T
        if abs(np.linalg.det(M_)) < 1e-9: continue
        t, u = np.linalg.solve(M_, p - c)
        if t > 0 and 0 <= u <= 1: best = max(best, t)
    newxy = c + d * (best + TRUNK_R * s + 8.0)
    g0 = S.z(*m.origin(pi)[:2]); gz = min(S.z(newxy[0] + dx, newxy[1] + dy) for dx in (-TRUNK_R * s, 0, TRUNK_R * s) for dy in (-TRUNK_R * s, 0, TRUNK_R * s))
    if not np.isfinite(gz) or gz < zt - 0.5: sys.exit('patch_world_3: no dry ground for the pool poplar at %s' % newxy.round(1))
    newz = gz - 6.0
    oldo = m.origin(pi)
    dmx.set_(m.E[pi], b'origin', dmx.T_V3, [float(newxy[0]), float(newxy[1]), float(newz)])
    declare(pnid, pi, ['origin'], 'L4 pool poplar out of the crater pool (%.0f u), set on the ground' % np.hypot(*(newxy - np.array(oldo[:2]))))
    rep['pool_tree'] = dict(nodeID=pnid, id=pi, origin=[[round(v, 1) for v in oldo], [round(float(newxy[0]), 1), round(float(newxy[1]), 1), round(float(newz), 1)]],
                            moved=round(float(np.hypot(*(newxy - np.array(oldo[:2])))), 1), ground_before=round(float(g0), 1), water=round(zt, 1))

    # ---- W8: crater pool rims set onto the ground
    sheets = {}                                        # every water sheet: nodeID -> (world level, rim box) for the z-fight test
    for nid_, n in nodes.items():
        if m.type(n) != b'CMapMesh': continue
        md = m.g(n, b'meshData')
        if not any('water' in x.decode().lower() for x in (m.g(md, b'materials') or [])): continue
        lo_, hi_ = m.bounds(n)
        sheets[nid_] = (float(hi_[2]), (lo_[0], lo_[1], hi_[0], hi_[1]))
    def forbid_for(me):
        def f(zl, Q):
            bx = (Q[:, 0].min(), Q[:, 1].min(), Q[:, 0].max(), Q[:, 1].max())
            return any(o_ != me and abs(zo - zl) < 2.0 and b_[0] < bx[2] and b_[2] > bx[0] and b_[1] < bx[3] and b_[3] > bx[1]
                       for o_, (zo, b_) in sheets.items())
        return f
    for nid_, n in sorted(nodes.items()):
        if m.type(n) != b'CMapMesh': continue
        md = m.g(n, b'meshData')
        mats = [x.decode().lower() for x in (m.g(md, b'materials') or [])]
        if not any('water' in x for x in mats): continue
        org = np.array(m.g(n, b'origin', [0, 0, 0]), float)
        if (m.g(n, b'customVisGroup') or b'').decode() != GROUP or any(m.g(n, b'angles', [0, 0, 0])) or list(m.g(n, b'scales', [1, 1, 1])) != [1.0, 1.0, 1.0]: continue
        rg = pool_rings(m, n)
        if rg is None: continue
        mi, loop, pair, z = rg
        z += org[2]                                    # patch_world_1 (L5) lowered three sheets by their node origin
        Q0 = mi['P'][loop][:, :2].copy() + org[:2]
        if abs(Q0[:, 0].mean()) > NML_X: continue
        lips, _ = rim_lips(S, Q0, z)
        if lips.max() <= LIP_FAIL: continue
        Q, zl, ok = trim_pool(S, Q0, z, forbid=forbid_for(nid_))
        rec = dict(nodeID=nid_, id=n, centre=[round(v) for v in Q0.mean(0)], z=[round(z, 2), round(zl, 2)], worst_lip=round(float(lips.max()), 1),
                   moved=int((np.hypot(*(Q - Q0).T) > 1e-6).sum()), max_move=round(float(np.hypot(*(Q - Q0).T).max()), 1),
                   area=[round(float(0.5 * abs(np.dot(Q0[:, 0], np.roll(Q0[:, 1], 1)) - np.dot(Q0[:, 1], np.roll(Q0[:, 0], 1))))),
                         round(float(0.5 * abs(np.dot(Q[:, 0], np.roll(Q[:, 1], 1)) - np.dot(Q[:, 1], np.roll(Q[:, 0], 1)))))])
        if not ok:
            rec['why'] = 'no convex rim meets the ground within 0.35-1.6 x its radius and 25 u of lowering without meeting another sheet at its height (left as it was)'
            rep['pools_left'].append(rec); continue
        P = mi['P'].copy(); ch = set()
        dz = zl - z
        for k, v in enumerate(loop):
            if np.hypot(*(Q[k] - Q0[k])) > 1e-9 or dz:
                P[v, :2] = Q[k] - org[:2]; P[pair[v], :2] = Q[k] - org[:2]; P[v, 2] += dz; P[pair[v], 2] += dz; ch.update((v, pair[v]))
        PS.update_positions(m, mi, P, sorted(ch))
        sheets[nid_] = (zl, (Q[:, 0].min(), Q[:, 1].min(), Q[:, 0].max(), Q[:, 1].max()))
        declare(nid_, n, ['mesh'], 'W8 crater pool rim set onto the ground (%d of %d rim vertices moved, up to %.0f u; level %+.0f u; worst lip was %.1f u)'
                % (rec['moved'], len(loop), rec['max_move'], dz, rec['worst_lip']))
        rep['pools'].append(rec)

    n = m.save(outp)
    T['output'] = outp
    os.makedirs(os.path.dirname(os.path.abspath(tp)), exist_ok=True)
    json.dump(T, open(tp, 'w'), indent=1)
    rep.update(input=inp, output=outp, input_crc32=T['input_crc32'], seconds=round(time.time() - t0, 1))
    json.dump(rep, open(rp, 'w'), indent=1, default=float)
    print('patched map: %s (%d bytes); %d poplars scaled, rack turned, pool poplar moved %.0f u, %d pool rims tucked in (%d left); %.1f s'
          % (outp, n, len(rep['trees']), rep['pool_tree']['moved'], len(rep['pools']), len(rep['pools_left']), time.time() - t0))
    if not a.no_guard:
        r = subprocess.run([sys.executable, os.path.join(HERE, 'patch_guard.py'), inp, outp, tp, '--strict', '--report',
                            os.path.splitext(outp)[0] + '.guard.json'], capture_output=True, text=True)
        print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-400:])
        if r.returncode: sys.exit('patch_world_3: GUARD FAILED')


if __name__ == '__main__':
    main()
