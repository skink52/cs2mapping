"""IRONFRAME weapon mounts: arm weapons in the hands, shoulder units clear of the body (skink52 playtest, 10 Nov 2026:
"line each weapon up better with each model's hands ... shoulder-mounted weapons ... merge into the bodies").

The game parents each weapon prop to the upper-body prop, rigid, axes = the upper body's (barrel along the aim direction +x).
This tool decides where each prop's origin goes, per frame and per weapon, in the upper model frame (x forward, y left, z up,
origin under the feet before the waist-pivot shift), and measures every placement against the frame's real mesh.

- Arm weapons: the weapon's grip (tools/weapon_props.py GRIPS / grip_point: the pistol grip, a blade's hilt, a shield's back face;
  repivot() makes it the prop's model origin) goes to the palm (posed centroid of the hand bone and its fingers) in the idle pose; when the body is in the way
  the smallest move out / down / forward that clears it is taken. The holding arm (forearm, hand, fingers) is left out of the check:
  the hand is meant to close round the grip.
- Shoulder weapons: RESTING on the frame in its idle pose. The unit comes down from above until it overlaps the idle frame by
  SEAT_FIT (rest_z: "slightly into the shoulder"; a thin aerial or fin reads under that and is passed through), centred near the
  shoulder joint, each unit on its own side of the centre plane and never below the joint. The spot is the cheapest by seat gap (how
  far the unit hovers over a SEAT_AREA patch of the frame: a unit caught on a spike pays for it) + rise above the shoulder top +
  distance from the joint + overlap in the moving poses beyond MOVE_FIT. Wide units overhang narrow shoulders outward.
  (Until 10 Nov 2026 evening the unit was dropped onto the MAXIMUM of a height map of EVERY pose under its whole footprint: one aerial,
  V-fin, sabre hilt or raised arm anywhere under a 150 u pod held it 20-90 u above the shoulder: skink52 "shoulder weapons float".)
- Clearance: the frame (upper + legs, LOD 0) is voxelised (RES u) in every pose (idle x2, walk x3, run, aim x4: fire clips with the
  upper body pitched +-10 deg and turned +-30 deg against the legs, as 30_render.js does), filled, and distance-transformed; the weapon
  likewise. Penetration of a placement = 2 x max over the weapon's inside of min(depth in frame, depth in weapon) - 1 voxel (so
  resting contact reads ~1 voxel; a thin aerial through a pod reads 1-2 voxels). An arm weapon passes at <= TOL u in every pose.
  A shoulder unit passes when it is seated (seat gap <= FLOAT_TOL in idle), overlaps the idle frame by <= SEAT_PEN and the frame in
  any other pose by <= MOVE_PEN (it is rigid on the upper prop while the arms and shoulder armour move under it).

usage:
  python -I tools/weapon_fit.py --fit [--only frame,..] [--jobs N]   compute the mounts -> models.json#mounts, build/weapon_fit.json,
                                [--lock]                              docs/WEAPON_FIT.md (old placement measured alongside); --lock
                                                                      takes out/addon/_gen/models.json.lock for the write (several
                                                                      sessions at work; not when the caller already holds it)
  python -I tools/weapon_fit.py [--only ..] [--jobs N]                the test: measure the mounts stored in models.json#mounts;
                                                                      exit 1 when a pair is over its tolerance, a grip is off the
                                                                      palm or a shoulder unit floats
models.json#mounts = {tol, res, grips: {weapon: [x, y, z]}, frames: {frame: {weapon: [right x, y, z, left x, y, z]}}}: the weapon
prop's origin for the right slot (ra / rs) and the left slot (la / ls). 30_render.js weaponMountPos() reads it; tools/frames.py keeps
the key when it rewrites models.json. data/frames.json frames.<key>.mount: per-frame overrides (hand_r / hand_l bone names for rigs
without hand bones, unfit: {weapon: reason} pairs accepted over the tolerance).
"""
import json, math, os, sys, time
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import numpy as np
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import review_frames as RF                                   # noqa: E402
import review_weapons as RW                                  # noqa: E402
import weapon_props as WP                                    # noqa: E402

OUT = os.path.join(PROJ, 'out', 'addon')
MODELS_JSON = os.path.join(OUT, '_gen', 'models.json')
FRAMES_JSON = os.path.join(PROJ, 'data', 'frames.json')
REPORT = os.path.join(PROJ, 'build', 'weapon_fit.json')
DOC = os.path.join(PROJ, 'docs', 'WEAPON_FIT.md')
RES = 2.5            # voxel (u)
TOL = 4.0            # allowed penetration (u): resting contact reads one voxel
ALIGN = 0.04         # alignment: the palm (idle) must lie inside the placed arm weapon's bounds grown by this x class height (the hand
                     # stays on the weapon even where a body part pushed the grip off the palm; grip_off reports how far)
