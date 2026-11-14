"""Procedural clips for IRONFRAME mech frames (legs / upper props), called by mdl2cs2.py --animate.

Finds the arm and leg chains of a converted GMod rig by bone name (ValveBiped, AC4 Japanese names, AC english packs, Titanfall 2,
ME3 Atlas, FEAR Mule), builds a small rig (root, pelvis/torso, thigh/shin/foot or upper arm/forearm per side), re-weights the
mesh to it, and writes a skinned reference SMD (+ weighted LOD SMDs), one animation SMD per clip and a vmdl with an AnimationList.

Conventions: model space is +X forward, +Y left, +Z up, feet at the origin. Every rig bone has an identity bind rotation in model
space, so a bone's local rotation is a model-space rotation about its joint. ModelDoc turns SMDs 90 degrees about Z: the root bone
carries a -90 degree turn in the reference and in every clip, mesh positions are written (y, -x, z) (docs/creation/models.md).
Rotation sign: Ry(+a) swings a hanging foot backwards (-X) and tips a standing figure's top forward; Rx(+a) swings a hanging foot toward +Y.
"""
import math, os, re
import numpy as np

FPS = 64
STYLE = {'fear3_mule': 'heavy', 'me2_loki': 'stiff'}      # per-frame gait character (mname without _legs / _upper)
# Stance: how far every clip brings the planted feet in toward the hips, as a fraction of the bind pose's hip-to-ankle sideways
# offset (0 = feet where the bind pose has them, 1 = straight under the hips). Generated meshes often stand A-legged: IRONFRAME's
# Tripo heavy has its ankles 28 u further out than its hips (legs leaning out ~10 deg; skink52, 14 Nov 2026: "the legs are
# slightly angled outwards").
STANCE_IN = {'tripo_bastion': 0.7, 'tripo_kestrel': 0.6, 'tripo_scout': 0.5, 'tripo_warden': 0.5}   # Kestrel ~20 deg out, Scout ~10, Warden ~14
LEG_CLIPS = ['hover', 'move', 'boost', 'air', 'land', 'qb_l', 'qb_r']
UP_CLIPS = ['idle', 'fire_r', 'fire_l', 'fire_s', 'stagger']

# ---------------------------------------------------------------- math
def Rx(a):
    c, s = math.cos(a), math.sin(a); return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
def Ry(a):
    c, s = math.cos(a), math.sin(a); return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
def Rz(a):
    c, s = math.cos(a), math.sin(a); return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
def rad(d): return d * math.pi / 180.0
FIX = Rz(-math.pi / 2)

def euler_smd(R):
    """SMD euler (rx, ry, rz) for R = Rz Ry Rx"""
    sy = -R[2, 0]
    if abs(sy) < 0.99999: return math.atan2(R[2, 1], R[2, 2]), math.asin(sy), math.atan2(R[1, 0], R[0, 0])
    return math.atan2(-R[1, 2], R[1, 1]), math.copysign(math.pi / 2, sy), 0.0

def rot_between(a, b):
    a = a / np.linalg.norm(a); b = b / np.linalg.norm(b)
    v = np.cross(a, b); c = float(a @ b)
    if c < -0.99999:
        ax = np.cross(a, [1, 0, 0]);
        if np.linalg.norm(ax) < 1e-3: ax = np.cross(a, [0, 1, 0])
        ax /= np.linalg.norm(ax); K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]]); return np.eye(3) + 2 * K @ K
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K / (1 + c)

def unit(v): v = np.asarray(v, float); return v / np.linalg.norm(v)

# ---------------------------------------------------------------- chains by bone name
# {S} = l|r, {W} = left|right (lower case names). Each family: arm = (upper, lower, end), leg = (upper, lower, end)
FAMILIES = [
    # Mixamo rigs (Tripo GLBs): create/glbrig.py renames the bones to ValveBiped for the other tools and keeps the original name in
    # 'src'; matched on that, so these rigs get their own family. floor=True (every leg family since 10 Nov 2026): feet kept above the floor
    # in the hover / boost / air / QB clips (13 GMod frames sank 3-50 u in hover before)
    dict(name='mixamo', key='src', arm=(r'^(?:mixamorig\d*:)?{W}arm$', r'^(?:mixamorig\d*:)?{W}forearm$', r'^(?:mixamorig\d*:)?{W}hand$'),
         leg=(r'^(?:mixamorig\d*:)?{W}upleg$', r'^(?:mixamorig\d*:)?{W}leg$', r'^(?:mixamorig\d*:)?{W}foot$'), floor=True),
    dict(name='valve', arm=(r'^valvebiped\.bip01_{S}_upperarm$', r'^valvebiped\.bip01_{S}_forearm$', r'^valvebiped\.bip01_{S}_hand$'),
         leg=(r'^valvebiped\.bip01_{S}_thigh$', r'^valvebiped\.bip01_{S}_calf$', r'^valvebiped\.bip01_{S}_foot$'), floor=True),
    dict(name='ac4jp', arm=(r'^{S}_ude$', r'^{S}_te$', None), hand_only=True,   # Moon.'s AC rigs: ude is the whole arm (2ude / 1ude are shoulder caps), te the hand: no elbow
          leg=(r'^{S}_momo$', r'^{S}_sune$', r'^{S}_(?:kakato|asi)$'), floor=True),
    dict(name='ac4jp_kata', arm=(r'^{S}_kata$', r'^{S}_2ude$', r'^{S}_te$'), leg=None),
    dict(name='acpack', arm=(r'^upperarm {W}$', r'^forearm {W}$', r'^hand {W}$'), leg=(r'^thigh {W}$', r'^(?:knee|calf|shin) {W}$', r'^foot {W}$'), floor=True),
    dict(name='tf2', arm=(r'^def_{S}_shoulder$', r'^def_{S}_elbow$', r'^valvebiped\.bip01_{S}_hand$'), leg=(r'^def_{S}_thigh$', r'^def_{S}_knee$', r'^def_{S}_ankle$'), floor=True),
    dict(name='atlas', arm=(r'^{W}shoulder$', r'^{W}arm$', r'^{W}hand$'), leg=(r'^{W}upperleg$', r'^{W}calf$', r'^{W}foot$'), floor=True),
    dict(name='mule', arm=None, leg=(r'^{W}_leg1$', r'^{W}_leg2$', r'^{W}_leg3$'), floor=True),
]
WAIST_EXACT = [r'^valvebiped\.bip01_pelvis$', r'^pelvis$', r'^def_c_hip$', r'^kosi$', r'^lower body$', r'^hip$', r'^waist$', r'^upper body$']
WAIST_ANY = re.compile(r'(?i)pelvis|hip|lower.?body|waist|root')
SIDED = re.compile(r'(?i)(^|[ _.\-])(l|r|left|right)([ _.\-\d]|$)|^(left|right)')


def _find(bones, tmpl, side, key='name'):
    S, W = ('l', 'left') if side == 'l' else ('r', 'right')
    rx = re.compile(tmpl.replace('{S}', S).replace('{W}', W))
    for i, b in enumerate(bones):
        if rx.search((b.get(key) or '').lower()): return i
    return None


def waist_bone(bones):
    """index of the pelvis / hip bone (None if the skeleton has nothing usable)"""
    for t in WAIST_EXACT:
        rx = re.compile(t)
        for i, b in enumerate(bones):
            if rx.search(b['name'].lower()): return i
    for i, b in enumerate(bones):
        if WAIST_ANY.search(b['name']) and not SIDED.search(b['name']): return i
    return None


def find_chain(bones, kind):
    """-> {'l': (up, lo, end|None), 'r': (...), 'family': name} or None; both sides needed"""
    for fam in FAMILIES:
        t = fam[kind]
        if not t: continue
        out = {}
        bk = fam.get('key', 'name')
        for side in 'lr':
            up, lo = _find(bones, t[0], side, bk), _find(bones, t[1], side, bk)
            if up is None or lo is None or up == lo: break
            out[side] = (up, lo, _find(bones, t[2], side, bk) if t[2] else None)
        else:
            if out['l'][0] != out['r'][0]:
                out['family'] = fam['name']; out['hand_only'] = bool(fam.get('hand_only')); out['floor'] = bool(fam.get('floor')); return out
    return None

