"""World patch 3 (13 Nov 2026, docs/REVIEW_WORLD_3.md): the real problems check_play still found in the generated content of the chained
map, as one guarded delta patch. Reads the input map (never writes it); writes the patched copy, the guard's target list and a report.

usage: python tools/patch_world_3.py [--in V] [--out V] [--targets T] [--report R] [--no-guard] [--pit-sandbags [both|ct|t]]
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
  W9  pit sandbags OPTIONAL, OFF by default (--pit-sandbags [both|ct|t]; PENDING THE USER'S DECISION, docs/REVIEW_WORLD_3.md W9):
                  one more course of sandbags on the enemy-facing arc of the generated mortar pits' breastworks. The three generated
                  courses (make_map: walls at r 194 / 192, a sandbag_low cap at r 190, 17 bags a course, every other course half a bag
                  round, +0.04 rad per pit) top out at about the crew's standing eye (ground + 64), so whether a fire-step eye 5,000 u
                  away sees a crewman was a matter of a unit or two of terrain. The new course is the generator's fourth: sandbag_low
                  (a clone of the pit's own cap bag: model, scale 1 1 1.1, keyvalues, vis group tw_gen) at r 188, half a bag round from
                  the cap, on the slots whose span meets the arc where a line from any crew position (seats a / b, the tube) to any enemy
                  fire step crosses the ring. Each bag rests on the exact triangles of the bags under it (LOD0 meshes): z is set so that
                  3/4 of its bottom samples touch or bed into them (generator courses bed 0.4 u), and the report gives the largest gap and
                  bedding. Refused (nothing written) when a bag would touch the tube, table, ammo box, stores or a crew seat's player box,
                  or would need the tube to fire under 30 deg to clear it. 'both' = every pit of both sides, 'ct' / 't' = one side only.
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


# ================================================================ W9 (optional): one more sandbag course on the pits' enemy-facing arc
SANDBAG_LOW = 'models/tw/sandbag_low/sandbag_low.vmdl'
FIRESTEP = 'models/tw/firestep/firestep.vmdl'
PIT_NB, PIT_R_CAP, PIT_R_NEW = 17, 190.0, 188.0      # make_map: 17 bags a course; courses at r 194 / 192 / 190, each 2 u further in
PIT_ANG_K = 0.04                                     # make_map: + 0.04 rad per pit (k 0..4 = mortarpit_<tg>_1..5)
PIT_TOUCH_Q = 25.0                                   # z: 75 % of the bag's bottom samples touch or bed into the course under it
PIT_MIN_ELEV = 30.0                                  # the tube must be able to fire at this elevation and up over the new course
SEAT_BOX = (16.0, 72.0)                              # a crew seat's player box: half width, height


def _wrap(a): return (a + math.pi) % (2 * math.pi) - math.pi


def _world_tris(T, R, o): return T @ np.asarray(R).T + np.asarray(o)


def _support_top(Tw, xy):
    """highest point of the triangles Tw (n, 3, 3) straight over / under each point xy (k, 2); -inf where none covers it"""
    out = np.full(len(xy), -np.inf)
    if not len(Tw): return out
    A, B, C = Tw[:, 0], Tw[:, 1], Tw[:, 2]
    v0, v1 = (B - A)[:, :2], (C - A)[:, :2]
    den = v0[:, 0] * v1[:, 1] - v1[:, 0] * v0[:, 1]
    ok = np.abs(den) > 1e-9
    A, B, C, v0, v1, den = A[ok], B[ok], C[ok], v0[ok], v1[ok], den[ok]
    for k, p in enumerate(xy):
        w = p[None, :] - A[:, :2]
        b1 = (w[:, 0] * v1[:, 1] - v1[:, 0] * w[:, 1]) / den
        b2 = (v0[:, 0] * w[:, 1] - w[:, 0] * v0[:, 1]) / den
        hit = (b1 >= -1e-6) & (b2 >= -1e-6) & (b1 + b2 <= 1 + 1e-6)
        if hit.any():
            z = A[hit, 2] + b1[hit] * (B[hit, 2] - A[hit, 2]) + b2[hit] * (C[hit, 2] - A[hit, 2])
            out[k] = z.max()
    return out


def plan_pit_sandbags(m, sc, sides, seed):
    """-> (list of new bags per pit, report); raises Mismatch when the pits are not the generator's or a bag would not fit"""
    import random as _r
    ents = {}
    for n in m.entities():
        nm = m.name(n)
        if nm: ents[nm] = n
    fs = [(m.origin(n), n) for n in m.entities() if m.cls(n) == 'prop_static' and (m.P(n, 'model', '') or '') == FIRESTEP]
    if len(fs) < 20: raise Mismatch('pit sandbags: only %d fire steps (%s) in the map' % (len(fs), FIRESTEP))
    bag_T = CS.model_tris(SANDBAG_LOW)
    if bag_T is None or not len(bag_T): raise Mismatch('pit sandbags: no LOD0 mesh for %s' % SANDBAG_LOW)
    plans, rep = [], []
    for tg in ('t', 'ct'):
        if sides not in ('both', tg): continue
        s = 1 if tg == 'ct' else -1
        phi0 = math.pi if s > 0 else 0.0                 # toward the enemy (CT faces -x)
        enemy = np.array([o[:2] for o, _ in fs if o[0] * s < 0], float)
        for k in range(1, 6):
            pn = ents.get('mortarpit_%s_%d' % (tg, k))
            if pn is None or m.cls(pn) != 'info_target' or (m.g(pn, b'customVisGroup') or b'').decode() != GROUP:
                raise Mismatch('pit sandbags: mortarpit_%s_%d is not a generated info_target' % (tg, k))
            c = np.array(m.origin(pn)[:2], float); cz = m.origin(pn)[2]
            crew = []
            for q in ('a', 'b'):
                e = ents.get('mortarcrew_%s_%d_%s' % (tg, k, q))
                if e is None: raise Mismatch('pit sandbags: mortarcrew_%s_%d_%s missing' % (tg, k, q))
                crew.append(('seat_' + q, m.origin(e)))
            tube = ents.get('mortar_%s_%d' % (tg, k))
            if tube is None: raise Mismatch('pit sandbags: tube mortar_%s_%d missing' % (tg, k))
            crew.append(('tube', m.origin(tube)))
            # the props of this pit (CS scene: R = rotation @ scale, o) and the cap course (the generator's third, sandbag_low at r 190)
            near = [p for p in sc['props'] if np.hypot(p['o'][0] - c[0], p['o'][1] - c[1]) < 240.0]
            caps = [p for p in near if p['model'] == SANDBAG_LOW and p['vg'] == GROUP and abs(np.hypot(p['o'][0] - c[0], p['o'][1] - c[1]) - PIT_R_CAP) < 2.0]
            k0 = k - 1
            want = [c + PIT_R_CAP * np.array([math.cos(2 * math.pi * q / PIT_NB + PIT_ANG_K * k0), math.sin(2 * math.pi * q / PIT_NB + PIT_ANG_K * k0)]) for q in range(PIT_NB)]
            matched = sum(1 for w in want if any(np.hypot(p['o'][0] - w[0], p['o'][1] - w[1]) < 1.5 for p in caps))
            if matched < 12: raise Mismatch('pit sandbags: pit %s_%d cap course matches the generator at %d of %d slots' % (tg, k, matched, PIT_NB))
            # the arc: where a line from a crew position to an enemy fire step crosses the new course's ring
            rel = []
            for _, q in crew:
                q2 = np.array(q[:2], float)
                for f in enemy:
                    d = f - q2; d /= np.hypot(*d)
                    w = q2 - c; b = np.dot(w, d); cc = np.dot(w, w) - PIT_R_NEW ** 2
                    t = -b + math.sqrt(max(0.0, b * b - cc))
                    p = q2 + d * t
                    rel.append(_wrap(math.atan2(p[1] - c[1], p[0] - c[0]) - phi0))
            lo, hi = min(rel), max(rel)
            half = math.pi / PIT_NB
            slots = [q for q in range(PIT_NB) if _wrap(2 * math.pi * (q + 0.5) / PIT_NB + PIT_ANG_K * k0 - phi0) + half >= lo
                     and _wrap(2 * math.pi * (q + 0.5) / PIT_NB + PIT_ANG_K * k0 - phi0) - half <= hi]
            sup = [p for p in near if '/sandbag_' in p['model']]
            sup_T = [(_world_tris(CS.model_tris(p['model']), p['R'], p['o'])) for p in sup if CS.model_tris(p['model']) is not None]
            sup_T = np.concatenate(sup_T) if sup_T else np.zeros((0, 3, 3))
            others = [p for p in near if '/sandbag_' not in p['model'] and CS.model_tris(p['model']) is not None]
            tube_p = [p for p in near if p['i'] == tube]
            muzzle = None
            if tube_p and CS.model_tris(tube_p[0]['model']) is not None:
                tw = _world_tris(CS.model_tris(tube_p[0]['model']), tube_p[0]['R'], tube_p[0]['o']).reshape(-1, 3)
                muzzle = tw[np.argmax(tw[:, 2])]
            rng = _r.Random('%s:%s_%d' % (seed, tg, k))
            pit_rep = dict(pit='%s_%d' % (tg, k), arc_deg=[round(math.degrees(lo), 1), round(math.degrees(hi), 1)], slots=slots, bags=[],
                           caps_matched=matched, muzzle_over_floor=round(float(muzzle[2] - cz), 1) if muzzle is not None else None)
            src = None
            for q in slots:
                a = 2 * math.pi * (q + 0.5) / PIT_NB + PIT_ANG_K * k0
                rx, ry = math.cos(a), math.sin(a)
                x, y = c[0] + rx * PIT_R_NEW, c[1] + ry * PIT_R_NEW
                yaw = (math.degrees(math.atan2(-rx, ry)) + rng.uniform(-2.0, 2.0)) % 360.0
                cap = min(caps, key=lambda p: abs(_wrap(math.atan2(p['o'][1] - c[1], p['o'][0] - c[0]) - a)))   # the clone source: the cap under it
                scl = [float(v) for v in (m.g(cap['i'], b'scales') or [1, 1, 1])]
                R = np.array(V.rot_matrix([0.0, yaw, 0.0]), float) @ np.diag(scl)
                Tb = _world_tris(bag_T, R, (x, y, 0.0))
                Pv = Tb.reshape(-1, 3)
                bot = Pv[Pv[:, 2] <= Pv[:, 2].min() + 3.0]
                bot = np.unique(np.round(bot, 2), axis=0)
                lo_xy, hi_xy = Pv[:, :2].min(0) - 2, Pv[:, :2].max(0) + 2
                st = sup_T[(sup_T[:, :, 0].max(1) >= lo_xy[0]) & (sup_T[:, :, 0].min(1) <= hi_xy[0]) & (sup_T[:, :, 1].max(1) >= lo_xy[1]) & (sup_T[:, :, 1].min(1) <= hi_xy[1])]
                top = _support_top(st, bot[:, :2])
                okk = np.isfinite(top)
                if okk.mean() < 0.6: raise Mismatch('pit sandbags: %s_%d slot %d: only %.0f %% of the bag rests on the course under it' % (tg, k, q, 100 * okk.mean()))
                g = top[okk] - bot[okk, 2]                      # the z that puts each bottom sample on its support
                z = float(np.percentile(g, 100 - PIT_TOUCH_Q))
                z = round(z, 2)
                gap = z + bot[okk, 2] - top[okk]                # > 0: in the air over the course; < 0: bedded into it
                Tz = Tb + np.array([0.0, 0.0, z])
                # nothing but sandbags may be inside the new bag (sampled surfaces of the tube, table, ammo box, stores, rack)
                Rinv = np.linalg.inv(R)
                blo, bhi = bag_T.reshape(-1, 3).min(0) + 0.5, bag_T.reshape(-1, 3).max(0) - 0.5
                hits = []
                for p in others:
                    Sp = CS.sample_tris(_world_tris(CS.model_tris(p['model']), p['R'], p['o']), 4.0)
                    L = (Sp - np.array([x, y, z])) @ Rinv.T
                    n_in = int(np.all((L >= blo) & (L <= bhi), axis=1).sum())
                    if n_in: hits.append((p['model'].split('/')[-1], p['nid'], n_in))
                if hits: raise Mismatch('pit sandbags: %s_%d slot %d touches %s' % (tg, k, q, hits))
                Pz = Tz.reshape(-1, 3)
                for nm_, so in crew[:2]:
                    fz = so[2] - 8.0                             # the teleport destination stands 8 u over the floor (make_map)
                    if (Pz[:, 0].min() < so[0] + SEAT_BOX[0] and Pz[:, 0].max() > so[0] - SEAT_BOX[0] and Pz[:, 1].min() < so[1] + SEAT_BOX[0]
                            and Pz[:, 1].max() > so[1] - SEAT_BOX[0] and Pz[:, 2].min() < fz + SEAT_BOX[1] and Pz[:, 2].max() > fz):
                        raise Mismatch('pit sandbags: %s_%d slot %d meets the %s player box' % (tg, k, q, nm_))
                elev = None
                if muzzle is not None:
                    dh = np.hypot(Pz[:, 0] - muzzle[0], Pz[:, 1] - muzzle[1])
                    elev = float(np.degrees(np.arctan2(Pz[:, 2] - muzzle[2], dh)).max())
                    if elev > PIT_MIN_ELEV: raise Mismatch('pit sandbags: %s_%d slot %d: the tube would need %.1f deg to clear it' % (tg, k, q, elev))
                plans.append(dict(src=cap['i'], origin=(x, y, z), yaw=yaw, why='W9 pit sandbags (%s): mortarpit_%s_%d, 4th course slot %d' % (sides, tg, k, q)))
                pit_rep['bags'].append(dict(slot=q, origin=[round(x, 2), round(y, 2), z], yaw=round(yaw, 2), clone_of=cap['nid'],
                                            top_over_floor=round(float(Pz[:, 2].max() - cz), 1), max_gap=round(float(gap.max()), 1),
                                            max_bed=round(float(-gap.min()), 1), unsupported_pct=round(100 * (1 - okk.mean()), 1),
                                            tube_clear_deg=None if elev is None else round(elev, 1)))
            rep.append(pit_rep)
    return plans, rep