SEAT_FIT, SEAT_PEN = 5.0, 7.5     # shoulder units: overlap with the idle frame the fit rests them at / the test allows ("slightly into")
MOVE_FIT, MOVE_PEN = 10.0, 15.0   # ... and in the other poses (walk / run sway, fire clips, aim): the fit starts paying / the test fails
SEAT_AREA = 100.0                 # the patch of frame (u^2; half of a smaller underside) a unit must rest on
FLOAT_TOL = 5.0                   # the test: seat gap (hover over that patch, idle) above this = floating
AIM_PITCH, AIM_YAW = 10.0, 30.0   # 30_render.js: upper pitch = -aim pitch / 2 (torso_pitch 20), torso yaw free against the legs
F = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1.]])           # SMD import frame -> model frame (undo the (y, -x, z) turn)
# the converted frames carry mdl2cs2's reduced rig (root, torso, arm_up_*, arm_lo_*, arm_hand_* when the source has hand bones). Frames
# without arm_hand_* (the AC rigs, Aretha, 002-B) keep the hand in arm_lo_*: the palm is its distal end. Normal, Mule and MOA have no arms.
HAND = {'r': ('arm_hand_r', 'arm_lo_r'), 'l': ('arm_hand_l', 'arm_lo_l')}
SHOULDER = {'r': ('arm_up_r',), 'l': ('arm_up_l',)}
# the source rig's hand bone (<frame>_skeleton.json, bind centroid, model frame): the palm of frames whose hand sits inside arm_lo_*
# (the far end of that group is the frame's own built-in gun on the AC rigs). data/frames.json mount.hand_r / hand_l override it.
HAND_SRC = {'r': ('ValveBiped.Bip01_R_Hand', 'Hand Right', 'RightHand', 'r_te'), 'l': ('ValveBiped.Bip01_L_Hand', 'Hand Left', 'LeftHand', 'l_te')}
SIDE = {'r': -1.0, 'l': 1.0}                                  # outward sign of y


def jload(p): return json.load(open(p, encoding='utf-8'))


def weapon_kinds():
    return {p['key']: p['kind'] for p in jload(os.path.join(PROJ, 'data', 'parts.json'))['parts'] if p.get('kind') in ('arm', 'shoulder')}


# ---------------------------------------------------------------- voxels
def surf_vox(T, org, shape, res):
    """surface voxels of triangles T (n,3,3)"""
    g = np.zeros(shape, bool)
    if not len(T): return g
    e = np.max(np.stack([np.linalg.norm(T[:, 1] - T[:, 0], axis=1), np.linalg.norm(T[:, 2] - T[:, 1], axis=1), np.linalg.norm(T[:, 0] - T[:, 2], axis=1)]), 0)
    n = np.clip(np.ceil(e / (res * 0.6)).astype(int), 1, 300)
    shp = np.array(shape)
    for k in np.unique(n):
        sel = T[n == k]
        i, j = np.mgrid[0:k + 1, 0:k + 1]; m = i + j <= k; a = i[m] / k; b = j[m] / k; c = 1 - a - b
        step = max(1, int(3e6 // len(a)))
        for s0 in range(0, len(sel), step):
            S = sel[s0:s0 + step]
            P = S[:, 0, None, :] * c[None, :, None] + S[:, 1, None, :] * a[None, :, None] + S[:, 2, None, :] * b[None, :, None]
            idx = np.floor((P.reshape(-1, 3) - org) / res).astype(np.int32)
            ok = ((idx >= 0) & (idx < shp)).all(1); idx = idx[ok]
            g[idx[:, 0], idx[:, 1], idx[:, 2]] = True
    return g


def solid_depth(T, org, shape, res):
    """depth inside the closed mesh, in voxels (0 outside, 1 on the surface): closing (1 voxel) seals small mesh gaps, holes filled"""
    s = surf_vox(T, org, shape, res)
    s = ndimage.binary_fill_holes(ndimage.binary_closing(s, iterations=1)) | s
    return ndimage.distance_transform_edt(s).astype(np.float32)


class Weapon:
    def __init__(self, key, kind, vmdl):
        smd, _ = RW.entry_paths(key, vmdl)
        tris, _, _ = RW.load_smd(smd)
        self.key, self.kind, self.tris = key, kind, tris
        P = tris.reshape(-1, 3); self.lo, self.hi = P.min(0), P.max(0)
        self.grip, self.grip_how = WP.grip_point(key, kind, P)
        org = self.lo - 3 * RES; shape = tuple(np.ceil((self.hi - self.lo) / RES).astype(int) + 7)
        D = solid_depth(tris, org, shape, RES)
        idx = np.argwhere(D > 0)
        self.pts = org + (idx + 0.5) * RES; self.dw = D[D > 0]
        if len(self.pts) > 60000:
            keep = np.random.default_rng(1).choice(len(self.pts), 60000, replace=False); self.pts, self.dw = self.pts[keep], self.dw[keep]
        # bottom profile for the shoulder drop: lowest inside voxel per (x, y) column
        col = {}
        for (ix, iy, iz) in idx:
            k = (ix, iy)
            if k not in col or iz < col[k]: col[k] = iz
        cc = np.array([[ix, iy, iz] for (ix, iy), iz in col.items()], float)
        self.bot = np.column_stack([org[0] + (cc[:, 0] + 0.5) * RES, org[1] + (cc[:, 1] + 0.5) * RES, org[2] + cc[:, 2] * RES])
        self.pts3 = self.pts[::3]; self.dw3 = self.dw[::3]                  # a third of the inside voxels: the shoulder search


# ---------------------------------------------------------------- frames: meshes, bones, poses
def bone_world(nodes, fr):
    return [(F @ M[:3, :3] @ F.T, F @ M[:3, 3]) for M in RF.world_mats(nodes, fr)]


def subtree(nodes, roots):
    kids = {}
    for i, (_, p) in enumerate(nodes): kids.setdefault(p, []).append(i)
    out, st = set(), list(roots)
    while st:
        b = st.pop()
        if b in out: continue
        out.add(b); st += kids.get(b, [])
    return out


def Ry(deg):
    a = math.radians(deg); c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])      # Source pitch: + = nose down, forward (c, 0, -s)


def Rz(deg):
    a = math.radians(deg); c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