# ---------------------------------------------------------------- rig
class Rig:
    def __init__(self): self.names, self.par, self.pos, self.vec = [], [], [], []
    def add(self, name, par, pos, vec=None):
        self.names.append(name); self.par.append(par); self.pos.append(np.asarray(pos, float)); self.vec.append(None if vec is None else np.asarray(vec, float)); return len(self.names) - 1
    def idx(self, n): return self.names.index(n)
    def fk_locals(self, Rw):
        """local rotations (model space, identity bind) from world rotations; bones not in Rw inherit their parent's"""
        W = []
        for i in range(len(self.names)):
            W.append(Rw.get(self.names[i], W[self.par[i]] if self.par[i] >= 0 else np.eye(3)))
        return [W[i] if self.par[i] < 0 else W[self.par[i]].T @ W[i] for i in range(len(W))]


def _ext(bones, ch, bp, height):
    up, lo, end = ch
    v = bp[lo] - bp[up]
    return (bp[end] - bp[lo]) if end is not None and np.linalg.norm(bp[end] - bp[lo]) > 0.02 * height else v * 0.9


def build_rig(kind, bones, bp, height, waist_i):
    """kind 'legs' | 'upper'. -> (rig, srcmap {source bone: rig index}, fallback rig index, info) or (None, reason)"""
    ch = find_chain(bones, 'leg' if kind == 'legs' else 'arm')
    if ch is None: return None, 'no %s chain by bone name' % ('leg' if kind == 'legs' else 'arm')
    if waist_i is None: return None, 'no pelvis/waist bone'
    rig = Rig(); root = rig.add('root', -1, [0, 0, 0]); wb = rig.add('pelvis' if kind == 'legs' else 'torso', root, bp[waist_i])
    smap = {waist_i: wb}
    info = {'family': ch['family'], 'hand_only': bool(ch.get('hand_only')) and kind == 'upper', 'floor': bool(ch.get('floor'))}
    for side in 'lr':
        up, lo, end = ch[side]
        sd = 1 if bp[up][1] > bp[waist_i][1] else -1
        if kind == 'legs' and not (bp[up][2] > bp[lo][2] + 0.03 * height): return None, 'leg chain not hanging (thigh not above knee)'
        if kind == 'upper' and abs(bp[up][1] - bp[waist_i][1]) < 0.01 * height and abs(bp[lo][1] - bp[waist_i][1]) < 0.01 * height: return None, 'arm chain on the centre line'
        a = rig.add(('thigh_%s' if kind == 'legs' else 'arm_up_%s') % side, wb, bp[up], bp[lo] - bp[up])
        b = rig.add(('shin_%s' if kind == 'legs' else 'arm_lo_%s') % side, a, bp[lo], _ext(bones, ch[side], bp, height))
        smap[up] = a; smap[lo] = b
        if kind == 'legs' and end is not None and np.linalg.norm(bp[end] - bp[lo]) > 0.02 * height:
            f = rig.add('foot_%s' % side, b, bp[end], [1, 0, 0]); smap[end] = f
            for j, bj in enumerate(bones):                       # toe bones hanging off the shin beside the heel bone (AC: tuma) belong to the foot, not the shin
                q, hops = bj['parent'], 0
                while q is not None and q >= 0 and q != lo and hops < 64: q = bones[q]['parent']; hops += 1
                if q == lo and j != end and re.search(r'(?i)tuma|toe|ball', bj['name']): smap[j] = f
        elif kind == 'upper' and end is not None and np.linalg.norm(bp[end] - bp[lo]) > 0.02 * height and not ch.get('hand_only'):
            h = rig.add('arm_hand_%s' % side, b, bp[end], bp[end] - bp[lo]); smap[end] = h             # wrist bone: follow-through and the recoil whip
        elif end is not None: smap[end] = b
        info['sd_' + side] = sd
        if kind == 'legs':
            e = bp[end] if end is not None else bp[lo] + (bp[lo] - bp[up])
            info['knee_sign'] = -1 if (bp[lo][0] - (bp[up][0] + e[0]) / 2) < -0.04 * height else 1
    return (rig, smap, wb, info), None

# ---------------------------------------------------------------- clips
def env(t, T, peak=0.2):
    """0 -> 1 at peak*T -> 0 at T (quick attack, soft decay)"""
    u = t / T
    return u / peak if u < peak else max(0.0, 1 - (u - peak) / (1 - peak)) ** 2

def sine_env(t, T): return math.sin(math.pi * t / T)


# ---------------------------------------------------------------- IK + weighty gait
def _ease(a):                      # cosine ease 0..1
    return 0.5 - 0.5 * math.cos(math.pi * min(1.0, max(0.0, a)))