def main(argv=None):
    ap = argparse.ArgumentParser(description='world patch 3: air lanes, pit_t_2 rack, the pool poplar, crater pool rims')
    ap.add_argument('--in', dest='inp', default=os.path.join(OUT, 'step9', 'chain', '4_seams.vmap'))
    ap.add_argument('--out', default=os.path.join(OUT, 'mg_trenchwarfare_world3.vmap'))
    ap.add_argument('--targets', default=None)
    ap.add_argument('--report', default=None)
    ap.add_argument('--no-guard', action='store_true')
    # W9 option, OFF by default: pending the user's decision (docs/REVIEW_WORLD_3.md W9); a bare flag means 'both'
    ap.add_argument('--pit-sandbags', nargs='?', const='both', choices=('both', 'ct', 't'), default=None,
                    help='one more sandbag course on the enemy-facing arc of the mortar pits (both sides / one side); off by default')
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
    seed = 'patch_world_3:%08x:%d' % (zlib.crc32(raw) & 0xffffffff, len(raw))
    V.random.seed(seed)   # only the optional pit sandbags draw from it (new referenceIDs / randomSeeds); kept like the other stages
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

    # ---- W9 (optional, off by default): one more sandbag course on the pits' enemy-facing arc
    if a.pit_sandbags:
        try:
            plans, rep['pit_sandbags'] = plan_pit_sandbags(m, sc, a.pit_sandbags, seed)
        except Mismatch as ex:
            sys.exit('patch_world_3: --pit-sandbags REFUSED, nothing written: %s' % ex)
        par = {n_: p_ for n_, p_ in m.walk()}
        node_id = [m.next_node_id()]
        for pl in plans:
            if par.get(pl['src']) != m.world: sys.exit('patch_world_3: --pit-sandbags: cap bag %d is not a child of the world' % pl['src'])
            e = m.import_subtree(m, pl['src'], {}, node_id)
            dmx.set_(m.E[e], b'referenceID', dmx.T_U64, V.random.getrandbits(63))
            dmx.set_(m.E[e], b'randomSeed', dmx.T_INT, V.random.randint(1, 2 ** 31 - 1))
            dmx.geta(m.E[e], b'origin')[2] = [float(v) for v in pl['origin']]
            dmx.geta(m.E[e], b'angles')[2] = [0.0, float(pl['yaw']), 0.0]
            dmx.geta(m.E[m.world], b'children')[2].append(e)
            T['add'].append(dict(type='CMapEntity', **{'class': 'prop_static'}, why=pl['why']))
        counts = {}
        for e in m.entities(): counts[m.cls(e)] = counts.get(m.cls(e), 0) + 1
        for attrs in m.doc.prefix:
            pre = {x[0]: x for x in attrs}
            if b'map_subasset_reference_names' in pre:
                names = sorted(counts)
                pre[b'map_subasset_reference_types'][2] = [b'entity'] * len(names)
                pre[b'map_subasset_reference_names'][2] = [nm.encode() for nm in names]
                pre[b'map_subasset_reference_counts'][2] = [counts[nm] for nm in names]
                T['prefix'] += ['map_subasset_reference_counts']
        rep['pit_sandbags_option'] = a.pit_sandbags

    n = m.save(outp)
    T['output'] = outp
    os.makedirs(os.path.dirname(os.path.abspath(tp)), exist_ok=True)
    json.dump(T, open(tp, 'w'), indent=1)
    rep.update(input=inp, output=outp, input_crc32=T['input_crc32'], seconds=round(time.time() - t0, 1))
    json.dump(rep, open(rp, 'w'), indent=1, default=float)
    print('patched map: %s (%d bytes); %d poplars scaled, rack turned, pool poplar moved %.0f u, %d pool rims tucked in (%d left)%s; %.1f s'
          % (outp, n, len(rep['trees']), rep['pool_tree']['moved'], len(rep['pools']), len(rep['pools_left']),
             ('; pit sandbags (%s): %d bags on %d pits' % (a.pit_sandbags, sum(len(p['bags']) for p in rep['pit_sandbags']), len(rep['pit_sandbags'])))
             if a.pit_sandbags else '', time.time() - t0))
    if not a.no_guard:
        r = subprocess.run([sys.executable, os.path.join(HERE, 'patch_guard.py'), inp, outp, tp, '--strict', '--report',
                            os.path.splitext(outp)[0] + '.guard.json'], capture_output=True, text=True)
        print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-400:])
        if r.returncode: sys.exit('patch_world_3: GUARD FAILED')


if __name__ == '__main__':
    main()