class Frame:
    def __init__(self, key, entry, over, lod=0):
        self.key, self.e, self.h = key, entry, entry['height']
        self.pv = np.array(list(entry.get('pivot') or [0, 0]) + [0.0])
        d = os.path.join(OUT, 'models', 'ifr', 'frames', key)
        self.parts = {}
        for g in ('legs', 'upper'):
            v = entry.get(g)
            if v: self.parts[g] = RF.read_mesh(RF.lod_file(d, os.path.basename(v)[:-5], lod))
        self.clips = {}
        for g in self.parts:
            for c in entry.get('anims', {}).get(g, []):
                p = os.path.join(d, 'anims', '%s_%s.smd' % (g, c))
                if os.path.exists(p): self.clips[(g, c)] = RF.clip_frames(p)[1]
        up = self.parts['upper']
        self.nodes = up['nodes']; self.names = [n for n, _ in self.nodes]
        self.hand = {s: self.find([over.get('hand_' + s)] if over.get('hand_' + s) else HAND[s]) for s in 'rl'}
        self.shoulder = {s: self.find(SHOULDER[s]) for s in 'rl'}
        self.hand_tree, self.arm_set = {}, {}
        for s in 'rl':
            hb = self.hand[s]
            if hb is None: self.hand_tree[s] = set(); self.arm_set[s] = set(); continue
            self.hand_tree[s] = subtree(self.nodes, [hb])
            lo_b = self.find(['arm_lo_' + s])                       # the holding forearm + hand: left out of the arm-weapon check
            self.arm_set[s] = subtree(self.nodes, [lo_b if lo_b is not None else hb])
        dom = lambda m: m['BI'][np.arange(len(m['BI'])), np.argmax(m['BW'], 1)]
        self.vbone = dom(up); self.tbone = self.vbone.reshape(-1, 3)[:, 0]
        sk = os.path.join(d, key + '_skeleton.json')
        skel = {b['name']: b for b in jload(sk)['bones']} if os.path.exists(sk) else {}
        self.hand_src = {}
        for s in 'rl':
            for n in ([over['hand_' + s]] if over.get('hand_' + s) else HAND_SRC[s]):
                b = skel.get(n)
                if b and (b.get('centroid') or b.get('pos')): self.hand_src[s] = (n, np.array(b.get('centroid') or b['pos'], float)); break

    def find(self, names):
        for n in names:
            if n in self.names: return self.names.index(n)
        return None

    def frame_of(self, g, clip, tf, loop=True):
        fr = self.clips.get((g, clip))
        if not fr: return None
        T = self.e.get('anim_len', {}).get(clip, 1.0); ks = sorted(fr); i = int(tf * T * 64 + 1e-6)
        return fr[ks[i % len(ks) if loop else min(i, len(ks) - 1)]]

    def poses(self):
        """[(name, upper frame, legs frame, pitch, yaw offset of the upper against the legs)]"""
        sw = RF.upper_clip_for(self.e, 'walk'); sr = RF.upper_clip_for(self.e, 'run')
        P = [('idle', self.frame_of('upper', 'idle', 0), self.frame_of('legs', 'hover', 0), 0, 0),
             ('idle 0.5', self.frame_of('upper', 'idle', 0.5), self.frame_of('legs', 'hover', 0.5), 0, 0)]
        for t in (0.0, 0.33, 0.66):
            P.append(('walk %.2f' % t, self.frame_of('upper', sw, t), self.frame_of('legs', 'walk', t), 0, 0))
        P.append(('run 0.25', self.frame_of('upper', sr, 0.25), self.frame_of('legs', 'run', 0.25), 0, 0))
        for c, pt, yw in (('fire_r', AIM_PITCH, AIM_YAW), ('fire_l', -AIM_PITCH, -AIM_YAW), ('fire_s', AIM_PITCH, -AIM_YAW), ('idle', -AIM_PITCH, AIM_YAW)):
            P.append(('aim %s %+.0f/%+.0f' % (c, pt, yw), self.frame_of('upper', c, 0.4, c == 'idle'), self.frame_of('legs', 'hover', 0), pt, yw))
        return P

    def posed(self, pose):
        """upper tris, upper verts, legs tris (in the upper body's frame) for a pose"""
        _, fu, fl, pt, yw = pose
        Vu = RF.posed(self.parts['upper'], fu)
        Tl = np.zeros((0, 3, 3))
        if 'legs' in self.parts:
            Vl = RF.posed(self.parts['legs'], fl)
            # world: upper X = Tu + Ry(pt) x_u with Tu = -pv (pivotOrigin), legs X = -Rz(-yw) pv + Rz(-yw) x_l (legs turned -yw against the upper)
            W = (Vl - self.pv) @ Rz(-yw).T + self.pv
            Tl = (W @ Ry(pt)).reshape(-1, 3, 3)                 # Ry(pt)^T applied to row vectors
        return Vu.reshape(-1, 3, 3), Vu, Tl

    def palm(self, s, Vu, fu):
        hb = self.hand[s]
        up = self.parts['upper']
        if (hb is None or self.names[hb].startswith('arm_lo')) and s in self.hand_src:
            # the source hand's bind centroid, carried by the group that owns it (arm_lo_*, or root on the armless rigs)
            c = self.hand_src[s][1]; k = hb if hb is not None else 0
            Wb = RF.world_mats(self.nodes, up['bind'])[k]; Wp = RF.world_mats(self.nodes, fu if fu is not None else up['bind'])[k]
            S = Wp @ np.linalg.inv(Wb); ci = F.T @ c
            return F @ (S[:3, :3] @ ci + S[:3, 3])
        if hb is None: return None
        own = np.isin(self.vbone, list(self.hand_tree[s]))
        B = bone_world(self.nodes, fu if fu is not None else up['bind'])
        if own.sum() < 3: return B[hb][1]
        if not self.names[hb].startswith('arm_lo'): return Vu[own].mean(0)
        # forearm group holding the hand: the palm is the centroid of its far end (the 15 % of its vertices farthest from the elbow)
        V = Vu[own]; d = np.linalg.norm(V - B[hb][1], axis=1)
        return V[d >= np.percentile(d, 85)].mean(0)

    def shoulder_pt(self, s, fu):
        b = self.shoulder[s]
        if b is None: return None
        return bone_world(self.nodes, fu if fu is not None else self.parts['upper']['bind'])[b][1]