def _keys(x, pts):
    """cosine-eased interpolation through [(x, y), ...] (x ascending)"""
    if x <= pts[0][0]: return pts[0][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x <= x1: return y0 + (y1 - y0) * _ease((x - x0) / max(1e-9, x1 - x0))
    return pts[-1][1]

def _frame(d, pole=(1.0, 0.0, 0.0)):
    """orthonormal frame, columns (pole component perpendicular to d, d x that, d)"""
    d = unit(d); p = np.asarray(pole, float); q = p - (p @ d) * d
    if np.linalg.norm(q) < 1e-4: q = np.array([0.0, 1.0, 0.0]) - d[1] * d
    q = unit(q); return np.stack([q, np.cross(d, q), d], 1)

class LegGeo:
    """one leg's bind geometry + two-bone IK (hinge knee: the knee sits on the s * +X side of the hip-ankle line)"""
    def __init__(self, rig, side, s):
        self.side, self.s = side, s
        it, ish = rig.idx('thigh_' + side), rig.idx('shin_' + side)
        self.H0 = rig.pos[it].copy(); self.v1 = rig.vec[it].copy(); self.v2 = rig.vec[ish].copy()
        self.l1, self.l2 = float(np.linalg.norm(self.v1)), float(np.linalg.norm(self.v2))
        self.A0 = self.H0 + self.v1 + self.v2
        self.F1 = _frame(self.v1); self.F2 = _frame(self.v2)
        self.has_foot = ('foot_' + side) in rig.names
    def solve(self, H, A):
        """-> (R_thigh, R_shin, over) ; over = requested reach / max reach"""
        D = A - H; d0 = float(np.linalg.norm(D)); Dh = D / max(d0, 1e-6)
        over = d0 / (self.l1 + self.l2)
        d = min(max(d0, abs(self.l1 - self.l2) + 1e-3), (self.l1 + self.l2) * 0.997)
        cd = (self.l1 ** 2 + d * d - self.l2 ** 2) / (2 * self.l1 * d)
        dl = math.acos(max(-1.0, min(1.0, cd)))
        n = np.array([self.s, 0.0, 0.0]); n = n - (n @ Dh) * Dh
        n = unit(n) if np.linalg.norm(n) > 1e-4 else np.array([0.0, 0.0, 1.0])
        K = H + Dh * self.l1 * math.cos(dl) + n * self.l1 * math.sin(dl)
        Ae = H + Dh * d
        return _frame(K - H) @ self.F1.T, _frame(Ae - K) @ self.F2.T, over, K, Ae

def cr_periodic(v, x):
    """periodic Catmull-Rom through the samples v (len n) at position x (in samples, wraps): how the script is told to read hip_curve / sway_curve"""
    n = len(v); i = int(math.floor(x)); f = x - i
    p0, p1, p2, p3 = v[(i - 1) % n], v[i % n], v[(i + 1) % n], v[(i + 2) % n]
    return 0.5 * (2 * p1 + (-p0 + p2) * f + (2 * p0 - 5 * p1 + 4 * p2 - p3) * f * f + (-p0 + 3 * p1 - 3 * p2 + p3) * f ** 3)

def _smooth_circ(v, w, passes=2):
    v = np.asarray(v, float)
    for _ in range(passes):
        acc = np.zeros_like(v)
        for k in range(-w, w + 1): acc += np.roll(v, k)
        v = acc / (2 * w + 1)
    return v

class Gait:
    """Weighty biped cycle: planted stance feet (constant ground speed in the body frame), hips that sink on each plant and rise to a
    locked-straight passing pose, late-rising / slamming feet, toe roll, hip yaw / roll / sway. All lengths in model units.
    m: unit horizontal direction the body travels (+X forward); stride_h: stride (two steps) in hip heights; sf: stance fraction;
    hl: swing lift in hip heights; rkeys: stance progress -> leg chord / full length; pk_st / pk_sw: foot pitch (deg, + toes down)."""
    def __init__(self, legs, info, pel0, name, m, T, stride_h, sf, hl, rkeys, pk_st, pk_sw, yaw=3.5, roll=2.2, sway=0.014,
                 widen=0.0, p0=0.10, flight=False, rise=1.07, smooth=0.05, dip=0.0):
        self.legs, self.info, self.name, self.T, self.sf, self.p0, self.flight = legs, info, name, T, sf, p0, flight
        self.dip = dip                       # extra weight: the body drops onto each plant (fraction of the hip height)
        self.pel0 = np.asarray(pel0, float)
        self.m = np.asarray(m, float)
        L = [legs[s] for s in 'lr']
        self.lmax = float(np.mean([g.l1 + g.l2 for g in L]))
        self.hh0 = float(np.mean([g.H0[2] - g.A0[2] for g in L]))
        self.stride = stride_h * self.hh0                      # ground covered per full cycle (two steps)
        self.a = self.stride * sf / 2
        self.hl = hl * self.hh0; self.rkeys, self.pk_st, self.pk_sw = rkeys, pk_st, pk_sw
        self.yaw, self.roll, self.sway = yaw, roll, sway * self.hh0
        self.Lf = 0.17 * self.lmax; self.Lh = 0.07 * self.lmax
        fx = info.get('foot_x')
        if fx:                                                       # the real toe / heel reach (long AC feet would dig in with the default guess)
            self.Lf = min(0.45 * self.lmax, max(0.05 * self.lmax, float(np.mean([v[0] for v in fx.values()]))))
            self.Lh = min(0.30 * self.lmax, max(0.03 * self.lmax, float(np.mean([v[1] for v in fx.values()]))))
        self.sdl = info['sd_l']
        self.base = {}
        k_in = float(info.get('stance_in') or 0.0)
        for s in 'lr':
            g = legs[s]; sd = info['sd_' + s]
            self.base[s] = np.array([g.A0[0], g.A0[1] + k_in * (g.H0[1] - g.A0[1]) + sd * widen * self.hh0])
        self.cap = self.hh0 * rise
        N = 256; ts = np.arange(N) / N; hh = np.zeros(N)
        for i, tau in enumerate(ts):
            best = self.cap if not flight else self.cap
            for s in 'lr':
                u = (tau + p0 + (0.0 if s == 'l' else 0.5)) % 1.0
                if u < sf:
                    ho = float(np.linalg.norm(self.foot_xy(s, u)[0] - legs[s].H0[:2]))
                    R = _keys(u / sf, rkeys) * self.lmax
                    best = min(best, math.sqrt(max(R * R - ho * ho, (0.3 * self.lmax) ** 2)))
            hh[i] = best
        hh = _smooth_circ(hh, max(2, int(N * smooth)))
        self.table_t = np.append(ts, 1.0); self.hh = np.append(hh, hh[0])
        self.speed = self.stride / T
        self.build_curve()
    def foot_xy(self, s, u):
        sf, a = self.sf, self.a
        if u < sf:
            return self.base[s] + self.m * (a - 2 * a * (u / sf)), 0.0
        q = (u - sf) / (1 - sf)
        tg = -0.5 * 2 * a * (1 - sf) / sf
        h00, h10, h01, h11 = 2 * q ** 3 - 3 * q ** 2 + 1, q ** 3 - 2 * q ** 2 + q, -2 * q ** 3 + 3 * q ** 2, q ** 3 - q ** 2
        d = h00 * -a + h10 * tg + h01 * a + h11 * tg
        return self.base[s] + self.m * d, self.hl * math.sin(math.pi * q ** 1.4) ** 1.1
    def pitch(self, u):
        if u < self.sf: return _keys(u / self.sf, self.pk_st)
        return _keys((u - self.sf) / (1 - self.sf), self.pk_sw)
    def pelvis_exact(self, tau):
        """(dz, dy, roll_deg, yaw_deg) at cycle fraction tau, straight from the stance geometry"""
        ul = (tau + self.p0) % 1.0
        dz = min(float(np.interp(tau % 1.0, self.table_t, self.hh)), self.cap) - self.hh0
        if self.dip: dz -= self.dip * self.hh0 * (0.5 + 0.5 * math.cos(4 * math.pi * ul)) ** 1.5
        ph = math.cos(2 * math.pi * (ul - self.sf / 2))
        return dz, self.sdl * self.sway * ph, self.sdl * self.roll * ph, -self.sdl * self.yaw * math.cos(2 * math.pi * ul)
    def build_curve(self, n=16, fine=128, smooth=0.04):
        """the exported hip curve: n samples of the (slightly smoothed) exact hip motion. pelvis() then reads THIS curve with periodic
        Catmull-Rom, i.e. exactly what the script does, so the planted feet stay planted for it"""
        ex = np.array([self.pelvis_exact(i / fine)[:2] for i in range(fine)])
        w = max(1, int(fine * smooth))
        sm = np.stack([_smooth_circ(ex[:, k], w, 2) for k in range(2)], 1)
        self.c16 = [[round(float(sm[i * fine // n, k]), 2) for i in range(n)] for k in range(2)]
    def pelvis(self, tau):
        dz, dy, roll, yaw = self.pelvis_exact(tau)
        c = getattr(self, 'c16', None)
        if c is not None:
            x = (tau % 1.0) * len(c[0]); dz, dy = cr_periodic(c[0], x), cr_periodic(c[1], x)
        return dz, dy, roll, yaw
    def contacts(self):
        return {'l': round((1 - self.p0) % 1.0, 4), 'r': round((1 - self.p0 - 0.5) % 1.0, 4)}
    def pose(self, t, T, want_pts=False):
        tau = (t / T) % 1.0
        dz, dy, roll, yaw = self.pelvis(tau)
        Rp = Rz(rad(yaw)) @ Rx(rad(roll))
        off = np.array([0.0, dy, dz])          # the script moves BOTH props by this (models.json hip_curve / sway_curve); the pelvis bone itself stays on the origin
        R = {'pelvis': Rp, '_off': off}
        over = 0.0; pts = {}
        for s in 'lr':
            g = self.legs[s]
            u = (tau + self.p0 + (0.0 if s == 'l' else 0.5)) % 1.0
            xy, lift = self.foot_xy(s, u)
            p = self.pitch(u)
            rise = self.Lf * math.sin(rad(p)) * 0.9 if p > 0 else self.Lh * math.sin(rad(-p)) * 0.9
            hipw = self.pel0 + off + Rp @ (g.H0 - self.pel0)             # hip in the world, as if the pelvis had moved
            A = np.array([xy[0], xy[1], g.A0[2] + lift + rise])
            dmax = 0.985 * (g.l1 + g.l2); hxy = float(np.linalg.norm(A[:2] - hipw[:2]))
            if (A - hipw) @ (A - hipw) > dmax * dmax: A[2] = hipw[2] - math.sqrt(max(1.0, dmax * dmax - hxy * hxy))      # out of reach: lift the foot, never overstretch
            hip = hipw - off; Al = A - off                               # prop-local: the same chord, with the hip on its bind spot
            Rt, Rs, ov, K, Ae = g.solve(hip, Al); over = max(over, ov)
            R['thigh_' + s] = Rt; R['shin_' + s] = Rs
            if g.has_foot: R['foot_' + s] = Ry(rad(p))
            pts[s] = (hip, K, Ae, p, lift, u)
        R['_over'] = over
        if want_pts: R['_pts'] = pts
        return R

def make_gaits(rig, info):
    """weighty locomotion cycles for a legs rig -> ({clip: Gait}, meta). None when the rig has no usable feet/knees."""
    try:
        legs = {s: LegGeo(rig, s, info['knee_sign']) for s in 'lr'}
        pel0 = rig.pos[rig.idx('pelvis')]
    except Exception:
        return None, {}
    hh0 = float(np.mean([g.H0[2] - g.A0[2] for g in legs.values()]))
    if hh0 < 1.0: return None, {}
    sep = abs(legs['l'].A0[1] - legs['r'].A0[1])
    # foot pitch keys, deg toes-down: stance progress s (heel strike ... toe-off) and swing progress q (lift-off ... touch-down)
    P_WALK = ([(0, -13), (0.12, 0), (0.62, 0), (0.88, 9), (1.0, 24)], [(0, 24), (0.4, 8), (0.75, -2), (1.0, -13)])
    P_BACK = ([(0, 9), (0.14, 0), (0.6, 0), (0.9, -6), (1.0, -12)], [(0, -12), (0.5, 0), (1.0, 9)])
    P_RUN = ([(0, -9), (0.15, 0), (0.6, 6), (1.0, 30)], [(0, 30), (0.4, 38), (0.8, 6), (1.0, -9)])
    P_SIDE = ([(0, -4), (0.2, 0), (0.7, 0), (1.0, 8)], [(0, 8), (0.5, 3), (1.0, -4)])
    R_WALK = [(0, 0.945), (0.14, 0.915), (0.5, 0.975), (0.86, 0.935), (1.0, 0.93)]
    R_RUN = [(0, 0.955), (0.4, 0.88), (0.75, 0.93), (1.0, 0.97)]
    R_SIDE = [(0, 0.95), (0.16, 0.92), (0.5, 0.965), (1.0, 0.94)]
    sf_side, sh_side = 0.64, 0.85
    a_side = sh_side * hh0 * sf_side / 2
    widen = max(0.0, (2 * a_side + 0.30 * hh0 - sep) / (2 * hh0))
    G = {}
    mk = lambda nm, mv, T, *a, **k: Gait(legs, info, pel0, nm, mv, round(T * FPS) / FPS, *a, **k)
    st = info.get('style')
    if st == 'heavy':      # fear3_mule: slow, long ground contact, flat plants, a clear stomp and the whole body dropping onto each step
        P_H = ([(0, -4), (0.12, 0), (0.75, 0), (1.0, 9)], [(0, 9), (0.5, 3), (1.0, -4)])
        R_H = [(0, 0.93), (0.14, 0.90), (0.5, 0.965), (0.86, 0.92), (1.0, 0.915)]
        G['walk'] = mk('walk', (1, 0), 1.6, 1.9, 0.68, 0.20, R_H, *P_H, yaw=2.0, roll=3.2, sway=0.03, dip=0.17)
        G['walk_back'] = mk('walk_back', (-1, 0), 1.7, 1.25, 0.69, 0.16, R_H, *P_H, yaw=1.8, roll=3.0, sway=0.028, dip=0.14)
        G['strafe_l'] = mk('strafe_l', (0, 1), 1.35, sh_side * 1.15, 0.68, 0.17, R_H, *P_H, yaw=1.0, roll=3.4, sway=0.034, widen=widen, dip=0.15)
        G['strafe_r'] = mk('strafe_r', (0, -1), 1.35, sh_side * 1.15, 0.68, 0.17, R_H, *P_H, yaw=1.0, roll=3.4, sway=0.034, widen=widen, dip=0.15)
        G['run'] = mk('run', (1, 0), 1.0, 2.6, 0.50, 0.26, R_RUN, *P_RUN, yaw=3.0, roll=3.6, sway=0.026, flight=True, smooth=0.035, rise=1.05, dip=0.12)
    elif st == 'stiff':    # me2_loki: a humanoid made to look mechanical: short stiff-kneed steps, a quick even cadence, almost no hip roll
        R_S = [(0, 0.975), (0.14, 0.965), (0.5, 0.99), (0.86, 0.972), (1.0, 0.965)]
        P_S = ([(0, -8), (0.12, 0), (0.62, 0), (0.88, 6), (1.0, 14)], [(0, 14), (0.4, 6), (0.75, -1), (1.0, -8)])
        G['walk'] = mk('walk', (1, 0), 0.9, 1.05, 0.62, 0.05, R_S, *P_S, yaw=1.6, roll=1.0, sway=0.007, dip=0.012)
        G['walk_back'] = mk('walk_back', (-1, 0), 0.95, 0.75, 0.63, 0.04, R_S, *P_BACK, yaw=1.4, roll=1.0, sway=0.007, dip=0.01)
        G['strafe_l'] = mk('strafe_l', (0, 1), 0.8, sh_side * 0.9, sf_side, 0.06, R_SIDE, *P_SIDE, yaw=1.0, roll=1.4, sway=0.01, widen=widen)
        G['strafe_r'] = mk('strafe_r', (0, -1), 0.8, sh_side * 0.9, sf_side, 0.06, R_SIDE, *P_SIDE, yaw=1.0, roll=1.4, sway=0.01, widen=widen)
        G['run'] = mk('run', (1, 0), 0.62, 1.75, 0.42, 0.12, R_RUN, *P_RUN, yaw=2.5, roll=1.6, sway=0.008, flight=True, smooth=0.035, rise=1.05)
    else:
        G['walk'] = mk('walk', (1, 0), 1.15, 1.4, 0.62, 0.075, R_WALK, *P_WALK, yaw=3.5, roll=2.2, sway=0.014)
        G['walk_back'] = mk('walk_back', (-1, 0), 1.2, 0.95, 0.63, 0.06, R_WALK, *P_BACK, yaw=3.0, roll=2.0, sway=0.013)
        G['strafe_l'] = mk('strafe_l', (0, 1), 0.95, sh_side, sf_side, 0.085, R_SIDE, *P_SIDE, yaw=1.5, roll=2.6, sway=0.02, widen=widen)
        G['strafe_r'] = mk('strafe_r', (0, -1), 0.95, sh_side, sf_side, 0.085, R_SIDE, *P_SIDE, yaw=1.5, roll=2.6, sway=0.02, widen=widen)
        G['run'] = mk('run', (1, 0), 0.8, 2.1, 0.42, 0.17, R_RUN, *P_RUN, yaw=4.5, roll=2.8, sway=0.016, flight=True, smooth=0.035, rise=1.05)
    meta = {'stride': {}, 'steps': {}, 'hip_drop': {}, 'hh': round(hh0, 1), 'leg_len': round(G['walk'].lmax, 1)}
    for k, g in G.items():
        meta['stride'][k] = {'length': round(g.stride, 1), 'speed': round(g.speed, 1), 'period': g.T,
                             'dir': [float(g.m[0]), float(g.m[1])]}
        c = g.contacts(); meta['steps'][k] = {'l': c['l'], 'r': c['r']}
        dz = [g.pelvis(i / 128)[0] for i in range(128)]
        meta['hip_drop'][k] = {'min': round(min(dz), 1), 'max': round(max(dz), 1)}
    return G, meta


def legs_clips(info, rig=None):
    s = info['knee_sign']
    sdl = info['sd_l']                 # +1 when the 'l' bone is on +Y

    def leg(side, hip, bend, foot, roll=0.0, base=None):
        """hip: thigh pitch (deg, + swings the foot back); bend: knee flex; foot: absolute toes-down pitch"""
        sd = info['sd_' + side]
        R = {}
        at = hip; asn = hip + s * bend
        R['thigh_' + side] = Ry(rad(at)) @ Rx(rad(roll)) if base is None else base @ Ry(rad(at)) @ Rx(rad(roll))
        R['shin_' + side] = Ry(rad(asn)) @ Rx(rad(roll)) if base is None else base @ Ry(rad(asn)) @ Rx(rad(roll))
        R['foot_' + side] = Ry(rad(foot))
        return R

    def pose(f):
        def g(t, T):
            R = {}
            for side in 'lr':
                R.update(f(side, info['sd_' + side], t, T, R))
            return R
        return g

    def move(side, sd, t, T, R):                 # legacy clip, kept for older scripts
        ph = 2 * math.pi * t / T; sw = 7 * math.sin(ph) * sd
        return leg(side, 15 + sw, 14 + 4 * math.sin(ph + 1), 14, roll=-2 * sd)

    out = {'move': (0.8, True, pose(move))}
    gaits, meta = (make_gaits(rig, info) if rig is not None else (None, {}))
    if gaits is None:
        # fallback for rigs without a usable IK leg: the old angle poses
        def hover(side, sd, t, T, R):
            ph = 2 * math.pi * t / T + (0 if sd > 0 else 1.3)
            return leg(side, -6 + 2 * math.sin(ph), 16 + 4 * math.sin(ph + 0.6), 8 + 3 * math.sin(ph + 1.0), roll=2 * sd)
        def boost(side, sd, t, T, R):
            ph = 2 * math.pi * t / T
            return leg(side, 35 + 1.5 * math.sin(ph), 22 + 1.5 * math.sin(ph + 1), 48 + 2 * math.sin(ph), roll=-6 * sd)
        def air(side, sd, t, T, R):
            ph = 2 * math.pi * t / T + (0 if sd > 0 else 1.7)
            return leg(side, -12 + 3 * math.sin(ph), 28 + 4 * math.sin(ph + 0.8), 22 + 4 * math.sin(ph), roll=3 * sd)
        def land(side, sd, t, T, R):
            e = sine_env(t, T)
            return leg(side, -6 - 30 * e, 16 + 42 * e, 8 + 20 * e, roll=2 * sd + 3 * sd * e)
        def qb(lean):
            def f(side, sd, t, T, R):
                e = sine_env(t, T) ** 0.7
                pr = Rx(rad(12 * lean * sdl * e))
                return leg(side, 14 * e - 6, 16 + 6 * e, 8 + 14 * e, roll=2 * sd - 4 * lean * e, base=pr) | {'pelvis': pr}
            return f
        out.update({'hover': (3.0, True, pose(hover)), 'boost': (1.5, True, pose(boost)), 'air': (2.0, True, pose(air)),
                    'land': (0.4, False, pose(land)), 'qb_l': (0.35, False, pose(qb(+1))), 'qb_r': (0.35, False, pose(qb(-1)))})
        info['meta'] = {}
        return out

    LG = gaits['walk'].legs; pel0 = gaits['walk'].pel0; hh0 = meta['hh']
    cy = (LG['l'].A0[1] + LG['r'].A0[1]) / 2

    def ik_clip(fn, floor=True):
        """fn(t, T) -> (pelvis_off (3,), Rp, {side: (ankle offset from bind (3,), pitch deg)}); legs solved by IK"""
        def g(t, T):
            off, Rp, feet = fn(t, T)
            off = np.asarray(off, float)
            if fpts and floor: feet = {sd_: _above_floor(sd_, rel, p) for sd_, (rel, p) in feet.items()}
            R = {'pelvis': Rp, '_off': off}        # no pelvis translation: the feet are solved against the bind hip, the script moves the props by `off`
            over = 0.0
            for sd_ in 'lr':
                gg = LG[sd_]; rel, p = feet[sd_]
                hip = pel0 + Rp @ (gg.H0 - pel0)
                Rt, Rs, ov, K, Ae = gg.solve(hip, gg.A0 + np.asarray(rel, float) - off + np.array([0.0, k_in * (gg.H0[1] - gg.A0[1]), 0.0])); over = max(over, ov)
                R['thigh_' + sd_] = Rt; R['shin_' + sd_] = Rs
                if gg.has_foot: R['foot_' + sd_] = Ry(rad(p))
            R['_over'] = over
            return R
        return g

    # feet kept above the floor (families with floor=True; hover / boost / air / QB, not the 0.6 s land): the measured foot mesh
    # (info['foot_pts'], offsets from the ankle) is pitched like the clip pitches it; a toe that would dig in first flattens the
    # tiptoe (down to 35 % of the clip's pitch, while that still needs more than FLOOR_LIFT of extra ankle lift), then the ankle is
    # lifted until the lowest point clears FLOOR_CLEAR (big flat Mixamo feet tiptoed 52 deg in hover dug 7-40 u into the ground;
    # lifting alone bent the heavy's hip seam). Gaits already lift the ankle by the measured toe / heel reach (foot_x).
    fpts = {sd_: np.asarray(v, float) for sd_, v in (info.get('foot_pts') or {}).items()} if info.get('floor') else {}
    FLOOR_CLEAR, FLOOR_LIFT = 1.0, 0.04 * hh0
    def _above_floor(sd_, rel, p):
        q = fpts.get(sd_)
        if q is None: return rel, p
        rel = np.asarray(rel, float); z0 = LG[sd_].A0[2] + rel[2]
        need = lambda pp: FLOOR_CLEAR - (z0 + float((q @ Ry(rad(pp)).T)[:, 2].min()))
        if need(p) <= 0: return rel, p
        pp = p
        while need(pp) > FLOOR_LIFT and abs(pp) > abs(p) * 0.35 + 1e-6: pp -= math.copysign(min(2.0, abs(pp) - abs(p) * 0.35), p)
        n = need(pp)
        return (rel + np.array([0.0, 0.0, n]) if n > 0 else rel), pp

    I3 = np.eye(3)
    k_in = float(info.get('stance_in') or 0.0)
    INW = {sd_: k_in * (LG[sd_].H0[1] - LG[sd_].A0[1]) for sd_ in 'lr'}      # the stance shift ik_clip adds to every foot
    fin = info.get('foot_in') or {}
    GAP = 0.07 * hh0                                   # clear space kept between the two feet's inner edges in hover / boost
    def hover(t, T):
        ft = {}
        for sd_ in 'lr':
            sd = info['sd_' + sd_]; ph = 2 * math.pi * t / T + (0 if sd > 0 else 1.5)
            dyk = sd * max((fin[sd_] + GAP / 2) - abs(LG[sd_].A0[1] + INW[sd_] - cy), 0.035 * hh0) if sd_ in fin else 0.0      # hip abduction: outward, never into the other foot
            ft[sd_] = ((-0.13 * hh0 + 0.025 * hh0 * math.sin(ph), dyk + 0.012 * hh0 * math.sin(ph + 1.0) * sd, 0.11 * hh0 + 0.02 * hh0 * math.sin(ph + 0.7) + (0.03 * hh0 if sd_ == 'l' else 0.0)), 52 + 4 * math.sin(ph + 1.2))
        return (0, 0.006 * hh0 * math.sin(2 * math.pi * t / T), 0), Rx(rad(0.8 * sdl * math.sin(2 * math.pi * t / T))), ft
    def boost(t, T):
        ph = 2 * math.pi * t / T; ft = {}
        for sd_ in 'lr':
            dy = 0.82 * (cy - LG[sd_].A0[1]) - INW[sd_]
            if sd_ in fin:                              # pulled together, but never into each other
                dy = info['sd_' + sd_] * ((fin[sd_] + GAP / 2) - abs(LG[sd_].A0[1] - cy)) - INW[sd_]
            ft[sd_] = ((-0.60 * hh0 + 0.012 * hh0 * math.sin(ph), dy, 0.36 * hh0 + 0.01 * hh0 * math.sin(ph + 1) + (0.035 * hh0 if sd_ == 'l' else 0.0)), 58 + 2 * math.sin(ph))
        return (0, 0, 0), I3, ft
    def air(t, T):
        ft = {}
        for sd_ in 'lr':
            sd = info['sd_' + sd_]; ph = 2 * math.pi * t / T + (0 if sd > 0 else 1.7)
            ft[sd_] = ((-0.05 * hh0 + 0.03 * hh0 * math.sin(ph), 0.04 * hh0 * sd, 0.15 * hh0 + 0.035 * hh0 * math.sin(ph + 0.8)), 26 + 5 * math.sin(ph))
        return (0, 0, 0), I3, ft
    LAND_D = 0.22
    def land_dz(t, T):
        x = t / T
        d = _ease(x / 0.16) if x < 0.16 else 1 - _ease((x - 0.16) / 0.84)
        return -LAND_D * hh0 * d
    def land(t, T):
        dz = land_dz(t, T); x = t / T
        ft = {sd_: ((0.0, 0.0, 0.0), 0.0 + 4 * math.sin(math.pi * min(1.0, x / 0.3))) for sd_ in 'lr'}
        return (0, 0, dz), I3, ft
    def qb(lean):                                 # lean: +1 = toward +Y (the player's left), -1 = right
        def f(t, T):
            e = sine_env(t, T) ** 0.7; ft = {}
            Rp = Rx(rad(-12 * lean * e))              # Rx(+) swings feet to +Y, so the top (and the lean) goes to -Y
            for sd_ in 'lr':
                sd = info['sd_' + sd_]
                if sd * lean < 0: ft[sd_] = ((-0.34 * hh0 * e, -lean * 0.06 * hh0 * e, 0.17 * hh0 * e), 34 * e)      # trailing leg: swept back, straight
                else: ft[sd_] = ((0.06 * hh0 * e, lean * 0.02 * hh0 * e, 0.07 * hh0 * e), 8 * e)                      # leading leg: bent forward
            return (0, 0, -0.02 * hh0 * e), Rp, ft
        return f
    def gait_fn(gt):
        return lambda t, T: gt.pose(t, T)
    out.update({'hover': (3.5, True, ik_clip(hover)), 'boost': (1.5, True, ik_clip(boost)), 'air': (2.0, True, ik_clip(air)),
                'land': (0.6, False, ik_clip(land, floor=False)), 'qb_l': (0.35, False, ik_clip(qb(+1))), 'qb_r': (0.35, False, ik_clip(qb(-1)))})
    for k, gt in gaits.items(): out[k] = (gt.T, True, gait_fn(gt))
    meta['hip_drop']['land'] = {'min': round(-LAND_D * hh0, 1), 'max': 0.0, 'down_t': round(0.16 * 0.6, 3)}
    # hip motion the script applies to both props: 16 samples over one cycle (loops: sample i at t = i/16 * length), one-shots 16 samples
    # from the first to the last frame (t = i/15 * length). z = vertical, y = lateral sway (model +Y).
    hc, sc_ = {}, {}
    for nm in ('walk', 'walk_back', 'strafe_l', 'strafe_r', 'run'):
        hc[nm] = list(gaits[nm].c16[0]); sc_[nm] = list(gaits[nm].c16[1])
    for nm in ('land', 'qb_l', 'qb_r'):
        T_, loop_, fn_ = out[nm]; T_ = round(T_ * FPS) / FPS
        ts = [i / 16 * T_ for i in range(16)] if loop_ else [i / 15 * T_ for i in range(16)]
        offs = [np.asarray(fn_(t_, T_)['_off'], float) for t_ in ts]
        hc[nm] = [round(float(o[2]), 2) for o in offs]; sc_[nm] = [round(float(o[1]), 2) for o in offs]
    meta['hip_curve'] = hc; meta['sway_curve'] = sc_
    info['meta'] = meta; info['gaits'] = gaits; info['land_dz'] = land_dz
    return out


def upper_clips(rig, info, linfo=None):
    """upper-body clips. Arms are posed by angles in the torso frame: shoulder pitch (+ forward), abduction (+ outward), elbow flexion
    (the forearm swings forward by that many degrees beyond the upper arm). No clip translates the torso: the hip motion of the
    locomotion cycles is the legs clips' hip_curve / sway_curve, which the script applies to both props."""
    names = rig.names
    ho = info.get('hand_only')
    # stance relative to each rig's own bind arm pose (the converter hangs the arms 20 degrees out): shoulder pitch forward, abduction,
    # and elbow flexion topped up to ~34 degrees of total bend (rigs whose bind arm is already bent keep it; AC arms have no elbow: wrist only)
    ST, PFB = {}, {}
    pitch_of = lambda v: math.degrees(math.atan2(v[0], -v[2]))          # forward angle from hanging straight down, in the sagittal plane
    for side in 'lr':
        ia, ib = rig.idx('arm_up_' + side), rig.idx('arm_lo_' + side)
        va, vb = unit(rig.vec[ia]), unit(rig.vec[ib])
        bend = math.degrees(math.acos(max(-1.0, min(1.0, float(va @ vb)))))
        pu, pf = pitch_of(va), pitch_of(vb); PFB[side] = pf
        sp0 = min(9.0 if not ho else 6.0, max(0.0, 45.0 - pu))
        el0 = (min(34.0, max(10.0, 34.0 - bend)) if not ho else 5.0)
        el0 = max(3.0, min(el0, 70.0 - pf - sp0))                       # rigs whose bind forearm already points forward keep their pose
        ST[side] = (sp0, 0.0, el0)
    info['elbow_bind'] = {s: round(math.degrees(math.acos(max(-1.0, min(1.0, float(unit(rig.vec[rig.idx('arm_up_' + s)]) @ unit(rig.vec[rig.idx('arm_lo_' + s)])))))), 1) for s in 'lr'}
    kel = 0.35 if ho else 1.0                  # AC arms: the 'elbow' is the wrist, keep its angles small

    def arms(Rt, ex):
        """ex: {side: (d_shoulder_pitch, d_elbow, d_abduction[, d_wrist])} in degrees on top of the stance (shoulder + elbow + hand
        rotate about their own joints: + pitch swings the arm forward, + elbow folds the forearm forward / up, + abduction swings it out)"""
        R = {'torso': Rt}
        for side in 'lr':
            sd = info['sd_' + side]
            e = ex.get(side, (0, 0, 0)); s0 = ST[side]
            sp = s0[0] + e[0]; ab = s0[1] + e[2]; el = s0[2] + e[1] * kel
            pa = PFB[side] + sp + el                                      # absolute forearm pitch: compressed above 84 degrees (never up past horizontal)
            if pa > 84.0: el = 84.0 + (pa - 84.0) * 0.25 - PFB[side] - sp
            Rup = Rt @ Rx(rad(sd * ab)) @ Ry(rad(-sp))
            Rlo = Rup @ Ry(rad(-el))
            R['arm_up_' + side] = Rup; R['arm_lo_' + side] = Rlo
            if 'arm_hand_' + side in names:
                R['arm_hand_' + side] = Rlo @ Ry(rad(-(e[3] if len(e) > 3 else 0.0)))
        return R

    def idle(t, T):
        ph = 2 * math.pi * t / T
        ex = {}
        for side in 'lr':
            q = ph + (0 if info['sd_' + side] > 0 else 0.9)
            ex[side] = (1.6 * math.sin(q), 2.5 * math.sin(q + 0.6), 0.8 * math.sin(q + 1.2), 3 * math.sin(q + 1.0))
        return arms(Ry(rad(0.8 * math.sin(ph))) @ Rx(rad(0.6 * math.sin(ph * 2 + 1))), ex)
    def fire(sidename):
        def f(t, T):
            e = env(t, T); e2 = env(t, T, 0.3)
            ex = {sidename: (-13 * e, 30 * e, 3 * e, -22 * e2)}                 # recoil: the shoulder kicks back, the elbow folds, the wrist whips
            o = 'l' if sidename == 'r' else 'r'; ex[o] = (-1.5 * e, 3 * e, 0, 0)
            return arms(Ry(rad(-2.5 * e)) @ Rz(rad((1.5 if sidename == 'l' else -1.5) * e)), ex)
        return f
    def fire_s(t, T):
        e = env(t, T); e2 = env(t, T, 0.3)
        k = (-8 * e, 18 * e, 2 * e, -14 * e2)
        return arms(Ry(rad(-6 * e)), {'l': k, 'r': k})
    def stagger(t, T):
        e = sine_env(t, T) ** 0.8
        shake = math.sin(2 * math.pi * 5 * t / T) * (1 - t / T)
        k = (-16 * e + 5 * shake, 22 * e, 8 * e, -10 * e)
        return arms(Ry(rad(-11 * e)) @ Rx(rad(4 * shake)) @ Rz(rad(5 * shake)), {'l': k, 'r': k})
    out = {'idle': (3.0, True, idle), 'fire_r': (0.25, False, fire('r')), 'fire_l': (0.25, False, fire('l')),
           'fire_s': (0.25, False, fire_s), 'stagger': (0.6, False, stagger)}
    gaits = (linfo or {}).get('gaits')
    if gaits:
        def sway(gt, Aw, Ae, nod, Ay=0.0):
            """Aw: shoulder swing (deg, counter to the legs, signed by the travel direction), Ae: elbow flex swing, Ay: lateral shoulder sway (strafes)"""
            mx = float(gt.m[0]); my = float(gt.m[1])
            def f(t, T):
                tau = (t / T) % 1.0
                dz, dy, roll, yaw = gt.pelvis(tau)
                ul = (tau + gt.p0) % 1.0
                ph = 2 * math.pi * ul
                c = math.cos(ph); c2 = math.cos(2 * ph)
                Rt = Rz(rad(-0.75 * yaw)) @ Rx(rad(-0.5 * roll)) @ Ry(rad(nod * (-dz / (0.12 * gt.hh0))))
                ex = {}
                for side, sg in (('l', 1.0), ('r', -1.0)):
                    sh = -sg * mx * Aw * c                                  # + forward; the arm opposite the forward foot goes forward
                    sh2 = -0.5 * Ay * (c2 + 0.3)                            # strafes: both shoulders rock at the step rate
                    # the elbow folds as the arm comes forward and opens as it goes back; peaks a little after the shoulder
                    el = (Ae * (-sg * mx * math.cos(ph - 0.5)) if abs(mx) > 0 else 0.0) + (Ae * 0.5 * (c2 - 0.2) if my else 0.0)
                    ab = -sg * my * Ay * 0.6 * c
                    wr = 0.5 * Ae * (-sg * mx * math.cos(ph - 1.1)) if abs(mx) > 0 else 0.0     # wrist follows through late
                    ex[side] = (sh + sh2, el, ab, wr)
                return arms(Rt, ex)
            return f
        out['walk_sway'] = (gaits['walk'].T, True, sway(gaits['walk'], 14.0, 9.0, 1.2))
        out['run_sway'] = (gaits['run'].T, True, sway(gaits['run'], 19.0, 13.0, 2.5))
        out['walk_back_sway'] = (gaits['walk_back'].T, True, sway(gaits['walk_back'], 9.0, 7.0, 0.8))
        out['strafe_l_sway'] = (gaits['strafe_l'].T, True, sway(gaits['strafe_l'], 0.0, 5.0, 0.8, Ay=5.0))
        out['strafe_r_sway'] = (gaits['strafe_r'].T, True, sway(gaits['strafe_r'], 0.0, 5.0, 0.8, Ay=5.0))
        ld = linfo['land_dz']
        def land_up(t, T):
            dz = ld(t, T); e = -dz / (0.22 * linfo['meta']['hh'])
            k = (-9 * e, 12 * e, 4 * e, -6 * e)
            return arms(Ry(rad(5 * e)), {'l': k, 'r': k})
        out['land'] = (0.6, False, land_up)
    return out

# ---------------------------------------------------------------- SMD / vmdl output
f5 = lambda v: '0' if abs(v) < 5e-6 else '%.5f' % v

def nodes_text(rig):
    return 'version 1\nnodes\n' + ''.join('%d "%s" %d\n' % (i, n, p) for i, (n, p) in enumerate(zip(rig.names, rig.par))) + 'end\n'

def frame_text(rig, locals_, t, offs=None):
    s = 'time %d\n' % t
    for i, R in enumerate(locals_):
        if rig.par[i] < 0:
            s += '%d 0 0 0 %s %s %s\n' % (i, f5(0), f5(0), f5(-math.pi / 2)); continue
        off = rig.pos[i] - rig.pos[rig.par[i]]
        if offs and rig.names[i] in offs: off = off + offs[rig.names[i]]
        e = euler_smd(R)
        s += '%d %s %s %s %s %s %s\n' % (i, f5(off[0]), f5(off[1]), f5(off[2]), f5(e[0]), f5(e[1]), f5(e[2]))
    return s

def header_text(rig):
    """nodes + bind skeleton (every bone at its bind rotation, root turned -90 degrees)"""
    return nodes_text(rig) + 'skeleton\n' + frame_text(rig, [np.eye(3)] * len(rig.names), 0) + 'end\ntriangles\n'

def anim_text(rig, fn, T, loop):
    n = int(round(T * FPS)); T = n / FPS
    cnt = n if loop else n + 1
    parts = [nodes_text(rig), 'skeleton\n']
    for k in range(cnt):
        R = fn(k / FPS, T)
        offs = {n[5:]: v for n, v in R.items() if n.startswith('_pos:')}
        parts.append(frame_text(rig, rig.fk_locals({n: v for n, v in R.items() if not n.startswith('_')}), k, offs))
    parts.append('end\n')
    return ''.join(parts), T


def anim_node(name, fade, loop, idle, src, subdir):
    return ('\t\t\t\t{\n\t\t\t\t\t_class = "AnimFile"\n\t\t\t\t\tname = "%s"\n\t\t\t\t\tis_default_idle_anim = %s\n\t\t\t\t\tactivity_name = ""\n\t\t\t\t\tactivity_weight = 1\n'
            '\t\t\t\t\tweight_list_name = ""\n\t\t\t\t\tfade_in_time = %s\n\t\t\t\t\tfade_out_time = %s\n\t\t\t\t\tlooping = %s\n\t\t\t\t\tdelta = false\n\t\t\t\t\tworldSpace = false\n'
            '\t\t\t\t\thidden = false\n\t\t\t\t\tanim_markup_ordered = false\n\t\t\t\t\tdisable_compression = false\n\t\t\t\t\tanimgraph_additive = false\n'
            '\t\t\t\t\tdelete_from_compiled_model = false\n\t\t\t\t\tsource_filename = "%s/anims/%s.smd"\n\t\t\t\t\timport_bone_scales = false\n'
            '\t\t\t\t\tstart_frame = -1\n\t\t\t\t\tend_frame = -1\n\t\t\t\t\tframerate = %.1f\n\t\t\t\t\treverse = false\n\t\t\t\t\tadditional_anim_files = [  ]\n\t\t\t\t},'
            % (name, 'true' if idle else 'false', fade, fade, 'true' if loop else 'false', subdir, src, float(FPS)))


def patch_vmdl(text, entries, subdir):
    blk = ('\t\t\t{\n\t\t\t\t_class = "BoneMarkupList"\n\t\t\t\tbone_cull_type = "None"\n\t\t\t},\n'
           '\t\t\t{\n\t\t\t\t_class = "AnimationList"\n\t\t\t\tchildren =\n\t\t\t\t[\n%s\n\t\t\t\t]\n\t\t\t\tdefault_root_bone_name = ""\n\t\t\t},\n'
           % '\n'.join(anim_node(n, fade, loop, idle, src, subdir) for n, fade, loop, idle, src in entries))
    key = '\t\t]\n\t\tmodel_archetype'
    if key not in text: raise RuntimeError('vmdl layout not recognised')
    text = text.replace(key, blk + key, 1)
    return text.replace('\t\tanim_graph_name = ""\n', '') if False else text

# ---------------------------------------------------------------- weights
def rig_weights(W, B, bone_to_rig, nrig, fallback):
    n = len(W); M = np.zeros((n, nrig))
    rows = np.arange(n)
    for k in range(B.shape[1]):
        np.add.at(M, (rows, bone_to_rig[B[:, k]]), W[:, k])
    s = M.sum(1); z = s < 1e-6
    M[z, fallback] = 1.0; s[z] = 1.0
    M /= s[:, None]
    top = np.argsort(-M, axis=1)[:, :3]
    out = np.zeros_like(M); np.put_along_axis(out, top, np.take_along_axis(M, top, 1), 1)
    out /= out.sum(1, keepdims=True)
    return out, top


def link_strings(Wt, top):
    res = []
    for w, tp in zip(Wt, top):
        pairs = [(int(b), float(w[b])) for b in tp if w[b] > 1e-4]
        pairs.sort(key=lambda p: -p[1])
        res.append((pairs[0][0], '%d %s' % (len(pairs), ' '.join('%d %.4f' % p for p in pairs))))
    return res

# ---------------------------------------------------------------- main entry
def animate_group(out, sub, mname, gname, P, Nn, UV, faces, W, B, bones, bone_ok, height, lod_files, warn, lod_cb=None):
    """Rewrites the group's SMDs as skinned, adds clips and the AnimationList. P/Nn/UV: final model-space arrays; faces [(smd material, (m,3) ids)];
    bones [{'name','parent','pos'}] in the same space; lod_files: LOD SMD file names (written by make_lods) to re-weight.
    Returns {'anims': [...], 'anim_len': {...}, 'family': ...} or None (the group stays a static prop; a note goes to warn())."""
    if gname not in ('legs', 'upper'): return None
    if not bone_ok or len(bones) < 3: warn('%s: no usable skeleton, static prop' % mname); return None
    bp = np.array([b['pos'] for b in bones], float)
    wi = waist_bone(bones)
    r, why = build_rig(gname, bones, bp, height, wi)
    if r is None: warn('%s: static prop (%s)' % (mname, why)); return None
    rig, smap, fallback, info = r
    info['style'] = STYLE.get(mname.rsplit('_', 1)[0]); info['stance_in'] = STANCE_IN.get(mname.rsplit('_', 1)[0], 0.0)
    # source bone -> rig bone through the nearest mapped ancestor
    b2r = np.full(len(bones), fallback)
    for i in range(len(bones)):
        j, hops = i, 0
        while j >= 0 and j not in smap and hops < 200: j = bones[j]['parent']; hops += 1
        if j in smap: b2r[i] = smap[j]
    Wt, top = rig_weights(W, B, b2r, len(rig.names), fallback)
    links = link_strings(Wt, top)
    if gname == 'legs':                      # how far each foot's mesh reaches toward the centre line (hover / boost keep the feet apart)
        gvv = np.unique(np.concatenate([F for _, F in faces]).ravel())
        info['foot_in'] = {}
        for sd_ in 'lr':
            nm = 'foot_' + sd_
            if nm not in rig.names: continue
            sel = gvv[top[gvv, 0] == rig.idx(nm)]
            if len(sel) < 10: continue
            y0 = rig.pos[rig.idx(nm)][1]; sg = info['sd_' + sd_]
            info['foot_in'][sd_] = float(y0 * sg - (P[sel][:, 1] * sg).min())
            x0 = rig.pos[rig.idx(nm)][0]
            info.setdefault('foot_x', {})[sd_] = (float(P[sel][:, 0].max() - x0), float(x0 - P[sel][:, 0].min()))     # reach past / behind the ankle
            if info.get('floor'):                # the foot mesh around its ankle (<= 600 points), for the floor clearance of the IK clips
                q = P[sel] - rig.pos[rig.idx(nm)]
                info.setdefault('foot_pts', {})[sd_] = q[::max(1, len(q) // 600)]
    if os.environ.get('IFR_RIGMAP'):                      # debug: which source bone feeds which rig bone (with its extent in model space)
        import json as _j
        dm = np.asarray(B)[np.arange(len(B)), np.asarray(W).argmax(1)]; rows = []; ing = np.zeros(len(P), bool); ing[np.unique(np.concatenate([F for _, F in faces]).ravel())] = True; dm = np.where(ing, dm, -1)
        for bi, b in enumerate(bones):
            sel = dm == bi
            if sel.any(): rows.append([bi, b['name'], bones[b['parent']]['name'] if b['parent'] >= 0 else '-', rig.names[b2r[bi]], int(sel.sum()), P[sel].min(0).round(0).tolist(), P[sel].max(0).round(0).tolist()])
        _j.dump(rows, open(os.path.join(os.environ['IFR_RIGMAP'], mname + '.json'), 'w'))
    d = os.path.join(out, sub)
    # bone-aware LODs: remake LOD1..4 from the still static LOD0 so no cluster spans two skin bones (else a far LOD bridges knee/shin/foot/other leg)
    lod_res = {}
    if lod_cb is not None:
        dom = np.concatenate([np.asarray([links[i][0] for i in F.ravel()], int).reshape(-1, 3) for _, F in faces])
        for k in range(1, 5):
            for ext in ('.smd', '.lab.npy'):
                fp = os.path.join(d, '%s_lod%dd%s' % (mname, k, ext))
                if os.path.exists(fp): os.remove(fp)
        counts_, notes_ = lod_cb(dom)
        lod_res = {'lod_counts': counts_, 'lod_notes': notes_}
        lod_files = [f for f in ('%s_lod%dd' % (mname, k) for k in range(1, 5)) if os.path.exists(os.path.join(d, f + '.smd'))]
    # LOD0 skinned reference
    gv = np.unique(np.concatenate([F for _, F in faces]).ravel())
    hdr = header_text(rig)
    lines = [hdr]
    for mat, F in faces:
        for f in F:
            lines.append(mat + '\n')
            for i in f:
                x, y, z = P[i]; nx, ny, nz = Nn[i]; pb, ls = links[i]
                lines.append('%d %.4f %.4f %.4f %.4f %.4f %.4f %.5f %.5f %s\n' % (pb, y, -x, z, ny, -nx, nz, UV[i, 0], 1 - UV[i, 1], ls))
    lines.append('end\n')
    open(os.path.join(d, mname + '.smd'), 'w', newline='\n').write(''.join(lines))
    # LODs: weights from the nearest LOD0 vertex
    if lod_files:
        from scipy.spatial import cKDTree
        Q = np.stack([P[gv][:, 1], -P[gv][:, 0], P[gv][:, 2]], 1); tree = cKDTree(Q)
        for lf in lod_files:
            fp = os.path.join(d, lf + '.smd')
            if not os.path.exists(fp): continue
            L = open(fp).read().split('\n')
            ti = L.index('triangles')
            body = L[ti + 1:]
            vi = [k for k, ln in enumerate(body) if ln.count(' ') >= 8 and ln[:1].isdigit()]
            xyz = np.array([[float(v) for v in body[k].split()[1:4]] for k in vi])
            labp = os.path.join(d, lf + '.lab.npy')
            lab = np.load(labp).reshape(-1) if os.path.exists(labp) else None
            if lab is not None and len(lab) != len(vi): lab = None
            if lab is None: _, nn = tree.query(xyz)
            else:                                                     # each corner takes the weights of the nearest LOD0 vertex owned by the same bone
                nn = np.zeros(len(xyz), int); dom0 = np.array([links[g][0] for g in gv])
                for bn in np.unique(lab):
                    sel = np.where(lab == bn)[0]; pool = np.where(dom0 == bn)[0]
                    if not len(pool): nn[sel] = tree.query(xyz[sel])[1]; continue
                    nn[sel] = pool[cKDTree(Q[pool]).query(xyz[sel])[1]]
            for k, q in zip(vi, nn):
                pb, ls = links[gv[q]]; p = body[k].split()
                body[k] = '%d %s %s' % (pb, ' '.join(p[1:9]), ls)
            open(fp, 'w', newline='\n').write(hdr.replace('\r', '') + '\n'.join(body))
            if os.path.exists(labp): os.remove(labp)
    # clips
    linfo = None
    if gname == 'legs':
        clips = legs_clips(info, rig); linfo = info
    else:
        r2, _why = build_rig('legs', bones, bp, height, wi)
        if r2 is not None:
            linfo = dict(r2[3]); linfo['style'] = STYLE.get(mname.rsplit('_', 1)[0]); linfo['stance_in'] = STANCE_IN.get(mname.rsplit('_', 1)[0], 0.0); legs_clips(linfo, r2[0])
        clips = upper_clips(rig, info, linfo)
    ad = os.path.join(d, 'anims'); os.makedirs(ad, exist_ok=True)
    entries, lens = [], {}
    for name, (T, loop, fn) in clips.items():
        txt, T2 = anim_text(rig, fn, T, loop)
        fname = '%s_%s' % (gname, name)
        open(os.path.join(ad, fname + '.smd'), 'w', newline='\n').write(txt)
        entries.append((name, 0.2 if loop else 0.15, loop, name == 'idle', fname)); lens[name] = round(T2, 4)
    if gname == 'legs': entries.append(('idle', 0.2, True, True, 'legs_hover'))   # prop_dynamic's default 'idle'
    vp = os.path.join(d, mname + '.vmdl')
    txt0 = open(vp).read()
    open(vp, 'w', newline=chr(10)).write(patch_vmdl(txt0, entries, sub))
    return {**lod_res, 'anims': list(clips), 'anim_len': lens, 'family': info['family'], 'rig': rig.names, 'meta': (linfo or {}).get('meta') if gname == 'legs' else None,
            'rig_pos': [p.round(1).tolist() for p in rig.pos], 'knee_sign': info.get('knee_sign')}