# ---------------------------------------------------------------- fields + measuring
class Fields:
    """per pose and variant ('full', 'r', 'l': without that holding arm) the depth field (uint8, 1/4 voxel), and the max over poses"""
    def __init__(self, fr):
        self.fr = fr
        self.poses = fr.poses()
        posed = [fr.posed(p) for p in self.poses]
        allP = np.concatenate([np.concatenate([u.reshape(-1, 3), l.reshape(-1, 3)]) for u, _, l in posed])
        lo, hi = allP.min(0), allP.max(0)
        self.org = lo - 6 * RES; self.shape = tuple(np.ceil((hi - lo) / RES).astype(int) + 13)
        self.per = {v: [] for v in ('full', 'r', 'l')}; self.mx = {}
        self.palms = {'r': [], 'l': []}; self.shoulders = {'r': None, 'l': None}
        for pi, (pose, (Tu, Vu, Tl)) in enumerate(zip(self.poses, posed)):
            for s in 'rl':
                self.palms[s].append(fr.palm(s, Vu, pose[1]))
                if pi == 0: self.shoulders[s] = fr.shoulder_pt(s, pose[1])
            for v in ('full', 'r', 'l'):
                keep = np.ones(len(Tu), bool) if v == 'full' else ~np.isin(fr.tbone, list(fr.arm_set[v]))
                D = solid_depth(np.concatenate([Tu[keep], Tl]), self.org, self.shape, RES)
                self.per[v].append(np.minimum(D * 4, 255).astype(np.uint8))
                self.mx[v] = np.maximum(self.mx[v], self.per[v][-1]) if v in self.mx else self.per[v][-1].copy()
        # top-down height map of everything (the shoulder drop): top surface z per column, NaN where empty
        self.top0 = self.topmap(self.per['full'][0] > 0)        # the idle pose: what a shoulder unit rests on

    def topmap(self, solid):
        """top-down height map: top surface z per column, NaN where empty"""
        anyz = solid.any(2); topi = self.shape[2] - 1 - np.argmax(solid[:, :, ::-1], axis=2)
        return np.where(anyz, self.org[2] + (topi + 1) * RES, np.nan)

    def under(self, w, o):
        """the idle frame's top surface z under each underside column of weapon w at origin o (NaN: nothing below)"""
        bx = np.floor((w.bot[:, 0] + o[0] - self.org[0]) / RES).astype(int); by = np.floor((w.bot[:, 1] + o[1] - self.org[1]) / RES).astype(int)
        ok = (bx >= 0) & (bx < self.shape[0]) & (by >= 0) & (by < self.shape[1])
        tz = np.full(len(bx), np.nan); tz[ok] = self.top0[bx[ok], by[ok]]
        return tz

    def seat(self, w, o):
        """(gap, support, on) of a shoulder unit at origin o in the idle pose. gap = how far the unit hovers over the frame: the height
        of its underside over the frame's top at the seat_cols-th closest column (u; <= 0 = that patch touches or is sunk in, over
        FLOAT_TOL = floating: it hangs in the air or stands on a spike). support = share of the underside with the frame below it,
        on = at least seat_cols columns have"""
        tz = self.under(w, o); fin = np.isfinite(tz); k = seat_cols(w)
        if fin.sum() < k: return 999.0, float(fin.mean()), False
        g = np.sort(o[2] + w.bot[fin, 2] - tz[fin])
        return float(g[k - 1]), float(fin.mean()), True

    def pen(self, field, w, offs, thin=False):
        """penetration (u) of weapon w at each origin offset offs (K,3) in a field (thin: a third of the weapon's voxels, the search)"""
        offs = np.atleast_2d(offs); out = np.zeros(len(offs))
        pts, dw = (w.pts3, w.dw3) if thin else (w.pts, w.dw)
        shp = np.array(self.shape); step = max(1, int(1e6 // len(pts)))
        for k0 in range(0, len(offs), step):
            O = offs[k0:k0 + step]
            idx = np.floor((pts[None] + O[:, None] - self.org) / RES).astype(np.int32)
            ok = ((idx >= 0) & (idx < shp)).all(2)
            idx = np.where(ok[..., None], idx, 0)
            db = field[idx[..., 0], idx[..., 1], idx[..., 2]].astype(np.float32) / 4 * ok
            m = np.minimum(db, dw[None]).max(1)
            out[k0:k0 + step] = np.maximum(0, 2 * m - 1) * RES * (m > 0)
        return out

    def worst(self, variant, w, off):
        """(worst penetration, pose name) over the poses"""
        best = (0.0, '-')
        for p, f in zip(self.poses, self.per[variant]):
            v = float(self.pen(f, w, off)[0])
            if v > best[0]: best = (v, p[0])
        return best


def fit_arm(F_, w, s, hand):
    """origin for weapon w in hand s: grip at the palm, else the cheapest clear move (out / down / forward)"""
    base = np.round(hand - w.grip, 1)                        # 0.1 u: models.json stores what is measured here
    sg = SIDE[s]
    ext = max(45.0 * max(1.0, F_.fr.h / 288.0), 0.45 * float((w.hi - w.lo).max())); st = 3.0 if ext <= 45 else 6.0   # big props / the boss: wider, coarser
    C = []
    for dyo in np.arange(-6, ext + 1, st):
        for dz in np.arange(-ext * 0.8, ext * 0.5 + 1, st):
            for dx in np.arange(-15, ext + 1, st):
                C.append((1.0 * abs(dyo) + (1.2 * -dz if dz < 0 else 2.0 * dz) + 1.5 * abs(dx) + (6 if dyo < 0 else 0), dx, sg * dyo, dz))
    C.sort()
    offs = np.round(np.array([[c[1], c[2], c[3]] for c in C]) + base, 1)
    m = ALIGN * F_.fr.h                                       # moves that keep the hand on the weapon come first
    held = np.all((hand >= offs + w.lo - m) & (hand <= offs + w.hi + m), axis=1)
    offs = np.concatenate([offs[held], offs[~held]])
    for k0 in range(0, len(offs), 192):
        p = F_.pen(F_.mx[s], w, offs[k0:k0 + 192])
        ok = np.nonzero(p <= TOL)[0]
        if len(ok): return offs[k0 + ok[0]], True
    p = F_.pen(F_.mx[s], w, offs)
    return offs[int(np.argmin(p))], False


def seat_cols(w):
    """underside columns of a shoulder unit that must rest on the frame: a SEAT_AREA patch, or half of a smaller underside"""
    return int(max(3, min(SEAT_AREA / (RES * RES), 0.5 * len(w.bot))))


def rest_z(F_, w, xy, z_lo, limit=SEAT_FIT):
    """for each origin (x, y) in xy (K,2): the lowest origin z, coming down from above the frame, at which unit w still overlaps the idle
    frame by <= limit (bisection on the RES grid, a third of the unit's voxels), or NaN when it meets nothing before z_lo"""
    xy = np.atleast_2d(np.asarray(xy, float)); K = len(xy); idle = F_.per['full'][0]
    hi = np.full(K, np.nan); flat = np.full(K, np.nan); need = seat_cols(w)
    for i, (x, y) in enumerate(xy):
        c = F_.under(w, (x, y, 0.0)) - w.bot[:, 2]; c = c[np.isfinite(c)]
        if len(c) < need: continue
        hi[i] = np.ceil((c.max() + 0.5 * RES) / RES) * RES               # touching from above: clear by construction
        flat[i] = np.sort(c)[-need] + 0.5 * RES                          # the height at which a seat patch of the underside is half a voxel in
    lo = np.full(K, float(np.floor(z_lo / RES) * RES))
    live = np.isfinite(hi) & (hi > lo); keep = np.zeros(K, bool)
    if live.any():
        p = F_.pen(idle, w, np.column_stack([xy[live], lo[live]]), thin=True)
        free = np.zeros(K, bool); free[np.nonzero(live)[0][p <= limit]] = True
        # still within the limit at the floor (a wide unit with only a sliver of the frame under it): it rests where its seat patch
        # touches, when that is above the floor; else there is nothing to rest on
        hi[free] = np.where(flat[free] >= lo[free], flat[free], np.nan); live &= ~free
        keep = free & np.isfinite(hi)
    for _ in range(8):
        act = live & (hi - lo > RES + 1e-6)
        if not act.any(): break
        mid = np.round(((lo + hi) / 2) / RES) * RES
        p = F_.pen(idle, w, np.column_stack([xy[act], mid[act]]), thin=True)
        ai = np.nonzero(act)[0]; ok = p <= limit
        hi[ai[ok]] = mid[ai[ok]]; lo[ai[~ok]] = mid[ai[~ok]]
    hi[~(live | keep)] = np.nan
    return hi


def fit_shoulder(F_, w, s, anchor, hp):
    """origin for shoulder unit w on side s: resting on the idle frame near the shoulder joint (see the module docstring)"""
    fr = F_.fr; sg = SIDE[s]; h = fr.h; k = h / 288.0
    ax, ay, az = (anchor if anchor is not None else np.asarray(hp, float))[:3]
    # the shoulder top: the idle surface over the joint (median within 10 u, so a neighbouring hull roof or aerial does not set it)
    ix = int((ax - F_.org[0]) / RES); iy = int((ay - F_.org[1]) / RES); r = int(10 / RES)
    win = F_.top0[max(0, ix - r):ix + r + 1, max(0, iy - r):iy + r + 1]
    zS = float(np.nanmedian(win)) if np.isfinite(win).any() else float(az)
    py = fr.pv[1]; dx0 = -0.03 * h; wc = (w.lo + w.hi) / 2; need = seat_cols(w)
    z_floor = min(az, zS) - 0.06 * h - w.lo[2]                           # never below the shoulder joint: that is the arm
    idle = F_.per['full'][0]

    def spots(dxs, dys):
        out = []
        for dx in dxs:
            for dyo in dys:
                ox, oy = ax + dx - wc[0], ay + sg * dyo - wc[1]          # the unit's centre near the joint
                # each unit stays on its own side of the centre plane (2 u gap)
                if sg < 0 and oy + w.hi[1] > py - 2: continue
                if sg > 0 and oy + w.lo[1] < py + 2: continue
                if np.isfinite(F_.under(w, (ox, oy, 0.0))).sum() < need: continue      # (almost) nothing of the frame under it
                out.append((ox, oy, dx, dyo))
        return np.array(out) if out else np.zeros((0, 4))

    def score(S):
        """[cost, ox, oy, oz] per spot (NaN cost: no rest)"""
        z = rest_z(F_, w, S[:, :2], z_floor)
        R = []
        for (ox, oy, dx, dyo), oz in zip(S, z):
            if not np.isfinite(oz): continue
            gap = F_.seat(w, (ox, oy, oz))[0]
            rise = max(0.0, oz + w.lo[2] - zS)
            R.append((2.0 * max(0.0, gap - RES) + 0.4 * rise + 0.5 * abs(dx - dx0) + 0.7 * abs(dyo), ox, oy, oz, dx, dyo))
        return sorted(R)

    S = spots(np.arange(-80, 31, 10.0) * k, np.arange(-20, 81, 10.0) * k)
    R = score(S) if len(S) else []
    if not R: return np.round(np.asarray(hp, float) - w.grip, 1), False
    # around the best coarse spot on the 5 u grid, then the moving poses decide between the best few
    _, _, _, _, bdx, bdy = R[0]
    S2 = spots([bdx - 5 * k, bdx, bdx + 5 * k], [bdy - 5 * k, bdy, bdy + 5 * k])
    R = sorted(R[:5] + (score(S2) if len(S2) else []))
    best = None
    for c, ox, oy, oz, _, _ in R[:5]:
        o = np.array([ox, oy, oz])
        move = max(float(F_.pen(f, w, o, thin=True)[0]) for f in F_.per['full'][1:])
        c2 = c + 1.0 * max(0.0, move - MOVE_FIT)
        if best is None or c2 < best[0]: best = (c2, o)
    o = np.round(best[1], 1)
    for _ in range(4):                                                   # the search used a third of the unit's voxels: settle on the full set
        if F_.pen(idle, w, o)[0] <= SEAT_FIT: break
        o = np.round(o + np.array([0, 0, RES]), 1)
    gap, sup, on = F_.seat(w, o)
    return o, on and gap <= FLOAT_TOL and F_.pen(idle, w, o)[0] <= SEAT_PEN


# ---------------------------------------------------------------- one frame (a worker)
_W = None


def _init():
    global _W
    M = jload(MODELS_JSON); kinds = weapon_kinds()
    _W = {k: Weapon(k, kinds[k], v) for k, v in M['weapons'].items() if k in kinds}


def do_frame(args):
    key, entry, over, stored, fit = args
    t0 = time.time()
    fr = Frame(key, entry, over)
    F_ = Fields(fr)
    hp = entry.get('hardpoints') or {}
    res = dict(frame=key, height=fr.h, pairs={}, hands={}, mounts={}, seconds=0)
    for s in 'rl':
        P = [p for p in F_.palms[s] if p is not None]
        if P:
            dr = max(float(np.linalg.norm(p - P[0])) for p in P)
            res['hands'][s] = dict(bone=fr.hand_src[s][0] if s in fr.hand_src else fr.names[fr.hand[s]], palm=np.round(P[0], 1).tolist(), drift=round(dr, 1),
                                   drift_pose=F_.poses[int(np.argmax([np.linalg.norm(p - P[0]) for p in P]))][0],
                                   # a mech holding a hand weapon keeps the idle upper clip while it walks (30_render.js rigAnimate,
                                   # IFR_ARMED_SWAY): its palms move only with idle and the fire clips
                                   drift_armed=round(max(float(np.linalg.norm(p - F_.palms[s][0])) for p, ps in zip(F_.palms[s], F_.poses)
                                                         if p is not None and not ps[0].startswith(('walk', 'run'))), 1))
        else: res['hands'][s] = dict(bone=None)
    for wk, w in _W.items():
        row = {}; mount = []
        for s in 'rl':
            slot = ('r' if s == 'r' else 'l') + ('a' if w.kind == 'arm' else 's')
            hpp = np.array(hp.get(slot, [0, 0, 0]), float)
            var = s if w.kind == 'arm' else 'full'
            old = F_.worst(var, w, hpp - (w.lo + w.hi) / 2)                  # the old placement: the prop's bounds centre on the hard-point
            palm = F_.palms[s][0] if w.kind == 'arm' else None
            if fit:
                if w.kind == 'arm': o, ok = fit_arm(F_, w, s, palm if palm is not None else hpp)
                else: o, ok = fit_shoulder(F_, w, s, F_.shoulders[s], hpp)
            else:
                st = stored.get(wk)
                o = np.array(st[0:3] if s == 'r' else st[3:6], float) if st else hpp - w.grip
            o = np.round(np.asarray(o, float), 1); new = F_.worst(var, w, o)   # measured exactly as stored
            d = dict(old=round(old[0], 1), old_pose=old[1], pen=round(new[0], 1), pose=new[1], origin=np.round(o, 1).tolist())
            if w.kind == 'shoulder':
                gap, sup, on = F_.seat(w, o)
                d['seat'] = round(gap, 1); d['support'] = round(sup, 2); d['pen_idle'] = round(float(F_.pen(F_.per['full'][0], w, o)[0]), 1)
            if w.kind == 'arm':
                ref = palm if palm is not None else hpp
                d['grip_off'] = round(float(np.linalg.norm(o + w.grip - ref)), 1); d['palm'] = palm is not None
                m = ALIGN * fr.h; d['held'] = bool(np.all(ref >= o + w.lo - m) and np.all(ref <= o + w.hi + m))
            row[s] = d; mount += [round(float(x), 1) for x in o]
        res['pairs'][wk] = row; res['mounts'][wk] = mount
    res['seconds'] = round(time.time() - t0, 1)
    return res


# ---------------------------------------------------------------- main
def verdict(res, unfit):
    """[(weapon, side, reason)] failures of one frame"""
    bad = []
    for wk, row in res['pairs'].items():
        if wk in unfit: continue
        for s, d in row.items():
            if 'seat' in d:                                               # a shoulder unit: seated, not merged
                if d['seat'] > FLOAT_TOL: bad.append((wk, s, 'floating: %.1f u over the frame (%.0f %% of the underside has frame below it)' % (d['seat'], 100 * d['support'])))
                if d['pen_idle'] > SEAT_PEN: bad.append((wk, s, 'sunk %.1f u into the idle frame' % d['pen_idle']))
                if d['pen'] > MOVE_PEN: bad.append((wk, s, 'penetration %.1f u (%s)' % (d['pen'], d['pose'])))
                continue
            if d['pen'] > TOL: bad.append((wk, s, 'penetration %.1f u (%s)' % (d['pen'], d['pose'])))
            if d.get('palm') and not d.get('held', True): bad.append((wk, s, 'hand off the weapon (grip %.1f u from the palm)' % d['grip_off']))
    return bad


def write_doc(results, kinds, cat):
    L = ['# IRONFRAME weapon fit', '',
         'Generated by `tools/weapon_fit.py --fit` (do not edit by hand). Each frame x weapon placement measured against the frame mesh in the idle, walk, run',
         'and aim poses: penetration = how deep the weapon sits inside the frame (u; resting contact reads ~%.1f), tolerance %.1f u. Arm weapons leave the' % (RES, TOL),
         'holding forearm and hand out (the hand closes round the grip). "old" = the placement before 10 Nov 2026 (weapon centre on the hard-point).',
         'Shoulder units rest on the idle frame: **seat** = how far the unit hovers over a %.0f u^2 patch of the frame under it (u; <= 0 = it rests on or' % SEAT_AREA,
         'in that patch, negative when a fin or overhang of the frame stands above it; over %.1f = floating), **idle** = its overlap with the idle frame' % FLOAT_TOL,
         '(tolerance %.1f u: seated slightly into the shoulder), **move** = the worst overlap in any other pose (tolerance %.1f u: the unit is rigid on the' % (SEAT_PEN, MOVE_PEN),
         'upper body while the arms and shoulder armour move under it).',
         'Review sheets: `preview/weapons/<frame>.png`, every shoulder unit `preview/weapons/shoulders_<frame>.png` (tools/review_mounts.py).', '',
         '| frame | class h | hands (bone, palm drift holding a weapon: idle + fire clips / with the walk arm swing) | arms: worst old (pair) | arms: worst now (pair) | arm grip off palm max | shoulders: seat max (pair) | idle max | move max (pair, pose) | fails |',
         '|---|---|---|---|---|---|---|---|---|---|']
    for k in sorted(results):
        r = results[k]; unfit = (cat['frames'].get(k, {}).get('mount') or {}).get('unfit', {})
        arm = [(wk, s, d) for wk, row in r['pairs'].items() for s, d in row.items() if 'seat' not in d]
        sh = [(wk, s, d) for wk, row in r['pairs'].items() for s, d in row.items() if 'seat' in d]
        wo = max(((d['old'], '%s %s' % (wk, s)) for wk, s, d in arm), default=(0, '-'))
        wn = max(((d['pen'], '%s %s' % (wk, s)) for wk, s, d in arm), default=(0, '-'))
        go = max((d.get('grip_off', 0) for row in r['pairs'].values() for d in row.values() if d.get('palm')), default=0)
        ss = max(((d['seat'], '%s %s' % (wk, s)) for wk, s, d in sh), default=(0, '-'))
        si = max((d['pen_idle'] for wk, s, d in sh), default=0)
        sm = max(((d['pen'], '%s %s, %s' % (wk, s, d['pose'])) for wk, s, d in sh), default=(0, '-'))
        hands = ', '.join('%s %s %.0f / %.0f u' % (s, (r['hands'][s].get('bone') or 'none'), r['hands'][s].get('drift_armed', r['hands'][s].get('drift', 0)), r['hands'][s].get('drift', 0)) if r['hands'][s].get('bone') else '%s none' % s for s in 'rl')
        bad = verdict(r, unfit)
        L.append('| %s | %.0f | %s | %.1f (%s) | %.1f (%s) | %.1f | %+.1f (%s) | %.1f | %.1f (%s) | %s |' % (
            k, r['height'], hands, wo[0], wo[1], wn[0], wn[1], go, ss[0], ss[1], si, sm[0], sm[1],
            ('%d: ' % len(bad) + '; '.join('%s %s' % (a, b) for a, b, _ in bad[:6])) if bad else '-'))
    L += ['', '## Accepted over the tolerance (data/frames.json frames.<key>.mount.unfit)', '']
    any_ = False
    for k in sorted(results):
        for wk, why in ((cat['frames'].get(k, {}).get('mount') or {}).get('unfit', {})).items():
            L.append('- `%s` x `%s`: %s' % (k, wk, why)); any_ = True
    if not any_: L.append('- none')
    for kind, title, cell in (('arm', '## Arm weapons per pair (penetration now / old, u)', lambda row: '%.0f/%.0f' % (max(d['pen'] for d in row.values()), max(d['old'] for d in row.values()))),
                              ('shoulder', '## Shoulder units per pair (seat gap / idle overlap / worst overlap in another pose, u; the worse side)',
                               lambda row: '%+.0f/%.0f/%.0f' % (max(d.get('seat', 0) for d in row.values()), max(d.get('pen_idle', 0) for d in row.values()), max(d['pen'] for d in row.values())))):
        L += ['', title, '']
        wks = sorted(k for k in kinds if kinds[k] == kind)
        L.append('| frame | ' + ' | '.join(wks) + ' |'); L.append('|---' * (len(wks) + 1) + '|')
        for k in sorted(results):
            r = results[k]
            L.append('| %s | ' % k + ' | '.join(cell(r['pairs'][wk]) if r['pairs'].get(wk) else '-' for wk in wks) + ' |')
    open(DOC, 'w', encoding='utf-8', newline='\n').write('\n'.join(L) + '\n')


def models_lock(who, wait=1200):
    """out/addon/_gen/models.json.lock, created exclusively (several agents write models.json): waits while another holds it, a lock
    older than 15 min is stale. -> the path (delete it when done)"""
    lock = MODELS_JSON + '.lock'; t0 = time.time()
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY); os.write(fd, ('%s pid %d %s\n' % (who, os.getpid(), time.strftime('%H:%M:%S'))).encode()); os.close(fd)
            return lock
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(lock) > 900: os.remove(lock); continue
            except OSError: continue
            if time.time() - t0 > wait: raise RuntimeError('models.json.lock held for over %d s' % wait)
            time.sleep(2)


def main():
    a = sys.argv[1:]
    fit = '--fit' in a
    only = set(a[a.index('--only') + 1].split(',')) if '--only' in a else None
    jobs = int(a[a.index('--jobs') + 1]) if '--jobs' in a else min(3, os.cpu_count() or 2)   # ~0.3-0.8 GB per worker (Aretha's 700 u grid the most)
    M = jload(MODELS_JSON); cat = jload(FRAMES_JSON); kinds = weapon_kinds()
    mounts = M.get('mounts') or {}
    if not fit and not mounts.get('frames'):
        print('models.json has no mounts: run python -I tools/weapon_fit.py --fit'); return 1
    keys = [k for k in M['frames'] if not only or k in only]
    work = [(k, M['frames'][k], (cat['frames'].get(k, {}).get('mount') or {}), (mounts.get('frames') or {}).get(k, {}), fit) for k in keys]
    t0 = time.time(); results = {}
    print('weapon_fit: %s %d frames x %d weapons, %d jobs, RES %.1f u, TOL %.1f u' % ('fitting' if fit else 'checking', len(keys), len(M['weapons']), jobs, RES, TOL), flush=True)
    if jobs > 1 and len(work) > 1:
        from multiprocessing import Pool
        with Pool(jobs, initializer=_init) as pool:
            for i, r in enumerate(pool.imap_unordered(do_frame, work)):
                results[r['frame']] = r; report_line(i + 1, len(work), r, cat, t0)
    else:
        _init()
        for i, w in enumerate(work):
            r = do_frame(w); results[r['frame']] = r; report_line(i + 1, len(work), r, cat, t0)
    if fit:
        lock = models_lock('weapon_fit --fit') if '--lock' in a else None     # --lock: several sessions write models.json (not when the caller holds the lock)
        try:
            M = jload(MODELS_JSON)                                            # re-read: other tools may have written meanwhile
            mo = M.get('mounts') or {}
            mo.update(v=2, tol=TOL, res=RES, seat=dict(fit=SEAT_FIT, pen=SEAT_PEN, move=MOVE_PEN, float=FLOAT_TOL),
                      grips={k: np.round(w_grip(k, kinds), 1).tolist() for k in kinds if k in M['weapons']})
            fr = mo.get('frames') or {}
            for k, r in results.items(): fr[k] = r['mounts']
            mo['frames'] = {k: fr[k] for k in M['frames'] if k in fr}
            M['mounts'] = mo
            tmp = MODELS_JSON + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f: json.dump(M, f, indent=1)
            os.replace(tmp, MODELS_JSON)
        finally:
            if lock: os.remove(lock)
        print('models.json#mounts: %d frames' % len(mo['frames']))
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    old = jload(REPORT) if os.path.exists(REPORT) and only else {}
    old.update(results); json.dump(old, open(REPORT, 'w', encoding='utf-8'), indent=1)
    if fit and all(k in old for k in M['frames']): write_doc({k: old[k] for k in M['frames']}, kinds, cat)   # --only: the other rows from the report
    nbad = 0
    for k in sorted(results):
        bad = verdict(results[k], (cat['frames'].get(k, {}).get('mount') or {}).get('unfit', {}))
        for wk, s, why in bad: print('FAIL %-16s %-13s %s %s' % (k, wk, s, why)); nbad += 1
    print('%s: %d frames, %d failures, %.0f s' % ('weapon fit' if fit else 'weapon clearance check', len(results), nbad, time.time() - t0))
    return 1 if nbad else 0


_GRIPS = {}


def w_grip(k, kinds):
    if k not in _GRIPS:
        M = jload(MODELS_JSON); smd, _ = RW.entry_paths(k, M['weapons'][k]); t, _, _ = RW.load_smd(smd)
        _GRIPS[k] = WP.grip_point(k, kinds[k], t.reshape(-1, 3))[0]
    return _GRIPS[k]


def report_line(i, n, r, cat, t0):
    unfit = (cat['frames'].get(r['frame'], {}).get('mount') or {}).get('unfit', {})
    wn = max(((d['pen'], wk) for wk, row in r['pairs'].items() for d in row.values() if 'seat' not in d), default=(0, '-'))
    ss = max(((d['seat'], wk) for wk, row in r['pairs'].items() for d in row.values() if 'seat' in d), default=(0, '-'))
    si = max((d['pen_idle'] for row in r['pairs'].values() for d in row.values() if 'seat' in d), default=0)
    sm = max((d['pen'] for row in r['pairs'].values() for d in row.values() if 'seat' in d), default=0)
    print('[%d/%d] %-16s arms worst %4.1f u (%s)  shoulders seat max %+5.1f u (%s) idle %4.1f move %4.1f  fails %d  %.0f s (elapsed %.0f s)' % (
        i, n, r['frame'], wn[0], wn[1], ss[0], ss[1], si, sm, len(verdict(r, unfit)), r['seconds'], time.time() - t0), flush=True)


if __name__ == '__main__':
    sys.exit(main())
